from __future__ import annotations
import re
import sys
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, current_app, session, jsonify, abort, flash
from ..auth.decorators import admin_required, login_required
from ..charts import line_chart, stacked_bar_chart
from ..utils import fmt_duration_seconds, format_date_short

# Inject v0.3 into path so DashboardRepository is importable
_V03_ROOT = Path(__file__).resolve().parents[3] / "v0.3"
if str(_V03_ROOT) not in sys.path:
    sys.path.insert(0, str(_V03_ROOT))

from vaecos_v03.storage import DashboardRepository
from ..notion_helpers import get_estado_novedad_options

dashboard_bp = Blueprint("dashboard", __name__)


def _repo() -> DashboardRepository:
    return DashboardRepository(current_app.config["DB_PATH"])


@dashboard_bp.route("/")
@login_required
def home():
    repo = _repo()
    latest = repo.latest_run()
    if latest is None:
        return render_template("dashboard/home.html",
                               latest=None,
                               count_map={},
                               needs_attention=0,
                               trend_svg="",
                               created=False)

    run_id = int(latest["id"])
    counts_rows = repo.result_counts(run_id)
    count_map = {str(row["resultado"]): int(row["total"]) for row in counts_rows}
    needs_attention = sum(v for k, v in count_map.items() if k != "unchanged")
    trend_rows = repo.attention_trend(days=30)
    trend_points = [(str(row["day"]), int(row["total"])) for row in trend_rows]
    trend_svg = line_chart("Atencion (30 dias)", trend_points, color="#dc2626")
    created = bool(request.args.get("created"))

    return render_template(
        "dashboard/home.html",
        latest=latest,
        count_map=count_map,
        needs_attention=needs_attention,
        trend_svg=trend_svg,
        created=created,
    )


@dashboard_bp.route("/attention")
@login_required
def attention():
    repo = _repo()
    latest = repo.latest_run()
    if latest is None:
        return render_template("dashboard/attention.html", latest=None, rows={}, duration_text="")

    run_id = int(latest["id"])
    rows = repo.get_results_requiring_attention(run_id)
    duration = repo.run_duration_seconds(run_id)
    duration_text = fmt_duration_seconds(duration) if duration else ""

    _section_labels = {
        "changed": "Cambios detectados",
        "manual_review": "Revision manual",
        "parse_error": "Errores de parsing HTML",
        "error": "Errores tecnicos",
    }
    by_result: dict[str, list] = {}
    for row in rows:
        by_result.setdefault(str(row["resultado"]), []).append(row)

    return render_template(
        "dashboard/attention.html",
        latest=latest,
        by_result=by_result,
        section_labels=_section_labels,
        duration_text=duration_text,
    )


