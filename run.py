import os
import uvicorn
import webbrowser
import threading
import time
from dotenv import load_dotenv
from app.config import logger, HOST, PORT

def open_browser():
    """Wait for the server to spin up, then open the browser."""
    time.sleep(1.5)
    url = f"http://{HOST}:{PORT}"
    logger.info(f"Launching web interface at {url}...")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to open browser automatically: {e}")

if __name__ == "__main__":
    logger.info("Initializing F.R.I.D.A.Y. Cognitive System...")
    
    # Start thread to open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run FastAPI server
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
