"""Background jobs para corridas Effi disparadas desde la UI.

Mismo patrón que v0.4/app/runs/jobs.py: thread daemon + dict de estados por token.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import asdict


_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _try_build_notion_provider():
    """Construye un NotionProvider desde las V04Settings si están disponibles.

    Devuelve None si faltan credenciales — el runner skipea el sync a Notion
    pero la creación en Effi sigue procediendo normalmente.
    """
    try:
        from app.config import load_settings as load_v04_settings  # type: ignore
        from vaecos_v02.providers.notion_provider import NotionProvider  # type: ignore
    except ImportError:
        return None
    from pathlib import Path
    try:
        v04 = load_v04_settings(Path(__file__).resolve().parents[2])  # .../v0.4
    except Exception:
        return None
    if not getattr(v04, "notion_api_key", "") or not getattr(v04, "notion_data_source_id", ""):
        return None
    try:
        return NotionProvider(
            api_key=v04.notion_api_key,
            notion_version=v04.notion_version,
            data_source_id=v04.notion_data_source_id,
        )
    except Exception:
        return None


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

            # Wire opcionalmente el NotionProvider: si hay credenciales, el bot
            # crea la guía también en Notion automáticamente tras crearla en Effi.
            notion_provider = _try_build_notion_provider()

            runner = EffiRunner(settings, dry_run=not apply, notion_provider=notion_provider)
            if not runner.catalog:
                _update(token, status="error", error="Catálogo vacío. Cargá productos en /effi/catalog.")
                return

            # Jobs disparados desde la UI SIEMPRE corren headless — el operador
            # no espera ver un navegador abriéndose en su pantalla.
            with EffiBot(settings, headless_override=True) as bot:
                if not bot.health_check():
                    _update(token, current_order=None, total=0, current=0)
                    print("⚠ Sesión Effi expirada — intentando re-login automático...")
                    if not (bot.try_auto_login() and bot.health_check()):
                        _update(
                            token,
                            status="error",
                            error="Sesión Effi expirada y auto-login falló — renová effi-session.json con scripts/effi_login.py.",
                        )
                        return
                    print("✓ Re-login automático exitoso.")

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
