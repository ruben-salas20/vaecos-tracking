// App root + tweaks panel integration
const { useState: useStateApp, useEffect: useEffectApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "density": "default",
  "accent": "#DC2626",
  "showSidebarBadge": true
}/*EDITMODE-END*/;

function App() {
  const [screen, setScreen] = useStateApp("centro");
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  useEffectApp(() => {
    document.documentElement.setAttribute("data-theme", tweaks.theme);
    document.documentElement.setAttribute("data-density", tweaks.density);
    document.documentElement.style.setProperty("--brand", tweaks.accent);
    // adjust strong/soft variants
    document.documentElement.style.setProperty("--brand-strong", shade(tweaks.accent, -0.18));
  }, [tweaks.theme, tweaks.density, tweaks.accent]);

  // Allow screen ids like "guide:B263378877-1" to pass an arg
  const [base, ...rest] = String(screen).split(":");
  const arg = rest.join(":");

  const Screens = {
    centro: window.CentroOperativo,
    attention: window.Attention,
    analytics: window.Analytics,
    runs: window.DetalleCorrida,
    newrun: window.NuevaCorrida,
    rules: window.Reglas,
    history: window.HistorialCorridas,
    porrecoger: window.PorRecoger,
    guide: window.GuideDetail,
    client: window.ClientDetail,
    progress: window.RunProgress,
  };
  const Current = Screens[base] || Screens.centro;

  return (
    <>
      <div className="app">
        <Sidebar current={screen} onNav={setScreen}/>
        <main className="main">
          <Current onNav={setScreen} guia={arg} cliente={arg}/>
        </main>
      </div>
      <TweaksPanel title="Tweaks">
        <TweakSection title="Apariencia">
          <TweakRadio label="Tema" value={tweaks.theme} onChange={v=>setTweak("theme", v)} options={[{value:"light",label:"Claro"},{value:"dark",label:"Oscuro"}]}/>
          <TweakRadio label="Densidad" value={tweaks.density} onChange={v=>setTweak("density", v)} options={[{value:"compact",label:"Compacta"},{value:"default",label:"Normal"},{value:"comfortable",label:"Amplia"}]}/>
          <TweakColor label="Color de acento" value={tweaks.accent} onChange={v=>setTweak("accent", v)}/>
        </TweakSection>
        <TweakSection title="Navegación rápida">
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:6}}>
            {[
              ["centro","Centro"],["attention","Atención"],
              ["analytics","Analytics"],["porrecoger","Por recoger"],
              ["history","Historial"],["runs","Corrida"],
              ["guide","Guía"],["client","Cliente"],
              ["progress","Progreso"],["newrun","Nueva"],
              ["rules","Reglas"]
            ].map(([k,l]) => (
              <button key={k}
                className={"chip " + (base===k?"active":"")}
                style={{justifyContent:"center"}}
                onClick={()=>setScreen(k)}>{l}</button>
            ))}
          </div>
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

function shade(hex, amt) {
  // hex -> rgb -> shade
  const h = hex.replace("#","");
  const r = parseInt(h.substring(0,2),16);
  const g = parseInt(h.substring(2,4),16);
  const b = parseInt(h.substring(4,6),16);
  const adj = c => Math.max(0, Math.min(255, Math.round(c + 255*amt)));
  const toHex = c => c.toString(16).padStart(2,"0");
  return "#" + toHex(adj(r)) + toHex(adj(g)) + toHex(adj(b));
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
