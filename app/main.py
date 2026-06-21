import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import logger, PORT, HOST, DATA_DIR, LLM_MODEL
from app.brain.memory import MemoryManager
from app.brain.agent import VaibAgent
from app.voice.tts import TTSManager
from app.voice.stt import STTManager
from app.tools import PermissionsManager
from app.brain.rag import DocumentIngestionPipeline
from app.brain.planner import AgentExecutorManager

# Initialize components
logger.info("Initializing V.A.I.B. core systems...")
memory = MemoryManager()
agent = VaibAgent(memory)
tts = TTSManager()
stt = STTManager()
rag_pipeline = DocumentIngestionPipeline(memory)
agent_executor = AgentExecutorManager(agent, memory)

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

class ClientLogRequest(BaseModel):
    level: str
    message: str

class ProfileRequest(BaseModel):
    key: str
    value: str

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
(DATA_DIR / "audio_cache").mkdir(parents=True, exist_ok=True)
app.mount("/audio-cache", StaticFiles(directory=str(DATA_DIR / "audio_cache")), name="audio-cache")

# Mount screenshots directory
(DATA_DIR / "screenshots").mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(DATA_DIR / "screenshots")), name="screenshots")

# Mount webcam directory
(DATA_DIR / "webcam").mkdir(parents=True, exist_ok=True)
app.mount("/webcam", StaticFiles(directory=str(DATA_DIR / "webcam")), name="webcam")

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

@app.post("/api/log")
async def client_log(request: ClientLogRequest):
    if request.level.lower() == "error":
        logger.error(f"[CLIENT ERROR] {request.message}")
    elif request.level.lower() == "warning":
        logger.warning(f"[CLIENT WARN] {request.message}")
    else:
        logger.info(f"[CLIENT INFO] {request.message}")
    return {"status": "ok"}

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

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """Streaming text-based interaction endpoint."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        async def event_generator():
            try:
                async for token in agent.generate_response_stream(request.message):
                    yield token
            except Exception as stream_err:
                logger.error(f"Error in stream generation: {stream_err}")
                yield f"\n[STREAM ERROR: {str(stream_err)}]"

        return StreamingResponse(
            event_generator(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Error starting chat stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    """Upload recorded audio and transcribe using Whisper."""
    import time
    logger.info(f"[STT] Received audio file for STT: {file.filename}")
    
    try:
        # Read the file contents asynchronously to ensure they are fully in memory
        contents = await file.read()
        byte_size = len(contents)
        logger.info(f"[STT] Uploaded file size: {byte_size} bytes")
    except Exception as e:
        logger.error(f"[STT] Failed to read uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {str(e)}")

    if byte_size == 0:
        logger.error("[STT] Uploaded audio file is empty (0 bytes). Rejecting request to prevent EOF error.")
        raise HTTPException(
            status_code=400, 
            detail="Uploaded audio file is empty. Please verify microphone/capture settings."
        )

    # Save to a temporary file ensuring proper lifecycle
    suffix = Path(file.filename).suffix or ".webm"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            temp_audio.write(contents)
            temp_audio.flush()
            temp_path = Path(temp_audio.name)
            
        disk_size = temp_path.stat().st_size
        logger.info(f"[STT] Created temporary file: '{temp_path.name}' on disk ({disk_size} bytes)")
    except Exception as e:
        logger.error(f"[STT] Failed to write temporary audio file to disk: {e}")
        if temp_path and temp_path.exists():
            try: os.unlink(temp_path)
            except Exception: pass
        raise HTTPException(status_code=500, detail=f"Failed to write audio file to disk: {str(e)}")

    start_time = time.time()
    try:
        # Transcribe using Whisper
        logger.info(f"[STT] Commencing local Whisper transcription for '{temp_path.name}'...")
        transcription = await stt.transcribe_audio(temp_path)
        elapsed = time.time() - start_time
        logger.info(f"[STT] Transcription complete in {elapsed:.2f}s. Result: '{transcription}'")
        return {"text": transcription}
    except ValueError as ve:
        logger.warning(f"[STT] Whisper STT Configuration Error: {ve}")
        raise HTTPException(status_code=400, detail="STT_KEY_MISSING")
    except Exception as e:
        logger.error(f"[STT] Transcription engine failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temporary file safely
        if temp_path and temp_path.exists():
            try:
                os.unlink(temp_path)
                logger.info(f"[STT] Cleaned up temporary file: '{temp_path.name}'")
            except Exception as e:
                logger.error(f"[STT] Failed to delete temporary file {temp_path}: {e}")

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

@app.get("/api/profile")
async def get_profile_endpoint():
    """Retrieve all profile details."""
    try:
        return memory.get_all_profile()
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile")
async def set_profile_endpoint(request: ProfileRequest):
    """Set or update a profile value."""
    try:
        memory.set_profile_value(request.key, request.value)
        return {"status": "success", "message": f"Updated profile key '{request.key}'."}
    except Exception as e:
        logger.error(f"Error setting profile value: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profile/{key}")
async def delete_profile_endpoint(key: str):
    """Delete a profile key."""
    try:
        success = memory.delete_profile_value(key)
        if success:
            return {"status": "success", "message": f"Profile key '{key}' deleted."}
        raise HTTPException(status_code=400, detail="Failed to delete key.")
    except Exception as e:
        logger.error(f"Error deleting profile key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memory/facts")
async def get_facts_endpoint():
    """Retrieve all long-term facts stored in ChromaDB."""
    try:
        return memory.get_all_facts()
    except Exception as e:
        logger.error(f"Error fetching long-term memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memory/facts/{fact_id}")
async def delete_fact_endpoint(fact_id: str):
    """Delete a specific long-term fact from ChromaDB."""
    try:
        success = memory.delete_fact_by_id(fact_id)
        if success:
            return {"status": "success", "message": f"Fact '{fact_id}' deleted."}
        raise HTTPException(status_code=400, detail="Failed to delete fact.")
    except Exception as e:
        logger.error(f"Error deleting fact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rag/upload")
async def rag_upload_endpoint(file: UploadFile = File(...)):
    """Upload a TXT, PDF, or DOCX document to ingest into the local RAG knowledge base."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".txt", ".pdf", ".docx"]:
         raise HTTPException(status_code=400, detail=f"Unsupported file format: {suffix}. Only .txt, .pdf, and .docx are supported.")
         
    # Save the file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
         try:
              shutil.copyfileobj(file.file, temp_file)
              temp_path = Path(temp_file.name)
         except Exception as e:
              logger.error(f"Failed to save temp file for ingestion: {e}")
              raise HTTPException(status_code=500, detail="Failed to save uploaded file.")
              
    try:
         result = await rag_pipeline.ingest_document(temp_path, custom_source_name=file.filename)
         return {"status": "success", "data": result}
    except Exception as e:
         logger.error(f"Ingestion failed: {e}")
         raise HTTPException(status_code=500, detail=str(e))
    finally:
         if temp_path.exists():
              try:
                   os.unlink(temp_path)
              except Exception as e:
                   logger.error(f"Failed to clean up temp file {temp_path}: {e}")

