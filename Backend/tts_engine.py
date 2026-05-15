# Backend/tts_engine.py

import subprocess
import uuid
import os


# =========================================================
# CONFIG
# =========================================================
# VOICE_MODEL = "../models/en_US-ryan-high.onnx"

UPLOAD_FOLDER = "../uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# CLEAN TEXT    
# =========================================================
def clean_text(text):

    if not text:

        return ""

    text = text.strip()

    text = text.replace("\n", " ")

    text = text.replace("*", "")

    return text


# =========================================================
# TEXT TO SPEECH
# =========================================================
def text_to_speech(text):

    try:
        print("Generating TTS")
        # =============================================
        # CLEAN INPUT
        # =============================================
        text = clean_text(text)

        if not text:

            return None

        # =============================================
        # UNIQUE FILE
        # =============================================
        filename = f"{uuid.uuid4()}.wav"

        output_file = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        # =============================================
        # PIPER COMMAND
        # =============================================
        command = [

            "piper",

            "--model",
            VOICE_MODEL,

            "--output_file",
            output_file
        ]

        print("Generating TTS...")

        # =============================================
        # RUN PIPER
        # =============================================
        process = subprocess.run(

            command,

            input=text,

            text=True,

            capture_output=True,

            timeout=60
        )

        # =============================================
        # FAILURE CHECK
        # =============================================
        if process.returncode != 0:

            print("Piper failed")

            print(process.stderr)

            return None

        # =============================================
        # FILE EXISTS CHECK
        # =============================================
        if not os.path.exists(output_file):

            print("Audio file not generated")

            return None

        print(f"TTS Generated: {filename}")
        print("TTS generated")
        # =============================================
        # RETURN FULL PATH
        # =============================================
        return output_file

    except subprocess.TimeoutExpired:

        print("Piper timeout")

        return None

    except Exception as e:

        print("TTS Error:", e)

        return None