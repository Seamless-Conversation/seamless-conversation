from abc import ABC, abstractmethod
from queue import Queue
from threading import Thread, Event
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SpeechConfig(ABC):
    """Base configuration class for speech recognition providers"""
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = 'int16'

class SpeechProvider(ABC):
    def __init__(self, shared_queue: Queue, config: SpeechConfig):
        self.shared_queue = shared_queue
        self.config = config
        self.should_stop = Event()
        self.processing_thread: Optional[Thread] = None
        self._setup_provider()

    @abstractmethod
    def _setup_provider(self) -> None:
        """Initialize provider-specific resources"""
        pass

    @abstractmethod
    def _process_audio(self, audio_data: bytes) -> None:
        """Process audio data and put results in shared queue"""
        pass

    @abstractmethod
    def _setup_audio_stream(self) -> Any:
        """Set up the audio input stream"""
        pass

    def start(self) -> None:
        """Start the speech recognition process"""
        self.processing_thread = Thread(target=self._run)
        self.processing_thread.start()

    def stop(self) -> None:
        """Stop the speech recognition process"""
        self.should_stop.set()
        if self.processing_thread:
            self.processing_thread.join()
            logger.info(f"{self.__class__.__name__} stopped")

    @abstractmethod
    def _run(self) -> None:
        """Main processing loop"""
        pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()