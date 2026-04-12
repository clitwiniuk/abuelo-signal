"""
=============================================================
  FINVIZ SNAPSHOT + HYPE ENGINE - Backend Python
  Scraping finviz.com cada 5 minutos + análisis hype intradía
  API local en http://localhost:5050
=============================================================
  Dependencias:
    pip install fastapi uvicorn pytz pandas requests beautifulsoup4
  Opcional (barras IBKR):
    pip install ib_insync
=============================================================
"""

import json
import math
import sqlite3
import logging
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from ibkr_service import IBKRDataService

def df_records(df):
    """Convierte DataFrame a lista de dicts reemplazando NaN/Inf por None."""
    return json.loads(df.to_json(orient="records"))

def safe_float(val, default=0.0, decimals=None):
    """Convierte val a float seguro (None si NaN/Inf), con redondeo opcional."""
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, decimals) if decimals is not None else v
    except (TypeError, ValueError):
        return default
from hype_engine import compute_hype

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------

_APP_DATA_DIR = Path.home() / "Library" / "Application Support" / "finviz-dashboard"
_APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH      = str(_APP_DATA_DIR / "finviz_snapshots.db")
INTERVAL_SEC = 5 * 60   # 5 minutos
ET_TIMEZONE  = pytz.timezone("America/New_York")
MARKET_OPEN  = (9, 30)
MARKET_CLOSE = (16, 0)

FINVIZ_URL = "https://finviz.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

KNOWN_CATEGORIES = {
    "top gainers", "top losers", "new high", "new low",
    "most volatile", "most active", "unusual volume",
    "overbought", "oversold", "downgrades", "upgrades",
    "earnings before", "earnings after",
    "recent insider buying", "recent insider selling",
    "insider buying", "insider selling",
}

scheduler_status = {
    "running":       False,
    "last_snapshot": None,
    "market_open":   False,
    "logs":          [],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

def _on_ibkr_bars_saved():
    """Callback: se llama cada vez que IBKR termina de guardar bars (cada ~60s)."""
    try:
        compute_hype(DB_PATH)
        scheduler_status["last_hype_refresh"] = datetime.now(ET_TIMEZONE).isoformat()
        add_log(f"⚡ Hype actualizado (IBKR bars)")
        log.info("Hype recalculado tras fetch IBKR")
    except Exception as e:
        log.warning(f"Hype recompute error: {e}")

ibkr_svc = IBKRDataService(DB_PATH, on_bars_saved=_on_ibkr_bars_saved, on_status_change=lambda msg: add_log(msg))

# ------------------------------------------------------------------
# FASTAPI APP
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    # Pre-cargar tickers del día desde la DB (funciona aunque el mercado esté cerrado)
    try:
        day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM snapshots WHERE timestamp LIKE ?", (f"{day}%",)
        ).fetchall()
        conn.close()
        if rows:
            tickers = [r[0] for r in rows]
            ibkr_svc.add_tickers(tickers)
            add_log(f"Tickers cargados desde DB: {len(tickers)}")
    except Exception as e:
        add_log(f"WARN: no se pudieron cargar tickers: {e}")
    ibkr_svc.start()
    add_log("Servidor iniciado")
    yield

app = FastAPI(title="Finviz Snapshot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# BASE DE DATOS
# ------------------------------------------------------------------

def create_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            category   TEXT NOT NULL,
            ticker     TEXT NOT NULL,
            price      TEXT,
            change_pct TEXT,
            volume     TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_bars (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            bar_time TEXT NOT NULL,
            ticker   TEXT NOT NULL,
            open     REAL,
            high     REAL,
            low      REAL,
            close    REAL,
            volume   INTEGER,
            vwap     REAL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bars_ticker_time
        ON market_bars(ticker, bar_time)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hype_metrics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            ticker          TEXT NOT NULL,
            volume_1m       INTEGER,
            rel_volume      REAL,
            hype_cum        REAL,
            delta_5m        REAL,
            delta_15m       REAL,
            delta_1h        REAL,
            close_price     REAL,
            price_change_1m REAL,
            signal          TEXT,
            finviz_category TEXT,
            source          TEXT DEFAULT 'finviz'
        )
    """)
    # Migración: asegurar que el índice (ticker, timestamp) es UNIQUE
    # Si existe como no-único, lo borramos para recrearlo como único
    try:
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_hype_ticker_ts'"
        ).fetchone()
        if existing:
            # Verificar si ya es único
            is_unique = conn.execute(
                "SELECT \"unique\" FROM pragma_index_list('hype_metrics') WHERE name='idx_hype_ticker_ts'"
            ).fetchone()
            if is_unique and not is_unique[0]:
                conn.execute("DROP INDEX idx_hype_ticker_ts")
    except Exception:
        pass

    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hype_ticker_ts
        ON hype_metrics(ticker, timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_hype_ts
        ON hype_metrics(timestamp)
    """)

    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def add_log(msg: str):
    now = datetime.now(ET_TIMEZONE).strftime("%H:%M:%S")
    scheduler_status["logs"].insert(0, f"{now}  {msg}")
    if len(scheduler_status["logs"]) > 200:
        scheduler_status["logs"] = scheduler_status["logs"][:200]
    log.info(msg)

