# # Backend/audio_player.py
#
# import time
# import pygame
#
#
# # =========================================================
# # INIT PYGAME MIXER
# # =========================================================
# pygame.mixer.init()
#
#
# # =========================================================
# # PLAY AUDIO
# # =========================================================
# def play_audio(audio_path, session):
#
#     try:
#
#         # =============================================
#         # SESSION STATE
#         # =============================================
#         session.is_bot_speaking = True
#
#         session.stop_tts = False
#
#         print(f"Playing audio: {audio_path}")
#
#         # =============================================
#         # LOAD AUDIO
#         # =============================================
#         pygame.mixer.music.load(audio_path)
#
#         # =============================================
#         # PLAY AUDIO
#         # =============================================
#         pygame.mixer.music.play()
#
#         # =============================================
#         # PLAYBACK LOOP
#         # =============================================
#         while pygame.mixer.music.get_busy():
#
#             # =========================================
#             # INTERRUPTION CHECK
#             # =========================================
#             if session.stop_tts:
#
#                 print("Stopping TTS playback")
#
#                 pygame.mixer.music.stop()
#
#                 break
#
#             time.sleep(0.05)
#
#     except Exception as e:
#
#         print(f"Audio Playback Error: {e}")
#
#     finally:
#
#         # =============================================
#         # CLEANUP
#         # =============================================
#         pygame.mixer.music.stop()
#
#         session.is_bot_speaking = False
#
#         session.stop_tts = False
#
#         print("Playback finished")