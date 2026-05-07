from __future__ import annotations
import secrets
import sys
import threading
from pathlib import Path

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def create_job() -> str:
    token = secrets.token_hex(16)
    with _jobs_lock:
        _jobs[token] = {"status": "running", "run_id": None, "error": None}
    return token


def get_job(token: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[token]) if token in _jobs else None


def dispatch_run(
    token: str,
    db_path: Path,
    guides: list[str],
    all_active: bool,
    dry_run: bool,
    save_raw_html: bool,
) -> None:
    """Spawn a background thread to execute a tracking run."""
    _repo_root = Path(__file__).resolve().parents[3]
    _v02_root = _repo_root / "v0.2"
    if str(_v02_root) not in sys.path:
        sys.path.insert(0, str(_v02_root))

    def _run_job() -> None:
        try:
            from vaecos_v02.app.config import load_settings as load_v02_settings
            from vaecos_v02.app.services.run_tracking import execute_tracking
            from vaecos_v02.app.services.sync_guides import sync_guides
            from vaecos_v02.providers.notion_provider import NotionProvider
            from vaecos_v02.storage.db import connect as v02_connect

            v02_root = Path(__file__).resolve().parents[3] / "v0.2"
            settings = load_v02_settings(v02_root)
            execute_tracking(
                settings=settings,
                selected_guides=guides if guides else None,
                all_active=all_active,
                dry_run=dry_run,
                output_dir=None,
                save_raw_html=save_raw_html,
            )
            conn = v02_connect(db_path)
            latest = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            run_id = int(latest["id"]) if latest else 0
            conn.close()

            # Auto-sync the guides snapshot after the run finishes.
            try:
                notion = NotionProvider(
                    api_key=settings.notion_api_key,
                    notion_version=settings.notion_version,
                    data_source_id=settings.notion_data_source_id,
                )
                sync_guides(db_path, notion)
            except Exception:  # noqa: BLE001
                # Auto-sync failures must not mark the run as failed.
                pass

            with _jobs_lock:
                _jobs[token] = {"status": "done", "run_id": run_id, "error": None}
        except Exception as exc:  # noqa: BLE001
            with _jobs_lock:
                _jobs[token] = {"status": "error", "run_id": None, "error": str(exc)}

    t = threading.Thread(target=_run_job, daemon=True)
    t.start()


# ─────────────────────────── Sync jobs ───────────────────────────

_sync_jobs: dict[str, dict] = {}


def create_sync_job() -> str:
    token = secrets.token_hex(16)
    with _jobs_lock:
        _sync_jobs[token] = {"status": "running", "stats": None, "error": None}
    return token


def get_sync_job(token: str) -> dict | None:
    with _jobs_lock:
        return dict(_sync_jobs[token]) if token in _sync_jobs else None


def dispatch_sync(token: str, db_path: Path) -> None:
    """Spawn a background thread to sync the guides snapshot from Notion."""
    _repo_root = Path(__file__).resolve().parents[3]
    _v02_root = _repo_root / "v0.2"
    if str(_v02_root) not in sys.path:
        sys.path.insert(0, str(_v02_root))

    def _run_job() -> None:
        try:
            from vaecos_v02.app.config import load_settings as load_v02_settings
            from vaecos_v02.app.services.sync_guides import sync_guides
            from vaecos_v02.providers.notion_provider import NotionProvider

            v02_root = Path(__file__).resolve().parents[3] / "v0.2"
            settings = load_v02_settings(v02_root)
            notion = NotionProvider(
                api_key=settings.notion_api_key,
                notion_version=settings.notion_version,
                data_source_id=settings.notion_data_source_id,
            )
            stats = sync_guides(db_path, notion)
            with _jobs_lock:
                _sync_jobs[token] = {
                    "status": "done",
                    "stats": {
                        "read": stats.read_from_notion,
                        "inserted": stats.inserted,
                        "updated": stats.updated,
                        "unchanged": stats.unchanged,
                        "archived": stats.archived,
                        "incomplete": stats.incomplete,
                    },
                    "error": None,
                }
        except Exception as exc:  # noqa: BLE001
            with _jobs_lock:
                _sync_jobs[token] = {"status": "error", "stats": None, "error": str(exc)}

    t = threading.Thread(target=_run_job, daemon=True)
    t.start()
