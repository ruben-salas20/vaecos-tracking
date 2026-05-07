// Pantalla: Centro Operativo
const D = window.VAECOS_DATA;

function CentroOperativo({ onNav }) {
  const I = window.VAECOS_ICONS;
  const r = D.latestRun;
  const trendVals = D.trend.map(t => t.total);
  const attVals = D.trend.map(t => t.attention);
  const changedVals = D.trend.map(t => t.changed);
  const errVals = D.trend.map(t => 5 + (t.attention % 8));

  return (
    <>
      <PageHead
        crumbs={["Operación", "Centro Operativo"]}
        title="Centro Operativo"
        sub="Estado consolidado de tracking entre Notion y transportistas."
        actions={<>
          <button className="btn"><span className="row" style={{gap:6}}>{I.refresh}<span>Sincronizar</span></span></button>
          <button className="btn brand" onClick={() => onNav("newrun")}>{I.play}<span>Nueva corrida</span></button>
        </>}
      />

      <div className="banner">
        <span className="banner-icon">{I.alert}</span>
        <div className="banner-body">
          <div className="banner-title">42 guías requieren acción hoy</div>
          <div className="banner-text">8 con prioridad alta · 6 sin escaneo &gt; 5 días · 3 daños reportados. Última corrida hace 2 minutos.</div>
        </div>
        <button className="btn primary" onClick={() => onNav("attention")}>Revisar ahora {I.arrow}</button>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-label">{I.history}<span>Última corrida</span></div>
          <div className="kpi-value tnum">{r.total.toLocaleString()}</div>
          <div className="kpi-meta"><span className="mono">#{r.id}</span><span>·</span><span>{r.duration}</span><span>·</span><span className="delta up">+1.2%</span></div>
          <div className="kpi-spark"><Sparkline values={trendVals.slice(-14)} color="var(--ink-2)" w={70} h={26}/></div>
        </div>
        <div className="kpi alert">
          <div className="kpi-label">{I.bell}<span>Requieren atención</span></div>
          <div className="kpi-value tnum">42</div>
          <div className="kpi-meta"><span className="delta down">+4 vs ayer</span><span>·</span><span>8 alta · 12 media</span></div>
          <div className="kpi-spark"><Sparkline values={attVals.slice(-14)} color="var(--danger)" w={70} h={26}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">{I.refresh}<span>Cambios aplicados</span></div>
          <div className="kpi-value tnum">187</div>
          <div className="kpi-meta"><span>15.5% del total</span><span>·</span><span className="delta up">+19.8%</span></div>
          <div className="kpi-spark"><Sparkline values={changedVals.slice(-14)} color="var(--ok)" w={70} h={26}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">{I.alert}<span>Errores</span></div>
          <div className="kpi-value tnum">43</div>
          <div className="kpi-meta"><span>8 parse · 35 red</span><span>·</span><span className="delta flat">±0</span></div>
          <div className="kpi-spark"><Sparkline values={errVals.slice(-14)} color="var(--warn)" w={70} h={26}/></div>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap:16, marginBottom:16}}>
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">Guías recientes que requieren atención</div>
              <div className="panel-sub">Top resultados de la corrida #28 · ordenado por prioridad</div>
            </div>
            <button className="btn sm" onClick={() => onNav("attention")}>Ver todas (42) {I.arrow}</button>
          </div>
          <div className="panel-body flush">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Guía</th>
                  <th>Cliente</th>
                  <th>Estado</th>
                  <th>Carrier</th>
                  <th style={{textAlign:"right"}}>Días</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {D.attentionGuides.slice(0, 5).map(g => (
                  <tr key={g.id} style={{cursor:"pointer"}}>
                    <td className="mono">{g.id}</td>
                    <td>{g.cliente}</td>
                    <td>
                      <Pill kind={g.prioridad === "alta" ? "danger" : g.prioridad === "media" ? "warn" : "neutral"}>
                        {g.estado}
                      </Pill>
                    </td>
                    <td><CarrierBadge name={g.carrier}/></td>
                    <td className="num">{g.dias}</td>
                    <td style={{textAlign:"right"}}><button className="btn sm">Abrir</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="panel-title">Salud del sistema</div>
            </div>
            <Pill kind="ok">operativo</Pill>
          </div>
          <div className="panel-body" style={{display:"flex", flexDirection:"column", gap:14}}>
            <HealthRow label="Notion API" value="98 ms" pct={0.92} kind="ok"/>
            <HealthRow label="Effi scraper" value="ok · 1,089 guías" pct={0.95} kind="ok"/>
            <HealthRow label="Guatex (stub)" value="115 manual" pct={0.45} kind="warn"/>
            <HealthRow label="SQLite size" value="14.2 MB" pct={0.18} kind="ok"/>
            <div style={{paddingTop:6, borderTop:"1px solid var(--border)", display:"flex", justifyContent:"space-between", fontSize:12, color:"var(--muted)"}}>
              <span>Próx. corrida automática</span>
              <span className="mono">18:45 · en 4h 13m</span>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">Distribución de resultados — Corrida #{r.id}</div>
            <div className="panel-sub">Aplicado por reglas tras evaluación de {r.total.toLocaleString()} guías</div>
          </div>
        </div>
        <div className="panel-body" style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:18}}>
          <div>
            {D.estadosBreakdown.map((e, i) => {
              const pct = (e.count / r.total) * 100;
              return (
                <div key={i} style={{display:"flex", alignItems:"center", gap:10, marginBottom:10}}>
                  <div style={{flex:1, fontSize:13}}>{e.label}</div>
                  <div style={{width:140}}><div className="bar"><div className={"bar-fill " + e.color}  style={{width: pct + "%"}}/></div></div>
                  <div className="mono tnum" style={{width:60, textAlign:"right", fontSize:12.5}}>{e.count.toLocaleString()}</div>
                  <div className="mono tnum muted" style={{width:50, textAlign:"right", fontSize:12}}>{pct.toFixed(1)}%</div>
                </div>
              );
            })}
          </div>
          <StackedTrendChart/>
        </div>
      </div>
    </>
  );
}

