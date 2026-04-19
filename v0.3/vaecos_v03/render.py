from __future__ import annotations

from html import escape


def layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} — VAECOS</title>
  <style>
    :root {{
      --bg:            #f0f2f8;
      --surface:       #ffffff;
      --border:        #e2e8f0;
      --text:          #1e293b;
      --muted:         #64748b;
      --primary:       #2563eb;
      --primary-dark:  #1d4ed8;
      --sidebar-bg:    #0f172a;
      --sidebar-text:  #e2e8f0;
      --sidebar-muted: #94a3b8;
      --shadow-sm:     0 1px 3px rgba(15,23,42,.08), 0 0 0 1px rgba(15,23,42,.04);
      --shadow:        0 4px 16px rgba(15,23,42,.08), 0 0 0 1px rgba(15,23,42,.04);
      --radius:        12px;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Inter, "Segoe UI", system-ui, Arial, sans-serif;
      font-size: 14px; line-height: 1.55;
      background: var(--bg); color: var(--text);
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--primary); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* ── Layout ───────────────────────────────────────── */
    .app {{ display: grid; grid-template-columns: 232px minmax(0,1fr); min-height: 100vh; }}

    /* ── Sidebar ──────────────────────────────────────── */
    .sidebar {{
      background: var(--sidebar-bg); color: var(--sidebar-text);
      display: flex; flex-direction: column;
      position: sticky; top: 0; height: 100vh; overflow-y: auto;
    }}
    .sidebar-brand {{
      padding: 22px 18px 18px;
      border-bottom: 1px solid rgba(255,255,255,.07);
    }}
    .brand {{ font-size: 1rem; font-weight: 700; letter-spacing: -.01em; color: #fff; }}
    .brand-sub {{ color: var(--sidebar-muted); font-size: .75rem; margin-top: 3px; }}
    .sidebar-nav {{ padding: 14px 10px; flex: 1; display: flex; flex-direction: column; gap: 18px; }}
    .nav-group {{ display: flex; flex-direction: column; gap: 2px; }}
    .nav-label {{
      color: var(--sidebar-muted); font-size: .68rem; font-weight: 700;
      letter-spacing: .1em; text-transform: uppercase;
      padding: 0 10px 6px;
    }}
    .nav a {{
      color: var(--sidebar-text); padding: 8px 12px; border-radius: 8px;
      font-size: .85rem; display: block; transition: background .12s, color .12s;
    }}
    .nav a:hover {{ background: rgba(255,255,255,.07); text-decoration: none; color: #fff; }}
    .nav a.nav-active {{ background: rgba(255,255,255,.11); color: #fff; font-weight: 600; }}
    .nav-primary {{ color: #93c5fd !important; }}
    .nav-primary.nav-active {{ color: #fff !important; background: rgba(59,130,246,.25) !important; }}

    /* ── Main content ─────────────────────────────────── */
    .main {{ padding: 28px 32px; max-width: 1400px; }}

    /* ── Hero ─────────────────────────────────────────── */
    .hero {{
      display: flex; align-items: flex-start;
      justify-content: space-between; gap: 24px; margin-bottom: 24px;
    }}
    .hero-text h1 {{
      font-size: 1.55rem; font-weight: 700;
      letter-spacing: -.025em; color: var(--text); margin-bottom: 4px;
    }}
    .hero-text p {{ color: var(--muted); font-size: .875rem; max-width: 580px; }}
    .toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-start; padding-top: 4px; }}

    /* ── Buttons ──────────────────────────────────────── */
    .button, button {{
      display: inline-flex; align-items: center; gap: 6px;
      background: var(--primary); color: white; border: none;
      border-radius: 8px; padding: 8px 14px; cursor: pointer;
      font: inherit; font-size: .85rem; font-weight: 500;
      text-decoration: none; white-space: nowrap;
      transition: background .13s, box-shadow .13s;
    }}
    .button:hover, button:hover {{ background: var(--primary-dark); text-decoration: none; color: white; }}
    .button.ghost, button.ghost {{
      background: var(--surface); color: var(--text);
      border: 1px solid var(--border); box-shadow: var(--shadow-sm);
    }}
    .button.ghost:hover {{ background: #f8fafc; color: var(--text); }}
    .button.secondary {{ background: #1e293b; }}
    .button.secondary:hover {{ background: #0f172a; }}

    /* ── Cards ────────────────────────────────────────── */
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px,1fr)); gap: 12px; margin: 20px 0; }}
    .card {{
      background: var(--surface); border-radius: var(--radius);
      padding: 16px 18px; box-shadow: var(--shadow-sm); border: 1px solid var(--border);
    }}
    .card-label {{
      color: var(--muted); font-size: .72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px;
    }}
    .card-value {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -.03em; line-height: 1; }}
    .card.danger {{ border-color: #fca5a5; background: linear-gradient(135deg,#fff5f5 0%,#fff 55%); }}
    .card.danger .card-value {{ color: #dc2626; }}
    .card.ok    {{ border-color: #86efac; background: linear-gradient(135deg,#f0fdf4 0%,#fff 55%); }}
    .card.ok    .card-value {{ color: #16a34a; }}
    .card.warn  {{ border-color: #fde68a; background: linear-gradient(135deg,#fffbeb 0%,#fff 55%); }}
    .card.warn  .card-value {{ color: #d97706; }}
    .card.info  {{ border-color: #bfdbfe; background: linear-gradient(135deg,#eff6ff 0%,#fff 55%); }}
    .card.info  .card-value {{ color: #2563eb; }}

    /* ── Panel ────────────────────────────────────────── */
    .panel {{
      background: var(--surface); border-radius: var(--radius);
      padding: 18px; box-shadow: var(--shadow-sm); border: 1px solid var(--border);
    }}

    /* ── Section headers ──────────────────────────────── */
    .section {{ margin: 26px 0 12px; }}
    .section h2 {{
      font-size: .95rem; font-weight: 700; color: var(--text);
      display: flex; align-items: center; gap: 10px;
    }}
    .section h2::before {{
      content: ''; display: block; width: 3px; height: 16px;
      background: var(--primary); border-radius: 2px; flex-shrink: 0;
    }}

    /* ── Tables ───────────────────────────────────────── */
    .table-wrap {{
      overflow-x: auto; border-radius: var(--radius);
      box-shadow: var(--shadow-sm); border: 1px solid var(--border); margin-bottom: 4px;
    }}
    table {{ border-collapse: collapse; width: 100%; background: var(--surface); font-size: .84rem; }}
    th {{
      background: #f8fafc; color: var(--muted);
      font-size: .72rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .05em; padding: 10px 14px;
      border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap;
    }}
    td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    tbody tr:hover td {{ background: #f8faff; transition: background .1s; }}
    .cell-trunc {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

    /* ── Alerts ───────────────────────────────────────── */
    .alert {{
      padding: 11px 16px; border-radius: 10px; font-size: .86rem;
      margin-bottom: 16px; border: 1px solid;
      background: #fff7ed; border-color: #fed7aa; color: #9a3412;
    }}
    .alert.ok   {{ background: #f0fdf4; border-color: #86efac; color: #166534; }}
    .alert.info {{ background: #eff6ff; border-color: #bfdbfe; color: #1e40af; }}

    /* ── Pills ────────────────────────────────────────── */
    .pill {{
      display: inline-flex; align-items: center; padding: 2px 9px;
      border-radius: 999px; font-size: .75rem; font-weight: 600; white-space: nowrap;
      background: #eef2ff; color: #4338ca;
    }}
    .pill-changed  {{ background: #dbeafe; color: #1d4ed8; }}
    .pill-unchanged {{ background: #f1f5f9; color: #475569; }}
    .pill-manual   {{ background: #fef9c3; color: #92400e; }}
    .pill-parse    {{ background: #ffedd5; color: #9a3412; }}
    .pill-error    {{ background: #fee2e2; color: #991b1b; }}
    .pill-apply    {{ background: #dcfce7; color: #166534; }}
    .pill-dry      {{ background: #f1f5f9; color: #475569; }}

    /* ── Forms ────────────────────────────────────────── */
    .filters {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; }}
    label {{ display: flex; flex-direction: column; gap: 5px; font-size: .8rem; font-weight: 600; color: #475569; }}
    input[type=text], input[type=number], select, textarea {{
      border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px;
      font: inherit; font-size: .875rem; background: var(--surface); color: var(--text);
      outline: none; transition: border-color .15s, box-shadow .15s;
      min-width: 160px; width: 100%;
    }}
    input:focus, select:focus, textarea:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(37,99,235,.1);
    }}
    textarea {{ min-height: 80px; resize: vertical; }}
    .stack {{ display: flex; flex-direction: column; gap: 14px; }}

    /* ── Misc ─────────────────────────────────────────── */
    .muted {{ color: var(--muted); }}
    code {{ background: #eef2f8; padding: 2px 6px; border-radius: 5px; font-size: .82em; }}
    .sep {{ height: 1px; background: var(--border); margin: 24px 0; }}

    /* ── Responsive ───────────────────────────────────── */
    @media (max-width: 860px) {{
      .app {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; height: auto; }}
      .sidebar-nav {{ flex-direction: row; flex-wrap: wrap; gap: 6px; padding: 10px; }}
      .nav-label {{ display: none; }}
      .nav-group {{ flex-direction: row; }}
      .nav a {{ padding: 6px 10px; font-size: .8rem; }}
      .main {{ padding: 16px; }}
      .hero {{ flex-direction: column; gap: 12px; }}
      .toolbar {{ padding-top: 0; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand">VAECOS</div>
        <div class="brand-sub">Seguimiento de guias</div>
      </div>
      <div class="sidebar-nav">
        <div class="nav-group">
          <div class="nav-label">Operaciones</div>
          <nav class="nav">
            <a class="nav-primary" href="/attention">Requiere atencion</a>
            <a href="/">Resumen</a>
          </nav>
        </div>
        <div class="nav-group">
          <div class="nav-label">Historial</div>
          <nav class="nav">
            <a href="/runs">Corridas</a>
          </nav>
        </div>
        <div class="nav-group">
          <div class="nav-label">Acciones</div>
          <nav class="nav">
            <a href="/run/new">Nueva corrida</a>
          </nav>
        </div>
        <div class="nav-group">
          <div class="nav-label">Configuracion</div>
          <nav class="nav">
            <a href="/rules">Reglas de decision</a>
          </nav>
        </div>
      </div>
    </aside>
    <main class="main">
      {body}
    </main>
  </div>
  <script>
    var path = location.pathname;
    document.querySelectorAll('.nav a').forEach(function(a) {{
      var href = a.getAttribute('href');
      var active = false;
      if (href === '/')          {{ active = (path === '/'); }}
      else if (href === '/runs') {{ active = (path === '/runs' || path.startsWith('/runs/')); }}
      else if (href === '/run/new') {{ active = path.startsWith('/run/'); }}
      else if (href === '/rules') {{ active = (path === '/rules' || path.startsWith('/rules/')); }}
      else                       {{ active = (path === href); }}
      if (active) a.classList.add('nav-active');
    }});
  </script>
</body>
</html>
"""


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = [
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    ]
    return (
        '<div class="table-wrap">'
        f"<table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def h(text: str) -> str:
    return f'<div class="section"><h2>{escape(text)}</h2></div>'


def p(text: str, muted: bool = False) -> str:
    klass = ' class="muted"' if muted else ""
    return f"<p{klass}>{escape(text)}</p>"


def hero(title: str, subtitle: str, actions: str = "") -> str:
    return (
        '<div class="hero">'
        f'<div class="hero-text"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>'
        f'<div class="toolbar">{actions}</div>'
        "</div>"
    )


def button(href: str, label: str, variant: str = "") -> str:
    klass = f"button {variant}".strip()
    return f'<a class="{klass}" href="{href}">{escape(label)}</a>'


def card_grid(cards: list[tuple]) -> str:
    items = []
    for card in cards:
        label, value = card[0], card[1]
        variant = card[2] if len(card) > 2 else ""
        klass = f"card {variant}".strip() if variant else "card"
        items.append(
            f'<div class="{klass}">'
            f'<div class="card-label">{escape(label)}</div>'
            f'<div class="card-value">{escape(str(value))}</div>'
            "</div>"
        )
    return f'<div class="cards">{"".join(items)}</div>'


def panel(content: str) -> str:
    return f'<div class="panel">{content}</div>'


def alert(text: str, kind: str = "") -> str:
    klass = f"alert {kind}".strip() if kind else "alert"
    return f'<div class="{klass}">{escape(text)}</div>'


def result_pill(resultado: str) -> str:
    _classes = {
        "changed":       "pill pill-changed",
        "unchanged":     "pill pill-unchanged",
        "manual_review": "pill pill-manual",
        "parse_error":   "pill pill-parse",
        "error":         "pill pill-error",
    }
    klass = _classes.get(resultado, "pill")
    return f'<span class="{klass}">{escape(resultado)}</span>'


def mode_badge(mode: str) -> str:
    if mode == "apply":
        return '<span class="pill pill-apply">apply</span>'
    return '<span class="pill pill-dry">dry-run</span>'


def rule_enabled_pill(enabled: bool) -> str:
    if enabled:
        return '<span class="pill pill-apply">activa</span>'
    return '<span class="pill pill-unchanged">inactiva</span>'
