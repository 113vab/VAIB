import time
import json
import logging
import sqlite3
import threading
from typing import List, Dict, Any, Optional

from app.brain.memory import MemoryManager
from app.tools.permissions import PermissionsManager

logger = logging.getLogger("vaib")

class GoalPlanner:
    """Handles goal decomposition and reflection using LLM or offline simulation."""
    def __init__(self, agent):
        self.agent = agent

    def decompose(self, goal: str) -> List[Dict[str, Any]]:
        """Decompose a high-level goal into steps using Gemini (or simulated rules if offline)."""
        if not self.agent or not self.agent.model:
            return self._decompose_simulated(goal)
            
        # Compile list of tools with their docstrings
        tools_list = []
        for tool in self.agent.tools_list:
            name = getattr(tool, "__name__", str(tool))
            doc = getattr(tool, "__doc__", "")
            # Clean docstring
            doc = " ".join([line.strip() for line in doc.split("\n") if line.strip()])
            tools_list.append(f"- {name}: {doc}")
        tools_str = "\n".join(tools_list)
        
        prompt = f"""You are a professional task decomposition and planning agent.
Your goal is to break down the following user goal into a sequence of concrete tool executions:
Goal: "{goal}"

Available Tools:
{tools_str}

Respond ONLY with a valid JSON array of objects representing the plan. Do NOT include markdown fences, comments, or extra text.
Each object in the JSON array must follow this schema:
{{
  "step_number": <int>,
  "description": "<detailed description of what this step does>",
  "tool_name": "<the exact name of the tool to run>",
  "tool_args": {{ <arguments for the tool> }}
}}
"""
        try:
            response = self.agent.model.generate_content(prompt)
            text = response.text.strip()
            # Clean markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            
            steps = json.loads(text)
            if isinstance(steps, list):
                return steps
            elif isinstance(steps, dict) and "steps" in steps:
                return steps["steps"]
        except Exception as e:
            logger.error(f"Failed to decompose goal using Gemini: {e}. Falling back to simulation.")
            
        return self._decompose_simulated(goal)

    def _decompose_simulated(self, goal: str) -> List[Dict[str, Any]]:
        """Simulate goal decomposition for testing or offline usage."""
        goal_lower = goal.lower()
        steps = []
        
        # Scenario 1: Search and save
        if "search" in goal_lower and ("write" in goal_lower or "save" in goal_lower or "file" in goal_lower):
            steps.append({
                "step_number": 1,
                "description": "Perform web search for information",
                "tool_name": "browser_search",
                "tool_args": {"query": "V.A.I.B. AI assistant updates"}
            })
            steps.append({
                "step_number": 2,
                "description": "Save search results to a local file",
                "tool_name": "create_file",
                "tool_args": {
                    "file_path": "vaib_search_results.txt",
                    "content": "Simulated search results: V.A.I.B. is running successfully offline."
                }
            })
        # Scenario 2: System health status check
        elif "status" in goal_lower or "health" in goal_lower:
            steps.append({
                "step_number": 1,
                "description": "Check current system health and memory usage status",
                "tool_name": "get_system_status",
                "tool_args": {}
            })
        # Scenario 3: Clipboard flow
        elif "clipboard" in goal_lower:
            steps.append({
                "step_number": 1,
                "description": "Read content from current clipboard",
                "tool_name": "read_clipboard",
                "tool_args": {}
            })
            steps.append({
                "step_number": 2,
                "description": "Write response back to clipboard",
                "tool_name": "write_clipboard",
                "tool_args": {"text": "V.A.I.B. Processed clipboard text"}
            })
        # Scenario 4: Screenshot
        elif "screenshot" in goal_lower or "screen" in goal_lower:
            steps.append({
                "step_number": 1,
                "description": "Capture screen snapshot",
                "tool_name": "capture_screenshot",
                "tool_args": {}
            })
        # Default fallback
        else:
            steps.append({
                "step_number": 1,
                "description": "Retrieve system health and configuration status",
                "tool_name": "get_system_status",
                "tool_args": {}
            })
            
        return steps

    def reflect(self, goal: str, step: Dict[str, Any], observation: str) -> Dict[str, Any]:
        """Reflect on the step result and decide if we should proceed, modify the plan, or stop."""
        if not self.agent or not self.agent.model:
            return {
                "success": True,
                "reflection": f"Successfully completed step {step['step_number']} using {step['tool_name']}.",
                "action": "continue"
            }
            
        prompt = f"""You are the reflection module of an autonomous AI agent.
Goal: "{goal}"
Completed Step: {json.dumps(step)}
Observation/Result: "{observation}"

Analyze if this step succeeded and whether the goal is on track.
Respond with a JSON object containing:
- "success": true/false
- "reflection": "<a short reflection reasoning on what was observed and what to do next>"
- "action": "continue" (to go to next step), "modify" (if plan needs adjustment), or "stop" (if goal is completed or failed)
- "modified_steps": [ <optional list of remaining steps if action is "modify"> ]
"""
        try:
            response = self.agent.model.generate_content(prompt)
            text = response.text.strip()
            # Clean markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            
            res = json.loads(text)
            return res
        except Exception as e:
            logger.error(f"Reflection LLM call failed: {e}")
            return {
                "success": True,
                "reflection": "Reflection fallback: proceeding to next step.",
                "action": "continue"
            }