function HealthRow({ label, value, pct, kind }) {
  return (
    <div>
      <div style={{display:"flex", justifyContent:"space-between", marginBottom:5, fontSize:12.5}}>
        <span>{label}</span>
        <span className="mono muted">{value}</span>
      </div>
      <div className="bar"><div className={"bar-fill " + (kind || "ok")} style={{width: (pct*100) + "%"}}/></div>
    </div>
  );
}

function StackedTrendChart() {
  const days = D.trend.slice(-14);
  const max = Math.max(...days.map(d => d.total));
  const w = 360, h = 180, padX = 12, padY = 8;
  const bw = (w - padX*2) / days.length - 3;
  return (
    <div>
      <div style={{fontSize:11, fontWeight:600, color:"var(--muted)", textTransform:"uppercase", letterSpacing:"0.05em", marginBottom:8}}>Últimos 14 días · total / atención</div>
      <svg viewBox={`0 0 ${w} ${h+24}`} width="100%" height={h+24}>
        {[0.25, 0.5, 0.75, 1].map((s,i) => {
          const y = padY + (h - padY*2)*(1-s);
          return <line key={i} x1={padX} x2={w-padX} y1={y} y2={y} stroke="var(--border)" strokeDasharray="2 3" strokeWidth="0.8"/>;
        })}
        {days.map((d, i) => {
          const x = padX + i*(bw+3);
          const total_h = (d.total/max)*(h-padY*2);
          const att_h = (d.attention/max)*(h-padY*2);
          return (
            <g key={i}>
              <rect x={x} y={padY+(h-padY*2)-total_h} width={bw} height={total_h} fill="var(--ink-2)" opacity="0.15" rx="1.5"/>
              <rect x={x} y={padY+(h-padY*2)-att_h} width={bw} height={att_h} fill="var(--brand)" rx="1.5"/>
            </g>
          );
        })}
        {days.filter((_,i)=>i%3===0).map((d,k) => {
          const i = k*3;
          const x = padX + i*(bw+3) + bw/2;
          return <text key={i} x={x} y={h+18} fontSize="9" fill="var(--muted)" textAnchor="middle" fontFamily="var(--font-mono)">{d.fecha}</text>;
        })}
      </svg>
      <div style={{display:"flex", gap:14, fontSize:11, color:"var(--muted)", marginTop:4}}>
        <span style={{display:"inline-flex", alignItems:"center", gap:5}}><span style={{width:10, height:10, background:"var(--ink-2)", opacity:0.25, borderRadius:2}}></span>Total</span>
        <span style={{display:"inline-flex", alignItems:"center", gap:5}}><span style={{width:10, height:10, background:"var(--brand)", borderRadius:2}}></span>Requiere atención</span>
      </div>
    </div>
  );
}

window.CentroOperativo = CentroOperativo;
