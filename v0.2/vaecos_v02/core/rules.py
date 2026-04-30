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
    "cliente no llego a punto de encuentro",
    "cliente no llegó al punto de encuentro",
    "cliente no llegó a punto de encuentro",
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
        name="Almacenado en bodega con novedad de cliente",
        priority=25,
        enabled=True,
        estado_match_kind="equals_one_of",
        estado_match_values=["almacenado en bodega"],
        novelty_match_kind="contains_any_of",
        novelty_match_values=list(ANOMALIA_PATTERNS),
        days_comparator=None,
        days_threshold=None,
        estado_propuesto="En novedad",
        motivo_template="Almacenado en bodega con novedad coincidente: {matched_novelty}.",
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


# ── rule classification helpers (semantic, no schema change) ──────────


def _terminal(rule: Rule) -> bool:
    """Rule whose estado_propuesto is a definitive end state (delivered / returned)."""
    return rule.estado_propuesto in {"ENTREGADA", "En Devolución"}


def _stagnation(rule: Rule) -> bool:
    """Rule that depends on days-since-last-status (days_comparator is not None)."""
    return rule.days_comparator is not None


def _contextual(rule: Rule) -> bool:
    """Rule that matches against novelty text and is not a terminal rule."""
    return rule.novelty_match_kind != "any" and not _terminal(rule)


def _operational(rule: Rule) -> bool:
    """Any remaining rule not classified as terminal, contextual, or stagnation."""
    return not _terminal(rule) and not _contextual(rule) and not _stagnation(rule)


def _latest_relevant_novelty_text(tracking: EffiTrackingData) -> str:
    """Return the normalized text of the most recent novelty event.

    Uses only the latest event (by date) to avoid old contextual signals
    leaking into current decisions.  Returns '' when there are no events.
    """
    dated = [ev for ev in tracking.novelty_history if ev.date is not None]
    if not dated:
        return ""
    # All items in dated have non-None .date after the filter above.
    latest = max(dated, key=lambda ev: ev.date)  # type: ignore[arg-type]
    return normalize_for_match(f"{latest.novelty} {latest.details}")


def _try_match_in_group(
    rules: list[Rule],
    *,
    estado_norm: str,
    novelty_text: str,
    days: int | None,
    estado_raw: str,
) -> RuleDecision | None:
    """Evaluate a group of rules (already sorted by priority ASC).

    Returns the decision of the first matching rule, or None if no rule
    matches in this group.
    """
    for rule in rules:
        if not _estado_matches(rule, estado_norm):
            continue
        novelty_hit = _novelty_match(rule, novelty_text)
        if novelty_hit is None:
            continue
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
    return None


# ── cooldown helpers ──────────────────────────────────────────────────


def is_gestation_cooldown_active(
    notion_estado: str,
    decision: RuleDecision,
    fecha_ultimo_seguimiento: str | None,
    today: date,
) -> bool:
    """Determine if the Gestión novedad 2-day cooldown should block a change.

    Purpose:
    When a guide in Notion is ``Gestión novedad`` and the rule engine
    proposes ``En novedad`` (from ANOMALIA or ALMACENADO EN BODEGA rules),
    the update SHALL be blocked for 2 calendar days since the last
    seguimiento date.

    Terminal outcomes (``ENTREGADA``, ``En Devolución``) and contextual
    progress signals (``Por recoger (INFORMADO)``, ``En ruta de entrega``)
    are automatically bypassed because they produce a different
    ``estado_propuesto`` value.

    Returns ``True`` when ALL conditions are met:
    1. Notion status is exactly ``"Gestión novedad"``
    2. The decision's ``estado_propuesto`` is ``"En novedad"``
    3. ``review_needed`` is ``False``
    4. ``fecha_ultimo_seguimiento`` is a parseable ISO date
    5. Fewer than 2 calendar days have elapsed since that date
    """
    if notion_estado != "Gestión novedad":
        return False
    if decision.estado_propuesto != "En novedad":
        return False
    if decision.review_needed:
        return False
    if not fecha_ultimo_seguimiento:
        return False  # cannot determine cooldown without a date

    try:
        last_date = date.fromisoformat(fecha_ultimo_seguimiento)
    except (ValueError, TypeError):
        return False

    return (today - last_date).days < 2


