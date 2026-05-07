# VAECOS Tracking Platform — PRD v2.0

Version: v2.0
Fecha: 2026-05-06
Estado: Activo
Owner: Fundadores VAECOS
Supersede: PRD v1.0 (2026-05-01)

---

## 1. Contexto y estado actual

VAECOS Tracking nació como una automatización para sincronizar estados de guías entre transportistas y Notion. El sistema actual (baseline v0.3.4.2) es:

- Motor operativo `v0.2`: corridas, motor de reglas data-driven, trazabilidad, CLI/TUI.
- Interfaz web local `v0.3`: dashboard operativo, analytics, reglas editables, corridas en background.
- Persistencia: SQLite local en la máquina de la operadora.
- Fuente de entrada: Notion (lista de guías activas).
- Fuente de tracking: Effi (scraping HTML).

El sistema resuelve el problema central pero tiene limitaciones estructurales: es local, single-user, y depende de Notion como fuente de entrada y salida.

---

## 2. Visión del producto

Convertir la herramienta local en una **plataforma web operativa interna**, alojada en VPS, accesible para los 4 fundadores de VAECOS desde cualquier dispositivo, con:

- Base de datos propia como fuente de verdad (sin Notion).
- Ingesta diaria de guías vía Excel exportado del ERP.
- Seguimiento constante y real por guía, cliente y transportadora.
- Analytics operativos e inteligencia sobre comportamiento de clientes.
- Score de cliente para identificar problemas recurrentes antes de que escalen.
- Diseñada para escalar en usuarios y carriers cuando el negocio crezca.

**Tipo de producto**: plataforma operativa interna formal, con potencial de evolucionar a SaaS en el futuro.

---

## 3. Objetivos

### Principales
1. Eliminar la dependencia de Notion como fuente de entrada y salida.
2. Tener una plataforma siempre activa, accesible para todos los operarios desde el VPS.
3. Estandarizar la ingesta de guías vía Excel (el ERP no tiene API).
4. Asegurar trazabilidad completa por guía, corrida y cliente.
5. Consolidar analytics e inteligencia operativa para toma de decisiones.
6. Introducir score de cliente para detectar problemas recurrentes.

### No objetivos en esta fase
- SaaS comercial.
- Integración directa con ERP (no tiene API).
- Aplicación móvil nativa.
- Soporte multi-empresa.
- Scheduler automático de corridas (fase posterior).

---

## 4. Usuarios

### Fase inicial (hoy)
- **4 fundadores VAECOS**, mismo nivel de acceso.
- Acceso principalmente desde desktop/laptop.

### Futuro (cuando el negocio crezca)
- Operarios de tracking adicionales.
- Roles diferenciados: operador, supervisor, admin.
- Acceso desde dispositivos móviles.

---

## 5. Problemas a resolver

| # | Problema | Impacto |
|---|----------|---------|
| P1 | Herramienta local, un solo usuario a la vez | No se puede trabajar en paralelo |
| P2 | Dependencia de Notion para leer y escribir guías | Fricción operativa, límite de datos propios |
| P3 | Ingesta de guías no estandarizada | Propensa a errores, no auditable |
| P4 | Sin visión unificada por cliente | No se detectan clientes problemáticos a tiempo |
| P5 | Sin score o clasificación de clientes | No hay inteligencia sobre comportamiento de compra/entrega |
| P6 | Datos históricos dispersos en Notion y SQLite | Sin fuente única de verdad |

---

## 6. Alcance funcional

### Baseline (v0.3.4.2 — lo que ya existe)
- Corridas dry-run/apply contra Effi + Notion.
- Motor de reglas data-driven editable desde web.
- Dashboard con últimas corridas, analytics básicos.
- Vista `/attention` con guías que requieren acción.
- Trazabilidad por guía y cliente en SQLite.
- Sistema de actualizaciones vía GitHub Releases.
- Progreso de corrida en tiempo real (background thread).

### Módulos objetivo de la plataforma

**Core operativo**
1. **Ingesta de guías** — upload de Excel diario, parsing, validación, preview y confirmación.
2. **Centro operativo** — resumen del estado del día: urgencia, última corrida, guías activas.
3. **Corridas** — ejecutar tracking contra carriers, dry-run y apply, progreso en vivo.
4. **Requiere atención** — vista diaria de excepciones con filtros y acciones.

**Trazabilidad**
5. **Detalle de guía** — timeline completo de estados, resultado de cada corrida, notas del operario.
6. **Detalle de cliente** — todos los pedidos, historial, score, indicadores.
7. **Historial de corridas** — listado con filtros, detalle por corrida, exportación.

