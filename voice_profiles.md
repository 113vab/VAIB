# V.A.I.B. Voice Profiles

This document details the configuration, parameters, and design guidelines for the natural and smooth voice experience of V.A.I.B. (Voice-Activated Interactive Brain).

## Voice Profile Mapping

Three premium neural voices are configured as selectable profiles to match the user's preference without code modifications:

| Profile Name | Voice Identifier | Description / Cadence | Locale | Type |
| --- | --- | --- | --- | --- |
| **Friday (Default)** | `en-US-JennyNeural` | Clear, smooth, and professional feminine delivery. | US English | Primary |
| **Aria** | `en-US-AriaNeural` | Conversational, bright, and natural feminine delivery. | US English | Fallback |
| **Neerja** | `en-IN-NeerjaNeural` | Clear and clear-cadence Indian accent feminine voice. | IN English | Specialty |

---

## Speech Parameter Optimizations

To remove the mechanical, fast, and robotic default cadence, standard speech parameters have been optimized globally:

1. **Speech Rate (`-10%`)**: Slowed down by 10% to give speech a more deliberate, thoughtful, and executive presence.
2. **Speech Pitch (`+5Hz`)**: Tuned up by 5Hz to raise the register slightly, giving the voice a warmer, brighter, and clearer sound.
3. **Speech Volume (Default)**: Preserved at default levels to prevent clipping and maintain compatibility with standard audio output interfaces.

---

## Conversational Delivery Enhancements

To maximize natural delivery, the TTS layer executes automatic preprocessing on all sentences prior to synthesis:

*   **Punctuation-Driven Pauses**: Commas are dynamically injected after common prefixes (e.g. greetings like *"Acknowledged"*, *"Certainly"*, *"Indeed"*, *"Yes"*, and *"Of course"*) when referencing the user (*"Sir"*). This prompts Microsoft's neural network to pause naturally (typically `200ms` - `350ms`), replicating normal breathing patterns.
*   **Whitespace Normalization**: Multiple spaces, tabs, and duplicate spacing are collapsed to ensure predictable speech rhythms.
*   **Punctuation Spacing Correction**: Eliminates structural anomalies (such as spacing before punctuation) that could confuse neural prosody models.
