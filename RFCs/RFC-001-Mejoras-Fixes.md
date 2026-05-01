# RFC-001: Mejoras y Fixes — Solicitudes Operadora v0.3.3

| Campo           | Valor                                      |
|-----------------|--------------------------------------------|
| **RFC**         | RFC-001                                    |
| **Estado**      | Borrador                                   |
| **Autor**       | Ruben Salas                                |
| **Fecha**       | 2026-05-01                                 |
| **Versión**     | v0.3.3 (versión del proyecto a liberar)    |

---

## Resumen

Incorporar seis mejoras reportadas por la operadora: corregir error en guías sin movimiento en Effi, sistema no reconoce que son guías que no se han movido y por ende no propone mantener estado "Sin movimiento" si no que propone cambiar al estado en el que se encuentre en EFFI, mostrar la fecha del último estado registrado, agregar métricas de "recoger en oficina" en Analytics, habilitar observaciones manuales por guía por corrida, exportar a Excel las guías que requieren gestión con Effi, y hacer el menú de la interfaz web plegable.

---

## Motivación

La operadora usa el sistema diariamente para gestionar guías de envío. Durante el uso real detectó fricciones concretas que reducen la utilidad del sistema:

- Guías mal clasificadas porque sistema no prioriza regla de antiguedad del estado en Effi.
- No saber cuándo fue el último movimiento en Effi impide priorizar cuáles guías urgir.
- No hay visibilidad de cuántos paquetes "para recoger en oficina" se entregan vs. se devuelven.
- No existe forma de registrar lo que se hizo con cada guía un día específico; la memoria queda solo en notas externas.
- Para pasar guías al encargado de Effi se construye la lista a mano, lo que toma tiempo y tiene errores.
- El menú lateral ocupa espacio visible innecesario en pantallas pequeñas.

---

## Estado actual

### M1 — Guías sin movimiento
El motor de reglas evalúa días transcurridos desde el último estado (`_days_since()` en `v0.2/vaecos_v02/core/rules.py:567`). Al parecer no se esta escaneando la antiguedad del tiempo, y las reglas por días no se activan o reglas no tienen prioridad suficiente y el sistema no las toma. por lo que se propone cambiar el estado al que se encuentre en Effi a pesar de no haberse movido en días.

**Archivos relevantes:**
- `v0.2/vaecos_v02/core/rules.py`
- `v0.2/vaecos_v02/providers/carriers/effi.py` — scraper HTML

### M2 — Fecha del último estado en Effi
La fecha sí se extrae y almacena. La tabla `tracking_status_events` guarda `event_at TEXT` por cada evento. El motor de reglas la usa internamente (`latest_status_date` en `rules.py:428`). Sin embargo, la interfaz web nunca la muestra: no aparece en la tabla de resultados de corrida ni en la vista de guía individual.

**Archivos relevantes:**
- `v0.2/vaecos_v02/storage/db.py` — tabla `tracking_status_events` (línea ~38)
- `v0.3/vaecos_v03/storage.py` — consultas de analytics (sin campo de fecha)
- `v0.3/vaecos_v03/app.py` — ruta `/runs/<id>` (línea ~463)

### M3 — Analytics: guías para recoger en oficina
La regla "Paquete en agencia (novedad)" ya asigna `estado_propuesto = "Por recoger (INFORMADO)"`. La función `proposed_status_counts()` en `v0.3/vaecos_v03/storage.py` ya agrupa por `estado_propuesto`, pero no se usa en la ruta `/analytics`. No existe métrica que muestre cuántas terminaron entregadas vs. devueltas.

**Archivos relevantes:**
- `v0.3/vaecos_v03/storage.py` — `proposed_status_counts()` (línea ~62)
- `v0.3/vaecos_v03/app.py` — sección de cards en `/analytics` (línea ~611)

### M4 — Observación manual por guía por corrida
La tabla `run_results` tiene `motivo` y `requiere_accion`, ambos generados automáticamente por el motor de reglas. No existe campo editable por la operadora. No hay endpoint POST para actualizar resultados individuales, y la UI no tiene ningún control de edición en la vista de corrida.

