from __future__ import annotations

import sqlite3
from datetime import datetime

from vaecos_v02.core.models import EffiTrackingData, ProcessingResult
from vaecos_v02.storage.db import seed_default_rules


class RunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_run(self, started_at: datetime, dry_run: bool) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs (started_at, mode) VALUES (?, ?)",
            (
                started_at.isoformat(timespec="seconds"),
                "dry-run" if dry_run else "apply",
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finalize_run(
        self, run_id: int, finished_at: datetime, results: list[ProcessingResult]
    ) -> None:
        self.connection.execute(
            """
            UPDATE runs
            SET finished_at = ?, total_processed = ?, total_changed = ?, total_unchanged = ?,
                total_manual_review = ?, total_error = ?
            WHERE id = ?
            """,
            (
                finished_at.isoformat(timespec="seconds"),
                len(results),
                sum(1 for result in results if result.resultado == "changed"),
                sum(1 for result in results if result.resultado == "unchanged"),
                sum(1 for result in results if result.resultado == "manual_review"),
                sum(1 for result in results if result.resultado in {"error", "parse_error"}),
                run_id,
            ),
        )
        self.connection.commit()

    def save_result(self, run_id: int, result: ProcessingResult) -> None:
        self.connection.execute(
            """
            INSERT INTO run_results (
                run_id, guia, cliente, estado_notion_actual, estado_effi_actual,
                estado_propuesto, resultado, motivo, requiere_accion,
                actualizacion_notion, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                result.guia,
                result.cliente,
                result.estado_notion_actual,
                result.estado_effi_actual,
                result.estado_propuesto,
                result.resultado,
                result.motivo,
                result.requiere_accion,
                result.actualizacion_notion,
                result.error,
            ),
        )
        self.connection.commit()

    def save_tracking(self, run_id: int, guia: str, tracking: EffiTrackingData) -> None:
        for event in tracking.status_history:
            self.connection.execute(
                "INSERT INTO tracking_status_events (run_id, guia, event_at, status) VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    guia,
                    event.date.isoformat(sep=" ") if event.date else None,
                    event.status,
                ),
            )
        for event in tracking.novelty_history:
            self.connection.execute(
                "INSERT INTO tracking_novelty_events (run_id, guia, event_at, novelty, details) VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    guia,
                    event.date.isoformat(sep=" ") if event.date else None,
                    event.novelty,
                    event.details,
                ),
            )
        self.connection.commit()

    def list_runs(self, limit: int = 20) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT id, started_at, finished_at, mode, total_processed, total_changed,
                   total_unchanged, total_manual_review, total_error
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return list(cursor.fetchall())

    def get_run(self, run_id: int) -> sqlite3.Row | None:
        cursor = self.connection.execute(
            """
            SELECT id, started_at, finished_at, mode, total_processed, total_changed,
                   total_unchanged, total_manual_review, total_error
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        )
        return cursor.fetchone()

    def get_results_for_run(self, run_id: int) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT guia, cliente, estado_notion_actual, estado_effi_actual,
                   estado_propuesto, resultado, motivo, requiere_accion,
                   actualizacion_notion, error
            FROM run_results
            WHERE run_id = ?
            ORDER BY guia ASC
            """,
            (run_id,),
        )
        return list(cursor.fetchall())

    def get_previous_run_id(self, run_id: int) -> int | None:
        cursor = self.connection.execute(
            "SELECT id FROM runs WHERE id < ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None

    def get_latest_run_id(self) -> int | None:
        cursor = self.connection.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return int(row["id"]) if row else None

    def get_result_counts_for_run(self, run_id: int) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT resultado, COUNT(*) AS total
            FROM run_results
            WHERE run_id = ?
            GROUP BY resultado
            ORDER BY total DESC, resultado ASC
            """,
            (run_id,),
        )
        return list(cursor.fetchall())

    def get_proposed_status_counts_for_run(self, run_id: int) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT COALESCE(estado_propuesto, 'N/D') AS estado_propuesto, COUNT(*) AS total
            FROM run_results
            WHERE run_id = ?
            GROUP BY COALESCE(estado_propuesto, 'N/D')
            ORDER BY total DESC, estado_propuesto ASC
            """,
            (run_id,),
        )
        return list(cursor.fetchall())

    def get_top_motivos_for_run(
        self, run_id: int, limit: int = 10
    ) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT motivo, COUNT(*) AS total
            FROM run_results
            WHERE run_id = ?
            GROUP BY motivo
            ORDER BY total DESC, motivo ASC
            LIMIT ?
            """,
            (run_id, limit),
        )
        return list(cursor.fetchall())

    def get_guide_history(self, guia: str, limit: int = 10) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT rr.run_id, r.started_at, r.mode, rr.resultado, rr.estado_notion_actual,
                   rr.estado_effi_actual, rr.estado_propuesto, rr.actualizacion_notion, rr.motivo, rr.error
            FROM run_results rr
            JOIN runs r ON r.id = rr.run_id
            WHERE rr.guia = ?
            ORDER BY rr.run_id DESC
            LIMIT ?
            """,
            (guia, limit),
        )
        return list(cursor.fetchall())


class RulesRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def seed_if_empty(self) -> None:
        seed_default_rules(self.connection)

    def list_all(self) -> list[dict]:
        cursor = self.connection.execute(
            "SELECT * FROM rules ORDER BY priority ASC, id ASC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_enabled(self) -> list[dict]:
        cursor = self.connection.execute(
            "SELECT * FROM rules WHERE enabled = 1 ORDER BY priority ASC, id ASC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get(self, rule_id: int) -> dict | None:
        cursor = self.connection.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def create(self, data: dict) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO rules (priority, enabled, name, match_estado, match_estado_contains,
                match_novelty_contains, match_notion_estado, match_notion_estado_contains,
                min_days, estado_propuesto, motivo, requiere_accion,
                review_needed, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(data["priority"]),
                1 if data.get("enabled", True) else 0,
                str(data["name"]),
                data.get("match_estado") or None,
                data.get("match_estado_contains") or None,
                data.get("match_novelty_contains") or None,
                data.get("match_notion_estado") or None,
                data.get("match_notion_estado_contains") or None,
                int(data["min_days"]) if data.get("min_days") not in (None, "") else None,
                data.get("estado_propuesto") or None,
                str(data["motivo"]),
                str(data["requiere_accion"]),
                1 if data.get("review_needed") else 0,
                str(data.get("updated_by") or "operadora"),
                now,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def update(self, rule_id: int, data: dict) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.connection.execute(
            """
            UPDATE rules SET priority=?, enabled=?, name=?, match_estado=?,
                match_estado_contains=?, match_novelty_contains=?,
                match_notion_estado=?, match_notion_estado_contains=?,
                min_days=?, estado_propuesto=?, motivo=?, requiere_accion=?,
                review_needed=?, updated_by=?, updated_at=?
            WHERE id=?
            """,
            (
                int(data["priority"]),
                1 if data.get("enabled", True) else 0,
                str(data["name"]),
                data.get("match_estado") or None,
                data.get("match_estado_contains") or None,
                data.get("match_novelty_contains") or None,
                data.get("match_notion_estado") or None,
                data.get("match_notion_estado_contains") or None,
                int(data["min_days"]) if data.get("min_days") not in (None, "") else None,
                data.get("estado_propuesto") or None,
                str(data["motivo"]),
                str(data["requiere_accion"]),
                1 if data.get("review_needed") else 0,
                str(data.get("updated_by") or "operadora"),
                now,
                rule_id,
            ),
        )
        self.connection.commit()

    def toggle(self, rule_id: int) -> None:
        self.connection.execute(
            "UPDATE rules SET enabled = CASE WHEN enabled = 1 THEN 0 ELSE 1 END, "
            "updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), rule_id),
        )
        self.connection.commit()

    def delete(self, rule_id: int) -> None:
        self.connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self.connection.commit()
