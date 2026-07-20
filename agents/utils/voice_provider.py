import os
import re
import logging
from abc import ABC, abstractmethod

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

logger = logging.getLogger(__name__)

# Default edge-tts voices (same constants as voice_gen.py)
DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_RATE = "-8%"
DEFAULT_PITCH = "-2Hz"

GOOGLE_VOICE_MAP = {
    "en-US-AriaNeural": {"name": "en-US-Studio-O", "language_code": "en-US"},
    "en-US-JennyNeural": {"name": "en-US-Studio-Q", "language_code": "en-US"},
    "en-GB-SoniaNeural": {"name": "en-GB-Studio-B", "language_code": "en-GB"},
    "en-US-Journey-F": {"name": "en-US-Journey-F", "language_code": "en-US"},
    "en-US-Neural2-J": {"name": "en-US-Neural2-J", "language_code": "en-US"},
    "en-US-Studio-O": {"name": "en-US-Studio-O", "language_code": "en-US"},
    "en-US-Studio-Q": {"name": "en-US-Studio-Q", "language_code": "en-US"},
}

VOICE_NAME_MAP = {
    "en-US-AriaNeural": "en-US-Studio-O",
    "en-US-JennyNeural": "en-US-Studio-Q",
    "en-GB-SoniaNeural": "en-GB-Studio-B",
}

CONTENT_TYPE_VOICES = {
    "educational": "en-US-Studio-Q",
    "storytelling": "en-US-Journey-F",
    "story": "en-GB-Studio-B",
    "energetic": "en-US-Neural2-J",
    "documentary": "en-US-Studio-Q",
    "general": "en-US-Studio-O",
}

KOKORO_VOICE_MAP = {
    "en-US-AriaNeural": "af_bella",
    "en-US-JennyNeural": "af_nicole",
    "en-GB-SoniaNeural": "af_heart",
    "en-US-Journey-F": "af_bella",
    "en-US-Neural2-J": "am_adam",
    "en-US-Studio-O": "af_bella",
    "en-US-Studio-Q": "af_nicole",
}

CONTENT_KOKORO_VOICES = {
    "educational": "af_bella",
    "storytelling": "af_bella",
    "story": "af_heart",
    "energetic": "am_adam",
    "general": "af_nicole",
}

DEFAULT_KOKORO_VOICE = "af_bella"
KOKORO_SAMPLE_RATE = 24000

_GOOGLE_EMPHASIS_WORDS = [
    "key", "important", "crucial", "critical", "essential", "fundamental",
    "never", "always", "must", "cannot", "extremely", "remarkably",
    "significantly", "dramatically", "revolutionary", "breakthrough",
]

_DEEP_LESSON_EMPHASIS = _GOOGLE_EMPHASIS_WORDS + [
    "intuitively", "imagine", "think about", "here.s the key", "notice that",
    "under the hood", "actually happening", "core idea", "beautiful",
    "elegant", "fascinating", "powerful", "transforms", "underlying",
    "precisely", "exactly", "every single", "each", "understands",
    "emerges", "remarkable", "secret", "hidden",
]


def _build_google_ssml(text: str, rate: str, is_deep_lesson: bool = False, is_documentary: bool = False) -> str:
    if is_documentary:
        emphasis_words = []
        sentence_pause = "750ms"
        clause_pause = "250ms"
    elif is_deep_lesson:
        emphasis_words = _DEEP_LESSON_EMPHASIS
        sentence_pause = "500ms"
        clause_pause = "200ms"
    else:
        emphasis_words = _GOOGLE_EMPHASIS_WORDS
        sentence_pause = "300ms"
        clause_pause = "100ms"
    for word in emphasis_words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub(lambda m: f'<emphasis level="strong">{m.group()}</emphasis>', text)
    text = re.sub(r'([.?!])\s+', rf'\1<break time="{sentence_pause}"/> ', text)
    text = re.sub(r'([,;:])\s', rf'\1<break time="{clause_pause}"/> ', text)
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
        f'<prosody rate="{rate}">{text}</prosody>'
        f'</speak>'
    )


class BaseTTSProvider(ABC):

    @abstractmethod
    async def generate(self, text: str, output_path: str,
                       voice: str = DEFAULT_VOICE,
                       rate: str = DEFAULT_RATE,
                       pitch: str = DEFAULT_PITCH,
                       is_deep_lesson: bool = False,
                       is_documentary: bool = False) -> bool:
        ...

    @abstractmethod
    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH,
                              is_deep_lesson: bool = False,
                              is_documentary: bool = False) -> list[dict]:
        ...

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class EdgeTTSProvider(BaseTTSProvider):

    def name(self) -> str:
        return "edge"

    def is_available(self) -> bool:
        return True

    async def generate(self, text: str, output_path: str,
                       voice: str = DEFAULT_VOICE,
                       rate: str = DEFAULT_RATE,
                       pitch: str = DEFAULT_PITCH,
                       is_deep_lesson: bool = False,
                       is_documentary: bool = False) -> bool:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception as e:
            logger.error("Edge TTS generate error: %s", e)
            return False

    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH,
                              is_deep_lesson: bool = False,
                              is_documentary: bool = False) -> list[dict]:
        sentence_times = []
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            async for chunk in communicate.stream():
                if chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                    sentence_times.append({
                        "text": chunk.get("text", ""),
                        "offset_ms": chunk.get("offset", 0) / 10000,
                        "duration_ms": chunk.get("duration", 0) / 10000,
                        "type": chunk["type"],
                    })
        except Exception as e:
            logger.error("Edge TTS timing error: %s", e)
        return sentence_times


