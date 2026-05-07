"""Atomic update of a single guide's editable fields.
Writes to Notion first; if that succeeds, writes locally and audit-logs.
If Notion fails, logs the failed attempt in guide_edits and raises."""
from __future__ import annotations
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class FieldsUpdateResult:
    guia: str
    page_id: str
    changes: dict[str, tuple[str, str]] = field(default_factory=dict)
    edit_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ArchiveResult:
    guia: str
    page_id: str
    edit_id: int


def archive_guide(
    db_path: Path,
    notion: NotionProvider,
    guia: str,
    autor: str,
) -> ArchiveResult:
    """Soft-delete: archiva la página en Notion (papelera 30 días) y marca
    archived=1 en local. Preserva run_results, notes y audit.
    Atomic: Notion FIRST; si falla, no se modifica nada local."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT page_id, cliente, archived FROM guides WHERE guia = ?",
            (guia,),
        ).fetchone()
        if not row:
            raise LookupError(f"La guía {guia} no existe en el snapshot local.")
        if row["archived"]:
            raise ValueError(f"La guía {guia} ya está archivada.")

        page_id = row["page_id"]
        cliente = row["cliente"] or ""
        now = datetime.now().isoformat(timespec="seconds")

        try:
            notion.archive_page(page_id)
        except Exception as exc:  # noqa: BLE001
            conn.execute(
                "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
                "created_at, sync_ok, error_msg) VALUES (?,?,?,?,?,?,0,?)",
                (guia, autor, "__archive__", cliente, "", now, str(exc)),
            )
            conn.commit()
            raise

        conn.execute(
            "UPDATE guides SET archived = 1, last_synced_at = ? WHERE guia = ?",
            (now, guia),
        )
        cursor = conn.execute(
            "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
            "created_at, sync_ok) VALUES (?,?,?,?,?,?,1)",
            (guia, autor, "__archive__", cliente, "", now),
        )
        edit_id = cursor.lastrowid or 0
        conn.commit()
        return ArchiveResult(guia=guia, page_id=page_id, edit_id=edit_id)
    finally:
        conn.close()


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


# Campos editables por la operadora desde la app (estado_novedad va por update_guide_state)
_EDITABLE_FIELDS = ("telefono", "producto", "valor", "cantidad")


def _norm_text(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _norm_number(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def update_guide_fields(
    db_path: Path,
    notion: NotionProvider,
    guia: str,
    new_values: dict,
    autor: str,
) -> FieldsUpdateResult:
    """Atomic update of editable fields (telefono, producto, valor, cantidad).
    Writes to Notion FIRST; on success, updates local + one audit row per changed field.
    On Notion failure, logs the attempt with sync_ok=0 and raises.
    Fields not present in new_values (or unchanged vs current local) are skipped."""
    if not new_values:
        raise ValueError("No se recibieron campos para actualizar.")

    invalid = [k for k in new_values.keys() if k not in _EDITABLE_FIELDS]
    if invalid:
        raise ValueError(f"Campos no editables: {', '.join(invalid)}")

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT page_id, telefono, producto, valor, cantidad FROM guides WHERE guia = ?",
            (guia,),
        ).fetchone()
        if not row:
            raise LookupError(f"La guía {guia} no existe en el snapshot local.")

        page_id = row["page_id"]
        current = {
            "telefono": _norm_text(row["telefono"]),
            "producto": _norm_text(row["producto"]),
            "valor": _norm_number(row["valor"]),
            "cantidad": _norm_number(row["cantidad"]),
        }

        # Normalize incoming values
        proposed = dict(current)
        if "telefono" in new_values:
            proposed["telefono"] = _norm_text(new_values["telefono"])
        if "producto" in new_values:
            proposed["producto"] = _norm_text(new_values["producto"])
        if "valor" in new_values:
            proposed["valor"] = _norm_number(new_values["valor"])
        if "cantidad" in new_values:
            cant = _norm_number(new_values["cantidad"])
            proposed["cantidad"] = int(cant) if cant is not None else None

        # Compute diff
        changes: dict[str, tuple[str, str]] = {}
        for key in _EDITABLE_FIELDS:
            if key not in new_values:
                continue
            if proposed[key] != current[key]:
                changes[key] = (
                    "" if current[key] is None else str(current[key]),
                    "" if proposed[key] is None else str(proposed[key]),
                )

        if not changes:
            return FieldsUpdateResult(guia=guia, page_id=page_id, changes={}, edit_ids=[])

        # Validate telefono is numeric if present (Notion requires int)
        if "telefono" in changes and proposed["telefono"]:
            if not proposed["telefono"].isdigit():
                raise ValueError(f"Teléfono debe ser numérico: '{proposed['telefono']}'.")

        # Validate cantidad and valor non-negative if present
        if "cantidad" in changes and proposed["cantidad"] is not None and proposed["cantidad"] < 0:
            raise ValueError("Cantidad no puede ser negativa.")
        if "valor" in changes and proposed["valor"] is not None and proposed["valor"] < 0:
            raise ValueError("Valor no puede ser negativo.")

        # Build kwargs for Notion (only changed fields)
        notion_kwargs = {k: proposed[k] for k in changes.keys()}

        now = datetime.now().isoformat(timespec="seconds")
        try:
            notion.update_guide_fields(page_id, **notion_kwargs)
        except Exception as exc:  # noqa: BLE001
            # Audit each attempted field with sync_ok=0
            for campo, (prev, new) in changes.items():
                conn.execute(
                    "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
                    "created_at, sync_ok, error_msg) VALUES (?,?,?,?,?,?,0,?)",
                    (guia, autor, campo, prev, new, now, str(exc)),
                )
            conn.commit()
            raise

        # Notion accepted — update local + audit each changed field
        update_clauses = []
        update_params = []
        for k in changes.keys():
            db_col = "cliente" if k == "cliente" else k  # passthrough — cliente isn't editable, just for safety
            update_clauses.append(f"{db_col} = ?")
            update_params.append(proposed[k])
        update_params.extend([now, guia])
        conn.execute(
            f"UPDATE guides SET {', '.join(update_clauses)}, last_synced_at = ? WHERE guia = ?",
            update_params,
        )

        edit_ids: list[int] = []
        for campo, (prev, new) in changes.items():
            cursor = conn.execute(
                "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
                "created_at, sync_ok) VALUES (?,?,?,?,?,?,1)",
                (guia, autor, campo, prev, new, now),
            )
            edit_ids.append(cursor.lastrowid or 0)

        conn.commit()
        return FieldsUpdateResult(guia=guia, page_id=page_id, changes=changes, edit_ids=edit_ids)
    finally:
        conn.close()
