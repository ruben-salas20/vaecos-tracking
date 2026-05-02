# 04. Requerimientos Funcionales

## RF-01 Autenticacion y sesion

- Login con usuario/contrasena.
- Sesion persistente segura.
- Logout.
- Roles minimos: operador, supervisor, admin.

## RF-02 Multiusuario y DB compartida

- Persistencia central de acciones.
- Estado compartido entre usuarios.
- Auditoria por usuario y accion.

## RF-03 Corridas operativas

- Crear corrida en `dry-run` o `apply`.
- Alcance total, por carrier o lista manual.
- Progreso en vivo y eventos.
- Persistencia completa de resultados.

## RF-04 Gestion de excepciones

- Vista `Requiere atencion` con filtros y busqueda.
- Acciones individuales y masivas.
- Notas y estado de resolucion.

## RF-05 Motor de reglas

- CRUD de reglas sin codigo.
- Prioridad ascendente, primera coincidencia gana.
- Activar/desactivar reglas.
- Historial y metricas de acierto.

## RF-06 Trazabilidad por guia

- Timeline por guia.
- Resultado por corrida.
- Estado Notion/Carrier/Propuesto, motivo, errores, notas.
- Re-tracking por guia.

## RF-07 Trazabilidad por cliente

- Vista agregada por cliente (7/30/90 dias).
- KPIs de volumen, cambios, atencion y errores.

## RF-08 Analytics operativo

- Tendencias de procesadas, cambios, atencion y errores.
- Top clientes problematicos.
- Desempeno por carrier.
- Indicadores de por recoger.

## RF-09 Historial de corridas

- Listado de corridas con filtros.
- Detalle por corrida.
- Exportaciones.
- KPIs de eficiencia y estabilidad.

## RF-10 Salud del sistema

- Estado de integraciones.
- Latencias y errores.
- Estado de scheduler y proxima corrida.

## RF-11 Migracion fuera de Notion

- Fase de coexistencia.
- Fase de dependencia invertida.
- Fase de retiro completo.

## RF-12 Scheduler y notificaciones

- Corridas automaticas configurables.
- Notificacion al terminar o fallar.
- Registro del disparador (manual/auto).
