#!/usr/bin/env python3
"""
Momentum Breakout Worker - Rejection Analysis

Analyzes and quantifies all rejection reasons to identify the main bottlenecks.
"""

import sys
import os
import sqlite3
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict, Counter

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic

# Custom log handler to capture rejection reasons
class RejectionCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.rejections = []
        
    def emit(self, record):
        msg = record.getMessage()
        # Capture rejection messages
        if '⚪' in msg or 'REJECTED' in msg:
            # Extract the rejection reason
            if ':' in msg:
                parts = msg.split(':', 2)
                if len(parts) >= 3:
                    reason = parts[2].strip()
                    self.rejections.append(reason)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
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

class RejectionAnalyzer:
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
        self.rejection_counter = Counter()
        self.total_evaluations = 0
        self.approved_count = 0
        
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
            return []

    async def analyze_symbol(self, symbol: str, days: int = 7):
        """Analyze a symbol and track rejection reasons"""
        bars = self.get_bars(symbol, days)
        if not bars:
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
        
        for day, day_bars in bars_by_day.items():
            # Create fresh worker for each day
            worker = MomentumBreakoutWorkerLogic(
                execution_engine=MockExecutionEngine(),
                risk_manager=MockRiskManager()
            )
            worker.use_absorption_filter = True
            
            # Add custom handler to capture rejections
            rejection_handler = RejectionCapture()
            worker.logger.addHandler(rejection_handler)
            
            # Try multiple points in the day
            evaluation_points = [30, 60, 90, 120, 150, 180]
            
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
                
                try:
                    should_enter = await worker.should_enter(opportunity)
                    
                    if should_enter:
                        self.approved_count += 1
                    else:
                        # Capture the rejection reason
                        if rejection_handler.rejections:
                            reason = rejection_handler.rejections[-1]
                            # Categorize the reason
                            if 'momentum spike' in reason.lower():
                                self.rejection_counter['No momentum spike (< 2%)'] += 1
                            elif 'vwap declining' in reason.lower():
                                self.rejection_counter['VWAP declining'] += 1
                            elif 'breakout from consolidation' in reason.lower():
                                self.rejection_counter['No breakout from consolidation'] += 1
                            elif 'extended' in reason.lower():
                                self.rejection_counter['Too extended from base'] += 1
                            elif 'volume surge' in reason.lower():
                                self.rejection_counter['No volume surge'] += 1
                            elif 'structure' in reason.lower():
                                self.rejection_counter['Invalid structure'] += 1
                            else:
                                self.rejection_counter[f'Other: {reason[:50]}'] += 1
                        
                except Exception as e:
                    pass
            
            # Remove handler
            worker.logger.removeHandler(rejection_handler)

async def main():
    symbols = ['CRCG', 'BTBT', 'DEFT', 'RR', 'WRD', 'VEEE', 'NVTS', 'ESPR', 'MSTX', 'JBLU']
    
    analyzer = RejectionAnalyzer()
    analyzer.connect()
    
    print("\n" + "="*80)
    print("🔬 MOMENTUM BREAKOUT WORKER - REJECTION ANALYSIS")
    print("="*80)
    print("Analyzing rejection patterns across all symbols...")
    
    for symbol in symbols:
        await analyzer.analyze_symbol(symbol)
    
    print("\n" + "="*80)
    print("📊 REJECTION STATISTICS")
    print("="*80)
    print(f"Total Evaluations: {analyzer.total_evaluations}")
    print(f"Approved Entries:  {analyzer.approved_count}")
    print(f"Rejected Entries:  {analyzer.total_evaluations - analyzer.approved_count}")
    print(f"Rejection Rate:    {((analyzer.total_evaluations - analyzer.approved_count) / analyzer.total_evaluations * 100):.1f}%")
    
    print("\n" + "="*80)
    print("🎯 TOP REJECTION REASONS")
    print("="*80)
    
    for reason, count in analyzer.rejection_counter.most_common(10):
        pct = (count / analyzer.total_evaluations) * 100
        print(f"{count:4d} ({pct:5.1f}%) - {reason}")
    
    print("\n" + "="*80)
    print("💡 RECOMMENDATIONS")
    print("="*80)
    
    # Analyze the top rejection reason
    if analyzer.rejection_counter:
        top_reason, top_count = analyzer.rejection_counter.most_common(1)[0]
        top_pct = (top_count / analyzer.total_evaluations) * 100
        
        if 'momentum spike' in top_reason.lower():
            print(f"✅ Main Issue: Momentum spike threshold (2%) is too strict for smallcaps")
            print(f"   Recommendation: Lower threshold to 1.0-1.5% or make it adaptive")
        elif 'vwap declining' in top_reason.lower():
            print(f"✅ Main Issue: VWAP declining filter is too sensitive")
            print(f"   Recommendation: Relax VWAP slope requirement or use longer timeframe")
        elif 'consolidation' in top_reason.lower():
            print(f"✅ Main Issue: Consolidation detection is too strict")
            print(f"   Recommendation: Adjust consolidation range tolerance")

if __name__ == "__main__":
    asyncio.run(main())
