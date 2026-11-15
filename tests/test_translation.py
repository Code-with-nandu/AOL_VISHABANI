import unittest
from unittest.mock import patch

from backend.translator import (
    MADLADTranslator,
    MODEL_NAME,
    ModelUnavailable,
    SUPPORTED_TARGET_LANGUAGES,
    TranslationValidationError,
    validate_translation,
)


class TranslationValidationTests(unittest.TestCase):
    def test_supported_target_languages_match_product_scope(self) -> None:
        self.assertEqual(
            set(SUPPORTED_TARGET_LANGUAGES),
            {"bn", "hi", "ta", "ml", "kn", "or", "mr"},
        )

    def test_valid_request_is_trimmed(self) -> None:
        self.assertEqual(validate_translation("  hello  ", "hi"), ("hello", "hi"))

    def test_empty_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationValidationError, "must not be empty"):
            validate_translation("  ", "hi")

    def test_oversized_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationValidationError, "4000 characters"):
            validate_translation("x" * 4001, "hi")

    def test_unsupported_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationValidationError, "not supported"):
            validate_translation("hello", "en")


class ModelAvailabilityTests(unittest.TestCase):
    def test_required_model_name_is_fixed(self) -> None:
        self.assertEqual(MADLADTranslator().model_name, "google/madlad400-3b-mt")
        self.assertEqual(MODEL_NAME, "google/madlad400-3b-mt")

    def test_model_load_failure_is_not_substituted(self) -> None:
        translator = MADLADTranslator()
        with patch.object(translator, "_load_model", side_effect=ModelUnavailable("required model missing")):
            with self.assertRaisesRegex(ModelUnavailable, "required model missing"):
                translator.translate("hello", "hi")


if __name__ == "__main__":
    unittest.main()