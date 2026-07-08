import os
import logging
from abc import ABC, abstractmethod

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

logger = logging.getLogger(__name__)

# Default edge-tts voices (same constants as voice_gen.py)
DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_RATE = "-5%"
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
    "general": "en-US-Studio-O",
}


class BaseTTSProvider(ABC):

    @abstractmethod
    async def generate(self, text: str, output_path: str,
                       voice: str = DEFAULT_VOICE,
                       rate: str = DEFAULT_RATE,
                       pitch: str = DEFAULT_PITCH) -> bool:
        ...

    @abstractmethod
    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH) -> list[dict]:
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
                       pitch: str = DEFAULT_PITCH) -> bool:
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
                              pitch: str = DEFAULT_PITCH) -> list[dict]:
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
                       pitch: str = DEFAULT_PITCH) -> bool:
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

            with open(output_path, "wb") as f:
                f.write(response.audio_content)

            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception as e:
            logger.error("Google TTS generate error: %s", e)
            return False

    async def generate_timing(self, text: str,
                              voice: str = DEFAULT_VOICE,
                              rate: str = DEFAULT_RATE,
                              pitch: str = DEFAULT_PITCH) -> list[dict]:
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


_PROVIDER_INSTANCE = None


def get_tts_provider(name: str | None = None) -> BaseTTSProvider:
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    if name is None:
        name = os.getenv("VOICE_PROVIDER", "edge")

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