**Inteligencia**
8. **Analytics operativos** — tendencias, volúmenes, errores, performance por carrier, filtros por fecha.
9. **Score de cliente** — tasa de entregas exitosas, ranking, clasificación visual.
10. **Motor de reglas** — CRUD, prioridades, historial, vista previa contra guías reales.

**Plataforma**
11. **Autenticación** — login, sesión, logout.
12. **Gestión de usuarios** — ABM básico de usuarios.
13. **Salud del sistema** — estado de integraciones, última corrida, errores recientes.

---

## 7. Requerimientos funcionales

### RF-01 Ingesta de guías vía Excel

- Upload de archivo `.xlsx` o `.csv` con las guías generadas ese día.
- El operario exporta desde el ERP a Excel y sube el archivo en la plataforma.
- El parser valida formato, detecta duplicados e informa errores específicos.
- Se muestra un preview de las guías a importar antes de confirmar.
- Al confirmar, las guías nuevas entran como activas en la DB.
- Las guías ya existentes no se sobreescriben (se ignoran).
- Se registra: quién importó, cuándo, cuántas guías nuevas, cuántas ignoradas.
- Formato mínimo requerido: número de guía, nombre del cliente, transportadora. El resto se define en la spec técnica de la fase.

### RF-02 Autenticación

- Login con email y contraseña.
- Sesión persistente segura (cookie httponly).
- Logout explícito.
- Cambio de contraseña propio.
- Sin recuperación automática por email en fase inicial — el admin resetea manualmente.
- Todas las rutas de la plataforma requieren sesión activa.

### RF-03 Gestión de usuarios

- Admin puede crear, activar y desactivar usuarios.
- Fase inicial: un nivel de acceso para todos (sin roles).
- Arquitectura preparada para agregar roles (operador / supervisor / admin) en fase futura.

### RF-04 Corridas operativas

- Ejecutar corrida contra todas las guías activas o una lista manual de guías.
- Modos: dry-run (sin cambios) y apply (escribe en DB y en Notion durante la transición).
- Progreso en tiempo real con auto-refresh.
- Persistencia completa: resultados, estados Effi y propuestos, motivos, regla aplicada, carrier.
- Registro de quién disparó la corrida y desde qué interfaz.

### RF-05 Vista "Requiere atención"

- Todas las guías con resultado distinto a `unchanged` en la última corrida.
- Agrupadas por tipo: `changed`, `manual_review`, `parse_error`, `error`.
- Acción requerida visible por cada guía.
- Filtros por carrier, tipo de resultado y cliente.

### RF-06 Trazabilidad por guía

- Timeline cronológico de todos los estados registrados en DB.
- Resultado por corrida: estado Effi, estado propuesto, motivo, regla aplicada.
- Notas del operario editables por resultado.
- Indicador de estado actual en Notion vs propuesto durante la fase de transición.

### RF-07 Trazabilidad por cliente

- Todos los pedidos (guías) del cliente en una sola vista.
- KPIs: total pedidos, entregados, devueltos, en proceso, con novedad.
- Score del cliente visible con clasificación.
- Historial cronológico de comportamiento.

### RF-08 Score de cliente

- Cálculo: `entregas exitosas / (entregas exitosas + devoluciones)`.
- Solo cuentan estados terminales: `ENTREGADA` (éxito) y `En Devolución` (fracaso). Los estados intermedios no afectan el score.
- Se actualiza automáticamente después de cada corrida que registre un resultado terminal.
- Clasificación visual:
  - Verde (≥ 80%): cliente sin problemas recurrentes.
  - Amarillo (50%–79%): cliente con historial mixto, monitorear.
  - Rojo (< 50%): cliente problemático.
- Visible en el detalle de cliente y en la tabla de ranking de clientes.
- Un cliente con un pedido entregado y uno devuelto tiene score del 50%.

### RF-09 Analytics operativos

- Tendencias en el tiempo: corridas procesadas, cambiadas, atención requerida, errores.
- Top clientes con más excepciones o devoluciones.
- Distribución de resultados por carrier.
- Tiempo promedio por estado.
- Filtros por rango de fecha.

### RF-10 Motor de reglas

- CRUD de reglas desde web sin tocar código.
- Prioridad ascendente, primera coincidencia gana.
- Activar y desactivar reglas sin eliminarlas.
- Historial completo de cambios por regla.
- Vista previa del resultado contra guías almacenadas antes de guardar.

### RF-11 Migración de datos de Notion

- Importación one-time de guías históricas desde Notion a la tabla `guides` en DB interna.
- Se ejecuta como script (no como UI) al inicio de Fase 2.
- Notion queda como referencia temporal durante la fase de validación.
- Criterio de salida: equipo valida operación normal por 2 semanas sin depender de Notion.
- Después de esta migración, Notion ya no es necesario para ningún flujo operativo.

