"""Apply v0.4 migrations + sync + bootstrap admin to an existing operator DB.

This is the script to run on the VPS after copying the operator's
`vaecos_tracking.db` over. It is idempotent: safe to run multiple times.

Steps performed (in order):
    1. Backup the source DB next to it as `<name>.bak.<timestamp>`
    2. init_db() — adds tables / columns / indexes added since v0.3
       (telefono column on run_results, users, import_log, guides,
        guide_notes, guide_edits, WAL mode)
    3. sync_guides() — pulls all pages from Notion into the local guides
       table so the operator sees ALL guides on day 1
    4. Backfill telefono in run_results for rows where it is empty
    5. Seed the bootstrap admin user from .env if no users exist

Usage:
    python scripts/post_restore.py
        (uses the .env at the repo root and V02_SQLITE_DB_PATH)

    python scripts/post_restore.py --db-path /opt/vaecos/data/vaecos.db

Flags:
    --skip-backup     Do not create the .bak.<ts> file
    --skip-sync       Skip the Notion sync step (useful for offline DB prep)
    --skip-backfill   Skip the telefono backfill in run_results
    --skip-bootstrap  Skip seeding the admin user
    --dry-run         Print what would be done without writing anything
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "v0.2"))


def _load_env() -> None:
    """Load .env from repo root into os.environ."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _resolve_db_path(arg_path: str | None) -> Path:
    if arg_path:
        return Path(arg_path)
    env_path = os.environ.get("V02_SQLITE_DB_PATH")
    if env_path:
        return Path(env_path)
    return REPO_ROOT / "v0.2" / "data" / "vaecos_tracking.db"


def step_backup(db_path: Path, *, dry_run: bool) -> Path | None:
    if not db_path.exists():
        print(f"[skip backup] DB not found at {db_path} — will be created")
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".bak.{ts}")
    print(f"[backup] {db_path} -> {backup_path}")
    if not dry_run:
        shutil.copy2(db_path, backup_path)
    return backup_path


def step_migrate(db_path: Path, *, dry_run: bool) -> dict:
    from vaecos_v02.storage.db import connect, init_db
    print(f"[migrate] init_db() on {db_path}")
    if dry_run:
        return {"status": "dry-run"}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        init_db(conn)
        # Quick verification — list tables
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        tables = [r["name"] for r in rows]
        rr_cols = [c["name"] for c in conn.execute("PRAGMA table_info(run_results)").fetchall()]
        print(f"  tables: {', '.join(tables)}")
        print(f"  run_results columns: {', '.join(rr_cols)}")
        return {"tables": tables, "run_results_columns": rr_cols}
    finally:
        conn.close()


def step_sync(db_path: Path, *, dry_run: bool) -> dict:
    api_key = os.environ.get("NOTION_API_KEY", "")
    ds_id = os.environ.get("NOTION_DATA_SOURCE_ID", "")
    if not api_key or not ds_id:
        print("[skip sync] Missing NOTION_API_KEY or NOTION_DATA_SOURCE_ID in .env")
        return {"status": "skipped"}
    if dry_run:
        print("[sync] would pull all pages from Notion (dry-run)")
        return {"status": "dry-run"}
    from vaecos_v02.providers.notion_provider import NotionProvider
    from vaecos_v02.app.services.sync_guides import sync_guides
    notion = NotionProvider(
        api_key=api_key,
        notion_version=os.environ.get("NOTION_VERSION", "2025-09-03"),
        data_source_id=ds_id,
    )
    print("[sync] fetching all pages from Notion (this can take 5–30 seconds)...")
    stats = sync_guides(db_path, notion)
    print(f"  read:       {stats.read_from_notion}")
    print(f"  inserted:   {stats.inserted}")
    print(f"  updated:    {stats.updated}")
    print(f"  unchanged:  {stats.unchanged}")
    print(f"  archived:   {stats.archived}")
    print(f"  incomplete: {stats.incomplete}")
    return stats.__dict__


def step_backfill(db_path: Path, *, dry_run: bool) -> dict:
    """Fill run_results.telefono for rows where it is empty, using the
    canonical Teléfono recorded in the guides snapshot."""
    api_key = os.environ.get("NOTION_API_KEY", "")
    if not api_key:
        print("[skip backfill] Missing NOTION_API_KEY")
        return {"status": "skipped"}
    if dry_run:
        print("[backfill] would update run_results.telefono from guides table")
        return {"status": "dry-run"}
    from vaecos_v02.storage.db import connect
    conn = connect(db_path)
    try:
        # Fast path: copy from local guides table (already synced).
        cur = conn.execute(
            "UPDATE run_results "
            "SET telefono = (SELECT g.telefono FROM guides g "
            "                WHERE UPPER(g.guia) = UPPER(run_results.guia) "
            "                  AND g.telefono IS NOT NULL AND g.telefono != '') "
            "WHERE (telefono IS NULL OR telefono = '') "
            "  AND EXISTS (SELECT 1 FROM guides g "
            "              WHERE UPPER(g.guia) = UPPER(run_results.guia) "
            "                AND g.telefono IS NOT NULL AND g.telefono != '')"
        )
        updated = cur.rowcount
        conn.commit()
        empty_after = conn.execute(
            "SELECT COUNT(*) AS c FROM run_results "
            "WHERE telefono IS NULL OR telefono = ''"
        ).fetchone()["c"]
        print(f"[backfill] updated {updated} run_results rows; {empty_after} still empty")
        return {"updated": updated, "empty_remaining": empty_after}
    finally:
        conn.close()


def step_bootstrap(db_path: Path, *, dry_run: bool) -> dict:
    email = os.environ.get("V04_BOOTSTRAP_EMAIL", "")
    password = os.environ.get("V04_BOOTSTRAP_PASSWORD", "")
    if not email or not password:
        print("[skip bootstrap] Missing V04_BOOTSTRAP_EMAIL or V04_BOOTSTRAP_PASSWORD")
        return {"status": "skipped"}
    if dry_run:
        print(f"[bootstrap] would seed admin {email} if no users exist")
        return {"status": "dry-run"}
    try:
        import bcrypt
    except ImportError:
        print("[skip bootstrap] bcrypt not installed")
        return {"status": "skipped"}
    from vaecos_v02.storage.db import connect
    conn = connect(db_path)
    try:
        existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if existing > 0:
            print(f"[bootstrap] {existing} user(s) already exist — skipping seed")
            return {"status": "skipped", "existing": existing}
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (email, password_hash, name, role, active, created_at, created_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (email, pw_hash, "Admin", "admin", 1,
             datetime.now().isoformat(timespec="seconds"), "post_restore"),
        )
        conn.commit()
        print(f"[bootstrap] seeded admin user {email}")
        return {"status": "created", "email": email}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db-path", help="Path to the SQLite DB to migrate")
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--skip-bootstrap", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without writing anything")
    args = parser.parse_args()

    _load_env()
    db_path = _resolve_db_path(args.db_path)
    print(f"=== post_restore on {db_path} (dry_run={args.dry_run}) ===")

    if not args.skip_backup:
        step_backup(db_path, dry_run=args.dry_run)
    step_migrate(db_path, dry_run=args.dry_run)
    if not args.skip_sync:
        step_sync(db_path, dry_run=args.dry_run)
    if not args.skip_backfill:
        step_backfill(db_path, dry_run=args.dry_run)
    if not args.skip_bootstrap:
        step_bootstrap(db_path, dry_run=args.dry_run)

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
