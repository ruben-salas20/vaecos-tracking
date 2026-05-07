# VAECOS Tracking — Arquitectura

Version: v1.2
Fecha: 2026-05-07 (post Fase 2.1/2.2/2.3)

---

## Estado actual (baseline v0.4)

### Stack

| Componente | Tecnología |
|-----------|-----------|
| Lenguaje | Python 3.12+ |
| Dependencias | Flask 3.1, bcrypt, openpyxl, waitress |
| Web framework | Flask con blueprints (auth, dashboard, runs, import_guides, users) |
| Auth | bcrypt + Flask sessions firmadas |
| Base de datos | SQLite local (`v0.2/data/vaecos_tracking.db`) con WAL habilitado |
| Fuente operativa de guías | Tabla local `guides` (Fase 2.1 — el motor lee de aquí, no de Notion) |
| Fuente de tracking | Effi (scraping HTML) |
| Notion | Sigue siendo autoritativo para escrituras (Notion FIRST atomic). Lectura del motor ya migrada a local. Fase 2.4 (pendiente) invertirá la polaridad de escrituras. |
| Despliegue actual | Local, multi-usuario por login, Windows |
| Despliegue objetivo | VPS Hostinger con Caddy + systemd + Waitress (Fase 1 cierre) |

### Estructura de módulos

```
v0.2/                               # Motor de negocio (sin cambios estructurales)
  vaecos_v02/
    core/
      models.py                     # NotionClientRecord (con telefono, producto, valor, cantidad), ProcessingResult, Rule
      rules.py                      # Motor de reglas: decide_status()
      utils.py                      # Normalización de texto para matching
    providers/
      carrier.py                    # Protocol Carrier + CarrierConfig
      carriers/{effi,guatex}.py
      notion_provider.py            # NotionProvider con fetch_all_pages, create_guide_page,
                                    # update_estado_novedad, _resolve_select_option (case-insensitive)
    storage/
      db.py                         # Schema SQLite + migraciones idempotentes (incluye guides, guide_notes, guide_edits, users, import_log)
      repositories.py               # Queries de corridas; save_result persiste telefono
      rules_repository.py           # CRUD de reglas + auditoría + seeding
    app/
      services/
        run_tracking.py             # Flujo principal: pre-sync + lee de tabla local guides (Fase 2.1)
        local_guides.py             # Fase 2.1 — fetch_active/selected_guides_local (reemplaza lectura Notion del motor)
        sync_guides.py              # Pull-only sync Notion → tabla guides con upsert por page_id
        update_guide.py             # Atomic edits: state, fields (Fase 2.2), archive/unarchive (Fase 2.3)
        add_guide.py                # Fase 2.3 — create new guide atomic (Notion → local + audit)
        update_service.py           # Check/download/apply de releases
      config.py                     # V02Settings + .env loader
      cli.py                        # CLI y TUI

v0.3/                               # Capa de queries reusada por v0.4
  vaecos_v03/
    storage.py                      # DashboardRepository con métodos para corridas, búsqueda,
                                    # notes, edits, list_all_guides, search_by_phone
    render.py                       # SVG charts (line_chart, stacked_bar_chart) — reusados por v0.4
    rules_ui.py                     # UI de /rules* (legacy, todavía usado)

v0.4/                               # Interfaz Flask actual
  server.py                         # entrypoint dev/prod
  config.py                         # V04Settings (incluye Notion vars + bootstrap admin)
  app/
    __init__.py                     # create_app() factory + _seed_bootstrap_user
    auth/{routes,decorators,user_repo}.py
    dashboard/routes.py             # 14 GETs migrados de v0.3 + /all-guides + /search + /guides/<g>/{notes,state}
    runs/{routes,jobs}.py           # Run dispatch + sync dispatch + AJAX update_notas
    import_guides/{routes,parser}.py# Excel parser + crea páginas en Notion al confirmar
    users/routes.py                 # CRUD de usuarios (admin)
    notion_helpers.py               # Cache de opciones de Estado novedad (TTL 5 min)
    charts.py, utils.py
  templates/                        # Jinja2: base + macros + 25 templates
  static/css/{styles,app}.css       # Design system (Geist + warm neutrals + dark mode tokens)
  static/js/app.js                  # Theme toggle, sidebar collapse, AJAX para notas/estado/sync
```

### Flujo de datos actual (v0.4)

```
Notion API ⇄ NotionProvider
   │
   ├── Lectura:
   │   • fetch_active_guides() → run_tracking.run() (motor de corrida, en vivo)
   │   • fetch_all_pages()     → sync_guides() → tabla local `guides`
   │
   └── Escritura:
       • update_page_status()      ← motor cuando aplica cambios
       • update_estado_novedad()   ← operadora desde la app (atómico vía update_guide.py)
       • create_guide_page()       ← importación de Excel del ERP

UI (Flask) → DashboardRepository → SQLite (guides, run_results, guide_notes, guide_edits, ...)

Auto-sync: cada corrida termina con un sync_guides() que refresca el snapshot local.
```

### Fortalezas del diseño actual

- **Motor de reglas completamente desacoplado**: `rules.py` no sabe nada de carriers, storage ni HTTP. Es pura lógica.
- **Carriers abstraídos por Protocol**: agregar un carrier nuevo no requiere cambiar `run_tracking` ni `rules`.
- **Migraciones idempotentes**: `db.py` aplica ALTERs y seed seguro en cada `init_db()`. Nunca rompe DBs existentes.
- **Sin dependencias externas**: no hay gestión de entornos virtuales ni `requirements.txt`.
- **Tests unitarios**: cubren el motor de reglas, el parser de Effi, el repositorio y las migraciones.

### Limitaciones que motivan la evolución

- `http.server` no tiene soporte nativo de auth, sesiones, ni manejo de uploads.
- Dependencia de Notion para leer guías activas — fuente externa fuera del control del equipo.
- Diseñado para un solo usuario local — no puede desplegarse en VPS para múltiples usuarios.
- Sin HTTPS nativo.
- Sin mecanismo de ingesta estructurada de guías nuevas (hoy entran solo desde Notion).

---

## Arquitectura objetivo (Fase 1 → VPS)

### Stack objetivo

