import os
from seamlessconv.config.settings import TTSConfig
from seamlessconv.event.eventbus import EventBus
from .providers.elevenlabs_provider import ElevenLabsTTSProvider
from .providers.xtts_provider import XttsProvider

class TTSFactory:
    @staticmethod
    def create(event_bus: EventBus, config: TTSConfig):
        if config.provider == "elevenlabs":
            if config.elevenlabs.api_key is None:
                api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                config.elevenlabs.api_key = api_key

            return ElevenLabsTTSProvider(event_bus, config.elevenlabs)
        elif config.provider == "xtts":
            return XttsProvider(event_bus, config.xtts)
        raise ValueError(f"Unkown TTS provider: {config.provider}")
