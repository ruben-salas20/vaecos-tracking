from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

from vaecos_v02.core.models import (
    EffiNovedadEvent,
    EffiStatusEvent,
    EffiTrackingData,
    Rule,
)
from vaecos_v02.core.rules import decide_status
from vaecos_v02.storage.db import connect as v02_connect
from vaecos_v02.storage.rules_repository import RulesRepository

from vaecos_v03.render import (
    alert,
    button,
    carrier_badge,
    h,
    hero,
    layout,
    panel,
    table,
)


_ESTADO_KIND_LABELS = {
    "any": "Cualquiera",
    "equals_one_of": "Igual a",
    "contains_any_of": "Contiene",
}
_NOVELTY_KIND_LABELS = {
    "any": "Cualquiera",
    "contains_any_of": "Contiene",
}
_DAYS_COMP_LABELS = {
    "": "Sin regla de dias",
    "gt": "Mayor que",
    "gte": "Mayor o igual que",
    "lt": "Menor que",
    "lte": "Menor o igual que",
    "no_date": "Sin fecha valida",
}


# ---------------------------------------------------------------- list view
def render_rules_list(db_path: Path, flash: str | None = None) -> str:
    conn = v02_connect(db_path)
    try:
        rules = RulesRepository(conn).list_rules()
    finally:
        conn.close()

    actions = (
        button("/rules/new", "Crear regla")
        + button("/rules/preview", "Vista previa", "ghost")
        + button("/", "Volver al inicio", "ghost")
    )
    body = hero(
        "Reglas",
        "Decisiones que VAECOS aplica automaticamente a cada guia. La primera regla que coincide, por prioridad ascendente, es la que gana.",
        actions,
    )
    if flash:
        body += alert(flash, "ok")

    if not rules:
        body += panel("<p class='muted'>Aun no hay reglas. Se sembraran automaticamente en la proxima corrida.</p>")
        return layout("Reglas", body)

    rows = [_render_rule_row(rule) for rule in rules]
    body += table(
        [
            "Prio",
            "Nombre",
            "Transportista",
            "Estado",
            "Novedad",
            "Dias",
            "Propuesto",
            "Accion requerida",
            "Estado",
            "Acciones",
        ],
        rows,
    )
    body += panel(
        "<p class='muted' style='margin:0;font-size:.82rem'>"
        "Los cambios entran en vigor en la siguiente corrida. Cada edicion queda registrada en el historial de la regla."
        "</p>"
    )
    return layout("Reglas", body)


def _render_rule_row(rule: Rule) -> list[str]:
    estado_cell = _format_match(
        rule.estado_match_kind, rule.estado_match_values, _ESTADO_KIND_LABELS
    )
    novelty_cell = _format_match(
        rule.novelty_match_kind, rule.novelty_match_values, _NOVELTY_KIND_LABELS
    )
    days_cell = _format_days(rule.days_comparator, rule.days_threshold)
    propuesto = escape(rule.estado_propuesto or "-")
    accion = escape(rule.requiere_accion or "-")
    status_pill = (
        '<span class="pill pill-apply">activa</span>'
        if rule.enabled
        else '<span class="pill pill-unchanged">inactiva</span>'
    )
    actions_html = (
        f'<form method="post" action="/rules/{rule.id}/toggle" style="display:inline">'
        f'<button class="button ghost" type="submit">{"Desactivar" if rule.enabled else "Activar"}</button>'
        '</form> '
        f'<a class="button ghost" href="/rules/{rule.id}/edit">Editar</a> '
        f'<a class="button ghost" href="/rules/{rule.id}/history">Historial</a>'
    )
    name_cell = (
        f'<strong>{escape(rule.name)}</strong>'
        + (f'<br><span class="muted" style="font-size:.78rem">{escape(rule.notes)}</span>' if rule.notes else "")
    )
    return [
        str(rule.priority),
        name_cell,
        carrier_badge(rule.carrier),
        estado_cell,
        novelty_cell,
        days_cell,
        propuesto,
        accion,
        status_pill,
        actions_html,
    ]


