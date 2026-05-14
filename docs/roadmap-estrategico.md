# VAECOS Tracking Platform — Roadmap Estratégico

Version: v1.5
Fecha: 2026-05-14
Baseline: v0.4 + módulo Effi + Finanzas + Asistente IA (Flask + bot Playwright + MiniMax en producción, https://app.vaecos.com)

> Este documento define el roadmap estratégico del producto.
> El estado técnico detallado del proyecto vive en `docs/roadmap.md`.
> Los requerimientos completos están en `docs/PRD.md`.

---

## Fase 1 — Flask + Auth + Excel + UX para operadora + VPS ✅ Completada

**Objetivo cumplido**: la herramienta dejó de ser un mini-server local single-user con HTML embebido y pasó a ser una aplicación Flask multi-usuario corriendo en producción con HTTPS automático en `https://app.vaecos.com`.

### Lo entregado

- [x] Migración del web layer: `http.server` stdlib → Flask 3.1 con blueprints (`auth`, `dashboard`, `runs`, `import_guides`, `users`)
- [x] Sistema de autenticación con bcrypt, sesiones firmadas, login/logout/change-password
- [x] `@login_required` y `@admin_required` en todas las rutas
- [x] Gestión de usuarios: crear con rol, activar/desactivar, restablecer contraseña, eliminar
- [x] Bootstrap inicial de admin desde `.env` (`V04_BOOTSTRAP_EMAIL` / `V04_BOOTSTRAP_PASSWORD`)
- [x] Ingesta de guías por Excel del ERP: upload, parser flexible (header detection con normalización NFKD + case-insensitive), preview con stats, confirmación, log en `import_log`
- [x] Excel parsing extrae 6 campos: cliente (Destinatario), guía, DPI/teléfono, valor recaudo, contenido (cantidad + producto), estado inicial
- [x] Confirmación de importación crea las páginas en Notion vía API con resolución case-insensitive de selects
- [x] Diseño nuevo con design system (Geist Sans + Mono, tokens CSS, sidebar oscuro, paleta cálida)
- [x] **Sidebar colapsable** con persistencia en localStorage y tooltips en estado colapsado
- [x] **Modo oscuro** completo con detección de `prefers-color-scheme`, sin FOUC
- [x] **Búsqueda inteligente** (`/search`): un input que detecta guía, DPI o nombre y enruta automáticamente
- [x] **Página `/all-guides`**: snapshot de TODAS las guías de Notion (incluyendo estados que el motor no procesa) con filtros por estado/carrier/búsqueda
- [x] **Sync con Notion**: botón manual + auto-sync al final de cada corrida; trae todas las páginas a la tabla local `guides`
- [x] **Notas con historial por guía**: comentarios persistentes con autor + timestamp, AJAX, Ctrl+Enter, borrado por autor o admin
- [x] **Edición de estado desde la app**: dropdown inline en `/all-guides` y en `/guides/<guia>`, escritura atómica (Notion → local → audit), audit trail visible en `guide_edits`
- [x] Botón "Correr esta guía" (dry-run y apply) desde `/guides/<guia>`
- [x] Persistencia local del DPI/teléfono (columna nueva en `run_results`, backfill desde Notion: 163 rows / 126 guías)
- [x] Tabla responsive en `/users` y página `/users/<id>/reset-password`
- [x] Notas de corrida con AJAX (la página ya no se desplaza al inicio al guardar)

### Lo entregado en producción (deploy completado 2026-05-07)

- [x] **VPS Hostinger** (KVM 2: 2 vCPU / 8 GB / 100 GB) con Ubuntu 24.04 LTS
- [x] **HTTPS automático** con Caddy + Let's Encrypt en `https://app.vaecos.com`
- [x] **DNS** configurado vía Hostinger MCP (A record `app.vaecos.com → 2.24.206.197`)
- [x] **systemd** con auto-restart (`vaecos.service`)
- [x] **Firewall UFW**: solo puertos 22 / 80 / 443
- [x] **SSH hardening**: solo key auth (clave en `~/.ssh/vaecos_vps`), password rejected
- [x] **Usuario vaecos** con sudo NOPASSWD para administración
- [x] **`.env` productivo** con `FLASK_SECRET_KEY` fresh, `V04_BOOTSTRAP_PASSWORD` random alphanumeric, chmod 600
- [x] **ProxyFix** activo en producción para que Flask vea la IP real del cliente detrás de Caddy
- [x] **Bootstrap admin** seeded automáticamente al primer arranque del servicio
- [x] **Login validado** end-to-end por el dueño en producción

### Lo que queda para cerrar Fase 1 formalmente

- [x] Migrar la BD de la operadora al VPS con `scripts/post_restore.py` (2026-05-07)
- [x] Configurar backups automáticos del SQLite (cron + rotación 14 días, 2026-05-07)
- [x] Eliminar generación de reportes automáticos `.csv/.md/.pdf` (toda la info ya está en la app, 2026-05-07)
- [x] Edición de perfil propio + popover en sidebar (`/mi-cuenta`, 2026-05-07)
- [ ] Validación con la operadora 3-5 días en producción sin tocar Notion
- [ ] Crear los usuarios reales desde `/users` (operadora + fundadores)
- [ ] Retiro formal de v0.3 (archivar código + eliminar `iniciar.bat` viejo)

### Lo que NO cambió en Fase 1

- El motor de tracking (`run_tracking`) sigue leyendo guías activas desde Notion en cada corrida — la lectura desde la tabla local es Fase 2.
- El motor de reglas y los carriers no se tocan.
- Notion sigue recibiendo escrituras: el motor cuando aplica cambios y la operadora cuando edita estados desde la app (mirroring atómico).

### Criterios de salida (estado)

- [x] Flask + auth + Excel + diseño base funcionando y validados en local.
- [x] Usuarios pueden hacer login con roles (`admin` / `user`) y operar.
- [x] Se puede importar un Excel de guías → crea las páginas en Notion → dispara corridas.
- [x] Todas las rutas están protegidas por sesión.
- [x] VPS contratado y plataforma desplegada con HTTPS automático.
- [x] Login admin validado en producción.

---

## Fase 2 — DB interna como fuente de verdad

**Objetivo**: La plataforma deja de depender de Notion para leer guías. La DB local es la única fuente de verdad operacional. Notion queda como espejo de salida opcional o se deprecia.

### Estado parcial (heredado de Fase 1)

Durante Fase 1 ya se construyó parte de la base que originalmente pertenecía a Fase 2:

- [x] **Tabla `guides`** en SQLite con 14 columnas (page_id, guia, cliente, telefono, estado_novedad, carrier, producto, valor, cantidad, fecha_ultimo_seguimiento, archived, last_synced_at, created_at)
- [x] **Sync inicial**: 313 guías sincronizadas desde Notion (315 leídas, 2 incompletas)
- [x] **Vista de gestión** (`/all-guides`) con filtros, indicador Auto vs Manual
- [x] **Perfil de cliente** con DPI persistido y agrupación por DPI

### Lo entregado en Fase 2 (2026-05-07)

- [x] **2.1 Lectura local**: `run_tracking` lee desde la tabla `guides` (filtrando por `estado_novedad NOT IN excluded_states`). Pre-sync Notion→local automático antes de cada corrida (con fallback a snapshot local si Notion falla)
- [x] **2.2 Edición de campos**: la operadora puede editar `producto`, `telefono`, `valor`, `cantidad` desde `/guides/<g>` con escritura atómica (Notion → local → audit)
- [x] **2.3 Crear guías nuevas desde la app**: formulario `/guides/new` con validaciones, sin pasar por Excel ni Notion
- [x] **2.3 Archivar / restaurar guías** desde la app (soft-delete a la papelera de Notion, recuperable por 30 días)

### Lo que falta para cerrar Fase 2

- [ ] **2.4 Inversión de polaridad**: `--apply` y edits pasan a escribir solo en la tabla local; Notion queda como mirror best-effort configurable
- [ ] **2.5 Validación de consistencia**: comparar las guías locales contra Notion mediante un hash/checksum periódico

### Criterios de salida

- 100% de guías leídas y procesadas desde la BD local.
- Corridas funcionando completamente sin tocar Notion en lectura.
- 2 semanas de operación normal validada sin depender de Notion como fuente.
- Notion declarado opcional (sigue como mirror de salida solo si así se decide).

---

## Fase 3 — Bot Effi (Creador de guías automatizado) ✅ Completada (2026-05-13)

**Objetivo cumplido**: eliminar el cuello de botella manual de creación de guías en el ERP Effi. La operadora ya no abre Effi para crear remisiones/guías una por una — un bot Playwright lo hace de forma continua y deja todo sincronizado con Notion y la app.

### Lo entregado

- [x] **Bot Playwright** (`v0.4/app/effi_guides/bot.py`) — Chromium headless con `storageState` reusable; sesión persistida en `effi-session.json` para evitar re-login a cada corrida
- [x] **Flujo end-to-end**: scrape `/app/orden_v` → filtrar `PEDIDO CONFIRMADO` sin remisión → leer productos del modal → validar dirección → clasificar contra catálogo → `convert_to_remision` → `create_guia` → `read_guia_row_data` (tracking + valor)
- [x] **Catálogo de productos editable** (`/effi/catalog`, admin-only) con `descripcion_exacta`, `aliases` JSON, tipo (`intimo_femenino` / `otro`) y precio declarado
- [x] **Clasificación automática** de pedidos: combo / íntimo femenino / otro / escalación, con plan de valor declarado y contenido (copiar documento vs texto manual)
- [x] **Validación de dirección híbrida regex + IA**:
  - Patrones regex para casos comunes (Pattern A/B/C/D) que cubren 80%+ de direcciones válidas en Guatemala
  - Fallback a IA (MiniMax M2.7) con few-shot prompting cuando regex no concluye
  - Detección de prefijo estructural de Effi (`Depto / Muni / Localidad (Zona N) / texto libre`) para no confundir el bot
- [x] **Cola humana** (`/effi/queue`) — pedidos no automatizables van a una vista para revisión manual con motivo y detalles JSON
- [x] **Audit log granular** (`/effi/audit`) — cada acción del bot queda registrada con timestamp, orden, payload y `ok`
- [x] **Idempotencia + recovery logic**:
  - Snapshot/diff de IDs en tablas para detectar la nueva remisión/guía sin parsing frágil de HTML
  - Detección de remisión preexistente (`find_remision_for_order`) y guía preexistente (`find_guia_for_remision`) para rerun seguro tras fallos parciales
  - Recovery de `ERR_ABORTED` cuando la navegación post-submit cancela el `goto` de lectura
  - Espera explícita del AJAX cascading del modal (`_wait_modal_ajax_settled`) para evitar validation errors intermitentes
- [x] **Auto-sync a Notion** — al crear una guía en Effi, se crea automáticamente la página en Notion con tracking, producto, valor a recaudar (scrapeado de "Recaudo: $X"), teléfono y estado `Sin recolectar`. Cierra el loop: ya no hace falta `/import` manual de Excel
- [x] **Cron horario en VPS** (`scripts/effi_run.py --apply`) corriendo cada hora con headless
- [x] **Disparo manual desde UI** (`/effi` dashboard) con job en background, progress polling JSON, modo dry-run o apply
- [x] **Notificaciones email**:
  - Digest diario a las 22:00 GT con KPIs agregados, sustituye al email por corrida (que con cron horario se volvía spam)
  - Alertas inmediatas SOLO para errores críticos (sesión expirada con auto-relogin fallido, fatal de cron)
- [x] **Auto-relogin** — cuando el bot detecta sesión expirada, intenta loguearse automáticamente con `EFFI_USERNAME` / `EFFI_PASSWORD` antes de notificar. Solo si falla (reCAPTCHA, creds rechazadas) manda email
- [x] **Comandos CLI** para operación: `effi_login.py` (renovar sesión), `effi_dry_run.py` (escanear sin escribir), `effi_run_one.py` (procesar una orden), `effi_run.py` (masivo)

### Tablas SQLite añadidas (migración idempotente en `v0.2/vaecos_v02/storage/db.py`)

- `effi_catalog` — productos con clasificación y precio declarado
- `effi_orders` — PK `orden_id`, status (`done` / `failed` / `human_review` / `pending`)
- `effi_audit_log` — historial granular de acciones del bot
- `effi_review_queue` — cola para casos no automatizables

### Decisiones técnicas

- **Playwright sobre Selenium**: API más limpia, mejor manejo de selectores, snapshots/tracing built-in, soporte robusto de `storageState`
- **Sesión persistente vs login en cada corrida**: storage state vive semanas; renovación manual mensual (o auto-relogin) es más barato que reCAPTCHA cada hora
- **Validación de dirección híbrida (regex + IA) vs solo-IA**: regex cubre el 80% gratis; IA solo para casos no triviales — ahorra costo y latencia
- **Idempotencia por snapshot/diff vs parsing del modal de respuesta**: el modal de Effi a veces queda lingering tras submit exitoso; el snapshot de la tabla destino es la fuente de verdad confiable

### Criterios de salida cumplidos

- [x] Bot creando guías 24/7 en producción con cron horario
- [x] Cero intervención manual para pedidos del happy path
- [x] Cola humana operacional para casos no automatizables
- [x] Sync end-to-end (Effi → tabla local → Notion) sin pasos manuales
- [x] Sistema de notificaciones que no genera spam

---

## Fase 4 — Inteligencia operativa y refresh UI ✅ Completada (2026-05-14)

**Objetivo cumplido**: la plataforma se ve y se siente como una herramienta profesional. Analytics rediseñado con KPIs operativos (no técnicos), paginación en todas las tablas, exportación a Excel para Effi, y refresh visual integral con CSS vanilla alineado al design-system.

### Lo entregado

- [x] **Analytics rediseñado** con KPIs operativos: Por recoger, Backlog antiguo, Tasa de resolución, Tiempo de ciclo, Guías activas (5 cards en línea)
- [x] **Manual de métricas** (`/analytics/manual`) — explica qué muestra, cómo se calcula y qué acción tomar para cada métrica
- [x] **Tooltips inline** con ícono ⓘ en cada KPI (CSS-only, escape de overflow vía `:has()`)
- [x] **Filtros de fecha** en analytics: presets `7d/30d/90d` + rango custom `from/to` + umbral backlog configurable
- [x] **Paginación server-side** en 7 vistas: `/runs`, `/runs/<id>`, `/all-guides`, `/search`, `/clients/<c>`, `/effi/queue`, `/effi/audit`
- [x] **Export Effi a Excel** desde el historial de corridas (.xlsx organizado en lugar del CSV crudo)
- [x] **Por recoger — coherencia** entre los 3 displays distintos del KPI (homepage, analytics, detalle): todos usan tabla `guides` como fuente de verdad
- [x] **UI refresh integral** (2026-05-14):
  - Crumbs (`Operación / Centro Operativo`, etc.) en todas las vistas como navegación contextual
  - Centro operativo (`/`) rediseñado: banner estructurado, 4 KPIs, top 5 atención + distribución de resultados con barras horizontales, trend chart
  - `attention.html` con filterbar de chips por categoría (Cambios / Revisión manual / Errores)
  - Filterbar pattern unificado en 5 páginas (`analytics`, `all-guides`, `runs`, `run_detail`, `rules`) con grupos visuales etiquetados y separadores verticales
  - Forms vanilla CSS modernizados:
    - `<select>` con `appearance: none` + chevron SVG custom (sin dropdown nativo del SO)
    - `<input type="checkbox">` con `appearance: none` + check SVG (sin cuadrito nativo de Windows)
    - `<input type="date">` con icono nativo invisible + calendar SVG custom
    - `<input type="number">` sin spinners feos
  - `.btn.brand` (rojo VAECOS) aplicado consistente a CTAs primarios
  - Dark mode validado en todas las pantallas, incluyendo forms

### Decisiones de alcance

- ❌ **Score de cliente retirado del alcance**: el volumen actual de pedidos por cliente no justifica el filtro/cálculo. Reevaluable en Fase 7 si el negocio escala.
- ❌ **Vista de ranking de clientes con score**: dependía del score, también retirada.

### Decisión técnica

Se evaluó migrar a Tailwind/framework CSS durante esta fase y se descartó. Razones: el design-system vanilla ya está implementado (749 líneas en `styles.css` + ~700 en `app.css`), la app está en producción con deploy trivial (`git pull && systemctl restart`), agregar Node.js + build step al VPS suma deuda técnica sin resolver dolor existente. Los problemas reales (forms con look nativo del SO) se resolvieron con ~140 líneas de CSS moderno (`appearance: none`, custom properties, `:has()`).

### Criterios de salida cumplidos

- [x] Nuevo diseño desplegado y validado visualmente con Playwright (light + dark mode en todas las pantallas principales).
- [x] Analytics con filtros de fecha funcionando.
- [x] Exportación a Excel desde corridas disponible.
- [x] Paginación en todas las vistas con muchas filas.
- [x] Forms consistentes en toda la app (selects, checkboxes, dates).

---

## Fase 5 — Módulo financiero + Asistente IA conversacional ✅ Completada (2026-05-14)

**Objetivo cumplido**: la plataforma dejó de ser solo logística. Ahora maneja también la capa financiera (ingresos / egresos / saldos en COP) y tiene un asistente IA conversacional que responde preguntas operativas + financieras + del manual de uso en lenguaje natural.

### 5.1 Módulo financiero ✅

Implementación con **Opción C (híbrido)** — import one-shot del histórico de Notion + entrada nativa nueva en la app. Mismo patrón que se aplicó a las guías en Fase 2.

**Entregado**:

- [x] **Schema SQLite** — `fin_movements` (id, fecha, tipo `ingreso`/`egreso`/`transferencia`, monto_centavos, moneda COP, observación, guia_ref opcional, external_ref para idempotencia, audit `creado_por`/`actualizado_por`), `fin_categories` (nombre, color hex, activa), `fin_movement_categories` (M:N).
- [x] **Migración desde Notion** — script `scripts/import_finanzas_notion.py` idempotente: parser de fecha español (`"9 de febrero de 2026"` → ISO), parser de monto colombiano (`"2.004.599,67 COP"` → centavos), detección de transferencias internas (filas con ambos montos), soporte multi-categoría comma-separated. Procesó 445 filas (302 de 2025 + 143 de 2026) con balance = 0 verificable contra el original.
- [x] **Listado** (`/finanzas`) — tabla con filtros por año (default actual), mes, tipo, categoría, búsqueda libre. Paginación 50/página. Pills de categoría con color custom. KPIs en cabecera (ingresos, egresos, balance, count).
- [x] **CRUD de movimientos** — `/finanzas/new`, `/finanzas/<id>/edit`, `/finanzas/<id>/delete`. Form con date picker, monto con formato colombiano flex, multi-select de categorías, observación, vinculación opcional a guía. Permisos: todos crean, solo creador o admin edita, solo admin borra.
- [x] **Multi-categoría** — un movimiento puede tener N categorías (ej. "DEUDA + PUBLICIDAD" en un pago de tarjeta). Confirmado con 19 filas reales del histórico.
- [x] **Analytics financieros** (`/finanzas/analytics`) — KPIs del período, top categorías, evolución mensual. Filtro por año.
- [x] **Export Excel** — `.xlsx` con headers, autofilter, freeze pane. Aplica los mismos filtros del listado.
- [x] **Catálogo de categorías** (`/finanzas/categorias`, admin-only) — CRUD inline, color picker, toggle activar/desactivar. Las desactivadas se ocultan del form de nuevo movimiento pero siguen visibles en históricos (FK ON DELETE RESTRICT protege).
- [x] **Paleta visual muted** — 13 categorías con colores desaturados (L≈55-60%, S≈30-35%) para no saturar la UI.

### 5.2 Asistente IA conversacional ✅

**Stack**: MiniMax M2.7 (reusada del validador de direcciones del bot Effi) — endpoint OpenAI-compatible. Loop tool-use iterativo con parseo robusto de JSON, manejo de `<think>` blocks del modelo de razonamiento.

**Entregado**:

- [x] **Widget flotante** en esquina inferior derecha, disponible en cualquier pantalla con sesión activa. Estados colapsado (burbujita) / expandido (panel 380×540px). Persistencia de estado en localStorage.
- [x] **Backend** — Blueprint `/ai/` con 3 endpoints: `/ai/chat` (POST), `/ai/chat/history` (GET, hidrata al abrir), `/ai/chat/clear` (POST).
- [x] **6 tools expuestas** al modelo:
  - `get_logistic_summary(period)` — KPIs guías, breakdown por estado y carrier
  - `get_finanzas_summary(period, tipo)` — ingresos/egresos/balance + top categorías + breakdown mensual
  - `search_guides(query, limit)` — búsqueda por número/cliente/teléfono
  - `get_top_clients(period, limit)` — ranking de clientes por volumen y valor
  - `list_recent_runs(limit)` — últimas corridas con conteos
  - `get_app_help(topic)` — manual de uso del aplicativo (13 tópicos: overview, guías, estados, corridas, reglas, importar, effi, finanzas, analytics, buscar, atención, usuarios, ia, deploy)
- [x] **Anti-alucinación** — system prompt con sección dedicada "REGLA #1: cero alucinaciones". El modelo dice honestamente "no sé" cuando la data no está disponible en sus tools, y ofrece alternativas constructivas. Validado con 4 preguntas fuera de scope que correctamente rechazó.
- [x] **Manual integrado** — knowledge base estructurada en Python (`v0.4/app/ai/manual.py`) con scoring por keywords. El modelo lo consulta on-demand cuando el usuario pregunta cómo usar la app.
- [x] **Historial persistente** — tablas `ai_conversations` + `ai_messages` por usuario, últimos 20 turnos en context window. Botón "limpiar chat" disponible.
- [x] **Audit log** — tabla `ai_audit_log` registra cada tool call con args, latency_ms, ok/error. Trazabilidad completa.
- [x] **Rate limit** — 30 mensajes/hora por user via Flask-Limiter (key por user_id, no por IP).
- [x] **Markdown ligero** — render de `**bold**`, `*italic*`, `` `code` `` y saltos de línea en el widget.

### Performance medida en producción

| Tipo de pregunta | Latencia típica | Tool calls |
|---|---|---|
| Conversacional ("hola") | 1-3s | 0 |
| Una sola data tool | 3-5s | 1 |
| Cross-domain (logística + finanzas) | 8-16s | 2-3 |
| Pregunta del manual | 3-7s | 1 (`get_app_help`) |

### Decisiones arquitectónicas

- **Híbrido finanzas (Opción C)** en vez de nativo desde cero o sync continuo con Notion — preserva histórico sin atarse a Notion como fuente activa
- **MiniMax M2.7 sobre Claude API** — reusa infraestructura ya integrada, costo predecible, suficiente para el dominio
- **Tool use iterativo sobre snapshot** — más poderoso (queries específicas), aceptable la latencia extra para chat asíncrono
- **Manual en Python sobre RAG** — el volumen no justifica embeddings; scoring por keywords es suficiente y mantenible
- **Floating widget sobre página dedicada** — disponible siempre, fricción mínima
- **Monto en centavos INTEGER** en vez de REAL — evita errores de float con datos contables

### Criterios de salida cumplidos

- [x] Módulo financiero capturando movimientos en producción con histórico migrado (445 filas)
- [x] Analytics financieros funcionando con data real
- [x] Asistente IA respondiendo correctamente preguntas mixtas con cero alucinaciones
- [x] Auditoría completa de queries de IA disponible

---

## Fase 6 — Scheduler, notificaciones y mobile

**Objetivo**: La plataforma trabaja de forma proactiva. Accesible desde cualquier dispositivo.

### Alcance

- [ ] Corridas automáticas programadas (scheduler configurable por el admin)
- [ ] Notificaciones cuando termina o falla una corrida (canal a definir: email o webhook)
- [ ] Diseño responsive para dispositivos móviles
- [ ] Alertas tempranas: guías sin movimiento más de N días
- [ ] Indicadores de salud del sistema en tiempo real

### Criterios de salida

- Al menos una corrida automática configurada y funcionando de forma estable.
- Notificaciones entregadas de forma confiable.
- Plataforma operable desde celular.

---

## Fase 7 — Expansión y escala

**Objetivo**: El negocio crece, la plataforma crece con él.

### Alcance

- [ ] Carrier adicional real (Guatex u otro — infraestructura ya lista)
- [ ] Roles diferenciados: operador / supervisor / admin
- [ ] Gestión de usuarios ampliada para equipos más grandes
- [ ] Evaluación de migración SQLite → PostgreSQL según carga real
- [ ] Evaluación de evolución a SaaS o multi-empresa

### Criterios de entrada para esta fase

Al menos una de estas condiciones:
- Más de 4 usuarios activos.
- Corridas automáticas frecuentes con contención observable de escritura.
- Necesidad de permisos diferenciados por acción crítica.
- Interés en abrir la plataforma a otros clientes o empresas.

---

## Historial de versiones

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| v0.4.x (IA conversacional) | 2026-05-14 | Fase 5.2 cerrada. Widget flotante con MiniMax M2.7, 6 tools (logística, finanzas, búsqueda, top clientes, corridas, manual), tool use iterativo, anti-alucinación, audit log, rate limit 30/h. Manual integrado del aplicativo con 13 tópicos |
| v0.4.x (Finanzas) | 2026-05-14 | Fase 5.1 cerrada. Módulo financiero completo: schema SQLite (445 movimientos importados de Notion), CRUD, multi-categoría, analytics + export Excel, catálogo admin. Paleta muted desaturada |
| v0.4.x (Effi digest + auto-relogin) | 2026-05-14 | Digest diario en vez de email por corrida (apaga spam del cron horario). Auto-relogin del bot cuando expira sesión Effi. Recovery logic + idempotencia en `convert_to_remision` / `create_guia` |
| v0.4.x (UI refresh) | 2026-05-14 | Fase 4 cerrada. UI refresh integral: crumbs, home rediseñado, filterbar pattern, forms vanilla CSS modernizados (selects, checkboxes, dates sin look nativo). Score de cliente retirado de alcance |
| v0.4.x (Effi auto-sync) | 2026-05-13 | Bot Effi cierra el loop: auto-sync de guías nuevas a Notion (tracking, valor a recaudar, producto, teléfono). `/import` Excel queda casi obsoleto |
| v0.4.x (Effi bot) | 2026-05 | Módulo Creador guías Effi: bot Playwright, catálogo editable, validador dirección regex+IA, cola humana, audit log, cron horario en VPS, notificaciones email |
| v0.4 (producción) | 2026-05-07 | Deploy a VPS Hostinger con Caddy + TLS automático en https://app.vaecos.com. Hardening SSH, UFW, systemd, ProxyFix |
| v0.4 (dev) | 2026-05-06 → 2026-05-07 | Flask + auth + Excel + sync Notion + edición desde la app + notas con historial + búsqueda + modo oscuro + sidebar colapsable |
| v0.3.4.2 | 2026-05-02 | Hotfix: migración idempotente regla "Almacenado en bodega" reciente |
| v0.3.4 | 2026-05-01 | Refresh visual completo — RFC-001 + aesthetic refresh |
| v0.3.3 | 2026-04 | Corridas en background, progress page, scripts bat para usuaria final |
| v0.3.0 | 2026-04 | Dashboard web local, analytics, reglas editables desde web |
| v0.2.1 | 2026-04 | Multi-carrier (abstracción Carrier Protocol), Guatex stub |
| v0.2.0 | 2026-04 | Motor CLI, SQLite, reglas data-driven, TUI |

---

## Decisiones de alcance registradas

| Decisión | Fase | Razón |
|----------|------|-------|
| Excel como ingesta (no API ERP) | Fase 1 | El ERP actual no tiene API; exportación manual es el flujo aceptado |
| SQLite en Fase 1 (no PostgreSQL) | Fase 1 | 4 usuarios, baja concurrencia; datos ya en SQLite |
| Notion en coexistencia durante Fase 1 | Fase 1 | Migración gradual, sin cortar el flujo operativo actual |
| Sin scheduler en Fase 1 | Fase 1 | Corridas on-demand son suficientes para el equipo actual |
| Sin mobile en Fase 1 | Fase 1 | Desktop/laptop es suficiente para los 4 fundadores |
| Score solo sobre estados terminales | Fase 4 | Los intermedios no representan un resultado definitivo |
| Score de cliente retirado del alcance | Fase 4 (2026-05-14) | El volumen actual de pedidos por cliente no justifica el filtro. Reevaluable en Fase 7 |
| Vanilla CSS en vez de Tailwind | Fase 4 (2026-05-14) | Design-system ya implementado en CSS puro, deploy trivial sin Node, sin pain point que Tailwind resuelva mejor. Reevaluable si se agrega React o equipo frontend |
| Playwright sobre Selenium para el bot | Fase 3 (2026-05) | API más limpia, `storageState` reusable, mejor manejo de selectores. Selenium habría requerido más boilerplate |
| Sesión Effi persistente vs login en cada corrida | Fase 3 (2026-05) | reCAPTCHA en cada hora sería bloqueante. Storage state dura semanas, auto-relogin cubre la mayoría de expiraciones |
| Validación de dirección híbrida (regex + IA) | Fase 3 (2026-05) | Regex cubre ~80% gratis y rápido. IA solo para casos no triviales — ahorra costo y latencia |
| Digest diario vs email por corrida | Fase 3 (2026-05-14) | Cron horario × email por corrida = spam. Errores críticos siguen siendo inmediatos; rutina al digest 22:00 GT |
| Importación híbrida del módulo financiero (Opción C) | Fase 5.1 (2026-05-14) | Import one-shot del histórico de Notion + entrada nativa nueva. Mismo patrón que las guías en Fase 2. NO sync continuo con Notion — desacopla la app de Notion como fuente activa |
| IA con function calling, no SQL crudo | Fase 5.2 (2026-05-14) | Datos sensibles + riesgo de inyección. 6 funciones tipadas dan control y auditabilidad. Cada tool call queda en `ai_audit_log` |
| MiniMax M2.7 sobre Claude API para IA | Fase 5.2 (2026-05-14) | Reusa infraestructura ya integrada del validador de direcciones. Costo predecible. Modelo de razonamiento suficiente para el dominio. Reevaluable si la calidad no escala |
| Tool use iterativo sobre snapshot precomputado | Fase 5.2 (2026-05-14) | Permite queries específicas ("buscame guía X") que un snapshot no cubriría. Tradeoff latency aceptable para chat asíncrono |
| Manual del aplicativo en Python sobre RAG/embeddings | Fase 5.2 (2026-05-14) | Volumen no justifica vector DB. Scoring por keywords mantiene simplicidad y es mantenible directo en código |
| Floating widget IA sobre página dedicada | Fase 5.2 (2026-05-14) | Disponible en cualquier vista, fricción mínima, no requiere navegación |
| Anti-alucinación explícita en system prompt | Fase 5.2 (2026-05-14) | Reglas reforzadas: NUNCA inventar datos, decir "no sé" honestamente. Validado con 4 preguntas fuera de scope que el modelo rechazó correctamente |
| PostgreSQL solo si la carga lo requiere | Fase 7 | Sin overhead prematuro de infraestructura |
