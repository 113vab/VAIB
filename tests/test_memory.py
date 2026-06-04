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

def test_sqlite_user_profile(test_env):
    """Test user profile key-value operations in SQLite."""
    memory = test_env
    
    import sqlite3
    conn = sqlite3.connect(memory.db_path)
    conn.cursor().execute("DELETE FROM user_profile")
    conn.commit()
    conn.close()
    
    # Verify non-existent key returns None
    assert memory.get_profile_value("nonexistent") is None
    
    # Set profile key
    memory.set_profile_value("username", "Visha")
    memory.set_profile_value("theme", "glassmorphism")
    
    # Retrieve specific key
    assert memory.get_profile_value("username") == "Visha"
    assert memory.get_profile_value("theme") == "glassmorphism"
    
    # List all profile keys
    all_prefs = memory.get_all_profile()
    assert len(all_prefs) == 2
    assert all_prefs["username"] == "Visha"
    assert all_prefs["theme"] == "glassmorphism"
    
    # Delete profile key
    deleted = memory.delete_profile_value("theme")
    assert deleted is True
    assert memory.get_profile_value("theme") is None
    assert "theme" not in memory.get_all_profile()

def test_sqlite_conversation_summaries(test_env):
    """Test SQLite conversation summary table."""
    memory = test_env
    
    import sqlite3
    conn = sqlite3.connect(memory.db_path)
    conn.cursor().execute("DELETE FROM conversation_summaries")
    conn.commit()
    conn.close()
    
    # Initial empty state check
    assert memory.get_latest_summary() is None
    
    # Add summaries
    memory.add_summary("Summary of first discussion")
    memory.add_summary("Updated summary of discussion")
    
    # Latest summary check
    assert memory.get_latest_summary() == "Updated summary of discussion"

def test_chromadb_get_and_delete_facts(test_env):
    """Test get and delete operations for ChromaDB facts with mocks."""
    memory = test_env
    memory.facts_collection = MagicMock()
    
    # Setup mock returns
    memory.facts_collection.get.return_value = {
        "ids": ["fact_1", "fact_2"],
        "documents": ["fact 1 text", "fact 2 text"],
        "metadatas": [{"t": 1}, {"t": 2}]
    }
    
    facts = memory.get_all_facts()
    assert len(facts) == 2
    assert facts[0]["id"] == "fact_1"
    assert facts[0]["fact"] == "fact 1 text"
    
    # Test delete fact
    success = memory.delete_fact_by_id("fact_1")
    assert success is True
    memory.facts_collection.delete.assert_called_with(ids=["fact_1"])
