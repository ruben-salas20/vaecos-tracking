# Checklist

## Estado actual del proyecto

### Producción

- **URL**: https://app.vaecos.com
- **VPS**: Hostinger KVM 2 (2 vCPU, 8 GB RAM, 100 GB) — Ubuntu 24.04 LTS — IP `2.24.206.197`
- **Código**: clonado de `github.com/ruben-salas20/vaecos-tracking` en `/opt/vaecos/`
- **Service**: `vaecos.service` (systemd) — Waitress en `127.0.0.1:8765`, threads=4, restart=on-failure
- **Reverse proxy**: Caddy con TLS automático (Let's Encrypt) — bloqueo de paths sensibles
- **Firewall**: UFW activo, solo `22/80/443`
- **SSH**: solo key auth (clave en `~/.ssh/vaecos_vps`), root con `prohibit-password`, usuario `vaecos` con sudo NOPASSWD
- **DB**: `/opt/vaecos/data/vaecos_tracking.db` (WAL mode), bootstrap admin seeded
- **Secrets**: `/opt/vaecos/.env` chmod 600, owned `vaecos:vaecos`
- **DNS**: A record `app.vaecos.com → 2.24.206.197` configurado vía Hostinger MCP

#### Comandos de gestión del VPS

```bash
# Acceso SSH
ssh -i ~/.ssh/vaecos_vps vaecos@2.24.206.197

# Logs en vivo
journalctl -u vaecos -f

# Restart de la app
sudo systemctl restart vaecos

# Deploy de cambios (después de git push desde la PC del dueño)
ssh -i ~/.ssh/vaecos_vps vaecos@2.24.206.197 "cd /opt/vaecos && git pull && sudo systemctl restart vaecos"

# Si requirements.txt cambió:
ssh -i ~/.ssh/vaecos_vps vaecos@2.24.206.197 "cd /opt/vaecos && git pull && .venv/bin/pip install -r v0.4/requirements.txt && sudo systemctl restart vaecos"

# Migrar la DB de la operadora (cuando la pase)
scp -i ~/.ssh/vaecos_vps "ruta/operadora.db" vaecos@2.24.206.197:/opt/vaecos/data/operator.db
ssh -i ~/.ssh/vaecos_vps vaecos@2.24.206.197 "sudo systemctl stop vaecos && \
  mv /opt/vaecos/data/vaecos_tracking.db /opt/vaecos/data/vaecos_tracking.db.fresh-bootstrap && \
  mv /opt/vaecos/data/operator.db /opt/vaecos/data/vaecos_tracking.db && \
  cd /opt/vaecos && .venv/bin/python scripts/post_restore.py --skip-bootstrap && \
  sudo systemctl start vaecos"
```

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
- **Reportes auto-generados (`.csv` / `.md` / `.pdf`) eliminados** — toda la información ahora vive en SQLite + la app.
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
- Quedó como capa de compatibilidad. v0.4 lo importa para reusar `DashboardRepository`, `render.py` (charts) y la lógica de queries.
- Sigue arrancable con `python v0.3/server.py` para fallback durante la transición, pero NO es la interfaz que la operadora usa.
- Pendiente: archivar formalmente cuando la operadora valide v0.4 en uso real.

### v0.4 (interfaz principal en producción)
- Aplicación Flask 3.1 con blueprints, login, sesiones firmadas, modo oscuro, sidebar colapsable.
- Reusa el motor de v0.2 directamente (sin reescribir nada del business engine) y el `DashboardRepository` de v0.3.
- Arrancable con `python v0.4/server.py` o `iniciar_v04.bat`.
- **Fase 2 entregada (2.1, 2.2, 2.3 + archive/unarchive)**: el motor lee guías desde tabla local; la operadora puede crear, editar campos y archivar/restaurar guías desde la app sin tocar Notion ni Excel. Pendiente: 2.4 (inversión polaridad de escrituras) y 2.5 (validador de consistencia).
- Estructura:
  ```
  v0.4/
    server.py                       # entrypoint (dev: app.run, prod: waitress)
    config.py                       # V04Settings + .env loader (incluye Notion vars)
    app/
      __init__.py                   # create_app() factory + bootstrap admin
      auth/                         # /login, /logout, /change-password, decorators
      dashboard/                    # 14 GETs migrados de v0.3 + /all-guides + /search
      runs/                         # POST /run/new, progress, CSV export, /sync/*
      import_guides/                # /import (upload, preview, confirm) + parser
      users/                        # /users, /users/<id>/{toggle,delete,reset-password}
      notion_helpers.py             # cache de opciones de Estado novedad (TTL 5 min)
    templates/
      base.html, macros.html, partials/{sidebar,flash}.html
      auth/{login,change_password}.html
      dashboard/{home,attention,analytics,runs,run_detail,run_new,run_progress,
                 guide_detail,client_detail,rules_maintenance,
                 all_guides,search,sync_progress}.html
      import_guides/{import,import_preview,import_result}.html
      users/{users,reset_password}.html
    static/css/{styles.css,app.css} static/js/app.js
  ```
- Rutas (v0.4):
  - `/login`, `/logout`, `/change-password`
  - `/` — centro operativo
  - `/attention` — vista diaria de atención
  - `/all-guides` — snapshot completo de Notion con filtros + quick-edit de estado
  - `/search` — buscador inteligente (guía / DPI / nombre)
  - `/runs`, `/runs/<id>`, `/run/new`, `/run/progress/<token>`
  - `/runs/<id>/results/<guia>/notas` — notas de corrida (AJAX)
  - `/runs/<id>/export/effi` — CSV con BOM
  - `/guides/<guia>` — detalle + dropdown de estado + panel de notas + audit trail
  - `/guides/<guia>/notes` — POST/DELETE (AJAX)
  - `/guides/<guia>/state` — POST atómico Notion+local+audit
  - `/clients/<cliente>` — detalle con DPI persistido
  - `/sync/notion` — POST background sync
  - `/sync/progress/<token>` + `/sync/status/<token>` — UI + JSON polling
  - `/import` — upload Excel del ERP, preview, confirm (crea páginas en Notion)
  - `/users` (admin) — listar/crear/desactivar/eliminar/reset password
  - `/analytics`, `/analytics/por-recoger`, `/rules*`

## Estructura actual importante

### Root
- `README.md`: documentación raíz.
- `AGENTS.md`: instrucciones compactas para futuras sesiones.
- `.env`: configuración local real.
- `.env.example`: plantilla de configuración.
- `docs/proceso-seguimiento-guias.md`: documento histórico de reglas/proceso.
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

### v0.3 principales (legacy, reusable como respaldo)
- `python v0.3/server.py`
- `python v0.3/server.py --check`

### v0.4 principales (en uso real)
- `python v0.4/server.py`
- `iniciar_v04.bat` (doble clic para arrancar la app actual)
- `actualizar.bat` (sigue funcionando — preserva `.env` y SQLite)

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
