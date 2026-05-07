// Layout shell — sidebar + main
const { useState } = React;

function Sidebar({ current, onNav }) {
  const I = window.VAECOS_ICONS;
  const items = [
    { group: "Operación", entries: [
      { id: "centro", label: "Centro Operativo", icon: I.home },
      { id: "attention", label: "Requiere atención", icon: I.bell, badge: 42 },
    ]},
    { group: "Inteligencia", entries: [
      { id: "analytics", label: "Analytics", icon: I.chart },
      { id: "porrecoger", label: "Por recoger", icon: I.bell },
      { id: "history", label: "Historial corridas", icon: I.history },
      { id: "runs", label: "Detalle de corrida", icon: I.history },
    ]},
    { group: "Vistas detalle", entries: [
      { id: "guide", label: "Guía individual", icon: I.cart },
      { id: "client", label: "Cliente", icon: I.home },
      { id: "progress", label: "Progreso en vivo", icon: I.refresh },
    ]},
    { group: "Acciones", entries: [
      { id: "newrun", label: "Nueva corrida", icon: I.play },
      { id: "rules", label: "Reglas", icon: I.rules },
    ]},
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          {React.cloneElement(I.cart, { strokeWidth: 2.4 })}
        </div>
        <div>
          <div className="brand-name">VAECOS</div>
          <div className="brand-sub">Tracking · v0.3</div>
        </div>
      </div>
      <div className="env-pill">
        <span className="env-dot"></span>
        <span>Notion · sync ok</span>
        <span style={{marginLeft:"auto", fontFamily:"var(--font-mono)"}}>2m</span>
      </div>
      <nav className="nav">
        {items.map((g, gi) => (
          <div className="nav-group" key={gi}>
            <div className="nav-label">{g.group}</div>
            {g.entries.map(it => (
              <div
                key={it.id}
                className={"nav-item" + (current === it.id ? " active" : "")}
                onClick={() => onNav(it.id)}
              >
                {it.icon}
                <span>{it.label}</span>
                {it.badge && <span className="nav-badge">{it.badge}</span>}
              </div>
            ))}
          </div>
        ))}
      </nav>
      <div className="user-card">
        <div className="user-avatar">RS</div>
        <div className="user-info">
          <div className="user-name">Rubén Salas</div>
          <div className="user-meta">operadora</div>
        </div>
      </div>
    </aside>
  );
}

function PageHead({ crumbs, title, sub, actions }) {
  return (
    <div className="page-head">
      <div className="page-title-block">
        {crumbs && (
          <div className="crumbs">
            {crumbs.map((c, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span className="sep">/</span>}
                <span>{c}</span>
              </React.Fragment>
            ))}
          </div>
        )}
        <div className="page-title">{title}</div>
        {sub && <div className="page-sub">{sub}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

function Pill({ kind, children }) {
  return <span className={"pill " + (kind || "neutral")}><span className="dot"></span>{children}</span>;
}

function CarrierBadge({ name }) {
  const n = (name || "effi").toLowerCase();
  return (
    <span className="carrier">
      <span className={"carrier-mark " + n}>{n[0].toUpperCase()}</span>
      <span>{n}</span>
    </span>
  );
}

function Sparkline({ values, color = "currentColor", w = 60, h = 22 }) {
  if (!values || values.length === 0) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

Object.assign(window, { Sidebar, PageHead, Pill, CarrierBadge, Sparkline });
