"""Digest diario del bot Effi — manda 1 email con el resumen de las últimas 24h.

Sustituye al email por-corrida (que con cron horario se vuelve spam). Se ejecuta
una vez al día via cron a las 22:00 GT (= 03:00 UTC del día siguiente).

Ventana: últimas 24h desde el momento de ejecución. No persiste estado — si una
corrida del digest falla, la siguiente cubre 24h (no 48h), pero como el motor
deduplica por `effi_orders.status='done'`, no hay riesgo de info perdida — solo
el digest no reportará ese día.

Datos fuente:
  - effi_audit_log: eventos del bot (done, failed, escalation, etc.)
  - effi_orders:    estado consolidado por orden (status, valor, classification)
  - effi_review_queue: nuevas escalaciones a revisión humana

Usage:
    python scripts/effi_daily_digest.py
    python scripts/effi_daily_digest.py --hours 24       # ventana custom
    python scripts/effi_daily_digest.py --dry-run        # imprime, no manda
    python scripts/effi_daily_digest.py --force          # manda aunque no haya nada
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape as _esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.effi_config import load_settings  # noqa: E402
from app.effi_guides.notifier import notify  # noqa: E402


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def collect_digest_data(conn: sqlite3.Connection, hours: int) -> dict:
    """Consulta el DB y construye el diccionario de datos para el email."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    # Órdenes procesadas (done) en la ventana — el actor real del día.
    orders_done = conn.execute(
        """
        SELECT orden_id, classification, valor_declarado, remision_id, guia_id, processed_at
        FROM effi_orders
        WHERE status = 'done' AND processed_at >= ?
        ORDER BY processed_at ASC
        """,
        (cutoff,),
    ).fetchall()

    # Órdenes que fallaron en la ventana (status='failed', no recuperadas).
    orders_failed = conn.execute(
        """
        SELECT orden_id, classification, error_msg, remision_id, processed_at
        FROM effi_orders
        WHERE status = 'failed' AND updated_at >= ?
        ORDER BY updated_at ASC
        """,
        (cutoff,),
    ).fetchall()

    # Nuevas escalaciones a cola humana (sin resolver).
    queue_new = conn.execute(
        """
        SELECT orden_id, reason, details_json, created_at
        FROM effi_review_queue
        WHERE created_at >= ? AND resolved = 0
        ORDER BY created_at ASC
        """,
        (cutoff,),
    ).fetchall()

    # Sync a Notion: cuántas tuvieron éxito vs fallaron (del audit log).
    notion_events = conn.execute(
        """
        SELECT action, ok, COUNT(*) AS n
        FROM effi_audit_log
        WHERE action IN ('notion_sync_ok', 'notion_sync_failed') AND ts >= ?
        GROUP BY action, ok
        """,
        (cutoff,),
    ).fetchall()

    notion_ok = sum(r["n"] for r in notion_events if r["action"] == "notion_sync_ok")
    notion_failed = sum(r["n"] for r in notion_events if r["action"] == "notion_sync_failed")

    # Cuántas corridas se ejecutaron (cualquier `would_execute` o `done` o `failed`).
    # Útil para sanity check: si dice 0 corridas algo está roto con el cron.
    runs_count = conn.execute(
        """
        SELECT COUNT(DISTINCT date(ts) || ' ' || substr(ts, 12, 2)) AS n
        FROM effi_audit_log
        WHERE ts >= ?
        """,
        (cutoff,),
    ).fetchone()
    distinct_hours = runs_count["n"] if runs_count else 0

    classification_counts = Counter(r["classification"] for r in orders_done)
    total_valor = sum((r["valor_declarado"] or 0) for r in orders_done)

    return {
        "cutoff_utc": cutoff,
        "hours": hours,
        "orders_done": [dict(r) for r in orders_done],
        "orders_failed": [dict(r) for r in orders_failed],
        "queue_new": [dict(r) for r in queue_new],
        "classification_counts": dict(classification_counts),
        "total_valor": total_valor,
        "notion_ok": notion_ok,
        "notion_failed": notion_failed,
        "distinct_hours_with_activity": distinct_hours,
    }


def _classify_label(kind: str) -> str:
    return {
        "combo": "Combo",
        "femenino": "Ínt. femenino",
        "otro": "Otro",
        "escalation": "Escalación",
    }.get(kind, kind)


