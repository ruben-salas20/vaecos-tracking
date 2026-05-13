from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, abort, jsonify

from ..auth.decorators import login_required, admin_required
from .catalog_repo import CatalogRepository, VALID_TIPOS, parse_aliases_textarea
from .jobs import create_job, dispatch_effi_run, get_job
from .orders_repo import (
    EffiAuditLogRepository,
    EffiOrdersRepository,
    EffiReviewQueueRepository,
)

effi_bp = Blueprint("effi", __name__, url_prefix="/effi")


def _get_catalog_repo() -> CatalogRepository:
    return CatalogRepository(current_app.config["DB_PATH"])


def _get_orders_repo() -> EffiOrdersRepository:
    return EffiOrdersRepository(current_app.config["DB_PATH"])


def _get_audit_repo() -> EffiAuditLogRepository:
    return EffiAuditLogRepository(current_app.config["DB_PATH"])


def _get_queue_repo() -> EffiReviewQueueRepository:
    return EffiReviewQueueRepository(current_app.config["DB_PATH"])


@effi_bp.route("/")
@login_required
def dashboard():
    """Dashboard del módulo Creador guías con KPIs reales."""
    catalog = _get_catalog_repo().list_all(include_inactive=False)
    orders_repo = _get_orders_repo()
    queue_repo = _get_queue_repo()

    today_iso = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    counts_today = orders_repo.counts_by_status(since_iso=today_iso)
    counts_all = orders_repo.counts_by_status()

    return render_template(
        "effi_guides/dashboard.html",
        catalog_count=len(catalog),
        catalog_intimo_count=sum(1 for it in catalog if it.tipo == "intimo_femenino"),
        processed_today=counts_today.get("done", 0),
        failed_today=counts_today.get("failed", 0),
        review_today=counts_today.get("human_review", 0),
        processed_total=counts_all.get("done", 0),
        pending_queue=queue_repo.count_pending(),
        recent_orders=orders_repo.list_recent(limit=10),
    )


# ── Cola humana ─────────────────────────────────────────────────────


@effi_bp.route("/queue")
@login_required
def queue_list():
    items = _get_queue_repo().list_recent(limit=100)
    return render_template("effi_guides/queue.html", items=items)


@effi_bp.route("/queue/<int:item_id>/resolve", methods=["POST"])
@login_required
def queue_resolve(item_id: int):
    repo = _get_queue_repo()
    item = repo.get(item_id)
    if not item:
        flash("Item no encontrado.", "error")
        return redirect(url_for("effi.queue_list"))
    notes = (request.form.get("notes") or "").strip()
    repo.resolve(item_id, resolved_by=session.get("user_email", "anonimo"), notes=notes)
    flash(f"Item #{item_id} (orden {item.orden_id}) marcado como resuelto.", "ok")
    return redirect(url_for("effi.queue_list"))


# ── Audit log ──────────────────────────────────────────────────────


@effi_bp.route("/audit")
@login_required
def audit_list():
    only_order = request.args.get("orden_id", type=int)
    entries = _get_audit_repo().list_recent(limit=200, only_orden_id=only_order)
    return render_template("effi_guides/audit.html", entries=entries, only_order=only_order)


# ── Trigger manual de corrida ──────────────────────────────────────


@effi_bp.route("/run/manual", methods=["POST"])
@login_required
def run_manual():
    apply = (request.form.get("apply") or "").lower() in ("1", "true", "on", "yes")
    limit_raw = (request.form.get("limit") or "").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else 0
    only_order_raw = (request.form.get("only_order") or "").strip()
    only_order = int(only_order_raw) if only_order_raw.isdigit() else None

    token = create_job(
        mode="apply" if apply else "dry_run",
        limit=limit,
        only_order=only_order,
    )
    dispatch_effi_run(token, apply=apply, limit=limit, only_order=only_order)
    return redirect(url_for("effi.run_progress", token=token))


