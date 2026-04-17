from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
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
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()


def clear_history(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM tracking_novelty_events")
    connection.execute("DELETE FROM tracking_status_events")
    connection.execute("DELETE FROM run_results")
    connection.execute("DELETE FROM runs")
    connection.commit()
