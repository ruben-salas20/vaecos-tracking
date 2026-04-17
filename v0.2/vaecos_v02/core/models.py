from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class NotionClientRecord:
    page_id: str
    nombre: str
    guia: str
    estado_novedad: str


@dataclass(frozen=True)
class EffiStatusEvent:
    date: datetime | None
    status: str


@dataclass(frozen=True)
class EffiNovedadEvent:
    date: datetime | None
    novelty: str
    details: str


@dataclass(frozen=True)
class EffiTrackingData:
    url: str
    estado_actual: str | None
    status_history: list[EffiStatusEvent] = field(default_factory=list)
    novelty_history: list[EffiNovedadEvent] = field(default_factory=list)
    raw_html_path: str | None = None


@dataclass(frozen=True)
class RuleDecision:
    estado_propuesto: str | None
    motivo: str
    requiere_accion: str
    review_needed: bool = False


@dataclass(frozen=True)
class ProcessingResult:
    cliente: str
    guia: str
    estado_notion_actual: str
    estado_effi_actual: str | None
    estado_propuesto: str | None
    resultado: str
    motivo: str
    requiere_accion: str
    actualizacion_notion: str = ""
    error: str = ""


@dataclass(frozen=True)
class RunContext:
    started_at: datetime
    dry_run: bool
    selected_guides: list[str]
    run_dir: str
    today: date
