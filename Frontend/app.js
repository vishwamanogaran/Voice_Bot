// =====================================================
// DOM
// =====================================================
const recordBtn  = document.getElementById("recordBtn");
const userText   = document.getElementById("userText");
const aiText     = document.getElementById("aiText");
const loading    = document.getElementById("loading");
const statusText = document.getElementById("status");

function uiSetStatus(label, active) {
    if (typeof window.setStatus === "function") {
        window.setStatus(label, !!active);
        return;
    }
    if (statusText) statusText.innerText = label;
}

function uiSetSpeaker(speaker) {
    if (typeof window.setSpeaker === "function") {
        window.setSpeaker(speaker);
    }
}

// =====================================================
// STATE
// =====================================================
let websocket    = null;
let mediaRecorder = null;
let isRecording  = false;
let currentAudio = null;
let micStream    = null;
let audioChunks  = [];
let isAiSpeaking = false;
let safetyStartTimer = null;


// =====================================================
// VAD STATE
// =====================================================
let audioContext = null;
let analyser     = null;
let vadInterval  = null;

let silenceCount = 0;
let isSpeaking   = false;

const SILENCE_THRESHOLD = 10;
const SILENCE_CHUNKS    = 8;


// =====================================================
// START BUTTON
// =====================================================
recordBtn.addEventListener("click", async () => {
    if (!isRecording) {
        await startInterview();
    } else {
        stopInterview();
    }
});


// =====================================================
// CREATE NEW RECORDER
// =====================================================
function startRecorder() {
    if (!micStream) return;

    // PREVENT DUPLICATE RECORDERS
    if (mediaRecorder && mediaRecorder.state === "recording") {
        return;
    }

    audioChunks = [];

    mediaRecorder = new MediaRecorder(micStream, { mimeType: "audio/webm" });

    // STORE CHUNKS
    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            audioChunks.push(event.data);
            console.log("Chunk stored:", event.data.size);
        }
    };

    mediaRecorder.start(500);
    console.log("Recorder started");
}


// =====================================================
// START LISTENING
// =====================================================
function startListening() {

    // PREVENT MULTIPLE VAD LOOPS
    if (vadInterval) return;

    startRecorder();
    uiSetStatus("Listening...", true);
    uiSetSpeaker(null);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    vadInterval = setInterval(async () => {

        // IGNORE MIC WHILE AI IS SPEAKING
        if (isAiSpeaking) return;

        analyser.getByteFrequencyData(dataArray);

        const volume = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;

        // SILENCE DETECTION
        if (volume < SILENCE_THRESHOLD) {

            silenceCount++;

            if (silenceCount >= SILENCE_CHUNKS && isSpeaking) {
                isSpeaking   = false;
                silenceCount = 0;
                await processSpeechEnd();
            }

        } else {

            silenceCount = 0;

            if (!isSpeaking) {
                isSpeaking           = true;
                uiSetStatus("Listening...", true);
                uiSetSpeaker("candidate");
                console.log("🎙️ Speech started");
            }
        }

    }, 200);
}


// =====================================================
// PROCESS SPEECH END
// =====================================================
async function processSpeechEnd() {

    // FIX 1: Guard is at the very top, outside try, with correct indentation.
    if (isAiSpeaking) {
        console.log("AI speaking → ignore mic");
        return;
    }

    try {

        if (!mediaRecorder || mediaRecorder.state !== "recording") {
            return;
        }

        // STOP THE VAD LOOP WHILE WE FINALISE / SEND THIS UTTERANCE.
        // startListening() will be called again after the AI finishes.
        if (vadInterval) {
            clearInterval(vadInterval);
            vadInterval = null;
        }

        // FORCE THE FINAL CHUNK
        mediaRecorder.requestData();

        // FIX 2: Wait for the onstop event instead of a blind setTimeout.
        // This guarantees every ondataavailable chunk has arrived before
        // we create the blob — the previous setTimeout(300) was a race condition.
        await new Promise((resolve) => {
            mediaRecorder.onstop = resolve;
            mediaRecorder.stop();
        });

        // FIX 4: Null the recorder so the startRecorder() guard works cleanly.
        mediaRecorder = null;

        // CREATE FINAL WEBM BLOB
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        console.log("Final audio blob:", audioBlob.size);

        // IGNORE NEAR-EMPTY AUDIO
        if (audioBlob.size < 1000) {
            console.log("Ignoring tiny audio");
            startListening();
            return;
        }

        // SEND AUDIO
        if (websocket && websocket.readyState === WebSocket.OPEN) {

            const arrayBuffer = await audioBlob.arrayBuffer();
            websocket.send(arrayBuffer);
            websocket.send(JSON.stringify({ type: "SPEECH_END" }));

            console.log("🔇 Speech ended → sent");
            isAiSpeaking         = true;
            uiSetStatus("Processing...", true);
            uiSetSpeaker("ai");

        } else {
            // FIX 3: If the socket is gone, resume listening instead of
            // hanging silently (the old code had no else branch here).
            console.warn("WebSocket not ready — resuming listening");
            startListening();
        }

    } catch (err) {

        console.error("Speech end error:", err);
        startListening();
    }
}


