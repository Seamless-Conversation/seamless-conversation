import os
import logging
from src.event.eventbus import EventBus
from ..base_llm import BaseLLM
from ...config.settings import LlamaSettings

logger = logging.getLogger(__name__)

class LlamaProvider(BaseLLM):
    def __init__(self, event_bus: EventBus, settings: LlamaSettings):
        super().__init__(event_bus)
        self.settings = settings
        self.model = None

    def setup(self):
        if not os.path.exists(self.settings.model_path):
            raise FileNotFoundError(f"Model file not found: {self.settings.model_path}")

        try:
            # TODO
            # Setup this! And logic!            
            pass
        except Exception as e:
            logger.error(f"Failed to initialize Llama model: {e}")
            raise RuntimeError("Llama initialization failed") from e