# Listening Handoff Timing Trace

This report documents the detailed timing trace measured during the validation of Phase 5E-C: Automatic Listening Handoff.

## Listening Handoff Event Log (Simulation Run)

The metrics below trace the sequence of events from user query submission to active speech playback, simulated user interruption, instant speech termination, automatic transition into active listening, and capturing the user's spoken stream:

| Relative Time (ms) | Milestone | Event Detail / Text Content |
| --- | --- | --- |
| `+0ms` | **User Query Submitted** | *"Tell me a long story."* |
| `+5087ms` | **First Token Received** | LLM begins streaming text chunks. |
| `+5559ms` | **First Sentence Detected** | Sentence boundary matches first complete block: *"I am currently operating in simulation mode, Sir."* |
| `+5650ms` | **First TTS Request Dispatched** | Asynchronous fetch is sent to `/api/tts` for the first sentence. |
| `+7311ms` | **First Audio Returned** | Edge-TTS server synthesizes and returns the audio URL to the browser. |
| `+7340ms` | **First Audio Playback Started** | Speech playback begins for the first sentence chunk. |
| `+7340ms` | **User Starts Speaking** | User speech begins to bleed into active playback input. |
| `+7615ms` | **User Interruption Detected** | VAD detects sustained speech (6 frames) and emits `user.interrupted` event. State changes to `SpeechInterrupted`. Latency: **`275ms`**. |
| `+7619ms` | **Speech Playback Stopped** | Audio playback terminates instantly. Internal stop latency: **`4ms`**. |
| `+7621ms` | **Listening Activated** | Session state transitions to `listening`. Mic stream is confirmed active. Streaming STT starts. Activation latency: **`2ms`**. |
| `+7646ms` | **First Transcript Received** | Streaming STT returns first simulated transcript slice. Latency: **`25ms`**. |

---

## Technical Details

### 1. State Transition Pipeline
*   **State Progression**: Speaking $\rightarrow$ `SpeechInterrupted` $\rightarrow$ `listening`.
*   **Safety Assurance**: The transition from `SpeechInterrupted` to `listening` is automatically managed in a `setTimeout` callback. This guarantees that the UI has sufficient cycles to render the cutoff warning and register metrics before entering `listening` state.

### 2. Latency Measurement Heuristics
*   **Interruption Detection Latency**: Measured from the start of user speech energy detection (first VAD speech frame during playback) to the emission of the `user.interrupted` event. Sustaining speech for 6 frames (~270ms) ensures high confidence ($85\%$), with a final detection latency of **`275ms`**.
*   **Speech Stop Latency**: Synchronous pause of the audio track and queue clearing executes in **`4ms`**.
*   **Listening Handoff/Activation Latency**: The time required to activate mic capture and start the Web Speech API streaming recognition engine. This registers at **`2ms`**.
*   **First Transcript Latency**: Measured from the activation of the listening state to the arrival of the first character stream from the STT engine. The mock registers this at **`25ms`**.

### 3. Response Generation Suppression
*   **Constraint Verification**: The `VoiceSessionManager` sets a boolean flag `this.interruptedAndListening = true` immediately upon interruption. When the Whisper STT transcription completes, `processCommand()` intercepts the text, logs it, clears the flag, and returns without invoking the LLM pipeline (`llmPipeline.process()`). No new bubble or response is generated.