@dashboard_bp.route("/analytics")
@login_required
def analytics():
    from datetime import date as _date, timedelta as _td

    repo = _repo()

    # ── Filtros: presets (?days=N) o rango custom (?from=YYYY-MM-DD&to=YYYY-MM-DD) ──
    from_str = (request.args.get("from") or "").strip()
    to_str = (request.args.get("to") or "").strip()
    range_mode = "preset"
    days = 30
    if from_str and to_str:
        try:
            _date.fromisoformat(from_str)
            _date.fromisoformat(to_str)
            range_mode = "custom"
            # Calcular `days` aproximado para queries que lo requieren
            days = max(1, (_date.fromisoformat(to_str) - _date.fromisoformat(from_str)).days + 1)
        except ValueError:
            from_str = to_str = ""

    if range_mode == "preset":
        try:
            days = max(7, min(int(request.args.get("days") or "30"), 365))
        except ValueError:
            days = 30
        # Default presets para mostrar en UI
        from_str = (_date.today() - _td(days=days - 1)).isoformat()
        to_str = _date.today().isoformat()

    # Umbral configurable para backlog
    try:
        backlog_threshold = max(1, min(int(request.args.get("backlog_days") or "14"), 90))
    except ValueError:
        backlog_threshold = 14

    # ── KPIs operativos ────────────────────────────────────────────
    por_recoger = repo.latest_por_recoger_total()
    breakdown = repo.por_recoger_delivery_breakdown()
    resolution = repo.resolution_rate()
    cycle = repo.avg_cycle_time_days()
    backlog_count = repo.backlog_old_count(min_days=backlog_threshold)
    backlog_top = repo.backlog_old_list(min_days=backlog_threshold, limit=10)
    clients_open = repo.clients_with_open_cases(limit=10)

    # ── Gráfico de atención ────────────────────────────────────────
    trend_rows = repo.attention_trend(days=days)
    trend_points = [(str(row["day"]), int(row["total"])) for row in trend_rows]
    trend_svg = line_chart(
        f"Guías que requirieron atención por día ({days} días)",
        trend_points, color="#dc2626",
    )

    # ── Performance / Sistema (gráfico stacked + rates) ────────────
    kpi = repo.kpi_summary(days=days)
    summary_rows = repo.runs_summary_by_day(days=days)
    days_axis = [str(row["day"]) for row in summary_rows]
    series = [
        ("Sin cambios",    [int(r["unchanged"] or 0) for r in summary_rows],    "#cbd5e1"),
        ("Cambios",        [int(r["changed"] or 0) for r in summary_rows],      "#4338ca"),
        ("Revisión manual",[int(r["manual_review"] or 0) for r in summary_rows],"#d97706"),
        ("Parse error",    [int(r["parse_error"] or 0) for r in summary_rows],  "#ea580c"),
        ("Error",          [int(r["error"] or 0) for r in summary_rows],        "#dc2626"),
    ]
    bar_svg = stacked_bar_chart(f"Resultados por día ({days} días)", days_axis, series)

    total_rows = int(kpi["total_rows"] or 0) if kpi else 0
    parse_err = int(kpi["parse_error"] or 0) if kpi else 0
    err = int(kpi["error"] or 0) if kpi else 0
    parse_err_rate = (parse_err / total_rows * 100) if total_rows else 0.0
    err_rate = (err / total_rows * 100) if total_rows else 0.0

    # ── Tiempo por estado Effi (con conversión a días aprox) ──────
    status_rows = repo.avg_time_in_status(days=max(days, 60))

    return render_template(
        "dashboard/analytics.html",
        range_mode=range_mode,
        days=days,
        from_str=from_str,
        to_str=to_str,
        backlog_threshold=backlog_threshold,
        # Operativo
        por_recoger=por_recoger,
        breakdown=breakdown,
        resolution=resolution,
        cycle=cycle,
        backlog_count=backlog_count,
        backlog_top=backlog_top,
        clients_open=clients_open,
        trend_svg=trend_svg,
        # Sistema
        kpi=kpi,
        total_rows=total_rows,
        parse_err_rate=parse_err_rate,
        err_rate=err_rate,
        bar_svg=bar_svg,
        status_rows=status_rows,
    )


@dashboard_bp.route("/analytics/por-recoger")
@login_required
def por_recoger():
    repo = _repo()
    breakdown = repo.por_recoger_detailed_breakdown()
    return render_template("dashboard/analytics_por_recoger.html", breakdown=breakdown)


@dashboard_bp.route("/analytics/manual")
@login_required
def analytics_manual():
    """Página de referencia que explica cada métrica de analytics."""
    return render_template("dashboard/analytics_manual.html")


@dashboard_bp.route("/runs")
@login_required
def runs():
    from ..pagination import Pagination, read_pagination_args
    repo = _repo()
    mode_filter = (request.args.get("mode") or "").strip()
    page, per_page = read_pagination_args(default_per_page=50)
    # mode_filter es solo client-side. Para paginación correcta cuando hay filtro,
    # mejor: traer todo y filtrar. Volumen pequeño (decenas/cientos de corridas).
    total = repo.count_runs()
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    rows = repo.list_runs(limit=pag.per_page, offset=pag.offset)
    if mode_filter:
        rows = [row for row in rows if str(row["mode"]) == mode_filter]
    return render_template("dashboard/runs.html", rows=rows, mode_filter=mode_filter, pagination=pag)


