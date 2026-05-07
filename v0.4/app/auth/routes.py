from __future__ import annotations
import bcrypt
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from .user_repo import UserRepository
from .decorators import login_required
from ..extensions import limiter

auth_bp = Blueprint("auth", __name__)


def _login_rate_key() -> str:
    """Rate-limit by remote IP — works behind a single trusted reverse proxy
    (Caddy strips/forwards X-Forwarded-For). For multi-hop deploys, configure
    ProxyFix in create_app()."""
    from flask_limiter.util import get_remote_address
    return get_remote_address()


def _get_repo() -> UserRepository:
    return UserRepository(current_app.config["DB_PATH"])


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"], key_func=_login_rate_key)
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.home"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = _get_repo().get_by_email(email)
        if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            error = "Email o contraseña incorrectos."
        elif not user["active"]:
            error = "Cuenta desactivada. Contactá al administrador."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            next_url = session.pop("next", None)
            return redirect(next_url or url_for("dashboard.home"))
    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per minute", methods=["POST"], key_func=lambda: str(session.get("user_id", "anon")))
def change_password():
    error = None
    success = False
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")
        repo = _get_repo()
        user = repo.get_by_id(session["user_id"])
        if not user or not bcrypt.checkpw(current_pw.encode(), user["password_hash"].encode()):
            error = "Contraseña actual incorrecta."
        elif len(new_pw) < 8:
            error = "La nueva contraseña debe tener al menos 8 caracteres."
        elif new_pw != confirm_pw:
            error = "Las contraseñas no coinciden."
        else:
            new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            repo.update_password(session["user_id"], new_hash)
            success = True
    return render_template("auth/change_password.html", error=error, success=success)
