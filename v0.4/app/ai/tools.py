"""Tool registry para el asistente IA conversacional.

Cada tool es una función Python que recibe un dict de args y devuelve un dict.
El agent llama estas tools en respuesta a peticiones del modelo y le re-feedea
el resultado.

Diseño:
- Las tools son auto-contenidas (abren su propia conexión SQLite, no comparten state)
- Devuelven estructuras compactas (no rows crudas → resúmenes)
- Validan args defensivamente (el modelo puede enviar basura)
- Si fallan, devuelven {"error": "msg"} en vez de raise — el agent lo loguea
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


_VALID_TIPOS = ("ingreso", "egreso", "transferencia")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _parse_period(period: str | None) -> tuple[str | None, str | None]:
    """'2026' → ('2026-01-01', '2026-12-31'). '2026-04' → ('2026-04-01', '2026-04-30').
    None → (None, None) — sin filtro temporal.
    """
    if not period or not isinstance(period, str):
        return None, None
    p = period.strip()
    if len(p) == 4 and p.isdigit():
        return f"{p}-01-01", f"{p}-12-31"
    if len(p) == 7 and p[4] == "-":
        try:
            y, m = int(p[:4]), int(p[5:7])
            if 1 <= m <= 12:
                # último día del mes — calculo simplificado vía siguiente-1
                from calendar import monthrange
                last_day = monthrange(y, m)[1]
                return f"{p}-01", f"{p}-{last_day:02d}"
        except ValueError:
            pass
    if len(p) == 10 and p[4] == "-" and p[7] == "-":
        # YYYY-MM-DD exacto
        return p, p
    return None, None


# ── TOOL 1: get_logistic_summary ──────────────────────────────────────


def tool_get_logistic_summary(db_path: str, args: dict) -> dict:
    """KPIs operativos de guías. Args: {period?: 'YYYY'|'YYYY-MM'|None}.

    Devuelve totales, breakdown por estado, por carrier, attention count.
    """
    period = args.get("period")
    date_from, date_to = _parse_period(period)

    with _connect(db_path) as c:
        where = ""
        params = []
        if date_from:
            where = " WHERE fecha_ultimo_seguimiento BETWEEN ? AND ?"
            params = [date_from, date_to]

        total = c.execute(f"SELECT COUNT(*) FROM guides{where}", params).fetchone()[0]
        archived = c.execute(
            f"SELECT COUNT(*) FROM guides{(where + ' AND') if where else ' WHERE'} archived = 1",
            params,
        ).fetchone()[0]

        by_estado = {
            r[0]: r[1]
            for r in c.execute(
                f"""SELECT COALESCE(estado_novedad, '(sin estado)'), COUNT(*) AS n
                    FROM guides{where} GROUP BY estado_novedad ORDER BY n DESC""",
                params,
            )
            if r[0]
        }
        by_carrier = {
            r[0]: r[1]
            for r in c.execute(
                f"""SELECT COALESCE(carrier, '?'), COUNT(*) FROM guides{where}
                    GROUP BY carrier""",
                params,
            )
        }

        # Attention: guías con estados que requieren acción
        attention_states = ("Gestión novedad", "Cambio de estado", "Manual review", "Bodega clientes")
        placeholders = ",".join(["?"] * len(attention_states))
        att_where = f" WHERE estado_novedad IN ({placeholders})"
        attention_params = list(attention_states)
        if where:
            att_where = att_where + " AND fecha_ultimo_seguimiento BETWEEN ? AND ?"
            attention_params += [date_from, date_to]
        attention = c.execute(
            f"SELECT COUNT(*) FROM guides{att_where}", attention_params,
        ).fetchone()[0]

    return {
        "period": period or "all",
        "total_guides": total,
        "archived": archived,
        "active": total - archived,
        "by_estado": by_estado,
        "by_carrier": by_carrier,
        "requires_attention": attention,
    }


# ── TOOL 2: get_finanzas_summary ──────────────────────────────────────


def tool_get_finanzas_summary(db_path: str, args: dict) -> dict:
    """KPIs financieros COP. Args: {period?: 'YYYY'|'YYYY-MM'|None, tipo?: 'ingreso'|'egreso'}.

    Devuelve ingresos, egresos, balance, top 5 categorías, breakdown mensual si period es año.
    """
    period = args.get("period")
    tipo = args.get("tipo")
    if tipo not in _VALID_TIPOS:
        tipo = None
    date_from, date_to = _parse_period(period)

    clauses, params = [], []
    if date_from:
        clauses.append("m.fecha BETWEEN ? AND ?")
        params += [date_from, date_to]
    if tipo:
        clauses.append("m.tipo = ?")
        params.append(tipo)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with _connect(db_path) as c:
        row = c.execute(
            f"""SELECT
                SUM(CASE WHEN tipo='ingreso' THEN monto_centavos ELSE 0 END) as ing,
                SUM(CASE WHEN tipo='egreso'  THEN monto_centavos ELSE 0 END) as eg,
                COUNT(*) as n
              FROM fin_movements m{where}""",
            params,
        ).fetchone()
        ing = row["ing"] or 0
        eg = row["eg"] or 0

        top_cats = [
            {
                "nombre": r["nombre"],
                "ingresos_cop": (r["ing"] or 0) / 100,
                "egresos_cop": (r["eg"] or 0) / 100,
                "count": r["n"],
            }
            for r in c.execute(
                f"""SELECT c.nombre,
                    SUM(CASE WHEN m.tipo='ingreso' THEN m.monto_centavos ELSE 0 END) as ing,
                    SUM(CASE WHEN m.tipo='egreso'  THEN m.monto_centavos ELSE 0 END) as eg,
                    COUNT(*) as n
                FROM fin_movements m
                JOIN fin_movement_categories mc ON mc.movement_id = m.id
                JOIN fin_categories c ON c.id = mc.category_id{where}
                GROUP BY c.nombre
                ORDER BY (ing + eg) DESC
                LIMIT 8""",
                params,
            )
        ]

        # Breakdown mensual si period es un año
        monthly = []
        if period and len(period) == 4:
            for r in c.execute(
                f"""SELECT substr(m.fecha,1,7) as mes,
                    SUM(CASE WHEN tipo='ingreso' THEN monto_centavos ELSE 0 END) as ing,
                    SUM(CASE WHEN tipo='egreso'  THEN monto_centavos ELSE 0 END) as eg
                FROM fin_movements m{where}
                GROUP BY mes ORDER BY mes""",
                params,
            ):
                monthly.append({
                    "mes": r["mes"],
                    "ingresos_cop": (r["ing"] or 0) / 100,
                    "egresos_cop": (r["eg"] or 0) / 100,
                    "balance_cop": ((r["ing"] or 0) - (r["eg"] or 0)) / 100,
                })

    return {
        "period": period or "all",
        "tipo_filter": tipo,
        "total_movimientos": row["n"] or 0,
        "ingresos_cop": ing / 100,
        "egresos_cop": eg / 100,
        "balance_cop": (ing - eg) / 100,
        "moneda": "COP",
        "top_categories": top_cats,
        "monthly_breakdown": monthly,
    }


# ── TOOL 3: search_guides ─────────────────────────────────────────────


def tool_search_guides(db_path: str, args: dict) -> dict:
    """Busca guías por número, cliente o teléfono. Args: {query: str, limit?: int}."""
    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "query es requerido"}
    limit = args.get("limit", 10)
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 10

    with _connect(db_path) as c:
        rows = c.execute(
            """SELECT guia, cliente, telefono, estado_novedad, carrier,
                      fecha_ultimo_seguimiento, valor
               FROM guides
               WHERE guia LIKE ? OR cliente LIKE ? OR telefono LIKE ?
               ORDER BY fecha_ultimo_seguimiento DESC
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()

    return {
        "query": query,
        "count": len(rows),
        "results": [
            {
                "guia": r["guia"],
                "cliente": r["cliente"],
                "telefono": r["telefono"],
                "estado": r["estado_novedad"],
                "carrier": r["carrier"],
                "ultima_actividad": r["fecha_ultimo_seguimiento"],
                "valor_cop": r["valor"],
            }
            for r in rows
        ],
    }