**Archivos relevantes:**
- `v0.2/vaecos_v02/storage/db.py` — schema de `run_results` (línea ~21)
- `v0.2/vaecos_v02/core/models.py` — `ProcessingResult` (línea ~85)
- `v0.2/vaecos_v02/storage/repositories.py` — `save_result()` (línea ~47)
- `v0.3/vaecos_v03/app.py` — vista de corrida (línea ~463)

### M5 — Export Excel / guías para encargado Effi
El módulo de reportes genera Markdown, CSV y PDF (`v0.2/vaecos_v02/reporting/report_builder.py`). No existe ningún export específico de "guías que requieren gestión con Effi" ni descarga desde la interfaz web. Cambiar el CSV por un Excel donde esten las guías que como acción requieren gestionarse con Effi, el excel debe mostrar: guía, ultimo estado, problema presentado.

**Archivos relevantes:**
- `v0.2/vaecos_v02/reporting/report_builder.py`
- `v0.3/vaecos_v03/app.py` — rutas de descarga existentes

### M6 — Menú plegable
El menú lateral (`v0.3/vaecos_v03/render.py`) es HTML estático con 4 grupos siempre visibles. No tiene lógica de colapso. El JS actual solo detecta el ítem activo.

**Archivos relevantes:**
- `v0.3/vaecos_v03/render.py` — función `layout()` (línea ~238)

---

## Propuesta

| # | Mejora | Tipo |
|---|--------|------|
| M1 | Mejora o fix en regla de guías sin movimiento | Fix + Regla |
| M2 | Mostrar fecha del último estado Effi en tabla de resultados y en detalle de guía | UI |
| M3 | Nueva tarjeta en Analytics con desglose de "Por recoger en oficina" | Feature |
| M4 | Campo `notas_operador` editable por guía en cada corrida | Feature |
| M5 | Endpoint de descarga CSV/Excel de guías para gestión Effi | Feature |
| M6 | Grupos del menú lateral colapsables con estado persistido | UI |

---

## Diseño técnico

### M1 — Guías sin movimiento

**Problema raíz:** cuando la guía esta en sin movimiento en Notion pero en Effi aparece otro estado como por ejemplo el de novedad entonces el sistema no toma la antiguedad del estado para conservar el estado de sin movimiento si no que propone realizar el cambio sin revisar antiguedad del estado. Por lo tanto la regla debe ser: si la guía no tiene movimientos recientes (3 días o menos) en Effi entonces se mantiene en sin movimiento en Notion.

**Archivos a tener en cuenta:**

- `v0.2/vaecos_v02/core/rules.py`
- `v0.2/vaecos_v02/storage/db.py`

---

### M2 — Fecha del último estado en Effi

La fecha ya está en `tracking_status_events.event_at`. Se necesita:

1. Una consulta en `storage.py` que para cada `(run_id, guia)` retorne el `MAX(event_at)` de los eventos de estado.
2. Incluir esa fecha en la respuesta de la ruta `/runs/<id>` y en `/guides/<guia>`.
3. Agregar la columna "Último estado Effi" en la tabla de resultados de corrida.

**Archivos a tener en cuenta:**

| Archivo | Cambio |
|---------|--------|
| `v0.3/vaecos_v03/storage.py` | Nueva función `last_status_date_per_guide(run_id)` → dict[guia, date] |
| `v0.3/vaecos_v03/app.py` | Pasar el dict a la vista de corrida y de guía |
| `v0.3/vaecos_v03/render.py` | Agregar columna en la tabla de resultados |

**Consulta SQL propuesta:**
```sql
SELECT guia, MAX(event_at) as last_status_date
FROM tracking_status_events
WHERE run_id = ?
GROUP BY guia
```

---

### M3 — Analytics: recoger en oficina

Agregar una nueva sección en la página `/analytics` con tres métricas:

- **Total "Por recoger (INFORMADO)":** guías actualmente en ese estado propuesto.
- **Entregadas:** de esas, cuántas terminaron con `estado_propuesto` del grupo "Entregado" en corridas posteriores.
- **Devueltas:** cuántas terminaron con estado de devolución.

