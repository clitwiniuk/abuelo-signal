"""
edgar_loader.py — Carga filings de EDGAR/SEC para análisis de precursores de burst.

API utilizada: EDGAR REST API (pública, sin API key).
  - company_tickers.json  → ticker → CIK mapping
  - submissions/{CIK}.json → historial de filings de una empresa
  - Rate limit oficial: 10 req/s → se usan semáforos para respetar el límite

Todas las respuestas se cachean en edgar_cache/ para evitar re-descargas.
El caché de CIK map se regenera cada 7 días; el de submissions por empresa,
cada 24h (los filings recientes pueden actualizarse durante el día).

Uso típico:
    from helpers.edgar_loader import EdgarLoader
    loader = EdgarLoader()
    filings = loader.get_filings_before_burst("AAPL", "2026-04-10", days_lookback=7)
"""

import asyncio
import concurrent.futures
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """
    Ejecuta una coroutine de forma segura tanto en scripts como en Jupyter.

    Jupyter tiene un event loop ya corriendo — asyncio.run() falla en ese contexto.
    Solución: detectar si hay loop activo y, si es así, ejecutar en un thread
    separado con su propio loop (siempre disponible, sin dependencias extra).
    """
    try:
        asyncio.get_running_loop()
        # Hay un loop corriendo (Jupyter u otro contexto async)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No hay loop corriendo — uso normal de asyncio.run()
        return asyncio.run(coro)

# ── Constantes ──────────────────────────────────────────────────────────────

EDGAR_BASE        = "https://data.sec.gov"
EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT        = "BurstPrecursorAnalysis research@trading-research.com"
MAX_RPS           = 8          # requests per second (oficial: 10, usamos 8 por margen)
CACHE_DIR         = Path(__file__).parents[1] / "edgar_cache"
CIK_MAP_TTL_DAYS  = 7
SUBMISSIONS_TTL_H = 24

# Mapeo de tipos de filing a categorías de catalizador
FORM_TYPE_CATEGORY = {
    # Eventos materiales (8-K por items)
    "8-K":     "material_event",
    "8-K/A":   "material_event",
    # Offerings / dilución
    "S-1":     "offering",
    "S-1/A":   "offering",
    "S-3":     "offering",
    "S-3/A":   "offering",
    "S-3ASR":  "offering",
    "424B1":   "offering",
    "424B2":   "offering",
    "424B3":   "offering",
    "424B4":   "offering",
    "424B5":   "offering",
    # Foreign private issuers (equivalentes a S-1/S-3, comunes en microcaps
    # chinos/israelies -- ver analysis/dump_reversal_research)
    "F-1":     "offering",
    "F-1/A":   "offering",
    "F-3":     "offering",
    "F-3/A":   "offering",
    "F-3ASR":  "offering",
    "6-K":     "material_event",
    # Insider transactions
    "4":       "insider_transaction",
    "4/A":     "insider_transaction",
    # Grandes accionistas
    "SC 13G":  "large_holder",
    "SC 13G/A":"large_holder",
    "SC 13D":  "large_holder",
    "SC 13D/A":"large_holder",
}

# Items de 8-K y su significado
ITEM_CATEGORY = {
    "1.01": "material_agreement",
    "1.02": "material_agreement_terminated",
    "2.01": "asset_acquisition",
    "2.02": "earnings",
    "2.03": "debt_obligation",
    "2.05": "cost_associated_exit",
    "2.06": "asset_impairment",
    "3.01": "exchange_delisting",
    "4.01": "auditor_change",
    "5.01": "change_of_control",
    "5.02": "director_officer_change",
    "5.03": "charter_amendment",
    "7.01": "regulation_fd",
    "8.01": "other_event",        # press releases, FDA, partnerships, etc.
    "9.01": "financial_exhibits",
}

# Items de alto impacto para small caps (usados en classify_filing)
HIGH_IMPACT_ITEMS = {"1.01", "2.01", "2.02", "5.01", "7.01", "8.01"}