# ── TOOL 4: get_top_clients ───────────────────────────────────────────


def tool_get_top_clients(db_path: str, args: dict) -> dict:
    """Top clientes por número de guías y valor. Args: {period?: 'YYYY'|'YYYY-MM', limit?: int}."""
    period = args.get("period")
    date_from, date_to = _parse_period(period)
    limit = args.get("limit", 10)
    try:
        limit = max(1, min(int(limit), 30))
    except (TypeError, ValueError):
        limit = 10

    clauses, params = [], []
    if date_from:
        clauses.append("fecha_ultimo_seguimiento BETWEEN ? AND ?")
        params += [date_from, date_to]
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with _connect(db_path) as c:
        rows = c.execute(
            f"""SELECT cliente, COUNT(*) as n, SUM(valor) as total_valor
                FROM guides{where}
                GROUP BY cliente
                ORDER BY n DESC, total_valor DESC
                LIMIT ?""",
            params + [limit],
        ).fetchall()

    return {
        "period": period or "all",
        "count": len(rows),
        "results": [
            {
                "cliente": r["cliente"],
                "guias": r["n"],
                "valor_total_cop": r["total_valor"] or 0,
            }
            for r in rows
        ],
    }


# ── TOOL 5: list_recent_runs ──────────────────────────────────────────


