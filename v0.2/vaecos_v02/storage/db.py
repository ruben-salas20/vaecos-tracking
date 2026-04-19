from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    match_estado TEXT,
    match_estado_contains TEXT,
    match_novelty_contains TEXT,
    min_days INTEGER,
    estado_propuesto TEXT,
    motivo TEXT NOT NULL,
    requiere_accion TEXT NOT NULL,
    review_needed INTEGER NOT NULL DEFAULT 0,
    updated_by TEXT NOT NULL DEFAULT 'sistema',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL,
    total_processed INTEGER DEFAULT 0,
    total_changed INTEGER DEFAULT 0,
    total_unchanged INTEGER DEFAULT 0,
    total_manual_review INTEGER DEFAULT 0,
    total_error INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS run_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    guia TEXT NOT NULL,
    cliente TEXT NOT NULL,
    carrier TEXT NOT NULL DEFAULT 'effi',
    estado_notion_actual TEXT,
    estado_effi_actual TEXT,
    estado_propuesto TEXT,
    resultado TEXT NOT NULL,
    motivo TEXT NOT NULL,
    requiere_accion TEXT NOT NULL,
    actualizacion_notion TEXT,
    error TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS tracking_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    guia TEXT NOT NULL,
    event_at TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS tracking_novelty_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    guia TEXT NOT NULL,
    event_at TEXT,
    novelty TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier TEXT NOT NULL DEFAULT 'effi',
    name TEXT NOT NULL,
    priority INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    estado_match_kind TEXT NOT NULL DEFAULT 'any'
        CHECK (estado_match_kind IN ('any', 'equals_one_of', 'contains_any_of')),
    estado_match_values TEXT NOT NULL DEFAULT '[]',
    novelty_match_kind TEXT NOT NULL DEFAULT 'any'
        CHECK (novelty_match_kind IN ('any', 'contains_any_of')),
    novelty_match_values TEXT NOT NULL DEFAULT '[]',
    days_comparator TEXT
        CHECK (days_comparator IS NULL OR days_comparator IN ('gt', 'gte', 'lt', 'lte', 'no_date')),
    days_threshold INTEGER,
    estado_propuesto TEXT,
    motivo_template TEXT NOT NULL,
    requiere_accion TEXT NOT NULL DEFAULT '',
    review_needed INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT 'operadora'
);

