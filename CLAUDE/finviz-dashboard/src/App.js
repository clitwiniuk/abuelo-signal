import { useState, useEffect, useCallback } from "react";
import "./App.css";

const API = "http://127.0.0.1:5050";

const CATEGORIES = [
  { key: "top_gainers",    label: "TOP GAINERS",   accent: "#00ff88", icon: "▲" },
  { key: "new_high",       label: "NEW HIGH",       accent: "#00cfff", icon: "◆" },
  { key: "unusual_volume", label: "UNUSUAL VOLUME", accent: "#ff9f00", icon: "◉" },
];

const HYPE_COLORS = ["#00ff88","#00cfff","#ff9f00","#bf88ff","#ff4466","#44ffdd","#ffdd44","#ff88bf"];

const SIGNAL_CONFIG = {
  spike:          { label: "SPIKE",          color: "#ff4466" },
  trending:       { label: "TRENDING",       color: "#ff9f00" },
  early_momentum: { label: "EARLY MOM",      color: "#00cfff" },
};

// ------------------------------------------------------------------
// HELPERS
// ------------------------------------------------------------------

function formatChange(val) {
  if (!val) return "—";
  const n = parseFloat(String(val).replace("%", ""));
  if (isNaN(n)) return String(val);
  const color = n >= 0 ? "#00ff88" : "#ff4466";
  return <span style={{ color, fontWeight: 700 }}>{n >= 0 ? "+" : ""}{n.toFixed(2)}%</span>;
}

function formatPrice(val) {
  if (!val) return "—";
  const n = parseFloat(val);
  return isNaN(n) ? val : `$${n.toFixed(2)}`;
}

