import vosk
import json
import os
import logging
from ..base_stt import BaseSTT
from ...config.settings import VoskSettings
from src.event.eventbus import EventBus

logger = logging.getLogger(__name__)

class VoskProvider(BaseSTT):
    def __init__(self, event_bus: EventBus, config: VoskSettings):
        super().__init__(event_bus, config)
        self._validate_model_path(config.path_to_model)
        self.previous_partial = ""
        self.model = vosk.Model(self.config.path_to_model)
        self.recognizer = vosk.KaldiRecognizer(self.model, self.config.sample_rate)

    def _validate_model_path(self, path_to_model: str) -> None:
        if not os.path.exists(path_to_model):
            raise FileNotFoundError(f"Model path '{path_to_model}' does not exist")

    def process_audio(self, data) -> None:
        if self.recognizer.AcceptWaveform(bytes(data)):
            result = self.recognizer.Result()
            text = json.loads(result)["text"]
            self.previous_partial = ""
            return

        partial_result = self.recognizer.PartialResult()
        partial_text = json.loads(partial_result)["partial"]

        if not partial_text or partial_text == self.previous_partial:
            return

        new_words = partial_text[len(self.previous_partial):].strip()
        self.previous_partial = partial_text
        return new_words