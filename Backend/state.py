import time


class BotState:

    def __init__(self):

        # Conversation State
        self.last_user_text = ""

        self.last_response_time = 0

        # Audio State
        self.audio_buffer = bytearray()

        self.last_speech_time = time.time()

        # Bot State
        self.is_bot_speaking = False

        self.is_processing = False

        # Config
        self.response_cooldown = 4

        self.silence_threshold = 1.2

        self.stop_tts = False



# Global Singleton
bot_state = BotState()