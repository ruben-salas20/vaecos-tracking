from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.app.config import DEFAULT_EXCLUDED_STATUSES
from vaecos_v02.providers.notion_provider import NotionProvider


def _fake_notion_page(
    page_id: str,
    nombre: str,
    guia: str,
    estado_novedad: str,
    transportista: str = "effi",
    fecha_ultimo_seguimiento: str | None = None,
):
    """Build a fake Notion page dict in the shape returned by the API."""
    page: dict = {
        "id": page_id,
        "properties": {
            "Nombre": {"title": [{"plain_text": nombre}]},
            "No. Guía": {"rich_text": [{"plain_text": guia}]},
            "Estado novedad": {"select": {"name": estado_novedad}},
            "Transportista": {"select": {"name": transportista}},
        },
    }
    if fecha_ultimo_seguimiento is not None:
        page["properties"]["Fecha \u00faltimo seguimiento"] = {
            "date": {"start": fecha_ultimo_seguimiento}
        }
    return page


class NotionExclusionTestCase(unittest.TestCase):
    """Tests that the exclusion configuration and provider filtering work as expected."""

    # ------------------------------------------------------------------
    # 3.1a — Config assertion: PENDIENTE EFFI must be excluded by default
    # ------------------------------------------------------------------
    def test_pendiente_effi_in_default_excluded_statuses(self) -> None:
        """RED: PENDIENTE EFFI is not yet in DEFAULT_EXCLUDED_STATUSES.

        After adding it, this test asserts it IS present.
        """
        self.assertIn(
            "PENDIENTE EFFI",
            DEFAULT_EXCLUDED_STATUSES,
            "PENDIENTE EFFI debe estar en DEFAULT_EXCLUDED_STATUSES",
        )

    def test_previous_exclusions_remain(self) -> None:
        """Verify that previously excluded statuses are still excluded."""
        expected = {
            "ENTREGADA",
            "Indemnización",
            "Solicitud devolución",
            "En Devolución",
            "PENDIENTE CLIENTE",
            "Pendiente Indemnización",
            "PENDIENTE EFFI",
        }
        for status in expected:
            self.assertIn(status, DEFAULT_EXCLUDED_STATUSES)

    # ------------------------------------------------------------------
    # 3.1b — NotionProvider filtering behaviour (mocked API responses)
    # ------------------------------------------------------------------
    def test_active_fetch_excludes_pendiente_effi(self) -> None:
        """Mocked Notion returns a PENDIENTE EFFI page; it must be excluded."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        fake_results = [
            _fake_notion_page("p1", "Cliente A", "G001", "PENDIENTE EFFI"),
            _fake_notion_page("p2", "Cliente B", "G002", "En ruta"),
        ]
        fake_response = {"results": fake_results, "has_more": False}

        excluded = {"PENDIENTE EFFI", "ENTREGADA"}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, stats = provider.fetch_active_guides(excluded)

        # Only the non-excluded record should appear
        guias = [r.guia for r in records]
        self.assertNotIn("G001", guias, "PENDIENTE EFFI page should be excluded")
        self.assertIn("G002", guias, "En ruta page should be active")
        self.assertEqual(stats["excluded"], 1)

    def test_selected_fetch_excludes_pendiente_effi(self) -> None:
        """Mocked Notion returns a PENDIENTE EFFI page; selected fetch also excludes it."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        fake_results = [
            _fake_notion_page("p1", "Cliente A", "G001", "PENDIENTE EFFI"),
            _fake_notion_page("p2", "Cliente B", "G002", "En ruta"),
        ]
        fake_response = {"results": fake_results, "has_more": False}

        excluded = {"PENDIENTE EFFI", "ENTREGADA"}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, stats = provider.fetch_selected_guides(["G001", "G002"], excluded)

        guias = [r.guia for r in records]
        self.assertNotIn("G001", guias, "PENDIENTE EFFI page should be excluded")
        self.assertIn("G002", guias, "En ruta page should be matched")
        self.assertEqual(stats["excluded"], 1)

    def test_non_excluded_status_passes_through(self) -> None:
        """A page with a non-excluded status should appear in the result."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        fake_results = [
            _fake_notion_page("p1", "Cliente A", "G001", "En ruta"),
            _fake_notion_page("p2", "Cliente B", "G002", "Almacenado"),
        ]
        fake_response = {"results": fake_results, "has_more": False}

        excluded = {"PENDIENTE EFFI"}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, stats = provider.fetch_active_guides(excluded)

        guias = [r.guia for r in records]
        self.assertIn("G001", guias)
        self.assertIn("G002", guias)
        self.assertEqual(stats["excluded"], 0)


    # ------------------------------------------------------------------
    # 7.1 — Fecha último seguimiento parsing
    # ------------------------------------------------------------------
    def test_parse_record_includes_fecha_ultimo_seguimiento(self) -> None:
        """RED: _parse_record should extract 'Fecha último seguimiento' from the
        Notion page and expose it via NotionClientRecord."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        fake_results = [
            _fake_notion_page(
                "p1", "Cliente A", "G001", "Gestión novedad",
                fecha_ultimo_seguimiento="2026-04-28",
            ),
        ]
        fake_response = {"results": fake_results, "has_more": False}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, _ = provider.fetch_active_guides(set())

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].fecha_ultimo_seguimiento,
            "2026-04-28",
            "fecha_ultimo_seguimiento debe extraerse del campo date.start",
        )

    def test_parse_record_without_fecha_returns_none(self) -> None:
        """RED: when 'Fecha último seguimiento' is missing, fecha_ultimo_seguimiento
        should be None."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        fake_results = [
            _fake_notion_page("p1", "Cliente A", "G001", "Gestión novedad"),
            # No fecha_ultimo_seguimiento passed
        ]
        fake_response = {"results": fake_results, "has_more": False}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, _ = provider.fetch_active_guides(set())

        self.assertEqual(len(records), 1)
        self.assertIsNone(
            records[0].fecha_ultimo_seguimiento,
            "fecha_ultimo_seguimiento debe ser None si no existe en Notion",
        )

    def test_parse_record_with_null_date_returns_none(self) -> None:
        """Triangulate: when 'Fecha último seguimiento' exists but date.start is null,
        fecha_ultimo_seguimiento should be None (empty string → None)."""
        provider = NotionProvider(
            api_key="fake-key",
            notion_version="2025-09-03",
            data_source_id="fake-ds-id",
        )

        # Page that has the property but date object has no start value
        fake_page = {
            "id": "p-null",
            "properties": {
                "Nombre": {"title": [{"plain_text": "Cliente B"}]},
                "No. Guía": {"rich_text": [{"plain_text": "G002"}]},
                "Estado novedad": {"select": {"name": "Gestión novedad"}},
                "Transportista": {"select": {"name": "effi"}},
                "Fecha \u00faltimo seguimiento": {"date": None},
            },
        }
        fake_response = {"results": [fake_page], "has_more": False}

        with patch.object(provider, "_query_once", return_value=fake_response):
            records, _ = provider.fetch_active_guides(set())

        self.assertEqual(len(records), 1)
        self.assertIsNone(
            records[0].fecha_ultimo_seguimiento,
            "fecha_ultimo_seguimiento debe ser None cuando date es null",
        )


if __name__ == "__main__":
    unittest.main()
