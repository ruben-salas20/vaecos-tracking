// Datos demo realistas para VAECOS — clientes guatemaltecos, formato de guía Effi
window.VAECOS_DATA = {
  latestRun: {
    id: 28,
    timestamp: "2026-04-30 14:32",
    duration: "3m 47s",
    mode: "apply",
    total: 1204,
    changed: 187,
    unchanged: 932,
    manual: 42,
    parseError: 8,
    error: 35,
    triggeredBy: "Operadora · Auto-cron",
  },
  attentionGuides: [
    { id: "B263378877-1", cliente: "Curacao Centro", carrier: "effi", estado: "En Bodega Origen", cambios: 7, dias: 4, motivo: "Sin movimiento 4 días", prioridad: "alta", origen: "Guatemala, GT", destino: "Quetzaltenango, GT" },
    { id: "B263401336-1", cliente: "Cemaco Naranjo", carrier: "effi", estado: "Devuelto a Origen", cambios: 5, dias: 2, motivo: "Cliente no localizado (3 intentos)", prioridad: "alta", origen: "Guatemala, GT", destino: "Cobán, GT" },
    { id: "B263409347-1", cliente: "PriceSmart Roosevelt", carrier: "guatex", estado: "Reprogramada", cambios: 4, dias: 6, motivo: "Reprogramación 2da vez", prioridad: "media", origen: "Mixco, GT", destino: "Escuintla, GT" },
    { id: "B263400064-1", cliente: "Walmart Pradera", carrier: "effi", estado: "Daño en bodega", cambios: 6, dias: 3, motivo: "Reportado daño parcial", prioridad: "alta", origen: "Guatemala, GT", destino: "Huehuetenango, GT" },
    { id: "B263412908-1", cliente: "Office Depot Z10", carrier: "effi", estado: "En tránsito", cambios: 3, dias: 5, motivo: "Demora en ruta Atlántico", prioridad: "media", origen: "Guatemala, GT", destino: "Puerto Barrios, GT" },
    { id: "B263415221-1", cliente: "Max Distelsa", carrier: "guatex", estado: "Sin escaneo", cambios: 2, dias: 7, motivo: "Última lectura hace 7 días", prioridad: "alta", origen: "Guatemala, GT", destino: "Retalhuleu, GT" },
    { id: "B263418773-1", cliente: "La Torre Vista Hermosa", carrier: "effi", estado: "Pendiente recolección", cambios: 1, dias: 2, motivo: "Recolección no agendada", prioridad: "baja", origen: "Guatemala, GT", destino: "Antigua, GT" },
    { id: "B263421440-1", cliente: "Curacao Z11", carrier: "effi", estado: "Cliente no localizado", cambios: 4, dias: 3, motivo: "2 intentos fallidos", prioridad: "media", origen: "Guatemala, GT", destino: "Chimaltenango, GT" },
  ],
  recentRuns: [
    { id: 28, fecha: "2026-04-30 14:32", modo: "apply", total: 1204, changed: 187, attention: 42, errors: 8, dur: "3m 47s" },
    { id: 27, fecha: "2026-04-30 09:00", modo: "apply", total: 1198, changed: 156, attention: 38, errors: 4, dur: "3m 22s" },
    { id: 26, fecha: "2026-04-29 18:45", modo: "dry-run", total: 1187, changed: 142, attention: 35, errors: 6, dur: "3m 11s" },
    { id: 25, fecha: "2026-04-29 14:30", modo: "apply", total: 1187, changed: 168, attention: 33, errors: 3, dur: "3m 04s" },
    { id: 24, fecha: "2026-04-29 09:00", modo: "apply", total: 1175, changed: 144, attention: 31, errors: 5, dur: "2m 58s" },
    { id: 23, fecha: "2026-04-28 18:45", modo: "dry-run", total: 1162, changed: 129, attention: 28, errors: 7, dur: "3m 02s" },
  ],
  topClientes: [
    { nombre: "Curacao Centro", total: 184, attention: 12, ratio: 0.065 },
    { nombre: "Cemaco Naranjo", total: 142, attention: 9, ratio: 0.063 },
    { nombre: "Walmart Pradera", total: 128, attention: 7, ratio: 0.054 },
    { nombre: "PriceSmart Roosevelt", total: 96, attention: 5, ratio: 0.052 },
    { nombre: "Max Distelsa", total: 88, attention: 4, ratio: 0.045 },
    { nombre: "Office Depot Z10", total: 76, attention: 3, ratio: 0.039 },
  ],
  // 30 días de tendencia
  trend: Array.from({ length: 30 }, (_, i) => {
    const day = i + 1;
    const base = 1100 + Math.sin(i / 4) * 60 + i * 3;
    const att = 28 + Math.sin(i / 3) * 8 + (i > 22 ? (i - 22) * 1.5 : 0);
    return {
      fecha: `04-${String(day).padStart(2, "0")}`,
      total: Math.round(base),
      changed: Math.round(base * 0.14 + Math.cos(i / 2) * 12),
      attention: Math.max(15, Math.round(att)),
    };
  }),
  estadosBreakdown: [
    { label: "Procesada / Entregada", count: 738, color: "ok" },
    { label: "Sin cambios", count: 194, color: "neutral" },
    { label: "En tránsito", count: 142, color: "info" },
    { label: "Requiere atención", count: 42, color: "danger" },
    { label: "Reprogramada", count: 53, color: "warn" },
    { label: "Error de parseo", count: 8, color: "muted" },
    { label: "Error de red", count: 27, color: "muted" },
  ],
  rules: [
    { id: 1, prio: 10, nombre: "Devuelto → Atención", condicion: "estado contiene 'devuelto'", accion: "marcar atención", activa: true, hits: 47 },
    { id: 2, prio: 20, nombre: "Sin escaneo > 5 días", condicion: "dias_sin_escaneo > 5", accion: "marcar atención", activa: true, hits: 31 },
    { id: 3, prio: 30, nombre: "Cliente no localizado", condicion: "intentos_fallidos >= 2", accion: "marcar atención", activa: true, hits: 23 },
    { id: 4, prio: 40, nombre: "Daño reportado", condicion: "estado contiene 'daño'", accion: "marcar urgente", activa: true, hits: 12 },
    { id: 5, prio: 50, nombre: "Reprogramación 2da", condicion: "reprogramaciones >= 2", accion: "marcar atención", activa: true, hits: 18 },
    { id: 6, prio: 60, nombre: "Entregada → cerrar", condicion: "estado = 'entregada'", accion: "marcar procesada", activa: true, hits: 412 },
    { id: 7, prio: 70, nombre: "En bodega > 3 días", condicion: "dias_bodega > 3", accion: "marcar revisar", activa: true, hits: 19 },
    { id: 8, prio: 80, nombre: "Effi parse error", condicion: "carrier=effi & parse_error", accion: "log + skip", activa: true, hits: 8 },
    { id: 9, prio: 90, nombre: "Guatex stub", condicion: "carrier=guatex", accion: "manual review", activa: false, hits: 0 },
    { id: 10, prio: 100, nombre: "Default → unchanged", condicion: "ninguna anterior", accion: "marcar sin cambios", activa: true, hits: 932 },
  ],
  // ── Por recoger en oficina (M3 v2) ───────────────────────────────
  porRecoger: {
    delivered: [
      { guia: "B263380120-1", cliente: "Curacao Centro", carrier: "effi", estadoFinal: "Entregada", runId: 27, fecha: "2026-04-29" },
      { guia: "B263380455-1", cliente: "Cemaco Naranjo", carrier: "effi", estadoFinal: "Entregada", runId: 27, fecha: "2026-04-29" },
      { guia: "B263381099-1", cliente: "Walmart Pradera", carrier: "effi", estadoFinal: "Entregada", runId: 26, fecha: "2026-04-28" },
      { guia: "B263382441-1", cliente: "PriceSmart Roosevelt", carrier: "effi", estadoFinal: "Entregada", runId: 26, fecha: "2026-04-28" },
      { guia: "B263383902-1", cliente: "Office Depot Z10", carrier: "effi", estadoFinal: "Entregada", runId: 25, fecha: "2026-04-27" },
      { guia: "B263384712-1", cliente: "La Torre Vista Hermosa", carrier: "effi", estadoFinal: "Entregada", runId: 25, fecha: "2026-04-27" },
      { guia: "B263385188-1", cliente: "Max Distelsa", carrier: "effi", estadoFinal: "Entregada", runId: 24, fecha: "2026-04-26" },
    ],
    returned: [
      { guia: "B263390041-1", cliente: "Curacao Z11", carrier: "effi", estadoFinal: "Devuelta a origen", runId: 28, fecha: "2026-04-30" },
      { guia: "B263391772-1", cliente: "Cemaco Naranjo", carrier: "effi", estadoFinal: "Devuelta a origen", runId: 27, fecha: "2026-04-29" },
      { guia: "B263392188-1", cliente: "Walmart Pradera", carrier: "effi", estadoFinal: "Devuelta a origen", runId: 26, fecha: "2026-04-28" },
    ],
    pending: [
      { guia: "B263395010-1", cliente: "Curacao Centro", carrier: "effi", estado: "Por recoger (INFORMADO)", accion: "Avisar a cliente", runId: 28, dias: 3 },
      { guia: "B263395887-1", cliente: "PriceSmart Roosevelt", carrier: "effi", estado: "Por recoger (INFORMADO)", accion: "Avisar a cliente", runId: 28, dias: 5 },
      { guia: "B263396204-1", cliente: "Office Depot Z10", carrier: "effi", estado: "Por recoger (INFORMADO)", accion: "Avisar a cliente", runId: 28, dias: 2 },
      { guia: "B263397105-1", cliente: "La Torre Vista Hermosa", carrier: "effi", estado: "Por recoger (INFORMADO)", accion: "Pasar a Sin movimiento", runId: 28, dias: 8 },
      { guia: "B263397922-1", cliente: "Max Distelsa", carrier: "effi", estado: "Por recoger (INFORMADO)", accion: "Avisar a cliente", runId: 28, dias: 4 },
    ],
  },
  // ── Carrier breakdown (Analytics) ────────────────────────────────
  carrierBreakdown: [
    { carrier: "effi", uniqueGuides: 1089, totalRows: 4256, unchanged: 3201, changed: 712, manual: 198, parseError: 32, error: 113 },
    { carrier: "guatex", uniqueGuides: 115, totalRows: 460, unchanged: 0, changed: 0, manual: 460, parseError: 0, error: 0 },
  ],
  // ── Tiempo promedio por estado Effi ──────────────────────────────
  avgTimeInStatus: [
    { status: "En reparto", avgRuns: 1.42, maxRuns: 4, guides: 312 },
    { status: "Entregada", avgRuns: 1.08, maxRuns: 2, guides: 738 },
    { status: "En tránsito", avgRuns: 2.18, maxRuns: 8, guides: 142 },
    { status: "Por recoger (INFORMADO)", avgRuns: 4.71, maxRuns: 14, guides: 28 },
    { status: "En Bodega Origen", avgRuns: 3.92, maxRuns: 11, guides: 47 },
    { status: "Sin escaneo", avgRuns: 6.83, maxRuns: 18, guides: 12 },
    { status: "Devuelto a Origen", avgRuns: 2.34, maxRuns: 6, guides: 19 },
  ],
  // ── Historial de una guía individual ─────────────────────────────
  guideHistory: {
    "B263378877-1": {
      cliente: "Curacao Centro",
      carrier: "effi",
      origen: "Guatemala, GT",
      destino: "Quetzaltenango, GT",
      ultimoResultado: "manual_review",
      ultimoEstadoPropuesto: "Sin movimiento",
      ultimaCorrida: 28,
      diasEnSistema: 9,
      timeline: [
        { runId: 28, fecha: "2026-04-30 14:32", modo: "apply", carrier: "effi", resultado: "manual_review", notion: "En tránsito", effi: "En Bodega Origen", propuesto: "Sin movimiento", motivo: "Sin movimiento por 4 días. Se sugiere pasar a Sin movimiento." },
        { runId: 27, fecha: "2026-04-30 09:00", modo: "apply", carrier: "effi", resultado: "unchanged", notion: "En tránsito", effi: "En Bodega Origen", propuesto: "En Bodega Origen", motivo: "Se mantiene En Bodega Origen." },
        { runId: 26, fecha: "2026-04-29 18:45", modo: "dry-run", carrier: "effi", resultado: "unchanged", notion: "En tránsito", effi: "En Bodega Origen", propuesto: "En Bodega Origen", motivo: "Se mantiene En Bodega Origen." },
        { runId: 25, fecha: "2026-04-29 14:30", modo: "apply", carrier: "effi", resultado: "changed", notion: "En reparto", effi: "En Bodega Origen", propuesto: "En Bodega Origen", motivo: "Cambio detectado: vuelve a bodega." },
        { runId: 24, fecha: "2026-04-29 09:00", modo: "apply", carrier: "effi", resultado: "unchanged", notion: "En reparto", effi: "En reparto", propuesto: "En reparto", motivo: "Sin cambio." },
        { runId: 23, fecha: "2026-04-28 18:45", modo: "dry-run", carrier: "effi", resultado: "changed", notion: "En tránsito", effi: "En reparto", propuesto: "En reparto", motivo: "Cambio detectado: ahora en reparto." },
        { runId: 22, fecha: "2026-04-28 14:30", modo: "apply", carrier: "effi", resultado: "unchanged", notion: "En tránsito", effi: "En tránsito", propuesto: "En tránsito", motivo: "Sin cambio." },
      ],
    },
  },
  // ── Detalle de cliente ───────────────────────────────────────────
  clientDetail: {
    "Curacao Centro": {
      summary: { uniqueGuides: 24, totalRows: 184, changed: 38, manual: 12, parseError: 2, error: 5 },
      history: [
        { runId: 28, fecha: "2026-04-30 14:32", modo: "apply", carrier: "effi", guia: "B263378877-1", resultado: "manual_review", accion: "Sin movimiento 4 días", notion: "En tránsito", effi: "En Bodega Origen", propuesto: "Sin movimiento", motivo: "Sin movimiento por 4 días." },
        { runId: 28, fecha: "2026-04-30 14:32", modo: "apply", carrier: "effi", guia: "B263421440-1", resultado: "manual_review", accion: "Cliente no localizado", notion: "En reparto", effi: "Cliente no localizado", propuesto: "Reagendar", motivo: "2 intentos fallidos." },
        { runId: 28, fecha: "2026-04-30 14:32", modo: "apply", carrier: "effi", guia: "B263395010-1", resultado: "unchanged", accion: "—", notion: "Por recoger", effi: "Por recoger (INFORMADO)", propuesto: "Por recoger (INFORMADO)", motivo: "Se mantiene." },
        { runId: 27, fecha: "2026-04-30 09:00", modo: "apply", carrier: "effi", guia: "B263380120-1", resultado: "changed", accion: "Entregada", notion: "Por recoger", effi: "Entregada", propuesto: "Entregada", motivo: "Cliente recogió en oficina." },
        { runId: 27, fecha: "2026-04-30 09:00", modo: "apply", carrier: "effi", guia: "B263390041-1", resultado: "changed", accion: "Devuelta", notion: "Por recoger", effi: "Devuelta a origen", propuesto: "Devuelta a origen", motivo: "Sin recolección — devuelta." },
        { runId: 26, fecha: "2026-04-29 18:45", modo: "dry-run", carrier: "effi", guia: "B263378877-1", resultado: "unchanged", accion: "—", notion: "En tránsito", effi: "En Bodega Origen", propuesto: "En Bodega Origen", motivo: "Se mantiene." },
      ],
    },
  },
  // ── Detalle corrida 28 ───────────────────────────────────────────
  runDetail: {
    id: 28,
    eventos: [
      { hora: "14:32:01", tipo: "info", msg: "Inicio de corrida — modo apply" },
      { hora: "14:32:02", tipo: "info", msg: "1,204 guías activas leídas de Notion" },
      { hora: "14:32:03", tipo: "info", msg: "Distribución: Effi 1,089 · Guatex 115" },
      { hora: "14:32:04", tipo: "info", msg: "Iniciando fetch paralelo (8 workers)" },
      { hora: "14:34:21", tipo: "warn", msg: "Effi parse error en 8 guías — guardado HTML crudo" },
      { hora: "14:34:55", tipo: "warn", msg: "Guatex: 115 guías marcadas manual_review (stub)" },
      { hora: "14:35:12", tipo: "info", msg: "Aplicando reglas (10 activas)" },
      { hora: "14:35:38", tipo: "info", msg: "187 cambios detectados en propiedades" },
      { hora: "14:35:42", tipo: "ok", msg: "Notion update batch 1/4 — 50 guías ✓" },
      { hora: "14:35:46", tipo: "ok", msg: "Notion update batch 2/4 — 50 guías ✓" },
      { hora: "14:35:50", tipo: "ok", msg: "Notion update batch 3/4 — 50 guías ✓" },
      { hora: "14:35:48", tipo: "ok", msg: "Notion update batch 4/4 — 37 guías ✓" },
      { hora: "14:35:48", tipo: "ok", msg: "Corrida completada · 3m 47s · summary.md generado" },
    ],
    diff: [
      { guia: "B263378877-1", prop: "estado_tracking", antes: "En tránsito", despues: "En Bodega Origen" },
      { guia: "B263378877-1", prop: "ultima_actualizacion", antes: "2026-04-26", despues: "2026-04-30" },
      { guia: "B263401336-1", prop: "estado_tracking", antes: "En tránsito", despues: "Devuelto a Origen" },
      { guia: "B263400064-1", prop: "estado_tracking", antes: "En reparto", despues: "Daño en bodega" },
      { guia: "B263400064-1", prop: "requiere_atencion", antes: "false", despues: "true" },
      { guia: "B263409347-1", prop: "reprogramaciones", antes: "1", despues: "2" },
    ],
  },
};
