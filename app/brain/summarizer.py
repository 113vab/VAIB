import logging
import sqlite3
import time
import google.generativeai as genai
from app.brain.memory import MemoryManager
from app.config import logger

class ConversationSummarizer:
    """
    Manages automatic background summarization of old chat transcripts
    to compress context window usage while preserving long-term context.
    """
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    def auto_summarize_if_needed(self, model) -> bool:
        """
        Check chat history size. If messages exceed threshold, summarize the oldest ones,
        incorporating any previous summary, then delete the summarized records from chat_history.
        """
        try:
            # 1. Fetch total message count in SQLite
            conn = sqlite3.connect(self.memory.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chat_history")
            count = cursor.fetchone()[0]
            
            # If total turns are within bounds (e.g., less than 20 messages), do nothing
            threshold = 20
            if count <= threshold:
                conn.close()
                return False
            
            logger.info(f"Chat history has {count} messages (threshold {threshold} exceeded). Triggering summarization...")
            
            # 2. Get all messages sorted by ID ascending
            cursor.execute("SELECT id, role, content FROM chat_history ORDER BY id ASC")
            all_messages = cursor.fetchall()
            
            # Keep the last 6 messages verbatim for active conversation flow
            keep_count = 6
            to_summarize = all_messages[:-keep_count]
            to_keep_ids = [msg[0] for msg in all_messages[-keep_count:]]
            
            # Formulate text block to summarize
            transcript_lines = []
            for msg_id, role, content in to_summarize:
                role_name = "User" if role == "user" else "V.A.I.B."
                transcript_lines.append(f"{role_name}: {content}")
            
            new_transcript = "\n".join(transcript_lines)
            
            # 3. Retrieve any existing summary
            old_summary = self.memory.get_latest_summary()
            
            # 4. Generate summary (support simulation mode if model is None)
            new_summary = ""
            if model is None:
                # Simulation Mode fallback: simple text truncation
                new_summary = f"[Simulated Summary] Chat contains discussion on: " + ", ".join([msg[2][:30] for msg in to_summarize[:3]]) + "..."
                if old_summary:
                    new_summary = f"{old_summary} Additional topics: {new_summary}"
            else:
                # Build context-aware summarization prompt
                prompt = (
                    "You are the summarization subroutine of V.A.I.B., a highly competent personal AI assistant.\n"
                    "Synthesize a single, consolidated, chronologically-accurate narrative summary of the user's interaction.\n"
                    "Do NOT use bullet points; write a coherent paragraph. Focus on key decisions, personal facts, preferences, or tasks.\n\n"
                )
                if old_summary:
                    prompt += f"Existing Summary of older history:\n\"\"\"\n{old_summary}\n\"\"\"\n\n"
                    prompt += f"New messages to integrate into the summary:\n\"\"\"\n{new_transcript}\n\"\"\"\n\n"
                    prompt += "Generate a single updated paragraph incorporating the new turns into the existing summary."
                else:
                    prompt += f"Conversation transcript:\n\"\"\"\n{new_transcript}\n\"\"\"\n\n"
                    prompt += "Generate a concise summary paragraph based on the transcript above."
                
                try:
                    response = model.generate_content(prompt)
                    new_summary = response.text.strip()
                except Exception as e:
                    logger.error(f"Error calling LLM for summarization: {e}")
                    # Fallback to simple description if LLM fails
                    new_summary = old_summary or "Active conversation summary."
            
            if not new_summary:
                new_summary = "Interaction in progress, Sir."

            # 5. Write new summary to DB
            self.memory.add_summary(new_summary)
            logger.info("Successfully updated conversation summary.")

            # 6. Delete the summarized messages (keep the latest ones)
            # Delete messages that are NOT in the keep list
            placeholders = ",".join(["?"] * len(to_keep_ids))
            cursor.execute(
                f"DELETE FROM chat_history WHERE id NOT IN ({placeholders})",
                to_keep_ids
            )
            conn.commit()
            conn.close()
            logger.info(f"Compressed database: Deleted {count - keep_count} summarized messages.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to auto-summarize conversations: {e}")
            return False
