"""Orquestador del flujo Effi (idempotente).

Responsabilidades:
  - Recibir un EffiBot ya conectado.
  - Para cada orden: leer detalle, validar dirección, clasificar.
  - Decidir entre: ejecutar (write) / escalar (review_queue) / saltar (ya procesada).
  - Persistir TODO: effi_orders + effi_audit_log + effi_review_queue.
  - Notificar por email en escalations y errores.

NO sabe de:
  - Flask, blueprints, sesión web.
  - Playwright directamente (sólo el bot).
"""
from __future__ import annotations

import json
import sqlite3
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .address_ai_validator import (
    AIValidationResult,
    MiniMaxAddressValidator,
    build_validator_from_settings,
)
from .address_validator import AddressResult, AddressValidation, validate_address
from .bot import EffiBot, EffiBotError, ScrapedOrder, compute_fecha_entrega, compute_fecha_envio
from .classifier import (
    CatalogEntry,
    EscalationReason,
    OrderProduct,
    ProcessingPlan,
    classify,
)
from .notifier import notify
from .orders_repo import (
    EffiAuditLogRepository,
    EffiOrdersRepository,
    EffiReviewQueueRepository,
)


@dataclass(frozen=True)
class ProcessResult:
    orden_id: int
    status: str        # 'done' | 'failed' | 'human_review' | 'skipped' | 'would_process'
    classification: str | None = None
    address_status: str | None = None
    valor_declarado: float | None = None
    remision_id: int | None = None
    guia_id: int | None = None
    reason: str | None = None
    error_msg: str | None = None


@dataclass
class RunSummary:
    total_seen: int = 0
    needs_processing: int = 0
    skipped: int = 0
    processed: int = 0
    escalated: int = 0
    failed: int = 0
    details: list[ProcessResult] = field(default_factory=list)


