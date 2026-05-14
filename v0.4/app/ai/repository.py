"""Persistencia de conversaciones IA — ai_conversations + ai_messages + ai_audit_log.

Una conversación por usuario activa a la vez (modelo simple). El historial se trunca
a los últimos N turnos antes de pasarlo al modelo, para limitar tokens.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ChatMessage:
    id: int
    role: str             # 'user' | 'assistant' | 'tool'
    content: str          # texto del user/assistant, o JSON-stringificado de result si role=tool
    tool_name: str | None
    tool_args_json: str | None
    created_at: str


class ChatRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Conversaciones ─────────────────────────────────────────────

    def get_or_create_active_conversation(self, user_id: int) -> int:
        """Devuelve id de la conversación más reciente del usuario, creando una si no hay."""
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            r = c.execute(
                "SELECT id FROM ai_conversations WHERE user_id = ? ORDER BY last_message_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if r:
                return r["id"]
            cur = c.execute(
                "INSERT INTO ai_conversations (user_id, started_at, last_message_at) VALUES (?, ?, ?)",
                (user_id, now, now),
            )
            c.commit()
            return cur.lastrowid

    def touch_conversation(self, conv_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            c.execute("UPDATE ai_conversations SET last_message_at = ? WHERE id = ?", (now, conv_id))
            c.commit()

    def clear_conversation(self, user_id: int) -> int:
        """Borra TODAS las conversaciones del usuario (CASCADE limpia mensajes).
        Devuelve cantidad borrada."""
        with self._connect() as c:
            cur = c.execute("DELETE FROM ai_conversations WHERE user_id = ?", (user_id,))
            c.commit()
            return cur.rowcount

    # ── Mensajes ───────────────────────────────────────────────────

    def add_message(
        self,
        conv_id: int,
        *,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_args: dict | None = None,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        tool_args_json = json.dumps(tool_args, ensure_ascii=False) if tool_args else None
        with self._connect() as c:
            cur = c.execute(
                """INSERT INTO ai_messages
                    (conversation_id, role, content, tool_name, tool_args_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (conv_id, role, content, tool_name, tool_args_json, now),
            )
            c.commit()
            self.touch_conversation(conv_id)
            return cur.lastrowid

    def list_messages(self, conv_id: int, limit: int | None = None) -> list[ChatMessage]:
        sql = "SELECT * FROM ai_messages WHERE conversation_id = ? ORDER BY id ASC"
        params: list = [conv_id]
        if limit is not None:
            # Truncamos a los últimos N (en orden), pero queremos devolverlos en orden ASC.
            # Usamos subquery con ORDER DESC LIMIT N y reordenamos.
            sql = (
                "SELECT * FROM ("
                "  SELECT * FROM ai_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
                ") ORDER BY id ASC"
            )
            params.append(limit)

        with self._connect() as c:
            return [
                ChatMessage(
                    id=r["id"], role=r["role"], content=r["content"],
                    tool_name=r["tool_name"], tool_args_json=r["tool_args_json"],
                    created_at=r["created_at"],
                )
                for r in c.execute(sql, params)
            ]

    def list_user_messages_for_ui(self, user_id: int, limit_turns: int = 20) -> list[dict]:
        """Devuelve mensajes (role user/assistant) para mostrar en el UI del chat.

        Excluye roles tool (internos del agent). Devuelve los últimos `limit_turns`
        pares user+assistant (aprox limit_turns * 2 mensajes).
        """
        with self._connect() as c:
            conv = c.execute(
                "SELECT id FROM ai_conversations WHERE user_id = ? ORDER BY last_message_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if not conv:
                return []
            rows = c.execute(
                """SELECT * FROM (
                    SELECT id, role, content, created_at
                    FROM ai_messages
                    WHERE conversation_id = ? AND role IN ('user', 'assistant')
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC""",
                (conv["id"], limit_turns * 2),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Audit log ──────────────────────────────────────────────────

    def log_tool_call(
        self,
        *,
        user_id: int,
        tool_name: str,
        args: dict,
        result_summary: str,
        latency_ms: int,
        ok: bool,
        error_msg: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as c:
            c.execute(
                """INSERT INTO ai_audit_log
                    (user_id, tool_name, args_json, result_summary, latency_ms, ok, error_msg, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, tool_name,
                    json.dumps(args, ensure_ascii=False) if args else None,
                    result_summary[:500],
                    latency_ms,
                    1 if ok else 0,
                    error_msg[:500] if error_msg else None,
                    now,
                ),
            )
            c.commit()