def _fmt_date_local(iso_utc: str) -> str:
    """Convierte timestamp UTC a string local GT (UTC-6)."""
    try:
        dt = datetime.strptime(iso_utc[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        local = dt.astimezone(timezone(timedelta(hours=-6)))
        return local.strftime("%H:%M")
    except Exception:
        return iso_utc[:16]


def build_plain(data: dict) -> str:
    lines = []
    lines.append(f"Digest Effi — últimas {data['hours']}h (corte UTC: {data['cutoff_utc']})")
    lines.append("")
    lines.append(f"Guías creadas        : {len(data['orders_done'])}")
    lines.append(f"Errores              : {len(data['orders_failed'])}")
    lines.append(f"Nuevas en cola       : {len(data['queue_new'])}")
    lines.append(f"Sync Notion OK       : {data['notion_ok']}")
    lines.append(f"Sync Notion fallido  : {data['notion_failed']}")
    lines.append(f"Valor total declarado: Q {data['total_valor']:.2f}")
    lines.append("")

    if data["classification_counts"]:
        lines.append("--- Por clasificación ---")
        for kind, n in data["classification_counts"].items():
            lines.append(f"  {_classify_label(kind)}: {n}")
        lines.append("")

    if data["orders_done"]:
        lines.append("--- Guías creadas ---")
        for r in data["orders_done"]:
            valor = r["valor_declarado"] or 0
            lines.append(
                f"  #{r['orden_id']} {_classify_label(r['classification'])} "
                f"Q{valor:.2f} → rem #{r['remision_id']}, guía #{r['guia_id']} "
                f"({_fmt_date_local(r['processed_at'])})"
            )
        lines.append("")

    if data["orders_failed"]:
        lines.append("--- Errores ---")
        for r in data["orders_failed"]:
            err = (r["error_msg"] or "").splitlines()[0][:120]
            lines.append(f"  #{r['orden_id']}: {err}")
        lines.append("")

    if data["queue_new"]:
        lines.append("--- Nuevas en cola humana ---")
        for r in data["queue_new"]:
            details = ""
            if r["details_json"]:
                try:
                    d = json.loads(r["details_json"])
                    details = d.get("mensaje") or d.get("summary") or ""
                    if details:
                        details = " — " + details[:100]
                except Exception:
                    pass
            lines.append(f"  #{r['orden_id']} [{r['reason']}]{details}")
        lines.append("")

    lines.append("Detalle completo en /effi/audit, /effi/queue y /all-guides")
    return "\n".join(lines)


def build_html(data: dict) -> str:
    n_done = len(data["orders_done"])
    n_failed = len(data["orders_failed"])
    n_queue = len(data["queue_new"])

    def kpi(value, label, bg, fg):
        return (
            f'<td style="background:{bg};color:{fg};border-radius:6px;padding:14px 8px;'
            f'text-align:center;width:25%;">'
            f'<div style="font-size:26px;font-weight:700;line-height:1;">{value}</div>'
            f'<div style="font-size:11px;margin-top:6px;letter-spacing:.3px;">{label}</div>'
            "</td>"
        )

    parts = []
    parts.append('<div style="font-family:Inter,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#0f172a;">')
    parts.append(f'<h2 style="margin:0 0 4px 0;font-size:20px;">Digest diario Effi</h2>')
    parts.append(
        f'<div style="color:#64748b;font-size:13px;margin-bottom:18px;">'
        f'Últimas {data["hours"]}h · Q {data["total_valor"]:.2f} en valor declarado</div>'
    )

    parts.append('<table style="width:100%;border-collapse:separate;border-spacing:6px 0;"><tr>')
    parts.append(kpi(n_done, "Guías creadas", "#dcfce7", "#166534"))
    parts.append(kpi(data["notion_ok"], "Sync Notion", "#dbeafe", "#1e3a8a"))
    parts.append(kpi(n_queue, "Nuevas en cola", "#fef3c7", "#92400e"))
    parts.append(kpi(n_failed, "Errores", "#fee2e2", "#991b1b"))
    parts.append("</tr></table>")

    if data["classification_counts"]:
        parts.append('<div style="margin:18px 0 6px 0;font-size:12px;color:#475569;text-transform:uppercase;letter-spacing:.5px;font-weight:600;">Por clasificación</div>')
        parts.append('<div style="font-size:13px;color:#0f172a;">')
        chips = []
        for kind, n in data["classification_counts"].items():
            chips.append(
                f'<span style="display:inline-block;background:#f1f5f9;border-radius:4px;padding:3px 8px;margin:0 4px 4px 0;">'
                f'{_esc(_classify_label(kind))} · <b>{n}</b></span>'
            )
        parts.append("".join(chips))
        parts.append("</div>")

    if data["orders_done"]:
        parts.append('<div style="margin:18px 0 6px 0;font-size:12px;color:#16a34a;text-transform:uppercase;letter-spacing:.5px;font-weight:600;">Guías creadas</div>')
        for r in data["orders_done"]:
            valor = r["valor_declarado"] or 0
            parts.append(
                f'<div style="border-left:3px solid #16a34a;padding:8px 12px;margin:4px 0;background:#f0fdf4;font-size:13px;">'
                f"<b>#{r['orden_id']}</b> · {_esc(_classify_label(r['classification']))} · Q{valor:.2f}<br>"
                f'<span style="color:#475569;font-size:12px;">remisión #{r["remision_id"]} → guía #{r["guia_id"]} · {_fmt_date_local(r["processed_at"])}</span>'
                f"</div>"
            )

    if data["orders_failed"]:
        parts.append('<div style="margin:18px 0 6px 0;font-size:12px;color:#dc2626;text-transform:uppercase;letter-spacing:.5px;font-weight:600;">Errores</div>')
        for r in data["orders_failed"]:
            err = (r["error_msg"] or "").splitlines()[0][:200]
            parts.append(
                f'<div style="border-left:3px solid #dc2626;padding:8px 12px;margin:4px 0;background:#fef2f2;font-size:13px;">'
                f"<b>#{r['orden_id']}</b><br>"
                f'<span style="color:#475569;font-size:12px;">{_esc(err)}</span>'
                f"</div>"
            )

    if data["queue_new"]:
        parts.append('<div style="margin:18px 0 6px 0;font-size:12px;color:#d97706;text-transform:uppercase;letter-spacing:.5px;font-weight:600;">Nuevas en cola humana</div>')
        for r in data["queue_new"]:
            details = ""
            if r["details_json"]:
                try:
                    d = json.loads(r["details_json"])
                    details = d.get("mensaje") or d.get("summary") or ""
                except Exception:
                    pass
            parts.append(
                f'<div style="border-left:3px solid #d97706;padding:8px 12px;margin:4px 0;background:#fffbeb;font-size:13px;">'
                f"<b>#{r['orden_id']}</b> · {_esc(r['reason'])}<br>"
                f'<span style="color:#475569;font-size:12px;">{_esc(details[:200])}</span>'
                f"</div>"
            )

    parts.append(
        '<div style="margin-top:24px;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:12px;">'
        'Detalle completo: <a href="https://app.vaecos.com/effi/audit">/effi/audit</a> · '
        '<a href="https://app.vaecos.com/effi/queue">/effi/queue</a> · '
        '<a href="https://app.vaecos.com/all-guides">/all-guides</a>'
        "</div>"
    )
    parts.append("</div>")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Digest diario del bot Effi.")
    parser.add_argument("--hours", type=int, default=24, help="Ventana en horas (default 24).")
    parser.add_argument("--dry-run", action="store_true", help="Imprime el digest pero no manda email.")
    parser.add_argument("--force", action="store_true", help="Manda email aunque la ventana esté vacía.")
    args = parser.parse_args()

    settings = load_settings()
    conn = _connect(settings.db_path)
    try:
        data = collect_digest_data(conn, args.hours)
    finally:
        conn.close()

    n_total = (
        len(data["orders_done"])
        + len(data["orders_failed"])
        + len(data["queue_new"])
    )
    if n_total == 0 and not args.force:
        print(f"[digest] sin actividad en las últimas {args.hours}h — skip email.")
        return 0

    plain = build_plain(data)
    html = build_html(data)

    if args.dry_run:
        print(plain)
        print()
        print(f"[digest] dry-run: NO mandado. ({n_total} items en la ventana)")
        return 0

    today_local = (datetime.now(timezone.utc) + timedelta(hours=-6)).strftime("%Y-%m-%d")
    subject = (
        f"Digest {today_local}: "
        f"{len(data['orders_done'])} guías · "
        f"{len(data['queue_new'])} a revisar · "
        f"{len(data['orders_failed'])} errores"
    )
    ok = notify(subject=subject, body=plain, html=html, prefix="[VAECOS Effi]")
    print(f"[digest] {'enviado' if ok else 'NO enviado (notifier disabled o error)'} · {n_total} items")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
