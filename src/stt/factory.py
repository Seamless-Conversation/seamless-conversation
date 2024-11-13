from ..config.settings import STTConfig
from .providers.vosk_provider import VoskProvider
from .providers.whipser_provider import WhisperProvider
from src.event.eventbus import EventBus

class STTFactory:
    @staticmethod
    def create(event_bus: EventBus, config: STTConfig):
        if config.provider == "vosk":
            return VoskProvider(event_bus, config.vosk)
            VoskProvider()
        elif config.provider == "whisper":
            return WhisperProvider(event_bus, config.whisper)
        raise ValueError(f"Unknown STT provider: {config.provider}")