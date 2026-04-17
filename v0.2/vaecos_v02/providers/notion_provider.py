from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from vaecos_v02.core.models import NotionClientRecord


class NotionProvider:
    def __init__(
        self,
        api_key: str,
        notion_version: str,
        data_source_id: str,
        query_kind: str = "auto",
    ) -> None:
        self.api_key = api_key
        self.notion_version = notion_version
        self.data_source_id = data_source_id
        self.query_kind = query_kind

    def fetch_selected_guides(
        self, target_guides: list[str], excluded_statuses: set[str]
    ) -> tuple[list[NotionClientRecord], dict[str, int]]:
        remaining = {guide.upper() for guide in target_guides}
        found: list[NotionClientRecord] = []
        stats = {"read": 0, "active": 0, "excluded": 0, "incomplete": 0, "matched": 0}

        next_cursor: str | None = None
        while remaining:
            response = self._query_once(next_cursor)
            results = response.get("results", [])
            if not isinstance(results, list):
                break
            for page in results:
                stats["read"] += 1
                record = self._parse_record(page)
                if record is None:
                    stats["incomplete"] += 1
                    continue
                if record.estado_novedad in excluded_statuses:
                    stats["excluded"] += 1
                    continue
                stats["active"] += 1
                if record.guia.upper() in remaining:
                    found.append(record)
                    remaining.remove(record.guia.upper())
                    stats["matched"] += 1
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
        return found, stats

    def fetch_active_guides(
        self, excluded_statuses: set[str]
    ) -> tuple[list[NotionClientRecord], dict[str, int]]:
        found: list[NotionClientRecord] = []
        stats = {"read": 0, "active": 0, "excluded": 0, "incomplete": 0, "matched": 0}
        next_cursor: str | None = None
        while True:
            response = self._query_once(next_cursor)
            results = response.get("results", [])
            if not isinstance(results, list):
                break
            for page in results:
                stats["read"] += 1
                record = self._parse_record(page)
                if record is None:
                    stats["incomplete"] += 1
                    continue
                if record.estado_novedad in excluded_statuses:
                    stats["excluded"] += 1
                    continue
                found.append(record)
                stats["active"] += 1
                stats["matched"] += 1
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
        return found, stats

    def update_page_status(
        self, page_id: str, estado_novedad: str, fecha_seguimiento_iso: str
    ) -> None:
        endpoint = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "Estado novedad": {"select": {"name": estado_novedad}},
                "Fecha último seguimiento": {"date": {"start": fecha_seguimiento_iso}},
            }
        }
        self._request_json(endpoint, "PATCH", payload)

    def _query_once(self, start_cursor: str | None) -> dict[str, Any]:
        last_error: Exception | None = None
        for endpoint in self._query_endpoints():
            payload: dict[str, Any] = {"page_size": 25}
            if start_cursor:
                payload["start_cursor"] = start_cursor
            try:
                return self._request_json(endpoint, "POST", payload)
            except error.HTTPError as exc:
                last_error = RuntimeError(
                    f"Notion query failed on {endpoint}: {exc.code} {exc.reason}"
                )
                if exc.code in {400, 404} and self.query_kind == "auto":
                    continue
                raise last_error
        raise last_error or RuntimeError("Notion query failed without details")

    def _request_json(
        self, endpoint: str, method: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": self.notion_version,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError:
            raise
        except error.URLError as exc:
            raise RuntimeError(f"Notion connection error: {exc.reason}") from exc

    def _query_endpoints(self) -> list[str]:
        if self.query_kind == "database":
            return [f"https://api.notion.com/v1/databases/{self.data_source_id}/query"]
        if self.query_kind == "data_source":
            return [
                f"https://api.notion.com/v1/data_sources/{self.data_source_id}/query"
            ]
        return [
            f"https://api.notion.com/v1/data_sources/{self.data_source_id}/query",
            f"https://api.notion.com/v1/databases/{self.data_source_id}/query",
        ]

    def _parse_record(self, page: dict[str, Any]) -> NotionClientRecord | None:
        properties = page.get("properties", {})
        if not isinstance(properties, dict):
            return None
        page_id = page.get("id", "")
        nombre = self._read_title(properties.get("Nombre"))
        guia = self._read_rich_text(properties.get("No. Guía"))
        estado_novedad = self._read_select(properties.get("Estado novedad"))
        if not page_id or not nombre or not guia or not estado_novedad:
            return None
        return NotionClientRecord(
            page_id=page_id, nombre=nombre, guia=guia, estado_novedad=estado_novedad
        )

    @staticmethod
    def _read_title(prop: Any) -> str:
        if not isinstance(prop, dict):
            return ""
        items = prop.get("title", [])
        return (
            "".join(
                item.get("plain_text", "") for item in items if isinstance(item, dict)
            ).strip()
            if isinstance(items, list)
            else ""
        )

    @staticmethod
    def _read_rich_text(prop: Any) -> str:
        if not isinstance(prop, dict):
            return ""
        items = prop.get("rich_text", [])
        return (
            "".join(
                item.get("plain_text", "") for item in items if isinstance(item, dict)
            ).strip()
            if isinstance(items, list)
            else ""
        )

    @staticmethod
    def _read_select(prop: Any) -> str:
        if not isinstance(prop, dict):
            return ""
        select = prop.get("select")
        return str(select.get("name", "")).strip() if isinstance(select, dict) else ""