### RF-12 Salud del sistema

- Estado de la última corrida: cuándo fue, cuántas guías, resultados.
- Errores recientes de parsing o conexión.
- Estado de la base de datos.
- Indicadores básicos de disponibilidad.

---

## 8. Requerimientos no funcionales

### RNF-01 Disponibilidad
- Plataforma activa 24/7 en VPS Hostinger (ya disponible).
- Tolerancia básica a fallos de corrida individual sin detener el servidor.

### RNF-02 Seguridad
- Contraseñas con hash seguro (bcrypt).
- Sesiones con cookie httponly + secure en producción.
- HTTPS en producción (Caddy o nginx como proxy).
- Todas las rutas protegidas por sesión activa.

### RNF-03 Rendimiento
- Corridas paralelas configurable (ThreadPoolExecutor, existente).
- Vistas de tabla con paginación cuando superen 50 registros.
- Tiempo de carga de vistas operativas < 2 segundos en condiciones normales.

### RNF-04 Auditabilidad
- Registro de quién disparó cada corrida.
- Historial completo de cambios en reglas.
- Log de importaciones de Excel: quién importó, cuándo, cuántas guías.

### RNF-05 Escalabilidad
- SQLite en modo WAL para fase inicial (4 usuarios, baja concurrencia).
- Capa de datos suficientemente desacoplada para migrar a PostgreSQL si la carga crece.

### RNF-06 Calidad operativa
- Capacidad de reconstruir cualquier decisión: por corrida, por regla, por guía.
- Sin pérdida de datos históricos en ninguna migración o actualización.

---

## 9. Definición de score de cliente

El score mide la tasa de entregas exitosas históricas de un cliente.

```
score = entregadas / (entregadas + devueltas)
```

**Ejemplo**: 1 pedido entregado + 1 devuelto → score = 50%.

**Clasificación**:

| Rango | Color | Interpretación |
|-------|-------|---------------|
| ≥ 80% | Verde | Sin problemas recurrentes |
| 50%–79% | Amarillo | Historial mixto, monitorear |
| < 50% | Rojo | Cliente problemático |

**Reglas de cálculo**:
- Solo cuentan estados terminales: `ENTREGADA` y `En Devolución`.
- Estados intermedios (`En ruta`, `Sin movimiento`, etc.) no afectan el score.
- Pedidos sin resultado terminal aún no cuentan en el denominador.
- El score se recalcula automáticamente después de cada corrida con resultados terminales.
- Clientes con 0 pedidos terminales muestran "Sin datos" (no un score de 0%).

---

## 10. Flujo de datos — fuentes y carga

### Carga histórica inicial (one-time, Fase 2)
La DB se siembra con los datos existentes en Notion mediante un script de migración. Este es el punto de partida de la base de datos propia. No requiere UI.

### Ingesta diaria ongoing (Fase 1 en adelante)
El ERP no tiene API. El flujo operativo diario es:

1. Al final del día, el operario exporta las guías creadas ese día desde el ERP a Excel.
2. Sube el archivo en la plataforma (`/import`).
3. El sistema parsea, valida y muestra un preview.
4. El operario confirma.
5. Las guías nuevas entran como activas en la DB.
6. Las guías ya existentes se ignoran (con log de cuántas).
7. Queda registrado: quién importó, cuándo, resultado.

**Columnas mínimas del Excel del ERP** (definición final en spec técnica de Fase 1 — depende del formato de exportación del ERP):
- Número de guía
- Nombre del cliente
- Transportadora

---

## 11. Arquitectura objetivo

Ver `docs/ARCHITECTURE.md` para el detalle completo.

Resumen de la arquitectura objetivo:
1. **Web App** — Python + Flask, servidor siempre activo en VPS.
2. **Motor de tracking** — `v0.2` (Python), integrado como librería interna.
3. **DB** — SQLite en modo WAL (fase inicial), migrable a PostgreSQL.
4. **Auth** — Sesiones Flask + bcrypt.
5. **Carriers** — Effi implementado; Guatex como stub listo para activar.
6. **Ingesta** — endpoint de upload Excel + parser con `openpyxl`.
7. **Despliegue** — systemd en VPS Hostinger, HTTPS con Caddy.
8. **UI** — Jinja2 templates + sistema de diseño de `docs/design-system/` (Geist, tokens cálidos, 11 pantallas diseñadas). Ver `docs/DESIGN.md`.

---

## 12. Plan de migración Notion → DB interna