# Keywords FDA en texto de filing
FDA_KEYWORDS = {
    "fda", "ind ", "nda ", "bla ", "anda", "510(k)", "pdufa",
    "clinical trial", "phase 1", "phase 2", "phase 3",
    "approval", "clearance", "breakthrough therapy",
}


# ── Clase principal ──────────────────────────────────────────────────────────

class EdgarLoader:
    """
    Interfaz síncrona sobre la API asíncrona de EDGAR.
    Cachea resultados localmente para minimizar requests a SEC.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cik_map: Optional[dict] = None   # ticker (upper) → cik_str (zero-padded 10)

    # ── CIK map ─────────────────────────────────────────────────────────────

    def get_cik_map(self) -> dict:
        """
        Retorna dict {TICKER: '0000320193'} (CIK zero-padded a 10 dígitos).
        Cachea en edgar_cache/company_tickers.json durante CIK_MAP_TTL_DAYS días.
        """
        if self._cik_map is not None:
            return self._cik_map

        cache_file = self.cache_dir / "company_tickers.json"
        if self._cache_valid(cache_file, ttl_hours=CIK_MAP_TTL_DAYS * 24):
            with open(cache_file) as f:
                raw = json.load(f)
        else:
            logger.info("Descargando company_tickers.json desde SEC…")
            raw = _run_coro(self._fetch_json(EDGAR_TICKERS_URL))
            with open(cache_file, "w") as f:
                json.dump(raw, f)

        self._cik_map = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in raw.values()
        }
        return self._cik_map

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Retorna CIK zero-padded o None si el ticker no está en EDGAR."""
        return self.get_cik_map().get(ticker.upper())

    # ── Submissions ──────────────────────────────────────────────────────────

    def get_submissions(self, ticker: str) -> Optional[dict]:
        """
        Retorna el JSON de submissions de EDGAR para el ticker dado.
        Cachea en edgar_cache/submissions/{CIK}.json durante SUBMISSIONS_TTL_H horas.
        Retorna None si el ticker no tiene CIK en EDGAR.
        """
        cik = self.ticker_to_cik(ticker)
        if cik is None:
            logger.debug(f"{ticker}: no encontrado en company_tickers")
            return None

        cache_file = self.cache_dir / "submissions" / f"{cik}.json"
        cache_file.parent.mkdir(exist_ok=True)

        if self._cache_valid(cache_file, ttl_hours=SUBMISSIONS_TTL_H):
            with open(cache_file) as f:
                return json.load(f)

        url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
        logger.debug(f"Descargando submissions para {ticker} (CIK {cik})…")
        data = _run_coro(self._fetch_json(url))
        if data:
            with open(cache_file, "w") as f:
                json.dump(data, f)
        return data

    # ── Filings antes de un burst ────────────────────────────────────────────

    def get_filings_before_burst(
        self,
        ticker: str,
        burst_date: str,          # "YYYY-MM-DD"
        days_lookback: int = 7,
    ) -> list[dict]:
        """
        Retorna lista de filings del ticker en el período
        [burst_date - days_lookback, burst_date).

        Cada filing es un dict con claves:
            ticker, cik, form_type, filing_date, items,
            days_before_burst, catalyst_category, item_categories,
            is_high_impact, same_day_uncertain,
            primary_doc, accession_number
        """
        subs = self.get_submissions(ticker)
        if subs is None:
            return []

        burst_dt    = datetime.strptime(burst_date, "%Y-%m-%d").date()
        window_start = burst_dt - timedelta(days=days_lookback)

        recent = subs.get("filings", {}).get("recent", {})
        if not recent or "form" not in recent:
            return []

        forms       = recent.get("form", [])
        dates       = recent.get("filingDate", [])
        items_list  = recent.get("items", [])
        accessions  = recent.get("accessionNumber", [])
        primary_docs= recent.get("primaryDocument", [])

        results = []
        for i, (form, date_str) in enumerate(zip(forms, dates)):
            try:
                filing_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Solo dentro de la ventana ANTERIOR al burst
            if not (window_start <= filing_date < burst_dt):
                continue

            items_raw = items_list[i] if i < len(items_list) else ""
            accession  = accessions[i] if i < len(accessions) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""

            filing = classify_filing(
                ticker        = ticker,
                cik           = self.ticker_to_cik(ticker),
                form_type     = form,
                filing_date   = date_str,
                items_raw     = items_raw,
                accession     = accession,
                primary_doc   = primary_doc,
                burst_date    = burst_date,
            )
            results.append(filing)

        # Ordenar del más reciente al más antiguo
        results.sort(key=lambda x: x["filing_date"], reverse=True)
        return results

    # ── Batch asíncrono para múltiples tickers ───────────────────────────────

    def get_filings_batch(
        self,
        burst_events: pd.DataFrame,   # columnas: ticker, burst_date
        days_lookback: int = 7,
    ) -> dict[str, list[dict]]:
        """
        Retorna {"{ticker}|{burst_date}": [filings]} para todos los burst_events.
        Usa descarga asíncrona con semáforo para respetar rate limit de SEC.
        """
        # Primero cargar CIK map (una sola request)
        self.get_cik_map()

        # Identificar tickers únicos para descargar submissions en paralelo
        unique_tickers = burst_events["ticker"].unique().tolist()
        missing = [
            t for t in unique_tickers
            if not self._cache_valid(
                self.cache_dir / "submissions" / f"{self.ticker_to_cik(t) or 'NONE'}.json",
                ttl_hours=SUBMISSIONS_TTL_H
            )
        ]

        if missing:
            logger.info(f"Descargando submissions para {len(missing)} tickers…")
            _run_coro(self._fetch_submissions_batch(missing))

        # Construir resultados
        results = {}
        for _, row in burst_events.iterrows():
            key = f"{row['ticker']}|{row['burst_date']}"
            results[key] = self.get_filings_before_burst(
                row["ticker"], row["burst_date"], days_lookback
            )
        return results

    # ── Helpers privados ─────────────────────────────────────────────────────

    @staticmethod
    def _cache_valid(path: Path, ttl_hours: float) -> bool:
        if not path.exists():
            return False
        age_h = (time.time() - path.stat().st_mtime) / 3600
        return age_h < ttl_hours

    @staticmethod
    async def _fetch_json(url: str) -> Optional[dict]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
                    logger.warning(f"EDGAR {resp.status} para {url}")
                    return None
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None

    async def _fetch_submissions_batch(self, tickers: list[str]):
        """Descarga submissions en paralelo con semáforo de rate limit."""
        semaphore = asyncio.Semaphore(MAX_RPS)
        headers   = {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        }

        async def fetch_one(session, ticker):
            cik = self.ticker_to_cik(ticker)
            if cik is None:
                return
            cache_file = self.cache_dir / "submissions" / f"{cik}.json"
            cache_file.parent.mkdir(exist_ok=True)
            url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
            async with semaphore:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            with open(cache_file, "w") as f:
                                json.dump(data, f)
                        elif resp.status == 404:
                            logger.debug(f"{ticker}: 404 en EDGAR")
                        else:
                            logger.warning(f"{ticker}: HTTP {resp.status}")
                    await asyncio.sleep(1 / MAX_RPS)
                except Exception as e:
                    logger.debug(f"{ticker}: error {e}")

        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [fetch_one(session, t) for t in tickers]
            await asyncio.gather(*tasks)


