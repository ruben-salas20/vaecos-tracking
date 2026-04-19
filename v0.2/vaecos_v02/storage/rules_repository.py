from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, replace
from datetime import datetime

from vaecos_v02.core.models import Rule


VALID_ESTADO_KINDS = {"any", "equals_one_of", "contains_any_of"}
VALID_NOVELTY_KINDS = {"any", "contains_any_of"}
VALID_DAYS_COMPARATORS = {"gt", "gte", "lt", "lte", "no_date"}


class RulesRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    # ------------------------------------------------------------------ read
    def list_rules(
        self, carrier: str | None = None, only_enabled: bool = False
    ) -> list[Rule]:
        sql = "SELECT * FROM rules"
        clauses: list[str] = []
        params: list = []
        if carrier:
            clauses.append("(carrier = ? OR carrier = '*')")
            params.append(carrier)
        if only_enabled:
            clauses.append("enabled = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY priority ASC, id ASC"
        cursor = self.connection.execute(sql, params)
        return [self._row_to_rule(row) for row in cursor.fetchall()]

    def get_rule(self, rule_id: int) -> Rule | None:
        row = self.connection.execute(
            "SELECT * FROM rules WHERE id = ?", (rule_id,)
        ).fetchone()
        return self._row_to_rule(row) if row is not None else None

    # ------------------------------------------------------------------ write
    def save_rule(self, rule: Rule, *, changed_by: str = "operadora") -> Rule:
        """Inserts a new rule (rule.id is None) or updates an existing one."""
        self._validate(rule)
        now = _now_iso()
        if rule.id is None:
            cursor = self.connection.execute(
                """
                INSERT INTO rules (
                    carrier, name, priority, enabled,
                    estado_match_kind, estado_match_values,
                    novelty_match_kind, novelty_match_values,
                    days_comparator, days_threshold,
                    estado_propuesto, motivo_template, requiere_accion,
                    review_needed, notes, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.carrier,
                    rule.name,
                    rule.priority,
                    1 if rule.enabled else 0,
                    rule.estado_match_kind,
                    json.dumps(rule.estado_match_values, ensure_ascii=False),
                    rule.novelty_match_kind,
                    json.dumps(rule.novelty_match_values, ensure_ascii=False),
                    rule.days_comparator,
                    rule.days_threshold,
                    rule.estado_propuesto,
                    rule.motivo_template,
                    rule.requiere_accion,
                    1 if rule.review_needed else 0,
                    rule.notes,
                    now,
                    changed_by,
                ),
            )
            new_id = int(cursor.lastrowid)
            saved = replace(rule, id=new_id, updated_at=now, updated_by=changed_by)
            self._audit(
                None, saved, action="create", changed_by=changed_by, at=now
            )
        else:
            previous = self.get_rule(rule.id)
            self.connection.execute(
                """
                UPDATE rules SET
                    carrier = ?, name = ?, priority = ?, enabled = ?,
                    estado_match_kind = ?, estado_match_values = ?,
                    novelty_match_kind = ?, novelty_match_values = ?,
                    days_comparator = ?, days_threshold = ?,
                    estado_propuesto = ?, motivo_template = ?, requiere_accion = ?,
                    review_needed = ?, notes = ?, updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (
                    rule.carrier,
                    rule.name,
                    rule.priority,
                    1 if rule.enabled else 0,
                    rule.estado_match_kind,
                    json.dumps(rule.estado_match_values, ensure_ascii=False),
                    rule.novelty_match_kind,
                    json.dumps(rule.novelty_match_values, ensure_ascii=False),
                    rule.days_comparator,
                    rule.days_threshold,
                    rule.estado_propuesto,
                    rule.motivo_template,
                    rule.requiere_accion,
                    1 if rule.review_needed else 0,
                    rule.notes,
                    now,
                    changed_by,
                    rule.id,
                ),
            )
            saved = replace(rule, updated_at=now, updated_by=changed_by)
            action = "update"
            if previous is not None and previous.enabled != rule.enabled:
                action = "enable" if rule.enabled else "disable"
            self._audit(
                previous, saved, action=action, changed_by=changed_by, at=now
            )
        self.connection.commit()
        return saved

    def delete_rule(self, rule_id: int, *, changed_by: str = "operadora") -> bool:
        previous = self.get_rule(rule_id)
        if previous is None:
            return False
        self.connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self._audit(
            previous, None, action="delete", changed_by=changed_by, at=_now_iso()
        )
        self.connection.commit()
        return True

    def toggle_rule(self, rule_id: int, *, changed_by: str = "operadora") -> Rule | None:
        rule = self.get_rule(rule_id)
        if rule is None:
            return None
        return self.save_rule(replace(rule, enabled=not rule.enabled), changed_by=changed_by)

    def history_for_rule(self, rule_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT id, rule_id, action, before_json, after_json,
                       changed_at, changed_by, note
                FROM rule_history
                WHERE rule_id = ?
                ORDER BY id DESC
                """,
                (rule_id,),
            ).fetchall()
        )

    # --------------------------------------------------------------- seeding
    def seed_if_empty(self, default_rules: list[Rule]) -> int:
        """Inserts default_rules only when the rules table is empty.

        Returns the number of rules inserted (0 if table already had rules).
        """
        count = self.connection.execute(
            "SELECT COUNT(*) AS c FROM rules"
        ).fetchone()["c"]
        if count > 0:
            return 0
        now = _now_iso()
        inserted = 0
        for rule in default_rules:
            self._validate(rule)
            cursor = self.connection.execute(
                """
                INSERT INTO rules (
                    carrier, name, priority, enabled,
                    estado_match_kind, estado_match_values,
                    novelty_match_kind, novelty_match_values,
                    days_comparator, days_threshold,
                    estado_propuesto, motivo_template, requiere_accion,
                    review_needed, notes, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.carrier,
                    rule.name,
                    rule.priority,
                    1 if rule.enabled else 0,
                    rule.estado_match_kind,
                    json.dumps(rule.estado_match_values, ensure_ascii=False),
                    rule.novelty_match_kind,
                    json.dumps(rule.novelty_match_values, ensure_ascii=False),
                    rule.days_comparator,
                    rule.days_threshold,
                    rule.estado_propuesto,
                    rule.motivo_template,
                    rule.requiere_accion,
                    1 if rule.review_needed else 0,
                    rule.notes,
                    now,
                    "seed",
                ),
            )
            new_id = int(cursor.lastrowid)
            seeded = replace(rule, id=new_id, updated_at=now, updated_by="seed")
            self._audit(None, seeded, action="seed", changed_by="seed", at=now)
            inserted += 1
        self.connection.commit()
        return inserted

    # ------------------------------------------------------------- internals
    def _audit(
        self,
        before: Rule | None,
        after: Rule | None,
        *,
        action: str,
        changed_by: str,
        at: str,
        note: str | None = None,
    ) -> None:
        rule_id = after.id if after is not None else (before.id if before else None)
        self.connection.execute(
            """
            INSERT INTO rule_history (
                rule_id, action, before_json, after_json, changed_at, changed_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                action,
                _rule_to_json(before) if before else None,
                _rule_to_json(after) if after else None,
                at,
                changed_by,
                note,
            ),
        )

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> Rule:
        return Rule(
            id=int(row["id"]),
            carrier=str(row["carrier"]),
            name=str(row["name"]),
            priority=int(row["priority"]),
            enabled=bool(row["enabled"]),
            estado_match_kind=str(row["estado_match_kind"]),
            estado_match_values=_safe_json_list(row["estado_match_values"]),
            novelty_match_kind=str(row["novelty_match_kind"]),
            novelty_match_values=_safe_json_list(row["novelty_match_values"]),
            days_comparator=row["days_comparator"],
            days_threshold=(
                int(row["days_threshold"]) if row["days_threshold"] is not None else None
            ),
            estado_propuesto=row["estado_propuesto"],
            motivo_template=str(row["motivo_template"]),
            requiere_accion=str(row["requiere_accion"] or ""),
            review_needed=bool(row["review_needed"]),
            notes=str(row["notes"] or ""),
            updated_at=str(row["updated_at"] or ""),
            updated_by=str(row["updated_by"] or ""),
        )

    @staticmethod
    def _validate(rule: Rule) -> None:
        if rule.estado_match_kind not in VALID_ESTADO_KINDS:
            raise ValueError(
                f"estado_match_kind invalido: {rule.estado_match_kind!r}"
            )
        if rule.novelty_match_kind not in VALID_NOVELTY_KINDS:
            raise ValueError(
                f"novelty_match_kind invalido: {rule.novelty_match_kind!r}"
            )
        if rule.days_comparator is not None and rule.days_comparator not in VALID_DAYS_COMPARATORS:
            raise ValueError(f"days_comparator invalido: {rule.days_comparator!r}")
        if rule.days_comparator in {"gt", "gte", "lt", "lte"} and rule.days_threshold is None:
            raise ValueError(
                "days_threshold es obligatorio cuando days_comparator es numerico"
            )
        if not rule.motivo_template.strip():
            raise ValueError("motivo_template no puede estar vacio")
        if not rule.name.strip():
            raise ValueError("name no puede estar vacio")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_json_list(value) -> list[str]:
    if value is None:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _rule_to_json(rule: Rule) -> str:
    return json.dumps(asdict(rule), ensure_ascii=False, default=str)