def is_market_open() -> bool:
    now_et = datetime.now(ET_TIMEZONE)
    if now_et.weekday() >= 5:
        return False
    mins = now_et.hour * 60 + now_et.minute
    return (MARKET_OPEN[0]*60 + MARKET_OPEN[1]) <= mins < (MARKET_CLOSE[0]*60 + MARKET_CLOSE[1])

def parse_change(v):
    try: return float(str(v).replace("%","").replace("+",""))
    except: return 0.0

def parse_volume(v):
    if not v: return 0.0
    s = str(v).upper().replace(",","")
    try:
        if s.endswith("B"): return float(s[:-1]) * 1_000_000_000
        if s.endswith("M"): return float(s[:-1]) * 1_000_000
        if s.endswith("K"): return float(s[:-1]) * 1_000
        return float(s)
    except: return 0.0

# ------------------------------------------------------------------
# SCRAPING
# ------------------------------------------------------------------

def fetch_homepage() -> list:
    try:
        resp = requests.get(FINVIZ_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        add_log(f"ERROR descargando finviz.com: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    target_table = None

    for t in soup.find_all("table"):
        for tr in t.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) >= 6 and cells[5].lower() in KNOWN_CATEGORIES:
                target_table = t
                break
        if target_table:
            break

    if not target_table:
        add_log("ERROR: No se encontró la tabla en finviz.com")
        return []

    for tr in target_table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 6:
            continue
        if cells[5].lower() not in KNOWN_CATEGORIES:
            continue
        try:
            float(cells[1].replace(",", ""))
        except ValueError:
            continue
        results.append({
            "ticker":     cells[0],
            "price":      cells[1],
            "change_pct": cells[2],
            "volume":     cells[3],
            "category":   cells[5],
        })

    return results

# ------------------------------------------------------------------
# GUARDAR EN SQLITE
# ------------------------------------------------------------------

def save_rows(rows: list, timestamp: str) -> int:
    if not rows:
        return 0
    conn = sqlite3.connect(DB_PATH)
    for r in rows:
        conn.execute(
            "INSERT INTO snapshots (timestamp, category, ticker, price, change_pct, volume) "
            "VALUES (?,?,?,?,?,?)",
            (timestamp, r["category"], r["ticker"], r["price"], r["change_pct"], r["volume"])
        )
    conn.commit()
    conn.close()
    return len(rows)

# ------------------------------------------------------------------
# SNAPSHOT + HYPE
# ------------------------------------------------------------------

def run_snapshot(force: bool = False):
    market = is_market_open()
    scheduler_status["market_open"] = market

    if not market and not force:
        add_log("Mercado cerrado — snapshot omitido")
        # Aun así, mantener IBKR actualizado con tickers del día (aftermarket)
        try:
            day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
            conn = sqlite3.connect(DB_PATH)
            rows_db = conn.execute(
                "SELECT DISTINCT ticker FROM snapshots WHERE timestamp LIKE ?", (f"{day}%",)
            ).fetchall()
            conn.close()
            if rows_db:
                ibkr_svc.add_tickers([r[0] for r in rows_db])
        except Exception:
            pass
        return

    timestamp = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%dT%H:%M:%S%z")
    add_log(f"{'Manual' if force and not market else 'Auto'} — {timestamp}")

    rows = fetch_homepage()
    if not rows:
        add_log("Sin datos de Finviz")
        return

    for cat, n in sorted(Counter(r["category"] for r in rows).items()):
        add_log(f"  {cat}: {n}")

    total = save_rows(rows, timestamp)
    scheduler_status["last_snapshot"] = timestamp
    add_log(f"Snapshot: {total} registros guardados")

    # Pasar tickers nuevos al servicio IBKR
    tickers = list({r["ticker"] for r in rows})
    ibkr_svc.add_tickers(tickers)

    # Calcular métricas hype
    try:
        compute_hype(DB_PATH)
        scheduler_status["last_hype_refresh"] = datetime.now(ET_TIMEZONE).isoformat()
        add_log(f"Hype calculado para {len(tickers)} tickers")
    except Exception as e:
        add_log(f"ERROR hype: {e}")

# ------------------------------------------------------------------
# SCHEDULER
# ------------------------------------------------------------------

def scheduler_loop():
    while scheduler_status["running"]:
        run_snapshot()
        for _ in range(INTERVAL_SEC * 2):
            if not scheduler_status["running"]:
                break
            time.sleep(0.5)

# ------------------------------------------------------------------
# ENDPOINTS — LIVE (existentes)
# ------------------------------------------------------------------

@app.get("/status")
def get_status():
    return scheduler_status

@app.post("/start")
def start_scheduler():
    if scheduler_status["running"]:
        return {"ok": False, "msg": "Ya está corriendo"}
    scheduler_status["running"] = True
    threading.Thread(target=scheduler_loop, daemon=True).start()
    add_log("Scheduler iniciado")
    return {"ok": True}

@app.post("/stop")
def stop_scheduler():
    scheduler_status["running"] = False
    add_log("Scheduler detenido")
    return {"ok": True}

@app.post("/snapshot")
def manual_snapshot():
    threading.Thread(target=lambda: run_snapshot(force=True), daemon=True).start()
    return {"ok": True}

@app.post("/hype/reset")
def reset_hype():
    """Borra solo hype_metrics de hoy (mantiene market_bars) y recomputa desde cero."""
    day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    deleted = conn.execute("DELETE FROM hype_metrics WHERE timestamp LIKE ?", (f"{day}%",)).rowcount
    conn.commit()
    conn.close()
    add_log(f"Hype reset: {deleted} filas borradas, recomputando...")
    try:
        compute_hype(DB_PATH)
        add_log("✅ Hype recomputado desde cero")
    except Exception as e:
        add_log(f"ERROR recompute: {e}")
    return {"ok": True, "day": day}

@app.get("/data/latest")
def get_latest_all():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT timestamp FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return []
    ts = row[0]
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, price, change_pct, volume, category FROM snapshots WHERE timestamp=? ORDER BY category, id",
        conn, params=(ts,)
    )
    conn.close()
    return df_records(df)