# ── Clasificador de filings ──────────────────────────────────────────────────

def classify_filing(
    ticker: str,
    cik: Optional[str],
    form_type: str,
    filing_date: str,
    items_raw: str,
    accession: str,
    primary_doc: str,
    burst_date: str,
) -> dict:
    """
    Clasifica un filing y retorna un dict enriquecido.

    same_day_uncertain: True cuando filing_date == burst_date.
    En ese caso no podemos saber si el filing fue anterior o posterior al burst.
    Excluir del análisis principal; incluir en análisis de sensibilidad.
    """
    burst_dt   = datetime.strptime(burst_date, "%Y-%m-%d").date()
    filing_dt  = datetime.strptime(filing_date, "%Y-%m-%d").date()
    days_before = (burst_dt - filing_dt).days

    # Categoría base del form type
    catalyst_category = FORM_TYPE_CATEGORY.get(form_type, "other")

    # Parsear items del 8-K (campo puede ser "1.01,2.02" o "Item 1.01" etc.)
    item_codes: list[str] = []
    item_categories: list[str] = []
    is_high_impact = False
    has_fda_hint   = False

    if form_type in ("8-K", "8-K/A") and items_raw:
        # Normalizar: extraer números como "1.01", "8.01" etc.
        import re
        item_codes = re.findall(r'\d+\.\d+', str(items_raw))
        item_categories = [
            ITEM_CATEGORY.get(c, f"item_{c}") for c in item_codes
        ]
        is_high_impact = any(c in HIGH_IMPACT_ITEMS for c in item_codes)

        # Hint FDA: buscar en nombre de documento primario
        doc_lower = primary_doc.lower()
        has_fda_hint = any(kw in doc_lower for kw in FDA_KEYWORDS)

        # Refinar catalyst_category para 8-K
        if "2.02" in item_codes:
            catalyst_category = "earnings"
        elif "8.01" in item_codes or "7.01" in item_codes:
            catalyst_category = "other_event"  # press release / Reg FD
        elif "1.01" in item_codes:
            catalyst_category = "material_agreement"
        elif "5.02" in item_codes:
            catalyst_category = "director_officer_change"
        elif "5.01" in item_codes:
            catalyst_category = "change_of_control"
        else:
            catalyst_category = "material_event_other"

    # Insider: distinguir compra vs venta/ejercicio
    insider_is_purchase = False
    if form_type in ("4", "4/A"):
        # No podemos determinar la dirección sin parsear el XML completo.
        # Marcamos como unknown; el notebook puede enriquecer si es necesario.
        catalyst_category = "insider_transaction"

    return {
        "ticker":              ticker,
        "cik":                 cik,
        "form_type":           form_type,
        "filing_date":         filing_date,
        "days_before_burst":   days_before,
        "same_day_uncertain":  days_before == 0,
        "catalyst_category":   catalyst_category,
        "item_codes":          item_codes,
        "item_categories":     item_categories,
        "is_high_impact":      is_high_impact,
        "has_fda_hint":        has_fda_hint,
        "insider_is_purchase": insider_is_purchase,
        "accession_number":    accession,
        "primary_doc":         primary_doc,
    }


