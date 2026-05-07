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
        # Lazy-loaded schema for case-insensitive select option resolution.
        self._select_options: dict[str, list[str]] | None = None

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

    def update_estado_novedad(self, page_id: str, estado_novedad: str) -> None:
        """Update only the Estado novedad field — case-insensitive option resolution."""
        resolved = self._resolve_select_option("Estado novedad", estado_novedad)
        endpoint = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "Estado novedad": {"select": {"name": resolved}},
            }
        }
        try:
            self._request_json(endpoint, "PATCH", payload)
        except error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
            except Exception:
                body = ""
            detail = f"{exc.code} {exc.reason}"
            if body:
                try:
                    parsed = json.loads(body)
                    msg = parsed.get("message") or parsed.get("code") or ""
                    if msg:
                        detail = f"{detail} — {msg}"
                except Exception:
                    pass
            raise RuntimeError(f"Notion update failed: {detail}")

    def create_guide_page(
        self,
        guia: str,
        cliente: str,
        carrier: str = "effi",
        estado_novedad: str = "",
        telefono: str = "",
        valor: str = "",
        cantidad: int = 0,
        producto: str = "",
    ) -> str:
        """Create a new page in the Notion data source for a guide.
        Returns the new page_id. Raises RuntimeError on failure.

        Note: `carrier` is accepted for API symmetry but is not written to Notion
        because the data source does not have a Transportista field. The tracking
        engine reads it from a select if present, defaulting to 'effi' otherwise.
        """
        _ = carrier  # accepted but not persisted (no field in data source)

        properties: dict[str, Any] = {
            "Nombre": {"title": [{"text": {"content": cliente or guia}}]},
            "No. Guía": {"rich_text": [{"text": {"content": guia}}]},
        }
        if estado_novedad:
            resolved = self._resolve_select_option("Estado novedad", estado_novedad)
            properties["Estado novedad"] = {"select": {"name": resolved}}
        if telefono:
            try:
                properties["Teléfono"] = {"number": int(telefono)}
            except (ValueError, TypeError):
                pass
        if valor:
            try:
                properties["Valor"] = {"number": float(valor)}
            except (ValueError, TypeError):
                pass
        if cantidad:
            try:
                properties["Cant."] = {"number": int(cantidad)}
            except (ValueError, TypeError):
                pass
        if producto:
            properties["Producto"] = {
                "rich_text": [{"text": {"content": producto}}]
            }

        payload = {
            "parent": {"data_source_id": self.data_source_id},
            "properties": properties,
        }
        try:
            response = self._request_json(
                "https://api.notion.com/v1/pages", "POST", payload
            )
            return str(response.get("id", ""))
        except error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
            except Exception:
                body = ""
            detail = f"{exc.code} {exc.reason}"
            if body:
                try:
                    parsed = json.loads(body)
                    msg = parsed.get("message") or parsed.get("code") or ""
                    if msg:
                        detail = f"{detail} — {msg}"
                except Exception:
                    pass
            raise RuntimeError(f"Notion create failed: {detail}")

    def _resolve_select_option(self, field: str, value: str) -> str:
        """Match a value against the actual select options for `field`,
        case-insensitively. Returns the canonical Notion option name when
        a match is found, or the original value otherwise (which Notion
        will reject with a clear error message)."""
        target = value.strip()
        if not target:
            return target
        self._load_select_options()
        options = (self._select_options or {}).get(field, [])
        target_lower = target.lower()
        for opt in options:
            if opt.lower() == target_lower:
                return opt
        return target

    def _load_select_options(self) -> None:
        """Lazily fetch the data source schema and cache select/status options."""
        if self._select_options is not None:
            return
        try:
            req = request.Request(
                f"https://api.notion.com/v1/data_sources/{self.data_source_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": self.notion_version,
                },
                method="GET",
            )
            with request.urlopen(req, timeout=15) as response:
                schema = json.loads(response.read().decode("utf-8"))
        except Exception:
            self._select_options = {}
            return
        result: dict[str, list[str]] = {}
        for name, prop in (schema.get("properties") or {}).items():
            kind = prop.get("type")
            if kind in ("select", "status"):
                opts = prop.get(kind, {}).get("options", [])
                result[name] = [
                    str(o.get("name", "")) for o in opts if isinstance(o, dict)
                ]
        self._select_options = result

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
        carrier_raw = self._read_select(properties.get("Transportista")) or "effi"
        carrier = carrier_raw.strip().lower() or "effi"
        fecha_str = self._read_date(properties.get("Fecha \u00faltimo seguimiento"))
        telefono = self._read_number(properties.get("Tel\u00e9fono"))
        producto = self._read_rich_text(properties.get("Producto"))
        valor = self._read_number_raw(properties.get("Valor"))
        cantidad_raw = self._read_number_raw(properties.get("Cant."))
        cantidad = int(cantidad_raw) if cantidad_raw is not None else None
        return NotionClientRecord(
            page_id=page_id,
            nombre=nombre,
            guia=guia,
            estado_novedad=estado_novedad,
            carrier=carrier,
            fecha_ultimo_seguimiento=fecha_str or None,
            telefono=telefono,
            producto=producto,
            valor=valor,
            cantidad=cantidad,
        )

    def fetch_all_pages(self) -> tuple[list[NotionClientRecord], dict[str, int]]:
        """Fetch ALL pages without status filtering \u2014 used for the local guides snapshot."""
        found: list[NotionClientRecord] = []
        stats = {"read": 0, "valid": 0, "incomplete": 0}
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
                found.append(record)
                stats["valid"] += 1
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
        return found, stats

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

    @staticmethod
    def _read_number(prop: Any) -> str:
        """Extract a number property as string. Returns '' if missing/null."""
        if not isinstance(prop, dict):
            return ""
        n = prop.get("number")
        if n is None:
            return ""
        # Notion returns floats; for telephone-like ints we want a clean string.
        try:
            if float(n).is_integer():
                return str(int(n))
        except (TypeError, ValueError):
            pass
        return str(n)

    @staticmethod
    def _read_number_raw(prop: Any) -> float | None:
        """Extract a number property as float. Returns None if missing/null."""
        if not isinstance(prop, dict):
            return None
        n = prop.get("number")
        if n is None:
            return None
        try:
            return float(n)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_date(prop: Any) -> str:
        """Extract a date.start value from a Notion date property.
        Returns '' when the property is missing, null, or malformed."""
        if not isinstance(prop, dict):
            return ""
        date_obj = prop.get("date")
        if not isinstance(date_obj, dict):
            return ""
        return str(date_obj.get("start", "")).strip()
