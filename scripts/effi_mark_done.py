"""Marca una orden como 'done' con los IDs reales de remisión y guía.

Útil cuando el bot creó la remisión y guía en Effi pero falló parseando el ID
de vuelta, dejando effi_orders con status='failed'. Después de verificar
manualmente en Effi cuál es el ID real, registralo con este script.

Usage:
    python scripts/effi_mark_done.py --order 5348 --remision 3900 --guia 4006
    python scripts/effi_mark_done.py --order 5359 --remision 3901 --guia 4007

También resuelve automáticamente el item en review_queue (si existe) con
reason='remision_sin_guia' o cualquier otra para esa orden.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.effi_config import load_settings  # noqa: E402
from app.effi_guides.orders_repo import (  # noqa: E402
    EffiAuditLogRepository,
    EffiOrdersRepository,
    EffiReviewQueueRepository,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Marca una orden como done con IDs reales.")
    parser.add_argument("--order", type=int, required=True, help="ID de la orden en Effi.")
    parser.add_argument("--remision", type=int, required=True, help="ID de la remisión creada en Effi.")
    parser.add_argument("--guia", type=int, required=True, help="ID de la guía creada en Effi.")
    parser.add_argument("--actor", default="manual_cleanup",
                        help="Quién hace la corrección (default: manual_cleanup).")
    args = parser.parse_args()

    settings = load_settings()
    orders_repo = EffiOrdersRepository(settings.db_path)
    audit_repo = EffiAuditLogRepository(settings.db_path)
    queue_repo = EffiReviewQueueRepository(settings.db_path)

    existing = orders_repo.get(args.order)
    if existing is None:
        print(f"ERROR: no hay registro previo de la orden {args.order} en effi_orders.")
        print("       ¿La procesaste antes? Si no, esto es un error.")
        return 1

    print(f"→ Estado actual de orden {args.order}:")
    print(f"   status={existing.status} remision_id={existing.remision_id} guia_id={existing.guia_id}")
    print(f"→ Actualizando a: status=done remision_id={args.remision} guia_id={args.guia}")

    orders_repo.upsert(
        orden_id=args.order,
        remision_id=args.remision,
        guia_id=args.guia,
        status="done",
        error_msg=None,
    )

    audit_repo.log(
        "manual_mark_done",
        orden_id=args.order,
        payload={
            "remision_id": args.remision,
            "guia_id": args.guia,
            "previous_status": existing.status,
            "previous_remision_id": existing.remision_id,
            "previous_guia_id": existing.guia_id,
        },
        actor=args.actor,
    )

    # Resolver cualquier item pendiente en review_queue para esta orden.
    pending = [
        it for it in queue_repo.list_pending()
        if it.orden_id == args.order
    ]
    for item in pending:
        queue_repo.resolve(
            item.id,
            resolved_by=args.actor,
            notes=(
                f"Resuelto automáticamente por effi_mark_done.py — "
                f"remision={args.remision}, guia={args.guia}."
            ),
        )
        print(f"   ✓ review_queue item #{item.id} (reason={item.reason}) marcado como resuelto.")

    if not pending:
        print("   (sin items pendientes en review_queue para esta orden)")

    print(f"✓ Orden {args.order} marcada como done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