# ── Utilidades para el notebook ──────────────────────────────────────────────

def build_edgar_precursor_columns(
    burst_events: pd.DataFrame,
    edgar_results: dict,
    windows: tuple[int, ...] = (1, 3, 7),
) -> pd.DataFrame:
    """
    Añade columnas booleanas de precursores EDGAR a burst_events.

    Parámetros
    ----------
    burst_events : DataFrame con columnas [ticker, burst_date, ...]
    edgar_results: output de EdgarLoader.get_filings_batch()
    windows      : ventanas de lookback en días a generar como columnas

    Columnas añadidas (una por categoría × ventana):
        edgar_{category}_{N}d  (bool)
        edgar_any_filing_{N}d  (bool)
        edgar_no_filing_7d     (bool)  — sin ningún filing en 7 días
    """
    categories = [
        "earnings", "other_event", "material_agreement",
        "offering", "insider_transaction", "large_holder",
        "director_officer_change", "change_of_control",
        "material_event", "material_event_other",
    ]

    rows = []
    for _, burst in burst_events.iterrows():
        key      = f"{burst['ticker']}|{burst['burst_date']}"
        filings  = edgar_results.get(key, [])
        # Excluir same_day_uncertain del análisis principal
        filings  = [f for f in filings if not f["same_day_uncertain"]]

        row = {}
        for w in windows:
            w_filings = [f for f in filings if f["days_before_burst"] <= w]
            row[f"edgar_any_filing_{w}d"] = len(w_filings) > 0
            for cat in categories:
                col = f"edgar_{cat}_{w}d"
                row[col] = any(f["catalyst_category"] == cat for f in w_filings)

        row["edgar_no_filing_7d"] = len(
            [f for f in filings if f["days_before_burst"] <= 7]
        ) == 0

        # Columnas de alto impacto (8-K con items relevantes)
        hi = [f for f in filings if f.get("is_high_impact")]
        for w in windows:
            hi_w = [f for f in hi if f["days_before_burst"] <= w]
            row[f"edgar_high_impact_{w}d"] = len(hi_w) > 0

        rows.append(row)

    edgar_df = pd.DataFrame(rows, index=burst_events.index)
    return pd.concat([burst_events, edgar_df], axis=1)


