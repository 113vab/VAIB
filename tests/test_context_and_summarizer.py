import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

@pytest.fixture(scope="module", autouse=True)
def test_environment():
    temp_dir = tempfile.mkdtemp()
    
    # Patch config variables before importing models
    with patch("app.config.DATA_DIR", Path(temp_dir)), \
         patch("app.config.CHROMA_DB_PATH", str(Path(temp_dir) / "chroma")):
        from app.brain.memory import MemoryManager
        from app.brain.context import ContextManager
        from app.brain.summarizer import ConversationSummarizer
        
        memory = MemoryManager()
        context_mgr = ContextManager(memory)
        summarizer = ConversationSummarizer(memory)
        
        yield {
            "memory": memory,
            "context": context_mgr,
            "summarizer": summarizer
        }
        
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

def test_context_manager(test_environment):
    env = test_environment
    memory = env["memory"]
    context_mgr = env["context"]
    
    # Clear out SQLite
    memory.clear_chat_history()
    
    # Mock ChromaDB query to return a recalled fact
    memory.query_facts = MagicMock(return_value=["User prefers dark mode"])
    
    # Set mock profile
    memory.set_profile_value("name", "Sir Visha")
    
    # Set mock summary
    memory.add_summary("The previous discussion was about configuring testing pipelines.")
    
    # Build context
    ctx = context_mgr.build_system_context("What's my preference?")
    
    assert "Sir Visha" in ctx
    assert "configuring testing pipelines" in ctx
    assert "User prefers dark mode" in ctx

def test_conversation_summarizer_compression(test_environment):
    env = test_environment
    memory = env["memory"]
    summarizer = env["summarizer"]
    
    memory.clear_chat_history()
    
    # Populate history with 25 mock messages (exceeding threshold of 20)
    for i in range(25):
        role = "user" if i % 2 == 0 else "assistant"
        memory.add_chat_message(role, f"Message turn {i}")
        
    # Execute auto-summarization in simulation mode (model=None)
    triggered = summarizer.auto_summarize_if_needed(None)
    assert triggered is True
    
    # Verify latest summary is created
    latest_summary = memory.get_latest_summary()
    assert latest_summary is not None
    assert "[Simulated Summary]" in latest_summary
    
    # Verify chat history is compressed to exactly 6 messages
    history = memory.get_chat_history(limit=50)
    assert len(history) == 6
    
    # Running summarizer again with 6 messages should NOT trigger it
    second_trigger = summarizer.auto_summarize_if_needed(None)
    assert second_trigger is False
    assert len(memory.get_chat_history(limit=50)) == 6
