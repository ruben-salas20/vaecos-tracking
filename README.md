# Seguimiento VAECOS

VAECOS Seguimiento reconcilia el estado de las guías en Notion contra lo que reporta el transportista (Effi) y, cuando amerita, actualiza Notion automáticamente. Hoy es una **aplicación web multi-usuario en producción** en `https://app.vaecos.com`, operada por la dueña y la operadora desde el navegador.

## Estado actual (2026-05-10)

- **Producción**: `https://app.vaecos.com` — Hostinger VPS + Caddy (TLS automático) + systemd + Waitress
- **Interfaz principal**: v0.4 (Flask + auth + dark mode)
- **Fase actual**: 2.3 entregada (motor lee desde local, edición de campos, alta/archivo/restauración de guías). Pendiente 2.4 (inversión de polaridad: local FIRST, Notion mirror).

## Arquitectura por capas

| Capa | Rol | Estado |
|------|-----|--------|
| `v0.2/` | Motor de reglas + CLI/TUI + SQLite + servicios (`run_tracking`, `sync_guides`, `update_guide`, `add_guide`, `local_guides`) | Activo — reutilizado por v0.4 |
| `v0.3/` | `DashboardRepository` y gráficos SVG | **Reutilizado por v0.4** (el server v0.3 quedó legacy) |
| `v0.4/` | Flask web app: auth, blueprints, dark mode, búsqueda, importación Excel, edición de guías | **Principal en uso** |

v0.4 importa v0.2 (motor) y v0.3 (`DashboardRepository`, charts) directamente vía `sys.path.insert`. La base de datos `v0.2/data/vaecos_tracking.db` (SQLite WAL) es compartida por las tres capas.

## Uso rápido

### Local (desarrollo / operadora antes de migrar a la web)

```powershell
# Arrancar la web v0.4
iniciar_v04.bat
# o
python v0.4/server.py
```

Abre `http://127.0.0.1:8765` y entra con tu usuario.

### Producción

Acceso: `https://app.vaecos.com` — login con email + password. El primer admin se siembra desde `V04_BOOTSTRAP_EMAIL` / `V04_BOOTSTRAP_PASSWORD` al primer arranque y luego puede crear más usuarios desde `/users`.

### CLI (corridas manuales del motor)

```powershell
python v0.2/cli.py run --dry-run                    # todas las guías activas
python v0.2/cli.py run --apply                      # aplicar cambios a Notion
python v0.2/cli.py run --guides B263378877-1 --dry-run
python v0.2/cli.py tui                              # interfaz curses
```

## Funcionalidades clave de v0.4

- **Auth multi-usuario**: login/logout, cambio de contraseña, perfil editable (`/mi-cuenta`), rate limiting.
- **Dashboard operativo**: `/`, `/attention`, `/analytics`, `/all-guides`, `/search`, detalles por guía y por cliente.
- **Reglas editables**: `/rules` con auditoría (`rule_history`) y vista previa contra guías reales (`/rules/preview?guia=...`).
- **Corridas en background**: `/run/new` dispara un thread con polling de progreso. Auto-sync con Notion al terminar.
- **Importación Excel**: `/import` con preview + confirm. Crea páginas nuevas en Notion.
- **Edición de guías** (Fase 2.2): teléfono, producto, valor, cantidad — atómico Notion → local + audit. Campos vacíos NO borran datos en Notion.
- **Crear nueva guía** (Fase 2.3): `/guides/new` con formulario.
- **Archivar / restaurar** (Fase 2.3): soft-delete con papelera de 30 días vía archive de Notion.
- **Dark mode**, sidebar colapsable, favicon, búsqueda global.
- **Admin**: `/users` para crear, activar/desactivar y resetear contraseñas.

## Flujo de datos (post Fase 2.1)

1. **Pre-sync**: `sync_guides()` baja todas las páginas desde Notion a la tabla local `guides` al inicio de cada corrida.
2. **Lectura**: el motor lee desde la tabla local (`local_guides.fetch_active_guides_local()`), no directamente de Notion.
3. **Carrier**: se selecciona por guía según la columna `carrier` del registro local. Effi implementado; Guatex stub.
4. **Reglas**: `decide_status()` evalúa por orden semántico estratificado (terminal → operacional → contextual → estancamiento → preservación).
5. **Escritura** (patrón atómico Fase 2 actual): Notion FIRST → local + audit. Si Notion falla, no se modifica nada local; se registra `sync_ok=0` en `guide_edits`.

