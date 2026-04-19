from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable

from vaecos_v02.core.models import EffiTrackingData

CarrierStatus = EffiTrackingData


@dataclass(frozen=True)
class CarrierConfig:
    timeout_seconds: int
    raw_html_dir: Path
    save_raw_html: bool


@runtime_checkable
class Carrier(Protocol):
    name: ClassVar[str]

    def fetch_tracking(self, guide: str) -> CarrierStatus: ...
