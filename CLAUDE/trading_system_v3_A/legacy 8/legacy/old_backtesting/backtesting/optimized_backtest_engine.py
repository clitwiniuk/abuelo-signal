#!/usr/bin/env python3
"""
Optimized MACDV Backtesting Engine
Implements optimizations based on backtest analysis
"""

import asyncio
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine, BacktestTrade

@dataclass
class OptimizationConfig:
    """Configuration for optimizations"""
    # Trailing stop optimizations
    trailing_stop_pct: float = 0.08  # Increased from 5% to 8%
    dynamic_trailing: bool = True
    
    # Time filters
    blocked_hours: List[int] = None  # Hours to avoid trading
    preferred_hours: List[int] = None  # Hours to prioritize
    
    # Symbol filtering (disabled by default - trade ALL symbols)
    enable_symbol_filtering: bool = False  # Set to True to enable filtering
    whitelist_symbols: List[str] = None  # Only trade these symbols (if filtering enabled)
    blacklist_symbols: List[str] = None  # Avoid these symbols (if filtering enabled)
    
    # Position management
    max_hold_minutes_base: int = 240  # Base hold time
    extended_hold_multiplier: float = 2.0  # Extend for strong trends
    
    # Risk management
    use_atr_stops: bool = True  # Use ATR-based stops
    atr_multiplier: float = 2.0  # ATR multiplier for stops
    
    def __post_init__(self):
        # Set defaults for ET timezone (data now correctly converted from Spain)
        if self.blocked_hours is None:
            self.blocked_hours = []  # No blocked hours - allow trading during all market hours
            
        if self.preferred_hours is None:
            self.preferred_hours = [10, 11, 12, 13, 14, 15]  # Regular market hours ET 09:30-16:00
            
        # Symbol lists only used if filtering is enabled
        if self.whitelist_symbols is None:
            self.whitelist_symbols = ['ASST', 'ALTS', 'BTBT']  # Profitable symbols
            
        if self.blacklist_symbols is None:
            self.blacklist_symbols = ['BTBD', 'AEHL', 'CAMP']  # Losing symbols

