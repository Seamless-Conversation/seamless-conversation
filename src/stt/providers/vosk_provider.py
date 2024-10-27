from ..base import SpeechProvider
from ...config.settings import VoskSettings
import vosk
import sounddevice as sd
import json
from queue import Queue
import os
import logging

logger = logging.getLogger(__name__)

class VoskProvider(SpeechProvider):
    def __init__(self, shared_queue: Queue, config: VoskSettings):
        self._validate_model_path(config.path_to_model)
        self.input_queue = Queue()
        self.previous_partial = ""
        super().__init__(shared_queue, config)

    def _validate_model_path(self, path_to_model: str) -> None:
        if not os.path.exists(path_to_model):
            raise FileNotFoundError(f"Model path '{path_to_model}' does not exist")

    def _setup_provider(self) -> None:
        self.model = vosk.Model(self.config.path_to_model)
        self.recognizer = vosk.KaldiRecognizer(self.model, self.config.sample_rate)

    def _setup_audio_stream(self):
        return sd.RawInputStream(
            samplerate=self.config.sample_rate,
            blocksize=self.config.blocksize,
            dtype=self.config.dtype,
            channels=self.config.channels,
            callback=self._audio_callback
        )

    def _audio_callback(self, indata, frames, time, status):
        self.input_queue.put(bytes(indata))

    def _process_audio(self, data: bytes) -> None:
        if self.recognizer.AcceptWaveform(data):
            result = self.recognizer.Result()
            text = json.loads(result)["text"]
            self.previous_partial = ""
            return

        partial_result = self.recognizer.PartialResult()
        partial_text = json.loads(partial_result)["partial"]
        
        if not partial_text or partial_text == self.previous_partial:
            return

        new_words = partial_text[len(self.previous_partial):].strip()
        if new_words:
            self.shared_queue.put(new_words)
        self.previous_partial = partial_text

    def _run(self) -> None:
        try:
            with self._setup_audio_stream():
                while not self.should_stop.is_set():
                    data = self.input_queue.get()
                    self._process_audio(data)
        except Exception as e:
            logger.error(f"Error in speech recognition: {e}")