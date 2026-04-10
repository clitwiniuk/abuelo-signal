"""
=============================================================
  IBKR Data Service
  Fetches 1-min OHLCV bars for tracked tickers via TWS
  Runs in a background thread, optional (graceful if TWS down)
=============================================================
"""
import asyncio
import sqlite3
import threading
import logging
from datetime import datetime

import pytz

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

TWS_PORT   = 7497   # TWS paper/live gateway port
CLIENT_ID  = 5055   # Must not conflict with trading system (5001, 5099)
MAX_TICKERS = 40


class IBKRDataService:
    def __init__(self, db_path: str, on_bars_saved=None, on_status_change=None):
        self.db_path  = db_path
        self.connected = False
        self.last_fetch: datetime | None = None
        self.error_msg: str | None = None
        self._on_bars_saved    = on_bars_saved     # callback tras guardar bars
        self._on_status_change = on_status_change  # callback(msg: str) para UI log

        self._tracked: set[str] = set()
        self._lock    = threading.Lock()
        self._ib      = None
        self._loop    = asyncio.new_event_loop()
        self._thread  = threading.Thread(target=self._run, daemon=True, name="ibkr-svc")

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def start(self):
        self._thread.start()
        log.info("IBKRDataService thread started")

    def add_tickers(self, tickers: list[str]):
        with self._lock:
            for t in tickers:
                if len(self._tracked) < MAX_TICKERS:
                    self._tracked.add(t)

    def get_status(self) -> dict:
        with self._lock:
            tracked = sorted(self._tracked)
        return {
            "connected":       self.connected,
            "tracked_tickers": tracked,
            "last_fetch":      self.last_fetch.isoformat() if self.last_fetch else None,
            "error":           self.error_msg,
        }

    # ------------------------------------------------------------------
    # INTERNAL LOOP
    # ------------------------------------------------------------------

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main_loop())

    async def _main_loop(self):
        try:
            from ib_insync import IB
        except ImportError:
            log.warning("ib_insync not installed — IBKR service disabled")
            self.error_msg = "ib_insync not installed"
            return

        self._ib = IB()
        try:
            from ib_insync import util
            util.patchAsyncio()
        except Exception:
            pass

        while True:
            if not self.connected:
                try:
                    await self._ib.connectAsync("127.0.0.1", TWS_PORT, clientId=CLIENT_ID, timeout=10)
                    self.connected = True
                    self.error_msg = None
                    msg = f"IBKR conectado (clientId={CLIENT_ID}, port={TWS_PORT})"
                    log.info(msg)
                    if self._on_status_change: self._on_status_change(f"✅ {msg}")
                except Exception as e:
                    self.error_msg = str(e)
                    log.warning(f"IBKR not available: {e}")
                    if self._on_status_change: self._on_status_change(f"✗ IBKR no disponible: {e}")
                    await asyncio.sleep(60)
                    continue

            try:
                await self._fetch_all_bars()
                self.last_fetch = datetime.now(ET)
            except Exception as e:
                log.error(f"IBKR fetch error: {e}")
                self.error_msg = str(e)
                self.connected = False
                try:
                    self._ib.disconnect()
                except Exception:
                    pass

            await asyncio.sleep(60)  # fetch every minute

    async def _fetch_all_bars(self):
        from ib_insync import Stock

        with self._lock:
            tickers = list(self._tracked)

        if not tickers:
            log.info("IBKR fetch_all_bars: no tickers tracked yet")
            return

        log.info(f"IBKR fetching bars for {len(tickers)} tickers: {tickers[:10]}{'...' if len(tickers)>10 else ''}")
        saved_count = 0
        BATCH = 5  # peticiones simultáneas — respetar límites IBKR

        async def _fetch_one(symbol: str) -> bool:
            try:
                contract = Stock(symbol, "SMART", "USD")
                bars = await asyncio.wait_for(
                    self._ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime="",
                        durationStr="1 D",
                        barSizeSetting="1 min",
                        whatToShow="TRADES",
                        useRTH=False,
                        keepUpToDate=False,
                    ),
                    timeout=12,
                )
                if bars:
                    self._save_bars(symbol, bars)
                    log.debug(f"  {symbol}: {len(bars)} bars saved")
                    return True
                log.debug(f"  {symbol}: 0 bars")
                return False
            except asyncio.TimeoutError:
                log.debug(f"  {symbol}: timeout")
                return False
            except Exception as e:
                log.debug(f"  {symbol}: {e}")
                return False

        # Procesar en batches de BATCH tickers en paralelo
        for i in range(0, len(tickers), BATCH):
            batch = tickers[i:i + BATCH]
            results = await asyncio.gather(*[_fetch_one(s) for s in batch])
            saved_count += sum(results)
            await asyncio.sleep(0.5)  # pausa entre batches

        log.info(f"IBKR fetch complete: {saved_count}/{len(tickers)} tickers had data")

        if self._on_status_change:
            self._on_status_change(f"⚡ IBKR: {saved_count}/{len(tickers)} tickers con bars")
        if saved_count > 0 and self._on_bars_saved:
            try:
                self._on_bars_saved()
            except Exception as e:
                log.warning(f"on_bars_saved callback error: {e}")

    def _save_bars(self, symbol: str, bars):
        conn = sqlite3.connect(self.db_path)
        for bar in bars:
            try:
                dt = bar.date
                if hasattr(dt, "strftime"):
                    bar_time = dt.astimezone(ET).strftime("%Y-%m-%dT%H:%M:%S")
                else:
                    bar_time = str(dt)
                vwap = getattr(bar, "average", None)
                conn.execute(
                    """INSERT OR REPLACE INTO market_bars
                           (bar_time, ticker, open, high, low, close, volume, vwap)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (bar_time, symbol, bar.open, bar.high, bar.low,
                     bar.close, bar.volume, vwap),
                )
            except Exception as e:
                log.warning(f"Save bar error {symbol}: {e}")
        conn.commit()
        conn.close()