_ITEM_HEADLINE = {
    # 8-K items → headlines with FinBERT-friendly catalyst language
    "1.01": "{company} enters definitive agreement — contract signed",
    "1.02": "{company} material agreement terminated",
    "2.01": "{company} completes acquisition of assets — deal closed",
    "2.02": "{company} releases earnings results — quarterly revenue and profit",
    "2.03": "{company} creates direct financial obligation — debt or loan agreement",
    "2.05": "{company} announces exit costs and restructuring charges",
    "2.06": "{company} records asset impairment charge",
    "3.01": "{company} receives delisting notice — exchange compliance issue",
    "4.01": "{company} changes auditor",
    "5.01": "{company} announces change of control — acquisition or merger",
    "5.02": "{company} appoints new CEO or CFO — executive leadership change",
    "5.03": "{company} amends corporate charter or bylaws",
    "7.01": "{company} discloses material information under Regulation FD",
    "8.01": "{company} announces press release — corporate event or product update",
    "9.01": "{company} provides financial statements and supporting exhibits",
}

_FORM_HEADLINE = {
    "S-1":    "{company} registers IPO — initial public offering shares",
    "S-1/A":  "{company} amends IPO registration statement",
    "S-3":    "{company} registers shelf offering — capital raise via share sale",
    "S-3/A":  "{company} amends shelf offering registration",
    "S-3ASR": "{company} automatic shelf registration — capital raise",
    "424B1":  "{company} prices stock offering — proceeds to fund operations",
    "424B2":  "{company} prices stock offering",
    "424B3":  "{company} prices follow-on stock offering — dilutive capital raise",
    "424B4":  "{company} prices IPO — shares offered to public investors",
    "424B5":  "{company} prices supplemental stock offering",
    "4":      "{company} insider buying or selling shares — executive transaction",
    "4/A":    "{company} executive amends share transaction report",
    "SC 13G": "{company} institutional investor acquires significant stake",
    "SC 13G/A":"{company} institutional investor updates ownership stake",
    "SC 13D": "{company} activist investor acquires stake — strategic alternatives possible",
    "SC 13D/A":"{company} activist investor updates stake — strategic review ongoing",
}


def _build_headline(company: str, form_type: str, items_raw: str) -> str:
    """
    Build a semantically rich FinBERT headline from EDGAR filing metadata.
    Uses item-specific templates with catalyst keywords for proper classification.
    Avoids the word 'filing' which falsely triggers the ACTIVIST pattern.
    """
    import re
    item_codes = re.findall(r'\d+\.\d+', str(items_raw)) if items_raw else []

    if form_type in ("8-K", "8-K/A"):
        if item_codes:
            # Use the highest-impact item as the primary headline
            priority = ["5.01", "2.01", "2.02", "1.01", "8.01", "7.01",
                        "5.02", "3.01", "2.03", "1.02", "9.01"]
            for p in priority:
                if p in item_codes and p in _ITEM_HEADLINE:
                    return _ITEM_HEADLINE[p].format(company=company)
            # Fallback to first item
            first = item_codes[0]
            return _ITEM_HEADLINE.get(first, f"{company} reports corporate event").format(company=company)
        return f"{company} reports material corporate event"

    template = _FORM_HEADLINE.get(form_type)
    if template:
        return template.format(company=company)

    return f"{company} SEC disclosure: {form_type}"