class GoogleCloudTTSProvider(BaseTTSProvider):

    CLIENT = None

    def name(self) -> str:
        return "google"

    def is_available(self) -> bool:
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            return False
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def _get_client(self):
        if GoogleCloudTTSProvider.CLIENT is None:
            if texttospeech is None:
                logger.error("google-cloud-texttospeech not installed. Install with: pip install google-cloud-texttospeech")
                return None
            GoogleCloudTTSProvider.CLIENT = texttospeech.TextToSpeechClient()
        return GoogleCloudTTSProvider.CLIENT

    def _map_voice(self, voice: str) -> str:
        return VOICE_NAME_MAP.get(voice, CONTENT_TYPE_VOICES.get("general"))

    def _rate_to_speed(self, rate: str) -> float:
        rate = rate.replace("%", "").strip()
        multiplier = 1.0
        if rate.startswith("+"):
            multiplier = 1 + float(rate[1:]) / 100
        elif rate.startswith("-"):
            multiplier = 1 - float(rate[1:]) / 100
        else:
            multiplier = float(rate) / 100
        return round(multiplier, 2)

    def _pitch_to_semitones(self, pitch: str) -> float:
        pitch = pitch.replace("Hz", "").replace("st", "").strip()
        try:
            return float(pitch)
        except ValueError:
            return 0.0

    async def generate(self, text: str, output_path: str,
                       voice: str = DEFAULT_VOICE,
                       rate: str = DEFAULT_RATE,
                       pitch: str = DEFAULT_PITCH,
                       is_deep_lesson: bool = False,
                       is_documentary: bool = False) -> bool:
        try:
            client = self._get_client()
            voice_name = self._map_voice(voice)
            voice_info = GOOGLE_VOICE_MAP.get(voice_name, {"name": voice_name, "language_code": "en-US"})

            if is_documentary or is_deep_lesson:
                ssml = _build_google_ssml(text, rate, is_deep_lesson=is_deep_lesson, is_documentary=is_documentary)
                synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
            else:
                synthesis_input = texttospeech.SynthesisInput(text=text)

            voice_params = texttospeech.VoiceSelectionParams(
                language_code=voice_info["language_code"],
                name=voice_info["name"],
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=self._rate_to_speed(rate) if not is_deep_lesson else 1.0,
                pitch=self._pitch_to_semitones(pitch),
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )

            with open(output_path, "wb") as f:
                f.write(response.audio_content)

            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception as e:
            logger.error("Google TTS generate error: %s", e)
            return False

    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH,
                              is_deep_lesson: bool = False) -> list[dict]:
        try:
            client = self._get_client()
            voice_name = self._map_voice(voice)
            voice_info = GOOGLE_VOICE_MAP.get(voice_name, {"name": voice_name, "language_code": "en-US"})

            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice_params = texttospeech.VoiceSelectionParams(
                language_code=voice_info["language_code"],
                name=voice_info["name"],
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=self._rate_to_speed(rate),
                pitch=self._pitch_to_semitones(pitch),
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )

            total_bytes = len(response.audio_content)
            duration_sec = total_bytes / 48000.0
            duration_ms = duration_sec * 1000

            words = text.split()
            if not words:
                return []

            total_chars = sum(len(w) for w in words)
            sentence_times = []
            offset = 0.0

            for word in words:
                word_weight = len(word) / max(total_chars, 1)
                word_duration = duration_ms * word_weight
                sentence_times.append({
                    "text": word,
                    "offset_ms": int(offset),
                    "duration_ms": max(int(word_duration), 80),
                    "type": "WordBoundary",
                })
                offset += word_duration

            return sentence_times
        except Exception as e:
            logger.error("Google TTS timing error: %s", e)
            return []


