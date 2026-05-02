# 07. Metricas, Roadmap y Riesgos

## Metricas de exito

### Operacion

- Reduccion de intervencion manual.
- Tiempo promedio de resolucion de excepciones.
- Porcentaje de corridas completadas sin error tecnico.

### Calidad de tracking

- Precision de estado propuesto.
- Tasa de parse error por carrier.
- Tasa de error de red.

### Plataforma

- Disponibilidad.
- Latencia de vistas criticas.
- Adopcion por operador y modulo.

### Migracion

- Porcentaje de flujos sin Notion.
- Consistencia historica de datos migrados.

## Roadmap por fases

### Fase 1 Consolidacion web operativa

- Completar vistas clave del diseno objetivo.
- Mejorar filtros, busqueda, exportes y acciones operativas.
- Reforzar auditoria basica.

### Fase 2 Plataforma cloud multiusuario

- Login, sesiones y roles.
- DB compartida central.
- Deploy cloud always-on.
- Scheduler basico y notificaciones.

### Fase 3 Desacople de Notion

- DB interna como fuente principal.
- Validacion de consistencia.
- Retiro de dependencia operativa de Notion.

### Fase 4 Optimizacion y expansion

- Hardening de performance y observabilidad.
- Mejora continua de reglas y calidad.
- Evaluacion de evolucion a modelo SaaS.

## Riesgos y mitigaciones

1. **Migracion incompleta**: coexistencia y reconciliacion por fases.
2. **Persistencia de trabajo manual**: tuning continuo de reglas y monitoreo.
3. **Complejidad cloud + seguridad**: auth/roles temprano y auditoria obligatoria.
4. **Crecimiento sin foco**: gobernanza por roadmap y KPIs.
