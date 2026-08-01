#!/usr/bin/env python3
"""
burst_monitor.py — Monitor en tiempo real de candidatos pre-burst.

Monitoriza:
  1. SEC RSS (8-K, 13D, S-3) para tickers en la watchlist
  2. Finviz news para tickers en watchlist (via yahooquery)
  3. Alerta cuando watchlist + catalizador = setup completo

Uso:
    python burst_monitor.py              # monitorizar con watchlist de hoy
    python burst_monitor.py --interval 60  # poll cada 60s (default: 120s)
    python burst_monitor.py --test       # single poll y salir

Alertas:
    - Consola con formato claro
    - Log en burst_monitor.log
    - Guarda en watchlist.db tabla sec_alerts
"""

import asyncio
import sqlite3
import argparse
import logging
import json
import xml.etree.ElementTree as ET
import aiohttp
import sys
import signal
from datetime import date, datetime
from pathlib import Path

DB_WATCHLIST = Path(__file__).parent / 'watchlist.db'
LOG_FILE     = Path(__file__).parent / 'burst_monitor.log'

# Configurar logging: consola + fichero
handlers = [
    logging.StreamHandler(),
    logging.FileHandler(LOG_FILE),
]
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

# ── SEC RSS ──────────────────────────────────────────────────────────────────
SEC_RSS_URL    = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&count=100&output=atom"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_HEADERS    = {
    "User-Agent": "PreBurstMonitor/1.0 (trading@monitor.com)",
    "Accept-Encoding": "gzip, deflate",
}

# Tipos de filing que son catalizadores potenciales
CATALYST_FORMS   = {"8-K", "8-K/A", "13D", "13D/A", "13G", "13G/A", "SC 13D", "SC 13G"}
DILUTION_FORMS   = {"S-3", "S-3/A", "424B3", "424B4", "S-1", "S-1/A"}
WATCHOUT_FORMS   = {"DEFA14A", "DEF 14A", "14C"}  # proxy, posible reverse split

# Palabras clave en título de 8-K que elevan prioridad
HIGH_PRIORITY_KEYWORDS = [
    "agreement", "acquisition", "merger", "license", "collaboration",
    "fda", "approval", "clinical", "trial", "results", "contract",
    "partnership", "milestone", "grant", "award", "exclusive",
    "strategic", "investment", "offering", "uplisting",
]
NEGATIVE_KEYWORDS = [
    "reverse split", "reverse stock split", "going concern",
    "default", "bankruptcy", "delisting", "deregistration",
]


def _load_watchlist(today: str) -> set:
    """Carga tickers de la watchlist para hoy (y ayer si hoy está vacío)."""
    if not DB_WATCHLIST.exists():
        logger.warning("watchlist.db no existe — ejecutar watchlist_builder.py primero")
        return set()
    with sqlite3.connect(DB_WATCHLIST) as conn:
        # Intentar hoy primero, luego ayer
        for delta in [0, 1, 2]:
            d = (date.today() - __import__('datetime').timedelta(days=delta)).isoformat()
            rows = conn.execute(
                "SELECT ticker FROM watchlist WHERE date = ?", (d,)
            ).fetchall()
            if rows:
                tickers = {r[0] for r in rows}
                logger.info(f"Watchlist cargada ({d}): {len(tickers)} tickers")
                return tickers
    logger.warning("Watchlist vacía en los últimos 3 días")
    return set()


def _save_alert(ticker: str, form_type: str, title: str, filed_at: str, url: str):
    with sqlite3.connect(DB_WATCHLIST) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sec_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, date TEXT, form_type TEXT,
                title TEXT, filed_at TEXT, url TEXT,
                alerted_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO sec_alerts (ticker, date, form_type, title, filed_at, url) VALUES (?,?,?,?,?,?)",
            (ticker, date.today().isoformat(), form_type, title, filed_at, url)
        )
        conn.commit()


def _already_alerted(ticker: str, url: str) -> bool:
    if not DB_WATCHLIST.exists():
        return False
    with sqlite3.connect(DB_WATCHLIST) as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM sec_alerts WHERE ticker=? AND url=?", (ticker, url)
            ).fetchone()
            return row is not None
        except Exception:
            return False


