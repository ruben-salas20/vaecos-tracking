# Proceso de seguimiento automático de guías — VAECOS
*Última ejecución: 16 de abril de 2026*

---

## Contexto del negocio

VAECOS es un emprendimiento de dropshipping que vende productos en Guatemala a través de la plataforma **effi** (efficommerce). La transportadora utilizada es **Cargo Expreso Guatemala**. Cuando un pedido presenta dificultades de entrega, se registra y hace seguimiento en una base de datos de **Notion**.

El proceso que se automatiza aquí es el seguimiento diario de guías: consultar el estado de cada guía en effi, aplicar reglas de negocio y actualizar Notion con el nuevo estado y una entrada en el historial de cada ficha.

---

## Herramientas conectadas

- **Notion MCP** — para leer y escribir en la base de datos de clientes
- **web_fetch** — para consultar el estado de cada guía en la página pública de effi
- La URL de tracking de effi sigue el patrón: `https://effi.com.co/tracking/index/{número_guía}`

---

## Estructura de la base de datos en Notion

**Página principal:** `https://www.notion.so/rubensalas/Seguimiento-a-clientes-21c73515766b8013abd3ef99857ba192`

**Base de datos (data source):** `collection://e7da64fa-d6c7-47ab-bc12-d7af207f871b`

### Propiedades de la tabla "Clientes"

| Propiedad | Tipo | Notas |
|-----------|------|-------|
| Nombre | title | Nombre del cliente |
| No. Guía | text | Número de guía de Cargo Expreso |
| Producto | select | DERMAN, ESTRECHANTE, VIRILE, FEMPRO, etc. |
| Cant. | number | Cantidad de unidades |
| Teléfono | number | Teléfono del cliente |
| Estado novedad | select | Ver valores permitidos abajo |
| Fecha último seguimiento | date | Fecha de la última actualización |
| Valor | formula | Calculado automáticamente |
| Pago indemnización? | select | SI / PENDIENTE |

### Valores del campo "Estado novedad"

`En novedad` · `Por recoger (INFORMADO)` · `Indemnización` · `Sin movimiento` · `Solicitud devolución` · `Solicitud info Effi` · `PENDIENTE EFFI` · `PENDIENTE EFFI` · `En Devolución` · `En ruta de entrega` · `Gestión novedad` · `ENTREGADA` · `PENDIENTE CLIENTE`

### Estructura interna de cada ficha (contenido de la página)

Cada cliente tiene una tabla con el historial de seguimiento:

```
| Fecha seguimiento | Acción realizada | Observación |
```

Cada vez que se hace un seguimiento se agrega una nueva fila a esta tabla con la fecha en formato `DD-MM-YYYY`, la acción realizada y la observación.

---

## Reglas de negocio para clasificar estados

### Estados que se EXCLUYEN del procesamiento (ya cerrados)
- `ENTREGADA`
- `Indemnización`
- `Solicitud devolución`
- `En Devolución`

### Reglas de clasificación según estado en effi

| Condición en effi | Nuevo estado Notion | Acción |
|-------------------|--------------------|----|
| Estado = `ANOMALIA` + novedad "cliente no quiso recibir" | `En novedad` | Hablar con cliente |
| Estado = `ANOMALIA` + novedad "nadie en casa" | `En novedad` | Hablar con cliente |
| Estado = `ANOMALIA` + novedad "dirección no corresponde" | `En novedad` | Hablar con cliente |
| Estado = `ANOMALIA` + novedad "cliente no llegó al punto de encuentro" | `En novedad` | Hablar con cliente |
| Novedad = `Paquete en agencia` (en cualquier estado) | `Por recoger (INFORMADO)` | Avisar al cliente que vaya a recoger |
| Estado = `ALMACENADO EN BODEGA` con **más de 1 día** en ese estado | `Sin movimiento` | Gestionar con encargado |
| Estado = `EN RUTA DE ENTREGA` / `RUTA ENTREGA FINAL` con **más de 1 día** sin cambio | `Sin movimiento` | Gestionar con encargado |
| Estado = `Sin Recolectar` con **más de 1 día** | `Sin movimiento` | Gestionar con encargado |
| Estado = `Devolución` | `En Devolución` | Sin acción (pasa a excluidos) |
| Estado = `ENTREGADO` | `ENTREGADA` | Sin acción (pasa a excluidos) |
| Estado = `RUTA ENTREGA FINAL` con menos de 1 día | `En ruta de entrega` | Monitorear |

