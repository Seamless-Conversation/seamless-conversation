from ..config.settings import TTSConfig
from .providers.elevenlabs_provider import ElevenLabsTTSProvider
from .providers.gtts_provider import GttsProvider
from src.event.eventbus import EventBus
import os

class TTSFactory:
    @staticmethod
    def create(event_bus: EventBus, config: TTSConfig):
        if config.provider == "elevenlabs":
            if config.elevenlabs.api_key is None:
                api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                config.elevenlabs.api_key = api_key

            return ElevenLabsTTSProvider(event_bus, config.elevenlabs)
        elif config.provider == "gtts":
            return GttsProvider(event_bus)
        raise ValueError(f"Unkown TTS provider: {config.provider}")