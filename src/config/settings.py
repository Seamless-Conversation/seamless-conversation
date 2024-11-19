from pydantic import BaseModel, Field, validator
from typing import Literal, Optional
import os

def configProviderValidation(cls, v, values, name: str):
    if values.get('provider') == name.lower:
        if v is None:
            raise ValueError(f"{name} configuration required when provider is '{name.lower}'")
    return v

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
        return configProviderValidation(cls, v, values, "OpenAI")

    @validator('llama')
    def validate_llama_config(cls, v, values):
        return configProviderValidation(cls, v, values, "OpenAI")


class VoskSettings(BaseModel):
    path_to_model: str
    sample_rate: int
    dtype: str
    channels: int

    # Validator incorrectly setup. Need to be fixed.
    # @validator('path_to_model')
    # def validate_model_path(cls, v):
    #     if not os.path.exists(v):
    #         raise ValueError(f"Vosk model path does not exist: {v}")
    #     return v

class WhisperSettings(BaseModel):
    size_model: str
    device: str
    compute_type: str
    energy_threshold: float
    min_duration: float
    chunk_duration: float
    sample_rate: int
    channels: int

class STTConfig(BaseModel):
    provider: Literal["vosk", "whisper"]
    vosk: Optional[VoskSettings] = None
    whisper: Optional[WhisperSettings] = None

    @validator('vosk')
    def validate_vosk_config(cls, v, values):
        return configProviderValidation(cls, v, values, "OpenAI")

    @validator('whisper')
    def validate_whisper_config(cls, v, values):
        return configProviderValidation(cls, v, values, "OpenAI")


class ElevenlabsSettings(BaseModel):
    api_key: Optional[str]

class XttsSettings(BaseModel):
    model: str
    vocoder_path: Optional[str]
    output_sample_rate: Optional[int]
    min_word_duration: float
    word_gap: float
    sample_rate: int

class TTSConfig(BaseModel):
    provider: Literal["elevenlabs", "xtts"]
    elevenlabs: Optional[ElevenlabsSettings]
    xtts: Optional[XttsSettings]

    @validator('elevenlabs')
    def validate_elevenlabs_confi(cls, v, values):
        return configProviderValidation(cls, v, values, "Elevenlabs")

class AppConfig(BaseModel):
    llm: LLMConfig
    stt: STTConfig
    tts: TTSConfig

    class Config:
        extra = "forbid"  # prevents additional fields