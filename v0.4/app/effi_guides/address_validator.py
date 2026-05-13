"""Validador de direcciones para órdenes CARGO EXPRESO Guatemala.

Diseñado contra el doc `docs/direcciones.md` (15 buenas + 9 malas reales).

Patrones VÁLIDOS (basta con UNO):
  A. Agencia / retiro en oficina CARGO EXPRESO
  B. Estructura urbana cardinal: calle/avenida + zona N (no requiere landmark)
  C. Ubicación geográfica (aldea/colonia/barrio/...) + referencia con landmark
  D. Local interno identificable (mercado X local N, edificio Y apto Z)
     — requiere también ubicación, landmark, o estructura cardinal.

Salida:
  - VALID   : matchea ≥ 1 patrón → procesar automático.
  - REVIEW  : matchea parcial (ubicación sin referencia, etc.) → cola humana.
  - INVALID : ningún patrón ni componente → cola humana con motivo claro.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class AddressValidation(str, Enum):
    VALID = "valid"
    REVIEW = "review"
    INVALID = "invalid"


@dataclass(frozen=True)
class AddressResult:
    status: AddressValidation
    matched_patterns: tuple[str, ...]
    reasons: tuple[str, ...]
    normalized: str


def _normalize(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


# ── Patrón A: agencia / retiro en oficina ────────────────────────────────
_RE_AGENCIA = re.compile(
    r"(cargo\s*expres(o|s|os)?\b"            # cargo expreso / cargo expres
    r"|agencia\s+de\s+cargo"
    r"|agencia\s*\w*\s*cargo"                # agencia de cargo, agenciade cargo
    r"|recog(er|e)\s+en\s+(agencia|oficina))",
    re.IGNORECASE,
)

# ── Patrón B: estructura urbana cardinal ────────────────────────────────
# Variantes: "5 calle", "9 calle 0-54", "12 avenida", "av. 12",
# "5ta avenida", "1ra calle", "2da avenida", "10ma calle"
_RE_CALLE_O_AVENIDA = re.compile(
    r"(\b\d+(ra|da|ta|na|ma|va|to|do|er|mo|no)?\s*(calle|avenida|av\.?)\b"
    r"|\b(calle|avenida|av\.?)\s+\d+(ra|da|ta|na|ma|va|to|do|er|mo|no)?\b"
    r"|\bcalle\s+principal\b)",
    re.IGNORECASE,
)
# "zona N" o forma abreviada "z N", "z.N", "z14" — todas valen como zona.
_RE_ZONA = re.compile(
    r"("
    r"\bzona\s+("
    r"\d{1,2}"
    r"|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez"
    r"|once|doce|trece|catorce|quince|dieciseis|diecisiete|dieciocho|diecinueve|veinte"
    r"|veintiuno|veintidos|veintitres|veinticuatro|veinticinco"
    r")\b"
    r"|\bz\.?\s*\d{1,2}\b"          # "z 14", "z.14", "z14"
    r")",
    re.IGNORECASE,
)

# ── Patrón C: geográfica + referencia ────────────────────────────────────
_RE_UBICACION = re.compile(
    r"\b("
    r"aldea|colonia|barrio|canton|caserio|"
    r"parcelamiento|finca|parcela|lote|"
    r"km|kilometro|carretera|"
    r"ampliacion(?:\s+\w+)?"                 # ampliación mercado
    r")\b",
    re.IGNORECASE,
)
_RE_REFERENCIA_PREP = re.compile(
    r"\b("
    r"frente|enfrente|al\s+lado|a\s+un\s+costado|costado|"
    r"atras|cerca|"
    r"a\s+la\s+par|a\s+\d+(\.\d+)?\s*(metros|mts|km)|"
    r"antes\s+de|despues\s+de|"
    r"por\s+(el|la|los|las|donde|pollo|cerca)|"
    r"entrada\s+a|entrada\s+al"
    r")\b",
    re.IGNORECASE,
)
# Landmarks comunes en direcciones rurales/urbanas guatemaltecas.
# Se amplia con galerías/plaza/centro comercial/torre (puntos de referencia urbanos).
_RE_LANDMARK = re.compile(
    r"\b("
    r"iglesia|escuela|farmacia|gimnasio|gimnacio|gym|"
    r"mercado|ferreteria|bomberos|"
    r"centro\s+de\s+salud|hospital|"
    r"tienda|panaderia|carniceria|"
    r"parque|cancha|estadio|policia|municipalidad|colegio|universidad|"
    r"banco|cooperativa|restaurante|pollo\s+granjero|pollo\s+\w+|"
    r"comedor|bodega|edificio|cdag|"
    r"paiz|despensa|maxi\s*despensa|walmart|"
    r"galerias|galeria|plaza|centro\s+comercial|c\.?c\.?|"
    r"torre|condominio|residencial|"
    r"campamento|caminos"
    r")\b",
    re.IGNORECASE,
)

# ── Patrón D: local interno identificable ───────────────────────────────
_RE_LOCAL_INTERNO = re.compile(
    r"\b("
    r"local\s*#?\s*\d+"
    r"|apto\.?\s*#?\s*\d+"
    r"|apartamento\s+\d+"
    r"|oficina\s+\d+"
    r"|nivel\s+\d+"
    r")\b",
    re.IGNORECASE,
)

# ── Anti-patrones triviales → INVALID directo ───────────────────────────
_TRIVIAL_PATTERNS = [
    re.compile(r"^\s*en\s+mi\s+casa\s*$", re.IGNORECASE),
    re.compile(r"^\s*mi\s+casa\s*$", re.IGNORECASE),
    re.compile(r"^\s*casa\s*$", re.IGNORECASE),
    re.compile(r"^\s*en\s+la\s+iglesia\s*$", re.IGNORECASE),
    re.compile(r"^\s*caja\s+rural", re.IGNORECASE),
    re.compile(r"^\s*recibo\s+en\s+caja", re.IGNORECASE),
]


def validate_address(address: str | None) -> AddressResult:
    raw = (address or "").strip()
    normalized = _normalize(raw)

    if not normalized:
        return AddressResult(
            status=AddressValidation.INVALID,
            matched_patterns=(),
            reasons=("dirección vacía",),
            normalized=normalized,
        )

    if len(normalized) < 6:
        return AddressResult(
            status=AddressValidation.INVALID,
            matched_patterns=(),
            reasons=("dirección demasiado corta",),
            normalized=normalized,
        )

    for pat in _TRIVIAL_PATTERNS:
        if pat.match(normalized):
            return AddressResult(
                status=AddressValidation.INVALID,
                matched_patterns=(),
                reasons=("dirección trivial sin ubicación concreta",),
                normalized=normalized,
            )

    matched: list[str] = []
    reasons: list[str] = []

    if _RE_AGENCIA.search(normalized):
        matched.append("A")
        reasons.append("retiro en agencia CARGO EXPRESO")

    has_calle_avenida = bool(_RE_CALLE_O_AVENIDA.search(normalized))
    has_zona = bool(_RE_ZONA.search(normalized))
    has_ubicacion = bool(_RE_UBICACION.search(normalized))
    has_ref_prep = bool(_RE_REFERENCIA_PREP.search(normalized))
    has_landmark = bool(_RE_LANDMARK.search(normalized))
    has_local_interno = bool(_RE_LOCAL_INTERNO.search(normalized))

    if has_calle_avenida and has_zona:
        matched.append("B")
        reasons.append("estructura urbana cardinal (calle/avenida + zona)")

    has_reference = (has_ref_prep and has_landmark) or has_landmark and (
        # "a la par de la ferretería" o "frente a la iglesia"
        _RE_REFERENCIA_PREP.search(normalized) is not None
    )

    if has_ubicacion and (has_ref_prep and has_landmark):
        matched.append("C")
        reasons.append("ubicación geográfica + referencia con landmark")

    if has_local_interno and (has_ubicacion or has_landmark or has_calle_avenida):
        matched.append("D")
        reasons.append("local interno identificable con contexto geográfico")

    if matched:
        return AddressResult(
            status=AddressValidation.VALID,
            matched_patterns=tuple(matched),
            reasons=tuple(reasons),
            normalized=normalized,
        )

    # Si llegó hasta aquí, no matcheó ningún patrón completo.
    # Decidimos REVIEW vs INVALID según señales parciales.
    review_reasons: list[str] = []
    if has_ubicacion and not (has_ref_prep and has_landmark):
        review_reasons.append("ubicación nominal sin landmark claro")
    if (has_ref_prep or has_landmark) and not has_ubicacion and not has_calle_avenida:
        review_reasons.append("referencia/landmark sin ubicación geográfica")
    if has_zona and not has_calle_avenida:
        review_reasons.append("zona sin calle/avenida")
    if has_calle_avenida and not has_zona and not has_landmark:
        review_reasons.append("calle/avenida sin zona ni landmark")
    if has_local_interno and not (has_ubicacion or has_landmark or has_calle_avenida):
        review_reasons.append("local interno sin contexto geográfico")

    if review_reasons:
        return AddressResult(
            status=AddressValidation.REVIEW,
            matched_patterns=(),
            reasons=tuple(review_reasons),
            normalized=normalized,
        )

    return AddressResult(
        status=AddressValidation.INVALID,
        matched_patterns=(),
        reasons=("no matchea ningún patrón válido reconocible",),
        normalized=normalized,
    )
