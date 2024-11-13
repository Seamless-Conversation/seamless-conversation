from ..base import TTSProvider
import pyaudio
from io import BytesIO
from pydub import AudioSegment
import edge_tts
from threading import Thread

# This contains old code
# TODO Restructure and impliment

class EdgeTTSProvider(TTSProvider):
    def __init__(self):
        self.playing = True
        pass

    def stop_playing(self):
        self.playing = False

    def generate_audio(self, text):
        communicator = edge_tts.Communicate(text, "en-US-ChristopherNeural")
        audio_chunks = []

        pyaudio_instance = pyaudio.PyAudio()
        audio_stream = pyaudio_instance.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)

        for chunk in communicator.stream_sync():
            if chunk["type"] == "audio" and chunk["data"]:
                audio_chunks.append(chunk["data"])

        thread_play = Thread(target=self.play_audio_chunks, args=(audio_chunks, audio_stream))
        thread_play.start()

    def play_audio_chunks(self, chunks: list[bytes], stream: pyaudio.Stream) -> None:
        audio_segment =  AudioSegment.from_mp3(BytesIO(b''.join(chunks))).raw_data
        raw_data = audio_segment
        chunk_size = 1024

        for i in range(0, len(raw_data), chunk_size):
            if not self.playing:
                break
            stream.write(raw_data[i:i+chunk_size])
        stream.stop_stream()
        stream.close()