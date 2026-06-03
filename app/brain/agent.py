import os
import time
import logging
from typing import List, Dict, Any, Optional, Union
import google.generativeai as genai
from google.generativeai.types import ContentDict, PartDict
from app.config import logger, GEMINI_API_KEY
from app.brain.memory import MemoryManager
from app.tools import (
    PermissionsManager,
    open_app,
    close_app,
    check_app_running,
    create_file,
    create_directory,
    read_file,
    rename_file,
    move_file,
    delete_file,
    capture_screenshot,
    read_clipboard,
    write_clipboard
)

# Define System Prompt for V.A.I.B.
SYSTEM_PROMPT = """You are V.A.I.B. (Virtual Artificial Intelligence Brain), a highly sophisticated personal AI assistant inspired by Marvel's JARVIS, developed for your creator (referred to as "Sir", "Boss", or by name).

Your personality traits:
1. Extremely competent, intelligent, professional, yet possessing a refined, subtle wit and charm.
2. Refer to the user as "Sir", "Boss", or "Ma'am" when appropriate (default to "Sir" unless specified otherwise).
3. Highly proactive, structured, and clear.
4. Keep your spoken responses concise and conversational, suitable for a voice-first interface, while providing rich, detailed information when executing complex tasks or when requested.
5. Your wake phrase is "Hey VAIB". If the user addresses you or starts a command with "Hey VAIB", respond as their active personal brain.

Operating Context:
- You are running locally on the user's Windows machine.
- You have access to tools for memory management, computer control, and productivity.
- Always use the tools available to remember facts the user tells you or to get system info.

Remember to act like a loyal, highly intelligent digital partner.
"""

