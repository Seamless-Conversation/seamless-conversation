from gtts import gTTS
from io import BytesIO
import base64
from playsound import playsound
from io import BytesIO
from seamlessconv.event.eventbus import EventBus
from ..base_tts import BaseTTS

# This contains old code
# TODO Restructure and impliment

class GttsProvider(BaseTTS):
    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        pass

    def synthesize_speech(self, text):
        tts = gTTS(text=text, lang="en", slow=False, tld='us')
        audio_stream = BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        
        return audio_stream.getvalue()