// Pantalla: Analytics
function Analytics({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const trend = D.trend;
  const totals = trend.map(t => t.total);
  const att = trend.map(t => t.attention);
  const changed = trend.map(t => t.changed);
  const sumTot = totals.reduce((a,b)=>a+b,0);
  const sumAtt = att.reduce((a,b)=>a+b,0);
  const sumCh = changed.reduce((a,b)=>a+b,0);

  return (
    <>
      <PageHead
        crumbs={["Inteligencia", "Analytics"]}
        title="Analytics"
        sub="Tendencias de 30 días, clientes problemáticos y desempeño por transportista."
        actions={<>
          <button className="btn">{I.filter}<span>Filtrar período</span></button>
          <button className="btn">{I.download}<span>Exportar</span></button>
        </>}
      />

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-label">Guías procesadas (30d)</div>
          <div className="kpi-value tnum">{sumTot.toLocaleString()}</div>
          <div className="kpi-meta"><span className="delta up">+8.4%</span><span>vs período anterior</span></div>
          <div className="kpi-spark"><Sparkline values={totals} color="var(--ink-2)" w={70} h={26}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Cambios aplicados</div>
          <div className="kpi-value tnum">{sumCh.toLocaleString()}</div>
          <div className="kpi-meta"><span>{((sumCh/sumTot)*100).toFixed(1)}% del total</span></div>
          <div className="kpi-spark"><Sparkline values={changed} color="var(--ok)" w={70} h={26}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Atención acumulada</div>
          <div className="kpi-value tnum">{sumAtt.toLocaleString()}</div>
          <div className="kpi-meta"><span className="delta down">+12.1%</span><span>tendencia ↑</span></div>
          <div className="kpi-spark"><Sparkline values={att} color="var(--danger)" w={70} h={26}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Tasa de error</div>
          <div className="kpi-value tnum">3.5%</div>
          <div className="kpi-meta"><span>Effi 0.7% · Guatex 100%*</span></div>
        </div>
      </div>

      <div className="panel" style={{marginBottom:16}}>
        <div className="panel-head">
          <div>
            <div className="panel-title">Tendencia de 30 días</div>
            <div className="panel-sub">Total procesado · cambios · requieren atención</div>
          </div>
          <div className="row">
            <span className="chip active">30d</span>
            <span className="chip">7d</span>
            <span className="chip">90d</span>
          </div>
        </div>
        <div className="panel-body">
          <BigChart trend={trend}/>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">Top clientes problemáticos</div>
            <span className="muted" style={{fontSize:12}}>por % atención</span>
          </div>
          <div className="panel-body flush">
            <table className="tbl">
              <thead>
                <tr><th>Cliente</th><th style={{textAlign:"right"}}>Total</th><th style={{textAlign:"right"}}>Atención</th><th style={{textAlign:"right"}}>Tasa</th></tr>
              </thead>
              <tbody>
                {D.topClientes.map(c => (
                  <tr key={c.nombre}>
                    <td>{c.nombre}</td>
                    <td className="num">{c.total}</td>
                    <td className="num"><span style={{color:"var(--danger)"}}>{c.attention}</span></td>
                    <td>
                      <div style={{display:"flex", alignItems:"center", gap:8, justifyContent:"flex-end"}}>
                        <div className="bar" style={{width:60}}><div className="bar-fill danger" style={{width: (c.ratio*100*8) + "%"}}/></div>
                        <span className="mono num" style={{minWidth:38}}>{(c.ratio*100).toFixed(1)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">Desempeño por carrier</div>
          </div>
          <div className="panel-body" style={{display:"flex", flexDirection:"column", gap:18}}>
            <CarrierStat name="effi" total={1089} ok={1023} attention={31} error={35}/>
            <div style={{height:1, background:"var(--border)"}}></div>
            <CarrierStat name="guatex" total={115} ok={0} attention={11} error={0} stub/>
            <div style={{padding:"10px 12px", background:"var(--warn-tint)", border:"1px solid var(--warn-soft)", borderRadius:"var(--r)", fontSize:12, color:"var(--ink-2)"}}>
              <strong style={{color:"var(--warn)"}}>Nota:</strong> Guatex está como stub. Las 115 guías se marcan manual_review hasta que se implemente el scraper real.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function CarrierStat({ name, total, ok, attention, error, stub }) {
  return (
    <div>
      <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8}}>
        <CarrierBadge name={name}/>
        <span className="mono tnum" style={{fontSize:13, fontWeight:600}}>{total.toLocaleString()} guías</span>
      </div>
      {!stub ? (
        <>
          <div style={{display:"flex", height:8, borderRadius:4, overflow:"hidden", background:"var(--surface-2)"}}>
            <div style={{width: (ok/total*100)+"%", background:"var(--ok)"}}></div>
            <div style={{width: (attention/total*100)+"%", background:"var(--warn)"}}></div>
            <div style={{width: (error/total*100)+"%", background:"var(--danger)"}}></div>
          </div>
          <div style={{display:"flex", justifyContent:"space-between", marginTop:8, fontSize:12, color:"var(--muted)"}}>
            <span><span style={{color:"var(--ok)"}}>●</span> OK {ok}</span>
            <span><span style={{color:"var(--warn)"}}>●</span> Atención {attention}</span>
            <span><span style={{color:"var(--danger)"}}>●</span> Error {error}</span>
          </div>
        </>
      ) : (
        <div style={{padding:"8px 12px", background:"var(--surface-2)", borderRadius:"var(--r)", fontSize:12, color:"var(--muted)", fontFamily:"var(--font-mono)"}}>
          stub · pendiente implementación
        </div>
      )}
    </div>
  );
}

function BigChart({ trend }) {
  const w = 800, h = 240, padX = 36, padY = 16;
  const max = Math.max(...trend.map(t => t.total));
  const x = (i) => padX + (i/(trend.length-1)) * (w - padX*2);
  const y = (v) => padY + (1 - v/max) * (h - padY*2);

  const totalPath = trend.map((t,i) => `${i===0?"M":"L"}${x(i)},${y(t.total)}`).join(" ");
  const totalArea = totalPath + ` L${x(trend.length-1)},${h-padY} L${x(0)},${h-padY} Z`;
  const changedPath = trend.map((t,i) => `${i===0?"M":"L"}${x(i)},${y(t.changed)}`).join(" ");
  const attPath = trend.map((t,i) => `${i===0?"M":"L"}${x(i)},${y(t.attention)}`).join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h+24}`} width="100%" height={h+24}>
        <defs>
          <linearGradient id="totalGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--ink)" stopOpacity="0.08"/>
            <stop offset="100%" stopColor="var(--ink)" stopOpacity="0"/>
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((s,i) => {
          const yy = padY + s*(h-padY*2);
          return (
            <g key={i}>
              <line x1={padX} x2={w-padX} y1={yy} y2={yy} stroke="var(--border)" strokeDasharray="2 3" strokeWidth="0.8"/>
              <text x={padX-8} y={yy+3} fontSize="9" fill="var(--muted)" textAnchor="end" fontFamily="var(--font-mono)">{Math.round(max*(1-s))}</text>
            </g>
          );
        })}
        <path d={totalArea} fill="url(#totalGrad)"/>
        <path d={totalPath} fill="none" stroke="var(--ink-2)" strokeWidth="2"/>
        <path d={changedPath} fill="none" stroke="var(--ok)" strokeWidth="2"/>
        <path d={attPath} fill="none" stroke="var(--brand)" strokeWidth="2"/>
        {trend.filter((_,i)=>i%5===0).map((t,k) => {
          const i = k*5;
          return <text key={i} x={x(i)} y={h+18} fontSize="9" fill="var(--muted)" textAnchor="middle" fontFamily="var(--font-mono)">{t.fecha}</text>;
        })}
      </svg>
      <div style={{display:"flex", gap:18, fontSize:12, color:"var(--muted)", marginTop:6, paddingLeft:36}}>
        <span style={{display:"inline-flex", alignItems:"center", gap:6}}><span style={{width:12, height:2, background:"var(--ink-2)"}}></span>Total procesado</span>
        <span style={{display:"inline-flex", alignItems:"center", gap:6}}><span style={{width:12, height:2, background:"var(--ok)"}}></span>Cambios aplicados</span>
        <span style={{display:"inline-flex", alignItems:"center", gap:6}}><span style={{width:12, height:2, background:"var(--brand)"}}></span>Requieren atención</span>
      </div>
    </div>
  );
}

window.Analytics = Analytics;
