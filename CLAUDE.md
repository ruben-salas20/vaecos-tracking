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

1. **Pre-sync** (Phase 2.1): `sync_guides()` pulls all pages from Notion into the local `guides` table at the start of every tracking run. If Notion fails, the engine falls back to the existing local snapshot (warn logged).
2. **Read source** (Phase 2.1): the engine reads guides to process from the **local `guides` table** via `local_guides.fetch_active_guides_local()` / `fetch_selected_guides_local()` — NOT directly from Notion. Same shape as the old `NotionProvider.fetch_*` methods.
3. A `Carrier` (Protocol in `v0.2/vaecos_v02/providers/carrier.py`) fetches tracking data per guide. Effi is fully implemented; Guatex is a stub. The carrier is selected per guide from the local row's `carrier` column.
4. `decide_status()` in `v0.2/vaecos_v02/core/rules.py` evaluates rules in stratified semantic order: **terminal → operational → contextual → stagnation → preservation**. First match wins within each phase.
5. **Writes** (still atomic Notion-first): when `--apply` decides to change state, `notion.update_page_status()` is called; on success, the post-run sync brings the change back to local. App-initiated edits (state, fields, archive, create) follow the same pattern in `update_guide.py` / `add_guide.py`. Phase 2.4 (pendiente) invertirá esta polaridad.

### Rule engine

Rules live in the `rules` SQLite table, evaluated by ascending `priority`. The schema uses `estado_match_kind` (`any` | `equals_one_of` | `contains_any_of`), `novelty_match_kind`, and `days_comparator` (`gt` | `gte` | `lt` | `lte` | `no_date`). Contextual rules match only the **latest** novelty event (not the full history). A 2-day cooldown applies when Notion status is `Gestión novedad`. Rules are editable at `/rules` with full audit trail in `rule_history`.

New rules should be tested with `/rules/preview?guia=<guide>` before saving.

### SQLite schema

`v0.2/data/vaecos_tracking.db` (WAL mode). Tables:
- **Engine (v0.2)**: `runs`, `run_results`, `tracking_status_events`, `tracking_novelty_events`, `rules`, `rule_history`
- **App (v0.4)**: `users`, `import_log`, `guides`, `guide_notes`, `guide_edits`
- **Effi bot**: `effi_catalog`, `effi_orders`, `effi_audit_log`, `effi_review_queue`
- **Finanzas (Fase 5.1)**: `fin_movements` (monto en centavos, multi-moneda con default COP), `fin_categories` (color hex + activa), `fin_movement_categories` (M:N, FK CASCADE para movements / RESTRICT para categories)
- **IA conversacional (Fase 5.2)**: `ai_conversations` (1 por usuario activa), `ai_messages` (role IN user/assistant/tool, content + tool_name + tool_args_json), `ai_audit_log` (user_id, tool_name, args, latency_ms, ok/error)

`run_results` was extended with columns `carrier`, `notas_operador`, `telefono` (all idempotent ALTERs in `db.py`).

Migrations are idempotent functions in `v0.2/vaecos_v02/storage/db.py` called on every `init_db()`.

### v0.4 web server (current)

Flask app factory in `v0.4/app/__init__.py`. Eight blueprints:
- `auth` — `/login`, `/logout`, `/change-password`, `/mi-cuenta` (perfil + cambio de password en una sola página)
- `dashboard` — 14 GETs migrated from v0.3 + `/all-guides`, `/search`, `/guides/new` (crear), `/guides/<g>/notes`, `/guides/<g>/state`, `/guides/<g>/fields` (Phase 2.2), `/guides/<g>/archive` y `/guides/<g>/unarchive` (Phase 2.3)
- `runs` — `/run/new`, `/run/progress/<token>`, `/runs/<id>/export/effi`, `/sync/notion`, `/sync/progress/<token>`
- `import_guides` — `/import` (upload + preview + confirm; confirm creates Notion pages)
- `users` — `/users`, `/users/<id>/{toggle,delete,reset-password}` (admin-only)
- `effi` (Creador guías) — `/effi` dashboard, `/effi/catalog` CRUD (admin), `/effi/queue` cola humana, `/effi/audit` historial, `/effi/run/manual` trigger + `/effi/run/progress/<token>` polling JSON.
- `finanzas` (Fase 5.1) — `/finanzas` listado con filtros + paginación, `/finanzas/new`, `/finanzas/<id>/edit`, `/finanzas/<id>/delete` (admin), `/finanzas/analytics` con export `.xlsx`, `/finanzas/categorias` CRUD (admin).
- `ai` (Fase 5.2) — `POST /ai/chat` (rate-limited 30/h por user_id), `GET /ai/chat/history` (hidrata widget al abrir), `POST /ai/chat/clear`. Widget flotante incluido en `base.html` (visible si hay sesión).

