"""Procesa TODAS las órdenes pendientes en Effi (modo masivo).

Usa idempotencia: cada orden procesada se registra en effi_orders con
status='done'; reruns no la re-procesan.

Modo seguro por defecto (--dry-run). Para producción usar --apply.

Usage:
    python scripts/effi_run.py                  # dry-run, todas
    python scripts/effi_run.py --apply          # ejecuta REAL
    python scripts/effi_run.py --apply --limit 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.bot import EffiBot, NotLoggedInError  # noqa: E402
from app.effi_guides.effi_config import load_settings  # noqa: E402
from app.effi_guides.notifier import notify  # noqa: E402
from app.effi_guides.runner import EffiRunner  # noqa: E402


def _build_notion_provider():
    """Construye NotionProvider desde V04Settings; None si faltan credenciales."""
    try:
        from app.config import load_settings as load_v04_settings
        from vaecos_v02.providers.notion_provider import NotionProvider
    except ImportError:
        return None
    try:
        v04 = load_v04_settings(Path(__file__).resolve().parents[1] / "v0.4")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesa todas las órdenes Effi pendientes.")
    parser.add_argument("--apply", action="store_true",
                        help="Ejecuta conversiones REALES. Sin esta flag corre en dry-run.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Máximo de órdenes a procesar en esta corrida (0 = todas).")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.session_path.exists():
        print(f"ERROR: no existe {settings.session_path}. Corré 'python scripts/effi_login.py'.")
        return 2

    # Wire opcionalmente Notion: si hay credenciales en .env, el bot crea la
    # guía también en Notion automáticamente tras crearla en Effi.
    notion_provider = _build_notion_provider()
    if notion_provider is not None:
        print("→ Notion: habilitado (auto-sync de guías nuevas a Notion).")
    else:
        print("→ Notion: deshabilitado (faltan NOTION_API_KEY o NOTION_DATA_SOURCE_ID).")

    runner = EffiRunner(settings, dry_run=not args.apply, notion_provider=notion_provider)
    if not runner.catalog:
        print(f"ERROR: catálogo vacío. Cargá productos en /effi/catalog.")
        return 2

    print(f"→ Catálogo: {len(runner.catalog)} productos activos.")
    print(f"→ Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    if args.limit:
        print(f"→ Límite: {args.limit} órdenes por corrida.")
    print()

    try:
        with EffiBot(settings) as bot:
            if not bot.health_check():
                print("⚠ Sesión Effi expirada — intentando re-login automático...")
                if bot.try_auto_login() and bot.health_check():
                    print("✓ Re-login automático exitoso — continuando corrida.")
                else:
                    notify(
                        subject="Sesión Effi expirada — auto-login falló",
                        body=(
                            "El bot detectó sesión expirada e intentó re-loguear automáticamente "
                            "pero falló (probable reCAPTCHA o credenciales rechazadas). "
                            "Renová effi-session.json manualmente con scripts/effi_login.py."
                        ),
                    )
                    raise NotLoggedInError("Sesión expirada y auto-login falló.")

            def on_progress(i, total, orden_id):
                print(f"[{i}/{total}] procesando orden #{orden_id}...")

            summary = runner.run_all(bot, limit=args.limit, on_progress=on_progress)

            print()
            print("───── Resumen ─────")
            print(f"Filas escaneadas    : {summary.total_seen}")
            print(f"Necesitan proceso   : {summary.needs_processing}")
            print(f"  → Procesadas      : {summary.processed}")
            print(f"  → Escaladas       : {summary.escalated}")
            print(f"  → Fallidas        : {summary.failed}")
            print(f"  → Saltadas (done) : {summary.skipped}")
            # El email digest lo manda runner.run_all() — 1 solo email con todo.

    except NotLoggedInError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        notify(subject="Error fatal en corrida Effi", body=str(e))
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
