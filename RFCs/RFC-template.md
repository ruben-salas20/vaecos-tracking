# RFC-XXX: [Título del cambio]

| Campo           | Valor                                      |
|-----------------|--------------------------------------------|
| **RFC**         | RFC-XXX                                    |
| **Estado**      | Borrador                                   |
| **Autor**       | [Nombre]                                   |
| **Fecha**       | YYYY-MM-DD                                 |
| **Versión**     | v0.X (versión del proyecto que se modifica)|

---

## Resumen

<!-- Una sola oración que describa qué cambia y por qué. -->
_Ejemplo: Reactivar el editor de reglas en la interfaz web para que la operadora pueda modificar reglas sin editar la base de datos manualmente._

---

## Motivación

<!-- ¿Qué problema existe hoy? ¿Por qué es necesario este cambio? -->
<!-- Describir el dolor concreto, no la solución. -->

**Problema:**

**Impacto actual:**

---

## Estado actual

<!-- ¿Cómo funciona hoy la parte del sistema que se va a modificar? -->
<!-- Incluir rutas de archivos relevantes. -->

**Archivos involucrados hoy:**

- `v0.X/ruta/al/archivo.py` — descripción breve de su rol actual

**Comportamiento actual:**

---

## Propuesta

<!-- ¿Qué se quiere cambiar? Describir el resultado deseado, no cada paso. -->

---

## Diseño técnico

<!-- Detalle técnico de la implementación propuesta. -->
<!-- Incluir: archivos a crear/modificar, cambios de esquema, nuevas funciones, etc. -->

**Archivos a modificar:**

| Archivo | Cambio |
|---------|--------|
| `ruta/archivo.py` | Descripción del cambio |

**Esquema de datos (si aplica):**

```sql
-- Ejemplo de migración o nueva tabla
```

**Lógica principal:**

```python
# Pseudocódigo o fragmento clave (opcional)
```

---

## Alternativas consideradas

<!-- ¿Qué otras opciones se evaluaron? ¿Por qué se descartaron? -->

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Opción A    | ...               |
| Opción B    | ...               |

---

## Plan de implementación

<!-- Pasos ordenados. Cada paso debe ser accionable e independiente si es posible. -->

- [ ] Paso 1: ...
- [ ] Paso 2: ...
- [ ] Paso 3: ...
- [ ] Paso 4: Pruebas y verificación

---

## Criterios de aceptación

<!-- ¿Cómo saber que el cambio funciona correctamente? Ser específico y verificable. -->

- [ ] ...
- [ ] ...
- [ ] Los tests existentes siguen pasando (`python -m unittest discover -s "v0.2/tests" -v`)
- [ ] No hay regresiones visibles en el dashboard (`python v0.3/server.py --check`)

---

## Impacto y riesgos

<!-- Efectos secundarios, migraciones de datos, cambios incompatibles, riesgos conocidos. -->

**Migraciones necesarias:** Ninguna / [describir si aplica]

**Riesgos:**

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| ...    | Alta/Media/Baja | ...    |

**Compatibilidad:** Este cambio es / no es compatible con la versión anterior porque...

---

## Referencias

<!-- Issues de GitHub, commits relevantes, documentos relacionados, decisiones previas. -->

- `docs/roadmap.md` — Fase X: [nombre de la fase]
- Commit: `abc1234` — [descripción]
- Issue: #XX — [título]

---

---

## Guía de uso de esta plantilla

### Cómo crear un nuevo RFC

1. Copiar este archivo: `cp RFC-template.md RFC-XXX-nombre-del-cambio.md`
2. Reemplazar `XXX` con el número correlativo siguiente (ej: `001`, `002`, …)
3. Completar todas las secciones. Las secciones vacías se pueden omitir si no aplican.
4. Cambiar el estado a `Borrador` mientras se redacta.
5. Compartir con el equipo para revisión antes de implementar.

### Convención de nombres

```
RFC-001-reactivar-editor-reglas.md
RFC-002-integracion-guatex.md
RFC-003-despliegue-vps.md
```

### Estados del RFC

| Estado       | Significado                                                  |
|--------------|--------------------------------------------------------------|
| `Borrador`   | En redacción, aún no revisado                                |
| `En revisión`| Compartido para comentarios                                  |
| `Aceptado`   | Aprobado para implementar                                    |
| `Rechazado`  | No se implementará (con justificación en el documento)       |
| `Implementado`| Completo; el código ya existe en el proyecto                |
