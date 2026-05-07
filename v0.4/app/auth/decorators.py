from functools import wraps
from flask import session, redirect, url_for, request, abort


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            session["next"] = request.url
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            session["next"] = request.url
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated
