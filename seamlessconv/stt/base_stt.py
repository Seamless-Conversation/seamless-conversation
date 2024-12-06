from abc import abstractmethod
from typing import Optional
import queue
import time
import logging
import numpy as np
from seamlessconv.event.eventbus import EventBus, Event
from seamlessconv.event.event_types import EventType
from seamlessconv.components.base_component import BaseComponent
from seamlessconv.config.settings import STTConfig
from seamlessconv.stt.audio_input import AudioConfig, AudioInput

logger = logging.getLogger(__name__)

class BaseSTT(BaseComponent):
    """Base class for Speech-to-Text providers"""
    def __init__(self, event_bus: EventBus, config: STTConfig):
        super().__init__(event_bus)
        self.config = config
        self.audio_input: Optional[AudioInput] = None
        self.agent_id: str
        self.group_id: str
        self.event_bus.subscribe(EventType.STT_USER_UPDATE_DATA, self._handle_user_update_data)
        self.send_eoi = False
        self.time_since_last_eoi = 0

    @abstractmethod
    def process_audio(self, audio_data: bytes) -> str:
        """Process audio data into text - implemented by providers"""

    def set_group_id(self, group_id: str) -> None:
        """Set the user's group"""
        self.group_id = group_id

    def set_agent_id(self, agent_id: str) -> None:
        """Set the user's id"""
        self.agent_id = agent_id

    def _send_eoi(self) -> None:
        """Publish end of input to event bus"""
        if self.send_eoi and time.time()-self.time_since_last_eoi > 2:
            self.send_eoi = False
            self.event_bus.publish(Event(
                type=EventType.STT_TRANSCRIPTION_READY,
                agent_id=self.agent_id,
                group_id=self.group_id,
                timestamp=time.time(),
                data={
                    'text': "[EOI]",
                    'context': {'type': 'response'}
                }
            ))

    def _handle_user_update_data(self, event: Event) -> None:
        self.agent_id = event.agent_id
        self.group_id = event.group_id

    def _run_worker(self) -> None:
        self.audio_input = AudioInput(AudioConfig(
            sample_rate=self.config.sample_rate,
            dtype="int16",
            channels=self.config.channels,
            blocksize=8000
        ))

        self.audio_input.start()

        while self.running:
            self._send_eoi()
            try:
                audio_data = self.audio_input.get_audio_block(0.1)
                # Check if audio_data exists and has content
                if audio_data is not None and isinstance(audio_data, np.ndarray) and audio_data.size > 0:
                    text = self.process_audio(audio_data)
                    if text:
                        self.time_since_last_eoi = time.time()
                        self.send_eoi = True
                        logger.debug(text)
                        self.event_bus.publish(Event(
                            type=EventType.STT_TRANSCRIPTION_READY,
                            agent_id= self.agent_id,
                            group_id= self.group_id,
                            timestamp=time.time(),
                            data={
                                'text': text,
                                'context': {'type': 'response'}
                                }
                        ))

            except queue.Empty:
                continue

        self.audio_input.stop()
