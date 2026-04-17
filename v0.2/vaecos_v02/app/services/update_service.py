from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from vaecos_v02.app.config import Settings


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_name: str
    html_url: str
    download_url: str
    update_available: bool


def version_text(settings: Settings) -> str:
    return f"VAECOS v0.2\n- Version: {settings.app_version}\n- Canal: {settings.app_channel}"


def check_for_updates(settings: Settings) -> str:
    info = _fetch_update_info(settings)
    if isinstance(info, str):
        return info
    if not info.update_available:
        return (
            "No hay actualizaciones disponibles.\n"
            f"- Version local: {info.current_version}\n"
            f"- Ultima release: {info.latest_version}"
        )
    lines = [
        "Hay una actualizacion disponible.",
        f"- Version local: {info.current_version}",
        f"- Ultima release: {info.latest_version}",
        f"- Nombre: {info.release_name}",
        f"- Release: {info.html_url}",
    ]
    if info.download_url:
        lines.append(f"- Descarga: {info.download_url}")
    return "\n".join(lines)


def download_update(settings: Settings) -> str:
    info = _fetch_update_info(settings)
    if isinstance(info, str):
        return info
    if not info.update_available:
        return (
            "No hay actualizaciones disponibles para descargar.\n"
            f"- Version local: {info.current_version}\n"
            f"- Ultima release: {info.latest_version}"
        )
    if not info.download_url:
        return "La release existe, pero no tiene una URL de descarga utilizable."

    settings.updates_dir.mkdir(parents=True, exist_ok=True)
    target = settings.updates_dir / f"vaecos_v0.2_update_{info.latest_version}.zip"
    with request.urlopen(info.download_url, timeout=60) as response:
        target.write_bytes(response.read())
    return (
        "Actualizacion descargada correctamente.\n"
        f"- Version local: {info.current_version}\n"
        f"- Nueva version: {info.latest_version}\n"
        f"- Archivo: {target}"
    )


def _fetch_update_info(settings: Settings) -> UpdateInfo | str:
    if not settings.update_repo:
        return (
            "No hay repositorio configurado para actualizaciones.\n"
            "Define V02_UPDATE_REPO con el formato owner/repo."
        )
    url = f"https://api.github.com/repos/{settings.update_repo}/releases/latest"
    req = request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "VAECOS-v0.2-update-checker",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        return f"No se pudo consultar GitHub Releases: HTTP {exc.code}"
    except error.URLError as exc:
        return f"No se pudo consultar GitHub Releases: {exc.reason}"
    except json.JSONDecodeError:
        return "GitHub Releases devolvio una respuesta invalida."

    latest_version = _normalize_version(str(data.get("tag_name", "")))
    if not latest_version:
        return "La ultima release no tiene un tag_name valido."

    assets = data.get("assets", [])
    download_url = ""
    if isinstance(assets, list):
        zip_assets = [asset for asset in assets if isinstance(asset, dict) and str(asset.get("name", "")).lower().endswith(".zip")]
        if zip_assets:
            download_url = str(zip_assets[0].get("browser_download_url", "")).strip()
    if not download_url:
        download_url = str(data.get("zipball_url", "")).strip()

    return UpdateInfo(
        current_version=settings.app_version,
        latest_version=latest_version,
        release_name=str(data.get("name", latest_version)).strip() or latest_version,
        html_url=str(data.get("html_url", "")).strip(),
        download_url=download_url,
        update_available=_compare_versions(latest_version, settings.app_version) > 0,
    )


def _normalize_version(value: str) -> str:
    match = re.search(r"(\d+(?:\.\d+){0,3})", value)
    return match.group(1) if match else ""


def _compare_versions(left: str, right: str) -> int:
    left_parts = [int(part) for part in left.split(".")]
    right_parts = [int(part) for part in right.split(".")]
    size = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (size - len(left_parts)))
    right_parts.extend([0] * (size - len(right_parts)))
    if left_parts > right_parts:
        return 1
    if left_parts < right_parts:
        return -1
    return 0
