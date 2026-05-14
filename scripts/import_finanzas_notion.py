"""Importa un CSV exportado de Notion ('Ingresos y egresos Vaecos YYYY.csv')
a las tablas fin_movements + fin_movement_categories de SQLite.

Diseño:
- Idempotente: cada fila genera un `external_ref` determinista (hash SHA1) que
  se inserta UNIQUE. Re-correr el script sobre el mismo CSV no duplica.
- Tolerante: filas con problemas se loguean pero no abortan la corrida (a menos
  que --strict).
- Reversible: --dry-run muestra el plan sin escribir.

Reglas de mapeo (basadas en análisis 2026-05-14):
- Columna $ Egreso con valor      → tipo='egreso'
- Columna $ Ingreso con valor     → tipo='ingreso'
- AMBAS columnas con valor        → tipo='transferencia' (un solo movimiento)
- Categoría con coma              → multi-categoría (M:N)
- Categoría vacía                 → tag SIN_CATEGORIA
- Fecha español (DD de mes de YYYY) → ISO YYYY-MM-DD
- Monto colombiano '2.004,67 COP' → 200467 (centavos)

Usage:
    python scripts/import_finanzas_notion.py --csv docs/notion-export/file.csv --dry-run
    python scripts/import_finanzas_notion.py --csv docs/notion-export/file.csv --apply
    python scripts/import_finanzas_notion.py --csv docs/notion-export/*.csv --apply
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v0.4"))

from app.effi_guides.effi_config import load_settings  # noqa: E402


_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_DATE_RE = re.compile(r"^\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s*$", re.IGNORECASE)


def parse_spanish_date(s: str) -> str | None:
    """'9 de febrero de 2026' → '2026-02-09'. Devuelve None si no matchea."""
    if not s:
        return None
    m = _DATE_RE.match(s.strip())
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTHS_ES.get(m.group(2).lower())
    if not month:
        return None
    year = int(m.group(3))
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_cop_amount(s: str) -> int | None:
    """'2.004.599,67 COP' → 200459967 (centavos). 0/None si vacío. None si malformado."""
    if s is None:
        return 0
    raw = s.strip()
    if not raw:
        return 0
    # Quitar moneda y NBSP
    clean = re.sub(r"[A-Za-z\s\xa0]", "", raw)
    if not clean:
        return 0
    # Formato colombiano: '.' miles, ',' decimal. Quitamos los '.' y reemplazamos ',' por '.'
    clean = clean.replace(".", "").replace(",", ".")
    try:
        value = float(clean)
    except ValueError:
        return None
    return int(round(value * 100))


@dataclass
class ParsedRow:
    raw_idx: int
    fecha: str | None
    tipo: str | None         # 'ingreso' | 'egreso' | 'transferencia'
    monto_centavos: int      # >= 0
    observacion: str
    categorias: list[str] = field(default_factory=list)
    external_ref: str = ""
    error: str | None = None


def parse_row(idx: int, row: dict, year_hint: int | None = None) -> ParsedRow:
    headers = list(row.keys())
    if len(headers) < 5:
        return ParsedRow(idx, None, None, 0, "", error="headers insuficientes")
    obs_h, eg_h, ing_h, cat_h, fec_h = headers[:5]
    observacion = (row[obs_h] or "").strip()
    fecha = parse_spanish_date(row[fec_h] or "")
    monto_eg = parse_cop_amount(row[eg_h] or "")
    monto_ing = parse_cop_amount(row[ing_h] or "")

    if monto_eg is None or monto_ing is None:
        return ParsedRow(idx, fecha, None, 0, observacion, error="monto malformado")

    if monto_eg > 0 and monto_ing > 0:
        # Transferencia interna entre buckets.
        if monto_eg != monto_ing:
            return ParsedRow(
                idx, fecha, "transferencia", monto_eg, observacion,
                error=f"transferencia con montos distintos: eg={monto_eg} ing={monto_ing}",
            )
        tipo = "transferencia"
        monto = monto_eg
    elif monto_eg > 0:
        tipo = "egreso"
        monto = monto_eg
    elif monto_ing > 0:
        tipo = "ingreso"
        monto = monto_ing
    else:
        return ParsedRow(idx, fecha, None, 0, observacion, error="sin monto")

    # Categorías
    cat_raw = (row[cat_h] or "").strip()
    if not cat_raw:
        categorias = ["SIN_CATEGORIA"]
    else:
        categorias = [c.strip() for c in cat_raw.split(",") if c.strip()]
        if not categorias:
            categorias = ["SIN_CATEGORIA"]

    # external_ref determinista — incluye índice de fila para soportar filas
    # legítimamente duplicadas (ej. 2 cargos Meta de Q200k el mismo día).
    # Re-importar el mismo CSV sigue siendo idempotente porque idx no cambia
    # mientras no se reordene el archivo.
    raw_key = f"notion|{idx}|{fecha or '?'}|{tipo}|{monto}|{observacion}|{cat_raw}"
    external_ref = "fin-" + hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:16]

    return ParsedRow(
        idx, fecha, tipo, monto, observacion,
        categorias=categorias, external_ref=external_ref,
    )


def load_category_map(conn: sqlite3.Connection) -> dict[str, int]:
    """nombre → id. Asume que el seed ya corrió."""
    return {
        r[0]: r[1]
        for r in conn.execute("SELECT nombre, id FROM fin_categories")
    }


def ensure_category(conn: sqlite3.Connection, cat_map: dict[str, int], nombre: str) -> int:
    """Si la categoría no existe en el DB, la crea on-the-fly (color None, activa=1)."""
    if nombre in cat_map:
        return cat_map[nombre]
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO fin_categories (nombre, color, activa, created_at) VALUES (?, NULL, 1, ?)",
        (nombre, now),
    )
    cat_map[nombre] = cur.lastrowid
    print(f"  [info] categoría nueva creada: {nombre!r} (id={cur.lastrowid})")
    return cur.lastrowid


def import_csv(csv_path: Path, conn: sqlite3.Connection, *, apply: bool, actor: str) -> dict:
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    parsed = [parse_row(i, r) for i, r in enumerate(rows, start=2)]  # idx 2 = primera fila de datos

    valid = [p for p in parsed if not p.error and p.fecha]
    errors = [p for p in parsed if p.error or not p.fecha]

    stats = {
        "total": len(parsed),
        "valid": len(valid),
        "errors": len(errors),
        "inserted": 0,
        "skipped_existing": 0,
        "by_tipo": {"ingreso": 0, "egreso": 0, "transferencia": 0},
        "errors_detail": [],
    }
    for p in errors:
        stats["errors_detail"].append({"row": p.raw_idx, "obs": p.observacion[:40], "error": p.error})

    if not apply:
        for p in valid:
            stats["by_tipo"][p.tipo] += 1
        return stats

    # APPLY
    cat_map = load_category_map(conn)
    now_iso = datetime.now().isoformat(timespec="seconds")

    for p in valid:
        try:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO fin_movements
                    (fecha, tipo, monto_centavos, moneda, observacion, external_ref, creado_por, creado_at)
                VALUES (?, ?, ?, 'COP', ?, ?, ?, ?)
                """,
                (p.fecha, p.tipo, p.monto_centavos, p.observacion, p.external_ref, actor, now_iso),
            )
            if cur.rowcount == 0:
                # Ya existe (external_ref UNIQUE colisión) — skip
                stats["skipped_existing"] += 1
                continue
            movement_id = cur.lastrowid
            stats["inserted"] += 1
            stats["by_tipo"][p.tipo] += 1

            for cat_nombre in p.categorias:
                cat_id = ensure_category(conn, cat_map, cat_nombre)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO fin_movement_categories (movement_id, category_id)
                    VALUES (?, ?)
                    """,
                    (movement_id, cat_id),
                )
        except sqlite3.IntegrityError as e:
            stats["errors_detail"].append(
                {"row": p.raw_idx, "obs": p.observacion[:40], "error": f"IntegrityError: {e}"}
            )
    conn.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa CSV de finanzas Notion a SQLite.")
    parser.add_argument("--csv", required=True, action="append",
                        help="Path al CSV. Puede repetirse para múltiples archivos.")
    parser.add_argument("--apply", action="store_true",
                        help="Escribe en la DB. Sin esto, solo dry-run.")
    parser.add_argument("--actor", default="import-notion",
                        help="Valor para creado_por (default: 'import-notion').")
    args = parser.parse_args()

    settings = load_settings()
    db_path = settings.db_path
    if not db_path.exists():
        print(f"ERROR: DB no existe en {db_path}. Arrancá la app una vez para crearla.", file=sys.stderr)
        return 2

    print(f"→ DB: {db_path}")
    print(f"→ Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"→ Actor: {args.actor}")
    print()

    conn = sqlite3.connect(str(db_path))
    try:
        # Asegurarse de que las tablas existen (idempotente)
        from vaecos_v02.storage.db import (
            _ensure_fin_movements_table,
            _ensure_fin_categories_table,
            _ensure_fin_movement_categories_table,
            seed_fin_categories,
        )
        _ensure_fin_categories_table(conn)
        _ensure_fin_movements_table(conn)
        _ensure_fin_movement_categories_table(conn)
        seed_fin_categories(conn)

        total_stats = {
            "files": 0, "total": 0, "valid": 0, "errors": 0,
            "inserted": 0, "skipped_existing": 0,
            "by_tipo": {"ingreso": 0, "egreso": 0, "transferencia": 0},
        }
        for csv_path_str in args.csv:
            csv_path = Path(csv_path_str)
            if not csv_path.exists():
                print(f"✗ NO existe: {csv_path}")
                continue
            print(f"── {csv_path.name} ──")
            stats = import_csv(csv_path, conn, apply=args.apply, actor=args.actor)
            print(f"  Total filas:       {stats['total']}")
            print(f"  Válidas:           {stats['valid']}")
            print(f"  Con error:         {stats['errors']}")
            if args.apply:
                print(f"  Insertadas:        {stats['inserted']}")
                print(f"  Ya existían:       {stats['skipped_existing']}")
            print(f"  Por tipo:          {stats['by_tipo']}")
            if stats["errors_detail"]:
                print(f"  Errores (primeros 10):")
                for e in stats["errors_detail"][:10]:
                    print(f"    row {e['row']}: {e['obs']!r} → {e['error']}")
            print()
            total_stats["files"] += 1
            for k in ("total", "valid", "errors", "inserted", "skipped_existing"):
                total_stats[k] += stats[k]
            for t in ("ingreso", "egreso", "transferencia"):
                total_stats["by_tipo"][t] += stats["by_tipo"][t]

        if total_stats["files"] > 1:
            print("══ TOTAL ══")
            print(f"  Archivos:          {total_stats['files']}")
            print(f"  Total filas:       {total_stats['total']}")
            print(f"  Válidas:           {total_stats['valid']}")
            print(f"  Con error:         {total_stats['errors']}")
            if args.apply:
                print(f"  Insertadas:        {total_stats['inserted']}")
                print(f"  Ya existían:       {total_stats['skipped_existing']}")
            print(f"  Por tipo:          {total_stats['by_tipo']}")

        if not args.apply:
            print("(DRY-RUN — no se escribió nada. Para confirmar: agregar --apply)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
