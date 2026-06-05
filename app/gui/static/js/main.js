// V.A.I.B. Core HUD JavaScript Logic

// ----------------------------------------------------
// Global UI routing helpers for decoupled voice subsystem access
// ----------------------------------------------------
function addLog(text, type = "info") {
    if (window.addLog) window.addLog(text, type);
    else console.log(`[${type}] ${text}`);
}

function setUIState(state, text = "") {
    if (window.setUIState) window.setUIState(state, text);
    else console.log(`[UI STATE] ${state}: ${text}`);
}

function appendChatBubble(role, content) {
    if (window.appendChatBubble) window.appendChatBubble(role, content);
    else console.log(`[CHAT] ${role}: ${content}`);
}

function loggerError(context, err) {
    if (window.loggerError) window.loggerError(context, err);
    else console.error(`[ERROR] ${context}:`, err);
}

function fetchProfile() {
    if (window.fetchProfile) return window.fetchProfile();
    return Promise.resolve();
}

function fetchFacts() {
    if (window.fetchFacts) return window.fetchFacts();
    return Promise.resolve();
}

// ----------------------------------------------------
// Event-Driven Voice Subsystem Architecture
// ----------------------------------------------------

class EventEmitter {
    constructor() {
        this.listeners = {};
    }
    on(event, fn) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(fn);
    }
    off(event, fn) {
        if (!this.listeners[event]) return;
        this.listeners[event] = this.listeners[event].filter(f => f !== fn);
    }
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(fn => {
                try {
                    fn(data);
                } catch (err) {
                    console.error(`Error in event listener for ${event}:`, err);
                }
            });
        }
    }
}

class VADEngine extends EventEmitter {
    constructor() {
        super();
        this.audioContext = null;
        this.analyser = null;
        this.micStream = null;
        this.scriptProcessor = null;
        
        // VAD Tuning Parameters
        this.sensitivity = 0.02; 
        this.noiseFloor = 0.005;
        this.history = [];
        this.historySize = 60; // ~3 seconds window
        
        // State variables
        this.isSpeaking = false;
        this.speechTriggerFrames = 2;   // ~90ms of consecutive speech
        this.silenceTriggerFrames = 25;  // ~1.1s of consecutive silence
        this.consecutiveSpeechFrames = 0;
        this.consecutiveSilenceFrames = 0;
        
        // Recorder
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }
    
    setSensitivity(value) {
        // Map slider value (5-95) to VAD threshold offset (lower is more sensitive)
        this.sensitivity = 0.001 + ((100 - value) / 100) * 0.05;
    }
    
    async start(stream) {
        this.micStream = stream;
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        await this.audioContext.resume();
        
        const source = this.audioContext.createMediaStreamSource(stream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 512;
        source.connect(this.analyser);
        
        this.scriptProcessor = this.audioContext.createScriptProcessor(2048, 1, 1);
        source.connect(this.scriptProcessor);
        this.scriptProcessor.connect(this.audioContext.destination);
        
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Float32Array(bufferLength);
        
        this.scriptProcessor.onaudioprocess = () => {
            if (!this.micStream) return;
            
            this.analyser.getFloatTimeDomainData(dataArray);
            
            // Calculate RMS (Root Mean Square) energy
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i] * dataArray[i];
            }
            const rms = Math.sqrt(sum / bufferLength);
            
            // Slide noise floor estimation
            this.history.push(rms);
            if (this.history.length > this.historySize) {
                this.history.shift();
            }
            
            const sorted = [...this.history].sort((a,b) => a - b);
            this.noiseFloor = sorted[Math.floor(sorted.length * 0.1)] || 0.005;
            
            const threshold = this.noiseFloor + this.sensitivity;
            this.emit("volume", { rms, threshold });
            
            if (rms > threshold) {
                this.consecutiveSilenceFrames = 0;
                this.consecutiveSpeechFrames++;
                
                if (this.consecutiveSpeechFrames >= this.speechTriggerFrames) {
                    if (!this.isSpeaking) {
                        this.isSpeaking = true;
                        this.emit("speech.start");
                        this.startRecording();
                    }
                }
            } else {
                this.consecutiveSpeechFrames = 0;
                this.consecutiveSilenceFrames++;
                
                if (this.consecutiveSilenceFrames >= this.silenceTriggerFrames) {
                    if (this.isSpeaking) {
                        this.isSpeaking = false;
                        this.emit("speech.end");
                        this.stopRecording();
                    }
                }
            }
        };
    }
    
    stop() {
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        if (this.audioContext) {
            this.audioContext.close().catch(() => {});
            this.audioContext = null;
        }
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        this.isSpeaking = false;
        this.consecutiveSpeechFrames = 0;
        this.consecutiveSilenceFrames = 0;
        this.history = [];
        if (this.isRecording) {
            this.stopRecording();
        }
    }
    
    startRecording() {
        if (!this.micStream) return;
        this.audioChunks = [];
        
        let options = {};
        if (typeof MediaRecorder.isTypeSupported === 'function') {
            if (MediaRecorder.isTypeSupported('audio/webm')) {
                options = { mimeType: 'audio/webm' };
            } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
                options = { mimeType: 'audio/ogg' };
            }
        }
        
        try {
            this.mediaRecorder = new MediaRecorder(this.micStream, options);
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            this.mediaRecorder.start();
            this.isRecording = true;
        } catch (e) {
            console.error("VADRecorder error starting:", e);
        }
    }
    
    stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) return;
        
        this.mediaRecorder.onstop = () => {
            const mimeType = this.mediaRecorder.mimeType || 'audio/webm';
            const audioBlob = new Blob(this.audioChunks, { type: mimeType });
            this.emit("audio.ready", audioBlob);
        };
        
        try {
            this.mediaRecorder.stop();
        } catch (e) {
            console.error("VADRecorder error stopping:", e);
        }
        this.isRecording = false;
    }
}

class STTPipeline extends EventEmitter {
    async transcribe(audioBlob) {
        this.emit("start");
        const formData = new FormData();
        formData.append("file", audioBlob, "user_voice.webm");
        
        try {
            const res = await fetch("/api/stt", {
                method: "POST",
                body: formData
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Transcription error");
            }
            
            const data = await res.json();
            const text = data.text || "";
            this.emit("complete", text);
            return text;
        } catch (e) {
            this.emit("error", e);
            throw e;
        }
    }
}

class LLMPipeline extends EventEmitter {
    async process(message) {
        this.emit("start", message);
        appendChatBubble("user", message);
        addLog(`[INPUT] User input received: "${message}"`);
        
        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: message })
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Chat failed");
            }
            
            const data = await res.json();
            const reply = data.response || "";
            appendChatBubble("assistant", reply);
            addLog(`[BRAIN] Response synthesized successfully.`);
            
            // Reload cognitive memory panels dynamically
            if (typeof fetchProfile === 'function') await fetchProfile();
            if (typeof fetchFacts === 'function') await fetchFacts();
            
            this.emit("complete", reply);
            return reply;
        } catch (e) {
            this.emit("error", e);
            appendChatBubble("assistant", "I had trouble computing that request, Sir. Please check my connections.");
            throw e;
        }
    }
}