def _format_match(kind: str, values: list[str], labels: dict[str, str]) -> str:
    label = labels.get(kind, kind)
    if kind == "any" or not values:
        return f'<span class="muted">{escape(label)}</span>'
    joined = ", ".join(escape(v) for v in values[:3])
    if len(values) > 3:
        joined += f' <span class="muted">+{len(values) - 3}</span>'
    return f'<strong>{escape(label)}</strong>: {joined}'


def _format_days(comparator: str | None, threshold: int | None) -> str:
    if comparator is None:
        return '<span class="muted">Sin regla</span>'
    if comparator == "no_date":
        return '<strong>Sin fecha valida</strong>'
    sym = {"gt": "&gt;", "gte": "&gt;=", "lt": "&lt;", "lte": "&lt;="}.get(comparator, comparator)
    return f'<strong>{sym}</strong> {threshold if threshold is not None else "?"} dias'


# --------------------------------------------------------------- edit form
def render_rule_form(
    db_path: Path,
    rule_id: int | None = None,
    form_data: dict | None = None,
    errors: list[str] | None = None,
) -> str:
    rule: Rule | None = None
    if rule_id is not None:
        conn = v02_connect(db_path)
        try:
            rule = RulesRepository(conn).get_rule(rule_id)
        finally:
            conn.close()
        if rule is None:
            return layout(
                "Regla no encontrada",
                hero("Regla no encontrada", f"No existe la regla {rule_id}.")
                + panel(button("/rules", "Volver a reglas", "ghost")),
            )

    data = form_data or _rule_to_form_dict(rule)
    title = f"Editar regla #{rule.id}" if rule else "Nueva regla"
    subtitle = (
        "Ajusta los criterios de coincidencia y la decision propuesta."
        if rule
        else "Define una nueva regla. La primera que coincide (por prioridad ascendente) es la que gana."
    )
    body = hero(title, subtitle, button("/rules", "Volver a reglas", "ghost"))

    if errors:
        for err in errors:
            body += alert(err)

    action = f"/rules/{rule.id}/edit" if rule else "/rules/new"
    body += panel(_rule_form_html(action, data))
    if rule is not None:
        body += panel(
            f'<form method="post" action="/rules/{rule.id}/delete" '
            'onsubmit="return confirm(\'Eliminar la regla definitivamente?\')" '
            'style="display:inline">'
            '<button class="button secondary" type="submit">Eliminar regla</button>'
            "</form>"
        )
    return layout(title, body)


