from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vaecos_v02.providers.carrier import Carrier, CarrierConfig
from vaecos_v02.providers.carriers import (
    CARRIERS,
    EffiCarrier,
    GuatexCarrier,
    get_carrier,
    make_carrier,
)


class CarrierRegistryTestCase(unittest.TestCase):
    def _cfg(self, tmp: Path) -> CarrierConfig:
        return CarrierConfig(
            timeout_seconds=10, raw_html_dir=tmp, save_raw_html=False
        )

    def test_registry_contains_known_carriers(self) -> None:
        self.assertIn("effi", CARRIERS)
        self.assertIn("guatex", CARRIERS)

    def test_get_carrier_normalizes_case_and_whitespace(self) -> None:
        self.assertIs(get_carrier("EFFI"), EffiCarrier)
        self.assertIs(get_carrier("  effi  "), EffiCarrier)
        self.assertIs(get_carrier("guatex"), GuatexCarrier)

    def test_get_carrier_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_carrier("fedex")

    def test_make_carrier_returns_instance_conforming_to_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance = make_carrier("effi", self._cfg(Path(tmp)))
            self.assertIsInstance(instance, EffiCarrier)
            self.assertIsInstance(instance, Carrier)
            self.assertEqual(instance.name, "effi")

    def test_guatex_stub_raises_not_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance = make_carrier("guatex", self._cfg(Path(tmp)))
            self.assertEqual(instance.name, "guatex")
            with self.assertRaises(NotImplementedError):
                instance.fetch_tracking("ABC123")


if __name__ == "__main__":
    unittest.main()
