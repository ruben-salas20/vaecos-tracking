from __future__ import annotations

import sqlite3
from pathlib import Path


class DashboardRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def latest_run(self) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM runs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
            )

    def count_runs(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS c FROM runs").fetchone()
            return int(row["c"]) if row else 0

    def get_run(self, run_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()

    def count_run_results(self, run_id: int, resultado_filter: str = "") -> int:
        with self._connect() as connection:
            if resultado_filter:
                row = connection.execute(
                    "SELECT COUNT(*) AS c FROM run_results WHERE run_id = ? AND resultado = ?",
                    (run_id, resultado_filter),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) AS c FROM run_results WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
            return int(row["c"]) if row else 0

    def get_run_results(
        self,
        run_id: int,
        resultado_filter: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        sql = """
            SELECT rr.guia, rr.cliente, rr.carrier,
                   rr.estado_notion_actual, rr.estado_effi_actual,
                   rr.estado_propuesto, rr.resultado, rr.motivo,
                   rr.requiere_accion, rr.actualizacion_notion,
                   rr.error, rr.notas_operador,
                   (SELECT MAX(tse.event_at)
                    FROM tracking_status_events tse
                    WHERE tse.run_id = rr.run_id
                      AND tse.guia = rr.guia) AS latest_status_date
            FROM run_results rr
            WHERE rr.run_id = ?
        """
        params: list = [run_id]
        if resultado_filter:
            sql += " AND rr.resultado = ?"
            params.append(resultado_filter)
        sql += " ORDER BY rr.guia ASC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self._connect() as connection:
            return list(connection.execute(sql, tuple(params)).fetchall())

    def result_counts(self, run_id: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT resultado, COUNT(*) AS total FROM run_results WHERE run_id = ? GROUP BY resultado ORDER BY total DESC, resultado ASC",
                    (run_id,),
                ).fetchall()
            )

    def proposed_status_counts(self, run_id: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT COALESCE(estado_propuesto, 'N/D') AS estado_propuesto, COUNT(*) AS total FROM run_results WHERE run_id = ? GROUP BY COALESCE(estado_propuesto, 'N/D') ORDER BY total DESC, estado_propuesto ASC",
                    (run_id,),
                ).fetchall()
            )

    def top_guides_with_changes(self, limit: int = 10) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT guia, COUNT(*) AS total_cambios
                    FROM run_results
                    WHERE resultado = 'changed'
                    GROUP BY guia
                    ORDER BY total_cambios DESC, guia ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            )

    def get_results_requiring_attention(self, run_id: int) -> list[sqlite3.Row]:
        """Returns all non-unchanged results for a run, ordered by urgency."""
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT guia, cliente, carrier, estado_notion_actual, estado_effi_actual,
                           estado_propuesto, resultado, motivo, requiere_accion,
                           actualizacion_notion, error
                    FROM run_results
                    WHERE run_id = ? AND resultado != 'unchanged'
                    ORDER BY
                        CASE resultado
                            WHEN 'changed'       THEN 1
                            WHEN 'manual_review' THEN 2
                            WHEN 'parse_error'   THEN 3
                            WHEN 'error'         THEN 4
                            ELSE 5
                        END,
                        guia ASC
                    """,
                    (run_id,),
                ).fetchall()
            )

    def run_duration_seconds(self, run_id: int) -> int | None:
        """Returns run duration in seconds, or None if not finished yet."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT CAST(
                    (julianday(finished_at) - julianday(started_at)) * 86400
                    AS INTEGER
                ) AS duration
                FROM runs
                WHERE id = ? AND finished_at IS NOT NULL
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return int(row["duration"]) if row["duration"] is not None else None

    def kpi_summary(self, days: int = 30) -> sqlite3.Row | None:
        """Aggregate counters for the analytics KPI cards."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    COUNT(DISTINCT r.id) AS total_runs,
                    COUNT(DISTINCT rr.guia) AS unique_guides,
                    COUNT(*) AS total_rows,
                    SUM(CASE WHEN rr.resultado = 'changed'       THEN 1 ELSE 0 END) AS changed,
                    SUM(CASE WHEN rr.resultado = 'unchanged'     THEN 1 ELSE 0 END) AS unchanged,
                    SUM(CASE WHEN rr.resultado = 'manual_review' THEN 1 ELSE 0 END) AS manual_review,
                    SUM(CASE WHEN rr.resultado = 'parse_error'   THEN 1 ELSE 0 END) AS parse_error,
                    SUM(CASE WHEN rr.resultado = 'error'         THEN 1 ELSE 0 END) AS error
                FROM run_results rr
                JOIN runs r ON r.id = rr.run_id
                WHERE date(r.started_at) >= date('now', ?)
                """,
                (window,),
            ).fetchone()

    def attention_trend(self, days: int = 30) -> list[sqlite3.Row]:
        """Per-day count of non-unchanged guides in the window."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT date(r.started_at) AS day, COUNT(*) AS total
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.resultado != 'unchanged'
                      AND date(r.started_at) >= date('now', ?)
                    GROUP BY day
                    ORDER BY day ASC
                    """,
                    (window,),
                ).fetchall()
            )

    def runs_summary_by_day(self, days: int = 30) -> list[sqlite3.Row]:
        """Per-day counts and breakdown for the stacked bar chart."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        date(r.started_at) AS day,
                        SUM(CASE WHEN rr.resultado = 'unchanged'     THEN 1 ELSE 0 END) AS unchanged,
                        SUM(CASE WHEN rr.resultado = 'changed'       THEN 1 ELSE 0 END) AS changed,
                        SUM(CASE WHEN rr.resultado = 'manual_review' THEN 1 ELSE 0 END) AS manual_review,
                        SUM(CASE WHEN rr.resultado = 'parse_error'   THEN 1 ELSE 0 END) AS parse_error,
                        SUM(CASE WHEN rr.resultado = 'error'         THEN 1 ELSE 0 END) AS error
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE date(r.started_at) >= date('now', ?)
                    GROUP BY day
                    ORDER BY day ASC
                    """,
                    (window,),
                ).fetchall()
            )

    def top_problem_clients(self, days: int = 30, limit: int = 10) -> list[sqlite3.Row]:
        """Clients with the most non-unchanged results in the window."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        rr.cliente,
                        COUNT(*) AS total_issues,
                        SUM(CASE WHEN rr.resultado = 'changed'       THEN 1 ELSE 0 END) AS changed,
                        SUM(CASE WHEN rr.resultado = 'manual_review' THEN 1 ELSE 0 END) AS manual_review,
                        SUM(CASE WHEN rr.resultado = 'parse_error'   THEN 1 ELSE 0 END) AS parse_error,
                        SUM(CASE WHEN rr.resultado = 'error'         THEN 1 ELSE 0 END) AS error,
                        COUNT(DISTINCT rr.guia) AS unique_guides
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.resultado != 'unchanged'
                      AND date(r.started_at) >= date('now', ?)
                    GROUP BY rr.cliente
                    ORDER BY total_issues DESC, rr.cliente ASC
                    LIMIT ?
                    """,
                    (window, limit),
                ).fetchall()
            )

    def carrier_breakdown(self, days: int = 30) -> list[sqlite3.Row]:
        """Count rows per carrier + result breakdown within window."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        COALESCE(rr.carrier, 'effi') AS carrier,
                        COUNT(*) AS total_rows,
                        COUNT(DISTINCT rr.guia) AS unique_guides,
                        SUM(CASE WHEN rr.resultado = 'changed'       THEN 1 ELSE 0 END) AS changed,
                        SUM(CASE WHEN rr.resultado = 'unchanged'     THEN 1 ELSE 0 END) AS unchanged,
                        SUM(CASE WHEN rr.resultado = 'manual_review' THEN 1 ELSE 0 END) AS manual_review,
                        SUM(CASE WHEN rr.resultado = 'parse_error'   THEN 1 ELSE 0 END) AS parse_error,
                        SUM(CASE WHEN rr.resultado = 'error'         THEN 1 ELSE 0 END) AS error
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE date(r.started_at) >= date('now', ?)
                    GROUP BY COALESCE(rr.carrier, 'effi')
                    ORDER BY total_rows DESC
                    """,
                    (window,),
                ).fetchall()
            )

    def avg_time_in_status(self, days: int = 90) -> list[sqlite3.Row]:
        """Approximate how many consecutive runs a guide spends in each Effi status.

        Aggregates consecutive occurrences of (guia, estado_effi_actual) within the window
        and averages across guides. Not exact SLA, but detects stuck statuses.
        """
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    WITH per_guide AS (
                        SELECT
                            rr.estado_effi_actual AS status,
                            rr.guia,
                            COUNT(*) AS cnt
                        FROM run_results rr
                        JOIN runs r ON r.id = rr.run_id
                        WHERE rr.estado_effi_actual IS NOT NULL
                          AND rr.estado_effi_actual != ''
                          AND date(r.started_at) >= date('now', ?)
                        GROUP BY rr.estado_effi_actual, rr.guia
                    )
                    SELECT
                        status,
                        ROUND(AVG(cnt), 2) AS avg_runs,
                        COUNT(DISTINCT guia) AS guides_affected,
                        MAX(cnt) AS max_runs
                    FROM per_guide
                    GROUP BY status
                    ORDER BY avg_runs DESC, status ASC
                    """,
                    (window,),
                ).fetchall()
            )

    def client_history(
        self, cliente: str, days: int = 90, limit: int | None = None, offset: int = 0,
    ) -> list[sqlite3.Row]:
        """All results for a given client within the window, newest first."""
        window = f"-{int(days)} days"
        sql = """
            SELECT
                rr.run_id, r.started_at, r.mode, rr.carrier,
                rr.guia, rr.telefono, rr.estado_notion_actual, rr.estado_effi_actual,
                rr.estado_propuesto, rr.resultado, rr.motivo,
                rr.requiere_accion, rr.error
            FROM run_results rr
            JOIN runs r ON r.id = rr.run_id
            WHERE rr.cliente = ?
              AND date(r.started_at) >= date('now', ?)
            ORDER BY r.started_at DESC, rr.guia ASC
        """
        params: list = [cliente, window]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self._connect() as connection:
            return list(connection.execute(sql, tuple(params)).fetchall())

    def count_client_history(self, cliente: str, days: int = 90) -> int:
        window = f"-{int(days)} days"
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS c FROM run_results rr
                JOIN runs r ON r.id = rr.run_id
                WHERE rr.cliente = ? AND date(r.started_at) >= date('now', ?)
                """,
                (cliente, window),
            ).fetchone()
            return int(row["c"]) if row else 0

    def latest_phone_for_client(self, cliente: str) -> str:
        """Most recent non-empty telefono recorded for this client name."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT rr.telefono FROM run_results rr
                JOIN runs r ON r.id = rr.run_id
                WHERE rr.cliente = ? AND rr.telefono IS NOT NULL AND rr.telefono != ''
                ORDER BY r.started_at DESC LIMIT 1
                """,
                (cliente,),
            ).fetchone()
            return row["telefono"] if row else ""

    def latest_phone_for_guide(self, guia: str) -> str:
        """Most recent non-empty telefono recorded for this guide."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT telefono FROM run_results
                WHERE guia = ? AND telefono IS NOT NULL AND telefono != ''
                ORDER BY run_id DESC LIMIT 1
                """,
                (guia,),
            ).fetchone()
            return row["telefono"] if row else ""

    def count_search_clients_by_name(self, query: str) -> int:
        like = f"%{query.strip()}%"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(DISTINCT cliente) AS c FROM run_results WHERE cliente LIKE ? COLLATE NOCASE",
                (like,),
            ).fetchone()
            return int(row["c"]) if row else 0

    def search_clients_by_name(self, query: str, limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
        """Distinct clients whose name contains query (case-insensitive).
        Returns most recent telefono and guide count per client."""
        like = f"%{query.strip()}%"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        rr.cliente,
                        COUNT(DISTINCT rr.guia) AS guide_count,
                        (SELECT rr2.telefono FROM run_results rr2
                         JOIN runs r2 ON r2.id = rr2.run_id
                         WHERE rr2.cliente = rr.cliente
                           AND rr2.telefono IS NOT NULL AND rr2.telefono != ''
                         ORDER BY r2.started_at DESC LIMIT 1) AS telefono,
                        MAX(r.started_at) AS last_seen
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.cliente LIKE ? COLLATE NOCASE
                    GROUP BY rr.cliente
                    ORDER BY last_seen DESC
                    LIMIT ? OFFSET ?
                    """,
                    (like, limit, offset),
                ).fetchall()
            )

    # ─────────────────────── Guide edits (β2 — audit trail) ───────────────────────

    def list_edits_for_guide(self, guia: str, limit: int = 50) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(connection.execute(
                "SELECT id, guia, autor, campo, valor_anterior, valor_nuevo, "
                "created_at, sync_ok, error_msg FROM guide_edits "
                "WHERE guia = ? ORDER BY created_at DESC LIMIT ?",
                (guia, limit),
            ).fetchall())

    def latest_edit_for_guide(self, guia: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, autor, campo, valor_anterior, valor_nuevo, created_at, sync_ok "
                "FROM guide_edits WHERE guia = ? ORDER BY created_at DESC LIMIT 1",
                (guia,),
            ).fetchone()

    # ─────────────────────── Guide notes (β1) ───────────────────────

    def list_notes_for_guide(self, guia: str) -> list[sqlite3.Row]:
        """All notes for a guide, newest first."""
        with self._connect() as connection:
            return list(connection.execute(
                "SELECT id, guia, autor, body, created_at, edited_at "
                "FROM guide_notes WHERE guia = ? ORDER BY created_at DESC",
                (guia,),
            ).fetchall())

    def create_note(self, guia: str, autor: str, body: str) -> int:
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO guide_notes (guia, autor, body, created_at) VALUES (?,?,?,?)",
                (guia, autor, body, now),
            )
            connection.commit()
            return cursor.lastrowid or 0

    def get_note(self, note_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, guia, autor, body, created_at, edited_at FROM guide_notes WHERE id = ?",
                (note_id,),
            ).fetchone()

    def update_note(self, note_id: int, body: str) -> bool:
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE guide_notes SET body = ?, edited_at = ? WHERE id = ?",
                (body, now, note_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_note(self, note_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM guide_notes WHERE id = ?", (note_id,))
            connection.commit()
            return cursor.rowcount > 0

    def notes_count_by_guide(self, guides: list[str]) -> dict[str, int]:
        """Return { guia: count } for the given list of guides. Empty input → {}."""
        if not guides:
            return {}
        placeholders = ",".join("?" * len(guides))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT guia, COUNT(*) AS c FROM guide_notes WHERE guia IN ({placeholders}) GROUP BY guia",
                tuple(guides),
            ).fetchall()
            return {r["guia"]: r["c"] for r in rows}

    def _all_guides_where(
        self,
        estado: str,
        carrier: str,
        query: str,
        include_archived: bool,
    ) -> tuple[str, list]:
        """Construye el WHERE+params para list_all_guides y count_all_guides."""
        wheres: list[str] = []
        params: list = []
        if not include_archived:
            wheres.append("g.archived = 0")
        if estado:
            wheres.append("g.estado_novedad = ?")
            params.append(estado)
        if carrier:
            wheres.append("g.carrier = ?")
            params.append(carrier.lower())
        if query:
            like = f"%{query.strip()}%"
            wheres.append(
                "(g.cliente LIKE ? COLLATE NOCASE "
                "OR g.guia LIKE ? COLLATE NOCASE "
                "OR g.telefono LIKE ?)"
            )
            params.extend([like, like, like])
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        return where_sql, params

    def count_all_guides(
        self,
        estado: str = "",
        carrier: str = "",
        query: str = "",
        include_archived: bool = False,
    ) -> int:
        """Cuenta total de guías que matchean los filtros (sin paginar)."""
        where_sql, params = self._all_guides_where(estado, carrier, query, include_archived)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS c FROM guides g {where_sql}",
                tuple(params),
            ).fetchone()
            return int(row["c"]) if row else 0

    def list_all_guides(
        self,
        estado: str = "",
        carrier: str = "",
        query: str = "",
        include_archived: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """List rows from the guides snapshot with optional filters and pagination."""
        where_sql, params = self._all_guides_where(estado, carrier, query, include_archived)
        params.append(limit)
        params.append(offset)
        with self._connect() as connection:
            return list(connection.execute(
                f"""
                SELECT g.*,
                  (SELECT rr.resultado FROM run_results rr
                   JOIN runs r ON r.id = rr.run_id
                   WHERE rr.guia = g.guia
                   ORDER BY r.started_at DESC LIMIT 1) AS ultimo_resultado,
                  (SELECT r.started_at FROM run_results rr
                   JOIN runs r ON r.id = rr.run_id
                   WHERE rr.guia = g.guia
                   ORDER BY r.started_at DESC LIMIT 1) AS ultima_corrida
                FROM guides g
                {where_sql}
                ORDER BY g.estado_novedad, g.cliente
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall())

    def list_guide_states(self) -> list[sqlite3.Row]:
        """All distinct estado_novedad values present in the snapshot, with counts."""
        with self._connect() as connection:
            return list(connection.execute(
                """
                SELECT estado_novedad, COUNT(*) AS n
                FROM guides
                WHERE archived = 0 AND estado_novedad IS NOT NULL AND estado_novedad != ''
                GROUP BY estado_novedad
                ORDER BY n DESC
                """,
            ).fetchall())

    def guides_count(self) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived, "
                "MAX(last_synced_at) AS last_sync "
                "FROM guides"
            ).fetchone()
            return {
                "total": row["total"] or 0,
                "archived": row["archived"] or 0,
                "last_sync": row["last_sync"] or "",
            }

    _SEARCH_BY_PHONE_SQL = """
        SELECT
            g.guia, g.cliente, g.telefono, g.carrier,
            g.estado_novedad AS estado_notion,
            NULL AS estado_effi,
            (SELECT rr2.resultado FROM run_results rr2
             JOIN runs r2 ON r2.id = rr2.run_id
             WHERE rr2.guia = g.guia
             ORDER BY r2.started_at DESC LIMIT 1) AS ultimo_resultado,
            COALESCE(
                (SELECT MAX(r2.started_at) FROM run_results rr2
                 JOIN runs r2 ON r2.id = rr2.run_id
                 WHERE rr2.guia = g.guia),
                g.last_synced_at
            ) AS last_seen
        FROM guides g
        WHERE g.telefono = ? AND g.archived = 0

        UNION

        SELECT
            rr.guia, rr.cliente, rr.telefono, rr.carrier,
            rr.estado_notion_actual AS estado_notion,
            rr.estado_effi_actual AS estado_effi,
            rr.resultado AS ultimo_resultado,
            r.started_at AS last_seen
        FROM run_results rr
        JOIN runs r ON r.id = rr.run_id
        WHERE rr.telefono = ?
          AND rr.guia NOT IN (SELECT guia FROM guides)
        GROUP BY rr.guia
    """

    def search_by_phone(
        self, telefono: str, limit: int | None = None, offset: int = 0,
    ) -> list[sqlite3.Row]:
        """All distinct guides associated with this telefono."""
        tel = telefono.strip()
        sql = f"{self._SEARCH_BY_PHONE_SQL}\nORDER BY last_seen DESC"
        params: list = [tel, tel]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self._connect() as connection:
            return list(connection.execute(sql, tuple(params)).fetchall())

    def count_search_by_phone(self, telefono: str) -> int:
        tel = telefono.strip()
        sql = f"SELECT COUNT(*) AS c FROM ({self._SEARCH_BY_PHONE_SQL})"
        with self._connect() as connection:
            row = connection.execute(sql, (tel, tel)).fetchone()
            return int(row["c"]) if row else 0

    def client_summary(self, cliente: str, days: int = 90) -> sqlite3.Row | None:
        """Aggregated counters for a single client."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    COUNT(DISTINCT rr.guia) AS unique_guides,
                    COUNT(*) AS total_rows,
                    SUM(CASE WHEN rr.resultado = 'changed'       THEN 1 ELSE 0 END) AS changed,
                    SUM(CASE WHEN rr.resultado = 'unchanged'     THEN 1 ELSE 0 END) AS unchanged,
                    SUM(CASE WHEN rr.resultado = 'manual_review' THEN 1 ELSE 0 END) AS manual_review,
                    SUM(CASE WHEN rr.resultado = 'parse_error'   THEN 1 ELSE 0 END) AS parse_error,
                    SUM(CASE WHEN rr.resultado = 'error'         THEN 1 ELSE 0 END) AS error
                FROM run_results rr
                JOIN runs r ON r.id = rr.run_id
                WHERE rr.cliente = ?
                  AND date(r.started_at) >= date('now', ?)
                """,
                (cliente, window),
            ).fetchone()

    def guide_history(self, guide: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT rr.run_id, r.started_at, r.mode, rr.resultado, rr.carrier,
                           rr.estado_notion_actual, rr.estado_effi_actual,
                           rr.estado_propuesto, rr.actualizacion_notion,
                           rr.motivo, rr.error, rr.cliente,
                           rr.notas_operador,
                           (SELECT MAX(tse.event_at)
                            FROM tracking_status_events tse
                            WHERE tse.run_id = rr.run_id
                              AND tse.guia = rr.guia) AS latest_status_date
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.guia = ?
                    ORDER BY rr.run_id DESC
                    LIMIT ?
                    """,
                    (guide, limit),
                ).fetchall()
            )

    def update_operator_note(self, run_id: int, guia: str, note: str) -> bool:
        """Persist or clear an operator note for a given (run_id, guia) pair.

        Returns True if at least one row was updated, False otherwise.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE run_results SET notas_operador = ? WHERE run_id = ? AND guia = ?",
                (note, run_id, guia),
            )
            connection.commit()
            return cursor.rowcount > 0

    def export_effi_rows(self, run_id: int) -> list[sqlite3.Row]:
        """Return only rows where requiere_accion == 'Gestionar con encargado'
        for Effi CSV export.

        Columns returned: guia, estado_effi_actual, motivo, notas_operador.
        """
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT guia, estado_effi_actual, motivo, notas_operador
                    FROM run_results
                    WHERE run_id = ?
                      AND requiere_accion = 'Gestionar con encargado'
                    ORDER BY guia ASC
                    """,
                    (run_id,),
                ).fetchall()
            )

    def latest_por_recoger_total(self) -> int:
        """Count de guías ACTUALMENTE en 'Por recoger (INFORMADO)' según Notion.

        Fuente de verdad: tabla local `guides` (sincronizada desde Notion).
        Antes contaba filas de la última corrida (`run_results`), lo que producía
        números obsoletos cuando la operadora cambiaba el estado en Notion pero
        el motor ya no procesaba la guía por estar en estado excluido.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM guides
                WHERE estado_novedad = 'Por recoger (INFORMADO)'
                  AND archived = 0
                """
            ).fetchone()
        return int(row["total"]) if row and row["total"] is not None else 0

    def por_recoger_guides_list(self) -> list[sqlite3.Row]:
        """Return the list of guides currently in 'Por recoger (INFORMADO)'
        state in the most recent run, with guia, cliente, and requiere_accion."""
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT guia, cliente, requiere_accion
                    FROM run_results
                    WHERE run_id = (SELECT MAX(id) FROM runs)
                      AND estado_propuesto = 'Por recoger (INFORMADO)'
                    ORDER BY guia ASC
                    """
                ).fetchall()
            )

    def por_recoger_delivery_breakdown(self) -> dict[str, int]:
        """Counts del flujo Por recoger usando Notion como fuente de verdad.

        - total_por_recoger = pending: guías que AHORA están Por recoger según Notion.
        - delivered/returned/resolved_other: guías que TUVIERON Por recoger
          históricamente pero su estado actual en Notion es OTRO.

        Mantiene coherencia con `latest_por_recoger_total` y
        `por_recoger_detailed_breakdown` — los 3 dan el mismo `total_por_recoger`.
        """
        detail = self.por_recoger_detailed_breakdown()
        return {
            "total_por_recoger": detail["total_por_recoger"],
            "delivered": len(detail["delivered"]),
            "returned": len(detail["returned"]),
            "resolved_other": len(detail.get("resolved_other", [])),
        }

    def por_recoger_detailed_breakdown(self) -> dict:
        """Breakdown detallado del flujo Por recoger usando Notion como fuente de verdad.

        Coherente con `latest_por_recoger_total` y `por_recoger_delivery_breakdown`.

        Estructura:
          - pending: TODAS las guías que ACTUALMENTE están Por recoger según
            la tabla `guides` (sincronizada desde Notion). Incluye guías que
            nunca pasaron por el motor (recién creadas, marcadas manualmente).
          - delivered / returned / resolved_other: guías que TUVIERON el estado
            Por recoger históricamente pero su estado actual es OTRO.
          - total_por_recoger: alias de len(pending).
        """
        with self._connect() as connection:
            # 1) PENDING — snapshot actual de Notion.
            pending_rows = connection.execute(
                """
                SELECT
                    g.guia,
                    g.cliente,
                    g.carrier,
                    g.estado_novedad AS current_notion_estado,
                    g.estado_novedad AS estado_propuesto,
                    NULL AS requiere_accion,
                    (SELECT MAX(rr.run_id) FROM run_results rr WHERE rr.guia = g.guia) AS run_id
                FROM guides g
                WHERE g.estado_novedad = 'Por recoger (INFORMADO)'
                  AND g.archived = 0
                ORDER BY g.cliente ASC, g.guia ASC
                """
            ).fetchall()

            # 2) EX-POR-RECOGER — guías que pasaron por ese estado pero su estado actual es OTRO.
            ex_rows = connection.execute(
                """
                SELECT
                    rr1.guia, rr1.cliente, rr1.carrier,
                    rr1.estado_propuesto, rr1.requiere_accion, rr1.run_id,
                    g.estado_novedad AS current_notion_estado
                FROM run_results rr1
                LEFT JOIN guides g ON g.guia = rr1.guia
                WHERE rr1.guia IN (
                    SELECT DISTINCT guia FROM run_results
                    WHERE estado_propuesto = 'Por recoger (INFORMADO)'
                )
                AND rr1.run_id = (
                    SELECT MAX(rr2.run_id)
                    FROM run_results rr2
                    WHERE rr2.guia = rr1.guia
                )
                AND COALESCE(g.archived, 0) = 0
                AND COALESCE(g.estado_novedad, '') != 'Por recoger (INFORMADO)'
                ORDER BY rr1.guia ASC
                """
            ).fetchall()

        delivered: list[sqlite3.Row] = []
        returned: list[sqlite3.Row] = []
        resolved_other: list[sqlite3.Row] = []

        for row in ex_rows:
            current = (row["current_notion_estado"] or "").strip()
            state = (current or (row["estado_propuesto"] or "")).upper()
            if "ENTREGAD" in state:
                delivered.append(row)
            elif "DEVOLUCI" in state or "DEVUELT" in state or "INDEMN" in state:
                returned.append(row)
            else:
                resolved_other.append(row)

        return {
            "total_por_recoger": len(pending_rows),
            "delivered": delivered,
            "returned": returned,
            "pending": list(pending_rows),
            "resolved_other": resolved_other,
        }
