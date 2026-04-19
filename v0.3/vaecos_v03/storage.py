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

    def list_runs(self, limit: int = 50) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            )

    def get_run(self, run_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()

    def get_run_results(self, run_id: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT guia, cliente, carrier, estado_notion_actual, estado_effi_actual,
                           estado_propuesto, resultado, motivo, requiere_accion,
                           actualizacion_notion, error
                    FROM run_results
                    WHERE run_id = ?
                    ORDER BY guia ASC
                    """,
                    (run_id,),
                ).fetchall()
            )

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

    def client_history(self, cliente: str, days: int = 90) -> list[sqlite3.Row]:
        """All results for a given client within the window, newest first."""
        window = f"-{int(days)} days"
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        rr.run_id, r.started_at, r.mode, rr.carrier,
                        rr.guia, rr.estado_notion_actual, rr.estado_effi_actual,
                        rr.estado_propuesto, rr.resultado, rr.motivo,
                        rr.requiere_accion, rr.error
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.cliente = ?
                      AND date(r.started_at) >= date('now', ?)
                    ORDER BY r.started_at DESC, rr.guia ASC
                    """,
                    (cliente, window),
                ).fetchall()
            )

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
                           rr.estado_notion_actual, rr.estado_effi_actual, rr.estado_propuesto,
                           rr.actualizacion_notion, rr.motivo, rr.error, rr.cliente
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.guia = ?
                    ORDER BY rr.run_id DESC
                    LIMIT ?
                    """,
                    (guide, limit),
                ).fetchall()
            )
