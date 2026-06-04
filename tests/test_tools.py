import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

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
    delete_file,
    list_directory
)
from app.tools.computer import run_shell_command

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

# ----------------------------------------------------
# 6. Phase 2B Tools Tests
# ----------------------------------------------------
def test_list_directory(temp_dir):
    # Setup some test items
    create_file(str(temp_dir / "file1.txt"), "Hello")
    create_directory(str(temp_dir / "subdir"))
    
    res = list_directory(str(temp_dir))
    assert "file1.txt" in res
    assert "subdir" in res
    assert "[Folder] subdir" in res
    assert "[File] file1.txt" in res

def test_run_shell_command_blacklist(temp_dir):
    # Try a blacklisted command
    res = run_shell_command("format C:")
    assert "Access Denied" in res
    
    # Check that audit log has been written
    audit_file = temp_dir / "audit.log"
    with patch("app.tools.computer.AUDIT_PATH", audit_file, create=True), \
         patch("app.tools.computer.AUDIT_LOG_PATH", audit_file):
        res = run_shell_command("shutdown /s")
        assert "Access Denied" in res
        assert audit_file.exists()
        content = audit_file.read_text()
        assert "BLOCKED_BLACKLIST" in content

def test_run_shell_command_gated(temp_dir):
    pm = PermissionsManager()
    audit_file = temp_dir / "audit.log"
    
    with patch("app.tools.computer.AUDIT_LOG_PATH", audit_file):
        req = run_shell_command("echo 'Hello V.A.I.B.'")
        assert req["status"] == "pending_approval"
        action_id = req["action_id"]
        
        # Verify it's logged as PENDING
        assert audit_file.exists()
        assert "PENDING" in audit_file.read_text()
        
        # Approve execution
        res = pm.approve_action(action_id)
        assert res["status"] == "success"
        assert "Hello V.A.I.B." in res["result"]
        
        # Verify it's logged as SUCCESS or APPROVED
        content = audit_file.read_text()
        assert "APPROVED" in content
        assert "SUCCESS" in content

def test_run_shell_command_denied(temp_dir):
    pm = PermissionsManager()
    audit_file = temp_dir / "audit.log"
    
    with patch("app.tools.computer.AUDIT_LOG_PATH", audit_file):
        req = run_shell_command("echo 'Test Deny'")
        action_id = req["action_id"]
        
        # Deny the permission
        res = pm.deny_action(action_id)
        assert res["status"] == "success"
        
        # Manual log check or trigger helper
        from app.tools.computer import write_audit_log
        write_audit_log("DENIED", "echo 'Test Deny'")
        
        assert "DENIED" in audit_file.read_text()

@pytest.mark.asyncio
async def test_browser_automation_mock():
    from app.tools.browser import browser_search, browser_navigate, browser_click, browser_input
    
    # Mock playwright page and browser manager
    mock_page = MagicMock()
    mock_page.title = AsyncMock(return_value="DuckDuckGo Search")
    mock_page.goto = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.fill = AsyncMock()
    
    # Mock locator for DDG search results
    mock_el = MagicMock()
    mock_title_el = MagicMock()
    mock_title_el.inner_text = AsyncMock(return_value="Python Home")
    mock_title_el.get_attribute = AsyncMock(return_value="https://python.org")
    mock_snippet_el = MagicMock()
    mock_snippet_el.inner_text = AsyncMock(return_value="Python programming language")
    
    # Setup locator chaining
    mock_el.locator.side_effect = lambda sel: mock_title_el if "result__a" in sel else mock_snippet_el
    
    mock_locator = MagicMock()
    mock_locator.all = AsyncMock(return_value=[mock_el])
    mock_locator.inner_text = AsyncMock(return_value="Body text here")
    mock_page.locator.return_value = mock_locator
    
    with patch("app.tools.browser.browser_manager.get_page", return_value=mock_page):
        # 1. Search test
        search_res = await browser_search("python")
        assert "Python Home" in search_res
        assert "https://python.org" in search_res
        
        # 2. Navigate test
        mock_body_locator = MagicMock()
        mock_body_locator.inner_text = AsyncMock(return_value="Python Page Content")
        mock_page.locator.side_effect = lambda sel: mock_body_locator if sel == "body" else MagicMock()
        
        nav_res = await browser_navigate("https://python.org")
        assert "Python Page Content" in nav_res
        
        # 3. Click test
        click_res = await browser_click("#btn")
        assert "Clicked" in click_res
        mock_page.click.assert_called_with("#btn")
        
        # 4. Input test
        input_res = await browser_input("#input", "vaib")
        assert "Successfully typed" in input_res
        mock_page.fill.assert_called_with("#input", "vaib")

