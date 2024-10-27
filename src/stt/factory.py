from ..config.settings import STTConfig
from .providers.vosk_provider import VoskProvider
from .providers.whipser_provider import WhisperProvider
from queue import Queue

class STTFactory:
    @staticmethod
    def create(config: STTConfig, shared_queue: Queue):
        if config.provider == "vosk":
            return VoskProvider(shared_queue, config.vosk)
            VoskProvider()
        elif config.provider == "whisper":
            return WhisperProvider(shared_queue, config.whisper)
        raise ValueError(f"Unknown STT provider: {config.provider}")