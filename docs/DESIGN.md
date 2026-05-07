# VAECOS Tracking — Sistema de Diseño

Version: v2.0
Fecha: 2026-05-06

> El diseño de referencia completo (React funcional, 11 pantallas) vive en `docs/design-system/`.
> Este archivo es el resumen ejecutivo del sistema de diseño para implementación.

---

## Identidad visual

**Personalidad**: autoritativo, preciso, urgente. "Glass cockpit" — denso en información pero estructurado para procesamiento cognitivo inmediato.

**Estilo**: Corporate / Modern con Data-Centric Minimalism. Transiciones de alto contraste entre superficies cálidas neutras y rojo de acción.

---

## Tokens de color

```css
/* Brand */
--brand: #DC2626;
--brand-strong: #B91C1C;
--brand-soft: #FEE2E2;
--brand-tint: #FEF2F2;

/* Neutrals — cálidos, no fríos */
--bg: #FAFAF9;
--surface: #FFFFFF;
--surface-2: #F7F7F5;
--border: #E7E5E1;
--border-strong: #D6D3CE;
--hover: #F4F3F0;

/* Text */
--ink: #1A1A1A;
--ink-2: #3D3D3A;
--muted: #76746F;
--muted-2: #A3A09A;

/* Semantic */
--ok: #15803D;          --ok-soft: #DCFCE7;      --ok-tint: #F0FDF4;
--warn: #B45309;        --warn-soft: #FEF3C7;    --warn-tint: #FFFBEB;
--info: #1D4ED8;        --info-soft: #DBEAFE;    --info-tint: #EFF6FF;
--danger: #B91C1C;      --danger-soft: #FEE2E2;  --danger-tint: #FEF2F2;

/* Sidebar — carbón cálido */
--side-bg: #1C1B19;
--side-bg-2: #232220;
--side-text: #E8E6E1;
--side-muted: #8B8A85;
--side-border: #2D2C2A;
--side-active: #2F2E2C;
```

Dark mode completo disponible en `docs/design-system/project/app/styles.css`.

---

## Tipografía

- **Sans**: Geist (`'Geist', -apple-system, system-ui, sans-serif`)
- **Mono**: Geist Mono (`'Geist Mono', ui-monospace, 'SF Mono', monospace`)
- Base: 14px / line-height 1.5
- Font features: `cv11`, `ss01`
- Numbers: `font-feature-settings: 'tnum'` para tabular

---

## Layout

```
grid: 232px (sidebar fija) + minmax(0, 1fr) (contenido)
main padding: 24px 32px 48px
max-width contenido: 1400px
```

---

## Radii

```css
--r-sm: 6px    /* nav items, chips pequeños */
--r:    8px    /* botones, inputs, cards pequeñas */
--r-lg: 12px   /* panels, KPI cards, modales */
```

---

## Componentes principales

### KPI Cards
- `background: var(--surface)` + `border: 1px solid var(--border)` + `border-radius: var(--r-lg)`
- Variante `.alert`: border/bg en danger-tint cuando hay urgencia
- Sparklines SVG en esquina inferior derecha
- Delta badges: `.delta.up` (verde), `.delta.down` (rojo), `.delta.flat` (gris)

### Pills de estado
```
.pill.ok      → ok-tint bg, ok text, ok-soft border
.pill.warn    → warn-tint bg
.pill.danger  → danger-tint bg
.pill.info    → info-tint bg
.pill.neutral → surface-2 bg
```

### Carrier badges
```
.carrier-mark.effi   → #FEE2E2 bg, #991B1B text
.carrier-mark.guatex → #DBEAFE bg, #1E40AF text
```

### Botones
```
.btn          → surface bg, border, ink text
.btn.primary  → ink bg, white text
.btn.brand    → #DC2626 bg, white text
.btn.danger   → danger text, danger-tint on hover
.btn.sm       → padding reducido
.btn.icon     → solo ícono, sin texto
```

### Tablas
- Headers: 11px, uppercase, letter-spacing 0.05em, color muted, bg surface-2
- Rows: hover con `var(--hover)`, `font-mono` para IDs y números
- `.num` para columnas de números (text-align: right, tnum)

### Filter bar
- `.filterbar` con `.chip` pill-buttons
- `.chip.active` → ink bg, white text

### Sidebar nav
- Item activo: `background: var(--side-active)` + borde izquierdo 2px rojo
- Badge de conteo: `.nav-badge` rojo
- User card al fondo con avatar gradiente rojo

---

## Pantallas diseñadas

| Ruta | Pantalla | Archivo |
|------|----------|---------|
| `/` | Centro Operativo | `screen-centro.jsx` |
| `/attention` | Requiere Atención | `screen-attention.jsx` |
| `/analytics` | Analytics | `screen-analytics.jsx` |
| `/runs` | Historial de corridas | `screen-extras.jsx` |
| `/runs/<id>` | Detalle de corrida | `screen-rest.jsx` |
| `/run/new` | Nueva corrida | `screen-rest.jsx` |
| `/run/progress/<token>` | Progreso en vivo | `screen-extras.jsx` |
| `/rules` | Motor de reglas | `screen-rest.jsx` |
| `/guides/<guia>` | Detalle de guía | `screen-extras.jsx` |
| `/clients/<cliente>` | Detalle de cliente | `screen-extras.jsx` |
| `/analytics/por-recoger` | Por recoger | `screen-extras.jsx` |

---

## Notas de implementación

- El CSS embebido actual de `v0.3/vaecos_v03/render.py` se reemplaza por Jinja2 templates + `styles.css` externo.
- Los textos que referencian "Notion" en el diseño (ej: "cambios en Notion") se actualizan en Fase 2 cuando se retire Notion del flujo.
- Los iconos están en `docs/design-system/project/app/icons.jsx` — son SVG inline, no requieren librería externa.
- Dark mode se activa con `data-theme="dark"` en `<html>` — no requiere JS framework.
- Los datos de ejemplo están en `docs/design-system/project/app/data.js` — referencia para los queries SQLite necesarios.