class TTSPipeline extends EventEmitter {
    constructor(audioElement) {
        super();
        this.audio = audioElement;
        this.setupAudioListeners();
    }
    
    setupAudioListeners() {
        this.audio.onplay = () => {
            this.emit("play.start");
            addLog("[SPEECH] Speaking response...");
        };
        this.audio.onended = () => {
            this.emit("play.end");
            addLog("[SPEECH] Speech transmission completed.", "system");
        };
        this.audio.onerror = (e) => {
            this.emit("error", e);
        };
    }
    
    async speak(text) {
        this.emit("start", text);
        try {
            const res = await fetch("/api/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: text })
            });
            
            if (!res.ok) throw new Error("TTS API error");
            
            const data = await res.json();
            this.audio.src = data.audio_url;
            await this.audio.play();
        } catch (e) {
            this.emit("error", e);
            console.error("TTS failed:", e);
        }
    }
    
    interrupt() {
        if (!this.audio.paused) {
            this.audio.pause();
            this.emit("interrupted");
            addLog("[SYSTEM] Speech playback interrupted by user.", "system");
        }
    }
}

class VoiceSessionManager extends EventEmitter {
    constructor(vadEngine, sttPipeline, llmPipeline, ttsPipeline) {
        super();
        this.vad = vadEngine;
        this.stt = sttPipeline;
        this.llm = llmPipeline;
        this.tts = ttsPipeline;
        
        this.mode = "manual"; 
        this.state = "idle";  
        this.inactivityTimer = null;
        this.inactivityLimit = 30000; // 30 seconds
        
        // Static sound assets
        this.wakeAudio = new Audio("/static/sounds/wake.mp3");
        this.sleepAudio = new Audio("/static/sounds/sleep.mp3");
        
        this.setupEventListeners();
    }
    
    setMode(mode) {
        this.mode = mode;
        this.resetInactivityTimer();
        
        if (mode === "auto-wake") {
            this.state = "idle";
            this.updateHUDState("idle");
            this.startMicStream();
        } else {
            this.state = "idle";
            this.updateHUDState("idle");
            this.stopMicStream();
        }
    }
    
