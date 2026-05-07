# VAECOS Tracking Platform — Roadmap Estratégico

Version: v1.1
Fecha: 2026-05-07
Baseline: v0.4 (Flask, auth, snapshot local de Notion, edición desde la app)

> Este documento define el roadmap estratégico del producto.
> El estado técnico detallado del proyecto vive en `docs/roadmap.md`.
> Los requerimientos completos están en `docs/PRD.md`.

---

## Fase 1 — Flask + Auth + Excel + UX para operadora ✅ Completada en local

**Objetivo cumplido**: la herramienta dejó de ser un mini-server local single-user con HTML embebido y pasó a ser una aplicación Flask multi-usuario con login, gestión de guías, importación desde el ERP y notas/edición desde la app. Falta solo el despliegue al VPS para cerrarla formalmente.

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

### Lo que queda para cerrar Fase 1

- [ ] Validación con la operadora durante 3-5 días sin tocar Notion
- [ ] Retiro formal de v0.3 (archivar código + actualizar `iniciar.bat` para apuntar a v0.4)
- [ ] Despliegue en VPS Hostinger: systemd + Caddy + HTTPS

### Lo que NO cambió en Fase 1

- El motor de tracking (`run_tracking`) sigue leyendo guías activas desde Notion en cada corrida — la lectura desde la tabla local es Fase 2.
- El motor de reglas y los carriers no se tocan.
- Notion sigue recibiendo escrituras: el motor cuando aplica cambios y la operadora cuando edita estados desde la app (mirroring atómico).

### Criterios de salida (estado)

- [x] Flask + auth + Excel + diseño base funcionando y validados en local.
- [x] Usuarios pueden hacer login con roles (`admin` / `user`) y operar.
- [x] Se puede importar un Excel de guías → crea las páginas en Notion → dispara corridas.
- [x] Todas las rutas están protegidas por sesión.
- [ ] VPS contratado y plataforma desplegada con HTTPS.

---

## Fase 2 — DB interna como fuente de verdad

**Objetivo**: La plataforma deja de depender de Notion para leer guías. La DB local es la única fuente de verdad operacional. Notion queda como espejo de salida opcional o se deprecia.

### Estado parcial (heredado de Fase 1)

Durante Fase 1 ya se construyó parte de la base que originalmente pertenecía a Fase 2:

- [x] **Tabla `guides`** en SQLite con 14 columnas (page_id, guia, cliente, telefono, estado_novedad, carrier, producto, valor, cantidad, fecha_ultimo_seguimiento, archived, last_synced_at, created_at)
- [x] **Sync inicial**: 313 guías sincronizadas desde Notion (315 leídas, 2 incompletas)
- [x] **Vista de gestión** (`/all-guides`) con filtros, indicador Auto vs Manual
- [x] **Perfil de cliente** con DPI persistido y agrupación por DPI

### Lo que falta para cerrar Fase 2

- [ ] `run_tracking` lee la lista de guías a procesar desde la tabla `guides` (filtrando por `estado_novedad NOT IN excluded_states`) en vez de `NotionProvider.fetch_active_guides()`
- [ ] `--apply` pasa a escribir solo en la tabla local; Notion queda como mirror opcional configurable
- [ ] Validación de consistencia: comparar las 313 guías locales contra Notion mediante un hash/checksum periódico
- [ ] Permitir agregar guías nuevas desde la app (sin pasar por Excel ni Notion)
- [ ] Permitir editar otros campos además de `estado_novedad` (producto, valor, cantidad, teléfono) si la operadora lo necesita

### Criterios de salida

- 100% de guías leídas y procesadas desde la BD local.
- Corridas funcionando completamente sin tocar Notion en lectura.
- 2 semanas de operación normal validada sin depender de Notion como fuente.
- Notion declarado opcional (sigue como mirror de salida solo si así se decide).

---

## Fase 3 — Score de cliente y nuevo diseño UI

**Objetivo**: Inteligencia operativa visible. La plataforma se ve y se siente como una herramienta profesional.

### Alcance

- [ ] Score de cliente: cálculo automático post-corrida, clasificación verde/amarillo/rojo
- [ ] Vista de ranking de clientes con score y KPIs agregados
- [ ] Nuevo diseño UI completo (sistema de diseño de `docs/DESIGN.md`: Inter, sidebar dark, tokens de color)
- [ ] Analytics avanzados con filtros por fecha, carrier y cliente
- [ ] Exportación a Excel desde vistas clave (corridas, clientes, atención)
- [ ] Paginación en todas las vistas de tabla

### Criterios de salida

- Score calculado y visible para > 90% de los clientes con pedidos terminales.
- Nuevo diseño desplegado y validado por los 4 usuarios.
- Analytics con filtros de fecha y carrier funcionando.
- Exportación a Excel desde al menos corridas y clientes disponible.

---

## Fase 4 — Scheduler, notificaciones y mobile

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

## Fase 5 — Expansión y escala

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
| v0.4 (en desarrollo) | 2026-05-06 → 2026-05-07 | Flask + auth + Excel + sync Notion + edición desde la app + notas con historial + búsqueda + modo oscuro + sidebar colapsable |
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
| Score solo sobre estados terminales | Fase 3 | Los intermedios no representan un resultado definitivo |
| PostgreSQL solo si la carga lo requiere | Fase 5 | Sin overhead prematuro de infraestructura |
