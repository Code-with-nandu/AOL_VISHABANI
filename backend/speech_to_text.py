import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

from backend.speech_errors import SpeechUnavailable

logger = logging.getLogger(__name__)


class LocalSpeechToText:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("AOL_STT_MODEL")
        self.device = os.getenv("AOL_STT_DEVICE", "auto")
        self.compute_type = os.getenv("AOL_STT_COMPUTE_TYPE", "int8")
        self._model: Any = None
        self._load_attempted = False
        self._load_lock = Lock()
        self._load_error: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.model_name),
            "model": self.model_name,
            "model_loaded": self._model is not None,
            "model_error": self._load_error,
        }

    def _load_model(self) -> None:
        if not self.model_name:
            raise SpeechUnavailable("Local STT is not configured. Set AOL_STT_MODEL to a Faster-Whisper model or local model path.")
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if self._load_attempted:
                raise SpeechUnavailable("The configured local STT model could not be loaded.")
            self._load_attempted = True
            try:
                from faster_whisper import WhisperModel

                download_root = os.getenv("AOL_STT_CACHE")
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=download_root,
                )
            except Exception as exc:
                self._load_error = type(exc).__name__
                logger.exception("Unable to load configured local STT model")
                raise SpeechUnavailable("The configured local STT model could not be loaded. Check its local files and dependencies.") from exc

    def transcribe(self, audio_path: Path) -> dict[str, Any]:
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise ValueError("The uploaded audio is empty or unavailable.")
        self._load_model()
        try:
            segments, info = self._model.transcribe(str(audio_path), beam_size=1, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            logger.exception("Local STT failed to process uploaded audio")
            raise SpeechUnavailable("Local speech recognition could not process this audio.") from exc
        return {
            "text": text,
            "detected_language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
        }