# VAECOS v0.2

`v0.2` es la siguiente evolucion del proyecto actual. Mantiene el flujo operativo existente, pero agrega una arquitectura modular y persistencia local en SQLite para guardar corridas, resultados y eventos de tracking.

## Objetivo

- conservar la operacion manual actual
- mantener Notion como salida operativa
- mantener Effi como fuente de tracking
- agregar memoria interna del sistema con SQLite

## Estructura

```text
v0.2/
  cli.py
  README.md
  vaecos_v02/
    app/
    core/
    providers/
    reporting/
    storage/
```

## Requisitos

- Python 3.12+
- acceso a internet
- `.env` configurado en la raiz del proyecto o dentro de `v0.2/`

No requiere instalar paquetes externos con `pip`.

## Variables de entorno

Puede reutilizar el `.env` de la raiz. Variables relevantes:

```env
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=e7da64fa-d6c7-47ab-bc12-d7af207f871b
NOTION_VERSION=2025-09-03
NOTION_QUERY_KIND=auto
EFFI_TIMEOUT_SECONDS=20
V02_REPORTS_DIR=v0.2/reports
V02_SAVE_RAW_HTML=false
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db
V02_UPDATES_DIR=v0.2/updates
V02_UPDATE_REPO=owner/repo
```

## Uso

Todas las guias activas por defecto:

```powershell
python v0.2/cli.py run --dry-run
```

Todas las guias activas de forma explicita:

```powershell
python v0.2/cli.py run --all-active --dry-run
```

Aplicar cambios reales:

```powershell
python v0.2/cli.py run --all-active --apply
```

Guardar HTML crudo de Effi para depuracion:

```powershell
python v0.2/cli.py run --all-active --dry-run --save-raw-html
```

Cada corrida genera automaticamente:

- `summary.md`
- `results.csv`
- `summary.pdf`

Si hay Microsoft Edge o Google Chrome instalados, el PDF se renderiza con tablas y formato visual real a partir del reporte Markdown. Si no hay navegador compatible, el sistema usa un PDF funcional de respaldo.

Consultar historial de corridas:

```powershell
python v0.2/cli.py runs
```

Ver estadisticas agregadas de la ultima corrida:

```powershell
python v0.2/cli.py stats
```

Ver historial de una guia:

```powershell
python v0.2/cli.py guide-history --guide B263378877-1
```

Limpiar todo el historial SQLite:

```powershell
python v0.2/cli.py clear-history --yes
```

Ver detalle de una corrida:

```powershell
python v0.2/cli.py run-details --run-id 1
```

Comparar una corrida contra la anterior:

```powershell
python v0.2/cli.py compare-runs --run-id 2
```

Abrir la TUI interactiva:

```powershell
python v0.2/cli.py tui
```

Ver version local:

```powershell
python v0.2/cli.py version
```

Buscar actualizaciones en GitHub Releases:

```powershell
python v0.2/cli.py check-update
```

Descargar la ultima actualizacion disponible:

```powershell
python v0.2/cli.py download-update
```

## SQLite

SQLite no reemplaza Notion en esta etapa.

Su funcion es guardar:

- corridas ejecutadas
- resultados por guia
- historico de estados
- historico de novedades

Esto prepara la base para trazabilidad, auditoria y crecimiento futuro.

## Subcomandos

- `run`: ejecuta el seguimiento
- `runs`: lista corridas almacenadas en SQLite
- `run-details`: muestra el detalle de una corrida
- `compare-runs`: compara una corrida contra la anterior o contra una corrida especifica
- `stats`: muestra metricas agregadas de una corrida
- `guide-history`: muestra el historial de una guia en SQLite
- `clear-history`: elimina todas las corridas y resultados guardados en SQLite
- `version`: muestra la version local de la app
- `check-update`: revisa si hay una nueva release en GitHub
- `download-update`: descarga el paquete de la ultima release disponible
- `tui`: abre un menu interactivo en terminal para usar el sistema sin memorizar comandos

## Modos reales

El sistema queda con dos modos de uso:

- `todas las activas`: es el comportamiento por defecto si no pasas `--guides`
- `guias especificas`: solo si pasas `--guides`

## TUI

La TUI es un menu de terminal simple, sin dependencias externas, pensado para facilitar el uso operativo de `v0.2`.

Desde la TUI puedes:

- ejecutar todas las activas en `dry-run`
- aplicar cambios reales a todas las activas
- ejecutar guias especificas
- ver corridas guardadas en SQLite
- ver detalle de una corrida
- comparar corridas
- ver estadisticas de una corrida
- ver historial de una guia
- limpiar el historial SQLite
- ver la version local
- buscar actualizaciones
- descargar una actualizacion

## Actualizaciones

`v0.2` puede consultar GitHub Releases para saber si hay una nueva version y descargar el paquete `.zip` mas reciente.

Configura en `.env`:

```env
V02_UPDATE_REPO=owner/repo
V02_UPDATES_DIR=v0.2/updates
```

Notas:

- `V02_UPDATE_REPO` debe ir en formato `owner/repo`
- `check-update` solo consulta la ultima release publicada
- `download-update` descarga el primer asset `.zip` de la release si existe; si no, usa el `zipball` de GitHub
- la actualizacion descargada no se aplica sola todavia; se deja en `V02_UPDATES_DIR` para reemplazo controlado

## Tests

`v0.2` incluye pruebas automáticas con `unittest` para reglas y parser de Effi.

Ejecutar:

```powershell
python -m unittest discover -s v0.2/tests -v
```
