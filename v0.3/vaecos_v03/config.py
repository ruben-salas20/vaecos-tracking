from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    sqlite_db_path: Path
    host: str
    port: int


def load_settings(base_dir: Path) -> Settings:
    load_dotenv(base_dir / ".env")
    load_dotenv(base_dir.parent / ".env")
    sqlite_path = os.getenv(
        "V03_SQLITE_DB_PATH",
        os.getenv("V02_SQLITE_DB_PATH", str(base_dir.parent / "v0.2" / "data" / "vaecos_tracking.db")),
    )
    return Settings(
        sqlite_db_path=Path(sqlite_path),
        host=os.getenv("V03_HOST", "127.0.0.1"),
        port=int(os.getenv("V03_PORT", "8765")),
    )
