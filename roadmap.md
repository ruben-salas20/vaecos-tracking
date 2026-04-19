# Checklist

## Estado actual del proyecto

### v0.1
- Ya no existe como código operativo en el root.
- Se conserva solo como respaldo en `backups/`.
- No debe retomarse como base de trabajo salvo que se necesite restaurar o comparar algo histórico.

### v0.2
- Es la versión operativa principal (motor backend/CLI).
- Ya hace todo el flujo de negocio principal:
  - leer Notion
  - consultar el carrier configurado por registry (Effi implementado; Guatex como stub)
  - aplicar reglas (motor data-driven contra tabla `rules` de SQLite)
  - generar reportes
  - actualizar propiedades en Notion con `--apply`
- Tiene arquitectura modular con abstracción de carriers (`providers/carrier.py` + `providers/carriers/`).
- Tiene SQLite para histórico + reglas editables + auditoría (`rule_history`).
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
  - `apply-update`

### v0.3
- Es la aplicación web local y ya es la interfaz principal en uso.
- Dispara corridas usando la lógica de `v0.2`, en background con página de progreso.
- Lee y escribe sobre la SQLite de `v0.2` (seeding inicial incluido).
- Rutas principales:
  - `/` — centro operativo
  - `/attention` — vista diaria de lo que requiere atención
  - `/runs`, `/runs/<id>`
  - `/run/new`, `/run/progress/<token>`
  - `/guides/<guia>`, `/clients/<cliente>`
  - `/analytics` — KPIs, tendencias y distribución por carrier
  - `/rules`, `/rules/new`, `/rules/<id>/edit`, `/rules/<id>/history`, `/rules/preview` — edición sin tocar código
  - `/static/*`, `/favicon.ico`

## Estructura actual importante

### Root
- `README.md`: documentación raíz.
- `AGENTS.md`: instrucciones compactas para futuras sesiones.
- `.env`: configuración local real.
- `.env.example`: plantilla de configuración.
- `proceso_seguimiento_guias_VAECOS.md`: documento histórico de reglas/proceso.
- `Logo_vaecos-sin fondo.png`: logo fuente de la marca (negro `#0f172a` + rojo `#dc2626`).
- `iniciar.bat`, `actualizar.bat`: scripts de distribución para usuaria final.
- `backups/`: backups históricos de `v0.1` y `v0.2`.

### v0.2
- `v0.2/cli.py`: entrypoint.
- `v0.2/version.json`: versión local actual.
- `v0.2/vaecos_v02/app/cli.py`: CLI/TUI.
- `v0.2/vaecos_v02/app/config.py`: carga de config y variables de entorno.
- `v0.2/vaecos_v02/app/services/run_tracking.py`: flujo principal (dispatch por carrier + seeding de reglas).
- `v0.2/vaecos_v02/app/services/update_service.py`: check/download/apply de releases.
- `v0.2/vaecos_v02/core/rules.py`: motor de reglas data-driven + `DEFAULT_RULES`.
- `v0.2/vaecos_v02/core/models.py`: dataclasses de dominio (incluye `Rule`).
- `v0.2/vaecos_v02/providers/carrier.py`: `Carrier` Protocol + `CarrierConfig`.
- `v0.2/vaecos_v02/providers/carriers/__init__.py`: registry (`CARRIERS`, `get_carrier`, `make_carrier`).
- `v0.2/vaecos_v02/providers/carriers/effi.py`: implementación Effi.
- `v0.2/vaecos_v02/providers/carriers/guatex.py`: stub documentado.
- `v0.2/vaecos_v02/providers/effi_provider.py`: shim de compatibilidad sobre `EffiCarrier`.
- `v0.2/vaecos_v02/providers/notion_provider.py`: integración Notion (lee `Transportista`).
- `v0.2/vaecos_v02/reporting/report_builder.py`: Markdown/CSV/PDF.
- `v0.2/vaecos_v02/storage/db.py`: schema SQLite + migraciones idempotentes.
- `v0.2/vaecos_v02/storage/repositories.py`: queries SQLite de corridas.
- `v0.2/vaecos_v02/storage/rules_repository.py`: CRUD de reglas + auditoría + seeding.
- `v0.2/tests/`: tests con `unittest` (20+ casos, incluye registry, migración, reglas, repositorio).

