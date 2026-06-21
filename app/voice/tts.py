import os
import time
from pathlib import Path
from typing import Optional
import re
import edge_tts
from app.config import logger, DATA_DIR

class TTSManager:
    """Manages Text-to-Speech generation using edge-tts."""
    def __init__(self, output_dir: Optional[Path] = None):
        # Default output directory is in gui static folders or data dir
        self.output_dir = output_dir or DATA_DIR / "audio_cache"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Default primary is en-US-JennyNeural, fallback is en-US-AriaNeural
        self.default_voice = "en-US-JennyNeural"
        self.fallback_voice = "en-US-AriaNeural"
        self._cleanup_old_audio()

    def _cleanup_old_audio(self):
        """Clean up audio cache on startup to save disk space."""
        try:
            for file in self.output_dir.glob("*.mp3"):
                file.unlink()
            logger.info("Cleared voice cache folder.")
        except Exception as e:
            logger.error(f"Error cleaning up voice cache: {e}")

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocesses text to make speech cadence and delivery feel more natural.
        Ensures clear punctuation spacing and appends pauses (commas) after greetings
        and acknowledgements to allow for organic, smooth pauses.
        """
        if not text:
            return ""
            
        # Normalize double/multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Insert subtle commas after common introductory phrases/greetings for natural pausing
        greetings = [
            "Acknowledged", "Yes", "No", "Hello", "Hi", "Certainly", 
            "Indeed", "Of course", "Understood", "Right away", "Welcome back"
        ]
        for g in greetings:
            # Matches case-insensitive greeting followed directly by 'Sir' (e.g. "Acknowledged Sir" -> "Acknowledged, Sir")
            text = re.sub(rf'\b({g})\b\s+Sir\b', r'\1, Sir', text, flags=re.IGNORECASE)
        
        # Clean up any bad punctuation spacing like "word , word" -> "word, word"
        text = re.sub(r'\s+([.,?!;:])', r'\1', text)
        
        return text

    async def generate_speech(self, text: str, voice: Optional[str] = None) -> Optional[Path]:
        """
        Generate an MP3 file from text using edge-tts.
        Returns the Path to the generated file or None if it fails.
        """
        if not text:
            return None

        # Voice Profiles mapping
        VOICE_PROFILES = {
            "Friday": "en-US-JennyNeural",
            "Aria": "en-US-AriaNeural",
            "Neerja": "en-IN-NeerjaNeural"
        }
        
        requested_voice = voice or self.default_voice
        voice_id = VOICE_PROFILES.get(requested_voice, requested_voice)
        
        # Conversational text preprocessing for natural pausing/delivery
        processed_text = self._preprocess_text(text)
        if not processed_text:
            processed_text = text

        filename = f"tts_{int(time.time() * 1000)}.mp3"
        output_file = self.output_dir / filename

        # Configure rate (-10%), pitch (+5Hz), and volume (default)
        rate = "-10%"
        pitch = "+5Hz"

        try:
            logger.info(f"Generating TTS for: '{processed_text[:40]}...' using voice {voice_id} (Rate={rate}, Pitch={pitch})")
            communicate = edge_tts.Communicate(
                text=processed_text,
                voice=voice_id,
                rate=rate,
                pitch=pitch
            )
            await communicate.save(str(output_file))
            logger.info(f"Audio file generated at {output_file}")
            return output_file
        except Exception as e:
            logger.warning(f"Failed to generate TTS with voice {voice_id}: {e}. Retrying with fallback {self.fallback_voice}...")
            try:
                # Use fallback voice with same rate/pitch config
                communicate = edge_tts.Communicate(
                    text=processed_text,
                    voice=self.fallback_voice,
                    rate=rate,
                    pitch=pitch
                )
                await communicate.save(str(output_file))
                logger.info(f"Audio file generated using fallback at {output_file}")
                return output_file
            except Exception as fe:
                logger.error(f"Failed fallback TTS generation: {fe}")
                return None