Para la fase inicial (borrador), alcanza con mostrar el total actual de guías "Por recoger" y su evolución en el tiempo (por corrida). La desagregación entregadas/devueltas requiere cruzar corridas, lo que se puede hacer en v2 de esta mejora.

**Archivos a tener en cuenta:**

| Archivo | Cambio |
|---------|--------|
| `v0.3/vaecos_v03/storage.py` | `office_pickup_stats()` → total "Por recoger", trend por corrida |
| `v0.3/vaecos_v03/app.py` | Agregar tarjeta en sección de analytics (línea ~611) |
| `v0.3/vaecos_v03/render.py` | Reutilizar componente `card()` existente |

---

### M4 — Observación manual por guía por corrida

**Migración de BD:** agregar columna nullable a `run_results`.

```sql
ALTER TABLE run_results ADD COLUMN notas_operador TEXT;
```

La migración debe ser idempotente (checar si la columna existe antes de agregar, patrón ya usado en `db.py`).

**Modelo:** agregar campo opcional a `ProcessingResult` en `models.py`:
```python
notas_operador: str = ""
```

**Endpoint nuevo en v0.3:**
```
POST /runs/<run_id>/results/<guia>/notas
Body: { "notas": "texto libre" }
Response: 200 OK
```

**UI:** En la tabla de resultados de corrida, agregar un ícono de lápiz por fila. Al hacer clic, se muestra un `<textarea>` inline que hace POST al endpoint. Sin dependencias externas (JavaScript vanilla).

**Archivos a modificar:**

| Archivo | Cambio |
|---------|--------|
| `v0.2/vaecos_v02/storage/db.py` | Migración `ADD COLUMN notas_operador TEXT` |
| `v0.2/vaecos_v02/core/models.py` | Campo `notas_operador: str = ""` en `ProcessingResult` |
| `v0.2/vaecos_v02/storage/repositories.py` | `update_notas(run_id, guia, notas)` |
| `v0.3/vaecos_v03/app.py` | Ruta POST `/runs/<run_id>/results/<guia>/notas` |
| `v0.3/vaecos_v03/render.py` | Columna "Notas" con textarea inline en tabla de corrida |

---

### M5 — Export CSV/Excel para encargado Effi

Agregar un endpoint de descarga que genere un CSV con las guías que `requieren_accion IS NOT NULL AND requiere_accion != ''` de una corrida específica.

**Columnas del archivo:**

| Columna | Fuente |
|---------|--------|
| No. Guía | `run_results.guia` |
| Estado actual (Effi) | `run_results.estado_effi_actual` |
| Problema | `run_results.motivo` |
| Notas operadora | `run_results.notas_operador` |

**Formato:** CSV con encoding UTF-8-BOM (para que Excel en Windows lo abra correctamente sin configuración adicional). Sin dependencias externas — usar `csv` de stdlib.

**Endpoint:**
```
GET /runs/<run_id>/export/effi
Response: Content-Disposition: attachment; filename="effi-gestion-<fecha>.csv"
```

**Botón en UI:** Agregar en la vista `/runs/<id>` un botón "Descargar para Effi" junto a los botones existentes.

**Archivos a modificar:**

| Archivo | Cambio |
|---------|--------|
| `v0.3/vaecos_v03/app.py` | Ruta GET `/runs/<run_id>/export/effi` |
| `v0.3/vaecos_v03/storage.py` | `guides_for_effi_review(run_id)` → lista de dicts |
| `v0.3/vaecos_v03/render.py` | Botón "Descargar para Effi" en header de corrida |

---

### M6 — Menú plegable

Convertir cada `<div class="nav-group">` en un bloque colapsable con clic en el `<div class="nav-label">`. Estado (abierto/cerrado) persistido en `localStorage` por clave `nav-<nombre-grupo>`.

Por defecto, todos los grupos están abiertos. Al colapsar, el `<nav>` interno se oculta con CSS (`max-height` + `overflow: hidden` para animación suave).

**Solo se modifica `render.py`:** sin cambios en rutas ni backend.

**Archivos a modificar:**

| Archivo | Cambio |
|---------|--------|
| `v0.3/vaecos_v03/render.py` | Agregar atributo `data-group` a cada `nav-label`, JS vanilla para toggle + localStorage |