### v0.3
- `v0.3/server.py`: entrypoint web.
- `v0.3/vaecos_v03/app.py`: servidor HTTP, rutas GET/POST, arranque con seeding.
- `v0.3/vaecos_v03/storage.py`: lecturas de SQLite para dashboard (incluye `carrier_breakdown`, `attention_trend`, `top_problem_clients`, `avg_time_in_status`).
- `v0.3/vaecos_v03/render.py`: shell, componentes HTML, SVG charts, branding.
- `v0.3/vaecos_v03/rules_ui.py`: renderers y handlers de `/rules*`.
- `v0.3/vaecos_v03/static/`: logo y favicon.

## Estado de GitHub / releases

- Repo privado creado:
  - `ruben-salas20/vaecos-tracking`
- Remoto configurado en `origin`.
- Releases publicadas:
  - `v0.2.0`, `v0.2.1`, `v0.3.0`, `v0.3.1`, `v0.3.2`
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
- `python v0.2/cli.py apply-update`
- `python v0.2/cli.py tui`

### v0.3 principales
- `python v0.3/server.py`
- `python v0.3/server.py --check`
- `iniciar.bat` (doble clic para arrancar)
- `actualizar.bat` (doble clic para actualizar)

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
- App web local consolidada como interfaz principal.
- Base de versionado en GitHub + `apply-update` con backup automático.
- Fetching paralelo de Effi con `ThreadPoolExecutor` (hasta 8 workers simultáneos).
- Detección de `parse_error`: distingue fallo de parser (HTTP OK pero sin estado_actual) de error de red.
- Corridas no bloqueantes en v0.3: background thread + página de progreso con auto-refresh.
- Scripts de distribución: `iniciar.bat` y `actualizar.bat` para la usuaria final.
- **Fase 0 (backup)**: release `v0.3.0` con zip subido; snapshot local en `backups/`.
- **Fase A (identidad visual)**: logo y paleta (`#dc2626` + `#0f172a`) aplicados en web, favicon y PDF.
- **Fase B (analytics)**: ruta `/analytics` con KPI cards, tendencia de atención, breakdown diario y por carrier, clientes problemáticos y tiempo promedio por estado.
- **Fase C1 (multi-carrier)**: abstracción `Carrier` + registry (`effi` real, `guatex` stub), propiedad `Transportista` leída desde Notion, columna `carrier` en SQLite con migración idempotente, badges en todas las vistas.
- **Fase C2 (reglas editables)**: reglas en SQLite con CRUD web (`/rules`), auditoría `rule_history`, vista previa contra guías almacenadas, seeding automático de 10 reglas default al primer arranque; motor data-driven que itera por prioridad.

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

### 2. Empaquetado distribuible para usuario final (Fase D)
Estado: base lista, empaquetado `.exe` pendiente.

Disponible:
- `iniciar.bat`: abre la app web con doble clic
- `actualizar.bat`: guía interactiva de actualización completa
- separación código / config / data ya existente en la estructura de carpetas

