import unittest

from backend.speech_errors import SpeechUnavailable
from backend.speech_to_text import LocalSpeechToText
from backend.text_to_speech import LocalTextToSpeech


class LocalSpeechServiceTests(unittest.TestCase):
    def test_unconfigured_stt_fails_explicitly(self) -> None:
        service = LocalSpeechToText(model_name=None)
        with self.assertRaisesRegex(SpeechUnavailable, "AOL_STT_MODEL"):
            service._load_model()

    def test_unconfigured_piper_voice_fails_explicitly(self) -> None:
        service = LocalTextToSpeech(voice_models={})
        with self.assertRaisesRegex(SpeechUnavailable, "No local Piper voice"):
            service.synthesize("Welcome", "hi")

    def test_unsupported_speech_target_is_rejected(self) -> None:
        service = LocalTextToSpeech(voice_models={})
        with self.assertRaisesRegex(ValueError, "not supported"):
            service.synthesize("Welcome", "en")


if __name__ == "__main__":
    unittest.main()