| Componente | Tecnología | Justificación |
|-----------|-----------|---------------|
| Lenguaje | Python 3.12+ | Sin rewrite — la lógica de negocio es sólida y cubierta por tests |
| Web framework | Flask | Maneja auth, sesiones y file uploads. Mínimo overhead para 4 usuarios. |
| Base de datos | SQLite (WAL mode) | 4 usuarios, baja concurrencia. Datos ya existentes. Migrable a PostgreSQL. |
| Auth | Flask sessions + bcrypt | Simple, seguro, suficiente para el caso de uso actual. |
| Excel parsing | openpyxl | Estándar para `.xlsx`, sin dependencias pesadas. |
| Proxy / HTTPS | Caddy | TLS automático (Let's Encrypt), configuración mínima. |
| Despliegue | systemd | Simple, robusto, reinicio automático, control de logs. |
| VPS | Hostinger (ya disponible) | Linux, disponible, sin uso actual. |

### Por qué Flask y no continuar con stdlib

El `http.server` actual resuelve bien el caso local single-user. Para VPS con múltiples usuarios necesitamos:

1. **Gestión de sesiones**: cookies seguras con firma criptográfica.
2. **Protección de rutas**: decoradores de auth sobre cada handler.
3. **File upload**: manejo multipart/form-data con validación de tamaño y tipo.
4. **Concurrent request handling**: Flask + servidor WSGI (Waitress o Gunicorn) maneja esto correctamente.

Flask agrega ~2MB de dependencias y resuelve todos estos puntos sin introducir overhead arquitectural. FastAPI sería excesivo para una app de renderizado server-side sin API REST pública.

### Por qué SQLite en Fase 1 y no PostgreSQL

- Los datos ya están en SQLite. Migrar a PostgreSQL en Fase 1 agrega complejidad sin beneficio real para 4 usuarios concurrentes.
- SQLite en WAL mode soporta múltiples readers simultáneos y un writer. Suficiente para el caso de uso.
- La capa de storage (`repositories.py`, `db.py`) está suficientemente desacoplada para migrar más adelante.

**Cuándo migrar a PostgreSQL**: cuando se superen ~20 usuarios concurrentes, se agreguen corridas automáticas frecuentes, o haya contención de escritura observable en producción.

### Estructura objetivo

```
v0.2/           # Sin cambios — motor de negocio estable
v0.3/           # Reemplazado o coexistente durante transición
v0.4/           # Nueva capa web (Flask) — o reestructuración de v0.3
  app/
    __init__.py             # Factory de la app Flask
    auth/
      routes.py             # /login, /logout, /change-password
      decorators.py         # @login_required
    import_guides/
      routes.py             # /import (GET preview, POST confirmar)
      parser.py             # Lógica de parsing y validación del Excel
    users/
      routes.py             # /users (admin ABM)
    templates/              # Jinja2 — HTML sin CSS embebido
    static/
      css/                  # Design tokens (docs/DESIGN.md)
      js/                   # Mínimo — sin frameworks JS
```

### Módulos nuevos vs. reutilizados

| Módulo | Acción | Razón |
|--------|--------|-------|
| `core/rules.py` | Sin cambios | Estable, cubierto por tests |
| `core/models.py` | Sin cambios | Dataclasses de dominio correctos |
| `storage/db.py` | Extensión | Nuevas tablas (`users`, `guides`, `import_log`) vía migraciones idempotentes |
| `storage/repositories.py` | Sin cambios | Queries de corridas vigentes |
| `providers/carrier.py` | Sin cambios | Protocol vigente |
| `providers/effi.py` | Sin cambios | Implementación real funcionando |
| `app/services/run_tracking.py` | Adaptación en Fase 2 | Leer de `guides` en DB en lugar de Notion |
| `v0.3/app.py` | Reemplazado por Flask | http.server no escala al caso VPS |
| `v0.3/render.py` | Migrado a Jinja2 | CSS embebido en código Python es deuda visual |

---

## Nuevas tablas SQLite

### `users` (Fase 1 — implementada)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',    -- 'user' | 'admin'
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by TEXT
);
```

### `import_log` (Fase 1 — implementada)

```sql
CREATE TABLE import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL,
    imported_by TEXT NOT NULL,           -- email del usuario
    filename TEXT NOT NULL,
    guides_new INTEGER NOT NULL DEFAULT 0,
    guides_skipped INTEGER NOT NULL DEFAULT 0,
    guides_error INTEGER NOT NULL DEFAULT 0
);
```

### `guides` (Fase 2 parcial — implementada como snapshot de Notion)

Snapshot local de TODAS las páginas de Notion (no filtra por estado). Sincronizado por `sync_guides()`. Upsert por `page_id`. Si una página deja de aparecer en Notion, se marca `archived = 1` (no se elimina).

```sql
CREATE TABLE guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id TEXT NOT NULL UNIQUE,         -- ID de la página en Notion
    guia TEXT NOT NULL,
    cliente TEXT NOT NULL,
    telefono TEXT,                        -- DPI/teléfono del cliente
    estado_novedad TEXT,
    carrier TEXT NOT NULL DEFAULT 'effi',
    producto TEXT,
    valor REAL,
    cantidad INTEGER,
    fecha_ultimo_seguimiento TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    last_synced_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_guides_estado   ON guides (estado_novedad);
