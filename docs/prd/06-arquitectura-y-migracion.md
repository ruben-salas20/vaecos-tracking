# 06. Arquitectura Objetivo y Migracion

## Arquitectura objetivo (alto nivel)

1. **Web App**: UI operativa multiusuario.
2. **Capa aplicacion/API**: auth, reglas, corridas, analytics y trazabilidad.
3. **Runner/Workers**: ejecucion en background.
4. **DB central**: fuente de verdad compartida.
5. **Integraciones externas**: carriers; Notion solo en transicion.

## Principios de arquitectura

- Separar presentacion de logica de negocio.
- Evitar acoplar ejecucion de corridas al hilo principal web.
- Diseñar para auditoria desde el inicio.
- Permitir migracion gradual sin detener operacion.

## Plan de migracion Notion -> DB interna

### M1 Coexistencia controlada

- Mantener continuidad operativa con Notion.
- Escribir datos completos en DB interna.
- Verificar consistencia entre fuentes.

### M2 Inversion de dependencia

- DB interna pasa a ser principal.
- Notion queda como salida auxiliar temporal.

### M3 Retiro

- Remover Notion del flujo core.
- Conservar solo exportes/reportes necesarios.

## Criterio de salida de migracion

- Corridas estables en DB interna.
- Trazabilidad completa sin consultas criticas a Notion.
- Validacion operativa consistente por un periodo definido.