@app.get("/data/{category}/latest")
def get_latest_category(category: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT timestamp FROM snapshots WHERE category=? ORDER BY id DESC LIMIT 1", (category,)
    ).fetchone()
    conn.close()
    if not row:
        return []
    ts = row[0]
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, price, change_pct, volume, category FROM snapshots WHERE category=? AND timestamp=? ORDER BY id",
        conn, params=(category, ts)
    )
    conn.close()
    return df_records(df)

# ------------------------------------------------------------------
# ENDPOINTS — HISTORY (existentes)
# ------------------------------------------------------------------

@app.get("/history/days")
def get_days():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT substr(timestamp, 1, 10) as day FROM snapshots ORDER BY day DESC LIMIT 60"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

@app.get("/history/snapshots/{day}")
def get_snapshots_for_day(day: str):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM snapshots WHERE timestamp LIKE ? ORDER BY timestamp ASC",
        (f"{day}%",)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

@app.get("/history/snapshot/{timestamp:path}")
def get_snapshot_at(timestamp: str):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, price, change_pct, volume, category FROM snapshots WHERE timestamp=? ORDER BY category, id",
        conn, params=(timestamp,)
    )
    conn.close()
    return df_records(df)

@app.get("/history/day_summary/{day}")
def get_day_summary(day: str):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, price, change_pct, volume, category, timestamp FROM snapshots WHERE timestamp LIKE ? ORDER BY ticker, timestamp",
        conn, params=(f"{day}%",)
    )
    conn.close()
    if df.empty:
        return []

    df["change_num"] = df["change_pct"].apply(parse_change)
    df["volume_num"] = df["volume"].apply(parse_volume)

    summary = []
    for ticker, group in df.groupby("ticker"):
        idx_max_change = group["change_num"].idxmax()
        idx_max_volume = group["volume_num"].idxmax()
        summary.append({
            "ticker":         ticker,
            "appearances":    len(group["timestamp"].unique()),
            "max_change_pct": group.loc[idx_max_change, "change_pct"],
            "max_change_num": round(group["change_num"].max(), 2),
            "max_volume":     group.loc[idx_max_volume, "volume"],
            "max_volume_num": group["volume_num"].max(),
            "last_price":     group.iloc[-1]["price"],
            "categories":     group["category"].unique().tolist(),
            "first_seen":     group["timestamp"].min(),
            "last_seen":      group["timestamp"].max(),
        })

    summary.sort(key=lambda x: x["max_change_num"], reverse=True)
    return summary

