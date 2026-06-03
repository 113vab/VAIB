import subprocess
import logging

logger = logging.getLogger("vaib")

def read_clipboard() -> str:
    """
    Read text content from the Windows system clipboard.
    Returns the clipboard text, or an empty string if it fails.
    """
    try:
        # Run PowerShell command to get clipboard contents securely
        cmd = ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
        content = result.stdout
        # Normalize line endings
        return content.replace("\r\n", "\n").rstrip("\n")
    except Exception as e:
        logger.error(f"Failed to read clipboard: {e}")
        return ""

def write_clipboard(text: str) -> str:
    """
    Write text content to the Windows system clipboard.
    Returns a status message.
    """
    try:
        # Run PowerShell command passing text via standard input to avoid command line escaping issues
        cmd = ["powershell.exe", "-NoProfile", "-Command", "$input | Set-Clipboard"]
        subprocess.run(cmd, input=text, text=True, check=True, encoding="utf-8")
        logger.info(f"Clipboard updated: {len(text)} characters written.")
        return f"Successfully copied to clipboard, Sir."
    except Exception as e:
        logger.error(f"Failed to write clipboard: {e}")
        return f"Failed to update clipboard, Sir: {e}"
