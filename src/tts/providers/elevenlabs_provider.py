from ..base_tts import BaseTTS
from ...config.settings import ElevenlabsSettings
import requests
import logging
from typing import Dict, List, Union
from src.event.eventbus import EventBus
import json
import base64

logger = logging.getLogger(__name__)

class ElevenLabsTTSProvider(BaseTTS):
    def __init__(self, event_bus: EventBus, settings: ElevenlabsSettings):
        super().__init__(event_bus)
        self.settings = settings

    def synthesize_speech(self, text):
        voice_id = "iP95p4xoKVk53GoZ742B"

        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.settings.api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        response = requests.post(
            url,
            json=data,
            headers=headers,
        )

        if response.status_code != 200:
            logger.error(f"Error encountered, status: {response.status_code}, "f"content: {response.text}")

        json_string = response.content.decode("utf-8")
        response_dict = json.loads(json_string)

        audio_bytes = base64.b64decode(response_dict["audio_base64"])

        word_timestamps = self.process_word_timings(response_dict['alignment'].get('characters'), response_dict['alignment'].get('character_end_times_seconds'))

        return (audio_bytes, word_timestamps)


    def process_word_timings(self, characters, end_times):
        """
        Combines characters into words and pairs them with their end times.
        
        Args:
            characters (list): List of individual characters
            end_times (list): List of end times for each character
        
        Returns:
            list: List of tuples containing (word, end_time)
        """
        if len(characters) != len(end_times):
            raise ValueError("Characters and end times must have the same length")

        words = []
        word_timings = []
        current_word = []

        for i, (char, time) in enumerate(zip(characters, end_times)):
            if char == ' ':
                if current_word:
                    word = ''.join(current_word)
                    words.append((word, end_times[i-1]))
                    current_word = []
            else:
                current_word.append(char)

        if current_word:
            word = ''.join(current_word)
            words.append((word, end_times[-1]))

        return words

    def setup(self):
        try:
            headers = {
                "Authorization": f"Bearer {self.settings.api_key}"
            }
            response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)

            if response.status_code != 200:
                logger.error(f"Invalid API key. Status code: {response.status_code}, Response: {response.text}")
                raise RuntimeError(f"Failed to connect to Elevenlabs: {response.status_code} - {response.reason}")
        except Exception as e:
            logger.error(f"Failed to connect to Elevenlabs: {e}")
            raise RuntimeError("Elevenlabs initialization failed") from e
        pass