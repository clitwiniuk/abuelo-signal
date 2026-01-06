#!/usr/bin/env python3
"""
Live FOMO Exit Debug Tool
Analyzes current live positions to understand why FOMO exits aren't triggering
"""

import asyncio
import logging
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.append('.')

from core.database_manager import DatabaseManager
from core.interfaces import MarketData, Position

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LiveFOMODebugger:
    """Debug live positions to understand FOMO exit behavior"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        
    async def get_current_positions(self) -> List[Dict]:
        """Get all current open positions"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                df = pd.read_sql_query("""
                    SELECT 
                        symbol,
                        quantity,
                        avg_price as entry_price,
                        entry_time,
                        strategy,
                        status,
                        notes
                    FROM trades 
                    WHERE status = 'OPEN'
                    ORDER BY entry_time DESC
                """, conn)
                
                return df.to_dict('records') if not df.empty else []
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def analyze_position_for_fomo(self, position: Dict):
        """Analyze a single position for FOMO exit conditions"""
        symbol = position['symbol']
        entry_price = float(position['entry_price'])
        entry_time = datetime.fromisoformat(position['entry_time'])
        
        logger.info(f"\n🔍 ANALYZING POSITION: {symbol}")
        logger.info(f"Entry Price: ${entry_price:.2f}")
        logger.info(f"Entry Time: {entry_time}")
        
        # Get recent price data (simulate current conditions)
        # In real implementation, this would fetch from your data provider
        current_price = entry_price * 1.08  # Simulate 8% profit
        profit_pct = (current_price - entry_price) / entry_price
        
        logger.info(f"Current Price: ${current_price:.2f} (simulated)")
        logger.info(f"Current Profit: {profit_pct:.1%}")
        
        # Analyze FOMO conditions
        fomo_analysis = self.simulate_fomo_conditions(symbol, entry_price, current_price, profit_pct)
        
        return fomo_analysis
    
    def simulate_fomo_conditions(self, symbol: str, entry_price: float, current_price: float, profit_pct: float) -> Dict:
        """Simulate and analyze FOMO conditions"""
        analysis = {
            'symbol': symbol,
            'profit_pct': profit_pct,
            'fomo_conditions': {},
            'recommendations': []
        }
        
        # Check minimum profit requirement
        min_profit_req = 0.03  # 3%
        meets_min_profit = profit_pct >= min_profit_req
        analysis['fomo_conditions']['meets_min_profit'] = meets_min_profit
        
        if not meets_min_profit:
            analysis['recommendations'].append(f"Profit {profit_pct:.1%} < {min_profit_req:.1%} minimum required")
            logger.warning(f"❌ {symbol}: Insufficient profit for FOMO exit ({profit_pct:.1%} < {min_profit_req:.1%})")
            return analysis
        
        logger.info(f"✅ {symbol}: Meets minimum profit requirement ({profit_pct:.1%} >= {min_profit_req:.1%})")
        
        # Simulate volume conditions
        # In real scenario, we'd analyze actual volume data
        avg_volume = 100000  # Simulate average
        current_volume = 180000  # Simulate current
        volume_multiplier = current_volume / avg_volume
        volume_spike_threshold = 2.5
        
        has_volume_spike = volume_multiplier >= volume_spike_threshold
        analysis['fomo_conditions']['volume_spike'] = has_volume_spike
        analysis['fomo_conditions']['volume_multiplier'] = volume_multiplier
        
        if has_volume_spike:
            logger.info(f"✅ {symbol}: Volume spike detected ({volume_multiplier:.1f}x >= {volume_spike_threshold}x)")
        else:
            logger.warning(f"❌ {symbol}: No volume spike ({volume_multiplier:.1f}x < {volume_spike_threshold}x)")
            analysis['recommendations'].append(f"Volume {volume_multiplier:.1f}x below {volume_spike_threshold}x threshold")
        
        # Simulate price stall conditions
        recent_high = current_price * 1.002  # Simulate recent high slightly above current
        price_stall_threshold = 0.01  # 1%
        price_distance = abs(current_price - recent_high) / recent_high
        has_price_stall = price_distance < price_stall_threshold
        
        analysis['fomo_conditions']['price_stall'] = has_price_stall
        analysis['fomo_conditions']['price_distance_from_high'] = price_distance
        
        if has_price_stall:
            logger.info(f"✅ {symbol}: Price stall detected ({price_distance:.2%} < {price_stall_threshold:.1%})")
        else:
            logger.warning(f"❌ {symbol}: No price stall ({price_distance:.2%} >= {price_stall_threshold:.1%})")
            analysis['recommendations'].append(f"Price distance from high {price_distance:.2%} >= {price_stall_threshold:.1%}")
        
        # Check for 5%+ profit requirement for volume spike exit
        volume_exit_min_profit = 0.05  # 5%
        meets_volume_exit_profit = profit_pct >= volume_exit_min_profit
        analysis['fomo_conditions']['meets_volume_exit_profit'] = meets_volume_exit_profit
        
        if not meets_volume_exit_profit:
            logger.warning(f"❌ {symbol}: Insufficient profit for volume spike exit ({profit_pct:.1%} < {volume_exit_min_profit:.1%})")
            analysis['recommendations'].append(f"Need {volume_exit_min_profit:.1%}+ profit for volume spike exit")
        
        # Overall FOMO exit decision
        would_exit = (
            meets_min_profit and 
            has_volume_spike and 
            has_price_stall and 
            meets_volume_exit_profit
        )
        
        analysis['would_exit_fomo'] = would_exit
        
        if would_exit:
            logger.info(f"🚨 {symbol}: WOULD TRIGGER FOMO EXIT!")
        else:
            logger.warning(f"⚠️ {symbol}: Would NOT trigger FOMO exit")
            
        return analysis
    
    async def check_position_tracking(self):
        """Check if positions are being tracked correctly"""
        logger.info("\n🔍 CHECKING POSITION TRACKING...")
        
        # Check recent trades
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                recent_trades = pd.read_sql_query("""
                    SELECT 
                        symbol,
                        entry_time,
                        exit_time,
                        status,
                        pnl,
                        exit_reason,
                        strategy
                    FROM trades 
                    WHERE entry_time >= date('now', '-7 days')
                    ORDER BY entry_time DESC
                    LIMIT 20
                """, conn)
                
                if not recent_trades.empty:
                    logger.info(f"📊 Found {len(recent_trades)} recent trades:")
                    
                    open_trades = recent_trades[recent_trades['status'] == 'OPEN']
                    closed_trades = recent_trades[recent_trades['status'] == 'CLOSED']
                    
                    logger.info(f"   - Open: {len(open_trades)}")
                    logger.info(f"   - Closed: {len(closed_trades)}")
                    
                    if not closed_trades.empty:
                        exit_reasons = closed_trades['exit_reason'].value_counts()
                        logger.info(f"📈 Exit reasons in last 7 days:")
                        for reason, count in exit_reasons.items():
                            logger.info(f"   - {reason}: {count}")
                        
                        # Check for FOMO exits
                        fomo_exits = closed_trades[closed_trades['exit_reason'].str.contains('fomo', case=False, na=False)]
                        if not fomo_exits.empty:
                            logger.info(f"🚨 Found {len(fomo_exits)} FOMO exits in last 7 days!")
                            for _, trade in fomo_exits.iterrows():
                                logger.info(f"   - {trade['symbol']}: {trade['exit_reason']} (PnL: ${trade['pnl']:.2f})")
                        else:
                            logger.warning("⚠️ NO FOMO exits found in last 7 days")
                else:
                    logger.warning("⚠️ No recent trades found")
                    
        except Exception as e:
            logger.error(f"Error checking position tracking: {e}")
    
    async def run_live_analysis(self):
        """Run comprehensive live analysis"""
        logger.info("🚀 Starting Live FOMO Exit Analysis\n")
        
        # Check position tracking first
        await self.check_position_tracking()
        
        # Get current positions
        positions = await self.get_current_positions()
        
        if not positions:
            logger.warning("⚠️ No open positions found")
            return
        
        logger.info(f"📊 Found {len(positions)} open positions")
        
        # Analyze each position
        all_analyses = []
        for position in positions:
            try:
                analysis = await self.analyze_position_for_fomo(position)
                all_analyses.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing position {position.get('symbol', 'unknown')}: {e}")
        
        # Generate summary report
        self.generate_live_report(all_analyses)
    
    def generate_live_report(self, analyses: List[Dict]):
        """Generate summary report of live analysis"""
        logger.info("\n" + "="*80)
        logger.info("📊 LIVE FOMO EXIT ANALYSIS REPORT")
        logger.info("="*80)
        
        if not analyses:
            logger.warning("⚠️ No positions analyzed")
            return
        
        total_positions = len(analyses)
        would_exit_count = sum(1 for a in analyses if a.get('would_exit_fomo', False))
        
        logger.info(f"Total Positions: {total_positions}")
        logger.info(f"Would Trigger FOMO Exit: {would_exit_count}")
        logger.info(f"FOMO Exit Rate: {would_exit_count/total_positions*100:.1f}%")
        
        # Analyze common issues
        common_issues = {}
        for analysis in analyses:
            for rec in analysis.get('recommendations', []):
                common_issues[rec] = common_issues.get(rec, 0) + 1
        
        if common_issues:
            logger.info(f"\n🔍 COMMON ISSUES PREVENTING FOMO EXITS:")
            for issue, count in sorted(common_issues.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"   - {issue}: {count}/{total_positions} positions")
        
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        
        if would_exit_count == 0:
            logger.warning("🚨 NO positions would trigger FOMO exit under current conditions!")
            logger.info("Consider adjusting FOMO detection parameters:")
            
            if any("Volume" in issue for issue in common_issues):
                logger.info("   📊 Volume spike threshold too high (currently 2.5x)")
                logger.info("      - Try lowering to 2.0x or 1.8x")
            
            if any("profit" in issue.lower() for issue in common_issues):
                logger.info("   💰 Profit requirements too strict")
                logger.info("      - Lower minimum profit from 3% to 2%")
                logger.info("      - Lower volume exit profit from 5% to 3%")
            
            if any("price" in issue.lower() for issue in common_issues):
                logger.info("   📈 Price stall detection too strict (currently 1%)")
                logger.info("      - Try increasing to 1.5% or 2%")
        
        else:
            logger.info(f"✅ {would_exit_count} positions would trigger FOMO exits")
            logger.info("System appears to be working, check if:")
            logger.info("   - Real-time data is feeding correctly")
            logger.info("   - Strategy is actually being called for exits")
            logger.info("   - Position tracking is accurate")
        
        logger.info("\n" + "="*80)

async def main():
    """Main debug function"""
    debugger = LiveFOMODebugger()
    await debugger.run_live_analysis()

if __name__ == "__main__":
    asyncio.run(main())