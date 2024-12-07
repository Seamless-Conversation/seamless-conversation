from dataclasses import dataclass
from typing import Optional
import threading
import queue
import logging
import sounddevice as sd
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class AudioConfig:
    sample_rate: int = 16000
    dtype: str = "int16"
    channels: int = 1
    blocksize: int = 8000

class AudioInput:
    """Handles audio input stream and routing of audio data"""

    def __init__(self, config: AudioConfig):
        self.config = config
        self.input_queue = queue.Queue()
        self._stream = Optional[sd.RawInputStream]
        self._running = False
        self._lock = threading.Lock()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: dict,
        status: Optional[str]
    ) -> None:
        """Callback for the sounddevice input stream"""
        if status:
            logger.warning("Audio callback status: %s", status)
        self.input_queue.put((indata.copy()))

    def start(self) -> None:
        """Start the audio input stream"""
        with self._lock:
            if not self._running:
                self._stream = sd.InputStream(
                    samplerate=self.config.sample_rate,
                    dtype=self.config.dtype,
                    channels=self.config.channels,
                    blocksize=self.config.blocksize,
                    callback=self._audio_callback
                )
                self._stream.start()
                self._running = True

    def stop(self) -> None:
        """Stop the audio input stream"""
        with self._lock:
            if self._running:
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                self._running = False

    def get_audio_block(self, timeout: Optional[float] = None):
        """Get the next block of audio data"""
        try:
            return self.input_queue.get(timeout=timeout)
        except queue.Empty:
            return None