@app.get("/history/export_csv")
def export_all_snapshots_csv():
    """Export all snapshots from all days as a CSV file download."""
    import io
    from fastapi.responses import StreamingResponse
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT timestamp, category, ticker, price, change_pct, volume FROM snapshots ORDER BY timestamp, category, ticker",
        conn
    )
    conn.close()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = f"finviz_snapshots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/opportunities/{day}")
def get_opportunities(day: str, min_appearances: int = 2):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, price, change_pct, volume, category, timestamp FROM snapshots WHERE timestamp LIKE ? ORDER BY ticker, timestamp",
        conn, params=(f"{day}%",)
    )
    conn.close()
    if df.empty:
        return {"persistent_gainers": [], "volume_climbers": []}

    df["change_num"] = df["change_pct"].apply(parse_change)
    df["volume_num"] = df["volume"].apply(parse_volume)

    gainers_df = df[df["category"] == "Top Gainers"]
    persistent = []
    for ticker, group in gainers_df.groupby("ticker"):
        n = len(group["timestamp"].unique())
        if n >= min_appearances:
            max_idx = group["change_num"].argmax()
            persistent.append({
                "ticker":         ticker,
                "appearances":    n,
                "max_change_pct": group.iloc[max_idx]["change_pct"],
                "max_change_num": round(group["change_num"].max(), 2),
                "last_price":     group.iloc[-1]["price"],
                "first_seen":     group["timestamp"].min(),
                "last_seen":      group["timestamp"].max(),
            })
    persistent.sort(key=lambda x: (x["appearances"], x["max_change_num"]), reverse=True)

    climbers = []
    for ticker, group in df.groupby("ticker"):
        by_ts = group.groupby("timestamp")["volume_num"].max().reset_index().sort_values("timestamp")
        if len(by_ts) < min_appearances:
            continue
        volumes = by_ts["volume_num"].tolist()
        growth_pct = ((volumes[-1] - volumes[0]) / volumes[0] * 100) if volumes[0] > 0 else 0
        if growth_pct > 0:
            last_row = group.iloc[-1]
            climbers.append({
                "ticker":            ticker,
                "volume_start":      group[group["timestamp"] == by_ts.iloc[0]["timestamp"]].iloc[0]["volume"],
                "volume_end":        group[group["timestamp"] == by_ts.iloc[-1]["timestamp"]].iloc[0]["volume"],
                "volume_growth_pct": round(growth_pct, 1),
                "last_price":        last_row["price"],
                "last_change":       last_row["change_pct"],
                "appearances":       len(by_ts),
                "categories":        group["category"].unique().tolist(),
                "first_seen":        group["timestamp"].min(),
                "last_seen":         group["timestamp"].max(),
            })
    climbers.sort(key=lambda x: x["volume_growth_pct"], reverse=True)

    return {"persistent_gainers": persistent, "volume_climbers": climbers[:20]}

# ------------------------------------------------------------------
# ENDPOINTS — HYPE (nuevos)
# ------------------------------------------------------------------

@app.get("/ibkr/status")
def get_ibkr_status():
    return ibkr_svc.get_status()

