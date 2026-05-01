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
                    ORDER BY rr.guia ASC
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
        """Count of 'Por recoger (INFORMADO)' guides in the most recent run.

        Returns 0 when no runs exist or no matching guides in the latest run.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM run_results
                WHERE run_id = (SELECT MAX(id) FROM runs)
                  AND estado_propuesto = 'Por recoger (INFORMADO)'
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
        """Breakdown of 'Por recoger (INFORMADO)' guides into delivered vs returned.

        Tracks guides that appeared as 'Por recoger (INFORMADO)' in any run
        and checks whether they later ended up in a delivery state
        (ENTREGADA, ENTREGADO) or a return state (DEVUELTO, DEVOLUCION).

        Returns dict with keys:
          - total_por_recoger: count still in 'Por recoger' in the latest run
          - delivered: count that transitioned to delivery
          - returned: count that transitioned to return
        """
        with self._connect() as connection:
            # Total Por recoger in latest run (reuse existing method)
            total = self.latest_por_recoger_total()

            # Guides that were ever 'Por recoger (INFORMADO)' (distinct)
            ever_por_recoger = connection.execute(
                """
                SELECT DISTINCT guia
                FROM run_results
                WHERE estado_propuesto = 'Por recoger (INFORMADO)'
                """
            ).fetchall()
            por_recoger_guides = [row["guia"] for row in ever_por_recoger]

            if not por_recoger_guides:
                return {"total_por_recoger": total, "delivered": 0, "returned": 0}

            # For each guide that was ever Por recoger, find the latest
            # estado_propuesto across all runs.
            delivered = 0
            returned = 0

            for guia in por_recoger_guides:
                row = connection.execute(
                    """
                    SELECT rr.estado_propuesto, rr.run_id
                    FROM run_results rr
                    WHERE rr.guia = ?
                    ORDER BY rr.run_id DESC
                    LIMIT 1
                    """,
                    (guia,),
                ).fetchone()
                if row is None:
                    continue
                estado = (row["estado_propuesto"] or "").upper()
                # Delivery states
                if "ENTREGAD" in estado:
                    delivered += 1
                # Return states
                elif "DEVOLUCI" in estado or "DEVUELT" in estado:
                    returned += 1
                # Still Por recoger → counted in total_por_recoger, not delivered/returned

            return {
                "total_por_recoger": total,
                "delivered": delivered,
                "returned": returned,
            }

    def por_recoger_detailed_breakdown(self) -> dict:
        """Returns detailed breakdown of Por recoger guides with actual
        guide lists for operational verification.

        Classifies every guide that was ever 'Por recoger (INFORMADO)'
        into one of three groups based on its latest estado_propuesto:

        - delivered: latest state contains ENTREGAD (e.g. ENTREGADA, ENTREGADO)
        - returned:  latest state contains DEVOLUCI or DEVUELT
        - pending:   latest state is still Por recoger (INFORMADO)

        Returns:
            dict with keys:
              - total_por_recoger (int): count still pending
              - delivered (list[sqlite3.Row]): guide rows with guia, cliente,
                carrier, estado_propuesto, requiere_accion, run_id
              - returned (list[sqlite3.Row]): same structure
              - pending (list[sqlite3.Row]): same structure
        """
        with self._connect() as connection:
            # Get latest estado_propuesto for every guide that was ever
            # Por recoger, in a single query.
            rows = connection.execute(
                """
                SELECT rr1.guia, rr1.cliente, rr1.carrier,
                       rr1.estado_propuesto, rr1.requiere_accion, rr1.run_id
                FROM run_results rr1
                WHERE rr1.guia IN (
                    SELECT DISTINCT guia FROM run_results
                    WHERE estado_propuesto = 'Por recoger (INFORMADO)'
                )
                AND rr1.run_id = (
                    SELECT MAX(rr2.run_id)
                    FROM run_results rr2
                    WHERE rr2.guia = rr1.guia
                )
                ORDER BY rr1.guia ASC
                """
            ).fetchall()

        delivered: list[sqlite3.Row] = []
        returned: list[sqlite3.Row] = []
        pending: list[sqlite3.Row] = []

        for row in rows:
            estado = (row["estado_propuesto"] or "").upper()
            if "ENTREGAD" in estado:
                delivered.append(row)
            elif "DEVOLUCI" in estado or "DEVUELT" in estado:
                returned.append(row)
            elif "POR RECOGER" in estado or "INFORMADO" in estado:
                pending.append(row)
            # else: unrecognized final state, excluded

        return {
            "total_por_recoger": len(pending),
            "delivered": delivered,
            "returned": returned,
            "pending": pending,
        }
