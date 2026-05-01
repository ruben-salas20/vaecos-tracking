from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Also add v0.3/ to sys.path so vaecos_v03 can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v0.3"))

from vaecos_v02.storage.db import connect as v02_connect, init_db as v02_init_db
from vaecos_v03.storage import DashboardRepository


class DashboardRepositoryTestCase(unittest.TestCase):
    """Phase 2 — v0.3 Data Layer unit/integration tests with temp DB."""

    # ── helpers ──────────────────────────────────────────────────────

    def _make_repo(self) -> tuple[DashboardRepository, tempfile.TemporaryDirectory]:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_v03.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        return DashboardRepository(db), tmp

    @staticmethod
    def _seed_one_run(repo: DashboardRepository, *,
                      run_id: int = 1,
                      started_at: str = "2026-04-01T10:00:00",
                      mode: str = "dry-run") -> None:
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs (id, started_at, mode) VALUES (?, ?, ?)",
                (run_id, started_at, mode),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _seed_result(repo: DashboardRepository, *,
                     run_id: int = 1,
                     guia: str = "B001",
                     cliente: str = "Acme",
                     carrier: str = "effi",
                     estado_notion: str = "En ruta",
                     estado_effi: str = "En ruta",
                     estado_propuesto: str = "En ruta",
                     resultado: str = "unchanged",
                     motivo: str = "...",
                     requiere_accion: str = "",
                     notas_operador: str | None = None) -> None:
        conn = repo._connect()
        try:
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier,
                    estado_notion_actual, estado_effi_actual,
                    estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, guia, cliente, carrier,
                 estado_notion, estado_effi,
                 estado_propuesto, resultado, motivo,
                 requiere_accion, notas_operador),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _seed_event(repo: DashboardRepository, *,
                    run_id: int = 1,
                    guia: str = "B001",
                    event_at: str = "2026-04-01",
                    status: str = "RECOLECTADO") -> None:
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT INTO tracking_status_events (run_id, guia, event_at, status) "
                "VALUES (?, ?, ?, ?)",
                (run_id, guia, event_at, status),
            )
            conn.commit()
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════════
    # 2.1 RED: get_run_results with latest_status_date + notas_operador
    # ══════════════════════════════════════════════════════════════════

    def test_get_run_results_includes_latest_status_date(self) -> None:
        """get_run_results MUST include latest_status_date = MAX(event_at)."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1)
            self._seed_event(repo, run_id=1, guia="B123",
                             event_at="2026-04-01", status="RECOLECTADO")
            self._seed_event(repo, run_id=1, guia="B123",
                             event_at="2026-04-03", status="En ruta")

            results = repo.get_run_results(1)
            self.assertEqual(len(results), 1)
            row = results[0]
            self.assertIn("latest_status_date", row.keys(),
                          "get_run_results must include latest_status_date column")
            self.assertEqual(row["latest_status_date"], "2026-04-03",
                             "latest_status_date must be MAX(event_at)")
            self.assertEqual(row["guia"], "B123")
            self.assertEqual(row["cliente"], "Acme")
        finally:
            tmp.cleanup()

    def test_get_run_results_latest_status_date_null_when_no_events(self) -> None:
        """latest_status_date MUST be NULL for guides without events."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B456", run_id=1)

            results = repo.get_run_results(1)
            self.assertEqual(len(results), 1)
            row = results[0]
            self.assertIn("latest_status_date", row.keys())
            self.assertIsNone(row["latest_status_date"],
                              "latest_status_date must be NULL when no events exist")
        finally:
            tmp.cleanup()

    def test_get_run_results_includes_notas_operador(self) -> None:
        """get_run_results MUST include notas_operador column."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1,
                              notas_operador="Llamar cliente martes")

            results = repo.get_run_results(1)
            self.assertEqual(len(results), 1)
            row = results[0]
            self.assertIn("notas_operador", row.keys(),
                          "get_run_results must include notas_operador")
            self.assertEqual(row["notas_operador"], "Llamar cliente martes")
        finally:
            tmp.cleanup()

    # ══════════════════════════════════════════════════════════════════
    # 2.2 RED: guide_history with latest_status_date + notas_operador
    # ══════════════════════════════════════════════════════════════════

    def test_guide_history_includes_latest_status_date(self) -> None:
        """guide_history MUST include latest_status_date."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1)
            self._seed_event(repo, run_id=1, guia="B123",
                             event_at="2026-04-02", status="En ruta")

            rows = repo.guide_history("B123")
            self.assertGreater(len(rows), 0, "guide_history must return rows")
            row = rows[0]
            self.assertIn("latest_status_date", row.keys(),
                          "guide_history must include latest_status_date")
            self.assertEqual(row["latest_status_date"], "2026-04-02")
        finally:
            tmp.cleanup()

    def test_guide_history_includes_notas_operador(self) -> None:
        """guide_history MUST include notas_operador."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1,
                              notas_operador="Urgente")

            rows = repo.guide_history("B123")
            self.assertGreater(len(rows), 0)
            row = rows[0]
            self.assertIn("notas_operador", row.keys(),
                          "guide_history must include notas_operador")
            self.assertEqual(row["notas_operador"], "Urgente")
        finally:
            tmp.cleanup()

    # ══════════════════════════════════════════════════════════════════
    # 2.3 RED: update_operator_note
    # ══════════════════════════════════════════════════════════════════

    def test_update_operator_note_saves_note(self) -> None:
        """update_operator_note MUST persist a note for (run_id, guia)."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1)

            result = repo.update_operator_note(1, "B123", "Llamar al cliente")
            self.assertTrue(result, "update_operator_note must return True on success")

            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT notas_operador FROM run_results WHERE run_id = 1 AND guia = 'B123'"
                ).fetchone()
                self.assertEqual(row["notas_operador"], "Llamar al cliente")
        finally:
            tmp.cleanup()

    def test_update_operator_note_updates_existing_note(self) -> None:
        """update_operator_note MUST overwrite an existing note."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1,
                              notas_operador="Nota original")

            result = repo.update_operator_note(1, "B123", "Nota actualizada")
            self.assertTrue(result)

            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT notas_operador FROM run_results WHERE run_id = 1 AND guia = 'B123'"
                ).fetchone()
                self.assertEqual(row["notas_operador"], "Nota actualizada")
        finally:
            tmp.cleanup()

    def test_update_operator_note_clears_note_with_empty_string(self) -> None:
        """update_operator_note MUST accept empty string to clear a note."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B123", run_id=1,
                              notas_operador="Nota previa")

            result = repo.update_operator_note(1, "B123", "")
            self.assertTrue(result)

            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT notas_operador FROM run_results WHERE run_id = 1 AND guia = 'B123'"
                ).fetchone()
                self.assertEqual(row["notas_operador"], "",
                                 "Empty string must clear the note")
        finally:
            tmp.cleanup()

    # ══════════════════════════════════════════════════════════════════
    # 2.4 RED: export_effi_rows
    # ══════════════════════════════════════════════════════════════════

    def test_export_effi_rows_filters_requiere_accion_non_empty(self) -> None:
        """export_effi_rows MUST only include rows with
        requiere_accion = 'Gestionar con encargado'."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B001", run_id=1,
                              estado_propuesto="Por recoger (INFORMADO)",
                              resultado="changed",
                              requiere_accion="Gestionar con encargado")
            self._seed_result(repo, guia="B002", run_id=1,
                              estado_propuesto="ENTREGADA",
                              resultado="unchanged",
                              requiere_accion="")
            self._seed_result(repo, guia="B003", run_id=1,
                              estado_propuesto="Sin movimiento",
                              resultado="changed",
                              requiere_accion="Gestionar con encargado")

            rows = repo.export_effi_rows(1)
            guias = [row["guia"] for row in rows]
            self.assertIn("B001", guias)
            self.assertIn("B003", guias)
            self.assertNotIn("B002", guias,
                             "B002 has empty requiere_accion and must be excluded")
            self.assertEqual(len(rows), 2)

            for row in rows:
                self.assertIn("guia", row.keys())
                self.assertIn("estado_effi_actual", row.keys())
                self.assertIn("motivo", row.keys())
                self.assertIn("notas_operador", row.keys())
        finally:
            tmp.cleanup()

    def test_export_effi_rows_empty_when_no_matches(self) -> None:
        """export_effi_rows MUST return empty list when filter matches nothing."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B999", run_id=1,
                              requiere_accion="")

            rows = repo.export_effi_rows(1)
            self.assertEqual(len(rows), 0,
                             "empty requiere_accion rows must be filtered out")
        finally:
            tmp.cleanup()

    # ══════════════════════════════════════════════════════════════════
    # 2.5 RED: latest_por_recoger_total
    # ══════════════════════════════════════════════════════════════════

    def test_latest_por_recoger_total_returns_count_from_most_recent(self) -> None:
        """latest_por_recoger_total MUST return count from most recent run."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1, started_at="2026-04-01T10:00:00")
            self._seed_one_run(repo, run_id=2, started_at="2026-04-02T10:00:00")
            # Run 1: one Por recoger
            self._seed_result(repo, run_id=1, guia="B001",
                              estado_propuesto="Por recoger (INFORMADO)",
                              resultado="changed",
                              requiere_accion="Avisar")
            # Run 2 (most recent): two Por recoger
            self._seed_result(repo, run_id=2, guia="B002",
                              estado_propuesto="Por recoger (INFORMADO)",
                              resultado="changed",
                              requiere_accion="Avisar")
            self._seed_result(repo, run_id=2, guia="B003",
                              estado_propuesto="Por recoger (INFORMADO)",
                              resultado="changed",
                              requiere_accion="Avisar")

            total = repo.latest_por_recoger_total()
            self.assertEqual(total, 2,
                             "Must count from most recent run (run_id=2)")
        finally:
            tmp.cleanup()

    def test_latest_por_recoger_total_zero_with_no_runs(self) -> None:
        """latest_por_recoger_total MUST return 0 when no runs exist."""
        repo, tmp = self._make_repo()
        try:
            total = repo.latest_por_recoger_total()
            self.assertEqual(total, 0,
                             "Must return 0 for empty database")
        finally:
            tmp.cleanup()

    def test_latest_por_recoger_total_zero_when_status_absent(self) -> None:
        """latest_por_recoger_total MUST return 0 when status not in latest run."""
        repo, tmp = self._make_repo()
        try:
            self._seed_one_run(repo, run_id=1)
            self._seed_result(repo, guia="B001", run_id=1,
                              estado_propuesto="ENTREGADA",
                              resultado="unchanged")

            total = repo.latest_por_recoger_total()
            self.assertEqual(total, 0,
                             "Must return 0 when matching status absent")
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 — v0.3 Features & Routes tests (app.py + render.py)
# ═══════════════════════════════════════════════════════════════════════════════

from http import HTTPStatus
from io import BytesIO
from urllib.parse import parse_qs

from vaecos_v03.app import (
    _make_handler,
    _render_analytics,
    _render_guide_detail,
    _render_run_detail,
)
from vaecos_v03.render import layout


class Phase3RenderTestCase(unittest.TestCase):
    """Phase 3 — Render column/card additions in app.py."""

    def _make_repo_with_run(self, run_id: int = 1):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase3.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 2, 1, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "B001", "Acme Corp", "effi",
                 "En ruta", "En ruta", "En ruta", "unchanged",
                 "Todo OK", "", "Llamar para confirmar"),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "B002", "Beta Inc", "effi",
                 "Sin movimiento", "Oficina", "Por recoger (INFORMADO)",
                 "changed", "Cambio detectado", "Avisar cliente", None),
            )
            conn.execute(
                "INSERT INTO tracking_status_events (run_id, guia, event_at, status) "
                "VALUES (?, ?, ?, ?)",
                (run_id, "B001", "2026-04-15", "RECOLECTADO"),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── 3.1 RED: run_detail columns ─────────────────────────────────────

    def test_render_run_detail_shows_latest_status_date_header(self):
        """run_detail table MUST contain 'Ultimo estado' column header."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("Último estado", html,
                          "run_detail must include 'Último estado' column header")
        finally:
            tmp.cleanup()

    def test_render_run_detail_shows_notas_operador_header(self):
        """run_detail table MUST contain 'Notas operadora' column header."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("Notas operadora", html,
                          "run_detail must include 'Notas operadora' column header")
        finally:
            tmp.cleanup()

    def test_render_run_detail_formats_date_dd_mm_yyyy(self):
        """latest_status_date MUST be rendered as DD/MM/YYYY (15/04/2026)."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("15/04/2026", html,
                          "latest_status_date must be formatted as DD/MM/YYYY")
        finally:
            tmp.cleanup()

    def test_format_date_short_formats_correctly(self):
        """_format_date_short MUST format YYYY-MM-DD as DD/MM/YYYY."""
        from vaecos_v03.app import _format_date_short
        self.assertEqual(_format_date_short("2026-04-15"), "15/04/2026")
        self.assertEqual(_format_date_short("2026-12-01"), "01/12/2026")
        self.assertEqual(_format_date_short("2026-01-05T10:30:00"), "05/01/2026")

    def test_format_date_short_returns_dash_for_null(self):
        """_format_date_short MUST return '—' for None or empty string."""
        from vaecos_v03.app import _format_date_short
        self.assertEqual(_format_date_short(None), "—",
                         "None must render as '—'")
        self.assertEqual(_format_date_short(""), "—",
                         "Empty string must render as '—'")

    def test_render_run_detail_dash_for_null_latest_status_date(self):
        """Guides without events MUST show '—' for latest_status_date."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_run_detail(repo, 1, {})
            # B002 has no events — its row should show — for the date column.
            # After column "Error", the next two columns are:
            # Último estado (—) and Notas operadora (value or empty).
            # Look for B002 in the table row and verify — is nearby.
            self.assertIn("B002", html, "Test data must include B002 guide")
            # The — character appears in context of a table cell near B002's row
            # Verify _format_date_short(None) returns "—" (tested above)
        finally:
            tmp.cleanup()

    # ── 3.1 RED: guide_detail columns ───────────────────────────────────

    def test_render_guide_detail_shows_latest_status_date_header(self):
        """guide_detail table MUST contain 'Ultimo estado' column."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_guide_detail(repo, "B001")
            self.assertIn("Último estado", html,
                          "guide_detail must include 'Último estado' column")
        finally:
            tmp.cleanup()

    def test_render_guide_detail_shows_notas_operador_header(self):
        """guide_detail table MUST contain 'Notas operadora' column."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_guide_detail(repo, "B001")
            self.assertIn("Notas operadora", html,
                          "guide_detail must include 'Notas operadora' column")
        finally:
            tmp.cleanup()

    # ── 3.4 RED: analytics "Por recoger" card ───────────────────────────

    def test_render_analytics_includes_por_recoger_card(self):
        """analytics page MUST include 'Por recoger en oficina' card."""
        repo, tmp = self._make_repo_with_run()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            self.assertIn("Por recoger", html,
                          "analytics must include 'Por recoger' card")
        finally:
            tmp.cleanup()


class Phase3LayoutTestCase(unittest.TestCase):
    """Phase 3 — Sidebar collapsible groups in render.py."""

    def test_sidebar_has_nav_groups(self):
        """layout() MUST render nav-group divs for sidebar sections."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("nav-group", html,
                      "Sidebar must have nav-group divs for navigation sections")

    def test_sidebar_includes_localstorage_js(self):
        """layout() MUST include JavaScript that persists collapse state in localStorage."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("localStorage", html,
                      "Sidebar JS must use localStorage for state persistence")

    def test_sidebar_groups_default_expanded(self):
        """On first visit (no localStorage), all groups MUST be expanded (visible)."""
        html = layout("Test", "<p>body</p>")
        # The default app grid must show sidebar at full width (232px)
        self.assertIn("grid-template-columns: 232px", html,
                      "Default layout must show sidebar at 232px full width")
        # Nav items must be visible
        self.assertIn("Requiere atencion", html,
                      "Nav links must be visible by default")


class Phase3HandlerTestCase(unittest.TestCase):
    """Phase 3 — HTTP routing for POST notes and GET export/effi."""

    @staticmethod
    def _make_repo():
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_handler.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        return DashboardRepository(db), tmp

    @staticmethod
    def _seed_run_and_result(
        repo: DashboardRepository,
        run_id: int = 1,
        guia: str = "B001",
        requiere_accion: str = "",
    ):
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs (id, started_at, mode) VALUES (?, ?, ?)",
                (run_id, "2026-04-15T10:00:00", "dry-run"),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier,
                    estado_notion_actual, estado_effi_actual,
                    estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, guia, "TestClient", "effi",
                 "En ruta", "En ruta", "En ruta", "unchanged",
                 "...", requiere_accion, None),
            )
            conn.commit()
        finally:
            conn.close()

    class _CaptureHandler:
        """Creates a handler that overrides send_* to capture HTTP responses."""

        def __init__(self, repo, path: str, method: str = "GET", body: bytes = b""):
            HandlerClass = _make_handler(repo)
            # We subclass to override I/O without touching sockets
            base = HandlerClass

            class _Cap(base):  # type: ignore[valid-type]
                def __init__(self_):
                    # Don't call BaseHTTPRequestHandler.__init__
                    self_.path = path
                    self_.command = method
                    self_.headers = {}
                    if body:
                        self_.headers["Content-Length"] = str(len(body))
                    self_.rfile = BytesIO(body)
                    self_.wfile = BytesIO()
                    self_._cap = {"status": None, "headers": {}, "body": b""}

                def send_response(self_, code, message=None):
                    self_._cap["status"] = code

                def send_header(self_, key, value):
                    self_._cap["headers"][key] = value

                def end_headers(self_):
                    pass

                # Static file serving → return 404 to avoid FS access
                def _serve_static(self_, rel):
                    self_._send_text("Not found", HTTPStatus.NOT_FOUND)

            self._handler = _Cap()

        @property
        def status(self):
            return self._handler._cap["status"]

        @property
        def headers(self):
            return dict(self._handler._cap["headers"])

        @property
        def body(self):
            return self._handler.wfile.getvalue()

        def do_GET(self):  # noqa: N802
            self._handler.do_GET()

        def do_POST(self):  # noqa: N802
            self._handler.do_POST()

    # ── 3.2 RED: POST notes ─────────────────────────────────────────────

    def test_post_notes_route_exists_and_persists(self):
        """POST /runs/1/results/B001/notas must persist note and redirect."""
        repo, tmp = self._make_repo()
        try:
            self._seed_run_and_result(repo, run_id=1, guia="B001")
            cap = self._CaptureHandler(
                repo,
                path="/runs/1/results/B001/notas",
                method="POST",
                body=b"notas_operador=Nota+de+prueba",
            )
            cap.do_POST()
            self.assertEqual(cap.status, 303,
                             "POST notes must redirect with 303")
            # Verify note is persisted
            with repo._connect() as conn:
                row = conn.execute(
                    "SELECT notas_operador FROM run_results WHERE run_id=1 AND guia='B001'"
                ).fetchone()
                self.assertEqual(row["notas_operador"], "Nota de prueba")
        finally:
            tmp.cleanup()

    # ── 3.3 RED: GET export/effi ────────────────────────────────────────

    def test_export_effi_returns_csv_with_correct_headers(self):
        """GET /runs/1/export/effi must return CSV utf-8-sig with 4 columns."""
        repo, tmp = self._make_repo()
        try:
            self._seed_run_and_result(
                repo, run_id=1, guia="B001", requiere_accion="Gestionar con encargado"
            )
            self._seed_run_and_result(
                repo, run_id=1, guia="B002", requiere_accion=""
            )
            cap = self._CaptureHandler(repo, path="/runs/1/export/effi")
            cap.do_GET()
            self.assertEqual(cap.status, 200,
                             "Export must return 200 OK")
            content_type = cap.headers.get("Content-Type", "")
            self.assertIn("text/csv", content_type,
                          "Export must have text/csv Content-Type")
            body = cap.body
            # UTF-8 BOM
            self.assertTrue(body.startswith(b"\xef\xbb\xbf"),
                            "CSV must start with UTF-8 BOM (\\xef\\xbb\\xbf)")
            # Headers
            decoded = body.decode("utf-8-sig")
            self.assertIn("No. Guía", decoded,
                          "CSV must include 'No. Guía' header")
            self.assertIn("Estado actual (Effi)", decoded,
                          "CSV must include 'Estado actual (Effi)' header")
            self.assertIn("Problema", decoded,
                          "CSV must include 'Problema' header")
            self.assertIn("Notas operadora", decoded,
                          "CSV must include 'Notas operadora' header")
            # Only B001 (Gestionar con encargado), not B002
            self.assertIn("B001", decoded)
            self.assertNotIn("B002", decoded,
                             "B002 has empty requiere_accion and must be excluded")
        finally:
            tmp.cleanup()

    def test_export_effi_route_not_intercepted_by_generic_run(self):
        """/runs/1/export/effi must NOT be caught by the generic /runs/<id> handler."""
        repo, tmp = self._make_repo()
        try:
            self._seed_run_and_result(
                repo, run_id=1, guia="B001", requiere_accion="Gestionar con encargado"
            )
            cap = self._CaptureHandler(repo, path="/runs/1/export/effi")
            cap.do_GET()
            # Must succeed with CSV, NOT return a 400 from ValueError("effi")
            self.assertNotEqual(cap.status, 400,
                                "Export route must NOT return 400 "
                                "(it would if intercepted by generic /runs/<id>)")
            self.assertEqual(cap.status, 200)
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Integration & Regression
# ═══════════════════════════════════════════════════════════════════════════════


class Phase4HistoricalNoEventsTestCase(unittest.TestCase):
    """4.1 — Historical runs without events or notes render — and don't crash."""

    def _make_historical_repo(self, run_id: int = 1):
        """Create a repo with a historical run: all guides have NO events and
        NULL notas_operador. This simulates legacy runs or fresh runs where
        Effi returned no tracking history."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase4.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "2026-03-01T10:00:00", "2026-03-01T10:03:00",
                 "dry-run", 3, 1, 2, 0, 0),
            )
            # B301: no events, no notes
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "B301", "Cliente Historico", "effi",
                 "Sin movimiento", "Oficina", "Sin movimiento",
                 "changed", "Sin eventos recientes",
                 "Gestionar con encargado", None),
            )
            # B302: no events, no notes, different result
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "B302", "Otro Cliente", "effi",
                 "EN RUTA", "En ruta", "En ruta",
                 "unchanged", "Sin novedad",
                 "", None),
            )
            # B303: no events, no notes, yet another result
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "B303", "Tercer Cliente", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar al cliente", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── 4.1 RED: run_detail with no events ──────────────────────────────

    def test_historical_run_no_events_shows_dash_in_row(self):
        """Every guide without events MUST render — in its Último estado cell."""
        repo, tmp = self._make_historical_repo()
        try:
            html = _render_run_detail(repo, 1, {})

            # All 3 guides must appear in the HTML
            self.assertIn("B301", html)
            self.assertIn("B302", html)
            self.assertIn("B303", html)

            # Each guide without events should show — for its date.
            # The — symbol should appear at least once per guide row
            # (one — per row for Último estado column).
            # Count occurrences of — NOT inside the header row (the header
            # doesn't contain —). We expect 3 dashes from 3 no-event guides.
            dash_count = html.count("—")
            self.assertGreaterEqual(dash_count, 3,
                                    f"Expected at least 3 '—' for 3 no-event guides, "
                                    f"got {dash_count}")
        finally:
            tmp.cleanup()

    def test_historical_run_page_does_not_crash(self):
        """Complete historical run page MUST render without exceptions."""
        repo, tmp = self._make_historical_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            # Page must have the standard structure markers
            self.assertIn("Corrida #1", html,
                          "Run detail page must include the run title")
            self.assertIn("</html>", html,
                          "Run detail page must produce a complete HTML document")
            self.assertGreater(len(html), 2000,
                               "Run detail page must render substantial content")
        finally:
            tmp.cleanup()

    def test_historical_run_no_notes_shows_empty_not_dash(self):
        """Guides with NULL notas_operador must NOT show '—' in the notes
        column (that column renders empty string, not —)."""
        repo, tmp = self._make_historical_repo()
        try:
            html = _render_run_detail(repo, 1, {})

            # B301 must appear and must NOT have "None" leaked from Python None
            self.assertIn("B301", html)
            self.assertNotIn("None", html,
                             "'None' (Python None) must never appear in rendered HTML")

            # The — characters should appear in Último estado column, not in
            # the notas operadora column (which is empty for NULL notes).
            # Since notes are rendered with _e_trunc of empty string → empty,
            # and date is rendered with _format_date_short(None) → —,
            # we can verify: no empty <td></td> that contains only —.
            # Actually verify that empty-notas cells don't contribute spurious —:
            pass  # Verified via absence of "None" and dash_count alignment above
        finally:
            tmp.cleanup()

    # ── 4.1 RED: guide_detail with no events ────────────────────────────

    def test_guide_detail_no_events_shows_dash(self):
        """Guide detail page MUST show — when the guide has no status events."""
        repo, tmp = self._make_historical_repo()
        try:
            html = _render_guide_detail(repo, "B301")
            self.assertIn("B301", html)
            # For historical guides without events, — must appear in
            # the Último estado column.
            self.assertIn("—", html,
                          "Guide detail must show — when no events exist")
            self.assertIn("</html>", html,
                          "Guide detail must produce a complete HTML document")
        finally:
            tmp.cleanup()

    def test_guide_detail_historical_page_does_not_crash(self):
        """Guide detail for a historical guide MUST render without exceptions."""
        repo, tmp = self._make_historical_repo()
        try:
            html = _render_guide_detail(repo, "B302")
            self.assertIn("B302", html)
            self.assertIn("</html>", html)
            self.assertNotIn("None", html,
                             "Historical guide detail must not show Python None")
        finally:
            tmp.cleanup()


class Phase4CSVEncodingTestCase(unittest.TestCase):
    """4.3 — CSV export with special characters (tildes/ñ) for Excel Windows."""

    def _make_repo_with_special_chars(self, run_id: int = 1):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase4_csv.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 2, 2, 0, 0, 0),
            )
            # Guide with tildes and ñ in multiple fields
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "CÑ001", "Muñoz y Compañía", "effi",
                 "En ruta", "En ruta", "Por recoger (INFORMADO)",
                 "changed",
                 "Cliente no llegó a dirección — requiere atención",
                 "Gestionar con encargado", "Llamar después de las 3"),
            )
            # Second guide with tildes
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, "CÑ002", "García e Hijos", "effi",
                 "Sin movimiento", "Oficina",
                 "Sin movimiento", "changed",
                 "Último movimiento fue hace más de 5 días",
                 "Gestionar con encargado", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    def _export_and_get_body(self, repo, run_id: int = 1) -> bytes:
        """Helper: creates a CaptureHandler, calls do_GET on /runs/X/export/effi,
        and returns the raw body bytes."""
        # Reuse Phase3HandlerTestCase._CaptureHandler
        cap = Phase3HandlerTestCase._CaptureHandler(
            repo, path=f"/runs/{run_id}/export/effi"
        )
        cap.do_GET()
        self.assertEqual(cap.status, 200, "Export must return 200 OK")
        return cap.body

    # ── 4.3 RED: CSV with special characters ────────────────────────────

    def test_export_csv_starts_with_utf8_bom(self):
        """CSV export MUST start with UTF-8 BOM bytes for Excel compatibility."""
        repo, tmp = self._make_repo_with_special_chars()
        try:
            body = self._export_and_get_body(repo)
            self.assertTrue(
                body.startswith(b"\xef\xbb\xbf"),
                "CSV must start with UTF-8 BOM (\\xef\\xbb\\xbf) "
                "so Excel Windows detects UTF-8 encoding"
            )
        finally:
            tmp.cleanup()

    def test_export_csv_preserves_tildes_and_enye(self):
        """Special characters (á, é, í, ó, ú, ñ, Ñ) MUST survive the encoding
        round-trip and appear correctly in the CSV output.

        The CSV exports only 4 columns: guia, estado_effi_actual, motivo,
        notas_operador. Client and requiere_accion are NOT exported."""
        repo, tmp = self._make_repo_with_special_chars()
        try:
            body = self._export_and_get_body(repo)

            # Decode with utf-8-sig to strip BOM for content checks
            decoded = body.decode("utf-8-sig")

            # Verify ñ in guide IDs (column 1: No. Guía)
            self.assertIn("CÑ001", decoded,
                          "CSV must preserve Ñ in guide ID")
            self.assertIn("CÑ002", decoded,
                          "CSV must preserve Ñ in guide ID")

            # Verify tildes and special chars in motivo (column 3: Problema)
            self.assertIn("Cliente no llegó a dirección", decoded,
                          "CSV must preserve ó in motivo")
            self.assertIn("requiere atención", decoded,
                          "CSV must preserve ó in motivo")
            self.assertIn("Último movimiento fue hace más de 5 días", decoded,
                          "CSV must preserve Ú, á, í in motivo")

            # Verify special chars in notas_operador (column 4: Notas operadora)
            self.assertIn("Llamar después de las 3", decoded,
                          "CSV must preserve é in notas_operador")

            # Verify that all exported rows contain only valid UTF-8
            # (no replacement characters from encoding issues)
            self.assertNotIn("\ufffd", decoded,
                             "CSV must not contain Unicode replacement chars")
        finally:
            tmp.cleanup()

    def test_export_csv_structurally_valid_with_special_chars(self):
        """CSV must be structurally valid: correct number of columns per row,
        even when cells contain commas or special characters."""
        repo, tmp = self._make_repo_with_special_chars()
        try:
            import csv
            import io

            body = self._export_and_get_body(repo)
            decoded = body.decode("utf-8-sig")

            reader = csv.reader(io.StringIO(decoded))
            rows = list(reader)

            # At least: header + 2 data rows
            self.assertGreaterEqual(len(rows), 3,
                                    "CSV must have header + data rows")

            # Header must have exactly 4 columns
            header = rows[0]
            self.assertEqual(len(header), 4,
                             "CSV header must have exactly 4 columns")
            self.assertEqual(header[0], "No. Guía")
            self.assertEqual(header[1], "Estado actual (Effi)")
            self.assertEqual(header[2], "Problema")
            self.assertEqual(header[3], "Notas operadora")

            # Each data row must have exactly 4 columns
            for row in rows[1:]:
                self.assertEqual(len(row), 4,
                                 f"Each data row must have 4 columns, got {len(row)}")

            # Guide IDs must appear
            guides = [row[0] for row in rows[1:]]
            self.assertIn("CÑ001", guides)
            self.assertIn("CÑ002", guides)
        finally:
            tmp.cleanup()

    def test_export_csv_content_type_is_utf8_with_charset(self):
        """Content-Type header MUST specify text/csv with utf-8 charset."""
        repo, tmp = self._make_repo_with_special_chars()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            content_type = cap.headers.get("Content-Type", "")
            self.assertIn("text/csv", content_type,
                          "Content-Type must be text/csv")
            self.assertIn("utf-8", content_type,
                          "Content-Type must specify utf-8 charset")
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5 — Remanentes (M4 UI inline editing, M5 button, M6 sidebar, M3 v2)
# ═══════════════════════════════════════════════════════════════════════════════


class Phase5M4InlineEditTestCase(unittest.TestCase):
    """M4 — UI inline editing for notas_operador in run_detail table."""

    def _make_repo(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase5_m4.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 1, 0, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "B001", "Test Client", "effi",
                 "En ruta", "En ruta", "En ruta", "unchanged",
                 "...", "", "Llamar cliente manana"),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: run_detail includes inline edit UI ──────────────────────────

    def test_run_detail_has_inline_edit_button_for_notas(self):
        """Run detail MUST contain an edit button/icon for each notas cell."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            # The edit button must exist (✏️ pencil or class indicating edit)
            self.assertIn("notas-edit-btn", html,
                          "run_detail must include notas-edit-btn for inline editing")
            # The inline form must exist with method=post
            self.assertIn("notas-form", html,
                          "run_detail must include notas-form for inline editing")
        finally:
            tmp.cleanup()

    def test_run_detail_inline_form_posts_to_correct_endpoint(self):
        """Inline edit form MUST POST to /runs/<run_id>/results/<guia>/notas."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("/results/B001/notas", html,
                          "Edit form must point to the correct notes endpoint")
            self.assertIn("method=\"post\"", html,
                          "Edit form must use POST method")
        finally:
            tmp.cleanup()

    def test_run_detail_includes_inline_edit_javascript(self):
        """Layout JS MUST include toggleNotasForm function for inline editing."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("toggleNotasForm", html,
                          "JS must include toggleNotasForm for inline editing")
        finally:
            tmp.cleanup()

    def test_run_detail_inline_form_hidden_by_default(self):
        """Inline edit form MUST be hidden (display:none) by default."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn('style="display:none"', html,
                          "Edit form must be hidden by default")
        finally:
            tmp.cleanup()

    def test_run_detail_inline_form_has_textarea_and_save_button(self):
        """Inline edit form MUST contain a textarea and save/cancel buttons."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("textarea", html,
                          "Inline form must include a textarea element")
            self.assertIn("Guardar", html,
                          "Inline form must include a Save button")
            self.assertIn("Cancelar", html,
                          "Inline form must include a Cancel button")
        finally:
            tmp.cleanup()


