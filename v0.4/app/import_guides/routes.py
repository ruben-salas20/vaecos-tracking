from __future__ import annotations
from datetime import datetime
from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, flash, current_app
)
from ..auth.decorators import login_required
from .parser import ExcelParser, ParseResult

import_bp = Blueprint("import_guides", __name__)


@import_bp.route("/import", methods=["GET"])
@login_required
def import_form():
    return render_template("import_guides/import.html")


@import_bp.route("/import", methods=["POST"])
@login_required
def import_preview():
    from vaecos_v02.storage.db import connect as v02_connect
    db_path = current_app.config["DB_PATH"]
    f = request.files.get("excel_file")
    if not f or not f.filename:
        flash("Seleccioná un archivo Excel.", "error")
        return redirect(url_for("import_guides.import_form"))
    if not f.filename.lower().endswith((".xlsx", ".xls")):
        flash("El archivo debe ser .xlsx o .xls.", "error")
        return redirect(url_for("import_guides.import_form"))

    conn = v02_connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT guia FROM run_results").fetchall()
        existing = {r["guia"].upper() for r in rows}
    finally:
        conn.close()

    parser = ExcelParser(existing)
    result = parser.parse(f.stream, filename=f.filename)

    # Serialize preview to session (JSON-safe)
    session["import_preview"] = {
        "filename": result.filename,
        "raw_count": result.raw_count,
        "new": [
            {"guia": g.guia, "cliente": g.cliente, "carrier": g.carrier,
             "id_cliente": g.id_cliente, "telefono": g.telefono,
             "estado_inicial": g.estado_inicial, "valor": g.valor,
             "cantidad": g.cantidad, "producto": g.producto,
             "row_number": g.row_number}
            for g in result.new
        ],
        "skipped": [
            {"guia": g.guia, "cliente": g.cliente, "carrier": g.carrier,
             "id_cliente": g.id_cliente, "telefono": g.telefono,
             "estado_inicial": g.estado_inicial, "valor": g.valor,
             "cantidad": g.cantidad, "producto": g.producto,
             "row_number": g.row_number}
            for g in result.skipped
        ],
        "errors": [
            {"guia": g.guia, "error": g.error, "row_number": g.row_number}
            for g in result.errors
        ],
    }
    return render_template("import_guides/import_preview.html", result=result)


@import_bp.route("/import/confirm", methods=["POST"])
@login_required
def import_confirm():
    from vaecos_v02.storage.db import connect as v02_connect
    from vaecos_v02.providers.notion_provider import NotionProvider

    preview = session.pop("import_preview", None)
    if not preview:
        flash("No hay importación pendiente de confirmar.", "error")
        return redirect(url_for("import_guides.import_form"))

    settings = current_app.config["SETTINGS"]
    if not settings.notion_api_key or not settings.notion_data_source_id:
        flash("Faltan credenciales de Notion en .env (NOTION_API_KEY o NOTION_DATA_SOURCE_ID).", "error")
        return redirect(url_for("import_guides.import_form"))

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
        query_kind="auto",
    )

    created: list[dict] = []
    failed: list[dict] = []
    for guide in preview["new"]:
        try:
            page_id = notion.create_guide_page(
                guia=guide["guia"],
                cliente=guide.get("cliente", ""),
                carrier=guide.get("carrier", "effi"),
                estado_novedad=guide.get("estado_inicial", ""),
                telefono=guide.get("telefono", ""),
                valor=guide.get("valor", ""),
                cantidad=guide.get("cantidad", 0) or 0,
                producto=guide.get("producto", ""),
            )
            created.append({**guide, "page_id": page_id})
        except Exception as exc:
            failed.append({**guide, "error": str(exc)})

    db_path = current_app.config["DB_PATH"]
    conn = v02_connect(db_path)
    try:
        conn.execute(
            "INSERT INTO import_log (imported_at, imported_by, filename, guides_new, guides_skipped, guides_error) "
            "VALUES (?,?,?,?,?,?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                session.get("user_email", "unknown"),
                preview["filename"],
                len(created),
                len(preview["skipped"]),
                len(preview["errors"]) + len(failed),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return render_template(
        "import_guides/import_result.html",
        filename=preview["filename"],
        created=created,
        failed=failed,
        skipped_count=len(preview["skipped"]),
        parse_errors_count=len(preview["errors"]),
    )
