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


@auth_bp.route("/mi-cuenta", methods=["GET"])
@login_required
def my_account():
    repo = _get_repo()
    user = repo.get_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/my_account.html",
        user=user,
        profile_success=request.args.get("profile") == "ok",
        profile_error=request.args.get("profile_error"),
        password_success=request.args.get("password") == "ok",
        password_error=request.args.get("password_error"),
    )


@auth_bp.route("/mi-cuenta/profile", methods=["POST"])
@login_required
def profile_update():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not name:
        return redirect(url_for("auth.my_account", profile_error="El nombre no puede estar vacío."))
    if not email or "@" not in email or "." not in email:
        return redirect(url_for("auth.my_account", profile_error="Email inválido."))
    repo = _get_repo()
    ok, err = repo.update_profile(session["user_id"], name, email)
    if not ok:
        return redirect(url_for("auth.my_account", profile_error=err or "No se pudo actualizar."))
    session["user_name"] = name
    session["user_email"] = email
    return redirect(url_for("auth.my_account", profile="ok"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per minute", methods=["POST"], key_func=lambda: str(session.get("user_id", "anon")))
def change_password():
    if request.method == "GET":
        return redirect(url_for("auth.my_account"))
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")
    repo = _get_repo()
    user = repo.get_by_id(session["user_id"])
    if not user or not bcrypt.checkpw(current_pw.encode(), user["password_hash"].encode()):
        return redirect(url_for("auth.my_account", password_error="Contraseña actual incorrecta."))
    if len(new_pw) < 8:
        return redirect(url_for("auth.my_account", password_error="La nueva contraseña debe tener al menos 8 caracteres."))
    if new_pw != confirm_pw:
        return redirect(url_for("auth.my_account", password_error="Las contraseñas no coinciden."))
    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    repo.update_password(session["user_id"], new_hash)
    return redirect(url_for("auth.my_account", password="ok"))
