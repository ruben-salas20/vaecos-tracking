"""Endpoints del asistente IA conversacional.

3 endpoints:
- POST /ai/chat       → recibe mensaje del usuario, devuelve respuesta del agent
- GET  /ai/chat/history → devuelve los mensajes recientes (para hidratar widget al abrir)
- POST /ai/chat/clear  → borra el historial del usuario
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session, current_app

from ..auth.decorators import login_required
from ..extensions import limiter
from .agent import build_agent
from .repository import ChatRepository


ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


def _ai_rate_key() -> str:
    """Rate limit por user_id (no por IP) — multi-tab del mismo user comparten cuota."""
    return f"ai-user-{session.get('user_id', 'anon')}"


def _repo() -> ChatRepository:
    return ChatRepository(current_app.config["DB_PATH"])


@ai_bp.route("/chat", methods=["POST"])
@login_required
@limiter.limit("30 per hour", key_func=_ai_rate_key)
def chat():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "no auth"}), 401

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Mensaje vacío."}), 400
    if len(message) > 2000:
        return jsonify({"ok": False, "error": "Mensaje demasiado largo (máx 2000 caracteres)."}), 400

    settings = current_app.config["SETTINGS"]
    repo = _repo()
    agent = build_agent(settings, str(current_app.config["DB_PATH"]), repo)
    if agent is None:
        return jsonify({
            "ok": False,
            "error": (
                "El asistente no está configurado — falta MINIMAX_API_KEY en .env. "
                "Avisale a un admin."
            ),
        }), 503

    conv_id = repo.get_or_create_active_conversation(user_id)
    result = agent.run_turn(user_id, conv_id, message)

    return jsonify({
        "ok": result.error is None or bool(result.answer),
        "answer": result.answer,
        "tool_calls": result.tool_calls,
        "iterations": result.iterations,
        "error": result.error,
    })


@ai_bp.route("/chat/history", methods=["GET"])
@login_required
def chat_history():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "no auth"}), 401
    messages = _repo().list_user_messages_for_ui(user_id, limit_turns=20)
    # Para el UI sólo necesitamos role + texto. Para mensajes assistant guardados como JSON
    # extraemos el text de answer si está disponible.
    out = []
    import json as _json
    for m in messages:
        content = m["content"]
        if m["role"] == "assistant":
            try:
                parsed = _json.loads(content)
                if isinstance(parsed, dict):
                    if parsed.get("action") == "tool_call":
                        # Tool calls son ephemeral del agent — no se muestran al usuario.
                        continue
                    if parsed.get("action") == "answer":
                        content = parsed.get("text", content)
            except Exception:
                # JSON malformado (probablemente raw_response viejo con <think>).
                # Skip — no es seguro mostrarlo.
                continue
        out.append({
            "role": m["role"],
            "content": content,
            "created_at": m["created_at"],
        })
    return jsonify({"ok": True, "messages": out})


@ai_bp.route("/chat/clear", methods=["POST"])
@login_required
def chat_clear():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "no auth"}), 401
    n = _repo().clear_conversation(user_id)
    return jsonify({"ok": True, "cleared": n})
