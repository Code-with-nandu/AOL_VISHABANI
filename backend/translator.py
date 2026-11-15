from collections import OrderedDict
from logging import getLogger
from threading import Lock
from time import perf_counter
from typing import Any

logger = getLogger(__name__)

MODEL_NAME = "google/madlad400-3b-mt"
MAX_INPUT_LENGTH = 4000
SUPPORTED_TARGET_LANGUAGES = {
    "bn": "Bengali",
    "hi": "Hindi",
    "ta": "Tamil",
    "ml": "Malayalam",
    "kn": "Kannada",
    "or": "Odia",
    "mr": "Marathi",
}


class TranslationValidationError(ValueError):
    pass


class ModelUnavailable(RuntimeError):
    pass


def validate_translation(text: str, target_language: str) -> tuple[str, str]:
    if not isinstance(text, str) or not text.strip():
        raise TranslationValidationError("Text must not be empty.")
    if len(text) > MAX_INPUT_LENGTH:
        raise TranslationValidationError(f"Text must be at most {MAX_INPUT_LENGTH} characters.")
    if target_language not in SUPPORTED_TARGET_LANGUAGES:
        raise TranslationValidationError("Target language is not supported.")
    return text.strip(), target_language


class MADLADTranslator:
    def __init__(self, local_files_only: bool = False, cache_capacity: int = 256) -> None:
        self.model_name = MODEL_NAME
        self.local_files_only = local_files_only
        self.cache_capacity = cache_capacity
        self._model: Any = None
        self._tokenizer: Any = None
        self._torch: Any = None
        self._device = "cpu"
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self._cache_lock = Lock()
        self._cache: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._load_attempted = False
        self._load_error: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "model_loaded": self._model is not None,
            "model_error": self._load_error,
        }

    def _load_model(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if self._load_attempted:
                raise ModelUnavailable(self._unavailable_message())
            self._load_attempted = True
            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                self._torch = torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.float16 if self._device == "cuda" else torch.float32
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=self.local_files_only,
                )
                self._model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    torch_dtype=dtype,
                    local_files_only=self.local_files_only,
                ).to(self._device)
                self._model.eval()
            except Exception as exc:
                self._load_error = type(exc).__name__
                logger.exception("Unable to load required translation model %s", self.model_name)
                raise ModelUnavailable(self._unavailable_message()) from exc

    def _unavailable_message(self) -> str:
        return (
            f"Required model {self.model_name} is unavailable. Check the local model cache, "
            "installed dependencies, and available memory. No alternate model is configured."
        )

    def translate(self, text: str, target_language: str) -> tuple[str, float, bool]:
        cleaned_text, target_language = validate_translation(text, target_language)
        cache_key = (target_language, cleaned_text)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached, 0.0, True

        started = perf_counter()
        self._load_model()
        try:
            prompt = f"<2{target_language}> {cleaned_text}"
            with self._inference_lock, self._torch.inference_mode():
                inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)
                generated = self._model.generate(
                    **inputs,
                    max_new_tokens=512,
                    num_beams=1,
                    do_sample=False,
                )
                translated = self._tokenizer.decode(generated[0], skip_special_tokens=True).strip()
            if not translated:
                raise RuntimeError("MADLAD returned an empty translation.")
        except Exception as exc:
            logger.exception("MADLAD inference failed for target language %s", target_language)
            raise ModelUnavailable(
                f"Translation with {self.model_name} failed. No alternate model is configured."
            ) from exc

        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        with self._cache_lock:
            self._cache[cache_key] = translated
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_capacity:
                self._cache.popitem(last=False)
        logger.info("MADLAD translation completed target=%s latency_ms=%.2f", target_language, elapsed_ms)
        return translated, elapsed_ms, False