---

## Flujo de ejecución paso a paso

### Paso 1 — Leer guías activas de Notion

Buscar en la base de datos `collection://e7da64fa-d6c7-47ab-bc12-d7af207f871b` todos los registros cuyo campo `Estado novedad` NO sea ninguno de los estados excluidos.

Usar `Notion:notion-search` con `page_size: 25` (máximo permitido). Si hay más de 25 registros activos, paginar con múltiples llamadas.

De cada resultado obtener:
- `page_id` — ID de la página Notion
- `Nombre` — nombre del cliente
- `No. Guía` — número de guía para consultar en effi
- `Estado novedad` — estado actual para verificar exclusiones

**Nota importante:** El CSV exportado desde Notion también sirve como fuente alternativa para obtener la lista de guías cuando el número de registros supera el límite de búsqueda.

---

### Paso 2 — Consultar estado en effi

Para cada guía, hacer `web_fetch` a:
```
https://effi.com.co/tracking/index/{No_Guía}
```

Extraer del HTML:
- **Estado actual** (campo `Estado actual`)
- **Histórico de estados** (sección `HISTÓRICO DE ESTADOS`) — incluye fecha y estado de cada movimiento
- **Histórico de novedades** (sección `HISTÓRICO DE NOVEDADES`) — incluye fecha, tipo de novedad y aclaración

**Importante:** Las URLs de effi deben ser provistas por el usuario en el chat para que `web_fetch` pueda acceder a ellas. El formato para pedírselas es:

```
https://effi.com.co/tracking/index/B26XXXXXXX-1
https://effi.com.co/tracking/index/B26XXXXXXX-1
...
```

---

### Paso 3 — Aplicar reglas y determinar nuevo estado

Con el estado actual y el historial de effi, aplicar las reglas de negocio descritas arriba para determinar:
1. El nuevo valor del campo `Estado novedad` en Notion
2. La observación que se agregará al historial de la ficha
3. Si requiere acción (hablar con cliente, gestionar con encargado, etc.)

Para calcular días sin movimiento: comparar la fecha del último estado en effi con la fecha actual.

---

### Paso 4 — Actualizar Notion

Para cada ficha, hacer **dos operaciones**:

#### 4a. Actualizar propiedades
```
Notion:notion-update-page
  command: update_properties
  page_id: {id de la página}
  properties:
    Estado novedad: {nuevo estado}
    date:Fecha último seguimiento:start: {fecha actual en formato YYYY-MM-DD}
    date:Fecha último seguimiento:is_datetime: 0
```

#### 4b. Agregar fila al historial

Primero hacer `Notion:notion-fetch` sobre la página para obtener el contenido exacto de la tabla (el formato HTML interno).

Luego usar `Notion:notion-update-page` con `command: update_content` para hacer un `old_str` / `new_str` que reemplace la última fila vacía de la tabla (o la última fila con contenido) por la nueva fila más la nueva entrada:

```html
<!-- Fila existente (última con contenido) -->
<tr>
<td>DD-MM-YYYY</td>
<td>Acción anterior</td>
<td>Observación anterior</td>
</tr>
<!-- Nueva fila agregada -->
<tr>
<td>16-04-2026</td>
<td>Revisión estado de la guía</td>
<td>Estado en effi: {ESTADO}. {Observación relevante}.</td>
</tr>
```