Falta:
- `build.py` con PyInstaller (onedir, no onefile) que produzca `dist/VAECOS/VAECOS.exe`
- mover `.env`, `data/vaecos_tracking.db` y `reports/` a `%APPDATA%\VAECOS\` fuera del bundle
- adaptar `apply-update` para reconocer instalaciones empaquetadas
- probar upgrade empaquetado en el computador de logística

### 3. Pulido de UX en v0.3
Estado: implementado (fase operativa).

Implementado:
- Home page operativa: muestra urgencia de la última corrida, no solo stats genéricas
- Ruta `/attention`: vista diaria con todas las guías no-unchanged, agrupadas por prioridad (changed → manual_review → parse_error → error)
- Pills con color por tipo de resultado (azul/gris/amarillo/naranja/rojo) + badges de carrier
- Columna "Acción requerida" visible en detalle de corrida y en historial de guía
- Duración de corrida calculada y visible en home y en `/attention`
- Sidebar con "Requiere atención" como primer link, más grupo "Inteligencia" (Analytics) y "Acciones" (Nueva corrida, Reglas)
- Branding: logo en sidebar, favicon, paleta roja/negra en toda la web

Pendiente (opcional):
- filtros por fecha en `/runs`
- buscador de guía más prominente en la home
- notificación sonora/visual cuando termina una corrida en progreso

### 4. v0.3 como app principal
Estado: alcanzado en la práctica.

Hoy:
- las corridas se disparan desde `/run/new`
- el análisis diario vive en `/attention` y `/analytics`
- la edición de reglas se hace desde `/rules`
- la TUI de v0.2 queda como respaldo técnico y CLI sigue siendo útil para automatización scripteada

Pendiente (bajo impacto):
- decidir formalmente si la TUI se retira del menú de la usuaria final o solo del README

### 5. Mejorar flujo de release
Estado: parcialmente hecho.

Ya existe:
- repo GitHub
- releases `v0.2.x` y `v0.3.0`
- assets `.zip`

Falta:
- definir procedimiento estable para nuevas releases (checklist de pasos)
- documentar versión, empaquetado y publicación
- posiblemente automatizar parte del empaquetado (GitHub Action)

### 6. Mejorar PDF si se quiere estándar más ejecutivo
Estado: aceptable, no bloqueante.

Ya existe conversión más legible usando navegador headless y header con logo de marca.

Pendientes opcionales:
- que el PDF se parezca más a `v0.3`
- resaltar cambios, errores y alertas con el mismo color coding que la web

### 7. Endurecimiento operativo final
Estado: parcialmente hecho.

Pendientes opcionales pero útiles:
- más cobertura de casos raros de Effi
- tests HTTP end-to-end de v0.3 (hoy solo hay smoke manual)
- estrategia de rollback de actualizaciones
- validaciones más estrictas en el formulario de reglas (ej: advertir cuando un motivo_template usa un placeholder sin datos disponibles)

### 8. Carrier real adicional (Guatex u otro)
Estado: infraestructura lista, integración real pendiente.

Disponible:
- `Carrier` Protocol + registry
- columna `carrier` en SQLite con migración idempotente
- stub `providers/carriers/guatex.py` que sirve de plantilla
- propiedad `Transportista` leída desde Notion

Falta:
- implementar un segundo carrier real (scraping o API)
- decidir paleta de colores/iconos si se agregan más carriers al badge

### 9. Despliegue a VPS con auth (futuro)
Estado: pendiente, alineado con visión del proyecto.

Hoy la app es local single-user. La visión a largo plazo es correr en un VPS accesible desde cualquier computador, con autenticación.

Requiere (cuando se aborde):
- auth layer (sesiones, cookies, usuarios)
- hardening del server HTTP (hoy `http.server` stdlib)
- gestión de secretos fuera del repo
- HTTPS / certificado
- estrategia de backups remotos de la SQLite

## Roadmap sugerido desde este punto

### Fase D (packaging final)
1. Escribir `build.py` con PyInstaller spec (onedir).
2. Mover `.env`, SQLite y `reports/` a `%APPDATA%\VAECOS\`.
3. Adaptar `apply-update` para instalaciones empaquetadas.
4. Probar flujo completo en una Windows limpia sin Python.
5. Publicar release con `.exe` como asset.

### Fase E (segundo carrier real)
1. Capturar HTML o API del nuevo carrier.
2. Implementar en `providers/carriers/<nombre>.py` siguiendo el Protocol.
3. Registrar en `CARRIERS`.
4. Añadir badge y colores en `render.py`.
5. Validar con `/analytics` que el breakdown por carrier funcione.

### Fase F (VPS + auth)
1. Diseñar capa de auth compatible con el HTTP handler actual.
2. Elegir forma de despliegue (systemd, Docker, Caddy, etc.).
3. Migrar datos locales al servidor con estrategia de backup.
4. Revisar permisos y exposición de rutas.

## Recomendación para el siguiente agente

Si otro agente continúa, lo más sensato es:

1. No tocar `backups/`.
2. Tratar `v0.2` como motor estable principal.
3. Tratar `v0.3` como interfaz principal (ya no solo evolución).
4. Antes de cambiar reglas, usar `/rules/preview` contra una guía real para verificar el efecto.
5. Antes de tocar el parser de Effi, capturar raw HTML con `--save-raw-html`.
6. Si se trabaja en updates reales, cuidar especialmente:
   - preservar `.env`
   - preservar SQLite (reglas y corridas)
   - preservar reportes
   - no sobrescribir datos de usuaria
7. Si se agrega un carrier nuevo, seguir el patrón del registry y no meter lógica de carrier en `rules.py` ni en `run_tracking.py`.

## Riesgos clave a no olvidar

- Repo privado requiere token para updates desde GitHub Releases.
- Auto-actualizar una app local en Windows mientras está corriendo requiere cuidado.
- Effi depende del HTML actual; si cambia, primero capturar raw HTML antes de cambiar reglas.
- `--apply` escribe en Notion de verdad.
- La usuaria final idealmente no debería tocar archivos del proyecto manualmente; las reglas se editan en `/rules`.
- Una regla mal configurada puede afectar miles de guías en la siguiente corrida — usar siempre `/rules/preview` antes de activarla.
