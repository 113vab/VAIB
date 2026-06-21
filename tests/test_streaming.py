import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.brain.agent import VaibAgent
from app.brain.memory import MemoryManager
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def mock_memory():
    memory = MagicMock(spec=MemoryManager)
    memory.get_chat_history.return_value = []
    memory.query_facts.return_value = []
    memory.save_fact.return_value = True
    return memory

@pytest.mark.asyncio
async def test_agent_generate_response_stream_simulation(mock_memory):
    """Test streaming response in offline simulation mode."""
    with patch("app.config.GEMINI_API_KEY", ""):
        agent = VaibAgent(mock_memory)
        
        # Override providers to be unhealthy to trigger simulation fallback
        for p in agent.router.providers.values():
            p.is_healthy = AsyncMock(return_value=False)
            
        tokens = []
        async for token in agent.generate_response_stream("Hello VAIB"):
            tokens.append(token)
            
        full_response = "".join(tokens)
        assert "Simulation Mode" in full_response or "simulation mode" in full_response

@pytest.mark.asyncio
async def test_agent_generate_response_stream_gemini(mock_memory):
    """Test streaming response from Gemini provider."""
    agent = VaibAgent(mock_memory)
    
    # Mock Gemini provider to be healthy
    gemini_prov = agent.router.providers["gemini"]
    gemini_prov.is_healthy = AsyncMock(return_value=True)
    
    # Mock generator for generate_response_stream
    async def mock_stream(*args, **kwargs):
        yield "Greetings, "
        yield "Sir. "
        yield "How may I help?"
        
    gemini_prov.generate_response_stream = mock_stream
    
    tokens = []
    async for token in agent.generate_response_stream("Hello"):
        tokens.append(token)
        
    assert tokens == ["Greetings, ", "Sir. ", "How may I help?"]
    assert mock_memory.add_chat_message.call_count == 2
    mock_memory.add_chat_message.assert_any_call("user", "Hello")
    mock_memory.add_chat_message.assert_any_call("assistant", "Greetings, Sir. How may I help?")

def test_chat_stream_endpoint():
    """Test the /api/chat/stream HTTP endpoint."""
    client = TestClient(app)
    
    # Mock agent.generate_response_stream to yield tokens
    async def mock_agent_stream(message):
        yield "Token1 "
        yield "Token2"
        
    with patch("app.main.agent.generate_response_stream", side_effect=mock_agent_stream):
        response = client.post("/api/chat/stream", json={"message": "hello streaming"})
        assert response.status_code == 200
        assert response.text == "Token1 Token2"
        assert response.headers["content-type"].startswith("text/plain")
