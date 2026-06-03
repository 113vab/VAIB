import time
from pathlib import Path
from PIL import ImageGrab
from app.config import logger, DATA_DIR

def capture_screenshot() -> str:
    """
    Captures a full screenshot of the primary monitor and saves it to the data directory.
    Returns the absolute path to the saved image file, or an error message if it fails.
    """
    screenshots_dir = DATA_DIR / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(time.time() * 1000)
    filename = f"screenshot_{timestamp}.png"
    output_path = screenshots_dir / filename
    
    try:
        logger.info("Capturing screen...")
        # ImageGrab.grab() captures the primary screen
        screenshot = ImageGrab.grab()
        screenshot.save(output_path, "PNG")
        logger.info(f"Screenshot saved successfully: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        return f"Failed to capture screenshot, Sir: {e}"
