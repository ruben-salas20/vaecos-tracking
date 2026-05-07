from __future__ import annotations
import bcrypt
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from ..auth.decorators import admin_required
from ..auth.user_repo import UserRepository

users_bp = Blueprint("users", __name__)


def _get_repo() -> UserRepository:
    return UserRepository(current_app.config["DB_PATH"])


@users_bp.route("/users")
@admin_required
def users_list():
    users = _get_repo().list_all()
    return render_template("users/users.html", users=users)


@users_bp.route("/users", methods=["POST"])
@admin_required
def users_create():
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")
    if role not in ("user", "admin"):
        role = "user"
    if not email or not name or not password:
        flash("Todos los campos son requeridos.", "error")
        return redirect(url_for("users.users_list"))
    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("users.users_list"))
    repo = _get_repo()
    if repo.get_by_email(email):
        flash(f"El email {email} ya está registrado.", "error")
        return redirect(url_for("users.users_list"))
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    repo.create(email=email, name=name, password_hash=pw_hash, role=role, created_by=session.get("user_email", ""))
    flash(f"Usuario {email} creado exitosamente.", "ok")
    return redirect(url_for("users.users_list"))


@users_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def users_toggle(user_id: int):
    if user_id == session.get("user_id"):
        flash("No podés desactivar tu propia cuenta.", "error")
        return redirect(url_for("users.users_list"))
    _get_repo().toggle_active(user_id)
    return redirect(url_for("users.users_list"))


@users_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def users_delete(user_id: int):
    if user_id == session.get("user_id"):
        flash("No podés eliminar tu propia cuenta.", "error")
        return redirect(url_for("users.users_list"))
    _get_repo().delete(user_id)
    flash("Usuario eliminado.", "ok")
    return redirect(url_for("users.users_list"))


@users_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@admin_required
def users_reset_password(user_id: int):
    repo = _get_repo()
    user = repo.get_by_id(user_id)
    if not user:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("users.users_list"))
    error = None
    if request.method == "POST":
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")
        if len(new_pw) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        elif new_pw != confirm_pw:
            error = "Las contraseñas no coinciden."
        else:
            new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            repo.update_password(user_id, new_hash)
            flash(f"Contraseña de {user['name']} restablecida exitosamente.", "ok")
            return redirect(url_for("users.users_list"))
    return render_template("users/reset_password.html", user=user, error=error)