> **Fase 2.4** (pendiente) invertirá esta polaridad: local FIRST, Notion mirror best-effort.

## Documentación

| Archivo | Contenido |
|---------|-----------|
| `CLAUDE.md` | Guía técnica completa (comandos, arquitectura, deploy, gotchas) |
| `docs/PRD.md` | Product Requirements v2.0 |
| `docs/roadmap-estrategico.md` | Roadmap por fases con criterios de salida |
| `docs/ARCHITECTURE.md` | Arquitectura actual y objetivo |
| `docs/DESIGN.md` | Design system (Inter, tokens, componentes) |
| `docs/roadmap.md` | Checklist técnico de estado |
| `docs/guia-operadora-novedades-v0.4.html` | Guía visual imprimible a PDF de los cambios desde v0.3.4.2 |
| `v0.2/README.md`, `v0.3/README.md`, `v0.4/README.md` | Detalle por capa |

## Variables de entorno

`.env` en la raíz del repo:

```env
# Notion
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=e7da64fa-d6c7-47ab-bc12-d7af207f871b
NOTION_VERSION=2025-09-03

# Effi
EFFI_TIMEOUT_SECONDS=20

# DB compartida
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db

# Flask v0.4
FLASK_SECRET_KEY=...                      # requerido en producción
VAECOS_ENV=development                    # o "production"
V04_BOOTSTRAP_EMAIL=admin@vaecos.com      # solo primer arranque
V04_BOOTSTRAP_PASSWORD=...
V04_HOST=127.0.0.1
V04_PORT=8765

# Updates desde GitHub Releases
V02_UPDATE_REPO=ruben-salas20/vaecos-tracking
V02_UPDATE_GITHUB_TOKEN=                  # repo privado requiere token con scope repo
```

## Producción — VPS

| | |
|---|---|
| URL | `https://app.vaecos.com` |
| VPS | Hostinger KVM 2 — Ubuntu 24.04 LTS |
| App user | `vaecos` (sudo NOPASSWD), código en `/opt/vaecos/` |
| Servicio | systemd `vaecos.service` → `waitress-serve --listen=127.0.0.1:8765 --threads=4 wsgi:application` |
| Proxy | Caddy con TLS automático (Let's Encrypt) |
| Firewall | UFW: 22 / 80 / 443 |
| Backups | `sqlite3 .backup` + gzip diario 3am UTC, retención 14 días (`/opt/vaecos/backups/`) |

### Deploy de un cambio

```powershell
git add . ; git commit -m "..." ; git push
ssh -i $env:USERPROFILE\.ssh\vaecos_vps vaecos@2.24.206.197 "cd /opt/vaecos && git pull && sudo systemctl restart vaecos"
# Si cambió requirements.txt, agregar: && .venv/bin/pip install -r v0.4/requirements.txt
```

## Verificación

```powershell
python -m compileall "v0.2" "v0.3" "v0.4"
python -m unittest discover -s "v0.2/tests" -v
```

## Notas operativas

- Tras cualquier cambio de código en local, reiniciar **completamente** `iniciar_v04.bat` (Flask recarga templates, no módulos Python; `use_reloader=False`).
- `--apply` actualiza propiedades en Notion; el body de la página sigue siendo manual.
- Toda edición de la operadora es atómica: si Notion rechaza, no se modifica nada local y queda registrado el intento fallido en `guide_edits`.
- Auto-sync corre al terminar cada corrida. Sync manual disponible en `/sync/notion` desde `/all-guides`.
- `apply-update` preserva `.env` y `v0.2/data/` — seguro de ejecutar.
- Si Effi cambia su HTML, usar `--save-raw-html` para depurar antes de tocar el parser.

## Agregar un carrier nuevo

1. Crear `v0.2/vaecos_v02/providers/carriers/<name>.py` implementando el `Carrier` Protocol.
2. Registrarlo en `v0.2/vaecos_v02/providers/carriers/__init__.py`.
3. El valor de `Transportista` en Notion debe coincidir con el `name` de la clase.

## Legacy

- `v0.1/` — primera iteración, conservada en `backups/` por referencia histórica.
- `v0.3/server.py` — server `http.server` original, ya no se usa. Su `DashboardRepository` y `render.py` siguen vivos como dependencias de v0.4.
