# core/data_collection_stage.py
"""
Data Collection Stage - Pipeline Pattern
Concentrated IBKR data fetching with intelligent batching and caching
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time

from core.pipeline import PipelineStage
from core.interfaces import MarketData, IDataProvider


class DataCollectionStage(PipelineStage):
    """
    Stage 1: Data Collection
    - Fetches ALL market data in batch
    - Handles IBKR rate limiting intelligently 
    - Caches data to minimize IBKR calls
    - NO analysis logic here
    """
    
    def __init__(self, data_provider: IDataProvider, config):
        super().__init__("DataCollection")
        self.data_provider = data_provider
        self.config = config
        
        # Data caching for efficiency
        self.data_cache: Dict[str, List[MarketData]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_ttl = 60  # 1 minute cache
        
        # Batch processing settings - REDUCED to 1 to prevent pipeline blocks
        self.batch_size = 1  # Process 1 symbol at a time to prevent timeouts blocking others
        self.batch_delay = 0.2  # Reduced delay between symbols
        
        # Enhanced circuit breaker for problematic symbols
        self.failed_symbols = set()
        self.max_failures = 2
        self.symbol_failure_count: Dict[str, int] = {}
        self.symbol_timeout_count: Dict[str, int] = {}
        self.persistent_timeout_threshold = 3  # Force reconnection after 3 consecutive timeouts
        
        self.logger.info(f"🏭 DataCollectionStage initialized: batch_size={self.batch_size}, cache_ttl={self.cache_ttl}s")
    
    async def _process(self, symbols: List[str]) -> Dict[str, List[MarketData]]:
        """
        Fetch market data for all symbols in optimized batches, ensuring data is clean.

        Args:
            symbols: List of symbol strings to fetch data for.

        Returns:
            A dictionary mapping each symbol to its list of MarketData bars, free of duplicates.
        """
        if not symbols:
            return {}

        active_symbols = [s for s in symbols if s not in self.failed_symbols]
        if len(active_symbols) != len(symbols):
            skipped = set(symbols) - set(active_symbols)
            self.logger.info(f"⚠️ Skipping {len(skipped)} failed symbols: {skipped}")

        if not active_symbols:
            self.logger.warning("📭 No active symbols to process")
            return {}

        # Only log data collection if there are many symbols (more relevant)
        if len(active_symbols) > 20:
            self.logger.info(f"📊 Collecting data for {len(active_symbols)} symbols")
        else:
            self.logger.debug(f"📊 Collecting data for {len(active_symbols)} symbols: {active_symbols[:10]}{'...' if len(active_symbols) > 10 else ''}")
        if self.failed_symbols:
            self.logger.warning(f"🚫 Failed symbols being skipped: {list(self.failed_symbols)[:10]}{'...' if len(self.failed_symbols) > 10 else ''} (total: {len(self.failed_symbols)})")

        # Check cache first
        market_data = {}
        symbols_to_fetch = []
        for symbol in active_symbols:
            cached_data = self._get_cached_data(symbol)
            if cached_data:
                market_data[symbol] = cached_data
                self.logger.debug(f"♻️ Using cached data for {symbol}")
            else:
                symbols_to_fetch.append(symbol)

        if symbols_to_fetch:
            self.logger.info(f"🔄 Fetching fresh data for {len(symbols_to_fetch)} symbols: {symbols_to_fetch}")
            fetched_data = await self._fetch_data_in_batches(symbols_to_fetch)

            # Combine with cache, deduplicate, and update
            for symbol, new_bars in fetched_data.items():
                # Combine cached data with new data
                cached_bars = self._get_cached_data(symbol) or []
                combined_bars = cached_bars + new_bars
                
                original_count = len(combined_bars)
                
                # Deduplicate the combined list, keeping the latest bar based on timestamp
                seen_timestamps = {}
                for bar in combined_bars:
                    # Almacena la barra más reciente para cada timestamp
                    seen_timestamps[bar.timestamp] = bar
                
                # Reconstruir la lista ordenada por timestamp
                unique_bars = sorted(seen_timestamps.values(), key=lambda b: b.timestamp)
                
                deduplicated_count = len(unique_bars)
                if original_count > deduplicated_count:
                    self.logger.info(f"✂️ Deduplicated {original_count - deduplicated_count} bars for {symbol}, resulting in {deduplicated_count} unique bars.")
                
                market_data[symbol] = unique_bars
                self._cache_data(symbol, unique_bars)

        self.logger.info(f"✅ Data collection completed: {len(market_data)} datasets ready")
        return market_data
    
    async def _fetch_data_in_batches(self, symbols: List[str]) -> Dict[str, List[MarketData]]:
        """Fetch data in small batches to prevent IBKR overload"""
        all_data = {}
        
        # Process symbols in batches
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(symbols) + self.batch_size - 1) // self.batch_size
            
            # Reduced logging: only log batch processing in debug mode
            self.logger.debug(f"📦 Processing batch {batch_num}/{total_batches}: {batch}")
            
            # Process batch concurrently but with limited concurrency
            batch_tasks = []
            for symbol in batch:
                task = asyncio.create_task(self._fetch_symbol_data(symbol))
                batch_tasks.append((symbol, task))
            
            # Wait for batch completion with timeout (reduced since batch_size=1)
            try:
                batch_results = await asyncio.wait_for(
                    self._wait_for_batch(batch_tasks), 
                    timeout=45.0  # 45 seconds max per batch (adjusted for higher latency)
                )
                all_data.update(batch_results)
                
            except asyncio.TimeoutError:
                self.logger.error(f"⏰ Batch {batch_num} timed out after 18s")
                # Cancel remaining tasks
                for symbol, task in batch_tasks:
                    if not task.done():
                        task.cancel()
                        self._mark_symbol_failed(symbol)
            
            # Delay between batches to prevent overwhelming IBKR
            if i + self.batch_size < len(symbols):
                await asyncio.sleep(self.batch_delay)
        
        return all_data
    
    async def _wait_for_batch(self, batch_tasks: List[tuple]) -> Dict[str, List[MarketData]]:
        """Wait for a batch of symbol data fetching tasks"""
        batch_data = {}
        
        for symbol, task in batch_tasks:
            try:
                data = await task
                if data:
                    batch_data[symbol] = data
                    self._cache_data(symbol, data)
                else:
                    # Reduced logging: only log no data in debug mode (common during off-hours)
                    self.logger.debug(f"📭 No data received for {symbol}")
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to fetch data for {symbol}: {e}")
                self._mark_symbol_failed(symbol)
        
        return batch_data
    
    async def _fetch_symbol_data(self, symbol: str) -> Optional[List[MarketData]]:
        """Fetch data for a single symbol with aggressive timeout to prevent pipeline blocks"""
        import time
        t0 = time.time()
        
        try:
            # AGGRESSIVE TIMEOUT: 15s per symbol to prevent 20-minute pipeline blocks
            data = await asyncio.wait_for(
                self.data_provider.get_bars(
                    symbol=symbol,
                    timeframe=self.config.timeframe,
                    count=100  # Get enough bars for analysis
                ),
                timeout=40.0  # 40 second timeout per symbol (adjusted for higher latency)
            )
            
            # Log fetch duration for performance monitoring
            fetch_duration = time.time() - t0
            
            if not data:
                # Reduced logging: only log no historical data in debug mode
                self.logger.debug(f"📭 No historical data available for {symbol} after {fetch_duration:.2f}s")
                return None
            
            # Enrich latest bar with current bid/ask data for extended hours
            enriched_data = await self._enrich_with_current_prices(symbol, data)
            
            final_duration = time.time() - t0
            if enriched_data:
                self.logger.debug(f"✅ Fetched {len(enriched_data)} bars for {symbol} (with bid/ask) in {final_duration:.2f}s")
                return enriched_data
            else:
                self.logger.debug(f"✅ Fetched {len(data)} bars for {symbol} (historical only) in {final_duration:.2f}s")
                return data
                
        except asyncio.TimeoutError:
            duration = time.time() - t0
            self.logger.error(f"⏰ TIMEOUT: {symbol} exceeded 15s limit (actual: {duration:.2f}s) - preventing pipeline block")
            
            # Enhanced timeout tracking for circuit breaker
            self.symbol_timeout_count[symbol] = self.symbol_timeout_count.get(symbol, 0) + 1
            
            # Force reconnection if persistent timeouts
            if self.symbol_timeout_count[symbol] >= self.persistent_timeout_threshold:
                self.logger.warning(f"🔄 {symbol} had {self.symbol_timeout_count[symbol]} consecutive timeouts - forcing reconnection")
                await self._force_reconnection()
                self.symbol_timeout_count[symbol] = 0  # Reset counter after reconnection
            
            self._mark_symbol_failed(symbol)
            return None
        except Exception as e:
            duration = time.time() - t0
            self.logger.error(f"❌ Error fetching {symbol} after {duration:.2f}s: {e}")
            # Reset timeout counter on successful failure (non-timeout error)
            if symbol in self.symbol_timeout_count:
                self.symbol_timeout_count[symbol] = 0
            self._mark_symbol_failed(symbol)
            return None
    
    async def _enrich_with_current_prices(self, symbol: str, historical_data: List[MarketData]) -> Optional[List[MarketData]]:
        """Enrich latest bar with current bid/ask data"""
        try:
            # Only enrich if we have method to get market data snapshot
            if not hasattr(self.data_provider, 'get_market_data_snapshot'):
                return historical_data
            
            # Get current market data snapshot
            snapshot = await self.data_provider.get_market_data_snapshot(symbol)
            
            if not snapshot or not historical_data:
                return historical_data
            
            # Create enriched copy of historical data
            enriched_data = historical_data.copy()
            latest_bar = enriched_data[-1]
            
            # Update latest bar with current bid/ask if available
            if 'bid' in snapshot and snapshot['bid'] > 0:
                latest_bar.bid = float(snapshot['bid'])
            
            if 'ask' in snapshot and snapshot['ask'] > 0:
                latest_bar.ask = float(snapshot['ask'])
            
            if 'bid_size' in snapshot:
                latest_bar.bid_size = int(snapshot.get('bid_size', 0))
                
            if 'ask_size' in snapshot:
                latest_bar.ask_size = int(snapshot.get('ask_size', 0))
            
            if 'last_price' in snapshot and snapshot['last_price'] > 0:
                latest_bar.last_price = float(snapshot['last_price'])
            
            # Only log if we got meaningful bid/ask data
            if latest_bar.bid and latest_bar.ask:
                spread = latest_bar.ask - latest_bar.bid
                self.logger.debug(f"💰 {symbol}: bid={latest_bar.bid:.4f}, ask={latest_bar.ask:.4f}, spread=${spread:.4f}")
            
            return enriched_data
            
        except Exception as e:
            self.logger.debug(f"⚠️ Could not enrich {symbol} with current prices: {e}")
            return historical_data
    
    def _get_cached_data(self, symbol: str) -> Optional[List[MarketData]]:
        """Get cached data if still fresh"""
        if symbol not in self.data_cache or symbol not in self.cache_timestamps:
            return None
        
        cache_age = (datetime.now() - self.cache_timestamps[symbol]).total_seconds()
        if cache_age > self.cache_ttl:
            # Cache expired
            self.data_cache.pop(symbol, None)
            self.cache_timestamps.pop(symbol, None)
            return None
        
        return self.data_cache[symbol]
    
    def _cache_data(self, symbol: str, data: List[MarketData]):
        """Cache data for symbol"""
        self.data_cache[symbol] = data
        self.cache_timestamps[symbol] = datetime.now()
    
    async def _force_reconnection(self):
        """Force IBKR reconnection for persistent latency issues"""
        try:
            if hasattr(self.data_provider, 'disconnect') and hasattr(self.data_provider, 'connect'):
                self.logger.info("🔄 Forcing IBKR reconnection due to persistent timeouts...")
                await self.data_provider.disconnect()
                await asyncio.sleep(2)  # Brief pause
                await self.data_provider.connect()
                self.logger.info("✅ IBKR reconnection completed")
            else:
                self.logger.warning("⚠️ Data provider doesn't support reconnection")
        except Exception as e:
            self.logger.error(f"❌ Failed to force reconnection: {e}")
    
    def _mark_symbol_failed(self, symbol: str):
        """Mark symbol as failed and remove from processing"""
        if symbol not in self.failed_symbols:
            # Track failure count
            self.symbol_failure_count[symbol] = self.symbol_failure_count.get(symbol, 0) + 1
            
            # Only mark as permanently failed after max failures
            if self.symbol_failure_count[symbol] >= self.max_failures:
                self.failed_symbols.add(symbol)
                self.logger.warning(f"🚫 Marked {symbol} as permanently failed after {self.symbol_failure_count[symbol]} failures")
            else:
                self.logger.warning(f"⚠️ {symbol} failed ({self.symbol_failure_count[symbol]}/{self.max_failures}) - temporary failure")
    
    def clear_failed_symbols(self):
        """Clear failed symbols list (for recovery)"""
        cleared_count = len(self.failed_symbols)
        self.failed_symbols.clear()
        self.symbol_failure_count.clear()
        self.symbol_timeout_count.clear()
        if cleared_count > 0:
            self.logger.info(f"🔄 Cleared {cleared_count} failed symbols and reset counters for retry")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cached_symbols': len(self.data_cache),
            'failed_symbols': len(self.failed_symbols),
            'cache_hit_potential': len(self.cache_timestamps)
        }
    
    async def add_symbol(self, symbol: str) -> bool:
        """
        Add a symbol to the data collection stage.
        This is a compatibility method for pipeline integration.
        The actual data collection happens when the pipeline processes symbols.
        
        Args:
            symbol: Symbol to add to monitoring
            
        Returns:
            bool: Always True as symbols are processed dynamically
        """
        # Remove from failed symbols if it was previously failed to allow retry
        if symbol in self.failed_symbols:
            self.failed_symbols.remove(symbol)
            self.symbol_failure_count.pop(symbol, None)
            self.symbol_timeout_count.pop(symbol, None)
            self.logger.info(f"🔄 Removed {symbol} from failed list - will retry data collection")
        
        # Clear any stale cache for this symbol to ensure fresh data
        if symbol in self.data_cache:
            self.data_cache.pop(symbol, None)
            self.cache_timestamps.pop(symbol, None)
            self.logger.debug(f"🗑️ Cleared stale cache for {symbol}")
        
        self.logger.debug(f"✅ {symbol} added to data collection monitoring")
        return True
    
    async def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from data collection stage.
        This cleans up any cached data and failure tracking.
        
        Args:
            symbol: Symbol to remove from monitoring
            
        Returns:
            bool: Always True
        """
        # Clean up all references to this symbol
        self.data_cache.pop(symbol, None)
        self.cache_timestamps.pop(symbol, None)
        self.failed_symbols.discard(symbol)
        self.symbol_failure_count.pop(symbol, None)
        self.symbol_timeout_count.pop(symbol, None)
        
        self.logger.debug(f"🗑️ {symbol} removed from data collection monitoring")
        return True