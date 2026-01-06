# scanner/daily_plays_filter.py
"""
Daily Plays Filter Tool
Procesa datos de ProRealTime ProScreener y aplica filtros adicionales de float y noticias.

Input: Datos de ProScreener con formato:
"Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"

Output: Lista de tickers filtrados que cumplen todos los criterios
"""

import re
import asyncio
import aiohttp
from yahooquery import Ticker
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import pandas as pd
import json
import logging
from dataclasses import dataclass

# Import our enhanced news sources
from news_sources import MultiSourceNewsChecker, NewsSource

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TickerData:
    """Datos básicos de un ticker desde ProRealTime"""
    ticker: str
    name: str
    criterio: str
    var_pct: float
    var_abs: float
    last_price: float
    volume: str
    
    @classmethod
    def from_prt_line(cls, line: str) -> Optional['TickerData']:
        """Parse una línea de datos de ProRealTime - formato flexible"""
        try:
            # Extraer datos usando regex para manejar comillas y espacios
            pattern = r'"([^"]*)"'
            matches = re.findall(pattern, line)
            
            if len(matches) < 3:  # Mínimo: ticker, nombre, y algo más
                return None
                
            ticker = matches[0].strip()
            name = matches[1].strip()
            
            # Detectar formato automáticamente basado en número de campos
            if len(matches) >= 7:
                # Nuevo formato: "Ticker" "Nombre" "%Var" "Var" "Último" "Inserción" "Volumen"
                var_pct_str = matches[2].replace('+', '').replace('%', '').replace(',', '.')
                var_abs_str = matches[3].replace('+', '').replace(',', '.')
                last_price_str = matches[4].replace('(c)', '').replace(',', '.')
                volume = matches[6].strip()
                criterio = "auto"  # No hay criterio en este formato
                
            elif len(matches) >= 8:
                # Formato anterior: "Ticker" "Nombre" "Criterio" "%Var" "Var" "Inserción" "Último" "Volumen"
                criterio = matches[2].strip()
                var_pct_str = matches[3].replace('+', '').replace('%', '').replace(',', '.')
                var_abs_str = matches[4].replace('+', '').replace(',', '.')
                last_price_str = matches[6].replace(',', '.')
                volume = matches[7].strip()
                
            else:
                # Formato mínimo - solo extraer ticker
                return cls(
                    ticker=ticker,
                    name=name,
                    criterio="unknown",
                    var_pct=0.0,
                    var_abs=0.0,
                    last_price=0.0,
                    volume="0"
                )
            
            return cls(
                ticker=ticker,
                name=name,
                criterio=criterio,
                var_pct=float(var_pct_str) if var_pct_str.replace('.', '').replace('-', '').isdigit() else 0.0,
                var_abs=float(var_abs_str) if var_abs_str.replace('.', '').replace('-', '').isdigit() else 0.0,
                last_price=float(last_price_str) if last_price_str.replace('.', '').replace('-', '').isdigit() else 0.0,
                volume=volume
            )
            
        except Exception as e:
            logger.warning(f"Error parsing line: {line[:50]}... - {e}")
            return None

@dataclass
class FilterCriteria:
    """Criterios de filtrado para daily plays"""
    max_float_shares: float = 100_000_000  # 100M shares max
    min_gap_percent: float = 10.0  # Gap mínimo ya filtrado en PRT
    min_premarket_volume: int = 500_000  # Ya filtrado en PRT
    
    # Palabras clave para catalizadores
    catalyst_keywords: Set[str] = None
    
    def __post_init__(self):
        if self.catalyst_keywords is None:
            # Separate positive and negative catalysts for sentiment analysis
            self.positive_catalysts = {
                # FDA/Regulatory Positive
                'fda approval', 'approved', 'breakthrough', 'patent granted', 
                'orphan designation', 'fast track', 'phase success',
                
                # Earnings/Financial Positive  
                'beat earnings', 'beat estimates', 'revenue growth', 'profit increase',
                'upgraded', 'raised guidance', 'positive outlook', 'strong results',
                
                # M&A/Corporate Positive
                'acquisition', 'merger', 'buyout', 'takeover offer', 'deal',
                'partnership', 'collaboration', 'joint venture', 'strategic alliance',
                
                # Contracts/Business Positive
                'contract awarded', 'order received', 'win', 'selected',
                'agreement signed', 'license granted', 'expansion',
                
                # Technology/Innovation Positive
                'breakthrough', 'innovation', 'launch', 'new product',
                'technology advance', 'patent', 'discovery',
                
                # Crypto/Digital Assets Positive
                'crypto', 'bitcoin', 'ethereum', 'blockchain', 'digital assets',
                'cryptocurrency', 'defi', 'nft',
                
                # Energy/Commodities Positive
                'discovery', 'new reserve', 'drilling success', 'resource found',
                'production increase', 'capacity expansion',
                
                # Investment/Institutional Positive
                'insider buying', 'institutional investment', 'analyst upgrade',
                'price target raised', 'recommendation upgrade', 'buys stake',
                'stake', 'investment', 'backing'
            }
            
            self.negative_catalysts = {
                # FDA/Regulatory Negative
                'fda rejection', 'trial failed', 'clinical hold', 'safety concern',
                'regulatory delay', 'investigation', 'warning letter',
                
                # Earnings/Financial Negative
                'miss earnings', 'missed estimates', 'revenue decline', 'loss',
                'downgraded', 'lowered guidance', 'negative outlook', 'weak results',
                
                # Legal/Compliance Negative
                'lawsuit', 'investigation', 'sec inquiry', 'compliance issue',
                'fraud allegation', 'penalty', 'fine',
                
                # Business Negative
                'bankruptcy', 'debt default', 'restructuring', 'layoffs',
                'plant closure', 'recall', 'suspension',
                
                # Market Negative
                'delisting', 'halt', 'investigation', 'short seller report',
                'analyst downgrade', 'price target cut'
            }
            
            # Combine for backward compatibility
            self.catalyst_keywords = self.positive_catalysts.union(self.negative_catalysts)

