# AOL Live Multilingual Translator

Art of Living — One World, One Language.

## Current capabilities

- First-run onboarding asks separately for Mother Tongue and most comfortable language. Preferences, interaction choice, and accessibility settings are saved in browser storage.
- The student dashboard and classroom screen are responsive, with light/dark mode and adjustable translation text. No classroom, transcript, or audio is fabricated; joining reports that no classroom service is configured.
- Voice onboarding records microphone audio and sends it only to the same-origin local STT endpoint. Manual selection stays available when recording or local recognition fails.
- `POST /api/translate` and `WS /ws/translate` use only `google/madlad400-3b-mt`. The model loads lazily once and is reused. Requests are queued, validated, timed, and cached in memory.
- `POST /api/speech/transcribe` uses optional local Faster-Whisper. `POST /api/speech/synthesize` uses optional local Piper voices. Each service is independent and returns a clear error until configured.

The model weights and speech assets are not bundled. The translation service reports a clear unavailable error until MADLAD can be loaded. A classroom provider and live audio delivery are not present, so the complete live speech pipeline is not implemented.

## Local setup

Use Python 3.11 or newer. Install PyTorch using the command appropriate for the machine's CPU or CUDA setup, then install the API and translation dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the application from the project root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The first supported translation request loads the configured Hugging Face model into local memory and may download its files into the Hugging Face cache. To require an existing cache and prohibit downloads, set `MADLAD_LOCAL_FILES_ONLY=true` before starting the server.

The 3B model requires substantial RAM/VRAM; CPU inference may be slow. The application does not fall back to another translation model. `GET /api/health` reports whether model loading has occurred. Translation target codes are `bn`, `hi`, `ta`, `ml`, `kn`, `or`, and `mr`.

### Optional speech services

Install the local STT/TTS packages when they are needed:

```powershell
python -m pip install -r requirements-speech.txt
```

Configure a Faster-Whisper model name or existing local model path. A model name may be downloaded into the local cache on first use; set a local path to keep setup offline. The onboarding microphone control records up to eight seconds or until the user taps Stop.

```powershell
$env:AOL_STT_MODEL = 'small'
$env:AOL_STT_DEVICE = 'cpu'
$env:AOL_STT_COMPUTE_TYPE = 'int8'
```

For Piper, provide local `.onnx` voice paths keyed by supported language code. Only configured voices are available; no voice is substituted.

```powershell
$env:AOL_PIPER_VOICES = '{"hi":"C:\\voices\\hi_IN-voice-medium.onnx","ta":"C:\\voices\\ta_IN-voice-medium.onnx"}'
```

Set these variables before starting Uvicorn. `GET /api/health` reports STT and TTS configuration. Supported speech target codes are `bn`, `hi`, `ta`, `ml`, `kn`, `or`, and `mr`.

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/translate -ContentType 'application/json' -Body '{"text":"Welcome to the session.","target_language":"hi"}'
```

Run the API, validation, and local-service configuration tests with:

```powershell
python -m unittest discover -s tests -v
```

## Limitations

- Actual STT and TTS inference has not been tested here because local Faster-Whisper/Piper packages and their model assets are not installed. Actual MADLAD inference has not been tested because PyTorch, Transformers, and the 3B model are not installed.
- The dashboard is not connected to a classroom/session provider. Play and volume controls remain unavailable until real audio delivery is integrated.
- No live transcript source or audio delivery is configured. Do not treat the interface as a tested end-to-end live translation system.
- English and Other remain onboarding choices, but are not supported translation targets; the translation API accepts only the seven configured model target codes.
- Preferences are stored per browser and device; there is no account synchronization or authentication.