@effi_bp.route("/run/progress/<token>")
@login_required
def run_progress(token: str):
    job = get_job(token)
    if job is None:
        flash("Corrida no encontrada o expirada.", "error")
        return redirect(url_for("effi.dashboard"))
    return render_template("effi_guides/run_progress.html", job=job, token=token)


@effi_bp.route("/run/progress/<token>/json")
@login_required
def run_progress_json(token: str):
    job = get_job(token)
    if job is None:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)


@effi_bp.route("/catalog")
@admin_required
def catalog_list():
    items = _get_catalog_repo().list_all(include_inactive=True)
    return render_template("effi_guides/catalog.html", items=items, tipos=VALID_TIPOS)


@effi_bp.route("/catalog", methods=["POST"])
@admin_required
def catalog_create():
    sku = (request.form.get("sku") or "").strip()
    descripcion = (request.form.get("descripcion_exacta") or "").strip()
    precio_raw = (request.form.get("precio_declarado") or "").strip()
    tipo = (request.form.get("tipo") or "otro").strip()
    notas = (request.form.get("notas") or "").strip()
    aliases = parse_aliases_textarea(request.form.get("aliases"))

    if not sku or not descripcion or not precio_raw:
        flash("SKU, descripción y precio son obligatorios.", "error")
        return redirect(url_for("effi.catalog_list"))
    try:
        precio = float(precio_raw)
    except ValueError:
        flash("Precio inválido.", "error")
        return redirect(url_for("effi.catalog_list"))
    if tipo not in VALID_TIPOS:
        flash("Tipo inválido.", "error")
        return redirect(url_for("effi.catalog_list"))

    repo = _get_catalog_repo()
    if repo.get_by_sku(sku):
        flash(f"Ya existe un producto con SKU '{sku}'.", "error")
        return redirect(url_for("effi.catalog_list"))

    try:
        repo.create(
            sku=sku,
            descripcion_exacta=descripcion,
            precio_declarado=precio,
            tipo=tipo,
            notas=notas,
            aliases=aliases,
            updated_by=session.get("user_email", "admin"),
        )
        flash(f"Producto '{sku}' agregado.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("effi.catalog_list"))


@effi_bp.route("/catalog/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def catalog_edit(item_id: int):
    repo = _get_catalog_repo()
    item = repo.get_by_id(item_id)
    if not item:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("effi.catalog_list"))

    error = None
    if request.method == "POST":
        descripcion = (request.form.get("descripcion_exacta") or "").strip()
        precio_raw = (request.form.get("precio_declarado") or "").strip()
        tipo = (request.form.get("tipo") or "otro").strip()
        notas = (request.form.get("notas") or "").strip()
        aliases = parse_aliases_textarea(request.form.get("aliases"))
        if not descripcion or not precio_raw:
            error = "Descripción y precio son obligatorios."
        else:
            try:
                precio = float(precio_raw)
                repo.update(
                    item_id,
                    descripcion_exacta=descripcion,
                    precio_declarado=precio,
                    tipo=tipo,
                    notas=notas,
                    aliases=aliases,
                    updated_by=session.get("user_email", "admin"),
                )
                flash(f"Producto '{item.sku}' actualizado.", "ok")
                return redirect(url_for("effi.catalog_list"))
            except ValueError as e:
                error = str(e)

    return render_template("effi_guides/catalog_edit.html", item=item, tipos=VALID_TIPOS, error=error)


@effi_bp.route("/catalog/<int:item_id>/toggle", methods=["POST"])
@admin_required
def catalog_toggle(item_id: int):
    _get_catalog_repo().toggle_active(item_id, updated_by=session.get("user_email", "admin"))
    return redirect(url_for("effi.catalog_list"))


@effi_bp.route("/catalog/<int:item_id>/delete", methods=["POST"])
@admin_required
def catalog_delete(item_id: int):
    repo = _get_catalog_repo()
    item = repo.get_by_id(item_id)
    if not item:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("effi.catalog_list"))
    repo.delete(item_id)
    flash(f"Producto '{item.sku}' eliminado.", "ok")
    return redirect(url_for("effi.catalog_list"))
