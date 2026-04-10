import React, { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";

const API = "http://127.0.0.1:5050";

const CATEGORIES = [
  { key: "top_gainers",    label: "TOP GAINERS",     accent: "#00ff88", icon: "▲" },
  { key: "new_high",       label: "NEW HIGH",         accent: "#00cfff", icon: "◆" },
  { key: "unusual_volume", label: "UNUSUAL VOLUME",   accent: "#ff9f00", icon: "◉" },
];

// ------------------------------------------------------------------
// HELPERS
// ------------------------------------------------------------------

function formatChange(val) {
  if (!val) return "—";
  const s = String(val);
  const n = parseFloat(s.replace("%", ""));
  if (isNaN(n)) return s;
  const color = n >= 0 ? "#00ff88" : "#ff4466";
  const sign  = n >= 0 ? "+" : "";
  return <span style={{ color, fontWeight: 700 }}>{sign}{n.toFixed(2)}%</span>;
}

function formatPrice(val) {
  if (!val) return "—";
  const n = parseFloat(val);
  return isNaN(n) ? val : `$${n.toFixed(2)}`;
}

function formatVolume(val) {
  if (!val) return "—";
  const s = String(val).replace(/,/g, "");
  const n = parseInt(s);
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
  } catch {
    return ts;
  }
}

// ------------------------------------------------------------------
// HOOK: API polling
// ------------------------------------------------------------------

function useAPI() {
  const [status, setStatus]   = useState(null);
  const [data,   setData]     = useState({ top_gainers: [], new_high: [], unusual_volume: [] });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/status`);
      const d = await r.json();
      setStatus(d);
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
    setTimeout(() => { fetchLatest(); setLoading(false); }, 3000);
  };

  useEffect(() => {
    fetchStatus();
    fetchLatest();
    const statusInterval = setInterval(fetchStatus, 5000);
    const dataInterval   = setInterval(fetchLatest, 60000);
    return () => { clearInterval(statusInterval); clearInterval(dataInterval); };
  }, [fetchStatus, fetchLatest]);

  return { status, data, loading, error, start, stop, snap, fetchLatest };
}

// ------------------------------------------------------------------
// COMPONENTE: Tabla de tickers
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
// COMPONENTE: Log de actividad
// ------------------------------------------------------------------

function ActivityLog({ logs }) {
  const ref = useRef(null);
  return (
    <div className="log-panel">
      <div className="log-header">ACTIVITY LOG</div>
      <div className="log-body" ref={ref}>
        {(logs || []).map((l, i) => (
          <div key={i} className={`log-line ${l.includes("ERROR") ? "log-err" : l.includes("✅") ? "log-ok" : ""}`}>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// COMPONENTE PRINCIPAL
// ------------------------------------------------------------------

export default function App() {
  const { status, data, loading, error, start, stop, snap } = useAPI();
  const [tab, setTab] = useState("top_gainers");

  const isRunning    = status?.running;
  const marketOpen   = status?.market_open;
  const lastSnapshot = status?.last_snapshot;
  const logs         = status?.logs || [];

  const activeCategory = CATEGORIES.find(c => c.key === tab);

  return (
    <div className="app">
      {/* TITLEBAR */}
      <div className="titlebar">
        <div className="titlebar-drag">
          <span className="app-logo">▣</span>
          <span className="app-name">FINVIZ DASHBOARD</span>
        </div>
        <div className="titlebar-right">
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
          <span className="interval-badge">Every 15 min</span>
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div className="main-layout">
        {/* LEFT: TABS + TABLE */}
        <div className="data-panel">
          {/* TABS */}
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

          {/* TABLE */}
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

        {/* RIGHT: LOG */}
        <ActivityLog logs={logs} />
      </div>
    </div>
  );
}
