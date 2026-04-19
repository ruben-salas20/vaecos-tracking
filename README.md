# Seguimiento VAECOS

VAECOS reconcilia el estado de las guias en Notion contra lo que reporta el transportista y, cuando amerita, actualiza Notion automaticamente.

El proyecto tiene dos capas:

- `v0.2/`: motor de negocio + CLI/TUI + SQLite.
- `v0.3/`: interfaz web local (ya es la interfaz principal en uso).

## Uso rapido

Arrancar la web (recomendado):

```powershell
iniciar.bat
```

o bien:

```powershell
python v0.3/server.py
```

La web cubre los casos de uso operativos:

- `/attention` — que requiere accion hoy
- `/analytics` — KPIs, tendencias, clientes problematicos
- `/rules` — editar reglas sin tocar codigo, con auditoria y vista previa
- `/run/new` — disparar una corrida en background

Actualizar a la ultima release publicada:

```powershell
actualizar.bat
```

`actualizar.bat` usa el flujo de `v0.2` pero ahora aplica el paquete completo del producto:

- `v0.2`
- `v0.3`
- scripts raiz como `iniciar.bat` y `actualizar.bat`

Tambien puedes hacerlo manualmente desde CLI:

```powershell
python v0.2/cli.py check-update
python v0.2/cli.py download-update
python v0.2/cli.py apply-update
```

## CLI (v0.2)

Entrypoint principal:

```powershell
python v0.2/cli.py
```

Comandos mas usados:

```powershell
python v0.2/cli.py --dry-run
python v0.2/cli.py --apply
python v0.2/cli.py --guides B263378877-1 --dry-run
python v0.2/cli.py tui
python v0.2/cli.py check-update
python v0.2/cli.py apply-update
```

Documentacion detallada:

- `v0.2/README.md`
- `v0.3/README.md`

## Arquitectura

- **Carriers**: abstraccion via `Carrier` Protocol en `v0.2/vaecos_v02/providers/carrier.py` + registry en `providers/carriers/`. Effi esta implementado; Guatex existe como stub. Notion provee la propiedad `Transportista` para seleccionar el carrier por guia.
- **Reglas**: tabla `rules` en SQLite evaluada por prioridad ascendente, primera coincidencia gana. Se editan desde `/rules`, cada cambio queda en `rule_history`. Al primer arranque se siembran 10 reglas default equivalentes a la logica historica.
- **Corridas**: guardadas en SQLite con `carrier`, eventos de tracking, resultados y motivos. La web consulta estos datos para `/analytics`, `/attention` y vistas por cliente/guia.

## Legacy

`v0.1` ya no vive como codigo operativo. Se conserva en `backups/` por referencia historica.

## Variables de entorno

El proyecto usa `.env` en la raiz. Variables mas importantes:

```env
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=e7da64fa-d6c7-47ab-bc12-d7af207f871b
NOTION_VERSION=2025-09-03
NOTION_QUERY_KIND=auto
EFFI_TIMEOUT_SECONDS=20
V02_REPORTS_DIR=v0.2/reports
V02_SAVE_RAW_HTML=false
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db
V02_UPDATE_REPO=ruben-salas20/vaecos-tracking
V02_UPDATE_GITHUB_TOKEN=
```

Como el repo de releases es privado, los comandos `check-update`/`download-update`/`apply-update` requieren `V02_UPDATE_GITHUB_TOKEN` con permiso `repo`.

## Verificacion

```powershell
python -m compileall "v0.2" "v0.3"
python -m unittest discover -s "v0.2/tests" -v
python "v0.3/server.py" --check
```

## Notas

- `v0.2` procesa todas las guias activas por defecto si no pasas `--guides`.
- `--apply` actualiza propiedades en Notion; el historial dentro de la pagina sigue siendo manual.
- `v0.3` crea automaticamente la carpeta `v0.2/data/` y la SQLite en el primer arranque si no existen todavia.
- Antes de cambiar una regla, usar `/rules/preview?guia=...` contra una guia real para confirmar el efecto.
- Si Effi cambia su HTML, usar `--save-raw-html` para depurar antes de tocar el parser.
- La web es local single-user hoy. Diseñada para poder mover a VPS con auth mas adelante.
