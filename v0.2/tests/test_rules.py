from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.core.models import EffiNovedadEvent, EffiStatusEvent, EffiTrackingData
from vaecos_v02.core.rules import decide_status


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


if __name__ == "__main__":
    unittest.main()