def get_finbert_features(
    ticker: str,
    burst_date: str,
    lookback_days: int = 90,
    max_filings: int = 3,
    cache_dir: Path = CACHE_DIR,
    trading_system_path: str = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3",
) -> dict:
    """
    Construye headlines sintéticos desde metadata EDGAR cached y los pasa por FinBERT.

    Para cada burst ticker toma los filings más recientes (días_before >= 1) dentro
    de lookback_days, construye "FORM_TYPE: item1, item2 filing" como headline
    y ejecuta FinBERTAnalyzer. Devuelve el filing de mayor catalyst_strength.

    Resultados cacheados en edgar_cache/finbert_cache.json para evitar re-inferencia.

    Retorna dict con claves:
        finbert_sentiment      : 'Positive' | 'Negative' | 'Neutral' | None
        finbert_confidence     : float | None
        finbert_catalyst_type  : str | None
        finbert_catalyst_strength : int | None   (1-10)
        finbert_n_filings      : int             (# filings analizados)
        finbert_form_types     : str             (CSV de form types analizados)
    """
    import sys
    import os

    # Cache
    cache_file = cache_dir / "finbert_cache.json"
    cache_key  = f"{ticker}|{burst_date}"
    cache: dict = {}
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    if cache_key in cache:
        return cache[cache_key]

    _empty = {
        "finbert_sentiment": None,
        "finbert_confidence": None,
        "finbert_catalyst_type": None,
        "finbert_catalyst_strength": None,
        "finbert_n_filings": 0,
        "finbert_form_types": "",
    }

    # Load submissions from cache only (no new API calls)
    sub_dir = cache_dir / "submissions"
    cik_map_file = cache_dir / "company_tickers.json"
    if not cik_map_file.exists():
        return _empty

    try:
        with open(cik_map_file) as f:
            raw_map = json.load(f)
        cik_map = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw_map.values()}
    except Exception:
        return _empty

    cik = cik_map.get(ticker.upper())
    if cik is None:
        result = dict(_empty)
        cache[cache_key] = result
        _save_finbert_cache(cache_file, cache)
        return result

    sub_file = sub_dir / f"{cik}.json"
    if not sub_file.exists():
        return _empty

    try:
        with open(sub_file) as f:
            subs = json.load(f)
    except Exception:
        return _empty

    recent   = subs.get("filings", {}).get("recent", {})
    company  = subs.get("name", ticker)
    if not recent or "form" not in recent:
        result = dict(_empty)
        cache[cache_key] = result
        _save_finbert_cache(cache_file, cache)
        return result

    burst_dt     = datetime.strptime(burst_date, "%Y-%m-%d").date()
    window_start = burst_dt - timedelta(days=lookback_days)

    forms       = recent.get("form", [])
    dates       = recent.get("filingDate", [])
    items_list  = recent.get("items", [])

    # Collect eligible filings (days_before >= 1, no look-ahead)
    candidates = []
    for i, (form, date_str) in enumerate(zip(forms, dates)):
        try:
            filing_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (window_start <= filing_dt < burst_dt):
            continue
        days_before = (burst_dt - filing_dt).days
        if days_before < 1:
            continue
        items_raw = items_list[i] if i < len(items_list) else ""
        candidates.append({
            "form_type":   form,
            "filing_date": date_str,
            "days_before": days_before,
            "items_raw":   str(items_raw),
        })

    if not candidates:
        result = dict(_empty)
        cache[cache_key] = result
        _save_finbert_cache(cache_file, cache)
        return result

    # Sort by recency (most recent first), take up to max_filings
    candidates.sort(key=lambda x: x["days_before"])
    candidates = candidates[:max_filings]

    # Load FinBERT (lazy singleton via sys.path injection)
    if trading_system_path not in sys.path:
        sys.path.insert(0, trading_system_path)

    try:
        from scanner.smallcap.finbert_analyzer import FinBERTAnalyzer
        analyzer = FinBERTAnalyzer()
    except Exception as e:
        logger.warning(f"FinBERT not available: {e}")
        return _empty

    best = None
    analyzed_forms = []
    for c in candidates:
        headline = _build_headline(company, c["form_type"], c["items_raw"])
        age_hours = c["days_before"] * 24.0
        try:
            res = analyzer.analyze_headline(headline, age_hours=age_hours)
            analyzed_forms.append(form)
            strength = getattr(res, "catalyst_strength", 0) or 0
            if best is None or strength > (getattr(best["result"], "catalyst_strength", 0) or 0):
                best = {"result": res, "form": form}
        except Exception as e:
            logger.debug(f"{ticker} FinBERT error on '{headline}': {e}")
            continue

    if best is None:
        result = dict(_empty)
    else:
        r = best["result"]
        result = {
            "finbert_sentiment":          getattr(r, "sentiment", None),
            "finbert_confidence":         getattr(r, "confidence", None),
            "finbert_catalyst_type":      getattr(r, "catalyst_type", None),
            "finbert_catalyst_strength":  getattr(r, "catalyst_strength", None),
            "finbert_n_filings":          len(analyzed_forms),
            "finbert_form_types":         ",".join(analyzed_forms),
        }

    cache[cache_key] = result
    _save_finbert_cache(cache_file, cache)
    return result


