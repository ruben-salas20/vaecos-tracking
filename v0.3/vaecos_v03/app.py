from __future__ import annotations

import argparse
import secrets
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
V02_ROOT = REPO_ROOT / "v0.2"
if str(V02_ROOT) not in sys.path:
    sys.path.insert(0, str(V02_ROOT))

from vaecos_v02.app.config import load_settings as load_v02_settings
from vaecos_v02.app.services.run_tracking import execute_tracking
from vaecos_v02.storage.db import connect as db_connect, init_db, seed_default_rules
from vaecos_v02.storage.repositories import RulesRepository
from vaecos_v03.config import Settings, load_settings
from vaecos_v03.render import alert, button, card_grid, hero, h, layout, mode_badge, panel, p, result_pill, rule_enabled_pill, table
from vaecos_v03.storage import DashboardRepository

# In-memory store for background run jobs: token -> {status, run_id, error}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dashboard web VAECOS v0.3")
    parser.add_argument("--host", help="Host para el servidor web")
    parser.add_argument("--port", type=int, help="Puerto para el servidor web")
    parser.add_argument("--check", action="store_true", help="Valida acceso a SQLite y sale")
    return parser.parse_args()


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    settings = load_settings(base_dir)
    args = parse_args()
    settings = Settings(
        sqlite_db_path=settings.sqlite_db_path,
        host=args.host or settings.host,
        port=args.port or settings.port,
    )
    repo = DashboardRepository(settings.sqlite_db_path)
    _bootstrap_db(settings.sqlite_db_path)

    latest = repo.latest_run()
    if args.check:
        if latest is None:
            print(f"SQLite accesible pero sin corridas: {settings.sqlite_db_path}")
            return 0
        print(f"SQLite OK: {settings.sqlite_db_path}")
        print(f"Ultima corrida: {latest['id']} | {latest['started_at']} | {latest['mode']}")
        return 0

    server = ThreadingHTTPServer((settings.host, settings.port), _make_handler(repo))
    print(f"Aplicacion v0.3 en http://{settings.host}:{settings.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _bootstrap_db(db_path) -> None:
    conn = db_connect(db_path)
    init_db(conn)
    seed_default_rules(conn)
    conn.close()


def _rules_repo(db_path):
    conn = db_connect(db_path)
    init_db(conn)
    return conn, RulesRepository(conn)


def _make_handler(repo: DashboardRepository):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            try:
                if path == "/":
                    return self._send_html(_render_home(repo, query))
                if path == "/attention":
                    return self._send_html(_render_attention(repo))
                if path == "/runs":
                    return self._send_html(_render_runs(repo, query))
                if path == "/run/new":
                    return self._send_html(_render_run_form(query))
                if path.startswith("/run/progress/"):
                    token = path.split("/")[-1]
                    return self._send_html(_render_run_progress(token))
                if path.startswith("/runs/"):
                    run_id = int(path.split("/")[-1])
                    return self._send_html(_render_run_detail(repo, run_id, query))
                if path.startswith("/guides/"):
                    guide = unquote(path.split("/")[-1])
                    return self._send_html(_render_guide_detail(repo, guide))
                if path == "/rules":
                    return self._send_html(_render_rules_list(repo.db_path, query))
                if path == "/rules/new":
                    return self._send_html(_render_rule_form(repo.db_path, None, query))
                if path.startswith("/rules/") and path.endswith("/edit"):
                    rule_id = int(path.split("/")[2])
                    return self._send_html(_render_rule_form(repo.db_path, rule_id, query))
            except ValueError:
                return self._send_text("Ruta invalida", HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                return self._send_text(f"Error interno: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)
            return self._send_text("No encontrado", HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            try:
                if path == "/run/new":
                    return self._handle_run_submit()
                if path == "/rules/new":
                    return self._handle_rule_create(repo.db_path)
                if path.startswith("/rules/") and path.endswith("/edit"):
                    rule_id = int(path.split("/")[2])
                    return self._handle_rule_update(repo.db_path, rule_id)
                if path.startswith("/rules/") and path.endswith("/toggle"):
                    rule_id = int(path.split("/")[2])
                    return self._handle_rule_toggle(repo.db_path, rule_id)
                if path.startswith("/rules/") and path.endswith("/delete"):
                    rule_id = int(path.split("/")[2])
                    return self._handle_rule_delete(repo.db_path, rule_id)
            except Exception as exc:  # noqa: BLE001
                return self._send_text(f"Error interno: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)
            return self._send_text("No encontrado", HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return None

        def _handle_run_submit(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length).decode("utf-8") if length else ""
            form = parse_qs(payload)
            guides_raw = (form.get("guides", [""]) or [""])[0]
            guides = [item.strip() for item in guides_raw.replace("\n", ",").split(",") if item.strip()]
            mode = (form.get("mode", ["dry-run"]) or ["dry-run"])[0]
            save_raw_html = bool(form.get("save_raw_html"))
            all_active = not guides

            token = secrets.token_hex(16)
            with _jobs_lock:
                _jobs[token] = {"status": "running", "run_id": None, "error": None}

            def _run_job() -> None:
                try:
                    settings = load_v02_settings(V02_ROOT)
                    execute_tracking(
                        settings=settings,
                        selected_guides=guides,
                        all_active=all_active,
                        dry_run=(mode != "apply"),
                        output_dir=None,
                        save_raw_html=save_raw_html,
                    )
                    latest = repo.latest_run()
                    run_id = int(latest["id"]) if latest else 0
                    with _jobs_lock:
                        _jobs[token] = {"status": "done", "run_id": run_id, "error": None}
                except Exception as exc:  # noqa: BLE001
                    with _jobs_lock:
                        _jobs[token] = {"status": "error", "run_id": None, "error": str(exc)}

            threading.Thread(target=_run_job, daemon=True).start()
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/run/progress/{token}")
            self.end_headers()

        def _read_form(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length).decode("utf-8") if length else ""
            return parse_qs(payload)

        def _form_val(self, form: dict, key: str, default: str = "") -> str:
            return (form.get(key, [default]) or [default])[0]

        def _handle_rule_create(self, db_path) -> None:
            form = self._read_form()
            conn, rules_repo = _rules_repo(db_path)
            try:
                rules_repo.create(_form_to_rule_data(form))
            finally:
                conn.close()
            self._redirect("/rules?saved=1")

        def _handle_rule_update(self, db_path, rule_id: int) -> None:
            form = self._read_form()
            conn, rules_repo = _rules_repo(db_path)
            try:
                rules_repo.update(rule_id, _form_to_rule_data(form))
            finally:
                conn.close()
            self._redirect("/rules?saved=1")

        def _handle_rule_toggle(self, db_path, rule_id: int) -> None:
            conn, rules_repo = _rules_repo(db_path)
            try:
                rules_repo.toggle(rule_id)
            finally:
                conn.close()
            self._redirect("/rules")

        def _handle_rule_delete(self, db_path, rule_id: int) -> None:
            conn, rules_repo = _rules_repo(db_path)
            try:
                rules_repo.delete(rule_id)
            finally:
                conn.close()
            self._redirect("/rules?deleted=1")

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.end_headers()

        def _send_html(self, html: str) -> None:
            encoded = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_text(self, text: str, status: HTTPStatus) -> None:
            encoded = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _form_to_rule_data(form: dict) -> dict:
    fv = lambda k, d="": (form.get(k, [d]) or [d])[0]  # noqa: E731
    return {
        "priority": fv("priority", "100"),
        "enabled": bool(fv("enabled")),
        "name": fv("name"),
        "match_estado": fv("match_estado"),
        "match_estado_contains": fv("match_estado_contains"),
        "match_novelty_contains": fv("match_novelty_contains"),
        "min_days": fv("min_days"),
        "estado_propuesto": fv("estado_propuesto"),
        "motivo": fv("motivo"),
        "requiere_accion": fv("requiere_accion"),
        "review_needed": bool(fv("review_needed")),
        "updated_by": "operadora",
    }


def _render_rules_list(db_path, query: dict[str, list[str]]) -> str:
    conn, rules_repo = _rules_repo(db_path)
    try:
        rules = rules_repo.list_all()
    finally:
        conn.close()

    body = hero(
        "Reglas de decision",
        "Determinan como se interpreta el estado de Effi para cada guia. Se evaluan en orden de prioridad.",
        button("/rules/new", "Nueva regla") + button("/", "Volver al resumen", "ghost"),
    )
    body += alert(
        "Las reglas se evaluan en orden de prioridad ascendente. La primera que coincide determina el resultado.",
        "info",
    )
    if _q(query, "saved"):
        body += alert("Regla guardada correctamente.", "ok")
    if _q(query, "deleted"):
        body += alert("Regla eliminada.", "ok")

    body += table(
        ["Prio", "Estado", "Nombre", "Estado Effi (exacto)", "Estado Effi (contiene)", "Novedad (contiene)", "Dias min.", "Estado propuesto", "Acciones"],
        [
            [
                str(rule["priority"]),
                rule_enabled_pill(bool(rule["enabled"])),
                _e(rule["name"]),
                _e(rule["match_estado"] or ""),
                _e(rule["match_estado_contains"] or ""),
                _e(rule["match_novelty_contains"] or ""),
                str(rule["min_days"]) if rule["min_days"] is not None else "",
                _e(rule["estado_propuesto"] or "(revision manual)"),
                (
                    f'<a class="button ghost" style="padding:4px 10px;font-size:.78rem" href="/rules/{rule["id"]}/edit">Editar</a>'
                    f'<form method="post" action="/rules/{rule["id"]}/toggle" style="display:inline">'
                    f'<button style="padding:4px 10px;font-size:.78rem;background:{"#16a34a" if not rule["enabled"] else "#64748b"}">'
                    f'{"Activar" if not rule["enabled"] else "Desactivar"}</button></form>'
                    f'<form method="post" action="/rules/{rule["id"]}/delete" style="display:inline" '
                    f'onsubmit="return confirm(\'Eliminar esta regla?\');">'
                    f'<button style="padding:4px 10px;font-size:.78rem;background:#dc2626">Eliminar</button></form>'
                ),
            ]
            for rule in rules
        ],
    )
    return layout("Reglas de decision", body)


def _render_rule_form(db_path, rule_id: int | None, query: dict[str, list[str]]) -> str:
    conn, rules_repo = _rules_repo(db_path)
    try:
        rule = rules_repo.get(rule_id) if rule_id is not None else None
    finally:
        conn.close()

    is_edit = rule is not None
    title = f"Editar regla #{rule_id}" if is_edit else "Nueva regla"

    def val(field: str, default: str = "") -> str:
        if rule and rule.get(field) is not None:
            return _e(str(rule[field]))
        return _e(default)

    checked_enabled = 'checked' if (rule is None or rule.get("enabled", 1)) else ''
    checked_review = 'checked' if rule and rule.get("review_needed") else ''

    action = f"/rules/{rule_id}/edit" if is_edit else "/rules/new"
    body = hero(
        title,
        "Configura las condiciones y la accion de esta regla. Los campos de coincidencia usan texto normalizado (minusculas).",
        button("/rules", "Volver a reglas", "ghost"),
    )
    body += alert(
        "Tip: usa solo los campos de coincidencia que necesites. Los campos vacios se ignoran. "
        "El campo 'Dias min.' activa la regla solo si el estado lleva al menos esos dias sin cambio.",
        "info",
    )
    body += panel(f"""
        <form class="stack" method="post" action="{action}">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
            <label>Prioridad (menor = primero)
              <input type="number" name="priority" value="{val('priority', '100')}" min="1" max="9999" required>
            </label>
            <label>Nombre descriptivo
              <input type="text" name="name" value="{val('name')}" required>
            </label>
          </div>
          <label style="flex-direction:row;align-items:center;gap:10px;font-weight:600">
            <input type="checkbox" name="enabled" value="1" {checked_enabled}> Habilitada
          </label>
          <div class="sep"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px">
            <label>Estado Effi exacto
              <input type="text" name="match_estado" value="{val('match_estado')}" placeholder="ej: entregado">
            </label>
            <label>Estado Effi contiene
              <input type="text" name="match_estado_contains" value="{val('match_estado_contains')}" placeholder="ej: devoluci">
            </label>
            <label>Novedad contiene
              <input type="text" name="match_novelty_contains" value="{val('match_novelty_contains')}" placeholder="ej: nadie en casa">
            </label>
          </div>
          <label style="max-width:200px">Dias minimos sin cambio
            <input type="number" name="min_days" value="{val('min_days')}" min="1" placeholder="dejar vacio para ignorar">
          </label>
          <div class="sep"></div>
          <label>Estado propuesto en Notion (dejar vacio = revision manual)
            <input type="text" name="estado_propuesto" value="{val('estado_propuesto')}" placeholder="ej: ENTREGADA">
          </label>
          <label>Motivo (usa {{days}} para insertar los dias calculados)
            <input type="text" name="motivo" value="{val('motivo')}" required placeholder="ej: Effi reporta entrega exitosa.">
          </label>
          <label>Accion requerida
            <input type="text" name="requiere_accion" value="{val('requiere_accion')}" required placeholder="ej: Sin accion">
          </label>
          <label style="flex-direction:row;align-items:center;gap:10px;font-weight:600">
            <input type="checkbox" name="review_needed" value="1" {checked_review}> Marcar como revision manual
          </label>
          <div class="toolbar">
            <button type="submit">Guardar regla</button>
            <a class="button ghost" href="/rules">Cancelar</a>
          </div>
        </form>
    """)
    return layout(title, body)


def _render_home(repo: DashboardRepository, query: dict[str, list[str]]) -> str:
    latest = repo.latest_run()
    actions = (
        button("/attention", "Ver que requiere atencion")
        + button("/run/new", "Nueva corrida", "ghost")
        + button("/runs", "Historial", "ghost")
    )
    if latest is None:
        body = hero("Centro operativo", "No hay corridas registradas en SQLite.", actions)
        return layout("Centro operativo", body)

    run_id = int(latest["id"])
    counts_rows = repo.result_counts(run_id)
    count_map = {str(row["resultado"]): int(row["total"]) for row in counts_rows}
    needs_attention = sum(v for k, v in count_map.items() if k != "unchanged")
    unchanged = count_map.get("unchanged", 0)
    duration = repo.run_duration_seconds(run_id)
    duration_text = _format_duration(duration) if duration else ""
    subtitle = f"Corrida #{latest['id']} · {_fmt_ts(str(latest['started_at']))}" + (f" · {duration_text}" if duration_text else "")

    body = hero("Centro operativo", subtitle, actions)

    if _q(query, "created"):
        body += alert("Corrida ejecutada correctamente.", "ok")

    if needs_attention > 0:
        body += alert(
            f"{needs_attention} guia(s) requieren atencion en la ultima corrida. "
            "Haz clic en 'Ver que requiere atencion' para revisarlas."
        )
    else:
        body += alert("Sin guias que requieran atencion en la ultima corrida.", "ok")

    attention_variant = "danger" if needs_attention > 0 else "ok"
    body += card_grid(
        [
            ("Ultima corrida", f"#{latest['id']}", "info"),
            ("Procesadas", str(latest["total_processed"]), ""),
            ("Requieren atencion", str(needs_attention), attention_variant),
            ("Sin cambios", str(unchanged), "ok" if unchanged > 0 else ""),
        ]
    )

    top_guides = repo.top_guides_with_changes(limit=10)
    if top_guides:
        body += h("Guias con mas cambios historicos")
        body += table(
            ["Guia", "Cambios acumulados"],
            [
                [
                    f'<a href="/guides/{_u(row["guia"])}">{_e(row["guia"])}</a>',
                    str(row["total_cambios"]),
                ]
                for row in top_guides
            ],
        )
    return layout("Centro operativo", body)


def _render_runs(repo: DashboardRepository, query: dict[str, list[str]]) -> str:
    rows = repo.list_runs(limit=100)
    mode_filter = (_q(query, "mode") or "").strip()
    if mode_filter:
        rows = [row for row in rows if str(row["mode"]) == mode_filter]

    body = hero(
        "Corridas",
        "Historial completo de ejecuciones almacenadas en SQLite.",
        button("/run/new", "Nueva corrida") + button("/", "Volver al resumen", "ghost"),
    )
    body += panel(
        '<form class="filters" method="get">'
        '<label>Modo<select name="mode"><option value="">Todos</option><option value="dry-run">dry-run</option><option value="apply">apply</option></select></label>'
        '<button type="submit">Filtrar</button>'
        f'{button("/runs", "Limpiar", "ghost")}'
        '</form>'
    ).replace(f'<option value="{mode_filter}">', f'<option value="{mode_filter}" selected>')
    body += table(
        ["Run ID", "Inicio", "Fin", "Modo", "Procesadas", "Cambios", "Sin cambios", "Manual", "Errores"],
        [
            [
                f'<a href="/runs/{row["id"]}"><strong>#{row["id"]}</strong></a>',
                _fmt_ts(str(row["started_at"])),
                _fmt_ts(str(row["finished_at"])) if row["finished_at"] else '<span class="muted">—</span>',
                mode_badge(str(row["mode"])),
                str(row["total_processed"]),
                str(row["total_changed"]),
                str(row["total_unchanged"]),
                str(row["total_manual_review"]),
                str(row["total_error"]),
            ]
            for row in rows
        ],
    )
    return layout("Corridas", body)


def _render_run_form(query: dict[str, list[str]]) -> str:
    body = hero(
        "Nueva corrida",
        "Ejecuta una corrida desde la web usando la logica operativa de v0.2.",
        button("/runs", "Ver corridas", "ghost"),
    )
    body += alert("Usa apply solo cuando ya validaste el comportamiento. La aplicacion escribira en Notion.")
    body += panel(
        """
        <form class="stack" method="post">
          <label>Modo
            <select name="mode">
              <option value="dry-run">dry-run</option>
              <option value="apply">apply</option>
            </select>
          </label>
          <label>Guias especificas
            <textarea name="guides" placeholder="Deja vacio para todas las activas. Tambien puedes separar por coma."></textarea>
          </label>
          <label><span class="muted">Opcional</span>
            <span><input type="checkbox" name="save_raw_html"> Guardar HTML crudo de Effi</span>
          </label>
          <div class="toolbar">
            <button type="submit">Ejecutar corrida</button>
            <a class="button ghost" href="/">Cancelar</a>
          </div>
        </form>
        """
    )
    return layout("Nueva corrida", body)


def _render_run_detail(repo: DashboardRepository, run_id: int, query: dict[str, list[str]]) -> str:
    run = repo.get_run(run_id)
    if run is None:
        return layout("Corrida no encontrada", hero("Corrida no encontrada", f"No existe la corrida {run_id}.") + panel(button("/runs", "Volver", "ghost")))

    rows = repo.get_run_results(run_id)
    result_filter = (_q(query, "resultado") or "").strip()
    if result_filter:
        rows = [row for row in rows if str(row["resultado"]) == result_filter]

    duration = repo.run_duration_seconds(run_id)
    duration_text = _format_duration(duration) if duration else ""
    subtitle = (
        f"{_fmt_ts(str(run['started_at']))} · {mode_badge(str(run['mode']))} · "
        f"{run['total_processed']} guias procesadas"
        + (f" · {duration_text}" if duration_text else "")
    )
    body = hero(
        f"Corrida #{run_id}",
        "",
        button("/run/new", "Nueva corrida") + button("/runs", "Volver a corridas", "ghost"),
    )
    # Insert subtitle with raw HTML (mode_badge is HTML)
    body = body.replace('<p></p>', f'<p class="muted">{subtitle}</p>')
    if _q(query, "created"):
        body += alert("Corrida creada correctamente.", "ok")
    body += panel(
        '<form class="filters" method="get">'
        '<label>Resultado'
        '<select name="resultado">'
        '<option value="">Todos</option>'
        '<option value="changed">changed</option>'
        '<option value="unchanged">unchanged</option>'
        '<option value="manual_review">manual_review</option>'
        '<option value="parse_error">parse_error</option>'
        '<option value="error">error</option>'
        '</select></label>'
        '<button type="submit">Filtrar</button>'
        f'{button(f"/runs/{run_id}", "Limpiar", "ghost")}'
        '</form>'
    ).replace(f'<option value="{result_filter}">', f'<option value="{result_filter}" selected>')
    body += table(
        ["Guia", "Cliente", "Resultado", "Accion requerida", "Notion", "Effi", "Propuesto", "Motivo", "Error"],
        [
            [
                f'<a href="/guides/{_u(row["guia"])}">{_e(row["guia"])}</a>',
                _e(row["cliente"]),
                result_pill(str(row["resultado"])),
                _e(row["requiere_accion"] or ""),
                _e(row["estado_notion_actual"] or "N/D"),
                _e(row["estado_effi_actual"] or "N/D"),
                _e(row["estado_propuesto"] or "N/D"),
                _e_trunc(row["motivo"]),
                _e_trunc(row["error"] or ""),
            ]
            for row in rows
        ],
    )
    return layout(f"Corrida #{run_id}", body)


def _render_guide_detail(repo: DashboardRepository, guide: str) -> str:
    rows = repo.guide_history(guide, limit=30)
    body = hero(
        f"Historial de {guide}",
        "Seguimiento historico de una guia a traves de las corridas almacenadas.",
        button("/runs", "Ver corridas", "ghost") + button("/run/new", "Nueva corrida"),
    )
    if not rows:
        body += panel(p(f"No hay historial para la guia {guide}."))
        return layout("Guia no encontrada", body)
    body += card_grid([
        ("Cliente", str(rows[0]["cliente"])),
        ("Ultimo resultado", str(rows[0]["resultado"])),
        ("Ultimo estado propuesto", str(rows[0]["estado_propuesto"] or "N/D")),
        ("Ultima corrida", f"#{rows[0]['run_id']}"),
    ])
    body += table(
        ["Corrida", "Inicio", "Modo", "Resultado", "Notion", "Effi", "Propuesto", "Motivo", "Error"],
        [
            [
                f'<a href="/runs/{row["run_id"]}">#{row["run_id"]}</a>',
                _fmt_ts(str(row["started_at"])),
                mode_badge(str(row["mode"])),
                result_pill(str(row["resultado"])),
                _e(row["estado_notion_actual"] or "N/D"),
                _e(row["estado_effi_actual"] or "N/D"),
                _e(row["estado_propuesto"] or "N/D"),
                _e_trunc(row["motivo"]),
                _e_trunc(row["error"] or ""),
            ]
            for row in rows
        ],
    )
    return layout(f"Historial — {guide}", body)


def _render_attention(repo: DashboardRepository) -> str:
    latest = repo.latest_run()
    actions = button("/run/new", "Nueva corrida") + button("/runs", "Ver corridas", "ghost")

    if latest is None:
        body = hero("Requiere atencion", "No hay corridas registradas en SQLite.", actions)
        return layout("Requiere atencion", body)

    run_id = int(latest["id"])
    rows = repo.get_results_requiring_attention(run_id)
    duration = repo.run_duration_seconds(run_id)
    duration_text = _format_duration(duration) if duration else ""
    subtitle = (
        f"Corrida #{latest['id']} · {_fmt_ts(str(latest['started_at']))}"
        + (f" · {duration_text}" if duration_text else "")
        + f" · {latest['total_processed']} guias procesadas"
    )

    body = hero("Requiere atencion", subtitle, actions)

    if not rows:
        body += alert("Sin guias que requieran atencion en la ultima corrida. Todo en orden.", "ok")
        return layout("Requiere atencion", body)

    _section_labels = {
        "changed": "Cambios detectados",
        "manual_review": "Revision manual",
        "parse_error": "Errores de parsing HTML",
        "error": "Errores tecnicos",
    }
    by_result: dict[str, list] = {}
    for row in rows:
        by_result.setdefault(str(row["resultado"]), []).append(row)

    for resultado in ("changed", "manual_review", "parse_error", "error"):
        group = by_result.get(resultado, [])
        if not group:
            continue
        body += h(f"{_section_labels[resultado]} ({len(group)})")
        body += table(
            ["Guia", "Cliente", "Resultado", "Accion requerida", "Estado Effi", "Propuesto", "Motivo"],
            [
                [
                    f'<a href="/guides/{_u(row["guia"])}">{_e(row["guia"])}</a>',
                    _e(row["cliente"]),
                    result_pill(str(row["resultado"])),
                    _e(row["requiere_accion"] or ""),
                    _e(row["estado_effi_actual"] or "N/D"),
                    _e(row["estado_propuesto"] or "N/D"),
                    _e_trunc(row["motivo"]),
                ]
                for row in group
            ],
        )

    return layout("Requiere atencion", body)


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def _render_run_progress(token: str) -> str:
    with _jobs_lock:
        job = dict(_jobs.get(token, {}))

    if not job:
        body = hero(
            "Corrida no encontrada",
            "El token no existe o ya expiro.",
            button("/runs", "Ver corridas", "ghost"),
        )
        return layout("No encontrado", body)

    status = job.get("status", "running")

    if status == "running":
        # JS auto-refresh every 3 seconds so the page stays inside the app layout.
        refresh_script = "<script>setTimeout(function(){location.reload()},3000)</script>"
        body = (
            hero(
                "Corrida en progreso",
                "Se estan consultando las guias en paralelo. Esta pagina se actualiza automaticamente cada 3 segundos.",
                button("/runs", "Ver corridas en otro momento", "ghost"),
            )
            + alert("La corrida esta ejecutandose en segundo plano. Por favor espera.")
            + refresh_script
        )
        return layout("Corrida en progreso", body)

    if status == "done":
        run_id = job.get("run_id", 0)
        redirect_script = f'<script>location.href="/runs/{run_id}?created=1"</script>'
        return layout("Corrida completada", redirect_script)

    # status == "error"
    error_msg = job.get("error") or "Error desconocido."
    body = hero(
        "Error en la corrida",
        "Ocurrio un error al ejecutar la corrida.",
        button("/run/new", "Intentar de nuevo") + button("/runs", "Ver corridas", "ghost"),
    ) + alert(f"Detalle: {_e(error_msg)}")
    return layout("Error en corrida", body)


def _q(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _e(value: object) -> str:
    from html import escape
    return escape(str(value))


def _u(value: object) -> str:
    return quote(str(value), safe="")


def _fmt_ts(ts: str | None) -> str:
    """Format ISO timestamp to a readable short form: '17 abr 2026, 16:12'."""
    if not ts:
        return ""
    ts = str(ts).replace("T", " ")
    try:
        date_part, time_part = ts[:10], ts[11:16]
        year, month, day = date_part.split("-")
        months = ["", "ene", "feb", "mar", "abr", "may", "jun",
                  "jul", "ago", "sep", "oct", "nov", "dic"]
        return f"{int(day)} {months[int(month)]} {year}, {time_part}"
    except Exception:  # noqa: BLE001
        return ts[:16]


def _e_trunc(value: object, max_len: int = 90) -> str:
    """Escape and truncate long text; show full text on hover via title attribute."""
    from html import escape
    s = str(value)
    if not s or s == "None":
        return ""
    if len(s) <= max_len:
        return escape(s)
    return f'<span class="cell-trunc" title="{escape(s)}">{escape(s[:max_len])}\u2026</span>'