@app.get("/api/rag/documents")
async def get_rag_documents_endpoint():
    """Retrieve list of all indexed documents in the local knowledge base."""
    try:
        return memory.get_indexed_documents()
    except Exception as e:
        logger.error(f"Error fetching indexed documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/rag/documents/{source_name}")
async def delete_rag_document_endpoint(source_name: str):
    """Delete a document from the RAG knowledge base by its name."""
    try:
        success = memory.delete_document_by_source(source_name)
        if success:
            return {"status": "success", "message": f"Document '{source_name}' successfully deleted."}
        raise HTTPException(status_code=400, detail=f"Failed to delete document '{source_name}'.")
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Permission endpoints

@app.get("/api/permissions/pending")
async def get_pending_permissions():
    """Get list of actions currently awaiting user approval."""
    pm = PermissionsManager()
    return pm.get_pending_actions()

@app.post("/api/permissions/approve/{action_id}")
async def approve_permission(action_id: str):
    """Approve a pending action and execute it."""
    pm = PermissionsManager()
    status = pm.get_action_status(action_id)
    if status.get("status") == "not_found":
         raise HTTPException(status_code=404, detail="Action not found")
         
    res = pm.approve_action(action_id)
    if res.get("status") == "success":
         action_type = status.get("type", "action")
         result_val = res.get("result", "")
         # Add record of approval outcome in SQLite log
         memory.add_chat_message("assistant", f"[APPROVED] Action '{action_type}' executed: {result_val}")
         return res
    else:
         raise HTTPException(status_code=400, detail=res.get("error", "Execution failed"))

@app.post("/api/permissions/deny/{action_id}")
async def deny_permission(action_id: str):
    """Deny and discard a pending action."""
    pm = PermissionsManager()
    status = pm.get_action_status(action_id)
    if status.get("status") == "not_found":
         raise HTTPException(status_code=404, detail="Action not found")
         
    res = pm.deny_action(action_id)
    if res.get("status") == "success":
         action_type = status.get("type", "action")
         if action_type == "run_shell_command":
              details = status.get("details", {})
              cmd = details.get("command", "")
              from app.tools.computer import write_audit_log
              write_audit_log("DENIED", cmd)
         # Add record of denial in SQLite log
         memory.add_chat_message("assistant", f"[DENIED] Action '{action_type}' rejected.")
         return res
    else:
         raise HTTPException(status_code=400, detail=res.get("message", "Denial failed"))

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

