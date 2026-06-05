import os
import time
import logging
import abc
import inspect
import re
import json
from typing import List, Dict, Any, AsyncIterator, Union, Optional
import httpx
import google.generativeai as genai

from app.config import logger

# Load the system prompt to maintain persona across providers
# We import it inside the methods to prevent circular import loops

def function_to_openai_tool(func) -> dict:
    """Converts a Python function docstring and type annotations into OpenAI Tool schema."""
    name = func.__name__
    doc = func.__doc__ or ""
    
    # Extract description
    description = ""
    lines = [line.strip() for line in doc.split("\n") if line.strip()]
    if lines:
        description = lines[0]
        
    sig = inspect.signature(func)
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        if param_name in ["self", "cls"]:
            continue
        
        # Translate Python types to JSON Schema types
        param_type = "string"
        if param.annotation == int:
            param_type = "integer"
        elif param.annotation == float:
            param_type = "number"
        elif param.annotation == bool:
            param_type = "boolean"
        elif param.annotation == list:
            param_type = "array"
        elif param.annotation == dict:
            param_type = "object"
            
        param_desc = ""
        # Search for parameter description inside docstring
        for line in lines:
            match = re.search(rf"\b{param_name}\s*:\s*(.*)", line)
            if match:
                param_desc = match.group(1).strip()
                break
                
        properties[param_name] = {
            "type": param_type,
            "description": param_desc or f"Parameter {param_name}"
        }
        
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
            
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


class LLMProvider(abc.ABC):
    def __init__(self, model_name: str, tools: list):
        self.model_name = model_name
        self.tools = tools
        self.last_health_check = 0.0
        self.health_cache = False
        self.cache_ttl = 60.0 # Cache health status for 60 seconds

    async def is_healthy(self) -> bool:
        """Dynamic health check with caching to prevent latency on every turn."""
        current_time = time.time()
        if current_time - self.last_health_check < self.cache_ttl:
            return self.health_cache
            
        self.last_health_check = current_time
        try:
            self.health_cache = await self._check_health()
        except Exception as e:
            logger.warning(f"Health check failed for {self.__class__.__name__}: {e}")
            self.health_cache = False
            
        return self.health_cache

    @abc.abstractmethod
    async def _check_health(self) -> bool:
        """Internal provider specific check."""
        pass

    @abc.abstractmethod
    async def generate_response(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any],
        execute_tool_callback
    ) -> str:
        pass

    @abc.abstractmethod
    async def generate_response_stream(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any]
    ) -> AsyncIterator[str]:
        pass


