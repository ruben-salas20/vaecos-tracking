"""Background jobs para corridas Effi disparadas desde la UI.

Mismo patrón que v0.4/app/runs/jobs.py: thread daemon + dict de estados por token.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import asdict


_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def create_job(*, mode: str, limit: int = 0, only_order: int | None = None) -> str:
    token = secrets.token_hex(16)
    with _jobs_lock:
        _jobs[token] = {
            "status": "running",
            "mode": mode,            # "apply" | "dry_run"
            "limit": limit,
            "only_order": only_order,
            "current": 0,
            "total": 0,
            "current_order": None,
            "summary": None,
            "error": None,
        }
    return token


def get_job(token: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[token]) if token in _jobs else None


def _update(token: str, **fields) -> None:
    with _jobs_lock:
        if token in _jobs:
            _jobs[token].update(fields)


def dispatch_effi_run(token: str, *, apply: bool, limit: int, only_order: int | None) -> None:
    """Lanza una corrida Effi en background. Esquema mismo que runs/jobs.py."""

    def _run_job() -> None:
        try:
            from .bot import EffiBot, NotLoggedInError
            from .effi_config import load_settings
            from .runner import EffiRunner

            settings = load_settings()
            if not settings.session_path.exists():
                _update(token, status="error", error="No hay sesión guardada. Corré 'scripts/effi_login.py'.")
                return

            runner = EffiRunner(settings, dry_run=not apply)
            if not runner.catalog:
                _update(token, status="error", error="Catálogo vacío. Cargá productos en /effi/catalog.")
                return

            # Jobs disparados desde la UI SIEMPRE corren headless — el operador
            # no espera ver un navegador abriéndose en su pantalla.
            with EffiBot(settings, headless_override=True) as bot:
                if not bot.health_check():
                    _update(token, status="error", error="Sesión Effi expirada — renová effi-session.json.")
                    return

                def on_progress(i, total, orden_id):
                    _update(token, current=i, total=total, current_order=orden_id)

                summary = runner.run_all(
                    bot,
                    limit=limit,
                    only_order=only_order,
                    on_progress=on_progress,
                )
                _update(
                    token,
                    status="done",
                    summary={
                        "total_seen": summary.total_seen,
                        "needs_processing": summary.needs_processing,
                        "processed": summary.processed,
                        "escalated": summary.escalated,
                        "failed": summary.failed,
                        "skipped": summary.skipped,
                        "details": [asdict(d) for d in summary.details],
                    },
                )
        except Exception as e:
            import traceback
            _update(token, status="error", error=f"{e}\n{traceback.format_exc(limit=3)}")

    threading.Thread(target=_run_job, daemon=True).start()
