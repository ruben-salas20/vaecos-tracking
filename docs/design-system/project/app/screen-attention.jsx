// Pantalla: Requiere Atención (lista filtrable)
const { useState: useStateAtt } = React;

function Attention({ onNav }) {
  const I = window.VAECOS_ICONS;
  const D = window.VAECOS_DATA;
  const [filter, setFilter] = useStateAtt("todas");
  const [carrier, setCarrier] = useStateAtt("todos");

  const filtered = D.attentionGuides.filter(g =>
    (filter === "todas" || g.prioridad === filter) &&
    (carrier === "todos" || g.carrier === carrier)
  );

  return (
    <>
      <PageHead
        crumbs={["Operación", "Requiere atención"]}
        title="Requiere atención"
        sub="Guías que las reglas activas marcaron para revisión manual."
        actions={<>
          <button className="btn">{I.download}<span>Exportar CSV</span></button>
          <button className="btn primary">{I.check}<span>Marcar resueltas</span></button>
        </>}
      />

      <div className="panel">
        <div className="filterbar">
          <span className={"chip " + (filter==="todas"?"active":"")} onClick={()=>setFilter("todas")}>Todas <span className="count">42</span></span>
          <span className={"chip " + (filter==="alta"?"active":"")} onClick={()=>setFilter("alta")}>Prioridad alta <span className="count">8</span></span>
          <span className={"chip " + (filter==="media"?"active":"")} onClick={()=>setFilter("media")}>Media <span className="count">12</span></span>
          <span className={"chip " + (filter==="baja"?"active":"")} onClick={()=>setFilter("baja")}>Baja <span className="count">22</span></span>
          <div style={{width:1, height:20, background:"var(--border)", margin:"0 4px"}}></div>
          <span className={"chip " + (carrier==="todos"?"active":"")} onClick={()=>setCarrier("todos")}>Todos carriers</span>
          <span className={"chip " + (carrier==="effi"?"active":"")} onClick={()=>setCarrier("effi")}>Effi <span className="count">31</span></span>
          <span className={"chip " + (carrier==="guatex"?"active":"")} onClick={()=>setCarrier("guatex")}>Guatex <span className="count">11</span></span>
          <div style={{flex:1}}></div>
          <input className="input search" placeholder="Buscar guía, cliente..." style={{maxWidth:240}}/>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{width:30}}><input type="checkbox"/></th>
              <th>Guía</th>
              <th>Cliente</th>
              <th>Origen → Destino</th>
              <th>Estado actual</th>
              <th>Motivo</th>
              <th>Carrier</th>
              <th style={{textAlign:"right"}}>Días</th>
              <th style={{textAlign:"right"}}>Cambios</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(g => (
              <tr key={g.id}>
                <td><input type="checkbox"/></td>
                <td className="mono">{g.id}</td>
                <td>{g.cliente}</td>
                <td className="muted" style={{fontSize:12.5}}>{g.origen} → <span style={{color:"var(--ink-2)"}}>{g.destino}</span></td>
                <td>
                  <Pill kind={g.prioridad === "alta" ? "danger" : g.prioridad === "media" ? "warn" : "neutral"}>
                    {g.estado}
                  </Pill>
                </td>
                <td style={{fontSize:12.5, color:"var(--ink-2)"}}>{g.motivo}</td>
                <td><CarrierBadge name={g.carrier}/></td>
                <td className="num">{g.dias}</td>
                <td className="num">{g.cambios}</td>
                <td style={{textAlign:"right"}}>
                  <button className="btn sm">{I.ext}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{padding:"10px 16px", display:"flex", justifyContent:"space-between", alignItems:"center", borderTop:"1px solid var(--border)", fontSize:12, color:"var(--muted)"}}>
          <span>Mostrando {filtered.length} de 42 · Última corrida #{D.latestRun.id}</span>
          <div className="row">
            <button className="btn sm">Anterior</button>
            <span className="mono">1 / 6</span>
            <button className="btn sm">Siguiente</button>
          </div>
        </div>
      </div>
    </>
  );
}

window.Attention = Attention;