@dashboard_bp.route("/runs/<int:run_id>")
@login_required
def run_detail(run_id: int):
    from ..pagination import Pagination, read_pagination_args
    repo = _repo()
    run = repo.get_run(run_id)
    if run is None:
        return render_template("dashboard/run_detail.html", run=None, run_id=run_id, rows=[], resultado_filter="", duration_text="", pagination=None)

    resultado_filter = (request.args.get("resultado") or "").strip()
    page, per_page = read_pagination_args(default_per_page=100)
    total = repo.count_run_results(run_id, resultado_filter=resultado_filter)
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    rows = repo.get_run_results(
        run_id, resultado_filter=resultado_filter,
        limit=pag.per_page, offset=pag.offset,
    )
    duration = repo.run_duration_seconds(run_id)
    duration_text = fmt_duration_seconds(duration) if duration else ""
    created = bool(request.args.get("created"))

    return render_template(
        "dashboard/run_detail.html",
        run=run,
        run_id=run_id,
        rows=rows,
        resultado_filter=resultado_filter,
        duration_text=duration_text,
        created=created,
        format_date_short=format_date_short,
        pagination=pag,
    )


@dashboard_bp.route("/guides/new", methods=["GET", "POST"])
@login_required
def new_guide():
    """Create a new guide atomically (Notion → local + audit).
    Disponible para cualquier usuario logueado; las credenciales de Notion
    se toman del .env del servidor."""
    settings = current_app.config["SETTINGS"]
    notion_ready = bool(settings.notion_api_key and settings.notion_data_source_id)
    estado_options = []
    if notion_ready:
        try:
            from ..notion_helpers import get_estado_novedad_options
            estado_options = get_estado_novedad_options()
        except Exception:  # noqa: BLE001
            estado_options = []

    form_data = {"guia": "", "cliente": "", "telefono": "", "producto": "",
                 "valor": "", "cantidad": "", "estado_novedad": "", "carrier": "effi"}
    error = None

    if request.method == "POST":
        if not notion_ready:
            error = "Faltan credenciales de Notion en el servidor."
        else:
            for k in form_data:
                form_data[k] = (request.form.get(k) or "").strip()

            from vaecos_v02.providers.notion_provider import NotionProvider
            from vaecos_v02.app.services.add_guide import add_guide
            notion = NotionProvider(
                api_key=settings.notion_api_key,
                notion_version=settings.notion_version,
                data_source_id=settings.notion_data_source_id,
            )
            autor = session.get("user_email", "unknown")
            try:
                result = add_guide(
                    db_path=current_app.config["DB_PATH"],
                    notion=notion,
                    fields=form_data,
                    autor=autor,
                )
                flash(f"Guía {result.guia} creada correctamente en Notion y en la app.", "ok")
                return redirect(url_for("dashboard.guide_detail", guia=result.guia))
            except (ValueError, LookupError) as exc:
                error = str(exc)
            except Exception as exc:  # noqa: BLE001
                error = f"Notion rechazó la creación: {exc}"

    return render_template(
        "dashboard/new_guide.html",
        form_data=form_data,
        estado_options=estado_options,
        error=error,
        notion_ready=notion_ready,
    )


@dashboard_bp.route("/guides/<path:guia>")
@login_required
def guide_detail(guia: str):
    repo = _repo()
    rows = repo.guide_history(guia, limit=30)
    telefono = repo.latest_phone_for_guide(guia)
    notes = repo.list_notes_for_guide(guia)
    edits = repo.list_edits_for_guide(guia)
    # Pull current snapshot row for this guide (if exists in guides table)
    guide_row = None
    from sqlite3 import connect as _sqlite_connect
    conn = _sqlite_connect(str(current_app.config["DB_PATH"]))
    conn.row_factory = lambda c, r: dict((c.description[i][0], r[i]) for i in range(len(r)))
    try:
        guide_row = conn.execute(
            "SELECT guia, cliente, telefono, estado_novedad, carrier, "
            "       producto, valor, cantidad, archived, last_synced_at "
            "FROM guides WHERE guia = ? LIMIT 1", (guia,)
        ).fetchone()
    finally:
        conn.close()
    return render_template(
        "dashboard/guide_detail.html",
        guia=guia,
        rows=rows,
        telefono=telefono,
        notes=notes,
        edits=edits,
        guide_row=guide_row,
        estado_options=get_estado_novedad_options(),
        format_date_short=format_date_short,
    )


