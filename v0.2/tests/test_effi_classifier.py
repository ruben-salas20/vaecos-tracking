from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add v0.4/ to sys.path so we can import the effi_guides module.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v0.4"))

from app.effi_guides.classifier import (  # noqa: E402
    CatalogEntry,
    EscalationReason,
    OrderProduct,
    ProcessingPlan,
    classify,
)


def _entry(sku, desc, precio, tipo, aliases=()):
    return CatalogEntry(
        sku=sku,
        descripcion_exacta=desc,
        precio_declarado=precio,
        tipo=tipo,
        aliases=tuple(aliases),
    )


CATALOG = [
    _entry("CREMA ESTRECHANTE",                "CREMA ESTRECHANTE",                32.0, "intimo_femenino"),
    _entry("GEL ESTIMULANTE MULTI ORGÁSMICO",  "GEL ESTIMULANTE MULTI ORGÁSMICO",  34.0, "intimo_femenino"),
    _entry("INSTANT VIRGIN",                   "INSTANT VIRGIN",                   76.0, "intimo_femenino"),
    _entry("DERMAN",                           "DERMAN",                           76.0, "otro"),
    _entry("HEMOCREAM",                        "HEMOCREAM",                        71.0, "otro"),
    _entry("MOBIFLEX",                         "MOBIFLEX",                         80.0, "otro"),
    _entry("FEMPRO",                           "FEMPRO",                           95.0, "otro"),
]


class ClassifierHistoricalCasesTest(unittest.TestCase):
    """Los 4 casos reales del 2026-05-13 documentados en EFFI_AUTOMATION_HANDOFF.md §9."""

    def test_orden_5343_combo_crema_gel(self):
        """Combo CREMA + GEL × 1 → kind=combo, valor=66, copiar_documento."""
        result = classify(
            [
                OrderProduct("CREMA ESTRECHANTE", 1),
                OrderProduct("GEL ESTIMULANTE MULTI ORGÁSMICO", 1),
            ],
            CATALOG,
        )
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "combo")
        self.assertEqual(result.contenido_modo, "copiar_documento")
        self.assertIsNone(result.contenido_texto)
        self.assertEqual(result.valor_declarado, 66.0)

    def test_orden_5345_crema_x2(self):
        """CREMA × 2 → femenino, '2* PRODUCTO FEMENINO VAECOS', valor=64."""
        result = classify([OrderProduct("CREMA ESTRECHANTE", 2)], CATALOG)
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.contenido_modo, "texto_manual")
        self.assertEqual(result.contenido_texto, "2* PRODUCTO FEMENINO VAECOS")
        self.assertEqual(result.valor_declarado, 64.0)

    def test_orden_5344_crema_x1(self):
        result = classify([OrderProduct("CREMA ESTRECHANTE", 1)], CATALOG)
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.contenido_texto, "1* PRODUCTO FEMENINO VAECOS")
        self.assertEqual(result.valor_declarado, 32.0)

    def test_orden_5342_crema_x1(self):
        result = classify([OrderProduct("CREMA ESTRECHANTE", 1)], CATALOG)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.valor_declarado, 32.0)


class ClassifierComboVariantsTest(unittest.TestCase):
    """Variantes del combo y composiciones de íntimos no estándar."""

    def test_combo_con_cantidad_3(self):
        result = classify(
            [
                OrderProduct("CREMA ESTRECHANTE", 3),
                OrderProduct("GEL ESTIMULANTE MULTI ORGÁSMICO", 3),
            ],
            CATALOG,
        )
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "combo")
        self.assertEqual(result.valor_declarado, 198.0)

    def test_crema_y_gel_cantidades_distintas_no_es_combo(self):
        """CREMA × 2 + GEL × 1 → no es combo, va a femenino texto_manual."""
        result = classify(
            [
                OrderProduct("CREMA ESTRECHANTE", 2),
                OrderProduct("GEL ESTIMULANTE MULTI ORGÁSMICO", 1),
            ],
            CATALOG,
        )
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.contenido_texto, "3* PRODUCTO FEMENINO VAECOS")
        self.assertEqual(result.valor_declarado, 32.0 * 2 + 34.0)

    def test_intimos_no_combo_instant_virgin(self):
        """INSTANT VIRGIN × 1 → femenino, '1* PRODUCTO FEMENINO VAECOS', valor=76."""
        result = classify([OrderProduct("INSTANT VIRGIN", 1)], CATALOG)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.contenido_texto, "1* PRODUCTO FEMENINO VAECOS")
        self.assertEqual(result.valor_declarado, 76.0)

    def test_intimos_no_combo_tres_productos(self):
        """CREMA + GEL + INSTANT VIRGIN → no es combo (3 items), femenino texto_manual."""
        result = classify(
            [
                OrderProduct("CREMA ESTRECHANTE", 1),
                OrderProduct("GEL ESTIMULANTE MULTI ORGÁSMICO", 1),
                OrderProduct("INSTANT VIRGIN", 1),
            ],
            CATALOG,
        )
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.contenido_texto, "3* PRODUCTO FEMENINO VAECOS")
        self.assertEqual(result.valor_declarado, 32.0 + 34.0 + 76.0)


