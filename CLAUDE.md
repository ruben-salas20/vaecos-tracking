# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

VAECOS Seguimiento reconciles the shipment state in Notion against the carrier (Effi) and updates Notion automatically. It has three layers:

- `v0.2/` — business engine + CLI/TUI + SQLite persistence + services (run_tracking, sync_guides, update_guide)
- `v0.3/` — `DashboardRepository` and SVG charts, **reused** by v0.4 (the standalone v0.3 server is legacy)
- `v0.4/` — Flask web UI (primary interface in use): auth, blueprints, dark mode, search, all-guides, notes, state editor

Dependencies: Flask 3.1, bcrypt, openpyxl, waitress. Python 3.12+.

## Commands

Start the web interface (v0.4 — primary):
```powershell
python v0.4/server.py
# or
iniciar_v04.bat
```

Legacy v0.3 (only for fallback during transition):
```powershell
python v0.3/server.py
```

Run tracking from CLI (all active guides, dry-run):
```powershell
python v0.2/cli.py run --dry-run
```

Apply changes to Notion:
```powershell
python v0.2/cli.py run --apply
```

Run on specific guides:
```powershell
python v0.2/cli.py run --guides B263378877-1 --dry-run
```

Tests:
```powershell
python -m unittest discover -s v0.2/tests -v
```

Verify syntax (all layers):
```powershell
python -m compileall "v0.2" "v0.3" "v0.4"
```

## Architecture

### Data flow

1. `NotionProvider` (`v0.2/vaecos_v02/providers/notion_provider.py`) fetches active guides from Notion.
2. A `Carrier` (Protocol in `v0.2/vaecos_v02/providers/carrier.py`) fetches tracking data per guide. Effi is fully implemented; Guatex is a stub. The carrier is selected per guide from the Notion `Transportista` field.
3. `decide_status()` in `v0.2/vaecos_v02/core/rules.py` evaluates rules in stratified semantic order: **terminal → operational → contextual → stagnation → preservation**. First match wins within each phase.
4. `UpdateService` (`v0.2/vaecos_v02/app/services/update_service.py`) applies the decision and writes results to both Notion and SQLite.

### Rule engine

Rules live in the `rules` SQLite table, evaluated by ascending `priority`. The schema uses `estado_match_kind` (`any` | `equals_one_of` | `contains_any_of`), `novelty_match_kind`, and `days_comparator` (`gt` | `gte` | `lt` | `lte` | `no_date`). Contextual rules match only the **latest** novelty event (not the full history). A 2-day cooldown applies when Notion status is `Gestión novedad`. Rules are editable at `/rules` with full audit trail in `rule_history`.

New rules should be tested with `/rules/preview?guia=<guide>` before saving.

### SQLite schema

`v0.2/data/vaecos_tracking.db` (WAL mode). Tables:
- **Engine (v0.2)**: `runs`, `run_results`, `tracking_status_events`, `tracking_novelty_events`, `rules`, `rule_history`
- **App (v0.4)**: `users`, `import_log`, `guides`, `guide_notes`, `guide_edits`

`run_results` was extended with columns `carrier`, `notas_operador`, `telefono` (all idempotent ALTERs in `db.py`).

Migrations are idempotent functions in `v0.2/vaecos_v02/storage/db.py` called on every `init_db()`.

### v0.4 web server (current)

Flask app factory in `v0.4/app/__init__.py`. Five blueprints:
- `auth` — `/login`, `/logout`, `/change-password`
- `dashboard` — 14 GETs migrated from v0.3 + `/all-guides`, `/search`, `/guides/<g>/notes`, `/guides/<g>/state`
- `runs` — `/run/new`, `/run/progress/<token>`, `/runs/<id>/export/effi`, `/sync/notion`, `/sync/progress/<token>`
- `import_guides` — `/import` (upload + preview + confirm; confirm creates Notion pages)
- `users` — `/users`, `/users/<id>/{toggle,delete,reset-password}` (admin-only)

v0.4 imports v0.2 (engine) and v0.3 (`DashboardRepository`, charts) directly via `sys.path.insert`. Bootstrap admin is seeded on first start from `V04_BOOTSTRAP_EMAIL` / `V04_BOOTSTRAP_PASSWORD`.

### Notion writes

