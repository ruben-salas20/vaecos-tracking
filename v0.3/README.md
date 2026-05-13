# VAECOS v0.3 — LEGACY (solo como librería)

> **Estado**: el **server v0.3 fue retirado** (mayo 2026). v0.4 lo reemplaza completamente como interfaz principal.
>
> Este directorio queda únicamente como **librería** para que v0.4 reutilice tres componentes ya probados:
>
> - `vaecos_v03/storage.py` — `DashboardRepository`: queries de dashboard, búsqueda, attention, analytics, notas, edits.
> - `vaecos_v03/render.py` — generadores SVG (`line_chart`, `stacked_bar_chart`). Migrados verbatim a `v0.4/app/charts.py`; este sigue para retro-compat de tests.
> - `vaecos_v03/__init__.py` — paquete vacío.
>
> Los demás módulos (`app.py`, `config.py`, `rules_ui.py`) ya **no se ejecutan en producción**. Quedan por mantener los tests históricos del DashboardRepository (`v0.2/tests/test_v03_dashboard.py`, ~150 casos validados).

## Qué hacía v0.3 (histórico)

Aplicación web local sobre `http.server` (stdlib). Cubría:
- Dashboard operativo
- Navegación por corridas/guía/cliente
- Disparo de corridas desde la web
- Edición de reglas con auditoría

Todo eso ahora vive en `v0.4/app/` con Flask, autenticación, dark mode, deploy en VPS, y los módulos adicionales (Effi automation, etc.).

## ¿Cómo arranco la app?

NO uses este directorio. La aplicación es ahora:

```powershell
iniciar_v04.bat
# o
python v0.4/server.py
```

URL local: `http://127.0.0.1:8765` · Producción: `https://app.vaecos.com`.