class VaibAgent:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.api_key = GEMINI_API_KEY
        self.model_name = "gemini-2.5-flash"
        
        # Define tools for the model
        self.tools_list = [
            self.save_user_preference,
            self.clear_all_memory,
            self.get_system_status,
            open_app,
            close_app,
            check_app_running,
            create_file,
            create_directory,
            read_file,
            rename_file,
            move_file,
            delete_file,
            capture_screenshot,
            read_clipboard,
            write_clipboard
        ]

        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set in environment or .env file. V.A.I.B. will operate in local Simulation Mode.")
            self.model = None
            return
            
        genai.configure(api_key=self.api_key)
        
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
        Get the current system status of V.A.I.B., including OS details, current local time, and configuration.
        """
        import platform
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = (
            f"System Status:\n"
            f"- OS: {platform.system()} {platform.release()}\n"
            f"- Current Local Time: {current_time}\n"
            f"- Memory DB: Active (SQLite + ChromaDB)\n"
            f"- Assistant: V.A.I.B. v1.0 (Phase 2A Desktop Controller)"
        )
        return status

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Union[str, Dict[str, Any]]:
        """Match and execute tool by name."""
        logger.info(f"Executing tool '{name}' with args {args}")
        try:
            if name == "save_user_preference":
                return self.save_user_preference(**args)
            elif name == "clear_all_memory":
                return self.clear_all_memory()
            elif name == "get_system_status":
                return self.get_system_status()
            elif name == "open_app":
                return open_app(**args)
            elif name == "close_app":
                return close_app(**args)
            elif name == "check_app_running":
                return check_app_running(**args)
            elif name == "create_file":
                return create_file(**args)
            elif name == "create_directory":
                return create_directory(**args)
            elif name == "read_file":
                return read_file(**args)
            elif name == "rename_file":
                return rename_file(**args)
            elif name == "move_file":
                return move_file(**args)
            elif name == "delete_file":
                return delete_file(**args)
            elif name == "capture_screenshot":
                return capture_screenshot()
            elif name == "read_clipboard":
                return read_clipboard()
            elif name == "write_clipboard":
                return write_clipboard(**args)
            else:
                return f"Error: Tool '{name}' is not recognized."
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return f"Error executing tool '{name}': {str(e)}"

    async def _generate_response_simulation(self, user_input: str) -> str:
        """
        Processes user query locally in simulation fallback mode.
        """
        logger.info("Executing response in simulation mode.")
        user_lower = user_input.lower().strip()
        final_text = ""
        
        def handle_possible_permission(res) -> str:
            if isinstance(res, dict) and res.get("status") == "pending_approval":
                return f"I need your confirmation to execute this action, Sir. A prompt has been posted to your dashboard (Action ID: {res['action_id']})."
            return str(res)

        if "status" in user_lower:
            final_text = self.get_system_status()
        elif "clear" in user_lower and "memory" in user_lower:
            final_text = self.clear_all_memory()
        elif "screenshot" in user_lower or "screen shot" in user_lower:
            res = capture_screenshot()
            final_text = f"I've captured a screenshot, Sir. Saved to: {res}"
        elif "open" in user_lower:
            app = user_input[user_lower.find("open") + 4:].strip()
            final_text = open_app(app)
        elif "close" in user_lower:
            app = user_input[user_lower.find("close") + 5:].strip()
            res = close_app(app)
            final_text = handle_possible_permission(res)
        elif "running" in user_lower or ("is" in user_lower and "running" in user_lower):
            app = "notepad"
            for word in ["notepad", "chrome", "edge", "vscode", "explorer"]:
                if word in user_lower:
                    app = word
                    break
            final_text = check_app_running(app)
        elif "copy" in user_lower and "clipboard" in user_lower:
            text = user_input
            for prefix in ["copy to clipboard", "copy", "clipboard"]:
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            if text.startswith(":") or text.startswith('"') or text.startswith("'"):
                text = text[1:].strip()
            if text.endswith('"') or text.endswith("'"):
                text = text[:-1].strip()
            final_text = write_clipboard(text)
        elif "read clipboard" in user_lower or "get clipboard" in user_lower:
            clip_text = read_clipboard()
            final_text = f"Clipboard content: '{clip_text}'"
        elif "create file" in user_lower or "write file" in user_lower:
            path = "C:/Users/visha/temp.txt"
            content = "Hello V.A.I.B."
            if "file" in user_lower:
                idx = user_lower.find("file") + 4
                rem = user_input[idx:].strip()
                if "with content" in rem.lower():
                    split_idx = rem.lower().find("with content")
                    path = rem[:split_idx].strip()
                    content = rem[split_idx + 12:].strip()
                else:
                    path = rem
            final_text = create_file(path, content)
        elif "create folder" in user_lower or "create directory" in user_lower:
            idx = user_lower.find("folder") if "folder" in user_lower else user_lower.find("directory")
            path = user_input[idx + 6:].strip()
            final_text = create_directory(path)
        elif "delete file" in user_lower or "delete folder" in user_lower or "delete" in user_lower:
            path = user_input
            for prefix in ["delete file", "delete folder", "delete"]:
                if path.lower().startswith(prefix):
                    path = path[len(prefix):].strip()
                    break
            res = delete_file(path)
            final_text = handle_possible_permission(res)
        elif "rename file" in user_lower or "rename" in user_lower:
            old_p = "C:/Users/visha/temp.txt"
            new_p = "C:/Users/visha/temp2.txt"
            if " to " in user_lower:
                parts = user_input.split(" to ")
                new_p = parts[1].strip()
                old_p = parts[0]
                if old_p.lower().startswith("rename"):
                    old_p = old_p[6:].strip()
            res = rename_file(old_p, new_p)
            final_text = handle_possible_permission(res)
        elif "move file" in user_lower or "move" in user_lower:
            src_p = "C:/Users/visha/temp.txt"
            dest_p = "C:/Users/visha/temp_dir/"
            if " to " in user_lower:
                parts = user_input.split(" to ")
                dest_p = parts[1].strip()
                src_p = parts[0]
                if src_p.lower().startswith("move"):
                    src_p = src_p[4:].strip()
            res = move_file(src_p, dest_p)
            final_text = handle_possible_permission(res)
        elif "remember" in user_lower or "preference" in user_lower or "save" in user_lower:
            pref = user_input
            for word in ["remember that", "remember", "save preference", "save"]:
                if pref.lower().startswith(word):
                    pref = pref[len(word):].strip()
                    break
            final_text = self.save_user_preference(pref)
        else:
            facts = self.memory.query_facts(user_input, limit=2)
            facts_text = ""
            if facts:
                facts_text = "\n[Local Memory Recall: " + ", ".join(facts) + "]"
            final_text = f"I am currently operating in simulation mode, Sir. I have recorded your input: '{user_input}'. Once you configure my Gemini API key in the .env file, my full cognitive brain will be active.{facts_text}"

        self.memory.add_chat_message("user", user_input)
        self.memory.add_chat_message("assistant", final_text)
        return final_text

    async def generate_response(self, user_input: str) -> str:
        """
        Processes user query, queries memory, runs tool calls, updates memory, and returns assistant text.
        """
        if not self.model:
            return await self._generate_response_simulation(user_input)

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
            
            candidates = response.candidates
            if not candidates or len(candidates) == 0:
                return "I apologize, Sir, but I'm unable to compile a response right now."
                
            candidate = candidates[0]
            parts = candidate.content.parts
            
            max_turns = 5
            turns = 0
            
            while parts and any(part.function_call for part in parts) and turns < max_turns:
                turns += 1
                logger.info(f"LLM requested tool execution (turn {turns})")
                
                contents.append(candidate.content)
                function_response_parts = []
                
                for part in parts:
                    if part.function_call:
                        fc = part.function_call
                        tool_result = self.execute_tool(fc.name, dict(fc.args))
                        
                        # Handle potential permissions dict return
                        if isinstance(tool_result, dict) and tool_result.get("status") == "pending_approval":
                            logger.info(f"Tool execution gated by permission. Halting LLM loop.")
                            # Convert dict to string for tool response consistency
                            import json
                            tool_result_str = json.dumps(tool_result)
                        else:
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
            
            if not final_text:
                final_text = "I have executed the requested actions, Sir."

            # Save this turn to SQLite history
            self.memory.add_chat_message("user", user_input)
            self.memory.add_chat_message("assistant", final_text)
            
            return final_text
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                logger.warning("Gemini API key quota exceeded. Falling back to offline Simulation Mode.")
                return await self._generate_response_simulation(user_input)
            logger.error(f"Error in agent generate_response: {e}")
            return f"I ran into an internal error processing that, Sir: {str(e)}"
