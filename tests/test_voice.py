import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from app.voice.tts import TTSManager
from app.voice.stt import STTManager

@pytest.fixture
def temp_cache():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

def test_tts_init(temp_cache):
    """Test TTS Manager initializes and cleans up folders."""
    tts = TTSManager(output_dir=temp_cache)
    assert tts.output_dir == temp_cache
    assert temp_cache.exists()

@pytest.mark.asyncio
async def test_tts_generation_mock(temp_cache):
    """Test generating speech using mock Communicate to prevent network calls."""
    tts = TTSManager(output_dir=temp_cache)
    
    with patch("edge_tts.Communicate") as mock_comm:
        mock_instance = MagicMock()
        mock_instance.save = AsyncMock()
        mock_comm.return_value = mock_instance
        
        # Call generate
        file_path = await tts.generate_speech("Greetings Sir.")
        
        assert file_path is not None
        assert file_path.parent == temp_cache
        assert mock_comm.called
        assert mock_instance.save.called

def test_stt_init():
    """Test STT Manager initializes with lazy loading."""
    stt = STTManager()
    assert stt._model is None

@pytest.mark.asyncio
async def test_stt_transcription_mock():
    """Test local STT transcription calls the whisper model correctly with mock segments."""
    stt = STTManager()
    
    # Mock the WhisperModel instance and its return segments
    mock_model = MagicMock()
    # Mock segments returned as an iterable list of objects containing a 'text' property
    segment_1 = MagicMock()
    segment_1.text = "Hello "
    segment_2 = MagicMock()
    segment_2.text = "world."
    
    mock_model.transcribe.return_value = ([segment_1, segment_2], None)
    
    # Set the lazy loaded model to our mock
    stt._model = mock_model
    
    # Transcribe a dummy path
    with patch("pathlib.Path.exists", return_value=True):
        text = await stt.transcribe_audio(Path("dummy_audio.wav"))
        assert text == "Hello world."
        assert mock_model.transcribe.called

