"""Dry-run: escaneo de órdenes en Effi sin escribir nada.

Conecta usando el storageState ya guardado, lista órdenes en estado PEDIDO CONFIRMADO
sin remisión, abre cada modal para leer los productos, clasifica con el catálogo de la
DB y valida la dirección. Imprime el plan que SE EJECUTARÍA, pero NUNCA submitea.

Usar antes de habilitar el modo real para verificar que:
  - El bot entra a Effi con la sesión guardada.
  - Lee correctamente las filas de la tabla.
  - Clasifica las órdenes con el catálogo actual.
  - Identifica direcciones válidas/review/invalid.

Usage:
  python scripts/effi_dry_run.py                  # procesa todas las órdenes que necesitan procesamiento
  python scripts/effi_dry_run.py --limit 3        # solo las primeras 3 (para testing rápido)
  python scripts/effi_dry_run.py --order 5343     # solo una orden específica
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.address_validator import AddressValidation, validate_address  # noqa: E402
from app.effi_guides.bot import (  # noqa: E402
    EffiBot,
    NotLoggedInError,
    compute_fecha_entrega,
    compute_fecha_envio,
)
from app.effi_guides.classifier import (  # noqa: E402
    CatalogEntry,
    EscalationReason,
    ProcessingPlan,
    classify,
)
from app.effi_guides.effi_config import load_settings  # noqa: E402


def load_catalog(db_path: Path) -> list[CatalogEntry]:
    import json as _json
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT sku, descripcion_exacta, precio_declarado, tipo, aliases "
            "FROM effi_catalog WHERE activo = 1"
        ).fetchall()
    finally:
        conn.close()
    entries: list[CatalogEntry] = []
    for r in rows:
        try:
            aliases = tuple(a for a in _json.loads(r["aliases"] or "[]") if a)
        except (TypeError, ValueError):
            aliases = ()
        entries.append(
            CatalogEntry(
                sku=r["sku"],
                descripcion_exacta=r["descripcion_exacta"],
                precio_declarado=float(r["precio_declarado"]),
                tipo=r["tipo"],
                aliases=aliases,
            )
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run del bot de Effi (no escribe).")
    parser.add_argument("--limit", type=int, default=0, help="Máximo de órdenes a procesar (0 = todas).")
    parser.add_argument("--order", type=int, default=0, help="Procesar solo una orden específica.")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.session_path.exists():
        print(f"ERROR: no existe {settings.session_path}. Corré 'python scripts/effi_login.py' primero.")
        return 2

    catalog = load_catalog(settings.db_path)
    if not catalog:
        print(f"ERROR: catálogo vacío en {settings.db_path}. Cargá productos en /effi/catalog.")
        return 2
    print(f"→ Catálogo cargado: {len(catalog)} productos activos.")

    fecha_envio = compute_fecha_envio()
    fecha_entrega = compute_fecha_entrega()
    print(f"→ Fecha envío: {fecha_envio} | fecha entrega: {fecha_entrega}")

    try:
        with EffiBot(settings) as bot:
            if not bot.health_check():
                raise NotLoggedInError("Sesión expirada — corré scripts/effi_login.py para renovarla.")

            print("→ Escaneando /app/orden_v...")
            orders = bot.list_orders()
            total = len(orders)
            pendientes = [o for o in orders if o.needs_processing]
            print(f"   Total filas: {total} | A procesar: {len(pendientes)}")

            if args.order:
                pendientes = [o for o in pendientes if o.orden_id == args.order]
                if not pendientes:
                    print(f"   ⚠ La orden {args.order} no aparece en la tabla o ya está procesada.")
                    return 1
            elif args.limit > 0:
                pendientes = pendientes[: args.limit]

            for i, o in enumerate(pendientes, 1):
                print(f"\n── [{i}/{len(pendientes)}] Orden #{o.orden_id} ──")
                print(f"  Cliente   : {o.cliente[:80]}")
                print(f"  Teléfono  : {o.telefono or '(no detectado)'}")
                print(f"  Dirección : {o.direccion[:100] or '(vacía)'}")
                print(f"  Estado    : {o.estado}")

                # Dirección
                addr = validate_address(o.direccion)
                print(f"  Address   : {addr.status.value.upper()} patterns={addr.matched_patterns} reasons={addr.reasons}")

                # Detalle de productos
                try:
                    detail = bot.get_order_detail(o.orden_id)
                except Exception as e:
                    print(f"  ✗ No pude leer detalle: {e}")
                    continue
                for p in detail.productos:
                    print(f"     - {p.cantidad} × {p.descripcion}")

                result = classify(detail.productos, catalog)
                if isinstance(result, ProcessingPlan):
                    print(f"  Plan      : kind={result.kind} valor=${result.valor_declarado:.2f}")
                    print(f"              contenido_modo={result.contenido_modo} texto={result.contenido_texto!r}")
                    if addr.status == AddressValidation.VALID:
                        print("  → 🟢 SE PROCESARÍA AUTOMÁTICAMENTE (dirección válida + plan listo)")
                    else:
                        print(f"  → 🟡 IRÍA A COLA HUMANA (dirección {addr.status.value})")
                elif isinstance(result, EscalationReason):
                    print(f"  → 🔴 ESCALATION: {result.code} — {result.message}")

            print(f"\n✓ Dry-run terminado. {len(pendientes)} órdenes revisadas. NO se escribió nada en Effi.")

    except NotLoggedInError as e:
        print(f"✗ {e}")
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