v0.4 imports v0.2 (engine) and v0.3 (`DashboardRepository`, charts) directly via `sys.path.insert`. Bootstrap admin is seeded on first start from `V04_BOOTSTRAP_EMAIL` / `V04_BOOTSTRAP_PASSWORD`.

### Notion writes

Entry points to Notion API:
- `update_page_status(page_id, estado, fecha)` — engine when `--apply` changes a state.
- `update_estado_novedad(page_id, estado)` — app cuando la operadora edita el estado.
- `update_guide_fields(page_id, *, telefono=_UNSET, producto=_UNSET, valor=_UNSET, cantidad=_UNSET)` — Phase 2.2 PATCH atómico de campos editables. Sentinel `_UNSET` distingue "no enviado" de "enviado vacío" (clear).
- `create_guide_page(guia, cliente, ...)` — Excel import + Phase 2.3 (formulario `/guides/new`).
- `archive_page(page_id)` / `unarchive_page(page_id)` — Phase 2.3 soft-delete y restore (papelera 30 días).

**Patrón atómico** (vigente en Fase 2 actual): todos los servicios en `update_guide.py` y `add_guide.py` escriben **Notion FIRST** y, si Notion responde OK, actualizan local + audit (`guide_edits`). Si Notion falla, no se modifica nada local pero queda registrado el intento con `sync_ok=0` y `error_msg`. **Phase 2.4** (pendiente) invertirá esta polaridad: local FIRST, Notion mirror best-effort.

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

# Effi ERP (módulo Creador guías)
EFFI_USERNAME=
EFFI_PASSWORD=
EFFI_SESSION_PATH=v0.2/data/effi-session.json
EFFI_HEADLESS=true
EFFI_BASE_URL=https://effi.com.co
EFFI_NAVIGATION_TIMEOUT_MS=30000

# Notificaciones email (opcional — si están vacías, el notifier solo logea)
NOTIFY_EMAIL=                              # destinatario(s) separados por coma
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_SSL=false                         # true para puerto 465
EFFI_DAILY_DIGEST_ONLY=true                # producción: digest 22:00 GT en vez de email por corrida

