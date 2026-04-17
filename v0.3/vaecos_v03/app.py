from __future__ import annotations

import argparse
import sys
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
from vaecos_v03.config import Settings, load_settings
from vaecos_v03.render import alert, button, card_grid, hero, h, layout, panel, p, table
from vaecos_v03.storage import DashboardRepository


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


def _make_handler(repo: DashboardRepository):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            try:
                if path == "/":
                    return self._send_html(_render_home(repo, query))
                if path == "/runs":
                    return self._send_html(_render_runs(repo, query))
                if path == "/run/new":
                    return self._send_html(_render_run_form(query))
                if path.startswith("/runs/"):
                    run_id = int(path.split("/")[-1])
                    return self._send_html(_render_run_detail(repo, run_id, query))
                if path.startswith("/guides/"):
                    guide = unquote(path.split("/")[-1])
                    return self._send_html(_render_guide_detail(repo, guide))
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

            settings = load_v02_settings(V02_ROOT)
            _, _, _ = execute_tracking(
                settings=settings,
                selected_guides=guides,
                all_active=all_active,
                dry_run=(mode != "apply"),
                output_dir=None,
                save_raw_html=save_raw_html,
            )
            latest = repo.latest_run()
            run_id = int(latest["id"]) if latest else 0
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/runs/{run_id}?created=1")
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


def _render_home(repo: DashboardRepository, query: dict[str, list[str]]) -> str:
    latest = repo.latest_run()
    actions = button("/run/new", "Nueva corrida") + button("/runs", "Ver corridas", "ghost")
    body = hero(
        "Centro operativo",
        "Aplicacion web local para ejecutar seguimientos, revisar resultados y navegar historico desde SQLite.",
        actions,
    )
    if _q(query, "created"):
        body += alert("Corrida ejecutada correctamente desde la aplicacion.", "ok")
    if latest is None:
        body += panel(p("No hay corridas registradas en SQLite."))
        return layout("Centro operativo", body)

    counts = repo.result_counts(int(latest["id"]))
    statuses = repo.proposed_status_counts(int(latest["id"]))
    top_guides = repo.top_guides_with_changes(limit=10)
    body += card_grid(
        [
            ("Ultima corrida", str(latest["id"])),
            ("Inicio", str(latest["started_at"])),
            ("Modo", str(latest["mode"])),
            ("Procesadas", str(latest["total_processed"])),
        ]
    )

    quick = panel(
        '<form class="filters" method="get" action="/guides/">'
        '<label>Buscar guia<input type="text" name="guide" placeholder="B263378877-1"></label>'
        '<button type="submit">Abrir historial</button>'
        '</form>'
    )
    body += quick.replace('action="/guides/"', 'onsubmit="event.preventDefault();window.location=\'/guides/\'+encodeURIComponent(this.guide.value);"')

    body += '<div class="grid-two">'
    body += panel(h("Resultados de la ultima corrida") + table(["Resultado", "Total"], [[_e(row["resultado"]), str(row["total"])] for row in counts]))
    body += panel(h("Estados propuestos") + table(["Estado propuesto", "Total"], [[_e(row["estado_propuesto"]), str(row["total"])] for row in statuses]))
    body += '</div>'
    body += h("Guias con mas cambios historicos")
    body += table(
        ["Guia", "Cambios acumulados"],
        [[f'<a href="/guides/{_u(row["guia"])}">{_e(row["guia"])}</a>', str(row["total_cambios"])] for row in top_guides],
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
                f'<a href="/runs/{row["id"]}">{row["id"]}</a>',
                _e(row["started_at"]),
                _e(row["finished_at"] or ""),
                _e(row["mode"]),
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

    body = hero(
        f"Corrida {run_id}",
        f"Inicio {run['started_at']} | modo {run['mode']} | procesadas {run['total_processed']}",
        button("/run/new", "Nueva corrida") + button("/runs", "Volver a corridas", "ghost"),
    )
    if _q(query, "created"):
        body += alert("Corrida creada correctamente.", "ok")
    body += panel(
        '<form class="filters" method="get">'
        '<label>Resultado<select name="resultado"><option value="">Todos</option><option value="changed">changed</option><option value="unchanged">unchanged</option><option value="manual_review">manual_review</option><option value="error">error</option></select></label>'
        '<button type="submit">Filtrar</button>'
        f'{button(f"/runs/{run_id}", "Limpiar", "ghost")}'
        '</form>'
    ).replace(f'<option value="{result_filter}">', f'<option value="{result_filter}" selected>')
    body += table(
        ["Guia", "Cliente", "Resultado", "Notion", "Effi", "Propuesto", "Actualizacion", "Motivo", "Error"],
        [
            [
                f'<a href="/guides/{_u(row["guia"])}">{_e(row["guia"])}</a>',
                _e(row["cliente"]),
                f'<span class="pill">{_e(row["resultado"])}</span>',
                _e(row["estado_notion_actual"] or "N/D"),
                _e(row["estado_effi_actual"] or "N/D"),
                _e(row["estado_propuesto"] or "N/D"),
                _e(row["actualizacion_notion"] or ""),
                _e(row["motivo"]),
                _e(row["error"] or ""),
            ]
            for row in rows
        ],
    )
    return layout(f"Corrida {run_id}", body)


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
        ("Cliente mas reciente", str(rows[0]["cliente"])),
        ("Ultimo resultado", str(rows[0]["resultado"])),
        ("Ultimo estado propuesto", str(rows[0]["estado_propuesto"] or "N/D")),
        ("Ultimo modo", str(rows[0]["mode"])),
    ])
    body += table(
        ["Run ID", "Inicio", "Modo", "Resultado", "Notion", "Effi", "Propuesto", "Actualizacion", "Motivo", "Error"],
        [
            [
                f'<a href="/runs/{row["run_id"]}">{row["run_id"]}</a>',
                _e(row["started_at"]),
                _e(row["mode"]),
                f'<span class="pill">{_e(row["resultado"])}</span>',
                _e(row["estado_notion_actual"] or "N/D"),
                _e(row["estado_effi_actual"] or "N/D"),
                _e(row["estado_propuesto"] or "N/D"),
                _e(row["actualizacion_notion"] or ""),
                _e(row["motivo"]),
                _e(row["error"] or ""),
            ]
            for row in rows
        ],
    )
    return layout(f"Historial de {guide}", body)


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