**Nota crítica sobre el formato:** Las tablas en Notion usan etiquetas HTML `<tr><td>` en el contenido de la página, NO markdown estándar. El `old_str` debe coincidir exactamente con el contenido de la tabla tal como lo devuelve `notion-fetch`. Si hay comillas tipográficas (`"` `"`), caracteres especiales o saltos de línea `<br>`, deben preservarse exactamente.

**Estrategia cuando hay filas vacías al final:** Reemplazar la primera fila vacía junto con la última fila con contenido para insertar la nueva entrada. Si no hay filas vacías, reemplazar el cierre `</table>` incluyendo la última fila.

---

## Consideraciones técnicas importantes

### Paginación en Notion
El límite actual de `notion-search` es 25 resultados por llamada. Si la base de datos crece más de 25 registros activos, se deben hacer múltiples llamadas usando el cursor de paginación.

### Permisos de web_fetch
`web_fetch` solo puede acceder a URLs que hayan sido proporcionadas directamente por el usuario en el chat. Por esto, las URLs de effi deben ser pegadas manualmente por el usuario antes de ejecutar el seguimiento.

### Formato de fechas
- En las **propiedades de Notion**: formato ISO `YYYY-MM-DD` (ej: `2026-04-16`)
- En las **filas del historial**: formato `DD-MM-YYYY` (ej: `16-04-2026`)

### Manejo de errores en update_content
Si `old_str` no encuentra coincidencia exacta, el update falla con error `validation_error: No matches found`. Solución: hacer `notion-fetch` de la página justo antes del update para obtener el contenido actual y construir el `old_str` correcto.

---

## Comandos de referencia

### Buscar guías activas
```
Notion:notion-search
  data_source_url: collection://e7da64fa-d6c7-47ab-bc12-d7af207f871b
  query: seguimiento clientes guías
  page_size: 25
  max_highlight_length: 0
  filters: {}
```

### Leer ficha de un cliente
```
Notion:notion-fetch
  id: {page_id}
```

### Actualizar propiedades
```
Notion:notion-update-page
  command: update_properties
  page_id: {page_id}
  properties:
    Estado novedad: "En novedad"
    date:Fecha último seguimiento:start: "2026-04-16"
    date:Fecha último seguimiento:is_datetime: 0
```

### Agregar fila al historial
```
Notion:notion-update-page
  command: update_content
  page_id: {page_id}
  content_updates:
    - old_str: "<tr>\n<td>última fila existente...</td>\n</tr>\n<tr>\n<td></td>..."
      new_str: "<tr>\n<td>última fila existente...</td>\n</tr>\n<tr>\n<td>16-04-2026</td>\n<td>Revisión estado de la guía</td>\n<td>Observación aquí</td>\n</tr>"
```

---

## Observaciones del historial de ejecución (16 abril 2026)

- Se procesaron **40 guías** en total (dos tandas por límite de paginación)
- La primera tanda de 14 guías se obtuvo directamente con `notion-search`
- La segunda tanda de 26 guías se obtuvo desde un CSV exportado por el usuario desde Notion
- Las URLs de effi fueron pegadas por el usuario en dos bloques de 14 y 26 URLs respectivamente
- El proceso de actualización tomó múltiples iteraciones por la necesidad de hacer `fetch` previo a cada `update_content`
- Algunos registros con `En Devolución` que aparecían en el CSV no fueron procesados (correctamente excluidos)

---

## Checklist de ejecución

- [ ] Exportar CSV de Notion o usar `notion-search` para obtener guías activas
- [ ] Filtrar excluyendo: ENTREGADA, Indemnización, Solicitud devolución, En Devolución
- [ ] Pedir al usuario que pegue las URLs de effi en el chat
- [ ] Hacer `web_fetch` a cada URL y extraer estado, historial y novedades
- [ ] Aplicar reglas de negocio y determinar nuevo estado + observación
- [ ] Para cada ficha: `notion-fetch` → `update_properties` → `update_content`
- [ ] Generar resumen final con estados por categoría y casos urgentes

---

*Documento generado el 16 de abril de 2026 · Proyecto: Seguimiento VAECOS*