    async startMicStream() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: { 
                    echoCancellation: true, 
                    noiseSuppression: true 
                } 
            });
            await this.vad.start(stream);
            addLog("[SYSTEM] Continuous voice monitoring initialized.", "system");
        } catch (err) {
            console.error("VAD mic start failed:", err);
            addLog("[ERROR] Failed to start continuous voice monitoring.", "error");
            const toggle = document.getElementById("toggle-continuous-voice");
            if (toggle) toggle.checked = false;
            this.setMode("manual");
        }
    }
    
    stopMicStream() {
        this.vad.stop();
        addLog("[SYSTEM] Continuous voice monitoring deactivated.", "system");
    }
    
    setupEventListeners() {
        this.vad.on("speech.start", () => {
            this.resetInactivityTimer();
            if (this.state === "speaking") {
                this.tts.interrupt();
                addLog("[SYSTEM] Vocal interruption detected.", "system");
                this.state = "listening";
                this.updateHUDState("listening");
            } else if (this.state === "idle" || this.state === "listening") {
                this.state = "listening";
                this.updateHUDState("listening");
            }
        });
        
        this.vad.on("audio.ready", async (audioBlob) => {
            if (this.state === "listening") {
                this.state = "processing";
                this.updateHUDState("processing");
                
                try {
                    const text = await this.stt.transcribe(audioBlob);
                    this.emit("stt.complete", text);
                } catch (e) {
                    addLog(`[ERROR] STT failed: ${e.message || e}`, "error");
                    this.returnToListeningOrIdle();
                }
            } else if (this.state === "idle") {
                try {
                    const text = await this.stt.transcribe(audioBlob);
                    if (text.trim()) {
                        const wakeMatch = text.match(/\b(hey\s+vaib|vaib)\b/i);
                        if (wakeMatch) {
                            addLog("[WAKE] Wake word detected!", "positive");
                            
                            try {
                                await this.wakeAudio.play();
                            } catch (e) { console.error("Wake sound failed:", e); }
                            
                            this.state = "listening";
                            this.updateHUDState("listening");
                            
                            const matchIndex = wakeMatch.index;
                            const matchLength = wakeMatch[0].length;
                            const commandText = text.substring(matchIndex + matchLength).trim().replace(/^[,\s]+|[.!?\s]+$/g, "");
                            
                            if (commandText) {
                                addLog(`[WAKE] Command detected: "${commandText}"`);
                                this.processCommand(commandText);
                            } else {
                                this.resetInactivityTimer();
                            }
                        } else {
                            this.returnToListeningOrIdle();
                        }
                    } else {
                        this.returnToListeningOrIdle();
                    }
                } catch (e) {
                    this.returnToListeningOrIdle();
                }
            }
        });
        
        this.tts.on("play.end", () => {
            this.returnToListeningOrIdle();
        });
        
        this.tts.on("play.start", () => {
            this.state = "speaking";
            this.updateHUDState("speaking");
        });
        
        this.on("stt.complete", (text) => {
            if (!text.trim()) {
                this.returnToListeningOrIdle();
                return;
            }
            this.processCommand(text);
        });
    }
    
    async processCommand(text) {
        this.state = "processing";
        this.updateHUDState("processing");
        try {
            const reply = await this.llm.process(text);
            this.state = "speaking";
            this.updateHUDState("speaking");
            await this.tts.speak(reply);
        } catch (e) {
            this.returnToListeningOrIdle();
        }
    }
    
    returnToListeningOrIdle() {
        if (this.mode === "auto-wake") {
            this.state = "listening";
            this.updateHUDState("listening");
            this.resetInactivityTimer();
        } else {
            this.state = "idle";
            this.updateHUDState("idle");
        }
    }
    
    resetInactivityTimer() {
        clearTimeout(this.inactivityTimer);
        if (this.mode === "auto-wake" && this.state !== "processing" && this.state !== "speaking") {
            this.inactivityTimer = setTimeout(async () => {
                this.state = "idle";
                this.updateHUDState("idle");
                addLog("[SYSTEM] Inactivity timeout. Returning to wake-word standby.", "system");
                try {
                    await this.sleepAudio.play();
                } catch (e) { console.error("Sleep sound failed:", e); }
            }, this.inactivityLimit);
        }
    }
    
    updateHUDState(state) {
        const hudStateSpan = document.getElementById("voice-hud-state");
        if (hudStateSpan) {
            hudStateSpan.textContent = state.toUpperCase();
            if (state === "idle") hudStateSpan.style.color = "#00f0ff";
            else if (state === "listening") hudStateSpan.style.color = "#00f0ff";
            else if (state === "processing") hudStateSpan.style.color = "#a000ff";
            else if (state === "speaking") hudStateSpan.style.color = "#00f0ff";
        }
        
        if (typeof setUIState === 'function') {
            if (state === "idle") setUIState("standby", "STANDBY // ACTIVE");
            else if (state === "listening") setUIState("listening", "LISTENING (AUTO-WAKE)");
            else if (state === "processing") setUIState("thinking", "PROCESSING PATHWAYS");
            else if (state === "speaking") setUIState("speaking", "TRANSMITTING SPEECH");
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Expose local functions to window for globally scoped helper routing
    window.addLog = addLog;
    window.setUIState = setUIState;
    window.appendChatBubble = appendChatBubble;
    window.loggerError = loggerError;
    window.fetchProfile = fetchProfile;
    window.fetchFacts = fetchFacts;

    // UI Elements
    const timeDisplay = document.getElementById("time-display");
    const arcCore = document.getElementById("arc-core");
    const soundWaves = document.getElementById("sound-waves");
    const coreActionText = document.getElementById("core-action-text");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");
    const btnMic = document.getElementById("btn-mic");
    const micStatusLabel = document.getElementById("mic-status-label");
    const btnClearMem = document.getElementById("btn-clear-mem");
    const consoleStream = document.getElementById("console-stream");
    const ttsAudio = document.getElementById("tts-audio");

    // Memory Panel Elements
    const profileList = document.getElementById("profile-list");
    const profileKeyInput = document.getElementById("profile-key");
    const profileValInput = document.getElementById("profile-val");
    const btnSaveProfile = document.getElementById("btn-save-profile");
    const factsList = document.getElementById("facts-list");

    // RAG Knowledge Base Elements
    const ragFileInput = document.getElementById("rag-file-input");
    const uploadStatus = document.getElementById("upload-status");
    const docCountBadge = document.getElementById("doc-count-badge");
    const documentsList = document.getElementById("documents-list");

    // Diagnostics Elements
    const diagBrain = document.getElementById("diag-brain");
    const diagStt = document.getElementById("diag-stt");
    const diagTts = document.getElementById("diag-tts");
    const diagDb = document.getElementById("diag-db");
    const diagOs = document.getElementById("diag-os");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");

    // Permissions Elements
    const panelPermissions = document.getElementById("panel-permissions");
    const pendingPermissionsList = document.getElementById("pending-permissions-list");

    // Agent Autonomous Panel Elements
    const agentGoalInput = document.getElementById("agent-goal-input");
    const btnSubmitGoal = document.getElementById("btn-submit-goal");
    const agentGoalsList = document.getElementById("agent-goals-list");

    // Recording State Variables
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    // Browser Web Speech recognition fallback
    let webSpeechRecognizer = null;
    let webSpeechActive = false;

    // Instantiate Decoupled Voice Subsystem Components
    const sttPipeline = new STTPipeline();
    const llmPipeline = new LLMPipeline();
    const ttsPipeline = new TTSPipeline(ttsAudio);
    const vadEngine = new VADEngine();
    const voiceSessionManager = new VoiceSessionManager(vadEngine, sttPipeline, llmPipeline, ttsPipeline);

    // Attach to window for automated end-to-end integration testing and developer diagnostics
    window.sttPipeline = sttPipeline;
    window.llmPipeline = llmPipeline;
    window.ttsPipeline = ttsPipeline;
    window.vadEngine = vadEngine;
    window.voiceSessionManager = voiceSessionManager;

    // Bind Voice HUD Config Panel Inputs
    const toggleContinuousVoice = document.getElementById("toggle-continuous-voice");
    const sliderMicThreshold = document.getElementById("slider-mic-threshold");
    const labelVadThreshold = document.getElementById("label-vad-threshold");

    if (toggleContinuousVoice) {
        toggleContinuousVoice.addEventListener("change", (e) => {
            if (e.target.checked) {
                voiceSessionManager.setMode("auto-wake");
            } else {
                voiceSessionManager.setMode("manual");
            }
        });
    }

    if (sliderMicThreshold) {
        sliderMicThreshold.addEventListener("input", (e) => {
            const val = e.target.value;
            if (labelVadThreshold) {
                labelVadThreshold.textContent = `${val}%`;
            }
            vadEngine.setSensitivity(val);
        });
        // Set initial sensitivity based on default value
        vadEngine.setSensitivity(sliderMicThreshold.value);
    }

    // Initialize HUD Systems
    startClock();
    fetchDiagnostics();
    initWebSpeechRecognition();
    fetchPendingPermissions();
    fetchProfile();
    fetchFacts();
    fetchRAGDocuments();

    btnSaveProfile.addEventListener("click", saveProfileDetail);
    ragFileInput.addEventListener("change", handleRAGUpload);
    
    if (btnSubmitGoal) {
        btnSubmitGoal.addEventListener("click", submitAgentGoal);
    }
    if (agentGoalInput) {
        agentGoalInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                submitAgentGoal();
            }
        });
    }

    // Load initial goals list
    fetchAgentGoals();
    
    // Poll for pending permissions every 3 seconds
    setInterval(fetchPendingPermissions, 3000);
    
    // Poll for active reminders every 3 seconds
    setInterval(fetchReminders, 3000);

    // Poll for agent goals every 2 seconds
    setInterval(fetchAgentGoals, 2000);

    // ----------------------------------------------------
    // Clock HUD Display
    // ----------------------------------------------------
    function startClock() {
        setInterval(() => {
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            timeDisplay.textContent = timeStr;
        }, 1000);
    }

    async function sendLogToServer(level, message) {
        try {
            await fetch("/api/log", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ level: level, message: message })
            });
        } catch (e) {}
    }

    window.onerror = function(message, source, lineno, colno, error) {
        sendLogToServer("error", `Global JS Error: ${message} at ${source}:${lineno}:${colno}`);
        return false;
    };
    window.onunhandledrejection = function(event) {
        sendLogToServer("error", `Global Unhandled Promise Rejection: ${event.reason}`);
    };

    // ----------------------------------------------------
    // System Logger (Console Stream)
    // ----------------------------------------------------
    function addLog(text, type = "info") {
        const line = document.createElement("div");
        line.className = `console-line ${type}`;
        const timestamp = new Date().toLocaleTimeString().split(' ')[0];
        line.textContent = `[${timestamp}] ${text}`;
        consoleStream.appendChild(line);
        consoleStream.scrollTop = consoleStream.scrollHeight;
        
        sendLogToServer(type === "error" ? "error" : type === "system" ? "warning" : "info", text);
    }

    // ----------------------------------------------------
    // Fetch Component Statuses
    // ----------------------------------------------------
    async function fetchDiagnostics() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            
            diagBrain.textContent = data.brain.toUpperCase();
            diagStt.textContent = data.stt.toUpperCase();
            diagTts.textContent = data.tts.toUpperCase();
            diagOs.textContent = `${data.system} ${data.release}`.toUpperCase();
            
            if (data.brain === "offline") {
                statusDot.className = "status-dot danger";
                statusText.textContent = "COGNITIVE MODULE OFFLINE";
                addLog("[WARN] Primary brain API key is missing. Fill GEMINI_API_KEY in .env.", "error");
            } else {
                statusDot.className = "status-dot pulsing";
                statusText.textContent = "SYSTEM SECURE";
                addLog("[SYSTEM] Connection to Gemini API verified.", "positive");
            }
        } catch (err) {
            addLog("[ERROR] Failed to fetch system diagnostics.", "error");
            statusDot.className = "status-dot danger";
            statusText.textContent = "COMMUNICATION BREAKDOWN";
        }
    }

    // ----------------------------------------------------
    // Web Speech API Initialization (Browser STT Fallback)
    // ----------------------------------------------------
    function initWebSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            webSpeechRecognizer = new SpeechRecognition();
            webSpeechRecognizer.continuous = false;
            webSpeechRecognizer.interimResults = false;
            webSpeechRecognizer.lang = 'en-US';

            webSpeechRecognizer.onstart = () => {
                webSpeechActive = true;
                setUIState("listening", "LISTENING (BROWSER RECOGNITION)");
            };

            webSpeechRecognizer.onresult = async (event) => {
                const text = event.results[0][0].transcript;
                addLog(`[BROWSER RECOG] Detected speech: "${text}"`, "info");
                if (text.trim()) {
                    await handleUserMessage(text);
                }
            };

            webSpeechRecognizer.onerror = (e) => {
                addLog(`[BROWSER RECOG] Error: ${e.error}`, "error");
                setUIState("standby");
            };

            webSpeechRecognizer.onend = () => {
                webSpeechActive = false;
                if (!isRecording) {
                    setUIState("standby");
                }
            };
        } else {
            addLog("[SYSTEM] Browser Speech Recognition API not supported.", "system");
        }
    }

    // ----------------------------------------------------
    // Set UI State (Animations / Central Core Status)
    // ----------------------------------------------------
    function setUIState(state, text = "") {
        // Clear previous classes
        arcCore.className = "arc-reactor";
        soundWaves.className = "sound-waves";
        
        switch (state) {
            case "listening":
                arcCore.classList.add("listening");
                soundWaves.classList.add("active");
                coreActionText.textContent = text || "LISTENING FOR INPUT";
                coreActionText.className = "core-status-text cyan-text";
                break;
            case "thinking":
                arcCore.classList.add("thinking");
                coreActionText.textContent = text || "PROCESSING PATHWAYS";
                coreActionText.className = "core-status-text purple-text";
                break;
            case "speaking":
                arcCore.classList.add("speaking");
                soundWaves.classList.add("active");
                coreActionText.textContent = text || "TRANSMITTING RESPONSE";
                coreActionText.className = "core-status-text cyan-text";
                break;
            case "standby":
            default:
                coreActionText.textContent = text || "STANDBY // ACTIVE";
                coreActionText.className = "core-status-text";
                break;
        }
    }

    // Interrupt TTS playback if user clicks the core
    arcCore.addEventListener("click", () => {
        if (typeof ttsPipeline !== 'undefined') {
            ttsPipeline.interrupt();
        } else if (!ttsAudio.paused) {
            ttsAudio.pause();
            addLog("[SYSTEM] Speech playback interrupted by user.", "system");
            setUIState("standby");
        }
    });

    // ----------------------------------------------------
    // TTS Audio Playback
    // ----------------------------------------------------
    async function playTTS(text) {
        await ttsPipeline.speak(text);
    }

    // Helper logger
    function loggerError(context, err) {
        addLog(`[ERROR] ${context}: ${err.message || err}`, "error");
        console.error(context, err);
    }

    // ----------------------------------------------------
    // Message Appending & API Chat Trigger
    // ----------------------------------------------------
    function appendChatBubble(role, content) {
        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${role}`;
        
        const sender = document.createElement("div");
        sender.className = "bubble-sender";
        sender.textContent = role === "user" ? "USER" : "V.A.I.B.";
        
        const body = document.createElement("div");
        body.className = "bubble-content";
        body.textContent = content;
        
        const time = document.createElement("div");
        time.className = "bubble-time";
        const now = new Date();
        time.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        
        bubble.appendChild(sender);
        bubble.appendChild(body);
        bubble.appendChild(time);
        
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function handleUserMessage(message) {
        ttsPipeline.interrupt();
        setUIState("thinking", "COMPUTING MATRIX");
        try {
            const reply = await llmPipeline.process(message);
            setUIState("speaking", "TRANSMITTING SPEECH");
            await ttsPipeline.speak(reply);
        } catch (err) {
            setUIState("standby");
        }
    }

    // Chat submit handler
    chatForm.addEventListener("submit", async () => {
        const msg = chatInput.value.trim();
        if (!msg) return;
        chatInput.value = "";
        await handleUserMessage(msg);
    });

    // ----------------------------------------------------
    // Mic Voice Recording (MediaRecorder -> Whisper STT)
    // ----------------------------------------------------
    let wantsToRecord = false;
    let recordingStartTime = 0;
    let isToggled = false;

    async function startRecording() {
        if (isRecording) {
            if (isToggled) {
                stopRecording();
                isToggled = false;
            }
            return;
        }
        
        // Pause continuous voice monitor if active during manual push-to-talk override
        if (typeof voiceSessionManager !== 'undefined' && voiceSessionManager.mode === "auto-wake") {
            voiceSessionManager.stopMicStream();
        }

        wantsToRecord = true;
        isToggled = false;
        recordingStartTime = Date.now();
        audioChunks = [];
        
        // Interrupt any playing speech
        if (typeof ttsPipeline !== 'undefined') {
            ttsPipeline.interrupt();
        } else if (!ttsAudio.paused) {
            ttsAudio.pause();
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Abort if the user released the button before permission was granted
            if (!wantsToRecord) {
                stream.getTracks().forEach(track => track.stop());
                if (typeof voiceSessionManager !== 'undefined' && voiceSessionManager.mode === "auto-wake") {
                    voiceSessionManager.startMicStream();
                }
                return;
            }

            let options = {};
            if (typeof MediaRecorder.isTypeSupported === 'function') {
                if (MediaRecorder.isTypeSupported('audio/webm')) {
                    options = { mimeType: 'audio/webm' };
                } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
                    options = { mimeType: 'audio/ogg' };
                }
            }
            
            mediaRecorder = new MediaRecorder(stream, options);
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                // Stop mic capture tracks after recording stops to prevent encoding truncation
                stream.getTracks().forEach(track => track.stop());

                setUIState("thinking", "TRANSCRIBING WHISPER");
                addLog("[AUDIO] Voice capture complete. Commencing transcription...", "info");
                
                const audioBlob = new Blob(audioChunks, { type: options.mimeType || 'audio/webm' });
                if (audioChunks.length === 0 || audioBlob.size === 0) {
                    addLog("[AUDIO] No audio data captured.", "warning");
                    setUIState("standby");
                    if (typeof voiceSessionManager !== 'undefined' && voiceSessionManager.mode === "auto-wake") {
                        voiceSessionManager.returnToListeningOrIdle();
                    }
                    return;
                }

                const formData = new FormData();
                formData.append("file", audioBlob, "user_voice.webm");

                try {
                    const sttRes = await fetch("/api/stt", {
                        method: "POST",
                        body: formData
                    });

                    if (sttRes.ok) {
                        const sttData = await sttRes.json();
                        const text = sttData.text;
                        addLog(`[WHISPER] Transcribed: "${text}"`, "positive");
                        if (text.trim()) {
                            await handleUserMessage(text);
                        } else {
                            setUIState("standby", "NO AUDIO DETECTED");
                            if (typeof voiceSessionManager !== 'undefined' && voiceSessionManager.mode === "auto-wake") {
                                voiceSessionManager.returnToListeningOrIdle();
                            }
                        }
                    } else {
                        const errData = await sttRes.json();
                        if (errData.detail === "STT_KEY_MISSING") {
                            addLog("[SYSTEM] Whisper API key missing. Transitioning to browser fallback recognition.", "system");
                            fallbackWebSpeech();
                        } else {
                            throw new Error(errData.detail || "Transcription error");
                        }
                    }
                } catch (err) {
                    loggerError("Transcription process failed", err);
                    setUIState("standby");
                    if (typeof voiceSessionManager !== 'undefined' && voiceSessionManager.mode === "auto-wake") {
                        voiceSessionManager.returnToListeningOrIdle();
                    }
                }
            };

            mediaRecorder.start();
            isRecording = true;
            setUIState("listening", "LISTENING (MIC CAPTURE)");
            btnMic.classList.add("active");
            if (isToggled) {
                micStatusLabel.textContent = "CLICK TO SEND";
            } else {
                micStatusLabel.textContent = "RELEASE TO SEND";
            }
            addLog("[AUDIO] Capturing microphone audio...");
        } catch (err) {
            loggerError("Microphone access denied", err);
            addLog("[SYSTEM] Direct mic recording failed. Triggering browser fallback...", "system");
            fallbackWebSpeech();
        }
    }

    function stopRecording() {
        wantsToRecord = false;
        if (!isRecording) return;
        isRecording = false;
        btnMic.classList.remove("active");
        micStatusLabel.textContent = "HOLD TO TALK";
        
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }
    }

    function handleRelease() {
        if (!wantsToRecord) {
            return;
        }

        if (!isRecording) {
            const pressDuration = Date.now() - recordingStartTime;
            if (pressDuration < 300) {
                isToggled = true;
                micStatusLabel.textContent = "CLICK TO SEND";
            } else {
                wantsToRecord = false;
            }
            return;
        }

        const holdDuration = Date.now() - recordingStartTime;
        if (holdDuration < 300) {
            isToggled = true;
            micStatusLabel.textContent = "CLICK TO SEND";
        } else {
            stopRecording();
        }
    }

    // Direct browser fallback call
    function fallbackWebSpeech() {
        if (webSpeechRecognizer && !webSpeechActive) {
            try {
                webSpeechRecognizer.start();
            } catch (e) {
                console.error("Failed to start speech recognition fallback:", e);
            }
        } else if (!webSpeechRecognizer) {
            addLog("[ERROR] Speech fallback unavailable on this browser.", "error");
            setUIState("standby");
        }
    }

    // Add mouse & touch handlers for Hold-to-Talk button
    btnMic.addEventListener("mousedown", startRecording);
    window.addEventListener("mouseup", handleRelease);
    
    // Mobile Touch events
    btnMic.addEventListener("touchstart", (e) => {
        e.preventDefault();
        startRecording();
    });
    window.addEventListener("touchend", handleRelease);

    // ----------------------------------------------------
    // Memory Operations (Purge Database)
    // ----------------------------------------------------
    btnClearMem.addEventListener("click", async () => {
        if (confirm("Are you certain you wish to purge the memory cores, Sir? This is irreversible.")) {
            addLog("[MEMORY] Initiating core wipe...", "error");
            try {
                const res = await fetch("/api/memory/clear", { method: "POST" });
                if (res.ok) {
                    chatMessages.innerHTML = "";
                    appendChatBubble("assistant", "My memory cores have been completely wiped, Sir. I am ready to start fresh.");
                    addLog("[MEMORY] Memory cores purged successfully.", "positive");
                    await fetchProfile();
                    await fetchFacts();
                } else {
                    throw new Error("Failed to clear memory database");
                }
            } catch (err) {
                loggerError("Wipe failed", err);
            }
        }
    });

    // ----------------------------------------------------
    // Pending Permission Confirmations
    // ----------------------------------------------------
    async function fetchPendingPermissions() {
        try {
            const res = await fetch("/api/permissions/pending");
            if (!res.ok) return;
            const pending = await res.json();
            
            if (pending.length === 0) {
                panelPermissions.style.display = "none";
                return;
            }
            
            panelPermissions.style.display = "flex";
            pendingPermissionsList.innerHTML = "";
            
            pending.forEach(action => {
                const card = document.createElement("div");
                card.style.background = "rgba(255, 255, 255, 0.03)";
                card.style.border = "1px solid rgba(0, 240, 255, 0.2)";
                card.style.padding = "10px";
                card.style.borderRadius = "4px";
                card.style.display = "flex";
                card.style.flexDirection = "column";
                card.style.gap = "8px";
                card.style.marginBottom = "8px";
                
                // Render key-value pairs beautifully
                const detailsFormatted = Object.entries(action.details)
                    .map(([key, val]) => `<span style="color: #00f0ff;">${key.replace("_", " ")}:</span> ${val}`)
                    .join("<br>");

                card.innerHTML = `
                    <div style="font-family: 'Share Tech Mono', monospace; font-size: 0.85rem; color: #00f0ff; text-transform: uppercase; font-weight: bold; border-bottom: 1px solid rgba(0, 240, 255, 0.1); padding-bottom: 4px;">
                        ${action.type.replace("_", " ")}
                    </div>
                    <div style="font-family: 'Share Tech Mono', monospace; font-size: 0.75rem; color: #c0c0c0; word-break: break-all; max-height: 80px; overflow-y: auto;">
                        ${detailsFormatted}
                    </div>
                    <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 4px;">
                        <button class="approve-btn" data-id="${action.id}" style="background: rgba(0, 240, 255, 0.1); border: 1px solid #00f0ff; color: #00f0ff; padding: 4px 10px; font-family: 'Share Tech Mono', monospace; font-size: 0.75rem; cursor: pointer; border-radius: 2px;">APPROVE</button>
                        <button class="deny-btn" data-id="${action.id}" style="background: rgba(255, 0, 85, 0.1); border: 1px solid #ff0055; color: #ff0055; padding: 4px 10px; font-family: 'Share Tech Mono', monospace; font-size: 0.75rem; cursor: pointer; border-radius: 2px;">DENY</button>
                    </div>
                `;
                
                // Add button handlers
                const approveBtn = card.querySelector(".approve-btn");
                const denyBtn = card.querySelector(".deny-btn");
                
                approveBtn.addEventListener("click", async () => {
                    const id = approveBtn.getAttribute("data-id");
                    addLog(`[SYSTEM] Approving action ${action.type}...`);
                    try {
                        const postRes = await fetch(`/api/permissions/approve/${id}`, { method: "POST" });
                        const data = await postRes.json();
                        if (postRes.ok) {
                            addLog(`[SYSTEM] Action ${action.type} approved and executed.`, "positive");
                            appendChatBubble("assistant", `[APPROVED] Action executed: ${data.result}`);
                            await playTTS(data.result);
                        } else {
                            throw new Error(data.detail || "Approval execution failed");
                        }
                    } catch (err) {
                        loggerError("Approval failed", err);
                    }
                    fetchPendingPermissions();
                });
                
                denyBtn.addEventListener("click", async () => {
                    const id = denyBtn.getAttribute("data-id");
                    addLog(`[SYSTEM] Denying action ${action.type}...`, "error");
                    try {
                        const postRes = await fetch(`/api/permissions/deny/${id}`, { method: "POST" });
                        if (postRes.ok) {
                            addLog(`[SYSTEM] Action ${action.type} denied by user.`, "system");
                            appendChatBubble("assistant", `[DENIED] Action was rejected, Sir.`);
                            await playTTS("Action rejected.");
                        } else {
                            const data = await postRes.json();
                            throw new Error(data.detail || "Deny request failed");
                        }
                    } catch (err) {
                        loggerError("Denial failed", err);
                    }
                    fetchPendingPermissions();
                });
                
                pendingPermissionsList.appendChild(card);
            });
        } catch (err) {
            console.error("Failed to fetch pending permissions:", err);
        }
    }

    // ----------------------------------------------------
    // Reminders & Active Timers Polling
    // ----------------------------------------------------
    async function fetchReminders() {
        try {
            const res = await fetch("/api/notifications/poll");
            if (!res.ok) return;
            const data = await res.json();
            
            if (data.notifications && data.notifications.length > 0) {
                for (const notif of data.notifications) {
                    const text = `Sir, this is a reminder: ${notif.text}`;
                    addLog(`[TIMER ALERT] Reminder triggered: "${notif.text}"`, "system");
                    appendChatBubble("assistant", `[REMINDER] ${notif.text}`);
                    await playTTS(text);
                }
            }
        } catch (err) {
            console.error("Failed to poll reminders:", err);
        }
    }

    // ----------------------------------------------------
    // Cognitive Memory Panel Operations
    // ----------------------------------------------------
    async function fetchProfile() {
        try {
            const res = await fetch("/api/profile");
            if (!res.ok) throw new Error("Failed to fetch profile");
            const profile = await res.json();
            profileList.innerHTML = "";
            
            const keys = Object.keys(profile);
            if (keys.length === 0) {
                profileList.innerHTML = `<div style="color: var(--text-muted); font-style: italic;">No profile data saved, Sir.</div>`;
                return;
            }
            
            keys.forEach(key => {
                const item = document.createElement("div");
                item.style.display = "flex";
                item.style.justify = "space-between";
                item.style.alignItems = "center";
                item.style.background = "rgba(255, 255, 255, 0.02)";
                item.style.padding = "2px 6px";
                item.style.borderRadius = "2px";
                item.style.marginBottom = "4px";
                item.innerHTML = `
                    <span><strong style="color: var(--neon-cyan); font-family: 'Share Tech Mono', monospace;">${key}</strong>: ${profile[key]}</span>
                    <span class="delete-profile-item" style="color: var(--neon-purple); cursor: pointer; font-size: 16px; font-weight: bold; padding: 0 4px;" title="Delete Key">&times;</span>
                `;
                const delBtn = item.querySelector(".delete-profile-item");
                delBtn.addEventListener("click", () => deleteProfileKey(key));
                profileList.appendChild(item);
            });
        } catch (err) {
            console.error("Failed to load profile details:", err);
        }
    }

    async function saveProfileDetail() {
        const key = profileKeyInput.value.trim();
        const val = profileValInput.value.trim();
        if (!key || !val) {
            alert("Sir, please enter both a Key and Value.");
            return;
        }
        try {
            const res = await fetch("/api/profile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ key, value: val })
            });
            if (res.ok) {
                addLog(`[MEMORY] Saved profile key '${key}' = '${val}'`, "positive");
                profileKeyInput.value = "";
                profileValInput.value = "";
                await fetchProfile();
            } else {
                throw new Error("Save profile failed");
            }
        } catch (err) {
            console.error("Save profile error:", err);
            addLog("[ERROR] Failed to save profile detail.", "error");
        }
    }

    async function deleteProfileKey(key) {
        if (!confirm(`Remove profile preference '${key}', Sir?`)) return;
        try {
            const res = await fetch(`/api/profile/${key}`, { method: "DELETE" });
            if (res.ok) {
                addLog(`[MEMORY] Deleted profile key '${key}'`, "system");
                await fetchProfile();
            } else {
                throw new Error("Delete profile key failed");
            }
        } catch (err) {
            console.error("Delete profile key error:", err);
        }
    }

    async function fetchFacts() {
        try {
            const res = await fetch("/api/memory/facts");
            if (!res.ok) throw new Error("Failed to fetch facts");
            const facts = await res.json();
            factsList.innerHTML = "";
            
            if (facts.length === 0) {
                factsList.innerHTML = `<div style="color: var(--text-muted); font-style: italic;">No semantic facts stored, Sir.</div>`;
                return;
            }
            
            facts.forEach(item => {
                const el = document.createElement("div");
                el.style.display = "flex";
                el.style.justify = "space-between";
                el.style.alignItems = "flex-start";
                el.style.gap = "8px";
                el.style.borderBottom = "1px solid rgba(255, 255, 255, 0.04)";
                el.style.padding = "4px 0";
                el.style.marginBottom = "4px";
                el.innerHTML = `
                    <span style="flex-grow: 1; word-break: break-all; font-family: 'Share Tech Mono', monospace; font-size: 11px;">${item.fact}</span>
                    <button class="delete-fact-btn" style="background: none; border: none; color: var(--text-negative); cursor: pointer; font-size: 16px; font-weight: bold; padding: 0 4px; line-height: 1;" title="Forget Fact">&times;</button>
                `;
                const delBtn = el.querySelector(".delete-fact-btn");
                delBtn.addEventListener("click", () => deleteFact(item.id));
                factsList.appendChild(el);
            });
        } catch (err) {
            console.error("Failed to load memory facts:", err);
        }
    }

    async function deleteFact(factId) {
        if (!confirm("Are you sure you want me to forget this fact, Sir?")) return;
        try {
            const res = await fetch(`/api/memory/facts/${factId}`, { method: "DELETE" });
            if (res.ok) {
                addLog(`[MEMORY] Forgot semantic fact ${factId}`, "system");
                await fetchFacts();
            } else {
                throw new Error("Forget fact failed");
            }
        } catch (err) {
            console.error("Forget fact error:", err);
        }
    }

    // ----------------------------------------------------
    // RAG Knowledge Base Operations
    // ----------------------------------------------------
    async function fetchRAGDocuments() {
        try {
            const res = await fetch("/api/rag/documents");
            if (!res.ok) throw new Error("Failed to fetch indexed documents");
            const docs = await res.json();
            documentsList.innerHTML = "";
            docCountBadge.textContent = docs.length;
            
            if (docs.length === 0) {
                documentsList.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 11px;">No documents indexed, Sir.</div>`;
                return;
            }
            
            docs.forEach(doc => {
                const el = document.createElement("div");
                el.style.display = "flex";
                el.style.justify = "space-between";
                el.style.alignItems = "center";
                el.style.background = "rgba(255, 255, 255, 0.02)";
                el.style.padding = "4px 6px";
                el.style.borderRadius = "2px";
                el.style.marginBottom = "4px";
                
                // Formulate a short date string
                const dateStr = new Date(doc.timestamp * 1000).toLocaleDateString(undefined, {
                     month: "short",
                     day: "numeric"
                });
                
                el.innerHTML = `
                    <div style="display: flex; flex-direction: column; max-width: 80%;">
                         <span style="strong; color: var(--neon-cyan); font-family: 'Share Tech Mono', monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${doc.source}">${doc.source}</span>
                         <span style="font-size: 9px; color: var(--text-muted);">${doc.chunk_count} chunks // ${dateStr}</span>
                    </div>
                    <span class="delete-doc-btn" style="color: var(--neon-purple); cursor: pointer; font-size: 16px; font-weight: bold; padding: 0 4px;" title="Forget Document">&times;</span>
                `;
                const delBtn = el.querySelector(".delete-doc-btn");
                delBtn.addEventListener("click", () => deleteRAGDocument(doc.source));
                documentsList.appendChild(el);
            });
        } catch (err) {
            console.error("Failed to load documents list:", err);
        }
    }

    async function handleRAGUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        uploadStatus.style.color = "var(--neon-cyan)";
        uploadStatus.textContent = `Processing and chunking '${file.name}'...`;
        addLog(`[RAG] Initiating upload for: ${file.name}`);
        
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            const res = await fetch("/api/rag/upload", {
                method: "POST",
                body: formData
            });
            
            if (res.ok) {
                const result = await res.json();
                uploadStatus.style.color = "var(--text-positive)";
                uploadStatus.textContent = `Successfully indexed ${result.data.chunk_count} chunks, Sir.`;
                addLog(`[RAG] Successfully indexed ${file.name} (${result.data.chunk_count} chunks).`, "positive");
                ragFileInput.value = "";
                await fetchRAGDocuments();
                // Refresh facts list as well
                await fetchFacts();
            } else {
                const data = await res.json();
                throw new Error(data.detail || "Upload failed");
            }
        } catch (err) {
            console.error("RAG upload failed:", err);
            uploadStatus.style.color = "var(--text-negative)";
            uploadStatus.textContent = `Index failed: ${err.message}`;
            addLog(`[ERROR] Document ingestion failed: ${err.message}`, "error");
        }
    }

    async function deleteRAGDocument(sourceName) {
        if (!confirm(`Forget document '${sourceName}' and delete all its chunks, Sir?`)) return;
        try {
            const res = await fetch(`/api/rag/documents/${encodeURIComponent(sourceName)}`, {
                method: "DELETE"
            });
            if (res.ok) {
                addLog(`[RAG] Removed document '${sourceName}' from library.`, "system");
                await fetchRAGDocuments();
                // Refresh facts list as well
                await fetchFacts();
            } else {
                throw new Error("Delete document failed");
            }
        } catch (err) {
            console.error("Delete RAG document failed:", err);
            addLog(`[ERROR] Failed to delete document: ${err.message}`, "error");
        }
    }

    // ----------------------------------------------------
    // Agent Goal Execution Operations
    // ----------------------------------------------------
    async function fetchAgentGoals() {
        if (!agentGoalsList) return;
        try {
            const res = await fetch("/api/agent/goals");
            if (!res.ok) throw new Error("Failed to fetch agent goals");
            const goals = await res.json();
            agentGoalsList.innerHTML = "";
            
            if (goals.length === 0) {
                agentGoalsList.innerHTML = `<div style="color: var(--text-muted); font-style: italic; font-size: 11px;">No active goals, Sir.</div>`;
                return;
            }
            
            for (const goal of goals) {
                const el = document.createElement("div");
                el.style.border = "1px solid rgba(255, 255, 255, 0.05)";
                el.style.background = "rgba(0, 0, 0, 0.2)";
                el.style.padding = "6px 8px";
                el.style.borderRadius = "3px";
                el.style.marginBottom = "6px";
                
                let statusColor = "var(--text-muted)";
                if (goal.status === "running") statusColor = "var(--neon-cyan)";
                else if (goal.status === "paused") statusColor = "yellow";
                else if (goal.status === "completed") statusColor = "var(--text-positive)";
                else if (goal.status === "failed") statusColor = "var(--text-negative)";
                else if (goal.status === "cancelled") statusColor = "var(--neon-purple)";
                
                const tasksRes = await fetch(`/api/agent/goals/${goal.id}`);
                let tasksHtml = "";
                if (tasksRes.ok) {
                    const detail = await tasksRes.json();
                    if (detail.tasks && detail.tasks.length > 0) {
                        tasksHtml = `<div style="margin-top: 5px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 4px; display: flex; flex-direction: column; gap: 2px;">`;
                        detail.tasks.forEach(task => {
                            let taskStatusColor = "var(--text-muted)";
                            if (task.status === "running") taskStatusColor = "var(--neon-cyan)";
                            else if (task.status === "completed") taskStatusColor = "var(--text-positive)";
                            else if (task.status === "failed") taskStatusColor = "var(--text-negative)";
                            else if (task.status === "paused_on_permission") taskStatusColor = "yellow";
                            
                            tasksHtml += `
                                <div style="font-size: 10px; display: flex; justify-content: space-between; font-family: 'Share Tech Mono', monospace;">
                                    <span style="color: ${taskStatusColor};">Step ${task.step_number}: ${task.description}</span>
                                    <span style="color: ${taskStatusColor}; text-transform: uppercase;">[${task.status}]</span>
                                </div>
                            `;
                        });
                        tasksHtml += `</div>`;
                    }
                }

                let actionsHtml = "";
                if (goal.status === "running" || goal.status === "paused") {
                    actionsHtml = `<button class="goal-action-btn cancel-btn" data-id="${goal.id}" style="background: rgba(255, 0, 80, 0.2); border: 1px solid var(--neon-purple); color: var(--neon-purple); font-size: 9px; padding: 2px 5px; cursor: pointer; border-radius: 2px; font-family: 'Orbitron', sans-serif;">CANCEL</button>`;
                } else if (goal.status === "failed" || goal.status === "cancelled" || goal.status === "completed") {
                    actionsHtml = `
                        <button class="goal-action-btn resume-btn" data-id="${goal.id}" style="background: rgba(0, 240, 255, 0.1); border: 1px solid var(--neon-cyan); color: var(--neon-cyan); font-size: 9px; padding: 2px 5px; cursor: pointer; border-radius: 2px; font-family: 'Orbitron', sans-serif;">RE-RUN</button>
                        <button class="goal-action-btn delete-goal-btn" data-id="${goal.id}" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.2); color: var(--text-color); font-size: 9px; padding: 2px 5px; cursor: pointer; border-radius: 2px; font-family: 'Orbitron', sans-serif; margin-left: 4px;">REMOVE</button>
                    `;
                }

                el.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 5px;">
                        <div style="display: flex; flex-direction: column; max-width: 70%;">
                            <span style="font-weight: bold; color: var(--text-color); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${goal.goal}">${goal.goal}</span>
                            <span style="font-size: 10px; color: ${statusColor}; text-transform: uppercase; font-family: 'Orbitron', sans-serif;">Status: ${goal.status} ${goal.result ? ' - ' + goal.result : ''}</span>
                        </div>
                        <div style="display: flex; gap: 3px;">
                            ${actionsHtml}
                        </div>
                    </div>
                    ${tasksHtml}
                `;
                
                el.querySelectorAll(".cancel-btn").forEach(btn => {
                    btn.addEventListener("click", () => cancelAgentGoal(goal.id));
                });
                el.querySelectorAll(".resume-btn").forEach(btn => {
                    btn.addEventListener("click", () => resumeAgentGoal(goal.id));
                });
                el.querySelectorAll(".delete-goal-btn").forEach(btn => {
                    btn.addEventListener("click", () => deleteAgentGoal(goal.id));
                });
                
                agentGoalsList.appendChild(el);
            }
        } catch (err) {
            console.error("fetchAgentGoals error:", err);
        }
    }

    async function submitAgentGoal() {
        const goalText = agentGoalInput.value.trim();
        if (!goalText) return;
        
        addLog(`[AGENT] Dispatching autonomous goal: "${goalText}"`, "system");
        agentGoalInput.value = "";
        
        try {
            const res = await fetch("/api/agent/goals", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ goal: goalText })
            });
            if (res.ok) {
                const data = await res.json();
                addLog(`[AGENT] Goal accepted, execution ID: ${data.id}`, "positive");
                await fetchAgentGoals();
            } else {
                throw new Error("Goal submission failed");
            }
        } catch (err) {
            console.error("Goal submit error:", err);
            addLog(`[ERROR] Goal submission failed: ${err.message}`, "error");
        }
    }

    async function cancelAgentGoal(goalId) {
        try {
            const res = await fetch(`/api/agent/goals/${goalId}/cancel`, { method: "POST" });
            if (res.ok) {
                addLog(`[AGENT] Cancellation requested for Goal ID: ${goalId}`, "system");
                await fetchAgentGoals();
            }
        } catch (err) {
            console.error("Cancel goal error:", err);
        }
    }

    async function resumeAgentGoal(goalId) {
        try {
            const res = await fetch(`/api/agent/goals/${goalId}/resume`, { method: "POST" });
            if (res.ok) {
                addLog(`[AGENT] Goal ID ${goalId} restarted.`, "system");
                await fetchAgentGoals();
            }
        } catch (err) {
            console.error("Resume goal error:", err);
        }
    }

    async function deleteAgentGoal(goalId) {
        try {
            const res = await fetch(`/api/agent/goals/${goalId}`, { method: "DELETE" });
            if (res.ok) {
                addLog(`[AGENT] Goal ID ${goalId} removed from log history.`, "system");
                await fetchAgentGoals();
            }
        } catch (err) {
            console.error("Delete goal error:", err);
        }
    }

    // Notify user initialization is complete
    addLog("[SYSTEM] V.A.I.B. cognitive matrix ready.", "positive");
    setUIState("standby");
});