def tool_list_recent_runs(db_path: str, args: dict) -> dict:
    """Lista las últimas N corridas de tracking. Args: {limit?: int}."""
    limit = args.get("limit", 5)
    try:
        limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        limit = 5

    with _connect(db_path) as c:
        rows = c.execute(
            """SELECT id, started_at, finished_at, mode,
                      total_processed, total_changed, total_unchanged,
                      total_manual_review, total_error
               FROM runs
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    return {
        "count": len(rows),
        "results": [
            {
                "id": r["id"],
                "iniciada": r["started_at"],
                "terminada": r["finished_at"],
                "modo": r["mode"],
                "procesadas": r["total_processed"],
                "cambios": r["total_changed"],
                "sin_cambio": r["total_unchanged"],
                "manual_review": r["total_manual_review"],
                "errores": r["total_error"],
            }
            for r in rows
        ],
    }


# ── TOOL 6: get_app_help ──────────────────────────────────────────────


def tool_get_app_help(db_path: str, args: dict) -> dict:
    """Devuelve manual de la app por tópico. Args: {topic: string libre}."""
    from .manual import get_help
    topic = (args.get("topic") or "").strip()
    return get_help(topic)


# ── Registry ──────────────────────────────────────────────────────────


TOOL_REGISTRY = {
    "get_logistic_summary": {
        "fn": tool_get_logistic_summary,
        "description": (
            "Devuelve KPIs de guías (logística): total, archivadas, activas, "
            "breakdown por estado de novedad y carrier, y cuántas requieren atención. "
            "Args: period (opcional, 'YYYY' o 'YYYY-MM'; sin period = todo el histórico)."
        ),
        "args_schema": {"period": "string opcional, ej. '2026' o '2026-04'"},
    },
    "get_finanzas_summary": {
        "fn": tool_get_finanzas_summary,
        "description": (
            "Devuelve resumen financiero en COP para un período: ingresos, egresos, balance, "
            "top categorías, y breakdown mensual (solo si period es un año completo). "
            "Args: period (opcional), tipo (opcional, 'ingreso'|'egreso'|'transferencia')."
        ),
        "args_schema": {
            "period": "string opcional, ej. '2026' o '2026-04'",
            "tipo": "string opcional, 'ingreso'|'egreso'|'transferencia'",
        },
    },
    "search_guides": {
        "fn": tool_search_guides,
        "description": (
            "Busca guías por número de guía, nombre de cliente o teléfono. "
            "Args: query (string, requerido), limit (opcional, default 10, max 50)."
        ),
        "args_schema": {
            "query": "string requerido (parte del número, cliente o tel)",
            "limit": "int opcional (default 10, max 50)",
        },
    },
    "get_top_clients": {
        "fn": tool_get_top_clients,
        "description": (
            "Devuelve el top N de clientes por número de guías y valor total. "
            "Args: period (opcional), limit (opcional, default 10, max 30)."
        ),
        "args_schema": {
            "period": "string opcional",
            "limit": "int opcional (default 10)",
        },
    },
    "list_recent_runs": {
        "fn": tool_list_recent_runs,
        "description": (
            "Lista las últimas N corridas de tracking con conteos de cambios/errores. "
            "Args: limit (opcional, default 5, max 20)."
        ),
        "args_schema": {"limit": "int opcional (default 5, max 20)"},
    },
    "get_app_help": {
        "fn": tool_get_app_help,
        "description": (
            "Devuelve documentación del aplicativo VAECOS por tópico. Usalo CUANDO el usuario "
            "pregunte cómo usar la app, qué hace un módulo, qué significa un estado, dónde está "
            "una opción, o cualquier consulta sobre el funcionamiento del sistema (NO sobre datos). "
            "Ejemplos: '¿cómo importo un Excel?', '¿qué significa Gestión novedad?', "
            "'¿dónde edito categorías financieras?', '¿qué hace el motor de reglas?'. "
            "Si no encuentra el tópico exacto, devuelve la lista de tópicos disponibles."
        ),
        "args_schema": {
            "topic": (
                "string requerido — palabra clave o pregunta corta del usuario. "
                "Ej: 'importar excel', 'estados', 'reglas', 'finanzas', 'bot effi'."
            ),
        },
    },
}


def execute_tool(tool_name: str, db_path: str, args: dict | None) -> dict:
    """Ejecuta tool por nombre. Devuelve {error: ...} si no existe o args inválidos."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool desconocido: {tool_name}"}
    if not isinstance(args, dict):
        args = {}
    try:
        return TOOL_REGISTRY[tool_name]["fn"](db_path, args)
    except Exception as e:
        return {"error": f"Tool '{tool_name}' falló: {type(e).__name__}: {e}"}


def tools_for_prompt() -> str:
    """Genera la descripción de tools para incluir en el system prompt."""
    lines = []
    for name, spec in TOOL_REGISTRY.items():
        lines.append(f"- `{name}`: {spec['description']}")
        for arg, desc in spec["args_schema"].items():
            lines.append(f"    · {arg}: {desc}")
    return "\n".join(lines)