// =====================================================
// START INTERVIEW
// =====================================================
async function startInterview() {

    try {

        loading.style.display = "block";
        uiSetStatus("Connecting...", true);

        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        websocket = new WebSocket(`${protocol}://${window.location.host}/ws`);
        websocket.binaryType = "arraybuffer";

        // WEBSOCKET OPEN
        websocket.onopen = async () => {

            console.log("WebSocket Connected");
            uiSetStatus("Connected", true);
            loading.style.display = "none";

            // GET MIC
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl:  true,
                },
            });

            // AUDIO CONTEXT + ANALYSER
            audioContext = new AudioContext();
            const source = audioContext.createMediaStreamSource(micStream);
            analyser     = audioContext.createAnalyser();
            analyser.fftSize = 512;
            source.connect(analyser);

            // DO NOT START LISTENING YET — WAIT UNTIL AI GREETING FINISHES

            isRecording          = true;
            recordBtn.innerText  = "🛑 Stop Interview";
            recordBtn.classList.add("recording");

            // Wait for the backend greeting to arrive first (and potentially be
            // played via audio). If nothing arrives, start listening anyway so
            // the UI doesn't look stuck.
            if (safetyStartTimer) clearTimeout(safetyStartTimer);
            safetyStartTimer = setTimeout(() => {
                if (isRecording && !isAiSpeaking && !vadInterval) startListening();
            }, 3000);
        };

        // RECEIVE AI RESPONSE
        websocket.onmessage = async (event) => {

            if (safetyStartTimer) {
                clearTimeout(safetyStartTimer);
                safetyStartTimer = null;
            }

            const data = JSON.parse(event.data);
            console.log(data);

            userText.innerText = data.user_text   || "No speech";
            aiText.innerText   = data.ai_response || "No response";
            uiSetStatus("Connected", true);

            // NO AUDIO RESPONSE
            if (!data.audio_file) {
                console.log("No audio response");
                uiSetStatus("Listening...", true);
                isAiSpeaking         = false;
                uiSetSpeaker(null);
                startListening();
                return;
            }

            // STOP OLD AUDIO
            if (currentAudio) {
                currentAudio.pause();
                currentAudio.currentTime = 0;
                currentAudio.src         = "";
                currentAudio.load();
                currentAudio = null;
            }

            // CREATE NEW AUDIO
            currentAudio = new Audio(
                `${window.location.origin}${data.audio_file}`
            );

            // FIX 5: Removed currentAudio.autoplay = true.
            // autoplay + manual play() in oncanplaythrough caused a double-play
            // race condition in some browsers. One approach is enough.
            isAiSpeaking = true;

            // AUDIO READY — PLAY
            currentAudio.oncanplaythrough = async () => {
                try {
                    console.log("Playing audio...");
                    uiSetSpeaker("ai");
                    await currentAudio.play();
                } catch (err) {
                    console.error("Playback error:", err);
                    isAiSpeaking = false;
                    uiSetSpeaker(null);
                    startListening();
                }
            };

            // AUDIO FINISHED — RESUME LISTENING
            currentAudio.onended = () => {
                console.log("Playback finished");
                isAiSpeaking         = false;
                uiSetStatus("Listening...", true);
                uiSetSpeaker(null);
                startListening();
            };

            // AUDIO ERROR — RESUME LISTENING
            currentAudio.onerror = (err) => {
                console.error("Audio failed:", err);
                isAiSpeaking = false;
                uiSetSpeaker(null);
                startListening();
            };
        };

        // SOCKET CLOSED
        websocket.onclose = () => {
            console.log("Disconnected");
            stopInterview();
            uiSetStatus("Disconnected", false);
            uiSetSpeaker(null);
        };

        // SOCKET ERROR
        websocket.onerror = (err) => {
            console.error("WebSocket Error:", err);
            uiSetStatus("Connection Error", false);
            uiSetSpeaker(null);
        };

    } catch (err) {
        console.error(err);
        loading.style.display = "none";
        uiSetStatus("Mic Permission Denied", false);
        uiSetSpeaker(null);
    }
}


// =====================================================
// STOP INTERVIEW
// =====================================================
function stopInterview() {

    if (safetyStartTimer) {
        clearTimeout(safetyStartTimer);
        safetyStartTimer = null;
    }

    // STOP VAD
    if (vadInterval) {
        clearInterval(vadInterval);
        vadInterval = null;
    }

    // CLOSE AUDIO CONTEXT
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }

    // FIX 7a: Null the analyser after the context is closed.
    analyser = null;

    // STOP RECORDER
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    // FIX 7b: Null the recorder so startRecorder() starts fresh next session.
    mediaRecorder = null;

    // STOP MIC
    if (micStream) {
        micStream.getTracks().forEach((track) => track.stop());
        micStream = null;
    }

    // CLOSE WEBSOCKET
    if (websocket && websocket.readyState !== WebSocket.CLOSED) {
        // Remove onclose BEFORE calling close() so the handler does not
        // call stopInterview() a second time (infinite loop guard).
        websocket.onclose = null;
        websocket.close();
    }
    // FIX 6: Null the reference so no stale handler can act on the old socket.
    websocket = null;

    // STOP CURRENT AUDIO
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio.src         = "";
        currentAudio.load();
        currentAudio = null;
    }

    // RESET STATE
    silenceCount = 0;
    isSpeaking   = false;
    isAiSpeaking = false;
    isRecording  = false;
    audioChunks  = [];

    recordBtn.innerText = "🚀 Start Live Interview";
    recordBtn.classList.remove("recording");
    uiSetStatus("Disconnected", false);
    uiSetSpeaker(null);
}
