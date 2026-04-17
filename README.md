# Seguimiento VAECOS

La version operativa principal del proyecto es `v0.2/`.

`v0.2` mantiene la integracion con Notion y Effi, pero agrega arquitectura modular, SQLite, historial de corridas, analitica y una TUI para uso interactivo.

`v0.3/` es la siguiente fase en curso: un dashboard web local y de solo lectura sobre la SQLite de `v0.2`.

## Version principal

Entry point principal:

```powershell
python v0.2/cli.py
```

Comandos mas usados:

```powershell
python v0.2/cli.py --dry-run
python v0.2/cli.py --apply
python v0.2/cli.py --guides B263378877-1 --dry-run
python v0.2/cli.py tui
```

Documentacion completa:

- `v0.2/README.md`

## Dashboard v0.3

Entry point del dashboard:

```powershell
python v0.3/server.py
```

Chequeo rapido de acceso a SQLite:

```powershell
python v0.3/server.py --check
```

Documentacion completa:

- `v0.3/README.md`

## Legacy

La version `v0.1` ya no vive como codigo operativo en el root.

Se conserva solo como respaldo en:

- `backups/`

## Variables de entorno

El proyecto usa `.env` en la raiz. Para `v0.2`, las variables mas importantes son:

```env
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=e7da64fa-d6c7-47ab-bc12-d7af207f871b
NOTION_VERSION=2025-09-03
NOTION_QUERY_KIND=auto
EFFI_TIMEOUT_SECONDS=20
V02_REPORTS_DIR=v0.2/reports
V02_SAVE_RAW_HTML=false
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db
```

## Verificacion

```powershell
python -m compileall "v0.2"
python -m unittest discover -s "v0.2/tests" -v
python "v0.2/cli.py" --dry-run
```

## Notas

- `v0.2` procesa todas las guias activas por defecto si no pasas `--guides`.
- `--apply` actualiza propiedades en Notion; el historial dentro de la pagina sigue siendo manual.
- Si Effi cambia su HTML, usa `--save-raw-html` para depuracion antes de tocar reglas.
