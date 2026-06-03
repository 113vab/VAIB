import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import logger, PORT, HOST, DATA_DIR
from app.brain.memory import MemoryManager
from app.brain.agent import VaibAgent
from app.voice.tts import TTSManager
from app.voice.stt import STTManager

# Initialize components
logger.info("Initializing V.A.I.B. core systems...")
memory = MemoryManager()
agent = VaibAgent(memory)
tts = TTSManager()
stt = STTManager()

app = FastAPI(
    title="V.A.I.B. Personal AI Assistant",
    description="Inspired by Marvel's JARVIS, V.A.I.B. is a voice-first AI assistant for Windows.",
    version="1.0.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input data models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None

# Mount static folders
# Ensure directories exist
GUI_DIR = Path(__file__).resolve().parent / "gui"
STATIC_DIR = GUI_DIR / "static"
TEMPLATES_DIR = GUI_DIR / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Mount audio cache for generated speech
app.mount("/audio-cache", StaticFiles(directory=str(DATA_DIR / "audio_cache")), name="audio-cache")

# Endpoints
@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main dashboard page."""
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.exists():
        logger.error("index.html not found!")
        raise HTTPException(status_code=404, detail="Dashboard index.html not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Text-based interaction endpoint."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        response_text = await agent.generate_response(request.message)
        return ChatResponse(response=response_text)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    """Upload recorded audio and transcribe using Whisper."""
    logger.info(f"Received audio file for STT: {file.filename}")
    
    # Save the uploaded file to a temporary location
    suffix = Path(file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
        try:
            shutil.copyfileobj(file.file, temp_audio)
            temp_path = Path(temp_audio.name)
        except Exception as e:
            logger.error(f"Failed to save temp audio: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse audio file")

    try:
        # Transcribe using Whisper
        transcription = await stt.transcribe_audio(temp_path)
        return {"text": transcription}
    except ValueError as ve:
        # Key missing error
        logger.warning(f"Whisper STT Configuration Error: {ve}")
        raise HTTPException(status_code=400, detail="STT_KEY_MISSING")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_path.exists():
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Failed to delete temp file {temp_path}: {e}")

@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """Generate TTS audio for the given text."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        audio_file = await tts.generate_speech(request.text, request.voice)
        if audio_file and audio_file.exists():
            return {
                "audio_url": f"/audio-cache/{audio_file.name}",
                "text": request.text
            }
        else:
            raise HTTPException(status_code=500, detail="TTS generation returned no file")
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

@app.post("/api/memory/clear")
async def clear_memory_endpoint():
    """Clear memory database and chat history."""
    try:
        memory.clear_chat_history()
        memory.clear_long_term_memories()
        return {"status": "success", "message": "Memory cleared."}
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def status_endpoint():
    """Get system and component status."""
    import platform
    return {
        "status": "online",
        "system": platform.system(),
        "release": platform.release(),
        "brain": "Gemini 2.5 Flash" if agent.model else "offline",
        "stt": "local-whisper (tiny)",
        "tts": "edge-tts (Sonia)"
    }

# Also mount static assets under /static for stylesheet, scripts, etc.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