CREATE INDEX idx_guides_telefono ON guides (telefono);
CREATE INDEX idx_guides_cliente  ON guides (cliente);
CREATE INDEX idx_guides_guia     ON guides (guia);
```

### `guide_notes` (β1 — implementada)

Notas con historial por guía. Cada nota es una fila inmutable con autor, timestamp y body.

```sql
CREATE TABLE guide_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guia TEXT NOT NULL,                  -- FK lógica (no constraint) a guides.guia
    autor TEXT NOT NULL,                  -- email del usuario
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    edited_at TEXT
);
CREATE INDEX idx_guide_notes_guia ON guide_notes (guia);
```

### `guide_edits` (β2 — implementada, audit trail)

Registro de cambios manuales hechos desde la app. Se inserta tanto cuando el cambio sincroniza OK con Notion como cuando falla — esto permite diagnosticar problemas de sincronización después.

```sql
CREATE TABLE guide_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guia TEXT NOT NULL,
    autor TEXT NOT NULL,                  -- email del usuario
    campo TEXT NOT NULL,                  -- 'estado_novedad' inicialmente
    valor_anterior TEXT,
    valor_nuevo TEXT,
    created_at TEXT NOT NULL,
    sync_ok INTEGER NOT NULL DEFAULT 1,   -- 0 si Notion rechazó el cambio
    error_msg TEXT
);
CREATE INDEX idx_guide_edits_guia ON guide_edits (guia);
```

### Cambios en tablas existentes

- **`run_results`**: agregadas columnas `carrier` (Fase C1), `notas_operador` (Fase C2 v0.3) y `telefono` (β2 v0.4). Backfill de `telefono` ejecutado desde Notion para los registros existentes (163 rows / 126 guías).

Todas las tablas nuevas y los ALTER TABLE se aplican como migraciones idempotentes en `db.py`, siguiendo el patrón `_table_exists` / `_column_exists` antes de aplicar el DDL.

---

## Flujo de datos objetivo (post Fase 2)

```
Excel (upload) → ImportParser → tabla guides (DB)
                                     ↓
DB guides (activas) → run_tracking → Carrier (Effi/Guatex/...)
                                          ↓
                              rules.decide_status()
                                          ↓
                              DB (run_results, tracking_events)
                                          ↓
                              Flask views → Browser
```

Notion sale completamente del flujo core. La DB interna es la única fuente de verdad.

---

## Despliegue en VPS — estado actual (2026-05-07)

La aplicación está corriendo en producción en `https://app.vaecos.com`.

### Diagrama de runtime

```
[Browser] ──HTTPS:443──► [Caddy] ──HTTP:8765──► [Waitress/Flask (systemd)] ──► [SQLite WAL]
                          │  │                          │
                  TLS auto │  └─ ProxyFix    [run_tracking worker thread + sync_guides]
              Let's Encrypt│                            │
                          │                  [Effi scraper] [Notion API]
                          ▼
                     UFW → solo 22/80/443
```

### Configuración real desplegada

