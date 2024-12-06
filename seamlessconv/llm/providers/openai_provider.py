from openai import OpenAI
import logging
from seamlessconv.event.eventbus import EventBus
from ..base_llm import BaseLLM
from ...config.settings import OpenAISettings

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLM):
    def __init__(self, event_bus: EventBus, settings: OpenAISettings):
        super().__init__(event_bus)
        self.settings = settings
        self.client = OpenAI(api_key=self.settings.api_key)

    def setup(self):
        try:
            self.client = OpenAI(api_key=self.settings.api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise RuntimeError("OpenAI initialization failed") from e

    def generate_response(self, messages):        
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.settings.model,
                temperature=self.settings.temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise