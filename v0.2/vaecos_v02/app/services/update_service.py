from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
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
    if settings.update_github_token:
        req.add_header("Authorization", f"Bearer {settings.update_github_token}")
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


def apply_update(settings: Settings, v02_dir: Path) -> str:
    """Find the latest downloaded zip, back up current code, and apply it.

    Preserves: .env, data/ (SQLite), reports/, backups/.
    Replaces:  vaecos_v02/, cli.py, version.json.
    """
    updates_dir = settings.updates_dir
    if not updates_dir.exists():
        return (
            "No se encontro el directorio de actualizaciones.\n"
            "Ejecuta primero: python v0.2/cli.py download-update"
        )

    zips = sorted(
        updates_dir.glob("*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not zips:
        return (
            "No hay archivos de actualizacion descargados.\n"
            "Ejecuta primero: python v0.2/cli.py download-update"
        )

    latest_zip = zips[0]
    project_root = v02_dir.parent

    # --- Backup current code ---
    backup_dir = project_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"vaecos_v0.2_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    backup_path = backup_dir / backup_name

    code_sources = [
        v02_dir / "vaecos_v02",
        v02_dir / "cli.py",
        v02_dir / "version.json",
    ]
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as bz:
        for src in code_sources:
            if src.is_file():
                bz.write(src, src.relative_to(project_root))
            elif src.is_dir():
                for file_path in src.rglob("*"):
                    if file_path.is_file() and "__pycache__" not in str(file_path):
                        bz.write(file_path, file_path.relative_to(project_root))

    # --- Extract zip and detect layout ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(latest_zip, "r") as zf:
                zf.extractall(tmp_path)
        except zipfile.BadZipFile:
            backup_path.unlink(missing_ok=True)
            return f"El archivo {latest_zip.name} no es un zip valido."

        # Look for the vaecos_v02 package inside the extracted content.
        candidates = [
            p for p in tmp_path.rglob("vaecos_v02") if p.is_dir()
        ]
        if not candidates:
            backup_path.unlink(missing_ok=True)
            return (
                f"No se encontro el paquete 'vaecos_v02' en {latest_zip.name}.\n"
                "Asegurate de que el zip contiene el codigo correcto."
            )

        # Use the shallowest match (closest to the root of the zip).
        zip_v02_dir = min(candidates, key=lambda p: len(p.parts)).parent

        # Replace vaecos_v02 package.
        src_pkg = zip_v02_dir / "vaecos_v02"
        dst_pkg = v02_dir / "vaecos_v02"
        if dst_pkg.exists():
            shutil.rmtree(dst_pkg)
        shutil.copytree(
            src_pkg,
            dst_pkg,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        # Replace cli.py if present in zip.
        src_cli = zip_v02_dir / "cli.py"
        if src_cli.exists():
            shutil.copy2(src_cli, v02_dir / "cli.py")

        # Replace version.json if present in zip.
        src_version = zip_v02_dir / "version.json"
        if src_version.exists():
            shutil.copy2(src_version, v02_dir / "version.json")

    return (
        f"Actualizacion aplicada desde: {latest_zip.name}\n"
        f"Backup guardado en:           {backup_path}\n"
        "Reinicia la aplicacion para que los cambios tomen efecto."
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
