# VAECOS v0.3

`v0.3` es la siguiente fase del proyecto: una aplicacion web local construida sobre la SQLite que mantiene `v0.2`.

## Objetivo

- visualizar corridas sin leer archivos manualmente
- navegar resultados por corrida
- revisar historial por guia
- ejecutar corridas desde una interfaz web
- aprovechar SQLite como fuente operativa secundaria

## Requisitos

- Python 3.12+
- una base SQLite existente de `v0.2`

No requiere instalar paquetes externos.

## Variables de entorno

`v0.3` usa por defecto la base de `v0.2`:

```env
V03_SQLITE_DB_PATH=v0.2/data/vaecos_tracking.db
V03_HOST=127.0.0.1
V03_PORT=8765
```

Si `V03_SQLITE_DB_PATH` no existe, intenta `V02_SQLITE_DB_PATH` y luego `v0.2/data/vaecos_tracking.db`.

## Uso

Levantar dashboard:

```powershell
python v0.3/server.py
```

Puerto o host personalizados:

```powershell
python v0.3/server.py --host 0.0.0.0 --port 9000
```

Verificacion rapida sin levantar servidor:

```powershell
python v0.3/server.py --check
```

## Vistas disponibles

- `/` resumen de la ultima corrida
- `/runs` listado de corridas
- `/run/new` formulario para ejecutar corridas desde web
- `/runs/<id>` detalle de una corrida
- `/guides/<guia>` historial de una guia

## Relacion con v0.2

- `v0.2` sigue siendo quien ejecuta corridas y escribe a SQLite
- `v0.3` usa la logica de `v0.2` para ejecutar corridas desde web y luego presenta resultados leyendo SQLite
