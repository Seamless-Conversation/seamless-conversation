from abc import ABC, abstractmethod
import queue
import time
import logging
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from src.components.base_component import BaseComponent

logger = logging.getLogger(__name__)

class BaseLLM(BaseComponent):
    """Base class for Language Model providers"""
    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        self._queue = queue.Queue()
        self.event_bus.subscribe(EventType.LLM_INPUT_RECEIVED, self._handle_input)

    @abstractmethod
    def generate_response(self, input_text: str) -> str:
        """Generate response from input - implemented by providers"""
        pass

    def _handle_input(self, event: Event) -> None:
        self._queue.put(event)

    def _run_worker(self) -> None:
        while self.running:
            try:
                event = self._queue.get(timeout=0.1)
                input_text = event.data['text']
                context = event.data.get('context', {})

                response = self.generate_response(event.data['system_prompt'] + input_text)

                logger.debug(f" LLM response type {event.data['context']['type']}: \"{response[0:20]}\"")

                self.event_bus.publish(Event(
                    type=EventType.LLM_RESPONSE_READY,
                    speaker_id=event.speaker_id,
                    group_id=event.group_id,
                    timestamp=time.time(),
                    data={'text': response,
                    'context': context}
                ))
            except queue.Empty:
                continue