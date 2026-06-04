import os
import time
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

@pytest.fixture(scope="module", autouse=True)
def test_agent_env():
    temp_dir = tempfile.mkdtemp()
    
    # Patch config variables before importing
    with patch("app.config.DATA_DIR", Path(temp_dir)), \
         patch("app.config.CHROMA_DB_PATH", str(Path(temp_dir) / "chroma")):
        from app.brain.memory import MemoryManager
        from app.brain.agent import VaibAgent
        from app.brain.planner import GoalPlanner, AgentExecutorManager
        
        memory = MemoryManager()
        agent = VaibAgent(memory)
        # Force offline/simulation mode for tests unless explicitly mocked
        agent.model = None
        
        yield {
            "temp_dir": Path(temp_dir),
            "memory": memory,
            "agent": agent,
            "planner": GoalPlanner(agent),
            "executor": AgentExecutorManager(agent, memory)
        }
        
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

def test_sqlite_agent_goals_and_tasks(test_agent_env):
    """Test CRUD operations for goals and tasks in SQLite."""
    memory = test_agent_env["memory"]
    
    # Create goal
    goal_id = memory.add_agent_goal("Test high level goal")
    assert goal_id > 0
    
    # Verify goal list
    goals = memory.get_agent_goals()
    assert len(goals) > 0
    assert goals[0]["id"] == goal_id
    assert goals[0]["goal"] == "Test high level goal"
    assert goals[0]["status"] == "pending"
    
    # Add tasks
    task_id1 = memory.add_agent_task(goal_id, 1, "First task description", "get_system_status", {})
    task_id2 = memory.add_agent_task(goal_id, 2, "Second task description", "capture_screenshot", {})
    assert task_id1 > 0
    assert task_id2 > 0
    
    # Retrieve tasks
    tasks = memory.get_agent_tasks(goal_id)
    assert len(tasks) == 2
    assert tasks[0]["step_number"] == 1
    assert tasks[0]["tool_name"] == "get_system_status"
    assert tasks[1]["step_number"] == 2
    
    # Update goal and task status
    memory.update_agent_goal_status(goal_id, "running")
    goal = memory.get_agent_goal(goal_id)
    assert goal["status"] == "running"
    
    memory.update_agent_task(task_id1, status="completed", observation="System OK", reflection="Step 1 complete")
    tasks = memory.get_agent_tasks(goal_id)
    assert tasks[0]["status"] == "completed"
    assert tasks[0]["observation"] == "System OK"
    assert tasks[0]["reflection"] == "Step 1 complete"
    
    # Delete goal
    success = memory.delete_agent_goal(goal_id)
    assert success is True
    assert memory.get_agent_goal(goal_id) is None
    assert len(memory.get_agent_tasks(goal_id)) == 0

def test_goal_decomposition_simulation(test_agent_env):
    """Test simulated goal decomposition when agent is offline."""
    planner = test_agent_env["planner"]
    
    # Search and save scenario
    steps = planner.decompose("search for programming updates and write to file")
    assert len(steps) == 2
    assert steps[0]["tool_name"] == "browser_search"
    assert steps[1]["tool_name"] == "create_file"
    
    # Default scenario
    steps = planner.decompose("custom weird goal")
    assert len(steps) == 1
    assert steps[0]["tool_name"] == "get_system_status"

def test_executor_loop_execution(test_agent_env):
    """Test the complete Plan-Act-Observe-Reflect loop execution."""
    memory = test_agent_env["memory"]
    agent = test_agent_env["agent"]
    executor = test_agent_env["executor"]
    
    goal_id = memory.add_agent_goal("Check status and log health")
    
    # Execute goal thread synchronously using a mock execute_tool
    with patch.object(agent, "execute_tool", return_value="Simulated Tool Success") as mock_tool:
        # Run thread logic synchronously
        executor._execute_goal_thread(goal_id)
        
        mock_tool.assert_called()
        goal = memory.get_agent_goal(goal_id)
        assert goal["status"] == "completed"
        
        tasks = memory.get_agent_tasks(goal_id)
        assert len(tasks) > 0
        for task in tasks:
            assert task["status"] == "completed"
            assert task["observation"] == "Simulated Tool Success"

def test_executor_loop_permission_handling(test_agent_env):
    """Test pausing and resuming of autonomous tasks when gated by permissions."""
    memory = test_agent_env["memory"]
    agent = test_agent_env["agent"]
    executor = test_agent_env["executor"]
    from app.tools.permissions import PermissionsManager
    
    pm = PermissionsManager()
    pm.clear_all()
    
    goal_id = memory.add_agent_goal("Read clipboard contents")
    
    # Decompose mock plan manually
    memory.add_agent_task(goal_id, 1, "Read clipboard step", "read_clipboard", {})
    
    # Mock execute_tool to return a permission request
    action_id = "test-action-123"
    perm_res = {
        "status": "pending_approval",
        "action_id": action_id,
        "type": "read_clipboard",
        "message": "Needs permission"
    }
    
    # Callback to simulate completion
    def test_cb():
        return "Clipboard secret contents"
    
    # Register in PermissionsManager
    pm._pending_actions[action_id] = {
        "id": action_id,
        "type": "read_clipboard",
        "details": {},
        "callback": test_cb,
        "status": "pending",
        "timestamp": time.time(),
        "result": None,
        "error": None
    }
    
    with patch.object(agent, "execute_tool", return_value=perm_res):
        # We start goal execution in a separate thread so it pauses on the loop
        executor.start_goal_execution(goal_id)
        
        # Wait a moment for thread to initialize and pause
        time.sleep(0.5)
        
        # Verify goal is paused
        goal = memory.get_agent_goal(goal_id)
        assert goal["status"] == "paused"
        
        tasks = memory.get_agent_tasks(goal_id)
        assert tasks[0]["status"] == "paused_on_permission"
        
        # Now approve permission action
        pm.approve_action(action_id)
        
        # Wait a moment for execution thread to finish
        time.sleep(1.0)
        
        # Verify it completed successfully after approval
        goal = memory.get_agent_goal(goal_id)
        assert goal["status"] == "completed"
        
        tasks = memory.get_agent_tasks(goal_id)
        assert tasks[0]["status"] == "completed"
        assert tasks[0]["observation"] == "Clipboard secret contents"
