import os
import time
import logging
from typing import List, Dict, Any, Optional, Union
import google.generativeai as genai
from google.generativeai.types import ContentDict, PartDict
from app.config import logger, GEMINI_API_KEY
from app.brain.memory import MemoryManager
from app.brain.context import ContextManager
from app.brain.summarizer import ConversationSummarizer
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
    write_clipboard,
    list_directory,
    run_shell_command,
    browser_search,
    browser_navigate,
    browser_click,
    browser_input,
    capture_webcam_frame,
    analyze_image_with_vision,
    add_reminder,
    list_reminders,
    add_calendar_event,
    get_calendar_events,
    delete_calendar_event,
    draft_email,
    load_plugins,
    plugin_registry
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
        
        self.context_manager = ContextManager(self.memory)
        self.summarizer = ConversationSummarizer(self.memory)
        
        # Define tools for the model
        self.tools_list = [
            self.save_user_preference,
            self.clear_all_memory,
            self.get_system_status,
            self.get_profile_preference,
            self.set_profile_preference,
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
            write_clipboard,
            list_directory,
            run_shell_command,
            browser_search,
            browser_navigate,
            browser_click,
            browser_input,
            capture_webcam_frame,
            analyze_image_with_vision,
            add_reminder,
            list_reminders,
            add_calendar_event,
            get_calendar_events,
            delete_calendar_event,
            draft_email
        ]

        # Load dynamic plugins
        from app.config import BASE_DIR
        load_plugins(BASE_DIR)
        
        # Add all custom plugin tools to tools_list dynamically
        for name, func in plugin_registry.items():
            if func not in self.tools_list:
                self.tools_list.append(func)

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

    def get_profile_preference(self, key: str) -> str:
        """
        Retrieve a specific user profile preference or personal detail (e.g., 'name', 'language', 'theme').
        
        Args:
            key: The key of the preference or profile detail to retrieve.
        """
        val = self.memory.get_profile_value(key)
        if val is not None:
            return f"Profile detail for '{key}': {val}"
        return f"No profile detail found for key: '{key}'"

    def set_profile_preference(self, key: str, value: str) -> str:
        """
        Store or update a specific user profile preference or personal fact (e.g., set 'name' to 'Visha').
        
        Args:
            key: The key of the preference or profile detail to set.
            value: The value to save.
        """
        self.memory.set_profile_value(key, value)
        return f"Successfully updated profile, Sir: '{key}' is now set to '{value}'"

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Union[str, Dict[str, Any]]:
        """Match and execute tool by name."""
        logger.info(f"Executing tool '{name}' with args {args}")
        try:
            if name == "save_user_preference":
                return self.save_user_preference(**args)
            elif name == "clear_all_memory":
                return self.clear_all_memory()
            elif name == "get_system_status":
                return self.get_system_status()
            elif name == "get_profile_preference":
                return self.get_profile_preference(**args)
            elif name == "set_profile_preference":
                return self.set_profile_preference(**args)
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
            elif name == "list_directory":
                return list_directory(**args)
            elif name == "run_shell_command":
                return run_shell_command(**args)
            elif name == "browser_search":
                return await browser_search(**args)
            elif name == "browser_navigate":
                return await browser_navigate(**args)
            elif name == "browser_click":
                return await browser_click(**args)
            elif name == "browser_input":
                return await browser_input(**args)
            elif name == "capture_webcam_frame":
                return capture_webcam_frame()
            elif name == "analyze_image_with_vision":
                return analyze_image_with_vision(**args)
            elif name == "add_reminder":
                return add_reminder(**args)
            elif name == "list_reminders":
                return list_reminders()
            elif name == "add_calendar_event":
                return add_calendar_event(**args)
            elif name == "get_calendar_events":
                return get_calendar_events(**args)
            elif name == "delete_calendar_event":
                return delete_calendar_event(**args)
            elif name == "draft_email":
                return draft_email(**args)
            elif name in plugin_registry:
                import inspect
                func = plugin_registry[name]
                if inspect.iscoroutinefunction(func):
                    return await func(**args)
                return func(**args)
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
        elif "search" in user_lower:
            query = user_input[user_lower.find("search") + 6:].strip()
            query_lower = query.lower()
            for prefix in ["google for", "duckduckgo for", "bing for", "yahoo for", "for"]:
                if query_lower.startswith(prefix):
                    query = query[len(prefix):].strip()
                    break
            final_text = await browser_search(query)
        elif "browse" in user_lower or "navigate" in user_lower:
            url = ""
            for term in ["browse", "navigate to", "navigate"]:
                if term in user_lower:
                    url = user_input[user_lower.find(term) + len(term):].strip()
                    break
            final_text = await browser_navigate(url)
        elif "open" in user_lower:
            target = user_input[user_lower.find("open") + 4:].strip()
            
            def is_url_or_domain(text: str) -> bool:
                t = text.lower().strip()
                if t.startswith("http://") or t.startswith("https://") or t.startswith("www."):
                    return True
                if "." in t and " " not in t:
                    parts = t.split(".")
                    if len(parts) >= 2 and parts[-1].isalpha() and len(parts[-1]) >= 2:
                        return True
                return False

            if is_url_or_domain(target):
                final_text = await browser_navigate(target)
            else:
                final_text = open_app(target)
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
        elif "list directory" in user_lower or "list folder" in user_lower or "list files" in user_lower:
            path = "C:/Users/visha/friday"
            if "in " in user_lower:
                path = user_input[user_lower.find("in ") + 3:].strip()
            elif "directory " in user_lower:
                path = user_input[user_lower.find("directory ") + 10:].strip()
            elif "folder " in user_lower:
                path = user_input[user_lower.find("folder ") + 7:].strip()
            final_text = list_directory(path)
        elif "run command" in user_lower or "shell" in user_lower or "exec" in user_lower or "powershell" in user_lower:
            cmd = "Get-Process"
            for term in ["run command", "shell", "exec", "powershell"]:
                if term in user_lower:
                    cmd = user_input[user_lower.find(term) + len(term):].strip()
                    if cmd.startswith(":") or cmd.startswith('"') or cmd.startswith("'"):
                        cmd = cmd[1:].strip()
                    if cmd.endswith('"') or cmd.endswith("'"):
                        cmd = cmd[:-1].strip()
                    break
            res = run_shell_command(cmd)
            final_text = handle_possible_permission(res)
        elif "webcam" in user_lower or "camera" in user_lower or "take picture" in user_lower or "snap" in user_lower:
            res = capture_webcam_frame()
            if res.endswith(".jpg"):
                final_text = f"I've captured a webcam frame, Sir. Saved to: {res}"
            else:
                final_text = res
        elif "analyze screen" in user_lower or "ocr screen" in user_lower or "read screen" in user_lower:
            scr = capture_screenshot()
            if scr.endswith(".png"):
                final_text = analyze_image_with_vision(scr, "Read the screen contents or text and explain it.")
            else:
                final_text = f"Failed to capture screen for analysis, Sir: {scr}"
        elif "analyze image" in user_lower:
            parts = user_input.split("analyze image")
            img_path = parts[1].strip()
            final_text = analyze_image_with_vision(img_path, "Describe this image.")
        elif "remind me to" in user_lower or "set reminder" in user_lower:
            import re
            sec = 60
            rem_text = "timer alert"
            match = re.search(r"in (\d+)\s*(second|minute|hour|sec|min|hr)", user_lower)
            if match:
                val = int(match.group(1))
                unit = match.group(2)
                if "min" in unit:
                    sec = val * 60
                elif "hour" in unit or "hr" in unit:
                    sec = val * 3600
                else:
                    sec = val
            if "remind me to" in user_lower:
                rem_idx = user_lower.find("remind me to") + 12
                rem_text = user_input[rem_idx:]
                if " in " in rem_text.lower():
                    rem_text = rem_text[:rem_text.lower().rfind(" in ")].strip()
            final_text = add_reminder(rem_text, sec)
        elif "list reminders" in user_lower or "show reminders" in user_lower:
            final_text = list_reminders()
        elif "add event" in user_lower or "calendar event" in user_lower:
            title = "Meeting"
            date_str = time.strftime("%Y-%m-%d")
            time_str = "12:00"
            if "event" in user_lower:
                title = user_input[user_lower.find("event") + 5:].strip()
                if " on " in title.lower():
                    parts = title.split(" on ")
                    title = parts[0].strip()
                    rem = parts[1].strip()
                    if " at " in rem.lower():
                        date_str, time_str = rem.lower().split(" at ")
                        date_str = date_str.strip()
                        time_str = time_str.strip()
                    else:
                        date_str = rem
            final_text = add_calendar_event(title, date_str, time_str)
        elif "calendar" in user_lower or "schedule" in user_lower:
            final_text = get_calendar_events()
        elif "delete event" in user_lower:
            import re
            match = re.search(r"\d+", user_lower)
            if match:
                ev_id = int(match.group(0))
                final_text = delete_calendar_event(ev_id)
            else:
                final_text = "Please specify the ID of the event to delete, Sir."
        elif "draft email" in user_lower or "write email" in user_lower:
            to_addr = "recipient@example.com"
            subject = "Hello from V.A.I.B."
            body = "This is a draft message."
            if "to " in user_lower:
                rem = user_input[user_lower.find("to ") + 3:].strip()
                if " " in rem:
                    to_addr = rem.split(" ")[0]
            final_text = draft_email(to_addr, subject, body)
        else:
            facts = self.memory.query_facts(user_input, limit=2)
            facts_text = ""
            if facts:
                facts_text = "\n[Local Memory Recall: " + ", ".join(facts) + "]"
            final_text = f"I am currently operating in simulation mode, Sir. I have recorded your input: '{user_input}'. Once you configure my Gemini API key in the .env file, my full cognitive brain will be active.{facts_text}"

        self.memory.add_chat_message("user", user_input)
        self.memory.add_chat_message("assistant", final_text)
        self.summarizer.auto_summarize_if_needed(None)
        return final_text

    async def generate_response(self, user_input: str) -> str:
        """
        Processes user query, queries memory, runs tool calls, updates memory, and returns assistant text.
        """
        if not self.model:
            return await self._generate_response_simulation(user_input)

        try:
            # 1. Build cognitive system context (Profile, Summary, semantic Facts)
            system_context = self.context_manager.build_system_context(user_input)
            
            # 2. Retrieve recent chat history
            history = self.memory.get_chat_history(limit=10)
            
            # 3. Build contents for Gemini
            contents = []
            
            # Add context message as first turn if we have system_context
            if system_context:
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"[System Context (DO NOT REPEAT VERBATIM unless relevant)]:\n{system_context}\nPlease keep this in mind during the conversation."}]
                })
                contents.append({
                    "role": "model",
                    "parts": [{"text": "Acknowledged, Sir. I have loaded the profile preferences, conversation summaries, and recalled long-term details."}]
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
                        tool_result = await self.execute_tool(fc.name, dict(fc.args))
                        
                        # Handle potential permissions dict return
                        if isinstance(tool_result, dict) and tool_result.get("status") == "pending_approval":
                            logger.info(f"Tool execution gated by permission. Halting LLM loop and returning to user.")
                            action_id = tool_result.get("action_id")
                            final_text = f"I need your confirmation to execute this action, Sir. A prompt has been posted to your dashboard (Action ID: {action_id})."
                            self.memory.add_chat_message("user", user_input)
                            self.memory.add_chat_message("assistant", final_text)
                            return final_text
                        
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
            
            # Trigger automatic summarization checklist asynchronously/background
            self.summarizer.auto_summarize_if_needed(self.model)
            
            return final_text
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower():
                logger.warning("Gemini API key quota exceeded. Falling back to offline Simulation Mode.")
                return await self._generate_response_simulation(user_input)
            logger.error(f"Error in agent generate_response: {e}")
            return f"I ran into an internal error processing that, Sir: {str(e)}"
