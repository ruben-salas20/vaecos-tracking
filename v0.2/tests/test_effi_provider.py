from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.providers.effi_provider import EffiProvider


SAMPLE_HTML = """
<html>
  <body>
    <div><span><strong>Estado actual:</strong></span> RUTA ENTREGA FINAL</div>
    <p class="tracking-status text-light">HISTÓRICO DE ESTADOS</p>
    <div class="tracking-list">
      <div class="tracking-item">
        <div class="tracking-date">2026-04-17<span>09:10 AM</span></div>
        <div class="tracking-content">RUTA ENTREGA FINAL<span></span></div>
      </div>
      <div class="tracking-item">
        <div class="tracking-date">2026-04-16<span>08:00 AM</span></div>
        <div class="tracking-content">ALMACENADO EN BODEGA<span></span></div>
      </div>
    </div>
    <p class="tracking-status text-light">HISTÓRICO DE NOVEDADES</p>
    <div class="tracking-list">
      <div class="tracking-item">
        <div class="tracking-date">2026-04-17<span>09:15 AM</span></div>
        <div class="tracking-content">Paquete en agencia<span>Sucursal 1</span></div>
      </div>
    </div>
  </body>
</html>
"""


class EffiProviderTestCase(unittest.TestCase):
    def test_parse_tracking_extracts_estado_and_histories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = EffiProvider(
                timeout_seconds=20,
                raw_html_dir=Path(temp_dir),
                save_raw_html=False,
            )

            tracking = provider._parse_tracking(
                url="https://effi.test/tracking/B123",
                html=SAMPLE_HTML,
                raw_path=None,
            )

        self.assertEqual(tracking.estado_actual, "RUTA ENTREGA FINAL")
        self.assertEqual(len(tracking.status_history), 2)
        self.assertEqual(tracking.status_history[0].status, "RUTA ENTREGA FINAL")
        self.assertEqual(len(tracking.novelty_history), 1)
        self.assertEqual(tracking.novelty_history[0].novelty, "Paquete en agencia")
        self.assertEqual(tracking.novelty_history[0].details, "Sucursal 1")


if __name__ == "__main__":
    unittest.main()
