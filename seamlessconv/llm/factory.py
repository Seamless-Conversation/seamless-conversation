import os
from seamlessconv.config.settings import LLMConfig
from seamlessconv.event.eventbus import EventBus
from .providers.openai_provider import OpenAIProvider
from .providers.llama_provider import LlamaProvider

class LLMFactory:
    @staticmethod
    def create(event_bus: EventBus, config: LLMConfig):
        if config.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                config.openai.api_key = api_key

            return OpenAIProvider(event_bus, config.openai)
        elif config.provider == "llama":
            return LlamaProvider(event_bus, config.llama)
        raise ValueError(f"Unknown LLM provider: {config.provider}")
