from src.event.event_types import EventType
from dataclasses import dataclass
from typing import Dict, List, Callable, Any
from enum import Enum
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class Event:
    type: EventType
    speaker_id: str
    group_id: str
    timestamp: float
    data: dict

class EventBus:
    def __init__(self, max_workers: Optional[int] = None):
        self._subscribers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }
        self._subscribers_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers or 4)
        self._event_queue = queue.Queue()
        self._running = True
        self._event_processor = threading.Thread(target=self._process_events)
        self._event_processor.daemon = True
        self._event_processor.start()

    def _process_events(self):
        """Background thread to process events asynchronously"""
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
                self._event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    def _dispatch_event(self, event: Event):
        """Dispatch a single event to all subscribers"""
        with self._subscribers_lock:
            # Create a copy of subscribers to avoid holding the lock during callback execution
            subscribers = self._subscribers[event.type].copy()

        # Execute callbacks
        for callback in subscribers:
            try:
                self._executor.submit(callback, event)
            except Exception as e:
                logger.error(f"Error dispatching event to callback: {e}")

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to event"""
        with self._subscribers_lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """unsubsribe from event"""
        with self._subscribers_lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event: Event) -> None:
        """Event publication"""
        self._event_queue.put(event)

    def shutdown(self, wait: bool = True):
        """Cleanup resources and shutdown the event bus"""
        self._running = False
        if wait:
            self._event_queue.join()
            self._executor.shutdown(wait=True)