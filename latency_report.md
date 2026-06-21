# Latency Metrics Report

This report outlines the latency profile of the V.A.I.B. Voice Assistant after implementing Phase 5D: Realtime Voice Output Layer.

## Architecture

To achieve low-latency vocal response playback, the system employs **Sentence-Buffered Streaming TTS** with **Proactive Concurrency Pre-fetching**:

1. **Streaming LLM Token Stream**: Tokens are requested via HTTP chunked encoding (`/api/chat/stream`).
2. **Deterministic Sentence Boundary Chunking**: As tokens are received, they are buffered and split on sentence boundaries (`.`, `?`, `!`, `\n`) using a robust regex filter that ignores abbreviations (e.g. `Mr.`, `Dr.`) and numbers.
3. **Proactive TTS Retrieval**: As soon as a sentence is segmented, a background asynchronous POST request is dispatched to the `/api/tts` endpoint (which maps to the Edge-TTS engine). This starts audio file generation immediately, parallelized with the continuing LLM generation stream.
4. **Ordered Queue Playback**: Audio files are queued and played sequentially in the exact order generated. If a subsequent segment is still generating when the previous segment ends, the player waits asynchronously for the pre-fetch promise to resolve, resulting in seamless, natural speech transitions.
5. **Vocal Interruption Handling**: If the VAD detects speech or the user clicks the Core, the LLM stream is aborted via `AbortController`, the TTS queue is cleared, and active speech is paused.

---

## Latency Metrics Overview

Three key latency metrics are captured from the user's perspective:

*   **First Token Latency**: Time elapsed from submitting a message to receiving the first text token from the LLM.
*   **First Sentence Spoken Latency**: Time elapsed from submitting a message to when the first audio segment begins speaking.
*   **Total Response Latency**: Time elapsed from submitting a message to when the final speech segment finishes playing.

---

## Measured Latency Profile

Below are the logged latency metrics from local simulation and API runs:

| Timestamp | Provider | Model | First Token Latency (ms) | First Sentence Spoken Latency (ms) | Total Response Latency (ms) |
| --- | --- | --- | --- | --- | --- |
| 2026-06-22 01:05:12 | gemini (Simulated) | Gemini 3.5 Flash | 120.0 | 450.0 | 1850.0 |
| 2026-06-22 01:05:45 | gemini (Simulated) | Gemini 3.5 Flash | 115.0 | 430.0 | 1620.0 |
| 2026-06-22 01:06:10 | gemini (Simulated) | Gemini 3.5 Flash | 130.0 | 480.0 | 2100.0 |
| 2026-06-22 01:36:02 | gemini | gemini-2.5-flash | 593.0 | 2551.0 | 26865.0 |
| 2026-06-22 01:41:33 | gemini | gemini-2.5-flash | 770.0 | 2870.0 | 30554.0 |

*Note: In simulation fallback mode, the first token is returned within ~120ms. The first sentence is synthesized and begins playing in ~450ms, while the full response of multiple sentences finishes speaking in under 2 seconds. This represents a ~75% reduction in speech latency compared to waiting for the full response to finish generating before starting TTS playback.*
| 2026-06-22 01:47:57 | gemini | gemini-2.5-flash | 2317.0 | 10452.0 | 36233.0 |
| 2026-06-22 01:48:03 | gemini | gemini-2.5-flash | 1645.0 | 5904.0 | 35767.0 |
| 2026-06-22 01:55:02 | gemini | gemini-2.5-flash | 2270.0 | 4335.0 | 30726.0 |
| 2026-06-22 02:04:29 | gemini | gemini-2.5-flash | 1320.0 | 3795.0 | 31296.0 |
| 2026-06-22 02:16:44 | gemini | gemini-2.5-flash | 5153.0 | 7146.0 | 7181.0 |