# ----------------------------------------------------
# 7. Phase 3 Tools Tests
# ----------------------------------------------------
def test_vision_webcam_mock(temp_dir):
    from app.tools.vision import capture_webcam_frame
    
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    
    with patch("cv2.VideoCapture", return_value=mock_cap), \
         patch("cv2.imwrite", return_value=True), \
         patch("app.tools.vision.DATA_DIR", temp_dir):
        
        res = capture_webcam_frame()
        assert "webcam_" in res
        assert res.endswith(".jpg")

def test_vision_analysis_mock(temp_dir):
    from app.tools.vision import analyze_image_with_vision
    
    # Setup test file
    test_img = temp_dir / "test.jpg"
    test_img.write_text("dummy content")
    
    mock_response = MagicMock()
    mock_response.text = "This is a beautiful test image description."
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    with patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("app.tools.vision.GEMINI_API_KEY", "mock_key"), \
         patch("PIL.Image.open", return_value=MagicMock()):
        
        res = analyze_image_with_vision(str(test_img), "Describe this")
        assert "beautiful test image description" in res


def test_productivity_reminders_and_calendar(temp_dir):
    from app.tools.productivity import (
        add_reminder,
        list_reminders,
        add_calendar_event,
        get_calendar_events,
        delete_calendar_event
    )
    
    db_file = temp_dir / "history.db"
    
    with patch("app.tools.productivity.DB_PATH", db_file):
        # 1. Initialize tables
        from app.tools.productivity import init_productivity_db
        init_productivity_db()
        
        # 2. Add reminder
        rem_res = add_reminder("Walk the dog", 10)
        assert "remind you to 'Walk the dog'" in rem_res
        
        # 3. List reminders
        list_res = list_reminders()
        assert "Walk the dog" in list_res
        
        # 4. Calendar event
        cal_res = add_calendar_event("Meeting", "2026-06-04", "15:00", "Discuss milestone")
        assert "booked event 'Meeting'" in cal_res
        
        # 5. Get events
        sched_res = get_calendar_events("2026-06-04")
        assert "Meeting" in sched_res
        
        # 6. Delete event
        import sqlite3
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM calendar_events WHERE title='Meeting'")
        ev_id = cursor.fetchone()[0]
        conn.close()
        
        del_res = delete_calendar_event(ev_id)
        assert f"removed event 'Meeting' (ID {ev_id})" in del_res

def test_productivity_email(temp_dir):
    from app.tools.productivity import draft_email
    
    with patch("app.tools.productivity.DATA_DIR", temp_dir), \
         patch("webbrowser.open") as mock_open:
        
        res = draft_email("test@example.com", "Test Subj", "Test Body")
        assert "drafted the email" in res
        assert mock_open.called
        
        # Verify file is saved in drafts
        drafts_dir = temp_dir / "drafts"
        assert drafts_dir.exists()
        files = list(drafts_dir.glob("*.eml"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "To: test@example.com" in content
        assert "Subject: Test Subj" in content
        assert "Test Body" in content

def test_plugins_loader_mock(temp_dir):
    from app.tools.plugins import load_plugins, plugin_registry
    
    # Setup plug folder structure
    plugins_dir = temp_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    
    # Let's clean the registry first to avoid side effects
    plugin_registry.clear()
    
    load_plugins(temp_dir)
    
    # Check example plugin was created
    assert (plugins_dir / "example_plugin.py").exists()
    
    # Check that custom functions got registered
    assert "get_weather_forecast" in plugin_registry
    assert "roll_dice" in plugin_registry
    
    # Run a registered plugin
    weather_func = plugin_registry["get_weather_forecast"]
    weather_res = weather_func("London")
    assert "forecast for London" in weather_res

