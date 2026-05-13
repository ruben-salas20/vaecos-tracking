"""Repositorios para las tablas effi_orders, effi_audit_log y effi_review_queue.

Encapsulan toda la persistencia del módulo Creador guías. El runner orquesta
sobre estas APIs; los repos no llaman al runner ni al bot.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vaecos_v02.storage.db import connect as v02_connect


# ──────────────────────────────────────────────────────────────────────
# effi_orders — registro idempotente de cada orden procesada
# ──────────────────────────────────────────────────────────────────────


VALID_ORDER_STATUSES = ("done", "failed", "human_review", "pending")
VALID_CLASSIFICATIONS = ("combo", "femenino", "otro", "escalation")
VALID_CONTENIDO_MODOS = ("copiar_documento", "texto_manual")
VALID_ADDRESS_STATUSES = ("valid", "review", "invalid")


@dataclass(frozen=True)
class EffiOrderRecord:
    orden_id: int
    cliente: str | None
    direccion: str | None
    productos_json: str
    classification: str
    valor_declarado: float | None
    contenido_modo: str | None
    contenido_texto: str | None
    address_status: str | None
    remision_id: int | None
    guia_id: int | None
    status: str
    error_msg: str | None
    processed_at: str
    updated_at: str

    @property
    def productos(self) -> list:
        try:
            return json.loads(self.productos_json or "[]")
        except (TypeError, ValueError):
            return []


class EffiOrdersRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def is_processed(self, orden_id: int) -> bool:
        """True si la orden ya existe con status='done' (no reprocesar)."""
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT status FROM effi_orders WHERE orden_id = ?", (orden_id,)
            ).fetchone()
            return row is not None and row["status"] == "done"
        finally:
            conn.close()

    def get(self, orden_id: int) -> EffiOrderRecord | None:
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM effi_orders WHERE orden_id = ?", (orden_id,)
            ).fetchone()
            return self._row_to_record(row) if row else None
        finally:
            conn.close()

    def upsert(self, **kwargs) -> None:
        """Insert or update by orden_id. Llena/actualiza todos los campos provistos."""
        if "orden_id" not in kwargs:
            raise ValueError("orden_id es requerido")
        if kwargs.get("status") and kwargs["status"] not in VALID_ORDER_STATUSES:
            raise ValueError(f"status inválido: {kwargs['status']}")
        if kwargs.get("classification") and kwargs["classification"] not in VALID_CLASSIFICATIONS:
            raise ValueError(f"classification inválida: {kwargs['classification']}")
        now = datetime.now().isoformat(timespec="seconds")
        kwargs.setdefault("processed_at", now)
        kwargs["updated_at"] = now

        conn = v02_connect(self.db_path)
        try:
            existing = conn.execute(
                "SELECT orden_id FROM effi_orders WHERE orden_id = ?",
                (kwargs["orden_id"],),
            ).fetchone()
            if existing:
                set_clauses = []
                params: list = []
                for key, value in kwargs.items():
                    if key == "orden_id":
                        continue
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
                params.append(kwargs["orden_id"])
                conn.execute(
                    f"UPDATE effi_orders SET {', '.join(set_clauses)} WHERE orden_id = ?",
                    params,
                )
            else:
                cols = list(kwargs.keys())
                placeholders = ", ".join("?" for _ in cols)
                conn.execute(
                    f"INSERT INTO effi_orders ({', '.join(cols)}) VALUES ({placeholders})",
                    [kwargs[c] for c in cols],
                )
            conn.commit()
        finally:
            conn.close()

    def list_recent(self, limit: int = 50) -> list[EffiOrderRecord]:
        conn = v02_connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM effi_orders ORDER BY processed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]
        finally:
            conn.close()

    def counts_by_status(self, since_iso: str | None = None) -> dict[str, int]:
        conn = v02_connect(self.db_path)
        try:
            if since_iso:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS c FROM effi_orders WHERE processed_at >= ? GROUP BY status",
                    (since_iso,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS c FROM effi_orders GROUP BY status"
                ).fetchall()
            return {r["status"]: r["c"] for r in rows}
        finally:
            conn.close()

    @staticmethod
    def _row_to_record(row) -> EffiOrderRecord:
        return EffiOrderRecord(
            orden_id=row["orden_id"],
            cliente=row["cliente"],
            direccion=row["direccion"],
            productos_json=row["productos_json"] or "[]",
            classification=row["classification"],
            valor_declarado=row["valor_declarado"],
            contenido_modo=row["contenido_modo"],
            contenido_texto=row["contenido_texto"],
            address_status=row["address_status"],
            remision_id=row["remision_id"],
            guia_id=row["guia_id"],
            status=row["status"],
            error_msg=row["error_msg"],
            processed_at=row["processed_at"],
            updated_at=row["updated_at"],
        )


# ──────────────────────────────────────────────────────────────────────
# effi_audit_log — historial granular de acciones del bot
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuditEntry:
    id: int
    ts: str
    action: str
    orden_id: int | None
    actor: str
    payload_json: str | None
    ok: int


class EffiAuditLogRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def log(
        self,
        action: str,
        *,
        orden_id: int | None = None,
        payload: dict | None = None,
        ok: bool = True,
        actor: str = "bot",
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else None
        conn = v02_connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO effi_audit_log (ts, action, orden_id, actor, payload_json, ok)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, action, orden_id, actor, payload_json, 1 if ok else 0),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def list_recent(self, limit: int = 100, only_orden_id: int | None = None) -> list[AuditEntry]:
        conn = v02_connect(self.db_path)
        try:
            if only_orden_id is not None:
                rows = conn.execute(
                    "SELECT * FROM effi_audit_log WHERE orden_id = ? ORDER BY ts DESC LIMIT ?",
                    (only_orden_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM effi_audit_log ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [
                AuditEntry(
                    id=r["id"],
                    ts=r["ts"],
                    action=r["action"],
                    orden_id=r["orden_id"],
                    actor=r["actor"],
                    payload_json=r["payload_json"],
                    ok=r["ok"],
                )
                for r in rows
            ]
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────────────────
# effi_review_queue — cola humana para casos no automatizables
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewItem:
    id: int
    orden_id: int
    reason: str
    details_json: str | None
    created_at: str
    resolved: int
    resolved_by: str | None
    resolved_at: str | None
    resolution_notes: str | None

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except (TypeError, ValueError):
            return {}


class EffiReviewQueueRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def enqueue(
        self,
        orden_id: int,
        reason: str,
        details: dict | None = None,
    ) -> tuple[int, bool]:
        """Encola un item para revisión humana. Devuelve (id, is_new).

        is_new=False indica que ya existía un item pendiente para esta orden con
        la misma reason — el caller puede usar esto para evitar spam de notificaciones.
        """
        now = datetime.now().isoformat(timespec="seconds")
        details_json = json.dumps(details, ensure_ascii=False) if details is not None else None
        conn = v02_connect(self.db_path)
        try:
            existing = conn.execute(
                "SELECT id FROM effi_review_queue WHERE orden_id = ? AND reason = ? AND resolved = 0",
                (orden_id, reason),
            ).fetchone()
            if existing:
                return (int(existing["id"]), False)
            cursor = conn.execute(
                """
                INSERT INTO effi_review_queue (orden_id, reason, details_json, created_at, resolved)
                VALUES (?, ?, ?, ?, 0)
                """,
                (orden_id, reason, details_json, now),
            )
            conn.commit()
            return (int(cursor.lastrowid), True)
        finally:
            conn.close()

    def list_pending(self) -> list[ReviewItem]:
        conn = v02_connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM effi_review_queue WHERE resolved = 0 ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_item(r) for r in rows]
        finally:
            conn.close()

    def list_recent(self, limit: int = 50) -> list[ReviewItem]:
        conn = v02_connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM effi_review_queue ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_item(r) for r in rows]
        finally:
            conn.close()

    def get(self, item_id: int) -> ReviewItem | None:
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM effi_review_queue WHERE id = ?", (item_id,)
            ).fetchone()
            return self._row_to_item(row) if row else None
        finally:
            conn.close()

    def resolve(self, item_id: int, resolved_by: str, notes: str | None = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        conn = v02_connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE effi_review_queue
                SET resolved = 1, resolved_by = ?, resolved_at = ?, resolution_notes = ?
                WHERE id = ?
                """,
                (resolved_by, now, (notes or "").strip() or None, item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def count_pending(self) -> int:
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM effi_review_queue WHERE resolved = 0"
            ).fetchone()
            return int(row["c"]) if row else 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_item(row) -> ReviewItem:
        return ReviewItem(
            id=row["id"],
            orden_id=row["orden_id"],
            reason=row["reason"],
            details_json=row["details_json"],
            created_at=row["created_at"],
            resolved=row["resolved"],
            resolved_by=row["resolved_by"],
            resolved_at=row["resolved_at"],
            resolution_notes=row["resolution_notes"],
        )