Three entry points to Notion API:
- `update_page_status(page_id, estado, fecha)` — used by the engine when a tracking run applies a change.
- `update_estado_novedad(page_id, estado)` — used when the operator edits state from the app (case-insensitive option resolution via `_resolve_select_option`).
- `create_guide_page(guia, cliente, ...)` — used by Excel import to create new pages with all available fields.

Atomic state edits go through `v0.2/vaecos_v02/app/services/update_guide.py`: writes to Notion FIRST, then to the local `guides` table, and audits the attempt in `guide_edits` (with `sync_ok = 0` and `error_msg` if Notion rejected).

### Environment

`.env` lives at the repo root. Key variables:

```
# Notion
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=e7da64fa-d6c7-47ab-bc12-d7af207f871b
NOTION_VERSION=2025-09-03

# Effi
EFFI_TIMEOUT_SECONDS=20

# DB shared by all layers
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db

# v0.4 Flask
FLASK_SECRET_KEY=...                      # required in production
VAECOS_ENV=development
V04_BOOTSTRAP_EMAIL=admin@vaecos.com      # only used on first start (seed admin)
V04_BOOTSTRAP_PASSWORD=...
V04_HOST=127.0.0.1
V04_PORT=8765

# Updates from GitHub Releases
V02_UPDATE_REPO=ruben-salas20/vaecos-tracking
V02_UPDATE_GITHUB_TOKEN=                  # required for private release repo
```

### Adding a new carrier

1. Create `v0.2/vaecos_v02/providers/carriers/<name>.py` implementing the `Carrier` Protocol.
2. Register it in `v0.2/vaecos_v02/providers/carriers/__init__.py`.
3. Notion's `Transportista` field value must match the carrier's `name` class variable.

## Documentation

| File | Purpose |
|------|---------|
| `docs/PRD.md` | Product requirements v2.0 — vision, features, decisions |
| `docs/roadmap-estrategico.md` | Strategic roadmap — 5 phases with exit criteria |
| `docs/ARCHITECTURE.md` | Current and target architecture, stack decisions, new DB tables |
| `docs/DESIGN.md` | UI design system (Inter, tokens, components) |
| `docs/roadmap.md` | Technical state checklist — current state, commands, risks |

## Key files

| File | Purpose |
|------|---------|
| `v0.2/vaecos_v02/core/rules.py` | Rule engine — `decide_status()` and all matching logic |
| `v0.2/vaecos_v02/core/models.py` | Frozen dataclasses: `Rule`, `RuleDecision`, `ProcessingResult`, `NotionClientRecord` |
| `v0.2/vaecos_v02/storage/db.py` | SQLite schema, `init_db()`, idempotent migrations |
| `v0.2/vaecos_v02/storage/rules_repository.py` | CRUD + audit trail for the `rules` table |
| `v0.2/vaecos_v02/providers/effi_provider.py` | Effi HTML scraper |
| `v0.2/vaecos_v02/providers/notion_provider.py` | Notion API client (read + write + page create) |
| `v0.2/vaecos_v02/app/services/sync_guides.py` | Pull-only sync Notion → tabla `guides` (upsert by page_id) |
| `v0.2/vaecos_v02/app/services/update_guide.py` | Atomic state edit: Notion → local → audit |
| `v0.3/vaecos_v03/storage.py` | `DashboardRepository` — reused by v0.4 for queries (search, guides, notes, edits) |
| `v0.3/vaecos_v03/render.py` | SVG charts reused by v0.4 |
| `v0.4/app/__init__.py` | Flask `create_app()` factory, blueprint registration, bootstrap admin |
| `v0.4/app/dashboard/routes.py` | Most GET routes + `/all-guides`, `/search`, notes/state endpoints |
| `v0.4/app/runs/routes.py` | Run dispatch, sync dispatch, CSV export, AJAX update_notas |
| `v0.4/app/runs/jobs.py` | Background job pattern (threads + token + polling) for runs and syncs |
| `v0.4/app/import_guides/parser.py` | Excel parser (NFKD-normalized headers, DPI digits, contenido cantidad+producto) |
| `v0.4/app/notion_helpers.py` | Cached Estado novedad options for editor dropdowns (TTL 5 min) |

## Operational notes

