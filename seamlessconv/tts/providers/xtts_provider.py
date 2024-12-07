from dataclasses import dataclass
import logging
import io
from pathlib import Path
from typing import List, Tuple, Optional
from scipy.signal import resample
import numpy as np
import torch
import scipy.io.wavfile as wav_io
from TTS.api import TTS
from seamlessconv.config.settings import XttsSettings
from seamlessconv.event.eventbus import EventBus
from ..base_tts import BaseTTS

logger = logging.getLogger(__name__)

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float

class XttsProvider(BaseTTS):
    def __init__(self, event_bus: EventBus, settings: XttsSettings):
        super().__init__(event_bus)
        self.settings = settings
        self.tts = self._initialize_tts()
        self.manager = self.tts.synthesizer.tts_model

    def _initialize_tts(self) -> TTS:
        logger.debug("Xtts model loading")
        try:
            tts = TTS(
                model_name=self.settings.model,
                vocoder_path=self.settings.vocoder_path
            )
            logger.debug("Xtts model has been loaded")
            return tts
        except Exception as e:
            logger.error("Failed to initialize TTS model: %s", e)
            raise

    def _generate_mel_and_attention(self, text: str) -> Tuple[torch.Tensor, np.ndarray]:
        """
        Generate mel spectrogram and attention weights for input text.
        
        Args:
            text: Input text to synthesize
            
        Returns:
            Tuple of (mel_outputs, attention_weights)
        """
        inputs = self.manager.tokenizer.text_to_ids(text)
        inputs = torch.LongTensor(inputs).unsqueeze(0)

        with torch.no_grad():
            outputs = self.manager.inference(inputs)
            mel_outputs = outputs["model_outputs"][0].transpose(0, 1)
            attention_weights = outputs["alignments"][0].cpu().numpy()

        return mel_outputs, attention_weights

    def _generate_audio(self, mel_outputs: torch.Tensor) -> Tuple[np.ndarray, float]:
        """
        Generate audio from mel spectrogram with proper scaling.
        
        Args:
            mel_outputs: Mel spectrogram tensor
            
        Returns:
            Tuple of (audio_wave, duration)
        """
        mel_tensor = torch.FloatTensor(mel_outputs).unsqueeze(0)
        wav = self.tts.synthesizer.vocoder_model.inference(mel_tensor)
        wav = wav.squeeze().cpu().numpy()


        # Scale to 16-bit integer range
        # This needs to be converted to whatever smaplerate the config tells it
        wav = wav * 32767 # TEMPORARY SOLUTION

        if self.settings.sample_rate != self.tts.synthesizer.output_sample_rate:
            wav = self._resample_wav(wav, self.settings.sample_rate)

        duration = len(wav) / self.settings.sample_rate

        return wav, duration


    def _resample_wav(self, wav, target_sample_rate):
        num_samples = int(len(wav)*target_sample_rate/self.tts.synthesizer.output_sample_rate)
        wav_resampled = resample(wav, num_samples)

        return wav_resampled

    def _extract_word_timestamps(
        self,
        words: List[str],
        attention_weights: np.ndarray,
        audio_duration: float,
        n_mel_frames: int
    ) -> List[WordTimestamp]:
        """
        Extract word timestamps from attention weights.
        
        Args:
            words: List of words from input text
            attention_weights: Attention weights from model
            audio_duration: Total duration of audio
            n_mel_frames: Number of mel spectrogram frames
            
        Returns:
            List of WordTimestamp objects
        """
        time_per_frame = audio_duration / n_mel_frames
        current_pos = 0
        timestamps = []

        for word in words:
            word_length = len(self.manager.tokenizer.text_to_ids(word))
            word_end = current_pos + word_length

            word_attention = attention_weights[current_pos:word_end]
            summed_attention = word_attention.sum(axis=0)

            # Dynamic thresholding
            threshold = summed_attention.mean() + summed_attention.std()
            significant_frames = np.where(summed_attention > threshold)[0]

            if len(significant_frames) > 0:
                start_time = significant_frames[0] * time_per_frame
                end_time = significant_frames[-1] * time_per_frame
                timestamps.append(WordTimestamp(word, start_time, end_time))

            current_pos = word_end + 1

        return self._post_process_timestamps(timestamps, audio_duration)

    def _post_process_timestamps(
        self,
        timestamps: List[WordTimestamp],
        audio_duration: float
    ) -> List[WordTimestamp]:
        """
        Post-process timestamps to ensure proper spacing and timing.
        
        Args:
            timestamps: List of initial word timestamps
            audio_duration: Total duration of audio
            
        Returns:
            List of processed WordTimestamp objects
        """
        if not timestamps:
            return []

        processed = []
        total_words = len(timestamps)

        for i, stamp in enumerate(timestamps):
            start = stamp.start
            end = stamp.end

            if i > 0:
                # Ensure start time is after previous end time
                start = max(start, processed[-1].end + self.settings.word_gap)

            if i < total_words - 1:
                # Adjust end time to not overlap with next word
                end = min(end, timestamps[i + 1].start - self.settings.word_gap)

            # Min duration
            if end - start < self.settings.min_word_duration:
                end = start + self.settings.min_word_duration

            processed.append(WordTimestamp(stamp.word, start, end))

        # Scale timestamps to match total audio duration
        if processed:
            final_end = processed[-1].end
            scaling_factor = audio_duration / final_end
            processed = [
                WordTimestamp(
                    stamp.word,
                    stamp.start * scaling_factor,
                    stamp.end * scaling_factor
                )
                for stamp in processed
            ]

        return processed

    def synthesize_speech(
        self,
        text: str,
        output_path: Optional[str] = None
    ) -> Tuple[bytes, List[Tuple[str, float]]]:
        try:
            # Generate mel spectrogram and attention weights
            mel_outputs, attention_weights = self._generate_mel_and_attention(text)

            # Generate audio
            wav, audio_duration = self._generate_audio(mel_outputs)

            # Extract word timestamps
            words = text.split()
            timestamps = self._extract_word_timestamps(
                words,
                attention_weights,
                audio_duration,
                mel_outputs.shape[0]
            )

            # This needs to be converted to whatever smaplerate the config tells it
            wav_int16 = wav.astype(np.int16) #TEMPORARY SOLUTION

            audio_stream = io.BytesIO()
            wav_io.write(
                audio_stream,
                self.settings.sample_rate,
                wav_int16
            )
            audio_stream.seek(0)
            audio_bytes = audio_stream.getvalue()

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                wav_io.write(
                    output_path,
                    self.settings.sample_rate,
                    wav_int16
                )
                logger.info("Audio saved to %s", output_path)

            timestamp_to_return = [(t.word, t.end) for t in timestamps]

            return audio_bytes, timestamp_to_return

        except Exception as e:
            logger.error("Error generating speech: %s", e)
            raise
