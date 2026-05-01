from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class NotionClientRecord:
    page_id: str
    nombre: str
    guia: str
    estado_novedad: str
    carrier: str = "effi"
    fecha_ultimo_seguimiento: str | None = None


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
    matched_rule_id: int | None = None
    matched_rule_name: str | None = None
    days_since_last_status: int | None = None


@dataclass(frozen=True)
class Rule:
    """Data-driven rule that maps (carrier, estado, novelty, days) to a decision.

    Fields:
      - estado_match_kind: 'any' (skip) | 'equals_one_of' | 'contains_any_of'
      - estado_match_values: list[str] (lowercase, normalized for matching)
      - novelty_match_kind: 'any' | 'contains_any_of'
      - novelty_match_values: list[str] (lowercase, matched against joined novelty history)
      - days_comparator: None | 'gt' | 'gte' | 'lt' | 'lte' | 'no_date'
        * 'no_date' fires only when latest status date cannot be parsed
        * numeric comparators require a parseable date (no match if missing)
      - days_threshold: int | None (required unless comparator is None or 'no_date')
      - motivo_template: supports {days}, {estado_actual}, {estado_upper}, {matched_novelty}
    """
    id: int | None
    carrier: str
    name: str
    priority: int
    enabled: bool
    estado_match_kind: str
    estado_match_values: list[str]
    novelty_match_kind: str
    novelty_match_values: list[str]
    days_comparator: str | None
    days_threshold: int | None
    estado_propuesto: str | None
    motivo_template: str
    requiere_accion: str
    review_needed: bool
    notes: str = ""
    updated_at: str = ""
    updated_by: str = "operadora"


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
    carrier: str = "effi"


@dataclass(frozen=True)
class RunContext:
    started_at: datetime
    dry_run: bool
    selected_guides: list[str]
    run_dir: str
    today: date