def _rule_form_html(action: str, data: dict) -> str:
    estado_values_text = "\n".join(data.get("estado_match_values", []))
    novelty_values_text = "\n".join(data.get("novelty_match_values", []))
    days_comparator = data.get("days_comparator") or ""
    days_threshold = data.get("days_threshold", "")
    estado_kind = data.get("estado_match_kind", "any")
    novelty_kind = data.get("novelty_match_kind", "any")
    enabled_checked = "checked" if data.get("enabled", True) else ""
    review_checked = "checked" if data.get("review_needed", False) else ""

    def _sel(options: list[tuple[str, str]], current: str) -> str:
        return "".join(
            f'<option value="{escape(v)}" {"selected" if v == current else ""}>{escape(l)}</option>'
            for v, l in options
        )

    estado_kind_options = [
        ("any", "Cualquier estado"),
        ("equals_one_of", "Igual a alguno de..."),
        ("contains_any_of", "Contiene alguno de..."),
    ]
    novelty_kind_options = [
        ("any", "Cualquier novedad"),
        ("contains_any_of", "Contiene alguno de..."),
    ]
    days_options = [
        ("", "Sin regla de dias"),
        ("gt", "Mayor que (dias > N)"),
        ("gte", "Mayor o igual (dias >= N)"),
        ("lt", "Menor que (dias < N)"),
        ("lte", "Menor o igual (dias <= N)"),
        ("no_date", "Sin fecha valida en historico"),
    ]
    carrier_options = [
        ("effi", "Effi (Cargo Expreso)"),
        ("guatex", "Guatex (proximamente)"),
        ("*", "Cualquier transportista"),
    ]

    return f"""
    <form class="stack" method="post" action="{escape(action)}">
      <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:14px">
        <label>Nombre
          <input type="text" name="name" value="{escape(data.get("name", ""))}" required>
        </label>
        <label>Prioridad
          <input type="number" name="priority" value="{escape(str(data.get("priority", 100)))}" required min="0">
        </label>
        <label>Transportista
          <select name="carrier">{_sel(carrier_options, data.get("carrier", "effi"))}</select>
        </label>
      </div>

      <div class="section"><h2>Coincidencia de estado</h2></div>
      <div style="display:grid;grid-template-columns:1fr 2fr;gap:14px">
        <label>Tipo de match
          <select name="estado_match_kind">{_sel(estado_kind_options, estado_kind)}</select>
        </label>
        <label>Valores (uno por linea)
          <textarea name="estado_match_values" placeholder="Uno por linea. Ej: entregado">{escape(estado_values_text)}</textarea>
        </label>
      </div>

      <div class="section"><h2>Coincidencia de novedad</h2></div>
      <div style="display:grid;grid-template-columns:1fr 2fr;gap:14px">
        <label>Tipo de match
          <select name="novelty_match_kind">{_sel(novelty_kind_options, novelty_kind)}</select>
        </label>
        <label>Valores (uno por linea)
          <textarea name="novelty_match_values" placeholder="Uno por linea. Ej: paquete en agencia">{escape(novelty_values_text)}</textarea>
        </label>
      </div>

      <div class="section"><h2>Antiguedad del ultimo estado</h2></div>
      <div style="display:grid;grid-template-columns:2fr 1fr;gap:14px">
        <label>Comparador
          <select name="days_comparator">{_sel(days_options, days_comparator)}</select>
        </label>
        <label>Umbral (dias)
          <input type="number" name="days_threshold" value="{escape(str(days_threshold) if days_threshold != "" else "")}" min="0">
        </label>
      </div>

      <div class="section"><h2>Decision propuesta</h2></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
        <label>Estado propuesto (Notion)
          <input type="text" name="estado_propuesto" value="{escape(data.get("estado_propuesto") or "")}" placeholder="Ej: Sin movimiento">
        </label>
        <label>Accion requerida
          <input type="text" name="requiere_accion" value="{escape(data.get("requiere_accion", ""))}" placeholder="Ej: Gestionar con encargado">
        </label>
      </div>
      <label>Motivo (plantilla)
        <textarea name="motivo_template" required>{escape(data.get("motivo_template", ""))}</textarea>
      </label>
      <p class="muted" style="font-size:.78rem;margin:-6px 0 4px">
        Marcadores disponibles: <code>{{days}}</code>, <code>{{estado_actual}}</code>,
        <code>{{estado_upper}}</code>, <code>{{matched_novelty}}</code>.
      </p>

      <label>Notas (opcional)
        <textarea name="notes" placeholder="Por que existe esta regla, quien la pidio, etc.">{escape(data.get("notes", ""))}</textarea>
      </label>

      <div style="display:flex;gap:18px;flex-wrap:wrap">
        <label style="flex-direction:row;align-items:center;gap:8px">
          <input type="checkbox" name="enabled" {enabled_checked}> Regla activa
        </label>
        <label style="flex-direction:row;align-items:center;gap:8px">
          <input type="checkbox" name="review_needed" {review_checked}> Forzar revision manual
        </label>
      </div>

      <div class="toolbar">
        <button type="submit">Guardar</button>
        <a class="button ghost" href="/rules">Cancelar</a>
      </div>
    </form>
    """


def _rule_to_form_dict(rule: Rule | None) -> dict:
    if rule is None:
        return {
            "name": "",
            "priority": 100,
            "carrier": "effi",
            "enabled": True,
            "estado_match_kind": "any",
            "estado_match_values": [],
            "novelty_match_kind": "any",
            "novelty_match_values": [],
            "days_comparator": "",
            "days_threshold": "",
            "estado_propuesto": "",
            "motivo_template": "",
            "requiere_accion": "",
            "review_needed": False,
            "notes": "",
        }
    return {
        "name": rule.name,
        "priority": rule.priority,
        "carrier": rule.carrier,
        "enabled": rule.enabled,
        "estado_match_kind": rule.estado_match_kind,
        "estado_match_values": list(rule.estado_match_values),
        "novelty_match_kind": rule.novelty_match_kind,
        "novelty_match_values": list(rule.novelty_match_values),
        "days_comparator": rule.days_comparator or "",
        "days_threshold": rule.days_threshold if rule.days_threshold is not None else "",
        "estado_propuesto": rule.estado_propuesto or "",
        "motivo_template": rule.motivo_template,
        "requiere_accion": rule.requiere_accion,
        "review_needed": rule.review_needed,
        "notes": rule.notes,
    }


