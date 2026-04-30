from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.core.models import EffiNovedadEvent, EffiStatusEvent, EffiTrackingData, RuleDecision
from vaecos_v02.core.rules import classify_result_with_cooldown, decide_status, is_gestation_cooldown_active


class RulesTestCase(unittest.TestCase):
    def test_anomalia_with_customer_novelty_maps_to_en_novedad(self) -> None:
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ANOMALIA",
            status_history=[
                EffiStatusEvent(date=datetime(2026, 4, 14, 11, 17), status="ANOMALIA")
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 14, 11, 17),
                    novelty="Cliente no quizo recibir",
                    details="-",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 17))

        self.assertEqual(decision.estado_propuesto, "En novedad")
        self.assertFalse(decision.review_needed)

    # ------------------------------------------------------------------
    # Regression: "a punto de encuentro" variants (missing "al")
    # ------------------------------------------------------------------
    def test_anomalia_with_a_punto_de_encuentro_maps_to_en_novedad(self) -> None:
        """RED: 'Cliente no llegó a punto de encuentro' (without 'al') should
        match the ANOMALIA rule and produce 'En novedad', not manual_review."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ANOMALIA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 11, 0), status="ANOMALIA"
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 30, 11, 0),
                    novelty="Cliente no llegó a punto de encuentro",
                    details="-",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En novedad")
        self.assertFalse(decision.review_needed)

    def test_anomalia_with_a_punto_de_encuentro_no_accent(self) -> None:
        """Triangulate: unaccented variant 'cliente no llego a punto de
        encuentro' must also match (Effi may omit accents)."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ANOMALIA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 11, 0), status="ANOMALIA"
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 30, 11, 0),
                    novelty="Cliente no llego a punto de encuentro",
                    details="-",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En novedad")
        self.assertFalse(decision.review_needed)

    def test_ruta_entrega_final_older_than_one_day_maps_to_sin_movimiento(self) -> None:
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="RUTA ENTREGA FINAL",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 13, 9, 0), status="RUTA ENTREGA FINAL"
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(tracking, today=date(2026, 4, 17))

        self.assertEqual(decision.estado_propuesto, "Sin movimiento")
        self.assertIn("4 dias", decision.motivo)

    def test_paquete_en_agencia_novelty_maps_to_por_recoger(self) -> None:
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 17, 8, 30), status="ALMACENADO EN BODEGA"
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 17, 8, 31),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 17))

        self.assertEqual(decision.estado_propuesto, "Por recoger (INFORMADO)")

    # ------------------------------------------------------------------
    # 3.2 — terminal beats contextual: ENTREGADO wins over old "Paquete en agencia"
    # ------------------------------------------------------------------
    def test_terminal_beats_contextual_entregado_vs_old_agencia(self) -> None:
        """RED: with old agencia novelty + current ENTREGADO, terminal must win."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ENTREGADO",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0), status="ENTREGADO"
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 15, 10, 0),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "ENTREGADA")
        self.assertNotEqual(
            decision.estado_propuesto, "Por recoger (INFORMADO)"
        )

    # ------------------------------------------------------------------
    # 3.3 — return beats contextual: Devolución wins over old agency signal
    # ------------------------------------------------------------------
    def test_terminal_beats_contextual_devolucion_vs_old_agencia(self) -> None:
        """RED: with old agencia novelty + current Devolución, terminal must win."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="Devolución iniciada",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0),
                    status="Devolución iniciada",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 15, 10, 0),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En Devolución")
        self.assertNotEqual(
            decision.estado_propuesto, "Por recoger (INFORMADO)"
        )

    # ------------------------------------------------------------------
    # 3.4 — latest context only: old contextual novelty does not leak
    # ------------------------------------------------------------------
    def test_latest_context_only_no_leak(self) -> None:
        """RED: old 'paquete en agencia' should not fire when latest novelty is
        something else that does not match any contextual pattern."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 15, 10, 0),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                ),
                EffiNovedadEvent(
                    date=datetime(2026, 4, 29, 15, 0),
                    novelty="Intentó entrega",
                    details="No había nadie",
                ),
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        # Contextual "Paquete en agencia" must NOT fire because only the
        # latest novelty ("intento entrega no habia nadie") is evaluated.
        self.assertNotEqual(
            decision.matched_rule_name,
            "Paquete en agencia (novedad)",
        )
        self.assertNotEqual(
            decision.estado_propuesto, "Por recoger (INFORMADO)"
        )

    # ------------------------------------------------------------------
    # 3.4b — triangulation: latest novelty still fires contextual rule
    # ------------------------------------------------------------------
    def test_latest_context_matches_when_relevant(self) -> None:
        """Triangulate 3.4: when the latest novelty DOES match the contextual
        pattern, the rule should fire (it is not suppressed)."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 15, 10, 0),
                    novelty="Cliente no quizo recibir",
                    details="-",
                ),
                EffiNovedadEvent(
                    date=datetime(2026, 4, 29, 15, 0),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                ),
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))
        # Latest novelty is "paquete en agencia" → contextual rule still fires.
        self.assertEqual(decision.estado_propuesto, "Por recoger (INFORMADO)")
        self.assertEqual(
            decision.matched_rule_name, "Paquete en agencia (novedad)"
        )

    # ------------------------------------------------------------------
    # 3.5 — single-event history preserved
    # ------------------------------------------------------------------
    def test_single_event_preserved(self) -> None:
        """Approval: single-novelty context still fires contextual rule as before."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 29, 15, 0),
                    novelty="Paquete en agencia",
                    details="Agencia central",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "Por recoger (INFORMADO)")

    # ------------------------------------------------------------------
    # 3.6 — stagnation rules still work (non-terminal days-based)
    # ------------------------------------------------------------------
    def test_operational_stagnation_still_works(self) -> None:
        """Approval: stagnation rules based on days still produce correct output."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="RUTA ENTREGA FINAL",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 9, 0),
                    status="RUTA ENTREGA FINAL",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))
        # 0 days elapsed → "Ruta entrega final reciente" (lte 1) fires
        self.assertEqual(decision.estado_propuesto, "En ruta de entrega")

    # ------------------------------------------------------------------
    # Regression: ALMACENADO EN BODEGA + customer-relevant novelty → En novedad
    # Bug: guide B263437646-1 moved from ANOMALIA to ALMACENADO EN BODEGA
    # but kept a customer-relevant novelty. The existing ANOMALIA rule only
    # matches estado_actual==ANOMALIA, producing manual_review instead of
    # "En novedad".  A new rule is required.
    # ------------------------------------------------------------------
    def test_almacenado_bodega_with_customer_novelty_maps_to_en_novedad(self) -> None:
        """RED: 'ALMACENADO EN BODEGA' + customer novelty ('Cliente no llegó
        a punto de encuentro') should produce 'En novedad', not manual_review."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    novelty="Cliente no llegó a punto de encuentro",
                    details="(Segundo intento)",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En novedad")
        self.assertFalse(decision.review_needed)
        self.assertEqual(decision.requiere_accion, "Hablar con cliente")

    def test_almacenado_bodega_sin_novedad_sigue_manual_review(self) -> None:
        """Triangulate: ALMACENADO EN BODEGA without a customer-relevant
        novelty (e.g., no novelty at all, 0 days) should still fall through
        to manual_review (no stagnation since days=0 < 1)."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    novelty="En ruta de entrega",
                    details="",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        # Stagnation rule "Almacenado en bodega estancado" requires days > 1,
        # so with 0 days it won't fire.  No contextual novelty match → fallback.
        self.assertTrue(decision.review_needed)
        self.assertIsNone(decision.estado_propuesto)

    def test_almacenado_bodega_with_cliente_no_quiso_recibir(self) -> None:
        """Triangulate: another ANOMALIA_PATTERNS entry ('cliente no quiso
        recibir') must also match for ALMACENADO EN BODEGA."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 13, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 30, 13, 0),
                    novelty="Cliente no quiso recibir",
                    details="Rechaza el paquete",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En novedad")
        self.assertFalse(decision.review_needed)
        self.assertEqual(decision.requiere_accion, "Hablar con cliente")

    # ------------------------------------------------------------------
    # Phase 7 — Gestión novedad 2-day operational cooldown
    # ------------------------------------------------------------------
    def _make_cooldown_decision(
        self,
        estado_propuesto: str | None = "En novedad",
        review_needed: bool = False,
    ) -> RuleDecision:
        """Helper: build a RuleDecision for cooldown testing."""
        return RuleDecision(
            estado_propuesto=estado_propuesto,
            motivo="Test motive",
            requiere_accion="Hablar con cliente",
            review_needed=review_needed,
            matched_rule_id=1,
            matched_rule_name="Test rule",
        )

    def test_cooldown_active_within_2_days(self) -> None:
        """RED: Gestión novedad + En novedad + fecha 1 day ago → cooldown ACTIVE."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        self.assertTrue(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "Cooldown debe estar activo con solo 1 día transcurrido",
        )

    def test_cooldown_expired_after_2_days(self) -> None:
        """Triangulate: fecha >= 2 days ago → cooldown must NOT be active."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-28",
                today=date(2026, 4, 30),
            ),
            "Cooldown debe expirar a los 2 días (≥ 2)",
        )

    def test_cooldown_bypass_terminal_entregada(self) -> None:
        """Bypass: ENTREGADA decision must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(estado_propuesto="ENTREGADA")
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "ENTREGADA siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_terminal_en_devolucion(self) -> None:
        """Bypass: En Devolución decision must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(estado_propuesto="En Devolución")
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "En Devolución siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_por_recoger(self) -> None:
        """Bypass: Por recoger (INFORMADO) must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="Por recoger (INFORMADO)"
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "Por recoger siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_en_ruta_de_entrega(self) -> None:
        """Bypass: En ruta de entrega must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En ruta de entrega"
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "En ruta de entrega siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_different_notion_state(self) -> None:
        """Bypass: only 'Gestión novedad' triggers cooldown, not other states."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="En novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "Solo Gestión novedad activa el cooldown, no En novedad",
        )

    def test_cooldown_bypass_no_fecha(self) -> None:
        """Bypass: when fecha_ultimo_seguimiento is None, cooldown cannot be
        determined → return False (don't block the update)."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento=None,
                today=date(2026, 4, 30),
            ),
            "Sin fecha no se puede determinar cooldown → no bloquear",
        )

    def test_cooldown_bypass_review_needed(self) -> None:
        """Bypass: when decision has review_needed=True, cooldown does not apply."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", review_needed=True
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "Si review_needed ya está activo, no aplica cooldown",
        )

    def test_cooldown_bypass_estado_propuesto_none(self) -> None:
        """Bypass: when decision has estado_propuesto=None, cooldown does not apply."""
        decision = self._make_cooldown_decision(estado_propuesto=None)
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
                fecha_ultimo_seguimiento="2026-04-29",
                today=date(2026, 4, 30),
            ),
            "Si no hay estado propuesto, no aplica cooldown",
        )

    # ------------------------------------------------------------------
    # 7.3 — classify_result_with_cooldown integration tests
    # ------------------------------------------------------------------
    def test_classify_cooldown_blocks_en_novedad_operator_friendly(self) -> None:
        """RED: Gestión novedad + En novedad within 2 days → result 'unchanged',
        but with operator-friendly representation (no 'cooldown' as main concept)."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        resultado, motivo, accion, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
            fecha_ultimo_seguimiento="2026-04-29",
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "unchanged")
        # Verify estado_propuesto override → operator sees "Gestión novedad" not "En novedad"
        self.assertEqual(estado_propuesto, "Gestión novedad",
            "Debe sugerir mantener Gestión novedad, no exponer En novedad")
        # Verify motivo is operator-friendly — NO mention of 'cooldown' or 'bloqueado'
        self.assertNotIn("BLOQUEADO", motivo,
            "No debe exponer lenguaje técnico de bloqueo")
        self.assertNotIn("COOLDOWN", motivo,
            "No debe exponer el término cooldown como concepto principal")
        self.assertIn("Gestión novedad", motivo,
            "Debe mencionar que se mantiene Gestión novedad")
        # Verify accion is consistent with the system's 'No aplica' pattern
        self.assertEqual(accion, "No aplica")

    def test_classify_cooldown_allows_terminal_entregada(self) -> None:
        """Terminal ENTREGADA bypasses cooldown → 'changed' (different from Gestión)."""
        decision = self._make_cooldown_decision(estado_propuesto="ENTREGADA")
        resultado, motivo, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
            fecha_ultimo_seguimiento="2026-04-29",
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "changed")
        self.assertNotIn("BLOQUEADO", motivo)
        # When cooldown is NOT active, estado_propuesto comes from the decision
        self.assertEqual(estado_propuesto, "ENTREGADA")

    def test_classify_cooldown_allows_ruta_entrega_reciente(self) -> None:
        """En ruta de entrega bypasses cooldown → 'changed'."""
        decision = self._make_cooldown_decision(estado_propuesto="En ruta de entrega")
        resultado, motivo, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
            fecha_ultimo_seguimiento="2026-04-29",
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "changed")
        self.assertNotIn("BLOQUEADO", motivo)
        self.assertEqual(estado_propuesto, "En ruta de entrega")

    def test_classify_cooldown_respects_review_needed(self) -> None:
        """Decision with review_needed stays manual_review regardless of cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", review_needed=True
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
            fecha_ultimo_seguimiento="2026-04-29",
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "manual_review")
        self.assertEqual(estado_propuesto, "En novedad")

    def test_classify_cooldown_unchanged_when_same_state(self) -> None:
        """When proposed == current notion state → unchanged (even without cooldown)."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="En novedad",
            fecha_ultimo_seguimiento=None,
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "unchanged")
        self.assertEqual(estado_propuesto, "En novedad")

    def test_classify_cooldown_changed_when_different_no_cooldown(self) -> None:
        """Different state, no cooldown conditions met → 'changed'."""
        decision = self._make_cooldown_decision(estado_propuesto="Por recoger (INFORMADO)")
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="En ruta",
            fecha_ultimo_seguimiento=None,
            today=date(2026, 4, 30),
        )
        self.assertEqual(resultado, "changed")
        self.assertEqual(estado_propuesto, "Por recoger (INFORMADO)")


if __name__ == "__main__":
    unittest.main()
