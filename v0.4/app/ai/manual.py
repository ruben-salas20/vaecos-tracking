"""Manual de usuario del aplicativo VAECOS — knowledge base para la IA.

Estructura: dict `HELP_TOPICS` keyed por topic_id, cada entry tiene:
  - title: título visible
  - keywords: lista de aliases/sinónimos para matching
  - content: markdown del contenido

Función pública `get_help(topic_query)` busca el tópico más relevante por
overlap de keywords y devuelve su contenido. Si nada matchea, devuelve el
índice de tópicos disponibles.
"""
from __future__ import annotations


HELP_TOPICS: dict[str, dict] = {
    # ── NAVEGACIÓN GENERAL ────────────────────────────────────────
    "overview": {
        "title": "Resumen general de VAECOS",
        "keywords": ["resumen", "general", "aplicativo", "app", "qué es", "para qué", "overview", "intro", "panel"],
        "content": """
**VAECOS Tracking** es una plataforma para reconciliar el estado de envíos en Notion contra carriers
(Effi/Cargo Expreso) y gestionar las operaciones del negocio. Tiene 4 grandes áreas:

1. **Operación** — Centro Operativo, Todas las guías, Buscar, Requiere atención.
2. **Inteligencia** — Analytics, Por recoger, Historial de corridas.
3. **Finanzas** — Movimientos de ingresos/egresos en COP, Analytics financieros.
4. **Acciones** — Nueva corrida, Importar guías (Excel), Creador automático de guías Effi.

Hay también un área **Admin** (solo administradores) con Reglas, Usuarios, Catálogo Effi y
Catálogo de categorías financieras.
""",
    },

    # ── GUÍAS ────────────────────────────────────────────────────
    "guias": {
        "title": "Gestión de guías",
        "keywords": ["guía", "guías", "guides", "envío", "envíos", "tracking", "paquete", "paquetes"],
        "content": """
**Guías** son los envíos que se sincronizan desde Notion + carriers.

- **Ver todas**: sidebar → "Todas las guías" (`/all-guides`). Tabla con filtros por estado, carrier,
  e incluir archivadas. Sincronización automática se ejecuta al final de cada corrida.
- **Buscar una guía específica**: sidebar → "Buscar". Detecta automáticamente si es número de guía,
  DPI o nombre.
- **Detalle de una guía**: click en cualquier guía. Muestra historial de eventos, notas operadora,
  edición de estado, botón "Correr esta guía" (dry-run o apply).
- **Crear guía nueva manual**: en `/all-guides`, botón "Nueva guía".
- **Archivar/restaurar**: el botón está en el detalle. Las archivadas van a "papelera de Notion"
  (recuperables 30 días).

Edición de estado, producto, teléfono, valor y cantidad son **atómicas**: si Notion rechaza el
cambio, NO se actualiza local. Cada edición queda en `guide_edits` con autor + timestamp.
""",
    },

    # ── ESTADOS ──────────────────────────────────────────────────
    "estados": {
        "title": "Estados de las guías",
        "keywords": ["estado", "estados", "novedad", "novedades", "qué significa", "glosario", "entregado", "gestión"],
        "content": """
Los estados (campo "Estado novedad" en Notion) marcan en qué etapa está cada envío:

- **Sin recolectar** — guía creada pero el carrier todavía no la pasó a recoger.
- **Por recoger (INFORMADO)** — el carrier ya sabe, pendiente de pasar.
- **En tránsito** / **En distribución** — el paquete se está moviendo.
- **ENTREGADA** — entregada al cliente (estado terminal positivo).
- **En novedad** — el carrier reportó un problema (dirección incorrecta, teléfono no contesta, etc.).
- **Gestión novedad** — la operadora está trabajando en resolver la novedad.
- **Cambio de estado** — el sistema propuso un cambio que requiere revisión humana.
- **En Devolución** — el envío vuelve al vendedor.
- **Indemnización** — el carrier pagará por la pérdida/daño del paquete.
- **Manual review** — el motor de reglas escaló para revisión.
- **Bodega clientes** — el paquete quedó en bodega esperando que el cliente lo retire.

El motor de reglas evalúa estos estados y propone transiciones. Algunas son automáticas (`--apply`),
otras requieren revisión humana.
""",
    },

    # ── CORRIDAS ─────────────────────────────────────────────────
    "corridas": {
        "title": "Corridas de tracking",
        "keywords": ["corrida", "corridas", "run", "runs", "ejecutar", "tracking run", "nueva corrida"],
        "content": """
Una **corrida** ejecuta el motor de reglas sobre las guías activas, consultando el carrier para
obtener el estado actual y decidiendo cambios.

- **Lanzar manual**: sidebar → "Nueva corrida". Opciones:
  - Guías específicas o todas las activas
  - Modo `dry-run` (no escribe nada, solo simula)
  - Modo `apply` (escribe los cambios en Notion)
- **Ver progreso**: aparece una página de progreso con polling automático.
- **Historial**: sidebar → "Historial corridas". Cada corrida muestra # de cambios, guías sin
  cambio, errores y duración. Click para ver detalle.
- **Exportar**: dentro del detalle de una corrida, botón "Export Effi" descarga un Excel con las
  guías que requieren "Gestionar con encargado".

Las corridas también se ejecutan automáticamente vía cron (en VPS) o disparadas por el bot Effi.
""",
    },

    # ── REGLAS ───────────────────────────────────────────────────
    "reglas": {
        "title": "Motor de reglas (admin)",
        "keywords": ["regla", "reglas", "rule", "rules", "motor", "transición", "lógica", "automation"],
        "content": """
El **motor de reglas** decide qué estado debe tener cada guía después de consultar al carrier.

- **Ver reglas**: sidebar → "Reglas" (solo admin). Lista todas con prioridad, estado actual del
  carrier, novedad esperada, días, y acción a tomar.
- **Crear/editar regla**: cada regla tiene:
  - Prioridad (orden de evaluación, ascendente)
  - Match por `estado` (any, equals_one_of, contains_any_of)
  - Match por `novedad` (same)
  - Filtro de días (gt, gte, lt, lte, no_date)
  - Acción: estado propuesto, requiere_revisión, etc.
- **Preview**: antes de guardar, podés probar una regla nueva con `/rules/preview?guia=<X>` para
  ver qué decisión tomaría sobre una guía específica.
- **Audit trail**: cada cambio queda en `rule_history` con autor + timestamp.

Las reglas se evalúan en orden estratificado: terminal → operacional → contextual → estancamiento
→ preservación. La primera que matchea dentro de cada fase gana.
""",
    },

    # ── IMPORTAR EXCEL ───────────────────────────────────────────
    "importar": {
        "title": "Importar guías por Excel",
        "keywords": ["importar", "import", "excel", "xlsx", "carga", "cargar guías", "subir guías"],
        "content": """
Importa guías nuevas desde un Excel exportado del ERP de la operadora.

1. Sidebar → "Importar guías" (`/import`).
2. Subir el archivo `.xlsx`. El parser detecta headers automáticamente (normaliza acentos,
   case-insensitive).
3. Preview muestra:
   - Guías **nuevas** (no existen en la DB)
   - Guías **skipped** (ya existen)
   - **Errores** (filas malformadas)
4. Confirmar → crea las páginas en Notion vía API.
5. Cada import queda registrado en `import_log` con autor + counts.

**Nota**: con el bot Effi corriendo, la mayoría de las guías nuevas se crean automáticamente
y este flujo es solo para casos especiales (carrier no soportado por el bot, carga histórica, etc.).
""",
    },

    # ── BOT EFFI ─────────────────────────────────────────────────
    "effi": {
        "title": "Creador automático de guías Effi (bot)",
        "keywords": ["effi", "bot", "creador guías", "creador de guías", "automatización", "playwright", "erp"],
        "content": """
El **Creador de guías Effi** es un bot que automatiza la creación de remisiones y guías en el ERP
de Effi (sin API, scrapeando el HTML).

- **Dashboard**: sidebar → "Creador guías" (`/effi`). Muestra órdenes pendientes, cola humana
  y audit log.
- **Catálogo de productos** (admin): `/effi/catalog`. Productos con descripción exacta, aliases
  para match difuso, tipo (íntimo femenino / otro) y precio declarado.
- **Cola humana**: `/effi/queue`. Pedidos no automatizables (dirección inválida, producto fuera de
  catálogo, etc.) esperando que la operadora resuelva manualmente.
- **Audit log**: `/effi/audit`. Cada acción del bot queda registrada: orden creada, remisión
  generada, guía creada, escalación, error.
- **Lanzar manual**: botón "Procesar ahora" desde el dashboard. Corre headless.
- **Cron**: en producción corre cada hora vía cron en el VPS.

El bot también sincroniza cada guía nueva con Notion automáticamente (cierre del loop).
""",
    },

    # ── FINANZAS ─────────────────────────────────────────────────
    "finanzas": {
        "title": "Módulo financiero",
        "keywords": ["finanzas", "financiero", "dinero", "plata", "ingresos", "egresos", "balance", "movimientos", "cop"],
        "content": """
**Finanzas** lleva el libro de movimientos del negocio en COP (peso colombiano).

- **Movimientos**: sidebar → "Movimientos" (`/finanzas`). Tabla con filtros por año (default año
  actual), mes, tipo (ingreso/egreso/transferencia), categoría y búsqueda libre. Paginación 50/página.
- **Crear movimiento**: botón "+ Nuevo movimiento". Campos: fecha, tipo, monto en COP (formato
  colombiano '1.234.567,89'), observación, categoría(s) y vinculación opcional a una guía.
- **Editar/borrar**: cualquier usuario puede editar sus propios movimientos. Solo admin puede
  borrar. Multi-categoría es válido (ej: "DEUDA + PUBLICIDAD" en un mismo pago de tarjeta).
- **Analytics**: sidebar → "Analytics finanzas" (`/finanzas/analytics`). KPIs (ingresos, egresos,
  balance), top categorías, evolución mensual. Botón "Exportar Excel" descarga el período.
- **Catálogo de categorías** (admin): `/finanzas/categorias`. Crear/editar/desactivar categorías.
  No se pueden borrar (protección FK); solo desactivar — las desactivadas dejan de aparecer en el
  formulario de nuevo movimiento pero siguen visibles en históricos.

El histórico inicial se importó desde Notion (~445 movimientos 2025-2026). Nuevas capturas van
directo a SQLite.
""",
    },

    # ── ANALYTICS ────────────────────────────────────────────────
    "analytics": {
        "title": "Analytics operativos",
        "keywords": ["analytics", "kpi", "kpis", "métricas", "metricas", "dashboard", "estadísticas", "reportes"],
        "content": """
**Analytics** (`/analytics`) muestra KPIs operativos del negocio logístico:

- **Por recoger** — guías en estados pendientes de recolección.
- **Backlog antiguo** — guías con >N días sin movimiento (umbral configurable).
- **Tasa de resolución** — % de guías que terminaron en estados terminales (entregada / devolución).
- **Tiempo de ciclo** — días promedio desde creación hasta estado terminal.
- **Guías activas** — total de guías no terminales.

Filtros: presets 7d / 30d / 90d, rango custom con fechas, umbral backlog.

Hay también:
- **Manual de métricas** (`/analytics/manual`) — qué muestra cada KPI, cómo se calcula, qué acción tomar.
- **Por recoger** (`/por-recoger`) — vista detallada con paginación.

Para finanzas hay un Analytics aparte (`/finanzas/analytics`).
""",
    },

    # ── BÚSQUEDA Y ATENCIÓN ──────────────────────────────────────
    "buscar": {
        "title": "Buscar guías y clientes",
        "keywords": ["buscar", "búsqueda", "search", "encontrar", "dpi", "cliente", "teléfono"],
        "content": """
**Buscar** (`/search`) acepta cualquier dato y enruta automáticamente:

- Número de guía (formato `B...-N`) → detalle de la guía.
- DPI (13 dígitos) → perfil del cliente (todas sus guías agrupadas por DPI).
- Teléfono o nombre → lista de clientes que matchean.

Tip: la IA (este asistente) también busca con `search_guides(query)`. Si querés interfaz visual,
usá `/search`. Si querés respuesta narrativa, preguntame.
""",
    },

    "atencion": {
        "title": "Guías que requieren atención",
        "keywords": ["atención", "atencion", "requiere atención", "revisión", "manual review", "urgente"],
        "content": """
**Requiere atención** (`/attention`) lista guías priorizadas para revisión humana:

- Filtros por categoría: Cambios propuestos, Revisión manual, Errores.
- Se actualiza tras cada corrida del motor de reglas.
- Click en una fila abre el detalle de la guía con su contexto.

Esta vista es el punto de partida diario de la operadora.
""",
    },

    # ── USUARIOS ─────────────────────────────────────────────────
    "usuarios": {
        "title": "Gestión de usuarios (admin)",
        "keywords": ["usuario", "usuarios", "user", "admin", "rol", "permisos", "cuenta", "contraseña"],
        "content": """
**Usuarios** (`/users`, solo admin):

- Crear: email + nombre + password (mínimo 8 caracteres) + rol (user / admin).
- Activar/desactivar (toggle). Un usuario desactivado no puede loguearse pero se mantienen sus
  registros históricos.
- Restablecer contraseña (genera una nueva que el admin le pasa al usuario).
- Eliminar (cuidado: pierde audit trail del usuario).

Cada usuario puede editar su propio perfil y cambiar contraseña en `/mi-cuenta` (popover del avatar).

Permisos resumidos:
- **user**: crea/edita guías, edita estados, corre el tracking, captura finanzas, usa el bot Effi.
- **admin**: todo lo anterior + gestión de reglas, usuarios, catálogo Effi, catálogo finanzas, borrado de movimientos.
""",
    },

    # ── ASISTENTE IA ─────────────────────────────────────────────
    "ia": {
        "title": "Asistente IA (este chat)",
        "keywords": ["asistente", "ia", "chat", "bot conversacional", "preguntar"],
        "content": """
El **asistente IA** (yo mismo) es un widget flotante disponible en cualquier pantalla. Sirve para:

- Preguntar sobre guías, finanzas, clientes, corridas en lenguaje natural.
- Consultar el manual de la app (lo que estás leyendo ahora).
- Obtener KPIs rápidos sin navegar.

**No alucino**: si una pregunta no tiene respuesta en mi data, te lo digo y ofrezco alternativa.

Limites:
- Máximo 30 mensajes por hora por usuario.
- Cada conversación guarda los últimos 20 turnos (se trunca el más viejo).
- Botón 🗑 limpia toda la conversación.

Para reportar bugs del asistente o sugerir tools nuevas, escribile al admin.
""",
    },

    # ── DEPLOY / VPS / OPERACIÓN TÉCNICA ─────────────────────────
    "deploy": {
        "title": "Deploy y operación del VPS",
        "keywords": ["deploy", "vps", "producción", "produccion", "servidor", "hostinger", "caddy"],
        "content": """
La plataforma corre en un VPS Hostinger (Ubuntu 24.04) en `https://app.vaecos.com`:

- Stack: Flask + Waitress detrás de Caddy (TLS automático Let's Encrypt).
- Servicio systemd: `vaecos.service`. Logs con `journalctl -u vaecos -f`.
- DB SQLite: `/opt/vaecos/data/vaecos_tracking.db` (WAL mode).
- Backups: cron diario a las 3am UTC con rotación 14 días. Path: `/opt/vaecos/backups/`.

**Deploy de un cambio**:
```
git push (local)
ssh vaecos@VPS "cd /opt/vaecos && git pull && sudo systemctl restart vaecos"
```

Si cambian dependencias: agregar `&& .venv/bin/pip install -r v0.4/requirements.txt`.

Esta info es para uso del admin / mantenedor del proyecto.
""",
    },
}


