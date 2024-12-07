import io
import logging
import wave
from typing import Optional, List, Tuple
from collections import deque
from dataclasses import dataclass
import numpy as np
from faster_whisper import WhisperModel
from seamlessconv.config.settings import WhisperSettings
from seamlessconv.event.eventbus import EventBus
from ..base_stt import BaseSTT

logger = logging.getLogger(__name__)

@dataclass
class TranscriptionSegment:
    text: str
    start_time: float
    end_time: float

class TranscriptionContext:
    def __init__(self, max_history: int = 5):
        self.segments: List[TranscriptionSegment] = []
        self.last_timestamp: float = 0
        self.max_history = max_history

    def add_segment(self, text: str, start_time: float, end_time: float):
        self.segments.append(TranscriptionSegment(text, start_time, end_time))
        if len(self.segments) > self.max_history:
            self.segments.pop(0)
        self.last_timestamp = end_time

    def get_recent_text(self) -> str:
        return " ".join(segment.text for segment in self.segments)

class AudioProcessor:
    def __init__(self, 
                 energy_threshold: float = 0.01,
                 chunk_duration: float = 2.0,
                 min_speech_duration: float = 0.3):
        self.energy_threshold = energy_threshold
        self.chunk_duration = chunk_duration
        self.min_speech_duration = min_speech_duration
        self.silence_frames = deque(maxlen=5)
        self.recording = False
        self.recording_start_time = 0
        self.audio_buffer = []
        self.chunk_buffer = []
        self.processed_duration = 0
        self.chunk_samples = None

    def initialize_chunk_size(self, sample_rate: int):
        """Calculate chunk size based on desired duration and sample rate"""
        self.chunk_samples = int(self.chunk_duration * sample_rate)

    def calculate_energy(self, audio_data: np.ndarray) -> float:
        float_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max
        return np.sqrt(np.mean(float_data**2))

    def is_silence(self) -> bool:
        if len(self.silence_frames) < self.silence_frames.maxlen:
            return False
        recent_energy = np.mean(list(self.silence_frames))
        return recent_energy < self.energy_threshold

    def is_speech(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        float_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max
        window_size = int(sample_rate * 0.02)
        windows = np.array_split(float_data, len(float_data) // window_size)
        energies = [np.sqrt(np.mean(window**2)) for window in windows if len(window) == window_size]
        speech_duration = sum(1 for energy in energies if energy > self.energy_threshold) * 0.02
        return speech_duration >= self.min_speech_duration

    def process_chunk(
        self,
        audio_chunk: np.ndarray,
        sample_rate: int
    ) -> Tuple[Optional[np.ndarray], float, float]:
        """Process an audio chunk with fixed-time intervals"""
        if self.chunk_samples is None:
            self.initialize_chunk_size(sample_rate)

        self.chunk_buffer.extend(audio_chunk)

        if len(self.chunk_buffer) >= self.chunk_samples:
            # Extract the complete chunk
            complete_chunk = np.array(self.chunk_buffer[:self.chunk_samples])
            # Keep remaining samples
            self.chunk_buffer = self.chunk_buffer[self.chunk_samples:]

            current_energy = self.calculate_energy(complete_chunk)
            self.silence_frames.append(current_energy)

            chunk_start_time = self.processed_duration
            chunk_end_time = chunk_start_time + self.chunk_duration
            self.processed_duration = chunk_end_time

            # If chunk contains speech, return it for processing
            if self.is_speech(complete_chunk, sample_rate):
                return complete_chunk, chunk_start_time, chunk_end_time

        return None, 0, 0

    def create_wav_buffer(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        channels: int
    ) -> io.BytesIO:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)
        return wav_buffer

class WhisperProvider(BaseSTT):
    def __init__(self, event_bus: EventBus, config: WhisperSettings):
        super().__init__(event_bus, config)
        self.audio_processor = AudioProcessor(
            config.energy_threshold,
            config.chunk_duration,
            config.min_duration
        )

        self.model = WhisperModel(
            config.size_model,
            device=config.device,
            compute_type=config.compute_type
        )
        self.context = TranscriptionContext()

    def process_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """Process a single chunk of audio data with context"""
        complete_utterance, start_time, end_time = self.audio_processor.process_chunk(
            audio_data, 
            self.config.sample_rate
        )

        if complete_utterance is not None:
            if self.audio_processor.is_speech(complete_utterance, self.config.sample_rate):
                wav_buffer = self.audio_processor.create_wav_buffer(
                    complete_utterance,
                    self.config.sample_rate,
                    self.config.channels
                )

                prompt = self.context.get_recent_text()
                segments, _ = self.model.transcribe(
                    wav_buffer,
                    initial_prompt=prompt if prompt else None
                )

                text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())

                if text:
                    self.context.add_segment(text, start_time, end_time)
                    return text

        return None

    def get_full_transcript(self) -> str:
        """Get the complete transcript with all context"""
        return self.context.get_recent_text()
