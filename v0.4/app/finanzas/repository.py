"""Repository del módulo financiero — consultas contra fin_movements / fin_categories.

Diseño: queries optimizadas para la UI (listado paginado, analytics). Devuelve
estructuras planas (dict / NamedTuple-ish) que las rutas consumen y los templates
renderizan.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FinMovement:
    id: int
    fecha: str
    tipo: str
    monto_centavos: int
    moneda: str
    observacion: str
    guia_ref: str | None
    creado_por: str
    creado_at: str
    actualizado_por: str | None
    actualizado_at: str | None
    categorias: list[dict]   # [{id, nombre, color}]

    @property
    def monto_cop(self) -> float:
        return self.monto_centavos / 100.0


@dataclass
class FinCategory:
    id: int
    nombre: str
    color: str | None
    activa: bool


class FinanzasRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # FK CASCADE no funciona en SQLite sin esto — fin_movement_categories
        # quedaría huérfana al borrar un movement sin este pragma.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Categorías ─────────────────────────────────────────────────

    def list_categories(self, only_active: bool = False) -> list[FinCategory]:
        sql = "SELECT id, nombre, color, activa FROM fin_categories"
        if only_active:
            sql += " WHERE activa = 1"
        sql += " ORDER BY nombre"
        with self._connect() as c:
            return [
                FinCategory(id=r["id"], nombre=r["nombre"], color=r["color"], activa=bool(r["activa"]))
                for r in c.execute(sql)
            ]

    def category_usage_counts(self) -> dict[int, int]:
        """{category_id: n_movimientos} — para mostrar cuántos rows usa cada cat."""
        with self._connect() as c:
            return {
                r["id"]: r["n"]
                for r in c.execute(
                    """
                    SELECT c.id, COUNT(mc.movement_id) AS n
                    FROM fin_categories c
                    LEFT JOIN fin_movement_categories mc ON mc.category_id = c.id
                    GROUP BY c.id
                    """
                )
            }

    def create_category(self, nombre: str, color: str | None) -> int | None:
        """Devuelve id si OK, None si nombre duplicado."""
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._connect() as c:
                cur = c.execute(
                    "INSERT INTO fin_categories (nombre, color, activa, created_at) VALUES (?, ?, 1, ?)",
                    (nombre, color, now),
                )
                c.commit()
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def update_category(self, cat_id: int, *, nombre: str, color: str | None) -> bool:
        """Renombrar/recolor. False si no existe o si el nombre nuevo está en uso."""
        try:
            with self._connect() as c:
                cur = c.execute(
                    "UPDATE fin_categories SET nombre = ?, color = ? WHERE id = ?",
                    (nombre, color, cat_id),
                )
                c.commit()
                return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def toggle_category(self, cat_id: int) -> bool | None:
        """Flip activa 0↔1. Devuelve el nuevo valor, o None si no existe."""
        with self._connect() as c:
            row = c.execute("SELECT activa FROM fin_categories WHERE id = ?", (cat_id,)).fetchone()
            if not row:
                return None
            new_val = 0 if row["activa"] else 1
            c.execute("UPDATE fin_categories SET activa = ? WHERE id = ?", (new_val, cat_id))
            c.commit()
            return bool(new_val)

    def get_category(self, cat_id: int) -> FinCategory | None:
        with self._connect() as c:
            r = c.execute(
                "SELECT id, nombre, color, activa FROM fin_categories WHERE id = ?",
                (cat_id,),
            ).fetchone()
            return FinCategory(id=r["id"], nombre=r["nombre"], color=r["color"], activa=bool(r["activa"])) if r else None

    # ── Movimientos: filtros y paginación ──────────────────────────

    def list_movements(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        tipo: str | None = None,
        category_id: int | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FinMovement], int]:
        """Devuelve (page, total_count)."""
        where_clauses: list[str] = []
        params: list = []

        if year is not None:
            where_clauses.append("substr(m.fecha,1,4) = ?")
            params.append(f"{year:04d}")
        if month is not None:
            where_clauses.append("substr(m.fecha,6,2) = ?")
            params.append(f"{month:02d}")
        if date_from:
            where_clauses.append("m.fecha >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("m.fecha <= ?")
            params.append(date_to)
        if tipo and tipo in ("ingreso", "egreso", "transferencia"):
            where_clauses.append("m.tipo = ?")
            params.append(tipo)
        if search:
            where_clauses.append("m.observacion LIKE ?")
            params.append(f"%{search}%")

        # Category filter requires a join with EXISTS
        if category_id is not None:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM fin_movement_categories mc "
                "WHERE mc.movement_id = m.id AND mc.category_id = ?)"
            )
            params.append(category_id)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        with self._connect() as c:
            total = c.execute(
                f"SELECT COUNT(*) AS n FROM fin_movements m{where_sql}",
                params,
            ).fetchone()["n"]

            rows = c.execute(
                f"""
                SELECT m.id, m.fecha, m.tipo, m.monto_centavos, m.moneda, m.observacion,
                       m.guia_ref, m.creado_por, m.creado_at, m.actualizado_por, m.actualizado_at
                FROM fin_movements m
                {where_sql}
                ORDER BY m.fecha DESC, m.id DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

            # Una sola query para todas las categorías de la página
            ids = [r["id"] for r in rows]
            cat_map: dict[int, list[dict]] = {i: [] for i in ids}
            if ids:
                placeholders = ",".join(["?"] * len(ids))
                for cr in c.execute(
                    f"""
                    SELECT mc.movement_id, c.id, c.nombre, c.color
                    FROM fin_movement_categories mc
                    JOIN fin_categories c ON c.id = mc.category_id
                    WHERE mc.movement_id IN ({placeholders})
                    ORDER BY c.nombre
                    """,
                    ids,
                ):
                    cat_map[cr["movement_id"]].append({
                        "id": cr["id"], "nombre": cr["nombre"], "color": cr["color"],
                    })

            movements = [
                FinMovement(
                    id=r["id"], fecha=r["fecha"], tipo=r["tipo"],
                    monto_centavos=r["monto_centavos"], moneda=r["moneda"],
                    observacion=r["observacion"], guia_ref=r["guia_ref"],
                    creado_por=r["creado_por"], creado_at=r["creado_at"],
                    actualizado_por=r["actualizado_por"], actualizado_at=r["actualizado_at"],
                    categorias=cat_map[r["id"]],
                )
                for r in rows
            ]
            return movements, total

    # ── Mutaciones ─────────────────────────────────────────────────

    def create_movement(
        self,
        *,
        fecha: str,
        tipo: str,
        monto_centavos: int,
        observacion: str,
        category_ids: list[int],
        guia_ref: str | None = None,
        creado_por: str,
    ) -> int:
        """Inserta un movimiento + sus relaciones M:N. Devuelve el ID nuevo."""
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            cur = c.execute(
                """
                INSERT INTO fin_movements
                    (fecha, tipo, monto_centavos, moneda, observacion, guia_ref, creado_por, creado_at)
                VALUES (?, ?, ?, 'COP', ?, ?, ?, ?)
                """,
                (fecha, tipo, monto_centavos, observacion, guia_ref, creado_por, now),
            )
            mov_id = cur.lastrowid
            for cat_id in category_ids:
                c.execute(
                    "INSERT OR IGNORE INTO fin_movement_categories (movement_id, category_id) VALUES (?, ?)",
                    (mov_id, cat_id),
                )
            c.commit()
        return mov_id

    def update_movement(
        self,
        mov_id: int,
        *,
        fecha: str,
        tipo: str,
        monto_centavos: int,
        observacion: str,
        category_ids: list[int],
        guia_ref: str | None,
        actualizado_por: str,
    ) -> bool:
        """Actualiza un movimiento + reemplaza las relaciones M:N. False si no existe."""
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            cur = c.execute(
                """
                UPDATE fin_movements
                SET fecha = ?, tipo = ?, monto_centavos = ?, observacion = ?, guia_ref = ?,
                    actualizado_por = ?, actualizado_at = ?
                WHERE id = ?
                """,
                (fecha, tipo, monto_centavos, observacion, guia_ref, actualizado_por, now, mov_id),
            )
            if cur.rowcount == 0:
                return False
            c.execute("DELETE FROM fin_movement_categories WHERE movement_id = ?", (mov_id,))
            for cat_id in category_ids:
                c.execute(
                    "INSERT OR IGNORE INTO fin_movement_categories (movement_id, category_id) VALUES (?, ?)",
                    (mov_id, cat_id),
                )
            c.commit()
        return True

    def delete_movement(self, mov_id: int) -> bool:
        """Borra un movimiento. CASCADE limpia fin_movement_categories."""
        with self._connect() as c:
            cur = c.execute("DELETE FROM fin_movements WHERE id = ?", (mov_id,))
            c.commit()
            return cur.rowcount > 0

    def get_movement(self, mov_id: int) -> FinMovement | None:
        with self._connect() as c:
            r = c.execute(
                """
                SELECT id, fecha, tipo, monto_centavos, moneda, observacion, guia_ref,
                       creado_por, creado_at, actualizado_por, actualizado_at
                FROM fin_movements WHERE id = ?
                """,
                (mov_id,),
            ).fetchone()
            if not r:
                return None
            cats = [
                {"id": cr["id"], "nombre": cr["nombre"], "color": cr["color"]}
                for cr in c.execute(
                    """
                    SELECT c.id, c.nombre, c.color
                    FROM fin_movement_categories mc
                    JOIN fin_categories c ON c.id = mc.category_id
                    WHERE mc.movement_id = ?
                    ORDER BY c.nombre
                    """,
                    (mov_id,),
                )
            ]
            return FinMovement(
                id=r["id"], fecha=r["fecha"], tipo=r["tipo"],
                monto_centavos=r["monto_centavos"], moneda=r["moneda"],
                observacion=r["observacion"], guia_ref=r["guia_ref"],
                creado_por=r["creado_por"], creado_at=r["creado_at"],
                actualizado_por=r["actualizado_por"], actualizado_at=r["actualizado_at"],
                categorias=cats,
            )

    # ── Helpers ────────────────────────────────────────────────────

    # ── Analytics ──────────────────────────────────────────────────

    def _build_where(
        self, year=None, month=None, date_from=None, date_to=None, tipo=None,
    ) -> tuple[str, list]:
        clauses, params = [], []
        if year is not None:
            clauses.append("substr(m.fecha,1,4) = ?"); params.append(f"{year:04d}")
        if month is not None:
            clauses.append("substr(m.fecha,6,2) = ?"); params.append(f"{month:02d}")
        if date_from:
            clauses.append("m.fecha >= ?"); params.append(date_from)
        if date_to:
            clauses.append("m.fecha <= ?"); params.append(date_to)
        if tipo and tipo in ("ingreso", "egreso", "transferencia"):
            clauses.append("m.tipo = ?"); params.append(tipo)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where_sql, params

    def category_breakdown(
        self, *, year=None, month=None, date_from=None, date_to=None,
    ) -> list[dict]:
        """Total por categoría dentro del período, separado por tipo (ingreso/egreso)."""
        where_sql, params = self._build_where(year=year, month=month, date_from=date_from, date_to=date_to)
        with self._connect() as c:
            rows = c.execute(
                f"""
                SELECT c.id, c.nombre, c.color,
                       SUM(CASE WHEN m.tipo='ingreso' THEN m.monto_centavos ELSE 0 END) as ing,
                       SUM(CASE WHEN m.tipo='egreso'  THEN m.monto_centavos ELSE 0 END) as eg,
                       COUNT(DISTINCT m.id) as n
                FROM fin_movements m
                JOIN fin_movement_categories mc ON mc.movement_id = m.id
                JOIN fin_categories c ON c.id = mc.category_id
                {where_sql}
                GROUP BY c.id, c.nombre, c.color
                ORDER BY (ing + eg) DESC
                """,
                params,
            ).fetchall()
            return [
                {
                    "id": r["id"], "nombre": r["nombre"], "color": r["color"],
                    "ingresos_centavos": r["ing"] or 0,
                    "egresos_centavos": r["eg"] or 0,
                    "total_centavos": (r["ing"] or 0) + (r["eg"] or 0),
                    "count": r["n"] or 0,
                }
                for r in rows
            ]

    def monthly_evolution(
        self, *, year=None, date_from=None, date_to=None,
    ) -> list[dict]:
        """Agregado por mes: ingresos, egresos, balance. Para chart."""
        where_sql, params = self._build_where(year=year, date_from=date_from, date_to=date_to)
        with self._connect() as c:
            rows = c.execute(
                f"""
                SELECT substr(m.fecha,1,7) as mes,
                       SUM(CASE WHEN m.tipo='ingreso' THEN m.monto_centavos ELSE 0 END) as ing,
                       SUM(CASE WHEN m.tipo='egreso'  THEN m.monto_centavos ELSE 0 END) as eg,
                       COUNT(*) as n
                FROM fin_movements m
                {where_sql}
                GROUP BY mes
                ORDER BY mes ASC
                """,
                params,
            ).fetchall()
            return [
                {
                    "mes": r["mes"],
                    "ingresos_centavos": r["ing"] or 0,
                    "egresos_centavos": r["eg"] or 0,
                    "balance_centavos": (r["ing"] or 0) - (r["eg"] or 0),
                    "count": r["n"],
                }
                for r in rows
            ]

    def export_all(
        self, *, year=None, month=None, date_from=None, date_to=None, tipo=None,
        category_id=None, search=None,
    ) -> list[dict]:
        """Devuelve TODAS las filas (sin paginar) para export Excel. Con categorías joineadas."""
        movs, _ = self.list_movements(
            year=year, month=month, date_from=date_from, date_to=date_to,
            tipo=tipo, category_id=category_id, search=search,
            limit=100000, offset=0,
        )
        return [
            {
                "id": m.id, "fecha": m.fecha, "tipo": m.tipo,
                "monto": m.monto_cop, "moneda": m.moneda,
                "observacion": m.observacion,
                "categorias": ", ".join(c["nombre"] for c in m.categorias),
                "guia_ref": m.guia_ref or "",
                "creado_por": m.creado_por, "creado_at": m.creado_at,
            }
            for m in movs
        ]

    def available_years(self) -> list[int]:
        """Años con datos, ordenados DESC."""
        with self._connect() as c:
            return [
                int(r[0]) for r in c.execute(
                    "SELECT DISTINCT substr(fecha,1,4) AS y FROM fin_movements ORDER BY y DESC"
                )
            ]

    def totals_for_filters(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        tipo: str | None = None,
        category_id: int | None = None,
        search: str | None = None,
    ) -> dict:
        """Totales agregados para los mismos filtros del listado."""
        where_clauses: list[str] = []
        params: list = []
        if year is not None:
            where_clauses.append("substr(m.fecha,1,4) = ?"); params.append(f"{year:04d}")
        if month is not None:
            where_clauses.append("substr(m.fecha,6,2) = ?"); params.append(f"{month:02d}")
        if date_from:
            where_clauses.append("m.fecha >= ?"); params.append(date_from)
        if date_to:
            where_clauses.append("m.fecha <= ?"); params.append(date_to)
        if tipo and tipo in ("ingreso", "egreso", "transferencia"):
            where_clauses.append("m.tipo = ?"); params.append(tipo)
        if search:
            where_clauses.append("m.observacion LIKE ?"); params.append(f"%{search}%")
        if category_id is not None:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM fin_movement_categories mc "
                "WHERE mc.movement_id = m.id AND mc.category_id = ?)"
            )
            params.append(category_id)
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        with self._connect() as c:
            row = c.execute(
                f"""
                SELECT
                    SUM(CASE WHEN tipo='ingreso'       THEN monto_centavos ELSE 0 END) AS ing,
                    SUM(CASE WHEN tipo='egreso'        THEN monto_centavos ELSE 0 END) AS eg,
                    SUM(CASE WHEN tipo='transferencia' THEN monto_centavos ELSE 0 END) AS tr,
                    COUNT(*) AS n
                FROM fin_movements m
                {where_sql}
                """,
                params,
            ).fetchone()
            return {
                "ingresos_centavos": row["ing"] or 0,
                "egresos_centavos": row["eg"] or 0,
                "transferencias_centavos": row["tr"] or 0,
                "balance_centavos": (row["ing"] or 0) - (row["eg"] or 0),
                "count": row["n"] or 0,
            }
