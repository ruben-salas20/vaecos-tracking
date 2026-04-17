from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXCLUDED_STATUSES = {
    "ENTREGADA",
    "Indemnización",
    "Solicitud devolución",
    "En Devolución",
}


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    app_version: str
    app_channel: str
    notion_api_key: str
    notion_data_source_id: str
    notion_version: str
    notion_query_kind: str
    effi_timeout_seconds: int
    reports_dir: Path
    save_raw_html: bool
    sqlite_db_path: Path
    updates_dir: Path
    update_repo: str
    excluded_statuses: set[str]


def load_settings(base_dir: Path) -> Settings:
    load_dotenv(base_dir / ".env")
    load_dotenv(base_dir.parent / ".env")
    version_info = _load_version_info(base_dir / "version.json")
    return Settings(
        app_version=version_info.get("version", "0.0.0"),
        app_channel=version_info.get("channel", "stable"),
        notion_api_key=os.getenv("NOTION_API_KEY", ""),
        notion_data_source_id=os.getenv("NOTION_DATA_SOURCE_ID", ""),
        notion_version=os.getenv("NOTION_VERSION", "2025-09-03"),
        notion_query_kind=os.getenv("NOTION_QUERY_KIND", "auto").lower(),
        effi_timeout_seconds=int(os.getenv("EFFI_TIMEOUT_SECONDS", "20")),
        reports_dir=Path(os.getenv("V02_REPORTS_DIR", str(base_dir / "reports"))),
        save_raw_html=os.getenv(
            "V02_SAVE_RAW_HTML", os.getenv("SAVE_RAW_HTML", "false")
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        sqlite_db_path=Path(
            os.getenv(
                "V02_SQLITE_DB_PATH", str(base_dir / "data" / "vaecos_tracking.db")
            )
        ),
        updates_dir=Path(os.getenv("V02_UPDATES_DIR", str(base_dir / "updates"))),
        update_repo=os.getenv("V02_UPDATE_REPO", "").strip(),
        excluded_statuses=set(DEFAULT_EXCLUDED_STATUSES),
    )


def _load_version_info(version_path: Path) -> dict[str, str]:
    if not version_path.exists():
        return {"version": "0.0.0", "channel": "stable"}
    try:
        data = json.loads(version_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": "0.0.0", "channel": "stable"}
    if not isinstance(data, dict):
        return {"version": "0.0.0", "channel": "stable"}
    return {
        "version": str(data.get("version", "0.0.0")).strip() or "0.0.0",
        "channel": str(data.get("channel", "stable")).strip() or "stable",
    }
