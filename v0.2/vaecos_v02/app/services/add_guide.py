"""Atomic creation of a single new guide.

Phase 2.3: la operadora puede crear guías nuevas desde la app sin pasar por
Excel ni Notion directamente. El patrón es el mismo de update_guide:
escribir Notion FIRST y, si responde OK, insertar en local + audit.

Si Notion rechaza, no se inserta nada local pero queda registrado el intento
en `guide_edits` con sync_ok=0 (campo='__create__').
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vaecos_v02.providers.notion_provider import NotionProvider
from vaecos_v02.storage.db import connect


@dataclass(frozen=True)
class AddGuideResult:
    guia: str
    page_id: str
    edit_id: int


def add_guide(
    db_path: Path,
    notion: NotionProvider,
    fields: dict,
    autor: str,
) -> AddGuideResult:
    guia = (fields.get("guia") or "").strip()
    cliente = (fields.get("cliente") or "").strip()
    estado = (fields.get("estado_novedad") or "").strip()
    carrier = ((fields.get("carrier") or "effi").strip().lower()) or "effi"
    telefono = (fields.get("telefono") or "").strip()
    producto = (fields.get("producto") or "").strip()
    valor_raw = fields.get("valor", "")
    cantidad_raw = fields.get("cantidad", "")

    if not guia:
        raise ValueError("Número de guía requerido.")
    if not cliente:
        raise ValueError("Cliente requerido.")
    if telefono and not telefono.isdigit():
        raise ValueError(f"Teléfono debe ser numérico: '{telefono}'.")

    valor: float | None = None
    if valor_raw not in (None, ""):
        try:
            valor = float(valor_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Valor inválido: '{valor_raw}'.")
        if valor < 0:
            raise ValueError("Valor no puede ser negativo.")

    cantidad: int | None = None
    if cantidad_raw not in (None, ""):
        try:
            cantidad = int(cantidad_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Cantidad inválida: '{cantidad_raw}'.")
        if cantidad < 0:
            raise ValueError("Cantidad no puede ser negativa.")

    # Uniqueness check (local). Si está archivada con la misma guia, también la consideramos colisión.
    conn = connect(db_path)
    try:
        existing = conn.execute(
            "SELECT page_id, archived FROM guides WHERE UPPER(guia) = UPPER(?)",
            (guia,),
        ).fetchone()
        if existing:
            if existing["archived"]:
                raise ValueError(
                    f"Ya existe una guía archivada con número {guia}. "
                    "Verificá en Notion antes de crear una nueva."
                )
            raise ValueError(f"Ya existe una guía con número {guia}.")
    finally:
        conn.close()

    now = datetime.now().isoformat(timespec="seconds")

    # Notion FIRST. Si falla, no insertamos local pero auditamos el intento.
    try:
        page_id = notion.create_guide_page(
            guia=guia,
            cliente=cliente,
            carrier=carrier,
            estado_novedad=estado,
            telefono=telefono,
            valor=str(valor) if valor is not None else "",
            cantidad=cantidad or 0,
            producto=producto,
        )
    except Exception as exc:  # noqa: BLE001
        conn = connect(db_path)
        try:
            conn.execute(
                "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
                "created_at, sync_ok, error_msg) VALUES (?,?,?,?,?,?,0,?)",
                (guia, autor, "__create__", "", cliente, now, str(exc)),
            )
            conn.commit()
        finally:
            conn.close()
        raise

    if not page_id:
        raise RuntimeError("Notion no devolvió page_id al crear la página.")

    # Notion creó la página — insertamos local + audit
    canonical_estado = estado
    if estado:
        try:
            canonical_estado = notion._resolve_select_option("Estado novedad", estado)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            canonical_estado = estado  # fallback al valor original si falla la resolución

    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO guides (
                page_id, guia, cliente, telefono, estado_novedad, carrier,
                producto, valor, cantidad, fecha_ultimo_seguimiento,
                archived, last_synced_at, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,NULL,0,?,?)""",
            (
                page_id, guia, cliente, telefono, canonical_estado, carrier,
                producto, valor, cantidad,
                now, now,
            ),
        )
        cursor = conn.execute(
            "INSERT INTO guide_edits (guia, autor, campo, valor_anterior, valor_nuevo, "
            "created_at, sync_ok) VALUES (?,?,?,?,?,?,1)",
            (guia, autor, "__create__", "", cliente, now),
        )
        edit_id = cursor.lastrowid or 0
        conn.commit()
    finally:
        conn.close()

    return AddGuideResult(guia=guia, page_id=page_id, edit_id=edit_id)
