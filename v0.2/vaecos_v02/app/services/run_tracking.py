from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vaecos_v02.app.config import Settings
from vaecos_v02.core.models import ProcessingResult, RunContext
from vaecos_v02.core.rules import decide_status
from vaecos_v02.providers.effi_provider import EffiProvider
from vaecos_v02.providers.notion_provider import NotionProvider
from vaecos_v02.reporting.report_builder import write_reports
from vaecos_v02.storage.db import clear_history, connect, init_db
from vaecos_v02.storage.repositories import RunRepository


def execute_tracking(
    settings: Settings,
    selected_guides: list[str] | None,
    all_active: bool,
    dry_run: bool,
    output_dir: str | None,
    save_raw_html: bool,
) -> tuple[Path, Path, Path]:
    started_at = datetime.now()
    output_base_dir = Path(output_dir) if output_dir else settings.reports_dir
    run_dir = output_base_dir / started_at.strftime("%Y-%m-%d_%H-%M-%S")

    notion = NotionProvider(
        api_key=settings.notion_api_key,
        notion_version=settings.notion_version,
        data_source_id=settings.notion_data_source_id,
        query_kind=settings.notion_query_kind,
    )
    if all_active:
        records, notion_stats = notion.fetch_active_guides(settings.excluded_statuses)
        guides = [record.guia for record in records]
        missing_guides: list[str] = []
    else:
        guides = selected_guides or []
        records, notion_stats = notion.fetch_selected_guides(
            guides, settings.excluded_statuses
        )
        record_map_tmp = {record.guia.upper(): record for record in records}
        missing_guides = [
            guide for guide in guides if guide.upper() not in record_map_tmp
        ]

    run_context = RunContext(
        started_at=started_at,
        dry_run=dry_run,
        selected_guides=guides,
        run_dir=str(run_dir),
        today=started_at.date(),
    )
    effi = EffiProvider(
        settings.effi_timeout_seconds,
        run_dir / "raw_html",
        save_raw_html or settings.save_raw_html,
    )

    connection = connect(settings.sqlite_db_path)
    init_db(connection)
    repository = RunRepository(connection)
    run_id = repository.create_run(started_at, dry_run)

    record_map = {record.guia.upper(): record for record in records}
    results: list[ProcessingResult] = []
    for guide in guides:
        record = record_map.get(guide.upper())
        if record is None:
            result = ProcessingResult(
                cliente="N/D",
                guia=guide,
                estado_notion_actual="N/D",
                estado_effi_actual=None,
                estado_propuesto=None,
                resultado="error",
                motivo="La guia no fue encontrada dentro de los registros activos de Notion.",
                requiere_accion="Revisar manualmente",
                actualizacion_notion="No actualizado",
                error="Guia no encontrada en Notion",
            )
            repository.save_result(run_id, result)
            results.append(result)
            continue
        try:
            tracking = effi.fetch_tracking(guide)
            repository.save_tracking(run_id, guide, tracking)
            decision = decide_status(tracking, run_context.today)
            if decision.review_needed:
                resultado = "manual_review"
            elif decision.estado_propuesto == record.estado_novedad:
                resultado = "unchanged"
            else:
                resultado = "changed"

            actualizacion_notion = "No aplica"
            if resultado == "changed":
                if dry_run:
                    actualizacion_notion = "Pendiente por dry-run"
                else:
                    notion.update_page_status(
                        record.page_id,
                        decision.estado_propuesto or record.estado_novedad,
                        run_context.today.isoformat(),
                    )
                    actualizacion_notion = "Actualizado"

            result = ProcessingResult(
                cliente=record.nombre,
                guia=record.guia,
                estado_notion_actual=record.estado_novedad,
                estado_effi_actual=tracking.estado_actual,
                estado_propuesto=decision.estado_propuesto,
                resultado=resultado,
                motivo=decision.motivo,
                requiere_accion=decision.requiere_accion,
                actualizacion_notion=actualizacion_notion,
            )
        except Exception as exc:  # noqa: BLE001
            result = ProcessingResult(
                cliente=record.nombre,
                guia=record.guia,
                estado_notion_actual=record.estado_novedad,
                estado_effi_actual=None,
                estado_propuesto=None,
                resultado="error",
                motivo="Error durante la consulta o el parsing de Effi.",
                requiere_accion="Revisar manualmente",
                actualizacion_notion="No actualizado",
                error=str(exc),
            )
        repository.save_result(run_id, result)
        results.append(result)

    repository.finalize_run(run_id, datetime.now(), results)
    markdown_path, csv_path, pdf_path = write_reports(
        run_context, results, notion_stats, missing_guides, run_id=run_id
    )
    connection.close()
    return markdown_path, csv_path, pdf_path


