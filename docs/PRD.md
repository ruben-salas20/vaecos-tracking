# VAECOS Tracking Platform PRD

Version: v1.0  
Fecha: 2026-05-01  
Estado: Borrador base para ejecucion  
Owner: Operacion VAECOS

## 1. Contexto

VAECOS inicio como una automatizacion para sincronizar estados de guias entre transportistas y Notion. El MVP actual evoluciono a:

- Motor operativo `v0.2` con corridas, reglas y trazabilidad.
- Capa web `v0.3` con vistas operativas y analytics.
- Persistencia historica en SQLite.

La evolucion objetivo es pasar de una herramienta local a una plataforma web en nube, multiusuario y siempre activa, eliminando la dependencia de Notion.

## 2. Vision del producto

Construir una plataforma operativa interna de tracking para 4 operadores que permita:

- Ejecutar y monitorear corridas en tiempo real.
- Reducir trabajo manual en deteccion y resolucion de excepciones.
- Tener trazabilidad completa por guia, corrida y cliente.
- Tomar decisiones operativas con analytics accionables.
- Reemplazar completamente Notion cuando el sistema este estable.

## 3. Objetivos

### Objetivos principales

1. Reducir trabajo manual operativo.
2. Eliminar dependencia progresiva de Notion.
3. Asegurar trazabilidad completa y auditable.
4. Consolidar analytics para decisiones operativas.
5. Migrar a aplicacion web cloud always-on.

### Prioridad actual

- Reducir trabajo manual.
- Trazabilidad.
- Analytics.

### No objetivos inmediatos

- SaaS comercial en esta fase.
- Integraciones no criticas antes de estabilizar el core.
- Expansion de carriers sin estabilizar flujo actual.

## 4. Usuarios y roles

### Usuario principal

- Operador(a) de tracking (4 usuarios iniciales).

### Usuarios secundarios (proxima fase)

- Supervisor(a) operativo.
- Admin tecnico/operativo.

### Roles esperados

- Operador.
- Supervisor.
- Admin.

## 5. Problemas a resolver

1. Demasiado trabajo manual para gestionar excepciones.
2. Dependencia operativa de Notion.
3. Falta de plataforma compartida multiusuario.
4. Necesidad de trazabilidad y auditoria robusta.
5. Flujo sin estandar completo de ejecucion-resolucion-mejora.

## 6. Alcance funcional

### Estado actual (MVP)

- Corridas `dry-run/apply`.
- Reglas editables y con historial.
- Historial de corridas/resultados en SQLite.
- Vistas web operativas base.
- Progreso de corrida con auto-refresh.
- Notion aun en el flujo operativo.

### Estado objetivo

- Plataforma web cloud always-on.
- Multiusuario con login.
- Base de datos compartida como fuente de verdad.
- Notion removido del flujo core.

### Modulos objetivo

1. Centro Operativo
2. Requiere Atencion
3. Analytics
4. Por Recoger
5. Historial de Corridas
6. Detalle de Corrida
7. Detalle de Guia
8. Detalle de Cliente
9. Progreso en Vivo
10. Nueva Corrida
11. Motor de Reglas
12. Autenticacion y gestion de usuarios
13. Scheduler y notificaciones
14. Salud del sistema

## 7. Requerimientos funcionales

### RF-01 Autenticacion y sesion

- Login con usuario/contrasena.
- Sesion persistente segura.
- Logout.
- Roles minimos: operador, supervisor, admin.

### RF-02 Multiusuario y DB compartida

- Persistencia central de acciones.
- Estado compartido entre usuarios.
- Auditoria por usuario y accion.

### RF-03 Corridas operativas

- Crear corrida en `dry-run` o `apply`.
- Alcance total, por carrier o lista manual.
- Progreso en vivo con eventos.
- Persistencia completa por corrida.

### RF-04 Gestion de excepciones

- Vista `Requiere atencion` con filtros/busqueda.
- Acciones individuales y masivas.
- Notas y estado de resolucion.

### RF-05 Motor de reglas

- CRUD de reglas sin codigo.
- Prioridad ascendente, primera coincidencia gana.
- Activar/desactivar reglas.
- Historial y metricas de acierto.

### RF-06 Trazabilidad por guia

- Timeline por guia.
- Resultado por corrida.
- Estado Carrier/Propuesto, motivo, errores, notas.
- Re-tracking por guia.

