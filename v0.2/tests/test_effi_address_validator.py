from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v0.4"))

from app.effi_guides.address_validator import (  # noqa: E402
    AddressValidation,
    validate_address,
)


# ── 15 BUENAS — direcciones reales aportadas por la dueña ──────────────
BUENAS = [
    "10 avenida zona 1 entre 1ra calle Enfrente dl Gimnacio CDAG",
    "Colonia las flores zona4 Por pollo granjero",
    "En Aldea el florido Aceituno escuintla carretera que ba para siquinala llamar cuando estén en la calle de la escuela frente a la iglesia católica",
    "Ampliacion mercado municipal de jutiapa local # 7 Mercado de jutiapa",
    "Cargo expres morales (quiere decir que recoge en agencia)",
    "Kilómetro 143 - Entrada a campamento caminos",
    "18 calle y 12 avenida Edificio nuvo apto 105 Edificio apartamentos atrás de paiz naranjo",
    "9 Calle 0-54 zona 3 colonia las victorias Enfrente a la vieja bodega de tecnoprosa",
    "Parcelamiento caballo blanco frente a a la farmacia flor de lis Frente a la farmacia flor de lis",
    "Km 52.5 carretera interamericana A la par de la ferretería el tejar chimaltenango",
    "5 calle 12- 51 zona uno de mixco",
    "Calle principal lote 29 a 150 metros arriba del centro de salud Llamar antes",
    "Barrio la reforma A un costado de los bomberos",
    "Agencia de cargo expreso Recoger en agenciade cargo llama",
    "Morales Cargo expreso (quiere decir que recoge en oficina cargo expreso)",
]

# ── 9 MALAS — direcciones insuficientes ────────────────────────────────
MALAS = [
    "Sentro Colotenago",
    "en mi casa",
    "Caja rural Caja rural",
    "Recibo en caja rural Recibo en caja rural",
    "Colonia la promesa La democria",
    "Lote 2 La piedrona",
    "en la iglesia",
    "La sarampaña",
    "Retalhuleu Caballo blanco",
]


class AddressValidatorRealCasesTest(unittest.TestCase):
    """Las 15 buenas DEBEN ser VALID. Las 9 malas NO deben ser VALID (REVIEW o INVALID)."""

    def test_todas_las_buenas_son_valid(self):
        failures = []
        for addr in BUENAS:
            res = validate_address(addr)
            if res.status != AddressValidation.VALID:
                failures.append(f"  {res.status.value} → {addr!r} (reasons={res.reasons})")
        if failures:
            self.fail(
                "Direcciones BUENAS marcadas como no-VALID:\n" + "\n".join(failures)
            )

    def test_ninguna_mala_es_valid(self):
        failures = []
        for addr in MALAS:
            res = validate_address(addr)
            if res.status == AddressValidation.VALID:
                failures.append(
                    f"  VALID → {addr!r} (patterns={res.matched_patterns})"
                )
        if failures:
            self.fail(
                "Direcciones MALAS marcadas como VALID:\n" + "\n".join(failures)
            )


class AddressValidatorPatternsTest(unittest.TestCase):
    """Verifica que cada patrón se identifica correctamente."""

    def test_patron_A_agencia_cargo_expreso(self):
        for addr in [
            "Cargo expres morales",
            "Agencia de cargo expreso",
            "Morales Cargo expreso",
            "Recoger en agencia de cargo",
        ]:
            res = validate_address(addr)
            self.assertEqual(res.status, AddressValidation.VALID, msg=addr)
            self.assertIn("A", res.matched_patterns, msg=addr)

    def test_patron_B_urbana_cardinal(self):
        for addr in [
            "5 calle 12-51 zona uno de mixco",
            "9 Calle 0-54 zona 3 colonia las victorias",
            "12 avenida zona 10",
        ]:
            res = validate_address(addr)
            self.assertEqual(res.status, AddressValidation.VALID, msg=addr)
            self.assertIn("B", res.matched_patterns, msg=addr)

    def test_patron_C_geografica_landmark(self):
        for addr in [
            "Aldea el florido frente a la iglesia católica",
            "Barrio la reforma a un costado de los bomberos",
            "Km 52.5 carretera interamericana a la par de la ferretería",
        ]:
            res = validate_address(addr)
            self.assertEqual(res.status, AddressValidation.VALID, msg=addr)
            self.assertIn("C", res.matched_patterns, msg=addr)

    def test_patron_D_local_interno(self):
        addr = "18 calle y 12 avenida Edificio nuevo apto 105 atras de paiz"
        res = validate_address(addr)
        self.assertEqual(res.status, AddressValidation.VALID, msg=addr)
        self.assertIn("D", res.matched_patterns, msg=addr)


class AddressValidatorTrivialTest(unittest.TestCase):
    """Direcciones triviales → INVALID inmediato."""

    def test_vacio(self):
        self.assertEqual(validate_address("").status, AddressValidation.INVALID)
        self.assertEqual(validate_address(None).status, AddressValidation.INVALID)
        self.assertEqual(validate_address("   ").status, AddressValidation.INVALID)

    def test_trivial_casa(self):
        for s in ["en mi casa", "mi casa", "casa", "EN MI CASA"]:
            self.assertEqual(
                validate_address(s).status,
                AddressValidation.INVALID,
                msg=s,
            )

    def test_trivial_iglesia(self):
        self.assertEqual(validate_address("en la iglesia").status, AddressValidation.INVALID)

    def test_caja_rural(self):
        self.assertEqual(validate_address("Caja rural").status, AddressValidation.INVALID)
        self.assertEqual(validate_address("Recibo en caja rural").status, AddressValidation.INVALID)


class AddressValidatorEdgeCasesTest(unittest.TestCase):
    """Smoke tests de robustez."""

    def test_unicode_y_acentos_no_rompen(self):
        # No raise.
        validate_address("Km 52.5 carretera ñoño á é í ó ú")

    def test_string_muy_largo(self):
        long_addr = "Aldea " + "x" * 500 + " frente a la iglesia"
        res = validate_address(long_addr)
        # No assertion sobre el status; solo que no rompa.
        self.assertIsNotNone(res)


if __name__ == "__main__":
    unittest.main()
