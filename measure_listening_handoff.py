import subprocess
import time
import sys
import json
from playwright.sync_api import sync_playwright

def run_diagnostics():
    print("--- STARTING V.A.I.B. SERVER FOR LISTENING HANDOFF DIAGNOSTICS ---")
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
            
            # Mock the SpeechRecognition start/stop methods for headless environments
            page.evaluate("""
                if (window.streamingRecognizer) {
                    window.streamingRecognizer.start = function() {
                        window.streamingActive = true;
                        if (this.onstart) this.onstart();
                    };
                    window.streamingRecognizer.stop = function() {
                        window.streamingActive = false;
                        if (this.onend) this.onend();
                    };
                }
            """)
            
            # Trigger a long speech response
            print("\nSubmitting query...")
            page.fill("#chat-input", "Tell me a long story.")
            page.click("#chat-form button[type='submit']")
            
            # Wait for speaking state
            print("Waiting for speaking state...")
            page.wait_for_function("window.voiceSessionManager.state === 'speaking'", timeout=20000)
            
            print("VAIB is speaking. Simulating user interruption...")
            page.evaluate("""
                window.vadEngine.emit('user.interrupted', {
                    rms: 0.08,
                    threshold: 0.03,
                    confidence: 85,
                    timestamp: Date.now(),
                    detectionLatency: 275
                });
            """)
            
            # Wait for Listening state
            print("Waiting for listening state...")
            page.wait_for_function("window.voiceSessionManager.state === 'listening'", timeout=5000)
            
            # Verify microphone and STT are active
            is_mic_active = page.evaluate("window.voiceSessionManager.vad.micStream !== null")
            is_stt_active = page.evaluate("window.streamingActive")
            
            # Simulate streaming STT input to measure first transcript latency
            print("Simulating streaming STT result...")
            page.evaluate("""
                if (window.streamingRecognizer && window.streamingRecognizer.onresult) {
                    const event = {
                        resultIndex: 0,
                        results: [
                            {
                                isFinal: false,
                                0: { transcript: "hello, please stop speaking" }
                            }
                        ]
                    };
                    window.streamingRecognizer.onresult(event);
                }
            """)
            
            # Wait for metrics to populate
            page.wait_for_function("window.interruptionMetrics && window.interruptionMetrics.firstTranscriptLatency !== null", timeout=5000)
            
            metrics = page.evaluate("window.interruptionMetrics")
            state = page.evaluate("window.voiceSessionManager.state")
            is_playing = page.evaluate("window.ttsPipeline.isPlaying")
            queue_len = page.evaluate("window.ttsPipeline.queue.length")
            
            # Count the number of messages in the chat area to make sure no new response was generated
            chat_count = page.locator("#chat-messages .chat-bubble").count()
            
            print(f"\n--- INTERRUPTION & LISTENING HANDOFF METRICS ---")
            print(f"HUD State: {state}")
            print(f"Is TTS Playback Active: {is_playing}")
            print(f"TTS Queue Length: {queue_len}")
            print(f"Is Mic Capture Active: {is_mic_active}")
            print(f"Is Streaming STT Active: {is_stt_active}")
            print(f"Number of Chat Bubbles: {chat_count} (Expected: 3 - Welcome + User query + Cancelled assistant query)")
            print(f"Interruption Detection Latency: {metrics['detectionLatency']}ms")
            print(f"Speech Stop Latency: {metrics['speechStopLatency']}ms")
            print(f"Listening Handoff/Activation Latency: {metrics['listeningActivationLatency']}ms")
            print(f"First Transcript Latency: {metrics['firstTranscriptLatency']}ms")
            
            success = (
                state == "listening" and
                is_playing == False and
                queue_len == 0 and
                is_mic_active == True and
                is_stt_active == True and
                chat_count <= 3
            )
            
            if success:
                print("\nSUCCESS: User speech successfully cut off VAIB, transitioned to active listening, and captured transcription without LLM call!")
                with open("handoff_metrics.json", "w") as f:
                    json.dump(metrics, f)
                sys.exit(0)
            else:
                print("\nFAIL: Handoff was not successful or state did not transition.")
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
