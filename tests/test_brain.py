import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.brain.agent import VaibAgent
from app.brain.memory import MemoryManager

@pytest.fixture
def mock_memory():
    memory = MagicMock(spec=MemoryManager)
    memory.get_chat_history.return_value = []
    memory.query_facts.return_value = []
    memory.save_fact.return_value = True
    return memory

def test_agent_tool_calling(mock_memory):
    """Test tool execution logic locally in agent."""
    agent = VaibAgent(mock_memory)
    
    # Test system status
    status = agent.execute_tool("get_system_status", {})
    assert "System Status" in status
    assert "OS:" in status
    
    # Test user preference storage
    pref = "User works as a software designer"
    res = agent.execute_tool("save_user_preference", {"preference": pref})
    assert "Successfully saved" in res
    mock_memory.save_fact.assert_called_with(pref)
    
    # Test clearing memory
    clear_res = agent.execute_tool("clear_all_memory", {})
    assert "cleared" in clear_res
    assert mock_memory.clear_chat_history.called
    assert mock_memory.clear_long_term_memories.called

@pytest.mark.asyncio
async def test_agent_generate_response_offline(mock_memory):
    """Test response generation fallback when Gemini model is offline (API key missing)."""
    with patch("app.brain.agent.GEMINI_API_KEY", ""):
        agent = VaibAgent(mock_memory)
        response = await agent.generate_response("Hello VAIB")
        assert "simulation mode" in response or "API key" in response
