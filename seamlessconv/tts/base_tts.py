import queue
import logging
from typing import Union, List, Dict, Tuple
from abc import abstractmethod
from seamlessconv.config.settings import TTSConfig
from seamlessconv.components.base_component import BaseComponent
from seamlessconv.event.eventbus import EventBus, Event
from seamlessconv.event.event_types import EventType
from seamlessconv.tts.audio_manager import AudioManager

logger = logging.getLogger(__name__)

class BaseTTS(BaseComponent):
    """Base class for Text-to-Speech providers"""
    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        self.audio_manager = AudioManager(event_bus)
        self.event_bus.subscribe(EventType.TTS_START_SPEAKING, self._handle_speech_request)
        self.event_bus.subscribe(EventType.TTS_STOP_SPEAKING, self._handle_speech_interruption)

    @abstractmethod
    def synthesize_speech(self, text: str) -> Tuple[bytes, Dict[str, List[Union[str, float]]]]:
        """Convert text to audio data - implemented by providers"""

    def _handle_speech_request(self, event: Event) -> None:
        self._queue.put(event)

    def _handle_speech_interruption(self, event: Event) -> None:
        self.audio_manager.stop_player(event)

    def _run_worker(self) -> None:
        while self.running:
            try:
                event = self._queue.get(timeout=0.1)
                text = event.data['text']
                synthesized_speech = self.synthesize_speech(text)
                audio_data = synthesized_speech[0]
                word_timestamps = synthesized_speech[1]
                self.audio_manager.add_player(event, audio_data, word_timestamps, text)
                self.audio_manager.play_player(event)

            except queue.Empty:
                continue
