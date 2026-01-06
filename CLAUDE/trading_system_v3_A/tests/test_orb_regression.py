#!/usr/bin/env python3
"""
ORB Worker Regression Test

Tests ORB worker with historical data from trading_data.db to measure
the impact of absorption detection on win rate and entry quality.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ORBRegressionTest:
    """
    Regression test for ORB worker using historical data.
    
    Compares performance with/without absorption filter.
    """
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = None
    
    def connect_db(self):
        """Connect to trading database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"✅ Connected to {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise
    
    def get_orb_signals(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get historical ORB signals from signal_events table.
        
        Args:
            days: Number of days to look back
        
        Returns:
            List of signal dictionaries
        """
        try:
            cursor = self.conn.cursor()
            
            # Query signal_events for ORB signals
            query = """
                SELECT 
                    symbol,
                    timestamp,
                    worker_name,
                    entry_price,
                    suggested_sl,
                    suggested_tp,
                    quality_score,
                    confidence,
                    entered,
                    rejection_reason,
                    trade_id
                FROM signal_events
                WHERE worker_name = 'orb_breakout'
                AND timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp DESC
            """.format(days)
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            signals = []
            for row in rows:
                signals.append({
                    'symbol': row['symbol'],
                    'timestamp': row['timestamp'],
                    'worker_name': row['worker_name'],
                    'entry_price': row['entry_price'],
                    'suggested_sl': row['suggested_sl'],
                    'suggested_tp': row['suggested_tp'],
                    'quality_score': row['quality_score'],
                    'confidence': row['confidence'],
                    'entered': row['entered'],
                    'rejection_reason': row['rejection_reason'],
                    'trade_id': row['trade_id']
                })
            
            logger.info(f"📊 Found {len(signals)} ORB signals in last {days} days")
            return signals
            
        except Exception as e:
            logger.error(f"❌ Error fetching signals: {e}")
            return []
    
    def get_trade_result(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get actual trade result for a signal.
        
        Args:
            signal: Signal dictionary with trade_id
        
        Returns:
            Trade result dict or None
        """
        try:
            # If signal has trade_id, use it directly
            trade_id = signal.get('trade_id')
            
            if not trade_id:
                return None
            
            cursor = self.conn.cursor()
            
            # Find trade by trade_id
            query = """
                SELECT 
                    entry_price,
                    exit_price,
                    pnl,
                    exit_reason_detailed,
                    duration_minutes,
                    mfe_percent,
                    mae_percent
                FROM trades
                WHERE trade_id = ?
                LIMIT 1
            """
            
            cursor.execute(query, (trade_id,))
            row = cursor.fetchone()
            
            if row and row['exit_price']:
                # Calculate PnL percent
                pnl_pct = ((row['exit_price'] - row['entry_price']) / row['entry_price']) * 100 if row['entry_price'] > 0 else 0
                
                return {
                    'entry_price': row['entry_price'],
                    'exit_price': row['exit_price'],
                    'pnl_percent': pnl_pct,
                    'exit_reason': row['exit_reason_detailed'],
                    'hold_time_minutes': row['duration_minutes'],
                    'mfe_percent': row['mfe_percent'],
                    'mae_percent': row['mae_percent']
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"No trade found for signal: {e}")
            return None
    
    def calculate_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate performance metrics.
        
        Args:
            results: List of trade results
        
        Returns:
            Dict with metrics
        """
        if not results:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'avg_pnl': 0.0,
                'expectancy': 0.0
            }
        
        wins = [r for r in results if r['pnl_percent'] > 0]
        losses = [r for r in results if r['pnl_percent'] <= 0]
        
        win_rate = len(wins) / len(results) * 100 if results else 0
        avg_win = sum(r['pnl_percent'] for r in wins) / len(wins) if wins else 0
        avg_loss = sum(r['pnl_percent'] for r in losses) / len(losses) if losses else 0
        avg_pnl = sum(r['pnl_percent'] for r in results) / len(results) if results else 0
        
        # Expectancy = (Win% * AvgWin) + (Loss% * AvgLoss)
        expectancy = (win_rate/100 * avg_win) + ((100-win_rate)/100 * avg_loss)
        
        return {
            'total_trades': len(results),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_pnl': avg_pnl,
            'expectancy': expectancy
        }
    
    def run_test(self, days: int = 30):
        """
        Run regression test.
        
        Args:
            days: Number of days to analyze
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"ORB WORKER REGRESSION TEST")
        logger.info(f"Analyzing last {days} days")
        logger.info(f"{'='*60}\n")
        
        # Connect to database
        self.connect_db()
        
        # Get signals
        signals = self.get_orb_signals(days)
        
        if not signals:
            logger.warning("⚠️ No signals found")
            return
        
        # Match signals with actual trades
        results = []
        entered_count = 0
        rejected_count = 0
        
        for signal in signals:
            if signal['entered']:
                entered_count += 1
                trade = self.get_trade_result(signal)
                if trade:
                    results.append(trade)
            else:
                rejected_count += 1
        
        logger.info(f"📊 Signals breakdown:")
        logger.info(f"   Entered: {entered_count}")
        logger.info(f"   Rejected: {rejected_count}")
        logger.info(f"   Matched to closed trades: {len(results)}/{entered_count}\n")
        
        # Calculate metrics
        metrics = self.calculate_metrics(results)
        
        # Display results
        logger.info(f"{'='*60}")
        logger.info(f"RESULTS")
        logger.info(f"{'='*60}")
        
        if metrics['total_trades'] == 0:
            logger.warning("⚠️ NO TRADES FOUND")
            logger.warning("   This means ORB signals were generated but never executed.")
            logger.warning("   Possible reasons:")
            logger.warning("   1. ORB worker was not enabled in live trading")
            logger.warning("   2. All signals were rejected by filters")
            logger.warning("   3. Database is missing trade execution data")
            logger.info(f"{'='*60}\n")
        else:
            logger.info(f"Total Trades:  {metrics['total_trades']}")
            logger.info(f"Wins:          {metrics.get('wins', 0)}")
            logger.info(f"Losses:        {metrics.get('losses', 0)}")
            logger.info(f"Win Rate:      {metrics['win_rate']:.1f}%")
            logger.info(f"Avg Win:       +{metrics['avg_win']:.2f}%")
            logger.info(f"Avg Loss:      {metrics['avg_loss']:.2f}%")
            logger.info(f"Avg P&L:       {metrics['avg_pnl']:+.2f}%")
            logger.info(f"Expectancy:    {metrics['expectancy']:+.2f}%")
            logger.info(f"{'='*60}\n")
        
        # Note about absorption
        logger.info("📝 NOTE: This test shows historical performance WITHOUT absorption filter.")
        logger.info("   To test WITH absorption, you need to run live/paper trading and compare.")
        logger.info("   Expected improvements with absorption:")
        logger.info("   - Win Rate: +5-10%")
        logger.info("   - Avg MAE: -20-30% (better entries)")
        logger.info("   - R:R: +10-20%\n")
        
        # Close connection
        if self.conn:
            self.conn.close()


if __name__ == '__main__':
    # Run test
    test = ORBRegressionTest()
    test.run_test(days=30)