### RF-07 Trazabilidad por cliente

- Vista agregada por cliente (7/30/90 dias).
- KPIs de volumen, cambios, atencion y errores.

### RF-08 Analytics operativo

- Tendencias de procesadas, cambios, atencion y errores.
- Top clientes problematicos.
- Desempeno por carrier.
- Indicadores de por recoger.

### RF-09 Historial de corridas

- Listado de corridas con filtros.
- Detalle por corrida.
- Exportaciones.
- KPIs de eficiencia y estabilidad.

### RF-10 Salud del sistema

- Estado de integraciones.
- Latencias y errores.
- Estado de scheduler y proxima corrida.

### RF-11 Migracion fuera de Notion

- Coexistencia temporal.
- Dependencia invertida hacia DB interna.
- Retiro completo de Notion.

### RF-12 Scheduler y notificaciones

- Corridas automaticas configurables.
- Notificacion al terminar/fallar.
- Registro del disparador (manual/auto).

## 8. Requerimientos no funcionales

### RNF-01 Disponibilidad

- Plataforma activa en nube para operacion continua.
- Recuperacion basica ante fallos de corrida.

### RNF-02 Rendimiento

- Ejecucion paralela configurable.
- UI responsiva con volumen alto (filtros/paginacion).

### RNF-03 Seguridad

- Hash seguro de contrasenas.
- Sesiones seguras.
- Control de acceso por rol.
- Auditoria de acciones criticas.

### RNF-04 Observabilidad

- Logs estructurados por modulo y corrida.
- Metricas tecnicas y operativas.

### RNF-05 Escalabilidad

- Separacion entre web, motor y almacenamiento.
- Preparado para crecimiento de usuarios/carga.

### RNF-06 Calidad operativa

- Trazabilidad completa de cambios.
- Capacidad de reconstruir decisiones por regla y corrida.

## 9. Arquitectura objetivo (alto nivel)

1. Web App: UI operativa multiusuario.
2. Capa aplicacion/API: auth, reglas, corridas, analytics y trazabilidad.
3. Runner/Workers: ejecucion en background.
4. DB central: fuente de verdad compartida.
5. Integraciones externas: carriers; Notion solo en transicion.

## 10. Plan de migracion Notion -> DB interna

### M1 Coexistencia controlada

- Mantener continuidad con Notion.
- Escribir datos completos en DB interna.
- Validar consistencia entre fuentes.

### M2 Inversion de dependencia

- DB interna pasa a ser principal.
- Notion queda como salida auxiliar temporal.

### M3 Retiro

- Remover Notion del flujo core.
- Conservar solo exportes/reportes necesarios.

## 11. Metricas de exito

### Operacion

- Reduccion de intervencion manual.
- Tiempo promedio de resolucion de excepciones.
- Corridas completadas sin error tecnico.

### Calidad de tracking

- Precision de estado propuesto.
- Tasa de parse error por carrier.
- Tasa de error de red.

### Plataforma

- Disponibilidad.
- Latencia de vistas criticas.
- Adopcion por operador/modulo.

### Migracion

- Porcentaje de flujos sin Notion.
- Consistencia de datos migrados.

## 12. Roadmap por fases

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
- Evaluacion de evolucion a SaaS.

## 13. Riesgos y mitigaciones

1. Migracion incompleta -> coexistencia por fases + reconciliacion.
2. Manualidad persistente -> tuning continuo de reglas + monitoreo.
3. Complejidad cloud/seguridad -> auth y auditoria tempranas.
4. Crecimiento sin foco -> gobernanza por roadmap y KPIs.

## 14. Decisiones confirmadas

1. Objetivo: plataforma operativa interna formal.
2. Prioridad: manualidad, trazabilidad y analytics.
3. Notion sera reemplazado completamente.
4. Producto en nube, siempre activo y multiusuario.
5. Potencial SaaS futuro, no objetivo inmediato.

## 15. Preguntas abiertas (v1.1)

1. Definicion final de roles/permisos por accion critica.
2. Canal oficial de notificaciones (email/webhook/otro).
3. Politica de scheduler (frecuencia, ventanas, reintentos).
4. SLA operativos (disponibilidad y tiempos maximos).
5. Definicion formal de guia resuelta y flujo de cierre.
