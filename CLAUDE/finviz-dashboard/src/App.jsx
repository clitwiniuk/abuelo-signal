import React, { useState, useEffect, useCallback } from "react";
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

function getColor(cat) { return CATEGORY_COLORS[cat] || "#c8d8f0"; }

function formatChange(val) {
  if (!val || val === "None") return "—";
  const n = parseFloat(String(val).replace("%",""));
  if (isNaN(n)) return val;
  const color = n >= 0 ? "#00ff88" : "#ff4466";
  return <span style={{color, fontWeight:700}}>{n>=0?"+":""}{n.toFixed(2)}%</span>;
}

function formatTs(ts) {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleTimeString("en-US", {hour:"2-digit",minute:"2-digit",hour12:false,timeZone:"America/New_York"}); }
  catch { return ts; }
}

function formatDate(d) {
  if (!d) return "—";
  try {
    const [y,m,day] = d.split("-");
    return `${day}/${m}/${y}`;
  } catch { return d; }
}

// ─── HOOKS ───────────────────────────────────────────────────────

function useAPI() {
  const [status,  setStatus]  = useState(null);
  const [rows,    setRows]    = useState([]);
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

  const start = async () => { await fetch(`${API}/start`,{method:"POST"}); fetchStatus(); };
  const stop  = async () => { await fetch(`${API}/stop`, {method:"POST"}); fetchStatus(); };
  const snap  = async () => {
    setLoading(true);
    await fetch(`${API}/snapshot`,{method:"POST"});
    setTimeout(() => { fetchData(); fetchStatus(); setLoading(false); }, 8000);
  };

  useEffect(() => {
    fetchStatus(); fetchData();
    const si = setInterval(fetchStatus, 5000);
    const di = setInterval(fetchData, 60000);
    return () => { clearInterval(si); clearInterval(di); };
  }, [fetchStatus, fetchData]);

  return { status, rows, loading, error, start, stop, snap, fetchData };
}

// ─── LIVE VIEW ───────────────────────────────────────────────────

function LiveView({ rows }) {
  const [filterCat, setFilterCat] = useState("ALL");
  const categories = ["ALL", ...Array.from(new Set(rows.map(r=>r.category))).sort()];
  const filtered = filterCat === "ALL" ? rows : rows.filter(r=>r.category===filterCat);

  return (
    <div className="view-content">
      <div className="filter-bar">
        {categories.map(cat => (
          <button key={cat}
            className={`filter-btn ${filterCat===cat?"filter-active":""}`}
            style={filterCat===cat && cat!=="ALL" ? {borderColor:getColor(cat),color:getColor(cat)} : {}}
            onClick={() => setFilterCat(cat)}>
            {cat==="ALL" ? `ALL (${rows.length})` : <>
              <span style={{color:getColor(cat)}}>●</span>
              {` ${cat} (${rows.filter(r=>r.category===cat).length})`}
            </>}
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
                <td>{row.price||"—"}</td>
                <td>{formatChange(row.change_pct)}</td>
                <td className="vol">{row.volume||"—"}</td>
                <td><span className="cat-badge" style={{borderColor:color,color}}>{row.category}</span></td>
              </tr>;
            })}</tbody>
          </table></div>
      }
    </div>
  );
}

// ─── HISTORY VIEW ─────────────────────────────────────────────────

