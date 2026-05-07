// Pantalla: Detalle de corrida + Nueva corrida + Reglas
const { useState: useStateDetalle } = React;

function DetalleCorrida({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const r = D.latestRun;
  const det = D.runDetail;
  const [tab, setTab] = useStateDetalle("eventos");

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Corridas", `#${r.id}`]}
        title={`Corrida #${r.id}`}
        sub={`Ejecutada ${r.timestamp} · ${r.duration} · disparada por ${r.triggeredBy}`}
        actions={<>
          <Pill kind="ok">apply</Pill>
          <button className="btn">{I.download}<span>summary.md</span></button>
          <button className="btn">{I.refresh}<span>Re-ejecutar</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi"><div className="kpi-label">Procesadas</div><div className="kpi-value tnum">{r.total.toLocaleString()}</div><div className="kpi-meta"><span>Effi 1,089 · Guatex 115</span></div></div>
        <div className="kpi"><div className="kpi-label">Cambios</div><div className="kpi-value tnum" style={{color:"var(--ok)"}}>{r.changed}</div><div className="kpi-meta"><span>Aplicados a Notion</span></div></div>
        <div className="kpi alert"><div className="kpi-label">Atención</div><div className="kpi-value tnum">{r.manual}</div><div className="kpi-meta"><span>Marcadas por reglas</span></div></div>
        <div className="kpi"><div className="kpi-label">Errores</div><div className="kpi-value tnum" style={{color:"var(--warn)"}}>{r.parseError + r.error}</div><div className="kpi-meta"><span>{r.parseError} parse · {r.error} red</span></div></div>
      </div>

      <div className="panel">
        <div className="panel-head" style={{padding:0, borderBottom:"1px solid var(--border)"}}>
          <div style={{display:"flex"}}>
            {[
              {id:"eventos", label:"Eventos", count: det.eventos.length},
              {id:"diff", label:"Cambios en Notion", count: det.diff.length},
              {id:"errores", label:"Errores", count: 8},
              {id:"summary", label:"summary.md"}
            ].map(t => (
              <button
                key={t.id}
                onClick={()=>setTab(t.id)}
                style={{
                  padding:"14px 18px",
                  borderBottom: tab===t.id ? "2px solid var(--ink)" : "2px solid transparent",
                  color: tab===t.id ? "var(--ink)" : "var(--muted)",
                  fontWeight: tab===t.id ? 600 : 500,
                  fontSize:13,
                  background:"none",
                  cursor:"pointer"
                }}
              >
                {t.label}{t.count != null && <span className="mono" style={{marginLeft:6, fontSize:11, color:"var(--muted)"}}>{t.count}</span>}
              </button>
            ))}
          </div>
        </div>
        <div className="panel-body">
          {tab === "eventos" && (
            <div style={{fontFamily:"var(--font-mono)", fontSize:12.5}}>
              {det.eventos.map((e,i) => (
                <div key={i} style={{display:"flex", gap:12, padding:"6px 0", borderBottom:"1px solid var(--border)"}}>
                  <span style={{color:"var(--muted)", minWidth:80}}>{e.hora}</span>
                  <span style={{
                    minWidth:46, textAlign:"center",
                    padding:"1px 6px", borderRadius:3, fontSize:10, fontWeight:600,
                    background: e.tipo==="ok"?"var(--ok-soft)":e.tipo==="warn"?"var(--warn-soft)":"var(--surface-2)",
                    color: e.tipo==="ok"?"var(--ok)":e.tipo==="warn"?"var(--warn)":"var(--ink-2)",
                    height: "fit-content"
                  }}>{e.tipo.toUpperCase()}</span>
                  <span style={{color:"var(--ink-2)"}}>{e.msg}</span>
                </div>
              ))}
            </div>
          )}
          {tab === "diff" && (
            <table className="tbl" style={{margin:"-16px -18px", width:"calc(100% + 36px)"}}>
              <thead><tr><th>Guía</th><th>Propiedad</th><th>Antes</th><th></th><th>Después</th></tr></thead>
              <tbody>
                {det.diff.map((d,i) => (
                  <tr key={i}>
                    <td className="mono">{d.guia}</td>
                    <td className="mono" style={{color:"var(--muted)"}}>{d.prop}</td>
                    <td><span style={{textDecoration:"line-through", color:"var(--muted)"}}>{d.antes}</span></td>
                    <td>{I.arrow}</td>
                    <td><span style={{color:"var(--ok)", fontWeight:500}}>{d.despues}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {tab === "errores" && (
            <div className="empty">8 guías con parse_error · 35 con error de red. <a href="#" style={{color:"var(--brand)"}}>Ver detalle →</a></div>
          )}
          {tab === "summary" && (
            <pre style={{background:"var(--surface-2)", padding:"14px 16px", borderRadius:"var(--r)", fontSize:12, fontFamily:"var(--font-mono)", color:"var(--ink-2)", overflow:"auto", margin:0}}>
{`# Corrida #${r.id} — ${r.timestamp}
modo: apply
duración: ${r.duration}
total: ${r.total}
- Effi: 1,089 procesadas
- Guatex: 115 (stub → manual_review)
cambios aplicados: ${r.changed}
atención: ${r.manual}
errores: parse=${r.parseError} red=${r.error}

## Reglas más activadas
- Default → unchanged: 932
- Entregada → cerrar: 412
- Devuelto → Atención: 47
...`}
            </pre>
          )}
        </div>
      </div>
    </>
  );
}

function NuevaCorrida({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const [mode, setMode] = useStateDetalle("dry-run");
  const [scope, setScope] = useStateDetalle("todas");
  const [carrier, setCarrier] = useStateDetalle("auto");

  return (
    <>
      <PageHead
        crumbs={["Acciones", "Nueva corrida"]}
        title="Nueva corrida"
        sub="Dispara un proceso de tracking en background. La página de progreso se abre al confirmar."
      />

      <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap:16}}>
        <div className="panel">
          <div className="panel-body" style={{display:"flex", flexDirection:"column", gap:22}}>
            <div className="fieldgroup">
              <div>
                <label className="field-label">Modo de ejecución</label>
                <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
                  <ModeCard active={mode==="dry-run"} onClick={()=>setMode("dry-run")} title="Dry-run" desc="Calcula cambios pero no escribe en Notion. Recomendado primero." pill="recomendado" pillKind="info"/>
                  <ModeCard active={mode==="apply"} onClick={()=>setMode("apply")} title="Apply" desc="Aplica cambios reales a propiedades de Notion." pill="escribe" pillKind="danger"/>
                </div>
              </div>

              <div>
                <label className="field-label">Alcance</label>
                <div style={{display:"flex", gap:8, flexWrap:"wrap"}}>
                  <Radio label="Todas las guías activas" sub="~1,200 guías" v="todas" cur={scope} on={setScope}/>
                  <Radio label="Solo carrier específico" sub="filtra por transportista" v="carrier" cur={scope} on={setScope}/>
                  <Radio label="Lista manual" sub="pega IDs de guías" v="manual" cur={scope} on={setScope}/>
                </div>
              </div>

              {scope === "carrier" && (
                <div>
                  <label className="field-label">Transportista</label>
                  <select className="input" value={carrier} onChange={e=>setCarrier(e.target.value)}>
                    <option value="auto">auto (todos)</option>
                    <option value="effi">Effi · 1,089 guías</option>
                    <option value="guatex">Guatex · 115 guías (stub)</option>
                  </select>
                </div>
              )}

              {scope === "manual" && (
                <div>
                  <label className="field-label">Guías a procesar</label>
                  <textarea className="input" rows="4" placeholder="B263378877-1, B263401336-1, ..." style={{fontFamily:"var(--font-mono)", fontSize:12.5}}></textarea>
                  <div className="field-help">Una guía por línea o separadas por coma.</div>
                </div>
              )}

              <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
                <ToggleField label="Guardar HTML crudo" desc="Útil si Effi cambió su HTML." defaultChecked={false}/>
                <ToggleField label="Notificar al terminar" desc="Push al completar o fallar." defaultChecked={true}/>
              </div>
            </div>

            <div style={{display:"flex", justifyContent:"flex-end", gap:8, paddingTop:14, borderTop:"1px solid var(--border)"}}>
              <button className="btn" onClick={()=>onNav("centro")}>Cancelar</button>
              <button className={"btn " + (mode==="apply"?"brand":"primary")}>
                {I.play}<span>Iniciar corrida {mode === "apply" ? "(apply)" : "(dry-run)"}</span>
              </button>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><div className="panel-title">Vista previa</div></div>
          <div className="panel-body" style={{fontSize:13}}>
            <div style={{display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:"1px solid var(--border)"}}><span className="muted">Modo</span><Pill kind={mode==="apply"?"danger":"info"}>{mode}</Pill></div>
            <div style={{display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:"1px solid var(--border)"}}><span className="muted">Guías estimadas</span><span className="mono tnum">~1,204</span></div>
            <div style={{display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:"1px solid var(--border)"}}><span className="muted">Workers</span><span className="mono tnum">8</span></div>
            <div style={{display:"flex", justifyContent:"space-between", padding:"6px 0", borderBottom:"1px solid var(--border)"}}><span className="muted">Tiempo estimado</span><span className="mono tnum">~3m 45s</span></div>
            <div style={{display:"flex", justifyContent:"space-between", padding:"6px 0"}}><span className="muted">Reglas activas</span><span className="mono tnum">9 / 10</span></div>
            <div style={{marginTop:14, padding:"10px 12px", background:"var(--info-tint)", border:"1px solid var(--info-soft)", borderRadius:"var(--r)", fontSize:12, color:"var(--ink-2)"}}>
              {mode === "apply"
                ? <><strong style={{color:"var(--danger)"}}>Atención:</strong> apply escribe en Notion. Te recomendamos un dry-run primero.</>
                : <><strong style={{color:"var(--info)"}}>Tip:</strong> Después del dry-run revisa <code style={{fontFamily:"var(--font-mono)"}}>summary.md</code> antes de hacer apply.</>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ModeCard({ active, onClick, title, desc, pill, pillKind }) {
  return (
    <div onClick={onClick} style={{
      padding:"12px 14px",
      border: active ? "1.5px solid var(--ink)" : "1px solid var(--border)",
      borderRadius:"var(--r-lg)",
      cursor:"pointer",
      background: active ? "var(--surface)" : "var(--surface)",
      boxShadow: active ? "0 0 0 3px rgba(0,0,0,0.04)" : "none",
      transition:"all 0.12s"
    }}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4}}>
        <span style={{fontWeight:600, fontSize:13}}>{title}</span>
        <Pill kind={pillKind}>{pill}</Pill>
      </div>
      <div style={{fontSize:12, color:"var(--muted)"}}>{desc}</div>
    </div>
  );
}

function Radio({ label, sub, v, cur, on }) {
  const active = v === cur;
  return (
    <div onClick={()=>on(v)} style={{
      flex:1, minWidth:160, padding:"10px 12px",
      border: active ? "1.5px solid var(--ink)" : "1px solid var(--border)",
      borderRadius:"var(--r)", cursor:"pointer", background:"var(--surface)"
    }}>
      <div style={{fontSize:13, fontWeight:500}}>{label}</div>
      <div style={{fontSize:11.5, color:"var(--muted)", marginTop:2}}>{sub}</div>
    </div>
  );
}

function ToggleField({ label, desc, defaultChecked }) {
  const [c, setC] = useStateDetalle(defaultChecked);
  return (
    <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", padding:"10px 12px", border:"1px solid var(--border)", borderRadius:"var(--r)"}}>
      <div>
        <div style={{fontSize:13, fontWeight:500}}>{label}</div>
        <div style={{fontSize:11.5, color:"var(--muted)", marginTop:2}}>{desc}</div>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={c} onChange={e=>setC(e.target.checked)}/>
        <span className="knob"></span>
      </label>
    </div>
  );
}

function Reglas({ onNav }) {
  const D = window.VAECOS_DATA;
  const I = window.VAECOS_ICONS;
  return (
    <>
      <PageHead
        crumbs={["Acciones", "Reglas"]}
        title="Motor de reglas"
        sub="Editables sin tocar código. Evaluación por prioridad ascendente, primera coincidencia gana."
        actions={<>
          <button className="btn">{I.history}<span>Historial</span></button>
          <button className="btn primary">{I.plus}<span>Nueva regla</span></button>
        </>}
      />

      <div className="panel">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{width:50}}>Prio</th>
              <th>Nombre</th>
              <th>Condición</th>
              <th>Acción</th>
              <th style={{textAlign:"right"}}>Aciertos (30d)</th>
              <th style={{width:80}}>Activa</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {D.rules.map(r => (
              <tr key={r.id} style={{opacity: r.activa ? 1 : 0.55}}>
                <td className="mono num">{r.prio}</td>
                <td><span style={{fontWeight:500}}>{r.nombre}</span></td>
                <td className="mono" style={{fontSize:12, color:"var(--ink-2)"}}>{r.condicion}</td>
                <td><Pill kind={r.accion.includes("urgente")?"danger":r.accion.includes("atención")?"warn":"neutral"}>{r.accion}</Pill></td>
                <td className="num">{r.hits}</td>
                <td>
                  <label className="toggle">
                    <input type="checkbox" defaultChecked={r.activa}/>
                    <span className="knob"></span>
                  </label>
                </td>
                <td style={{textAlign:"right"}}><button className="btn sm">Editar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

Object.assign(window, { DetalleCorrida, NuevaCorrida, Reglas });
