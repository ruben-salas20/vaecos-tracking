from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vaecos_v02.storage.db import connect as v02_connect


VALID_TIPOS = ("intimo_femenino", "otro")


@dataclass(frozen=True)
class CatalogItem:
    id: int
    sku: str
    descripcion_exacta: str
    precio_declarado: float
    tipo: str
    activo: int
    notas: str | None
    aliases: tuple[str, ...]
    created_at: str
    updated_at: str
    updated_by: str


class CatalogRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def list_all(self, include_inactive: bool = True) -> list[CatalogItem]:
        conn = v02_connect(self.db_path)
        try:
            if include_inactive:
                rows = conn.execute(
                    "SELECT * FROM effi_catalog ORDER BY tipo DESC, sku ASC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM effi_catalog WHERE activo = 1 ORDER BY tipo DESC, sku ASC"
                ).fetchall()
            return [self._row_to_item(row) for row in rows]
        finally:
            conn.close()

    def get_by_id(self, item_id: int) -> CatalogItem | None:
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM effi_catalog WHERE id = ?", (item_id,)
            ).fetchone()
            return self._row_to_item(row) if row else None
        finally:
            conn.close()

    def get_by_sku(self, sku: str) -> CatalogItem | None:
        conn = v02_connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM effi_catalog WHERE sku = ?", (sku.strip(),)
            ).fetchone()
            return self._row_to_item(row) if row else None
        finally:
            conn.close()

    def create(
        self,
        *,
        sku: str,
        descripcion_exacta: str,
        precio_declarado: float,
        tipo: str,
        notas: str | None,
        aliases: list[str] | tuple[str, ...] | None,
        updated_by: str,
    ) -> int:
        if tipo not in VALID_TIPOS:
            raise ValueError(f"tipo inválido: {tipo}")
        if precio_declarado < 0:
            raise ValueError("precio_declarado no puede ser negativo")
        now = datetime.now().isoformat(timespec="seconds")
        aliases_json = json.dumps(_clean_aliases(aliases), ensure_ascii=False)
        conn = v02_connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO effi_catalog
                    (sku, descripcion_exacta, precio_declarado, tipo, activo, notas, aliases, created_at, updated_at, updated_by)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (sku.strip(), descripcion_exacta.strip(), float(precio_declarado), tipo,
                 (notas or "").strip() or None, aliases_json, now, now, updated_by),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def update(
        self,
        item_id: int,
        *,
        descripcion_exacta: str,
        precio_declarado: float,
        tipo: str,
        notas: str | None,
        aliases: list[str] | tuple[str, ...] | None,
        updated_by: str,
    ) -> None:
        if tipo not in VALID_TIPOS:
            raise ValueError(f"tipo inválido: {tipo}")
        if precio_declarado < 0:
            raise ValueError("precio_declarado no puede ser negativo")
        now = datetime.now().isoformat(timespec="seconds")
        aliases_json = json.dumps(_clean_aliases(aliases), ensure_ascii=False)
        conn = v02_connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE effi_catalog
                SET descripcion_exacta = ?, precio_declarado = ?, tipo = ?, notas = ?, aliases = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (descripcion_exacta.strip(), float(precio_declarado), tipo,
                 (notas or "").strip() or None, aliases_json, now, updated_by, item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def toggle_active(self, item_id: int, updated_by: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        conn = v02_connect(self.db_path)
        try:
            conn.execute(
                "UPDATE effi_catalog SET activo = 1 - activo, updated_at = ?, updated_by = ? WHERE id = ?",
                (now, updated_by, item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, item_id: int) -> None:
        conn = v02_connect(self.db_path)
        try:
            conn.execute("DELETE FROM effi_catalog WHERE id = ?", (item_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_item(row) -> CatalogItem:
        # Soporta dbs antiguas que no tengan 'aliases' (defensive).
        aliases_raw = "[]"
        try:
            aliases_raw = row["aliases"] or "[]"
        except (IndexError, KeyError):
            aliases_raw = "[]"
        try:
            aliases = tuple(_clean_aliases(json.loads(aliases_raw)))
        except (json.JSONDecodeError, TypeError):
            aliases = ()
        return CatalogItem(
            id=row["id"],
            sku=row["sku"],
            descripcion_exacta=row["descripcion_exacta"],
            precio_declarado=row["precio_declarado"],
            tipo=row["tipo"],
            activo=row["activo"],
            notas=row["notas"],
            aliases=aliases,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
        )


def _clean_aliases(raw) -> list[str]:
    """Normaliza una lista/tupla/iterable de aliases: strip, dedupe case-insensitive, descarta vacíos."""
    if raw is None:
        return []
    seen: dict[str, str] = {}
    for item in raw:
        s = (item or "").strip() if isinstance(item, str) else ""
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen[key] = s
    return list(seen.values())


def parse_aliases_textarea(text: str | None) -> list[str]:
    """Convierte el contenido del textarea (un alias por línea) en lista limpia."""
    if not text:
        return []
    return _clean_aliases(text.replace("\r", "").split("\n"))
