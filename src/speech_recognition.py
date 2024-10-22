import os
import sys
import json
import vosk
import sounddevice as sd
from queue import Queue
from threading import Thread, Event
import logging

class SpeechRecognition:
    def __init__(self, shared_queue, model_path):
        self._validate_model_path(model_path)
        self.shared_queue = shared_queue
        self.input_queue = Queue()
        self.model = vosk.Model(model_path)
        self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
        self.should_stop = Event()
        self.recognition_thread = None
        self.previous_partial = ""

    def _validate_model_path(self, model_path):
        if not os.path.exists(model_path):
            logging.critical(f"Model path '{model_path}' does not exist. Download that shit.")
            sys.exit(1)

    def start(self):
        self.recognition_thread = Thread(target=self.transcribe_live)
        self.recognition_thread.start()

    def stop(self):
        self.should_stop.set()
        if self.recognition_thread:
            self.recognition_thread.join()

    def callback(self, indata, frames, time, status):
        self.input_queue.put(bytes(indata))

    def _process_recognition_result(self, data):
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
            logging.debug(f"SpeechRecognition heard: {new_words}")
            self.shared_queue.put(new_words)
        self.previous_partial = partial_text

    def _setup_audio_stream(self):
        return sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self.callback
        )

    def _process_audio_stream(self):
        while True:
            if self.should_stop.is_set():
                break
            data = self.input_queue.get()
            self._process_recognition_result(data)

    def transcribe_live(self):
        try:
            with self._setup_audio_stream():
                self._process_audio_stream()
        except KeyboardInterrupt:
            logging.info("Stopping transcription")
        except Exception as e:
            logging.error(f"Error in speech recognition: {e}")

def main():
    shared_queue = Queue()
    model_path = "models/vosk-model-en-us-0.22"
    
    recognizer = SpeechRecognition(shared_queue, model_path)
    try:
        recognizer.start()
        while True:
            pass
    except KeyboardInterrupt:
        recognizer.stop()

if __name__ == "__main__":
    main()