class DailyPlaysFilter:
    """Filtro principal para Daily Plays"""
    
    def __init__(self, criteria: FilterCriteria = None, newsapi_key: Optional[str] = None):
        self.criteria = criteria or FilterCriteria()
        self.session = None
        
        # Initialize enhanced news checker
        news_config = NewsSource(newsapi_key=newsapi_key)
        self.news_checker = MultiSourceNewsChecker(
            config=news_config,
            catalyst_keywords=self.criteria.catalyst_keywords
        )
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def parse_prt_data(self, prt_text: str) -> List[TickerData]:
        """Parse datos de ProRealTime ProScreener"""
        lines = prt_text.strip().split('\n')
        tickers = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('"Ticker"'):  # Skip header
                continue
                
            ticker_data = TickerData.from_prt_line(line)
            if ticker_data:
                tickers.append(ticker_data)
                
        logger.info(f"Parsed {len(tickers)} tickers from ProRealTime data")
        return tickers
    
    async def get_float_data(self, tickers: List[str]) -> Dict[str, Optional[float]]:
        """Obtener datos de float usando yahooquery (más eficiente)"""
        float_data = {}
        
        logger.info(f"Fetching float data for {len(tickers)} tickers...")
        
        # Process in larger batches - yahooquery is more efficient
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            
            try:
                # Create ticker object for multiple symbols at once
                ticker_obj = Ticker(batch)
                
                # Get key stats (contains float info)
                key_stats_data = ticker_obj.key_stats
                
                # Process each ticker in the batch
                for ticker in batch:
                    try:
                        if ticker in key_stats_data and isinstance(key_stats_data[ticker], dict):
                            ticker_info = key_stats_data[ticker]
                            
                            # Try different float fields
                            float_shares = None
                            for field in ['floatShares', 'sharesOutstanding', 'impliedSharesOutstanding']:
                                if field in ticker_info and ticker_info[field]:
                                    float_shares = ticker_info[field]
                                    break
                            
                            float_data[ticker] = float_shares
                            
                            if float_shares:
                                logger.debug(f"{ticker}: Float = {float_shares:,.0f}")
                            else:
                                logger.warning(f"{ticker}: Float data not available")
                        else:
                            logger.warning(f"{ticker}: No key stats data available")
                            float_data[ticker] = None
                            
                    except Exception as e:
                        logger.warning(f"Error processing float for {ticker}: {e}")
                        float_data[ticker] = None
                        
                # Smaller delay - yahooquery is more rate-limit friendly
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error fetching batch {batch}: {e}")
                for ticker in batch:
                    float_data[ticker] = None
        
        return float_data
    
    async def get_news_data(self, tickers: List[str]) -> Dict[str, Any]:
        """Obtener noticias usando múltiples fuentes (NewsAPI, SEC, Yahoo)"""
        logger.info(f"Checking news/catalysts for {len(tickers)} tickers using multiple sources...")
        
        # Use enhanced multi-source news checker
        detailed_results = await self.news_checker.check_all_sources(tickers)
        
        # Convert to boolean format but filter by POSITIVE catalysts for LONG strategy
        news_data = {}
        for ticker, result in detailed_results.items():
            has_any_catalyst = result.get('has_catalyst', False)
            has_positive_catalyst = result.get('has_positive_catalyst', False)
            
            # For LONG strategy, only accept positive catalysts
            news_data[ticker] = has_positive_catalyst
            
            if has_any_catalyst:
                sentiment_analysis = result.get('sentiment_analysis')
                if sentiment_analysis:
                    sentiment = sentiment_analysis.sentiment.value
                    confidence = sentiment_analysis.confidence
                    
                    if has_positive_catalyst:
                        logger.info(f"{ticker}: ✅ POSITIVE catalyst (sentiment: {sentiment}, confidence: {confidence:.2f})")
                    else:
                        logger.info(f"{ticker}: ⚠️ Catalyst found but {sentiment.upper()} sentiment - FILTERED OUT for LONG strategy")
                else:
                    # Fallback if sentiment analysis failed
                    if has_positive_catalyst:
                        logger.info(f"{ticker}: ✅ Catalyst found (sentiment analysis unavailable)")
                    else:
                        logger.info(f"{ticker}: ⚠️ Catalyst found but filtered out for LONG strategy")
            else:
                logger.info(f"{ticker}: ❌ No catalysts found across all sources")
        
        # Store detailed results for later use
        self.detailed_news_results = detailed_results
        
        # Store float results for diagnostics
        if hasattr(self, 'float_data_results'):
            self.float_data_results = {}
        
        return news_data
    
    async def filter_tickers(self, prt_data: str) -> List[str]:
        """Filtrar tickers basado en todos los criterios"""
        
        # 1. Parse ProRealTime data
        ticker_data = self.parse_prt_data(prt_data)
        if not ticker_data:
            logger.error("No valid ticker data found")
            return []
        
        # Extract ticker symbols
        tickers = [t.ticker for t in ticker_data]
        logger.info(f"Initial tickers from ProRealTime: {len(tickers)}")
        
        # 2. Filter by float
        logger.info("Applying float filter...")
        float_data = await self.get_float_data(tickers)
        
        # Store float data for diagnostics
        self.float_data_results = float_data.copy()
        
        float_filtered = []
        for ticker in tickers:
            float_shares = float_data.get(ticker)
            if float_shares is None:
                logger.warning(f"{ticker}: No float data - SKIPPING")
                continue
            elif float_shares <= self.criteria.max_float_shares:
                float_filtered.append(ticker)
                logger.info(f"{ticker}: Float {float_shares:,.0f} ✓")
            else:
                logger.info(f"{ticker}: Float {float_shares:,.0f} > {self.criteria.max_float_shares:,.0f} ✗")
        
        logger.info(f"After float filter: {len(float_filtered)} tickers")
        
        # 3. Filter by news/catalysts
        if float_filtered:
            logger.info("Applying catalyst filter...")
            news_data = await self.get_news_data(float_filtered)
            
            final_filtered = []
            for ticker in float_filtered:
                has_catalyst = news_data.get(ticker, False)
                if has_catalyst:
                    final_filtered.append(ticker)
                    logger.info(f"{ticker}: Has catalyst ✓")
                else:
                    logger.info(f"{ticker}: No catalyst found ✗")
            
            logger.info(f"Final filtered tickers: {len(final_filtered)}")
            return final_filtered
        
        return []
    
    def format_output(self, tickers: List[str]) -> str:
        """Format output as comma-separated ticker list"""
        if not tickers:
            return "No tickers found matching all criteria"
        
        return ', '.join(tickers)

