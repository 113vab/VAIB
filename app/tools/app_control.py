import subprocess
import logging
from typing import Dict, Any, Union
from app.tools.permissions import PermissionsManager

logger = logging.getLogger("vaib")

APP_MAPPINGS = {
    "notepad": {"exec": "notepad.exe", "proc": "notepad.exe"},
    "chrome": {"exec": "start chrome", "proc": "chrome.exe", "shell": True},
    "edge": {"exec": "start msedge", "proc": "msedge.exe", "shell": True},
    "vs code": {"exec": "code", "proc": "Code.exe", "shell": True},
    "vscode": {"exec": "code", "proc": "Code.exe", "shell": True},
    "file explorer": {"exec": "explorer.exe", "proc": "explorer.exe"},
    "explorer": {"exec": "explorer.exe", "proc": "explorer.exe"}
}

def open_app(app_name: str) -> str:
    """
    Launch a supported application (Chrome, Edge, Notepad, VS Code, File Explorer).
    Returns a success or failure status message.
    """
    name_lower = app_name.lower().strip()
    # Fuzzy match app name
    matched_app = None
    for key in APP_MAPPINGS:
        if key in name_lower or name_lower in key:
            matched_app = key
            break
            
    if not matched_app:
        return f"Unknown application '{app_name}', Sir. I support Chrome, Edge, Notepad, VS Code, and File Explorer."

    app_info = APP_MAPPINGS[matched_app]
    exec_cmd = app_info["exec"]
    use_shell = app_info.get("shell", False)

    try:
        logger.info(f"Opening app: {matched_app} using cmd: '{exec_cmd}'")
        if use_shell:
            subprocess.Popen(exec_cmd, shell=True)
        else:
            subprocess.Popen([exec_cmd])
        return f"Opened {matched_app} successfully, Sir."
    except Exception as e:
        logger.error(f"Failed to open app {matched_app}: {e}")
        return f"Failed to open {matched_app}, Sir: {e}"

def check_app_running(app_name: str) -> str:
    """
    Checks if a supported application is running.
    """
    name_lower = app_name.lower().strip()
    matched_app = None
    for key in APP_MAPPINGS:
        if key in name_lower or name_lower in key:
            matched_app = key
            break

    if not matched_app:
        return f"Unknown application '{app_name}', Sir."

    process_name = APP_MAPPINGS[matched_app]["proc"]
    try:
        # Check process status using Windows tasklist
        cmd = ["tasklist", "/fi", f"imagename eq {process_name}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Check if the process name is in the output (ignoring header)
        if process_name.lower() in result.stdout.lower():
            return f"Yes, {matched_app} is currently running, Sir."
        else:
            return f"No, {matched_app} is not running, Sir."
    except Exception as e:
        logger.error(f"Failed to check app status for {matched_app}: {e}")
        return f"Failed to check if {matched_app} is running: {e}"

def _close_app_callback(matched_app: str, process_name: str) -> str:
    """The actual callback triggered when close_app is approved."""
    try:
        # Run taskkill to terminate the process
        cmd = ["taskkill", "/f", "/im", process_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Closed {matched_app} successfully, Sir."
        else:
            # Taskkill output might say process not found
            if "not found" in result.stderr or "not found" in result.stdout:
                return f"{matched_app} was not running, Sir."
            return f"Failed to close {matched_app}: {result.stderr or result.stdout}"
    except Exception as e:
        return f"Error closing {matched_app}: {str(e)}"

def close_app(app_name: str) -> Union[str, Dict[str, Any]]:
    """
    Request permission to close a running application.
    Gates process termination behind User approval.
    """
    name_lower = app_name.lower().strip()
    matched_app = None
    for key in APP_MAPPINGS:
        if key in name_lower or name_lower in key:
            matched_app = key
            break

    if not matched_app:
        return f"Unknown application '{app_name}', Sir."

    process_name = APP_MAPPINGS[matched_app]["proc"]
    
    # Delegate closure to PermissionsManager callback
    pm = PermissionsManager()
    return pm.request_permission(
        action_type="close_app",
        details={"app_name": matched_app},
        callback=lambda: _close_app_callback(matched_app, process_name)
    )
