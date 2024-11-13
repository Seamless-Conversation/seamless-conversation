from dataclasses import dataclass
from pydub import AudioSegment
import wave
import pyaudio
import threading
import io
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from src.speech import SpeechType

logger = logging.getLogger(__name__)

@dataclass
class AudioContext:
    """Data class to store audio context information"""
    original_text: str
    transcription: List[Tuple[str, float]]
    last_publish_time: float = 0
    publish_snippet_time: float = 0
    start_time: Optional[float] = None
    pause_position: float = 0

class AudioPlayer:
    """Handles playing of individual audio streams"""
    CHUNK_SIZE = 1024
    PUBLISH_INTERVAL = 3

    def __init__(self, audio_data: bytes, event: Event, context: AudioContext, event_bus: EventBus, on_finished_callback: callable):
        self.event = event
        self.context = context
        self.event_bus = event_bus
        self.on_finished_callback = on_finished_callback

        self.wf = self._init_wave_file(audio_data)
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        self.playing = False
        self.thread: Optional[threading.Thread] = None

    def _init_wave_file(self, audio_data: bytes) -> wave.Wave_read:
        """Convert MP3 data to WAV format"""
        audio_stream = io.BytesIO(audio_data)
        audio = AudioSegment.from_mp3(audio_stream)
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        return wave.open(wav_io, 'rb')

    def _publish_snippet(self, is_final: bool = False) -> None:
        if 'context' not in self.event.data:
            return

        current_time = time.time() - self.context.start_time

        if is_final:
            word_timestamps = [
                (word, timestamp)
                for word, timestamp in self.context.transcription
                if timestamp > self.context.publish_snippet_time
            ]
            event_type = EventType.SPEECH_ENDED
        else:
            word_timestamps = [
                (word, timestamp)
                for word, timestamp in self.context.transcription
                if self.context.publish_snippet_time <= timestamp <= current_time
            ]
            event_type = EventType.TTS_STREAMING_RESPONSE
            self.context.publish_snippet_time = current_time

        context_update = {
            'speech_type': SpeechType.LLM,
            'original_text': self.context.original_text,
            'speech_finished': is_final,
            'word_timestamps': word_timestamps,
            'timestamps_supported': bool(self.context.transcription)
        }
        self.event.data['context'].update(context_update)

        self.event_bus.publish(Event(
            type=event_type,
            speaker_id=self.event.speaker_id,
            group_id=self.event.group_id,
            timestamp=time.time(),
            data=self.event.data
        ))

    def _play_audio(self) -> None:
        """Internal method to handle audio playback"""
        data = self.wf.readframes(self.CHUNK_SIZE)

        while data and self.playing:
            current_time = time.time()

            if current_time - self.context.last_publish_time > self.PUBLISH_INTERVAL:
                self.context.last_publish_time = current_time
                self._publish_snippet()

            self.stream.write(data)
            data = self.wf.readframes(self.CHUNK_SIZE)

        if self.playing:
            self.stop(True)

    def play(self, start_seconds: float = 0) -> float:
        """Start playing audio from specified position"""
        self.wf.setpos(int(start_seconds * self.wf.getframerate()))

        self.stream = self.pyaudio.open(
            format=self.pyaudio.get_format_from_width(self.wf.getsampwidth()),
            channels=self.wf.getnchannels(),
            rate=self.wf.getframerate(),
            output=True
        )

        self.context.start_time = time.time() - start_seconds
        self.playing = True
        self.thread = threading.Thread(target=self._play_audio)
        self.thread.start()

        return self.context.start_time

    def stop(self, interrupted: bool) -> float:
        """Stop audio playback"""
        if self.stream and self.thread and self.thread.is_alive():
            self.playing = False
            self.context.pause_position = time.time() - self.context.start_time

            self._publish_snippet(is_final=True)

            self.stream.stop_stream()
            self.stream.close()

            self.on_finished_callback(self.event, self.context.pause_position)

        return self.context.pause_position

    def resume(self) -> None:
        """Resume playback from last position"""
        self.play(self.context.pause_position)

    def close(self) -> None:
        """Clean up resources"""
        if self.playing:
            self.stop(False)
        self.pyaudio.terminate()

class AudioManager:
    """Manages multiple audio players across different groups and speakers"""
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.players: Dict[str, Dict[str, AudioPlayer]] = {}

    def add_player(self, event: Event, audio_data: bytes, transcription: List[Tuple[str, float]], original_text: str) -> AudioPlayer:
        """Create and store a new audio player"""
        context = AudioContext(
            original_text=original_text,
            transcription=transcription
        )

        player = AudioPlayer(
            audio_data=audio_data,
            event=event,
            context=context,
            event_bus=self.event_bus,
            on_finished_callback=self._on_player_finished
        )

        if event.group_id not in self.players:
            self.players[event.group_id] = {}

        self.players[event.group_id][event.speaker_id] = player
        return player

    def _on_player_finished(self, event: Event, stop_time: float) -> None:
        """Callback for when a player finishes"""
        if event.group_id in self.players and event.speaker_id in self.players[event.group_id]:
            del self.players[event.group_id][event.speaker_id]

            if not self.players[event.group_id]:
                del self.players[event.group_id]

    def play_player(self, event: Event) -> None:
        """Start playback for a specific player"""
        if event.group_id in self.players and event.speaker_id in self.players[event.group_id]:
            player = self.players[event.group_id][event.speaker_id]
            start_time = player.play()

            event.data['context'] = {'time_started': start_time}

            self.event_bus.publish(Event(
                type=EventType.SPEECH_STARTED,
                speaker_id=event.speaker_id,
                group_id=event.group_id,
                timestamp=time.time(),
                data=event.data
            ))

    def stop_player(self, event: Event) -> None:
        """Stop playback for a specific player"""
        if event.group_id in self.players and event.speaker_id in self.players[event.group_id]:
            self.players[event.group_id][event.speaker_id].stop(False)

    def close(self) -> None:
        """Clean up all players"""
        for group in list(self.players.keys()):
            for player in list(self.players[group].values()):
                player.close()
        self.players.clear()