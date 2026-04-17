from __future__ import annotations

from datetime import date

from .models import EffiTrackingData, RuleDecision
from .utils import normalize_for_match


ANOMALIA_PATTERNS = [
    "cliente no quiso recibir",
    "cliente no quizo recibir",
    "nadie en casa",
    "direccion no corresponde",
    "dirección no corresponde",
    "cliente no llego al punto de encuentro",
    "cliente no llegó al punto de encuentro",
]


def decide_status(tracking: EffiTrackingData, today: date) -> RuleDecision:
    estado_actual = normalize_for_match(tracking.estado_actual or "")
    latest_status_date = _latest_status_date(tracking)
    latest_novelty_text = " ".join(
        normalize_for_match(f"{event.novelty} {event.details}")
        for event in tracking.novelty_history
    )

    if "paquete en agencia" in latest_novelty_text:
        return RuleDecision(
            estado_propuesto="Por recoger (INFORMADO)",
            motivo="Novedad de Effi indica paquete en agencia.",
            requiere_accion="Avisar al cliente que vaya a recoger",
        )

    if estado_actual == "anomalia":
        for pattern in ANOMALIA_PATTERNS:
            if pattern in latest_novelty_text:
                return RuleDecision(
                    estado_propuesto="En novedad",
                    motivo=f"Anomalia con novedad coincidente: {pattern}.",
                    requiere_accion="Hablar con cliente",
                )

    if "devolucion" in estado_actual or "devolución" in estado_actual:
        return RuleDecision(
            estado_propuesto="En Devolución",
            motivo="Effi reporta devolución.",
            requiere_accion="Sin accion",
        )

    if estado_actual == "entregado":
        return RuleDecision(
            estado_propuesto="ENTREGADA",
            motivo="Effi reporta entrega exitosa.",
            requiere_accion="Sin accion",
        )

    if estado_actual == "ruta entrega final":
        days = _days_since(latest_status_date, today)
        if days is None:
            return RuleDecision(
                estado_propuesto=None,
                motivo="RUTA ENTREGA FINAL sin fecha valida en historico.",
                requiere_accion="Revisar manualmente",
                review_needed=True,
            )
        if days > 1:
            return RuleDecision(
                estado_propuesto="Sin movimiento",
                motivo=f"RUTA ENTREGA FINAL con {days} dias sin cambio.",
                requiere_accion="Gestionar con encargado",
            )
        return RuleDecision(
            estado_propuesto="En ruta de entrega",
            motivo="RUTA ENTREGA FINAL con menos de 1 dia sin cambio.",
            requiere_accion="Monitorear",
        )

    if estado_actual == "en ruta de entrega":
        days = _days_since(latest_status_date, today)
        if days is not None and days > 1:
            return RuleDecision(
                estado_propuesto="Sin movimiento",
                motivo=f"EN RUTA DE ENTREGA con {days} dias sin cambio.",
                requiere_accion="Gestionar con encargado",
            )

    if estado_actual == "almacenado en bodega":
        days = _days_since(latest_status_date, today)
        if days is not None and days > 1:
            return RuleDecision(
                estado_propuesto="Sin movimiento",
                motivo=f"ALMACENADO EN BODEGA con {days} dias sin cambio.",
                requiere_accion="Gestionar con encargado",
            )

    if estado_actual == "sin recolectar":
        days = _days_since(latest_status_date, today)
        if days is not None and days > 1:
            return RuleDecision(
                estado_propuesto="Sin movimiento",
                motivo=f"Sin Recolectar con {days} dias sin cambio.",
                requiere_accion="Gestionar con encargado",
            )

    if tracking.estado_actual:
        return RuleDecision(
            estado_propuesto=None,
            motivo=f"Estado de Effi sin regla exacta: {tracking.estado_actual}.",
            requiere_accion="Revisar manualmente",
            review_needed=True,
        )

    return RuleDecision(
        estado_propuesto=None,
        motivo="No se pudo extraer el estado actual de Effi.",
        requiere_accion="Revisar manualmente",
        review_needed=True,
    )


def _latest_status_date(tracking: EffiTrackingData):
    dated = [event.date for event in tracking.status_history if event.date is not None]
    return max(dated) if dated else None


def _days_since(event_date, today: date) -> int | None:
    if event_date is None:
        return None
    return (today - event_date.date()).days
