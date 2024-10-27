from ..base import LLMProvider
from ...config.settings import OpenAISettings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    def __init__(self, settings: OpenAISettings):
        self.settings = settings
        self.client = None

    def setup(self):
        try:
            self.client = OpenAI(api_key=self.settings.api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise RuntimeError("OpenAI initialization failed") from e

    def generate_response(self, messages):
        if self.client is None:
            raise RuntimeError("OpenAI provider not properly initialized. Call setup() first.")
        
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