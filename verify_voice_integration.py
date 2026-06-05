import subprocess
import time
import sys
from playwright.sync_api import sync_playwright

def run_verification():
    print("--- COMMENCING AUTOMATED VOICE HUD INTEGRATION VERIFICATION ---")
    
    # 1. Start the FastAPI server as a subprocess
    server_process = subprocess.Popen(
        [sys.executable, "run.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("Starting V.A.I.B. server process...")
    time.sleep(3.0)  # Wait for server to spin up and load
    
    tests_passed = 0
    total_tests = 5
    report = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            )
            page = browser.new_page()
            
            # Capture browser console output
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
            page.on("pageerror", lambda err: print(f"BROWSER EXCEPTION: {err.message}"))
            
            page.goto("http://127.0.0.1:8000")
            print("Successfully loaded V.A.I.B. Dashboard in headless browser.")
            
            # --- TEST 1: HUD Element Presence ---
            print("\nVerification 1: Checking HUD Elements Presence...")
            toggle_exist = page.locator("#toggle-continuous-voice").count() > 0
            slider_exist = page.locator("#slider-mic-threshold").count() > 0
            state_hud_exist = page.locator("#voice-hud-state").count() > 0
            
            if toggle_exist and slider_exist and state_hud_exist:
                print("SUCCESS: Auto-Wake Toggle, VAD Slider, and State HUD elements found.")
                tests_passed += 1
                report.append("Element Presence: PASSED")
            else:
                print(f"FAIL: Missing elements (Toggle: {toggle_exist}, Slider: {slider_exist}, HUD: {state_hud_exist})")
                report.append("Element Presence: FAILED")

            # --- TEST 2: VoiceSessionManager Initialization ---
            print("\nVerification 2: Checking VoiceSessionManager Object Initialization...")
            is_initialized = page.evaluate("typeof window.voiceSessionManager !== 'undefined'")
            if is_initialized:
                initial_state = page.evaluate("window.voiceSessionManager.state")
                initial_mode = page.evaluate("window.voiceSessionManager.mode")
                print(f"SUCCESS: VoiceSessionManager initialized. State: '{initial_state}', Mode: '{initial_mode}'")
                if initial_state == "idle" and initial_mode == "manual":
                    tests_passed += 1
                    report.append("VoiceSessionManager Init: PASSED")
                else:
                    print(f"FAIL: Unexpected initial state/mode: State={initial_state}, Mode={initial_mode}")
                    report.append("VoiceSessionManager Init: FAILED")
            else:
                print("FAIL: window.voiceSessionManager is undefined")
                report.append("VoiceSessionManager Init: FAILED")

            # --- TEST 3: Auto-Wake Toggle Behavior ---
            print("\nVerification 3: Toggling Auto-Wake (Continuous Voice) Mode...")
            # Click the switch slider
            page.locator(".switch span.slider").click()
            time.sleep(1.0)
            
            mode_after_toggle = page.evaluate("window.voiceSessionManager.mode")
            state_after_toggle = page.evaluate("window.voiceSessionManager.state")
            print(f"SUCCESS: Mode after toggle: '{mode_after_toggle}', State: '{state_after_toggle}'")
            if mode_after_toggle == "auto-wake" and state_after_toggle == "idle":
                tests_passed += 1
                report.append("Auto-Wake Mode Toggle: PASSED")
            else:
                print("FAIL: Failed to transition into auto-wake mode.")
                report.append("Auto-Wake Mode Toggle: FAILED")

            # --- TEST 4: VAD Trigger State Transitions ---
            print("\nVerification 4: Simulating VAD Speech Triggers...")
            # Emit speech.start event on VADEngine
            page.evaluate("window.vadEngine.emit('speech.start')")
            time.sleep(0.5)
            state_after_speech_start = page.evaluate("window.voiceSessionManager.state")
            print(f"State after VAD speech start event: '{state_after_speech_start}'")
            
            if state_after_speech_start == "listening":
                tests_passed += 1
                report.append("VAD State Transition: PASSED")
            else:
                print("FAIL: State did not transition to listening on VAD trigger.")
                report.append("VAD State Transition: FAILED")

            # --- TEST 5: Interruptible Speech TTS Interrupt ---
            print("\nVerification 5: Verifying Interruptible TTS Playback Interruption...")
            # Set manager state to speaking to simulate active Edge-TTS play
            page.evaluate("window.voiceSessionManager.state = 'speaking'")
            
            # Emit speech.start event which should interrupt TTS and return to listening
            page.evaluate("window.vadEngine.emit('speech.start')")
            time.sleep(0.5)
            
            state_after_interrupt = page.evaluate("window.voiceSessionManager.state")
            print(f"State after VAD interrupt event: '{state_after_interrupt}'")
            
            if state_after_interrupt == "listening":
                tests_passed += 1
                report.append("Interruptible TTS: PASSED")
            else:
                print("FAIL: State did not interrupt speaking state to return to listening.")
                report.append("Interruptible TTS: FAILED")

            browser.close()

    except Exception as e:
        print(f"Playwright automation encountered an error: {e}")
        report.append(f"Automation Error: {e}")
    finally:
        print("\nShutting down server process...")
        server_process.terminate()
        server_process.wait()

    print("\n--- FINAL VERIFICATION REPORT ---")
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    for item in report:
        print(f"- {item}")
        
    if tests_passed == total_tests:
        print("\nSUCCESS: All automated Voice Subsystem integrations verified successfully!")
        sys.exit(0)
    else:
        print("\nFAIL: One or more integration verifications failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