# --------------------------------------------------------- history view
def render_rule_history(db_path: Path, rule_id: int) -> str:
    conn = v02_connect(db_path)
    try:
        repo = RulesRepository(conn)
        rule = repo.get_rule(rule_id)
        rows = repo.history_for_rule(rule_id)
    finally:
        conn.close()

    title = f"Historial de regla #{rule_id}"
    subtitle = f"Regla: {rule.name}" if rule else "Regla eliminada"
    body = hero(
        title,
        subtitle,
        button("/rules", "Volver a reglas", "ghost")
        + (button(f"/rules/{rule_id}/edit", "Editar regla") if rule else ""),
    )
    if not rows:
        body += panel("<p class='muted'>Sin cambios registrados para esta regla.</p>")
        return layout(title, body)

    data_rows: list[list[str]] = []
    for row in rows:
        before = _pretty_json(row["before_json"])
        after = _pretty_json(row["after_json"])
        data_rows.append(
            [
                escape(str(row["changed_at"])),
                _action_pill(str(row["action"])),
                escape(str(row["changed_by"] or "-")),
                _diff_html(before, after),
            ]
        )
    body += table(["Fecha", "Accion", "Autor", "Cambios"], data_rows)
    return layout(title, body)


def _pretty_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _action_pill(action: str) -> str:
    classes = {
        "create": "pill pill-apply",
        "update": "pill pill-changed",
        "enable": "pill pill-apply",
        "disable": "pill pill-unchanged",
        "delete": "pill pill-error",
        "seed": "pill pill-dry",
    }
    klass = classes.get(action, "pill")
    return f'<span class="{klass}">{escape(action)}</span>'


def _diff_html(before: dict | None, after: dict | None) -> str:
    if before is None and after is not None:
        return '<span class="muted">Regla creada</span>'
    if after is None and before is not None:
        return '<span class="muted">Regla eliminada</span>'
    if before is None or after is None:
        return '<span class="muted">-</span>'

    lines: list[str] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        if key in {"updated_at", "updated_by", "id"}:
            continue
        b = before.get(key)
        a = after.get(key)
        if b == a:
            continue
        lines.append(
            f'<div style="font-size:.82rem"><strong>{escape(key)}</strong>: '
            f'<span class="muted">{escape(_short(b))}</span> → {escape(_short(a))}</div>'
        )
    if not lines:
        return '<span class="muted">Sin cambios semanticos</span>'
    return "".join(lines)