@dashboard_bp.route("/guides/<path:guia>/state", methods=["POST"])
@login_required
def update_state(guia: str):
    """Atomic state update — writes to Notion first, then local + audit."""
    new_state = (request.form.get("estado") or "").strip()
    if not new_state:
        return jsonify({"ok": False, "error": "Estado requerido."}), 400

    settings = current_app.config["SETTINGS"]
    if not settings.notion_api_key or not settings.notion_data_source_id:
        return jsonify({"ok": False, "error": "Faltan credenciales de Notion."}), 500

    from vaecos_v02.providers.notion_provider import NotionProvider
    from vaecos_v02.app.services.update_guide import update_guide_state

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
    )
    autor = session.get("user_email", "unknown")

    try:
        result = update_guide_state(
            db_path=current_app.config["DB_PATH"],
            notion=notion,
            guia=guia,
            new_state=new_state,
            autor=autor,
        )
    except (ValueError, LookupError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify({
        "ok": True,
        "guia": result.guia,
        "valor_anterior": result.valor_anterior,
        "valor_nuevo": result.valor_nuevo,
        "edit_id": result.edit_id,
    })


@dashboard_bp.route("/guides/<path:guia>/fields", methods=["POST"])
@login_required
def update_fields(guia: str):
    """Atomic update of editable fields (telefono/producto/valor/cantidad)."""
    settings = current_app.config["SETTINGS"]
    if not settings.notion_api_key or not settings.notion_data_source_id:
        flash("Faltan credenciales de Notion.", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    # Empty inputs = "do not touch this field" (no clearing via form). Si la operadora
    # quiere realmente borrar un valor, lo hace desde Notion directamente. Esto evita
    # borrados accidentales por dejar el formulario en blanco.
    new_values = {}
    for key in ("telefono", "producto", "valor", "cantidad"):
        if key in request.form:
            raw = (request.form.get(key) or "").strip()
            if raw:
                new_values[key] = raw

    if not new_values:
        flash("No se enviaron cambios — todos los campos están vacíos.", "warn")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    from vaecos_v02.providers.notion_provider import NotionProvider
    from vaecos_v02.app.services.update_guide import update_guide_fields

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
    )
    autor = session.get("user_email", "unknown")

    try:
        result = update_guide_fields(
            db_path=current_app.config["DB_PATH"],
            notion=notion,
            guia=guia,
            new_values=new_values,
            autor=autor,
        )
    except (ValueError, LookupError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))
    except Exception as exc:  # noqa: BLE001
        flash(f"Notion rechazó los cambios: {exc}", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    if not result.changes:
        flash("Sin cambios — los valores ingresados son iguales a los actuales.", "warn")
    else:
        labels = {"telefono": "Teléfono", "producto": "Producto", "valor": "Valor", "cantidad": "Cantidad"}
        changed_labels = ", ".join(labels.get(k, k) for k in result.changes.keys())
        flash(f"Actualizado: {changed_labels}.", "ok")
    return redirect(url_for("dashboard.guide_detail", guia=guia))


@dashboard_bp.route("/guides/<path:guia>/unarchive", methods=["POST"])
@login_required
def unarchive_guide_route(guia: str):
    """Restaurar una guía archivada (saca de papelera Notion + archived=0 local)."""
    settings = current_app.config["SETTINGS"]
    if not settings.notion_api_key or not settings.notion_data_source_id:
        flash("Faltan credenciales de Notion en el servidor.", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    from vaecos_v02.providers.notion_provider import NotionProvider
    from vaecos_v02.app.services.update_guide import unarchive_guide

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
    )
    autor = session.get("user_email", "unknown")

    try:
        result = unarchive_guide(
            db_path=current_app.config["DB_PATH"],
            notion=notion,
            guia=guia,
            autor=autor,
        )
    except (ValueError, LookupError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))
    except Exception as exc:  # noqa: BLE001
        flash(f"Notion rechazó la restauración: {exc}", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    flash(f"Guía {result.guia} restaurada y disponible en /all-guides.", "ok")
    return redirect(url_for("dashboard.guide_detail", guia=guia))


@dashboard_bp.route("/guides/<path:guia>/archive", methods=["POST"])
@login_required
def archive_guide_route(guia: str):
    """Soft delete: archiva en Notion (papelera 30 días) + marca archived=1 local."""
    settings = current_app.config["SETTINGS"]
    if not settings.notion_api_key or not settings.notion_data_source_id:
        flash("Faltan credenciales de Notion en el servidor.", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    from vaecos_v02.providers.notion_provider import NotionProvider
    from vaecos_v02.app.services.update_guide import archive_guide

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
    )
    autor = session.get("user_email", "unknown")

    try:
        result = archive_guide(
            db_path=current_app.config["DB_PATH"],
            notion=notion,
            guia=guia,
            autor=autor,
        )
    except (ValueError, LookupError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))
    except Exception as exc:  # noqa: BLE001
        flash(f"Notion rechazó el archivado: {exc}", "error")
        return redirect(url_for("dashboard.guide_detail", guia=guia))

    flash(
        f"Guía {result.guia} archivada. Está en la papelera de Notion (recuperable por 30 días).",
        "ok",
    )
    return redirect(url_for("dashboard.all_guides"))