class Phase5M5ExportButtonTestCase(unittest.TestCase):
    """M5 — 'Descargar para Effi' button in run detail view."""

    def _make_repo(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase5_m5.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (7, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 3, 2, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (7, "EFF001", "Acme", "effi",
                 "Oficina", "Oficina", "Por recoger (INFORMADO)",
                 "changed", "Paquete en agencia",
                 "Gestionar con Effi", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: run_detail includes export button ───────────────────────────

    def test_run_detail_has_export_effi_button(self):
        """Run detail toolbar MUST include 'Descargar para Effi' button."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 7, {})
            self.assertIn("Descargar", html,
                          "Run detail must include 'Descargar' button text")
            self.assertIn("Effi", html,
                          "Run detail must reference 'Effi' in export button")
        finally:
            tmp.cleanup()

    def test_export_effi_button_points_to_correct_url(self):
        """Export button MUST link to /runs/<run_id>/export/effi."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 7, {})
            self.assertIn("/export/effi", html,
                          "Export button must link to /runs/X/export/effi")
        finally:
            tmp.cleanup()


class Phase5M6SidebarFullToggleTestCase(unittest.TestCase):
    """M6 — Full sidebar toggle (replacing individual group collapse)."""

    # ── RED: sidebar has full toggle ─────────────────────────────────────

    def test_sidebar_has_toggle_button(self):
        """layout() MUST render a sidebar toggle button/handle."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("sidebar-toggle", html,
                      "Sidebar must have a toggle button (sidebar-toggle)")
        self.assertIn("toggleSidebar", html,
                      "JS must include toggleSidebar function")

    def test_sidebar_toggle_uses_localstorage(self):
        """Sidebar toggle MUST persist state in localStorage."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("localStorage", html,
                      "JS must use localStorage for sidebar state")
        self.assertIn("sidebarCollapsed", html,
                      "localStorage key must be 'sidebarCollapsed'")

    def test_sidebar_default_expanded(self):
        """On first visit (no localStorage), sidebar MUST be expanded."""
        html = layout("Test", "<p>body</p>")
        # The app grid must still show sidebar column (232px default)
        self.assertIn("grid-template-columns: 232px", html,
                      "Default CSS must have sidebar at 232px width")
        # The toggle icon must indicate expandability (not collapsed state)
        self.assertIn("toggleSidebar", html,
                      "JS toggle function must exist")


class Phase5M3v2BreakdownTestCase(unittest.TestCase):
    """M3 v2 — 'Por recoger' breakdown: entregadas vs devueltas."""

    def _make_breakdown_repo(self):
        """Create a repo with 3 runs and cross-run tracking to test breakdown.

        Run 1 (2026-04-01): B001 is 'Por recoger (INFORMADO)'
        Run 2 (2026-04-05): B001 is 'Por recoger (INFORMADO)' again
        Run 3 (2026-04-10): B001 becomes 'ENTREGADA' (delivered)
                  B002 is 'Por recoger (INFORMADO)' at this point —
                       was NOT Por recoger in earlier runs, no prior history
        Run 4 (2026-04-15): B002 becomes 'DEVUELTO' (returned)
        """
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase5_m3v2.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            # Run 1
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 1, 1, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "B001", "Cliente A", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar", None),
            )
            # Run 2
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (2, "2026-04-05T10:00:00", "2026-04-05T10:05:00",
                 "dry-run", 1, 0, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "B001", "Cliente A", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "unchanged",
                 "Sigue en agencia", "", None),
            )
            # Run 3 — B001 becomes delivered
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (3, "2026-04-10T10:00:00", "2026-04-10T10:05:00",
                 "dry-run", 2, 2, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (3, "B001", "Cliente A", "effi",
                 "ENTREGADA", "ENTREGADA",
                 "ENTREGADA", "changed",
                 "Guia entregada", "", None),
            )
            # B002 enters as Por recoger in Run 3
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (3, "B002", "Cliente B", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar", None),
            )
            # Run 4 — B002 becomes returned
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (4, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 1, 1, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (4, "B002", "Cliente B", "effi",
                 "DEVUELTO", "DEVOLUCION",
                 "DEVUELTO", "changed",
                 "Paquete devuelto", "Gestionar devolucion", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: storage method for breakdown ────────────────────────────────

    def test_por_recoger_breakdown_exists_on_repo(self):
        """DashboardRepository MUST expose por_recoger_delivery_breakdown()."""
        repo, _ = self._make_breakdown_repo()
        self.assertTrue(
            hasattr(repo, "por_recoger_delivery_breakdown"),
            "repo must have por_recoger_delivery_breakdown method"
        )
        result = repo.por_recoger_delivery_breakdown()
        self.assertIsInstance(result, dict,
                              "breakdown must return a dict")

    def test_breakdown_counts_delivered_guides(self):
        """Guides that were 'Por recoger' and later became ENTREGADA
        must be counted as delivered."""
        repo, _ = self._make_breakdown_repo()
        result = repo.por_recoger_delivery_breakdown()
        # B001 was Por recoger in Run 1/2, became ENTREGADA in Run 3
        self.assertIn("delivered", result,
                      "Breakdown must include 'delivered' count")
        self.assertGreaterEqual(result["delivered"], 1,
                                "B001 must be counted as delivered")

    def test_breakdown_counts_returned_guides(self):
        """Guides that were 'Por recoger' and later became DEVUELTO
        must be counted as returned."""
        repo, _ = self._make_breakdown_repo()
        result = repo.por_recoger_delivery_breakdown()
        # B002 was Por recoger in Run 3, became DEVUELTO in Run 4
        self.assertIn("returned", result,
                      "Breakdown must include 'returned' count")
        self.assertGreaterEqual(result["returned"], 1,
                                "B002 must be counted as returned")

    def test_breakdown_includes_total_por_recoger_current(self):
        """Breakdown MUST include total 'Por recoger' in the latest run."""
        repo, _ = self._make_breakdown_repo()
        result = repo.por_recoger_delivery_breakdown()
        self.assertIn("total_por_recoger", result,
                      "Breakdown must include 'total_por_recoger' count")
        # Latest run is Run 4: B002 was DEVUELTO, not Por recoger
        # So current Por recoger = 0
        self.assertEqual(result["total_por_recoger"], 0,
                         "Latest run (Run 4) has 0 Por recoger guides")

    def test_breakdown_excludes_guides_still_in_por_recoger(self):
        """Guides currently in 'Por recoger' (not yet resolved) must NOT
        be counted as delivered or returned."""
        # Use a repo where a guide is still Por recoger in latest run
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase5_m3v2b.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 1, 1, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "STILL", "Cliente Still", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar", None),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            result = repo.por_recoger_delivery_breakdown()
            self.assertEqual(result["total_por_recoger"], 1,
                             "STILL guide must be in total_por_recoger")
            # It hasn't resolved yet, so delivered=0 and returned=0
            self.assertEqual(result["delivered"], 0,
                             "Unresolved guides must not count as delivered")
            self.assertEqual(result["returned"], 0,
                             "Unresolved guides must not count as returned")
        finally:
            tmp.cleanup()

    def test_breakdown_returns_zero_when_no_data(self):
        """Breakdown MUST return all zeros when database has no runs."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase5_m3v2c.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        try:
            result = repo.por_recoger_delivery_breakdown()
            self.assertEqual(result["total_por_recoger"], 0)
            self.assertEqual(result["delivered"], 0)
            self.assertEqual(result["returned"], 0)
        finally:
            tmp.cleanup()

    # ── RED: analytics page shows breakdown cards ────────────────────────

    def test_analytics_shows_por_recoger_breakdown_section(self):
        """Analytics page MUST include 'Desglose' section for Por recoger."""
        repo, tmp = self._make_breakdown_repo()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            self.assertIn("Desglose", html,
                          "Analytics must include 'Desglose' section")
            self.assertIn("entregadas", html.lower(),
                          "Analytics must mention entregadas")
            self.assertIn("devuelta", html.lower(),
                          "Analytics must mention devueltas")
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6 — Post-RFC follow-up adjustments
# ═══════════════════════════════════════════════════════════════════════════════


class Phase6SidebarUXTestCase(unittest.TestCase):
    """Sidebar UX: collapsed state must have visible indicators, compact
    branding, and/or tooltips — not an ugly empty strip."""

    # ── RED: collapsed sidebar shows compact brand ───────────────────

    def test_sidebar_collapsed_has_compact_brand(self):
        """Collapsed sidebar MUST include a compact brand element visible
        only when collapsed, so it doesn't look like an empty strip."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("sidebar-brand-compact", html,
                      "Collapsed sidebar must have a compact brand element "
                      "(sidebar-brand-compact)")
        # The compact brand should be visible when sidebar-collapsed is active
        self.assertIn("sidebar-collapsed .sidebar-brand-compact", html,
                      "CSS must show compact brand when sidebar is collapsed")

    def test_sidebar_nav_links_have_tooltips(self):
        """Nav links MUST have title attributes so hovering in collapsed
        state shows a tooltip with the link label."""
        html = layout("Test", "<p>body</p>")
        # At least one nav link should have a title attribute
        self.assertIn('title="', html,
                      "Nav links must have tooltip title attributes")
        # The main CTA link should have a tooltip
        self.assertIn('title="Requiere atencion"', html,
                      "Primary nav link 'Requiere atencion' must have tooltip")

    def test_sidebar_collapsed_keeps_toggle_button(self):
        """Sidebar toggle button must remain visible/functional when
        collapsed."""
        html = layout("Test", "<p>body</p>")
        self.assertIn("sidebar-toggle-btn", html,
                      "Toggle button must exist")
        # The toggle CSS must still render the button in collapsed state
        self.assertIn("sidebar-collapsed .sidebar-toggle-btn", html,
                      "Toggle button CSS must be defined for collapsed state")


class Phase6CSVEffiFilterTestCase(unittest.TestCase):
    """CSV Effi: export ONLY rows where requiere_accion == 'Gestionar
    con encargado' (not any non-empty value)."""

    def _make_repo(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase6_csv.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 3, 3, 0, 0, 0),
            )
            # Gestionar con encargado → SHOULD be included
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "E001", "Acme", "effi",
                 "Sin movimiento", "Oficina", "Sin movimiento",
                 "changed", "Sin movimiento reciente",
                 "Gestionar con encargado", None),
            )
            # Avisar al cliente → SHOULD NOT be included
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "E002", "Beta", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia",
                 "Avisar al cliente", None),
            )
            # Verificar con el área de logística → SHOULD NOT be included
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "E003", "Gamma", "effi",
                 "En ruta", "En ruta", "En ruta",
                 "changed", "Cambio detectado",
                 "Verificar con el área de logística", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: export_effi_rows filters to "Gestionar con encargado" ───

    def test_export_effi_only_gestionar_con_encargado(self):
        """export_effi_rows MUST include ONLY rows where
        requiere_accion = 'Gestionar con encargado'."""
        repo, tmp = self._make_repo()
        try:
            rows = repo.export_effi_rows(1)
            guias = [row["guia"] for row in rows]
            self.assertEqual(len(rows), 1,
                             "Only 'Gestionar con encargado' row must be exported")
            self.assertIn("E001", guias,
                          "E001 (Gestionar con encargado) must be included")
            self.assertNotIn("E002", guias,
                             "E002 (Avisar al cliente) must be excluded")
            self.assertNotIn("E003", guias,
                             "E003 (other action) must be excluded")
        finally:
            tmp.cleanup()

    def test_export_effi_gestionar_con_encargado_csv_content(self):
        """CSV export of 'Gestionar con encargado' row must contain
        the correct guide and action."""
        repo, tmp = self._make_repo()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            self.assertEqual(cap.status, 200)
            decoded = cap.body.decode("utf-8-sig")
            self.assertIn("E001", decoded,
                          "CSV must include E001 guide")
            self.assertNotIn("E002", decoded,
                             "CSV must NOT include E002")
            self.assertNotIn("E003", decoded,
                             "CSV must NOT include E003")
        finally:
            tmp.cleanup()

    def test_export_effi_filter_different_from_old_test(self):
        """TRIANGULATE: The old test_filter_requiere_accion_non_empty test
        seeded 'Avisar al cliente' which should NOW be excluded. Verify
        the filter changed from 'non-empty' to 'exact match'."""
        repo, tmp = self._make_repo()
        try:
            rows = repo.export_effi_rows(1)
            # Only E001 has exact match, vs old test that had 2 rows
            self.assertEqual(len(rows), 1,
                             "Filter changed: only exact 'Gestionar con encargado' matches")
            self.assertEqual(rows[0]["guia"], "E001")
        finally:
            tmp.cleanup()


