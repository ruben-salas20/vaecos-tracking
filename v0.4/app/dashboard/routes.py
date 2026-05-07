from __future__ import annotations
import re
import sys
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, current_app, session, jsonify, abort, flash
from ..auth.decorators import login_required
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
                               unchanged=0,
                               duration_text="",
                               top_guides=[],
                               trend_svg="",
                               created=False)

    run_id = int(latest["id"])
    counts_rows = repo.result_counts(run_id)
    count_map = {str(row["resultado"]): int(row["total"]) for row in counts_rows}
    needs_attention = sum(v for k, v in count_map.items() if k != "unchanged")
    unchanged = count_map.get("unchanged", 0)
    duration = repo.run_duration_seconds(run_id)
    duration_text = fmt_duration_seconds(duration) if duration else ""
    top_guides = repo.top_guides_with_changes(limit=10)
    trend_rows = repo.attention_trend(days=30)
    trend_points = [(str(row["day"]), int(row["total"])) for row in trend_rows]
    trend_svg = line_chart("Atencion (30 dias)", trend_points, color="#dc2626")
    created = bool(request.args.get("created"))

    return render_template(
        "dashboard/home.html",
        latest=latest,
        count_map=count_map,
        needs_attention=needs_attention,
        unchanged=unchanged,
        duration_text=duration_text,
        top_guides=top_guides,
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
    repo = _repo()
    try:
        days = max(7, min(int(request.args.get("days") or "30"), 180))
    except ValueError:
        days = 30

    kpi = repo.kpi_summary(days=days)
    por_recoger = repo.latest_por_recoger_total()
    breakdown = repo.por_recoger_delivery_breakdown()
    trend_rows = repo.attention_trend(days=days)
    trend_points = [(str(row["day"]), int(row["total"])) for row in trend_rows]
    trend_svg = line_chart(f"Guias que requirieron atencion por dia ({days} dias)", trend_points, color="#dc2626")
    summary_rows = repo.runs_summary_by_day(days=days)
    days_axis = [str(row["day"]) for row in summary_rows]
    _C_SILVER = "#cbd5e1"
    _C_INFO   = "#4338ca"
    _C_WARN   = "#d97706"
    _C_PARSE  = "#ea580c"
    _C_DANGER = "#dc2626"
    series = [
        ("Sin cambios",    [int(r["unchanged"] or 0) for r in summary_rows],    _C_SILVER),
        ("Cambios",        [int(r["changed"] or 0) for r in summary_rows],      _C_INFO),
        ("Revision manual",[int(r["manual_review"] or 0) for r in summary_rows],_C_WARN),
        ("Parse error",    [int(r["parse_error"] or 0) for r in summary_rows],  _C_PARSE),
        ("Error",          [int(r["error"] or 0) for r in summary_rows],        _C_DANGER),
    ]
    bar_svg = stacked_bar_chart(f"Resultados por dia ({days} dias)", days_axis, series)
    carriers = repo.carrier_breakdown(days=days)
    clients = repo.top_problem_clients(days=days, limit=10)
    status_rows = repo.avg_time_in_status(days=max(days, 60))

    total_rows = int(kpi["total_rows"] or 0) if kpi else 0
    parse_err = int(kpi["parse_error"] or 0) if kpi else 0
    err = int(kpi["error"] or 0) if kpi else 0
    parse_err_rate = (parse_err / total_rows * 100) if total_rows else 0.0
    err_rate = (err / total_rows * 100) if total_rows else 0.0

    return render_template(
        "dashboard/analytics.html",
        days=days,
        kpi=kpi,
        total_rows=total_rows,
        parse_err_rate=parse_err_rate,
        err_rate=err_rate,
        por_recoger=por_recoger,
        breakdown=breakdown,
        trend_svg=trend_svg,
        bar_svg=bar_svg,
        carriers=carriers,
        clients=clients,
        status_rows=status_rows,
    )


@dashboard_bp.route("/analytics/por-recoger")
@login_required
def por_recoger():
    repo = _repo()
    breakdown = repo.por_recoger_detailed_breakdown()
    return render_template("dashboard/analytics_por_recoger.html", breakdown=breakdown)


@dashboard_bp.route("/runs")
@login_required
def runs():
    repo = _repo()
    mode_filter = (request.args.get("mode") or "").strip()
    rows = repo.list_runs(limit=100)
    if mode_filter:
        rows = [row for row in rows if str(row["mode"]) == mode_filter]
    return render_template("dashboard/runs.html", rows=rows, mode_filter=mode_filter)


@dashboard_bp.route("/runs/<int:run_id>")
@login_required
def run_detail(run_id: int):
    repo = _repo()
    run = repo.get_run(run_id)
    if run is None:
        return render_template("dashboard/run_detail.html", run=None, run_id=run_id, rows=[], resultado_filter="", duration_text="")

    resultado_filter = (request.args.get("resultado") or "").strip()
    rows = repo.get_run_results(run_id)
    if resultado_filter:
        rows = [row for row in rows if str(row["resultado"]) == resultado_filter]
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
    repo = _repo()
    try:
        days = max(7, min(int(request.args.get("days") or "90"), 365))
    except ValueError:
        days = 90

    summary = repo.client_summary(cliente, days=days)
    rows = repo.client_history(cliente, days=days)
    telefono = repo.latest_phone_for_client(cliente)
    return render_template(
        "dashboard/client_detail.html",
        cliente=cliente,
        days=days,
        summary=summary,
        rows=rows,
        telefono=telefono,
    )


_GUIDE_RE = re.compile(r"^[Bb]\d+(?:-\d+)?$")


@dashboard_bp.route("/search")
@login_required
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("dashboard/search.html", q="", clients=None,
                               phone_results=None, kind=None)

    # Smart routing
    if _GUIDE_RE.match(q):
        return redirect(url_for("dashboard.guide_detail", guia=q.upper()))

    repo = _repo()
    digits = "".join(c for c in q if c.isdigit())
    if digits and len(digits) >= 6 and not any(c.isalpha() for c in q):
        # Looks like a DPI/phone number — search by phone
        rows = repo.search_by_phone(digits)
        return render_template("dashboard/search.html", q=q, kind="phone",
                               telefono=digits, phone_results=rows, clients=None)

    # Otherwise, search by client name
    clients = repo.search_clients_by_name(q, limit=50)
    return render_template("dashboard/search.html", q=q, kind="name",
                           clients=clients, phone_results=None)


@dashboard_bp.route("/all-guides")
@login_required
def all_guides():
    repo = _repo()
    estado = (request.args.get("estado") or "").strip()
    carrier = (request.args.get("carrier") or "").strip()
    q = (request.args.get("q") or "").strip()
    include_archived = request.args.get("archived") == "1"
    rows = repo.list_all_guides(
        estado=estado, carrier=carrier, query=q, include_archived=include_archived,
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
    )


@dashboard_bp.route("/run/new")
@login_required
def run_new():
    return render_template("dashboard/run_new.html")


@dashboard_bp.route("/rules")
@login_required
def rules():
    return render_template("dashboard/rules_maintenance.html")
