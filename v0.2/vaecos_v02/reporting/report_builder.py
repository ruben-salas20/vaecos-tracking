from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path
from html import escape

from vaecos_v02.core.models import ProcessingResult, RunContext


def write_reports(
    run_context: RunContext,
    results: list[ProcessingResult],
    notion_stats: dict[str, int],
    missing_guides: list[str],
    run_id: int | None = None,
) -> tuple[Path, Path, Path]:
    run_dir = Path(run_context.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = run_dir / "summary.md"
    csv_path = run_dir / "results.csv"
    pdf_path = run_dir / "summary.pdf"
    _write_csv(csv_path, results)
    markdown_lines = _build_markdown_lines(
        run_context, results, notion_stats, missing_guides, run_id
    )
    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")
    _write_pdf(pdf_path, markdown_lines)
    return markdown_path, csv_path, pdf_path


def _write_csv(csv_path: Path, results: list[ProcessingResult]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cliente",
                "guia",
                "estado_notion_actual",
                "estado_effi_actual",
                "estado_propuesto",
                "resultado",
                "motivo",
                "requiere_accion",
                "actualizacion_notion",
                "error",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result.__dict__)


def _build_markdown_lines(
    run_context: RunContext,
    results: list[ProcessingResult],
    notion_stats: dict[str, int],
    missing_guides: list[str],
    run_id: int | None,
) -> list[str]:
    changed = [result for result in results if result.resultado == "changed"]
    unchanged = [result for result in results if result.resultado == "unchanged"]
    manual_review = [
        result for result in results if result.resultado == "manual_review"
    ]
    parse_errors = [result for result in results if result.resultado == "parse_error"]
    errors = [result for result in results if result.resultado == "error"]
    lines = [
        "# Informe seguimiento VAECOS v0.2",
        "",
        f"- Fecha ejecucion: {run_context.started_at.isoformat(timespec='seconds')}",
        f"- Modo dry-run: {'si' if run_context.dry_run else 'no'}",
        f"- Corrida SQLite: {run_id if run_id is not None else 'N/D'}",
        f"- Guias objetivo: {', '.join(run_context.selected_guides)}",
        f"- Directorio de corrida: `{run_context.run_dir}`",
        "",
        "## Resumen",
        "",
        "| Metrica | Valor |",
        "| --- | ---: |",
        f"| Registros leidos desde Notion | {notion_stats.get('read', 0)} |",
        f"| Registros activos revisados | {notion_stats.get('active', 0)} |",
        f"| Registros excluidos | {notion_stats.get('excluded', 0)} |",
        f"| Registros incompletos | {notion_stats.get('incomplete', 0)} |",
        f"| Guias encontradas del lote | {notion_stats.get('matched', 0)} |",
        f"| Guias faltantes en Notion | {len(missing_guides)} |",
        f"| Cambios detectados | {len(changed)} |",
        f"| Sin cambios | {len(unchanged)} |",
        f"| Revision manual | {len(manual_review)} |",
        f"| Errores de parsing HTML | {len(parse_errors)} |",
        f"| Errores tecnicos | {len(errors)} |",
        "",
    ]
    if missing_guides:
        lines.extend(["## Guias faltantes en Notion", "", "| Guia |", "| --- |"])
        lines.extend([f"| {_md_cell(guide)} |" for guide in missing_guides])
        lines.append("")
    _append_section(lines, "Cambios detectados", changed)
    _append_section(lines, "Sin cambios", unchanged)
    _append_section(lines, "Revision manual", manual_review)
    _append_section(lines, "Errores de parsing HTML", parse_errors)
    _append_section(lines, "Errores tecnicos", errors)
    return lines


def _append_section(
    lines: list[str], title: str, results: list[ProcessingResult]
) -> None:
    lines.extend([f"## {title}", ""])
    if not results:
        lines.extend(["- Sin registros", ""])
        return
    lines.extend(
        [
            "| Guia | Cliente | Notion | Effi | Propuesto | Motivo | Accion | Actualizacion Notion | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for result in results:
        lines.append(
            "| {guia} | {cliente} | {notion} | {effi} | {propuesto} | {motivo} | {accion} | {actualizacion} | {error} |".format(
                guia=_md_cell(result.guia),
                cliente=_md_cell(result.cliente),
                notion=_md_cell(result.estado_notion_actual),
                effi=_md_cell(result.estado_effi_actual or "N/D"),
                propuesto=_md_cell(result.estado_propuesto or "N/D"),
                motivo=_md_cell(result.motivo),
                accion=_md_cell(result.requiere_accion),
                actualizacion=_md_cell(result.actualizacion_notion),
                error=_md_cell(result.error),
            )
        )
    lines.append("")


def _md_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").strip()


def _write_pdf(pdf_path: Path, markdown_lines: list[str]) -> None:
    browser_path = _detect_pdf_browser()
    if browser_path:
        html = _markdown_to_html(markdown_lines)
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "summary.html"
            html_path.write_text(html, encoding="utf-8")
            command = [
                str(browser_path),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--print-to-pdf={pdf_path}",
                str(html_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and pdf_path.exists():
                return

    plain_lines = [_pdf_safe_line(line) for line in markdown_lines]
    pages = _paginate_lines(plain_lines, lines_per_page=48)

    objects: list[bytes] = []
    page_object_numbers: list[int] = []
    content_object_numbers: list[int] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")

    font_object_number = 3 + (len(pages) * 2)

    for page_lines in pages:
        content_stream = _build_pdf_stream(page_lines)
        content_object_numbers.append(len(objects) + 1)
        objects.append(
            b"<< /Length "
            + str(len(content_stream)).encode("ascii")
            + b" >>\nstream\n"
            + content_stream
            + b"\nendstream"
        )
        page_object_numbers.append(len(objects) + 1)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object_number} 0 R >> >> /Contents {content_object_numbers[-1]} 0 R >>"
            ).encode("ascii")
        )

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects[1] = f"<< /Type /Pages /Count {len(page_object_numbers)} /Kids [{kids}] >>".encode(
        "ascii"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf_path.write_bytes(_assemble_pdf(objects))


def _paginate_lines(lines: list[str], lines_per_page: int) -> list[list[str]]:
    if not lines:
        return [[""]]
    return [
        lines[index : index + lines_per_page]
        for index in range(0, len(lines), lines_per_page)
    ]


def _build_pdf_stream(lines: list[str]) -> bytes:
    parts = [b"BT", b"/F1 10 Tf", b"40 752 Td", b"14 TL"]
    for line in lines:
        escaped = (
            line.replace("\\", r"\\")
            .replace("(", r"\(")
            .replace(")", r"\)")
            .encode("latin-1", errors="replace")
        )
        parts.append(b"(" + escaped + b") Tj")
        parts.append(b"T*")
    parts.append(b"ET")
    return b"\n".join(parts)


def _assemble_pdf(objects: list[bytes]) -> bytes:
    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    current_offset = len(chunks[0])

    for index, obj in enumerate(objects, start=1):
        offsets.append(current_offset)
        chunk = f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
        chunks.append(chunk)
        current_offset += len(chunk)

    xref_offset = current_offset
    xref_lines = [
        f"xref\n0 {len(objects) + 1}\n".encode("ascii"),
        b"0000000000 65535 f \n",
    ]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n".encode("ascii"))

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return b"".join(chunks + xref_lines + [trailer])


def _pdf_safe_line(line: str) -> str:
    return line.replace("\t", "    ")


def _detect_pdf_browser() -> Path | None:
    candidates = [
        os.getenv("V02_PDF_BROWSER_PATH", "").strip(),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _markdown_to_html(lines: list[str]) -> str:
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("# "):
            blocks.append(f"<h1>{escape(stripped[2:])}</h1>")
            index += 1
            continue
        if stripped.startswith("## "):
            blocks.append(f"<h2>{escape(stripped[3:])}</h2>")
            index += 1
            continue
        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(f"<li>{_inline_markup(lines[index].strip()[2:])}</li>")
                index += 1
            blocks.append(f"<ul>{''.join(items)}</ul>")
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
            table_html, index = _parse_markdown_table(lines, index)
            blocks.append(table_html)
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            current = lines[index].strip()
            if not current or current.startswith("#") or current.startswith("- ") or current.startswith("|"):
                break
            paragraph_lines.append(current)
            index += 1
        blocks.append(f"<p>{_inline_markup(' '.join(paragraph_lines))}</p>")

    return f"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Informe seguimiento VAECOS</title>
  <style>
    @page {{ size: A4; margin: 18mm 12mm; }}
    body {{ font-family: Arial, sans-serif; color: #18202a; font-size: 11px; line-height: 1.4; }}
    h1 {{ font-size: 22px; margin: 0 0 14px; color: #0f172a; }}
    h2 {{ font-size: 15px; margin: 20px 0 8px; color: #1d4ed8; page-break-after: avoid; }}
    p {{ margin: 0 0 8px; }}
    ul {{ margin: 0 0 10px 18px; padding: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0 16px; table-layout: fixed; font-size: 9px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 7px; vertical-align: top; word-wrap: break-word; }}
    th {{ background: #e2e8f0; text-align: left; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    code {{ background: #eef2ff; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  {''.join(blocks)}
</body>
</html>
"""


def _parse_markdown_table(lines: list[str], start_index: int) -> tuple[str, int]:
    header = _split_md_row(lines[start_index])
    index = start_index + 2
    body_rows: list[list[str]] = []
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("|"):
            break
        body_rows.append(_split_md_row(lines[index]))
        index += 1

    thead = "".join(f"<th>{_inline_markup(cell)}</th>" for cell in header)
    tbody_rows = []
    for row in body_rows:
        cells = row + [""] * (len(header) - len(row))
        tbody_rows.append("<tr>" + "".join(f"<td>{_inline_markup(cell)}</td>" for cell in cells[: len(header)]) + "</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(tbody_rows)}</tbody></table>", index


def _split_md_row(line: str) -> list[str]:
    content = line.strip().strip("|")
    return [cell.replace(r"\|", "|").strip() for cell in content.split("|")]


def _inline_markup(text: str) -> str:
    parts = text.split("`")
    rendered: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            rendered.append(f"<code>{escape(part)}</code>")
        else:
            rendered.append(escape(part))
    return "".join(rendered)
