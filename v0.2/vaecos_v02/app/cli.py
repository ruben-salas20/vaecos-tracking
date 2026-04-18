from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vaecos_v02.app.config import load_settings
from vaecos_v02.app.services.run_tracking import (
    clear_history_data,
    compare_runs_history,
    execute_tracking,
    guide_history,
    list_runs_history,
    run_details_history,
    stats_history,
)
from vaecos_v02.app.services.update_service import (
    apply_update,
    check_for_updates,
    download_update,
    version_text,
)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[1:]
    known_commands = {
        "run",
        "runs",
        "run-details",
        "compare-runs",
        "stats",
        "guide-history",
        "clear-history",
        "version",
        "check-update",
        "download-update",
        "apply-update",
        "tui",
    }
    if not argv or argv[0] not in known_commands:
        argv = ["run", *argv]

    parser = argparse.ArgumentParser(description="Seguimiento de guias VAECOS v0.2")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Ejecuta seguimiento")
    run_parser.add_argument("--guides", nargs="*", help="Guias especificas a procesar")
    run_parser.add_argument(
        "--all-active",
        action="store_true",
        help="Procesa todas las guias activas de Notion",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Ejecuta sin escribir en Notion",
    )
    run_parser.add_argument(
        "--apply", action="store_true", help="Aplica en Notion los cambios detectados"
    )
    run_parser.add_argument("--output-dir", help="Directorio base para reportes")
    run_parser.add_argument(
        "--save-raw-html",
        action="store_true",
        help="Guarda HTML crudo de Effi para depuracion",
    )

    runs_parser = subparsers.add_parser(
        "runs", help="Lista corridas guardadas en SQLite"
    )
    runs_parser.add_argument(
        "--limit", type=int, default=20, help="Cantidad maxima de corridas a listar"
    )

    details_parser = subparsers.add_parser(
        "run-details", help="Muestra el detalle de una corrida"
    )
    details_parser.add_argument(
        "--run-id", type=int, required=True, help="ID de corrida"
    )

    compare_parser = subparsers.add_parser(
        "compare-runs",
        help="Compara una corrida contra la anterior o una corrida especifica",
    )
    compare_parser.add_argument(
        "--run-id", type=int, required=True, help="ID de corrida actual"
    )
    compare_parser.add_argument(
        "--previous-run-id", type=int, help="ID de corrida anterior a comparar"
    )

    stats_parser = subparsers.add_parser(
        "stats", help="Muestra estadisticas agregadas de una corrida"
    )
    stats_parser.add_argument(
        "--run-id", type=int, help="ID de corrida; por defecto usa la ultima"
    )

    guide_parser = subparsers.add_parser(
        "guide-history", help="Muestra el historial de una guia en SQLite"
    )
    guide_parser.add_argument("--guide", required=True, help="Numero de guia")
    guide_parser.add_argument(
        "--limit", type=int, default=10, help="Cantidad maxima de registros"
    )

    clear_parser = subparsers.add_parser(
        "clear-history", help="Limpia todas las corridas almacenadas en SQLite"
    )
    clear_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma la limpieza sin pedir aprobacion adicional",
    )

    subparsers.add_parser("version", help="Muestra la version local de v0.2")
    subparsers.add_parser(
        "check-update", help="Consulta si hay una nueva release en GitHub"
    )
    subparsers.add_parser(
        "download-update", help="Descarga la ultima actualizacion disponible"
    )
    subparsers.add_parser(
        "apply-update",
        help="Aplica la actualizacion descargada (preserva .env, SQLite y reportes)",
    )

    subparsers.add_parser("tui", help="Abre una interfaz de terminal interactiva")

    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    base_dir = Path(__file__).resolve().parents[2]
    settings = load_settings(base_dir)

    command = args.command or "run"
    if command == "runs":
        print(list_runs_history(settings.sqlite_db_path, limit=args.limit))
        return 0
    if command == "run-details":
        print(run_details_history(settings.sqlite_db_path, run_id=args.run_id))
        return 0
    if command == "compare-runs":
        print(
            compare_runs_history(
                settings.sqlite_db_path,
                run_id=args.run_id,
                previous_run_id=args.previous_run_id,
            )
        )
        return 0
    if command == "stats":
        print(stats_history(settings.sqlite_db_path, run_id=args.run_id))
        return 0
    if command == "guide-history":
        print(
            guide_history(
                settings.sqlite_db_path, guia=args.guide.strip(), limit=args.limit
            )
        )
        return 0
    if command == "clear-history":
        if not args.yes:
            raise SystemExit(
                "Este comando borra todo el historial SQLite. Ejecuta de nuevo con --yes para confirmar."
            )
        print(clear_history_data(settings.sqlite_db_path))
        return 0
    if command == "version":
        print(version_text(settings))
        return 0
    if command == "check-update":
        print(check_for_updates(settings))
        return 0
    if command == "download-update":
        print(download_update(settings))
        return 0
    if command == "apply-update":
        print(apply_update(settings, base_dir))
        return 0
    if command == "tui":
        if not settings.notion_api_key or not settings.notion_data_source_id:
            raise SystemExit(
                "Faltan NOTION_API_KEY o NOTION_DATA_SOURCE_ID en el entorno o en .env"
            )
        return start_tui(settings)

    if not settings.notion_api_key or not settings.notion_data_source_id:
        raise SystemExit(
            "Faltan NOTION_API_KEY o NOTION_DATA_SOURCE_ID en el entorno o en .env"
        )

    selected_guides = [
        guide.strip()
        for guide in ((getattr(args, "guides", None)) or [])
        if guide.strip()
    ]
    markdown_path, csv_path, pdf_path = execute_tracking(
        settings=settings,
        selected_guides=selected_guides,
        all_active=getattr(args, "all_active", False) or not selected_guides,
        dry_run=not getattr(args, "apply", False),
        output_dir=getattr(args, "output_dir", None),
        save_raw_html=getattr(args, "save_raw_html", False),
    )
    print(f"Informe generado: {markdown_path}")
    print(f"CSV generado: {csv_path}")
    print(f"PDF generado: {pdf_path}")
    return 0