- `--apply` updates Notion properties only; the page history body is updated manually.
- Use `--save-raw-html` to save Effi HTML for debugging when the parser breaks.
- v0.4 supports multiple users; first admin is seeded from `V04_BOOTSTRAP_EMAIL`/`V04_BOOTSTRAP_PASSWORD`.
- `apply-update` preserves `.env`, `v0.2/data/`, and `v0.2/reports/` — safe to run.
- After any code change you must FULLY restart `iniciar_v04.bat` (Flask reloads templates but NOT Python modules; `use_reloader=False` is set to avoid the BuildError trap).
- Auto-sync runs after each tracking run finishes; manual sync is available at `/sync/notion` from `/all-guides`.
- All state changes from the operator are atomic: if Notion rejects, nothing is written locally and the failed attempt is logged in `guide_edits` with `sync_ok = 0`.

## Production deploy (live)

URL: `https://app.vaecos.com` (deploy 2026-05-07).

| | |
|---|---|
| VPS | Hostinger KVM 2 — IP `2.24.206.197` — Ubuntu 24.04 LTS |
| App user | `vaecos` (sudo NOPASSWD), code at `/opt/vaecos/`, venv at `/opt/vaecos/.venv/` |
| Service | systemd `vaecos.service` running `waitress-serve --listen=127.0.0.1:8765 --threads=4 wsgi:application` |
| Reverse proxy | Caddy with auto TLS (Let's Encrypt) at `/etc/caddy/Caddyfile` |
| Firewall | UFW: only `22/80/443` |
| SSH | Key-only — local key at `~/.ssh/vaecos_vps` (PC dueño) |
| DB | `/opt/vaecos/data/vaecos_tracking.db` (WAL) |
| Secrets | `/opt/vaecos/.env` (chmod 600) — `FLASK_SECRET_KEY`, `NOTION_API_KEY`, etc. |
| ProxyFix | Active only when `VAECOS_ENV=production` for correct rate-limiting IPs |

### Deploy a code change

```powershell
# From the dueño's PC (Windows):
git add . ; git commit -m "..." ; git push
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@2.24.206.197 "cd /opt/vaecos && git pull && sudo systemctl restart vaecos"
# If requirements.txt changed, add: && .venv/bin/pip install -r v0.4/requirements.txt
```

### Operate the VPS

```powershell
# SSH in as vaecos (preferred) or root
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@2.24.206.197

# Inside the VPS:
sudo systemctl status vaecos          # service status
sudo journalctl -u vaecos -f           # live app logs
sudo journalctl -u caddy -n 50         # caddy logs
sudo systemctl restart vaecos          # restart app
```

### Migrate the operator's DB (one-shot)

When the operator hands over her local `vaecos_tracking.db`:
```powershell
scp -i $env:USERPROFILE\.ssh\vaecos_vps "ruta\operadora.db" vaecos@2.24.206.197:/opt/vaecos/data/operator.db
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@2.24.206.197 "sudo systemctl stop vaecos && \
  mv /opt/vaecos/data/vaecos_tracking.db /opt/vaecos/data/vaecos_tracking.db.fresh-bootstrap && \
  mv /opt/vaecos/data/operator.db /opt/vaecos/data/vaecos_tracking.db && \
  cd /opt/vaecos && .venv/bin/python scripts/post_restore.py --skip-bootstrap && \
  sudo systemctl start vaecos"
```

`scripts/post_restore.py` is idempotent and supports `--dry-run`. It applies migrations + Notion sync + telefono backfill on top of the operator's existing data.

### Hostinger MCP (DNS + VPS management)

The Hostinger MCP is available at `mcp__hostinger__*` tools. Useful operations:

- `VPS_getVirtualMachineDetailsV1` — VPS info
- `VPS_getMetricsV1` — CPU/memory metrics
- `VPS_createSnapshotV1` — manual snapshot before risky changes
- `DNS_getDNSRecordsV1` / `DNS_updateDNSRecordsV1` — manage DNS records (always use `overwrite=false` to avoid wiping existing records)

### SSH gotcha — first-match-wins

If you change `/etc/ssh/sshd_config.d/99-*.conf` and the change doesn't take effect: SSHD uses **first-match-wins** in alphabetical order. Ubuntu cloud-init drops a `50-cloud-init.conf` that may conflict. Always verify the effective config with:
```
sudo sshd -T | grep -iE 'passwordauth|permitroot|pubkey'
```
