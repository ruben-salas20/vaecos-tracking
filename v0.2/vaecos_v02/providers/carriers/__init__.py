from __future__ import annotations

from vaecos_v02.providers.carrier import Carrier, CarrierConfig, CarrierStatus
from vaecos_v02.providers.carriers.effi import EffiCarrier
from vaecos_v02.providers.carriers.guatex import GuatexCarrier

CARRIERS: dict[str, type[Carrier]] = {
    EffiCarrier.name: EffiCarrier,
    GuatexCarrier.name: GuatexCarrier,
}


def get_carrier(name: str) -> type[Carrier]:
    key = (name or "").strip().lower()
    cls = CARRIERS.get(key)
    if cls is None:
        raise KeyError(
            f"Carrier desconocido: {name!r}. Disponibles: {sorted(CARRIERS)}"
        )
    return cls


def make_carrier(name: str, config: CarrierConfig) -> Carrier:
    return get_carrier(name)(config)


__all__ = [
    "CARRIERS",
    "Carrier",
    "CarrierConfig",
    "CarrierStatus",
    "EffiCarrier",
    "GuatexCarrier",
    "get_carrier",
    "make_carrier",
]