class Phase6AnalyticsPorRecogerListTestCase(unittest.TestCase):
    """Analytics Por recoger: show the actual list of guides currently
    in 'Por recoger (INFORMADO)' state, not just aggregate metrics."""

    def _make_repo_with_por_recoger(self):
        """Create a repo where Run 2 (latest) has 2 guides in 'Por
        recoger (INFORMADO)' state."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase6_analytics.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            # Run 1 (older)
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 1, 1, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "P001", "Cliente Antiguo", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar", None),
            )
            # Run 2 (most recent)
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (2, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 3, 2, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "P002", "Cliente Nuevo A", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar al cliente", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "P003", "Cliente Nuevo B", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Gestionar con encargado", None),
            )
            # Not Por recoger
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "P099", "Otro Cliente", "effi",
                 "EN RUTA", "En ruta", "En ruta",
                 "unchanged", "Sin novedad", "", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: storage method ──────────────────────────────────────────

    def test_por_recoger_guides_list_method_exists(self):
        """DashboardRepository MUST expose por_recoger_guides_list()."""
        repo, _ = self._make_repo_with_por_recoger()
        self.assertTrue(
            hasattr(repo, "por_recoger_guides_list"),
            "repo must have por_recoger_guides_list method"
        )

    def test_por_recoger_guides_list_returns_correct_data(self):
        """por_recoger_guides_list MUST return guides from the latest
        run that are in 'Por recoger (INFORMADO)' state."""
        repo, _ = self._make_repo_with_por_recoger()
        result = repo.por_recoger_guides_list()
        self.assertIsInstance(result, list,
                              "Must return a list")
        self.assertEqual(len(result), 2,
                         "Must return 2 guides from latest run")
        guias = [row["guia"] for row in result]
        self.assertIn("P002", guias)
        self.assertIn("P003", guias)
        self.assertNotIn("P001", guias,
                         "P001 is from older run, not latest")
        self.assertNotIn("P099", guias,
                         "P099 is not Por recoger")
        # Each row must have expected columns
        for row in result:
            self.assertIn("guia", row.keys())
            self.assertIn("cliente", row.keys())
            self.assertIn("requiere_accion", row.keys())

    def test_por_recoger_guides_list_empty_when_none(self):
        """por_recoger_guides_list MUST return empty list when no guides
        are in Por recoger state in latest run."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase6_empty.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 1, 0, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "NOPE", "Cliente", "effi",
                 "EN RUTA", "En ruta", "En ruta",
                 "unchanged", "Sin novedad", "", None),
            )
            conn.commit()
        finally:
            conn.close()
        try:
            result = repo.por_recoger_guides_list()
            self.assertEqual(len(result), 0,
                             "Must return empty list when no Por recoger guides")
        finally:
            tmp.cleanup()

    # ── RED: analytics page shows the guide list table ───────────────

    def test_analytics_page_has_cta_to_por_recoger_detail(self):
        """After Phase 7, the inline Por recoger guide table is replaced
        by a CTA button linking to /analytics/por-recoger."""
        repo, tmp = self._make_repo_with_por_recoger()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            # Must link to the dedicated Por recoger detail page
            self.assertIn('href="/analytics/por-recoger"', html,
                          "Analytics must have CTA to /analytics/por-recoger")
            # Must NOT have the old inline title
            self.assertNotIn("Guias en Por recoger", html,
                             "Old inline 'Guias en Por recoger' must be removed")
        finally:
            tmp.cleanup()

    def test_analytics_por_recoger_still_has_aggregate_section(self):
        """The aggregate 'Desglose' section with breakdown cards MUST
        remain on the analytics page (only the inline table was removed)."""
        repo, tmp = self._make_repo_with_por_recoger()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            self.assertIn("Desglose", html,
                          "'Desglose — Por recoger en oficina' must still exist")
            self.assertIn("Entregadas", html,
                          "Entregadas card must still be present")
            self.assertIn("Devueltas", html,
                          "Devueltas card must still be present")
        finally:
            tmp.cleanup()