class ClassifierOtrosTest(unittest.TestCase):
    def test_derman_x2(self):
        result = classify([OrderProduct("DERMAN", 2)], CATALOG)
        self.assertEqual(result.kind, "otro")
        self.assertEqual(result.contenido_modo, "copiar_documento")
        self.assertIsNone(result.contenido_texto)
        self.assertEqual(result.valor_declarado, 152.0)

    def test_hemocream_x3(self):
        result = classify([OrderProduct("HEMOCREAM", 3)], CATALOG)
        self.assertEqual(result.kind, "otro")
        self.assertEqual(result.valor_declarado, 213.0)

    def test_combo_otros_mobiflex_fempro(self):
        """MOBIFLEX × 1 + FEMPRO × 2 → otro, copiar_documento, valor=80+190=270."""
        result = classify(
            [OrderProduct("MOBIFLEX", 1), OrderProduct("FEMPRO", 2)],
            CATALOG,
        )
        self.assertEqual(result.kind, "otro")
        self.assertEqual(result.valor_declarado, 80.0 + 2 * 95.0)


class ClassifierEscalationTest(unittest.TestCase):
    def test_pedido_mixto_femenino_y_otro(self):
        """CREMA + DERMAN → pedido_mixto."""
        result = classify(
            [OrderProduct("CREMA ESTRECHANTE", 1), OrderProduct("DERMAN", 1)],
            CATALOG,
        )
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "pedido_mixto")

    def test_producto_no_en_catalogo(self):
        result = classify(
            [OrderProduct("PRODUCTO DESCONOCIDO XYZ", 1)],
            CATALOG,
        )
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "producto_no_en_catalogo")

    def test_productos_vacios(self):
        result = classify([], CATALOG)
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "productos_vacios")

    def test_cantidad_invalida_cero(self):
        result = classify([OrderProduct("DERMAN", 0)], CATALOG)
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "cantidad_invalida")

    def test_cantidad_invalida_negativa(self):
        result = classify([OrderProduct("DERMAN", -1)], CATALOG)
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "cantidad_invalida")


class ClassifierNormalizationTest(unittest.TestCase):
    """El matching debe ser tolerante a acentos y espacios extras."""

    def test_descripcion_con_espacios_extra(self):
        result = classify([OrderProduct("  DERMAN  ", 1)], CATALOG)
        self.assertEqual(result.kind, "otro")

    def test_descripcion_lowercase(self):
        result = classify([OrderProduct("derman", 1)], CATALOG)
        self.assertEqual(result.kind, "otro")

    def test_gel_sin_acento_matchea(self):
        """Effi puede devolver el texto sin tilde — debe matchear igual."""
        result = classify(
            [
                OrderProduct("CREMA ESTRECHANTE", 1),
                OrderProduct("GEL ESTIMULANTE MULTI ORGASMICO", 1),
            ],
            CATALOG,
        )
        self.assertEqual(result.kind, "combo")


class ClassifierAliasesTest(unittest.TestCase):
    """El matching debe resolver descripciones registradas como alias."""

    def _catalog_with_aliases(self):
        return [
            _entry(
                "CREMA ESTRECHANTE",
                "CREMA ESTRECHANTE",
                32.0,
                "intimo_femenino",
                aliases=("ESTRECHANTE", "CR ESTRECHANTE"),
            ),
            _entry(
                "GEL ESTIMULANTE MULTI ORGÁSMICO",
                "GEL ESTIMULANTE MULTI ORGÁSMICO",
                34.0,
                "intimo_femenino",
                aliases=("GEL ESTIMULANTE", "GEL MULTI ORGASMICO"),
            ),
            _entry("DERMAN", "DERMAN", 76.0, "otro", aliases=("DERMAN CREMA",)),
        ]

    def test_alias_simple_resuelve_a_sku_correcto(self):
        """Si Effi devuelve 'ESTRECHANTE', se mapea a CREMA ESTRECHANTE."""
        catalog = self._catalog_with_aliases()
        result = classify([OrderProduct("ESTRECHANTE", 1)], catalog)
        self.assertIsInstance(result, ProcessingPlan)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.matched[0].sku, "CREMA ESTRECHANTE")
        self.assertEqual(result.valor_declarado, 32.0)

    def test_alias_case_insensitive(self):
        catalog = self._catalog_with_aliases()
        result = classify([OrderProduct("estrechante", 2)], catalog)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.matched[0].sku, "CREMA ESTRECHANTE")
        self.assertEqual(result.valor_declarado, 64.0)

    def test_combo_via_aliases(self):
        """Si CREMA aparece como 'ESTRECHANTE' y GEL como 'GEL ESTIMULANTE', el combo se reconoce."""
        catalog = self._catalog_with_aliases()
        result = classify(
            [
                OrderProduct("ESTRECHANTE", 1),
                OrderProduct("GEL ESTIMULANTE", 1),
            ],
            catalog,
        )
        self.assertEqual(result.kind, "combo")
        self.assertEqual(result.valor_declarado, 66.0)

    def test_alias_para_producto_otro(self):
        catalog = self._catalog_with_aliases()
        result = classify([OrderProduct("DERMAN CREMA", 1)], catalog)
        self.assertEqual(result.kind, "otro")
        self.assertEqual(result.matched[0].sku, "DERMAN")
        self.assertEqual(result.valor_declarado, 76.0)

    def test_descripcion_no_listada_en_aliases_escala(self):
        catalog = self._catalog_with_aliases()
        result = classify([OrderProduct("CREMA ESTRECHANTE 30G", 1)], catalog)
        self.assertIsInstance(result, EscalationReason)
        self.assertEqual(result.code, "producto_no_en_catalogo")

    def test_descripcion_exacta_sigue_funcionando(self):
        """Agregar aliases no debe romper el match por descripción exacta original."""
        catalog = self._catalog_with_aliases()
        result = classify([OrderProduct("CREMA ESTRECHANTE", 1)], catalog)
        self.assertEqual(result.kind, "femenino")
        self.assertEqual(result.matched[0].sku, "CREMA ESTRECHANTE")


if __name__ == "__main__":
    unittest.main()
