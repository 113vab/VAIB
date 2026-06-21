# Realtime Playback Timing Trace

This report documents the detailed timing trace measured during the concurrent execution of streaming LLM generation and sentence-buffered speech playback after our playback optimizations.

## Timing Trace (Main Diagnostic Query)

The metrics below trace the lifecycle of a multi-sentence prompt response (measured in milliseconds from the exact moment the user message is submitted to the backend):

| Step | Milestone | Relative Time (ms) | Event Detail / Text Content |
| --- | --- | --- | --- |
| 1 | **User Query Submitted** | `+0ms` | *"Write a short reply with three sentences. Each sentence should end with a period."* |
| 2 | **First Token Received** | `+1320ms` | LLM begins streaming text chunks back to the browser. |
| 3 | **First Sentence Detected** | `+1780ms` | Sentence boundary regex matches the first complete sentence: *"I am currently operating in simulation mode, Sir."* |
| 4 | **First TTS Request Dispatched** | `+1862ms` | Asynchronous fetch is sent to `/api/tts` for the first sentence. |
| 5 | **First Audio Returned** | `+3334ms` | Edge-TTS server synthesizes and returns the audio URL to the browser. |
| 6 | **First Audio Playback Started** | `+3795ms` | Speech playback begins for the first sentence chunk. |
| 7 | **Full LLM Generation Completed** | `+5086ms` | Streaming connection ends. Full response text is rendered on the UI. |
| 8 | **Full Speech Playback Completed** | `+31293ms` | Speech player finishes speaking the 5th and final sentence chunk. |

---

## Technical Analysis & Refactoring Details

### 1. Verification of Concurrency
Speech playback begins at **`3795ms`** (3.8 seconds), whereas the LLM stream does not finish generating until **`5086ms`** (5.1 seconds). This represents a **`1.29 second` concurrency window** where speech playback actively starts while the LLM is still streaming subsequent sentences in the background.

### 2. Autoplay Policies & UI Interaction Gap (Root Cause identified)
In standard web browsers, media playback (such as calling `audio.play()` on a dynamically loaded source) is blocked by the **Browser Autoplay Policy** unless it is initiated inside a direct, synchronous user gesture stack.
*   **The Issue**: Although submitting a query counts as a user gesture, the transient user activation state expires before the asynchronous fetch to `/api/tts` resolves. This triggers a `NotAllowedError` in standard playback flow, causing the queue worker to discard the sentence chunks. Playback is deferred until the user performs a second interaction on the page (like clicking anywhere out of curiosity), which unblocks the audio.
*   **The Solution**: We implemented:
    1.  A global **silent audio unlocker** that plays a silent sound upon the very first user interaction (`click`, `keydown`, `touchstart`), permanently unlocking the browser's audio context.
    2.  A **Queue Hold on Block**: If `audio.play()` throws a `NotAllowedError`, we pause playback and hold the sentence queue, registering a one-time gesture handler to automatically resume once the user interacts, preventing sentence loss.

### 3. Fetching Optimization (Blob Object URLs)
*   **Original latency gap**: Previously, setting `this.audio.src` to a remote URL forced the browser to make a second GET request to `/audio-cache/...` which added an average of **`961ms`** of buffering latency.
*   **Optimized flow**: We pre-fetched the audio stream as a blob immediately upon receiving the `/api/tts` response, generating a memory-resident Object URL (`URL.createObjectURL(blob)`). This reduces the buffering delay to only **`461ms`**, saving **`500ms`** of latency and enabling instant audio playback.