def _short(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    if len(text) > 60:
        return text[:60] + "..."
    return text


# ------------------------------------------------------------ preview
def render_rule_preview(db_path: Path, guide: str | None) -> str:
    body = hero(
        "Vista previa de reglas",
        "Aplica las reglas activas a una guia con datos ya almacenados y muestra que decision tomarian.",
        button("/rules", "Volver a reglas", "ghost"),
    )
    body += panel(
        '<form class="filters" method="get" action="/rules/preview">'
        f'<label>Guia<input type="text" name="guia" value="{escape(guide or "")}" placeholder="Numero de guia"></label>'
        '<button type="submit">Previsualizar</button>'
        "</form>"
    )

    if not guide:
        body += panel("<p class='muted'>Ingresa una guia para ver su evaluacion.</p>")
        return layout("Vista previa", body)

    events = _load_latest_tracking(db_path, guide)
    if events is None:
        body += alert(
            f"No hay historico almacenado de {guide}. Corre una ejecucion que la incluya para poder previsualizar."
        )
        return layout("Vista previa", body)

    tracking = _build_tracking(events)
    conn = v02_connect(db_path)
    try:
        rules = RulesRepository(conn).list_rules(only_enabled=True)
    finally:
        conn.close()

    today = date.today()
    decision = decide_status(tracking, today, rules=rules, carrier=events["carrier"])

    body += h(f"Resultado si corriera hoy ({today.isoformat()})")
    propuesto = decision.estado_propuesto or '<span class="muted">Sin propuesta</span>'
    review_badge = (
        ' <span class="pill pill-manual">requiere revision</span>'
        if decision.review_needed
        else ""
    )
    matched = (
        f'<strong>{escape(decision.matched_rule_name)}</strong> '
        f'(#{decision.matched_rule_id}) '
        f'<a class="button ghost" href="/rules/{decision.matched_rule_id}/edit" style="padding:2px 10px;font-size:.78rem">Ver regla</a>'
        if decision.matched_rule_id is not None
        else '<span class="muted">Ninguna regla aplico (fallback a revision manual).</span>'
    )
    body += panel(
        f'<div style="font-size:.86rem;line-height:1.7">'
        f'<div><strong>Regla ganadora:</strong> {matched}</div>'
        f'<div><strong>Estado propuesto:</strong> {escape(str(propuesto))}{review_badge}</div>'
        f'<div><strong>Motivo:</strong> {escape(decision.motivo)}</div>'
        f'<div><strong>Accion requerida:</strong> {escape(decision.requiere_accion or "-")}</div>'
        "</div>"
    )

    body += h("Datos evaluados")
    body += panel(
        f'<div style="font-size:.86rem;line-height:1.7">'
        f'<div><strong>Transportista:</strong> {carrier_badge(events["carrier"])}</div>'
        f'<div><strong>Estado actual:</strong> {escape(tracking.estado_actual or "-")}</div>'
        f'<div><strong>Ultima fecha de estado:</strong> {escape(_format_latest_date(tracking))}</div>'
        f'<div><strong>Corrida fuente:</strong> #{events["run_id"]} ({_format_ts(events["run_started_at"])})</div>'
        "</div>"
    )

    if tracking.novelty_history:
        body += h("Historial de novedades")
        body += table(
            ["Fecha", "Novedad", "Detalle"],
            [
                [
                    _format_ts(ev.date.isoformat() if ev.date else None),
                    escape(ev.novelty),
                    escape(ev.details or ""),
                ]
                for ev in tracking.novelty_history
            ],
        )
    return layout("Vista previa", body)


def _load_latest_tracking(db_path: Path, guide: str) -> dict | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        base = conn.execute(
            """
            SELECT rr.run_id, rr.estado_effi_actual, rr.carrier, r.started_at
            FROM run_results rr
            JOIN runs r ON r.id = rr.run_id
            WHERE rr.guia = ? AND rr.estado_effi_actual IS NOT NULL AND rr.estado_effi_actual != ''
            ORDER BY rr.run_id DESC
            LIMIT 1
            """,
            (guide,),
        ).fetchone()
        if base is None:
            return None
        run_id = int(base["run_id"])
        status_events = list(conn.execute(
            "SELECT event_at, status FROM tracking_status_events WHERE run_id=? AND guia=? ORDER BY id ASC",
            (run_id, guide),
        ).fetchall())
        novelty_events = list(conn.execute(
            "SELECT event_at, novelty, details FROM tracking_novelty_events WHERE run_id=? AND guia=? ORDER BY id ASC",
            (run_id, guide),
        ).fetchall())
        return {
            "run_id": run_id,
            "estado_actual": base["estado_effi_actual"],
            "carrier": (base["carrier"] if "carrier" in base.keys() else "effi") or "effi",
            "run_started_at": base["started_at"],
            "status_events": status_events,
            "novelty_events": novelty_events,
        }
    finally:
        conn.close()


def _build_tracking(events: dict) -> EffiTrackingData:
    status_history = [
        EffiStatusEvent(date=_parse_iso(row["event_at"]), status=str(row["status"]))
        for row in events["status_events"]
    ]
    novelty_history = [
        EffiNovedadEvent(
            date=_parse_iso(row["event_at"]),
            novelty=str(row["novelty"]),
            details=str(row["details"] or ""),
        )
        for row in events["novelty_events"]
    ]
    return EffiTrackingData(
        url="",
        estado_actual=events["estado_actual"],
        status_history=status_history,
        novelty_history=novelty_history,
    )


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt) + (0 if "S" in fmt else 0)], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_latest_date(tracking: EffiTrackingData) -> str:
    dated = [e.date for e in tracking.status_history if e.date is not None]
    if not dated:
        return "Sin fecha valida"
    return max(dated).isoformat(sep=" ", timespec="minutes")