class AgentExecutorManager:
    """Manages background threads executing agent goals."""
    def __init__(self, agent, memory_manager: MemoryManager):
        self.agent = agent
        self.memory = memory_manager
        self.planner = GoalPlanner(agent)
        self.active_threads = {}

    def start_goal_execution(self, goal_id: int) -> bool:
        """Spawn a background thread to execute the goal."""
        goal_record = self.memory.get_agent_goal(goal_id)
        if not goal_record:
            logger.error(f"Cannot start execution: Goal ID {goal_id} not found in database.")
            return False
            
        if goal_record["status"] in ["running", "paused"]:
            logger.warning(f"Goal ID {goal_id} is already in state: {goal_record['status']}")
            return True
            
        t = threading.Thread(target=self._execute_goal_thread, args=(goal_id,), daemon=True)
        self.active_threads[goal_id] = t
        t.start()
        return True

    def cancel_goal_execution(self, goal_id: int):
        """Request cancellation of an active goal by setting status to cancelled."""
        self.memory.update_agent_goal_status(goal_id, "cancelled", "Cancelled by user.")

    def _execute_goal_thread(self, goal_id: int):
        try:
            self.memory.update_agent_goal_status(goal_id, "running")
            goal_record = self.memory.get_agent_goal(goal_id)
            if not goal_record:
                return
                
            goal_text = goal_record["goal"]
            
            # Phase 1: Decompose
            steps = self.planner.decompose(goal_text)
            if not steps:
                self.memory.update_agent_goal_status(goal_id, "failed", "No plan could be generated.")
                return
                
            # Save decomposed steps to the database
            for step in steps:
                self.memory.add_agent_task(
                    goal_id=goal_id,
                    step_number=step["step_number"],
                    description=step["description"],
                    tool_name=step["tool_name"],
                    tool_args=step["tool_args"]
                )
                
            # Phase 2: Act -> Observe -> Reflect Loop
            tasks = self.memory.get_agent_tasks(goal_id)
            
            for task in tasks:
                # Check for cancellation
                current_goal = self.memory.get_agent_goal(goal_id)
                if not current_goal or current_goal["status"] in ["cancelled", "failed"]:
                    break
                    
                task_id = task["id"]
                self.memory.update_agent_task(task_id, status="running", started_at=time.time())
                
                # Act: execute tool
                tool_name = task["tool_name"]
                tool_args = task["tool_args"]
                
                logger.info(f"Goal {goal_id} executing task {task_id}: {tool_name} with args {tool_args}")
                
                # Execute the tool
                import asyncio
                try:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(lambda: asyncio.run(self.agent.execute_tool(tool_name, tool_args)))
                            tool_result = future.result()
                    else:
                        tool_result = loop.run_until_complete(self.agent.execute_tool(tool_name, tool_args))
                except Exception as e:
                    tool_result = f"Error during execution: {str(e)}"
                    
                # Handle permissions (pending_approval)
                if isinstance(tool_result, dict) and tool_result.get("status") == "pending_approval":
                    action_id = tool_result.get("action_id")
                    self.memory.update_agent_task(task_id, status="paused_on_permission")
                    self.memory.update_agent_goal_status(goal_id, "paused")
                    
                    # Wait/poll for permission approval in PermissionsManager
                    permissions_manager = PermissionsManager()
                    approved = False
                    denied = False
                    
                    while not approved and not denied:
                        # Check goal cancellation during pause
                        cg = self.memory.get_agent_goal(goal_id)
                        if not cg or cg["status"] == "cancelled":
                            break
                            
                        status_rec = permissions_manager.get_action_status(action_id)
                        if status_rec["status"] == "approved":
                            approved = True
                            tool_result = status_rec["result"]
                        elif status_rec["status"] in ["denied", "failed"]:
                            denied = True
                            tool_result = f"Permission denied or failed for Action ID: {action_id}"
                        else:
                            time.sleep(0.5)
                            
                    cg = self.memory.get_agent_goal(goal_id)
                    if not cg or cg["status"] == "cancelled":
                        break
                        
                    # Reset goal status to running and task status to running
                    self.memory.update_agent_goal_status(goal_id, "running")
                    self.memory.update_agent_task(task_id, status="running")
                
                observation = str(tool_result)
                
                # Reflect
                reflection_res = self.planner.reflect(goal_text, task, observation)
                reflection_text = reflection_res.get("reflection", "Completed step.")
                task_success = reflection_res.get("success", True)
                next_action = reflection_res.get("action", "continue")
                
                status_to_set = "completed" if task_success else "failed"
                self.memory.update_agent_task(
                    task_id,
                    status=status_to_set,
                    observation=observation,
                    reflection=reflection_text,
                    completed_at=time.time()
                )
                
                if not task_success or next_action == "stop":
                    self.memory.update_agent_goal_status(
                        goal_id,
                        "failed" if not task_success else "completed",
                        result=f"Halted at step {task['step_number']}: {reflection_text}"
                    )
                    return
                    
                # Handle modified plan if LLM decides to change remaining steps
                if next_action == "modify" and "modified_steps" in reflection_res:
                    # Remove remaining tasks that are pending
                    conn = sqlite3.connect(self.memory.db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM agent_tasks WHERE goal_id = ? AND status = 'pending'", (goal_id,))
                    conn.commit()
                    conn.close()
                    
                    # Insert new modified tasks
                    for mod_step in reflection_res["modified_steps"]:
                        self.memory.add_agent_task(
                            goal_id=goal_id,
                            step_number=mod_step["step_number"],
                            description=mod_step["description"],
                            tool_name=mod_step["tool_name"],
                            tool_args=mod_step["tool_args"]
                        )
                    # Refresh the tasks list to iterate over the new plan
                    tasks = self.memory.get_agent_tasks(goal_id)
            
            # Wrap up goal
            final_goal = self.memory.get_agent_goal(goal_id)
            if final_goal and final_goal["status"] == "cancelled":
                self.memory.update_agent_goal_status(goal_id, "cancelled", "Goal execution was cancelled by user.")
            else:
                self.memory.update_agent_goal_status(goal_id, "completed", "Goal completed successfully.")
                
        except Exception as e:
            logger.error(f"Error in execution thread for goal {goal_id}: {e}")
            self.memory.update_agent_goal_status(goal_id, "failed", f"Internal execution error: {str(e)}")
        finally:
            if goal_id in self.active_threads:
                del self.active_threads[goal_id]
