# Seguimiento VAECOS

VAECOS Seguimiento es la plataforma logística + financiera interna de VAECOS Guatemala. Cumple cuatro funciones:

1. **Seguimiento de guías**: reconcilia el estado de las guías en Notion contra lo que reporta el transportista (Effi), aplica reglas configurables, y actualiza Notion automáticamente.
2. **Creador de guías (Effi)**: convierte órdenes de venta confirmadas en remisiones + guías CARGO EXPRESO en el ERP de Effi sin intervención manual. Incluye clasificador determinista + IA (MiniMax) para validar direcciones, cola humana para excepciones, y digest por email.
3. **Módulo financiero**: libro de movimientos en COP (ingresos / egresos / transferencias), categorías multi-tag, analytics con KPIs, export Excel.
4. **Asistente IA conversacional**: widget flotante con MiniMax M2.7 que responde preguntas operativas, financieras y del manual de uso. 6 tools con function calling, cero alucinaciones, audit log completo.

Aplicación web multi-usuario en producción en `https://app.vaecos.com`.

## Estado actual (2026-05-14)

- **Producción**: `https://app.vaecos.com` — Hostinger VPS + Caddy (TLS automático) + systemd + Waitress
- **Interfaz principal**: v0.4 (Flask + auth + dark mode + UI refresh completo + finanzas + IA)
- **Tracking** (Fase 2 — parcial): motor lee desde local, edición de campos, alta/archivo/restauración entregados. Pendiente 2.4 (inversión de polaridad).
- **Creador guías Effi** (Fase 3): módulo completo end-to-end (catálogo con aliases, classifier, address regex+IA, bot Playwright, cola humana, audit log, trigger UI/cron, digest diario por email, auto-relogin).
- **Inteligencia operativa + UI refresh** (Fase 4 — 2026-05-14): analytics rediseñado con KPIs operativos, paginación en 7 vistas, export Excel, crumbs, filterbar pattern unificado, forms vanilla CSS modernizados.
- **Módulo financiero + Asistente IA** (Fase 5 — 2026-05-14): 445 movimientos importados desde Notion, CRUD completo con multi-categoría, analytics + export. Widget IA con 6 tools (logística + finanzas + búsqueda + clientes + corridas + manual del aplicativo), tool use iterativo, anti-alucinación validada, rate limit 30/h, audit log.
- **Reglas del motor**: CRUD completo admin-only (`/rules`) con historial de auditoría.

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

### Seguimiento de guías

- **Auth multi-usuario**: login/logout, cambio de contraseña, perfil editable (`/mi-cuenta`), rate limiting.
- **Dashboard operativo**: `/`, `/attention`, `/analytics`, `/all-guides`, `/search`, detalles por guía y por cliente.
- **Corridas en background**: `/run/new` dispara un thread con polling de progreso. Auto-sync con Notion al terminar.
- **Importación Excel**: `/import` con plantilla descargable, vista previa + confirm. Crea páginas nuevas en Notion.
- **Edición de guías** (Fase 2.2): teléfono, producto, valor, cantidad — atómico Notion → local + audit. Campos vacíos NO borran datos en Notion.
- **Crear nueva guía** (Fase 2.3): `/guides/new` con formulario.
- **Archivar / restaurar** (Fase 2.3): soft-delete con papelera de 30 días vía archive de Notion.
- **Dark mode**, sidebar colapsable, favicon, búsqueda global.

### Reglas del motor (admin-only)

- **CRUD completo** en `/rules`: lista filtrable, crear, editar, toggle, eliminar, historial de auditoría.
- Cada cambio queda registrado en `rule_history` con autor.
- Soporta priorización, matching por estado / novedad / días desde último seguimiento, plantillas de motivo con placeholders.

### Creador de guías (módulo Effi)

- **Catálogo de productos editable** en `/effi/catalog` con aliases para tolerancia a variantes en descripción.
- **Clasificador determinista**: combo CREMA+GEL, íntimos femeninos (texto manual "N* PRODUCTO FEMENINO VAECOS"), otros (copiar del documento), mixto → escalation.
- **Validador de direcciones híbrido**: regex con 4 patrones (agencia / urbana cardinal / geográfica+landmark / local interno) + **IA MiniMax M2.7** como segunda opinión cuando regex no está confidente. Few-shot con ejemplos canónicos guatemaltecos.
- **Bot Playwright headless**: scrape de órdenes, modal de remisión/guía con snapshot+diff para leer IDs nuevos, retry con detección de submit fallido + screenshot/HTML dump en errores.
- **Idempotencia**: cada orden procesada se registra con PK (no se reprocesa).
- **Cola humana** en `/effi/queue` para casos no automatizables. Dedupe: una orden ya pendiente no genera nuevo email hasta cambiar de estado.
- **Audit log granular** en `/effi/audit`.
- **Trigger manual desde UI** (`/effi/run/manual`) o **cron en VPS** cada hora.
- **Email digest HTML** mobile-first con resumen consolidado (KPIs + listas por categoría) — solo cuando hay novedades reales.

### Módulo financiero (Fase 5.1)

