# filters/volume_filter.py
"""
Volume filter implementation compatible with new architecture.
"""

import logging
from typing import List, Tuple
from core.interfaces import IFilter, MarketData, TradingConfig


class VolumeFilter(IFilter):
    """
    Volume-based filter to determine if a symbol should be traded.
    
    Filters based on:
    - Average volume over period
    - Volume spike detection
    - Price range validation
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger("VolumeFilter")
        
        # Default parameters (can be overridden by config)
        self.min_volume_avg = getattr(config, 'min_volume_avg', 100000)
        self.min_volume_current = getattr(config, 'min_volume_current', 50000)
        self.min_price = getattr(config, 'min_price', 0.5)
        self.max_price = getattr(config, 'max_price', 50.0)
        self.volume_spike_threshold = getattr(config, 'volume_spike_threshold', 1.5)
        self.volume_period = getattr(config, 'volume_period', 20)
    
    async def should_trade(self, symbol: str, bars: List[MarketData]) -> Tuple[bool, str]:
        """
        Determine if symbol should be traded based on volume criteria.
        
        Args:
            symbol: Stock symbol
            bars: List of market data bars
            
        Returns:
            Tuple of (should_trade: bool, reason: str)
        """
        try:
            if not bars or len(bars) < self.volume_period:
                return False, f"Insufficient data: {len(bars) if bars else 0} bars"
            
            current_bar = bars[-1]
            recent_bars = bars[-self.volume_period:]
            
            # 1. Price filter
            if current_bar.close < self.min_price:
                return False, f"Price too low: ${current_bar.close:.2f} < ${self.min_price}"
            
            if current_bar.close > self.max_price:
                return False, f"Price too high: ${current_bar.close:.2f} > ${self.max_price}"
            
            # 2. Current volume filter
            if current_bar.volume < self.min_volume_current:
                return False, f"Current volume too low: {current_bar.volume:,} < {self.min_volume_current:,}"
            
            # 3. Average volume filter
            avg_volume = sum(bar.volume for bar in recent_bars[:-1]) / (len(recent_bars) - 1)
            if avg_volume < self.min_volume_avg:
                return False, f"Average volume too low: {avg_volume:,.0f} < {self.min_volume_avg:,}"
            
            # 4. Volume spike detection
            volume_ratio = current_bar.volume / avg_volume if avg_volume > 0 else 0
            if volume_ratio < self.volume_spike_threshold:
                return False, f"No volume spike: {volume_ratio:.1f}x < {self.volume_spike_threshold}x"
            
            # 5. Additional quality checks
            
            # Check for zero or invalid volume
            if current_bar.volume <= 0:
                return False, "Invalid volume data"
            
            # Check for valid price data
            if any(price <= 0 for price in [current_bar.open, current_bar.high, current_bar.low, current_bar.close]):
                return False, "Invalid price data"
            
            # Check for reasonable price range (high >= low)
            if current_bar.high < current_bar.low:
                return False, "Invalid price range (high < low)"
            
            # Passed all filters
            self.logger.info(f"✅ {symbol} passed volume filter: "
                           f"Price=${current_bar.close:.2f}, "
                           f"Volume={current_bar.volume:,} ({volume_ratio:.1f}x avg)")
            
            return True, f"Volume spike: {volume_ratio:.1f}x average, Price: ${current_bar.close:.2f}"
            
        except Exception as e:
            self.logger.error(f"Error in volume filter for {symbol}: {e}")
            return False, f"Filter error: {str(e)}"
    
    def get_filter_info(self) -> dict:
        """Get filter configuration information"""
        return {
            "name": "VolumeFilter",
            "parameters": {
                "min_volume_avg": self.min_volume_avg,
                "min_volume_current": self.min_volume_current,
                "min_price": self.min_price,
                "max_price": self.max_price,
                "volume_spike_threshold": self.volume_spike_threshold,
                "volume_period": self.volume_period
            }
        }