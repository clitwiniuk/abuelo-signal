# scanner/tiingo_data_provider.py
"""
Tiingo Data Provider - Real-time data for smallcaps
Focused on maintaining edge with real-time pre-market and intraday data
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class TiingoQuote:
    """Real-time quote from Tiingo"""
    symbol: str
    last_price: float
    previous_close: float
    gap_percentage: float
    volume: int
    avg_volume_30d: int
    volume_ratio: float
    bid: float
    ask: float
    spread: float
    timestamp: datetime
    market_session: str  # 'premarket', 'regular', 'afterhours'

@dataclass
class TiingoScanResult:
    """Scan result with real-time data"""
    symbol: str
    quote: TiingoQuote
    gap_rank: int
    volume_rank: int
    overall_score: float
    meets_criteria: bool

class TiingoDataProvider:
    """
    Tiingo API integration for real-time smallcap data
    
    Key advantages:
    - Real-time pre-market data (4AM-9:30AM)
    - 1-minute intraday bars
    - Volume data for smallcaps
    - $10-30/month (affordable)
    - API rate limits: 1000 calls/hour (sufficient)
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tiingo.com"
        self.logger = logging.getLogger(f"{__name__}.TiingoDataProvider")
        
        # Session for connection pooling
        self._session = None
        
        # Cache for avoiding duplicate calls
        self._quote_cache = {}
        self._cache_expiry = {}
        self.cache_duration = 60  # 1 minute cache for real-time data
        
        # Tiingo endpoints
        self.endpoints = {
            'iex_quote': '/iex',  # Real-time quotes
            'eod_prices': '/tiingo/daily',  # End of day
            'intraday': '/iex',  # Intraday data
            'metadata': '/tiingo/daily'  # Company metadata
        }
        
        self.logger.info("TiingoDataProvider initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_session()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is available"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_real_time_quotes(self, symbols: List[str]) -> List[TiingoQuote]:
        """
        Get real-time quotes for symbols
        This is the KEY method for maintaining edge
        """
        await self._ensure_session()
        
        self.logger.info(f"🔍 Fetching real-time quotes for {len(symbols)} symbols from Tiingo...")
        
        quotes = []
        
        # Process in batches (Tiingo allows multiple symbols per request)
        batch_size = 50  # Tiingo supports up to 100 symbols per request
        
        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]
            
            try:
                batch_quotes = await self._fetch_quotes_batch(batch_symbols)
                quotes.extend(batch_quotes)
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error fetching batch {batch_symbols}: {e}")
                continue
        
        self.logger.info(f"✅ Retrieved {len(quotes)} real-time quotes")
        return quotes
    
    async def _fetch_quotes_batch(self, symbols: List[str]) -> List[TiingoQuote]:
        """Fetch quotes for a batch of symbols"""
        symbols_str = ','.join(symbols)
        
        url = f"{self.base_url}/iex"
        params = {
            'tickers': symbols_str,
            'token': self.api_key,
            'format': 'json'
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_tiingo_quotes(data)
                else:
                    error_text = await response.text()
                    self.logger.error(f"Tiingo API error {response.status}: {error_text}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"Network error fetching quotes: {e}")
            return []
    
    def _parse_tiingo_quotes(self, data: List[Dict]) -> List[TiingoQuote]:
        """Parse Tiingo API response into TiingoQuote objects"""
        quotes = []
        
        for item in data:
            try:
                symbol = item.get('ticker', '')
                
                # Safe parsing with None handling
                last_price_raw = item.get('last')
                last_price = float(last_price_raw) if last_price_raw is not None else 0.0
                
                prev_close_raw = item.get('prevClose')
                prev_close = float(prev_close_raw) if prev_close_raw is not None else 0.0
                
                volume_raw = item.get('volume')
                volume = int(volume_raw) if volume_raw is not None else 0
                
                # Calculate gap percentage
                gap_pct = 0.0
                if prev_close > 0:
                    gap_pct = (last_price - prev_close) / prev_close
                
                # Determine market session
                current_time = datetime.now().time()
                if current_time < datetime.strptime("09:30", "%H:%M").time():
                    market_session = 'premarket'
                elif current_time > datetime.strptime("16:00", "%H:%M").time():
                    market_session = 'afterhours'
                else:
                    market_session = 'regular'
                
                # Calculate spread with safe parsing
                bid_raw = item.get('bid')
                bid = float(bid_raw) if bid_raw is not None else 0.0
                
                ask_raw = item.get('ask')
                ask = float(ask_raw) if ask_raw is not None else 0.0
                spread = ask - bid if ask > 0 and bid > 0 else 0
                
                quote = TiingoQuote(
                    symbol=symbol,
                    last_price=last_price,
                    previous_close=prev_close,
                    gap_percentage=gap_pct,
                    volume=volume,
                    avg_volume_30d=int(item.get('avgVolume') or 0),  # Safe None handling
                    volume_ratio=volume / (item.get('avgVolume') or 1) if (item.get('avgVolume') or 0) > 0 else 0,
                    bid=bid,
                    ask=ask,
                    spread=spread,
                    timestamp=datetime.now(),
                    market_session=market_session
                )
                
                quotes.append(quote)
                
            except Exception as e:
                self.logger.warning(f"Error parsing quote for {item.get('ticker', 'unknown')}: {e}")
                continue
        
        return quotes
    
    async def scan_gap_movers(self, 
                            min_gap_percent: float = 0.08,
                            min_price: float = 0.50,
                            max_price: float = 15.00,
                            min_volume: int = 100000,
                            max_results: int = 50) -> List[TiingoScanResult]:
        """
        Scan for gap movers using Tiingo real-time data
        This replaces the ProRealTime manual process
        """
        self.logger.info("🔍 Scanning gap movers with Tiingo real-time data...")
        
        # Step 1: Get universe of smallcap symbols
        # This would typically be a pre-defined list or fetched from Tiingo
        smallcap_universe = await self._get_smallcap_universe(min_price, max_price)
        
        if not smallcap_universe:
            self.logger.warning("No smallcap universe available")
            return []
        
        # Step 2: Get real-time quotes
        quotes = await self.get_real_time_quotes(smallcap_universe)
        
        # Step 3: Filter for gap criteria
        gap_movers = []
        
        for quote in quotes:
            if not self._meets_gap_criteria(quote, min_gap_percent, min_price, max_price, min_volume):
                continue
            
            # Calculate scores
            gap_rank = self._calculate_gap_rank(quote, quotes)
            volume_rank = self._calculate_volume_rank(quote, quotes)
            overall_score = self._calculate_overall_score(quote, gap_rank, volume_rank)
            
            scan_result = TiingoScanResult(
                symbol=quote.symbol,
                quote=quote,
                gap_rank=gap_rank,
                volume_rank=volume_rank,
                overall_score=overall_score,
                meets_criteria=True
            )
            
            gap_movers.append(scan_result)
        
        # Step 4: Sort by overall score and limit results
        gap_movers.sort(key=lambda x: x.overall_score, reverse=True)
        final_results = gap_movers[:max_results]
        
        self.logger.info(f"🎯 Found {len(final_results)} gap movers meeting criteria")
        
        return final_results
    
    async def _get_smallcap_universe(self, min_price: float, max_price: float) -> List[str]:
        """
        Get universe of smallcap symbols
        This would be enhanced with a real universe list
        """
        # For now, return a sample universe
        # In production, this would be a comprehensive smallcap list
        sample_universe = [
            'AAPL', 'MSFT', 'GOOGL',  # These are for testing - replace with real smallcaps
            'AMC', 'GME', 'SNDL', 'PLTR', 'MVIS', 'CLOV',  # Known volatile smallcaps
            'RIOT', 'MARA', 'PLUG', 'FCEL', 'WKHS', 'SPCE'  # More examples
        ]
        
        # In production, you might:
        # 1. Use Tiingo's universe endpoint
        # 2. Load from a curated list
        # 3. Filter by market cap using Tiingo metadata
        
        return sample_universe[:100]  # Limit for testing
    
    def _meets_gap_criteria(self, quote: TiingoQuote, 
                          min_gap_percent: float,
                          min_price: float, 
                          max_price: float,
                          min_volume: int) -> bool:
        """Check if quote meets gap scanning criteria"""
        return (
            abs(quote.gap_percentage) >= min_gap_percent and
            min_price <= quote.last_price <= max_price and
            quote.volume >= min_volume and
            quote.last_price > 0 and
            quote.previous_close > 0
        )
    
    def _calculate_gap_rank(self, quote: TiingoQuote, all_quotes: List[TiingoQuote]) -> int:
        """Calculate gap rank among all quotes"""
        gap_abs = abs(quote.gap_percentage)
        larger_gaps = sum(1 for q in all_quotes if abs(q.gap_percentage) > gap_abs)
        return larger_gaps + 1
    
    def _calculate_volume_rank(self, quote: TiingoQuote, all_quotes: List[TiingoQuote]) -> int:
        """Calculate volume rank among all quotes"""
        higher_volumes = sum(1 for q in all_quotes if q.volume_ratio > quote.volume_ratio)
        return higher_volumes + 1
    
    def _calculate_overall_score(self, quote: TiingoQuote, gap_rank: int, volume_rank: int) -> float:
        """Calculate overall quality score"""
        # Score components
        gap_score = abs(quote.gap_percentage) * 100  # 0-50+ points
        volume_score = min(quote.volume_ratio * 10, 50)  # 0-50 points
        
        # Ranking bonus (lower rank = higher bonus)
        gap_bonus = max(0, 50 - gap_rank)  # 0-50 points
        volume_bonus = max(0, 50 - volume_rank)  # 0-50 points
        
        # Pre-market bonus
        premarket_bonus = 20 if quote.market_session == 'premarket' else 0
        
        # Spread penalty (tighter spreads are better)
        spread_penalty = min(quote.spread * 10, 20) if quote.spread > 0 else 0
        
        total_score = gap_score + volume_score + gap_bonus + volume_bonus + premarket_bonus - spread_penalty
        
        return total_score
    
    async def get_historical_volume(self, symbol: str, days: int = 30) -> float:
        """Get historical average volume for comparison"""
        # This would fetch historical data from Tiingo
        # For now, return estimated value
        return 1_000_000  # Placeholder
    
    def format_scan_results(self, results: List[TiingoScanResult]) -> str:
        """Format scan results for display"""
        if not results:
            return "No gap movers found with current criteria."
        
        output = f"🎯 TIINGO GAP SCANNER ({len(results)} movers found):\n"
        
        # Quick symbols list
        symbols = [r.symbol for r in results]
        output += f"📋 Symbols: {', '.join(symbols)}\n\n"
        
        # Detailed results
        output += "📊 REAL-TIME DETAILS:\n"
        for i, result in enumerate(results, 1):
            q = result.quote
            gap_direction = "↗" if q.gap_percentage > 0 else "↘"
            
            output += f"{i}. {q.symbol} {gap_direction} (Score: {result.overall_score:.0f})\n"
            output += f"   Gap: {q.gap_percentage*100:+.1f}% | Price: ${q.last_price:.2f}\n"
            output += f"   Volume: {q.volume:,} ({q.volume_ratio:.1f}x avg)\n"
            output += f"   Session: {q.market_session.upper()} | Spread: ${q.spread:.3f}\n"
            output += f"   Ranks: Gap #{result.gap_rank}, Volume #{result.volume_rank}\n\n"
        
        return output

# Convenience function for testing
async def test_tiingo_scanner(api_key: str):
    """Test function for Tiingo scanner"""
    async with TiingoDataProvider(api_key) as tiingo:
        results = await tiingo.scan_gap_movers(
            min_gap_percent=0.05,  # 5% for testing
            max_results=10
        )
        
        print(tiingo.format_scan_results(results))
        return results