import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from app.brain.providers import (
    GeminiProvider,
    GroqProvider,
    DeepSeekProvider,
    OllamaProvider,
    LLMProviderRouter,
    function_to_openai_tool
)

def dummy_tool(param1: str, param2: int = 10) -> str:
    """
    This is a dummy tool for testing.
    
    param1: Description of param1.
    param2: Description of param2.
    """
    return f"{param1} - {param2}"

def test_function_to_openai_tool():
    schema = function_to_openai_tool(dummy_tool)
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "dummy_tool"
    assert schema["function"]["description"] == "This is a dummy tool for testing."
    assert "param1" in schema["function"]["parameters"]["properties"]
    assert "param2" in schema["function"]["parameters"]["properties"]
    assert "param1" in schema["function"]["parameters"]["required"]
    assert "param2" not in schema["function"]["parameters"]["required"]

@pytest.mark.asyncio
async def test_gemini_provider_health_healthy():
    with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock()
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider(model_name="gemini-2.5-flash", tools=[])
        provider.api_key = "dummy_key"
        provider.model = mock_model
        
        healthy = await provider.is_healthy()
        assert healthy is True

@pytest.mark.asyncio
async def test_gemini_provider_health_unhealthy():
    with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API error")
        mock_model_class.return_value = mock_model
        
        provider = GeminiProvider(model_name="gemini-2.5-flash", tools=[])
        provider.api_key = "dummy_key"
        provider.model = mock_model
        
        # Reset cache so check actually triggers
        provider.last_health_check = 0.0
        
        healthy = await provider.is_healthy()
        assert healthy is False

@pytest.mark.asyncio
async def test_openai_compatible_provider_health_healthy():
    provider = GroqProvider(model_name="llama-3.3-70b-versatile", tools=[])
    provider.api_key = "dummy_key"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        healthy = await provider.is_healthy()
        assert healthy is True

@pytest.mark.asyncio
async def test_openai_compatible_provider_health_unhealthy():
    provider = GroqProvider(model_name="llama-3.3-70b-versatile", tools=[])
    provider.api_key = "dummy_key"
    
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        healthy = await provider.is_healthy()
        assert healthy is False

@pytest.mark.asyncio
async def test_provider_router_fallback_flow():
    # Test falling back from gemini -> groq -> deepseek -> ollama -> simulation
    with patch("google.generativeai.GenerativeModel"):
        router = LLMProviderRouter(provider="gemini", model_name="gemini-2.5-flash", tools=[])
        
        # Mock all providers to be unhealthy except deepseek
        router.providers["gemini"].is_healthy = AsyncMock(return_value=False)
        router.providers["groq"].is_healthy = AsyncMock(return_value=False)
        router.providers["deepseek"].is_healthy = AsyncMock(return_value=True)
        router.providers["ollama"].is_healthy = AsyncMock(return_value=False)
        
        router.providers["deepseek"].generate_response = AsyncMock(return_value="Response from DeepSeek")
        
        response = await router.generate_response(
            system_context="system",
            history=[],
            user_input="hello",
            tools=[],
            execute_tool_callback=None
        )
        assert response == "Response from DeepSeek"

@pytest.mark.asyncio
async def test_provider_router_simulation_fallback():
    with patch("google.generativeai.GenerativeModel"):
        router = LLMProviderRouter(provider="gemini", model_name="gemini-2.5-flash", tools=[])
        
        # Mock all providers to be unhealthy
        for p in router.providers.values():
            p.is_healthy = AsyncMock(return_value=False)
            
        response = await router.generate_response(
            system_context="system",
            history=[],
            user_input="hello",
            tools=[],
            execute_tool_callback=None
        )
        assert "Simulation Mode" in response
