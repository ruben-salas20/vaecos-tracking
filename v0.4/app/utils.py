from __future__ import annotations
import re
from html import escape


# ── Effi CSV sanitization ────────────────────────────────────────────────────
_EFFI_INTERNAL_PATTERNS: list[str] = [
    r'\s*Se sugiere\s+[^.]*\.[ ]*$',
    r'^Se mantiene\s+[^.]*\.[ ]*',
]


def sanitize_csv_field(motivo: str) -> str:
    """Strip internal VAECOS phrases from motivo for Effi CSV export."""
    if not motivo:
        return ""
    result = motivo.strip()
    for pattern in _EFFI_INTERNAL_PATTERNS:
        result = re.sub(pattern, "", result)
    result = result.strip()
    result = re.sub(r'\.\s*\.', '.', result)
    return result


# ── Jinja2 filters ───────────────────────────────────────────────────────────

def fmt_ts(ts: str | None) -> str:
    """Format ISO timestamp to readable short form: '17 abr 2026, 16:12'."""
    if not ts:
        return ""
    ts = str(ts).replace("T", " ")
    try:
        date_part, time_part = ts[:10], ts[11:16]
        year, month, day = date_part.split("-")
        months = ["", "ene", "feb", "mar", "abr", "may", "jun",
                  "jul", "ago", "sep", "oct", "nov", "dic"]
        return f"{int(day)} {months[int(month)]} {year}, {time_part}"
    except Exception:  # noqa: BLE001
        return ts[:16]


def e_trunc(value: object, max_len: int = 90) -> str:
    """Escape and truncate long text; show full text on hover via title attribute."""
    s = str(value)
    if not s or s == "None":
        return ""
    if len(s) <= max_len:
        return escape(s)
    return f'<span class="cell-trunc" title="{escape(s)}">{escape(s[:max_len])}…</span>'


def fmt_duration(started: str | None, finished: str | None) -> str:
    """Format duration between two ISO timestamps as human-readable string."""
    if not started or not finished:
        return ""
    try:
        from datetime import datetime
        fmt = "%Y-%m-%d %H:%M:%S"
        s = str(started).replace("T", " ")[:19]
        f = str(finished).replace("T", " ")[:19]
        dt_start = datetime.strptime(s, fmt)
        dt_end = datetime.strptime(f, fmt)
        seconds = int((dt_end - dt_start).total_seconds())
        if seconds < 0:
            return ""
        if seconds < 60:
            return f"{seconds}s"
        minutes, secs = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours, mins = divmod(minutes, 60)
        return f"{hours}h {mins}m"
    except Exception:  # noqa: BLE001
        return ""


def fmt_duration_seconds(seconds: int | None) -> str:
    """Format integer seconds as human-readable string."""
    if seconds is None:
        return ""
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def initials_of(name: str) -> str:
    """Return up to 2 initials from a name. 'Rubén Salas' -> 'RS'."""
    if not name:
        return "?"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][:2].upper()


def format_date_short(date_str: str | None) -> str:
    """Render YYYY-MM-DD as DD/MM/YYYY. Returns '—' for None/non-parseable."""
    if not date_str:
        return "—"
    date_part = str(date_str)[:10]
    try:
        year, month, day = date_part.split("-")
        return f"{int(day):02d}/{int(month):02d}/{year}"
    except (ValueError, IndexError):
        return "—"
