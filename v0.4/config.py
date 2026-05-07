from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(base: Path) -> None:
    env_file = base / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int
    secret_key: str
    env: str
    bootstrap_email: str
    bootstrap_password: str
    notion_api_key: str
    notion_version: str
    notion_data_source_id: str


def load_settings(base_dir: Path) -> Settings:
    # Load .env from v0.4/ and repo root
    _load_dotenv(base_dir)
    _load_dotenv(base_dir.parent)
    db_path = Path(
        os.environ.get("V04_SQLITE_DB_PATH")
        or os.environ.get("V02_SQLITE_DB_PATH")
        or str(base_dir.parent / "v0.2" / "data" / "vaecos_tracking.db")
    )
    return Settings(
        db_path=db_path,
        host=os.environ.get("V04_HOST", "127.0.0.1"),
        port=int(os.environ.get("V04_PORT", "8765")),
        secret_key=os.environ.get("FLASK_SECRET_KEY", "dev-insecure-change-in-prod"),
        env=os.environ.get("VAECOS_ENV", "development"),
        bootstrap_email=os.environ.get("V04_BOOTSTRAP_EMAIL", ""),
        bootstrap_password=os.environ.get("V04_BOOTSTRAP_PASSWORD", ""),
        notion_api_key=os.environ.get("NOTION_API_KEY", ""),
        notion_version=os.environ.get("NOTION_VERSION", "2025-09-03"),
        notion_data_source_id=os.environ.get("NOTION_DATA_SOURCE_ID", ""),
    )
