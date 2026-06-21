import subprocess
import time
import sys
import json
from playwright.sync_api import sync_playwright

def run_diagnostics():
    print("--- STARTING V.A.I.B. SERVER FOR DUPLEX CONVERSATION DIAGNOSTICS ---")
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
            print("\nSubmitting first query...")
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
            
            # Mock STT transcribe to return the capital of France query
            page.evaluate("""
                window.sttPipeline.transcribe = async function(blob) {
                    return "What is the capital of France?";
                };
            """)
            
            # Simulate streaming STT result
            print("Simulating streaming STT result...")
            page.evaluate("""
                if (window.streamingRecognizer && window.streamingRecognizer.onresult) {
                    const event = {
                        resultIndex: 0,
                        results: [
                            {
                                isFinal: false,
                                0: { transcript: "What is the capital of France?" }
                            }
                        ]
                    };
                    window.streamingRecognizer.onresult(event);
                }
            """)
            
            # Sleep slightly to let first transcript latency record
            time.sleep(0.5)
            
            # Trigger VAD audio ready to finish the query and trigger LLM processing
            print("Simulating VAD speech completion (audio.ready)...")
            page.evaluate("""
                const dummyBlob = new Blob(["dummy audio"], { type: "audio/webm" });
                window.vadEngine.emit("audio.ready", dummyBlob);
            """)
            
            # Wait for speaking state again (meaning the second response has started playback!)
            print("Waiting for VAIB to speak the new response...")
            page.wait_for_function("window.voiceSessionManager.state === 'speaking'", timeout=20000)
            
            metrics = page.evaluate("window.interruptionMetrics")
            state = page.evaluate("window.voiceSessionManager.state")
            is_playing = page.evaluate("window.ttsPipeline.isPlaying")
            
            # Count the number of messages in the chat area to make sure the response was generated
            chat_count = page.locator("#chat-messages .chat-bubble").count()
            last_message = page.locator("#chat-messages .chat-bubble").last.inner_text()
            
            print(f"\n--- DUPLEX CONVERSATION METRICS ---")
            print(f"HUD State: {state}")
            print(f"Is TTS Playback Active: {is_playing}")
            print(f"Number of Chat Bubbles: {chat_count} (Expected: 5)")
            print(f"Last Chat Bubble Content:\n{last_message}")
            print(f"Interruption Detection Latency: {metrics['detectionLatency']}ms")
            print(f"Speech Stop Latency: {metrics['speechStopLatency']}ms")
            print(f"Listening Handoff/Activation Latency: {metrics['listeningActivationLatency']}ms")
            print(f"First Transcript Latency: {metrics['firstTranscriptLatency']}ms")
            print(f"First Token Latency: {metrics['firstTokenLatency']}ms")
            print(f"First Spoken Sentence Latency: {metrics['firstSpokenSentenceLatency']}ms")
            
            success = (
                state == "speaking" and
                is_playing == True and
                chat_count >= 4 and
                metrics['firstTokenLatency'] is not None and
                metrics['firstSpokenSentenceLatency'] is not None
            )
            
            if success:
                print("\nSUCCESS: VAIB was interrupted, automatically listened, processed the new query, and began speaking the response!")
                with open("duplex_metrics.json", "w") as f:
                    json.dump(metrics, f)
                sys.exit(0)
            else:
                print("\nFAIL: Full duplex loop was not completed successfully.")
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