function formatVolume(val) {
  if (!val) return "—";
  const n = parseInt(String(val).replace(/,/g, ""));
  if (isNaN(n)) return val;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatTs(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch { return ts; }
}

function SignalBadge({ signal }) {
  if (!signal) return null;
  const cfg = SIGNAL_CONFIG[signal];
  if (!cfg) return null;
  return (
    <span className="signal-badge" style={{ color: cfg.color, borderColor: cfg.color }}>
      {cfg.label}
    </span>
  );
}

function DeltaCell({ val }) {
  if (val == null) return <span className="dim">—</span>;
  const n = parseFloat(val);
  if (isNaN(n)) return <span className="dim">—</span>;
  const color = n > 2 ? "#00ff88" : n > 1 ? "#ff9f00" : n > 0 ? "#c8d8f0" : "#4a6080";
  return <span style={{ color, fontWeight: n > 2 ? 700 : 400 }}>{n > 0 ? "+" : ""}{n.toFixed(2)}</span>;
}

// ------------------------------------------------------------------
// HOOK: API polling
// ------------------------------------------------------------------

function useAPI() {
  const [status, setStatus]   = useState(null);
  const [data,   setData]     = useState({ top_gainers: [], new_high: [], unusual_volume: [] });
  const [ibkr,   setIbkr]     = useState(null);
  const [hype,   setHype]     = useState({ ranking: [], curves: null, signals: [] });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/status`);
      setStatus(await r.json());
      setError(null);
    } catch {
      setError("No se puede conectar con el servidor Python");
    }
  }, []);

  const fetchLatest = useCallback(async () => {
    try {
      const results = await Promise.all(
        CATEGORIES.map(c => fetch(`${API}/data/${c.key}/latest`).then(r => r.json()))
      );
      setData({
        top_gainers:    results[0],
        new_high:       results[1],
        unusual_volume: results[2],
      });
    } catch {}
  }, []);

  const fetchIbkr = useCallback(async () => {
    try {
      const r = await fetch(`${API}/ibkr/status`);
      setIbkr(await r.json());
    } catch {}
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

  const start = async () => {
    await fetch(`${API}/start`, { method: "POST" });
    fetchStatus();
  };

  const stop = async () => {
    await fetch(`${API}/stop`, { method: "POST" });
    fetchStatus();
  };

  const snap = async () => {
    setLoading(true);
    await fetch(`${API}/snapshot`, { method: "POST" });
    setTimeout(() => { fetchLatest(); fetchHype(); setLoading(false); }, 4000);
  };

  useEffect(() => {
    fetchStatus();
    fetchLatest();
    fetchIbkr();
    fetchHype();
    const t1 = setInterval(fetchStatus, 5000);
    const t2 = setInterval(fetchLatest, 60000);
    const t3 = setInterval(fetchIbkr,  15000);
    const t4 = setInterval(fetchHype,  30000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); clearInterval(t4); };
  }, [fetchStatus, fetchLatest, fetchIbkr, fetchHype]);

  return { status, data, ibkr, hype, loading, error, start, stop, snap };
}

// ------------------------------------------------------------------
// COMPONENTE: Tabla Finviz
// ------------------------------------------------------------------

function TickerTable({ rows, accent }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="empty-state">
        <span>Sin datos disponibles</span>
        <span className="empty-sub">Inicia el scheduler o haz un snapshot manual</span>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ color: accent }}>#</th>
            <th>TICKER</th>
            <th>PRICE</th>
            <th>CHANGE%</th>
            <th>VOLUME</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.ticker}-${i}`} className="ticker-row">
              <td className="idx">{i + 1}</td>
              <td className="ticker-cell" style={{ color: accent }}>{row.ticker}</td>
              <td>{formatPrice(row.price)}</td>
              <td>{formatChange(row.change_pct)}</td>
              <td className="vol">{formatVolume(row.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE: SVG Hype Chart
// ------------------------------------------------------------------

function HypeChart({ curvesData }) {
  if (!curvesData || !curvesData.tickers || curvesData.tickers.length === 0) {
    return (
      <div className="chart-empty">
        Sin datos de hype — haz un snapshot para generar curvas
      </div>
    );
  }

  const tickers = curvesData.tickers;
  const W = 700, H = 200;
  const PAD = { t: 8, r: 80, b: 24, l: 36 };
  const IW = W - PAD.l - PAD.r;
  const IH = H - PAD.t - PAD.b;

  const allTimes = tickers.flatMap(c => c.points.map(p => p.time_min));
  const allHype  = tickers.flatMap(c => c.points.map(p => p.hype_cum));

  const xMin = allTimes.length ? Math.min(...allTimes) : 0;
  const xMax = allTimes.length ? Math.max(...allTimes) : 390;
  const yMax = Math.max(...allHype, 1);

  const xs = t  => PAD.l + ((t - xMin) / Math.max(xMax - xMin, 1)) * IW;
  const ys = h  => PAD.t + IH - (h / yMax) * IH;

  // Time axis labels (every 30 min)
  const timeLabels = [];
  for (let m = 0; m <= 390; m += 30) {
    const h = Math.floor((m + 570) / 60);
    const min = (m + 570) % 60;
    timeLabels.push({ m, label: `${String(h).padStart(2,"0")}:${String(min).padStart(2,"0")}` });
  }

  return (
    <div className="chart-wrap">
      <div className="chart-legend">
        {tickers.map((c, i) => (
          <span key={c.ticker} className="chart-legend-item" style={{ color: HYPE_COLORS[i % HYPE_COLORS.length] }}>
            ● {c.ticker}
          </span>
        ))}
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="hype-svg">
        {/* Grid horizontales */}
        {[0, 0.25, 0.5, 0.75, 1].map(v => {
          const y = ys(v * yMax);
          return (
            <g key={v}>
              <line x1={PAD.l} y1={y} x2={W - PAD.r} y2={y}
                    stroke="#1e2d45" strokeWidth="0.5" strokeDasharray="3,3" />
              <text x={PAD.l - 3} y={y} textAnchor="end" dominantBaseline="middle"
                    fontSize="7" fill="#4a6080">
                {(v * yMax).toFixed(1)}
              </text>
            </g>
          );
        })}
        {/* Grid verticales (cada 30 min) */}
        {timeLabels.map(({ m, label }) => {
          if (m < xMin || m > xMax) return null;
          const x = xs(m);
          return (
            <g key={m}>
              <line x1={x} y1={PAD.t} x2={x} y2={H - PAD.b}
                    stroke="#1e2d45" strokeWidth="0.5" strokeDasharray="2,4" />
              <text x={x} y={H - PAD.b + 8} textAnchor="middle"
                    fontSize="7" fill="#4a6080">{label}</text>
            </g>
          );
        })}
        {/* Líneas por ticker */}
        {tickers.map((c, i) => {
          if (!c.points.length) return null;
          const pts = c.points.map(p => `${xs(p.time_min).toFixed(1)},${ys(p.hype_cum).toFixed(1)}`).join(" ");
          const color = HYPE_COLORS[i % HYPE_COLORS.length];
          const last  = c.points[c.points.length - 1];
          return (
            <g key={c.ticker}>
              <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
                        strokeLinejoin="round" strokeLinecap="round" />
              {/* Punto final */}
              <circle cx={xs(last.time_min)} cy={ys(last.hype_cum)} r="2.5" fill={color} />
              {/* Label al final */}
              <text x={xs(last.time_min) + 4} y={ys(last.hype_cum)}
                    fill={color} fontSize="8" dominantBaseline="middle" fontWeight="700">
                {c.ticker}
              </text>
            </g>
          );
        })}
        {/* Spike markers */}
        {tickers.map((c) =>
          c.points
            .filter(p => p.signal === "spike")
            .map((p, j) => (
              <circle key={`${c.ticker}-${j}`}
                cx={xs(p.time_min)} cy={ys(p.hype_cum)} r="4"
                fill="none" stroke="#ff4466" strokeWidth="1.5" />
            ))
        )}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE: Hype Ranking Table
// ------------------------------------------------------------------

function HypeRanking({ ranking }) {
  if (!ranking || ranking.length === 0) {
    return (
      <div className="empty-state">
        <span>Sin métricas de hype</span>
        <span className="empty-sub">Los datos se calculan tras cada snapshot</span>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ color: "#bf88ff" }}>#</th>
            <th>TICKER</th>
            <th>SIGNAL</th>
            <th title="Delta últimos 5 min">Δ5m</th>
            <th title="Delta últimos 15 min">Δ15m</th>
            <th title="Delta última hora">Δ1h</th>
            <th title="Volumen relativo vs media">REL VOL</th>
            <th>PRICE</th>
            <th title="Cambio de precio 1 barra">Δ PRICE</th>
            <th>SOURCE</th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((row, i) => (
            <tr key={`${row.ticker}-${i}`} className={`ticker-row ${row.signal ? "row-signal" : ""}`}>
              <td className="idx">{i + 1}</td>
              <td className="ticker-cell" style={{ color: "#bf88ff" }}>{row.ticker}</td>
              <td><SignalBadge signal={row.signal} /></td>
              <td><DeltaCell val={row.delta_5m} /></td>
              <td><DeltaCell val={row.delta_15m} /></td>
              <td><DeltaCell val={row.delta_1h} /></td>
              <td>
                <span style={{ color: parseFloat(row.rel_volume) >= 2.5 ? "#ff4466" : parseFloat(row.rel_volume) >= 1.5 ? "#ff9f00" : "#4a6080" }}>
                  {row.rel_volume != null ? `${parseFloat(row.rel_volume).toFixed(2)}x` : "—"}
                </span>
              </td>
              <td>{formatPrice(row.close_price)}</td>
              <td>
                {row.price_change_1m != null
                  ? <span style={{ color: row.price_change_1m >= 0 ? "#00ff88" : "#ff4466" }}>
                      {row.price_change_1m >= 0 ? "+" : ""}{parseFloat(row.price_change_1m).toFixed(2)}
                    </span>
                  : "—"
                }
              </td>
              <td className="vol">{row.source || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE: Signals Feed
// ------------------------------------------------------------------

function SignalsFeed({ signals }) {
  if (!signals || signals.length === 0) {
    return <div className="signals-empty">Sin señales detectadas hoy</div>;
  }
  return (
    <div className="signals-feed">
      {signals.map((s, i) => {
        const cfg = SIGNAL_CONFIG[s.signal] || { label: s.signal, color: "#c8d8f0" };
        return (
          <div key={i} className="signal-item">
            <span className="signal-time">{formatTs(s.timestamp)}</span>
            <span className="signal-ticker" style={{ color: "#bf88ff" }}>{s.ticker}</span>
            <span className="signal-type" style={{ color: cfg.color, borderColor: cfg.color }}>
              {cfg.label}
            </span>
            <span className="signal-meta">
              Δ5m <DeltaCell val={s.delta_5m} /> · rv {s.rel_volume != null ? `${parseFloat(s.rel_volume).toFixed(1)}x` : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE: IBKR Status badge
// ------------------------------------------------------------------

function IBKRBadge({ ibkr }) {
  if (!ibkr) return null;
  return (
    <div className={`ibkr-badge ${ibkr.connected ? "connected" : "disconnected"}`}
         title={ibkr.error || `${ibkr.tracked_tickers?.length || 0} tickers tracked`}>
      <span className="dot" />
      IBKR {ibkr.connected
        ? `${ibkr.tracked_tickers?.length || 0}T`
        : "OFF"}
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE: Log
// ------------------------------------------------------------------

function ActivityLog({ logs }) {
  return (
    <div className="log-panel">
      <div className="log-header">ACTIVITY LOG</div>
      <div className="log-body">
        {(logs || []).map((l, i) => (
          <div key={i} className={`log-line ${l.includes("ERROR") ? "log-err" : l.includes("✅") || l.includes("Snapshot") ? "log-ok" : ""}`}>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// VISTA: LIVE (Finviz tables)
// ------------------------------------------------------------------

function LiveView({ data }) {
  const [tab, setTab] = useState("top_gainers");
  const activeCategory = CATEGORIES.find(c => c.key === tab);
  return (
    <div className="view-content">
      <div className="tabs">
        {CATEGORIES.map(c => (
          <button
            key={c.key}
            className={`tab ${tab === c.key ? "tab-active" : ""}`}
            style={tab === c.key ? { borderColor: c.accent, color: c.accent } : {}}
            onClick={() => setTab(c.key)}
          >
            <span className="tab-icon">{c.icon}</span>
            {c.label}
            {data[c.key]?.length > 0 && (
              <span className="tab-count" style={{ background: c.accent }}>
                {data[c.key].length}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="table-container">
        <div className="table-header">
          <span style={{ color: activeCategory.accent }}>
            {activeCategory.icon} {activeCategory.label}
          </span>
          <span className="table-count">{data[tab]?.length || 0} tickers</span>
        </div>
        <TickerTable rows={data[tab]} accent={activeCategory.accent} />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// VISTA: HYPE
// ------------------------------------------------------------------

function HypeView({ hype }) {
  const [subtab, setSubtab] = useState("ranking");

  return (
    <div className="view-content">
      {/* Subtabs */}
      <div className="subtabs">
        {[
          { key: "ranking", label: "RANKING" },
          { key: "curves",  label: "CURVAS HYPE" },
          { key: "signals", label: "SEÑALES" },
        ].map(t => (
          <button
            key={t.key}
            className={`subtab ${subtab === t.key ? "subtab-active" : ""}`}
            onClick={() => setSubtab(t.key)}
          >
            {t.label}
            {t.key === "signals" && hype.signals?.length > 0 && (
              <span className="signal-count">{hype.signals.length}</span>
            )}
          </button>
        ))}
      </div>

      {subtab === "ranking" && (
        <div className="hype-section">
          <div className="table-header">
            <span style={{ color: "#bf88ff" }}>⬡ HYPE RANKING — Δ5m ordenado</span>
            <span className="table-count">{hype.ranking?.length || 0} tickers</span>
          </div>
          <HypeRanking ranking={hype.ranking} />
        </div>
      )}

      {subtab === "curves" && (
        <div className="hype-section">
          <div className="table-header">
            <span style={{ color: "#bf88ff" }}>⬡ CURVAS HYPE ACUMULADO (top 8)</span>
            <span className="table-count dim" style={{ fontSize: 9 }}>
              {hype.curves?.day || "—"}
            </span>
          </div>
          <HypeChart curvesData={hype.curves} />
          {hype.curves?.tickers?.length > 0 && (
            <div className="curves-table-wrap">
              <table className="curves-detail-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>TICKER</th>
                    <th>PUNTOS</th>
                    <th>HYPE MAX</th>
                    <th>Δ5m ACTUAL</th>
                  </tr>
                </thead>
                <tbody>
                  {hype.curves.tickers.map((c, i) => {
                    const last = c.points[c.points.length - 1];
                    const maxHype = Math.max(...c.points.map(p => p.hype_cum));
                    return (
                      <tr key={c.ticker} className="ticker-row">
                        <td className="idx" style={{ color: HYPE_COLORS[i] }}>●</td>
                        <td className="ticker-cell" style={{ color: HYPE_COLORS[i] }}>{c.ticker}</td>
                        <td className="vol">{c.points.length} bars</td>
                        <td>{maxHype.toFixed(2)}</td>
                        <td><DeltaCell val={last?.delta_5m} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {subtab === "signals" && (
        <div className="hype-section">
          <div className="table-header">
            <span style={{ color: "#bf88ff" }}>⬡ SEÑALES DETECTADAS HOY</span>
            <span className="table-count">{hype.signals?.length || 0}</span>
          </div>
          <SignalsFeed signals={hype.signals} />
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE PRINCIPAL
// ------------------------------------------------------------------

export default function App() {
  const { status, data, ibkr, hype, loading, error, start, stop, snap } = useAPI();
  const [view, setView] = useState("live");

  const isRunning    = status?.running;
  const marketOpen   = status?.market_open;
  const lastSnapshot = status?.last_snapshot;
  const logs         = status?.logs || [];

  return (
    <div className="app">
      {/* TITLEBAR */}
      <div className="titlebar">
        <div className="titlebar-drag">
          <span className="app-logo">▣</span>
          <span className="app-name">FINVIZ DASHBOARD</span>
        </div>
        <div className="titlebar-nav">
          {[
            { key: "live", label: "LIVE" },
            { key: "hype", label: "HYPE" },
          ].map(v => (
            <button
              key={v.key}
              className={`nav-btn ${view === v.key ? "nav-active" : ""}`}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="titlebar-right">
          <IBKRBadge ibkr={ibkr} />
          <div className={`market-badge ${marketOpen ? "open" : "closed"}`}>
            <span className="dot" />
            {marketOpen ? "MARKET OPEN" : "MARKET CLOSED"}
          </div>
        </div>
      </div>

      {/* ERROR BANNER */}
      {error && (
        <div className="error-banner">
          ⚠ {error} — Asegúrate de que el servidor Python está corriendo
        </div>
      )}

      {/* CONTROLS */}
      <div className="controls">
        <div className="controls-left">
          <button
            className={`btn btn-primary ${isRunning ? "active" : ""}`}
            onClick={isRunning ? stop : start}
            disabled={!status}
          >
            {isRunning ? "⏹ STOP SCHEDULER" : "▶ START SCHEDULER"}
          </button>
          <button className="btn btn-secondary" onClick={snap} disabled={loading}>
            {loading ? "⟳ CAPTURING..." : "⬡ MANUAL SNAPSHOT"}
          </button>
        </div>
        <div className="controls-right">
          {lastSnapshot && (
            <span className="last-snap">
              Last snapshot: <strong>{formatTs(lastSnapshot)}</strong>
            </span>
          )}
          <span className="interval-badge">Every 5 min</span>
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div className="main-layout">
        <div className="data-panel">
          {view === "live" && <LiveView data={data} />}
          {view === "hype" && <HypeView hype={hype} />}
        </div>
        <ActivityLog logs={logs} />
      </div>
    </div>
  );
}
