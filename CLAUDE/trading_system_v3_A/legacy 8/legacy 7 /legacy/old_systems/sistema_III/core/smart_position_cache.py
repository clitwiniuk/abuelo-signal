#!/usr/bin/env python3
"""
Smart Position Cache - Optimización Fase 1
Cache inteligente para posiciones con event-driven invalidation
Reduce API calls de get_positions de 1,440 a 288 calls/día (80% reducción)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List
from threading import Lock
import asyncio

logger = logging.getLogger(__name__)

class SmartPositionCache:
    """
    Cache inteligente para posiciones con event-driven invalidation
    
    OPTIMIZACIÓN CLAVE:
    - ANTES: get_positions() cada ciclo = 2 API calls × 720 ciclos = 1,440 calls/día
    - DESPUÉS: Cache con TTL + invalidation por eventos = ~288 calls/día
    
    Reducción estimada: 80% menos API calls para positions
    """
    
    def __init__(self, ibkr_adapter, cache_ttl_minutes: int = 5):
        self.ibkr = ibkr_adapter
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        
        # Cache storage
        self.cached_positions = {}  # symbol -> Position object
        self.cached_portfolio = {}  # symbol -> Portfolio item
        self.last_update = None
        self.cache_lock = Lock()
        
        # Event-driven invalidation
        self.pending_order_symbols = set()  # Symbols with pending orders
        self.force_refresh_on_next = False
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.force_refreshes = 0
        
        logger.info("🧠 SmartPositionCache initialized")
        logger.info(f"   ⏰ Cache TTL: {cache_ttl_minutes} minutes")
        logger.info("   🎯 Expected 80% reduction in position API calls")
    
    async def get_positions(self) -> Dict[str, any]:
        """
        Get posiciones con smart caching
        
        Returns:
            Dict[symbol, Position] - Current positions
        """
        current_time = datetime.now()
        
        # Check if cache is valid
        should_use_cache = self._should_use_cache(current_time)
        
        if should_use_cache:
            logger.debug("📋 Using cached positions (cache hit)")
            self.cache_hits += 1
            
            with self.cache_lock:
                return self.cached_positions.copy()
        
        # Cache miss - refresh from IBKR
        logger.debug("🔄 Cache miss - refreshing positions from IBKR")
        self.cache_misses += 1
        
        return await self._refresh_positions_from_ibkr(current_time)
    
    async def get_portfolio(self) -> Dict[str, any]:
        """
        Get portfolio con smart caching
        
        Returns:
            Dict[symbol, PortfolioItem] - Current portfolio
        """
        current_time = datetime.now()
        
        # Check if cache is valid
        should_use_cache = self._should_use_cache(current_time)
        
        if should_use_cache:
            logger.debug("📊 Using cached portfolio (cache hit)")
            self.cache_hits += 1
            
            with self.cache_lock:
                return self.cached_portfolio.copy()
        
        # Cache miss - refresh from IBKR
        logger.debug("🔄 Cache miss - refreshing portfolio from IBKR")
        self.cache_misses += 1
        
        positions = await self._refresh_positions_from_ibkr(current_time)
        
        with self.cache_lock:
            return self.cached_portfolio.copy()
    
    def _should_use_cache(self, current_time: datetime) -> bool:
        """Determina si el cache es válido para usar"""
        with self.cache_lock:
            # No cache available
            if self.last_update is None:
                return False
            
            # Force refresh was requested
            if self.force_refresh_on_next:
                return False
            
            # Check TTL
            time_since_update = current_time - self.last_update
            if time_since_update >= self.cache_ttl:
                return False
            
            # Check pending orders (event-driven invalidation)
            if self.pending_order_symbols:
                logger.debug(f"🔄 Cache invalidated by pending orders: {self.pending_order_symbols}")
                return False
            
            return True
    
    async def _refresh_positions_from_ibkr(self, current_time: datetime) -> Dict[str, any]:
        """
        Fetch real positions from IBKR (actual API calls)
        This is where the API calls happen
        """
        try:
            # BULK API CALL: Get all positions in one call
            positions_list = self.ibkr.ib.positions()  # API CALL #1
            portfolio_list = self.ibkr.ib.portfolio()   # API CALL #2
            
            # Process positions
            positions_dict = {}
            for position in positions_list:
                symbol = position.contract.symbol
                positions_dict[symbol] = position
            
            # Process portfolio
            portfolio_dict = {}
            for portfolio_item in portfolio_list:
                symbol = portfolio_item.contract.symbol
                portfolio_dict[symbol] = portfolio_item
            
            # Update cache
            with self.cache_lock:
                self.cached_positions = positions_dict
                self.cached_portfolio = portfolio_dict
                self.last_update = current_time
                
                # Clear invalidation flags
                self.pending_order_symbols.clear()
                self.force_refresh_on_next = False
            
            logger.debug(f"✅ Cache refreshed: {len(positions_dict)} positions, {len(portfolio_dict)} portfolio items")
            
            return positions_dict
            
        except Exception as e:
            logger.error(f"❌ Error refreshing positions from IBKR: {e}")
            
            # Return cached data if available, even if stale
            with self.cache_lock:
                if self.cached_positions:
                    logger.warning("⚠️ Using stale cached positions due to refresh error")
                    return self.cached_positions.copy()
            
            return {}
    
    def invalidate_on_order_event(self, symbol: str, event_type: str = "unknown"):
        """
        Invalidar cache cuando hay order events
        
        Args:
            symbol: Symbol that had an order event
            event_type: Type of event (fill, cancel, etc.)
        """
        with self.cache_lock:
            self.pending_order_symbols.add(symbol)
        
        logger.debug(f"🔔 Cache invalidated for {symbol} due to {event_type}")
    
    def invalidate_on_order_fill(self, symbol: str):
        """Invalidar cache cuando hay order fill"""
        self.invalidate_on_order_event(symbol, "fill")
    
    def invalidate_on_new_order(self, symbol: str):
        """Invalidar cache cuando se coloca nueva orden"""
        self.invalidate_on_order_event(symbol, "new_order")
    
    def force_refresh(self):
        """Forzar refresh en el próximo get_positions()"""
        with self.cache_lock:
            self.force_refresh_on_next = True
            self.force_refreshes += 1
        
        logger.debug("🔄 Forced cache refresh scheduled")
    
    def clear_cache(self):
        """Limpiar todo el cache"""
        with self.cache_lock:
            self.cached_positions.clear()
            self.cached_portfolio.clear()
            self.last_update = None
            self.pending_order_symbols.clear()
            self.force_refresh_on_next = False
        
        logger.info("🧹 Position cache cleared")
    
    def get_cached_position(self, symbol: str) -> Optional[any]:
        """Get posición específica desde cache (no API call)"""
        with self.cache_lock:
            return self.cached_positions.get(symbol)
    
    def get_cached_portfolio_item(self, symbol: str) -> Optional[any]:
        """Get portfolio item específico desde cache (no API call)"""
        with self.cache_lock:
            return self.cached_portfolio.get(symbol)
    
    def is_cache_valid(self) -> bool:
        """Check si el cache es válido actualmente"""
        return self._should_use_cache(datetime.now())
    
    def get_cache_age_seconds(self) -> Optional[float]:
        """Get edad del cache en segundos"""
        with self.cache_lock:
            if self.last_update is None:
                return None
            
            return (datetime.now() - self.last_update).total_seconds()
    
    def get_cache_statistics(self) -> Dict[str, any]:
        """Get estadísticas de performance del cache"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        with self.cache_lock:
            cached_symbols = len(self.cached_positions)
            cache_age = self.get_cache_age_seconds()
            pending_invalidations = len(self.pending_order_symbols)
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate_percent': hit_rate,
            'force_refreshes': self.force_refreshes,
            'cached_symbols': cached_symbols,
            'cache_age_seconds': cache_age,
            'pending_invalidations': pending_invalidations,
            'cache_ttl_minutes': self.cache_ttl.total_seconds() / 60
        }
    
    def get_status_report(self) -> str:
        """Genera reporte de status del SmartPositionCache"""
        stats = self.get_cache_statistics()
        
        cache_status = "✅ VALID" if self.is_cache_valid() else "❌ INVALID"
        
        report = [
            "📊 SMART POSITION CACHE STATUS",
            f"🎯 Cache status: {cache_status}",
            f"📈 Hit rate: {stats['hit_rate_percent']:.1f}% ({stats['cache_hits']} hits, {stats['cache_misses']} misses)",
            f"📋 Cached symbols: {stats['cached_symbols']}",
            f"⏰ Cache age: {stats['cache_age_seconds']:.1f}s (TTL: {stats['cache_ttl_minutes']:.1f}min)"
        ]
        
        if stats['pending_invalidations'] > 0:
            report.append(f"🔔 Pending invalidations: {stats['pending_invalidations']}")
        
        if stats['force_refreshes'] > 0:
            report.append(f"🔄 Force refreshes: {stats['force_refreshes']}")
        
        # Estimated API savings
        total_requests = stats['cache_hits'] + stats['cache_misses']
        if total_requests > 0:
            api_calls_saved = stats['cache_hits'] * 2  # 2 API calls per cache hit saved
            report.append(f"⚡ API calls saved: ~{api_calls_saved} ({stats['hit_rate_percent']:.1f}% reduction)")
        
        return "\n".join(report)