### M1 — Coexistencia controlada (durante Fase 1)
- Las guías nuevas entran por Excel a la DB interna.
- Notion sigue siendo consultado para las guías históricas activas.
- Las corridas siguen escribiendo a Notion (`--apply`) durante la transición.
- La DB interna es la fuente de las guías nuevas; Notion es la fuente de las históricas.

### M2 — Migración one-time (inicio Fase 2)
- Script que exporta todas las guías activas e históricas de Notion a la tabla `guides` en DB.
- Validación de consistencia por muestreo.
- La DB interna pasa a ser la fuente única de lectura para las corridas.

### M3 — Retiro de Notion (fin Fase 2)
- `run_tracking` lee de DB interna en lugar de `NotionProvider`.
- `--apply` pasa a escribir solo en DB (Notion queda opcional para exportes si se necesita).
- Criterio de salida: 2 semanas de operación normal sin consultar Notion.

---

## 13. Roadmap por fases

Ver `docs/ROADMAP.md` para el detalle completo con criterios de salida.

| Fase | Nombre | Objetivo principal |
|------|--------|-------------------|
| Fase 1 | VPS + Auth + Excel | Plataforma online, acceso multi-usuario, ingesta por Excel |
| Fase 2 | DB propia + Remover Notion | Fuente de verdad interna, migración histórica |
| Fase 3 | Score + Nuevo diseño + Analytics | Inteligencia operativa, UI profesional |
| Fase 4 | Scheduler + Notificaciones + Mobile | Automatización y acceso móvil |
| Fase 5 | Escala + Nuevos carriers | Crecimiento de usuarios, nuevas integraciones |

---

## 14. Métricas de éxito

| Dimensión | Métrica |
|-----------|---------|
| Adopción | Los 4 usuarios usan la plataforma diariamente desde el VPS |
| Operación | Corridas completadas sin error técnico > 95% |
| Trazabilidad | 100% de guías con historial completo en DB interna |
| Migración | 0 consultas críticas a Notion al finalizar Fase 2 |
| Analytics | Score calculado para > 90% de clientes con pedidos terminales |
| Ingesta | Tiempo de importación de Excel < 30 segundos para un lote diario normal |

---

## 15. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Formato Excel inconsistente del ERP | Parser con validación estricta + mensajes de error claros para el operario |
| Migración incompleta de Notion | Script incremental + validación por muestreo antes de activar |
| SQLite con escrituras concurrentes | WAL mode; writes serializados desde el motor de corridas |
| Cambios en el HTML de Effi | `--save-raw-html` para debug; parser desacoplado del motor de reglas |
| VPS caído | Runbook básico de reinicio; corridas on-demand (sin scheduler automático en Fase 1) |
| Regla mal configurada que afecte muchas guías | `/rules/preview` obligatorio antes de activar cualquier regla nueva |

---

## 16. Decisiones confirmadas

1. Plataforma operativa interna formal, con potencial SaaS futuro.
2. Notion será reemplazado completamente (migración en Fase 2).
3. Ingesta de guías por Excel — el ERP no tiene API.
4. Score de cliente = `entregadas / (entregadas + devueltas)`.
5. 4 usuarios iniciales con el mismo nivel de acceso, arquitectura preparada para roles.
6. VPS se contrata al final de Fase 1 (~$5 USD/mes Hostinger). No se despliega antes — desarrollar sobre VPS incompleto genera overhead sin valor. El VPS regalo actual expira y no se renueva.
7. Python + Flask para la capa web del VPS.
8. SQLite en modo WAL para Fase 1; migrable a PostgreSQL si la carga lo requiere. Para 4 usuarios y un negocio logístico de esta escala, SQLite WAL es suficiente.
9. Acceso desktop/laptop en Fase 1; mobile en Fase 4.
10. Sin scheduler automático en Fase 1 — corridas siempre on-demand.
11. Migración inicial de Notion → DB es un script one-time al inicio de Fase 2, no una feature de UI. No bloquea Fase 1.

---

## 17. Preguntas abiertas (v2.1)

1. Formato exacto del Excel de exportación del ERP: columnas, nombres de encabezado, encoding.
2. ¿Umbral definitivo del score para "regular" vs "problema"? (propuesto: 80% / 50%).
3. Canal de notificaciones cuando termina una corrida (email, webhook, ninguno en Fase 1).
4. ¿Se necesita exportación a Excel desde la plataforma, además del CSV actual?
5. Flujo formal de "cierre" de una guía: ¿cuándo sale del ciclo activo?
6. Roles específicos cuando se contraten operarios: ¿qué puede hacer cada rol?
7. ¿Hay datos adicionales en Notion (notas, fechas custom) que deben migrarse además del estado?
