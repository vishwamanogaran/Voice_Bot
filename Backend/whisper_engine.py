# Backend/whisper_engine.py

import os
import subprocess

from faster_whisper import WhisperModel


# =========================================================
# LOAD WHISPER MODEL
# =========================================================
try:

    model = WhisperModel(
        "base.en",
        device="cuda",
        compute_type="int8_float16"
    )

    print("Faster-Whisper running on CUDA")

except Exception as e:

    print(f"CUDA load failed: {e}")

    print("Falling back to CPU")

    model = WhisperModel(
        "base.en",
        device="cpu",
        compute_type="int8"
    )


# =========================================================
# CONFIG
# =========================================================
MIN_VALID_BYTES = 5120


# =========================================================
# VALIDATE AUDIO FILE
# =========================================================
def is_valid_audio_file(path: str) -> bool:

    try:

        result = subprocess.run(

            [
                "ffprobe",

                "-v", "error",

                "-select_streams", "a:0",

                "-show_entries", "stream=codec_name",

                "-of", "default=noprint_wrappers=1",

                path
            ],

            capture_output=True,

            text=True
        )

        return (
            result.returncode == 0
            and
            "codec_name" in result.stdout
        )

    except:

        return False


# =========================================================
# CONVERT TO WAV
# =========================================================
def convert_to_wav(input_path: str) -> str:

    output_path = (
        input_path.rsplit(".", 1)[0]
        +
        "_conv.wav"
    )

    result = subprocess.run(

        [
            "ffmpeg",

            "-y",

            "-i", input_path,

            "-ar", "16000",

            "-ac", "1",

            "-f", "wav",

            output_path
        ],

        capture_output=True,

        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr.strip()
        )

    return output_path


# =========================================================
# MAIN TRANSCRIPTION
# =========================================================
def transcribe_audio(audio_path: str) -> str:

    wav_path = None

    try:

        # =================================================
        # FILE EXISTS
        # =================================================
        if not os.path.exists(audio_path):

            return ""
        print("Starting transcription")
        # =================================================
        # MIN SIZE CHECK
        # =================================================
        file_size = os.path.getsize(audio_path)

        if file_size < MIN_VALID_BYTES:

            print(f"Skipping tiny chunk ({file_size} bytes)")

            return ""

        # =================================================
        # VALID AUDIO CHECK
        # =================================================
        if not is_valid_audio_file(audio_path):

            print("Invalid audio container")

            return ""

        # =================================================
        # CONVERT TO CLEAN WAV
        # =================================================
        wav_path = convert_to_wav(audio_path)

        # =================================================
        # TRANSCRIBE
        # =================================================
        segments, info = model.transcribe(

            wav_path,

            language="en",

            beam_size=1,

            vad_filter=True,

            vad_parameters=dict(
                min_silence_duration_ms=500
            )
        )

        # =================================================
        # MERGE TRANSCRIPT
        # =================================================
        text = " ".join(

            segment.text

            for segment in segments

        ).strip()

        print("Transcription done")
        
        if not text:

            return ""

        print(f"Detected language: {info.language}")

        return text


    except Exception as e:

        print(f"Whisper Error: {e}")

        return ""

    finally:

        # =================================================
        # CLEANUP
        # =================================================
        for path in [audio_path, wav_path]:

            try:

                if path and os.path.exists(path):

                    os.remove(path)

            except:

                pass