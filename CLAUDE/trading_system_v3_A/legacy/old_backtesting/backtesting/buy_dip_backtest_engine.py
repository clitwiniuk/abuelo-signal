#!/usr/bin/env python3
"""
Buy-the-Dip MACDV Backtest Engine
Modifies MACDV behavior to wait for 4% price dip after signal before entering
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine, BacktestResults, BacktestTrade


@dataclass
class PendingSignal:
    """Pending buy signal waiting for dip"""
    symbol: str
    signal_time: datetime
    signal_price: float
    target_entry_price: float  # 4% below signal price
    expires_at: datetime


class BuyDipBacktestEngine(MacdvBacktestEngine):
    """
    Modified MACDV backtest engine that waits for 4% price dip after signal
    """
    
    def __init__(self,
                 position_size: float = 200.0,
                 trailing_stop_pct: float = 0.08,  # 8% trailing stop
                 max_hold_minutes: int = 240,
                 entry_discount_pct: float = 0.04,  # 4% discount for entry
                 signal_timeout_minutes: int = 60,  # Wait max 60 min for dip
                 debug: bool = False):
        
        super().__init__(position_size, trailing_stop_pct, max_hold_minutes, debug)
        
        self.entry_discount_pct = entry_discount_pct
        self.signal_timeout_minutes = signal_timeout_minutes
        
        # Track pending signals waiting for price dip
        self.pending_signals: Dict[str, PendingSignal] = {}
        
        self.logger.info("💡 BUY-THE-DIP MACDV BACKTEST ENGINE")
        self.logger.info(f"   📉 Entry discount: {entry_discount_pct*100}%")
        self.logger.info(f"   🛑 Trailing stop: {trailing_stop_pct*100}%")
        self.logger.info(f"   ⏰ Signal timeout: {signal_timeout_minutes} min")
    
    async def process_market_data(self, symbol: str, data: pd.DataFrame) -> Optional[BacktestResults]:
        """
        Process market data with buy-the-dip logic
        """
        if data.empty:
            return None
            
        # Sort by timestamp
        data = data.sort_values('timestamp').reset_index(drop=True)
        
        trades = []
        current_position = None
        current_entry_time = None
        current_entry_price = None
        max_profit = 0.0
        max_drawdown = 0.0
        
        for idx, row in data.iterrows():
            timestamp = pd.to_datetime(row['timestamp'])
            price = float(row['close'])
            volume = float(row.get('volume', 0))
            
            # Clean up expired signals
            self._cleanup_expired_signals(timestamp)
            
            # Check if we have a position
            if current_position is not None:
                # Manage existing position
                trade_result = self._process_position_exit(
                    symbol, timestamp, price, current_entry_time, 
                    current_entry_price, max_profit, max_drawdown
                )
                
                if trade_result:
                    trades.append(trade_result)
                    current_position = None
                    current_entry_time = None
                    current_entry_price = None
                    max_profit = 0.0
                    max_drawdown = 0.0
                else:
                    # Update profit/loss tracking
                    current_pnl = (price - current_entry_price) * current_position
                    max_profit = max(max_profit, current_pnl) if current_pnl > 0 else max_profit
                    max_drawdown = min(max_drawdown, current_pnl) if current_pnl < 0 else max_drawdown
            else:
                # Check for entry opportunities
                
                # 1. Check if we can fill a pending signal (price dipped enough)
                if symbol in self.pending_signals:
                    pending = self.pending_signals[symbol]
                    if price <= pending.target_entry_price:
                        # Price dipped enough! Enter position
                        quantity = int(self.position_size / price)
                        if quantity > 0:
                            current_position = quantity
                            current_entry_time = timestamp
                            current_entry_price = price
                            
                            if self.debug:
                                self.logger.info(f"🎯 DIP ENTRY: {symbol} @ ${price:.4f} "
                                               f"(signal was ${pending.signal_price:.4f}, "
                                               f"waited {(timestamp - pending.signal_time).total_seconds()/60:.1f}min)")
                            
                            # Remove the pending signal
                            del self.pending_signals[symbol]
                        continue
                
                # 2. Check for new MACDV signals
                signal_strength = self._evaluate_macdv_signal(row, idx, data)
                if signal_strength > 0.7:  # Strong signal threshold
                    # Create pending signal instead of immediate entry
                    target_price = price * (1 - self.entry_discount_pct)
                    expires_at = timestamp + timedelta(minutes=self.signal_timeout_minutes)
                    
                    self.pending_signals[symbol] = PendingSignal(
                        symbol=symbol,
                        signal_time=timestamp,
                        signal_price=price,
                        target_entry_price=target_price,
                        expires_at=expires_at
                    )
                    
                    if self.debug:
                        self.logger.info(f"📡 SIGNAL PENDING: {symbol} @ ${price:.4f} "
                                       f"-> waiting for ${target_price:.4f} (-{self.entry_discount_pct*100}%)")
        
        # Clean up any remaining pending signals for this symbol
        if symbol in self.pending_signals:
            del self.pending_signals[symbol]
        
        # Create results
        if not trades:
            return BacktestResults(
                symbol=symbol,
                trades=[],
                total_trades=0,
                total_pnl=0.0,
                win_rate=0.0,
                avg_pnl=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                avg_duration_minutes=0.0
            )
        
        # Calculate statistics
        total_pnl = sum(t.pnl for t in trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        win_rate = (winning_trades / len(trades)) * 100
        avg_pnl = total_pnl / len(trades)
        best_trade = max(t.pnl for t in trades)
        worst_trade = min(t.pnl for t in trades)
        avg_duration = sum(t.duration_minutes for t in trades) / len(trades)
        
        return BacktestResults(
            symbol=symbol,
            trades=trades,
            total_trades=len(trades),
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade,
            avg_duration_minutes=avg_duration
        )
    
    def _cleanup_expired_signals(self, current_time: datetime):
        """Remove expired pending signals"""
        expired_symbols = []
        for symbol, signal in self.pending_signals.items():
            if current_time >= signal.expires_at:
                expired_symbols.append(symbol)
                if self.debug:
                    self.logger.info(f"⏰ EXPIRED: {symbol} signal timed out "
                                   f"(waited {self.signal_timeout_minutes}min)")
        
        for symbol in expired_symbols:
            del self.pending_signals[symbol]
    
    def _evaluate_macdv_signal(self, row, idx: int, data: pd.DataFrame) -> float:
        """
        Evaluate MACDV signal strength (simplified version)
        Returns 0-1 signal strength
        """
        try:
            # Need at least 20 bars for MACD calculation
            if idx < 20:
                return 0.0
            
            # Get recent data for calculation
            recent_data = data.iloc[max(0, idx-20):idx+1].copy()
            
            if len(recent_data) < 10:
                return 0.0
            
            # Calculate MACD (simplified)
            close_prices = recent_data['close']
            ema12 = close_prices.ewm(span=12).mean()
            ema26 = close_prices.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line
            
            # Check for bullish conditions
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            
            signal_strength = 0.0
            
            # MACD above signal line
            if current_macd > current_signal:
                signal_strength += 0.3
            
            # Histogram increasing
            if len(histogram) >= 2 and current_histogram > histogram.iloc[-2]:
                signal_strength += 0.2
            
            # Volume check (simplified)
            current_volume = row.get('volume', 0)
            if idx >= 10:
                avg_volume = data.iloc[idx-10:idx]['volume'].mean()
                if current_volume > avg_volume * 1.2:  # 20% above average
                    signal_strength += 0.3
            
            # Price momentum
            if idx >= 5:
                price_change = (row['close'] - data.iloc[idx-5]['close']) / data.iloc[idx-5]['close']
                if price_change > 0.01:  # 1% price increase
                    signal_strength += 0.2
            
            return min(signal_strength, 1.0)
            
        except Exception as e:
            if self.debug:
                self.logger.error(f"Error evaluating signal: {e}")
            return 0.0
    
    def save_results_to_csv(self, filename: str = None, suffix: str = "_buy_dip") -> str:
        """Save buy-the-dip results with descriptive suffix"""
        return super().save_results_to_csv(filename, suffix)


async def run_buy_dip_comparison_test():
    """
    Compare original MACDV vs buy-the-dip MACDV
    """
    print("💡 BUY-THE-DIP MACDV COMPARISON TEST")
    print("Original vs Buy-the-Dip (4% entry discount + 8% trailing)")
    print("=" * 70)
    
    # Test 1: Original MACDV
    print("\n📊 TESTING ORIGINAL MACDV (immediate entry, 5% trailing)...")
    original_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,  # Original 5%
        max_hold_minutes=240,
        debug=False
    )
    
    if not await original_engine.initialize():
        print("❌ Failed to initialize original engine")
        return
        
    original_results = await original_engine.run_backtest(
        symbols=None,
        max_symbols=None,
        days_back=30
    )
    
    # Test 2: Buy-the-Dip MACDV
    print("\n💡 TESTING BUY-THE-DIP MACDV (4% discount entry, 8% trailing)...")
    dip_engine = BuyDipBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.08,  # 8% trailing
        max_hold_minutes=240,
        entry_discount_pct=0.04,  # 4% entry discount
        signal_timeout_minutes=60,  # Wait up to 1 hour
        debug=False
    )
    
    if not await dip_engine.initialize():
        print("❌ Failed to initialize dip engine")
        return
        
    dip_results = await dip_engine.run_backtest(
        symbols=None,
        max_symbols=None,
        days_back=30
    )
    
    # Compare results
    print("\n📈 COMPARISON RESULTS")
    print("=" * 70)
    
    if original_results and dip_results:
        # Original stats
        orig_trades = sum(r.total_trades for r in original_results.values())
        orig_pnl = sum(r.total_pnl for r in original_results.values())
        orig_symbols = len([r for r in original_results.values() if r.total_trades > 0])
        orig_avg = orig_pnl / orig_trades if orig_trades > 0 else 0
        
        # Dip stats
        dip_trades = sum(r.total_trades for r in dip_results.values())
        dip_pnl = sum(r.total_pnl for r in dip_results.values())
        dip_symbols = len([r for r in dip_results.values() if r.total_trades > 0])
        dip_avg = dip_pnl / dip_trades if dip_trades > 0 else 0
        
        print(f"📊 ORIGINAL MACDV (immediate entry, 5% trailing):")
        print(f"   🔢 Total trades: {orig_trades}")
        print(f"   💰 Total P&L: ${orig_pnl:.2f}")
        print(f"   📈 Avg P&L per trade: ${orig_avg:.2f}")
        print(f"   🎯 Active symbols: {orig_symbols}")
        
        print(f"\n💡 BUY-THE-DIP MACDV (4% discount entry, 8% trailing):")
        print(f"   🔢 Total trades: {dip_trades}")
        print(f"   💰 Total P&L: ${dip_pnl:.2f}")
        print(f"   📈 Avg P&L per trade: ${dip_avg:.2f}")
        print(f"   🎯 Active symbols: {dip_symbols}")
        
        # Calculate improvement
        pnl_change = dip_pnl - orig_pnl
        trade_change = dip_trades - orig_trades
        avg_change = dip_avg - orig_avg
        
        print(f"\n💡 BUY-THE-DIP IMPACT:")
        print(f"   💰 P&L change: ${pnl_change:+.2f}")
        print(f"   🔢 Trade count change: {trade_change:+d}")
        print(f"   📊 Avg trade change: ${avg_change:+.2f}")
        
        if pnl_change > 0:
            improvement_pct = (pnl_change / abs(orig_pnl)) * 100
            print(f"   📈 Performance improvement: +{improvement_pct:.1f}%")
            print(f"   ✅ BUY-THE-DIP strategy IMPROVED results!")
        else:
            decline_pct = (abs(pnl_change) / abs(orig_pnl)) * 100
            print(f"   📉 Performance decline: -{decline_pct:.1f}%")
            print(f"   ❌ BUY-THE-DIP strategy reduced performance")
        
        # Trade quality analysis
        if dip_trades > 0 and orig_trades > 0:
            print(f"\n🔍 TRADE QUALITY ANALYSIS:")
            print(f"   📊 Trade efficiency change: ${avg_change:+.2f} per trade")
            
            if dip_trades < orig_trades:
                print(f"   🎯 Fewer trades ({dip_trades} vs {orig_trades}) = more selective")
            elif dip_trades > orig_trades:
                print(f"   📈 More trades ({dip_trades} vs {orig_trades}) = more opportunities")
        
        # Save results
        orig_file = original_engine.save_results_to_csv(suffix="_original_vs_dip")
        dip_file = dip_engine.save_results_to_csv(suffix="_buy_dip_strategy")
        
        print(f"\n📁 RESULTS SAVED:")
        print(f"   📊 Original: {orig_file}")
        print(f"   💡 Buy-the-Dip: {dip_file}")
        
        return orig_file, dip_file
        
    else:
        print("❌ Failed to generate comparison results")


if __name__ == "__main__":
    asyncio.run(run_buy_dip_comparison_test())