class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str, tools: list):
        super().__init__(model_name or "gemini-2.5-flash", tools)
        import app.config as config
        self.api_key = config.GEMINI_API_KEY
        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            from app.brain.agent import SYSTEM_PROMPT
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
                tools=tools
            )

    async def _check_health(self) -> bool:
        if not self.api_key or not self.model:
            return False
        # Fast query execution test (max 1 output token to save cost/latency)
        def ping():
            resp = self.model.generate_content("ping", generation_config={"max_output_tokens": 1})
            return bool(resp)
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, ping)

    async def generate_response(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any],
        execute_tool_callback
    ) -> str:
        if not self.model:
            raise RuntimeError("Gemini model not initialized")

        # 1. Format contents payload for Gemini SDK
        contents = []
        if system_context:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System Context (DO NOT REPEAT VERBATIM unless relevant)]:\n{system_context}\nPlease keep this in mind during the conversation."}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Acknowledged, Sir. I have loaded the profile preferences, conversation summaries, and recalled long-term details."}]
            })

        for msg in history:
            contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": user_input}]
        })

        # 2. Tool calling loop
        response = self.model.generate_content(contents)
        candidates = response.candidates
        if not candidates or len(candidates) == 0:
            return "I apologize, Sir, but I'm unable to compile a response right now."

        candidate = candidates[0]
        parts = candidate.content.parts
        max_turns = 5
        turns = 0

        while parts and any(part.function_call for part in parts) and turns < max_turns:
            turns += 1
            logger.info(f"Gemini LLM requested tool execution (turn {turns})")
            contents.append(candidate.content)
            function_response_parts = []

            for part in parts:
                if part.function_call:
                    fc = part.function_call
                    tool_result = await execute_tool_callback(fc.name, dict(fc.args))

                    # Halting permission trigger
                    if isinstance(tool_result, dict) and tool_result.get("status") == "pending_approval":
                        action_id = tool_result.get("action_id")
                        return f"I need your confirmation to execute this action, Sir. A prompt has been posted to your dashboard (Action ID: {action_id})."

                    tool_result_str = str(tool_result)
                    function_response_parts.append({
                        "function_response": {
                            "name": fc.name,
                            "response": {"result": tool_result_str}
                        }
                    })

            contents.append({
                "role": "user",
                "parts": function_response_parts
            })

            response = self.model.generate_content(contents)
            candidates = response.candidates
            if not candidates or len(candidates) == 0:
                break
            candidate = candidates[0]
            parts = candidate.content.parts

        final_text = ""
        if candidates and len(candidates) > 0:
            text_parts = [p.text for p in candidates[0].content.parts if p.text]
            final_text = "".join(text_parts).strip()

        return final_text or "I have executed the requested actions, Sir."

    async def generate_response_stream(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any]
    ) -> AsyncIterator[str]:
        # Minimal placeholder stream (not full duplex yet)
        if not self.model:
            yield "Gemini API offline"
            return
        
        # Build contents
        contents = [{"role": "user", "content": user_input}]
        resp = self.model.generate_content(contents, stream=True)
        for chunk in resp:
            if chunk.text:
                yield chunk.text


class OpenAICompatibleProvider(LLMProvider):
    """Base class for Groq, DeepSeek, and Ollama since they share OpenAI REST formats."""
    def __init__(self, model_name: str, tools: list, url: str, api_key: str):
        super().__init__(model_name, tools)
        self.url = url
        self.api_key = api_key

    async def _check_health(self) -> bool:
        if not self.api_key and "localhost" not in self.url:
            return False
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, headers=headers, timeout=5.0)
                return resp.status_code == 200
        except Exception:
            return False

    async def generate_response(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any],
        execute_tool_callback
    ) -> str:
        from app.brain.agent import SYSTEM_PROMPT
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n[System Context]:\n{system_context}"}
        ]
        
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
            
        messages.append({"role": "user", "content": user_input})
        openai_tools = [function_to_openai_tool(t) for t in tools]

        async with httpx.AsyncClient() as client:
            turns = 0
            max_turns = 5
            
            while turns < max_turns:
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "tools": openai_tools,
                    "tool_choice": "auto" if openai_tools else None
                }
                
                resp = await client.post(self.url, json=payload, headers=headers, timeout=60.0)
                if resp.status_code != 200:
                    raise RuntimeError(f"API request failed with {resp.status_code}: {resp.text}")
                    
                resp_json = resp.json()
                choice = resp_json["choices"][0]
                message = choice["message"]
                
                # Append response message to conversation state
                messages.append(message)
                
                tool_calls = message.get("tool_calls")
                if not tool_calls:
                    return message.get("content") or "I have executed the action, Sir."

                turns += 1
                for tc in tool_calls:
                    func = tc["function"]
                    name = func["name"]
                    args = json.loads(func["arguments"] or "{}")
                    
                    tool_result = await execute_tool_callback(name, args)
                    
                    # Interruption check
                    if isinstance(tool_result, dict) and tool_result.get("status") == "pending_approval":
                        action_id = tool_result.get("action_id")
                        return f"I need your confirmation to execute this action, Sir. A prompt has been posted to your dashboard (Action ID: {action_id})."
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": str(tool_result)
                    })

        return "I completed tool runs but received no final content response, Sir."

    async def generate_response_stream(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any]
    ) -> AsyncIterator[str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        messages = [{"role": "user", "content": user_input}]
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", self.url, json=payload, headers=headers, timeout=30.0) as resp:
                if resp.status_code != 200:
                    yield f"Error: API returned {resp.status_code}"
                    return
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            token = data_json["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except Exception:
                            pass


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, model_name: str, tools: list):
        # Default model is Groq llama-3.3-70b-versatile
        import app.config as config
        super().__init__(
            model_name=model_name or "llama-3.3-70b-versatile",
            tools=tools,
            url="https://api.groq.com/openai/v1/chat/completions",
            api_key=config.GROQ_API_KEY
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, model_name: str, tools: list):
        # Default model is deepseek-chat
        import app.config as config
        super().__init__(
            model_name=model_name or "deepseek-chat",
            tools=tools,
            url="https://api.deepseek.com/v1/chat/completions",
            api_key=config.DEEPSEEK_API_KEY
        )


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, model_name: str, tools: list):
        # Ollama host endpoint is structured via standard v1 paths
        # Model defaults to llama3
        import app.config as config
        host = config.OLLAMA_HOST.rstrip("/")
        super().__init__(
            model_name=model_name or "llama3",
            tools=tools,
            url=f"{host}/v1/chat/completions",
            api_key=""
        )