class KokoroProvider(BaseTTSProvider):

    _pipeline = None

    def name(self) -> str:
        return "kokoro"

    def is_available(self) -> bool:
        import importlib.util
        return importlib.util.find_spec("kokoro") is not None

    def _get_pipeline(self):
        if KokoroProvider._pipeline is None:
            try:
                from kokoro import KPipeline
                repo_id = os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")
                KokoroProvider._pipeline = KPipeline(lang_code="a", repo_id=repo_id)
            except Exception as e:
                logger.error("Kokoro pipeline init error: %s", e)
                raise
        return KokoroProvider._pipeline

    def _map_voice(self, voice: str) -> str:
        mapped = KOKORO_VOICE_MAP.get(voice)
        if mapped:
            return mapped
        return CONTENT_KOKORO_VOICES.get(voice, os.getenv("KOKORO_VOICE", DEFAULT_KOKORO_VOICE))

    @staticmethod
    def _rate_to_speed(rate: str) -> float:
        rate = rate.replace("%", "").strip()
        if rate.startswith("+"):
            speed = 1 + float(rate[1:]) / 100
        elif rate.startswith("-"):
            speed = 1 - float(rate[1:]) / 100
        else:
            speed = float(rate) / 100
        return max(0.5, min(2.0, round(speed, 2)))

    async def generate(self, text: str, output_path: str,
                       voice: str = DEFAULT_VOICE,
                       rate: str = DEFAULT_RATE,
                       pitch: str = DEFAULT_PITCH,
                       is_deep_lesson: bool = False) -> bool:
        try:
            pipe = self._get_pipeline()
            speed = self._rate_to_speed(rate)
            voice_name = self._map_voice(voice)

            import torch
            gen = pipe(text, voice=voice_name, speed=speed)
            all_segments = []
            for _, _, audio in gen:
                all_segments.append(audio.cpu())
            if not all_segments:
                logger.warning("Kokoro generated no audio segments")
                return False

            combined = torch.cat(all_segments).float()
            audio_int16 = (combined * 32767).clamp(-32768, 32767).short()
            from pydub import AudioSegment
            seg = AudioSegment(
                audio_int16.numpy().tobytes(),
                frame_rate=KOKORO_SAMPLE_RATE,
                sample_width=2,
                channels=1,
            )
            seg.export(output_path, format="wav")
            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception as e:
            logger.error("Kokoro generate error: %s", e)
            return False

    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH,
                              is_deep_lesson: bool = False) -> list[dict]:
        events = await self._hybrid_timing(text, voice, rate, pitch)
        if events:
            return events
        return self._estimate_timing(text, rate)

    async def _hybrid_timing(self, text: str, voice: str,
                             rate: str, pitch: str) -> list[dict] | None:
        """Stream timing from edge-tts (metadata only, no audio download).

        Uses the original edge-tts voice name if available, otherwise falls
        back to a default. The voice for timing doesn't need to match Kokoro's
        — only reading speed and phrasing affect word boundaries.
        """
        try:
            import edge_tts
            if voice.startswith("en-") or voice.startswith("en-GB"):
                tts_voice = voice
            else:
                tts_voice = "en-US-AriaNeural"
            communicate = edge_tts.Communicate(text, voice=tts_voice, rate=rate, pitch=pitch)
            events = []
            async for chunk in communicate.stream():
                if chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                    events.append({
                        "text": chunk.get("text", ""),
                        "offset_ms": chunk.get("offset", 0) / 10000,
                        "duration_ms": chunk.get("duration", 0) / 10000,
                        "type": chunk["type"],
                    })
            return events if events else None
        except Exception as e:
            logger.debug("Kokoro hybrid timing unavailable, using estimation: %s", e)
            return None

    def _estimate_timing(self, text: str, rate: str) -> list[dict]:
        """Character-count proportional timing estimation."""
        words = text.split()
        if not words:
            return []

        speed = self._rate_to_speed(rate)
        total_chars = sum(len(w) for w in words)
        est_rate = 15.0 * speed
        total_duration_ms = (total_chars / max(est_rate, 1.0)) * 1000

        timings = []
        offset = 0.0
        for word in words:
            weight = len(word) / max(total_chars, 1)
            word_duration = total_duration_ms * weight
            timings.append({
                "text": word,
                "offset_ms": int(offset),
                "duration_ms": max(int(word_duration), 80),
                "type": "WordBoundary",
            })
            offset += word_duration

        return timings


_PROVIDER_INSTANCE = None


def get_tts_provider(name: str | None = None) -> BaseTTSProvider:
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    if name is None:
        name = os.getenv("VOICE_PROVIDER", "kokoro")

    if name == "kokoro":
        provider = KokoroProvider()
        if provider.is_available():
            logger.info("Using Kokoro TTS provider (local, no API key needed)")
            _PROVIDER_INSTANCE = provider
            return provider
        logger.warning("Kokoro not available, falling back to edge-tts")

    if name == "google":
        provider = GoogleCloudTTSProvider()
        if provider.is_available():
            logger.info("Using Google Cloud TTS provider")
            _PROVIDER_INSTANCE = provider
            return provider
        logger.warning("Google TTS not available (credentials missing?), falling back to edge-tts")

    logger.info("Using Edge TTS provider")
    _PROVIDER_INSTANCE = EdgeTTSProvider()
    return _PROVIDER_INSTANCE
