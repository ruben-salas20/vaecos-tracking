# Checklist

## Estado actual del proyecto

### v0.1
- Ya no existe como código operativo en el root.
- Se conserva solo como respaldo en `backups/`.
- No debe retomarse como base de trabajo salvo que se necesite restaurar o comparar algo histórico.

### v0.2
- Es la versión operativa principal.
- Ya hace todo el flujo de negocio principal:
  - leer Notion
  - consultar Effi
  - aplicar reglas
  - generar reportes
  - actualizar propiedades en Notion con `--apply`
- Tiene arquitectura modular.
- Tiene SQLite para histórico.
- Tiene CLI y TUI.
- Tiene exportación a:
  - `summary.md`
  - `results.csv`
  - `summary.pdf`
- Tiene consultas históricas:
  - `runs`
  - `run-details`
  - `compare-runs`
  - `stats`
  - `guide-history`
- Tiene limpieza de historial:
  - `clear-history --yes`
- Tiene sistema base de versionado y updates por GitHub Releases:
  - `version`
  - `check-update`
  - `download-update`

### v0.3
- Ya existe como aplicación web local.
- Ya no es solo dashboard de lectura: ya puede disparar corridas usando la lógica de `v0.2`.
- Lee la SQLite de `v0.2`.
- Tiene rutas principales:
  - `/`
  - `/runs`
  - `/run/new`
  - `/runs/<id>`
  - `/guides/<guia>`

## Estructura actual importante

### Root
- `README.md`: documentación raíz, apunta a `v0.2` como versión principal y a `v0.3` como fase web.
- `AGENTS.md`: instrucciones compactas para futuras sesiones.
- `.env`: configuración local real.
- `.env.example`: plantilla de configuración.
- `proceso_seguimiento_guias_VAECOS.md`: documento histórico de reglas/proceso.
- `backups/`: backups históricos de `v0.1` y `v0.2`.

### v0.2
- `v0.2/cli.py`: entrypoint.
- `v0.2/version.json`: versión local actual.
- `v0.2/vaecos_v02/app/cli.py`: CLI/TUI.
- `v0.2/vaecos_v02/app/config.py`: carga de config y variables de entorno.
- `v0.2/vaecos_v02/app/services/run_tracking.py`: flujo principal.
- `v0.2/vaecos_v02/app/services/update_service.py`: check/download de releases.
- `v0.2/vaecos_v02/core/rules.py`: reglas de negocio.
- `v0.2/vaecos_v02/providers/notion_provider.py`: integración Notion.
- `v0.2/vaecos_v02/providers/effi_provider.py`: scraping/parsing Effi.
- `v0.2/vaecos_v02/reporting/report_builder.py`: Markdown/CSV/PDF.
- `v0.2/vaecos_v02/storage/db.py`: schema SQLite.
- `v0.2/vaecos_v02/storage/repositories.py`: queries SQLite.
- `v0.2/tests/`: tests con `unittest`.

### v0.3
- `v0.3/server.py`: entrypoint web.
- `v0.3/vaecos_v03/app.py`: servidor HTTP y rutas.
- `v0.3/vaecos_v03/storage.py`: lecturas de SQLite para web.
- `v0.3/vaecos_v03/render.py`: shell y componentes HTML.

## Estado de GitHub / releases

- Repo privado creado:
  - `ruben-salas20/vaecos-tracking`
- Remoto configurado en `origin`.
- Releases publicadas:
  - `v0.2.0`
  - `v0.2.1`
- Asset de release usado para updates:
  - `.zip` publicado manualmente en GitHub Releases

## Configuración importante de updates

### Variables relevantes
- `V02_UPDATE_REPO=ruben-salas20/vaecos-tracking`
- `V02_UPDATES_DIR=v0.2/updates`
- `V02_UPDATE_GITHUB_TOKEN=`

### Nota crítica
- Como el repo es privado, `check-update` y `download-update` requieren `V02_UPDATE_GITHUB_TOKEN` con permisos `repo`.
- Sin token, GitHub responde `404` aunque la release exista.

## Comandos operativos actuales

### v0.2 principales
- `python v0.2/cli.py --dry-run`
- `python v0.2/cli.py --apply`
- `python v0.2/cli.py --guides B263378877-1 --dry-run`
- `python v0.2/cli.py runs`
- `python v0.2/cli.py run-details --run-id 1`
- `python v0.2/cli.py compare-runs --run-id 2`
- `python v0.2/cli.py stats`
- `python v0.2/cli.py guide-history --guide B263378877-1`
- `python v0.2/cli.py clear-history --yes`
- `python v0.2/cli.py version`
- `python v0.2/cli.py check-update`
- `python v0.2/cli.py download-update`
- `python v0.2/cli.py tui`

### v0.3 principales
- `python v0.3/server.py`
- `python v0.3/server.py --check`

## Verificaciones actuales

### v0.2
- `python -m compileall "v0.2"`
- `python -m unittest discover -s "v0.2/tests" -v`

### v0.3
- `python -m compileall "v0.3"`
- `python v0.3/server.py --check`

## Lo que ya está resuelto