def start_tui(settings) -> int:
    while True:
        _clear_screen()
        print("VAECOS v0.2 - Menu")
        print()
        print("1. Ejecutar todas las activas en dry-run")
        print("2. Aplicar cambios a todas las activas")
        print("3. Ejecutar guias especificas")
        print("4. Ver corridas guardadas")
        print("5. Ver detalle de una corrida")
        print("6. Comparar corridas")
        print("7. Ver estadisticas de una corrida")
        print("8. Ver historial de una guia")
        print("9. Limpiar historial SQLite")
        print("10. Version de la app")
        print("11. Buscar actualizaciones")
        print("12. Descargar actualizacion")
        print("13. Instalar actualizacion descargada")
        print("14. Salir")
        print()

        choice = input("Selecciona una opcion: ").strip()
        if choice == "1":
            _run_and_pause(settings, None, True, True, False)
        elif choice == "2":
            if _confirm("Esto escribira cambios reales en Notion. Continuar"):
                _run_and_pause(settings, None, True, False, False)
        elif choice == "3":
            guides = _prompt_guides()
            if guides:
                dry_run = not _confirm("Quieres aplicar cambios reales en Notion")
                save_raw_html = _confirm("Guardar HTML crudo de Effi para esta corrida")
                _run_and_pause(settings, guides, False, dry_run, save_raw_html)
        elif choice == "4":
            limit = _prompt_int("Cantidad de corridas a mostrar", default=10)
            if limit is not None:
                _show_text_and_pause(
                    list_runs_history(settings.sqlite_db_path, limit=limit)
                )
        elif choice == "5":
            run_id = _prompt_int("Run ID", default=None)
            if run_id is not None:
                _show_text_and_pause(
                    run_details_history(settings.sqlite_db_path, run_id=run_id)
                )
        elif choice == "6":
            run_id = _prompt_int("Run ID actual", default=None)
            if run_id is None:
                continue
            previous_run_id = _prompt_int(
                "Run ID anterior (enter para usar la anterior automaticamente)",
                default=None,
                allow_empty=True,
            )
            _show_text_and_pause(
                compare_runs_history(
                    settings.sqlite_db_path,
                    run_id=run_id,
                    previous_run_id=previous_run_id,
                )
            )
        elif choice == "7":
            run_id = _prompt_int(
                "Run ID (enter para usar la ultima corrida)",
                default=None,
                allow_empty=True,
            )
            _show_text_and_pause(stats_history(settings.sqlite_db_path, run_id=run_id))
        elif choice == "8":
            guide = input("Numero de guia: ").strip()
            if guide:
                limit = _prompt_int("Cantidad maxima de registros", default=10)
                if limit is not None:
                    _show_text_and_pause(
                        guide_history(settings.sqlite_db_path, guia=guide, limit=limit)
                    )
        elif choice == "9":
            if _confirm("Esto eliminara todas las corridas y resultados guardados en SQLite. Continuar"):
                _show_text_and_pause(clear_history_data(settings.sqlite_db_path))
        elif choice == "10":
            _show_text_and_pause(version_text(settings))
        elif choice == "11":
            _show_text_and_pause(check_for_updates(settings))
        elif choice == "12":
            if _confirm("Intentar descargar la ultima actualizacion disponible desde GitHub"):
                _show_text_and_pause(download_update(settings))
        elif choice == "13":
            if _confirm("Instalar la actualizacion descargada (se hara un backup automatico del codigo actual)"):
                _show_text_and_pause(apply_update(settings, Path(__file__).resolve().parents[2]))
        elif choice == "14":
            return 0
        else:
            _pause("Opcion no valida. Presiona Enter para continuar.")


def _run_and_pause(
    settings, selected_guides, all_active, dry_run, save_raw_html
) -> None:
    try:
        markdown_path, csv_path, pdf_path = execute_tracking(
            settings=settings,
            selected_guides=selected_guides,
            all_active=all_active,
            dry_run=dry_run,
            output_dir=None,
            save_raw_html=save_raw_html,
        )
        _pause(
            "Corrida completada.\n"
            f"Informe: {markdown_path}\n"
            f"CSV: {csv_path}\n\n"
            f"PDF: {pdf_path}\n\n"
            "Presiona Enter para continuar."
        )
    except Exception as exc:  # noqa: BLE001
        _pause(f"Ocurrio un error:\n{exc}\n\nPresiona Enter para continuar.")


def _show_text_and_pause(text: str) -> None:
    _clear_screen()
    print(text)
    print()
    input("Presiona Enter para volver al menu...")


def _prompt_guides() -> list[str]:
    raw = input("Ingresa una o varias guias separadas por coma: ").strip()
    if not raw:
        return []
    return [guide.strip() for guide in raw.split(",") if guide.strip()]


def _prompt_int(
    prompt: str, default: int | None, allow_empty: bool = False
) -> int | None:
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw:
        if allow_empty:
            return None
        return default
    try:
        return int(raw)
    except ValueError:
        _pause("Valor invalido. Presiona Enter para continuar.")
        return None


def _confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [s/N]: ").strip().lower()
    return answer in {"s", "si", "y", "yes"}


def _pause(message: str) -> None:
    print()
    input(message)


def _clear_screen() -> None:
    print("\n" * 40)