@app.get("/hype/ranking")
def get_hype_ranking():
    """Ranking actual de tickers por delta_5m (última métrica de cada ticker hoy)."""
    day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT h.ticker, h.rel_volume, h.hype_cum,
                  h.delta_5m, h.delta_15m, h.delta_1h,
                  h.close_price, h.price_change_1m,
                  h.signal, h.finviz_category, h.source, h.timestamp
           FROM hype_metrics h
           INNER JOIN (
               SELECT ticker, MAX(timestamp) AS max_ts
               FROM hype_metrics WHERE timestamp LIKE ?
               GROUP BY ticker
           ) latest ON h.ticker = latest.ticker AND h.timestamp = latest.max_ts
           ORDER BY h.delta_5m IS NULL, h.delta_5m DESC""",
        conn, params=(f"{day}%",)
    )
    conn.close()
    return df_records(df)

@app.get("/hype/curves")
def get_hype_curves(limit: int = 20):
    """
    Devuelve series temporales de hype_cum para TODOS los tickers del día,
    ordenados por pico máximo de hype_cum (los más activos primero).
    El campo 'tickers' tiene todos; el cliente decide cuáles mostrar.
    """
    day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)

    # Todos los tickers con actividad hoy, ordenados por peak_hype
    ranked = pd.read_sql(
        """SELECT ticker, MAX(hype_cum) AS peak_hype
           FROM hype_metrics
           WHERE timestamp LIKE ?
           GROUP BY ticker
           ORDER BY peak_hype DESC""",
        conn, params=(f"{day}%",)
    )

    if ranked.empty:
        conn.close()
        return {"day": day, "tickers": [], "top_limit": limit}

    all_tickers = ranked["ticker"].tolist()
    placeholders = ",".join("?" * len(all_tickers))

    df = pd.read_sql(
        f"""SELECT ticker, timestamp, hype_cum, delta_5m, rel_volume, close_price, signal
            FROM hype_metrics
            WHERE timestamp LIKE ? AND ticker IN ({placeholders})
            ORDER BY ticker, timestamp""",
        conn, params=[f"{day}%"] + all_tickers
    )
    conn.close()

    result = []
    market_open_min = 9 * 60 + 30

    for ticker in all_tickers:
        sub = df[df["ticker"] == ticker]
        points = []
        for _, row in sub.iterrows():
            try:
                ts = row["timestamp"]
                # bar_time from IBKR is already stored as naive ET string —
                # avoid astimezone() which would misinterpret it as local tz
                t = datetime.fromisoformat(ts[:19])
                time_min = t.hour * 60 + t.minute - market_open_min
                # Skip premarket bars before 9:00 ET (time_min < -30)
                if time_min < -30:
                    continue
                points.append({
                    "time_min":  time_min,
                    "time_str":  t.strftime("%H:%M"),
                    "hype_cum":  safe_float(row["hype_cum"], decimals=3),
                    "delta_5m":  safe_float(row["delta_5m"], decimals=3),
                    "rel_vol":   safe_float(row["rel_volume"], decimals=2),
                    "close":     safe_float(row["close_price"], decimals=2),
                    "signal":    row["signal"] if row["signal"] and str(row["signal"]) != "nan" else None,
                })
            except Exception:
                continue
        if points:
            result.append({"ticker": ticker, "points": points})

    return {"day": day, "tickers": result, "top_limit": limit}

@app.get("/hype/signals")
def get_hype_signals(limit: int = 50):
    """Señales detectadas hoy (spike, trending, early_momentum)."""
    day = datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT ticker, timestamp, signal, rel_volume, delta_5m,
                  close_price, price_change_1m, finviz_category
           FROM hype_metrics
           WHERE timestamp LIKE ? AND signal IS NOT NULL
           ORDER BY timestamp DESC
           LIMIT ?""",
        conn, params=(f"{day}%", limit)
    )
    conn.close()
    return df_records(df)

@app.get("/hype/history/{ticker}")
def get_ticker_hype_history(ticker: str, days: int = 5):
    """Histórico de métricas hype para un ticker específico (últimos N días)."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT timestamp, rel_volume, hype_cum, delta_5m, delta_15m, delta_1h,
                  close_price, price_change_1m, signal, source
           FROM hype_metrics
           WHERE ticker=?
           ORDER BY timestamp DESC
           LIMIT ?""",
        conn, params=(ticker.upper(), days * 100)
    )
    conn.close()
    return df_records(df)

# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5050, log_level="warning")
