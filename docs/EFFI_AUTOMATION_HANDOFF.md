# Handoff: Automatización Effi ERP — Conversión Órdenes → Remisiones → Guías de Transporte

> **Propósito de este documento**: capturar al 100% el contexto operativo, técnico y de reglas de negocio para que un nuevo chat de Claude pueda implementar la automatización en la plataforma logística sin tener que redescubrir nada. Este flujo fue ejecutado manualmente vía Playwright para entender cada paso.

---

## 1. Resumen ejecutivo

**Empresa**: VAECOS (ID EFFI: 34372) — ecommerce **Vaecos Guatemala**.
**Sucursal/Bodega/Centro de costos**: `1 - Principal` (único hoy).
**ERP**: Effi ERP (https://effi.com.co) — **NO tiene API pública**. Toda automatización debe ser **browser automation** (Playwright recomendado).
**Transportadora**: CARGO EXPRESO Guatemala 14%, modalidad **CON RECAUDO** (contra entrega).
**Volumen referencia**: ~220 órdenes/mes (mayo 2026, filtro default desde día 1 del mes).

**Flujo end-to-end por orden**:
```
Orden de Venta (estado "PEDIDO CONFIRMADO") 
  → Convertir en Remisión 
  → Convertir Remisión en Guía de Transporte (CARGO EXPRESO CON RECAUDO)
```

**Cuello de botella**: hoy el equipo lo hace manualmente, click por click, para cada orden. Es repetitivo, sin juicio humano real, y es candidato perfecto a automatización determinista.

---

## 2. Credenciales y acceso

| Campo | Valor |
|---|---|
| URL login | `https://effi.com.co/ingreso` |
| Usuario | `nutrinat.salas@gmail.com` |
| Password | `lunacris040524` |
| Usuario en UI | Natalia Stefania |
| reCAPTCHA | **Sí, en el login.** Bloquea automatización pura — ver estrategia abajo. |

### Estrategia de sesión

El reCAPTCHA hace que NO se pueda automatizar el login limpiamente. Solución:

1. **Login manual una vez** con navegador Playwright en modo headed.
2. Guardar `storageState.json` (cookies + localStorage) tras el login.
3. Reusar ese state en todas las corridas siguientes (sesión típica del ERP dura días/semanas).
4. Monitor de health-check: si una corrida detecta la página `/ingreso`, mandar alerta a humano para re-login.

```js
// Login inicial (headed, una vez por mes aprox.)
const context = await browser.newContext();
const page = await context.newPage();
await page.goto('https://effi.com.co/ingreso');
// Humano resuelve reCAPTCHA y hace login
await page.waitForURL(/\/app\//);
await context.storageState({ path: 'effi-session.json' });

// Corridas automáticas:
const context = await browser.newContext({ storageState: 'effi-session.json' });
```

---

## 3. URLs y navegación

| Pantalla | URL |
|---|---|
| Login | `https://effi.com.co/ingreso` |
| App home / Calendario | `https://effi.com.co/app/calendario` |
| **Órdenes de venta** | `https://effi.com.co/app/orden_v` |
| **Remisiones de venta** | `https://effi.com.co/app/remision_v` |
| **Guías de transporte** | `https://effi.com.co/app/guia_transporte` |
| Devoluciones | `https://effi.com.co/app/devolucion_v` |
| Recuperar password | `https://effi.com.co/recuperar_password` |

**Menú lateral**: `Ventas` → submenú con `Órdenes de venta`, `Remisiones de venta`, `Devoluciones de venta`, `Anticipos de clientes`.

Para automatización, **no navegues por el menú** — ir directo a las URLs es más estable.

---

## 4. Filtros y descubrimiento de órdenes

### Filtro default del ERP

> "Solo se visualizan los registros desde el 01-MM-AAAA"

El ERP filtra automáticamente al **día 1 del mes en curso**. Suficiente para corridas diarias/semanales. Si se necesita histórico, ampliar mediante "Filtros de búsqueda".

### Criterio para procesar

**Órdenes a convertir**: estado **`PEDIDO CONFIRMADO`** SIN `Remisión #NNNN` en el texto del estado.

Estados observados:
- `Generada` — no se procesan (aún no confirmadas por el cliente / equipo).
- `Generada. Remisión #NNNN ($XXX)` — ya tienen remisión, no procesar.
- `PEDIDO CONFIRMADO` — **PROCESAR**.
- `PEDIDO CONFIRMADO. Remisión #NNNN ($XXX)` — ya remisionada, no procesar.

**Regex de filtro**:
```js
const procesar = estado.includes('PEDIDO CONFIRMADO') 
              && !/Remisi[oó]n\s*#\d+/i.test(estado);
```

### Estructura de la tabla `/app/orden_v`

Columnas: `Fecha` · `Ubicación` · `ID orden` · `Cliente` · `Terceros` · `Totales` · `Estado`.

Por fila (selector `table tbody tr`):
- `td:nth-child(4)` — ID de orden (ej. `5343`).
- `td:nth-child(5)` — Cliente: nombre + DPI + teléfono + dirección completa concatenada.
- `td:last-child` — Estado.
- `button.dropdown-toggle` — abre menú de acciones.

**Importante**: la tabla NO está paginada — renderiza las 220 filas en el DOM directamente. Esto facilita el scraping (no hay que paginar).

---

## 5. El flujo paso a paso

### 5.1 Convertir Orden → Remisión

1. En `/app/orden_v`, encontrar fila con el ID de orden.
2. Click en `button.dropdown-toggle` de esa fila.
3. Click en link `Convertir en remisión`.
   - `href` tiene la forma `https://effi.com.co/app/remision_v?action=<encrypted-blob>`.
4. La URL cambia a `remision_v?action=...` y se abre el **modal `#modalCrear`** con datos prellenados:
   - Sucursal, Bodega, Centro de costos (1 - Principal)
   - Moneda (Quetzal GTQ)
   - Cliente, Dirección (heredados de la orden)
   - Convenio Dropshipping (preseleccionado)
   - **Conceptos** (productos) con: artículo (id), descripción, cantidad, descuento.
5. **No hay que modificar nada** — solo verificar productos y click en `Crear y cerrar`.
6. Tras el submit, se cierra el modal y la nueva remisión aparece como primera fila en `/app/remision_v` con un ID nuevo (en mayo 2026 iban en ~3889+).

### 5.2 Convertir Remisión → Guía de Transporte

1. En `/app/remision_v`, encontrar la remisión recién creada.
2. Click en `button.dropdown-toggle`.
3. Click en `Crear guía de transporte`.
   - `href`: `https://effi.com.co/app/guia_transporte?action=<encrypted-blob>`.
4. Se abre modal `#modalCrear` con datos prellenados (remitente, destinatario, dirección, etc.).
5. **Llenar manualmente**:
   - `Fecha de envío` → fecha de hoy (formato `YYYY-MM-DD`).
   - `Fecha de entrega esperada` → 3 días hábiles después. _(NOTA: el ERP tiene un bug — al cambiar transportadora pisa este valor con la fecha de envío. Es un error conocido del ERP, ignorar.)_
   - `Transportadora` → `1 - CARGO EXPRESO GT 14% | CON RECAUDO | FLETE CRÉDITO` (value=`1`). **Crítico que diga CON RECAUDO, no SIN RECAUDO** (value=`2`).
   - Al cambiar transportadora, **espera ~2-3 segundos** y el ERP llena automáticamente vía AJAX:
     - `Tipo de servicio` (value=`1`)
     - `Forma de pago flete` (value=`1`)
     - `Estado de guía` (value=`1`)
   - **Contenido** y **Valor declarado** → según reglas de negocio (sección 6).
6. Click en `Crear y cerrar`.
7. Aparece la nueva guía en `/app/guia_transporte` (IDs iban en ~4001+ en mayo 2026).

---

## 6. Reglas de negocio (CORE de la automatización)

### 6.1 Catálogo conocido y precios

| Producto (descripción exacta en ERP) | Precio unitario declarado | Tipo |
|---|---|---|
| `CREMA ESTRECHANTE` | $32 | femenino |
| `GEL ESTIMULANTE MULTI ORGÁSMICO` | inferido $34 (combo $66 − $32) | femenino |

> ⚠️ **A confirmar con el negocio**: si hay más productos en el catálogo y sus precios declarados individuales, antes de codificar.

### 6.2 Clasificación de la orden (en el modal de remisión)

Leer los productos del modal con:
```js
const descs = Array.from(modal.querySelectorAll('textarea[name="descripcion[]"], input[name="descripcion[]"]'))
                   .map(d => d.value).filter(Boolean);
const cants = Array.from(modal.querySelectorAll('input[name="cantidad[]"]'))
                   .map(c => parseInt(c.value, 10));
```

**Tipos de pedido identificados**:

| Tipo | Composición | Contenido en guía | Valor declarado |
|---|---|---|---|
| **Combo estándar** | `CREMA ESTRECHANTE` × N + `GEL ESTIMULANTE MULTI ORGÁSMICO` × N (mismo N) | ✅ Marcar checkbox **"Copiar del documento"** | `$66 × N` |
| **Crema-solo** | Solo `CREMA ESTRECHANTE` × N (sin gel) | ✏️ Escribir manualmente `N* PRODUCTO FEMENINOS VAECOS` (sin checkbox) | `$32 × N` |
| **Cualquier otra combinación** | — | ❓ **ESCALAR A HUMANO** | ❓ |

> 💡 **Por qué el texto genérico para cremas**: discreción/privacidad — no se quiere mostrar el nombre real del producto a la transportadora. Para el combo se permite porque el sistema lo copia internamente.

### 6.3 Validación de dirección (regla del negocio)

**Una dirección es VÁLIDA si tiene**:
- Una zona/colonia/aldea/barrio/cantón identificable, **O**
- Al menos un punto de referencia (negocio, iglesia, escuela, gimnasio, etc.).

**NO es requerido**: número de casa ni nombre exacto de calle.

> ⚠️ **Lección aprendida**: criterio urbano numérico NO aplica. Direcciones rurales tipo "Aldea El Florido, frente a la iglesia católica" SON válidas en el contexto guatemalteco. La transportadora opera con referencias, no con numeración cartesiana.

**Heurística para script**:
```js
function direccionValida(dir) {
  const tieneUbicacion = /zona\s*\d|aldea|colonia|barrio|cantón|caserío|kilómetro|km\s*\d/i.test(dir);
  const tieneReferencia = /frente|por\s+(el|la|los|las)?|enfrente|al lado|atrás|cerca|antes de|después de|costado/i.test(dir);
  return tieneUbicacion || tieneReferencia;
}
```

Lo que NO captura la heurística → cola humana.

---

## 7. Mapa de selectores y campos del modal

### 7.1 Modal de Remisión (`#modalCrear` en `/app/remision_v`)

| Campo | Selector | Notas |
|---|---|---|
| Sucursal | `select[name="sucursal"]` | Pre-llenado |
| Cliente | `select[name="cliente"]` | Pre-llenado |
| Dirección destinatario | `select[name="direccion_destinatario[]"]` | Pre-llenado |
| Artículo (id) | `input[name="articulo[]"]` (select2 oculto) | Pre-llenado |
| Cantidad | `input[name="cantidad[]"]` | Pre-llenado |
| Descripción | `textarea[name="descripcion[]"]` | Pre-llenado, usar para clasificar |
| Descuento | `input[name="descuento[]"]` | Pre-llenado |
| Botón submit | `button.submit` con texto `Crear y cerrar` | Hay varios botones de crear (PDF, POS, etc.); filtrar por texto exacto |

### 7.2 Modal de Guía (`#modalCrear` en `/app/guia_transporte`)

| Label | Selector ID | Tipo | Notas |
|---|---|---|---|
| Sucursal de la guía | `#sucursal_CR` | select | Pre=`1` |
| Fecha de envío | `#fecha_envio_CR` | input text | Formato `YYYY-MM-DD` |
| Fecha de entrega esperada | `#fecha_entrega_esperada_CR` | input text | Formato `YYYY-MM-DD` — pisada por bug del ERP |
| Transportadora | `#transportadora_CR` | select | **Setear `1`** (CARGO EXPRESO CON RECAUDO) |
| Tipo de servicio | `#t_servicio_CR` | select | Auto-fill tras transportadora |
| Forma de pago flete | `#t_forma_pago_flete_CR` | select | Auto-fill |
| Estado de guía | `#est_guia_CR` | select | Auto-fill |
| Guía de transportadora | `#guia_CR` | input text | Opcional, dejar vacío |
| ¿Recibe los sábados? | `#recibe_sabado_CR` | select | Default `1` (Sí) |
| Cant. paquetes | `#cant_paquetes_CR` | input | Default `1` |
| Peso (Kg) | `#peso_total_CR` | input | Default `1` |
| Volumen (Kg) | `#volumen_total_CR` | input | Default `1` |
| Alto/Ancho/Largo (cm) | `#alto_CR` `#ancho_CR` `#largo_CR` | input | Default `1` |
| Contenido | `#contenido_CR` | input text | Llenar según regla (sección 6.2) |
| Contenido — checkbox "Copiar del documento" | `#contenido_check_CR` | checkbox | Marcar SOLO si combo |
| Valor declarado | `#valor_declarado_CR` | input | Llenar según regla |
| Valor declarado — checkbox "Copiar del documento" | `#valor_declarado_check_CR` | checkbox | NO marcar (siempre custom) |
| Valor flete | `#valor_flete_CR` | input | Default `0` |
| Valor recaudo | `#valor_recaudo_CR` | input | Default `0` |
| Remitente | `#remitente_CR` | select | Pre=`3` (VAECOS San Miguel Petapa) |
| Nota en la guía | `#nota_guia_CR` | textarea | Opcional |
| Observación interna | `#observacion_CR` | textarea | Opcional |
| Botón submit | `button.submit` texto `Crear y cerrar` | — | — |

### 7.3 Botón dropdown en filas de tabla

Cada fila de tabla (`tr`) tiene `button.dropdown-toggle.btn-sm` que despliega menú con acciones. Las opciones interesantes:

| Origen | Acción a buscar (texto exacto) | Destino |
|---|---|---|
| Orden | `Convertir en remisión` | `/app/remision_v?action=...` con modal abierto |
| Remisión | `Crear guía de transporte` | `/app/guia_transporte?action=...` con modal abierto |

---

## 8. Detalles técnicos y "gotchas"

### 8.1 La forma se envía con jQuery — usar eventos correctos

El front-end es jQuery + Bootstrap modal. Selects con `select2`. **Importante**:

```js
// Cambiar fecha o valor de input
const el = document.getElementById('fecha_envio_CR');
el.value = '2026-05-13';
window.jQuery(el).trigger('change');  // ← necesario para que dispare AJAX cascading

// Submit
const btn = [...document.querySelectorAll('button')]
  .find(b => b.innerText.trim() === 'Crear y cerrar');
btn.click();  // funciona, dispara handler de submit + AJAX + cierra modal
```

### 8.2 NO usar `form.submit()`

**Bug que descubrí**: el formulario tiene un `<input name="action">` que **shadow-ea** la propiedad `form.action`. Llamar `form.submit()` redirige a la home (`/app/calendario`) en lugar de crear el registro. **Siempre usar el click del botón**.

### 8.3 Tiempos de espera post-AJAX

- Tras cambiar `transportadora_CR`: esperar **~2500 ms** antes de leer los selects dependientes.
- Tras click en `Crear y cerrar`: esperar **~2000-2500 ms** para que cierre modal y refresque tabla.

Robusto:
```js
await page.waitForResponse(resp => 
  resp.url().includes('/api/') && resp.status() === 200, 
  { timeout: 10000 }
);
```

### 8.4 Bug conocido: fecha de entrega

Al seleccionar transportadora, el ERP pisa `fecha_entrega_esperada` con el valor de `fecha_envio`. **El usuario confirmó que es un bug recurrente del ERP, no intentar corregirlo en cada corrida** — se acepta.

### 8.5 IDs de los registros

Los IDs se incrementan globalmente:
- Órdenes en mayo 2026: ~5340+
- Remisiones: ~3889+
- Guías de transporte: ~4001+

Para identificar la remisión recién creada tras `Crear y cerrar`, buscar la **primera fila** de la tabla post-submit (ordenada por fecha de creación descendente).

### 8.6 Datos hidden importantes

- `<input name="session_empresa" value="34372">` — ID de VAECOS.
- `<input name="session_usuario" value="nutrinat.salas@gmail.com">`.
- `<input name="action" value="3">` — código de acción del backend (crear remisión).
- `<input name="action" value="4">` — código de acción del backend (crear guía).
- `<select name="t_trans_ref[]" value="4">` — tipo de documento origen (4 = nota de remisión).
- `<input name="id_ref[]" value="3889">` — ID de la remisión origen.

---

## 9. Caso ejecutado (referencia)

Hoy 2026-05-13 procesamos las 4 órdenes con estado "PEDIDO CONFIRMADO" sin remisión:

| Orden | Cliente | Productos | Remisión | Guía | Valor declarado | Contenido |
|---|---|---|---|---|---|---|
| 5343 | Ana Lilian Pérez Lares (Chiquimula Z1) | CREMA + GEL × 1 (combo) | #3889 | #4001 | $66 | Copiar del documento |
| 5345 | Olga Hernández (Escuintla) | CREMA × 2 | #3890 | #4002 | $64 | `2x PRODUCTO FEMENINOS VAECOS` |
| 5344 | Yeni Curcin (Chiquimula El Molino) | CREMA × 1 | #3891 | #4003 | $32 | `1x PRODUCTO FEMENINOS VAECOS` |
| 5342 | Norma Noriega (Quiché Uspantán) | CREMA × 1 | #3892 | #4004 | $32 | `1x PRODUCTO FEMENINOS VAECOS` |

Todas con CARGO EXPRESO GT 14% CON RECAUDO, envío 2026-05-13.

---

## 10. Arquitectura recomendada para la plataforma logística

```
┌──────────────────────────────────────────────────────────┐
│  Plataforma logística (web app)                          │
│  - Dashboard de órdenes pendientes                       │
│  - Cola de excepciones (revisión humana)                 │
│  - Historial de corridas con audit log                   │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  Worker / Job runner                                     │
│  - Cron cada N horas (o trigger manual desde dashboard)  │
│  - Lock por job para evitar duplicados concurrentes      │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  Effi Bot (Playwright)                                   │
│  - storageState reusable                                 │
│  - Health check (¿estamos logueados?)                    │
│  - scrape /app/orden_v                                   │
│  - filtra "PEDIDO CONFIRMADO" sin remisión               │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  Clasificador (reglas, NO AI)                            │
│  - parse productos de cada orden                         │
│  - match contra catálogo (config JSON)                   │
│  - decide tipo: combo / crema-solo / desconocido         │
│  - calcula valor declarado                               │
│  - genera string de "Contenido"                          │
│  - valida dirección con heurística                       │
└──────────────────┬───────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  [encaja en reglas]    [no encaja → escalar]
        │                     │
        ▼                     ▼
  Ejecuta flow:         Crea ticket en cola
  - convertir a         humana, notifica vía
    remisión            Slack/Telegram con
  - crear guía          link directo a la orden
  - marca idempotencia
  - log audit
```

### Persistencias mínimas

```sql
-- Estado de cada orden procesada (idempotencia)
CREATE TABLE effi_processed_orders (
  orden_id INT PRIMARY KEY,
  cliente TEXT,
  remision_id INT,
  guia_id INT,
  status TEXT,  -- 'done', 'failed', 'human-review'
  classification TEXT,  -- 'combo', 'crema-only', 'unknown'
  valor_declarado NUMERIC,
  processed_at TIMESTAMP,
  raw_order_snapshot JSONB
);

-- Cola humana
CREATE TABLE effi_human_review (
  id SERIAL PRIMARY KEY,
  orden_id INT,
  reason TEXT,
  details JSONB,
  resolved BOOLEAN DEFAULT false,
  resolved_by TEXT,
  resolved_at TIMESTAMP
);

-- Audit log
CREATE TABLE effi_audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMP DEFAULT now(),
  action TEXT,  -- 'login', 'scrape', 'convert-remision', 'create-guia', 'error'
  orden_id INT,
  payload JSONB
);
```

### Config (catálogo + reglas)

```yaml
# effi-rules.yaml
catalog:
  CREMA ESTRECHANTE:
    valor_unitario: 32
    tipo: femenino
  GEL ESTIMULANTE MULTI ORGÁSMICO:
    valor_unitario: 34
    tipo: femenino

combos:
  - nombre: combo_femenino_basico
    productos:
      - { sku: "CREMA ESTRECHANTE", cantidad_min: 1 }
      - { sku: "GEL ESTIMULANTE MULTI ORGÁSMICO", cantidad_min: 1 }
    cantidades_iguales: true
    valor_declarado_unitario: 66
    contenido_modo: copiar_del_documento

individuales:
  - sku: "CREMA ESTRECHANTE"
    valor_unitario: 32
    contenido_template: "{n}* PRODUCTO FEMENINOS VAECOS"

transportadora_default:
  value: 1
  nombre: "CARGO EXPRESO GT 14% | CON RECAUDO | FLETE CRÉDITO"
  fecha_envio: today
  fecha_entrega_offset_dias_habiles: 3
```

### Recomendaciones operativas

1. **NO AI en el critical path**. Las reglas son deterministas. Meté LLM solo si después de 3 meses la cola humana se llena de patrones repetidos no clasificados.
2. **Idempotencia obligatoria**: nunca procesar una orden dos veces. Verificar primero contra `effi_processed_orders`.
3. **Health check antes de cada corrida**: navegar a `/app/calendario`. Si redirige a `/ingreso`, alertar y abortar.
4. **Audit log de cada click**: para poder reconstruir qué pasó cuando algo falle.
5. **Reintentos con backoff** en errores transitorios (timeout, 502, etc.). Máximo 3 intentos.
6. **Dashboard para humanos**: mostrar cola de excepciones, permitir resolución con un click (escribir contenido custom, valor declarado custom).
7. **Sin captura de password en código**: usar gestor de secretos (Vault, AWS Secrets Manager, .env cifrado).

---

## 11. Preguntas abiertas que deberíamos resolver antes de codificar

1. ¿Cuál es el catálogo completo de productos y precios declarados individuales?
2. ¿Hay otros combos además del CREMA+GEL?
3. ¿Existen otras transportadoras o solo CARGO EXPRESO?
4. ¿Hay productos cuyo `Contenido` requiera redacción especial (no genérica como "FEMENINOS")?
5. ¿La fecha de entrega "3 días hábiles" considera feriados nacionales de Guatemala? (¿hay calendario de feriados?)
6. ¿Qué hacer con órdenes en estado `Generada` (sin confirmar)? ¿Se procesan o se ignoran siempre?
7. ¿Hay productos masculinos / unisex que requieran texto distinto a "FEMENINOS VAECOS"?
8. ¿Frecuencia de corrida ideal? (cada hora, 3 veces al día, on-demand)
9. ¿Quién recibe las notificaciones de escalación humana?
10. ¿Hay límite de paquetes/peso/dimensiones a respetar? (hoy todo va con default `1`).

---

## 12. Cómo iniciar el próximo chat

Cuando empieces el nuevo chat en el proyecto de la plataforma logística:

1. Pegá este markdown al inicio (o referencialo si está en el repo).
2. Pedile a Claude que busque en Engram con keyword **`effi-automation`** o **`vaecos`** — hay memorias guardadas que complementan este doc.
3. Confirmá las preguntas abiertas de la sección 11 antes de pedir código.
4. Empezá por el módulo más bajo riesgo: **scraping read-only** de `/app/orden_v` con storageState. Sin escribir nada al ERP. Validar primero que el bot entiende qué leer.
5. Luego: el **clasificador** offline, con tests unitarios usando los 4 casos del histórico (sección 9).
6. Luego: la **escritura** (convert remisión, crear guía) en una orden de prueba.
7. Por último: orquestación, cola humana, dashboard.

---

**Fin del documento**. Cualquier ajuste/clarificación, anotar arriba del bloque relevante y dejar registro en el changelog abajo.

## Changelog
- `2026-05-13` — Documento inicial tras ejecución manual de 4 órdenes con Playwright.