# IA (validador direcciones + asistente conversacional)
MINIMAX_API_KEY=                           # requerido para bot Effi + asistente IA
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_TIMEOUT_SECONDS=30
AI_ADDRESS_VALIDATION=auto                 # auto = on si hay API key
```

### Módulo Creador guías (Effi)

Stack: Playwright (Chromium headless) + storageState reusable. Flujo end-to-end:
1. `scripts/effi_login.py` — login interactivo una vez al mes; guarda `effi-session.json`.
2. Bot lee `/app/orden_v`, filtra `PEDIDO CONFIRMADO` sin remisión.
3. Por cada orden: lee productos del modal, valida dirección, clasifica con `effi_catalog`.
4. Decide: ejecutar (write) / escalar a cola humana / saltar (ya procesada).
5. Persiste en `effi_orders` (idempotente), `effi_audit_log`, `effi_review_queue`.

Tablas (todas creadas por migración idempotente en `v0.2/vaecos_v02/storage/db.py`):
- `effi_catalog` — productos con `descripcion_exacta`, `aliases` (JSON), `tipo` (`intimo_femenino`|`otro`), `precio_declarado`.
- `effi_orders` — PK `orden_id`, status (`done`|`failed`|`human_review`|`pending`), classification, valor, remision/guia ids.
- `effi_audit_log` — historial granular de acciones del bot.
- `effi_review_queue` — cola para casos no automatizables.

Scripts:
- `python scripts/effi_login.py [--auto|--headless]` — generar/renovar sesión.
- `python scripts/effi_dry_run.py [--limit N|--order N]` — escanear sin escribir.
- `python scripts/effi_run_one.py --order N [--apply]` — procesar UNA orden.
- `python scripts/effi_run.py [--apply] [--limit N]` — masivo (usado por cron).

Cron VPS (cada hora, modo apply):
```
# Como vaecos@VPS, crontab -e:
0 * * * * cd /opt/vaecos && .venv/bin/python scripts/effi_run.py --apply >> /opt/vaecos/logs/effi.log 2>&1
```

Asegurarse que `/opt/vaecos/logs/` exista y sea writable por `vaecos`. Para inspeccionar:
```bash
tail -f /opt/vaecos/logs/effi.log
```

Recovery cuando expira sesión: el bot manda email vía notifier (si está configurado) y deja un audit log de tipo `health_check` fallido. Renovar localmente con `effi_login.py` y subir el nuevo `effi-session.json` al VPS con scp.

### Módulo Finanzas (Fase 5.1)

Libro de movimientos en COP con multi-categoría. Sin sync con Notion — Notion fue la fuente del histórico (one-shot import) pero ya no es fuente activa.

- Schema: ver "SQLite schema" arriba (3 tablas).
- Repository: `v0.4/app/finanzas/repository.py` — FK CASCADE/RESTRICT requiere `PRAGMA foreign_keys = ON` en cada conexión (incluido en `_connect()`).
- Monto siempre en **centavos INTEGER** (no REAL) para evitar errores de float con datos contables.
- Routes: `v0.4/app/finanzas/routes.py` con CRUD + analytics + export `.xlsx` + catálogo admin.
- Permisos: todos los users crean movimientos; solo creador o admin editan; solo admin borra. Solo admin gestiona catálogo de categorías.

Migración inicial del histórico Notion:
```powershell
python scripts/import_finanzas_notion.py --csv <path> --apply
```
Idempotente (`external_ref` UNIQUE como hash determinista por fila). Re-correr no duplica.

### Módulo IA conversacional (Fase 5.2)

Widget flotante incluido en `base.html` (visible si hay sesión activa). Backend en `v0.4/app/ai/`:
- `agent.py` — loop tool-use iterativo (max 5 iteraciones), system prompt anti-alucinación, parser robusto del JSON que tolera `<think>...</think>` de MiniMax M2.7.
- `tools.py` — 6 tools registradas (logística, finanzas, búsqueda, top clientes, corridas, manual). Cada tool valida args defensivamente y devuelve `{"error": ...}` en lugar de raise.
- `manual.py` — knowledge base del aplicativo en 13 tópicos con scoring por keywords. Editable directo en código.
- `repository.py` — persistencia de `ai_conversations`, `ai_messages`, `ai_audit_log` con FK CASCADE/RESTRICT.
- `routes.py` — endpoints `/ai/chat`, `/ai/chat/history`, `/ai/chat/clear`. Rate limit 30/h por user_id via Flask-Limiter.

Tools devuelven estructuras compactas (no rows crudas) para minimizar tokens. Si una tool devuelve `{"error": ...}`, el modelo NO la re-llama con los mismos args (regla explícita en system prompt).

Para agregar una nueva tool:
1. Implementar `tool_<nombre>(db_path, args)` en `tools.py`.
2. Registrar en `TOOL_REGISTRY` con `description` y `args_schema`.
3. El system prompt levanta la descripción automáticamente vía `tools_for_prompt()`.

Para extender el manual del asistente:
1. Agregar entrada a `HELP_TOPICS` en `manual.py` con `title`, `keywords` (aliases) y `content` (markdown).
2. La IA lo recoge automáticamente — no hay que tocar prompts.

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
| `v0.2/vaecos_v02/providers/notion_provider.py` | Notion API client (read + write + create + archive/unarchive) |
| `v0.2/vaecos_v02/app/services/sync_guides.py` | Pull-only sync Notion → tabla `guides` (upsert by page_id) |
| `v0.2/vaecos_v02/app/services/local_guides.py` | **Phase 2.1** — read guides from local table (engine consumes this, not Notion) |
| `v0.2/vaecos_v02/app/services/update_guide.py` | Atomic state/fields edit + archive + unarchive (Notion → local → audit) |
| `v0.2/vaecos_v02/app/services/add_guide.py` | **Phase 2.3** — atomic create new guide (Notion → local + audit) |
| `v0.3/vaecos_v03/storage.py` | `DashboardRepository` — reused by v0.4 for queries (search, guides, notes, edits) |
| `v0.3/vaecos_v03/render.py` | SVG charts reused by v0.4 |
| `v0.4/app/__init__.py` | Flask `create_app()` factory, blueprint registration, bootstrap admin |
| `v0.4/app/dashboard/routes.py` | Most GET routes + `/all-guides`, `/search`, notes/state endpoints |
| `v0.4/app/runs/routes.py` | Run dispatch, sync dispatch, CSV export, AJAX update_notas |
| `v0.4/app/runs/jobs.py` | Background job pattern (threads + token + polling) for runs and syncs |
| `v0.4/app/import_guides/parser.py` | Excel parser (NFKD-normalized headers, DPI digits, contenido cantidad+producto) |
| `v0.4/app/notion_helpers.py` | Cached Estado novedad options for editor dropdowns (TTL 5 min) |
| `v0.4/app/finanzas/repository.py` | **Phase 5.1** — CRUD finanzas con FK `PRAGMA foreign_keys = ON`, montos en centavos INTEGER, M:N categorías |
| `v0.4/app/finanzas/routes.py` | **Phase 5.1** — `/finanzas`, `/finanzas/new`, `/finanzas/<id>/edit`, `/finanzas/analytics`, `/finanzas/categorias` (admin) |
| `v0.4/app/ai/agent.py` | **Phase 5.2** — Agent loop tool-use con MiniMax M2.7. System prompt anti-alucinación. Parser de `<think>` blocks. Max 5 iteraciones |
| `v0.4/app/ai/tools.py` | **Phase 5.2** — 6 tools registradas: logística, finanzas, búsqueda, top clientes, corridas, manual del aplicativo |
| `v0.4/app/ai/manual.py` | **Phase 5.2** — Knowledge base del aplicativo en 13 tópicos, scoring por keywords. Editar para extender el manual |
| `v0.4/app/ai/routes.py` | **Phase 5.2** — `POST /ai/chat` (rate-limited 30/h), `GET /ai/chat/history`, `POST /ai/chat/clear` |
| `scripts/import_finanzas_notion.py` | **Phase 5.1** — Migración one-shot del histórico financiero de Notion a SQLite. Idempotente via hash determinista |

## Operational notes

- `--apply` updates Notion properties only; the page history body is updated manually.
- Use `--save-raw-html` to save Effi HTML for debugging when the parser breaks (only case in which `v0.2/reports/<ts>/` is created — toda la información operativa vive en SQLite y la app, ya no se generan `.csv/.md/.pdf` automáticos).
- v0.4 supports multiple users; first admin is seeded from `V04_BOOTSTRAP_EMAIL`/`V04_BOOTSTRAP_PASSWORD`. Cualquier usuario logueado puede editar su nombre/email y cambiar su contraseña desde `/mi-cuenta`.
- `apply-update` preserves `.env` and `v0.2/data/` — safe to run.
- After any code change you must FULLY restart `iniciar_v04.bat` (Flask reloads templates but NOT Python modules; `use_reloader=False` is set to avoid the BuildError trap).
- Auto-sync runs after each tracking run finishes; manual sync is available at `/sync/notion` from `/all-guides`.
- All state changes from the operator are atomic: if Notion rejects, nothing is written locally and the failed attempt is logged in `guide_edits` with `sync_ok = 0`.

## Production deploy (live)

URL: `https://app.vaecos.com`.

