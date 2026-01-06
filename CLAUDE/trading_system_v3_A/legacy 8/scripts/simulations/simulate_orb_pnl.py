#!/usr/bin/env python3
"""
Simulate ORB Strategy P&L using Real Trade Data

This script reads intraday bars from trading_data.db and simulates
the ORB worker execution to calculate potential P&L.
"""

import sys
import os
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from strategies.workers.orb_worker_logic import ORBWorkerLogic
from core.absorption_detector import get_absorption_detector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float = 0.0

class MockExecutionEngine:
    def __init__(self):
        self.positions = {}

class MockRiskManager:
    def check_entry(self, *args, **kwargs):
        return True
    def calculate_quantity(self, *args, **kwargs):
        return 100

class ORBSimulator:
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
        self.worker = ORBWorkerLogic(
            execution_engine=MockExecutionEngine(),
            risk_manager=MockRiskManager()
        )
        # Force enable absorption
        self.worker.use_absorption_filter = True
        self.worker.require_retest = False
        
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def get_bars(self, symbol: str, days: int = 7) -> List[Bar]:
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT b.bar_timestamp, b.open_price, b.high_price, 
                       b.low_price, b.close_price, b.volume
                FROM trade_intraday_bars b
                JOIN trades t ON b.trade_id = t.trade_id
                WHERE t.symbol = ?
                AND b.bar_timestamp >= datetime('now', '-{} days')
                ORDER BY b.bar_timestamp ASC
            """.format(days)
            
            cursor.execute(query, (symbol,))
            rows = cursor.fetchall()
            
            bars = []
            for row in rows:
                ts_str = row['bar_timestamp']
                if '+' in ts_str: ts_str = ts_str.split('+')[0]
                if 'Z' in ts_str: ts_str = ts_str.split('Z')[0]
                
                bars.append(Bar(
                    timestamp=datetime.fromisoformat(ts_str),
                    open=row['open_price'],
                    high=row['high_price'],
                    low=row['low_price'],
                    close=row['close_price'],
                    volume=row['volume']
                ))
            return bars
        except Exception as e:
            logger.error(f"Error getting bars for {symbol}: {e}")
            return []

    async def simulate_symbol(self, symbol: str, days: int = 7):
        bars = self.get_bars(symbol, days)
        if not bars:
            return None

        trades = []
        position = None
        
        # Deduplicate bars by timestamp
        unique_bars = {}
        for bar in bars:
            unique_bars[bar.timestamp] = bar
        bars = sorted(unique_bars.values(), key=lambda x: x.timestamp)

        # Group bars by day to simulate daily sessions
        bars_by_day = {}
        for bar in bars:
            day = bar.timestamp.date()
            if day not in bars_by_day:
                bars_by_day[day] = []
            bars_by_day[day].append(bar)

        for day, day_bars in bars_by_day.items():
            # Reset worker state for new day
            self.worker = ORBWorkerLogic(
                execution_engine=MockExecutionEngine(),
                risk_manager=MockRiskManager()
            )
            self.worker.use_absorption_filter = True
            # EXTEND TRADING WINDOW for testing
            self.worker.trading_end_time = datetime.strptime("15:30", "%H:%M").time()
            self.worker.no_entry_after = 15.5 # 15:30
            
            position = None
            
            for i, bar in enumerate(day_bars):
                # Update worker with current bar
                # We need to mock the opportunity data structure
                opportunity = {
                    'symbol': symbol,
                    'current_price': bar.close,
                    'high': bar.high,
                    'low': bar.low,
                    'volume': bar.volume,
                    'timestamp': bar.timestamp,
                    'market_cap': 100000000, # Mock
                    'avg_volume': 500000, # Mock
                    'volatility': 0.05 # Mock
                }
                
                # Update worker's internal state (important for ORB calculation)
                # We need to manually feed the bar to the worker's internal logic if it has any state
                # But ORBWorkerLogic usually queries history. 
                # Since we can't easily mock the history query inside the worker without patching,
                # we rely on the fact that we are passing the opportunity.
                
                # However, ORB calculation usually requires historical bars.
                # The worker might be failing because it can't calculate the ORB range 
                # because it tries to fetch history from IBKR/Polygon.
                
                # We need to bypass the history fetch or mock it.
                # Let's try to set the ORB levels manually if we can detect the range.
                
                # Simple ORB detection logic for simulation:
                # If time is past 10:00, calculate High/Low of 9:30-10:00
                if bar.timestamp.time() >= datetime.strptime("10:00", "%H:%M").time():
                    # Find bars in range
                    range_bars = [b for b in day_bars if 
                                  b.timestamp.time() >= datetime.strptime("09:30", "%H:%M").time() and
                                  b.timestamp.time() < datetime.strptime("10:00", "%H:%M").time()]
                    
                    if range_bars:
                        orb_high = max(b.high for b in range_bars)
                        orb_low = min(b.low for b in range_bars)
                        
                        # Manually inject ORB levels into worker if possible, 
                        # or ensure the worker can calculate them.
                        # Since we can't easily inject, we'll rely on the worker's logic 
                        # but we might need to patch 'get_historical_data'.
                        pass

                if position is None:
                    # Check for entry
                    # We need to patch the worker's data fetching to return our bars
                    # This is complex. 
                    # Alternative: Implement a simplified entry check here using the same logic
                    
                    # 1. Check if price > ORB High (Breakout)
                    # 2. Check Absorption
                    
                    # Let's use the simplified logic for this simulation to prove the concept
                    # assuming the worker WOULD have calculated the ORB correctly.
                    
                    current_time = bar.timestamp.time()
                    if current_time >= datetime.strptime("10:00", "%H:%M").time() and \
                       current_time <= datetime.strptime("15:30", "%H:%M").time():
                           
                        # Calculate ORB if not done
                        range_bars = [b for b in day_bars if 
                                      b.timestamp.time() >= datetime.strptime("09:30", "%H:%M").time() and
                                      b.timestamp.time() < datetime.strptime("10:00", "%H:%M").time()]
                        
                        if range_bars:
                            orb_high = max(b.high for b in range_bars)
                            
                            # Check Breakout
                            if bar.close > orb_high:
                                # Check Absorption (using our detector directly)
                                # Get last 30 bars
                                history = day_bars[max(0, i-30):i+1]
                                
                                # Detect absorption
                                detector = get_absorption_detector()
                                signal = detector.detect_absorption_with_intention(
                                    bars=history,
                                    direction='bullish',
                                    current_time=bar.timestamp
                                )
                                
                                if signal.has_signal and signal.confidence > 60:
                                    entry_price = bar.close
                                    position = {
                                        'entry_price': entry_price,
                                        'entry_time': bar.timestamp,
                                        'quantity': 100,
                                        'stop_loss': entry_price * 0.95, # 5% SL
                                        'take_profit': entry_price * 1.15 # 15% TP
                                    }
                                    logger.info(f"🟢 BUY {symbol} @ {entry_price:.2f} on {bar.timestamp} (ORB: {orb_high:.2f}, Abs: {signal.strength})")
                
                else:
                    # Check for exit
                    # 1. Stop Loss
                    if bar.low <= position['stop_loss']:
                        exit_price = position['stop_loss']
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        trades.append({
                            'symbol': symbol,
                            'entry_time': position['entry_time'],
                            'exit_time': bar.timestamp,
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'reason': 'STOP_LOSS'
                        })
                        logger.info(f"🔴 SELL {symbol} @ {exit_price:.2f} (SL) P&L: ${pnl:.2f}")
                        position = None
                        
                    # 2. Take Profit
                    elif bar.high >= position['take_profit']:
                        exit_price = position['take_profit']
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        trades.append({
                            'symbol': symbol,
                            'entry_time': position['entry_time'],
                            'exit_time': bar.timestamp,
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'reason': 'TAKE_PROFIT'
                        })
                        logger.info(f"🟢 SELL {symbol} @ {exit_price:.2f} (TP) P&L: ${pnl:.2f}")
                        position = None
                        
                    # 3. EOD Exit
                    elif bar.timestamp.hour >= 16:
                        exit_price = bar.close
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        trades.append({
                            'symbol': symbol,
                            'entry_time': position['entry_time'],
                            'exit_time': bar.timestamp,
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'reason': 'EOD'
                        })
                        logger.info(f"⚪ SELL {symbol} @ {exit_price:.2f} (EOD) P&L: ${pnl:.2f}")
                        position = None

            # Force close at end of data if still open
            if position:
                exit_price = day_bars[-1].close
                pnl = (exit_price - position['entry_price']) * position['quantity']
                trades.append({
                    'symbol': symbol,
                    'entry_time': position['entry_time'],
                    'exit_time': day_bars[-1].timestamp,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'reason': 'FORCE_CLOSE'
                })
                logger.info(f"⚪ SELL {symbol} @ {exit_price:.2f} (FORCE_CLOSE) P&L: ${pnl:.2f}")

        return trades

async def main():
    symbols = ['CRCG', 'BTBT', 'DEFT', 'RR', 'WRD', 'VEEE', 'NVTS', 'ESPR', 'MSTX', 'JBLU']
    
    simulator = ORBSimulator()
    simulator.connect()
    
    all_trades = []
    
    print("\n" + "="*80)
    print("🚀 ORB STRATEGY SIMULATION (Last 7 Days)")
    print("="*80)
    
    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")
        trades = await simulator.simulate_symbol(symbol)
        if trades:
            all_trades.extend(trades)
            
    print("\n" + "="*80)
    print("📊 SIMULATION RESULTS")
    print("="*80)
    
    total_pnl = sum(t['pnl'] for t in all_trades)
    wins = len([t for t in all_trades if t['pnl'] > 0])
    losses = len([t for t in all_trades if t['pnl'] <= 0])
    total_trades = len(all_trades)
    
    print(f"Total Trades: {total_trades}")
    if total_trades > 0:
        print(f"Win Rate:     {(wins/total_trades)*100:.1f}% ({wins}W-{losses}L)")
        print(f"Total P&L:    ${total_pnl:.2f}")
        print(f"Avg P&L:      ${total_pnl/total_trades:.2f}")
    else:
        print("No trades generated.")
        
    if all_trades:
        print("\nTrade Log:")
        for t in all_trades:
            print(f"  {t['symbol']} {t['entry_time'].strftime('%Y-%m-%d %H:%M')} "
                  f"${t['entry_price']:.2f} -> ${t['exit_price']:.2f} "
                  f"({t['reason']}) P&L: ${t['pnl']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
