from ..config.settings import LLMConfig
from .providers.openai_provider import OpenAIProvider
from .providers.llama_provider import LlamaProvider
import os

class LLMFactory:
    @staticmethod
    def create(config: LLMConfig):
        if config.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                config.openai.api_key = api_key
            
            return OpenAIProvider(config.openai)
        elif config.provider == "llama":
            return LlamaProvider(config.llama)
        raise ValueError(f"Unknown LLM provider: {config.provider}")