class LLMProviderRouter:
    def __init__(self, provider: str, model_name: str, tools: list):
        self.preferred_provider_name = provider.lower()
        self.model_name = model_name
        self.tools = tools
        
        # Initialize providers
        self.providers = {
            "gemini": GeminiProvider(model_name if provider.lower() == "gemini" else None, tools),
            "groq": GroqProvider(model_name if provider.lower() == "groq" else None, tools),
            "deepseek": DeepSeekProvider(model_name if provider.lower() == "deepseek" else None, tools),
            "ollama": OllamaProvider(model_name if provider.lower() == "ollama" else None, tools)
        }

    def get_active_model_for_summarizer(self) -> Optional[genai.GenerativeModel]:
        """Provides the GenerativeModel reference for the summarization loop if Gemini is active."""
        gemini = self.providers.get("gemini")
        if isinstance(gemini, GeminiProvider):
            return gemini.model
        return None

    async def generate_response(
        self,
        system_context: str,
        history: List[Dict[str, str]],
        user_input: str,
        tools: List[Any],
        execute_tool_callback
    ) -> str:
        # Fallback chain: Gemini -> Groq -> DeepSeek -> Ollama -> Simulation
        fallback_order = ["gemini", "groq", "deepseek", "ollama"]
        
        # Re-order checklist starting from the preferred provider
        search_list = []
        if self.preferred_provider_name in fallback_order:
            search_list.append(self.preferred_provider_name)
        for p in fallback_order:
            if p not in search_list:
                search_list.append(p)
            
        for prov_name in search_list:
            prov = self.providers[prov_name]
            if await prov.is_healthy():
                try:
                    logger.info(f"Provider Router: Routing request to active provider '{prov_name}'...")
                    response = await prov.generate_response(
                        system_context, history, user_input, tools, execute_tool_callback
                    )
                    return response
                except Exception as e:
                    logger.warning(f"Active provider '{prov_name}' failed during generation execution: {e}. Cascading fallback...")

        # Fallback to offline Simulation mode if all providers fail
        logger.warning("All LLM providers are unhealthy or failed during execution. Cascading fallback to Simulation Mode.")
        return await self._generate_response_simulation(user_input)

    async def _generate_response_simulation(self, user_input: str) -> str:
        """Simulation fallback if all configured providers are offline."""
        # Grab static facts from long term memories if possible
        facts_text = ""
        # Look for facts in the tools list self preferences
        try:
            from app.brain.memory import MemoryManager
            mem = MemoryManager()
            facts = mem.get_all_facts()
            if facts:
                facts_text = "\n[Local Memory Recall: " + ", ".join([f["fact"] for f in facts[:3]]) + "]"
        except Exception:
            pass
            
        return f"I am currently operating in offline Simulation Mode, Sir. I have recorded your input: '{user_input}'. Please check API key configurations.{facts_text}"
