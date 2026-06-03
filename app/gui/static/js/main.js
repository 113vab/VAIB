// V.A.I.B. Core HUD JavaScript Logic

document.addEventListener("DOMContentLoaded", () => {
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

    // Diagnostics Elements
    const diagBrain = document.getElementById("diag-brain");
    const diagStt = document.getElementById("diag-stt");
    const diagTts = document.getElementById("diag-tts");
    const diagDb = document.getElementById("diag-db");
    const diagOs = document.getElementById("diag-os");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");

    // Recording State Variables
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    // Browser Web Speech recognition fallback
    let webSpeechRecognizer = null;
    let webSpeechActive = false;

    // Initialize HUD Systems
    startClock();
    fetchDiagnostics();
    initWebSpeechRecognition();

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
        if (!ttsAudio.paused) {
            ttsAudio.pause();
            addLog("[SYSTEM] Speech playback interrupted by user.", "system");
            setUIState("standby");
        }
    });

    // ----------------------------------------------------
    // TTS Audio Playback
    // ----------------------------------------------------
    async function playTTS(text) {
        try {
            setUIState("thinking", "SYNTHESIZING VOCALS");
            
            const res = await fetch("/api/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: text })
            });

            if (!res.ok) throw new Error("TTS API error");

            const data = await res.json();
            
            // Play generated file
            ttsAudio.src = data.audio_url;
            
            ttsAudio.onplay = () => {
                setUIState("speaking", "TRANSMITTING SPEECH");
                addLog("[SPEECH] Speaking response...");
            };

            ttsAudio.onended = () => {
                setUIState("standby");
                addLog("[SPEECH] Speech transmission completed.", "system");
            };

            await ttsAudio.play();
        } catch (err) {
            loggerError("Speech synthesis failed", err);
            setUIState("standby");
        }
    }

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
        // Interrupt current audio if running
        if (!ttsAudio.paused) {
            ttsAudio.pause();
        }

        appendChatBubble("user", message);
        setUIState("thinking", "COMPUTING MATRIX");
        addLog(`[INPUT] User input received: "${message}"`);

        try {
            const chatRes = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: message })
            });

            if (!chatRes.ok) throw new Error("Chat response failed");

            const chatData = await chatRes.json();
            const assistantResponse = chatData.response;
            
            appendChatBubble("assistant", assistantResponse);
            addLog(`[BRAIN] Generated response.`);

            // Trigger TTS speech
            await playTTS(assistantResponse);
        } catch (err) {
            loggerError("Brain processing failed", err);
            appendChatBubble("assistant", "I had trouble computing that request, Sir. Please check my connections.");
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
    async function startRecording() {
        if (isRecording) return;
        audioChunks = [];
        
        // Interrupt any playing speech
        if (!ttsAudio.paused) {
            ttsAudio.pause();
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                setUIState("thinking", "TRANSCRIBING WHISPER");
                addLog("[AUDIO] Voice capture complete. Commencing transcription...", "info");
                
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
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
                }
            };

            mediaRecorder.start();
            isRecording = true;
            setUIState("listening", "LISTENING (MIC CAPTURE)");
            btnMic.classList.add("active");
            micStatusLabel.textContent = "RELEASE TO SEND";
            addLog("[AUDIO] Capturing microphone audio...");
        } catch (err) {
            loggerError("Microphone access denied", err);
            addLog("[SYSTEM] Direct mic recording failed. Triggering browser fallback...", "system");
            fallbackWebSpeech();
        }
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        btnMic.classList.remove("active");
        micStatusLabel.textContent = "HOLD TO TALK";
        
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            // Stop mic capture tracks
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
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
    window.addEventListener("mouseup", stopRecording);
    
    // Mobile Touch events
    btnMic.addEventListener("touchstart", (e) => {
        e.preventDefault();
        startRecording();
    });
    window.addEventListener("touchend", stopRecording);

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
                } else {
                    throw new Error("Failed to clear memory database");
                }
            } catch (err) {
                loggerError("Wipe failed", err);
            }
        }
    });

    // Notify user initialization is complete
    addLog("[SYSTEM] V.A.I.B. cognitive matrix ready.", "positive");
    setUIState("standby");
});
