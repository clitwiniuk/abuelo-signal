import { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";

const API = "http://127.0.0.1:5050";

const CATEGORY_COLORS = {
  "Top Gainers":           "#00ff88",
  "Top Losers":            "#ff4466",
  "New High":              "#00cfff",
  "New Low":               "#ff6b6b",
  "Most Volatile":         "#ff9f00",
  "Most Active":           "#c084fc",
  "Unusual Volume":        "#fb923c",
  "Overbought":            "#f472b6",
  "Oversold":              "#34d399",
  "Downgrades":            "#f87171",
  "Upgrades":              "#4ade80",
  "Earnings Before":       "#fbbf24",
  "Earnings After":        "#a78bfa",
  "Recent Insider Buying": "#2dd4bf",
  "Insider Buying":        "#2dd4bf",
  "Recent Insider Selling":"#f97316",
  "Insider Selling":       "#f97316",
};

const HYPE_COLORS  = ["#00ff88","#00cfff","#ff9f00","#bf88ff","#ff4466","#44ffdd","#ffdd44","#ff88bf"];
const SIGNAL_CONFIG = {
  spike:          { label: "SPIKE",     color: "#ff4466" },
  trending:       { label: "TRENDING",  color: "#ff9f00" },
  early_momentum: { label: "EARLY MOM", color: "#00cfff" },
};

function getColor(cat) { return CATEGORY_COLORS[cat] || "#c8d8f0"; }

function formatChange(val) {
  if (!val || val === "None") return "—";
  const n = parseFloat(String(val).replace("%",""));
  if (isNaN(n)) return val;
  const color = n >= 0 ? "#00ff88" : "#ff4466";
  return <span style={{color, fontWeight:700}}>{n>=0?"+":""}{n.toFixed(2)}%</span>;
}

function formatPrice(val) {
  if (!val) return "—";
  const n = parseFloat(val);
  return isNaN(n) ? val : `$${n.toFixed(2)}`;
}

function formatTs(ts) {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleTimeString("en-US", {hour:"2-digit",minute:"2-digit",hour12:false,timeZone:"America/New_York"}); }
  catch { return ts; }
}

function formatDate(d) {
  if (!d) return "—";
  try { const [y,m,day] = d.split("-"); return `${day}/${m}/${y}`; }
  catch { return d; }
}

function SignalBadge({ signal }) {
  if (!signal) return null;
  const cfg = SIGNAL_CONFIG[signal];
  if (!cfg) return null;
  return <span className="signal-badge" style={{ color: cfg.color, borderColor: cfg.color }}>{cfg.label}</span>;
}

function DeltaCell({ val }) {
  if (val == null) return <span style={{color:"#4a6080"}}>—</span>;
  const n = parseFloat(val);
  if (isNaN(n)) return <span style={{color:"#4a6080"}}>—</span>;
  const color = n > 2 ? "#00ff88" : n > 1 ? "#ff9f00" : n > 0 ? "#c8d8f0" : "#4a6080";
  return <span style={{ color, fontWeight: n > 2 ? 700 : 400 }}>{n > 0 ? "+" : ""}{n.toFixed(2)}</span>;
}

function useAPI() {
  const [status,  setStatus]  = useState(null);
  const [rows,    setRows]    = useState([]);
  const [ibkr,    setIbkr]    = useState(null);
  const [hype,    setHype]    = useState({ ranking: [], curves: null, signals: [] });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetchStatus = useCallback(async () => {
    try { const r = await fetch(`${API}/status`); setStatus(await r.json()); setError(null); }
    catch { setError("No se puede conectar con el servidor Python"); }
  }, []);

  const fetchData = useCallback(async () => {
    try { const r = await fetch(`${API}/data/latest`); setRows(await r.json()); }
    catch {}
  }, []);

  const fetchIbkr = useCallback(async () => {
    try { const r = await fetch(`${API}/ibkr/status`); setIbkr(await r.json()); }
    catch {}
  }, []);

  const fetchHype = useCallback(async () => {
    try {
      const [ranking, curves, signals] = await Promise.all([
        fetch(`${API}/hype/ranking`).then(r => r.json()),
        fetch(`${API}/hype/curves?limit=8`).then(r => r.json()),
        fetch(`${API}/hype/signals?limit=30`).then(r => r.json()),
      ]);
      setHype({ ranking, curves, signals });
    } catch {}
  }, []);

  const start = async () => { await fetch(`${API}/start`,{method:"POST"}); fetchStatus(); };
  const stop  = async () => { await fetch(`${API}/stop`, {method:"POST"}); fetchStatus(); };
  const snap  = async () => {
    setLoading(true);
    await fetch(`${API}/snapshot`,{method:"POST"});
    setTimeout(() => { fetchData(); fetchStatus(); fetchHype(); setLoading(false); }, 8000);
  };

  useEffect(() => {
    fetchStatus(); fetchData(); fetchIbkr(); fetchHype();
    const si = setInterval(fetchStatus, 5000);
    const di = setInterval(fetchData,   60000);
    const ii = setInterval(fetchIbkr,   15000);
    const hi = setInterval(fetchHype,   30000);
    return () => { clearInterval(si); clearInterval(di); clearInterval(ii); clearInterval(hi); };
  }, [fetchStatus, fetchData, fetchIbkr, fetchHype]);

  return { status, rows, ibkr, hype, loading, error, start, stop, snap };
}

