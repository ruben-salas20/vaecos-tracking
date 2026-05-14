"""Procesa UNA orden específica de Effi end-to-end.

Modo seguro por defecto (--dry-run). Para escribir realmente en Effi usar --apply.

Usage:
    python scripts/effi_run_one.py --order 5348             # dry-run, no escribe nada
    python scripts/effi_run_one.py --order 5348 --apply     # convierte a remisión + crea guía REAL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.bot import EffiBot, NotLoggedInError  # noqa: E402
from app.effi_guides.effi_config import load_settings  # noqa: E402
from app.effi_guides.runner import EffiRunner  # noqa: E402


def _build_notion_provider():
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
    parser = argparse.ArgumentParser(description="Procesa una orden Effi (end-to-end o dry-run).")
    parser.add_argument("--order", type=int, required=True, help="ID de la orden a procesar.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta la conversión REAL en Effi. Sin esta flag corre en dry-run.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if not settings.session_path.exists():
        print(f"ERROR: no existe {settings.session_path}. Corré 'python scripts/effi_login.py' primero.")
        return 2

    notion_provider = _build_notion_provider()
    if notion_provider is not None:
        print("→ Notion: habilitado (auto-sync de guías nuevas a Notion).")
    runner = EffiRunner(settings, dry_run=not args.apply, notion_provider=notion_provider)
    if not runner.catalog:
        print(f"ERROR: catálogo vacío en {settings.db_path}. Cargá productos en /effi/catalog.")
        return 2
    print(f"→ Catálogo: {len(runner.catalog)} productos activos.")
    print(f"→ Modo: {'APPLY (escribe en Effi)' if args.apply else 'DRY-RUN (no escribe)'}")
    print(f"→ Orden objetivo: {args.order}")
    print()

    try:
        with EffiBot(settings) as bot:
            if not bot.health_check():
                print("⚠ Sesión Effi expirada — intentando re-login automático...")
                if not (bot.try_auto_login() and bot.health_check()):
                    raise NotLoggedInError(
                        "Sesión expirada y auto-login falló — corré scripts/effi_login.py."
                    )
                print("✓ Re-login automático exitoso.")

            summary = runner.run_all(bot, only_order=args.order)

            if summary.needs_processing == 0:
                print(f"⚠ La orden {args.order} no aparece en /app/orden_v como 'needs_processing'.")
                print("  Posibles causas: ya fue convertida, no está en PEDIDO CONFIRMADO, o no existe.")
                return 1

            for r in summary.details:
                emoji = {
                    "done": "✓",
                    "would_process": "○",
                    "human_review": "🟡",
                    "failed": "✗",
                    "skipped": "⏭",
                }.get(r.status, "?")
                print(f"{emoji} Orden #{r.orden_id} — status={r.status}")
                if r.classification:
                    print(f"   kind={r.classification} valor={r.valor_declarado}")
                if r.remision_id:
                    print(f"   remision_id={r.remision_id}")
                if r.guia_id:
                    print(f"   guia_id={r.guia_id}")
                if r.reason:
                    print(f"   reason={r.reason}")
                if r.error_msg:
                    print(f"   error={r.error_msg}")
            print()
            print(f"Resumen: procesadas={summary.processed} escaladas={summary.escalated} "
                  f"fallidas={summary.failed} saltadas={summary.skipped}")

    except NotLoggedInError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
