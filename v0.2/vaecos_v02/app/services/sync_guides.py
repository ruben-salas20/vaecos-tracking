"""Sync the local `guides` table from Notion. Pull-only; never writes to Notion."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vaecos_v02.providers.notion_provider import NotionProvider
from vaecos_v02.storage.db import connect, init_db


@dataclass(frozen=True)
class SyncStats:
    read_from_notion: int
    inserted: int
    updated: int
    unchanged: int
    archived: int
    incomplete: int


def sync_guides(db_path: Path, notion: NotionProvider) -> SyncStats:
    """Fetch all pages from Notion and upsert into the local `guides` table.
    Pages no longer present in Notion are marked archived=1 (not deleted)."""
    records, fetch_stats = notion.fetch_all_pages()
    now = datetime.now().isoformat(timespec="seconds")

    conn = connect(db_path)
    try:
        init_db(conn)
        seen_page_ids: set[str] = set()
        inserted = updated = unchanged = 0

        for r in records:
            seen_page_ids.add(r.page_id)
            existing = conn.execute(
                "SELECT page_id, guia, cliente, telefono, estado_novedad, carrier, "
                "producto, valor, cantidad, fecha_ultimo_seguimiento, archived "
                "FROM guides WHERE page_id = ?",
                (r.page_id,),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO guides (
                        page_id, guia, cliente, telefono, estado_novedad, carrier,
                        producto, valor, cantidad, fecha_ultimo_seguimiento,
                        archived, last_synced_at, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?)
                    """,
                    (
                        r.page_id, r.guia, r.nombre, r.telefono, r.estado_novedad,
                        r.carrier, r.producto, r.valor, r.cantidad,
                        r.fecha_ultimo_seguimiento, now, now,
                    ),
                )
                inserted += 1
                continue

            # Compare to detect actual changes
            changed = (
                existing["guia"] != r.guia
                or existing["cliente"] != r.nombre
                or (existing["telefono"] or "") != (r.telefono or "")
                or (existing["estado_novedad"] or "") != (r.estado_novedad or "")
                or (existing["carrier"] or "effi") != (r.carrier or "effi")
                or (existing["producto"] or "") != (r.producto or "")
                or _num_diff(existing["valor"], r.valor)
                or _num_diff(existing["cantidad"], r.cantidad)
                or (existing["fecha_ultimo_seguimiento"] or "") != (r.fecha_ultimo_seguimiento or "")
                or existing["archived"] == 1  # un-archive if present again
            )

            if changed:
                conn.execute(
                    """
                    UPDATE guides SET
                        guia = ?, cliente = ?, telefono = ?, estado_novedad = ?,
                        carrier = ?, producto = ?, valor = ?, cantidad = ?,
                        fecha_ultimo_seguimiento = ?, archived = 0, last_synced_at = ?
                    WHERE page_id = ?
                    """,
                    (
                        r.guia, r.nombre, r.telefono, r.estado_novedad,
                        r.carrier, r.producto, r.valor, r.cantidad,
                        r.fecha_ultimo_seguimiento, now, r.page_id,
                    ),
                )
                updated += 1
            else:
                # Touch last_synced_at even when nothing changed
                conn.execute(
                    "UPDATE guides SET last_synced_at = ? WHERE page_id = ?",
                    (now, r.page_id),
                )
                unchanged += 1

        # Archive locally any page no longer returned by Notion
        archived = 0
        if seen_page_ids:
            placeholders = ",".join("?" * len(seen_page_ids))
            cur = conn.execute(
                f"UPDATE guides SET archived = 1 WHERE archived = 0 AND page_id NOT IN ({placeholders})",
                tuple(seen_page_ids),
            )
            archived = cur.rowcount

        conn.commit()
        return SyncStats(
            read_from_notion=fetch_stats.get("read", 0),
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            archived=archived,
            incomplete=fetch_stats.get("incomplete", 0),
        )
    finally:
        conn.close()


def _num_diff(a, b) -> bool:
    """Return True if two number-or-None values differ."""
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    try:
        return abs(float(a) - float(b)) > 1e-9
    except (TypeError, ValueError):
        return str(a) != str(b)
