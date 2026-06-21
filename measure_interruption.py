import subprocess
import time
import sys
from playwright.sync_api import sync_playwright

def run_diagnostics():
    print("--- STARTING V.A.I.B. SERVER FOR INTERRUPTION DIAGNOSTICS ---")
    server_process = subprocess.Popen(
        [sys.executable, "run.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print("Starting V.A.I.B. server process...")
    time.sleep(12.0)
    
    print("\n--- LAUNCHING CHROMIUM VIA PLAYWRIGHT ---")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            )
            page = browser.new_page()
            
            # Listen to console logs
            def on_console(msg):
                print(f"BROWSER CONSOLE: {msg.text}")
            page.on("console", on_console)
            page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err.message}"))
            
            page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
            print("Dashboard loaded successfully.")
            
            # Click the body to trigger audio context unlock
            page.click("body")
            
            # Submit a query to trigger speaking
            print("\nSubmitting query to trigger TTS playback...")
            page.fill("#chat-input", "Tell me a long story with three sentences.")
            page.click("#chat-form button[type='submit']")
            
            # Wait for speaking state
            print("Waiting for speaking state...")
            page.wait_for_function("window.voiceSessionManager.state === 'speaking'", timeout=20000)
            
            print("VAIB is speaking. Simulating user interruption...")
            # Simulate user interruption on VADEngine
            page.evaluate("""
                window.vadEngine.emit('user.interrupted', {
                    rms: 0.08,
                    threshold: 0.03,
                    confidence: 85,
                    timestamp: Date.now()
                });
            """)
            
            time.sleep(2.0)
            
            # Verify status in DOM
            status = page.locator("#interruption-status").inner_text()
            confidence = page.locator("#interruption-confidence").inner_text()
            timestamp = page.locator("#interruption-timestamp").inner_text()
            state = page.evaluate("window.voiceSessionManager.state")
            is_playing = page.evaluate("window.ttsPipeline.isPlaying")
            
            print(f"\n--- INTERRUPT VERIFICATION METRICS ---")
            print(f"HUD State: {state}")
            print(f"Interruption Status in HUD: {status}")
            print(f"Interruption Confidence: {confidence}")
            print(f"Interruption Timestamp: {timestamp}")
            print(f"Is TTS Playback Active: {is_playing}")
            
            if state == "UserInterruptDetected" and status == "DETECTED" and is_playing == True:
                print("\nSUCCESS: User interruption detected successfully while VAIB continues speaking!")
                sys.exit(0)
            else:
                print("\nFAIL: Interruption did not register correctly or playback was stopped.")
                sys.exit(1)
                
            browser.close()
            
    except Exception as e:
        print(f"Error during playwright run: {e}")
        sys.exit(1)
    finally:
        print("Terminating server...")
        server_process.terminate()
        server_process.wait()
        print("Server shutdown.")

if __name__ == "__main__":
    run_diagnostics()
