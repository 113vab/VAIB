import asyncio
from pathlib import Path
from app.config import logger

class STTManager:
    """Manages Speech-to-Text transcription locally using faster-whisper."""
    def __init__(self):
        self._model = None
        logger.info("Local STT Manager initialized (lazy loading enabled).")

    @property
    def model(self):
        """Lazy load the Whisper model to keep startup instant and unit tests lightweight."""
        if self._model is None:
            logger.info("Loading local faster-whisper model ('tiny') into memory...")
            from faster_whisper import WhisperModel
            # Load the tiny model on CPU using int8 quantization for speed and efficiency
            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("faster-whisper model loaded successfully.")
        return self._model

    async def transcribe_audio(self, audio_file_path: Path) -> str:
        """
        Transcribes audio from a file path locally using faster-whisper.
        Runs CPU-bound model inference in a thread executor to avoid blocking the event loop.
        """
        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found at {audio_file_path}")

        try:
            logger.info(f"Transcribing audio file locally: {audio_file_path.name}")
            
            # Define transcription call to run in executor
            def run_inference():
                segments, info = self.model.transcribe(str(audio_file_path), beam_size=5)
                return "".join([segment.text for segment in segments]).strip()

            # Run CPU-bound task in the default ThreadPoolExecutor
            loop = asyncio.get_event_loop()
            transcription = await loop.run_in_executor(None, run_inference)
            
            logger.info(f"Local Transcription result: '{transcription}'")
            return transcription
        except Exception as e:
            logger.error(f"Failed to transcribe audio locally: {e}")
            raise e
