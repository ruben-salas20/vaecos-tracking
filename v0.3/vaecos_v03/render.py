from __future__ import annotations

from html import escape


def layout(title: str, body: str) -> str:
    return f"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 0; background: linear-gradient(180deg, #f3f5fb 0%, #eef2f8 100%); color: #1c2430; }}
    a {{ color: #0a58ca; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .app {{ display: grid; grid-template-columns: 260px minmax(0, 1fr); min-height: 100vh; }}
    .sidebar {{ background: #121826; color: #e6edf7; padding: 24px 18px; }}
    .brand {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: #93a4bd; font-size: .92rem; margin-bottom: 24px; }}
    .nav {{ display:flex; flex-direction:column; gap:8px; }}
    .nav a {{ color: #e6edf7; padding: 10px 12px; border-radius: 10px; }}
    .nav a:hover {{ background: #1f2937; text-decoration: none; }}
    .main {{ padding: 28px; }}
    .hero {{ display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom: 22px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 2rem; }}
    .hero p {{ margin: 0; color: #64748b; max-width: 720px; }}
    .toolbar {{ display:flex; gap:10px; flex-wrap:wrap; }}
    .button, button {{ background: #2563eb; color: white; border: 0; border-radius: 10px; padding: 10px 14px; cursor: pointer; font: inherit; }}
    .button.secondary, button.secondary {{ background: #0f172a; }}
    .button.ghost {{ background: white; color: #1c2430; border: 1px solid #d6dce7; }}
    .cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 20px 0; }}
    .card {{ background: white; border-radius: 14px; padding: 16px; box-shadow: 0 10px 24px rgba(15,23,42,.06); border: 1px solid #e6eaf1; }}
    .card strong {{ font-size: 1.25rem; }}
    .panel {{ background: white; border-radius: 14px; padding: 18px; box-shadow: 0 10px 24px rgba(15,23,42,.06); border: 1px solid #e6eaf1; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 14px; overflow: hidden; box-shadow: 0 10px 24px rgba(15,23,42,.06); border: 1px solid #e6eaf1; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e7eaf0; text-align: left; vertical-align: top; }}
    th {{ background: #f7f9fc; }}
    .muted {{ color: #64748b; }}
    .section {{ margin-top: 28px; }}
    code {{ background: #eef2f8; padding: 2px 6px; border-radius: 6px; }}
    form.inline, .filters {{ display:flex; gap:10px; flex-wrap:wrap; align-items:end; }}
    label {{ display:flex; flex-direction:column; gap:6px; font-size:.92rem; color:#334155; }}
    input[type=text], input[type=number], select, textarea {{ width: 100%; min-width: 180px; border: 1px solid #cfd7e3; border-radius: 10px; padding: 10px 12px; font: inherit; background: white; }}
    textarea {{ min-height: 88px; resize: vertical; }}
    .stack {{ display:flex; flex-direction:column; gap:14px; }}
    .pill {{ display:inline-block; padding: 4px 8px; border-radius: 999px; background:#eef2ff; color:#4338ca; font-size:.82rem; }}
    .alert {{ background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; padding:12px 14px; border-radius:12px; margin-bottom:16px; }}
    .ok {{ background:#ecfdf5; border-color:#a7f3d0; color:#065f46; }}
    .grid-two {{ display:grid; grid-template-columns: 1.2fr .8fr; gap:18px; }}
    @media (max-width: 980px) {{ .app {{ grid-template-columns: 1fr; }} .sidebar {{ padding-bottom: 10px; }} .main {{ padding: 18px; }} .grid-two {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">VAECOS App</div>
      <div class="subtitle">v0.3 local web application</div>
      <nav class="nav">
        <a href="/">Resumen</a>
        <a href="/runs">Corridas</a>
        <a href="/run/new">Nueva corrida</a>
      </nav>
    </aside>
    <main class="main">
      {body}
    </main>
  </div>
</body>
</html>
"""


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def h(text: str) -> str:
    return f"<div class=\"section\"><h2>{escape(text)}</h2></div>"


def p(text: str, muted: bool = False) -> str:
    klass = " class=\"muted\"" if muted else ""
    return f"<p{klass}>{escape(text)}</p>"


def hero(title: str, subtitle: str, actions: str = "") -> str:
    return (
        '<div class="hero">'
        f'<div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>'
        f'<div class="toolbar">{actions}</div>'
        '</div>'
    )


def button(href: str, label: str, variant: str = "") -> str:
    klass = f"button {variant}".strip()
    return f'<a class="{klass}" href="{href}">{escape(label)}</a>'


def card_grid(cards: list[tuple[str, str]]) -> str:
    items = []
    for label, value in cards:
        items.append(
            f'<div class="card"><div class="muted">{escape(label)}</div><div><strong>{escape(value)}</strong></div></div>'
        )
    return f'<div class="cards">{"".join(items)}</div>'


def panel(content: str) -> str:
    return f'<div class="panel">{content}</div>'


def alert(text: str, kind: str = "") -> str:
    klass = f"alert {kind}".strip()
    return f'<div class="{klass}">{escape(text)}</div>'