function LiveView({ rows }) {
  const [filterCat, setFilterCat] = useState("ALL");
  const categories = ["ALL", ...Array.from(new Set(rows.map(r=>r.category))).sort()];
  const filtered = filterCat === "ALL" ? rows : rows.filter(r=>r.category===filterCat);
  return (
    <div className="view-content">
      <div className="filter-bar">
        {categories.map(cat => (
          <button key={cat} className={`filter-btn ${filterCat===cat?"filter-active":""}`}
            style={filterCat===cat && cat!=="ALL" ? {borderColor:getColor(cat),color:getColor(cat)} : {}}
            onClick={() => setFilterCat(cat)}>
            {cat==="ALL" ? `ALL (${rows.length})` : <><span style={{color:getColor(cat)}}>●</span>{` ${cat} (${rows.filter(r=>r.category===cat).length})`}</>}
          </button>
        ))}
      </div>
      {filtered.length === 0
        ? <div className="empty-state"><span>Sin datos</span><span className="empty-sub">Haz un snapshot manual para empezar</span></div>
        : <div className="table-wrap"><table>
            <thead><tr><th>#</th><th>TICKER</th><th>PRICE</th><th>CHANGE %</th><th>VOLUME</th><th>CATEGORY</th></tr></thead>
            <tbody>{filtered.map((row,i) => {
              const color = getColor(row.category);
              return <tr key={i} className="ticker-row">
                <td className="idx">{i+1}</td>
                <td className="ticker-cell" style={{color}}>{row.ticker}</td>
                <td>{row.price||"—"}</td><td>{formatChange(row.change_pct)}</td>
                <td className="vol">{row.volume||"—"}</td>
                <td><span className="cat-badge" style={{borderColor:color,color}}>{row.category}</span></td>
              </tr>;
            })}</tbody>
          </table></div>
      }
    </div>
  );
}

