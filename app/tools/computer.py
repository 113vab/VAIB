import os
import time
import logging
import subprocess
from typing import Dict, Any, Union
from pathlib import Path
from app.tools.permissions import PermissionsManager
from app.config import DATA_DIR

logger = logging.getLogger("vaib")
AUDIT_LOG_PATH = DATA_DIR / "audit.log"

def write_audit_log(status: str, command: str, result: str = ""):
    """Writes system command audit details to a persistent audit log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{status}] Command: {repr(command)}"
    if result:
        log_entry += f" | Result: {repr(result)}"
    log_entry += "\n"
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.info(f"Audit log updated: {status}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

# Destructive commands list (blacklisted to prevent execution even with prompt)
BLACKLIST = [
    "format ", "diskpart", "fdisk",
    "reg delete hklm\\system", "reg delete hklm\\software",
    "shutdown /s", "stop-computer"
]

def _run_shell_command_callback(command: str) -> str:
    """Executes the PowerShell command in a subprocess and logs the output."""
    write_audit_log("APPROVED", command)
    try:
        # Run PowerShell command securely
        cmd = ["powershell.exe", "-NoProfile", "-Command", command]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
        
        # Determine status based on return code
        if result.returncode == 0:
            output = result.stdout or "Command completed with no output."
            write_audit_log("SUCCESS", command, output)
            return output
        else:
            err_output = result.stderr or result.stdout or f"Failed with exit code {result.returncode}"
            write_audit_log("FAILED", command, err_output)
            return f"Error executing command: {err_output}"
    except Exception as e:
        write_audit_log("FAILED", command, str(e))
        return f"Error executing command, Sir: {str(e)}"

def run_shell_command(command: str) -> Union[str, Dict[str, Any]]:
    """
    Execute a command in Windows PowerShell. Gated by explicit permission system.
    Requires user approval. Logs execution to audit database/logs.
    """
    cmd_lower = command.lower().strip()
    
    # 1. Check Blacklist for highly destructive actions
    for item in BLACKLIST:
        if item in cmd_lower:
            write_audit_log("BLOCKED_BLACKLIST", command)
            return f"Access Denied: The command contains blacklisted substring '{item}' and cannot be executed."
            
    # 2. Gate under explicit approval requirement
    # We log PENDING to the audit trail
    write_audit_log("PENDING", command)
    
    # Create details dict for frontend
    details = {"command": command}
    
    pm = PermissionsManager()
    return pm.request_permission(
        action_type="run_shell_command",
        details=details,
        callback=lambda: _run_shell_command_callback(command)
    )
