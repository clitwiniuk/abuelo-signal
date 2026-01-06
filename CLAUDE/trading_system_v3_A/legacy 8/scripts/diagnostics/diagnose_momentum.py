#!/usr/bin/env python3
"""
Momentum Breakout Worker - Diagnostic Analysis

This script analyzes why the Momentum Breakout worker is not finding trades
with real data. It will log detailed rejection reasons at each filter stage.
"""

import sys
import os
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
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

class MomentumDiagnostics:
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
        self.rejection_stats = defaultdict(int)
        self.total_evaluations = 0
        
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

    async def analyze_symbol(self, symbol: str, days: int = 7):
        """Analyze a symbol and track rejection reasons"""
        bars = self.get_bars(symbol, days)
        if not bars:
            logger.info(f"⚪ {symbol}: No bars found in database")
            return
            
        # Deduplicate bars
        unique_bars = {}
        for bar in bars:
            unique_bars[bar.timestamp] = bar
        bars = sorted(unique_bars.values(), key=lambda x: x.timestamp)
        
        # Group by day
        bars_by_day = {}
        for bar in bars:
            day = bar.timestamp.date()
            if day not in bars_by_day:
                bars_by_day[day] = []
            bars_by_day[day].append(bar)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 ANALYZING {symbol} - {len(bars_by_day)} days of data")
        logger.info(f"{'='*80}")
        
        for day, day_bars in bars_by_day.items():
            logger.info(f"\n📅 Day: {day} - {len(day_bars)} bars")
            
            # Create fresh worker for each day
            worker = MomentumBreakoutWorkerLogic(
                execution_engine=MockExecutionEngine(),
                risk_manager=MockRiskManager()
            )
            worker.use_absorption_filter = True
            
            # Try multiple points in the day
            evaluation_points = [30, 60, 90, 120, 150, 180]  # Different bar indices
            
            for i in evaluation_points:
                if i >= len(day_bars):
                    continue
                    
                self.total_evaluations += 1
                bar = day_bars[i]
                current_price = bar.close
                
                # Create opportunity
                opportunity = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'high': bar.high,
                    'low': bar.low,
                    'volume': bar.volume,
                    'timestamp': bar.timestamp,
                    'volume_ratio': 2.5,
                    'volume_zscore': 3.0,
                    'risk_reward': 2.0,
                    'confidence': 80.0,
                    'quality_score': 70.0,
                    'bars_history': day_bars[:i+1],
                    'vwap': sum(b.close * b.volume for b in day_bars[:i+1]) / sum(b.volume for b in day_bars[:i+1]) if i > 0 else bar.close
                }
                
                # Mock methods
                worker._get_current_price = asyncio.coroutine(lambda s: current_price)
                worker.is_within_entry_hours = lambda s: (True, 10.0)
                
                # Capture logs to analyze rejection
                logger.info(f"\n  🔍 Evaluation #{self.total_evaluations} at bar {i} ({bar.timestamp.strftime('%H:%M')})")
                logger.info(f"     Price: ${current_price:.2f}, Volume: {bar.volume:,}")
                
                try:
                    should_enter = await worker.should_enter(opportunity)
                    
                    if should_enter:
                        logger.info(f"  ✅ ENTRY APPROVED!")
                        return True
                    else:
                        # Analyze why it was rejected by checking the logs
                        logger.info(f"  ❌ Entry rejected")
                        
                except Exception as e:
                    logger.error(f"  ⚠️ Error during evaluation: {e}")
                    import traceback
                    traceback.print_exc()
        
        return False

async def main():
    # symbols = ['CRCG', 'BTBT', 'DEFT', 'RR', 'WRD', 'VEEE', 'NVTS', 'ESPR', 'MSTX', 'JBLU']
    # Out-of-sample set
    symbols = ['BYND', 'DVLT', 'ASST', 'IONZ', 'LAES', 'HIVE', 'INTS', 'NUAI', 'SGBX', 'BITF']
    
    diagnostics = MomentumDiagnostics()
    diagnostics.connect()
    
    print("\n" + "="*80)
    print("🔬 MOMENTUM BREAKOUT WORKER - DIAGNOSTIC ANALYSIS")
    print("="*80)
    
    approved_count = 0
    
    for symbol in symbols:
        result = await diagnostics.analyze_symbol(symbol)
        if result:
            approved_count += 1
    
    print("\n" + "="*80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*80)
    print(f"Total Evaluations: {diagnostics.total_evaluations}")
    print(f"Approved Entries: {approved_count}")
    print(f"Rejection Rate: {((diagnostics.total_evaluations - approved_count) / diagnostics.total_evaluations * 100):.1f}%")
    
    print("\n💡 Review the logs above to see detailed rejection reasons at each filter stage.")

if __name__ == "__main__":
    asyncio.run(main())
