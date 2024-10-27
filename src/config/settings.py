from pydantic import BaseModel, Field, validator
from typing import Literal, Optional
import os

class OpenAISettings(BaseModel):
    api_key: Optional[str]
    model: str = "gpt-3.5-turbo"
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)

class LlamaSettings(BaseModel):
    path_to_model: str
    max_tokens: int = Field(default=2048, gt=0)

class LLMConfig(BaseModel):
    provider: Literal["openai", "llama"]
    openai: Optional[OpenAISettings] = None
    llama: Optional[LlamaSettings] = None

    @validator('openai')
    def validate_openai_config(cls, v, values):
        if values.get('provider') == 'openai':
            if v is None:
                raise ValueError("OpenAI configuration required when provider is 'openai'")
        return v

    @validator('llama')
    def validate_llama_config(cls, v, values):
        if values.get('provider') == 'llama':
            if v is None:
                raise ValueError("Llama configuration required when provider is 'llama'")
        return v

class VoskSettings(BaseModel):
    path_to_model: str
    sample_rate: int
    blocksize: int
    dtype: str
    channels: int

    @validator('path_to_model')
    def validate_model_path(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Vosk model path does not exist: {v}")
        return v

class WhisperSettings(BaseModel):
    size_model: str
    device: str
    compute_type: str
    energy_threshold: float
    min_duration: float
    max_duration: float
    chunk_duration: float
    sample_rate: int
    channels: int


class STTConfig(BaseModel):
    provider: Literal["vosk", "whisper"]
    vosk: Optional[VoskSettings] = None
    whisper: Optional[WhisperSettings] = None

    @validator('vosk')
    def validate_vosk_config(cls, v, values):
        if values.get('provider') == 'vosk' and v is None:
            raise ValueError("Vosk configuration required when provider is 'vosk'")
        return v

    @validator('whisper')
    def validate_whisper_config(cls, v, values):
        if values.get('provider') == 'whisper' and v is None:
            raise ValueError("Whisper configuration required when provider is 'whisper'")
        return v

class AppConfig(BaseModel):
    llm: LLMConfig
    stt: STTConfig

    class Config:
        extra = "forbid"  # prevents additional fields