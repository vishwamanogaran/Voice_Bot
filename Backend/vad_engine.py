# Backend/vad_engine.py

import io
import torch
import torchaudio

from silero_vad import (
    load_silero_vad,
    get_speech_timestamps
)


# =========================================================
# LOAD SILERO VAD MODEL
# =========================================================
model = load_silero_vad()

print("Silero VAD Loaded")


# =========================================================
# GLOBAL RESAMPLER CACHE
# =========================================================
resamplers = {}


# =========================================================
# GET RESAMPLER
# =========================================================
def get_resampler(sample_rate):

    if sample_rate not in resamplers:

        resamplers[sample_rate] = (
            torchaudio.transforms.Resample(
                orig_freq=sample_rate,
                new_freq=16000
            )
        )

    return resamplers[sample_rate]


# =========================================================
# MAIN VAD FUNCTION
# =========================================================
# def contains_speech(audio_bytes) -> bool:
# 
#     try:
#
#         # =================================================
#         # EMPTY CHECK
#         # =================================================
#         if not audio_bytes:
#
#             return False
#
#         # =================================================
#         # LOAD AUDIO FROM MEMORY
#         # =================================================
#         audio_stream = io.BytesIO(audio_bytes)
#         print("Running VAD")
#         waveform, sample_rate = torchaudio.load(
#             audio_stream
#         )
#
#         # =================================================
#         # EMPTY WAVEFORM CHECK
#         # =================================================
#         if waveform.numel() == 0:
#
#             return False
#
#         # =================================================
#         # CONVERT TO MONO
#         # =================================================
#         if waveform.shape[0] > 1:
#
#             waveform = torch.mean(
#                 waveform,
#                 dim=0,
#                 keepdim=True
#             )
#
#         # =================================================
#         # RESAMPLE TO 16kHz
#         # =================================================
#         if sample_rate != 16000:
#
#             resampler = get_resampler(sample_rate)
#
#             waveform = resampler(waveform)
#
#         # =================================================
#         # REMOVE CHANNEL DIMENSION
#         # =================================================
#         waveform = waveform.squeeze(0)
#
#         # =================================================
#         # VERY SHORT AUDIO CHECK
#         # =================================================
#         if waveform.shape[0] < 4000:
#
#             return False
#
#         # =================================================
#         # SPEECH DETECTION
#         # =================================================
#         speech_timestamps = get_speech_timestamps(
#
#             waveform,
#
#             model,
#
#             sampling_rate=16000
#         )
#
#         return len(speech_timestamps) > 0
#
#
#     except Exception as e:
#
#         print("VAD ERROR:", e)
#
#         return False