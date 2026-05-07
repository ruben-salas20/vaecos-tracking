"""Cached lookup of Notion select options used by editor dropdowns.
Avoids hitting Notion on every render — TTL is 5 minutes."""
from __future__ import annotations
import threading
import time
from flask import current_app

_cache: dict = {"options": [], "loaded_at": 0.0}
_lock = threading.Lock()
_TTL_SECONDS = 300

# Hardcoded fallback in case Notion is unreachable. Order matches what the operadora uses most.
_FALLBACK = [
    "Recolectada", "Sin recolectar", "Almacenado en bodega",
    "En ruta de entrega", "ENTREGADA", "PENDIENTE CLIENTE",
    "PENDIENTE EFFI", "Solicitud info Effi", "Sin movimiento",
    "En novedad", "Gestión novedad", "Por recoger (INFORMADO)",
    "Solicitud devolución", "En Devolución",
    "Indemnización", "Pendiente Indemnización",
]


def get_estado_novedad_options() -> list[str]:
    """Return the live options from Notion (cached) or fallback if unreachable."""
    now = time.time()
    with _lock:
        if _cache["options"] and now - _cache["loaded_at"] < _TTL_SECONDS:
            return list(_cache["options"])

    try:
        settings = current_app.config["SETTINGS"]
        from vaecos_v02.providers.notion_provider import NotionProvider
        provider = NotionProvider(
            api_key=settings.notion_api_key,
            notion_version=settings.notion_version,
            data_source_id=settings.notion_data_source_id,
        )
        provider._load_select_options()  # noqa: SLF001
        options = (provider._select_options or {}).get("Estado novedad", [])  # noqa: SLF001
        if options:
            with _lock:
                _cache["options"] = options
                _cache["loaded_at"] = now
            return list(options)
    except Exception:  # noqa: BLE001
        pass
    return list(_FALLBACK)
