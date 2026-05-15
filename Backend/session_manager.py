# Backend/session_manager.py

import asyncio
import time
from dataclasses import dataclass, field

from interview_logger import InterviewLogger


# =========================================================
# SESSION STATE
# =========================================================
@dataclass
class SessionState:

    session_id: str

    # =====================================================
    # AUDIO BUFFER
    # =====================================================
    audio_buffer: bytearray = field(
        default_factory=bytearray
    )

    # =====================================================
    # AUDIO BUFFER LOCK
    # =====================================================
    buffer_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock
    )

    # =====================================================
    # SESSION QUEUES
    # =====================================================
    audio_queue: asyncio.Queue = field(
        default_factory=asyncio.Queue
    )

    response_queue: asyncio.Queue = field(
        default_factory=asyncio.Queue
    )

    # =====================================================
    # PLAYBACK TASK
    # =====================================================
    playback_task: asyncio.Task = None

    # =====================================================
    # SESSION FLAGS
    # =====================================================
    is_bot_speaking: bool = False

    stop_tts: bool = False

    is_processing: bool = False

    # =====================================================
    # SPEECH TIMING
    # =====================================================
    last_speech_time: float = field(
        default_factory=time.time
    )

    silence_threshold: float = 1.2

    # =====================================================
    # RESPONSE FILTERING
    # =====================================================
    last_user_text: str = ""

    last_response_time: float = 0

    response_cooldown: float = 2.0

    # =====================================================
    # GENERAL SESSION LOCK
    # =====================================================
    lock: asyncio.Lock = field(
        default_factory=asyncio.Lock
    )

    # =====================================================
    # INTERVIEW LOGGING
    # =====================================================
    candidate_name: str = "Unknown"
    logger: InterviewLogger | None = None


# =========================================================
# SESSION STORAGE
# =========================================================
sessions = {}


# =========================================================
# CREATE SESSION
# =========================================================
def create_session(session_id):

    session = SessionState(session_id)

    # Create per-session interview logger (folder gets renamed once name is known).
    # Stored at repo root: ./create_interviews/<Name>_<session_id>/conversation.json
    logger = InterviewLogger(base_dir="../create_interviews", session_id=session_id)
    logger.init_dir()
    session.logger = logger

    sessions[session_id] = session

    print(f"Session created: {session_id}")

    return session


# =========================================================
# GET SESSION
# =========================================================
def get_session(session_id):

    return sessions.get(session_id)


# =========================================================
# REMOVE SESSION
# =========================================================
async def remove_session(session_id):

    session = sessions.get(session_id)

    if not session:

        return

    try:

        # =================================================
        # STOP PLAYBACK
        # =================================================
        session.stop_tts = True

        # =================================================
        # CANCEL PLAYBACK TASK
        # =================================================
        if session.playback_task:

            session.playback_task.cancel()

        # =================================================
        # CLEAR AUDIO BUFFER
        # =================================================
        async with session.buffer_lock:

            session.audio_buffer.clear()

        # =================================================
        # CLEAR QUEUES
        # =================================================
        while not session.audio_queue.empty():

            await session.audio_queue.get()

        while not session.response_queue.empty():

            await session.response_queue.get()

    except Exception as e:

        print(f"Session cleanup error: {e}")

    finally:

        del sessions[session_id]

        print(f"Session removed: {session_id}")
