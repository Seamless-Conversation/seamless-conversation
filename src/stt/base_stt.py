from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from ..base_component import BaseComponent
from ..config.settings import STTConfig
from .audio_input import AudioConfig, AudioInput
from abc import ABC, abstractmethod
from typing import Optional
import queue
import time
import numpy as np
import logging

logger = logging.getLogger(__name__)

class BaseSTT(BaseComponent):
    """Base class for Speech-to-Text providers"""
    def __init__(self, event_bus: EventBus, config: STTConfig):
        super().__init__(event_bus)
        self.config = config
        self.audio_input: Optional[AudioInput] = None
        self.user = "user"
        self.group = "group_a"
        self.event_bus.subscribe(EventType.STT_USER_UPDATE_DATA, self._handle_user_update_data)

    @abstractmethod
    def process_audio(self, audio_data: bytes) -> str:
        """Process audio data into text - implemented by providers"""
        pass

    def _handle_user_update_data(self, event: Event) -> None:
        self.user = event.speaker_id
        self.user = event.group_id

    def _run_worker(self) -> None:
        self.audio_input = AudioInput(AudioConfig(
            sample_rate=self.config.sample_rate,
            dtype="int16",
            channels=self.config.channels,
            blocksize=8000
        ))

        self.audio_input.start()

        while self.running:
            try:
                audio_data = self.audio_input.get_audio_block(0.1)
                # Check if audio_data exists and has content
                if audio_data is not None and isinstance(audio_data, np.ndarray) and audio_data.size > 0:
                    text = self.process_audio(audio_data)
                    if text:
                        logger.debug(text)
                        self.event_bus.publish(Event(
                            type=EventType.STT_TRANSCRIPTION_READY,
                            speaker_id= self.user,
                            group_id= "group_a",
                            timestamp=time.time(),
                            data={'text': text}
                        ))

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio block: {str(e)}")
                continue

        self.audio_input.stop()