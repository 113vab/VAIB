import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Create a temporary directory for tests
@pytest.fixture(scope="module", autouse=True)
def test_env():
    temp_dir = tempfile.mkdtemp()
    
    # Patch config variables before importing MemoryManager
    with patch("app.config.DATA_DIR", Path(temp_dir)), \
         patch("app.config.CHROMA_DB_PATH", str(Path(temp_dir) / "chroma")):
        from app.brain.memory import MemoryManager
        memory_manager = MemoryManager()
        yield memory_manager
        
    # Clean up temp files
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

def test_sqlite_chat_history(test_env):
    """Test SQLite chat logs functionality."""
    memory = test_env
    memory.clear_chat_history()
    
    # Verify initial empty state
    history = memory.get_chat_history()
    assert len(history) == 0
    
    # Save messages
    memory.add_chat_message("user", "Hello VAIB")
    memory.add_chat_message("assistant", "Hello Sir, how can I help?")
    
    # Retrieve messages
    history = memory.get_chat_history(limit=5)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello VAIB"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hello Sir, how can I help?"
    
    # Clear history
    memory.clear_chat_history()
    history = memory.get_chat_history()
    assert len(history) == 0

def test_chromadb_semantic_facts(test_env):
    """Test ChromaDB fact saving and query interface with mocks."""
    memory = test_env
    
    # Mock ChromaDB collections to avoid network embedding calls during tests
    memory.facts_collection = MagicMock()
    
    # Save a fact
    memory.save_fact("User loves espresso coffee")
    assert memory.facts_collection.add.called
    
    # Query facts
    memory.query_facts("coffee query")
    assert memory.facts_collection.query.called
