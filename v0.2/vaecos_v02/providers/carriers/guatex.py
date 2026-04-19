from __future__ import annotations

from typing import ClassVar

from vaecos_v02.providers.carrier import CarrierConfig, CarrierStatus


class GuatexCarrier:
    """Stub placeholder para integrar Guatex como segundo transportista.

    Cuando se implemente, esta clase debe:
      1. Reemplazar el NotImplementedError de fetch_tracking por la logica
         real de consulta al tracking publico de Guatex.
      2. Devolver un CarrierStatus (alias de EffiTrackingData) con estado_actual,
         status_history y novelty_history normalizados al mismo vocabulario que
         maneja core/rules.py (ej. "entregado", "ruta entrega final", etc.)
         para que las mismas reglas apliquen sin cambios.
      3. Mantener el contrato del Protocol Carrier (name, fetch_tracking).
    """

    name: ClassVar[str] = "guatex"

    def __init__(self, config: CarrierConfig) -> None:
        self.config = config

    def fetch_tracking(self, guide: str) -> CarrierStatus:
        raise NotImplementedError(
            "Guatex todavia no esta integrado. Asigna el transportista 'effi' "
            "en Notion o implementa este carrier."
        )