def load_catalog(db_path: Path) -> list[CatalogEntry]:
    """Carga el catálogo activo de la DB para alimentar al clasificador."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT sku, descripcion_exacta, precio_declarado, tipo, aliases "
            "FROM effi_catalog WHERE activo = 1"
        ).fetchall()
    finally:
        conn.close()
    entries: list[CatalogEntry] = []
    for r in rows:
        try:
            aliases = tuple(a for a in json.loads(r["aliases"] or "[]") if a)
        except (TypeError, ValueError):
            aliases = ()
        entries.append(
            CatalogEntry(
                sku=r["sku"],
                descripcion_exacta=r["descripcion_exacta"],
                precio_declarado=float(r["precio_declarado"]),
                tipo=r["tipo"],
                aliases=aliases,
            )
        )
    return entries


class EffiRunner:
    """Wrapper que persiste TODO lo que el bot hace o decide.

    Uso típico:
        runner = EffiRunner(settings, dry_run=False)
        with EffiBot(settings) as bot:
            if not bot.health_check():
                raise NotLoggedInError(...)
            summary = runner.run_all(bot)
    """

    def __init__(
        self,
        settings,
        dry_run: bool = True,
        *,
        ai_validator: MiniMaxAddressValidator | None = None,
        notion_provider=None,
    ):
        self.settings = settings
        self.dry_run = dry_run
        self.orders_repo = EffiOrdersRepository(settings.db_path)
        self.audit_repo = EffiAuditLogRepository(settings.db_path)
        self.queue_repo = EffiReviewQueueRepository(settings.db_path)
        self.catalog = load_catalog(settings.db_path)
        # AI validator: si no se pasa explícito, se construye desde settings.
        # Si AI no está configurada o disabled, queda None y se usa solo regex.
        self.ai_validator = ai_validator if ai_validator is not None else build_validator_from_settings(settings)
        # Notion provider opcional: si está, después de crear la guía en Effi
        # automáticamente la creamos en Notion también (que auto-sync la baja a
        # la tabla local `guides`). Si es None, se skipea — los callers (cron y
        # UI) son responsables de wirearlo desde V04Settings.
        self.notion_provider = notion_provider
        # Buffer de notificaciones por corrida. En lugar de mandar 1 email por
        # cada escalation/error, juntamos todo y mandamos UN solo digest al final
        # de run_all. Cada item: {"type": "escalation"|"failed"|"remision_sin_guia",
        # "orden_id", "subject", "summary"}.
        self._pending_notifications: list[dict] = []

    # ── API pública ─────────────────────────────────────────────────

    def process_order(self, bot: EffiBot, scraped: ScrapedOrder) -> ProcessResult:
        orden_id = scraped.orden_id

        # Idempotencia: si ya está done, no reprocesar.
        if self.orders_repo.is_processed(orden_id):
            self.audit_repo.log("skip_already_done", orden_id=orden_id)
            return ProcessResult(orden_id=orden_id, status="skipped", reason="ya procesada")

        # Capturar estado previo para detectar cambios reales (evita re-notificar).
        previous_record = self.orders_repo.get(orden_id)
        self._previous_status = previous_record.status if previous_record else None

        # Validar dirección: regex primero, IA solo si regex no está confidente.
        addr = validate_address(scraped.direccion)
        if addr.status != AddressValidation.VALID and self.ai_validator is not None:
            addr = self._ai_second_opinion(orden_id, scraped.direccion, addr)

        # Leer detalle (productos) del modal.
        try:
            detail = bot.get_order_detail(orden_id)
        except EffiBotError as e:
            self._fail(orden_id, scraped, addr, f"no se pudo abrir modal: {e}")
            return ProcessResult(orden_id=orden_id, status="failed", error_msg=str(e))
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            self._fail(orden_id, scraped, addr, f"excepción leyendo detalle: {e}\n{tb}")
            return ProcessResult(orden_id=orden_id, status="failed", error_msg=str(e))

        self.audit_repo.log(
            "order_detail_read",
            orden_id=orden_id,
            payload={
                "productos": [(p.descripcion, p.cantidad) for p in detail.productos],
                "address_status": addr.status.value,
                "address_patterns": list(addr.matched_patterns),
            },
        )

        # Clasificar.
        classification = classify(detail.productos, self.catalog)

        # Dirección INVALID → siempre escalar, sin importar plan.
        if addr.status == AddressValidation.INVALID:
            return self._escalate(
                orden_id,
                scraped,
                addr,
                detail.productos,
                classification,
                reason="direccion_invalida",
                message=f"Dirección insuficiente: {', '.join(addr.reasons)}",
            )

        # Clasificación falló (mixto, no en catálogo, etc).
        if isinstance(classification, EscalationReason):
            return self._escalate(
                orden_id,
                scraped,
                addr,
                detail.productos,
                classification,
                reason=classification.code,
                message=classification.message,
            )

        # Dirección REVIEW → escalar pero guardamos el plan completo para que la
        # operadora pueda aprobar/rechazar con un click después.
        if addr.status == AddressValidation.REVIEW:
            return self._escalate(
                orden_id,
                scraped,
                addr,
                detail.productos,
                classification,
                reason="direccion_review",
                message=f"Dirección ambigua: {', '.join(addr.reasons)}",
                plan=classification,
            )

        # ✓ Camino feliz: dirección VALID + plan listo.
        return self._execute(orden_id, scraped, addr, detail.productos, classification)

    # ── caminos internos ─────────────────────────────────────────────

    def _execute(
        self,
        orden_id: int,
        scraped: ScrapedOrder,
        addr,
        productos,
        plan: ProcessingPlan,
    ) -> ProcessResult:
        productos_json = json.dumps(
            [{"descripcion": p.descripcion, "cantidad": p.cantidad} for p in productos],
            ensure_ascii=False,
        )

        if self.dry_run:
            self.audit_repo.log(
                "would_execute",
                orden_id=orden_id,
                payload={
                    "kind": plan.kind,
                    "valor": plan.valor_declarado,
                    "contenido_modo": plan.contenido_modo,
                    "contenido_texto": plan.contenido_texto,
                },
            )
            return ProcessResult(
                orden_id=orden_id,
                status="would_process",
                classification=plan.kind,
                address_status=addr.status.value,
                valor_declarado=plan.valor_declarado,
            )

        bot = self._current_bot
        fecha_envio = compute_fecha_envio()
        fecha_entrega = compute_fecha_entrega()

        # 1) Convertir orden → remisión.
        try:
            remision_id = bot.convert_to_remision(orden_id)
            self.audit_repo.log(
                "remision_creada",
                orden_id=orden_id,
                payload={"remision_id": remision_id},
            )
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            self._fail(orden_id, scraped, addr, f"falló convert_to_remision: {e}\n{tb}",
                       productos=productos, plan=plan)
            return ProcessResult(orden_id=orden_id, status="failed", error_msg=str(e))

        # 2) Convertir remisión → guía.
        try:
            guia_id = bot.create_guia(remision_id, plan, fecha_envio, fecha_entrega)
            self.audit_repo.log(
                "guia_creada",
                orden_id=orden_id,
                payload={"remision_id": remision_id, "guia_id": guia_id},
            )
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            # CASO CRÍTICO: la remisión SE CREÓ pero la guía no.
            # IMPORTANTE: la guía PUEDE haberse creado en Effi aunque create_guia raise
            # (si el bug está en el parse del ID post-submit). Por eso encolamos para
            # revisión humana — la operadora debe verificar el estado real en Effi.
            self.audit_repo.log(
                "create_guia_failed",
                orden_id=orden_id,
                payload={"remision_id": remision_id, "error": str(e), "traceback": tb},
                ok=False,
            )
            self.orders_repo.upsert(
                orden_id=orden_id,
                cliente=scraped.cliente,
                direccion=scraped.direccion,
                productos_json=productos_json,
                classification=plan.kind,
                valor_declarado=plan.valor_declarado,
                contenido_modo=plan.contenido_modo,
                contenido_texto=plan.contenido_texto,
                address_status=addr.status.value,
                remision_id=remision_id,
                guia_id=None,
                status="failed",
                error_msg=f"create_guia falló: {e}",
            )
            self.queue_repo.enqueue(
                orden_id,
                reason="remision_sin_guia",
                details={
                    "remision_id": remision_id,
                    "error": str(e),
                    "mensaje": (
                        "La remisión se creó. La guía PUEDE haberse creado en Effi también "
                        "(el error puede ser solo en la lectura del ID). Verificá en Effi y, "
                        "si la guía existe, usá scripts/effi_mark_done.py para registrarla."
                    ),
                },
            )
            self._pending_notifications.append({
                "type": "remision_sin_guia",
                "orden_id": orden_id,
                "summary": (
                    f"Remisión #{remision_id} creada pero create_guia falló: {e}. "
                    f"Verificar en Effi si la guía existe."
                ),
            })
            return ProcessResult(
                orden_id=orden_id, status="failed", remision_id=remision_id, error_msg=str(e)
            )

        # 3) Sync a Notion: scrape tracking number CARGO EXPRESO + crear página
        #    en Notion. Si falla, marcamos done en Effi (la guía existe ahí) y
        #    encolamos para revisión humana — la operadora reintenta el sync.
        if self.notion_provider is not None:
            self._sync_to_notion(bot, scraped, plan, productos, remision_id, guia_id, addr)

        # ✓ Todo OK.
        self.orders_repo.upsert(
            orden_id=orden_id,
            cliente=scraped.cliente,
            direccion=scraped.direccion,
            productos_json=productos_json,
            classification=plan.kind,
            valor_declarado=plan.valor_declarado,
            contenido_modo=plan.contenido_modo,
            contenido_texto=plan.contenido_texto,
            address_status=addr.status.value,
            remision_id=remision_id,
            guia_id=guia_id,
            status="done",
            error_msg=None,
        )
        return ProcessResult(
            orden_id=orden_id,
            status="done",
            classification=plan.kind,
            address_status=addr.status.value,
            valor_declarado=plan.valor_declarado,
            remision_id=remision_id,
            guia_id=guia_id,
        )

    def _sync_to_notion(
        self,
        bot: EffiBot,
        scraped: ScrapedOrder,
        plan: ProcessingPlan,
        productos: list[OrderProduct],
        remision_id: int,
        guia_id: int,
        addr: AddressResult,
    ) -> None:
        """Crea la página en Notion para la guía recién generada en Effi.

        No falla la corrida si Notion rechaza — encola para revisión humana y
        deja el orden marcado done en Effi (la guía YA existe allá, solo falta
        sincronizarla). La operadora ve el item en `/effi/queue` y decide.
        """
        from .bot import _extract_name  # helper local
        orden_id = scraped.orden_id

        # Importar la dependencia con lazy import para que tests del runner
        # que NO usan Notion no requieran vaecos_v02 disponible.
        try:
            from vaecos_v02.app.services.add_guide import add_guide  # type: ignore
        except ImportError as e:
            self.audit_repo.log(
                "notion_sync_skipped",
                orden_id=orden_id,
                payload={"reason": f"vaecos_v02 no importable: {e}"},
                ok=False,
            )
            return

        # 1) Scrape tracking number + valor a recaudar del mismo row.
        try:
            row_data = bot.read_guia_row_data(guia_id)
        except Exception as e:
            row_data = None
            self.audit_repo.log(
                "notion_tracking_scrape_failed",
                orden_id=orden_id,
                payload={"guia_id": guia_id, "error": str(e)},
                ok=False,
            )

        tracking = (row_data or {}).get("tracking")
        valor_recaudar = (row_data or {}).get("valor_recaudar")

        if not tracking:
            self._enqueue_notion_failure(
                orden_id=orden_id,
                remision_id=remision_id,
                guia_id=guia_id,
                reason="no se pudo scrapear el tracking number CARGO EXPRESO desde la tabla",
            )
            return

        # 2) Construir payload para add_guide.
        nombre_cliente = _extract_name(scraped.cliente) or scraped.cliente.strip().split("\n")[0]
        # Producto: solo la descripción (la cantidad va en su columna propia).
        # Si hay múltiples items distintos, los concatenamos con coma.
        producto_str = ", ".join(p.descripcion for p in productos)
        cantidad_total = sum(p.cantidad for p in productos)
        # Valor: preferir el "Recaudo: $X" del row Effi (es lo que CARGO EXPRESO
        # va a cobrar al cliente). Fallback a plan.valor_declarado si el scrape falló.
        valor_final = valor_recaudar if valor_recaudar is not None else plan.valor_declarado

        fields = {
            "guia": tracking,
            "cliente": nombre_cliente,
            "estado_novedad": "Sin recolectar",
            "carrier": "effi",
            "telefono": scraped.telefono,
            "producto": producto_str,
            "valor": valor_final,
            "cantidad": cantidad_total,
        }

        # 3) Intentar crear en Notion → local + audit.
        try:
            result = add_guide(
                db_path=self.settings.db_path,
                notion=self.notion_provider,
                fields=fields,
                autor="bot:effi",
            )
        except ValueError as e:
            # Validación local (ej. guía ya existe). Log + encolar pero NO romper.
            msg = str(e)
            already_exists = "ya existe" in msg.lower()
            self.audit_repo.log(
                "notion_sync_skipped" if already_exists else "notion_sync_failed",
                orden_id=orden_id,
                payload={
                    "guia": tracking,
                    "guia_id": guia_id,
                    "error": msg,
                },
                ok=already_exists,  # ok=True si ya existía (no es error real)
            )
            if not already_exists:
                self._enqueue_notion_failure(
                    orden_id=orden_id,
                    remision_id=remision_id,
                    guia_id=guia_id,
                    reason=f"validación local: {msg}",
                    tracking=tracking,
                )
            return
        except Exception as e:
            self.audit_repo.log(
                "notion_sync_failed",
                orden_id=orden_id,
                payload={
                    "guia": tracking,
                    "guia_id": guia_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(limit=3),
                },
                ok=False,
            )
            self._enqueue_notion_failure(
                orden_id=orden_id,
                remision_id=remision_id,
                guia_id=guia_id,
                reason=f"Notion rechazó: {e}",
                tracking=tracking,
            )
            return

        # ✓ Sync OK.
        self.audit_repo.log(
            "notion_sync_ok",
            orden_id=orden_id,
            payload={
                "guia": result.guia,
                "page_id": result.page_id,
                "guia_id": guia_id,
            },
        )

    def _enqueue_notion_failure(
        self,
        *,
        orden_id: int,
        remision_id: int,
        guia_id: int,
        reason: str,
        tracking: str | None = None,
    ) -> None:
        """La guía SE CREÓ en Effi pero falló el sync a Notion. La encolamos para
        que la operadora reintente desde la app (ej. importar Excel con esa guía,
        o crear manualmente desde /guides/new)."""
        details = {
            "remision_id": remision_id,
            "guia_id_effi": guia_id,
            "tracking": tracking or "(no scrapeado)",
            "reason": reason,
            "mensaje": (
                f"La guía SE CREÓ en Effi (guia_id={guia_id}) pero no se pudo "
                f"sincronizar automáticamente a Notion. Razón: {reason}. "
                "Reintentar desde /guides/new o esperar al próximo sync_guides."
            ),
        }
        self.queue_repo.enqueue(orden_id, reason="notion_sync_failed", details=details)
        self._pending_notifications.append({
            "type": "notion_sync_failed",
            "orden_id": orden_id,
            "summary": (
                f"Guía {tracking or guia_id} creada en Effi pero no sincronizada a Notion. "
                f"{reason}"
            ),
        })

    def _escalate(
        self,
        orden_id: int,
        scraped: ScrapedOrder,
        addr,
        productos,
        classification_or_plan,
        *,
        reason: str,
        message: str,
        plan: ProcessingPlan | None = None,
    ) -> ProcessResult:
        productos_json = json.dumps(
            [{"descripcion": p.descripcion, "cantidad": p.cantidad} for p in productos],
            ensure_ascii=False,
        )
        plan_for_record: ProcessingPlan | None = plan if plan else (
            classification_or_plan if isinstance(classification_or_plan, ProcessingPlan) else None
        )
        kind = "escalation" if plan_for_record is None else plan_for_record.kind

        self.orders_repo.upsert(
            orden_id=orden_id,
            cliente=scraped.cliente,
            direccion=scraped.direccion,
            productos_json=productos_json,
            classification=kind,
            valor_declarado=plan_for_record.valor_declarado if plan_for_record else None,
            contenido_modo=plan_for_record.contenido_modo if plan_for_record else None,
            contenido_texto=plan_for_record.contenido_texto if plan_for_record else None,
            address_status=addr.status.value,
            status="human_review",
            error_msg=None,
        )
        _, is_new_queue_item = self.queue_repo.enqueue(
            orden_id,
            reason=reason,
            details={
                "message": message,
                "address_reasons": list(addr.reasons),
                "address_status": addr.status.value,
                "address_patterns": list(addr.matched_patterns),
                "productos": [(p.descripcion, p.cantidad) for p in productos],
                "plan_kind": plan_for_record.kind if plan_for_record else None,
                "plan_valor": plan_for_record.valor_declarado if plan_for_record else None,
                "plan_contenido_modo": plan_for_record.contenido_modo if plan_for_record else None,
                "plan_contenido_texto": plan_for_record.contenido_texto if plan_for_record else None,
            },
        )
        self.audit_repo.log(
            "escalation",
            orden_id=orden_id,
            payload={"reason": reason, "message": message, "is_new": is_new_queue_item},
            ok=False,
        )
        # Solo notificar si es escalation NUEVA (no existía pendiente con misma razón).
        if is_new_queue_item:
            self._pending_notifications.append({
                "type": "escalation",
                "orden_id": orden_id,
                "reason": reason,
                "summary": message,
                "cliente": scraped.cliente[:200],
                "direccion": scraped.direccion[:200],
            })
        return ProcessResult(
            orden_id=orden_id,
            status="human_review",
            classification=kind,
            address_status=addr.status.value,
            reason=reason,
        )

    def _fail(
        self,
        orden_id: int,
        scraped: ScrapedOrder,
        addr,
        error_msg: str,
        *,
        productos: list[OrderProduct] | None = None,
        plan: ProcessingPlan | None = None,
    ) -> None:
        productos_json = "[]"
        if productos:
            productos_json = json.dumps(
                [{"descripcion": p.descripcion, "cantidad": p.cantidad} for p in productos],
                ensure_ascii=False,
            )
        self.orders_repo.upsert(
            orden_id=orden_id,
            cliente=scraped.cliente,
            direccion=scraped.direccion,
            productos_json=productos_json,
            classification=(plan.kind if plan else "escalation"),
            valor_declarado=(plan.valor_declarado if plan else None),
            contenido_modo=(plan.contenido_modo if plan else None),
            contenido_texto=(plan.contenido_texto if plan else None),
            address_status=addr.status.value,
            status="failed",
            error_msg=error_msg,
        )
        # Solo notificar si la orden NO estaba ya en estado 'failed' antes de esta corrida.
        was_already_failed = getattr(self, "_previous_status", None) == "failed"
        self.audit_repo.log(
            "failed",
            orden_id=orden_id,
            payload={"error": error_msg, "was_already_failed": was_already_failed},
            ok=False,
        )
        if not was_already_failed:
            self._pending_notifications.append({
                "type": "failed",
                "orden_id": orden_id,
                "summary": error_msg.splitlines()[0] if error_msg else "(sin detalle)",
            })

    # ── IA second opinion ──────────────────────────────────────────

    def _ai_second_opinion(
        self,
        orden_id: int,
        address: str,
        regex_result: AddressResult,
    ) -> AddressResult:
        """Pide veredicto IA sobre una dirección que el regex no marcó VALID.

        Si la IA dice VALID → upgrade. Si dice REVIEW/INVALID → mantiene veredicto IA
        (siempre prevalece la IA porque tiene contexto semántico). Si la API falla
        (timeout, error de red, parse), se queda con el veredicto del regex.
        """
        try:
            ai_result: AIValidationResult | None = self.ai_validator.evaluate(address)
        except Exception as e:
            self.audit_repo.log(
                "ai_address_error",
                orden_id=orden_id,
                payload={"address": address[:200], "error": str(e)},
                ok=False,
            )
            return regex_result

        if ai_result is None:
            self.audit_repo.log(
                "ai_address_no_result",
                orden_id=orden_id,
                payload={"address": address[:200], "regex_status": regex_result.status.value},
                ok=False,
            )
            return regex_result

        merged = ai_result.merge_into(regex_result)
        self.audit_repo.log(
            "ai_address_evaluation",
            orden_id=orden_id,
            payload={
                "address": address[:200],
                "regex_status": regex_result.status.value,
                "ai_status": ai_result.status.value,
                "ai_reason": ai_result.reason,
                "ai_model": ai_result.model,
                "upgrade": (regex_result.status != ai_result.status),
            },
            ok=True,
        )
        return merged

    # ── plumbing y orquestación masiva ──────────────────────────────

    _current_bot: EffiBot | None = None

    def run_all(
        self,
        bot: EffiBot,
        *,
        limit: int = 0,
        only_order: int | None = None,
        on_progress=None,
    ) -> RunSummary:
        """Procesa todas las órdenes que necesitan procesamiento (o solo una)."""
        self._current_bot = bot
        self._pending_notifications = []  # reset por corrida
        try:
            summary = RunSummary()
            orders = bot.list_orders()
            summary.total_seen = len(orders)

            candidates = [o for o in orders if o.needs_processing]
            if only_order is not None:
                candidates = [o for o in candidates if o.orden_id == only_order]
            summary.needs_processing = len(candidates)

            if limit > 0:
                candidates = candidates[:limit]

            for i, scraped in enumerate(candidates, 1):
                if on_progress:
                    on_progress(i, len(candidates), scraped.orden_id)
                result = self.process_order(bot, scraped)
                summary.details.append(result)
                if result.status in ("done", "would_process"):
                    summary.processed += 1
                elif result.status == "human_review":
                    summary.escalated += 1
                elif result.status == "failed":
                    summary.failed += 1
                elif result.status == "skipped":
                    summary.skipped += 1

            # Email digest UNA sola vez por corrida.
            self._send_run_digest(summary)
            return summary
        finally:
            self._current_bot = None

    def _send_run_digest(self, summary: RunSummary) -> None:
        """Manda un único email con el resumen de la corrida (o nada si no hubo NEWS).

        Si _pending_notifications viene vacío (todo era re-detección de items ya en cola)
        y no hubo procesadas reales, no manda email.

        Cuando `EFFI_DAILY_DIGEST_ONLY=true` (caso producción con cron horario), este
        método NO manda nada — el resumen diario lo arma `scripts/effi_daily_digest.py`
        a las 22:00 GT consultando `effi_audit_log`. Alertas críticas (sesión expirada,
        error fatal de cron) siguen mandándose inmediato desde `scripts/effi_run.py`.
        """
        import os as _os
        if _os.environ.get("EFFI_DAILY_DIGEST_ONLY", "").lower() in ("1", "true", "yes", "on"):
            return

        if not self._pending_notifications and summary.processed == 0:
            return

        mode = "DRY-RUN" if self.dry_run else "APPLY"
        subject = (
            f"Corrida Effi [{mode}]: "
            f"{summary.processed} OK · "
            f"{summary.escalated} a revisar · "
            f"{summary.failed} con error"
        )
        plain = self._build_digest_plain(summary, mode)
        html = self._build_digest_html(summary, mode)
        notify(subject=subject, body=plain, html=html)

    def _build_digest_plain(self, summary: RunSummary, mode: str) -> str:
        from datetime import datetime as _dt
        escalations = [e for e in self._pending_notifications if e["type"] == "escalation"]
        failures = [e for e in self._pending_notifications if e["type"] == "failed"]
        sin_guia = [e for e in self._pending_notifications if e["type"] == "remision_sin_guia"]
        lines = []
        lines.append(f"Corrida Effi — {mode} — {_dt.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"Procesadas OK: {summary.processed}")
        lines.append(f"En cola humana: {summary.escalated}")
        lines.append(f"Con error: {summary.failed}")
        lines.append("")
        if summary.processed:
            lines.append("--- Procesadas ---")
            for r in summary.details:
                if r.status == "done":
                    lines.append(f"  #{r.orden_id} {r.classification} ${r.valor_declarado:.2f} → remisión #{r.remision_id}, guía #{r.guia_id}")
                elif r.status == "would_process":
                    lines.append(f"  #{r.orden_id} {r.classification} ${r.valor_declarado:.2f} (dry-run)")
            lines.append("")
        if escalations:
            lines.append("--- Nuevas en cola humana ---")
            for e in escalations:
                lines.append(f"  #{e['orden_id']} [{e['reason']}] {e['summary']}")
            lines.append("")
        if failures:
            lines.append("--- Nuevos errores ---")
            for e in failures:
                lines.append(f"  #{e['orden_id']}: {e['summary']}")
            lines.append("")
        if sin_guia:
            lines.append("--- Remisiones sin guía (revisar manual) ---")
            for e in sin_guia:
                lines.append(f"  #{e['orden_id']}: {e['summary']}")
            lines.append("")
        lines.append("Detalle completo: /effi/audit y /effi/queue")
        return "\n".join(lines)

    def _build_digest_html(self, summary: RunSummary, mode: str) -> str:
        from datetime import datetime as _dt
        from html import escape as _esc
        escalations = [e for e in self._pending_notifications if e["type"] == "escalation"]
        failures = [e for e in self._pending_notifications if e["type"] == "failed"]
        sin_guia = [e for e in self._pending_notifications if e["type"] == "remision_sin_guia"]
        now_str = _dt.now().strftime("%Y-%m-%d %H:%M")

        def kpi_box(value, label, bg, fg):
            return (
                f'<td style="background:{bg};color:{fg};border-radius:6px;'
                f'padding:14px 8px;text-align:center;width:33.33%;">'
                f'<div style="font-size:26px;font-weight:700;line-height:1;">{value}</div>'
                f'<div style="font-size:11px;margin-top:6px;letter-spacing:.3px;">{label}</div>'
                f"</td>"
            )

        def section_title(emoji, text, color):
            return (
                f'<tr><td style="padding:18px 0 6px 0;">'
                f'<div style="font-size:13px;font-weight:600;color:{color};'
                f'text-transform:uppercase;letter-spacing:.5px;">{emoji} {text}</div>'
                f"</td></tr>"
            )

        def item_row(border_color, html_body):
            return (
                f'<tr><td style="padding:6px 0;">'
                f'<div style="border-left:3px solid {border_color};padding:10px 12px;'
                f'background:#fafafa;border-radius:0 4px 4px 0;font-size:14px;line-height:1.5;">'
                f'{html_body}'
                f'</div></td></tr>'
            )

        rows: list[str] = []

        if summary.processed:
            rows.append(section_title("✓", "Procesadas", "#1b5e20"))
            for r in summary.details:
                if r.status in ("done", "would_process"):
                    valor = f"${r.valor_declarado:.2f}" if r.valor_declarado else ""
                    extra = ""
                    if r.status == "done" and r.remision_id and r.guia_id:
                        extra = f'<div style="color:#666;font-size:12px;margin-top:4px;">Remisión #{r.remision_id} · Guía #{r.guia_id}</div>'
                    elif r.status == "would_process":
                        extra = '<div style="color:#888;font-size:12px;margin-top:4px;">Dry-run (no se escribió)</div>'
                    rows.append(item_row(
                        "#43a047",
                        f'<strong>Orden #{r.orden_id}</strong> · {_esc(str(r.classification or ""))} · {valor}{extra}',
                    ))

        if escalations:
            rows.append(section_title("⚠", "Nuevas en cola humana", "#e65100"))
            for e in escalations:
                cliente_html = (
                    f'<div style="color:#666;font-size:12px;margin-top:4px;">Cliente: {_esc(str(e.get("cliente") or ""))}</div>'
                    if e.get("cliente") else ""
                )
                dir_html = (
                    f'<div style="color:#666;font-size:12px;margin-top:2px;">Dirección: {_esc(str(e.get("direccion") or ""))}</div>'
                    if e.get("direccion") else ""
                )
                rows.append(item_row(
                    "#fb8c00",
                    f'<strong>Orden #{e["orden_id"]}</strong> · '
                    f'<span style="color:#e65100;">{_esc(str(e["reason"]))}</span>'
                    f'<div style="margin-top:4px;">{_esc(str(e["summary"]))}</div>'
                    f'{cliente_html}{dir_html}',
                ))

        if failures:
            rows.append(section_title("✗", "Nuevos errores", "#b71c1c"))
            for e in failures:
                rows.append(item_row(
                    "#e53935",
                    f'<strong>Orden #{e["orden_id"]}</strong>'
                    f'<div style="margin-top:4px;">{_esc(str(e["summary"]))}</div>',
                ))

        if sin_guia:
            rows.append(section_title("⚡", "Remisiones sin guía (verificar manual)", "#b71c1c"))
            for e in sin_guia:
                rows.append(item_row(
                    "#e53935",
                    f'<strong>Orden #{e["orden_id"]}</strong>'
                    f'<div style="margin-top:4px;">{_esc(str(e["summary"]))}</div>',
                ))

        sections_html = "".join(rows) if rows else (
            '<tr><td style="padding:18px;color:#888;font-size:14px;text-align:center;">'
            "Sin novedades. Revisión silenciosa completada."
            "</td></tr>"
        )

        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f0f2f5;color:#222;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f0f2f5;padding:18px 12px;">
<tr><td align="center">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:580px;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);">

<tr><td style="background:#1a1a1a;color:#fff;padding:20px 22px;">
<div style="font-size:11px;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;">VAECOS · Creador guías</div>
<div style="font-size:18px;font-weight:600;margin-top:6px;">Corrida {_esc(mode)}</div>
<div style="font-size:12px;color:#9ca3af;margin-top:4px;">{now_str}</div>
</td></tr>

<tr><td style="padding:20px 22px 4px 22px;">
<table cellpadding="0" cellspacing="6" border="0" width="100%">
<tr>
{kpi_box(summary.processed, "Procesadas", "#e8f5e9", "#1b5e20")}
{kpi_box(summary.escalated, "Cola humana", "#fff3e0", "#e65100")}
{kpi_box(summary.failed, "Errores", "#ffebee", "#b71c1c")}
</tr>
</table>
</td></tr>

<tr><td style="padding:6px 22px 18px 22px;">
<table cellpadding="0" cellspacing="0" border="0" width="100%">
{sections_html}
</table>
</td></tr>

<tr><td style="background:#fafafa;padding:14px 22px;border-top:1px solid #eee;font-size:11px;color:#888;">
Detalle completo en <strong>/effi/audit</strong> y <strong>/effi/queue</strong>.<br>
Solo se notifican <em>cambios</em>: una orden ya en cola humana no genera nuevo email hasta que cambie de estado.
</td></tr>

</table>
</td></tr>
</table>
</body></html>"""