- Paso manual/chat -> automatización real.
- Dependencia de IA eliminada del flujo operativo.
- Notion y Effi integrados en código.
- Historial estructurado en SQLite.
- Reportes exportables.
- PDF mejorado usando Edge/Chrome headless cuando está disponible.
- App web local inicial.
- Base de versionado en GitHub.
- Fetching paralelo de Effi con `ThreadPoolExecutor` (hasta 8 workers simultáneos).
- Detección de `parse_error`: distingue fallo de parser (HTTP OK pero sin estado_actual) de error de red.
- Corridas no bloqueantes en v0.3: background thread + página de progreso con auto-refresh.
- Comando `apply-update`: descarga zip → backup automático → reemplaza código → preserva `.env`, SQLite, reportes.
- Scripts de distribución: `iniciar.bat` y `actualizar.bat` para la usuaria final.

## Pendientes para terminar el proyecto completo

### 1. Sistema de actualización real para usuaria final
Estado: implementado.

Disponible:
- `check-update`: consulta GitHub Releases
- `download-update`: descarga el zip al directorio `updates/`
- `apply-update`: aplica el zip, hace backup automático en `backups/`, preserva `.env`, SQLite y `reports/`
- `actualizar.bat`: orquesta todo el flujo en un doble clic

Falta (opcional):
- rollback explícito desde la TUI si la actualización da problemas

### 2. Empaquetado distribuible para usuario final
Estado: implementado (base).

Disponible:
- `iniciar.bat`: abre la app web con doble clic
- `actualizar.bat`: guía interactiva de actualización completa
- separación código / config / data ya existente en la estructura de carpetas

Falta (opcional):
- empaquetar en un `.exe` standalone con PyInstaller para eliminar dependencia de Python instalado

### 3. Pulido de UX en v0.3
Estado: implementado (fase operativa).

Implementado:
- Home page operativa: muestra urgencia de la última corrida, no solo stats genéricas
- Ruta `/attention`: vista diaria con todas las guías no-unchanged, agrupadas por prioridad (changed → manual_review → parse_error → error)
- Pills con color por tipo de resultado (azul/gris/amarillo/naranja/rojo)
- Columna “Acción requerida” visible en detalle de corrida y en historial de guía
- Duración de corrida calculada y visible en home y en `/attention`
- Sidebar con “Requiere atención” como primer link

Pendiente (opcional):
- filtros por fecha en `/runs`
- buscador de guía más prominente en la home
- notificación sonora/visual cuando termina una corrida en progreso

### 4. Decidir si v0.3 reemplazará la TUI
Estado: pendiente de decisión/ejecución.

La idea ya planteada es que `v0.3` deje de ser solo dashboard y sea la app principal.

Falta:
- migrar los casos de uso importantes de TUI a web
- decidir si la TUI se mantiene como respaldo técnico o si queda secundaria

### 5. Mejorar flujo de release
Estado: parcialmente hecho.

Ya existe:
- repo GitHub
- releases manuales
- assets `.zip`

Falta:
- definir procedimiento estable para nuevas releases
- documentar versión, empaquetado y publicación
- posiblemente automatizar parte del empaquetado

### 6. Mejorar PDF si se quiere estándar más ejecutivo
Estado: aceptable, no bloqueante.

Ya existe conversión más legible usando navegador headless.

Pendientes opcionales:
- que el PDF se parezca más a `v0.3`
- más branding/estilo visual
- resaltar cambios, errores y alertas

### 7. Endurecimiento operativo final
Estado: parcialmente hecho.

Pendientes opcionales pero útiles:
- más tests
- más cobertura de casos raros de Effi
- manejo más explícito de migraciones futuras en SQLite
- estrategia de rollback de actualizaciones

## Roadmap sugerido desde este punto

### Fase 1: distribución real de v0.2
1. Diseñar estructura portable para usuaria final.
2. Crear launcher simple.
3. Crear updater semiautomático.
4. Probar instalación/actualización en el computador de logística.

### Fase 2: convertir v0.3 en app principal
1. Seguir mejorando la UI/UX.
2. Agregar vistas operativas reales.
3. Mover tareas clave de TUI a web.
4. Dejar `v0.2` como motor backend/CLI.

### Fase 3: updates automáticos más sólidos
1. Descargar release.
2. Descomprimir en staging.
3. Reemplazar solo código.
4. Conservar config/data/reportes.
5. Dejar rollback básico.

### Fase 4: opcional futura
1. Dashboard más completo.
2. Más analítica.
3. Más carriers.
4. Reglas más configurables.

## Recomendación para el siguiente agente

Si otro agente continúa, lo más sensato es empezar por esto:

1. No tocar `backups/`.
2. Tratar `v0.2` como motor estable principal.
3. Tratar `v0.3` como interfaz principal en evolución.
4. Priorizar distribución/update antes que nuevas features grandes.
5. Si se trabaja en updates reales, cuidar especialmente:
   - preservar `.env`
   - preservar SQLite
   - preservar reportes
   - no sobrescribir datos de usuaria

## Riesgos clave a no olvidar

- Repo privado requiere token para updates desde GitHub Releases.
- Auto-actualizar una app local en Windows mientras está corriendo requiere cuidado.
- Effi depende del HTML actual; si cambia, primero capturar raw HTML antes de cambiar reglas.
- `--apply` escribe en Notion de verdad.
- La usuaria final idealmente no debería tocar archivos del proyecto manualmente.
