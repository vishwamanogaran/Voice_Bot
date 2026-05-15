from fastapi import (
    FastAPI,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect
)
import numpy as np
import io
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time
import asyncio
import shutil
import os
import uuid
import json
# =========================================================
# IMPORTS
# =========================================================
from session_manager import (
    create_session,
    remove_session
)

from workers import audio_worker

from whisper_engine import (
    transcribe_audio
)

from llm_engine import (
    ask_llama
)

from tts_engine import (
    text_to_speech
)
from fastapi.responses import FileResponse
# =========================================================
# FASTAPI
# =========================================================
app = FastAPI()


# =========================================================
# CORS
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# UPLOAD FOLDER
# =========================================================
UPLOAD_FOLDER = "../uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# STATIC AUDIO ROUTE
# =========================================================
app.mount(
    "/audio",
    StaticFiles(directory=UPLOAD_FOLDER),
    name="audio"
)


# =========================================================
# HOME ROUTE
# =========================================================
# @app.get("/")
# def home():
#
#     return {
#         "message": "AI Interview Bot Running"
#     }
# =========================================================
# FRONTEND STATIC FILES
# =========================================================

FRONTEND_FOLDER = "../Frontend"

ASSETS_FOLDER = os.path.join(
    FRONTEND_FOLDER,
    "assets"
)

# Serve assets folder
app.mount(
    "/assets",
    StaticFiles(directory=ASSETS_FOLDER),
    name="assets"
)

# =========================================================
# HOME ROUTE -> LOAD UI
# =========================================================
@app.get("/")
async def home():

    return FileResponse(
        os.path.join(
            FRONTEND_FOLDER,
            "index.html"
        )
    )

# =========================================================
# APP.JS ROUTE
# =========================================================
@app.get("/app.js")
async def app_js():

    return FileResponse(
        os.path.join(
            FRONTEND_FOLDER,
            "app.js"
        )
    )

# =========================================================
# REST API ROUTE
# =========================================================
@app.post("/interview")
async def interview(audio: UploadFile = File(...)):

    try:

        # =================================================
        # SAVE AUDIO
        # =================================================
        filename = f"{uuid.uuid4()}.webm"

        audio_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        with open(audio_path, "wb") as buffer:

            shutil.copyfileobj(
                audio.file,
                buffer
            )

        # =================================================
        # STT
        # =================================================
        user_text = await asyncio.to_thread(
            transcribe_audio,
            audio_path
        )

        if not user_text or len(user_text.strip()) < 2:
            print("Empty transcription ignored")

            return {
                "error": "Empty speech detected"
            }

        print("USER:", user_text)

        # =================================================
        # AI PROMPT
        # =================================================
        ai_prompt = f"""
        You are Vishwa — a smart, emotionally aware, human-like HR interviewer from a modern tech company.

        Your personality:
        - Friendly, confident, and conversational
        - Sound like a REAL human interviewer, not an AI bot
        - Speak naturally with small human reactions sometimes
        - Be warm, engaging, and slightly casual
        - Encourage the candidate subtly
        - Maintain professional HR behavior

        Interview behavior rules:
        - Ask ONLY ONE interview question at a time
        - Keep responses concise (2–4 lines max)
        - Never give long lectures
        - Never sound scripted or robotic
        - Avoid repetitive phrases
        - React naturally to the candidate's previous answer
        - Sometimes acknowledge answers naturally like:
          "Nice."
          "Got it."
          "That makes sense."
          "Interesting."
        - Transition smoothly into the next question

        Communication style:
        - Use natural spoken English
        - Sound like a live HR round from a real company
        - Be emotionally intelligent and adaptive
        - If candidate seems nervous, be supportive
        - If candidate gives strong answers, appreciate briefly
        - Never mention being an AI model
        - Never use bullet points while speaking
        - Avoid overly formal corporate language

        Current interview context:
        You are conducting an interview for a software/IT-related role.

        Candidate's latest response:
        \"\"\"{user_text}\"\"\"

        Now continue the interview naturally with:
        1. A short human-like acknowledgement
        2. ONE relevant follow-up interview question
        """

        # =================================================
        # LLM RESPONSE
        # =================================================
        ai_response = await ask_llama(
            ai_prompt
        )

        print("AI:", ai_response)

        # =================================================
        # TTS
        # =================================================
        audio_file = await asyncio.to_thread(
            text_to_speech,
            ai_response
        )

        if not audio_file:

            return {
                "error": "TTS failed"
            }

        # =================================================
        # AUDIO URL
        # =================================================
        audio_url = (
            "/audio/"
            +
            os.path.basename(audio_file)
        )

        return {

            "user_text": user_text,

            "ai_response": ai_response,

            "audio_file": audio_url
        }

    except Exception as e:

        print("Interview Route Error:", e)

        return {
            "error": str(e)
        }