@dashboard_bp.route("/guides/<path:guia>/notes", methods=["POST"])
@login_required
def create_note(guia: str):
    body = (request.form.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "La nota no puede estar vacía."}), 400
    autor = session.get("user_email", "unknown")
    note_id = _repo().create_note(guia=guia, autor=autor, body=body)
    note = _repo().get_note(note_id)
    return jsonify({
        "ok": True,
        "note": {
            "id": note["id"],
            "autor": note["autor"],
            "body": note["body"],
            "created_at": note["created_at"],
            "edited_at": note["edited_at"],
        },
    })


@dashboard_bp.route("/guides/<path:guia>/notes/<int:note_id>", methods=["DELETE", "POST"])
@login_required
def delete_note(guia: str, note_id: int):
    """Delete a note. Only the author may delete (or any admin)."""
    if request.method == "POST" and request.form.get("_method") != "DELETE":
        abort(405)
    repo = _repo()
    note = repo.get_note(note_id)
    if not note or note["guia"] != guia:
        return jsonify({"ok": False, "error": "Nota no encontrada."}), 404
    is_owner = note["autor"] == session.get("user_email", "")
    is_admin = session.get("role") == "admin"
    if not (is_owner or is_admin):
        return jsonify({"ok": False, "error": "Sólo el autor o un admin pueden borrar."}), 403
    repo.delete_note(note_id)
    return jsonify({"ok": True})


@dashboard_bp.route("/clients/<path:cliente>")
@login_required
def client_detail(cliente: str):
    from ..pagination import Pagination, read_pagination_args
    repo = _repo()
    try:
        days = max(7, min(int(request.args.get("days") or "90"), 365))
    except ValueError:
        days = 90

    page, per_page = read_pagination_args(default_per_page=50)
    summary = repo.client_summary(cliente, days=days)
    total = repo.count_client_history(cliente, days=days)
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    rows = repo.client_history(cliente, days=days, limit=pag.per_page, offset=pag.offset)
    telefono = repo.latest_phone_for_client(cliente)
    return render_template(
        "dashboard/client_detail.html",
        cliente=cliente,
        days=days,
        summary=summary,
        rows=rows,
        telefono=telefono,
        pagination=pag,
    )


_GUIDE_RE = re.compile(r"^[Bb]\d+(?:-\d+)?$")


@dashboard_bp.route("/search")
@login_required
def search():
    from ..pagination import Pagination, read_pagination_args

    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("dashboard/search.html", q="", clients=None,
                               phone_results=None, kind=None, pagination=None)

    # Smart routing
    if _GUIDE_RE.match(q):
        return redirect(url_for("dashboard.guide_detail", guia=q.upper()))

    repo = _repo()
    page, per_page = read_pagination_args(default_per_page=50)
    digits = "".join(c for c in q if c.isdigit())
    if digits and len(digits) >= 6 and not any(c.isalpha() for c in q):
        # Looks like a DPI/phone number — search by phone
        total = repo.count_search_by_phone(digits)
        pag = Pagination.build(page=page, per_page=per_page, total=total)
        rows = repo.search_by_phone(digits, limit=pag.per_page, offset=pag.offset)
        return render_template("dashboard/search.html", q=q, kind="phone",
                               telefono=digits, phone_results=rows, clients=None,
                               pagination=pag)

    # Otherwise, search by client name
    total = repo.count_search_clients_by_name(q)
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    clients = repo.search_clients_by_name(q, limit=pag.per_page, offset=pag.offset)
    return render_template("dashboard/search.html", q=q, kind="name",
                           clients=clients, phone_results=None, pagination=pag)


