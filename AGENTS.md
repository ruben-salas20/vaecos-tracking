# AGENTS.md

## Scope
- `v0.2/` is the primary operational codebase in the repo.
- `v0.3/` is the active dashboard/web phase built on top of `v0.2` SQLite data.
- `v0.1` no longer exists as runnable root code; it survives only in `backups/`.
- Prefer working in `v0.2/` for tracking logic and in `v0.3/` for dashboard/web work unless the user explicitly asks to inspect old backups.

## Runtime facts
- Python only. No third-party `pip` dependencies are required for either version.
- Commands are written for Windows PowerShell.
- Both versions read `.env`; `v0.2` first loads `v0.2/.env` and then falls back to the repo-root `.env`.

## `v0.2` commands
- Entry point wrapper: `python v0.2/cli.py`
- Default behavior: `run` is implied if no subcommand is given.
- Real modes:
  - default: process all active guides if `--guides` is omitted
  - targeted: process only guides passed to `--guides`
- Main run commands:
  - `python v0.2/cli.py --dry-run`
  - `python v0.2/cli.py --apply`
  - `python v0.2/cli.py --guides B263378877-1 --dry-run`
  - `python v0.2/cli.py run --all-active --dry-run`
- History / analytics:
  - `python v0.2/cli.py runs`
  - `python v0.2/cli.py run-details --run-id 7`
  - `python v0.2/cli.py compare-runs --run-id 7`
  - `python v0.2/cli.py stats`
  - `python v0.2/cli.py guide-history --guide B263378877-1`
- Update workflow:
  - `python v0.2/cli.py check-update`
  - `python v0.2/cli.py download-update`
  - `python v0.2/cli.py apply-update`
- TUI:
  - `python v0.2/cli.py tui`

## `v0.2` layout
- `v0.2/cli.py`: thin wrapper.
- `v0.2/vaecos_v02/app/cli.py`: command parsing, TUI, command dispatch.
- `v0.2/vaecos_v02/app/services/run_tracking.py`: main execution flow plus SQLite-backed history/analytics helpers.
- `v0.2/vaecos_v02/app/services/update_service.py`: GitHub release check/download/apply flow.
- `v0.2/vaecos_v02/core/rules.py`: data-driven rules engine plus `DEFAULT_RULES` seed.
- `v0.2/vaecos_v02/providers/carrier.py`: carrier protocol and shared config.
- `v0.2/vaecos_v02/providers/carriers/`: carrier registry and implementations. `effi` is real, `guatex` is still a stub.
- `v0.2/vaecos_v02/providers/notion_provider.py`: Notion read/write integration, including `Transportista` mapping.
- `v0.2/vaecos_v02/storage/db.py`, `storage/repositories.py`, and `storage/rules_repository.py`: SQLite schema, run queries, rules CRUD, and audit trail.

## `v0.3` layout
- `v0.3/server.py`: dashboard entrypoint.
- `v0.3/vaecos_v03/app.py`: local HTTP server, background run execution, progress pages, analytics, and rules routes.
- `v0.3/vaecos_v03/storage.py`: dashboard and analytics SQLite queries.
- `v0.3/vaecos_v03/render.py`: HTML rendering helpers, charts, branding, and badges.
- `v0.3/vaecos_v03/rules_ui.py`: forms, preview, history, and POST handlers for editable rules.
- `v0.3` reads `v0.2` SQLite and can trigger runs through `v0.2` services.

## Environment variables that matter
- Shared:
  - `NOTION_API_KEY`
  - `NOTION_DATA_SOURCE_ID`
  - `NOTION_VERSION`
  - `NOTION_QUERY_KIND`
  - `EFFI_TIMEOUT_SECONDS`
- `v0.2` overrides:
  - `V02_REPORTS_DIR` defaults to `v0.2/reports`
  - `V02_SAVE_RAW_HTML`
  - `V02_SQLITE_DB_PATH` defaults to `v0.2/data/vaecos_tracking.db`
- `v0.3` overrides:
  - `V03_SQLITE_DB_PATH` defaults to `v0.2/data/vaecos_tracking.db`
  - `V03_HOST` defaults to `127.0.0.1`
  - `V03_PORT` defaults to `8765`

## Verification
- Syntax check:
  - `python -m compileall .`
  - `python -m compileall "v0.2"`
- `v0.2` tests:
  - `python -m unittest discover -s "v0.2/tests" -v`
- `v0.3` smoke check:
  - `python v0.3/server.py --check`
- Tests use `unittest`, not `pytest`.

## Behavior constraints
- `--apply` writes real changes to Notion by updating properties only; the page body/history is intentionally still manual.
- Default operational flow is:
  - run dry-run first
  - inspect generated `summary.md`
  - then run `--apply` if the proposed changes look correct
- Effi fetching is parallel (up to 8 concurrent requests via `ThreadPoolExecutor`).
- If Effi returns HTTP 200 but `estado_actual` cannot be extracted, the result is `parse_error` (not `manual_review`). This signals a likely HTML structure change.
- Effi parsing is HTML-structure-dependent. If parsing breaks, rerun with raw HTML saving enabled before changing rules:
  - v0.2: `python v0.2/cli.py --dry-run --save-raw-html`

## apply-update behavior
- Searches `v0.2/updates/` for the newest `.zip` by modification time.
- Backs up current `v0.2` code and the active web layer before replacing anything.
- Replaces `v0.2` code, `v0.3/`, and root helper files when present in the zip.
- Never touches: `.env`, `v0.2/data/` (SQLite), `v0.2/reports/`.
- Detects the zip layout by searching for `vaecos_v02/` inside the extracted content and then updates sibling app files from the same package root.

## v0.3 run execution
- POST to `/run/new` now starts a background thread immediately and redirects to `/run/progress/<token>`.
- The progress page auto-refreshes every 3 seconds using JS until the run completes or errors.
- The server is never blocked during a run.

## Reporting / storage gotchas
- `v0.2` reports should write into `v0.2/reports/` by default; SQLite history should live in `v0.2/data/vaecos_tracking.db`.
- `v0.2` analytics commands read SQLite history, not report files.
- Exported reports should include `carrier` context now that runs can mix transportistas.

## When editing
- `v0.2` is the default target for all current functionality.
- Keep dashboard changes in `v0.3`; do not duplicate analytics queries across root files.
- Treat `backups/` as archive-only unless the user explicitly asks to inspect or restore something.
- Changes to rule behavior should be covered by updating or adding `v0.2/tests/test_rules.py`.
- Changes to Effi parsing should be covered by updating or adding `v0.2/tests/test_effi_provider.py`.
