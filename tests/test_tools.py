import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.tools.permissions import PermissionsManager
from app.tools.clipboard import read_clipboard, write_clipboard
from app.tools.screenshot import capture_screenshot
from app.tools.app_control import open_app, close_app, check_app_running
from app.tools.file_manager import (
    create_file,
    create_directory,
    read_file,
    rename_file,
    move_file,
    delete_file
)

@pytest.fixture(autouse=True)
def clean_permissions():
    """Reset PermissionsManager state before and after each test."""
    pm = PermissionsManager()
    pm.clear_all()
    yield
    pm.clear_all()

@pytest.fixture
def temp_dir():
    """Create a temporary directory for file system tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    try:
        shutil.rmtree(temp_path)
    except Exception:
        pass

# ----------------------------------------------------
# 1. PermissionsManager Tests
# ----------------------------------------------------
def test_permissions_manager_flow():
    pm = PermissionsManager()
    callback_mock = MagicMock(return_value="executed")
    
    # Request permission
    req = pm.request_permission("test_action", {"param": 1}, callback_mock)
    assert req["status"] == "pending_approval"
    assert "action_id" in req
    action_id = req["action_id"]
    
    # Check pending list
    pending = pm.get_pending_actions()
    assert len(pending) == 1
    assert pending[0]["id"] == action_id
    assert pending[0]["type"] == "test_action"
    
    # Approve action
    res = pm.approve_action(action_id)
    assert res["status"] == "success"
    assert res["result"] == "executed"
    callback_mock.assert_called_once()
    
    # Check status is approved
    status = pm.get_action_status(action_id)
    assert status["status"] == "approved"
    assert status["result"] == "executed"

def test_permissions_manager_deny():
    pm = PermissionsManager()
    callback_mock = MagicMock()
    req = pm.request_permission("test_action", {}, callback_mock)
    action_id = req["action_id"]
    
    # Deny action
    res = pm.deny_action(action_id)
    assert res["status"] == "success"
    callback_mock.assert_not_called()
    
    status = pm.get_action_status(action_id)
    assert status["status"] == "denied"

# ----------------------------------------------------
# 2. Clipboard Tests
# ----------------------------------------------------
@patch("subprocess.run")
def test_read_clipboard(mock_run):
    # Mock powershell Get-Clipboard output
    mock_run.return_value = MagicMock(stdout="Hello from Clipboard\r\n", returncode=0)
    text = read_clipboard()
    assert text == "Hello from Clipboard"
    mock_run.assert_called_once()
    assert "Get-Clipboard" in mock_run.call_args[0][0]

@patch("subprocess.run")
def test_write_clipboard(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    res = write_clipboard("VAIB text")
    assert "copied to clipboard" in res
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["input"] == "VAIB text"

# ----------------------------------------------------
# 3. Screenshot Tests
# ----------------------------------------------------
@patch("PIL.ImageGrab.grab")
def test_capture_screenshot(mock_grab, temp_dir):
    # Mock ImageGrab save
    mock_img = MagicMock()
    mock_grab.return_value = mock_img
    
    with patch("app.tools.screenshot.DATA_DIR", temp_dir):
        res_path_str = capture_screenshot()
        assert "Failed" not in res_path_str
        res_path = Path(res_path_str)
        assert res_path.parent == temp_dir / "screenshots"
        assert res_path.suffix == ".png"
        assert mock_grab.called
        assert mock_img.save.called

# ----------------------------------------------------
# 4. App Control Tests
# ----------------------------------------------------
@patch("subprocess.Popen")
def test_open_app_notepad(mock_popen):
    res = open_app("notepad")
    assert "Opened notepad successfully" in res
    mock_popen.assert_called_once()
    assert mock_popen.call_args[0][0] == ["notepad.exe"]

@patch("subprocess.Popen")
def test_open_app_chrome(mock_popen):
    res = open_app("chrome")
    assert "Opened chrome successfully" in res
    mock_popen.assert_called_once()
    # Chrome uses shell=True "start chrome"
    assert mock_popen.call_args[0][0] == "start chrome"
    assert mock_popen.call_args[1]["shell"] is True

@patch("subprocess.run")
def test_check_app_running(mock_run):
    # App is running
    mock_run.return_value = MagicMock(stdout="notepad.exe  1234 Console", returncode=0)
    res = check_app_running("notepad")
    assert "is currently running" in res
    
    # App is not running
    mock_run.return_value = MagicMock(stdout="INFO: No tasks are running", returncode=0)
    res2 = check_app_running("notepad")
    assert "is not running" in res2

@patch("subprocess.run")
def test_close_app_gated(mock_run):
    pm = PermissionsManager()
    
    # Trigger close app
    req = close_app("notepad")
    assert req["status"] == "pending_approval"
    action_id = req["action_id"]
    
    # Mock taskkill run
    mock_run.return_value = MagicMock(returncode=0)
    
    # Approve closure
    res = pm.approve_action(action_id)
    assert res["status"] == "success"
    assert "Closed notepad successfully" in res["result"]
    
    mock_run.assert_called_once()
    assert "taskkill" in mock_run.call_args[0][0]
    assert "notepad.exe" in mock_run.call_args[0][0]

# ----------------------------------------------------
# 5. File Manager Tests
# ----------------------------------------------------
def test_file_manager_crud(temp_dir):
    file_path = temp_dir / "test_file.txt"
    dir_path = temp_dir / "test_subdir"
    
    # Create file
    create_res = create_file(str(file_path), "Hello VAIB File")
    assert "created file" in create_res
    assert file_path.exists()
    
    # Read file
    read_res = read_file(str(file_path))
    assert read_res == "Hello VAIB File"
    
    # Create directory
    dir_res = create_directory(str(dir_path))
    assert "created folder directory" in dir_res
    assert dir_path.exists()

def test_file_manager_rename_gated(temp_dir):
    pm = PermissionsManager()
    old_file = temp_dir / "old.txt"
    new_file = temp_dir / "new.txt"
    
    # Setup source file
    create_file(str(old_file), "content")
    
    # Rename request
    req = rename_file(str(old_file), str(new_file))
    assert req["status"] == "pending_approval"
    action_id = req["action_id"]
    
    # Approve rename
    res = pm.approve_action(action_id)
    assert res["status"] == "success"
    assert not old_file.exists()
    assert new_file.exists()
    assert "Successfully renamed" in res["result"]

def test_file_manager_move_gated(temp_dir):
    pm = PermissionsManager()
    src_file = temp_dir / "src.txt"
    dest_dir = temp_dir / "subdir"
    dest_file = dest_dir / "src.txt"
    
    create_file(str(src_file), "content")
    create_directory(str(dest_dir))
    
    # Move request
    req = move_file(str(src_file), str(dest_file))
    assert req["status"] == "pending_approval"
    action_id = req["action_id"]
    
    # Approve move
    res = pm.approve_action(action_id)
    assert res["status"] == "success"
    assert not src_file.exists()
    assert dest_file.exists()

def test_file_manager_delete_gated(temp_dir):
    pm = PermissionsManager()
    file_path = temp_dir / "delete_me.txt"
    
    create_file(str(file_path), "content")
    
    # Delete request
    req = delete_file(str(file_path))
    assert req["status"] == "pending_approval"
    action_id = req["action_id"]
    
    # Approve delete
    res = pm.approve_action(action_id)
    assert res["status"] == "success"
    assert not file_path.exists()
    assert "Successfully deleted file" in res["result"]