# CLI Interface
async def main():
    """Interfaz de línea de comandos"""
    print("=== Daily Plays Filter ===")
    print("Paste your ProRealTime ProScreener data below.")
    print("Press Enter twice when finished:")
    print()
    
    # Read multi-line input
    lines = []
    empty_lines = 0
    
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_lines += 1
                if empty_lines >= 2:
                    break
            else:
                empty_lines = 0
                lines.append(line)
        except EOFError:
            break
    
    prt_data = '\n'.join(lines)
    
    if not prt_data.strip():
        print("No data provided. Exiting.")
        return
    
    # Initialize filter
    criteria = FilterCriteria()
    
    # Allow customization
    print(f"\nCurrent criteria:")
    print(f"- Max Float: {criteria.max_float_shares:,.0f} shares")
    print(f"- Catalyst keywords: {len(criteria.catalyst_keywords)} keywords")
    
    response = input(f"\nUse default criteria? (y/n): ").lower()
    if response == 'n':
        try:
            max_float = input(f"Max float shares ({criteria.max_float_shares:,.0f}): ")
            if max_float.strip():
                criteria.max_float_shares = float(max_float.replace(',', ''))
        except:
            print("Using default float limit")
    
    print(f"\nProcessing with criteria:")
    print(f"- Max Float: {criteria.max_float_shares:,.0f} shares")
    print("- Checking for news catalysts...")
    print()
    
    # Process
    async with DailyPlaysFilter(criteria) as filter_tool:
        result_tickers = await filter_tool.filter_tickers(prt_data)
        output = filter_tool.format_output(result_tickers)
        
        print("=" * 50)
        print("RESULTS:")
        print("=" * 50)
        print(output)
        print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())