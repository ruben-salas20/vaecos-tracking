# Guía de instalación y uso para operadora

Esta guía está pensada para usar VAECOS sin necesidad de conocimientos técnicos.

## Qué necesitas

1. Tener instalado `Python 3.12` o superior.
2. Tener la carpeta del proyecto descomprimida.
3. Tener el archivo `.env` configurado.
4. Tener conexión a internet.

## Versión recomendada

Usa siempre la release más reciente.

Actualmente la versión correcta es:

- `v0.3.2`

## Primera instalación

1. Descarga el archivo `.zip` de la versión más reciente.
2. Descomprímelo en una carpeta fácil de ubicar, por ejemplo:

```text
C:\Users\TuUsuario\Documents\VAECOS\
```

3. Verifica que dentro de la carpeta estén estos archivos principales:

- `iniciar.bat`
- `actualizar.bat`
- `.env.example`
- `v0.2/`
- `v0.3/`

4. Crea o pega el archivo `.env` en la raíz del proyecto.

## Configuración del `.env`

El archivo `.env` debe contener al menos esto:

```env
NOTION_API_KEY=
NOTION_DATA_SOURCE_ID=
NOTION_VERSION=2025-09-03
NOTION_QUERY_KIND=auto
EFFI_TIMEOUT_SECONDS=20
V02_REPORTS_DIR=v0.2/reports
V02_SAVE_RAW_HTML=false
V02_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db
V02_UPDATE_REPO=ruben-salas20/vaecos-tracking
V02_UPDATE_GITHUB_TOKEN=
```

Notas:

1. `NOTION_API_KEY` y `NOTION_DATA_SOURCE_ID` son obligatorios.
2. Si el repositorio de GitHub es privado, `V02_UPDATE_GITHUB_TOKEN` también debe estar configurado para poder actualizar.

## Cómo iniciar la app

Haz doble clic en:

```text
iniciar.bat
```

Después abre en el navegador:

```text
http://127.0.0.1:8765
```

## Qué pasa en el primer arranque

La app crea automáticamente lo necesario si aún no existe:

- carpeta `v0.2/data/`
- base de datos SQLite
- esquema interno
- reglas por defecto

No necesitas crear nada manualmente.

## Uso diario recomendado

### Ver información

En la web puedes revisar:

- `Resumen`
- `Requiere atención`
- `Analytics`
- `Corridas`
- `Reglas`

### Ejecutar una corrida

1. Entra a `Nueva corrida`
2. Elige una opción:
   - dejar vacío el campo de guías para procesar todas las activas
   - escribir una o varias guías específicas para revisar casos puntuales
3. Elige el modo:
   - `dry-run` para revisar sin actualizar Notion
   - `apply` para aplicar cambios reales

### Recomendación importante

Siempre usar primero:

- `dry-run`

Y solo después:

- `apply`

## Reportes

Cada corrida genera automáticamente:

- `summary.md`
- `results.csv`
- `summary.pdf`

Se guardan en:

```text
v0.2/reports/
```

## Cómo actualizar la aplicación

Haz doble clic en:

```text
actualizar.bat
```

Ese script:

1. revisa si hay una nueva versión
2. descarga la actualización
3. la aplica
4. conserva:
   - `.env`
   - la base de datos
   - los reportes

## Si algo falla

### La web no abre

1. Verifica que la ventana de consola siga abierta.
2. Revisa que el navegador esté entrando a:

```text
http://127.0.0.1:8765
```

### Error de Notion

Revisa:

1. que `NOTION_API_KEY` esté correcta
2. que `NOTION_DATA_SOURCE_ID` esté correcto
3. que la integración tenga acceso a la base de Notion

### No deja actualizar

Si el repo es privado, revisa:

1. que `V02_UPDATE_REPO` esté correcto
2. que `V02_UPDATE_GITHUB_TOKEN` esté configurado

### Effi cambia o no responde bien

Eso normalmente lo debe revisar soporte técnico. No hace falta que la operadora toque archivos internos.

## Qué no debe hacer la operadora

1. No borrar la carpeta `v0.2/data/`
2. No borrar el archivo `.env`
3. No modificar archivos Python
4. No ejecutar `apply` sin revisar primero el `dry-run`

## Resumen rápido

Para trabajar normalmente:

1. Abrir `iniciar.bat`
2. Entrar a la web
3. Ejecutar `dry-run`
4. Revisar resultados
5. Ejecutar `apply` si todo está correcto

Para actualizar:

1. Abrir `actualizar.bat`
