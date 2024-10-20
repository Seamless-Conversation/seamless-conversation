import queue
import sounddevice as sd
import vosk
import sys
import os
import json

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def transcribe_live(model_path="vosk-model-en-us-0.22"):
    if not os.path.exists(model_path):
        print(f"Model path '{model_path}' does not exist. Download that shit.")
        sys.exit(1)

    model = vosk.Model(model_path)
    recognizer = vosk.KaldiRecognizer(model, 16000)
    previous_partial = "" 

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        print("Listening... Press Ctrl+C to stop.")
        try:
            while True:
                data = q.get()
                if recognizer.AcceptWaveform(data):
                    result = recognizer.Result()
                    text = json.loads(result)["text"]
                    if text:
                        print("You said:", text)
                    previous_partial = ""
                else:
                    partial_result = recognizer.PartialResult()
                    partial_text = json.loads(partial_result)["partial"]

                    if partial_text and partial_text != previous_partial:

                        new_words = partial_text[len(previous_partial):].strip()
                        if new_words:
                            print("Current word:", new_words)
                        previous_partial = partial_text
        except KeyboardInterrupt:
            print("\nStopping transcription.")

if __name__ == "__main__":
    q = queue.Queue()
    transcribe_live("vosk-model-en-us-0.22")
