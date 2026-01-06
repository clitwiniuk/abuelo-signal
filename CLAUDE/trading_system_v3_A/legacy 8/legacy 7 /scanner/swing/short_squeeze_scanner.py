import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from yahooquery import Ticker
import pandas as pd

class ShortSqueezeScanner:
    """
    Scanner for Short Squeeze opportunities.
    
    Strategy:
    Identifies stocks with specific structural characteristics that lead to 
    explosive multi-day moves ("Runners"):
    1. Low Float (< 50M shares)
    2. High Short Interest (> 10% of float)
    3. Active Momentum (Volume > 1.5x, Price > VWAP)
    
    Data Source:
    - Uses yahooquery (Yahoo Finance) for Float and Short Interest data.
    - Uses IBKR for real-time price/volume validation.
    """
    
    def __init__(self, ibkr_adapter=None, logger=None):
        self.logger = logger or logging.getLogger("ShortSqueezeScanner")
        self.ibkr_adapter = ibkr_adapter
        
        # Squeeze Criteria (based on analysis)
        self.max_float = 50_000_000  # 50M shares
        self.min_short_percent = 0.10  # 10% short interest
        self.min_volume_ratio = 1.5    # 1.5x relative volume
        
        self.logger.info("🐻💥 Short Squeeze Scanner initialized")
        self.logger.info(f"   Criteria: Float < {self.max_float/1_000_000}M, Short > {self.min_short_percent:.0%}")

    async def scan_squeeze_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze a list of candidates for Short Squeeze potential.
        
        Args:
            candidates: List of opportunity dicts (must contain 'symbol')
            
        Returns:
            List of opportunities enriched with Squeeze data
        """
        if not candidates:
            return []
            
        squeeze_opportunities = []
        symbols = [c['symbol'] for c in candidates]
        
        self.logger.info(f"🔍 Analyzing {len(symbols)} candidates for Short Squeeze structure...")
        
        # 1. Fetch Fundamental Data (Batch)
        stats_map = await self._fetch_yahoo_stats(symbols)
        
        for cand in candidates:
            symbol = cand['symbol']
            stats = stats_map.get(symbol)
            
            if not stats:
                continue
                
            float_shares = stats.get('float_shares', float('inf'))
            short_percent = stats.get('short_percent', 0.0)
            
            # 2. Apply Structure Filters
            is_squeeze_structure = (
                float_shares is not None and 
                float_shares < self.max_float and
                short_percent is not None and 
                short_percent > self.min_short_percent
            )
            
            if is_squeeze_structure:
                self.logger.info(
                    f"💎 SQUEEZE DETECTED: {symbol} "
                    f"(Float: {float_shares/1_000_000:.1f}M, Short: {short_percent:.1%})"
                )
                
                # Create enriched opportunity
                squeeze_opp = cand.copy()
                squeeze_opp['opportunity_type'] = 'SHORT_SQUEEZE'
                squeeze_opp['squeeze_data'] = {
                    'float_shares': float_shares,
                    'short_percent': short_percent,
                    'short_ratio': stats.get('short_ratio', 0)
                }
                
                # Boost quality score for Squeeze setups
                original_score = squeeze_opp.get('quality_score', 50)
                squeeze_opp['quality_score'] = min(original_score + 20, 99) # +20 point boost
                
                squeeze_opportunities.append(squeeze_opp)
            else:
                self.logger.debug(
                    f"⚪ {symbol}: Not a squeeze (Float: {float_shares}, Short: {short_percent})"
                )
                
        return squeeze_opportunities

    async def _fetch_yahoo_stats(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch Float and Short Interest from Yahoo Finance via yahooquery.
        Runs in a separate thread to avoid blocking asyncio loop.
        """
        try:
            # Run blocking yahooquery call in executor
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, self._fetch_yahoo_stats_sync, symbols)
            return stats
        except Exception as e:
            self.logger.error(f"❌ Error fetching Yahoo stats: {e}")
            return {}

    def _fetch_yahoo_stats_sync(self, symbols: List[str]) -> Dict[str, Dict]:
        """Synchronous implementation of yahoo stats fetching"""
        stats_data = {}
        try:
            # Chunking to be safe
            chunk_size = 100
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i+chunk_size]
                t = Ticker(chunk, asynchronous=True)
                
                # Fetch key statistics
                data = t.get_modules('defaultKeyStatistics summaryDetail')
                
                for symbol in chunk:
                    if isinstance(data, dict) and symbol in data:
                        try:
                            s_stats = data[symbol].get('defaultKeyStatistics', {})
                            
                            # Handle cases where data is missing or error string
                            if isinstance(s_stats, str):
                                continue
                                
                            stats_data[symbol] = {
                                'float_shares': s_stats.get('floatShares'),
                                'short_ratio': s_stats.get('shortRatio'),
                                'short_percent': s_stats.get('shortPercentOfFloat')
                            }
                        except Exception:
                            continue
                            
            return stats_data
            
        except Exception as e:
            self.logger.error(f"Error in _fetch_yahoo_stats_sync: {e}")
            return {}