- **Movimientos** (`/finanzas`): tabla en COP con filtros por año (default actual), mes, tipo (ingreso/egreso/transferencia), categoría y búsqueda. Paginación 50/página. KPIs en cabecera (ingresos, egresos, balance, count).
- **CRUD** (`/finanzas/new`, `/finanzas/<id>/edit`, `/finanzas/<id>/delete`): formulario con date picker, monto formato colombiano (`1.234.567,89`), multi-select de categorías, observación, vinculación opcional a guía. Audit trail con `creado_por` / `actualizado_por`. Permisos: todos crean, creador o admin editan, solo admin borra.
- **Multi-categoría real**: un movimiento puede tener N categorías (ej. "DEUDA + PUBLICIDAD" en un pago de tarjeta).
- **Analytics** (`/finanzas/analytics`): KPIs del período + top categorías + evolución mensual + export a `.xlsx`.
- **Catálogo de categorías** (`/finanzas/categorias`, admin-only): CRUD inline, color picker, toggle activar/desactivar. No se pueden borrar (FK RESTRICT protege históricos).
- **Migración inicial**: histórico de Notion importado vía `scripts/import_finanzas_notion.py` (idempotente, hash determinista por fila).

### Asistente IA conversacional (Fase 5.2)

Widget flotante en esquina inferior derecha, disponible en cualquier pantalla con sesión activa.

- **Stack**: MiniMax M2.7 (OpenAI-compatible) — reusa la integración del validador de direcciones del bot Effi.
- **Tool use iterativo**: el modelo llama funciones tipadas (no SQL crudo) y razona sobre los resultados.
- **6 tools expuestas**:
  - `get_logistic_summary(period)` — KPIs guías por período
  - `get_finanzas_summary(period, tipo)` — ingresos/egresos/balance + top categorías + evolución mensual
  - `search_guides(query, limit)` — búsqueda por número, cliente o teléfono
  - `get_top_clients(period, limit)` — ranking
  - `list_recent_runs(limit)` — últimas corridas
  - `get_app_help(topic)` — manual de uso (13 tópicos: overview, guías, estados, corridas, reglas, importar, effi, finanzas, analytics, buscar, atención, usuarios, ia, deploy)
- **Anti-alucinación**: system prompt con regla explícita; si no tiene la data, dice "no sé" honestamente y ofrece alternativa.
- **Historial persistente** por usuario (últimos 20 turnos, botón "limpiar").
- **Audit log**: cada tool call queda en `ai_audit_log` con args, latency, ok/error.
- **Rate limit**: 30 mensajes/hora por user (Flask-Limiter por user_id).
- **Endpoints**: `POST /ai/chat`, `GET /ai/chat/history`, `POST /ai/chat/clear`.

### Admin

- `/users`: crear, activar/desactivar, resetear contraseñas, asignar rol admin/user.
- `/effi/catalog`: gestión del catálogo de productos VAECOS para el clasificador.
- `/finanzas/categorias`: gestión del catálogo de categorías financieras.
- `/rules`: gestión de reglas del motor de tracking.

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

# Effi ERP (módulo Creador guías)
EFFI_USERNAME=
EFFI_PASSWORD=
EFFI_SESSION_PATH=v0.2/data/effi-session.json
EFFI_HEADLESS=true
EFFI_BASE_URL=https://effi.com.co

# IA (validación de direcciones + asistente conversacional, MiniMax, OpenAI-compat)
AI_ADDRESS_VALIDATION=auto                # auto = on si hay API key
MINIMAX_API_KEY=                           # requerido para el bot Effi + asistente IA
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_TIMEOUT_SECONDS=30                 # timeout por llamada al modelo (chat)

# Notificaciones email (opcional)
NOTIFY_EMAIL=                              # destinatario(s), separados por coma
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_SSL=false
EFFI_DAILY_DIGEST_ONLY=true                # producción: solo digest diario 22:00 GT, sin email por corrida
```

## Scripts CLI del módulo Effi

```powershell
# Generar/renovar sesión Effi (login interactivo, una vez por mes aprox.)
python scripts/effi_login.py

# Escaneo read-only (no escribe nada en Effi)
python scripts/effi_dry_run.py --limit 5

# Procesar UNA orden específica
python scripts/effi_run_one.py --order 5343 --apply

# Procesar todas las pendientes (usado por cron VPS)
python scripts/effi_run.py --apply --limit 10

# Limpieza de un registro corrupto con IDs reales
python scripts/effi_mark_done.py --order 5343 --remision 3907 --guia 4015

# Probar configuración SMTP sin esperar evento real
python scripts/effi_test_email.py

# Diagnóstico de MiniMax
python scripts/effi_ai_debug.py

# Digest diario por email (cron: 0 3 * * * en VPS = 21:00 GT)
python scripts/effi_daily_digest.py --hours 24
python scripts/effi_daily_digest.py --hours 168 --dry-run    # preview semana
```

## Scripts CLI del módulo Finanzas

```powershell
# Importar histórico desde Notion (dry-run primero, después --apply)
python scripts/import_finanzas_notion.py --csv "docs/notion-export/finanzas-2025.csv" --csv "docs/notion-export/finanzas-2026.csv"
python scripts/import_finanzas_notion.py --csv "docs/notion-export/finanzas-2025.csv" --csv "docs/notion-export/finanzas-2026.csv" --apply

# Re-correr es idempotente — usa external_ref UNIQUE (hash determinista por fila)
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
