from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union
import threading
import multiprocessing
import queue
import time
import logging
from dataclasses import dataclass
from src.event.eventbus import EventBus

logger = logging.getLogger(__name__)

class BaseComponent(ABC):
    """Base class for all components"""
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._queue = queue.Queue()

    def start(self) -> None:
        """Start the component's processing thread"""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._run_worker)
            self._thread.daemon = True
            self._thread.start()

    def stop(self) -> None:
        """Stop the component's processing thread"""
        self.running = False
        if self._thread:
            self._thread.join()
            self._thread = None

    @abstractmethod
    def _run_worker(self) -> None:
        """Main thread loop - implemented by subclasses"""
        pass