def _normalize(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()


def get_help(topic_query: str | None) -> dict:
    """Busca el tópico más relevante. Si nada matchea, devuelve el índice.

    Args:
        topic_query: string libre del usuario / modelo (ej. "cómo importar excel")

    Returns:
        dict con:
          - found: bool — True si encontró un match
          - topic_id: str | None — id del tópico match
          - title, content: del tópico
          - available_topics: lista de todos los tópicos (solo si found=False)
    """
    if not topic_query or not isinstance(topic_query, str):
        return _topic_index()

    q = _normalize(topic_query)
    if not q:
        return _topic_index()

    # Score por overlap de palabras del query contra keywords + title + topic_id
    q_words = set(q.split())

    best_score = 0
    best_id = None
    for topic_id, spec in HELP_TOPICS.items():
        haystack_parts = [topic_id, spec["title"]] + spec["keywords"]
        haystack = " ".join(_normalize(p) for p in haystack_parts)
        haystack_words = set(haystack.split())

        # Score: cuántas palabras del query aparecen en el haystack
        overlap = len(q_words & haystack_words)
        # Bonus si el topic_id está en el query
        if topic_id in q:
            overlap += 3
        # Bonus si alguna keyword larga (>3 chars) está completa en el query
        for kw in spec["keywords"]:
            if len(kw) > 3 and _normalize(kw) in q:
                overlap += 2
        if overlap > best_score:
            best_score = overlap
            best_id = topic_id

    if best_id is None or best_score == 0:
        return _topic_index()

    spec = HELP_TOPICS[best_id]
    return {
        "found": True,
        "topic_id": best_id,
        "title": spec["title"],
        "content": spec["content"].strip(),
    }


def _topic_index() -> dict:
    return {
        "found": False,
        "topic_id": None,
        "title": None,
        "content": None,
        "available_topics": [
            {"topic_id": tid, "title": spec["title"]}
            for tid, spec in HELP_TOPICS.items()
        ],
        "hint": (
            "No encontré un tópico específico. Decile al usuario los temas disponibles y pedile "
            "que aclare. O llamá get_app_help con un tópico más específico de los listados."
        ),
    }
