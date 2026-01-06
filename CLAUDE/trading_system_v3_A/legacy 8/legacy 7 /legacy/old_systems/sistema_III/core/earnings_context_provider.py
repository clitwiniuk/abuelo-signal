#!/usr/bin/env python3
"""
Earnings Context Provider - Scanner-First Approach
Provides earnings context for tickers identified by scanner
"""

import os
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

@dataclass
class EarningsContext:
    """Earnings context for a specific ticker"""
    symbol: str
    phase: str  # NORMAL, PRE_EARNINGS, POST_EARNINGS_BEAT, POST_EARNINGS_MISS, POST_EARNINGS_SURPRISE
    days_to_earnings: Optional[int]
    days_since_earnings: Optional[int]
    is_earnings_week: bool
    actual_eps: Optional[float]
    estimated_eps: Optional[float]
    surprise_percent: Optional[float]
    confidence: float  # 0-1, confidence in the earnings data

class EarningsContextProvider:
    """
    Provides earnings context for scanner-identified tickers
    Uses Alpha Vantage API efficiently - only queries needed tickers
    """
    
    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.base_url = "https://www.alphavantage.co/query"
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # Cache earnings data to avoid repeat calls
        self.cache_duration = 3600  # 1 hour cache
        
        if not self.api_key:
            self.logger.warning("ALPHA_VANTAGE_API_KEY not found - earnings context disabled")
            self.enabled = False
        else:
            self.enabled = True
    
    async def get_earnings_context(self, symbol: str) -> EarningsContext:
        """
        Get earnings context for a specific ticker identified by scanner
        This is called AFTER scanner finds the ticker interesting
        """
        
        if not self.enabled:
            return self._get_default_context(symbol)
        
        # Check cache first
        cache_key = f"earnings_{symbol}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            # Get earnings data from Alpha Vantage
            earnings_data = await self._fetch_earnings_data(symbol)
            context = self._analyze_earnings_context(symbol, earnings_data)
            
            # Cache for future use
            self._cache_context(cache_key, context)
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting earnings context for {symbol}: {e}")
            return self._get_default_context(symbol)
    
    async def _fetch_earnings_data(self, symbol: str) -> Dict:
        """Fetch earnings data from Alpha Vantage API"""
        
        params = {
            'function': 'EARNINGS',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if we got valid data or API limit error
                    if 'Note' in data:
                        self.logger.warning(f"Alpha Vantage API limit reached: {data['Note']}")
                        return {}
                    
                    if 'Error Message' in data:
                        self.logger.warning(f"Alpha Vantage error for {symbol}: {data['Error Message']}")
                        return {}
                    
                    return data
                else:
                    self.logger.warning(f"Alpha Vantage API error {response.status} for {symbol}")
                    return {}
    
    def _analyze_earnings_context(self, symbol: str, earnings_data: Dict) -> EarningsContext:
        """Analyze earnings data to determine context"""
        
        if not earnings_data or 'quarterlyEarnings' not in earnings_data:
            return self._get_default_context(symbol)
        
        quarterly_earnings = earnings_data['quarterlyEarnings']
        if not quarterly_earnings:
            return self._get_default_context(symbol)
        
        # Get most recent earnings
        latest_earnings = quarterly_earnings[0]
        
        try:
            # Parse reported date
            reported_date_str = latest_earnings.get('reportedDate')
            if not reported_date_str:
                return self._get_default_context(symbol)
            
            reported_date = datetime.strptime(reported_date_str, '%Y-%m-%d')
            now = datetime.now()
            days_since = (now - reported_date).days
            
            # Get EPS data
            actual_eps = float(latest_earnings.get('reportedEPS', 0)) if latest_earnings.get('reportedEPS') else None
            estimated_eps = float(latest_earnings.get('estimatedEPS', 0)) if latest_earnings.get('estimatedEPS') else None
            
            # Calculate surprise
            surprise_percent = None
            if actual_eps is not None and estimated_eps is not None and estimated_eps != 0:
                surprise_percent = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
            
            # Determine phase based on timing and results
            phase = "NORMAL"
            is_earnings_week = False
            confidence = 0.8  # High confidence in Alpha Vantage data
            
            if days_since <= 7:  # Recent earnings (within 1 week)
                is_earnings_week = True
                
                if surprise_percent is not None:
                    if surprise_percent > 20:  # Beat by >20%
                        phase = "POST_EARNINGS_BEAT"
                    elif surprise_percent < -20:  # Miss by >20%
                        phase = "POST_EARNINGS_MISS"
                    elif abs(surprise_percent) > 50:  # Huge surprise either way
                        phase = "POST_EARNINGS_SURPRISE"
                    elif surprise_percent > 5:  # Modest beat
                        phase = "POST_EARNINGS_BEAT"
                    elif surprise_percent < -5:  # Modest miss
                        phase = "POST_EARNINGS_MISS"
                else:
                    # No estimate data, use actual EPS to guess
                    if actual_eps and actual_eps > 0.05:  # Decent positive earnings
                        phase = "POST_EARNINGS_BEAT"
                    elif actual_eps and actual_eps < -0.05:  # Significant loss
                        phase = "POST_EARNINGS_MISS"
            
            elif days_since < 0:  # Future date (shouldn't happen but handle it)
                # This might be next earnings date
                if abs(days_since) <= 7:  # Within a week
                    phase = "PRE_EARNINGS"
                    is_earnings_week = True
                
            return EarningsContext(
                symbol=symbol,
                phase=phase,
                days_to_earnings=None,  # Would need calendar data for this
                days_since_earnings=days_since if days_since >= 0 else None,
                is_earnings_week=is_earnings_week,
                actual_eps=actual_eps,
                estimated_eps=estimated_eps,
                surprise_percent=surprise_percent,
                confidence=confidence
            )
            
        except (ValueError, KeyError, TypeError) as e:
            self.logger.debug(f"Error parsing earnings data for {symbol}: {e}")
            return self._get_default_context(symbol)
    
    def _get_default_context(self, symbol: str) -> EarningsContext:
        """Return default earnings context when no data available"""
        
        return EarningsContext(
            symbol=symbol,
            phase="NORMAL",
            days_to_earnings=None,
            days_since_earnings=None,
            is_earnings_week=False,
            actual_eps=None,
            estimated_eps=None,
            surprise_percent=None,
            confidence=0.0  # No confidence without data
        )
    
    def _is_cached(self, cache_key: str) -> bool:
        """Check if earnings context is cached and still valid"""
        
        if cache_key not in self.cache:
            return False
        
        cache_time = self.cache[cache_key]['timestamp']
        return (datetime.now() - cache_time).seconds < self.cache_duration
    
    def _cache_context(self, cache_key: str, context: EarningsContext):
        """Cache earnings context"""
        
        self.cache[cache_key] = {
            'data': context,
            'timestamp': datetime.now()
        }
    
    async def get_multiple_contexts(self, symbols: list) -> Dict[str, EarningsContext]:
        """
        Get earnings context for multiple symbols efficiently
        Uses asyncio to make concurrent API calls
        """
        
        if not self.enabled:
            return {symbol: self._get_default_context(symbol) for symbol in symbols}
        
        # Limit concurrent requests to avoid API rate limiting
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def get_single_context(symbol):
            async with semaphore:
                return symbol, await self.get_earnings_context(symbol)
        
        # Execute all requests concurrently
        tasks = [get_single_context(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        contexts = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in concurrent earnings fetch: {result}")
                continue
            
            symbol, context = result
            contexts[symbol] = context
        
        return contexts

# Singleton instance for use throughout the system
earnings_context_provider = EarningsContextProvider()