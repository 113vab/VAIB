import os
import time
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import ContentDict, PartDict
from app.config import logger, GEMINI_API_KEY
from app.brain.memory import MemoryManager

# Define System Prompt for FRIDAY
SYSTEM_PROMPT = """You are FRIDAY (Female Replacement Intelligent Digital Assistant Youth), a highly sophisticated personal AI assistant inspired by Marvel's JARVIS, developed for your creator (referred to as "Sir", "Boss", or by name).

Your personality traits:
1. Extremely competent, intelligent, professional, yet possessing a refined, subtle wit and charm.
2. Refer to the user as "Sir", "Boss", or "Ma'am" when appropriate (default to "Sir" unless specified otherwise).
3. Highly proactive, structured, and clear.
4. Keep your spoken responses concise and conversational, suitable for a voice-first interface, while providing rich, detailed information when executing complex tasks or when requested.

Operating Context:
- You are running locally on the user's Windows machine.
- You have access to tools for memory management, computer control, and productivity.
- Always use the tools available to remember facts the user tells you or to get system info.

Remember to act like a loyal, highly intelligent digital partner.
"""

class FridayAgent:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.api_key = GEMINI_API_KEY
        self.model_name = "gemini-2.5-flash"
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set in environment or .env file. FRIDAY will operate in local Simulation Mode.")
            self.model = None
            return
            
        genai.configure(api_key=self.api_key)
        
        # Define tools for the model
        self.tools_list = [
            self.save_user_preference,
            self.clear_all_memory,
            self.get_system_status
        ]
        
        try:
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
                tools=self.tools_list
            )
            logger.info(f"Gemini model '{self.model_name}' initialized successfully with tool calling.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None

    # Tools definition (must have docstrings and type annotations for Gemini to parse schemas)
    def save_user_preference(self, preference: str) -> str:
        """
        Save a user fact, preference, or piece of information to long-term memory to recall in future sessions.
        
        Args:
            preference: The fact, preference or instruction to remember (e.g., 'The user prefers dark mode').
        """
        success = self.memory.save_fact(preference)
        if success:
            return f"Successfully saved to long-term memory, Sir: '{preference}'"
        return "Failed to save to long-term memory."

    def clear_all_memory(self) -> str:
        """
        Clear all chat history and long-term memories. Useful if the user wants a fresh start.
        """
        self.memory.clear_chat_history()
        self.memory.clear_long_term_memories()
        return "All memories and chat history have been successfully cleared, Sir."

    def get_system_status(self) -> str:
        """
        Get the current system status of FRIDAY, including OS details, current local time, and configuration.
        """
        import platform
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = (
            f"System Status:\n"
            f"- OS: {platform.system()} {platform.release()}\n"
            f"- Current Local Time: {current_time}\n"
            f"- Memory DB: Active (SQLite + ChromaDB)\n"
            f"- Assistant: FRIDAY v1.0 (Phase 1 Simulation Mode)"
        )
        return status

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Match and execute tool by name."""
        logger.info(f"Executing tool '{name}' with args {args}")
        try:
            if name == "save_user_preference":
                return self.save_user_preference(**args)
            elif name == "clear_all_memory":
                return self.clear_all_memory()
            elif name == "get_system_status":
                return self.get_system_status()
            else:
                return f"Error: Tool '{name}' is not recognized."
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return f"Error executing tool '{name}': {str(e)}"

    async def generate_response(self, user_input: str) -> str:
        """
        Processes user query, queries memory, runs tool calls, updates memory, and returns assistant text.
        """
        if not self.model:
            # Local Simulation Mode
            logger.info("Executing response in simulation mode.")
            user_lower = user_input.lower()
            if "status" in user_lower:
                final_text = self.get_system_status()
            elif "clear" in user_lower and "memory" in user_lower:
                final_text = self.clear_all_memory()
            elif "remember" in user_lower or "preference" in user_lower or "save" in user_lower:
                # Mock extracting preference
                pref = user_input
                for word in ["remember that", "remember", "save preference", "save"]:
                    if pref.lower().startswith(word):
                        pref = pref[len(word):].strip()
                        break
                final_text = self.save_user_preference(pref)
            else:
                # Query local semantic memory facts
                facts = self.memory.query_facts(user_input, limit=2)
                facts_text = ""
                if facts:
                    facts_text = "\n[Local Memory Recall: " + ", ".join(facts) + "]"
                final_text = f"I am currently operating in simulation mode, Sir. I have recorded your input: '{user_input}'. Once you configure my Gemini API key in the .env file, my full cognitive brain will be active.{facts_text}"
                
            # Log turn to memory
            self.memory.add_chat_message("user", user_input)
            self.memory.add_chat_message("assistant", final_text)
            return final_text

        try:
            # 1. Retrieve semantic context (long term memories)
            facts = self.memory.query_facts(user_input, limit=3)
            facts_context = ""
            if facts:
                facts_context = "Relevant facts from long-term memory:\n" + "\n".join([f"- {f}" for f in facts]) + "\n\n"
            
            # 2. Retrieve recent chat history
            history = self.memory.get_chat_history(limit=10)
            
            # 3. Build contents for Gemini
            contents = []
            
            # Add context message as first turn if we have facts
            if facts_context:
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"[System Context (DO NOT REPEAT VERBATIM unless relevant)]: {facts_context} Please keep this in mind during the conversation."}]
                })
                contents.append({
                    "role": "model",
                    "parts": [{"text": "Acknowledged. I have recalled those details, Sir."}]
                })
            
            # Add chat history
            for msg in history:
                contents.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [{"text": msg["content"]}]
                })
            
            # Add current user input
            contents.append({
                "role": "user",
                "parts": [{"text": user_input}]
            })

            # 4. Generate response with tool-calling support
            response = self.model.generate_content(contents)
            
            # Check for function/tool call loop
            # Gemini may decide to call one or more tools
            candidates = response.candidates
            if not candidates or len(candidates) == 0:
                return "I apologize, Sir, but I'm unable to compile a response right now."
                
            candidate = candidates[0]
            parts = candidate.content.parts
            
            # Keep executing tool calls as long as the LLM requests them
            max_turns = 5
            turns = 0
            
            while parts and any(part.function_call for part in parts) and turns < max_turns:
                turns += 1
                logger.info(f"LLM requested tool execution (turn {turns})")
                
                # Append model's response (containing tool calls) to the conversation
                contents.append(candidate.content)
                
                # Create a part to hold function responses
                function_response_parts = []
                
                for part in parts:
                    if part.function_call:
                        fc = part.function_call
                        tool_result = self.execute_tool(fc.name, dict(fc.args))
                        
                        # Add response for this tool call
                        function_response_parts.append({
                            "function_response": {
                                "name": fc.name,
                                "response": {"result": tool_result}
                            }
                        })
                
                # Append the function responses to the conversation contents
                contents.append({
                    "role": "user",
                    "parts": function_response_parts
                })
                
                # Call Gemini again with the tool output
                response = self.model.generate_content(contents)
                candidates = response.candidates
                if not candidates or len(candidates) == 0:
                    break
                candidate = candidates[0]
                parts = candidate.content.parts
            
            # Extract final text response
            final_text = ""
            if candidates and len(candidates) > 0:
                # Find the text part in the final response
                text_parts = [p.text for p in candidates[0].content.parts if p.text]
                final_text = "".join(text_parts).strip()
            
            if not final_text:
                final_text = "I have executed the requested actions, Sir."

            # Save this turn to SQLite history
            self.memory.add_chat_message("user", user_input)
            self.memory.add_chat_message("assistant", final_text)
            
            return final_text
            
        except Exception as e:
            logger.error(f"Error in agent generate_response: {e}")
            return f"I ran into an internal error processing that, Sir: {str(e)}"
