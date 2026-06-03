import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Union
from app.tools.permissions import PermissionsManager

logger = logging.getLogger("vaib")

def create_file(path: str, content: str = "") -> str:
    """
    Create a file with optional content. Creates parent directories if missing.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Created file: {path}")
        return f"Successfully created file at '{path}', Sir."
    except Exception as e:
        logger.error(f"Failed to create file {path}: {e}")
        return f"Failed to create file, Sir: {e}"

def create_directory(path: str) -> str:
    """
    Create a folder directory. Creates nested parent directories if missing.
    """
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {path}")
        return f"Successfully created folder directory at '{path}', Sir."
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return f"Failed to create directory, Sir: {e}"

def read_file(path: str) -> str:
    """
    Read contents of a text file.
    """
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' does not exist, Sir."
        if p.is_dir():
            return f"Error: '{path}' is a directory, not a file, Sir."
            
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(2000) # Read first 2000 chars to avoid prompt bloat
        return content
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        return f"Failed to read file, Sir: {e}"

# Callbacks for restricted actions

def _rename_file_callback(old_path: str, new_path: str) -> str:
    try:
        p_old = Path(old_path)
        p_new = Path(new_path)
        if not p_old.exists():
            return f"Error: Source '{old_path}' does not exist, Sir."
        p_new.parent.mkdir(parents=True, exist_ok=True)
        os.rename(p_old, p_new)
        return f"Successfully renamed '{old_path}' to '{p_new.name}', Sir."
    except Exception as e:
        return f"Error renaming file: {str(e)}"

def _move_file_callback(src_path: str, dest_path: str) -> str:
    try:
        p_src = Path(src_path)
        if not p_src.exists():
            return f"Error: Source path '{src_path}' does not exist, Sir."
        shutil.move(src_path, dest_path)
        return f"Successfully moved '{src_path}' to '{dest_path}', Sir."
    except Exception as e:
        return f"Error moving file: {str(e)}"

def _delete_file_callback(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: Target path '{path}' does not exist, Sir."
        if p.is_dir():
            shutil.rmtree(p)
            return f"Successfully deleted directory at '{path}', Sir."
        else:
            os.remove(p)
            return f"Successfully deleted file at '{path}', Sir."
    except Exception as e:
        return f"Error deleting file/folder: {str(e)}"

# Gated APIs requiring permissions

def rename_file(old_path: str, new_path: str) -> Union[str, Dict[str, Any]]:
    """
    Rename a file or folder (requires permission).
    """
    pm = PermissionsManager()
    return pm.request_permission(
        action_type="rename_file",
        details={"old_path": old_path, "new_path": new_path},
        callback=lambda: _rename_file_callback(old_path, new_path)
    )

def move_file(src_path: str, dest_path: str) -> Union[str, Dict[str, Any]]:
    """
    Move a file or folder to a new location (requires permission).
    """
    pm = PermissionsManager()
    return pm.request_permission(
        action_type="move_file",
        details={"src_path": src_path, "dest_path": dest_path},
        callback=lambda: _move_file_callback(src_path, dest_path)
    )

def delete_file(path: str) -> Union[str, Dict[str, Any]]:
    """
    Delete a file or folder (requires permission).
    """
    pm = PermissionsManager()
    return pm.request_permission(
        action_type="delete_file",
        details={"path": path},
        callback=lambda: _delete_file_callback(path)
    )
