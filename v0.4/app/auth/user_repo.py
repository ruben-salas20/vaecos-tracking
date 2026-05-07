from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime


class UserRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        from vaecos_v02.storage.db import connect as v02_connect
        return v02_connect(self.db_path)

    def get_by_email(self, email: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create(self, email: str, name: str, password_hash: str,
               role: str = "user", created_by: str = "") -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, name, role, active, created_at, created_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (email, password_hash, name, role, 1,
                 datetime.now().isoformat(timespec="seconds"), created_by),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def toggle_active(self, user_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE users SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE id = ?",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def update_profile(self, user_id: int, name: str, email: str) -> tuple[bool, str | None]:
        """Update name and email. Returns (ok, error_message).
        Email must remain unique across users."""
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (email, user_id),
            ).fetchone()
            if existing:
                return False, "Ese email ya está en uso por otro usuario."
            conn.execute(
                "UPDATE users SET name = ?, email = ? WHERE id = ?",
                (name, email, user_id),
            )
            conn.commit()
            return True, None
        finally:
            conn.close()

    def update_password(self, user_id: int, new_hash: str) -> None:
        conn = self._connect()
        try:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, user_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def list_all(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