@app.get("/api/notifications/poll")
async def poll_notifications():
    """Poll for reminders that need to be triggered."""
    import sqlite3
    import time
    DB_PATH = DATA_DIR / "history.db"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Query reminders that are overdue and not yet triggered
        current_time = time.time()
        cursor.execute(
            "SELECT id, text FROM reminders WHERE is_triggered = 0 AND trigger_time <= ?",
            (current_time,)
        )
        rows = cursor.fetchall()
        
        triggered = []
        if rows:
            for row in rows:
                rem_id, text = row
                triggered.append({"id": rem_id, "text": text})
                # Update status to triggered
                cursor.execute(
                    "UPDATE reminders SET is_triggered = 1 WHERE id = ?",
                    (rem_id,)
                )
            conn.commit()
            
        conn.close()
        return {"notifications": triggered}
    except Exception as e:
        logger.error(f"Error polling notifications: {e}")
        return {"notifications": []}

class GoalRequest(BaseModel):
    goal: str

@app.post("/api/agent/goals")
async def create_agent_goal(req: GoalRequest):
    goal_id = memory.add_agent_goal(req.goal)
    if goal_id == -1:
        raise HTTPException(status_code=500, detail="Failed to create agent goal.")
    
    started = agent_executor.start_goal_execution(goal_id)
    if not started:
        raise HTTPException(status_code=500, detail="Failed to initiate goal background execution.")
        
    return {"id": goal_id, "status": "pending"}

@app.get("/api/agent/goals")
async def get_agent_goals():
    return memory.get_agent_goals()

@app.get("/api/agent/goals/{goal_id}")
async def get_agent_goal_detail(goal_id: int):
    goal = memory.get_agent_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    tasks = memory.get_agent_tasks(goal_id)
    return {"goal": goal, "tasks": tasks}

@app.post("/api/agent/goals/{goal_id}/cancel")
async def cancel_agent_goal(goal_id: int):
    goal = memory.get_agent_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    agent_executor.cancel_goal_execution(goal_id)
    return {"status": "success", "message": "Goal cancellation requested."}

@app.post("/api/agent/goals/{goal_id}/resume")
async def resume_agent_goal(goal_id: int):
    goal = memory.get_agent_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    
    memory.update_agent_goal_status(goal_id, "pending", "")
    started = agent_executor.start_goal_execution(goal_id)
    if not started:
        raise HTTPException(status_code=500, detail="Failed to resume goal execution.")
    return {"status": "success", "message": "Goal execution resumed."}

@app.delete("/api/agent/goals/{goal_id}")
async def delete_agent_goal(goal_id: int):
    success = memory.delete_agent_goal(goal_id)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete agent goal.")
    return {"status": "success", "message": "Goal deleted successfully."}

class LatencyReportRequest(BaseModel):
    first_token_latency_ms: Optional[float] = None
    first_sentence_latency_ms: Optional[float] = None
    total_response_latency_ms: Optional[float] = None

@app.post("/api/latency/report")
async def report_latency_endpoint(request: LatencyReportRequest):
    """Logs latency metrics and writes them to latency_report.md."""
    try:
        report_path = Path(__file__).resolve().parent.parent / "latency_report.md"
        
        active_provider = "unknown"
        if hasattr(agent, "router"):
            active_provider = getattr(agent.router, "preferred_provider_name", "unknown")
        active_model = LLM_MODEL or "unknown"
        
        if not report_path.exists():
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Latency Metrics Report\n\n")
                f.write("| Timestamp | Provider | Model | First Token Latency (ms) | First Sentence Spoken Latency (ms) | Total Response Latency (ms) |\n")
                f.write("| --- | --- | --- | --- | --- | --- |\n")
                
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        token_ms = f"{request.first_token_latency_ms:.1f}" if request.first_token_latency_ms is not None else "N/A"
        sentence_ms = f"{request.first_sentence_latency_ms:.1f}" if request.first_sentence_latency_ms is not None else "N/A"
        total_ms = f"{request.total_response_latency_ms:.1f}" if request.total_response_latency_ms is not None else "N/A"
        
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(f"| {timestamp} | {active_provider} | {active_model} | {token_ms} | {sentence_ms} | {total_ms} |\n")
            
        logger.info(f"[LATENCY REPORT] Logged metrics: Token={token_ms}ms, Sentence={sentence_ms}ms, Total={total_ms}ms")
        return {"status": "success", "message": "Metrics logged."}
    except Exception as e:
        logger.error(f"Error logging latency metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Also mount static assets under /static for stylesheet, scripts, etc.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
