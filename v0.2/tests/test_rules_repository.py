from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.core.models import (
    EffiNovedadEvent,
    EffiStatusEvent,
    EffiTrackingData,
    Rule,
)
from vaecos_v02.core.rules import DEFAULT_RULES, decide_status
from vaecos_v02.storage.db import connect, init_db
from vaecos_v02.storage.rules_repository import RulesRepository


def _sample_rule(**overrides) -> Rule:
    base = dict(
        id=None,
        carrier="effi",
        name="Test rule",
        priority=100,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["probe"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="PROPUESTO",
        motivo_template="motivo test",
        requiere_accion="accion test",
        review_needed=False,
        notes="",
    )
    base.update(overrides)
    return Rule(**base)


class RulesRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "rules.db"
        self.conn = connect(db_path)
        init_db(self.conn)
        self.repo = RulesRepository(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def test_seed_is_idempotent(self) -> None:
        inserted_first = self.repo.seed_if_empty(DEFAULT_RULES)
        self.assertEqual(inserted_first, len(DEFAULT_RULES))

        inserted_second = self.repo.seed_if_empty(DEFAULT_RULES)
        self.assertEqual(inserted_second, 0)

        all_rules = self.repo.list_rules()
        self.assertEqual(len(all_rules), len(DEFAULT_RULES))

    def test_create_update_and_audit(self) -> None:
        rule = self.repo.save_rule(_sample_rule(), changed_by="tester")
        self.assertIsNotNone(rule.id)
        self.assertEqual(rule.updated_by, "tester")

        updated = self.repo.save_rule(
            replace(rule, motivo_template="nuevo motivo"), changed_by="tester"
        )
        self.assertEqual(updated.motivo_template, "nuevo motivo")

        history = self.repo.history_for_rule(rule.id)
        # Newest first: update, then create
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["action"], "update")
        self.assertEqual(history[1]["action"], "create")

    def test_toggle_records_enable_disable_actions(self) -> None:
        rule = self.repo.save_rule(_sample_rule())
        self.repo.toggle_rule(rule.id)
        self.repo.toggle_rule(rule.id)
        actions = [row["action"] for row in self.repo.history_for_rule(rule.id)]
        self.assertIn("disable", actions)
        self.assertIn("enable", actions)

    def test_validate_rejects_invalid_kinds(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.save_rule(_sample_rule(estado_match_kind="whatever"))
        with self.assertRaises(ValueError):
            self.repo.save_rule(
                _sample_rule(days_comparator="gt", days_threshold=None)
            )
        with self.assertRaises(ValueError):
            self.repo.save_rule(_sample_rule(motivo_template="   "))

    def test_delete_removes_rule_and_audits(self) -> None:
        rule = self.repo.save_rule(_sample_rule())
        ok = self.repo.delete_rule(rule.id)
        self.assertTrue(ok)
        self.assertIsNone(self.repo.get_rule(rule.id))
        actions = [row["action"] for row in self.repo.history_for_rule(rule.id)]
        self.assertIn("delete", actions)


class RulesEngineTestCase(unittest.TestCase):
    """Verifies the data-driven engine reproduces the legacy hardcoded decisions."""

    def test_default_rules_match_legacy_sin_recolectar(self) -> None:
        tracking = EffiTrackingData(
            url="",
            estado_actual="SIN RECOLECTAR",
            status_history=[
                EffiStatusEvent(date=datetime(2026, 4, 10, 8, 0), status="SIN RECOLECTAR")
            ],
            novelty_history=[],
        )
        decision = decide_status(tracking, today=date(2026, 4, 17))
        self.assertEqual(decision.estado_propuesto, "Sin movimiento")
        self.assertIn("Sin Recolectar", decision.motivo)

    def test_no_date_rule_fires_only_when_date_missing(self) -> None:
        tracking = EffiTrackingData(
            url="",
            estado_actual="RUTA ENTREGA FINAL",
            status_history=[EffiStatusEvent(date=None, status="RUTA ENTREGA FINAL")],
            novelty_history=[],
        )
        decision = decide_status(tracking, today=date(2026, 4, 17))
        self.assertTrue(decision.review_needed)
        self.assertIn("sin fecha", decision.motivo.lower())

    def test_empty_rules_falls_back_to_manual_review(self) -> None:
        tracking = EffiTrackingData(
            url="",
            estado_actual="ENTREGADO",
            status_history=[],
            novelty_history=[],
        )
        decision = decide_status(tracking, today=date(2026, 4, 17), rules=[])
        self.assertTrue(decision.review_needed)
        self.assertIsNone(decision.estado_propuesto)

    def test_matched_rule_id_populated(self) -> None:
        custom = [
            _sample_rule(
                id=42,
                name="captura entregado",
                estado_match_kind="equals_one_of",
                estado_match_values=["entregado"],
                estado_propuesto="ENTREGADA",
                motivo_template="hit",
                priority=1,
            )
        ]
        tracking = EffiTrackingData(
            url="",
            estado_actual="ENTREGADO",
            status_history=[],
            novelty_history=[],
        )
        decision = decide_status(tracking, today=date(2026, 4, 17), rules=custom)
        self.assertEqual(decision.matched_rule_id, 42)
        self.assertEqual(decision.matched_rule_name, "captura entregado")


if __name__ == "__main__":
    unittest.main()
