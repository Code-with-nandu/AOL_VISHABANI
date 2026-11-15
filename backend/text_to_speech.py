import json
import logging
import os
import tempfile
import wave
from pathlib import Path
from threading import Lock
from typing import Any

from backend.speech_errors import SpeechUnavailable
from backend.translator import SUPPORTED_TARGET_LANGUAGES

logger = logging.getLogger(__name__)


class LocalTextToSpeech:
    def __init__(self, voice_models: dict[str, str] | None = None) -> None:
        if voice_models is None:
            try:
                voice_models = json.loads(os.getenv("AOL_PIPER_VOICES", "{}"))
            except json.JSONDecodeError:
                voice_models = {}
        self.voice_models = voice_models
        self._voices: dict[str, Any] = {}
        self._lock = Lock()

    def status(self) -> dict[str, Any]:
        return {
            "configured_languages": sorted(
                language for language, path in self.voice_models.items() if Path(path).is_file()
            ),
            "loaded_languages": sorted(self._voices),
        }

    def synthesize(self, text: str, language: str) -> bytes:
        if not text.strip() or len(text) > 2000:
            raise ValueError("Speech text must contain 1 to 2000 characters.")
        if language not in SUPPORTED_TARGET_LANGUAGES:
            raise ValueError("Target language is not supported by the speech service.")
        model_path = self.voice_models.get(language)
        if not model_path or not Path(model_path).is_file():
            raise SpeechUnavailable(f"No local Piper voice is configured for {SUPPORTED_TARGET_LANGUAGES[language]}.")

        voice = self._load_voice(language, model_path)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
                temp_path = audio_file.name
            with wave.open(temp_path, "wb") as output:
                voice.synthesize_wav(text.strip(), output)
            return Path(temp_path).read_bytes()
        except Exception as exc:
            logger.exception("Local Piper synthesis failed for target language %s", language)
            raise SpeechUnavailable("The configured local Piper voice could not synthesize this text.") from exc
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _load_voice(self, language: str, model_path: str) -> Any:
        if language in self._voices:
            return self._voices[language]
        with self._lock:
            if language in self._voices:
                return self._voices[language]
            try:
                from piper import PiperVoice

                voice = PiperVoice.load(model_path)
            except Exception as exc:
                logger.exception("Unable to load configured Piper voice for language %s", language)
                raise SpeechUnavailable("The configured local Piper voice could not be loaded.") from exc
            self._voices[language] = voice
            return voice