def is_silent(audio_bytes: bytes, threshold: float = 500.0) -> bool:
    """
    Checks energy from raw bytes directly — no decoding needed.
    Works on WebM chunks, PCM, or any raw audio stream.
    """
    try:
        # Interpret raw bytes as 16-bit PCM samples
        samples = np.frombuffer(audio_bytes, dtype=np.int16)

        if len(samples) == 0:
            return True

        # RMS energy of the samples
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
        print(f"RMS energy: {rms:.1f}")
        return rms < threshold

    except Exception as e:
        print(f"Energy check failed: {e}")
        return False

# =========================================================
# REALTIME WEBSOCKET
# =========================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    session_id = str(uuid.uuid4())
    session = create_session(session_id)

    print(f"Client Connected: {session_id}")

    # =================================================
    # INITIAL HR GREETING
    # =================================================
    initial_message = (
        "Hi, Bala here from Perpetuuiti Technosoft. "
        "Welcome! It's nice to meet you. "
        "I hope you're doing well today. "
        "Before we begin, could you please "
        "introduce yourself?"
    )

    if session.logger:
        session.logger.add_turn("assistant", initial_message)

    audio_path = await asyncio.to_thread(
        text_to_speech,
        initial_message
    )

    await session.response_queue.put({

        "user_text": "",

        "ai_response": initial_message,

        "audio_file": audio_path
    })

    # AUDIO PROCESSOR WORKER
    worker_task = asyncio.create_task(
        audio_worker(session)
    )

    # ==========================================
    # RECEIVE AUDIO FROM FRONTEND
    # ==========================================
    async def receive_audio():

        while True:

            message = await websocket.receive()

            # CLIENT DISCONNECT
            if message["type"] == "websocket.disconnect":
                print(f"Disconnect received: {session_id}")
                break

            # ==================================
            # TEXT MESSAGE
            # ==================================
            if message.get("text"):

                data = json.loads(message["text"])

                # SPEECH END
                if data.get("type") == "SPEECH_END":

                    audio_data = None

                    async with session.buffer_lock:

                        if len(session.audio_buffer) > 0:
                            audio_data = bytes(session.audio_buffer)

                            session.audio_buffer.clear()

                    if audio_data:

                        print(
                            f"SPEECH_END -> processing {len(audio_data)} bytes"
                        )

                        await session.audio_queue.put(audio_data)

                    else:

                        print("Buffer empty")

            # ==================================
            # AUDIO BYTES
            # ==================================
            elif message.get("bytes"):

                async with session.buffer_lock:

                    session.audio_buffer.extend(message["bytes"])

                    print(
                        f"Audio chunk received, "
                        f"buffer={len(session.audio_buffer)}"
                    )

                print(
                    f"Audio chunk received, "
                    f"buffer={len(session.audio_buffer)}"
                )

    # ==========================================
    # SEND AI RESPONSE TO FRONTEND
    # ==========================================
    async def send_responses():

        while True:

            response = await session.response_queue.get()

            audio_path = response.get("audio_file")
            audio_url = ""

            if audio_path:
                audio_url = (
                        "/audio/"
                        + os.path.basename(audio_path)
                )

            # SEND RESPONSE
            await websocket.send_json({

                "session_id": session_id,

                "user_text": response.get("user_text"),

                "ai_response": response.get("ai_response"),

                # Empty string means "no audio" to the frontend.
                "audio_file": audio_url
            })

            print("Response sent")

    # ==========================================
    # RUN BOTH TASKS
    # ==========================================
    try:

        await asyncio.gather(
            receive_audio(),
            send_responses()
        )

    except WebSocketDisconnect:

        print(f"Client disconnected: {session_id}")

    except Exception as e:

        print("WebSocket Error:", e)

    finally:

        session.stop_tts = True

        if (
            session.playback_task
            and not session.playback_task.done()
        ):
            session.playback_task.cancel()

        worker_task.cancel()

        await remove_session(session_id)

        print(f"Session removed: {session_id}")
