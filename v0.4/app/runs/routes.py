from __future__ import annotations
import csv
import io
import sys
from pathlib import Path
from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, flash, current_app, make_response, jsonify
)
from ..auth.decorators import login_required
from ..utils import sanitize_csv_field
from .jobs import create_job, get_job, dispatch_run, create_sync_job, get_sync_job, dispatch_sync

# Inject v0.3 for DashboardRepository
_V03_ROOT = Path(__file__).resolve().parents[3] / "v0.3"
if str(_V03_ROOT) not in sys.path:
    sys.path.insert(0, str(_V03_ROOT))

from vaecos_v03.storage import DashboardRepository

runs_bp = Blueprint("runs", __name__)


def _repo() -> DashboardRepository:
    return DashboardRepository(current_app.config["DB_PATH"])


@runs_bp.route("/run/new", methods=["POST"])
@login_required
def run_new():
    guides_raw = request.form.get("guides", "").strip()
    guides = [g.strip() for g in guides_raw.replace("\n", ",").split(",") if g.strip()]
    mode = request.form.get("mode", "dry-run")
    save_raw_html = bool(request.form.get("save_raw_html"))
    all_active = not guides

    token = create_job()
    dispatch_run(
        token=token,
        db_path=current_app.config["DB_PATH"],
        guides=guides,
        all_active=all_active,
        dry_run=(mode != "apply"),
        save_raw_html=save_raw_html,
    )
    return redirect(url_for("runs.run_progress", token=token))


@runs_bp.route("/run/progress/<token>")
@login_required
def run_progress(token: str):
    job = get_job(token)
    return render_template("dashboard/run_progress.html", token=token, job=job)


@runs_bp.route("/runs/<int:run_id>/export/effi")
@login_required
def export_effi(run_id: int):
    repo = _repo()
    rows = repo.export_effi_rows(run_id)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["No. Guía", "Estado actual (Effi)", "Problema", "Notas operadora"])
    for row in rows:
        problema = sanitize_csv_field(row["motivo"] or "")
        writer.writerow([
            row["guia"] or "",
            row["estado_effi_actual"] or "",
            problema,
            row["notas_operador"] or "",
        ])
    encoded = ("﻿" + buf.getvalue()).encode("utf-8")
    response = make_response(encoded)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Length"] = str(len(encoded))
    response.headers["Content-Disposition"] = f'attachment; filename="run_{run_id}_effi_export.csv"'
    return response


@runs_bp.route("/sync/notion", methods=["POST"])
@login_required
def sync_notion():
    """Trigger a background sync of the guides snapshot from Notion."""
    token = create_sync_job()
    dispatch_sync(token=token, db_path=current_app.config["DB_PATH"])
    return redirect(url_for("runs.sync_progress", token=token))


@runs_bp.route("/sync/progress/<token>")
@login_required
def sync_progress(token: str):
    job = get_sync_job(token)
    return render_template("dashboard/sync_progress.html", token=token, job=job)


@runs_bp.route("/sync/status/<token>")
@login_required
def sync_status(token: str):
    """JSON status for AJAX polling."""
    job = get_sync_job(token)
    if not job:
        return jsonify({"status": "unknown"}), 404
    return jsonify(job)


@runs_bp.route("/runs/<int:run_id>/results/<path:guia>/notas", methods=["POST"])
@login_required
def update_notas(run_id: int, guia: str):
    note = request.form.get("notas_operador", "")
    _repo().update_operator_note(run_id, guia, note)
    # AJAX clients get JSON; classic form posts get the redirect fallback.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "guia": guia, "notas_operador": note})
    return redirect(url_for("dashboard.run_detail", run_id=run_id))
