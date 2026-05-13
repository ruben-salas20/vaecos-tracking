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

    runner = EffiRunner(settings, dry_run=not args.apply)
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
                notify(
                    subject="Sesión Effi expirada",
                    body="El bot no pudo entrar al ERP. Renová effi-session.json con scripts/effi_login.py.",
                )
                raise NotLoggedInError("Sesión expirada.")

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
