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

    def test_almacenado_bodega_sin_novedad_reciente_propone_mantener(self) -> None:
        """RED: ALMACENADO EN BODEGA sin novedad de cliente, reciente (0-1 días),
        debe proponer mantener 'Almacenado en bodega', NO manual_review.
        Bug: guide B263437621-1 caía en manual_review porque no había regla
        para el caso base de 'Almacenado en bodega' reciente."""
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

        # Nueva regla "Almacenado en bodega" (priority 71, lte 1) debe disparar.
        self.assertFalse(decision.review_needed,
            "Nueva regla base evita manual_review para Almacenado en bodega reciente")
        self.assertEqual(decision.estado_propuesto, "Almacenado en bodega",
            "Debe proponer mantener el estado actual de Almacenado en bodega")
        self.assertEqual(decision.requiere_accion, "Monitorear")
        self.assertEqual(decision.matched_rule_name, "Almacenado en bodega")

    def test_almacenado_bodega_sin_novedad_estancado_sigue_sin_movimiento(self) -> None:
        """TRIANGULATE: ALMACENADO EN BODEGA sin novedad, 2+ días →
        la regla de estancamiento 'Almacenado en bodega estancado' (priority 70,
        gt 1) debe seguir ganando sobre la nueva regla base (priority 71, lte 1)."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 28, 12, 0),  # 2 days ago
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "Sin movimiento",
            "Estancamiento (gt 1) debe ganar sobre regla base (lte 1)")
        self.assertFalse(decision.review_needed)
        self.assertEqual(decision.matched_rule_name, "Almacenado en bodega estancado")

    def test_almacenado_bodega_con_novedad_cliente_sigue_en_novedad(self) -> None:
        """TRIANGULATE: ALMACENADO EN BODEGA con novedad de cliente, 0 días →
        la regla contextual (priority 25, fase 3) debe ganar sobre la nueva
        regla base (priority 71, fase 4)."""
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
                    novelty="Cliente no quiso recibir",
                    details="Rechaza el paquete",
                )
            ],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "En novedad",
            "Contextual debe ganar sobre regla base cuando hay novedad de cliente")
        self.assertFalse(decision.review_needed)
        self.assertEqual(decision.matched_rule_name,
                         "Almacenado en bodega con novedad de cliente")

    def test_almacenado_bodega_reciente_pipeline_unchanged(self) -> None:
        """RED (integrated): Effi 'ALMACENADO EN BODEGA' + Notion
        'Almacenado en bodega' + 0 días + sin novedad de cliente →
        classify_result_with_cooldown debe devolver 'unchanged'."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(
            tracking,
            today=date(2026, 4, 30),
            notion_estado="Almacenado en bodega",
        )
        resultado, motivo, accion, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Almacenado en bodega",
        )

        self.assertEqual(resultado, "unchanged",
            "Pipeline debe devolver unchanged cuando Effi y Notion coinciden en Almacenado en bodega")
        self.assertEqual(estado_propuesto, "Almacenado en bodega")
        self.assertEqual(accion, "Monitorear")
        self.assertIn("coincide con Notion", motivo)

    def test_almacenado_bodega_1_dia_todavia_reciente(self) -> None:
        """TRIANGULATE: 1 día desde el último estado → todavía activa la
        regla base (lte 1), no la de estancamiento (gt 1)."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 29, 12, 0),  # 1 day ago
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(tracking, today=date(2026, 4, 30))

        self.assertEqual(decision.estado_propuesto, "Almacenado en bodega",
            "1 día debe ser reciente (lte 1), no estancado (gt 1)")
        self.assertEqual(decision.matched_rule_name, "Almacenado en bodega")

    def test_almacenado_bodega_reciente_notion_diferente_propone_cambio(self) -> None:
        """TRIANGULATE: Effi 'ALMACENADO EN BODEGA' + Notion 'En ruta' + 0 días →
        la regla propone 'Almacenado en bodega', y el clasificador devuelve
        'changed' por la diferencia de estados."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 30, 12, 0),
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(
            tracking,
            today=date(2026, 4, 30),
            notion_estado="En ruta",
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="En ruta",
        )

        self.assertEqual(resultado, "changed",
            "Cuando Notion difiere de Effi, debe proponer cambio (no unchanged)")
        self.assertEqual(estado_propuesto, "Almacenado en bodega")

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
    # Post-RFC: Gestión novedad cooldown (based on Effi days, not Notion fecha)
    # ------------------------------------------------------------------
    def _make_cooldown_decision(
        self,
        estado_propuesto: str | None = "En novedad",
        review_needed: bool = False,
        days_since_last_status: int | None = None,
    ) -> RuleDecision:
        """Helper: build a RuleDecision for cooldown testing."""
        return RuleDecision(
            estado_propuesto=estado_propuesto,
            motivo="Test motive",
            requiere_accion="Hablar con cliente",
            review_needed=review_needed,
            matched_rule_id=1,
            matched_rule_name="Test rule",
            days_since_last_status=days_since_last_status,
        )

    # ── is_gestation_cooldown_active() unit tests ────────────────────

    def test_cooldown_active_when_effi_days_less_than_2(self) -> None:
        """RED: Gestión novedad + En novedad + 1 Effi day → cooldown ACTIVE."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=1
        )
        self.assertTrue(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Cooldown debe estar activo con 1 día desde último evento Effi",
        )

    def test_cooldown_expired_when_effi_days_2_or_more(self) -> None:
        """Triangulate: Effi days ≥ 2 → cooldown must NOT be active."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=2
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Cooldown debe expirar a los 2 días (≥ 2) desde Effi",
        )

    def test_cooldown_expired_when_effi_days_5(self) -> None:
        """Triangulate: 5 Effi days → cooldown definitely NOT active."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=5
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "A los 5 días el cooldown ya no debe estar activo",
        )

    def test_cooldown_bypass_terminal_entregada(self) -> None:
        """Bypass: ENTREGADA decision must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="ENTREGADA", days_since_last_status=1
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "ENTREGADA siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_terminal_en_devolucion(self) -> None:
        """Bypass: En Devolución decision must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En Devolución", days_since_last_status=1
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "En Devolución siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_por_recoger(self) -> None:
        """Bypass: Por recoger (INFORMADO) must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="Por recoger (INFORMADO)", days_since_last_status=1
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Por recoger siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_en_ruta_de_entrega(self) -> None:
        """Bypass: En ruta de entrega must NOT trigger cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En ruta de entrega", days_since_last_status=1
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "En ruta de entrega siempre debe bypassear el cooldown",
        )

    def test_cooldown_bypass_different_notion_state(self) -> None:
        """Bypass: only 'Gestión novedad' triggers cooldown, not other states."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=1
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="En novedad",
                decision=decision,
            ),
            "Solo Gestión novedad activa el cooldown, no En novedad",
        )

    def test_cooldown_bypass_no_effi_days(self) -> None:
        """Bypass: when Effi days_since_last_status is None, cooldown cannot be
        determined → return False (don't block the update)."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=None
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Sin fecha Effi no se puede determinar cooldown → no bloquear",
        )

    def test_cooldown_bypass_review_needed(self) -> None:
        """Bypass: when decision has review_needed=True, cooldown does not apply."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", review_needed=True,
            days_since_last_status=1,
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Si review_needed ya está activo, no aplica cooldown",
        )

    def test_cooldown_bypass_estado_propuesto_none(self) -> None:
        """Bypass: when decision has estado_propuesto=None, cooldown does not apply."""
        decision = self._make_cooldown_decision(
            estado_propuesto=None, days_since_last_status=1,
        )
        self.assertFalse(
            is_gestation_cooldown_active(
                notion_estado="Gestión novedad",
                decision=decision,
            ),
            "Si no hay estado propuesto, no aplica cooldown",
        )

    # ── classify_result_with_cooldown() integration tests ────────────

    def test_classify_cooldown_blocks_en_novedad_operator_friendly(self) -> None:
        """RED: Gestión novedad + En novedad within 2 Effi days → result 'unchanged',
        operator-friendly representation (no 'cooldown' as main concept)."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=1
        )
        resultado, motivo, accion, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "unchanged")
        self.assertEqual(estado_propuesto, "Gestión novedad",
            "Debe sugerir mantener Gestión novedad, no exponer En novedad")
        self.assertNotIn("BLOQUEADO", motivo,
            "No debe exponer lenguaje técnico de bloqueo")
        self.assertNotIn("COOLDOWN", motivo,
            "No debe exponer el término cooldown como concepto principal")
        self.assertIn("Gestión novedad", motivo,
            "Debe mencionar que se mantiene Gestión novedad")
        self.assertEqual(accion, "No aplica")

    def test_classify_cooldown_expired_transitions_to_sin_movimiento(self) -> None:
        """RED: Gestión novedad + En novedad + 2+ Effi days → Sin movimiento."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=2
        )
        resultado, motivo, accion, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "changed",
            "Tras cooldown expirado debe proponer cambio a Sin movimiento")
        self.assertEqual(estado_propuesto, "Sin movimiento",
            "Debe sugerir transición a Sin movimiento")
        self.assertEqual(accion, "Gestionar con encargado",
            "La acción debe ser Gestionar con encargado")
        self.assertIn("Sin movimiento", motivo,
            "El motivo debe mencionar Sin movimiento")

    def test_classify_cooldown_expired_with_5_effi_days(self) -> None:
        """Triangulate: 5 Effi days → Sin movimiento transition."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=5
        )
        resultado, _, accion, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "changed")
        self.assertEqual(estado_propuesto, "Sin movimiento")
        self.assertEqual(accion, "Gestionar con encargado")

    def test_classify_cooldown_allows_terminal_entregada(self) -> None:
        """Terminal ENTREGADA bypasses cooldown → 'changed' (different from Gestión)."""
        decision = self._make_cooldown_decision(
            estado_propuesto="ENTREGADA", days_since_last_status=1
        )
        resultado, motivo, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "changed")
        self.assertNotIn("BLOQUEADO", motivo)
        self.assertEqual(estado_propuesto, "ENTREGADA")

    def test_classify_cooldown_allows_ruta_entrega_reciente(self) -> None:
        """En ruta de entrega bypasses cooldown → 'changed'."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En ruta de entrega", days_since_last_status=1
        )
        resultado, motivo, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "changed")
        self.assertNotIn("BLOQUEADO", motivo)
        self.assertEqual(estado_propuesto, "En ruta de entrega")

    def test_classify_cooldown_respects_review_needed(self) -> None:
        """Decision with review_needed stays manual_review regardless of cooldown."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", review_needed=True,
            days_since_last_status=1,
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "manual_review")
        self.assertEqual(estado_propuesto, "En novedad")

    def test_classify_cooldown_unchanged_when_same_state(self) -> None:
        """When proposed == current notion state → unchanged (even without cooldown)."""
        decision = self._make_cooldown_decision(estado_propuesto="En novedad")
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="En novedad",
        )
        self.assertEqual(resultado, "unchanged")
        self.assertEqual(estado_propuesto, "En novedad")

    def test_classify_cooldown_changed_when_different_no_cooldown(self) -> None:
        """Different state, no cooldown conditions met → 'changed'."""
        decision = self._make_cooldown_decision(
            estado_propuesto="Por recoger (INFORMADO)"
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="En ruta",
        )
        self.assertEqual(resultado, "changed")
        self.assertEqual(estado_propuesto, "Por recoger (INFORMADO)")

    def test_classify_cooldown_expired_not_blocked_by_no_effi_days(self) -> None:
        """When Effi days is None, expired branch must NOT trigger (no date → can't
        determine if it's been 2+ days). Normal rules proceed."""
        decision = self._make_cooldown_decision(
            estado_propuesto="En novedad", days_since_last_status=None
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        # Notion "Gestión novedad" vs proposed "En novedad" → different → "changed"
        # But with no Effi date, we can't determine if 2+ days have passed
        # Normal rules should apply: propose the rule's estado_propuesto
        self.assertEqual(resultado, "changed")
        self.assertEqual(estado_propuesto, "En novedad",
            "Sin fecha Effi, debe proponer En novedad (no transición a Sin movimiento)")

    def test_classify_cooldown_terminal_entregada_with_old_effi_days(self) -> None:
        """Terminal ENTREGADA with 10 Effi days must still bypass → ENTREGADA."""
        decision = self._make_cooldown_decision(
            estado_propuesto="ENTREGADA", days_since_last_status=10
        )
        resultado, _, _, estado_propuesto = classify_result_with_cooldown(
            decision=decision,
            notion_estado="Gestión novedad",
        )
        self.assertEqual(resultado, "changed")
        self.assertEqual(estado_propuesto, "ENTREGADA",
            "ENTREGADA debe bypassear incluso con días viejos de Effi")


    # ══════════════════════════════════════════════════════════════════
    # Task 1.3 — RED: M1 preservation of "Sin movimiento"
    # Scenario: Notion says "Sin movimiento", Effi has no recent
    # movement (latest_status_date > 3 days). The normal rules would
    # fall through to manual_review, but preservation must override
    # to keep "Sin movimiento".
    # ══════════════════════════════════════════════════════════════════
    def test_sin_movimiento_preservation_when_no_recent_effi_movement(self) -> None:
        """RED: Notion 'Sin movimiento' + Effi last movement 7 days ago →
        preservation overrides any other rule and returns 'Sin movimiento'."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="En oficina central",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 23, 9, 0),  # 7 days ago from today
                    status="En oficina central",
                )
            ],
            novelty_history=[],
        )

        # Without preservation, no rule matches "En oficina central"
        # → fallback with review_needed=True.
        # With preservation, "Sin movimiento" from Notion is respected.
        decision = decide_status(
            tracking,
            today=date(2026, 4, 30),
            notion_estado="Sin movimiento",
        )

        self.assertEqual(decision.estado_propuesto, "Sin movimiento",
                         "Preservación debe mantener Sin movimiento cuando Effi no tiene movimiento reciente")
        self.assertIn("Sin movimiento", decision.motivo,
                      "El motivo debe indicar que se preserva Sin movimiento")
        self.assertFalse(decision.review_needed,
                         "Preservación no debe marcar review_needed")
        self.assertIsNone(decision.matched_rule_id,
                          "No debe atribuirse a una regla concreta")

    def test_sin_movimiento_preservation_when_status_date_unknown(self) -> None:
        """RED: Notion 'Sin movimiento' + Effi latest_status_date is None
        (unknown/parse error) → preservation keeps 'Sin movimiento'."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="Paquete listo",
            status_history=[
                EffiStatusEvent(
                    date=None,  # unknown date
                    status="Paquete listo",
                )
            ],
            novelty_history=[],
        )

        decision = decide_status(
            tracking,
            today=date(2026, 4, 30),
            notion_estado="Sin movimiento",
        )

        self.assertEqual(decision.estado_propuesto, "Sin movimiento",
                         "Fecha desconocida equivale a sin movimiento reciente → preservar")
        self.assertIn("Sin movimiento", decision.motivo)

    # ══════════════════════════════════════════════════════════════════
    # Task 1.4 — TRIANGULATE: preservation does NOT block when
    # Effi shows recent movement (≤ 2 days)
    # ══════════════════════════════════════════════════════════════════
    def test_sin_movimiento_no_preservation_when_recent_effi_movement(self) -> None:
        """TRIANGULATE: Notion 'Sin movimiento' + Effi movement 1 day ago →
        preservation must NOT block other rules from firing."""
        tracking = EffiTrackingData(
            url="https://example.test",
            estado_actual="ALMACENADO EN BODEGA",
            status_history=[
                EffiStatusEvent(
                    date=datetime(2026, 4, 29, 9, 0),  # 1 day ago
                    status="ALMACENADO EN BODEGA",
                )
            ],
            novelty_history=[
                EffiNovedadEvent(
                    date=datetime(2026, 4, 29, 9, 0),
                    novelty="Paquete en agencia",
                    details="Oficina central",
                )
            ],
        )

        decision = decide_status(
            tracking,
            today=date(2026, 4, 30),
            notion_estado="Sin movimiento",
        )

        # With recent movement (1 day), the contextual rule should fire
        # and preservation must NOT override it.
        self.assertEqual(decision.estado_propuesto, "Por recoger (INFORMADO)",
                         "Con movimiento reciente, la preservación no debe bloquear otras reglas")
        self.assertEqual(decision.matched_rule_name, "Paquete en agencia (novedad)")


if __name__ == "__main__":
    unittest.main()
