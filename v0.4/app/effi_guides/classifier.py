"""Clasificador puro de órdenes de Effi.

No tiene dependencias de DB, HTTP, ni Playwright. Recibe productos parseados
del modal de remisión + el catálogo, y devuelve un ProcessingPlan (la orden
se puede procesar automático) o un EscalationReason (a cola humana).

Reglas (confirmadas por el dueño 2026-05-13):

  - Pedido SOLO de productos "otro"            → contenido = 'copiar_documento'
  - Pedido SOLO de productos "intimo_femenino":
      · Combo exacto CREMA + GEL (mismas cantidades) → 'copiar_documento', valor 66*N
      · Cualquier otra composición de íntimos       → 'texto_manual', "N* PRODUCTO FEMENINO VAECOS"
  - Pedido MIXTO (íntimo + otro)               → escalation (no hay regla)
  - Productos no reconocidos                   → escalation
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Union


# El combo CREMA + GEL es el único reconocido en v1. Se identifica por SKUs
# exactos para no depender de typos en la descripción de Effi.
_COMBO_SKUS = ("CREMA ESTRECHANTE", "GEL ESTIMULANTE MULTI ORGÁSMICO")
_COMBO_VALOR_POR_PAR = 66.0


def _norm(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


@dataclass(frozen=True)
class OrderProduct:
    """Producto tal como aparece en el modal de remisión de Effi."""
    descripcion: str
    cantidad: int


@dataclass(frozen=True)
class CatalogEntry:
    """Producto registrado en effi_catalog. Construido desde CatalogItem.

    `aliases` es una tupla de variantes con las que el producto puede aparecer
    en Effi. El matcher considera descripcion_exacta + cada alias (case-insensitive,
    NFKD-strip, espacios colapsados). Sin fuzzy matching: lo que no esté listado
    explícitamente, escala a humano.
    """
    sku: str
    descripcion_exacta: str
    precio_declarado: float
    tipo: str  # 'intimo_femenino' | 'otro'
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchedItem:
    sku: str
    descripcion: str
    cantidad: int
    precio_unitario: float
    tipo: str


@dataclass(frozen=True)
class ProcessingPlan:
    """Plan de procesamiento automático para la orden."""
    kind: str                       # 'combo' | 'femenino' | 'otro'
    contenido_modo: str             # 'copiar_documento' | 'texto_manual'
    contenido_texto: str | None     # None si copiar_documento
    valor_declarado: float
    matched: tuple[MatchedItem, ...]


@dataclass(frozen=True)
class EscalationReason:
    """Motivo por el que la orden debe ir a cola humana."""
    code: str
    message: str
    details: dict = field(default_factory=dict)


ClassificationResult = Union[ProcessingPlan, EscalationReason]


def classify(
    products: list[OrderProduct],
    catalog: list[CatalogEntry],
) -> ClassificationResult:
    if not products:
        return EscalationReason(
            code="productos_vacios",
            message="La orden no tiene productos.",
        )

    # Construye el lookup: cada entrada del catálogo aporta su descripción
    # exacta + cada uno de sus aliases. Si dos productos comparten un alias
    # (no debería pasar), gana el último — el repo debería evitarlo por UI.
    by_desc: dict[str, CatalogEntry] = {}
    for c in catalog:
        by_desc[_norm(c.descripcion_exacta)] = c
        for alias in c.aliases:
            key = _norm(alias)
            if key:
                by_desc[key] = c

    matched: list[MatchedItem] = []
    unknown: list[str] = []
    for p in products:
        if p.cantidad <= 0:
            return EscalationReason(
                code="cantidad_invalida",
                message=f"Cantidad inválida ({p.cantidad}) para '{p.descripcion}'.",
                details={"descripcion": p.descripcion, "cantidad": p.cantidad},
            )
        entry = by_desc.get(_norm(p.descripcion))
        if entry is None:
            unknown.append(p.descripcion)
            continue
        matched.append(
            MatchedItem(
                sku=entry.sku,
                descripcion=p.descripcion,
                cantidad=p.cantidad,
                precio_unitario=entry.precio_declarado,
                tipo=entry.tipo,
            )
        )

    if unknown:
        return EscalationReason(
            code="producto_no_en_catalogo",
            message=f"Productos no reconocidos: {', '.join(unknown)}.",
            details={"productos_desconocidos": unknown},
        )

    tipos = {m.tipo for m in matched}

    if "intimo_femenino" in tipos and "otro" in tipos:
        return EscalationReason(
            code="pedido_mixto",
            message=(
                "La orden mezcla productos íntimos femeninos con otros productos; "
                "no hay regla automática para este caso."
            ),
            details={"items": [(m.sku, m.cantidad, m.tipo) for m in matched]},
        )

    if tipos == {"otro"}:
        valor = sum(m.precio_unitario * m.cantidad for m in matched)
        return ProcessingPlan(
            kind="otro",
            contenido_modo="copiar_documento",
            contenido_texto=None,
            valor_declarado=round(valor, 2),
            matched=tuple(matched),
        )

    # tipos == {"intimo_femenino"} — verificar combo exacto CREMA + GEL.
    skus_count = {m.sku: m.cantidad for m in matched}
    if (
        len(matched) == 2
        and set(skus_count.keys()) == set(_COMBO_SKUS)
        and skus_count[_COMBO_SKUS[0]] == skus_count[_COMBO_SKUS[1]]
    ):
        n = skus_count[_COMBO_SKUS[0]]
        return ProcessingPlan(
            kind="combo",
            contenido_modo="copiar_documento",
            contenido_texto=None,
            valor_declarado=round(_COMBO_VALOR_POR_PAR * n, 2),
            matched=tuple(matched),
        )

    # Cualquier otra composición de íntimos femeninos.
    total_units = sum(m.cantidad for m in matched)
    valor = sum(m.precio_unitario * m.cantidad for m in matched)
    return ProcessingPlan(
        kind="femenino",
        contenido_modo="texto_manual",
        contenido_texto=f"{total_units}* PRODUCTO FEMENINO VAECOS",
        valor_declarado=round(valor, 2),
        matched=tuple(matched),
    )
