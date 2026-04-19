from __future__ import annotations

from datetime import date
from typing import Iterable

from .models import EffiTrackingData, Rule, RuleDecision
from .utils import normalize_for_match


ANOMALIA_PATTERNS = [
    "cliente no quiso recibir",
    "cliente no quizo recibir",
    "nadie en casa",
    "direccion no corresponde",
    "dirección no corresponde",
    "cliente no llego al punto de encuentro",
    "cliente no llegó al punto de encuentro",
]


DEFAULT_RULES: list[Rule] = [
    Rule(
        id=None,
        carrier="effi",
        name="Paquete en agencia (novedad)",
        priority=10,
        enabled=True,
        estado_match_kind="any",
        estado_match_values=[],
        novelty_match_kind="contains_any_of",
        novelty_match_values=["paquete en agencia"],
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="Por recoger (INFORMADO)",
        motivo_template="Novedad de Effi indica paquete en agencia.",
        requiere_accion="Avisar al cliente que vaya a recoger",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Anomalia con novedad del cliente",
        priority=20,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["anomalia"],
        novelty_match_kind="contains_any_of",
        novelty_match_values=list(ANOMALIA_PATTERNS),
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="En novedad",
        motivo_template="Anomalia con novedad coincidente: {matched_novelty}.",
        requiere_accion="Hablar con cliente",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Devolucion",
        priority=30,
        enabled=True,
        estado_match_kind="contains_any_of",
        estado_match_values=["devolucion", "devolución"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="En Devolución",
        motivo_template="Effi reporta devolución.",
        requiere_accion="Sin accion",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Entregado",
        priority=40,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["entregado"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="ENTREGADA",
        motivo_template="Effi reporta entrega exitosa.",
        requiere_accion="Sin accion",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Ruta entrega final sin fecha",
        priority=49,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["ruta entrega final"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="no_date",
        days_threshold=None,
        estado_propuesto=None,
        motivo_template="RUTA ENTREGA FINAL sin fecha valida en historico.",
        requiere_accion="Revisar manualmente",
        review_needed=True,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Ruta entrega final estancada",
        priority=50,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["ruta entrega final"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="gt",
        days_threshold=1,
        estado_propuesto="Sin movimiento",
        motivo_template="RUTA ENTREGA FINAL con {days} dias sin cambio.",
        requiere_accion="Gestionar con encargado",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Ruta entrega final reciente",
        priority=51,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["ruta entrega final"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="lte",
        days_threshold=1,
        estado_propuesto="En ruta de entrega",
        motivo_template="RUTA ENTREGA FINAL con menos de 1 dia sin cambio.",
        requiere_accion="Monitorear",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="En ruta de entrega estancada",
        priority=60,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["en ruta de entrega"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="gt",
        days_threshold=1,
        estado_propuesto="Sin movimiento",
        motivo_template="EN RUTA DE ENTREGA con {days} dias sin cambio.",
        requiere_accion="Gestionar con encargado",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Almacenado en bodega estancado",
        priority=70,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["almacenado en bodega"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="gt",
        days_threshold=1,
        estado_propuesto="Sin movimiento",
        motivo_template="ALMACENADO EN BODEGA con {days} dias sin cambio.",
        requiere_accion="Gestionar con encargado",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
    Rule(
        id=None,
        carrier="effi",
        name="Sin recolectar estancado",
        priority=80,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["sin recolectar"],
        novelty_match_kind="any",
        novelty_match_values=[],
        days_comparator="gt",
        days_threshold=1,
        estado_propuesto="Sin movimiento",
        motivo_template="Sin Recolectar con {days} dias sin cambio.",
        requiere_accion="Gestionar con encargado",
        review_needed=False,
        notes="",
        updated_by="seed",
    ),
]


def decide_status(
    tracking: EffiTrackingData,
    today: date,
    rules: Iterable[Rule] | None = None,
    *,
    carrier: str = "effi",
) -> RuleDecision:
    """Evaluates rules (priority asc, first match wins) against tracking data.

    When rules is None, uses DEFAULT_RULES. Hardcoded fallback decisions are
    applied only when no rule matches, to keep the engine safe even with an
    empty rules table.
    """
    rule_list = list(rules) if rules is not None else DEFAULT_RULES
    rule_list = sorted(
        (r for r in rule_list if r.enabled and _carrier_matches(r.carrier, carrier)),
        key=lambda r: r.priority,
    )

    estado_raw = tracking.estado_actual or ""
    estado_norm = normalize_for_match(estado_raw)
    latest_status_date = _latest_status_date(tracking)
    latest_novelty_text = " ".join(
        normalize_for_match(f"{event.novelty} {event.details}")
        for event in tracking.novelty_history
    )

    for rule in rule_list:
        if not _estado_matches(rule, estado_norm):
            continue
        novelty_hit = _novelty_match(rule, latest_novelty_text)
        if novelty_hit is None:
            continue
        days = _days_since(latest_status_date, today)
        if not _days_matches(rule, days):
            continue
        motivo = _format_motivo(
            rule.motivo_template,
            days=days,
            estado_actual=estado_raw,
            matched_novelty=novelty_hit,
        )
        return RuleDecision(
            estado_propuesto=rule.estado_propuesto,
            motivo=motivo,
            requiere_accion=rule.requiere_accion,
            review_needed=rule.review_needed,
            matched_rule_id=rule.id,
            matched_rule_name=rule.name,
        )

    if estado_raw:
        return RuleDecision(
            estado_propuesto=None,
            motivo=f"Estado de Effi sin regla exacta: {estado_raw}.",
            requiere_accion="Revisar manualmente",
            review_needed=True,
        )
    return RuleDecision(
        estado_propuesto=None,
        motivo="No se pudo extraer el estado actual de Effi.",
        requiere_accion="Revisar manualmente",
        review_needed=True,
    )


def _carrier_matches(rule_carrier: str, carrier: str) -> bool:
    return rule_carrier == "*" or rule_carrier == carrier


def _estado_matches(rule: Rule, estado_norm: str) -> bool:
    if rule.estado_match_kind == "any":
        return True
    values = [v.casefold() for v in rule.estado_match_values]
    if rule.estado_match_kind == "equals_one_of":
        return estado_norm in values
    if rule.estado_match_kind == "contains_any_of":
        return any(v in estado_norm for v in values)
    return False


def _novelty_match(rule: Rule, novelty_text: str) -> str | None:
    """Returns the matched value (for {matched_novelty}) or '' if 'any' matched.

    Returns None when no match — the rule should be skipped.
    """
    if rule.novelty_match_kind == "any":
        return ""
    if rule.novelty_match_kind == "contains_any_of":
        for value in rule.novelty_match_values:
            needle = value.casefold()
            if needle and needle in novelty_text:
                return value
    return None


def _days_matches(rule: Rule, days: int | None) -> bool:
    comp = rule.days_comparator
    if comp is None:
        return True
    if comp == "no_date":
        return days is None
    if days is None:
        return False
    threshold = rule.days_threshold
    if threshold is None:
        return False
    if comp == "gt":
        return days > threshold
    if comp == "gte":
        return days >= threshold
    if comp == "lt":
        return days < threshold
    if comp == "lte":
        return days <= threshold
    return False


def _format_motivo(
    template: str,
    *,
    days: int | None,
    estado_actual: str,
    matched_novelty: str,
) -> str:
    days_str = str(days) if days is not None else "-"
    return template.format(
        days=days_str,
        estado_actual=estado_actual,
        estado_upper=estado_actual.upper(),
        matched_novelty=matched_novelty,
    )


def _latest_status_date(tracking: EffiTrackingData):
    dated = [event.date for event in tracking.status_history if event.date is not None]
    return max(dated) if dated else None


def _days_since(event_date, today: date) -> int | None:
    if event_date is None:
        return None
    return (today - event_date.date()).days