function HistoryView() {
  const [days,         setDays]         = useState([]);
  const [selectedDay,  setSelectedDay]  = useState(null);
  const [snapshots,    setSnapshots]    = useState([]);
  const [selectedSnap, setSelectedSnap] = useState(null);
  const [snapData,     setSnapData]     = useState([]);
  const [daySummary,   setDaySummary]   = useState([]);
  const [subView,      setSubView]      = useState("snapshot");
  const [filterCat,    setFilterCat]    = useState("ALL");

  useEffect(() => {
    fetch(`${API}/history/days`).then(r=>r.json()).then(d => {
      const safe = Array.isArray(d) ? d : [];
      setDays(safe);
      if (safe.length > 0) selectDay(safe[0]);
    }).catch(()=>{});
  }, []);

  const selectDay = async (day) => {
    setSelectedDay(day); setSelectedSnap(null); setSnapData([]);
    const [snaps, summary] = await Promise.all([
      fetch(`${API}/history/snapshots/${day}`).then(r=>r.json()),
      fetch(`${API}/history/day_summary/${day}`).then(r=>r.json()),
    ]);
    setSnapshots(snaps); setDaySummary(summary);
    if (snaps.length > 0) selectSnapshot(snaps[snaps.length-1]);
  };

  const selectSnapshot = async (ts) => {
    setSelectedSnap(ts); setFilterCat("ALL");
    const data = await fetch(`${API}/history/snapshot/${encodeURIComponent(ts)}`).then(r=>r.json());
    setSnapData(data);
  };

  const categories = ["ALL", ...Array.from(new Set(snapData.map(r=>r.category))).sort()];
  const filteredSnap = filterCat==="ALL" ? snapData : snapData.filter(r=>r.category===filterCat);

  return (
    <div className="history-layout">
      <div className="history-sidebar">
        <div className="hsidebar-header">DÍAS</div>
        {days.map(d => (
          <button key={d} className={`hsidebar-item ${selectedDay===d?"hsidebar-active":""}`} onClick={() => selectDay(d)}>
            {formatDate(d)}
            {selectedDay===d && snapshots.length>0 && <span className="hsidebar-count">{snapshots.length}</span>}
          </button>
        ))}
        {days.length===0 && <div className="hsidebar-empty">Sin historial aún</div>}
      </div>
      <div className="history-main">
        {selectedDay && (<>
          <div className="subtabs">
            <button className={`subtab ${subView==="snapshot"?"subtab-active":""}`} onClick={() => setSubView("snapshot")}>◷ SNAPSHOT POR HORA</button>
            <button className={`subtab ${subView==="summary"?"subtab-active":""}`}  onClick={() => setSubView("summary")}>◈ RESUMEN DEL DÍA</button>
          </div>
          {subView === "snapshot" && (
            <div className="snapshot-view">
              <div className="timeline">
                {snapshots.map(ts => (
                  <button key={ts} className={`timeline-btn ${selectedSnap===ts?"timeline-active":""}`} onClick={() => selectSnapshot(ts)}>{formatTs(ts)}</button>
                ))}
              </div>
              {snapData.length > 0 && (
                <div className="filter-bar filter-bar-sm">
                  {categories.map(cat => (
                    <button key={cat} className={`filter-btn ${filterCat===cat?"filter-active":""}`}
                      style={filterCat===cat && cat!=="ALL" ? {borderColor:getColor(cat),color:getColor(cat)} : {}}
                      onClick={() => setFilterCat(cat)}>
                      {cat==="ALL" ? `ALL (${snapData.length})` : <><span style={{color:getColor(cat)}}>●</span>{` ${cat} (${snapData.filter(r=>r.category===cat).length})`}</>}
                    </button>
                  ))}
                </div>
              )}
              {filteredSnap.length > 0
                ? <div className="table-wrap"><table>
                    <thead><tr><th>#</th><th>TICKER</th><th>PRICE</th><th>CHANGE %</th><th>VOLUME</th><th>CATEGORY</th></tr></thead>
                    <tbody>{filteredSnap.map((row,i) => {
                      const color = getColor(row.category);
                      return <tr key={i} className="ticker-row">
                        <td className="idx">{i+1}</td><td className="ticker-cell" style={{color}}>{row.ticker}</td>
                        <td>{row.price||"—"}</td><td>{formatChange(row.change_pct)}</td>
                        <td className="vol">{row.volume||"—"}</td>
                        <td><span className="cat-badge" style={{borderColor:color,color}}>{row.category}</span></td>
                      </tr>;
                    })}</tbody>
                  </table></div>
                : <div className="empty-state"><span>Selecciona un snapshot</span></div>
              }
            </div>
          )}
          {subView === "summary" && (
            <div className="table-wrap"><table>
              <thead><tr><th>#</th><th>TICKER</th><th>LAST PRICE</th><th>MAX CHANGE %</th><th>MAX VOLUME</th><th>APPEARANCES</th><th>CATEGORIES</th></tr></thead>
              <tbody>{daySummary.map((row,i) => (
                <tr key={i} className="ticker-row">
                  <td className="idx">{i+1}</td><td className="ticker-cell" style={{color:"#00cfff"}}>{row.ticker}</td>
                  <td>{row.last_price||"—"}</td><td>{formatChange(row.max_change_pct)}</td>
                  <td className="vol">{row.max_volume||"—"}</td>
                  <td><span className={`appearances-badge ${row.appearances>=4?"app-high":row.appearances>=2?"app-mid":""}`}>{row.appearances}x</span></td>
                  <td className="cats-cell">{row.categories.map(c=>(
                    <span key={c} className="cat-badge cat-badge-sm" style={{borderColor:getColor(c),color:getColor(c)}}>{c}</span>
                  ))}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </>)}
        {!selectedDay && <div className="empty-state"><span>Selecciona un día</span></div>}
      </div>
    </div>
  );
}

function OpportunitiesView() {
  const [days,        setDays]        = useState([]);
  const [selectedDay, setSelectedDay] = useState(null);
  const [data,        setData]        = useState(null);
  const [minApp,      setMinApp]      = useState(2);
  const [subView,     setSubView]     = useState("gainers");

  useEffect(() => {
    fetch(`${API}/history/days`).then(r=>r.json()).then(d => {
      const safe = Array.isArray(d) ? d : [];
      setDays(safe);
      if (safe.length > 0) loadOpportunities(safe[0], 2);
    }).catch(()=>{});
  }, []);

  const loadOpportunities = async (day, min) => {
    setSelectedDay(day); setMinApp(min);
    const d = await fetch(`${API}/opportunities/${day}?min_appearances=${min}`).then(r=>r.json());
    setData(d);
  };

  const gainers  = data?.persistent_gainers || [];
  const climbers = data?.volume_climbers    || [];

  return (
    <div className="opp-layout">
      <div className="opp-controls">
        <div className="opp-controls-left">
          <span className="opp-label">DÍA:</span>
          <select className="opp-select" value={selectedDay||""} onChange={e=>loadOpportunities(e.target.value, minApp)}>
            {days.map(d=><option key={d} value={d}>{formatDate(d)}</option>)}
          </select>
          <span className="opp-label">MÍN. APARICIONES:</span>
          {[2,3,4,5].map(n=>(
            <button key={n} className={`filter-btn ${minApp===n?"filter-active":""}`} onClick={()=>loadOpportunities(selectedDay,n)}>{n}+</button>
          ))}
        </div>
        <div className="subtabs">
          <button className={`subtab ${subView==="gainers"?"subtab-active":""}`} onClick={()=>setSubView("gainers")}>▲ TOP GAINERS PERSISTENTES ({gainers.length})</button>
          <button className={`subtab ${subView==="volume"?"subtab-active":""}`}  onClick={()=>setSubView("volume")}>◉ VOLUMEN CRECIENTE ({climbers.length})</button>
        </div>
      </div>
      {subView==="gainers" && (gainers.length===0
        ? <div className="empty-state"><span>Sin gainers persistentes</span><span className="empty-sub">Necesitas más snapshots del día</span></div>
        : <div className="table-wrap"><table>
            <thead><tr><th>#</th><th>TICKER</th><th>LAST PRICE</th><th>MAX CHANGE %</th><th>APARICIONES</th><th>PRIMERA VEZ</th><th>ÚLTIMA VEZ</th></tr></thead>
            <tbody>{gainers.map((row,i)=>(
              <tr key={i} className="ticker-row">
                <td className="idx">{i+1}</td><td className="ticker-cell" style={{color:"#00ff88"}}>{row.ticker}</td>
                <td>{row.last_price||"—"}</td><td>{formatChange(row.max_change_pct)}</td>
                <td><span className={`appearances-badge ${row.appearances>=4?"app-high":"app-mid"}`}>{row.appearances}x</span></td>
                <td className="vol">{formatTs(row.first_seen)}</td><td className="vol">{formatTs(row.last_seen)}</td>
              </tr>
            ))}</tbody>
          </table></div>
      )}
      {subView==="volume" && (climbers.length===0
        ? <div className="empty-state"><span>Sin tickers con volumen creciente</span><span className="empty-sub">Necesitas más snapshots del día</span></div>
        : <div className="table-wrap"><table>
            <thead><tr><th>#</th><th>TICKER</th><th>PRICE</th><th>CHANGE</th><th>VOL INICIO</th><th>VOL FINAL</th><th>CRECIMIENTO</th><th>CATEGORÍAS</th></tr></thead>
            <tbody>{climbers.map((row,i)=>(
              <tr key={i} className="ticker-row">
                <td className="idx">{i+1}</td><td className="ticker-cell" style={{color:"#fb923c"}}>{row.ticker}</td>
                <td>{row.last_price||"—"}</td><td>{formatChange(row.last_change)}</td>
                <td className="vol">{row.volume_start}</td><td className="vol">{row.volume_end}</td>
                <td><span style={{color:"#fb923c",fontWeight:700}}>+{row.volume_growth_pct}%</span></td>
                <td className="cats-cell">{row.categories.map(c=>(
                  <span key={c} className="cat-badge cat-badge-sm" style={{borderColor:getColor(c),color:getColor(c)}}>{c}</span>
                ))}</td>
              </tr>
            ))}</tbody>
          </table></div>
      )}
    </div>
  );
}

function HypeChart({ curvesData, hiddenTickers = [] }) {
  if (!curvesData || !curvesData.tickers || curvesData.tickers.length === 0) {
    return <div className="chart-empty">Sin datos de hype — haz un snapshot para generar curvas</div>;
  }
  const [chartH, setChartH] = useState(220);
  const [xView, setXView] = useState(null); // null = auto-fit
  const [yView, setYView] = useState(null); // null = auto-fit
  const svgRef = useRef(null);
  const dragRef = useRef(null);

  // Registrar wheel como non-passive para poder llamar preventDefault
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const W = 700, PAD = { t: 8, r: 82, b: 24, l: 40 };
  const IW = W - PAD.l - PAD.r, IH = chartH - PAD.t - PAD.b;

  const tickers = curvesData.tickers.filter(c => !hiddenTickers.includes(c.ticker));
  const allTimesRaw = tickers.flatMap(c => c.points.map(p => p.time_min));
  const dataXMin = allTimesRaw.length ? Math.min(...allTimesRaw) : 0;
  const dataXMax = allTimesRaw.length ? Math.max(...allTimesRaw) : 390;
  const autoPad = Math.max(5, (dataXMax - dataXMin) * 0.04);
  const xMin = xView ? xView[0] : dataXMin - autoPad;
  const xMax = xView ? xView[1] : dataXMax + autoPad;

  const visPoints = tickers.flatMap(c => c.points.filter(p => p.time_min >= xMin && p.time_min <= xMax));
  const dataYMax = Math.max(...visPoints.map(p => p.hype_cum), 1);
  const dataYMin = Math.min(...visPoints.map(p => p.hype_cum), 0);
  const yMin = yView ? yView[0] : dataYMin;
  const yMax = yView ? yView[1] : dataYMax;

  const xs = t => PAD.l + ((t - xMin) / Math.max(xMax - xMin, 1)) * IW;
  const ys = h => PAD.t + IH - ((h - yMin) / Math.max(yMax - yMin, 1)) * IH;

  // Zoom con rueda: normal=X, Shift=Y
  const onWheel = (e) => {
    e.preventDefault();
    const rect = svgRef.current.getBoundingClientRect();
    const factor = e.deltaY > 0 ? 1.18 : 0.85;
    if (e.shiftKey) {
      // Zoom Y centrado en cursor
      const ratioY = 1 - (e.clientY - rect.top - PAD.t * rect.height / chartH) / (IH * rect.height / chartH);
      const cy = yMin + ratioY * (yMax - yMin);
      const newRange = (yMax - yMin) * factor;
      setYView([cy - ratioY * newRange, cy + (1 - ratioY) * newRange]);
    } else {
      // Zoom X centrado en cursor
      const ratioX = (e.clientX - rect.left - PAD.l * rect.width / W) / (IW * rect.width / W);
      const cx = xMin + ratioX * (xMax - xMin);
      const newRange = (xMax - xMin) * factor;
      setXView([cx - ratioX * newRange, cx + (1 - ratioX) * newRange]);
    }
  };

  // Pan con arrastre (ambos ejes)
  const onMouseDown = (e) => {
    if (e.button === 0) dragRef.current = { sx: e.clientX, sy: e.clientY, xMin, xMax, yMin, yMax };
  };
  const onMouseMove = (e) => {
    if (!dragRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = (e.clientX - dragRef.current.sx) / (rect.width / W) / IW * (xMax - xMin);
    const dy = (e.clientY - dragRef.current.sy) / (rect.height / chartH) / IH * (yMax - yMin);
    setXView([dragRef.current.xMin - dx, dragRef.current.xMax - dx]);
    setYView([dragRef.current.yMin + dy, dragRef.current.yMax + dy]);
  };
  const onMouseUp = () => { dragRef.current = null; };

  // Resize vertical
  const onResizeStart = (e) => {
    e.preventDefault();
    const sy = e.clientY, sh = chartH;
    const mv = (ev) => setChartH(Math.max(100, Math.min(700, sh + ev.clientY - sy)));
    const up = () => { window.removeEventListener("mousemove", mv); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", mv);
    window.addEventListener("mouseup", up);
  };

  // Labels X dinámicos según zoom
  const xRange = xMax - xMin;
  const step = xRange > 300 ? 60 : xRange > 120 ? 30 : xRange > 60 ? 15 : 5;
  const timeLabels = [];
  for (let m = Math.ceil(xMin / step) * step; m <= xMax; m += step) {
    const total = m + 570, h = Math.floor(total / 60), mn = ((total % 60) + 60) % 60;
    timeLabels.push({ m, label: `${String(h).padStart(2,"0")}:${String(mn).padStart(2,"0")}` });
  }

  return (
    <div className="chart-wrap">
      <div className="chart-legend" style={{display:"flex",flexWrap:"wrap",alignItems:"center",gap:8}}>
        {tickers.map((c,i) => <span key={c.ticker} className="chart-legend-item" style={{color:HYPE_COLORS[i%HYPE_COLORS.length]}}>● {c.ticker}</span>)}
        {(xView||yView) && <button className="pin-btn" style={{marginLeft:"auto",fontSize:9}} onClick={()=>{setXView(null);setYView(null);}}>↺ reset zoom</button>}
      </div>
      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${chartH}`} className="hype-svg"
           style={{height:chartH, cursor:dragRef.current?"grabbing":"grab"}}
           onMouseDown={onMouseDown} onMouseMove={onMouseMove}
           onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
        <defs><clipPath id="chartClip"><rect x={PAD.l} y={PAD.t} width={IW} height={IH}/></clipPath></defs>
        {/* Grid Y */}
        {[0,.25,.5,.75,1].map(v => {
          const val = yMin + v * (yMax - yMin);
          const y = ys(val);
          return <g key={v}>
            <line x1={PAD.l} y1={y} x2={W-PAD.r} y2={y} stroke="#1e2d45" strokeWidth="0.5" strokeDasharray="3,3"/>
            <text x={PAD.l-3} y={y} textAnchor="end" dominantBaseline="middle" fontSize="7" fill="#4a6080">{val.toFixed(1)}</text>
          </g>;
        })}
        {/* Grid X */}
        {timeLabels.map(({m,label}) => { const x=xs(m); return <g key={m}>
          <line x1={x} y1={PAD.t} x2={x} y2={chartH-PAD.b} stroke="#1e2d45" strokeWidth="0.5" strokeDasharray="2,4"/>
          <text x={x} y={chartH-PAD.b+8} textAnchor="middle" fontSize="7" fill="#4a6080">{label}</text>
        </g>; })}
        {/* Líneas clipeadas */}
        <g clipPath="url(#chartClip)">
          {tickers.map((c,i) => {
            const visP = c.points.filter(p => p.time_min >= xMin-5 && p.time_min <= xMax+5);
            if (!visP.length) return null;
            const pts = visP.map(p=>`${xs(p.time_min).toFixed(1)},${ys(p.hype_cum).toFixed(1)}`).join(" ");
            const color = HYPE_COLORS[i%HYPE_COLORS.length];
            const last = c.points.filter(p=>p.time_min>=xMin&&p.time_min<=xMax).at(-1);
            return <g key={c.ticker}>
              <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
              {last && <circle cx={xs(last.time_min)} cy={ys(last.hype_cum)} r="2.5" fill={color}/>}
            </g>;
          })}
          {/* Primer spike por ticker */}
          {tickers.map(c => {
            const sp = c.points.find(p=>p.signal==="spike"&&p.time_min>=xMin&&p.time_min<=xMax);
            return sp ? <circle key={c.ticker} cx={xs(sp.time_min)} cy={ys(sp.hype_cum)} r="4" fill="none" stroke="#ff4466" strokeWidth="1.5"/> : null;
          })}
        </g>
        {/* Labels de ticker fuera del clip */}
        {tickers.map((c,i) => {
          const last = c.points.filter(p=>p.time_min>=xMin&&p.time_min<=xMax).at(-1);
          if (!last) return null;
          return <text key={c.ticker} x={Math.min(xs(last.time_min)+4, W-PAD.r+2)} y={ys(last.hype_cum)}
            fill={HYPE_COLORS[i%HYPE_COLORS.length]} fontSize="8" dominantBaseline="middle" fontWeight="700">{c.ticker}</text>;
        })}
      </svg>
      <div className="chart-resize-handle" onMouseDown={onResizeStart} title="Arrastrar para redimensionar"/>
    </div>
  );
}

function HypeRanking({ ranking, pinned = [], onTogglePin }) {
  if (!ranking || ranking.length === 0)
    return <div className="empty-state"><span>Sin métricas de hype</span><span className="empty-sub">Los datos se calculan tras cada snapshot</span></div>;
  return (
    <div className="table-wrap"><table>
      <thead><tr>
        <th style={{color:"#bf88ff"}}>#</th><th>TICKER</th><th>SIGNAL</th>
        <th>Δ5m</th><th>Δ15m</th><th>Δ1h</th><th>REL VOL</th><th>PRICE</th><th>Δ PRICE</th><th>SOURCE</th>
        {onTogglePin && <th>📌</th>}
      </tr></thead>
      <tbody>{ranking.map((row,i) => (
        <tr key={`${row.ticker}-${i}`} className={`ticker-row ${row.signal?"row-signal":""}`}>
          <td className="idx">{i+1}</td>
          <td className="ticker-cell" style={{color:"#bf88ff"}}>{row.ticker}</td>
          <td><SignalBadge signal={row.signal}/></td>
          <td><DeltaCell val={row.delta_5m}/></td>
          <td><DeltaCell val={row.delta_15m}/></td>
          <td><DeltaCell val={row.delta_1h}/></td>
          <td><span style={{color:parseFloat(row.rel_volume)>=2.5?"#ff4466":parseFloat(row.rel_volume)>=1.5?"#ff9f00":"#4a6080"}}>
            {row.rel_volume!=null?`${parseFloat(row.rel_volume).toFixed(2)}x`:"—"}
          </span></td>
          <td>{formatPrice(row.close_price)}</td>
          <td>{row.price_change_1m!=null?<span style={{color:row.price_change_1m>=0?"#00ff88":"#ff4466"}}>{row.price_change_1m>=0?"+":""}{parseFloat(row.price_change_1m).toFixed(2)}</span>:"—"}</td>
          <td className="vol">{row.source||"—"}</td>
          {onTogglePin && <td>
            <button className={`pin-btn ${pinned.includes(row.ticker)?"pin-active":""}`} onClick={()=>onTogglePin(row.ticker)} title={pinned.includes(row.ticker)?"Ocultar curva":"Mantener curva"}>
              {pinned.includes(row.ticker)?"📌":"○"}
            </button>
          </td>}
        </tr>
      ))}</tbody>
    </table></div>
  );
}

function SignalsFeed({ signals }) {
  if (!signals || signals.length === 0) return <div className="signals-empty">Sin señales detectadas hoy</div>;
  return (
    <div className="signals-feed">
      {signals.map((s,i) => {
        const cfg = SIGNAL_CONFIG[s.signal]||{label:s.signal,color:"#c8d8f0"};
        return <div key={i} className="signal-item">
          <span className="signal-time">{formatTs(s.timestamp)}</span>
          <span className="signal-ticker" style={{color:"#bf88ff"}}>{s.ticker}</span>
          <span className="signal-type" style={{color:cfg.color,borderColor:cfg.color}}>{cfg.label}</span>
          <span className="signal-meta">Δ5m <DeltaCell val={s.delta_5m}/> · rv {s.rel_volume!=null?`${parseFloat(s.rel_volume).toFixed(1)}x`:"—"}</span>
        </div>;
      })}
    </div>
  );
}

const DEFAULT_VISIBLE = 12;  // tickers visibles por defecto en el gráfico

function HypeView({ hype }) {
  const [subtab, setSubtab] = useState("ranking");
  const allCurveTickers = hype.curves?.tickers || [];

  // Inicializar hidden: ocultar todos excepto los primeros DEFAULT_VISIBLE
  // Solo se recalcula cuando cambia la lista de tickers (no en cada render)
  const [hidden, setHidden] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("hype_hidden") || "null");
      if (saved !== null) return saved;
    } catch {}
    return [];  // vacío hasta que tengamos datos
  });

  // Cuando llegan datos por primera vez, ocultar los tickers fuera del top DEFAULT_VISIBLE
  // Solo si el usuario no ha tocado los controles (hidden está vacío)
  const prevTickerCount = useRef(0);
  useEffect(() => {
    if (allCurveTickers.length > 0 && prevTickerCount.current === 0) {
      const saved = localStorage.getItem("hype_hidden");
      if (!saved) {
        // Primera carga: ocultar tickers más allá del top DEFAULT_VISIBLE
        const toHide = allCurveTickers.slice(DEFAULT_VISIBLE).map(c => c.ticker);
        setHidden(toHide);
        localStorage.setItem("hype_hidden", JSON.stringify(toHide));
      }
      prevTickerCount.current = allCurveTickers.length;
    }
  }, [allCurveTickers.length]);

  const toggleHide = (ticker) => {
    setHidden(prev => {
      const next = prev.includes(ticker) ? prev.filter(t => t !== ticker) : [...prev, ticker];
      localStorage.setItem("hype_hidden", JSON.stringify(next));
      return next;
    });
  };

  const visibleCount = allCurveTickers.filter(c => !hidden.includes(c.ticker)).length;

  return (
    <div className="view-content">
      <div className="subtabs">
        {[{key:"ranking",label:"RANKING"},{key:"curves",label:"CURVAS HYPE"},{key:"signals",label:`SEÑALES${hype.signals?.length>0?` (${hype.signals.length})`:""}`}]
          .map(t => <button key={t.key} className={`subtab ${subtab===t.key?"subtab-active":""}`} onClick={()=>setSubtab(t.key)}>{t.label}</button>)}
      </div>
      {subtab==="ranking" && <div className="hype-section">
        <div className="table-header"><span style={{color:"#bf88ff"}}>⬡ HYPE RANKING — Δ5m ordenado</span><span className="table-count">{hype.ranking?.length||0} tickers</span></div>
        <HypeRanking ranking={hype.ranking} hidden={hidden} onToggleHide={toggleHide}/>
      </div>}
      {subtab==="curves" && <div className="hype-section">
        <div className="table-header">
          <span style={{color:"#bf88ff"}}>⬡ CURVAS HYPE — todos los tickers del día</span>
          <span style={{display:"flex",gap:6,alignItems:"center"}}>
            <button className="pin-btn" style={{color:"#ff4466",borderColor:"#ff4466"}} onClick={async()=>{
              if(!confirm("¿Borrar todos los datos de hype de hoy y recomputar?")) return;
              await fetch(`${API}/hype/reset`,{method:"POST"});
              localStorage.removeItem("hype_hidden");
            }}>reset hoy</button>
            <span className="table-count" style={{fontSize:9,color:"#4a6080"}}>
              {visibleCount} visibles · {allCurveTickers.length} total · {hype.curves?.day||"—"}
            </span>
          </span>
        </div>
        <HypeChart curvesData={hype.curves} hiddenTickers={hidden}/>
        {allCurveTickers.length>0 && <div className="curves-table-wrap">
          <table className="curves-detail-table">
            <thead><tr><th>#</th><th>TICKER</th><th>PUNTOS</th><th>HYPE MAX</th><th>Δ5m ACTUAL</th><th>👁</th></tr></thead>
            <tbody>{allCurveTickers.map((c)=>{
              const isHidden = hidden.includes(c.ticker);
              // Color basado en posición entre los visibles
              const visibleIdx = allCurveTickers.filter(x=>!hidden.includes(x.ticker)).findIndex(x=>x.ticker===c.ticker);
              const color = isHidden ? "#2a3a50" : HYPE_COLORS[visibleIdx % HYPE_COLORS.length];
              const last=c.points[c.points.length-1], maxHype=Math.max(...c.points.map(p=>p.hype_cum));
              return <tr key={c.ticker} className={`ticker-row ${isHidden?"row-hidden":""}`}>
                <td className="idx" style={{color}}>●</td>
                <td className="ticker-cell" style={{color,opacity:isHidden?0.4:1}}>{c.ticker}</td>
                <td className="vol" style={{opacity:isHidden?0.4:1}}>{c.points.length} bars</td>
                <td style={{opacity:isHidden?0.4:1}}>{maxHype.toFixed(2)}</td>
                <td style={{opacity:isHidden?0.4:1}}><DeltaCell val={last?.delta_5m}/></td>
                <td>
                  <button className={`pin-btn ${isHidden?"":"pin-active"}`} onClick={()=>toggleHide(c.ticker)} title={isHidden?"Mostrar curva":"Ocultar curva"}>
                    {isHidden?"○":"●"}
                  </button>
                </td>
              </tr>;
            })}</tbody>
          </table>
        </div>}
        <div style={{fontSize:10,color:"#4a6080",padding:"4px 8px",display:"flex",gap:8}}>
          <button className="pin-btn pin-active" onClick={()=>{
            const toHide = allCurveTickers.slice(DEFAULT_VISIBLE).map(c=>c.ticker);
            setHidden(toHide);
            localStorage.setItem("hype_hidden", JSON.stringify(toHide));
          }}>top {DEFAULT_VISIBLE}</button>
          <button className="pin-btn" onClick={()=>{
            setHidden([]);
            localStorage.removeItem("hype_hidden");
          }}>mostrar todos</button>
          <button className="pin-btn" onClick={()=>{
            const toHide = allCurveTickers.map(c=>c.ticker);
            setHidden(toHide);
            localStorage.setItem("hype_hidden", JSON.stringify(toHide));
          }}>ocultar todos</button>
          <span style={{marginLeft:"auto"}}>{visibleCount} visibles · {allCurveTickers.length} total</span>
        </div>
      </div>}
      {subtab==="signals" && <div className="hype-section">
        <div className="table-header"><span style={{color:"#bf88ff"}}>⬡ SEÑALES DETECTADAS HOY</span><span className="table-count">{hype.signals?.length||0}</span></div>
        <SignalsFeed signals={hype.signals}/>
      </div>}
    </div>
  );
}

function IBKRBadge({ ibkr, lastHypeRefresh }) {
  if (!ibkr) return null;
  const refreshStr = lastHypeRefresh
    ? new Date(lastHypeRefresh).toLocaleTimeString("es-ES", {hour:"2-digit",minute:"2-digit",second:"2-digit"})
    : null;
  return (
    <div className={`ibkr-badge ${ibkr.connected?"connected":"disconnected"}`}
         title={ibkr.error||`${ibkr.tracked_tickers?.length||0} tickers tracked`}>
      <span className="dot"/> IBKR {ibkr.connected?`${ibkr.tracked_tickers?.length||0}T`:"OFF"}
      {refreshStr && <span className="ibkr-refresh-time"> · hype {refreshStr}</span>}
    </div>
  );
}

function ActivityLog({ logs }) {
  return (
    <div className="log-panel">
      <div className="log-header">ACTIVITY LOG</div>
      <div className="log-body">
        {(logs||[]).map((l,i)=>(
          <div key={i} className={`log-line ${l.includes("ERROR")||l.includes("✗")?"log-err":l.includes("✅")?"log-ok":l.includes("⚡")?"log-warn":""}`}>{l}</div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const { status, rows, ibkr, hype, loading, error, start, stop, snap } = useAPI();
  const [view, setView] = useState("live");
  const isRunning=status?.running, marketOpen=status?.market_open, lastSnap=status?.last_snapshot, logs=status?.logs||[];

  return (
    <div className="app">
      <div className="titlebar">
        <div className="titlebar-drag">
          <span className="app-logo">▣</span>
          <span className="app-name">FINVIZ DASHBOARD</span>
        </div>
        <div className="titlebar-nav">
          {[["live","◉ LIVE"],["hype","⬡ HYPE"],["history","◷ HISTORY"],["opportunities","▲ OPP"]].map(([v,label])=>(
            <button key={v} className={`nav-btn ${view===v?"nav-active":""}`} onClick={()=>setView(v)}>{label}</button>
          ))}
        </div>
        <div className="titlebar-right">
          <IBKRBadge ibkr={ibkr} lastHypeRefresh={status?.last_hype_refresh}/>
          <div className={`market-badge ${marketOpen?"open":"closed"}`}>
            <span className="dot"/>{marketOpen?"MARKET OPEN":"MARKET CLOSED"}
          </div>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {(view==="live"||view==="hype") && (
        <div className="controls">
          <div className="controls-left">
            <button className={`btn btn-primary ${isRunning?"active":""}`} onClick={isRunning?stop:start} disabled={!status}>
              {isRunning?"⏹ STOP":"▶ START"} SCHEDULER
            </button>
            <button className="btn btn-secondary" onClick={snap} disabled={loading}>
              {loading?"⟳ CAPTURING...":"⬡ MANUAL SNAPSHOT"}
            </button>
          </div>
          <div className="controls-right">
            {lastSnap && <span className="last-snap">Last: <strong>{formatTs(lastSnap)}</strong></span>}
            <span className="interval-badge">Every 5 min</span>
          </div>
        </div>
      )}

      <div className="main-layout">
        <div className="data-panel">
          {view==="live"          && <LiveView rows={rows}/>}
          {view==="hype"          && <HypeView hype={hype}/>}
          {view==="history"       && <HistoryView/>}
          {view==="opportunities" && <OpportunitiesView/>}
        </div>
        <ActivityLog logs={logs}/>
      </div>
    </div>
  );
}
