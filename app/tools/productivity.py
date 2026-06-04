import sqlite3
import time
import webbrowser
import urllib.parse
from typing import Optional, List, Dict, Any
from app.config import DATA_DIR, logger

DB_PATH = DATA_DIR / "history.db"

def init_productivity_db():
    """Initializes tables for reminders and calendar events in the history database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Reminders Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                trigger_time REAL,
                is_triggered INTEGER DEFAULT 0
            )
        """)
        
        # Calendar Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                date TEXT,
                time TEXT,
                description TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Productivity tables initialized in SQLite.")
    except Exception as e:
        logger.error(f"Failed to initialize productivity database: {e}")

# Initialize productivity tables
init_productivity_db()

def add_reminder(text: str, delay_seconds: int) -> str:
    """
    Schedule a reminder or background timer. V.A.I.B. will alert you when the timer expires.
    
    Args:
        text: The reminder message/text to display and speak (e.g., 'Check the cake in the oven').
        delay_seconds: The duration from now in seconds to trigger the reminder (e.g., 60 for 1 minute).
    """
    try:
        trigger_time = time.time() + delay_seconds
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reminders (text, trigger_time, is_triggered) VALUES (?, ?, 0)",
            (text, trigger_time)
        )
        conn.commit()
        conn.close()
        
        # Formulate a readable time message
        m, s = divmod(delay_seconds, 60)
        h, m = divmod(m, 60)
        time_parts = []
        if h > 0: time_parts.append(f"{h} hours")
        if m > 0: time_parts.append(f"{m} minutes")
        if s > 0 or not time_parts: time_parts.append(f"{s} seconds")
        duration_str = ", ".join(time_parts)
        
        return f"Understood, Sir. I have set a timer to remind you to '{text}' in {duration_str}."
    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
        return f"Failed to set reminder, Sir: {str(e)}"

def list_reminders() -> str:
    """
    List all pending and active reminders and timers.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, text, trigger_time FROM reminders WHERE is_triggered = 0 ORDER BY trigger_time ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "You have no pending reminders, Sir."
            
        lines = ["Active Reminders:"]
        for row in rows:
            rem_id, text, trig_time = row
            time_left = max(0, int(trig_time - time.time()))
            m, s = divmod(time_left, 60)
            h, m = divmod(m, 60)
            
            time_str = ""
            if h > 0: time_str += f"{h}h "
            if m > 0 or h > 0: time_str += f"{m}m "
            time_str += f"{s}s"
            
            lines.append(f"- ID {rem_id}: '{text}' (Triggers in {time_str})")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        return f"Failed to list reminders: {str(e)}"

def add_calendar_event(title: str, date: str, time: str, description: str = "") -> str:
    """
    Create a new calendar entry or event.
    
    Args:
        title: The name of the event (e.g., 'Doctor appointment', 'Project Sync').
        date: The date of the event in YYYY-MM-DD format.
        time: The time of the event in HH:MM format.
        description: Optional details about the event.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO calendar_events (title, date, time, description) VALUES (?, ?, ?, ?)",
            (title, date, time, description)
        )
        conn.commit()
        conn.close()
        return f"Successfully booked event '{title}' for {date} at {time}, Sir."
    except Exception as e:
        logger.error(f"Error adding calendar event: {e}")
        return f"Failed to add event: {str(e)}"

def get_calendar_events(date: Optional[str] = None) -> str:
    """
    Retrieve calendar entries and schedule. Can be filtered by date.
    
    Args:
        date: Optional date filter in YYYY-MM-DD format (e.g. '2026-06-04').
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if date:
            cursor.execute(
                "SELECT id, title, time, description FROM calendar_events WHERE date = ? ORDER BY time ASC",
                (date,)
            )
        else:
            cursor.execute(
                "SELECT id, title, date, time, description FROM calendar_events ORDER BY date ASC, time ASC"
            )
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            if date:
                return f"No events scheduled for {date}, Sir."
            return "Your schedule is clear, Sir. No upcoming events found."
            
        lines = ["Calendar Schedule:"]
        for row in rows:
            if date:
                event_id, title, time_str, desc = row
                desc_str = f" ({desc})" if desc else ""
                lines.append(f"- ID {event_id}: [{time_str}] {title}{desc_str}")
            else:
                event_id, title, date_str, time_str, desc = row
                desc_str = f" ({desc})" if desc else ""
                lines.append(f"- ID {event_id}: [{date_str} {time_str}] {title}{desc_str}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error retrieving calendar events: {e}")
        return f"Failed to retrieve calendar: {str(e)}"

def delete_calendar_event(event_id: int) -> str:
    """
    Delete a scheduled calendar event by its unique ID.
    
    Args:
        event_id: The unique integer ID of the calendar event to delete.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Verify event exists
        cursor.execute("SELECT title FROM calendar_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return f"I couldn't find an event with ID {event_id}, Sir."
            
        title = row[0]
        cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
        return f"Successfully removed event '{title}' (ID {event_id}) from your calendar, Sir."
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        return f"Failed to delete event: {str(e)}"

def draft_email(to_address: str, subject: str, body: str) -> str:
    """
    Draft an email and trigger the local default mail composer (mailto) and save a backup draft.
    
    Args:
        to_address: Recipient email address (e.g. 'colleague@example.com').
        subject: Subject line of the email.
        body: Main text body of the email.
    """
    try:
        # Create a mailto URL
        subject_quoted = urllib.parse.quote(subject)
        body_quoted = urllib.parse.quote(body)
        mailto_url = f"mailto:{to_address}?subject={subject_quoted}&body={body_quoted}"
        
        # Save a copy in a local drafts directory for records
        drafts_dir = DATA_DIR / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        draft_file = drafts_dir / f"draft_{timestamp}.eml"
        
        eml_content = (
            f"To: {to_address}\n"
            f"Subject: {subject}\n"
            f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S %z')}\n"
            f"MIME-Version: 1.0\n"
            f"Content-Type: text/plain; charset=utf-8\n\n"
            f"{body}"
        )
        draft_file.write_text(eml_content, encoding="utf-8")
        
        # Open in default client
        webbrowser.open(mailto_url)
        
        return f"I've drafted the email to {to_address} and saved a local backup at {draft_file.name}. Opening your default mail client now, Sir."
    except Exception as e:
        logger.error(f"Error drafting email: {e}")
        return f"Failed to draft email: {str(e)}"