@dashboard_bp.route("/all-guides")
@login_required
def all_guides():
    from ..pagination import Pagination, read_pagination_args

    repo = _repo()
    estado = (request.args.get("estado") or "").strip()
    carrier = (request.args.get("carrier") or "").strip()
    q = (request.args.get("q") or "").strip()
    include_archived = request.args.get("archived") == "1"
    page, per_page = read_pagination_args(default_per_page=50)

    total = repo.count_all_guides(
        estado=estado, carrier=carrier, query=q, include_archived=include_archived,
    )
    pag = Pagination.build(page=page, per_page=per_page, total=total)

    rows = repo.list_all_guides(
        estado=estado, carrier=carrier, query=q, include_archived=include_archived,
        limit=pag.per_page, offset=pag.offset,
    )
    notes_counts = repo.notes_count_by_guide([r["guia"] for r in rows])
    states = repo.list_guide_states()
    counts = repo.guides_count()
    # Estados que el motor de tracking procesa hoy. Cualquier otro queda fuera.
    excluded = {
        "ENTREGADA", "PENDIENTE CLIENTE", "Solicitud devolución", "En Devolución",
        "Indemnización", "Pago indemnización", "Pendiente Indemnización",
    }
    return render_template(
        "dashboard/all_guides.html",
        rows=rows, states=states, counts=counts,
        notes_counts=notes_counts,
        estado=estado, carrier=carrier, q=q,
        include_archived=include_archived,
        excluded_states=excluded,
        estado_options=get_estado_novedad_options(),
        pagination=pag,
    )


@dashboard_bp.route("/run/new")
@login_required
def run_new():
    return render_template("dashboard/run_new.html")


@dashboard_bp.route("/rules")
@admin_required
def rules():
    """Lista de reglas del motor de tracking. Solo admin."""
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    carrier_filter = (request.args.get("carrier") or "").strip()
    show_disabled = request.args.get("show_disabled") == "1"

    conn = v02_connect(current_app.config["DB_PATH"])
    try:
        repo = RulesRepository(conn)
        rules_list = repo.list_rules(
            carrier=carrier_filter or None,
            only_enabled=not show_disabled,
        )
    finally:
        conn.close()

    total = len(rules_list)
    enabled_count = sum(1 for r in rules_list if r.enabled)
    return render_template(
        "dashboard/rules_list.html",
        rules=rules_list,
        total=total,
        enabled_count=enabled_count,
        disabled_count=total - enabled_count,
        carrier_filter=carrier_filter,
        show_disabled=show_disabled,
    )


@dashboard_bp.route("/rules/new", methods=["GET", "POST"])
@admin_required
def rule_new():
    return _rule_form(rule_id=None)


@dashboard_bp.route("/rules/<int:rule_id>/edit", methods=["GET", "POST"])
@admin_required
def rule_edit(rule_id: int):
    return _rule_form(rule_id=rule_id)


