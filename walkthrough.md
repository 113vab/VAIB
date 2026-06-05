# VAIB Voice Module Walkthrough: Phase 4D Advanced Voice Assistant

Welcome to the walkthrough of the Advanced Voice Assistant subsystem. This document outlines the event-driven architecture, components, and how to verify the new voice capabilities of V.A.I.B.

---

## 1. Modular Event-Driven Architecture

The voice module is split into decoupled, standalone pipelines that communicate using an event emitter pattern. This design allows you to easily swap turn-based implementations for streaming WebSockets/WebRTC in Phase 5 without refactoring core elements.

### Architecture Layout:
* **`EventEmitter`**: Simple base class providing `.on()`, `.off()`, and `.emit()` mechanics for asynchronous decoupled signaling.
* **`VADEngine`**: Wraps the HTML5 Web Audio API (`AudioContext`, `AnalyserNode`, `ScriptProcessorNode`) to perform real-time Voice Activity Detection.
  * Computes Root Mean Square (RMS) energy.
  * Dynamically computes noise floor to adapt to background hums.
  * Auto-starts/stops recording buffers based on speech triggers.
* **`STTPipeline`**: Encapsulates sending audio chunks to the `/api/stt` endpoint.
* **`LLMPipeline`**: Encapsulates posting messages to the brain (`/api/chat`), logging events, updating chat history panels, and reloading memory profiles.
* **`TTSPipeline`**: Manages synthesizing edge-tts speech (`/api/tts`) and handles playback, pause, and user interruption signals.
* **`VoiceSessionManager`**: The global state orchestrator that controls transitions between HUD states (`Idle`, `Listening`, `Processing`, `Speaking`).

---

## 2. Voice State Machine & HUD

The Dashboard includes a new **Voice Configuration HUD** display showing:
1. **Auto-Wake Mode Toggle**: Switch between Hold-To-Talk manual overrides and Continuous Voice monitoring.
2. **VAD Sensitivity Slider**: Adjust the sensitivity margin for the speech detection engine.
3. **Voice State**: Shows the active status:
   * **`IDLE`** (Standby, waiting for wake word)
   * **`LISTENING`** (Mic active, capturing speech)
   * **`PROCESSING`** (FastAPI / local Whisper transcribing / Brain thinking)
   * **`SPEAKING`** (Vocalizing responses)

---

## 3. Core Behaviors

### Wake Word Detection
When in Auto-Wake mode and the state is `Idle`, the mic is continuously monitored in the background. 
* Speech segments are recorded and transcribed.
* If a segment starts with or contains **"Hey VAIB"** or **"VAIB"** (case-insensitive, boundary-matched):
  1. A static **wake chime** (`wake.mp3`) is played.
  2. The state switches to `Listening`.
  3. Any command following the wake word in the same utterance is immediately extracted and processed.

### Voice Activity Detection (VAD)
* **Start of Speech**: Triggered when the mic level exceeds the adaptive threshold for 90ms.
* **End of Speech**: Triggered when the level stays below the threshold for 1.1 seconds, preventing truncation.

### Interruptible TTS
If the assistant is speaking (`Speaking` state) and the VAD engine detects the user speaking:
1. Playback of the TTS audio is immediately paused (`ttsPipeline.interrupt()`).
2. A status message is logged: `[SYSTEM] Vocal interruption detected.`
3. The HUD transitions to `Listening` and starts recording the new query.

### Hold-To-Talk Integration
* Holding down the mic button starts a manual override recording.
* If Continuous Listening was active, it is temporarily paused to avoid double-processing.
* Once the manual speech playback is complete, Continuous Listening resumes automatically.

---

## 4. Verification Steps

1. Start the server using:
   ```bash
   .\venv\Scripts\python.exe run.py
   ```
2. Open the browser interface at `http://127.0.0.1:8000`.
3. Check the **Voice Config** HUD under the mic button.
4. Toggle **Continuous Voice (Auto-Wake)** ON. The state indicator will show **IDLE**.
5. Say **"Hey VAIB"** or **"VAIB"**. Confirm:
   - The wake chime plays.
   - The state changes to **LISTENING**.
6. Say a command, e.g., **"What is your name?"**
   - Confirm it goes to **PROCESSING**, then **SPEAKING**.
   - Confirm the assistant responds vocalizing "My name is VAIB..."
7. While the assistant is speaking, say **"Hey VAIB, show me facts"**.
   - Confirm speech stops immediately.
   - Confirm it records, transcribes, and responds to the new query.
8. Let the system remain silent for 30 seconds.
   - Confirm the standby chime plays.
   - Confirm the HUD state transitions back to **IDLE**.
