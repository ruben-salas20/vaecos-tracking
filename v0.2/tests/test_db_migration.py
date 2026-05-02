from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.storage.db import connect, init_db


class CarrierMigrationTestCase(unittest.TestCase):
    def test_init_adds_carrier_column_on_fresh_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fresh.db"
            conn = connect(db)
            try:
                init_db(conn)
                cols = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertIn("carrier", cols)
            finally:
                conn.close()

    def test_init_migrates_legacy_rules_table_to_new_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy_rules.db"

            legacy = sqlite3.connect(str(db))
            legacy.executescript(
                """
                CREATE TABLE rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    name TEXT NOT NULL,
                    match_estado TEXT,
                    match_estado_contains TEXT,
                    match_novelty_contains TEXT,
                    min_days INTEGER,
                    estado_propuesto TEXT,
                    motivo TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL,
                    review_needed INTEGER NOT NULL DEFAULT 0,
                    updated_by TEXT NOT NULL DEFAULT 'sistema',
                    updated_at TEXT NOT NULL
                );
                INSERT INTO rules (
                    priority, enabled, name, match_estado, match_novelty_contains,
                    min_days, estado_propuesto, motivo, requiere_accion,
                    review_needed, updated_by, updated_at
                ) VALUES (
                    10, 1, 'Legacy Rule', 'entregado', 'cliente no quiso recibir',
                    2, 'ENTREGADA', 'Motivo legacy', 'Sin accion',
                    0, 'sistema', '2026-04-19T10:00:00'
                );
                """
            )
            legacy.commit()
            legacy.close()

            conn = connect(db)
            try:
                init_db(conn)
                cols = [row["name"] for row in conn.execute("PRAGMA table_info(rules)")]
                self.assertIn("carrier", cols)
                self.assertIn("estado_match_kind", cols)
                self.assertIn("motivo_template", cols)

                row = conn.execute(
                    "SELECT carrier, estado_match_kind, novelty_match_kind, days_comparator, days_threshold, motivo_template FROM rules WHERE name = 'Legacy Rule'"
                ).fetchone()
                self.assertEqual(row["carrier"], "effi")
                self.assertEqual(row["estado_match_kind"], "equals_one_of")
                self.assertEqual(row["novelty_match_kind"], "contains_any_of")
                self.assertEqual(row["days_comparator"], "gte")
                self.assertEqual(row["days_threshold"], 2)
                self.assertEqual(row["motivo_template"], "Motivo legacy")
            finally:
                conn.close()

    def test_init_is_idempotent_on_legacy_db(self) -> None:
        """Simulates an existing DB created before the carrier column existed."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy.db"

            legacy = sqlite3.connect(str(db))
            legacy.executescript(
                """
                CREATE TABLE runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    total_processed INTEGER DEFAULT 0,
                    total_changed INTEGER DEFAULT 0,
                    total_unchanged INTEGER DEFAULT 0,
                    total_manual_review INTEGER DEFAULT 0,
                    total_error INTEGER DEFAULT 0
                );
                CREATE TABLE run_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    guia TEXT NOT NULL,
                    cliente TEXT NOT NULL,
                    estado_notion_actual TEXT,
                    estado_effi_actual TEXT,
                    estado_propuesto TEXT,
                    resultado TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL,
                    actualizacion_notion TEXT,
                    error TEXT
                );
                INSERT INTO runs (started_at, mode) VALUES ('2026-04-17T10:00:00', 'dry-run');
                INSERT INTO run_results (run_id, guia, cliente, resultado, motivo, requiere_accion)
                VALUES (1, 'B123', 'Acme', 'unchanged', 'ok', 'ninguna');
                """
            )
            legacy.commit()
            legacy.close()

            conn = connect(db)
            try:
                init_db(conn)
                cols = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertIn("carrier", cols)

                row = conn.execute(
                    "SELECT carrier FROM run_results WHERE guia = 'B123'"
                ).fetchone()
                self.assertEqual(row["carrier"], "effi")

                init_db(conn)
                cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertEqual(cols, cols2)
            finally:
                conn.close()

    # ══════════════════════════════════════════════════════════════════
    # Task 1.5 — RED: notas_operador migration (idempotent)
    # ══════════════════════════════════════════════════════════════════

    def test_init_adds_notas_operador_column_on_fresh_db(self) -> None:
        """RED: init_db() must create the notas_operador column on a new database."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fresh_notes.db"
            conn = connect(db)
            try:
                init_db(conn)
                cols = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertIn("notas_operador", cols,
                              "init_db() must include notas_operador column")
            finally:
                conn.close()

    def test_init_migrates_notas_operador_on_legacy_db(self) -> None:
        """RED: existing DB without notas_operador column must gain it after init_db()."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy_notes.db"

            legacy = sqlite3.connect(str(db))
            legacy.executescript(
                """
                CREATE TABLE runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    total_processed INTEGER DEFAULT 0,
                    total_changed INTEGER DEFAULT 0,
                    total_unchanged INTEGER DEFAULT 0,
                    total_manual_review INTEGER DEFAULT 0,
                    total_error INTEGER DEFAULT 0
                );
                CREATE TABLE run_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    guia TEXT NOT NULL,
                    cliente TEXT NOT NULL,
                    carrier TEXT NOT NULL DEFAULT 'effi',
                    estado_notion_actual TEXT,
                    estado_effi_actual TEXT,
                    estado_propuesto TEXT,
                    resultado TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL,
                    actualizacion_notion TEXT,
                    error TEXT
                );
                INSERT INTO runs (started_at, mode) VALUES ('2026-04-17T10:00:00', 'dry-run');
                INSERT INTO run_results (run_id, guia, cliente, carrier, resultado, motivo, requiere_accion)
                VALUES (1, 'B123', 'Acme', 'effi', 'unchanged', 'ok', 'ninguna');
                """
            )
            legacy.commit()
            legacy.close()

            conn = connect(db)
            try:
                init_db(conn)
                cols = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertIn("notas_operador", cols,
                              "Legacy DB must gain notas_operador after migration")

                # Verify legacy row still accessible with NULL default
                row = conn.execute(
                    "SELECT notas_operador FROM run_results WHERE guia = 'B123'"
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["notas_operador"],
                                  "Existing rows default to NULL notas_operador")
            finally:
                conn.close()

    def test_notas_operador_migration_is_idempotent(self) -> None:
        """RED: calling init_db() multiple times must not crash nor duplicate the column."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "idem_notes.db"
            conn = connect(db)
            try:
                init_db(conn)
                cols1 = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertIn("notas_operador", cols1)

                # Second call must be safe
                init_db(conn)
                cols2 = [row["name"] for row in conn.execute("PRAGMA table_info(run_results)")]
                self.assertEqual(cols1, cols2,
                                 "Column list must be identical after second init_db()")
            finally:
                conn.close()


    # ══════════════════════════════════════════════════════════════════
    # Regression: Almacenado en bodega reciente rule migration
    # Bug: guide B263437621-1 fell to manual_review because the rule
    # "Almacenado en bodega" (priority 71, lte 1) existed in
    # DEFAULT_RULES but NOT in the live SQLite DB. The migration
    # _ensure_bodega_reciente_rule must insert it idempotently.
    # ══════════════════════════════════════════════════════════════════

    def test_init_migrates_bodega_reciente_rule_on_existing_db(self) -> None:
        """RED: Existing DB with rules but without 'Almacenado en bodega'
        (priority 71) must gain it after init_db()."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "existing_bodega.db"

            # Simulate a DB created from the old SEED_RULES (11 rules,
            # no "Almacenado en bodega" reciente rule).
            legacy = sqlite3.connect(str(db))
            legacy.executescript(
                """
                CREATE TABLE runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    total_processed INTEGER DEFAULT 0,
                    total_changed INTEGER DEFAULT 0,
                    total_unchanged INTEGER DEFAULT 0,
                    total_manual_review INTEGER DEFAULT 0,
                    total_error INTEGER DEFAULT 0
                );
                CREATE TABLE run_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    guia TEXT NOT NULL,
                    cliente TEXT NOT NULL,
                    carrier TEXT NOT NULL DEFAULT 'effi',
                    estado_notion_actual TEXT,
                    estado_effi_actual TEXT,
                    estado_propuesto TEXT,
                    resultado TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL,
                    actualizacion_notion TEXT,
                    error TEXT,
                    notas_operador TEXT
                );
                CREATE TABLE rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    carrier TEXT NOT NULL DEFAULT 'effi',
                    name TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    estado_match_kind TEXT NOT NULL DEFAULT 'any'
                        CHECK (estado_match_kind IN ('any', 'equals_one_of', 'contains_any_of')),
                    estado_match_values TEXT NOT NULL DEFAULT '[]',
                    novelty_match_kind TEXT NOT NULL DEFAULT 'any'
                        CHECK (novelty_match_kind IN ('any', 'contains_any_of')),
                    novelty_match_values TEXT NOT NULL DEFAULT '[]',
                    days_comparator TEXT
                        CHECK (days_comparator IS NULL OR days_comparator IN ('gt', 'gte', 'lt', 'lte', 'no_date')),
                    days_threshold INTEGER,
                    estado_propuesto TEXT,
                    motivo_template TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL DEFAULT '',
                    review_needed INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT 'operadora'
                );

                -- Old rules: Almacenado en bodega estancado (priority 70) only,
                -- NO "Almacenado en bodega" reciente rule (priority 71).
                INSERT INTO rules (
                    carrier, name, priority, enabled,
                    estado_match_kind, estado_match_values,
                    novelty_match_kind, novelty_match_values,
                    days_comparator, days_threshold,
                    estado_propuesto, motivo_template, requiere_accion,
                    review_needed, updated_at, updated_by
                ) VALUES (
                    'effi', 'Almacenado en bodega estancado', 70, 1,
                    'equals_one_of', '["almacenado en bodega"]',
                    'any', '[]',
                    'gt', 1,
                    'Sin movimiento', 'ALMACENADO EN BODEGA con {days} dias sin cambio.',
                    'Gestionar con encargado', 0,
                    '2026-04-01T10:00:00', 'sistema'
                );
                """
            )
            legacy.commit()
            legacy.close()

            conn = connect(db)
            try:
                # Before migration: rule must NOT exist
                before = conn.execute(
                    "SELECT COUNT(*) AS c FROM rules WHERE name = 'Almacenado en bodega'"
                ).fetchone()
                self.assertEqual(before["c"], 0,
                                 "Rule must NOT exist before migration")

                init_db(conn)

                # After migration: rule must exist with correct values
                row = conn.execute(
                    "SELECT * FROM rules WHERE name = 'Almacenado en bodega'"
                ).fetchone()
                self.assertIsNotNone(row, "Migration must insert Almacenado en bodega rule")
                self.assertEqual(row["priority"], 71)
                self.assertEqual(row["carrier"], "effi")
                self.assertEqual(row["enabled"], 1)
                self.assertEqual(row["estado_match_kind"], "equals_one_of")
                self.assertEqual(row["days_comparator"], "lte")
                self.assertEqual(row["days_threshold"], 1)
                self.assertEqual(row["estado_propuesto"], "Almacenado en bodega")
                self.assertEqual(row["requiere_accion"], "Monitorear")
                self.assertEqual(row["review_needed"], 0)
                self.assertEqual(row["updated_by"], "migration")

                # Old rule must still exist
                old_row = conn.execute(
                    "SELECT * FROM rules WHERE name = 'Almacenado en bodega estancado'"
                ).fetchone()
                self.assertIsNotNone(old_row,
                                     "Existing rules must not be affected by migration")
            finally:
                conn.close()

    def test_bodega_reciente_migration_is_idempotent(self) -> None:
        """RED: Calling init_db() multiple times must not crash nor duplicate
        the 'Almacenado en bodega' rule. The DB must have at least one other
        rule to bypass the empty-table guard in the migration."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "idem_bodega.db"

            legacy = sqlite3.connect(str(db))
            legacy.executescript(
                """
                CREATE TABLE runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    total_processed INTEGER DEFAULT 0,
                    total_changed INTEGER DEFAULT 0,
                    total_unchanged INTEGER DEFAULT 0,
                    total_manual_review INTEGER DEFAULT 0,
                    total_error INTEGER DEFAULT 0
                );
                CREATE TABLE run_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    guia TEXT NOT NULL,
                    cliente TEXT NOT NULL,
                    carrier TEXT NOT NULL DEFAULT 'effi',
                    estado_notion_actual TEXT,
                    estado_effi_actual TEXT,
                    estado_propuesto TEXT,
                    resultado TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL,
                    actualizacion_notion TEXT,
                    error TEXT,
                    notas_operador TEXT
                );
                CREATE TABLE rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    carrier TEXT NOT NULL DEFAULT 'effi',
                    name TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    estado_match_kind TEXT NOT NULL DEFAULT 'any'
                        CHECK (estado_match_kind IN ('any', 'equals_one_of', 'contains_any_of')),
                    estado_match_values TEXT NOT NULL DEFAULT '[]',
                    novelty_match_kind TEXT NOT NULL DEFAULT 'any'
                        CHECK (novelty_match_kind IN ('any', 'contains_any_of')),
                    novelty_match_values TEXT NOT NULL DEFAULT '[]',
                    days_comparator TEXT
                        CHECK (days_comparator IS NULL OR days_comparator IN ('gt', 'gte', 'lt', 'lte', 'no_date')),
                    days_threshold INTEGER,
                    estado_propuesto TEXT,
                    motivo_template TEXT NOT NULL,
                    requiere_accion TEXT NOT NULL DEFAULT '',
                    review_needed INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT 'operadora'
                );

                -- Insert a pre-existing rule to bypass the empty-table guard.
                INSERT INTO rules (
                    carrier, name, priority, enabled,
                    estado_match_kind, estado_match_values,
                    novelty_match_kind, novelty_match_values,
                    days_comparator, days_threshold,
                    estado_propuesto, motivo_template, requiere_accion,
                    review_needed, updated_at, updated_by
                ) VALUES (
                    'effi', 'Entregado', 40, 1,
                    'equals_one_of', '["entregado"]',
                    'any', '[]',
                    NULL, NULL,
                    'ENTREGADA', 'Effi reporta entrega exitosa.',
                    'Sin accion', 0,
                    '2026-04-01T10:00:00', 'sistema'
                );
                """
            )
            legacy.commit()
            legacy.close()

            conn = connect(db)
            try:
                init_db(conn)
                count1 = conn.execute(
                    "SELECT COUNT(*) AS c FROM rules WHERE name = 'Almacenado en bodega'"
                ).fetchone()["c"]
                self.assertEqual(count1, 1,
                                 "First init_db must insert exactly 1 rule")

                # Second call must be safe
                init_db(conn)
                count2 = conn.execute(
                    "SELECT COUNT(*) AS c FROM rules WHERE name = 'Almacenado en bodega'"
                ).fetchone()["c"]
                self.assertEqual(count2, 1,
                                 "Second init_db must not duplicate the rule")
            finally:
                conn.close()

    def test_init_seeds_bodega_reciente_on_fresh_db(self) -> None:
        """RED: A new DB that has been seeded with DEFAULT_RULES (which
        includes 'Almacenado en bodega') must contain the rule after the
        full init flow (init_db + seed)."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fresh_bodega.db"
            conn = connect(db)
            try:
                init_db(conn)
                # Simulate what the app does: init_db first, then seed.
                from vaecos_v02.core.rules import DEFAULT_RULES
                from vaecos_v02.storage.rules_repository import RulesRepository
                repo = RulesRepository(conn)
                repo.seed_if_empty(DEFAULT_RULES)

                # After seed, the 'Almacenado en bodega' rule must exist
                row = conn.execute(
                    "SELECT * FROM rules WHERE name = 'Almacenado en bodega'"
                ).fetchone()
                self.assertIsNotNone(row,
                    "Seeded DB must contain Almacenado en bodega rule from DEFAULT_RULES")
                self.assertEqual(row["priority"], 71)
                self.assertEqual(row["days_comparator"], "lte")
                self.assertEqual(row["days_threshold"], 1)
                self.assertEqual(row["estado_propuesto"], "Almacenado en bodega")
                self.assertEqual(row["requiere_accion"], "Monitorear")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
