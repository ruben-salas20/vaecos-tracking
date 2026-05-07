from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from typing import IO


def _normalize(s: str) -> str:
    """Lowercase, strip accents, remove non-alpha."""
    nfkd = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


def _digits_only(s: str) -> str:
    """Extract digit characters from a string. 'DPI: 53685499' -> '53685499'."""
    return "".join(c for c in s if c.isdigit())


def _parse_contenido(s: str) -> tuple[int, str]:
    """Parse 'N * PRODUCTO' into (cantidad, producto).
    Falls back to (1, original) if format doesn't match."""
    m = re.match(r"^\s*(\d+)\s*[*xX]\s*(.+?)\s*$", s)
    if m:
        try:
            return int(m.group(1)), m.group(2).strip()
        except ValueError:
            pass
    return 1, s.strip()


GUIA_HEADERS = {"guia", "noguia", "numerodeguia", "tracking", "nroguia", "guiatransportadora"}
CLIENTE_HEADERS = {"cliente", "client", "nombrecliente", "nombre", "destinatario"}
CARRIER_HEADERS = {"carrier", "transportista", "empresa"}
ID_CLIENTE_HEADERS = {"iddestinatario", "dpi", "identificacion", "cedula", "nit"}
ESTADO_HEADERS = {"estadoguiainicial", "estadoguia", "estadoinicial", "estadoactual", "estado"}
VALOR_HEADERS = {"valorrecaudo", "valor", "monto", "total"}
CONTENIDO_HEADERS = {"contenido", "producto", "productos", "detalle"}


@dataclass
class ParsedGuide:
    guia: str
    cliente: str
    carrier: str
    row_number: int
    id_cliente: str = ""        # Raw value from Excel (e.g. "DPI: 53685499")
    telefono: str = ""          # Digits only (e.g. "53685499")
    estado_inicial: str = ""
    valor: str = ""             # Numeric as string for JSON-safe session storage
    cantidad: int = 1
    producto: str = ""
    error: str | None = None


@dataclass
class ParseResult:
    new: list[ParsedGuide] = field(default_factory=list)
    skipped: list[ParsedGuide] = field(default_factory=list)
    errors: list[ParsedGuide] = field(default_factory=list)
    filename: str = ""
    raw_count: int = 0


class ExcelParser:
    def __init__(self, existing_guias: set[str]):
        self.existing_guias = {g.upper() for g in existing_guias}

    def parse(self, stream: IO, filename: str = "") -> ParseResult:
        import openpyxl
        result = ParseResult(filename=filename)
        wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        # Find header row in first 3 rows
        header_row_idx = None
        col_guia = col_cliente = col_carrier = col_id_cliente = col_estado = None
        col_valor = col_contenido = None
        for i, row in enumerate(rows[:3]):
            mapping: dict[str, int] = {}
            for j, cell in enumerate(row):
                if cell is None:
                    continue
                normalized = _normalize(str(cell)).replace(" ", "").replace(".", "").replace("-", "")
                if normalized in GUIA_HEADERS:
                    mapping["guia"] = j
                elif normalized in CLIENTE_HEADERS:
                    mapping["cliente"] = j
                elif normalized in CARRIER_HEADERS:
                    mapping["carrier"] = j
                elif normalized in ID_CLIENTE_HEADERS:
                    mapping["id_cliente"] = j
                elif normalized in ESTADO_HEADERS:
                    mapping["estado"] = j
                elif normalized in VALOR_HEADERS:
                    mapping["valor"] = j
                elif normalized in CONTENIDO_HEADERS:
                    mapping["contenido"] = j
            if "guia" in mapping:
                header_row_idx = i
                col_guia = mapping.get("guia")
                col_cliente = mapping.get("cliente")
                col_carrier = mapping.get("carrier")
                col_id_cliente = mapping.get("id_cliente")
                col_estado = mapping.get("estado")
                col_valor = mapping.get("valor")
                col_contenido = mapping.get("contenido")
                break

        if header_row_idx is None:
            result.errors.append(
                ParsedGuide("", "", "", 0, "No se encontró columna de guía en las primeras 3 filas.")
            )
            return result

        for row_num, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
            result.raw_count += 1
            guia_val = (
                str(row[col_guia]).strip()
                if col_guia is not None and col_guia < len(row) and row[col_guia] is not None
                else ""
            )
            if not guia_val or guia_val.lower() == "none":
                result.errors.append(ParsedGuide("", "", "", row_num, "Número de guía vacío."))
                continue

            cliente_val = (
                str(row[col_cliente]).strip()
                if col_cliente is not None and col_cliente < len(row) and row[col_cliente] is not None
                else ""
            )
            carrier_val = (
                str(row[col_carrier]).strip().lower()
                if col_carrier is not None and col_carrier < len(row) and row[col_carrier] is not None
                else "effi"
            )
            if not carrier_val or carrier_val == "none":
                carrier_val = "effi"
            id_cliente_val = (
                str(row[col_id_cliente]).strip()
                if col_id_cliente is not None and col_id_cliente < len(row) and row[col_id_cliente] is not None
                else ""
            )
            telefono_val = _digits_only(id_cliente_val)
            estado_val = (
                str(row[col_estado]).strip()
                if col_estado is not None and col_estado < len(row) and row[col_estado] is not None
                else ""
            )
            valor_raw = (
                row[col_valor]
                if col_valor is not None and col_valor < len(row) and row[col_valor] is not None
                else None
            )
            valor_val = ""
            if valor_raw is not None:
                try:
                    valor_val = str(float(valor_raw))
                except (ValueError, TypeError):
                    valor_val = ""
            contenido_val = (
                str(row[col_contenido]).strip()
                if col_contenido is not None and col_contenido < len(row) and row[col_contenido] is not None
                else ""
            )
            cantidad_val, producto_val = (1, "")
            if contenido_val:
                cantidad_val, producto_val = _parse_contenido(contenido_val)

            pg = ParsedGuide(
                guia=guia_val, cliente=cliente_val, carrier=carrier_val,
                row_number=row_num, id_cliente=id_cliente_val, telefono=telefono_val,
                estado_inicial=estado_val, valor=valor_val,
                cantidad=cantidad_val, producto=producto_val,
            )
            if guia_val.upper() in self.existing_guias:
                result.skipped.append(pg)
            else:
                result.new.append(pg)
                self.existing_guias.add(guia_val.upper())

        return result
