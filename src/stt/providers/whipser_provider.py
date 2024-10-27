import io
from queue import Queue
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import wave
import time
import logging
from typing import List, Optional
from collections import deque

from ...config.settings import WhisperSettings
from ..base import SpeechProvider

logger = logging.getLogger(__name__)

class AudioBuffer:
    def __init__(self, sample_rate: int, channels: int, dtype=np.int16):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.buffer: List[np.ndarray] = []
        self.overlap_buffer = np.array([], dtype=dtype)

    def add_chunk(self, chunk: np.ndarray) -> None:
        self.buffer.append(chunk)

    def get_total_samples(self) -> int:
        return sum(len(chunk) for chunk in self.buffer)

    def get_combined_audio(self) -> np.ndarray:
        if not self.buffer:
            return np.array([], dtype=self.dtype)
        combined = np.concatenate(self.buffer)
        if len(self.overlap_buffer) > 0:
            combined = np.concatenate([self.overlap_buffer, combined])
        return combined

    def clear(self) -> None:
        self.buffer = []
        self.overlap_buffer = np.array([], dtype=self.dtype)

class AudioProcessor:
    def __init__(self, 
                 energy_threshold: float = 0.01,
                 min_duration: float = 0.3,
                 max_duration: float = 5.0):
        self.energy_threshold = energy_threshold
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.silence_frames = deque(maxlen=5)

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
        speech_windows = sum(1 for energy in energies if energy > self.energy_threshold)
        return (speech_windows * 0.02) >= self.min_duration

    def create_wav_buffer(self, audio_data: np.ndarray, sample_rate: int, channels: int) -> io.BytesIO:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)
        return wav_buffer


class WhisperProvider(SpeechProvider):
    def __init__(self, shared_queue: Queue, config: WhisperSettings):
        self.audio_processor = AudioProcessor(
            energy_threshold=config.energy_threshold,
            min_duration=config.min_duration,
            max_duration=config.max_duration
        )
        self.audio_buffer = AudioBuffer(
            sample_rate=config.sample_rate,
            channels=config.channels
        )
        self.audio_queue = Queue()
        self.recording = False
        self.recording_start_time = 0
        super().__init__(shared_queue, config)

    def _setup_provider(self) -> None:
        self.model = WhisperModel(
            self.config.size_model,
            device=self.config.device,
            compute_type=self.config.compute_type
        )

    def _setup_audio_stream(self):
        chunk_samples = int(self.config.sample_rate * self.config.chunk_duration)
        return sd.InputStream(
            channels=self.config.channels,
            samplerate=self.config.sample_rate,
            dtype=np.int16,
            blocksize=chunk_samples,
            callback=self._audio_callback
        )

    def _audio_callback(self, indata: np.ndarray, frames: int, 
                       time_info: dict, status: Optional[str]) -> None:
        if status:
            logger.debug(f"Stream callback status: {status}")
        self.audio_queue.put(indata.copy())

    def _process_audio(self, audio_data: np.ndarray) -> None:
        if not self.audio_processor.is_speech(audio_data, self.config.sample_rate):
            return

        segments, _ = self.model.transcribe(
            self.audio_processor.create_wav_buffer(
                audio_data, 
                self.config.sample_rate,
                self.config.channels
            )
        )
        
        for segment in segments:
            text = segment.text.strip()
            if text:
                self.shared_queue.put(text)

    def _run(self) -> None:
        with self._setup_audio_stream():
            while not self.should_stop.is_set():
                try:
                    audio_chunk = self.audio_queue.get(timeout=1)
                    current_energy = self.audio_processor.calculate_energy(audio_chunk)
                    self.audio_processor.silence_frames.append(current_energy)
                    
                    if not self.recording and current_energy > self.audio_processor.energy_threshold:
                        self.recording = True
                        self.recording_start_time = time.time()
                        self.audio_buffer.clear()
                    
                    if self.recording:
                        self.audio_buffer.add_chunk(audio_chunk)
                        elapsed_time = time.time() - self.recording_start_time
                        
                        should_stop = (
                            (elapsed_time >= self.audio_processor.min_duration and 
                             self.audio_processor.is_silence()) or
                            elapsed_time >= self.audio_processor.max_duration
                        )
                        
                        if should_stop:
                            audio_data = self.audio_buffer.get_combined_audio()
                            self._process_audio(audio_data)
                            self.audio_buffer.clear()
                            self.recording = False
                    
                except Queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")