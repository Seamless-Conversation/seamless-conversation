from enum import Enum
from dataclasses import dataclass, field

class EventType(Enum):
    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    SPEECH_INTERRUPTED = "speech_interrupted"
    INTERRUPT_REQUESTED = "interrupt_requested"
    INTERRUPT_ACCEPTED = "interrupt_accepted"
    INTERRUPT_REJECTED = "interrupt_rejected"
    LLM_RESPONSE = "llm_response"
    STT_AUDIO_DETECTED = "stt_audio_detected"
    STT_TRANSCRIPTION_READY = "stt_transcription_ready"
    STT_USER_UPDATE_DATA = "stt_user_update_data"
    TTS_START_SPEAKING = "tts_start_speaking"
    TTS_STOP_SPEAKING = "tts_stop_speaking"
    TTS_STREAMING_RESPONSE = "tts_streaming_response"
    LLM_INPUT_RECEIVED = "llm_input_received"
    LLM_RESPONSE_READY = "llm_response_ready"
    AGENT_UPDATE_INFO = "agent_update_info"