def _rule_form(rule_id: int | None):
    """Maneja create + edit. Si rule_id es None, crea; si es int, edita."""
    from vaecos_v02.core.models import Rule
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    db_path = current_app.config["DB_PATH"]
    error: str | None = None

    if request.method == "POST":
        try:
            estado_kind = (request.form.get("estado_match_kind") or "any").strip()
            novelty_kind = (request.form.get("novelty_match_kind") or "any").strip()
            estado_values = _split_lines(request.form.get("estado_match_values"))
            novelty_values = _split_lines(request.form.get("novelty_match_values"))
            days_cmp_raw = (request.form.get("days_comparator") or "").strip()
            days_cmp = days_cmp_raw or None
            days_threshold_raw = (request.form.get("days_threshold") or "").strip()
            days_threshold = int(days_threshold_raw) if days_threshold_raw else None

            rule = Rule(
                id=rule_id,
                carrier=(request.form.get("carrier") or "effi").strip(),
                name=(request.form.get("name") or "").strip(),
                priority=int((request.form.get("priority") or "100").strip()),
                enabled=request.form.get("enabled") == "1",
                estado_match_kind=estado_kind,
                estado_match_values=estado_values,
                novelty_match_kind=novelty_kind,
                novelty_match_values=novelty_values,
                days_comparator=days_cmp,
                days_threshold=days_threshold,
                estado_propuesto=(request.form.get("estado_propuesto") or "").strip() or None,
                motivo_template=(request.form.get("motivo_template") or "").strip(),
                requiere_accion=(request.form.get("requiere_accion") or "").strip(),
                review_needed=request.form.get("review_needed") == "1",
                notes=(request.form.get("notes") or "").strip(),
            )
            conn = v02_connect(db_path)
            try:
                saved = RulesRepository(conn).save_rule(
                    rule, changed_by=session.get("user_email", "admin"),
                )
            finally:
                conn.close()
            flash(
                f"Regla {'creada' if rule_id is None else 'actualizada'}: {saved.name}.",
                "ok",
            )
            return redirect(url_for("dashboard.rules"))
        except (ValueError, TypeError) as e:
            error = str(e)

    # GET o POST con error → render form
    existing = None
    if rule_id is not None:
        conn = v02_connect(db_path)
        try:
            existing = RulesRepository(conn).get_rule(rule_id)
        finally:
            conn.close()
        if existing is None:
            flash(f"Regla #{rule_id} no encontrada.", "error")
            return redirect(url_for("dashboard.rules"))

    return render_template(
        "dashboard/rule_edit.html",
        rule=existing,
        error=error,
        form=request.form if request.method == "POST" else None,
    )


@dashboard_bp.route("/rules/<int:rule_id>/toggle", methods=["POST"])
@admin_required
def rule_toggle(rule_id: int):
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    conn = v02_connect(current_app.config["DB_PATH"])
    try:
        result = RulesRepository(conn).toggle_rule(
            rule_id, changed_by=session.get("user_email", "admin"),
        )
    finally:
        conn.close()
    if result is None:
        flash(f"Regla #{rule_id} no encontrada.", "error")
    else:
        flash(
            f"Regla '{result.name}' {'activada' if result.enabled else 'desactivada'}.",
            "ok",
        )
    return redirect(url_for("dashboard.rules"))


@dashboard_bp.route("/rules/<int:rule_id>/delete", methods=["POST"])
@admin_required
def rule_delete(rule_id: int):
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    conn = v02_connect(current_app.config["DB_PATH"])
    try:
        repo = RulesRepository(conn)
        existing = repo.get_rule(rule_id)
        ok = repo.delete_rule(rule_id, changed_by=session.get("user_email", "admin"))
    finally:
        conn.close()
    if ok and existing:
        flash(f"Regla '{existing.name}' eliminada.", "ok")
    else:
        flash(f"Regla #{rule_id} no encontrada.", "error")
    return redirect(url_for("dashboard.rules"))


@dashboard_bp.route("/rules/preview", methods=["GET", "POST"])
@admin_required
def rule_preview():
    """Simulador: dado un estado/novedad/días, muestra qué regla matchearía
    y qué decisión produciría el motor. NO escribe nada — read-only."""
    from datetime import date as _date, datetime as _dt, timedelta as _td
    from vaecos_v02.core.models import EffiNovedadEvent, EffiStatusEvent, EffiTrackingData
    from vaecos_v02.core.rules import decide_status
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    if request.method == "GET":
        return render_template("dashboard/rule_preview.html", form=None, result=None, error=None, autofilled=False)

    form = dict(request.form)
    action = form.get("action", "evaluate")
    guia_input = (form.get("guia") or "").strip()
    error: str | None = None

    # ── Modo autofill: cargar desde guía existente ────────────────
    if action == "autofill":
        if not guia_input:
            return render_template(
                "dashboard/rule_preview.html",
                form=form, result=None, autofilled=False,
                error="Ingresá un número de guía para auto-completar.",
            )
        autofilled, error = _autofill_from_guia(guia_input, current_app.config["DB_PATH"])
        if error:
            return render_template(
                "dashboard/rule_preview.html",
                form=form, result=None, autofilled=False, error=error,
            )
        return render_template(
            "dashboard/rule_preview.html",
            form=autofilled, result=None, autofilled=True, error=None,
        )

    # ── Modo evaluate ─────────────────────────────────────────────
    estado_effi = (form.get("estado_effi") or "").strip()
    novelty = (form.get("novelty") or "").strip()
    days_since_raw = (form.get("days_since") or "").strip()
    carrier = (form.get("carrier") or "effi").strip()
    notion_estado_raw = (form.get("notion_estado") or "").strip()
    notion_estado = notion_estado_raw or None

    status_history = []
    days_value: int | None = None
    if estado_effi:
        status_date = None
        if days_since_raw.isdigit():
            days_value = int(days_since_raw)
            status_date = _dt.combine(_date.today() - _td(days=days_value), _dt.min.time())
        status_history.append(EffiStatusEvent(date=status_date, status=estado_effi))

    novelty_history = []
    if novelty:
        novelty_history.append(EffiNovedadEvent(date=None, novelty=novelty, details=""))

    tracking = EffiTrackingData(
        url="",
        estado_actual=estado_effi or None,
        status_history=status_history,
        novelty_history=novelty_history,
    )

    conn = v02_connect(current_app.config["DB_PATH"])
    try:
        rules_list = RulesRepository(conn).list_rules(carrier=carrier, only_enabled=True)
    finally:
        conn.close()

    decision = decide_status(
        tracking, _date.today(),
        rules=rules_list, carrier=carrier, notion_estado=notion_estado,
    )

    return render_template(
        "dashboard/rule_preview.html",
        form=form, result=decision, autofilled=False, error=None,
        rules_evaluated=len(rules_list),
        days_value=days_value,
    )


