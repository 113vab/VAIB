import os
import time
from pathlib import Path
from typing import Optional
import edge_tts
from app.config import logger, DATA_DIR

class TTSManager:
    """Manages Text-to-Speech generation using edge-tts."""
    def __init__(self, output_dir: Optional[Path] = None):
        # Default output directory is in gui static folders or data dir
        self.output_dir = output_dir or DATA_DIR / "audio_cache"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # en-GB-SoniaNeural provides a elegant British accent fitting for FRIDAY
        self.default_voice = "en-GB-SoniaNeural"
        self._cleanup_old_audio()

    def _cleanup_old_audio(self):
        """Clean up audio cache on startup to save disk space."""
        try:
            for file in self.output_dir.glob("*.mp3"):
                file.unlink()
            logger.info("Cleared voice cache folder.")
        except Exception as e:
            logger.error(f"Error cleaning up voice cache: {e}")

    async def generate_speech(self, text: str, voice: Optional[str] = None) -> Optional[Path]:
        """
        Generate an MP3 file from text using edge-tts.
        Returns the Path to the generated file or None if it fails.
        """
        if not text:
            return None

        voice_name = voice or self.default_voice
        filename = f"tts_{int(time.time() * 1000)}.mp3"
        output_file = self.output_dir / filename

        try:
            logger.info(f"Generating TTS for: '{text[:40]}...' using voice {voice_name}")
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(str(output_file))
            logger.info(f"Audio file generated at {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Failed to generate TTS: {e}")
            return None
