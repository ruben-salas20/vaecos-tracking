"""Tests del validador IA + integración con el runner.

Mockea la llamada HTTP a MiniMax para no depender de la API real.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v0.4"))

from app.effi_guides.address_ai_validator import (  # noqa: E402
    AIValidationResult,
    MiniMaxAddressValidator,
)
from app.effi_guides.address_validator import (  # noqa: E402
    AddressResult,
    AddressValidation,
)


class MiniMaxValidatorParsingTest(unittest.TestCase):
    """El parser tolera JSON con texto extra, mayúsculas/minúsculas, etc."""

    def _validator(self):
        return MiniMaxAddressValidator(api_key="test-key")

    def test_response_json_valid(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value='{"status": "valid", "reason": "centro comercial identificable"}'):
            r = v.evaluate("sentro comercial santa clara")
        self.assertIsNotNone(r)
        self.assertEqual(r.status, AddressValidation.VALID)
        self.assertIn("centro", r.reason.lower())

    def test_response_json_review(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value='{"status": "review", "reason": "lugar ambiguo"}'):
            r = v.evaluate("La Promesa de la Democracia")
        self.assertEqual(r.status, AddressValidation.REVIEW)

    def test_response_json_invalid(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value='{"status": "invalid", "reason": "demasiado vaga"}'):
            r = v.evaluate("por ahi")
        self.assertEqual(r.status, AddressValidation.INVALID)

    def test_response_with_extra_text_around_json(self):
        v = self._validator()
        # Algunos modelos envuelven la respuesta con markdown o texto.
        msg = 'Aquí va el JSON:\n```json\n{"status": "valid", "reason": "tiene zona y avenida"}\n```'
        with patch.object(v, "_call_api", return_value=msg):
            r = v.evaluate("test")
        self.assertIsNotNone(r)
        self.assertEqual(r.status, AddressValidation.VALID)

    def test_response_with_invalid_json_returns_none(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value="esto no es JSON para nada"):
            r = v.evaluate("test")
        self.assertIsNone(r)

    def test_response_with_unknown_status_returns_none(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value='{"status": "maybe", "reason": "x"}'):
            r = v.evaluate("test")
        self.assertIsNone(r)

    def test_api_exception_propagates_none(self):
        v = self._validator()
        with patch.object(v, "_call_api", side_effect=Exception("network down")):
            r = v.evaluate("test")
        self.assertIsNone(r)

    def test_empty_address_returns_none(self):
        v = self._validator()
        self.assertIsNone(v.evaluate(""))
        self.assertIsNone(v.evaluate(None))
        self.assertIsNone(v.evaluate("   "))

    def test_cache_hits_avoid_second_api_call(self):
        v = self._validator()
        with patch.object(v, "_call_api", return_value='{"status": "valid", "reason": "ok"}') as mock_call:
            v.evaluate("zona 1 ciudad de guatemala")
            v.evaluate("zona 1 ciudad de guatemala")
            v.evaluate("Zona 1 Ciudad De Guatemala")  # variante de mayúsculas
            self.assertEqual(mock_call.call_count, 1)


class MergeIntoRegexResultTest(unittest.TestCase):
    """El veredicto IA preserva los patterns del regex y agrega su razón."""

    def test_ai_upgrade_to_valid(self):
        regex_result = AddressResult(
            status=AddressValidation.REVIEW,
            matched_patterns=(),
            reasons=("ubicación nominal sin landmark claro",),
            normalized="x",
        )
        ai = AIValidationResult(
            status=AddressValidation.VALID,
            reason="centro comercial identificable",
            raw_response="…",
            model="MiniMax-Text-01",
        )
        merged = ai.merge_into(regex_result)
        self.assertEqual(merged.status, AddressValidation.VALID)
        self.assertIn("[IA] centro comercial identificable", merged.reasons)
        # Preserva razón del regex.
        self.assertIn("ubicación nominal sin landmark claro", merged.reasons)


if __name__ == "__main__":
    unittest.main()
