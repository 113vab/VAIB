# Interruption Stop Timing Trace

This report documents the detailed timing trace measured during the validation of Phase 5E-B: Instant Speech Stop.

## Interruption Stop Event Log (Simulation Run)

The metrics below trace the sequence of events from user query submission to active speech playback, simulated user interruption, and instant speech termination:

| Relative Time (ms) | Milestone | Event Detail / Text Content |
| --- | --- | --- |
| `+0ms` | **User Query Submitted** | *"Tell me a long story."* |
| `+4122ms` | **First Token Received** | LLM begins streaming text chunks. |
| `+4593ms` | **First Sentence Detected** | Sentence boundary matches first complete block: *"I am currently operating in simulation mode, Sir."* |
| `+4687ms` | **First TTS Request Dispatched** | Asynchronous fetch is sent to `/api/tts` for the first sentence. |
| `+6039ms` | **First Audio Returned** | Edge-TTS server synthesizes and returns the audio URL to the browser. |
| `+6072ms` | **First Audio Playback Started** | Speech playback begins for the first sentence chunk. |
| `+6075ms` | **User Interruption Triggered** | Simulating user interruption input: RMS `0.08`, threshold `0.03`, confidence `85%`. |
| `+6082ms` | **Interruption Logic Activated** | `tts.interrupt()` called. Current audio paused. Queue cleared. |
| `+6089ms` | **Speech Playback Stopped** | Audio playback terminates instantly. Internal stop latency: **`7ms`**. |
| `+6090ms` | **State Transited & HUD Updated** | Manager state changes to **`SpeechInterrupted`**. Action subtext shows *"SPEECH INTERRUPTED"*. |
| `+6104ms` | **User Speech Cut Off Verified** | Total elapsed trigger-to-state verification time: **`29.4ms`**. Playback is inactive. |

---

## Technical Details

### 1. Instant Speech Termination Heuristic
When the system validates a user interruption:
*   **Active Playback Cut-off**: `this.audio.pause()` is called synchronously on the `<audio>` element to stop the current speaking sentence immediately.
*   **Queue Purge**: `this.queue = []` and `this.ttsRequestQueue = []` are cleared to discard any pre-fetched or pending sentences, preventing subsequent speech.
*   **Stop Latency**: The internal API stop latency is measured in milliseconds from the start of `interrupt()` execution to the completion of the pause call. Our run measures this at **`7ms`**.

### 2. State & Safety Measures
*   **SpeechInterrupted State**: The system transitions to the new `SpeechInterrupted` state and stays there. Inactivity timers are suspended, and VAD audio processing is ignored to prevent generating new responses or transcribing commands until Phase 5E-C.
*   **Playback Abort Handling**: In modern browsers, calling `audio.pause()` on a pending `play()` promise throws an `AbortError`. We refactored `playNext()` to catch and ignore `AbortError` specifically, preventing it from calling `playNext()` again, which would have prematurely emitted `"play.end"` and reset the state.