def _format_ts(raw: str | None) -> str:
    if not raw:
        return "-"
    return str(raw)[:16].replace("T", " ")


# ------------------------------------------------------------- POST handlers
def handle_create(db_path: Path, form: dict) -> tuple[str, Rule | None, list[str]]:
    """Returns (location, rule, errors). On error, rule is None and errors is populated."""
    rule, errors = _rule_from_form(form, existing_id=None)
    if errors:
        return "", None, errors
    conn = v02_connect(db_path)
    try:
        saved = RulesRepository(conn).save_rule(rule)
    except ValueError as exc:
        conn.close()
        return "", None, [str(exc)]
    finally:
        conn.close()
    return f"/rules?created={quote(saved.name)}", saved, []


def handle_update(db_path: Path, rule_id: int, form: dict) -> tuple[str, Rule | None, list[str]]:
    conn = v02_connect(db_path)
    try:
        repo = RulesRepository(conn)
        existing = repo.get_rule(rule_id)
        if existing is None:
            return "", None, [f"Regla {rule_id} no existe."]
        rule, errors = _rule_from_form(form, existing_id=rule_id, base=existing)
        if errors:
            return "", None, errors
        try:
            saved = repo.save_rule(rule)
        except ValueError as exc:
            return "", None, [str(exc)]
    finally:
        conn.close()
    return f"/rules?updated={quote(saved.name)}", saved, []


def handle_toggle(db_path: Path, rule_id: int) -> str:
    conn = v02_connect(db_path)
    try:
        RulesRepository(conn).toggle_rule(rule_id)
    finally:
        conn.close()
    return "/rules?toggled=1"


def handle_delete(db_path: Path, rule_id: int) -> str:
    conn = v02_connect(db_path)
    try:
        RulesRepository(conn).delete_rule(rule_id)
    finally:
        conn.close()
    return "/rules?deleted=1"


def _rule_from_form(
    form: dict, existing_id: int | None, base: Rule | None = None
) -> tuple[Rule, list[str]]:
    errors: list[str] = []

    def _get(key: str, default: str = "") -> str:
        values = form.get(key)
        if not values:
            return default
        return values[0] if isinstance(values, list) else str(values)

    def _get_list(key: str) -> list[str]:
        raw = _get(key, "")
        return [line.strip() for line in raw.replace("\r", "").split("\n") if line.strip()]

    name = _get("name").strip()
    if not name:
        errors.append("El nombre es obligatorio.")

    try:
        priority = int(_get("priority", "100"))
    except ValueError:
        priority = 100
        errors.append("La prioridad debe ser un numero entero.")

    carrier = _get("carrier", "effi").strip() or "effi"
    estado_kind = _get("estado_match_kind", "any")
    novelty_kind = _get("novelty_match_kind", "any")

    days_comp_raw = _get("days_comparator", "").strip()
    days_comparator: str | None = days_comp_raw or None

    days_threshold_raw = _get("days_threshold", "").strip()
    days_threshold: int | None
    if days_threshold_raw:
        try:
            days_threshold = int(days_threshold_raw)
        except ValueError:
            days_threshold = None
            errors.append("El umbral de dias debe ser un numero entero.")
    else:
        days_threshold = None

    motivo = _get("motivo_template").strip()
    if not motivo:
        errors.append("El motivo es obligatorio.")

    rule = Rule(
        id=existing_id,
        carrier=carrier,
        name=name,
        priority=priority,
        enabled=bool(form.get("enabled")),
        estado_match_kind=estado_kind,
        estado_match_values=[v.casefold() for v in _get_list("estado_match_values")],
        novelty_match_kind=novelty_kind,
        novelty_match_values=[v.casefold() for v in _get_list("novelty_match_values")],
        days_comparator=days_comparator,
        days_threshold=days_threshold,
        estado_propuesto=(_get("estado_propuesto").strip() or None),
        motivo_template=motivo,
        requiere_accion=_get("requiere_accion").strip(),
        review_needed=bool(form.get("review_needed")),
        notes=_get("notes").strip(),
        updated_at=base.updated_at if base else "",
        updated_by=base.updated_by if base else "operadora",
    )
    return rule, errors
