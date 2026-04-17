from __future__ import annotations

import re
from datetime import datetime
from html import unescape


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(html: str) -> str:
    no_tags = re.sub(r"<br\s*/?>", " ", html, flags=re.IGNORECASE)
    no_tags = re.sub(r"<[^>]+>", " ", no_tags)
    return normalize_space(unescape(no_tags))


def normalize_for_match(value: str) -> str:
    return normalize_space(strip_tags(value)).casefold()


def parse_date(value: str) -> datetime | None:
    cleaned = normalize_space(value)
    for fmt in (
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None
