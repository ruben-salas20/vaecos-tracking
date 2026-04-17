from __future__ import annotations

import re
from pathlib import Path
from urllib import error, request

from vaecos_v02.core.models import EffiNovedadEvent, EffiStatusEvent, EffiTrackingData
from vaecos_v02.core.utils import normalize_space, parse_date, strip_tags


class EffiProvider:
    BASE_URL = "https://effi.com.co/tracking/index/{guide}"

    def __init__(
        self, timeout_seconds: int, raw_html_dir: Path, save_raw_html: bool
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.raw_html_dir = raw_html_dir
        self.save_raw_html = save_raw_html
        if self.save_raw_html:
            self.raw_html_dir.mkdir(parents=True, exist_ok=True)

    def fetch_tracking(self, guide: str) -> EffiTrackingData:
        url = self.BASE_URL.format(guide=guide)
        req = request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                html = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            raise RuntimeError(f"Effi devolvio HTTP {exc.code} para {guide}") from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"No se pudo consultar Effi para {guide}: {exc.reason}"
            ) from exc

        raw_path: Path | None = None
        if self.save_raw_html:
            raw_path = self.raw_html_dir / f"{guide}.html"
            raw_path.write_text(html, encoding="utf-8")
        return self._parse_tracking(url, html, raw_path)

    def _parse_tracking(
        self, url: str, html: str, raw_path: Path | None
    ) -> EffiTrackingData:
        status_rows = self._extract_tracking_items(html, "HISTÓRICO DE ESTADOS")
        novedad_rows = self._extract_tracking_items(html, "HISTÓRICO DE NOVEDADES")
        return EffiTrackingData(
            url=url,
            estado_actual=self._extract_estado_actual(html),
            status_history=[
                self._parse_status_row(row) for row in status_rows if len(row) >= 2
            ],
            novelty_history=[
                self._parse_novedad_row(row) for row in novedad_rows if len(row) >= 2
            ],
            raw_html_path=str(raw_path) if raw_path else None,
        )

    def _extract_estado_actual(self, html: str) -> str | None:
        patterns = [
            r"Estado actual:</strong></span>\s*([^<]+)\s*</div>",
            r"<strong>\s*Estado actual:\s*</strong>\s*([^<]+)",
            r"Estado actual:\s*</strong>\s*([^<]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = strip_tags(match.group(1))
                if value:
                    return value
        return None

    def _extract_tracking_items(self, html: str, heading: str) -> list[list[str]]:
        heading_match = re.search(re.escape(heading), html, flags=re.IGNORECASE)
        if not heading_match:
            return []
        section_start = heading_match.end()
        next_heading_match = re.search(
            r"HISTÓRICO DE [A-ZÁÉÍÓÚ ]+", html[section_start:], flags=re.IGNORECASE
        )
        section_end = (
            section_start + next_heading_match.start()
            if next_heading_match
            else len(html)
        )
        section_html = html[section_start:section_end]
        row_matches = re.findall(
            r'<div class="tracking-item">(.*?)<div class="tracking-content">(.*?)</div>\s*</div>',
            section_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        rows: list[list[str]] = []
        for item_prefix, content_html in row_matches:
            date_match = re.search(
                r'<div class="tracking-date">(.*?)</div>',
                item_prefix,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not date_match:
                continue
            date_text = self._extract_tracking_date(date_match.group(1))
            content_text, detail_text = self._extract_tracking_content(content_html)
            row = [date_text, content_text]
            if detail_text:
                row.append(detail_text)
            rows.append(row)
        return rows

    @staticmethod
    def _extract_tracking_date(date_html: str) -> str:
        date_match = re.search(
            r"([^<]+)<span>([^<]+)</span>", date_html, flags=re.IGNORECASE | re.DOTALL
        )
        if date_match:
            return normalize_space(
                f"{strip_tags(date_match.group(1))} {strip_tags(date_match.group(2))}"
            )
        return strip_tags(date_html)

    @staticmethod
    def _extract_tracking_content(content_html: str) -> tuple[str, str]:
        span_match = re.search(
            r"^(.*?)<span>(.*?)</span>", content_html, flags=re.IGNORECASE | re.DOTALL
        )
        if span_match:
            return strip_tags(span_match.group(1)), strip_tags(span_match.group(2))
        return strip_tags(content_html), ""

    @staticmethod
    def _parse_status_row(row: list[str]) -> EffiStatusEvent:
        return EffiStatusEvent(date=parse_date(row[0]), status=row[1])

    @staticmethod
    def _parse_novedad_row(row: list[str]) -> EffiNovedadEvent:
        return EffiNovedadEvent(
            date=parse_date(row[0]),
            novelty=row[1],
            details=row[2] if len(row) > 2 else "",
        )