def list_runs_history(db_path: Path, limit: int) -> str:
    connection = connect(db_path)
    init_db(connection)
    repository = RunRepository(connection)
    rows = repository.list_runs(limit=limit)
    connection.close()

    if not rows:
        return "No hay corridas registradas en SQLite."

    lines = [
        "| Run ID | Inicio | Fin | Modo | Procesadas | Cambios | Sin cambios | Manual | Errores |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {id} | {started_at} | {finished_at} | {mode} | {total_processed} | {total_changed} | {total_unchanged} | {total_manual_review} | {total_error} |".format(
                **{
                    key: (row[key] if row[key] is not None else "")
                    for key in row.keys()
                }
            )
        )
    return "\n".join(lines)


def run_details_history(db_path: Path, run_id: int) -> str:
    connection = connect(db_path)
    init_db(connection)
    repository = RunRepository(connection)
    run_row = repository.get_run(run_id)
    result_rows = repository.get_results_for_run(run_id)
    connection.close()

    if run_row is None:
        return f"No existe la corrida {run_id}."

    lines = [
        f"# Corrida {run_row['id']}",
        "",
        f"- Inicio: {run_row['started_at']}",
        f"- Fin: {run_row['finished_at'] or 'N/D'}",
        f"- Modo: {run_row['mode']}",
        f"- Procesadas: {run_row['total_processed']}",
        f"- Cambios: {run_row['total_changed']}",
        f"- Sin cambios: {run_row['total_unchanged']}",
        f"- Revision manual: {run_row['total_manual_review']}",
        f"- Errores: {run_row['total_error']}",
        "",
    ]

    if not result_rows:
        lines.append("Sin resultados asociados.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Guia | Cliente | Resultado | Notion | Effi | Propuesto | Actualizacion | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in result_rows:
        lines.append(
            "| {guia} | {cliente} | {resultado} | {estado_notion_actual} | {estado_effi_actual} | {estado_propuesto} | {actualizacion_notion} | {error} |".format(
                guia=_md(str(row["guia"])),
                cliente=_md(str(row["cliente"])),
                resultado=_md(str(row["resultado"])),
                estado_notion_actual=_md(str(row["estado_notion_actual"] or "N/D")),
                estado_effi_actual=_md(str(row["estado_effi_actual"] or "N/D")),
                estado_propuesto=_md(str(row["estado_propuesto"] or "N/D")),
                actualizacion_notion=_md(str(row["actualizacion_notion"] or "")),
                error=_md(str(row["error"] or "")),
            )
        )
    return "\n".join(lines)


def compare_runs_history(
    db_path: Path, run_id: int, previous_run_id: int | None = None
) -> str:
    connection = connect(db_path)
    init_db(connection)
    repository = RunRepository(connection)
    current_run = repository.get_run(run_id)
    if current_run is None:
        connection.close()
        return f"No existe la corrida {run_id}."

    if previous_run_id is None:
        previous_run_id = repository.get_previous_run_id(run_id)
    if previous_run_id is None:
        connection.close()
        return f"La corrida {run_id} no tiene una corrida anterior para comparar."

    previous_run = repository.get_run(previous_run_id)
    if previous_run is None:
        connection.close()
        return f"No existe la corrida anterior {previous_run_id}."

    current_results = {
        row["guia"]: row for row in repository.get_results_for_run(run_id)
    }
    previous_results = {
        row["guia"]: row for row in repository.get_results_for_run(previous_run_id)
    }
    connection.close()

    all_guides = sorted(set(current_results) | set(previous_results))
    changed_rows: list[str] = []
    for guia in all_guides:
        current = current_results.get(guia)
        previous = previous_results.get(guia)
        prev_resultado = previous["resultado"] if previous else "N/D"
        prev_propuesto = previous["estado_propuesto"] if previous else "N/D"
        curr_resultado = current["resultado"] if current else "N/D"
        curr_propuesto = current["estado_propuesto"] if current else "N/D"
        if prev_resultado != curr_resultado or prev_propuesto != curr_propuesto:
            changed_rows.append(
                "| {guia} | {prev_resultado} | {prev_propuesto} | {curr_resultado} | {curr_propuesto} |".format(
                    guia=_md(str(guia)),
                    prev_resultado=_md(str(prev_resultado or "N/D")),
                    prev_propuesto=_md(str(prev_propuesto or "N/D")),
                    curr_resultado=_md(str(curr_resultado or "N/D")),
                    curr_propuesto=_md(str(curr_propuesto or "N/D")),
                )
            )

    lines = [
        f"# Comparacion de corridas {previous_run_id} -> {run_id}",
        "",
        f"- Corrida anterior: {previous_run['started_at']} ({previous_run['mode']})",
        f"- Corrida actual: {current_run['started_at']} ({current_run['mode']})",
        "",
    ]
    if not changed_rows:
        lines.append(
            "No hay diferencias de resultado o estado propuesto entre ambas corridas."
        )
        return "\n".join(lines)

    lines.extend(
        [
            "| Guia | Resultado anterior | Propuesto anterior | Resultado actual | Propuesto actual |",
            "| --- | --- | --- | --- | --- |",
            *changed_rows,
        ]
    )
    return "\n".join(lines)


def stats_history(db_path: Path, run_id: int | None = None) -> str:
    connection = connect(db_path)
    init_db(connection)
    repository = RunRepository(connection)
    resolved_run_id = run_id if run_id is not None else repository.get_latest_run_id()
    if resolved_run_id is None:
        connection.close()
        return "No hay corridas registradas en SQLite."

    run_row = repository.get_run(resolved_run_id)
    if run_row is None:
        connection.close()
        return f"No existe la corrida {resolved_run_id}."

    result_counts = repository.get_result_counts_for_run(resolved_run_id)
    status_counts = repository.get_proposed_status_counts_for_run(resolved_run_id)
    motivo_counts = repository.get_top_motivos_for_run(resolved_run_id, limit=10)
    connection.close()

    lines = [
        f"# Estadisticas de corrida {run_row['id']}",
        "",
        f"- Inicio: {run_row['started_at']}",
        f"- Modo: {run_row['mode']}",
        f"- Procesadas: {run_row['total_processed']}",
        "",
        "## Resultados",
        "",
        "| Resultado | Total |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {_md(str(row['resultado']))} | {row['total']} |" for row in result_counts
    )

    lines.extend(
        [
            "",
            "## Estados propuestos",
            "",
            "| Estado propuesto | Total |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| {_md(str(row['estado_propuesto']))} | {row['total']} |"
        for row in status_counts
    )

    lines.extend(
        [
            "",
            "## Motivos mas frecuentes",
            "",
            "| Motivo | Total |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| {_md(str(row['motivo']))} | {row['total']} |" for row in motivo_counts
    )
    return "\n".join(lines)


def guide_history(db_path: Path, guia: str, limit: int = 10) -> str:
    connection = connect(db_path)
    init_db(connection)
    repository = RunRepository(connection)
    rows = repository.get_guide_history(guia, limit=limit)
    connection.close()

    if not rows:
        return f"No hay historial almacenado para la guia {guia}."

    lines = [
        f"# Historial de guia {guia}",
        "",
        "| Run ID | Inicio | Modo | Resultado | Notion | Effi | Propuesto | Actualizacion | Error |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {run_id} | {started_at} | {mode} | {resultado} | {estado_notion_actual} | {estado_effi_actual} | {estado_propuesto} | {actualizacion_notion} | {error} |".format(
                run_id=row["run_id"],
                started_at=_md(str(row["started_at"])),
                mode=_md(str(row["mode"])),
                resultado=_md(str(row["resultado"])),
                estado_notion_actual=_md(str(row["estado_notion_actual"] or "N/D")),
                estado_effi_actual=_md(str(row["estado_effi_actual"] or "N/D")),
                estado_propuesto=_md(str(row["estado_propuesto"] or "N/D")),
                actualizacion_notion=_md(str(row["actualizacion_notion"] or "")),
                error=_md(str(row["error"] or "")),
            )
        )
    return "\n".join(lines)


def clear_history_data(db_path: Path) -> str:
    connection = connect(db_path)
    init_db(connection)
    clear_history(connection)
    connection.close()
    return f"Historial SQLite limpiado: {db_path}"


def _md(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").strip()