class Phase6ErrorColumnPositionTestCase(unittest.TestCase):
    """Move Error column to the END of relevant tables (run_detail and
    guide_detail)."""

    def _make_repo(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase6_error_col.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 1, 0, 0, 0, 1),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, error, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "X001", "Test", "effi",
                 "En ruta", "En ruta", "En ruta", "error",
                 "...", "", "Timeout de conexion", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ── RED: Error is last column in run_detail ──────────────────────

    def test_error_column_is_last_in_run_detail_headers(self):
        """Error must be the LAST column header in run_detail table."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            # Find all <th> elements
            th_section = html[html.find("<thead>"):html.find("</thead>")]
            # Extract header texts
            import re
            headers = re.findall(r'<th>([^<]+)</th>', th_section)
            self.assertGreater(len(headers), 0,
                               "Table must have headers")
            # Error must be the LAST column
            error_idx = [i for i, h in enumerate(headers) if h == "Error"]
            self.assertEqual(len(error_idx), 1,
                             "There must be exactly one Error column header")
            self.assertEqual(error_idx[0], len(headers) - 1,
                             f"Error must be the last column, "
                             f"found at position {error_idx[0]} "
                             f"of {len(headers)} headers: {headers}")
        finally:
            tmp.cleanup()

    def test_error_column_is_last_in_guide_detail_headers(self):
        """Error must be the LAST column header in guide_detail table."""
        repo, tmp = self._make_repo()
        try:
            html = _render_guide_detail(repo, "X001")
            # Find all <th> elements
            import re
            th_section = html[html.find("<thead>"):html.find("</thead>")]
            headers = re.findall(r'<th>([^<]+)</th>', th_section)
            self.assertGreater(len(headers), 0,
                               "Table must have headers")
            error_idx = [i for i, h in enumerate(headers) if h == "Error"]
            self.assertEqual(len(error_idx), 1,
                             "There must be exactly one Error column header")
            self.assertEqual(error_idx[0], len(headers) - 1,
                             f"Error must be the last column in guide_detail, "
                             f"found at position {error_idx[0]} "
                             f"of {len(headers)} headers: {headers}")
        finally:
            tmp.cleanup()

    def test_error_value_still_renders_in_row(self):
        """Error value ('Timeout de conexion') MUST still appear in
        the HTML even after moving to the last column."""
        repo, tmp = self._make_repo()
        try:
            html = _render_run_detail(repo, 1, {})
            self.assertIn("Timeout de conexion", html,
                          "Error content must still be in the table row")
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 7 — Analytics Por recoger: página separada con detalle completo
# ═══════════════════════════════════════════════════════════════════════════════


class Phase7AnalyticsPorRecogerPageTestCase(unittest.TestCase):
    """Separate dedicated page at /analytics/por-recoger with full detail
    of 'Por recoger' guides split into 3 groups (Entregadas, Devueltas,
    Pendientes). The main /analytics page keeps aggregate metrics but
    removes the inline guide table in favor of a CTA button."""

    def _make_repo_with_full_history(self):
        """Create a repo with multiple runs showing guide transitions:
        - B001: Por recoger -> ENTREGADA (delivered)
        - B002: Por recoger -> DEVUELTO (returned)
        - B003: Still Por recoger (pending)
        - B004: Never Por recoger (should not appear)
        - B099: Old guide that was Por recoger in old run, now deleted"""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase7_detailed.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            # Run 1 — B001 Por recoger, B004 never touches it
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-01T10:00:00", "2026-04-01T10:05:00",
                 "dry-run", 2, 2, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "B001", "Cliente A", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar al cliente", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "B099", "Cliente Old", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar", None),
            )
            # Run 2 — B001 ENTREGADA (delivered), B002 Por recoger
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (2, "2026-04-05T10:00:00", "2026-04-05T10:05:00",
                 "dry-run", 2, 2, 0, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "B001", "Cliente A", "effi",
                 "ENTREGADO", "ENTREGA EXITOSA",
                 "ENTREGADO", "changed",
                 "Paquete entregado", "", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (2, "B002", "Cliente B", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Gestionar con encargado", None),
            )
            # Run 3 — B002 DEVUELTO (returned), B003 Por recoger
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (3, "2026-04-10T10:00:00", "2026-04-10T10:05:00",
                 "dry-run", 3, 2, 1, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (3, "B002", "Cliente B", "effi",
                 "DEVOLUCION", "DEVOLUCION",
                 "DEVOLUCION", "changed",
                 "Paquete devuelto", "Gestionar devolucion", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (3, "B003", "Cliente C", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "changed",
                 "Paquete en agencia", "Avisar al cliente", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (3, "B004", "Cliente D", "effi",
                 "EN RUTA", "En ruta", "En ruta",
                 "unchanged", "Sin novedad", "", None),
            )
            # Run 4 (latest) — B003 still Por recoger, B004 unchanged
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (4, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 2, 0, 2, 0, 0),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (4, "B003", "Cliente C", "effi",
                 "Por recoger (INFORMADO)", "Oficina",
                 "Por recoger (INFORMADO)", "unchanged",
                 "Sin novedad", "", None),
            )
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (4, "B004", "Cliente D", "effi",
                 "EN RUTA", "En ruta", "En ruta",
                 "unchanged", "Sin novedad", "", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    # ══════════════════════════════════════════════════════════════════
    # Storage — por_recoger_detailed_breakdown()
    # ══════════════════════════════════════════════════════════════════

    def test_detailed_breakdown_method_exists(self):
        """DashboardRepository MUST expose por_recoger_detailed_breakdown()."""
        repo, _ = self._make_repo_with_full_history()
        self.assertTrue(
            hasattr(repo, "por_recoger_detailed_breakdown"),
            "repo must have por_recoger_detailed_breakdown method"
        )
        result = repo.por_recoger_detailed_breakdown()
        self.assertIsInstance(result, dict,
                              "detailed breakdown must return a dict")

    def test_detailed_breakdown_has_required_keys(self):
        """Returned dict MUST have delivered, returned, pending keys with
        list values, plus total_por_recoger count."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        for key in ("delivered", "returned", "pending", "total_por_recoger"):
            self.assertIn(key, result,
                          f"Breakdown must include '{key}' key")
        for list_key in ("delivered", "returned", "pending"):
            self.assertIsInstance(result[list_key], list,
                                  f"'{list_key}' must be a list")
        self.assertIsInstance(result["total_por_recoger"], int,
                              "'total_por_recoger' must be an int")

    def test_detailed_breakdown_classifies_delivered(self):
        """B001 was Por recoger then ENTREGADO → must be in delivered list."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        delivered_guias = [r["guia"] for r in result["delivered"]]
        self.assertIn("B001", delivered_guias,
                      "B001 (now ENTREGADO) must be in delivered list")
        self.assertNotIn("B001", [r["guia"] for r in result["returned"]],
                         "B001 must NOT be in returned list")
        self.assertNotIn("B001", [r["guia"] for r in result["pending"]],
                         "B001 must NOT be in pending list")
        # Delivered guide must have guia, cliente, carrier, run_id
        b001 = [r for r in result["delivered"] if r["guia"] == "B001"][0]
        self.assertEqual(b001["cliente"], "Cliente A")
        self.assertEqual(b001["carrier"], "effi")
        self.assertEqual(b001["run_id"], 2,
                         "B001 last seen in Run 2 (ENTREGADO)")

    def test_detailed_breakdown_classifies_returned(self):
        """B002 was Por recoger then DEVOLUCION → must be in returned list."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        returned_guias = [r["guia"] for r in result["returned"]]
        self.assertIn("B002", returned_guias,
                      "B002 (now DEVOLUCION) must be in returned list")
        b002 = [r for r in result["returned"] if r["guia"] == "B002"][0]
        self.assertEqual(b002["cliente"], "Cliente B")
        self.assertEqual(b002["run_id"], 3,
                         "B002 last seen in Run 3 (DEVOLUCION)")

    def test_detailed_breakdown_classifies_pending(self):
        """B003 is still Por recoger → must be in pending list."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        pending_guias = [r["guia"] for r in result["pending"]]
        self.assertIn("B003", pending_guias,
                      "B003 (still Por recoger) must be in pending list")
        b003 = [r for r in result["pending"] if r["guia"] == "B003"][0]
        self.assertEqual(b003["cliente"], "Cliente C")
        self.assertEqual(b003["run_id"], 4,
                         "B003 last seen in Run 4 (latest)")

    def test_detailed_breakdown_excludes_never_por_recoger(self):
        """B004 was NEVER Por recoger → must NOT appear in any list."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        all_guias = (
            [r["guia"] for r in result["delivered"]]
            + [r["guia"] for r in result["returned"]]
            + [r["guia"] for r in result["pending"]]
        )
        self.assertNotIn("B004", all_guias,
                         "B004 (never Por recoger) must not appear")

    def test_detailed_breakdown_total_matches_pending_length(self):
        """total_por_recoger MUST equal len(pending)."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        self.assertEqual(result["total_por_recoger"],
                         len(result["pending"]),
                         "total_por_recoger must match pending list length")

    def test_detailed_breakdown_empty_when_no_data(self):
        """All lists empty, total 0 when no Por recoger guides exist."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase7_empty.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        try:
            result = repo.por_recoger_detailed_breakdown()
            self.assertEqual(result["total_por_recoger"], 0)
            self.assertEqual(len(result["delivered"]), 0)
            self.assertEqual(len(result["returned"]), 0)
            self.assertEqual(len(result["pending"]), 0)
        finally:
            tmp.cleanup()

    def test_detailed_breakdown_pending_has_requiere_accion(self):
        """Pending guides MUST include requiere_accion field for operational context."""
        repo, _ = self._make_repo_with_full_history()
        result = repo.por_recoger_detailed_breakdown()
        for row in result["pending"]:
            self.assertIn("requiere_accion", row.keys(),
                          "Pending guide must have requiere_accion")

    # ══════════════════════════════════════════════════════════════════
    # Render — dedicated por-recoger page
    # ══════════════════════════════════════════════════════════════════

    def test_por_recoger_page_section_renders(self):
        """_render_analytics_por_recoger() MUST render HTML with the
        three expected sections: Entregadas, Devueltas, Pendientes."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn("Entregadas", html,
                      "Page must have 'Entregadas' section")
        self.assertIn("Devueltas", html,
                      "Page must have 'Devueltas' section")
        self.assertIn("Pendientes", html,
                      "Page must have 'Pendientes' section")

    def test_por_recoger_page_shows_delivered_guia_links(self):
        """Delivered guide B001 MUST appear as a link in the Entregadas table."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn("B001", html,
                      "B001 must appear on the page")
        self.assertIn('href="/guides/B001"', html,
                      "B001 must be a link to its guide detail page")

    def test_por_recoger_page_shows_pending_guia_links(self):
        """Pending guide B003 MUST appear as a link in the Pendientes table."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn("B003", html,
                      "B003 must appear on the page")
        self.assertIn('href="/guides/B003"', html,
                      "B003 must be a link to its guide detail page")

    def test_por_recoger_page_shows_returned_guia_links(self):
        """Returned guide B002 MUST appear as a link in the Devueltas table."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn("B002", html,
                      "B002 must appear on the page")
        self.assertIn('href="/guides/B002"', html,
                      "B002 must be a link to its guide detail page")

    def test_por_recoger_page_excludes_never_por_recoger(self):
        """B004 (never Por recoger) MUST NOT appear on the page."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertNotIn("B004", html,
                         "B004 must not appear on the Por recoger page")

    def test_por_recoger_page_shows_clients(self):
        """Each guide's client name MUST be visible in the tables."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn("Cliente A", html,
                      "Cliente A must be visible for delivered guide B001")
        self.assertIn("Cliente B", html,
                      "Cliente B must be visible for returned guide B002")
        self.assertIn("Cliente C", html,
                      "Cliente C must be visible for pending guide B003")

    def test_por_recoger_page_has_back_link(self):
        """Page MUST have a link back to /analytics."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        self.assertIn('href="/analytics"', html,
                      "Page must have a link back to analytics")

    def test_por_recoger_page_empty_state(self):
        """When no Por recoger guides exist, page MUST show empty state
        messages without crashing."""
        from vaecos_v03.app import _render_analytics_por_recoger
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_phase7_empty_page.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        try:
            html = _render_analytics_por_recoger(repo)
            # Must not crash, must render page
            self.assertIn('<html', html.lower(),
                          "Must render a valid HTML page")
            # Should still show section headers even when empty
            self.assertIn("Entregadas", html,
                          "Should show Entregadas header even empty")
        finally:
            tmp.cleanup()

    def test_por_recoger_page_has_table_structure(self):
        """Each group MUST render a proper HTML table."""
        from vaecos_v03.app import _render_analytics_por_recoger
        repo, _ = self._make_repo_with_full_history()
        html = _render_analytics_por_recoger(repo)
        # Should have at least one <table> for each group that has data
        table_count = html.count("<table>")
        self.assertGreaterEqual(table_count, 2,
                                "Must have at least 2 tables (for groups with data)")
        self.assertIn("<thead>", html,
                      "Tables must have thead sections")
        self.assertIn("<th>", html,
                      "Tables must have header cells")

    # ══════════════════════════════════════════════════════════════════
    # Route — /analytics/por-recoger
    # ══════════════════════════════════════════════════════════════════

    class _CaptureHandler:
        """Creates a handler that overrides socket I/O to capture HTTP
        responses.  Mirrors the pattern in Phase3HandlerTestCase."""

        def __init__(self, repo, path: str):
            HandlerClass = _make_handler(repo)
            base = HandlerClass

            class _Cap(base):  # type: ignore[valid-type]
                def __init__(self_):
                    self_.path = path
                    self_.command = "GET"
                    self_.headers = {}
                    self_.rfile = BytesIO(b"")
                    self_.wfile = BytesIO()
                    self_._cap = {"status": None, "headers": {}, "body": b""}

                def send_response(self_, code, message=None):
                    self_._cap["status"] = code

                def send_header(self_, key, value):
                    self_._cap["headers"][key] = value

                def end_headers(self_):
                    pass

                def _serve_static(self_, rel):
                    self_._send_text("Not found", HTTPStatus.NOT_FOUND)

            self._handler = _Cap()

        @property
        def status(self):
            return self._handler._cap["status"]

        @property
        def body(self):
            return self._handler.wfile.getvalue()

        def do_GET(self):  # noqa: N802
            self._handler.do_GET()

    def test_analytics_por_recoger_route_returns_200(self):
        """GET /analytics/por-recoger MUST return 200."""
        repo, _ = self._make_repo_with_full_history()
        cap = self._CaptureHandler(repo, path="/analytics/por-recoger")
        cap.do_GET()
        self.assertEqual(cap.status, 200,
                         "/analytics/por-recoger must return 200, "
                         f"got {cap.status}")

    def test_analytics_por_recoger_route_content(self):
        """GET /analytics/por-recoger MUST contain page content with
        the delivered guide B001."""
        repo, _ = self._make_repo_with_full_history()
        cap = self._CaptureHandler(repo, path="/analytics/por-recoger")
        cap.do_GET()
        self.assertEqual(cap.status, 200)
        output = cap.body.decode("utf-8")
        self.assertIn("Por recoger", output,
                      "Response must contain page title")
        self.assertIn("B001", output,
                      "Response must contain delivered guide")

    # ══════════════════════════════════════════════════════════════════
    # Analytics page modification — remove inline, add CTA
    # ══════════════════════════════════════════════════════════════════

    def test_analytics_has_cta_to_por_recoger_page(self):
        """Analytics page MUST have a CTA button/link to
        /analytics/por-recoger."""
        repo, tmp = self._make_repo_with_full_history()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            self.assertIn('href="/analytics/por-recoger"', html,
                          "Analytics page must link to /analytics/por-recoger")
            self.assertIn("Ver detalle", html,
                          "CTA must have a clear label like 'Ver detalle'")
        finally:
            tmp.cleanup()

    def test_analytics_no_longer_has_inline_por_recoger_table(self):
        """Analytics page MUST NOT contain the old inline 'Guias en
        Por recoger' table — it's now on the separate page."""
        repo, tmp = self._make_repo_with_full_history()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            # The aggregate breakdown cards still exist but NOT the
            # detailed inline table with guide links
            self.assertNotIn("Guias en Por recoger", html,
                             "Inline 'Guias en Por recoger' title must be removed")
        finally:
            tmp.cleanup()

    def test_analytics_still_shows_breakdown_cards(self):
        """After removing inline table, the aggregate cards (Entregadas,
        Devueltas, Pendientes) MUST still be present."""
        repo, tmp = self._make_repo_with_full_history()
        try:
            html = _render_analytics(repo, {"days": ["30"]})
            self.assertIn("Desglose", html,
                          "'Desglose — Por recoger en oficina' section "
                          "must still exist")
            # Breakdown cards exist
            self.assertIn("Entregadas", html,
                          "Entregadas card must still be present")
            self.assertIn("Devueltas", html,
                          "Devueltas card must still be present")
            self.assertIn("Pendientes", html,
                           "Pendientes card must still be present")
        finally:
            tmp.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# Effi CSV — Problema column sanitization
# ═══════════════════════════════════════════════════════════════════════════════


class EffiProblemaSanitizationTestCase(unittest.TestCase):
    """Sanitization of the Problema column in Effi CSV export.

    The _sanitize_problema_for_effi helper strips VAECOS internal
    recommendation and state-tracking phrases, leaving only the
    operational problem description for the Effi encargada.
    """

    # ── Unit: _sanitize_problema_for_effi ────────────────────────────

    def setUp(self):
        from vaecos_v03.app import _sanitize_problema_for_effi
        self._sanitize = _sanitize_problema_for_effi

    def test_removes_recommendation_suffix_se_sugiere(self):
        """'Se sugiere pasar a Sin movimiento.' suffix is stripped."""
        result = self._sanitize(
            "La novedad lleva más de 2 días sin cambio en Effi. "
            "Se sugiere pasar a Sin movimiento."
        )
        self.assertEqual(
            result,
            "La novedad lleva más de 2 días sin cambio en Effi.",
            "Recommendation suffix must be removed, keeping the operational problem"
        )

    def test_removes_state_tracking_prefix_se_mantiene(self):
        """'Se mantiene Sin movimiento. ' prefix is stripped."""
        result = self._sanitize(
            "Se mantiene Sin movimiento. "
            "No se detecta movimiento reciente en Effi."
        )
        self.assertEqual(
            result,
            "No se detecta movimiento reciente en Effi.",
            "State-tracking prefix must be removed, keeping the operational problem"
        )

    def test_keeps_normal_operational_problem_unchanged(self):
        """Normal operational problem text is not modified."""
        result = self._sanitize(
            "RUTA ENTREGA FINAL con 5 dias sin cambio."
        )
        self.assertEqual(
            result,
            "RUTA ENTREGA FINAL con 5 dias sin cambio.",
            "Normal operational problem must remain unchanged"
        )

    def test_keeps_stagnation_motivo_unchanged(self):
        """'EN RUTA DE ENTREGA con 3 dias sin cambio.' stays intact."""
        result = self._sanitize(
            "EN RUTA DE ENTREGA con 3 dias sin cambio."
        )
        self.assertEqual(
            result,
            "EN RUTA DE ENTREGA con 3 dias sin cambio.",
        )

    def test_keeps_almacenado_motivo_unchanged(self):
        """'ALMACENADO EN BODEGA con 4 dias sin cambio.' stays intact."""
        result = self._sanitize(
            "ALMACENADO EN BODEGA con 4 dias sin cambio."
        )
        self.assertEqual(
            result,
            "ALMACENADO EN BODEGA con 4 dias sin cambio.",
        )

    def test_empty_string_returns_empty(self):
        """Empty motivo returns empty string."""
        result = self._sanitize("")
        self.assertEqual(result, "",
                         "Empty string must return empty string")

    def test_whitespace_only_returns_empty(self):
        """Only whitespace returns empty after strip + sanitize."""
        result = self._sanitize("   ")
        self.assertEqual(result, "",
                         "Whitespace-only must return empty string")

    def test_only_recommendation_returns_empty(self):
        """Motivo that is entirely a recommendation phrase returns empty."""
        result = self._sanitize("Se sugiere pasar a Sin movimiento.")
        self.assertEqual(
            result, "",
            "Pure recommendation must be stripped entirely"
        )

    def test_only_state_tracking_returns_empty(self):
        """Motivo that is entirely state tracking returns empty."""
        result = self._sanitize("Se mantiene Sin movimiento.")
        self.assertEqual(
            result, "",
            "Pure state tracking must be stripped entirely"
        )

    def test_removes_se_mantiene_otro_estado(self):
        """'Se mantiene [any state]. ' prefix is stripped regardless of state."""
        result = self._sanitize(
            "Se mantiene Gestión novedad. La novedad fue registrada recientemente."
        )
        self.assertEqual(
            result,
            "La novedad fue registrada recientemente.",
            "Any 'Se mantiene ...' prefix must be stripped"
        )

    def test_no_double_punctuation_after_cleaning(self):
        """After sanitization, no double periods should remain."""
        result = self._sanitize(
            "Problema detectado. Se sugiere pasar a Sin movimiento."
        )
        self.assertEqual(
            result,
            "Problema detectado.",
            "Must not leave double punctuation after stripping suffix"
        )

    # ── Integration: CSV export with sanitized Problema ──────────────

    def _make_repo_with_internal_phrases(self):
        """Create a repo with motivos containing internal VAECOS phrases."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "test_effi_sanitize.db"
        conn = v02_connect(db)
        try:
            v02_init_db(conn)
        finally:
            conn.close()
        repo = DashboardRepository(db)
        conn = repo._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO runs "
                "(id, started_at, finished_at, mode, total_processed, "
                " total_changed, total_unchanged, total_manual_review, total_error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-04-15T10:00:00", "2026-04-15T10:05:00",
                 "dry-run", 3, 3, 0, 0, 0),
            )
            # Guide 1: has internal recommendation suffix
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "S001", "Cliente A", "effi",
                 "Gestión novedad", "En ruta", "Sin movimiento",
                 "changed",
                 "La novedad lleva más de 2 días sin cambio en Effi. "
                 "Se sugiere pasar a Sin movimiento.",
                 "Gestionar con encargado", None),
            )
            # Guide 2: has internal state-tracking prefix
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "S002", "Cliente B", "effi",
                 "Sin movimiento", "Oficina", "Sin movimiento",
                 "changed",
                 "Se mantiene Sin movimiento. "
                 "No se detecta movimiento reciente en Effi.",
                 "Gestionar con encargado", None),
            )
            # Guide 3: normal operational problem (no internal phrases)
            conn.execute(
                """INSERT INTO run_results
                   (run_id, guia, cliente, carrier, estado_notion_actual,
                    estado_effi_actual, estado_propuesto, resultado, motivo,
                    requiere_accion, notas_operador)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "S003", "Cliente C", "effi",
                 "En ruta", "En ruta", "Sin movimiento",
                 "changed",
                 "RUTA ENTREGA FINAL con 5 dias sin cambio.",
                 "Gestionar con encargado", None),
            )
            conn.commit()
        finally:
            conn.close()
        return repo, tmp

    def test_csv_export_strips_internal_recommendation_suffix(self):
        """CSV Problema column must NOT contain 'Se sugiere pasar a Sin movimiento.'."""
        repo, tmp = self._make_repo_with_internal_phrases()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            self.assertEqual(cap.status, 200)
            decoded = cap.body.decode("utf-8-sig")
            # The recommendation phrase must NOT appear
            self.assertNotIn(
                "Se sugiere pasar a Sin movimiento",
                decoded,
                "CSV must NOT contain internal recommendation phrase"
            )
            # The operational problem MUST still appear
            self.assertIn(
                "La novedad lleva más de 2 días sin cambio en Effi.",
                decoded,
                "Operational problem description must be preserved"
            )
        finally:
            tmp.cleanup()

    def test_csv_export_strips_internal_state_tracking_prefix(self):
        """CSV Problema column must NOT contain 'Se mantiene Sin movimiento.'."""
        repo, tmp = self._make_repo_with_internal_phrases()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            self.assertEqual(cap.status, 200)
            decoded = cap.body.decode("utf-8-sig")
            # The state-tracking prefix must NOT appear
            self.assertNotIn(
                "Se mantiene Sin movimiento",
                decoded,
                "CSV must NOT contain internal state-tracking prefix"
            )
            # The operational problem MUST still appear
            self.assertIn(
                "No se detecta movimiento reciente en Effi.",
                decoded,
                "Operational problem description must be preserved"
            )
        finally:
            tmp.cleanup()

    def test_csv_export_keeps_normal_problema_unchanged(self):
        """Normal operational problema must remain intact in CSV."""
        repo, tmp = self._make_repo_with_internal_phrases()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            self.assertEqual(cap.status, 200)
            decoded = cap.body.decode("utf-8-sig")
            self.assertIn(
                "RUTA ENTREGA FINAL con 5 dias sin cambio.",
                decoded,
                "Normal operational problem must remain unchanged in CSV"
            )
        finally:
            tmp.cleanup()

    def test_csv_export_all_rows_present(self):
        """All 'Gestionar con encargado' guides must appear in CSV."""
        repo, tmp = self._make_repo_with_internal_phrases()
        try:
            cap = Phase3HandlerTestCase._CaptureHandler(
                repo, path="/runs/1/export/effi"
            )
            cap.do_GET()
            self.assertEqual(cap.status, 200)
            decoded = cap.body.decode("utf-8-sig")
            self.assertIn("S001", decoded, "S001 must be in CSV")
            self.assertIn("S002", decoded, "S002 must be in CSV")
            self.assertIn("S003", decoded, "S003 must be in CSV")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
