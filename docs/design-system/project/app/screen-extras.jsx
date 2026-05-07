// Pantallas adicionales: Historial de corridas, Por recoger detalle,
// Detalle de guía, Detalle de cliente, Progreso de corrida.
const { useState: useStateExtras, useEffect: useEffectExtras } = React;

// ─── /runs — Historial de corridas ───────────────────────────────────
function HistorialCorridas({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const [modo, setModo] = useStateExtras("todos");

  // Generar más historial sintético a partir de recentRuns
  const allRuns = [
    ...D.recentRuns,
    { id: 22, fecha: "2026-04-28 14:30", modo: "apply", total: 1158, changed: 132, attention: 26, errors: 4, dur: "2m 51s" },
    { id: 21, fecha: "2026-04-28 09:00", modo: "apply", total: 1149, changed: 118, attention: 24, errors: 6, dur: "2m 47s" },
    { id: 20, fecha: "2026-04-27 18:45", modo: "dry-run", total: 1141, changed: 109, attention: 22, errors: 3, dur: "2m 44s" },
    { id: 19, fecha: "2026-04-27 14:30", modo: "apply", total: 1132, changed: 97, attention: 21, errors: 5, dur: "2m 39s" },
    { id: 18, fecha: "2026-04-27 09:00", modo: "apply", total: 1125, changed: 88, attention: 19, errors: 4, dur: "2m 36s" },
    { id: 17, fecha: "2026-04-26 18:45", modo: "dry-run", total: 1118, changed: 81, attention: 17, errors: 7, dur: "2m 41s" },
    { id: 16, fecha: "2026-04-26 14:30", modo: "apply", total: 1110, changed: 76, attention: 16, errors: 2, dur: "2m 32s" },
    { id: 15, fecha: "2026-04-26 09:00", modo: "apply", total: 1103, changed: 71, attention: 15, errors: 4, dur: "2m 29s" },
  ];
  const filtered = modo === "todos" ? allRuns : allRuns.filter(r => r.modo === modo);

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Corridas"]}
        title="Historial de corridas"
        sub={`${allRuns.length} corridas almacenadas en SQLite. Datos completos para auditoría y replays.`}
        actions={<>
          <button className="btn">{I.download}<span>Exportar CSV</span></button>
          <button className="btn primary" onClick={()=>onNav("newrun")}>{I.play}<span>Nueva corrida</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi"><div className="kpi-label">Corridas (30d)</div><div className="kpi-value tnum">142</div><div className="kpi-meta"><span>~4.7 / día</span></div></div>
        <div className="kpi"><div className="kpi-label">apply</div><div className="kpi-value tnum">98</div><div className="kpi-meta"><span style={{color:"var(--ok)"}}>69%</span></div></div>
        <div className="kpi"><div className="kpi-label">dry-run</div><div className="kpi-value tnum">44</div><div className="kpi-meta"><span style={{color:"var(--info)"}}>31%</span></div></div>
        <div className="kpi"><div className="kpi-label">Duración promedio</div><div className="kpi-value tnum">3m 12s</div><div className="kpi-meta"><span>último: 3m 47s</span></div></div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="panel-title">Corridas recientes</div>
          <div style={{display:"flex", gap:6}}>
            {[{v:"todos",l:"Todos"},{v:"apply",l:"apply"},{v:"dry-run",l:"dry-run"}].map(o => (
              <button key={o.v}
                className={"chip " + (modo===o.v?"active":"")}
                onClick={()=>setModo(o.v)}>{o.l}</button>
            ))}
          </div>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{width:80}}>Run</th>
              <th>Inicio</th>
              <th>Modo</th>
              <th className="num">Procesadas</th>
              <th className="num">Cambios</th>
              <th className="num">Atención</th>
              <th className="num">Errores</th>
              <th>Duración</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} onClick={()=>onNav("runs")} style={{cursor:"pointer"}}>
                <td><strong className="mono">#{r.id}</strong></td>
                <td className="muted">{r.fecha}</td>
                <td>
                  <Pill kind={r.modo==="apply"?"ok":"info"}>{r.modo}</Pill>
                </td>
                <td className="num tnum">{r.total.toLocaleString()}</td>
                <td className="num tnum">{r.changed}</td>
                <td className="num tnum" style={{color: r.attention > 30 ? "var(--danger)" : "var(--ink)"}}>{r.attention}</td>
                <td className="num tnum" style={{color: r.errors > 5 ? "var(--warn)" : "var(--muted)"}}>{r.errors}</td>
                <td className="mono muted">{r.dur}</td>
                <td style={{textAlign:"right"}}>
                  <span style={{color:"var(--muted)"}}>{I.arrow}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── /analytics/por-recoger — Detalle por recoger ────────────────────
function PorRecoger({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const pr = D.porRecoger;
  const [tab, setTab] = useStateExtras("pending");

  const tabs = [
    { id: "pending", label: "Pendientes", count: pr.pending.length, kind: "warn" },
    { id: "delivered", label: "Entregadas", count: pr.delivered.length, kind: "ok" },
    { id: "returned", label: "Devueltas", count: pr.returned.length, kind: "danger" },
  ];
  const rows = pr[tab];

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Analytics", "Por recoger"]}
        title="Por recoger en oficina"
        sub="Guías que pasaron por el estado 'Por recoger (INFORMADO)' y cómo terminaron."
        actions={<>
          <button className="btn" onClick={()=>onNav("analytics")}>← Volver a Analytics</button>
          <button className="btn">{I.download}<span>Exportar</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi alert">
          <div className="kpi-label">Pendientes — aún por recoger</div>
          <div className="kpi-value tnum">{pr.pending.length}</div>
          <div className="kpi-meta"><span style={{color:"var(--warn)"}}>requieren acción</span></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Entregadas</div>
          <div className="kpi-value tnum" style={{color:"var(--ok)"}}>{pr.delivered.length}</div>
          <div className="kpi-meta"><span>cliente recogió</span></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Devueltas a origen</div>
          <div className="kpi-value tnum" style={{color:"var(--danger)"}}>{pr.returned.length}</div>
          <div className="kpi-meta"><span>sin recolección</span></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Tasa de recolección</div>
          <div className="kpi-value tnum">{Math.round(pr.delivered.length / (pr.delivered.length + pr.returned.length) * 100)}%</div>
          <div className="kpi-meta"><span>histórico 90d</span></div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head" style={{padding:0, borderBottom:"1px solid var(--border)"}}>
          <div style={{display:"flex"}}>
            {tabs.map(t => (
              <button key={t.id} onClick={()=>setTab(t.id)} style={{
                padding:"14px 18px",
                borderBottom: tab===t.id ? "2px solid var(--ink)" : "2px solid transparent",
                color: tab===t.id ? "var(--ink)" : "var(--muted)",
                fontWeight: tab===t.id ? 600 : 500,
                fontSize: 13, background: "none", cursor: "pointer", display:"flex", alignItems:"center", gap:8
              }}>
                {t.label}
                <span className={"pill " + t.kind} style={{padding:"1px 7px", fontSize:10}}>
                  <span className="dot"></span>{t.count}
                </span>
              </button>
            ))}
          </div>
        </div>
        <table className="tbl">
          <thead>
            {tab === "pending" ? (
              <tr><th>Guía</th><th>Cliente</th><th>Carrier</th><th>Estado</th><th>Días</th><th>Acción sugerida</th><th>Run</th></tr>
            ) : (
              <tr><th>Guía</th><th>Cliente</th><th>Carrier</th><th>Estado final</th><th>Fecha</th><th>Run</th></tr>
            )}
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.guia} onClick={()=>onNav("guide:" + r.guia)} style={{cursor:"pointer"}}>
                <td><strong className="mono">{r.guia}</strong></td>
                <td>{r.cliente}</td>
                <td><CarrierBadge name={r.carrier}/></td>
                {tab === "pending" ? <>
                  <td><Pill kind="warn">{r.estado}</Pill></td>
                  <td className="num tnum" style={{color: r.dias > 5 ? "var(--danger)" : "var(--ink)"}}>{r.dias}d</td>
                  <td className="muted" style={{fontSize:12.5}}>{r.accion}</td>
                  <td className="mono muted">#{r.runId}</td>
                </> : <>
                  <td>
                    <Pill kind={tab === "delivered" ? "ok" : "danger"}>{r.estadoFinal}</Pill>
                  </td>
                  <td className="muted">{r.fecha}</td>
                  <td className="mono muted">#{r.runId}</td>
                </>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── /guides/<guia> — Detalle de guía ────────────────────────────────
function GuideDetail({ onNav, guia }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  // Si no hay data específica, usa la primera guía como demo
  const key = D.guideHistory[guia] ? guia : Object.keys(D.guideHistory)[0];
  const g = D.guideHistory[key];

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Guías", key]}
        title={key}
        sub={<>{g.cliente} · <CarrierBadge name={g.carrier}/> · {g.origen} → {g.destino}</>}
        actions={<>
          <button className="btn" onClick={()=>onNav("attention")}>← Volver</button>
          <button className="btn">{I.refresh}<span>Re-tracking</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi"><div className="kpi-label">Días en sistema</div><div className="kpi-value tnum">{g.diasEnSistema}</div><div className="kpi-meta"><span>desde primera corrida</span></div></div>
        <div className="kpi"><div className="kpi-label">Corridas registradas</div><div className="kpi-value tnum">{g.timeline.length}</div><div className="kpi-meta"><span>histórico completo</span></div></div>
        <div className="kpi"><div className="kpi-label">Último resultado</div><div className="kpi-value" style={{fontSize:18}}>{g.ultimoResultado}</div><div className="kpi-meta"><span className="muted">corrida #{g.ultimaCorrida}</span></div></div>
        <div className="kpi"><div className="kpi-label">Estado propuesto</div><div className="kpi-value" style={{fontSize:18, color:"var(--warn)"}}>{g.ultimoEstadoPropuesto}</div><div className="kpi-meta"><span className="muted">aún sin aplicar</span></div></div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="panel-title">Línea de tiempo de la guía</div>
          <span className="muted" style={{fontSize:12}}>Más reciente arriba</span>
        </div>
        <div className="panel-body" style={{padding:0}}>
          <div style={{position:"relative", padding:"16px 18px"}}>
            {g.timeline.map((t, i) => {
              const isLast = i === g.timeline.length - 1;
              const dotColor = t.resultado === "changed" ? "var(--info)"
                : t.resultado === "manual_review" ? "var(--warn)"
                : t.resultado === "unchanged" ? "var(--border-strong)" : "var(--muted)";
              return (
                <div key={i} style={{display:"grid", gridTemplateColumns:"24px 1fr", gap:12, paddingBottom: isLast?0:18}}>
                  <div style={{position:"relative"}}>
                    <div style={{width:10, height:10, borderRadius:"50%", background:dotColor, marginTop:6, marginLeft:7, boxShadow:"0 0 0 3px var(--surface)"}}></div>
                    {!isLast && <div style={{position:"absolute", top:18, left:11.5, width:1, bottom:-18, background:"var(--border)"}}></div>}
                  </div>
                  <div style={{paddingBottom: isLast?0:0}}>
                    <div style={{display:"flex", alignItems:"center", gap:10, flexWrap:"wrap", marginBottom:6}}>
                      <strong style={{fontSize:13}}>Corrida #{t.runId}</strong>
                      <Pill kind={t.modo==="apply"?"ok":"info"}>{t.modo}</Pill>
                      <span className="muted mono" style={{fontSize:11.5}}>{t.fecha}</span>
                      <span style={{flex:1}}></span>
                      <Pill kind={t.resultado==="changed"?"info":t.resultado==="manual_review"?"warn":"neutral"}>{t.resultado}</Pill>
                    </div>
                    <div style={{display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:10, padding:"10px 12px", background:"var(--surface-2)", borderRadius:"var(--r)", marginBottom:6, fontSize:12}}>
                      <div><div className="muted" style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.04em"}}>Notion</div><div style={{fontWeight:500}}>{t.notion}</div></div>
                      <div><div className="muted" style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.04em"}}>Effi</div><div style={{fontWeight:500}}>{t.effi}</div></div>
                      <div><div className="muted" style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.04em"}}>Propuesto</div><div style={{fontWeight:500, color: t.propuesto !== t.notion ? "var(--brand)" : "var(--ink)"}}>{t.propuesto}</div></div>
                    </div>
                    <div style={{fontSize:12.5, color:"var(--ink-2)"}}>{t.motivo}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

// ─── /clients/<cliente> — Detalle de cliente ─────────────────────────
function ClientDetail({ onNav, cliente }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const key = D.clientDetail[cliente] ? cliente : Object.keys(D.clientDetail)[0];
  const c = D.clientDetail[key];
  const s = c.summary;

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Clientes", key]}
        title={key}
        sub={`Historial agregado · últimos 90 días · ${s.uniqueGuides} guías únicas`}
        actions={<>
          <button className="btn" onClick={()=>onNav("analytics")}>← Volver a Analytics</button>
          <button className="btn">{I.download}<span>Exportar</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi"><div className="kpi-label">Guías únicas</div><div className="kpi-value tnum">{s.uniqueGuides}</div><div className="kpi-meta"><span>en ventana 90d</span></div></div>
        <div className="kpi"><div className="kpi-label">Filas totales</div><div className="kpi-value tnum">{s.totalRows}</div><div className="kpi-meta"><span>ratio {(s.totalRows/s.uniqueGuides).toFixed(1)} runs/guía</span></div></div>
        <div className="kpi"><div className="kpi-label">Cambios</div><div className="kpi-value tnum" style={{color:"var(--info)"}}>{s.changed}</div><div className="kpi-meta"><span>{Math.round(s.changed/s.totalRows*100)}% del tráfico</span></div></div>
        <div className="kpi alert"><div className="kpi-label">Atención manual</div><div className="kpi-value tnum">{s.manual}</div><div className="kpi-meta"><span>requirieron operadora</span></div></div>
        <div className="kpi"><div className="kpi-label">Parse errors</div><div className="kpi-value tnum" style={{color: s.parseError > 0 ? "var(--warn)" : "var(--ok)"}}>{s.parseError}</div><div className="kpi-meta"><span>HTML Effi</span></div></div>
        <div className="kpi"><div className="kpi-label">Errores red</div><div className="kpi-value tnum" style={{color: s.error > 0 ? "var(--danger)" : "var(--ok)"}}>{s.error}</div><div className="kpi-meta"><span>timeouts / 5xx</span></div></div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="panel-title">Historial de resultados</div>
          <span className="muted" style={{fontSize:12}}>{c.history.length} eventos · ordenados por fecha desc.</span>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Run</th>
              <th>Fecha</th>
              <th>Guía</th>
              <th>Resultado</th>
              <th>Notion</th>
              <th>Effi</th>
              <th>Propuesto</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {c.history.map((r, i) => (
              <tr key={i} onClick={()=>onNav("guide:" + r.guia)} style={{cursor:"pointer"}}>
                <td className="mono">#{r.runId}</td>
                <td className="muted">{r.fecha.split(" ")[0]}<br/><span className="mono" style={{fontSize:11}}>{r.fecha.split(" ")[1]}</span></td>
                <td><strong className="mono">{r.guia}</strong></td>
                <td><Pill kind={r.resultado==="changed"?"info":r.resultado==="manual_review"?"warn":"neutral"}>{r.resultado}</Pill></td>
                <td className="muted">{r.notion}</td>
                <td className="muted">{r.effi}</td>
                <td style={{fontWeight: r.propuesto !== r.notion ? 500 : 400, color: r.propuesto !== r.notion ? "var(--brand)" : "var(--ink-2)"}}>{r.propuesto}</td>
                <td className="muted" style={{fontSize:12}}>{r.motivo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── /run/progress/<token> — Progreso en vivo ────────────────────────
function RunProgress({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  // Animación: progreso simulado avanzando hasta 78% y eventos apareciendo
  const [pct, setPct] = useStateExtras(0);
  const [step, setStep] = useStateExtras(0);

  const eventos = D.runDetail.eventos.slice(0, 8);

  useEffectExtras(() => {
    const t = setInterval(() => {
      setPct(p => {
        if (p >= 78) return p;
        return Math.min(78, p + (Math.random() * 6 + 2));
      });
      setStep(s => Math.min(eventos.length, s + 1));
    }, 700);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <PageHead
        crumbs={["Acciones", "Nueva corrida", "Progreso"]}
        title="Corrida en progreso"
        sub="Ejecutándose en background. Esta página se actualiza automáticamente."
        actions={<>
          <Pill kind="info">apply</Pill>
          <button className="btn">{I.history}<span>Ver corridas</span></button>
        </>}
      />

      <div className="panel" style={{padding:0, overflow:"hidden"}}>
        <div style={{padding:"24px 22px", borderBottom:"1px solid var(--border)"}}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:14}}>
            <div>
              <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:6}}>
                <div className="spinner"></div>
                <span style={{fontSize:14, fontWeight:600}}>Procesando guías</span>
              </div>
              <div className="muted" style={{fontSize:12.5}}>~{Math.round(1204 * (pct/100))} de 1,204 guías procesadas</div>
            </div>
            <div style={{textAlign:"right"}}>
              <div className="tnum" style={{fontSize:32, fontWeight:600, fontFamily:"var(--font-mono)"}}>{Math.round(pct)}%</div>
              <div className="muted mono" style={{fontSize:11.5}}>~{Math.round((100-pct)*2.4)}s restantes</div>
            </div>
          </div>
          <div style={{height:8, background:"var(--surface-2)", borderRadius:4, overflow:"hidden"}}>
            <div style={{height:"100%", width: pct + "%", background:"var(--brand)", transition:"width 0.6s ease-out"}}></div>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"repeat(4, 1fr)", gap:14, marginTop:18}}>
            <ProgressStat label="Workers activos" value="8" sub="paralelo" />
            <ProgressStat label="Effi consultadas" value={Math.round(1089 * (pct/100))} sub="de 1,089" />
            <ProgressStat label="Cambios detectados" value={Math.round(187 * (pct/100))} sub="dry computed" />
            <ProgressStat label="Errores hasta ahora" value={Math.round(8 * (pct/100))} sub="parse + red" />
          </div>
        </div>

        <div style={{padding:"16px 22px"}}>
          <div style={{fontSize:11, fontWeight:600, color:"var(--muted)", textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:10}}>Eventos en vivo</div>
          <div style={{fontFamily:"var(--font-mono)", fontSize:12.5}}>
            {eventos.slice(0, step).map((e, i) => (
              <div key={i} style={{display:"flex", gap:12, padding:"6px 0", borderBottom: i === step-1 ? "none" : "1px solid var(--border)", animation: "fadeIn 0.3s ease-out"}}>
                <span style={{color:"var(--muted)", minWidth:80}}>{e.hora}</span>
                <span style={{
                  minWidth:46, textAlign:"center",
                  padding:"1px 6px", borderRadius:3, fontSize:10, fontWeight:600,
                  background: e.tipo==="ok"?"var(--ok-soft)":e.tipo==="warn"?"var(--warn-soft)":"var(--surface-2)",
                  color: e.tipo==="ok"?"var(--ok)":e.tipo==="warn"?"var(--warn)":"var(--ink-2)",
                  height:"fit-content"
                }}>{e.tipo.toUpperCase()}</span>
                <span style={{color:"var(--ink-2)"}}>{e.msg}</span>
              </div>
            ))}
            {step < eventos.length && (
              <div style={{display:"flex", gap:12, padding:"6px 0", color:"var(--muted)"}}>
                <span style={{minWidth:80}}>—</span>
                <span style={{minWidth:46}}></span>
                <span style={{display:"flex", alignItems:"center", gap:6}}>
                  <span className="dots-anim"></span> esperando próximo evento…
                </span>
              </div>
            )}
          </div>
        </div>

        <div style={{padding:"14px 22px", background:"var(--surface-2)", borderTop:"1px solid var(--border)", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
          <div className="muted" style={{fontSize:12}}>
            La página se actualiza cada 3s. Si cierras esta vista la corrida sigue en background.
          </div>
          <button className="btn" onClick={()=>onNav("runs")}>Ir a la corrida #{D.latestRun.id}</button>
        </div>
      </div>
    </>
  );
}

function ProgressStat({ label, value, sub }) {
  return (
    <div style={{padding:"10px 12px", background:"var(--surface-2)", borderRadius:"var(--r)"}}>
      <div className="muted" style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.06em", fontWeight:600}}>{label}</div>
      <div className="tnum" style={{fontSize:20, fontWeight:600, marginTop:2}}>{value}</div>
      <div className="muted" style={{fontSize:11}}>{sub}</div>
    </div>
  );
}

Object.assign(window, { HistorialCorridas, PorRecoger, GuideDetail, ClientDetail, RunProgress });