def classify_result_with_cooldown(
    decision: RuleDecision,
    notion_estado: str,
    fecha_ultimo_seguimiento: str | None,
    today: date,
) -> tuple[str, str, str, str | None]:
    """Classify the processing result, factoring in the Gestión novedad cooldown.

    Returns:
        ``(resultado, motivo, accion, estado_propuesto)`` where
        ``resultado`` is one of ``"changed"``, ``"unchanged"``, or
        ``"manual_review"``, and ``estado_propuesto`` is the state to
        display in the report.

        When the cooldown is active, ``estado_propuesto`` is set to
        ``"Gestión novedad"`` (suggesting the operator keep the current
        state) and the motivo is phrased in business terms without
        exposing technical cooldown jargon.

        When the cooldown is NOT active, ``estado_propuesto`` is the
        value from the rule decision unchanged.
    """
    if is_gestation_cooldown_active(
        notion_estado=notion_estado,
        decision=decision,
        fecha_ultimo_seguimiento=fecha_ultimo_seguimiento,
        today=today,
    ):
        return (
            "unchanged",
            "Se mantiene Gestión novedad. La guía fue revisada en los últimos 2 días.",
            "No aplica",
            "Gestión novedad",
        )

    if decision.review_needed:
        return ("manual_review", decision.motivo, decision.requiere_accion, decision.estado_propuesto)
    if decision.estado_propuesto == notion_estado:
        return ("unchanged", decision.motivo, decision.requiere_accion, decision.estado_propuesto)
    return ("changed", decision.motivo, decision.requiere_accion, decision.estado_propuesto)


# ── public API ──────────────────────────────────────────────────────────


def decide_status(
    tracking: EffiTrackingData,
    today: date,
    rules: Iterable[Rule] | None = None,
    *,
    carrier: str = "effi",
) -> RuleDecision:
    """Evaluate rules in stratified semantic order: terminal → operational →
    contextual (latest novelty only) → stagnation.

    Terminal outcomes (ENTREGADA, En Devolución) are evaluated first and,
    if matched, returned immediately.  Contextual rules use only the
    latest relevant novelty to avoid old signals leaking into current
    decisions.

    When *rules* is None the engine falls back to DEFAULT_RULES.  A
    hardcoded fallback decision is returned only when no rule matches.
    """
    rule_list = list(rules) if rules is not None else DEFAULT_RULES
    rule_list = sorted(
        (r for r in rule_list if r.enabled and _carrier_matches(r.carrier, carrier)),
        key=lambda r: r.priority,
    )

    estado_raw = tracking.estado_actual or ""
    estado_norm = normalize_for_match(estado_raw)
    latest_status_date = _latest_status_date(tracking)
    days = _days_since(latest_status_date, today)

    # Partition into semantic groups (priority ASC within each group)
    terminal_rules = [r for r in rule_list if _terminal(r)]
    operational_rules = [r for r in rule_list if _operational(r)]
    contextual_rules = [r for r in rule_list if _contextual(r)]
    stagnation_rules = [r for r in rule_list if _stagnation(r)]

    latest_rel_novelty = _latest_relevant_novelty_text(tracking)

    # ── phase 1: terminal rules ──────────────────────────────────────
    decision = _try_match_in_group(
        terminal_rules,
        estado_norm=estado_norm,
        novelty_text="",
        days=days,
        estado_raw=estado_raw,
    )
    if decision is not None:
        return decision

    # ── phase 2: operational rules ───────────────────────────────────
    decision = _try_match_in_group(
        operational_rules,
        estado_norm=estado_norm,
        novelty_text="",
        days=days,
        estado_raw=estado_raw,
    )
    if decision is not None:
        return decision

    # ── phase 3: contextual rules (latest novelty only) ─────────────
    decision = _try_match_in_group(
        contextual_rules,
        estado_norm=estado_norm,
        novelty_text=latest_rel_novelty,
        days=days,
        estado_raw=estado_raw,
    )
    if decision is not None:
        return decision

    # ── phase 4: stagnation rules ────────────────────────────────────
    decision = _try_match_in_group(
        stagnation_rules,
        estado_norm=estado_norm,
        novelty_text="",
        days=days,
        estado_raw=estado_raw,
    )
    if decision is not None:
        return decision

    # ── fallback ──────────────────────────────────────────────────────
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