function HistoryView() {
  const [days,         setDays]         = useState([]);
  const [selectedDay,  setSelectedDay]  = useState(null);
  const [snapshots,    setSnapshots]    = useState([]);
  const [selectedSnap, setSelectedSnap] = useState(null);
  const [snapData,     setSnapData]     = useState([]);
  const [daySummary,   setDaySummary]   = useState([]);
  const [subView,      setSubView]      = useState("snapshot"); // "snapshot" | "summary"
  const [filterCat,    setFilterCat]    = useState("ALL");

  useEffect(() => {
    fetch(`${API}/history/days`).then(r=>r.json()).then(d => {
      const safe = Array.isArray(d) ? d : [];
      setDays(safe);
      if (safe.length > 0) selectDay(safe[0]);
    }).catch(()=>{});
  }, []);

  const selectDay = async (day) => {
    setSelectedDay(day);
    setSelectedSnap(null);
    setSnapData([]);
    const [snaps, summary] = await Promise.all([
      fetch(`${API}/history/snapshots/${day}`).then(r=>r.json()),
      fetch(`${API}/history/day_summary/${day}`).then(r=>r.json()),
    ]);
    setSnapshots(snaps);
    setDaySummary(summary);
    if (snaps.length > 0) selectSnapshot(snaps[snaps.length-1]);
  };

  const selectSnapshot = async (ts) => {
    setSelectedSnap(ts);
    setFilterCat("ALL");
    const data = await fetch(`${API}/history/snapshot/${encodeURIComponent(ts)}`).then(r=>r.json());
    setSnapData(data);
  };

  const categories = ["ALL", ...Array.from(new Set(snapData.map(r=>r.category))).sort()];
  const filteredSnap = filterCat==="ALL" ? snapData : snapData.filter(r=>r.category===filterCat);

  return (
    <div className="history-layout">
      {/* Sidebar días */}
      <div className="history-sidebar">
        <div className="hsidebar-header">DÍAS</div>
        {days.map(d => (
          <button key={d} className={`hsidebar-item ${selectedDay===d?"hsidebar-active":""}`}
            onClick={() => selectDay(d)}>
            {formatDate(d)}
            {selectedDay===d && snapshots.length>0 && <span className="hsidebar-count">{snapshots.length}</span>}
          </button>
        ))}
        {days.length===0 && <div className="hsidebar-empty">Sin historial aún</div>}
      </div>

      {/* Panel principal */}
      <div className="history-main">
        {selectedDay && (
          <>
            {/* Sub-tabs */}
            <div className="subtabs">
              <button className={`subtab ${subView==="snapshot"?"subtab-active":""}`}
                onClick={() => setSubView("snapshot")}>
                ◷ SNAPSHOT POR HORA
              </button>
              <button className={`subtab ${subView==="summary"?"subtab-active":""}`}
                onClick={() => setSubView("summary")}>
                ◈ RESUMEN DEL DÍA
              </button>
            </div>

            {subView === "snapshot" && (
              <div className="snapshot-view">
                {/* Timeline de snapshots */}
                <div className="timeline">
                  {snapshots.map(ts => (
                    <button key={ts}
                      className={`timeline-btn ${selectedSnap===ts?"timeline-active":""}`}
                      onClick={() => selectSnapshot(ts)}>
                      {formatTs(ts)}
                    </button>
                  ))}
                </div>
                {/* Filtros */}
                {snapData.length > 0 && (
                  <div className="filter-bar filter-bar-sm">
                    {categories.map(cat => (
                      <button key={cat}
                        className={`filter-btn ${filterCat===cat?"filter-active":""}`}
                        style={filterCat===cat && cat!=="ALL" ? {borderColor:getColor(cat),color:getColor(cat)} : {}}
                        onClick={() => setFilterCat(cat)}>
                        {cat==="ALL" ? `ALL (${snapData.length})` : <>
                          <span style={{color:getColor(cat)}}>●</span>
                          {` ${cat} (${snapData.filter(r=>r.category===cat).length})`}
                        </>}
                      </button>
                    ))}
                  </div>
                )}
                {/* Tabla */}
                {filteredSnap.length > 0
                  ? <div className="table-wrap"><table>
                      <thead><tr><th>#</th><th>TICKER</th><th>PRICE</th><th>CHANGE %</th><th>VOLUME</th><th>CATEGORY</th></tr></thead>
                      <tbody>{filteredSnap.map((row,i) => {
                        const color = getColor(row.category);
                        return <tr key={i} className="ticker-row">
                          <td className="idx">{i+1}</td>
                          <td className="ticker-cell" style={{color}}>{row.ticker}</td>
                          <td>{row.price||"—"}</td>
                          <td>{formatChange(row.change_pct)}</td>
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
                <thead><tr>
                  <th>#</th><th>TICKER</th><th>LAST PRICE</th>
                  <th>MAX CHANGE %</th><th>MAX VOLUME</th>
                  <th>APPEARANCES</th><th>CATEGORIES</th>
                </tr></thead>
                <tbody>{daySummary.map((row,i) => (
                  <tr key={i} className="ticker-row">
                    <td className="idx">{i+1}</td>
                    <td className="ticker-cell" style={{color:"#00cfff"}}>{row.ticker}</td>
                    <td>{row.last_price||"—"}</td>
                    <td>{formatChange(row.max_change_pct)}</td>
                    <td className="vol">{row.max_volume||"—"}</td>
                    <td><span className={`appearances-badge ${row.appearances>=4?"app-high":row.appearances>=2?"app-mid":""}`}>{row.appearances}x</span></td>
                    <td className="cats-cell">{row.categories.map(c=>(
                      <span key={c} className="cat-badge cat-badge-sm" style={{borderColor:getColor(c),color:getColor(c)}}>{c}</span>
                    ))}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </>
        )}
        {!selectedDay && <div className="empty-state"><span>Selecciona un día</span></div>}
      </div>
    </div>
  );
}

// ─── OPPORTUNITIES VIEW ───────────────────────────────────────────

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
    setSelectedDay(day);
    setMinApp(min);
    const d = await fetch(`${API}/opportunities/${day}?min_appearances=${min}`).then(r=>r.json());
    setData(d);
  };

  const gainers  = data?.persistent_gainers || [];
  const climbers = data?.volume_climbers    || [];

  return (
    <div className="opp-layout">
      {/* Controls */}
      <div className="opp-controls">
        <div className="opp-controls-left">
          <span className="opp-label">DÍA:</span>
          <select className="opp-select" value={selectedDay||""} onChange={e=>loadOpportunities(e.target.value, minApp)}>
            {days.map(d=><option key={d} value={d}>{formatDate(d)}</option>)}
          </select>
          <span className="opp-label">MÍN. APARICIONES:</span>
          {[2,3,4,5].map(n=>(
            <button key={n} className={`filter-btn ${minApp===n?"filter-active":""}`}
              onClick={()=>loadOpportunities(selectedDay,n)}>{n}+</button>
          ))}
        </div>
        <div className="subtabs">
          <button className={`subtab ${subView==="gainers"?"subtab-active":""}`} onClick={()=>setSubView("gainers")}>
            ▲ TOP GAINERS PERSISTENTES ({gainers.length})
          </button>
          <button className={`subtab ${subView==="volume"?"subtab-active":""}`} onClick={()=>setSubView("volume")}>
            ◉ VOLUMEN CRECIENTE ({climbers.length})
          </button>
        </div>
      </div>

      {/* Tablas */}
      {subView==="gainers" && (
        gainers.length===0
          ? <div className="empty-state"><span>Sin gainers persistentes</span><span className="empty-sub">Necesitas más snapshots del día</span></div>
          : <div className="table-wrap"><table>
              <thead><tr><th>#</th><th>TICKER</th><th>LAST PRICE</th><th>MAX CHANGE %</th><th>APARICIONES</th><th>PRIMERA VEZ</th><th>ÚLTIMA VEZ</th></tr></thead>
              <tbody>{gainers.map((row,i)=>(
                <tr key={i} className="ticker-row">
                  <td className="idx">{i+1}</td>
                  <td className="ticker-cell" style={{color:"#00ff88"}}>{row.ticker}</td>
                  <td>{row.last_price||"—"}</td>
                  <td>{formatChange(row.max_change_pct)}</td>
                  <td><span className={`appearances-badge ${row.appearances>=4?"app-high":"app-mid"}`}>{row.appearances}x</span></td>
                  <td className="vol">{formatTs(row.first_seen)}</td>
                  <td className="vol">{formatTs(row.last_seen)}</td>
                </tr>
              ))}</tbody>
            </table></div>
      )}

      {subView==="volume" && (
        climbers.length===0
          ? <div className="empty-state"><span>Sin tickers con volumen creciente</span><span className="empty-sub">Necesitas más snapshots del día</span></div>
          : <div className="table-wrap"><table>
              <thead><tr><th>#</th><th>TICKER</th><th>PRICE</th><th>CHANGE</th><th>VOL INICIO</th><th>VOL FINAL</th><th>CRECIMIENTO</th><th>CATEGORÍAS</th></tr></thead>
              <tbody>{climbers.map((row,i)=>(
                <tr key={i} className="ticker-row">
                  <td className="idx">{i+1}</td>
                  <td className="ticker-cell" style={{color:"#fb923c"}}>{row.ticker}</td>
                  <td>{row.last_price||"—"}</td>
                  <td>{formatChange(row.last_change)}</td>
                  <td className="vol">{row.volume_start}</td>
                  <td className="vol">{row.volume_end}</td>
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

// ─── ACTIVITY LOG ─────────────────────────────────────────────────

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

// ─── MAIN APP ─────────────────────────────────────────────────────

export default function App() {
  const { status, rows, loading, error, start, stop, snap } = useAPI();
  const [view, setView] = useState("live"); // live | history | opportunities

  const isRunning  = status?.running;
  const marketOpen = status?.market_open;
  const lastSnap   = status?.last_snapshot;
  const logs       = status?.logs || [];

  return (
    <div className="app">
      {/* TITLEBAR */}
      <div className="titlebar">
        <div className="titlebar-drag">
          <span className="app-logo">▣</span>
          <span className="app-name">FINVIZ DASHBOARD</span>
        </div>
        <div className="titlebar-nav">
          {[["live","◉ LIVE"],["history","◷ HISTORY"],["opportunities","▲ OPPORTUNITIES"]].map(([v,label])=>(
            <button key={v} className={`nav-btn ${view===v?"nav-active":""}`} onClick={()=>setView(v)}>{label}</button>
          ))}
        </div>
        <div className="titlebar-right">
          <div className={`market-badge ${marketOpen?"open":"closed"}`}>
            <span className="dot"/>
            {marketOpen?"MARKET OPEN":"MARKET CLOSED"}
          </div>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* CONTROLS — solo en live */}
      {view==="live" && (
        <div className="controls">
          <div className="controls-left">
            <button className={`btn btn-primary ${isRunning?"active":""}`}
              onClick={isRunning?stop:start} disabled={!status}>
              {isRunning?"⏹ STOP":"▶ START"} SCHEDULER
            </button>
            <button className="btn btn-secondary" onClick={snap} disabled={loading}>
              {loading?"⟳ CAPTURING...":"⬡ MANUAL SNAPSHOT"}
            </button>
          </div>
          <div className="controls-right">
            {lastSnap && <span className="last-snap">Last: <strong>{formatTs(lastSnap)}</strong></span>}
            <span className="interval-badge">Every 15 min</span>
          </div>
        </div>
      )}

      {/* MAIN */}
      <div className="main-layout">
        <div className="data-panel">
          {view==="live"          && <LiveView rows={rows}/>}
          {view==="history"       && <HistoryView/>}
          {view==="opportunities" && <OpportunitiesView/>}
        </div>
        <ActivityLog logs={logs}/>
      </div>
    </div>
  );
}
