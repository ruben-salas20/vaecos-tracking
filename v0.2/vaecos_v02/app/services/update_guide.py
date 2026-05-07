"""Atomic update of a single guide's Estado novedad.
Writes to Notion first; if that succeeds, writes locally and audit-logs.
If Notion fails, logs the failed attempt in guide_edits and raises."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vaecos_v02.providers.notion_provider import NotionProvider
from vaecos_v02.storage.db import connect


@dataclass(frozen=True)
class UpdateResult:
    guia: str
    page_id: str
    valor_anterior: str
    valor_nuevo: str
    edit_id: int


def update_guide_state(
    db_path: Path,
    notion: NotionProvider,
    guia: str,
    new_state: str,
    autor: str,
) -> UpdateResult:
    new_state = (new_state or "").strip()
    if not new_state:
        raise ValueError("El estado no puede estar vacío.")

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT page_id, estado_novedad FROM guides WHERE guia = ?",
            (guia,),
        ).fetchone()
        if not row:
            raise LookupError(f"La guía {guia} no existe en el snapshot local.")

        page_id = row["page_id"]
        prev_state = row["estado_novedad"] or ""

        if prev_state.strip().lower() == new_state.lower():
            raise ValueError(f"La guía ya tiene el estado '{prev_state}'.")

        # Try Notion FIRST. If it fails, we log the failure and raise — nothing local changes.
        now = datetime.now().isoformat(timespec="seconds")
        try:
            notion.update_estado_novedad(page_id, new_state)
        except Exception as exc:  # noqa: BLE001
            cursor = conn.execute(
                "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
                "created_at, sync_ok, error_msg) VALUES (?,?,?,?,?,?,0,?)",
                (guia, autor, "estado_novedad", prev_state, new_state, now, str(exc)),
            )
            conn.commit()
            raise

        # Notion accepted — apply local update + log success
        # Use the canonical value Notion accepted (case-corrected)
        canonical = notion._resolve_select_option("Estado novedad", new_state)  # noqa: SLF001
        conn.execute(
            "UPDATE guides SET estado_novedad = ?, last_synced_at = ? WHERE guia = ?",
            (canonical, now, guia),
        )
        cursor = conn.execute(
            "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
            "created_at, sync_ok) VALUES (?,?,?,?,?,?,1)",
            (guia, autor, "estado_novedad", prev_state, canonical, now),
        )
        edit_id = cursor.lastrowid or 0
        conn.commit()
        return UpdateResult(
            guia=guia,
            page_id=page_id,
            valor_anterior=prev_state,
            valor_nuevo=canonical,
            edit_id=edit_id,
        )
    finally:
        conn.close()
