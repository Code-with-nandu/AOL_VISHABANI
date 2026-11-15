import asyncio
import logging
import os
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.speech_errors import SpeechUnavailable
from backend.speech_to_text import LocalSpeechToText
from backend.text_to_speech import LocalTextToSpeech
from backend.translator import MADLADTranslator, ModelUnavailable, TranslationValidationError, validate_translation

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("aol_live.api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
translator = MADLADTranslator(
    local_files_only=os.getenv("MADLAD_LOCAL_FILES_ONLY", "false").lower() == "true"
)
speech_to_text = LocalSpeechToText()
text_to_speech = LocalTextToSpeech()
translation_queue = asyncio.Semaphore(1)
MAX_AUDIO_BYTES = 20 * 1024 * 1024

app = FastAPI(title="AOL Live Multilingual Translator", version="1.0.0")


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    target_language: str = Field(min_length=2, max_length=2)


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_language: str = Field(min_length=2, max_length=2)


async def process_translation(payload: TranslationRequest) -> dict[str, Any]:
    try:
        text, target_language = validate_translation(payload.text, payload.target_language)
    except TranslationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    started = perf_counter()
    async with translation_queue:
        try:
            translated, model_latency_ms, cached = await run_in_threadpool(
                translator.translate,
                text,
                target_language,
            )
        except ModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "translation": translated,
        "target_language": target_language,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "model_latency_ms": model_latency_ms,
        "cached": cached,
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        **translator.status(),
        "speech_to_text": speech_to_text.status(),
        "text_to_speech": text_to_speech.status(),
    }


@app.post("/api/translate")
async def translate(payload: TranslationRequest) -> dict[str, Any]:
    return await process_translation(payload)


@app.post("/api/speech/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)) -> dict[str, Any]:
    if not audio.content_type or not (audio.content_type.startswith("audio/") or audio.content_type == "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Upload an audio recording.")
    contents = await audio.read(MAX_AUDIO_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=422, detail="The uploaded audio is empty.")
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio recordings must be 20 MB or smaller.")

    suffix = Path(audio.filename or "recording.webm").suffix.lower()
    if suffix not in {".webm", ".wav", ".ogg", ".mp3", ".m4a", ".mp4", ".flac"}:
        suffix = ".audio"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as recording:
            recording.write(contents)
            temp_path = Path(recording.name)
        return await run_in_threadpool(speech_to_text.transcribe, temp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SpeechUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        await audio.close()


@app.post("/api/speech/synthesize")
async def synthesize_speech(payload: SpeechSynthesisRequest) -> Response:
    try:
        audio = await run_in_threadpool(
            text_to_speech.synthesize,
            payload.text,
            payload.target_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SpeechUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/wav")


@app.websocket("/ws/translate")
async def translate_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                payload = TranslationRequest(**data)
                result = await process_translation(payload)
                await websocket.send_json({"type": "translation", **result})
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "status": exc.status_code, "message": exc.detail})
            except (TypeError, ValueError) as exc:
                await websocket.send_json({"type": "error", "status": 422, "message": str(exc)})
    except WebSocketDisconnect:
        logger.info("Translation WebSocket disconnected")


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/styles.css", include_in_schema=False)
async def styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
async def script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app.js", media_type="text/javascript")