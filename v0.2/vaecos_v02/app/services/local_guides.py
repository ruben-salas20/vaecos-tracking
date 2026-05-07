"""Read guides from the local SQLite snapshot — same shape as NotionProvider methods.

Phase 2.1: el motor de tracking deja de leer guías desde Notion en cada corrida y
las lee desde la tabla local `guides` (que se sincroniza desde Notion vía
`sync_guides()` antes de cada corrida).

Stats devueltos siguen el mismo formato que NotionProvider.fetch_active_guides:
    {"read", "active", "excluded", "incomplete", "matched"}
para que `run_tracking.execute_tracking()` no necesite branchear según el origen.
"""
from __future__ import annotations
from pathlib import Path

from vaecos_v02.core.models import NotionClientRecord
from vaecos_v02.storage.db import connect


_SELECT_COLS = (
    "page_id, guia, cliente, telefono, estado_novedad, carrier, "
    "producto, valor, cantidad, fecha_ultimo_seguimiento"
)


def _row_to_record(row) -> NotionClientRecord:
    return NotionClientRecord(
        page_id=row["page_id"],
        nombre=row["cliente"] or "",
        guia=row["guia"] or "",
        estado_novedad=row["estado_novedad"] or "",
        carrier=(row["carrier"] or "effi"),
        fecha_ultimo_seguimiento=row["fecha_ultimo_seguimiento"],
        telefono=row["telefono"] or "",
        producto=row["producto"] or "",
        valor=row["valor"],
        cantidad=row["cantidad"],
    )


def fetch_active_guides_local(
    db_path: Path, excluded_statuses: set[str]
) -> tuple[list[NotionClientRecord], dict[str, int]]:
    """Read all non-archived guides from `guides`, applying the same
    excluded_statuses filter that NotionProvider.fetch_active_guides() applies."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_SELECT_COLS} FROM guides WHERE archived = 0"
        ).fetchall()
    finally:
        conn.close()

    found: list[NotionClientRecord] = []
    stats = {"read": 0, "active": 0, "excluded": 0, "incomplete": 0, "matched": 0}
    for row in rows:
        stats["read"] += 1
        if not row["guia"] or not row["page_id"]:
            stats["incomplete"] += 1
            continue
        if (row["estado_novedad"] or "") in excluded_statuses:
            stats["excluded"] += 1
            continue
        found.append(_row_to_record(row))
        stats["active"] += 1
        stats["matched"] += 1
    return found, stats


def fetch_selected_guides_local(
    db_path: Path, target_guides: list[str], excluded_statuses: set[str]
) -> tuple[list[NotionClientRecord], dict[str, int]]:
    """Read specific guides from local, applying the same excluded_statuses filter
    that NotionProvider.fetch_selected_guides() applies."""
    target_upper = {g.strip().upper() for g in (target_guides or []) if g.strip()}
    stats = {"read": 0, "active": 0, "excluded": 0, "incomplete": 0, "matched": 0}
    if not target_upper:
        return [], stats

    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_SELECT_COLS} FROM guides WHERE archived = 0"
        ).fetchall()
    finally:
        conn.close()

    found: list[NotionClientRecord] = []
    for row in rows:
        stats["read"] += 1
        if not row["guia"] or not row["page_id"]:
            stats["incomplete"] += 1
            continue
        if row["guia"].upper() not in target_upper:
            continue
        if (row["estado_novedad"] or "") in excluded_statuses:
            stats["excluded"] += 1
            continue
        found.append(_row_to_record(row))
        stats["active"] += 1
        stats["matched"] += 1
    return found, stats
