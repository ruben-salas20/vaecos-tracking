"""Reset the password of an existing user in the VAECOS database.

Usage:
    python scripts/reset_user_password.py <email> <new_password> [--db <path>]

Examples:
    # Local PC (default DB path)
    python scripts/reset_user_password.py admin@vaecos.com NuevaPass123

    # VPS production
    python scripts/reset_user_password.py admin@vaecos.com NuevaPass123 --db /opt/vaecos/data/vaecos_tracking.db

Requires:
    - bcrypt installed (already in v0.4/requirements.txt)
    - The user must already exist (use the bootstrap flow in app/__init__.py to seed the first admin)
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import bcrypt


DEFAULT_DB = Path(__file__).resolve().parents[1] / "v0.2" / "data" / "vaecos_tracking.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a VAECOS user's password.")
    parser.add_argument("email", help="Email of the user to reset.")
    parser.add_argument("new_password", help="New password (min 8 chars).")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to vaecos_tracking.db (default: {DEFAULT_DB}).",
    )
    args = parser.parse_args()

    if len(args.new_password) < 8:
        print("ERROR: new_password must be at least 8 characters.", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"ERROR: DB not found at {args.db}", file=sys.stderr)
        return 2

    pw_hash = bcrypt.hashpw(args.new_password.encode(), bcrypt.gensalt()).decode()

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, email, name, role, active FROM users WHERE email = ?",
            (args.email.strip().lower(),),
        ).fetchone()
        if row is None:
            print(f"ERROR: no user found with email '{args.email}'.", file=sys.stderr)
            return 1
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (pw_hash, row["id"]),
        )
        # If the account was deactivated, the user wouldn't be able to log in even with the new password.
        if not row["active"]:
            print(f"WARNING: account '{row['email']}' is INACTIVE. Reactivating it.")
            conn.execute("UPDATE users SET active = 1 WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()

    print(f"OK: password reset for {row['email']} (name='{row['name']}', role='{row['role']}').")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
