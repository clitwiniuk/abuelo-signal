#!/usr/bin/env python3
"""
Simulate VCP Strategy P&L using Real Trade Data

This script reads intraday bars from trading_data.db and simulates
the VCP Smallcap worker execution to calculate potential P&L.
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

from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic

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
        self.broker = self

    async def get_current_price(self, symbol):
        return 0.0

class MockRiskManager:
    def check_entry(self, *args, **kwargs):
        return True
    def calculate_quantity(self, *args, **kwargs):
        return 100

class VCPSimulator:
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
        self.worker = VCPSmallcapWorkerLogic(
            execution_engine=MockExecutionEngine(),
            risk_manager=MockRiskManager()
        )
        # Force enable absorption
        self.worker.use_absorption_filter = True
        
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
            return []

        trades = []
        
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
            self.worker = VCPSmallcapWorkerLogic(
                execution_engine=MockExecutionEngine(),
                risk_manager=MockRiskManager()
            )
            self.worker.use_absorption_filter = True
            
            position = None
            
            for i, bar in enumerate(day_bars):
                if i < 30: continue # Need history for VCP detection
                
                # Calculate basic metrics
                current_price = bar.close
                
                # Mock opportunity data for VCP
                opportunity = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'high': bar.high,
                    'low': bar.low,
                    'volume': bar.volume,
                    'timestamp': bar.timestamp,
                    'volume_ratio': 1.5,
                    'quality_score': 60.0,
                    'catalyst_type': 'TECHNICAL',
                    'vwap': sum(b.close * b.volume for b in day_bars[:i+1]) / sum(b.volume for b in day_bars[:i+1]) if i > 0 else bar.close
                }
                
                # Inject bars history
                opportunity['bars_history'] = day_bars[:i+1]

                if position is None:
                    # Check for entry
                    # Mock _get_current_price and time validation
                    self.worker._get_current_price = asyncio.coroutine(lambda s: current_price)
                    self.worker.is_within_entry_hours = lambda s, timestamp=None: (True, 10.0)
                    
                    should_enter = await self.worker.should_enter(opportunity)
                    
                    if should_enter:
                        entry_price = bar.close
                        position = {
                            'entry_price': entry_price,
                            'entry_time': bar.timestamp,
                            'quantity': 100,
                            'stop_loss': entry_price * 0.95, # 5% SL
                            'take_profit': entry_price * 1.15 # 15% TP
                        }
                        logger.info(f"🟢 BUY {symbol} @ {entry_price:.2f} on {bar.timestamp}")
                
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
                        
                    # 3. EOD Exit (16:00)
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
    
    simulator = VCPSimulator()
    simulator.connect()
    
    all_trades = []
    
    print("\n" + "="*80)
    print("🚀 VCP SMALLCAP STRATEGY SIMULATION (Last 7 Days)")
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
