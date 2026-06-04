import sqlite3
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
import google.generativeai as genai
from typing import List, Dict, Any, Optional
import time
from pathlib import Path
from app.config import logger, CHROMA_DB_PATH, GEMINI_API_KEY, DATA_DIR

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Custom embedding function using Gemini API."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)

    def __call__(self, input: Documents) -> Embeddings:
        if not self.api_key:
            logger.warning("No Gemini API key provided. Using dummy embeddings.")
            return [[0.0] * 768 for _ in input]
        try:
            # gemini-embedding-001 returns 768-dimensional embeddings
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=input,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating embeddings with Gemini: {e}")
            # Fallback to zero vectors to prevent hard crashes
            return [[0.0] * 768 for _ in input]

class MemoryManager:
    """Manages V.A.I.B.'s memory: SQLite for chat logs, ChromaDB for semantic facts."""
    def __init__(self):
        self.db_path = DATA_DIR / "history.db"
        self._init_sqlite()
        self._init_chroma()

    def _init_sqlite(self):
        """Initialize SQLite database for chat history, user profile, and summaries."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    role TEXT,
                    content TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    summary TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info("SQLite chat history, profile, and summaries databases initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    def _init_chroma(self):
        """Initialize ChromaDB client and collections."""
        try:
            # Ensure Chroma DB path exists
            Path(CHROMA_DB_PATH).mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            
            # Use custom embedding function using Gemini
            self.emb_fn = GeminiEmbeddingFunction(api_key=GEMINI_API_KEY)
            
            # Create or get collection for long term memories
            self.facts_collection = self.chroma_client.get_or_create_collection(
                name="vaib_facts",
                embedding_function=self.emb_fn
            )
            logger.info("ChromaDB initialized with collection 'vaib_facts'.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.chroma_client = None
            self.facts_collection = None

    # SQLite Chat History Operations
    def add_chat_message(self, role: str, content: str):
        """Save a message (user/assistant) to the conversation history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (timestamp, role, content) VALUES (?, ?, ?)",
                (time.time(), role, content)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add chat message: {e}")

    def get_chat_history(self, limit: int = 15) -> List[Dict[str, str]]:
        """Retrieve recent messages sorted chronologically."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            conn.close()
            
            # Reverse to return chronological order
            history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
            return history
        except Exception as e:
            logger.error(f"Failed to fetch chat history: {e}")
            return []

    def clear_chat_history(self):
        """Clear all chat history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history")
            conn.commit()
            conn.close()
            logger.info("Chat history cleared.")
        except Exception as e:
            logger.error(f"Failed to clear chat history: {e}")

    # ChromaDB Long-Term Semantic Memory Operations
    def save_fact(self, fact: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save a semantic fact to long-term memory."""
        if not self.facts_collection:
            logger.error("ChromaDB not initialized. Cannot save fact.")
            return False
        try:
            fact_id = f"fact_{int(time.time() * 1000)}"
            meta = metadata or {}
            meta["timestamp"] = time.time()
            
            self.facts_collection.add(
                documents=[fact],
                metadatas=[meta],
                ids=[fact_id]
            )
            logger.info(f"Saved long-term memory: '{fact[:50]}...'")
            return True
        except Exception as e:
            logger.error(f"Failed to save fact to ChromaDB: {e}")
            return False

    def query_facts(self, query_text: str, limit: int = 5) -> List[str]:
        """Search long-term facts matching the query semantic meaning."""
        if not self.facts_collection:
            logger.error("ChromaDB not initialized. Cannot query facts.")
            return []
        try:
            results = self.facts_collection.query(
                query_texts=[query_text],
                n_results=limit
            )
            # return lists of document texts
            documents = results.get("documents", [])
            if documents and len(documents) > 0:
                return documents[0]
            return []
        except Exception as e:
            logger.error(f"Failed to query ChromaDB: {e}")
            return []

    def clear_long_term_memories(self):
        """Delete all facts in the long term memory collection."""
        if not self.chroma_client or not self.facts_collection:
            return
        try:
            self.chroma_client.delete_collection("vaib_facts")
            self.facts_collection = self.chroma_client.create_collection(
                name="vaib_facts",
                embedding_function=self.emb_fn
            )
            logger.info("Long-term memories cleared.")
        except Exception as e:
            logger.error(f"Failed to clear long-term memories: {e}")

    # SQLite User Profile Operations
    def get_profile_value(self, key: str) -> Optional[str]:
        """Retrieve user profile preference value by key."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get profile key {key}: {e}")
            return None

    def set_profile_value(self, key: str, value: str):
        """Set or update a user profile preference value."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to set profile key {key}: {e}")

    def get_all_profile(self) -> Dict[str, str]:
        """Retrieve all user profile preferences as key-value pairs."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_profile")
            rows = cursor.fetchall()
            conn.close()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get all profile values: {e}")
            return {}

    def delete_profile_value(self, key: str) -> bool:
        """Delete a profile preference key from SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
            conn.commit()
            conn.close()
            logger.info(f"Deleted profile key '{key}' from SQLite.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete profile key {key}: {e}")
            return False

    # SQLite Conversation Summary Operations
    def get_latest_summary(self) -> Optional[str]:
        """Retrieve the most recent conversation summary from SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT summary FROM conversation_summaries ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get latest summary: {e}")
            return None

    def add_summary(self, summary: str):
        """Save a new conversation summary to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversation_summaries (timestamp, summary) VALUES (?, ?)",
                (time.time(), summary)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add summary: {e}")

    # ChromaDB Facts Management Operations
    def get_all_facts(self) -> List[Dict[str, Any]]:
        """Retrieve all long-term facts stored in ChromaDB (documents, ids, metadatas)."""
        if not self.facts_collection:
            return []
        try:
            results = self.facts_collection.get()
            facts = []
            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            for i in range(len(ids)):
                facts.append({
                    "id": ids[i],
                    "fact": documents[i],
                    "metadata": metadatas[i] if metadatas else {}
                })
            return facts
        except Exception as e:
            logger.error(f"Failed to get all facts from ChromaDB: {e}")
            return []

    def delete_fact_by_id(self, fact_id: str) -> bool:
        """Delete a long-term fact by its unique ID in ChromaDB."""
        if not self.facts_collection:
            return False
        try:
            self.facts_collection.delete(ids=[fact_id])
            logger.info(f"Deleted fact with ID {fact_id} from ChromaDB.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete fact {fact_id} from ChromaDB: {e}")
            return False
