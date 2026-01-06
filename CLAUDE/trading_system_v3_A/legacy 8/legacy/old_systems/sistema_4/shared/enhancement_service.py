# shared/enhancement_service.py
"""
Shared Enhancement Service
Provides detailed market data enhancement for workers on-demand
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from ib_insync import Contract

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter_clean import IBKRAdapterClean as IBKRAdapter
from shared.config_reader import Sistema4Config
import redis.asyncio as redis

class EnhancementService:
    """
    Shared service for on-demand market data enhancement
    Used by workers to get detailed data only when needed
    """

    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.logger = logging.getLogger(f"{__name__}.EnhancementService")

        # IBKR adapter (can be shared or independent)
        self.ibkr_adapter = ibkr_adapter

        # Redis for caching (shared with workers)
        self.redis_client = None
        self._price_cache = {}
        self._fundamental_cache = {}

        # Rate limiting
        self._last_request_time = {}
        self._request_count = 0
        self._rate_limit_window = 60  # seconds
        self._max_requests_per_window = 30  # Conservative limit

        self.logger.info("📈 Enhancement Service initialized")

    async def connect(self):
        """Connect to Redis for caching"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            await self.redis_client.ping()
            self.logger.info("✅ Enhancement Service connected to Redis")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Redis: {e}")
            return False

    async def enhance_symbol(self, symbol: str, contract: Contract) -> Dict[str, Any]:
        """
        Enhance a single symbol with detailed market data
        Returns enhanced data or cached data if available
        """
        try:
            # Check cache first (Redis + memory)
            cached_data = await self._get_cached_enhancement(symbol)
            if cached_data:
                self.logger.debug(f"📋 Using cached data for {symbol}")
                return cached_data

            # Rate limiting check
            if not self._can_make_request():
                self.logger.warning(f"⏱️ Rate limit hit - using fallback data for {symbol}")
                return self._get_fallback_data(symbol)

            # Get fresh enhancement data
            enhancement_data = await self._fetch_enhancement_data(symbol, contract)

            # Cache the result
            await self._cache_enhancement(symbol, enhancement_data)

            self.logger.debug(f"✅ Enhanced {symbol} with fresh data")
            return enhancement_data

        except Exception as e:
            self.logger.error(f"❌ Error enhancing {symbol}: {e}")
            return self._get_fallback_data(symbol)

    async def _get_cached_enhancement(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached enhancement data if available and fresh"""
        try:
            # Check Redis cache first
            if self.redis_client:
                cache_key = f"enhancement:{symbol}"
                cached_json = await self.redis_client.get(cache_key)
                if cached_json:
                    cached_data = json.loads(cached_json)
                    # Check if cache is still fresh (5 minutes)
                    cache_time = datetime.fromisoformat(cached_data.get('cached_at', ''))
                    if datetime.now() - cache_time < timedelta(minutes=5):
                        return cached_data

            # Check memory cache
            if symbol in self._price_cache:
                cache_time = self._price_cache[symbol].get('cached_at')
                if cache_time and datetime.now() - cache_time < timedelta(minutes=2):
                    return self._price_cache[symbol]

            return None

        except Exception as e:
            self.logger.debug(f"Cache lookup error for {symbol}: {e}")
            return None

    async def _cache_enhancement(self, symbol: str, data: Dict[str, Any]):
        """Cache enhancement data in both Redis and memory"""
        try:
            data['cached_at'] = datetime.now().isoformat()

            # Memory cache
            self._price_cache[symbol] = data

            # Redis cache with expiration
            if self.redis_client:
                cache_key = f"enhancement:{symbol}"
                await self.redis_client.setex(
                    cache_key,
                    300,  # 5 minutes TTL
                    json.dumps(data, default=str)
                )

        except Exception as e:
            self.logger.debug(f"Cache store error for {symbol}: {e}")

    def _can_make_request(self) -> bool:
        """Check if we can make a request without hitting rate limits"""
        now = datetime.now()

        # Clean old requests from tracking
        cutoff = now - timedelta(seconds=self._rate_limit_window)
        self._last_request_time = {
            symbol: req_time
            for symbol, req_time in self._last_request_time.items()
            if req_time > cutoff
        }

        # Check if we're under the limit
        recent_requests = len(self._last_request_time)
        if recent_requests >= self._max_requests_per_window:
            return False

        # Record this request
        self._last_request_time[f"req_{now.timestamp()}"] = now
        return True

    async def _fetch_enhancement_data(self, symbol: str, contract: Contract) -> Dict[str, Any]:
        """Fetch fresh enhancement data from IBKR"""
        if not self.ibkr_adapter:
            return self._get_fallback_data(symbol)

        # Get price data with timeout
        price_data = await self._get_price_data_safe(contract)

        # Get fundamental data (simplified)
        fundamental_data = await self._get_fundamental_data_safe(contract)

        return {
            'symbol': symbol,
            'current_price': price_data.get('current_price', 0.0),
            'previous_close': price_data.get('previous_close', 0.0),
            'current_volume': price_data.get('current_volume', 0),
            'gap_percentage': self._calculate_gap_percentage(price_data),
            'market_cap': fundamental_data.get('market_cap', 500_000_000),
            'enhanced_at': datetime.now().isoformat()
        }

    async def _get_price_data_safe(self, contract: Contract) -> Dict[str, Any]:
        """Get price data with timeout and error handling"""
        try:
            ib = self.ibkr_adapter.ib

            # Quick market data request with timeout
            async def get_market_data():
                ib.reqMktData(contract, '', False, False)
                await asyncio.sleep(0.5)  # Reduced wait time
                ticker = ib.ticker(contract)
                ib.cancelMktData(contract)
                return ticker

            ticker = await asyncio.wait_for(get_market_data(), timeout=2.0)

            current_price = 0.0
            current_volume = 0
            if ticker:
                current_price = (
                    ticker.marketPrice() or
                    ticker.last or
                    ticker.bid or
                    ticker.ask or
                    ticker.close or
                    0.0
                )
                current_volume = ticker.volume if ticker.volume and ticker.volume > 0 else 0

            previous_close = ticker.close if ticker else 0.0

            return {
                'current_price': current_price,
                'previous_close': previous_close,
                'current_volume': current_volume
            }

        except Exception as e:
            self.logger.debug(f"Price data error for {contract.symbol}: {e}")
            return {'current_price': 0.0, 'previous_close': 0.0, 'current_volume': 0}

    async def _get_fundamental_data_safe(self, contract: Contract) -> Dict[str, Any]:
        """Get fundamental data with fallback"""
        # For now, return reasonable defaults
        # In production, could implement actual fundamental data requests
        return {'market_cap': 500_000_000}

    def _calculate_gap_percentage(self, price_data: Dict[str, Any]) -> float:
        """Calculate gap percentage from price data"""
        current = price_data.get('current_price', 0.0)
        previous = price_data.get('previous_close', 0.0)

        if previous > 0:
            return (current - previous) / previous
        return 0.0

    def _get_fallback_data(self, symbol: str) -> Dict[str, Any]:
        """Return reasonable fallback data when enhancement fails"""
        return {
            'symbol': symbol,
            'current_price': 5.0,  # Reasonable smallcap price
            'previous_close': 5.0,
            'current_volume': 100_000,
            'gap_percentage': 0.0,
            'market_cap': 500_000_000,
            'enhanced_at': datetime.now().isoformat(),
            'fallback': True
        }

    async def disconnect(self):
        """Cleanup connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            self.logger.info("🛑 Enhancement Service disconnected")
        except Exception as e:
            self.logger.error(f"Error disconnecting Enhancement Service: {e}")