def _save_finbert_cache(cache_file: Path, cache: dict):
    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"Could not save finbert cache: {e}")


def build_finbert_columns(
    burst_events: pd.DataFrame,
    cache_dir: Path = CACHE_DIR,
    trading_system_path: str = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3",
    lookback_days: int = 90,
) -> pd.DataFrame:
    """
    Aplica get_finbert_features a cada fila de burst_events y añade columnas FinBERT.

    Columnas añadidas:
        finbert_sentiment, finbert_confidence, finbert_catalyst_type,
        finbert_catalyst_strength, finbert_n_filings, finbert_form_types

    El modelo se carga una sola vez gracias al cache interno de FinBERTAnalyzer.
    """
    records = []
    total = len(burst_events)
    for i, (_, row) in enumerate(burst_events.iterrows()):
        if (i + 1) % 20 == 0:
            logger.info(f"FinBERT: {i+1}/{total} tickers procesados…")
        feat = get_finbert_features(
            ticker=row["ticker"],
            burst_date=row["burst_date"],
            lookback_days=lookback_days,
            cache_dir=cache_dir,
            trading_system_path=trading_system_path,
        )
        records.append(feat)

    feat_df = pd.DataFrame(records, index=burst_events.index)
    return pd.concat([burst_events, feat_df], axis=1)


def edgar_summary_stats(edgar_results: dict) -> pd.DataFrame:
    """
    Retorna un DataFrame resumen: por ticker+burst_date,
    cuántos filings de cada categoría hubo en cada ventana.
    Útil para exploración rápida antes del análisis formal.
    """
    records = []
    for key, filings in edgar_results.items():
        ticker, burst_date = key.split("|")
        clean = [f for f in filings if not f["same_day_uncertain"]]
        for f in clean:
            records.append({
                "ticker":            ticker,
                "burst_date":        burst_date,
                "form_type":         f["form_type"],
                "catalyst_category": f["catalyst_category"],
                "filing_date":       f["filing_date"],
                "days_before_burst": f["days_before_burst"],
                "is_high_impact":    f["is_high_impact"],
                "has_fda_hint":      f["has_fda_hint"],
            })
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(["burst_date", "ticker", "days_before_burst"])
