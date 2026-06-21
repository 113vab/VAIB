import subprocess
import time
import sys
from playwright.sync_api import sync_playwright

def run_diagnostics():
    print("--- STARTING V.A.I.B. SERVER FOR INTERRUPTION STOP DIAGNOSTICS ---")
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
            
            # Click to unlock audio context
            page.click("body")
            
            # Trigger a long speech response
            print("\nSubmitting query...")
            page.fill("#chat-input", "Tell me a long story.")
            page.click("#chat-form button[type='submit']")
            
            # Wait for speaking state
            print("Waiting for speaking state...")
            page.wait_for_function("window.voiceSessionManager.state === 'speaking'", timeout=20000)
            
            print("VAIB is speaking. Simulating user interruption...")
            start_trigger = time.time()
            page.evaluate("""
                window.vadEngine.emit('user.interrupted', {
                    rms: 0.08,
                    threshold: 0.03,
                    confidence: 85,
                    timestamp: Date.now()
                });
            """)
            
            # Wait for SpeechInterrupted state
            print("Waiting for SpeechInterrupted state...")
            page.wait_for_function("window.voiceSessionManager.state === 'SpeechInterrupted'", timeout=5000)
            stop_time = time.time()
            
            state = page.evaluate("window.voiceSessionManager.state")
            is_playing = page.evaluate("window.ttsPipeline.isPlaying")
            queue_len = page.evaluate("window.ttsPipeline.queue.length")
            
            print(f"\n--- INTERRUPT STOP METRICS ---")
            print(f"HUD State: {state}")
            print(f"Is TTS Playback Active: {is_playing}")
            print(f"TTS Queue Length: {queue_len}")
            print(f"Speech Stop Time (from trigger): {(stop_time - start_trigger)*1000:.1f}ms")
            
            if state == "SpeechInterrupted" and is_playing == False and queue_len == 0:
                print("\nSUCCESS: User speech successfully cut off VAIB playback instantly!")
                sys.exit(0)
            else:
                print("\nFAIL: Playback was not stopped or state did not transition.")
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