| Componente | Detalle |
|---|---|
| **VPS** | Hostinger KVM 2 (2 vCPU / 8 GB / 100 GB) — Ubuntu 24.04 LTS — IP `2.24.206.197` (id Hostinger 1593612) |
| **Dominio** | `app.vaecos.com` — A record en Hostinger DNS, TTL 300s |
| **Caddy** | v2.11.2 — `/etc/caddy/Caddyfile` con `reverse_proxy 127.0.0.1:8765`, gzip, bloqueo de `/.env` `/.git/*` `/wp-*` |
| **Python** | 3.12.3 sistema + venv en `/opt/vaecos/.venv/` con `flask 3.1.3`, `bcrypt 4.3.0`, `openpyxl 3.1.5`, `waitress 3.0.2`, `flask-limiter 3.12` |
| **Service** | `vaecos.service` (systemd) — corre `waitress-serve --listen=127.0.0.1:8765 --threads=4 wsgi:application` como user `vaecos`, restart on-failure, NoNewPrivileges, PrivateTmp |
| **Firewall** | UFW activo — default deny incoming, allow `22/tcp`, `80/tcp`, `443/tcp` |
| **SSH** | Key-only (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`). Clave deploy: `~/.ssh/vaecos_vps` (en la PC del dueño), id Hostinger 501049 |
| **Usuario app** | `vaecos` con sudo NOPASSWD vía `/etc/sudoers.d/vaecos`. La app corre como `vaecos`, no como root |
| **Secrets** | `/opt/vaecos/.env` chmod 600, owned `vaecos:vaecos`. `FLASK_SECRET_KEY` regenerado por `secrets.token_hex(32)`, `V04_BOOTSTRAP_PASSWORD` random alphanumeric 20 chars |
| **DB** | `/opt/vaecos/data/vaecos_tracking.db` (WAL mode), bootstrap admin seeded al primer arranque |
| **ProxyFix** | Activo solo en `production` con `x_for=1, x_proto=1, x_host=1, x_prefix=1` para que Flask vea la IP real del cliente detrás de Caddy (necesario para rate limiting correcto) |

### Pasos del despliegue ejecutado

1. ✅ `apt update && apt upgrade` (sistema en estado limpio post-reinstall)
2. ✅ Instalar Caddy desde repo oficial (`dl.cloudsmith.io/public/caddy/stable`) + `python3-venv` + `python3-pip`
3. ✅ Crear usuario `vaecos`, copiar SSH key a `~/.ssh/authorized_keys`, agregar a sudoers NOPASSWD
4. ✅ UFW: deny incoming default, permitir SSH/HTTP/HTTPS
5. ✅ DNS: A record `app.vaecos.com → 2.24.206.197` con `overwrite=false` (sin tocar Shopify/Zoho)
6. ✅ Clonar repo en `/opt/vaecos/` como user `vaecos`
7. ✅ Crear venv e instalar `requirements.txt`
8. ✅ Generar `.env` productivo y subir vía SCP con permisos 600
9. ✅ Crear `vaecos.service`, `daemon-reload`, `enable`, `start`
10. ✅ Crear `Caddyfile`, `caddy validate`, `systemctl reload caddy` — TLS automático emitido
11. ✅ Hardening SSH: `PasswordAuthentication no` en `99-vaecos-hardening.conf` + fix de `50-cloud-init.conf` (first-match-wins en orden alfabético)
12. ✅ Smoke test desde fuera: `curl -sI https://app.vaecos.com/login` → 200 OK + login web validado por dueño

### Variables de entorno adicionales para producción

```env
FLASK_SECRET_KEY=<valor aleatorio largo>
VAECOS_ENV=production
V04_HOST=127.0.0.1
V04_PORT=8765
```

---

## Decisiones de arquitectura registradas

| Decisión | Elección | Alternativa descartada | Razón |
|----------|----------|----------------------|-------|
| Web framework | Flask | stdlib http.server | No tiene auth/sessions/uploads |
| Web framework | Flask | FastAPI | Sin API REST pública; server-side render es suficiente |
| DB fase inicial | SQLite WAL | PostgreSQL | Migración innecesaria para 4 usuarios |
| Auth | Flask sessions + bcrypt | JWT | Stateless innecesario en web clásica |
| Proxy | Caddy | nginx | TLS automático, config mínima |
| Despliegue | systemd | Docker | Overhead innecesario para servicio único |
| Excel | openpyxl | pandas | pandas es excesivo para solo parsing |
| Diseño | Jinja2 + Geist + tokens DESIGN.md | Extender render.py actual | CSS embebido en Python acumula deuda visual |
| Lógica de negocio | Reutilizar v0.2 sin rewrite | Reescribir | El motor de reglas y carriers son estables |

---

## Qué NO cambia en ninguna fase

- El motor de reglas (`core/rules.py`) — lógica estable, cubierta por tests.
- El Carrier Protocol — los carriers existentes siguen funcionando sin modificación.
- El schema SQLite base — se extiende con nuevas tablas, nunca se reemplaza.
- Los tests `unittest` — siguen siendo la suite de regresión principal.
- Las migraciones idempotentes — cada nueva tabla sigue el mismo patrón.