class OptimizedMacdvBacktestEngine(MacdvBacktestEngine):
    """Enhanced backtesting engine with optimizations"""
    
    def __init__(self, optimization_config: OptimizationConfig = None, **kwargs):
        super().__init__(**kwargs)
        self.opt_config = optimization_config or OptimizationConfig()
        
        # Override base parameters with optimized ones
        self.trailing_stop_pct = self.opt_config.trailing_stop_pct
        
    def _should_enter_trade(self, symbol: str, timestamp: datetime, price: float) -> bool:
        """Enhanced entry logic with ET timezone filters"""
        
        # Original entry logic
        if not super()._should_enter_trade(symbol, timestamp, price):
            return False
            
        # Time filters (now data is correctly in ET)
        hour = timestamp.hour
        
        # Apply blocked hours filter (if any)
        if hour in self.opt_config.blocked_hours:
            return False
            
        # Symbol filters (only if enabled)
        if self.opt_config.enable_symbol_filtering:
            if self.opt_config.whitelist_symbols and symbol not in self.opt_config.whitelist_symbols:
                return False
                
            if self.opt_config.blacklist_symbols and symbol in self.opt_config.blacklist_symbols:
                return False
            
        return True
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range for dynamic stops"""
        if len(df) < period:
            return 0.0
            
        # Calculate True Range
        df = df.copy()
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
        # Return average of last 'period' values
        return df['true_range'].tail(period).mean()
    
    def _calculate_dynamic_trailing_stop(self, symbol: str, entry_price: float, 
                                       current_timestamp: datetime) -> float:
        """Calculate dynamic trailing stop based on ATR"""
        
        if not self.opt_config.use_atr_stops:
            return self.trailing_stop_pct
            
        try:
            # Get recent data for ATR calculation
            df = self.data_provider.get_data(symbol)
            recent_df = df[df.index <= current_timestamp].tail(20)
            
            if len(recent_df) < 14:
                return self.trailing_stop_pct  # Fallback to default
                
            atr = self._calculate_atr(recent_df)
            
            if atr > 0:
                # Convert ATR to percentage stop
                atr_stop_pct = (atr * self.opt_config.atr_multiplier) / entry_price
                
                # Use the more conservative of ATR stop or configured stop
                return max(atr_stop_pct, self.trailing_stop_pct)
                
        except Exception as e:
            if self.debug:
                print(f"Error calculating ATR for {symbol}: {e}")
                
        return self.trailing_stop_pct
    
    def _get_dynamic_max_hold_time(self, symbol: str, entry_price: float, 
                                 current_price: float, entry_time: datetime) -> int:
        """Calculate dynamic hold time based on performance"""
        
        base_hold = self.opt_config.max_hold_minutes_base
        
        # If trade is profitable and in strong trend, extend hold time
        if current_price > entry_price:
            profit_pct = (current_price - entry_price) / entry_price
            
            # For profits > 2%, consider extending hold time
            if profit_pct > 0.02:
                # Check if we're in preferred trading hours
                current_hour = entry_time.hour
                if current_hour in self.opt_config.preferred_hours:
                    return int(base_hold * self.opt_config.extended_hold_multiplier)
                    
        return base_hold
    
    def _update_position_exit_conditions(self, symbol: str, position: dict, 
                                       current_price: float, current_time: datetime) -> Tuple[bool, str]:
        """Enhanced exit logic with dynamic parameters"""
        
        entry_price = position['entry_price']
        entry_time = position['entry_time']
        current_max_profit = position.get('max_profit', 0.0)
        
        # Calculate dynamic trailing stop
        dynamic_stop_pct = self._calculate_dynamic_trailing_stop(symbol, entry_price, current_time)
        
        # Calculate dynamic max hold time
        dynamic_max_hold = self._get_dynamic_max_hold_time(symbol, entry_price, current_price, entry_time)
        
        # Check time-based exit first
        hold_minutes = (current_time - entry_time).total_seconds() / 60
        if hold_minutes >= dynamic_max_hold:
            return True, "MAX_HOLD_TIME"
            
        # Check end of day
        if current_time.hour >= 20 or current_time.hour < 9:
            return True, "END_OF_DAY"
            
        # Enhanced trailing stop logic
        current_profit = current_price - entry_price
        
        # Update max profit
        if current_profit > current_max_profit:
            position['max_profit'] = current_profit
            current_max_profit = current_profit
            
        # Trailing stop trigger - only after some minimum profit
        min_profit_threshold = entry_price * 0.01  # 1% minimum profit before trailing
        
        if current_max_profit > min_profit_threshold:
            # Calculate trailing stop level
            trailing_stop_level = entry_price + (current_max_profit * (1 - dynamic_stop_pct))
            
            if current_price <= trailing_stop_level:
                return True, "TRAILING_STOP"
                
        # Take profit at significant levels (optional aggressive take profit)
        profit_pct = current_profit / entry_price
        if profit_pct > 0.05:  # 5% take profit
            return True, "TAKE_PROFIT"
            
        return False, ""
    
    async def run_optimized_backtest(self, symbols: List[str] = None, 
                                   max_symbols: int = None, days_back: int = 30) -> Dict:
        """Run backtest with optimizations"""
        
        print(f"🎯 OPTIMIZED BACKTESTING")
        print(f"⚙️  Optimizations enabled:")
        print(f"   📊 Trailing stop: {self.opt_config.trailing_stop_pct:.1%}")
        print(f"   🚫 Blocked hours: {self.opt_config.blocked_hours}")
        print(f"   ✅ Preferred hours: {self.opt_config.preferred_hours}")
        print(f"   🎯 Symbol filtering: {'ENABLED' if self.opt_config.enable_symbol_filtering else 'DISABLED (ALL symbols)'}")
        if self.opt_config.enable_symbol_filtering:
            print(f"   📝 Symbol whitelist: {len(self.opt_config.whitelist_symbols)} symbols")
            print(f"   🚫 Symbol blacklist: {len(self.opt_config.blacklist_symbols)} symbols")
        print(f"   ⏱️  ATR-based stops: {self.opt_config.use_atr_stops}")
        print("")
        
        # Run the standard backtest with optimizations
        return await self.run_backtest(symbols, max_symbols, days_back)

async def run_optimization_comparison():
    """Compare original vs optimized backtesting"""
    
    print("🔬 OPTIMIZATION COMPARISON")
    print("=" * 50)
    
    # Original parameters
    print("\n1️⃣  Running ORIGINAL backtest...")
    original_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,  # Original 5%
        max_hold_minutes=240,
        debug=False
    )
    
    if not await original_engine.initialize():
        print("❌ Failed to initialize original engine")
        return
        
    original_results = await original_engine.run_backtest(max_symbols=10, days_back=30)
    
    # Optimized parameters  
    print("\n2️⃣  Running OPTIMIZED backtest...")
    opt_config = OptimizationConfig()
    optimized_engine = OptimizedMacdvBacktestEngine(
        optimization_config=opt_config,
        position_size=200.0,
        debug=False
    )
    
    if not await optimized_engine.initialize():
        print("❌ Failed to initialize optimized engine")
        return
        
    optimized_results = await optimized_engine.run_optimized_backtest(max_symbols=10, days_back=30)
    
    # Compare results
    print(f"\n📊 COMPARISON SUMMARY:")
    print(f"{'Metric':<20} | {'Original':<12} | {'Optimized':<12} | {'Change':<10}")
    print("-" * 65)
    
    if original_results and optimized_results:
        orig_trades = sum(r.total_trades for r in original_results.values())
        orig_pnl = sum(r.total_pnl for r in original_results.values())
        
        opt_trades = sum(r.total_trades for r in optimized_results.values())
        opt_pnl = sum(r.total_pnl for r in optimized_results.values())
        
        pnl_change = opt_pnl - orig_pnl
        trade_change = opt_trades - orig_trades
        
        print(f"{'Total Trades':<20} | {orig_trades:<12} | {opt_trades:<12} | {trade_change:+}")
        print(f"{'Total P&L':<20} | ${orig_pnl:<11.2f} | ${opt_pnl:<11.2f} | ${pnl_change:+.2f}")
        
        if orig_trades > 0 and opt_trades > 0:
            orig_avg = orig_pnl / orig_trades
            opt_avg = opt_pnl / opt_trades
            avg_change = opt_avg - orig_avg
            print(f"{'Avg P&L/Trade':<20} | ${orig_avg:<11.2f} | ${opt_avg:<11.2f} | ${avg_change:+.2f}")
            
        print(f"\n💡 Optimization Impact: {'+' if pnl_change > 0 else ''}${pnl_change:.2f}")
        
        # Save both results
        orig_file = original_engine.save_results_to_csv(suffix="_original")
        opt_file = optimized_engine.save_results_to_csv(suffix="_optimized")
        
        print(f"\n📁 Results saved:")
        print(f"   Original: {orig_file}")
        print(f"   Optimized: {opt_file}")

if __name__ == "__main__":
    asyncio.run(run_optimization_comparison())