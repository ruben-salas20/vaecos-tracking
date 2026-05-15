from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, abort, jsonify

from ..auth.decorators import login_required, admin_required
from .address_examples_repo import AddressExamplesRepository, VALID_VEREDICTOS
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


def _get_address_examples_repo() -> AddressExamplesRepository:
    return AddressExamplesRepository(current_app.config["DB_PATH"])


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
    from ..pagination import Pagination, read_pagination_args
    page, per_page = read_pagination_args(default_per_page=50)
    repo = _get_queue_repo()
    total = repo.count()
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    items = repo.list_recent(limit=pag.per_page, offset=pag.offset)
    return render_template("effi_guides/queue.html", items=items, pagination=pag)


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
    from ..pagination import Pagination, read_pagination_args
    only_order = request.args.get("orden_id", type=int)
    page, per_page = read_pagination_args(default_per_page=50)
    repo = _get_audit_repo()
    total = repo.count(only_orden_id=only_order)
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    entries = repo.list_recent(limit=pag.per_page, offset=pag.offset, only_orden_id=only_order)
    return render_template(
        "effi_guides/audit.html",
        entries=entries, only_order=only_order, pagination=pag,
    )


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


# ── Ejemplos del validador IA de direcciones ───────────────────────

@effi_bp.route("/address-examples")
@admin_required
def address_examples_list():
    repo = _get_address_examples_repo()
    return render_template(
        "effi_guides/address_examples.html",
        examples=repo.list_all(),
        counts=repo.counts(),
        veredictos=VALID_VEREDICTOS,
    )


@effi_bp.route("/address-examples", methods=["POST"])
@admin_required
def address_examples_create():
    address = (request.form.get("address") or "").strip()
    veredicto = (request.form.get("veredicto") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if not address or not reason:
        flash("Dirección y razón son obligatorias.", "error")
        return redirect(url_for("effi.address_examples_list"))
    if veredicto not in VALID_VEREDICTOS:
        flash("Veredicto inválido.", "error")
        return redirect(url_for("effi.address_examples_list"))
    new_id = _get_address_examples_repo().create(
        address=address, veredicto=veredicto, reason=reason,
        created_by=session.get("user_email", "admin"),
    )
    if new_id:
        flash(f"Ejemplo #{new_id} agregado. Aplica desde la próxima corrida del bot.", "ok")
    else:
        flash("No se pudo agregar el ejemplo.", "error")
    return redirect(url_for("effi.address_examples_list"))


@effi_bp.route("/address-examples/<int:ex_id>/edit", methods=["POST"])
@admin_required
def address_examples_edit(ex_id: int):
    address = (request.form.get("address") or "").strip()
    veredicto = (request.form.get("veredicto") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if not address or not reason or veredicto not in VALID_VEREDICTOS:
        flash("Datos inválidos — revisá dirección, veredicto y razón.", "error")
        return redirect(url_for("effi.address_examples_list"))
    ok = _get_address_examples_repo().update(
        ex_id, address=address, veredicto=veredicto, reason=reason,
    )
    flash(f"Ejemplo #{ex_id} actualizado." if ok else "Ejemplo no encontrado.",
          "ok" if ok else "error")
    return redirect(url_for("effi.address_examples_list"))


@effi_bp.route("/address-examples/<int:ex_id>/toggle", methods=["POST"])
@admin_required
def address_examples_toggle(ex_id: int):
    new_state = _get_address_examples_repo().toggle(ex_id)
    if new_state is None:
        flash("Ejemplo no encontrado.", "error")
    else:
        flash(f"Ejemplo #{ex_id} {'activado' if new_state else 'desactivado'}.", "ok")
    return redirect(url_for("effi.address_examples_list"))


@effi_bp.route("/address-examples/<int:ex_id>/delete", methods=["POST"])
@admin_required
def address_examples_delete(ex_id: int):
    ok = _get_address_examples_repo().delete(ex_id)
    flash(f"Ejemplo #{ex_id} eliminado." if ok else "Ejemplo no encontrado.",
          "ok" if ok else "error")
    return redirect(url_for("effi.address_examples_list"))


@effi_bp.route("/address-examples/test", methods=["POST"])
@admin_required
def address_examples_test():
    """Prueba una dirección contra el validador IA en vivo. Devuelve JSON.

    Usa los ejemplos ACTUALES de la DB (incluyendo los recién agregados).
    Puede tardar 10-25s — el cliente muestra un spinner.
    """
    data = request.get_json(silent=True) or {}
    address = (data.get("address") or "").strip()
    if not address:
        return jsonify({"ok": False, "error": "Dirección vacía."}), 400

    try:
        from .effi_config import load_settings
        from .address_ai_validator import build_validator_from_settings
        settings = load_settings()
        validator = build_validator_from_settings(settings)
        if validator is None:
            return jsonify({
                "ok": False,
                "error": "Validador IA no disponible (falta MINIMAX_API_KEY o AI_ADDRESS_VALIDATION off).",
            }), 503
        result = validator.evaluate(address)
        if result is None:
            return jsonify({
                "ok": False,
                "error": "La IA no devolvió resultado (timeout o error de parseo). Reintentá.",
            })
        return jsonify({
            "ok": True,
            "status": result.status.value,
            "reason": result.reason,
            "model": result.model,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500
