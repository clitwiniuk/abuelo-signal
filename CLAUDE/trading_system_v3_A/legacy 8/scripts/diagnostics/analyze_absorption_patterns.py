#!/usr/bin/env python3
"""
Analyze Absorption Patterns in Real Trading Data

This script analyzes real intraday bar data from trading_data.db to identify
absorption patterns and measure their effectiveness for trade entries.

Usage:
    python analyze_absorption_patterns.py --days 30
    python analyze_absorption_patterns.py --days 30 --symbols AAPL,TSLA
    python analyze_absorption_patterns.py --days 30 --worker orb_breakout
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from dataclasses import dataclass

from core.absorption_detector import get_absorption_detector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Bar:
    """Simple bar structure"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class AbsorptionPatternAnalyzer:
    """
    Analyzes absorption patterns in real trading data.
    """
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
        self.absorption_detector = get_absorption_detector()
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"✅ Connected to {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            raise
    
    def get_symbols_with_bars(self, days: int = 30, worker: str = None) -> List[str]:
        """Get symbols that have intraday bar data"""
        try:
            cursor = self.conn.cursor()
            
            # Query for symbols with bar data (join with trades table)
            query = """
                SELECT DISTINCT t.symbol
                FROM trade_intraday_bars b
                JOIN trades t ON b.trade_id = t.trade_id
                WHERE b.bar_timestamp >= datetime('now', '-{} days')
            """.format(days)
            
            if worker:
                query += " AND t.worker_name = ?"
                cursor.execute(query, (worker,))
            else:
                cursor.execute(query)
            
            symbols = [row['symbol'] for row in cursor.fetchall()]
            
            logger.info(f"📊 Found {len(symbols)} symbols with bar data in last {days} days")
            return symbols
            
        except Exception as e:
            logger.error(f"❌ Error fetching symbols: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def get_bars_for_symbol(self, symbol: str, days: int = 30) -> List[Bar]:
        """Get intraday bars for a symbol"""
        try:
            cursor = self.conn.cursor()
            
            # Get bars for this symbol (join with trades)
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
                # Parse timestamp
                ts_str = row['bar_timestamp']
                # Handle timezone-aware timestamps
                if '+' in ts_str or ts_str.endswith('Z'):
                    # Remove timezone info for simplicity
                    ts_str = ts_str.split('+')[0].split('-04:00')[0].split('Z')[0]
                
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
            logger.error(f"❌ Error fetching bars for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def analyze_symbol(self, symbol: str, bars: List[Bar]) -> Dict[str, Any]:
        """Analyze absorption patterns for a symbol"""
        if len(bars) < 30:
            return {
                'symbol': symbol,
                'total_bars': len(bars),
                'absorption_signals': 0,
                'reason': 'Insufficient bars'
            }
        
        absorption_signals = []
        
        # Scan through bars looking for absorption patterns
        # Use sliding window of 30 bars
        for i in range(30, len(bars)):
            window_bars = bars[i-30:i+1]
            
            # Try to detect bullish absorption
            signal = self.absorption_detector.detect_absorption_with_intention(
                bars=window_bars,
                direction='bullish',
                current_time=window_bars[-1].timestamp,
                spread_pct=None  # We don't have spread data in historical bars
            )
            
            if signal.has_signal:
                absorption_signals.append({
                    'timestamp': window_bars[-1].timestamp,
                    'direction': signal.direction,
                    'strength': signal.strength,
                    'confidence': signal.confidence,
                    'price': window_bars[-1].close,
                    'metadata': signal.metadata
                })
        
        return {
            'symbol': symbol,
            'total_bars': len(bars),
            'absorption_signals': len(absorption_signals),
            'signals': absorption_signals
        }
    
    def run_analysis(self, days: int = 30, symbols: List[str] = None, worker: str = None):
        """Run full absorption pattern analysis"""
        logger.info(f"\n{'='*80}")
        logger.info(f"ABSORPTION PATTERN ANALYSIS")
        logger.info(f"{'='*80}")
        logger.info(f"Analyzing last {days} days")
        if symbols:
            logger.info(f"Symbols: {', '.join(symbols)}")
        if worker:
            logger.info(f"Worker filter: {worker}")
        logger.info(f"{'='*80}\n")
        
        # Connect to database
        self.connect()
        
        # Get symbols to analyze
        if not symbols:
            symbols = self.get_symbols_with_bars(days, worker)
        
        if not symbols:
            logger.warning("⚠️ No symbols found with bar data")
            return
        
        # Analyze each symbol
        results = []
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] Analyzing {symbol}...")
            
            bars = self.get_bars_for_symbol(symbol, days)
            
            if not bars:
                logger.warning(f"  ⚠️ No bars found for {symbol}")
                continue
            
            result = self.analyze_symbol(symbol, bars)
            results.append(result)
            
            if result['absorption_signals'] > 0:
                logger.info(f"  ✅ Found {result['absorption_signals']} absorption signals")
            else:
                logger.debug(f"  ⚪ No absorption signals found")
        
        # Print summary
        self.print_summary(results)
        
        # Close connection
        if self.conn:
            self.conn.close()
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print analysis summary"""
        logger.info(f"\n{'='*80}")
        logger.info(f"ANALYSIS SUMMARY")
        logger.info(f"{'='*80}")
        
        total_symbols = len(results)
        symbols_with_signals = len([r for r in results if r['absorption_signals'] > 0])
        total_signals = sum(r['absorption_signals'] for r in results)
        total_bars = sum(r['total_bars'] for r in results)
        
        logger.info(f"Symbols analyzed: {total_symbols}")
        logger.info(f"Symbols with absorption: {symbols_with_signals} ({symbols_with_signals/total_symbols*100:.1f}%)" if total_symbols > 0 else "Symbols with absorption: 0")
        logger.info(f"Total absorption signals: {total_signals}")
        logger.info(f"Total bars analyzed: {total_bars}")
        logger.info(f"Absorption frequency: {total_signals/total_bars*100:.3f}%" if total_bars > 0 else "Absorption frequency: N/A")
        
        # Show top symbols by absorption signals
        if symbols_with_signals > 0:
            logger.info(f"\n📊 Top Symbols by Absorption Signals:")
            sorted_results = sorted(results, key=lambda x: x['absorption_signals'], reverse=True)
            for i, result in enumerate(sorted_results[:10], 1):
                if result['absorption_signals'] > 0:
                    logger.info(f"  {i}. {result['symbol']}: {result['absorption_signals']} signals ({result['total_bars']} bars)")
        
        # Show detailed signals for top symbol
        if symbols_with_signals > 0 and results:
            top_result = max(results, key=lambda x: x['absorption_signals'])
            if top_result['absorption_signals'] > 0:
                logger.info(f"\n🔍 Detailed Signals for {top_result['symbol']}:")
                for i, signal in enumerate(top_result['signals'][:5], 1):
                    logger.info(f"  {i}. {signal['timestamp']}: "
                              f"Strength={signal['strength']:.0f}, "
                              f"Confidence={signal['confidence']:.0f}, "
                              f"Price=${signal['price']:.2f}")
                if len(top_result['signals']) > 5:
                    logger.info(f"  ... and {len(top_result['signals']) - 5} more")
        
        logger.info(f"\n{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze absorption patterns in real trading data'
    )
    
    parser.add_argument('--days', type=int, default=30,
                        help='Number of days to analyze (default: 30)')
    parser.add_argument('--symbols', type=str,
                        help='Specific symbols to analyze (comma-separated)')
    parser.add_argument('--worker', type=str,
                        help='Filter by worker name (e.g., orb_breakout)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Run analysis
    analyzer = AbsorptionPatternAnalyzer()
    analyzer.run_analysis(
        days=args.days,
        symbols=symbols,
        worker=args.worker
    )


if __name__ == '__main__':
    main()