class SECWatchlistMonitor:
    def __init__(self, watchlist: set, poll_interval: int = 120):
        self.watchlist       = watchlist
        self.poll_interval   = poll_interval
        self.cik_to_ticker   = {}
        self.seen_accessions = set()
        self.is_running      = False

    async def initialize(self):
        """Descargar mapa CIK → ticker de SEC."""
        try:
            async with aiohttp.ClientSession(headers=SEC_HEADERS) as session:
                async with session.get(SEC_TICKER_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        for entry in data.values():
                            cik = str(entry['cik_str']).zfill(10)
                            self.cik_to_ticker[cik] = entry['ticker'].upper()
                        logger.info(f"CIK map: {len(self.cik_to_ticker)} tickers cargados")
                    else:
                        logger.error(f"SEC ticker map falló: {resp.status}")
        except Exception as e:
            logger.error(f"Error cargando CIK map: {e}")

    def _extract_form_and_cik(self, title_text: str) -> tuple[str, str]:
        """Extrae form_type y CIK del título del entry RSS."""
        # Formato típico: "8-K - COMPANY NAME (0001234567) (Filer)"
        import re
        form_match = re.match(r'^([A-Z0-9/\-]+)\s*-', title_text or '')
        form_type  = form_match.group(1).strip() if form_match else 'UNKNOWN'
        cik_match  = re.search(r'\((\d{10})\)', title_text or '')
        cik        = cik_match.group(1) if cik_match else ''
        return form_type, cik

    def _classify_alert(self, form_type: str, title: str) -> tuple[str, str]:
        """Retorna (priority, emoji) para la alerta."""
        title_lower = title.lower()

        if any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
            return 'NEGATIVE', '🚨'

        if form_type in DILUTION_FORMS:
            return 'DILUTION', '⚠️'

        if form_type in {'13D', '13D/A', 'SC 13D'}:
            return 'INSIDER_BUY', '🔥'

        if form_type in {'8-K', '8-K/A'}:
            if any(kw in title_lower for kw in HIGH_PRIORITY_KEYWORDS):
                return 'HIGH', '⭐'
            return 'MEDIUM', '📋'

        return 'LOW', '📄'

    async def poll_once(self) -> list:
        """Un poll del RSS — retorna alertas para tickers en watchlist."""
        alerts = []
        try:
            async with aiohttp.ClientSession(headers=SEC_HEADERS) as session:
                async with session.get(SEC_RSS_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning(f"SEC RSS falló: {resp.status}")
                        return []
                    content = await resp.read()

            root = ET.fromstring(content)
            ns   = {'atom': 'http://www.w3.org/2005/Atom'}

            for entry in root.findall('atom:entry', ns):
                title_el   = entry.find('atom:title', ns)
                link_el    = entry.find('atom:link', ns)
                updated_el = entry.find('atom:updated', ns)

                title_text  = title_el.text  if title_el  is not None else ''
                url         = link_el.get('href', '') if link_el is not None else ''
                filed_at    = updated_el.text if updated_el is not None else ''

                # Extraer accession number del URL para deduplicar
                acc_num = url.split('/')[-1] if url else title_text
                if acc_num in self.seen_accessions:
                    continue
                self.seen_accessions.add(acc_num)

                form_type, cik = self._extract_form_and_cik(title_text)

                # ¿El CIK corresponde a un ticker en nuestra watchlist?
                ticker = self.cik_to_ticker.get(cik, '').upper()
                if not ticker or ticker not in self.watchlist:
                    continue

                # Filtrar tipos poco relevantes
                all_relevant = CATALYST_FORMS | DILUTION_FORMS | WATCHOUT_FORMS
                if form_type not in all_relevant:
                    continue

                # Evitar alertas duplicadas
                if _already_alerted(ticker, url):
                    continue

                priority, emoji = self._classify_alert(form_type, title_text)

                alert = {
                    'ticker':    ticker,
                    'form_type': form_type,
                    'title':     title_text,
                    'filed_at':  filed_at,
                    'url':       url,
                    'priority':  priority,
                    'emoji':     emoji,
                }
                alerts.append(alert)
                _save_alert(ticker, form_type, title_text, filed_at, url)

        except Exception as e:
            logger.error(f"Error en poll SEC: {e}")

        return alerts

    def _print_alert(self, alert: dict):
        """Imprime alerta formateada en consola."""
        emoji    = alert['emoji']
        ticker   = alert['ticker']
        form     = alert['form_type']
        priority = alert['priority']
        filed    = alert['filed_at'][:16] if alert['filed_at'] else '?'
        title    = alert['title'][:80]

        print()
        print(f"{'='*70}")
        print(f"  {emoji} ALERTA SEC — {ticker}  [{form}]  {priority}")
        print(f"  {title}")
        print(f"  Presentado: {filed}")
        print(f"  URL: {alert['url']}")
        print(f"{'='*70}")

        # Obtener score de watchlist para contexto
        if DB_WATCHLIST.exists():
            with sqlite3.connect(DB_WATCHLIST) as conn:
                row = conn.execute(
                    "SELECT score, flags, dist_20d_high, range_5d_pct, float_M FROM watchlist "
                    "WHERE ticker=? ORDER BY date DESC LIMIT 1", (ticker,)
                ).fetchone()
            if row:
                score, flags, d20, r5, fl = row
                print(f"  Setup T-1: score={score}  dist_20d={d20:+.0f}%  range5d={r5:.0f}%  float={fl:.0f}M")
                print(f"  Flags: {flags}")
        print()

    async def run(self, single_poll: bool = False):
        """Loop principal de monitorización."""
        self.is_running = True
        logger.info(f"Monitor iniciado — watchlist: {len(self.watchlist)} tickers, "
                    f"poll cada {self.poll_interval}s")
        logger.info(f"Tickers monitorizados: {sorted(self.watchlist)[:20]}{'...' if len(self.watchlist)>20 else ''}")

        poll_count = 0
        while self.is_running:
            poll_count += 1
            logger.info(f"[Poll #{poll_count}] Escaneando SEC RSS...")
            alerts = await self.poll_once()

            if alerts:
                for alert in alerts:
                    self._print_alert(alert)
                logger.info(f"[Poll #{poll_count}] {len(alerts)} alertas nuevas")
            else:
                logger.info(f"[Poll #{poll_count}] Sin alertas nuevas para la watchlist")

            if single_poll:
                break

            await asyncio.sleep(self.poll_interval)

    def stop(self):
        self.is_running = False


async def main_async(args):
    watchlist = _load_watchlist(date.today().isoformat())

    if not watchlist:
        logger.error("Watchlist vacía. Ejecuta watchlist_builder.py primero.")
        if not args.test:
            sys.exit(1)
        # En test mode, usar tickers de ejemplo para probar
        watchlist = {'AAPL', 'TSLA', 'NVDA', 'MSTR'}
        logger.info(f"Usando tickers de prueba: {watchlist}")

    monitor = SECWatchlistMonitor(watchlist, poll_interval=args.interval)
    await monitor.initialize()

    if not monitor.cik_to_ticker:
        logger.error("No se pudo cargar el mapa CIK. Verifica conexión a internet.")
        sys.exit(1)

    # Verificar cuántos tickers de la watchlist tienen CIK mapeado
    mapped = {t for t in watchlist if t in monitor.cik_to_ticker.values()}
    logger.info(f"Tickers con CIK mapeado: {len(mapped)}/{len(watchlist)}")

    # Handler para Ctrl+C
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, monitor.stop)

    await monitor.run(single_poll=args.test)
    logger.info("Monitor detenido.")


def main():
    parser = argparse.ArgumentParser(description='Monitor SEC para candidatos pre-burst')
    parser.add_argument('--interval', type=int, default=120, help='Segundos entre polls (default: 120)')
    parser.add_argument('--test',     action='store_true',   help='Single poll y salir')
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
