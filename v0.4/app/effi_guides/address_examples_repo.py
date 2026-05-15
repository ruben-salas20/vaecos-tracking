"""CRUD de ejemplos few-shot para el validador IA de direcciones.

Los ejemplos viven en la tabla effi_address_examples y se editan desde
/effi/address-examples (admin). El validador IA los lee al construirse y
arma el system prompt dinámicamente.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


VALID_VEREDICTOS = ("valid", "review", "invalid")


@dataclass
class AddressExample:
    id: int
    address: str
    veredicto: str
    reason: str
    activo: bool
    created_at: str
    created_by: str | None


class AddressExamplesRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row(self, r: sqlite3.Row) -> AddressExample:
        return AddressExample(
            id=r["id"], address=r["address"], veredicto=r["veredicto"],
            reason=r["reason"], activo=bool(r["activo"]),
            created_at=r["created_at"], created_by=r["created_by"],
        )

    def list_all(self) -> list[AddressExample]:
        with self._connect() as c:
            return [
                self._row(r) for r in c.execute(
                    "SELECT * FROM effi_address_examples ORDER BY veredicto, id"
                )
            ]

    def list_active(self) -> list[AddressExample]:
        """Solo ejemplos activos — los que el validador inyecta al prompt."""
        with self._connect() as c:
            return [
                self._row(r) for r in c.execute(
                    "SELECT * FROM effi_address_examples WHERE activo = 1 ORDER BY veredicto, id"
                )
            ]

    def get(self, ex_id: int) -> AddressExample | None:
        with self._connect() as c:
            r = c.execute("SELECT * FROM effi_address_examples WHERE id = ?", (ex_id,)).fetchone()
            return self._row(r) if r else None

    def create(self, *, address: str, veredicto: str, reason: str, created_by: str) -> int | None:
        """Devuelve el id nuevo, o None si veredicto inválido."""
        if veredicto not in VALID_VEREDICTOS:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            cur = c.execute(
                """INSERT INTO effi_address_examples
                    (address, veredicto, reason, activo, created_at, created_by)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (address.strip(), veredicto, reason.strip(), now, created_by),
            )
            c.commit()
            return cur.lastrowid

    def update(self, ex_id: int, *, address: str, veredicto: str, reason: str) -> bool:
        if veredicto not in VALID_VEREDICTOS:
            return False
        with self._connect() as c:
            cur = c.execute(
                "UPDATE effi_address_examples SET address = ?, veredicto = ?, reason = ? WHERE id = ?",
                (address.strip(), veredicto, reason.strip(), ex_id),
            )
            c.commit()
            return cur.rowcount > 0

    def toggle(self, ex_id: int) -> bool | None:
        """Flip activo 0↔1. Devuelve el nuevo estado, o None si no existe."""
        with self._connect() as c:
            r = c.execute("SELECT activo FROM effi_address_examples WHERE id = ?", (ex_id,)).fetchone()
            if not r:
                return None
            new_val = 0 if r["activo"] else 1
            c.execute("UPDATE effi_address_examples SET activo = ? WHERE id = ?", (new_val, ex_id))
            c.commit()
            return bool(new_val)

    def delete(self, ex_id: int) -> bool:
        with self._connect() as c:
            cur = c.execute("DELETE FROM effi_address_examples WHERE id = ?", (ex_id,))
            c.commit()
            return cur.rowcount > 0

    def counts(self) -> dict:
        """Conteo por veredicto + activos/inactivos, para mostrar en la UI."""
        with self._connect() as c:
            total = c.execute("SELECT COUNT(*) FROM effi_address_examples").fetchone()[0]
            activos = c.execute("SELECT COUNT(*) FROM effi_address_examples WHERE activo = 1").fetchone()[0]
            by_v = {
                r[0]: r[1] for r in c.execute(
                    "SELECT veredicto, COUNT(*) FROM effi_address_examples WHERE activo = 1 GROUP BY veredicto"
                )
            }
            return {
                "total": total, "activos": activos, "inactivos": total - activos,
                "valid": by_v.get("valid", 0),
                "review": by_v.get("review", 0),
                "invalid": by_v.get("invalid", 0),
            }