def _autofill_from_guia(guia: str, db_path):
    """Devuelve (form_dict, error) con los últimos datos de tracking del guía."""
    from datetime import datetime as _dt, date as _date
    from vaecos_v02.storage.db import connect as v02_connect

    conn = v02_connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT rr.run_id, rr.carrier, rr.estado_notion_actual, rr.estado_effi_actual
            FROM run_results rr
            WHERE rr.guia = ?
            ORDER BY rr.run_id DESC
            LIMIT 1
            """,
            (guia,),
        ).fetchone()
        if row is None:
            return None, f"La guía '{guia}' no tiene corridas previas en la base."

        run_id = row["run_id"]
        status_evt = conn.execute(
            """
            SELECT event_at, status FROM tracking_status_events
            WHERE run_id = ? AND guia = ?
            ORDER BY event_at DESC LIMIT 1
            """,
            (run_id, guia),
        ).fetchone()
        novelty_evt = conn.execute(
            """
            SELECT event_at, novelty FROM tracking_novelty_events
            WHERE run_id = ? AND guia = ?
            ORDER BY event_at DESC LIMIT 1
            """,
            (run_id, guia),
        ).fetchone()
    finally:
        conn.close()

    days_since = ""
    if status_evt and status_evt["event_at"]:
        try:
            ev_dt = _dt.fromisoformat(status_evt["event_at"])
            days_since = str(max(0, (_date.today() - ev_dt.date()).days))
        except (ValueError, TypeError):
            days_since = ""

    return {
        "guia": guia,
        "carrier": (row["carrier"] or "effi").strip(),
        "notion_estado": row["estado_notion_actual"] or "",
        "estado_effi": (row["estado_effi_actual"] or (status_evt["status"] if status_evt else "")),
        "novelty": novelty_evt["novelty"] if novelty_evt else "",
        "days_since": days_since,
    }, None


@dashboard_bp.route("/rules/<int:rule_id>/history")
@admin_required
def rule_history(rule_id: int):
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.storage.rules_repository import RulesRepository

    conn = v02_connect(current_app.config["DB_PATH"])
    try:
        repo = RulesRepository(conn)
        rule = repo.get_rule(rule_id)
        history = repo.history_for_rule(rule_id)
    finally:
        conn.close()
    if rule is None:
        flash(f"Regla #{rule_id} no encontrada.", "error")
        return redirect(url_for("dashboard.rules"))
    return render_template("dashboard/rule_history.html", rule=rule, history=history)


def _split_lines(text: str | None) -> list[str]:
    """Convierte un textarea en lista, una línea = un valor, sin vacíos ni duplicados."""
    if not text:
        return []
    seen: dict[str, str] = {}
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        if not s:
            continue
        seen.setdefault(s.lower(), s)
    return list(seen.values())
