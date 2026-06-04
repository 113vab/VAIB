import logging
from typing import Dict, Any, List
from app.brain.memory import MemoryManager

logger = logging.getLogger("vaib")

class ContextManager:
    """
    Orchestrates V.A.I.B.'s cognitive context.
    Combines user profile preferences, recent conversation summaries,
    relevant semantic facts from ChromaDB, and short-term chat history.
    """
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    def build_system_context(self, user_query: str) -> str:
        """
        Gathers profile details, summary of older turns, and semantically
        relevant long-term facts to inject as high-priority system context.
        """
        context_parts = []

        # 1. Inject User Profile Details
        profile = self.memory.get_all_profile()
        if profile:
            profile_lines = ["User Preferences & Profile details:"]
            for key, val in profile.items():
                profile_lines.append(f"- {key}: {val}")
            context_parts.append("\n".join(profile_lines))

        # 2. Inject Latest Conversation Summary
        summary = self.memory.get_latest_summary()
        if summary:
            context_parts.append(f"Summary of previous conversations:\n{summary}")

        # 3. Inject Semantically Relevant Facts
        facts = self.memory.query_facts(user_query, limit=3)
        if facts:
            fact_lines = ["Relevant recalled facts:"]
            for fact in facts:
                fact_lines.append(f"- {fact}")
            context_parts.append("\n".join(fact_lines))

        # 4. Inject Semantically Relevant Local Document Chunks (RAG)
        doc_matches = self.memory.query_documents(user_query, limit=3)
        if doc_matches:
            doc_lines = ["Details found in user-uploaded documents (RAG):"]
            for doc in doc_matches:
                source = doc["metadata"].get("source", "Unknown Document")
                doc_lines.append(f"- [File: {source}] \"{doc['text']}\"")
            context_parts.append("\n".join(doc_lines))

        if context_parts:
            # Join all parts with distinct section dividers
            return "\n\n=== RECALLED COGNITIVE CONTEXT ===\n" + "\n\n".join(context_parts) + "\n==================================\n"
        
        return ""
