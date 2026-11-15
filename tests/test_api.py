import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.translator import MODEL_NAME


class TranslationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_reports_required_model(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model"], MODEL_NAME)
        self.assertFalse(response.json()["model_loaded"])
        self.assertFalse(response.json()["speech_to_text"]["configured"])
        self.assertEqual(response.json()["text_to_speech"]["configured_languages"], [])

    def test_invalid_target_is_rejected_without_loading_model(self) -> None:
        response = self.client.post(
            "/api/translate",
            json={"text": "hello", "target_language": "en"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("not supported", response.json()["detail"])

    def test_model_unavailable_returns_clear_service_error(self) -> None:
        response = self.client.post(
            "/api/translate",
            json={"text": "hello", "target_language": "hi"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn(MODEL_NAME, response.json()["detail"])
        self.assertIn("No alternate model", response.json()["detail"])

    def test_websocket_reports_invalid_target(self) -> None:
        with self.client.websocket_connect("/ws/translate") as websocket:
            websocket.send_json({"text": "hello", "target_language": "en"})
            response = websocket.receive_json()
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["status"], 422)

    def test_synthesis_without_local_voice_returns_service_error(self) -> None:
        response = self.client.post(
            "/api/speech/synthesize",
            json={"text": "Welcome", "target_language": "hi"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("No local Piper voice", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()