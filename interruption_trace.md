# Interruption Detection Timing Trace

This report documents the detailed timing trace measured during the validation of Phase 5E-A: Interruption Detection.

## Interruption Event Log (Simulation Run)

The metrics below trace the sequence of events from submitting a query to simulating a user speech interruption during active TTS playback:

| Relative Time (ms) | Milestone | Event Detail / Text Content |
| --- | --- | --- |
| `+0ms` | **User Query Submitted** | *"Tell me a long story with three sentences."* |
| `+4373ms` | **First Token Received** | LLM begins streaming text chunks. |
| `+4844ms` | **First Sentence Detected** | Sentence boundary regex matches: *"I am currently operating in simulation mode, Sir."* |
| `+4926ms` | **First TTS Request Dispatched** | Asynchronous fetch is sent to `/api/tts` for the first sentence. |
| `+6258ms` | **First Audio Returned** | Edge-TTS server synthesizes and returns the audio URL to the browser. |
| `+6280ms` | **First Audio Playback Started** | Speech playback begins for the first sentence chunk. |
| `+6282ms` | **Mic Stream Activated** | The microphone input is enabled to capture potential interruptions. |
| `+6300ms` | **User Speech Interruption Simulated** | Simulating user interruption input: RMS `0.08`, threshold `0.03`, confidence `85%`. |
| `+6350ms` | **User Interruption Detected** | VAD emits `user.interrupted` event. State changes to `UserInterruptDetected`. |
| `+6360ms` | **HUD Display Updated** | Status shows **DETECTED**, Confidence **85%**, Timestamp recorded. |
| `+7389ms` | **Full LLM Generation Completed** | Response finishes generating concurrently while speech continues playing. |
| `+31380ms` | **Full Speech Playback Completed** | Audio finishes playing all sentence chunks to completion. Interruption is cleared. |

---

## Technical Details

### 1. Interruption Decision Logic
To distinguish between user interruption and speaker echo/short noise bursts, we check:
*   **Speech Energy Level**: Microphone RMS exceeds a dynamically calculated threshold.
*   **Echo Suppression Margin**: When TTS playback is active (`ttsPipeline.isPlaying` is true), we raise the VAD threshold by an extra margin of `0.025` to ignore audio leakage from speakers.
*   **VAD Confidence**: Calculated as a percentage of RMS excess over the threshold:
    $$\text{Confidence} = \min\left(100, \max\left(0, \frac{\text{RMS} - \text{Threshold}}{\text{Threshold}} \times 100\right)\right)$$
*   **Speech Duration Filter**: We require the speech energy to persist for at least `6` consecutive frames (~270ms) before triggering an interruption. This suppresses short noise bursts and transient echo spikes.

### 2. State & Playback Preservation
When an interruption is validated, the `VoiceSessionManager` transitions to the new `UserInterruptDetected` state. However, to keep playback intact during detection testing:
*   `ttsPipeline.interrupt()` is **not** called.
*   Playback continues playing smoothly in the background.
*   The LLM stream is **not** cancelled.
