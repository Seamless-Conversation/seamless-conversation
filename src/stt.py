import io
import queue
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import wave
import time
from typing import List, Optional

class AudioBuffer:
    def __init__(self, sample_rate: int, channels: int, dtype=np.int16):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.buffer: List[np.ndarray] = []
        self.overlap_buffer = np.array([], dtype=dtype)

    def add_chunk(self, chunk: np.ndarray) -> None:
        self.buffer.append(chunk)

    def get_total_samples(self) -> int:
        return sum(len(chunk) for chunk in self.buffer)

    def get_combined_audio(self) -> np.ndarray:
        if not self.buffer:
            return np.array([], dtype=self.dtype)
        combined = np.concatenate(self.buffer)
        if len(self.overlap_buffer) > 0:
            combined = np.concatenate([self.overlap_buffer, combined])
        return combined

    def update_overlap(self, audio: np.ndarray, chunk_samples: int, overlap_samples: int) -> np.ndarray:
        self.overlap_buffer = audio[chunk_samples - overlap_samples:chunk_samples]
        return audio[:chunk_samples]

    def clear_and_store_remainder(self, audio: np.ndarray, chunk_samples: int) -> None:
        remaining = audio[chunk_samples:]
        self.buffer = [remaining] if len(remaining) > 0 else []

class AudioProcessor:
    def __init__(self, energy_threshold: float = 0.005, min_duration: float = 0.3):
        self.energy_threshold = energy_threshold
        self.min_duration = min_duration

    # Avoid "thank you", "thanks for watching" ect by analyzing the speech based on energy levels
    def is_speech(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        float_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max
        window_size = int(sample_rate * 0.02)
        windows = np.array_split(float_data, len(float_data) // window_size)
        energies = [np.sqrt(np.mean(window**2)) for window in windows if len(window) == window_size]
        speech_windows = sum(1 for energy in energies if energy > self.energy_threshold)
        return (speech_windows * 0.02) >= self.min_duration

    def create_wav_buffer(self, audio_data: np.ndarray, sample_rate: int, channels: int) -> io.BytesIO:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)
        return wav_buffer

class AudioTranscriber:
    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8"):
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16
        self.chunk_duration = 2
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
        
        self.processing_chunk_duration = 3
        self.processing_chunk_samples = int(self.sample_rate * self.processing_chunk_duration)
        self.overlap_duration = 0.5
        self.overlap_samples = int(self.sample_rate * self.overlap_duration)
        
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.audio_queue = queue.Queue()
        self.audio_buffer = AudioBuffer(self.sample_rate, self.channels, self.dtype)
        self.processor = AudioProcessor()
        self.is_running = False

    def audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: Optional[str]) -> None:
        if status:
            print(f"Stream callback status: {status}")
        self.audio_queue.put(indata.copy())

    def process_chunk(self, audio_chunk: np.ndarray) -> None:
        if not self.processor.is_speech(audio_chunk, self.sample_rate):
            return

        wav_buffer = self.processor.create_wav_buffer(audio_chunk, self.sample_rate, self.channels)
        segments, _ = self.model.transcribe(wav_buffer)
        
        current_time = time.strftime("%H:%M:%S")
        for segment in segments:
            text = segment.text.strip()
            if text and len(text) > 3:
                print(f"[{current_time}] Transcription: {text}")

    def process_audio(self) -> None:
        while self.is_running:
            try:
                audio_chunk = self.audio_queue.get(timeout=1)
                self.audio_buffer.add_chunk(audio_chunk)
                
                if self.audio_buffer.get_total_samples() < self.processing_chunk_samples:
                    continue
                    
                combined_audio = self.audio_buffer.get_combined_audio()
                main_chunk = self.audio_buffer.update_overlap(
                    combined_audio, 
                    self.processing_chunk_samples, 
                    self.overlap_samples
                )
                
                self.process_chunk(main_chunk)
                self.audio_buffer.clear_and_store_remainder(combined_audio, self.processing_chunk_samples)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in processing audio: {e}")

    def start_streaming(self) -> None:
        self.is_running = True
        self.processing_thread = threading.Thread(target=self.process_audio)
        self.processing_thread.start()
        
        with sd.InputStream(
            channels=self.channels,
            samplerate=self.sample_rate,
            dtype=self.dtype,
            blocksize=self.chunk_samples,
            callback=self.audio_callback
        ):
            print(f"Streaming started. Processing {self.processing_chunk_duration} second chunks "
                  f"with {self.overlap_duration}s overlap.")
            print("Press Ctrl+C to stop.")
            
            try:
                while self.is_running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.stop_streaming()

    def stop_streaming(self) -> None:
        self.is_running = False
        if hasattr(self, 'processing_thread'):
            self.processing_thread.join()
        print("\nStreaming stopped.")

def main():
    transcriber = AudioTranscriber()
    try:
        transcriber.start_streaming()
    except KeyboardInterrupt:
        transcriber.stop_streaming()

if __name__ == "__main__":
    main()