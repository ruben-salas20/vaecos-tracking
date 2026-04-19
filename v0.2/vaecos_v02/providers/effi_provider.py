from __future__ import annotations

from pathlib import Path

from vaecos_v02.providers.carrier import CarrierConfig
from vaecos_v02.providers.carriers.effi import EffiCarrier


class EffiProvider(EffiCarrier):
    def __init__(
        self, timeout_seconds: int, raw_html_dir: Path, save_raw_html: bool
    ) -> None:
        super().__init__(
            CarrierConfig(
                timeout_seconds=timeout_seconds,
                raw_html_dir=raw_html_dir,
                save_raw_html=save_raw_html,
            )
        )


__all__ = ["EffiProvider"]