---

## Alternativas consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| M5: usar `openpyxl` para generar .xlsx real | Agrega dependencia externa; el proyecto evita esto por diseño. CSV con UTF-8-BOM abre directamente en Excel sin configuración. |
| M4: campo de notas a nivel de guía global (no por corrida) | Pierde el contexto temporal; la operadora necesita saber qué se hizo cada día. |
| M3: mostrar entregadas/devueltas desde el primer momento | Requiere cruzar múltiples corridas con lógica de "estado final"; se deja para iteración posterior. |
| M6: menú en modal o drawer lateral en mobile | Fuera de alcance; el sistema se usa en escritorio. Colapso de grupos es suficiente. |

---

## Plan de implementación

Los ítems son independientes entre sí (salvo M4 que requiere migración de BD antes de la UI). Orden sugerido:

- [ ] **M1:** Arreglar regla de "Sin movimiento en Effi" + tests en `test_rules.py`
- [ ] **M2:** Consulta `last_status_date_per_guide()` + columna en tabla de corrida
- [ ] **M4-DB:** Migración `notas_operador` en `db.py` (idempotente)
- [ ] **M4-API:** Endpoint POST en app.py + `update_notas()` en repositories.py
- [ ] **M4-UI:** Columna con edición inline en tabla de corrida
- [ ] **M5:** Consulta `guides_for_effi_review()` + endpoint CSV + botón en UI
- [ ] **M3:** Consulta `office_pickup_stats()` + tarjeta en analytics
- [ ] **M6:** Toggle JS + localStorage en `render.py`
- [ ] Pruebas manuales end-to-end con corrida real
- [ ] Bump de versión a v0.3.3 en config y release notes

---

## Criterios de aceptación

- [ ] **M1:** La regla "Sin movimiento en Effi" se ejecuta correctamente y propone el cambio de estado con el motivo correcto, conservando la antiguedad del estado.
- [ ] **M2:** La columna "Último mvto. Effi" aparece en la tabla de resultados de corrida con la fecha formateada (DD/MM/YYYY). Guías sin eventos muestran "—".
- [ ] **M3:** La página `/analytics` muestra una tarjeta "Por recoger en oficina" con el total de guías en ese estado en la corrida más reciente.
- [ ] **M4:** Al hacer clic en el ícono de edición de una guía, aparece un textarea. Al guardar, el texto queda persistido y se muestra en la tabla al recargar.
- [ ] **M5:** El botón "Descargar para Effi" en una corrida descarga un `.csv` que Excel abre correctamente, con las columnas definidas y solo las guías con acción requerida.
- [ ] **M6:** Cada grupo del menú lateral se colapsa/expande al hacer clic en su título. El estado se mantiene al navegar entre páginas.
- [ ] Los tests existentes siguen pasando: `python -m unittest discover -s "v0.2/tests" -v`
- [ ] No hay regresiones en el dashboard: `python v0.3/server.py --check`

---

## Impacto y riesgos

**Migraciones necesarias:**
- `ALTER TABLE run_results ADD COLUMN notas_operador TEXT` — migración no destructiva, columna nullable. Las corridas anteriores quedan con `NULL`.

**Riesgos:**

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| La migración de BD falla en instalaciones con BD ya existente | Baja | Patrón idempotente ya implementado en `db.py`: checar columna con `PRAGMA table_info` antes de agregar |
| La regla M1 clasifica incorrectamente guías con error de red | Media | Añadir campo en el resultado del carrier que distinga "sin datos" vs "error de conexión"; la regla solo activa en el primer caso |
| El CSV con caracteres especiales (ñ, tildes) se corrompe en Excel | Baja | Usar UTF-8-BOM (`﻿`) al inicio del archivo |

**Compatibilidad:** Todos los cambios son retrocompatibles. La nueva columna en BD es nullable; los endpoints nuevos no modifican los existentes; los cambios de UI son aditivos.

---

## Referencias

- `AGENTS.md` — Restricciones operativas del sistema
- `checklist.md` — Estado actual de componentes
- Commit: `c527310` — "fix tracking rule handling and pause web rules editor" (contexto de M1)
