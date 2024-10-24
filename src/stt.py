import io
import queue
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import wave
import time
from typing import List, Optional
from collections import deque

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

    def clear(self) -> None:
        self.buffer = []
        self.overlap_buffer = np.array([], dtype=self.dtype)

class AudioProcessor:
    def __init__(self, 
                 energy_threshold: float = 0.01,
                 min_duration: float = 0.3,
                 max_duration: float = 5.0):
        self.energy_threshold = energy_threshold
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.silence_frames = deque(maxlen=5)

    def calculate_energy(self, audio_data: np.ndarray) -> float:
        float_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max
        return np.sqrt(np.mean(float_data**2))

    def is_silence(self) -> bool:
        if len(self.silence_frames) < self.silence_frames.maxlen:
            return False

        recent_energy = np.mean(list(self.silence_frames))
        return recent_energy < self.energy_threshold

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
    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "float32"):
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16
        self.chunk_duration = 0.1
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
        
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.audio_queue = queue.Queue()
        self.audio_buffer = AudioBuffer(self.sample_rate, self.channels, self.dtype)
        self.processor = AudioProcessor()
        self.is_running = False
        self.recording = False
        self.recording_start_time = 0

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
            if text:
                print(f"[{current_time}] Transcription: {text}")

    def process_audio(self) -> None:
        while self.is_running:
            try:
                audio_chunk = self.audio_queue.get(timeout=1)
                current_energy = self.processor.calculate_energy(audio_chunk)
                self.processor.silence_frames.append(current_energy)
                
                if not self.recording and current_energy > self.processor.energy_threshold:
                    self.recording = True
                    self.recording_start_time = time.time()
                    self.audio_buffer.clear()
                
                if self.recording:
                    self.audio_buffer.add_chunk(audio_chunk)
                    elapsed_time = time.time() - self.recording_start_time
                    
                    should_stop = (
                        (elapsed_time >= self.processor.min_duration and 
                         self.processor.is_silence()) or
                        elapsed_time >= self.processor.max_duration
                    )
                    
                    if should_stop:
                        audio_data = self.audio_buffer.get_combined_audio()
                        self.process_chunk(audio_data)
                        self.audio_buffer.clear()
                        self.recording = False
                
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
            print("Streaming started. Processing audio based on voice activity detection.")
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