CREATE TABLE IF NOT EXISTS rule_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER,
    action TEXT NOT NULL
        CHECK (action IN ('create', 'update', 'delete', 'enable', 'disable', 'seed')),
    before_json TEXT,
    after_json TEXT,
    changed_at TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'operadora',
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority);
CREATE INDEX IF NOT EXISTS idx_rule_history_rule_id ON rule_history(rule_id);
"""


SEED_RULES = [
    {"priority": 10,  "name": "Paquete en agencia",                      "match_estado": None,                 "match_estado_contains": None,      "match_novelty_contains": "paquete en agencia",                     "min_days": None, "estado_propuesto": "Por recoger (INFORMADO)", "motivo": "Novedad de Effi indica paquete en agencia.",                                      "requiere_accion": "Avisar al cliente que vaya a recoger",  "review_needed": 0},
    {"priority": 20,  "name": "Anomalia \u2013 no quiso recibir",          "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "cliente no quiso recibir",               "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: cliente no quiso recibir.",                     "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 21,  "name": "Anomalia \u2013 no quizo recibir",          "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "cliente no quizo recibir",               "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: cliente no quizo recibir.",                     "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 22,  "name": "Anomalia \u2013 nadie en casa",             "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "nadie en casa",                          "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: nadie en casa.",                                "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 23,  "name": "Anomalia \u2013 direccion no corresponde",  "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "direccion no corresponde",               "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: direccion no corresponde.",                     "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 24,  "name": "Anomalia \u2013 direcci\u00f3n no corresponde", "match_estado": "anomalia",        "match_estado_contains": None,      "match_novelty_contains": "direcci\u00f3n no corresponde",          "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: direcci\u00f3n no corresponde.",                "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 25,  "name": "Anomalia \u2013 no llego al punto",         "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "cliente no llego al punto de encuentro", "min_days": None, "estado_propuesto": "En novedad",              "motivo": "Anomalia con novedad coincidente: cliente no llego al punto de encuentro.",       "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 26,  "name": "Anomalia \u2013 no lleg\u00f3 al punto",    "match_estado": "anomalia",            "match_estado_contains": None,      "match_novelty_contains": "cliente no lleg\u00f3 al punto de encuentro", "min_days": None, "estado_propuesto": "En novedad",           "motivo": "Anomalia con novedad coincidente: cliente no lleg\u00f3 al punto de encuentro.",  "requiere_accion": "Hablar con cliente",                    "review_needed": 0},
    {"priority": 30,  "name": "Devoluci\u00f3n",                          "match_estado": None,                 "match_estado_contains": "devoluci", "match_novelty_contains": None,                                     "min_days": None, "estado_propuesto": "En Devoluci\u00f3n",     "motivo": "Effi reporta devoluci\u00f3n.",                                                    "requiere_accion": "Sin accion",                            "review_needed": 0},
    {"priority": 40,  "name": "Entregado",                                "match_estado": "entregado",           "match_estado_contains": None,      "match_novelty_contains": None,                                     "min_days": None, "estado_propuesto": "ENTREGADA",               "motivo": "Effi reporta entrega exitosa.",                                                   "requiere_accion": "Sin accion",                            "review_needed": 0},
    {"priority": 50,  "name": "Ruta entrega final \u2013 sin movimiento", "match_estado": "ruta entrega final", "match_estado_contains": None,      "match_novelty_contains": None,                                     "min_days": 2,    "estado_propuesto": "Sin movimiento",          "motivo": "RUTA ENTREGA FINAL con {days} dias sin cambio.",                                  "requiere_accion": "Gestionar con encargado",               "review_needed": 0},
    {"priority": 51,  "name": "Ruta entrega final \u2013 en ruta",        "match_estado": "ruta entrega final", "match_estado_contains": None,      "match_novelty_contains": None,                                     "min_days": None, "estado_propuesto": "En ruta de entrega",      "motivo": "RUTA ENTREGA FINAL activo (menos de 1 dia sin cambio o sin fecha).",              "requiere_accion": "Monitorear",                            "review_needed": 0},
    {"priority": 60,  "name": "En ruta de entrega \u2013 sin movimiento", "match_estado": "en ruta de entrega", "match_estado_contains": None,      "match_novelty_contains": None,                                     "min_days": 2,    "estado_propuesto": "Sin movimiento",          "motivo": "EN RUTA DE ENTREGA con {days} dias sin cambio.",                                  "requiere_accion": "Gestionar con encargado",               "review_needed": 0},
    {"priority": 70,  "name": "Almacenado en bodega \u2013 sin movimiento", "match_estado": "almacenado en bodega", "match_estado_contains": None, "match_novelty_contains": None,                                     "min_days": 2,    "estado_propuesto": "Sin movimiento",          "motivo": "ALMACENADO EN BODEGA con {days} dias sin cambio.",                                "requiere_accion": "Gestionar con encargado",               "review_needed": 0},
    {"priority": 80,  "name": "Sin recolectar \u2013 sin movimiento",     "match_estado": "sin recolectar",     "match_estado_contains": None,      "match_novelty_contains": None,                                     "min_days": 2,    "estado_propuesto": "Sin movimiento",          "motivo": "Sin Recolectar con {days} dias sin cambio.",                                      "requiere_accion": "Gestionar con encargado",               "review_needed": 0},
]


def seed_default_rules(connection: sqlite3.Connection) -> None:
    count = connection.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    if count > 0:
        return
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    for rule in SEED_RULES:
        connection.execute(
            """
            INSERT INTO rules (priority, enabled, name, match_estado, match_estado_contains,
                match_novelty_contains, min_days, estado_propuesto, motivo, requiere_accion,
                review_needed, updated_by, updated_at)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sistema', ?)
            """,
            (
                rule["priority"], rule["name"], rule["match_estado"],
                rule["match_estado_contains"], rule["match_novelty_contains"],
                rule["min_days"], rule["estado_propuesto"], rule["motivo"],
                rule["requiere_accion"], rule["review_needed"], now,
            ),
        )
    connection.commit()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    _apply_migrations(connection)
    connection.commit()


def _apply_migrations(connection: sqlite3.Connection) -> None:
    """Idempotent ALTERs for schemas created before new columns existed."""
    if not _column_exists(connection, "run_results", "carrier"):
        connection.execute(
            "ALTER TABLE run_results ADD COLUMN carrier TEXT NOT NULL DEFAULT 'effi'"
        )


def _column_exists(
    connection: sqlite3.Connection, table: str, column: str
) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def clear_history(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM tracking_novelty_events")
    connection.execute("DELETE FROM tracking_status_events")
    connection.execute("DELETE FROM run_results")
    connection.execute("DELETE FROM runs")
    connection.commit()


def reset_rules(connection: sqlite3.Connection) -> None:
    """Wipes rules and rule_history. Intended for tests and full resets."""
    connection.execute("DELETE FROM rule_history")
    connection.execute("DELETE FROM rules")
    connection.commit()
