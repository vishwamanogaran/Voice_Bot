import asyncio
import os
import time
import uuid

from whisper_engine import transcribe_audio
from llm_engine import ask_llama
from tts_engine import text_to_speech
# from vad_engine import contains_speech
from interview_logger import extract_candidate_name


# =========================================================
# AUDIO PIPELINE
# =========================================================
class AudioPipeline:

    def __init__(self, upload_folder):

        self.upload_folder = upload_folder

        self.max_buffer_size = 5 * 1024 * 1024

    # =====================================================
    # MAIN PROCESSOR
    # =====================================================
    async def process_audio_chunk(

        self,

        session,

        audio_bytes
    ):

        """
        Process one finalized utterance.

        In the websocket flow, the frontend sends raw audio chunks continuously
        and then a `SPEECH_END` signal. The websocket handler concatenates the
        chunks and enqueues the *final* utterance bytes here.

        Important: do not use `session.audio_buffer` here (it's cleared in the
        websocket handler right before enqueue). Always process `audio_bytes`.
        """

        # =================================================
        # SKIP TINY UTTERANCES
        # =================================================
        if not audio_bytes or len(audio_bytes) < 1024:
            # Return a payload so the frontend can resume recording.
            return {
                "user_text": "",
                "ai_response": "",
                "audio_file": None
            }

        # Ensure we only run one utterance pipeline at a time per session.
        async with session.lock:

            print(
                f"Utterance received: {len(audio_bytes)} bytes "
                f"(session={session.session_id})"
            )

            # =================================================
            # SAVE UTTERANCE
            # =================================================
            filename = f"{uuid.uuid4()}.webm"

            audio_path = os.path.join(
                self.upload_folder,
                filename
            )

            with open(audio_path, "wb") as f:

                f.write(audio_bytes)

            with open(audio_path, "rb") as f:
                header = f.read(20)
            print("HEADER:", header)
            # =================================================
            # STT
            # =================================================
            session.is_processing = True

            print(f"Saved audio file: {audio_path}")
            print(f"Audio size: {os.path.getsize(audio_path)} bytes")

            user_text = await asyncio.to_thread(
                transcribe_audio,
                audio_path
            )

            session.is_processing = False

            # `transcribe_audio()` already attempts to delete `audio_path` (and
            # its converted wav) in its own finally block.

            print("USER:", user_text)

            # =================================================
            # EMPTY FILTER
            # =================================================
            if not user_text:
                # Still return a payload so the frontend can resume recording.
                return {
                    "user_text": "",
                    "ai_response": "",
                    "audio_file": None
                }

            user_text = user_text.strip()

            # =================================================
            # NAME EXTRACTION + LOGGING
            # =================================================
            if session.logger:

                if (
                    (not session.candidate_name)
                    or session.candidate_name == "Unknown"
                ):
                    try:
                        name = await extract_candidate_name(
                            user_text=user_text,
                            ask_llama_fn=ask_llama
                        )
                    except Exception:
                        name = "Unknown"

                    if name and name != "Unknown":
                        session.candidate_name = name
                        session.logger.set_candidate_name(name)

                session.logger.add_turn("user", user_text)

            if len(user_text) < 3:
                return {
                    "user_text": user_text,
                    "ai_response": "",
                    "audio_file": None
                }

            # =================================================
            # DUPLICATE FILTER
            # =================================================
            if (
                user_text.lower()
                ==
                session.last_user_text.lower()
            ):
                print("Duplicate transcript")
                return {
                    "user_text": user_text,
                    "ai_response": "",
                    "audio_file": None
                }

            # =================================================
            # OVERLAP FILTER
            # =================================================
            if (
                session.last_user_text
                and user_text.lower() in session.last_user_text.lower()
            ):
                print("Overlapping transcript")
                return {
                    "user_text": user_text,
                    "ai_response": "",
                    "audio_file": None
                }

            # =================================================
            # RESPONSE COOLDOWN
            # =================================================
            current_time = time.time()
            if (
                current_time - session.last_response_time
                <
                session.response_cooldown
            ):
                print("Cooldown active")
                return {
                    "user_text": user_text,
                    "ai_response": "",
                    "audio_file": None
                }

            # =================================================
            # SAVE SESSION STATE
            # =================================================
            session.last_user_text = user_text
            session.last_response_time = current_time

            # =================================================
            # AI PROMPT
            # =================================================
            ai_prompt = f"""
You are Bala, a friendly HR interviewer.

Rules:
- Speak naturally
- Be warm and professional
- Ask only ONE interview question
- Keep responses short
- Do not sound robotic

Candidate said:
{user_text}
"""

            # =================================================
            # LLM RESPONSE
            # =================================================
            session.is_processing = True
            ai_response = await ask_llama(ai_prompt)
            session.is_processing = False

            print("AI:", ai_response)

            if session.logger and ai_response:
                session.logger.add_turn("assistant", ai_response)

            # =================================================
            # TTS GENERATION (optional)
            # =================================================
            audio_file = await asyncio.to_thread(
                text_to_speech,
                ai_response
            )

            # =================================================
            # FINAL RESPONSE
            # =================================================
            return {
                "user_text": user_text,
                "ai_response": ai_response,
                "audio_file": audio_file
            }
