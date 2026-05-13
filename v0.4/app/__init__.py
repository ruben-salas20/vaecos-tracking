from __future__ import annotations
import sys
from pathlib import Path
from flask import Flask, session, request

# Inject v0.2 into path before any v0.2 imports
_REPO_ROOT = Path(__file__).resolve().parents[2]
_V02_ROOT = _REPO_ROOT / "v0.2"
if str(_V02_ROOT) not in sys.path:
    sys.path.insert(0, str(_V02_ROOT))

from vaecos_v02.storage.db import connect as v02_connect, init_db as v02_init_db
from vaecos_v02.storage.rules_repository import RulesRepository
from vaecos_v02.core.rules import DEFAULT_RULES


def create_app() -> Flask:
    from .config import load_settings
    from .extensions import limiter
    from .utils import fmt_ts, e_trunc, fmt_duration, initials_of

    base_dir = Path(__file__).resolve().parents[1]  # v0.4/
    settings = load_settings(base_dir)

    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["DB_PATH"] = settings.db_path
    app.config["SETTINGS"] = settings

    # Trust the X-Forwarded-* headers from Caddy (single hop). DO NOT enable in
    # development without a proxy or attackers can spoof the client IP.
    if settings.env == "production":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    limiter.init_app(app)

    conn = v02_connect(settings.db_path)
    v02_init_db(conn)
    RulesRepository(conn).seed_if_empty(DEFAULT_RULES)
    conn.close()

    _seed_bootstrap_user(settings)

    app.jinja_env.filters["fmt_ts"] = fmt_ts
    app.jinja_env.filters["e_trunc"] = e_trunc
    app.jinja_env.filters["fmt_duration"] = fmt_duration
    app.jinja_env.filters["initials"] = initials_of

    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .runs.routes import runs_bp
    from .import_guides.routes import import_bp
    from .users.routes import users_bp
    from .effi_guides.routes import effi_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(effi_bp)

    @app.errorhandler(429)
    def _ratelimit_handler(e):
        from flask import render_template, request, jsonify
        # AJAX clients get JSON; classic form posts get a friendly HTML page.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" \
                or request.accept_mimetypes.best == "application/json":
            return jsonify({
                "ok": False,
                "error": "Demasiados intentos. Esperá un minuto y volvé a probar.",
            }), 429
        return render_template("auth/rate_limited.html", message=str(e.description)), 429

    @app.context_processor
    def inject_globals():
        name = session.get("user_name", "")
        return {
            "current_user": {
                "email": session.get("user_email", ""),
                "name": name,
                "initials": initials_of(name),
                "role": session.get("role", "user"),
                "id": session.get("user_id"),
            },
            "active_endpoint": request.endpoint or "",
        }

    return app


def _seed_bootstrap_user(settings) -> None:
    if not settings.bootstrap_email or not settings.bootstrap_password:
        return
    try:
        import bcrypt
    except ImportError:
        return
    from datetime import datetime
    conn = v02_connect(settings.db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if row and row["c"] > 0:
            return
        pw_hash = bcrypt.hashpw(settings.bootstrap_password.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (email, password_hash, name, role, active, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
            (settings.bootstrap_email, pw_hash, "Admin", "admin", 1,
             datetime.now().isoformat(timespec="seconds"), "bootstrap"),
        )
        conn.commit()
    finally:
        conn.close()
