from __future__ import annotations

import sqlite3
from pathlib import Path


class DashboardRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
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
                    SELECT guia, cliente, estado_notion_actual, estado_effi_actual,
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
                    SELECT guia, cliente, estado_notion_actual, estado_effi_actual,
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

    def guide_history(self, guide: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT rr.run_id, r.started_at, r.mode, rr.resultado, rr.estado_notion_actual,
                           rr.estado_effi_actual, rr.estado_propuesto, rr.actualizacion_notion,
                           rr.motivo, rr.error, rr.cliente
                    FROM run_results rr
                    JOIN runs r ON r.id = rr.run_id
                    WHERE rr.guia = ?
                    ORDER BY rr.run_id DESC
                    LIMIT ?
                    """,
                    (guide, limit),
                ).fetchall()
            )