> ⚠️ **PUENTE TEMPORAL (desde 2026-05-16).** El VPS original de Hostinger se canceló por costo.
> La app corre en **AWS EC2** bajo el free tier (~$200 de crédito / ~6 meses → vence ~mediados de
> noviembre 2026). El equipo debe decidir el destino DEFINITIVO antes de esa fecha; habrá una
> 2da migración. El servidor viejo de Hostinger (`2.24.206.197`) quedó congelado como respaldo
> hasta que su suscripción expire.

| | |
|---|---|
| Servidor | **AWS EC2 `t3.small`** (2 vCPU / 2 GB) — IP elástica `23.22.103.64` — región `us-east-1` — Ubuntu 24.04 LTS |
| SSH user | `ubuntu` (default AWS, sudo NOPASSWD) o `vaecos` (sudo NOPASSWD) — ambos con la llave `~/.ssh/vaecos_vps` |
| App user | `vaecos` (corre el servicio), code at `/opt/vaecos/`, venv at `/opt/vaecos/.venv/` |
| Service | systemd `vaecos.service` running `waitress-serve --listen=127.0.0.1:8765 --threads=4 wsgi:application` |
| Reverse proxy | Caddy with auto TLS (Let's Encrypt) at `/etc/caddy/Caddyfile` |
| Firewall | AWS Security Group: solo `22/80/443` |
| SSH | Key-only — local key at `~/.ssh/vaecos_vps` (PC dueño); en AWS importada como key pair `vaecos-deploy` |
| RAM | 2 GB + **swap 2 GB** (`/swapfile`) — colchón para Chromium del bot Effi |
| DB | `/opt/vaecos/data/vaecos_tracking.db` (WAL) |
| Secrets | `/opt/vaecos/.env` (chmod 600) — `FLASK_SECRET_KEY`, `NOTION_API_KEY`, etc. |
| ProxyFix | Active only when `VAECOS_ENV=production` for correct rate-limiting IPs |
| Backups | `/opt/vaecos/backups/vaecos_<ts>.db.gz` — daily 3am UTC via cron, 14-day retention. Log: `/opt/vaecos/backups/backup.log` |
| DNS | `app.vaecos.com` → A record gestionado en Hostinger (el dominio sigue ahí), apunta a la IP elástica de AWS |

### Deploy a code change

```powershell
# From the dueño's PC (Windows):
git add . ; git commit -m "..." ; git push
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@23.22.103.64 "cd /opt/vaecos && git pull && sudo systemctl restart vaecos"
# If requirements.txt changed, add: && .venv/bin/pip install -r v0.4/requirements.txt
```

### Operate the VPS

```powershell
# SSH in as vaecos (preferred) or ubuntu
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@23.22.103.64

# Inside the VPS:
sudo systemctl status vaecos          # service status
sudo journalctl -u vaecos -f           # live app logs
sudo journalctl -u caddy -n 50         # caddy logs
sudo systemctl restart vaecos          # restart app
```

### Migrate the operator's DB (one-shot)

When the operator hands over her local `vaecos_tracking.db`:
```powershell
scp -i $env:USERPROFILE\.ssh\vaecos_vps "ruta\operadora.db" vaecos@23.22.103.64:/opt/vaecos/data/operator.db
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@23.22.103.64 "sudo systemctl stop vaecos && \
  mv /opt/vaecos/data/vaecos_tracking.db /opt/vaecos/data/vaecos_tracking.db.fresh-bootstrap && \
  mv /opt/vaecos/data/operator.db /opt/vaecos/data/vaecos_tracking.db && \
  cd /opt/vaecos && .venv/bin/python scripts/post_restore.py --skip-bootstrap && \
  sudo systemctl start vaecos"
```

`scripts/post_restore.py` is idempotent and supports `--dry-run`. It applies migrations + Notion sync + telefono backfill on top of the operator's existing data.

### Backups del SQLite

Cron de `vaecos@VPS` corre `/opt/vaecos/scripts/backup_db.sh` a las 3am UTC todos los días:
- Usa `sqlite3 .backup` (online API, WAL-safe — no bloquea writers)
- Comprime con `gzip -9` y rota manteniendo los últimos 14 días
- Output: `/opt/vaecos/backups/vaecos_YYYYMMDD_HHMMSS.db.gz` (~160 KB)
- Log persistente: `/opt/vaecos/backups/backup.log`

Recuperar un backup:
```bash
gunzip -k vaecos_<ts>.db.gz                    # -k mantiene el .gz original
sqlite3 vaecos_<ts>.db 'SELECT COUNT(*) FROM runs;'   # verificar
sudo systemctl stop vaecos
mv /opt/vaecos/data/vaecos_tracking.db /opt/vaecos/data/vaecos_tracking.db.before-restore
mv vaecos_<ts>.db /opt/vaecos/data/vaecos_tracking.db
sudo systemctl start vaecos
```

Backup manual on-demand: `/opt/vaecos/scripts/backup_db.sh`

### Hostinger MCP (solo DNS)

El dominio `vaecos.com` sigue gestionado en Hostinger, así que el Hostinger MCP (`mcp__hostinger__*`)
sirve para el DNS. Los tools de VPS (`VPS_*`) ya **no aplican** — el servidor está en AWS.

- `DNS_getDNSRecordsV1` / `DNS_updateDNSRecordsV1` — gestionar registros DNS (usar siempre `overwrite=false` para no borrar registros existentes)

El registro relevante: `app` (tipo A) → IP elástica de AWS `23.22.103.64`, TTL 300.

### SSH gotcha — first-match-wins

If you change `/etc/ssh/sshd_config.d/99-*.conf` and the change doesn't take effect: SSHD uses **first-match-wins** in alphabetical order. Ubuntu cloud-init drops a `50-cloud-init.conf` that may conflict. Always verify the effective config with:
```
sudo sshd -T | grep -iE 'passwordauth|permitroot|pubkey'
```
