import subprocess
import time
import sys
import asyncio
from playwright.sync_api import sync_playwright

def run_diagnostics():
    print("--- STARTING V.A.I.B. SERVER FOR DIAGNOSTICS ---")
    # 1. Start the FastAPI server as a subprocess
    server_process = subprocess.Popen(
        [sys.executable, "run.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print("Starting V.A.I.B. server process...")
    
    # Wait for server to output startup confirmation or wait 9 seconds
    time.sleep(12.0)
    
    print("\n--- LAUNCHING CHROMIUM VIA PLAYWRIGHT ---")
    try:
        with sync_playwright() as p:
            # Launch chromium in headless mode with microphone flags enabled
            browser = p.chromium.launch(
                headless=True,
                args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            )
            page = browser.new_page()
            
            # Timestamp monitoring list
            events = []
            start_time = None
            
            # Listen to console logs
            def on_console(msg):
                nonlocal start_time
                text = msg.text
                elapsed = time.time() - start_time if start_time else 0.0
                print(f"[{elapsed:.3f}s] BROWSER CONSOLE: {text}")
                events.append((elapsed, text))
            
            page.on("console", on_console)
            page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err.message}"))
            
            page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
            print("Dashboard loaded successfully.")
            
            # Submit a warm-up prompt
            print("\nSubmitting warm-up query...")
            start_time = time.time()
            page.fill("#chat-input", "Warm up query.")
            page.click("#chat-form button[type='submit']")
            page.wait_for_timeout(8000)
            
            # Submit a multi-sentence prompt
            print("\nSubmitting main diagnostic query...")
            start_time = time.time()
            page.fill("#chat-input", "Write a short reply with three sentences. Each sentence should end with a period.")
            page.click("#chat-form button[type='submit']")
            page.wait_for_function("window.lastTotalResponseLatency !== null", timeout=60000)
            page.wait_for_timeout(3000)
            
            print("\n--- LATENCY DIAGNOSTICS COMPLETED ---")
            browser.close()
            
    except Exception as e:
        print(f"Error during playwright run: {e}")
    finally:
        print("Terminating server...")
        server_process.terminate()
        try:
            pass
        except Exception:
            pass
        server_process.wait()
        print("Server shutdown.")

if __name__ == "__main__":
    run_diagnostics()
