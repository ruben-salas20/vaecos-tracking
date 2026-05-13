"""Configuración del módulo Creador guías.

Lee variables de entorno necesarias para el bot de Playwright y para el flujo
de automatización. Es independiente de la config de v0.4/app/config.py para
poder usarse desde scripts standalone (scripts/effi_login.py, etc.) sin tener
que arrancar Flask.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _strip_inline_comment(value: str) -> str:
    """Quita comentario inline (' # ...' o '\\t# ...') de un valor desquoted.

    Si el valor empieza con comilla, NO toca nada — el '#' puede ser parte legítima
    de la cadena (ej. password#xyz). Solo se considera comentario cuando aparece
    después de whitespace.
    """
    if value.startswith(('"', "'")):
        return value
    m = re.search(r"\s+#", value)
    if m:
        return value[: m.start()].rstrip()
    return value


def _load_dotenv() -> None:
    """Lee .env de la raíz del repo si existe. No depende de python-dotenv.

    Soporta:
      - Líneas en blanco y comentarios completos (#)
      - Comentarios inline después de valores (KEY=value  # comentario)
      - Valores entre comillas dobles o simples
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        value = value.strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class EffiSettings:
    username: str
    password: str
    base_url: str
    session_path: Path
    headless: bool
    navigation_timeout_ms: int
    db_path: Path
    # ── IA address validation (MiniMax) ─────────────────
    ai_address_validation: bool
    minimax_api_key: str
    minimax_model: str
    minimax_base_url: str
    minimax_timeout_seconds: int

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/ingreso"

    @property
    def calendario_url(self) -> str:
        return f"{self.base_url}/app/calendario"

    @property
    def orden_v_url(self) -> str:
        return f"{self.base_url}/app/orden_v"

    @property
    def remision_v_url(self) -> str:
        return f"{self.base_url}/app/remision_v"

    @property
    def guia_transporte_url(self) -> str:
        return f"{self.base_url}/app/guia_transporte"


def load_settings() -> EffiSettings:
    _load_dotenv()

    username = os.environ.get("EFFI_USERNAME", "").strip()
    password = os.environ.get("EFFI_PASSWORD", "").strip()
    base_url = os.environ.get("EFFI_BASE_URL", "https://effi.com.co").rstrip("/")

    session_raw = os.environ.get("EFFI_SESSION_PATH", "v0.2/data/effi-session.json")
    session_path = Path(session_raw)
    if not session_path.is_absolute():
        session_path = REPO_ROOT / session_path

    headless = os.environ.get("EFFI_HEADLESS", "true").strip().lower() in ("1", "true", "yes", "on")
    timeout = int(os.environ.get("EFFI_NAVIGATION_TIMEOUT_MS", "30000"))

    db_raw = os.environ.get("V02_SQLITE_DB_PATH", "v0.2/data/vaecos_tracking.db")
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = REPO_ROOT / db_path

    minimax_api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    minimax_model = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7").strip()
    minimax_base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
    minimax_timeout = int(os.environ.get("MINIMAX_TIMEOUT_SECONDS", "15"))
    ai_address_validation = os.environ.get("AI_ADDRESS_VALIDATION", "auto").strip().lower()
    if ai_address_validation == "auto":
        ai_enabled = bool(minimax_api_key)
    else:
        ai_enabled = ai_address_validation in ("1", "true", "yes", "on")

    return EffiSettings(
        username=username,
        password=password,
        base_url=base_url,
        session_path=session_path,
        headless=headless,
        navigation_timeout_ms=timeout,
        db_path=db_path,
        ai_address_validation=ai_enabled,
        minimax_api_key=minimax_api_key,
        minimax_model=minimax_model,
        minimax_base_url=minimax_base_url,
        minimax_timeout_seconds=minimax_timeout,
    )
