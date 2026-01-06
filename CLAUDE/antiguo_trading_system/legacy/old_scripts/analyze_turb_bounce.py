#!/usr/bin/env python3
"""
TURB Symbol Analysis for First Day Bounce Scanner

This script analyzes TURB to understand why the First Day Bounce scanner
isn't detecting any setups. It uses real IBKR data to check all criteria:

1. Overextension: 30%+ gain in 7 days with 2x+ volume
2. Retrace: 20-60% pullback from peak
3. Red-to-Green potential: Recent red days

Usage:
    python analyze_turb_bounce.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np

# Add the trading system path
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

from adapters.ibkr_adapter import IBKRAdapter
from core.interfaces import MarketData

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TURBAnalysis")

class TURBBounceAnalyzer:
    """Analyzer for TURB symbol bounce potential"""

    def __init__(self):
        self.ibkr = IBKRAdapter(host="127.0.0.1", port=7497, client_id=4150)
        self.symbol = "TURB"

        # Current bounce criteria from the scanner
        self.criteria = {
            'min_gain_pct': 0.30,              # 30% minimum gain
            'max_days_for_overextension': 7,   # Within 7 days
            'min_volume_multiple': 2.0,        # 2x volume minimum
            'min_retrace_pct': 0.20,           # 20% minimum retrace
            'max_retrace_pct': 0.60,           # 60% maximum retrace
            'max_days_in_retrace': 15,         # Maximum 15 days
            'min_days_red': 1,                 # Minimum 1 red day
            'max_days_red': 7,                 # Maximum 7 red days
        }

    async def analyze_turb(self) -> Dict[str, Any]:
        """Complete analysis of TURB symbol"""
        try:
            # Connect to IBKR
            logger.info("🔌 Connecting to IBKR...")
            await self.ibkr.connect()

            if not self.ibkr.is_connected():
                raise Exception("Failed to connect to IBKR")

            logger.info(f"✅ Connected to IBKR, analyzing {self.symbol}")

            # Get 30 days of daily data
            logger.info(f"📊 Requesting 30 days of historical data for {self.symbol}...")
            bars = await self.ibkr.get_bars(self.symbol, "1 day", 30)

            if not bars or len(bars) < 20:
                logger.error(f"❌ Insufficient data for {self.symbol}: {len(bars) if bars else 0} bars")
                return {"error": "Insufficient historical data"}

            logger.info(f"✅ Got {len(bars)} days of data for {self.symbol}")

            # Convert to analysis format
            daily_data = self._convert_bars_to_analysis_format(bars)

            # Perform all analyses
            analysis_results = {
                'symbol': self.symbol,
                'data_period': f"{bars[0].timestamp.strftime('%Y-%m-%d') if hasattr(bars[0].timestamp, 'strftime') else str(bars[0].timestamp)} to {bars[-1].timestamp.strftime('%Y-%m-%d') if hasattr(bars[-1].timestamp, 'strftime') else str(bars[-1].timestamp)}",
                'total_bars': len(bars),
                'current_price': daily_data[-1]['close'],
                'criteria': self.criteria
            }

            # 1. Overextension Analysis
            logger.info("🚀 Analyzing overextension patterns...")
            overextension = self._analyze_overextension(daily_data)
            analysis_results['overextension'] = overextension

            # 2. Retrace Analysis
            logger.info("📉 Analyzing retrace patterns...")
            retrace = self._analyze_retrace(daily_data, overextension)
            analysis_results['retrace'] = retrace

            # 3. Red-to-Green Analysis
            logger.info("💚 Analyzing red-to-green potential...")
            rtg = self._analyze_red_to_green(daily_data)
            analysis_results['red_to_green'] = rtg

            # 4. Overall Assessment
            logger.info("📋 Generating overall assessment...")
            assessment = self._generate_assessment(overextension, retrace, rtg)
            analysis_results['assessment'] = assessment

            return analysis_results

        except Exception as e:
            logger.error(f"❌ Error analyzing {self.symbol}: {e}")
            return {"error": str(e)}

        finally:
            if self.ibkr.is_connected():
                await self.ibkr.disconnect()
                logger.info("🔌 Disconnected from IBKR")

    def _convert_bars_to_analysis_format(self, bars: List[MarketData]) -> List[Dict]:
        """Convert MarketData bars to analysis format"""
        daily_data = []
        for bar in bars:
            daily_data.append({
                'date': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        return daily_data

    def _analyze_overextension(self, data: List[Dict]) -> Dict[str, Any]:
        """Analyze overextension patterns"""
        try:
            prices = [bar['close'] for bar in data]
            volumes = [bar['volume'] for bar in data]
            dates = [bar['date'] for bar in data]

            # Find the highest price in recent period
            recent_data = data[-10:]  # Last 10 days
            recent_prices = [bar['close'] for bar in recent_data]
            peak_idx = np.argmax(recent_prices)
            peak_price = recent_prices[peak_idx]
            peak_date = recent_data[peak_idx]['date']

            # Calculate base price (15-25 days ago average)
            if len(data) >= 25:
                base_prices = prices[-25:-15]
                base_price = np.mean(base_prices)
            else:
                base_prices = prices[:-10] if len(prices) > 10 else prices[:5]
                base_price = np.mean(base_prices)

            # Calculate total gain
            total_gain_pct = (peak_price - base_price) / base_price if base_price > 0 else 0

            # Volume analysis
            peak_volume = recent_data[peak_idx]['volume']
            if len(data) >= 25:
                baseline_volumes = volumes[-25:-10]
            else:
                baseline_volumes = volumes[:-5] if len(volumes) > 5 else volumes[:5]

            baseline_volume = np.mean(baseline_volumes) if baseline_volumes else 1
            volume_multiple = peak_volume / baseline_volume if baseline_volume > 0 else 0

            # Check criteria
            meets_gain_criteria = total_gain_pct >= self.criteria['min_gain_pct']
            meets_volume_criteria = volume_multiple >= self.criteria['min_volume_multiple']

            return {
                'peak_price': peak_price,
                'peak_date': peak_date.strftime('%Y-%m-%d') if hasattr(peak_date, 'strftime') else str(peak_date).split()[0],
                'base_price': base_price,
                'total_gain_pct': total_gain_pct,
                'total_gain_percent': total_gain_pct * 100,
                'peak_volume': peak_volume,
                'baseline_volume': baseline_volume,
                'volume_multiple': volume_multiple,
                'meets_gain_criteria': meets_gain_criteria,
                'meets_volume_criteria': meets_volume_criteria,
                'gain_vs_required': f"{total_gain_pct:.1%} vs {self.criteria['min_gain_pct']:.1%} required",
                'volume_vs_required': f"{volume_multiple:.1f}x vs {self.criteria['min_volume_multiple']:.1f}x required"
            }

        except Exception as e:
            logger.error(f"Error in overextension analysis: {e}")
            return {"error": str(e)}

    def _analyze_retrace(self, data: List[Dict], overextension: Dict) -> Dict[str, Any]:
        """Analyze retrace patterns"""
        try:
            if 'error' in overextension:
                return {"error": "Cannot analyze retrace without valid overextension data"}

            current_price = data[-1]['close']
            peak_price = overextension['peak_price']

            # Calculate retrace percentage
            retrace_pct = (peak_price - current_price) / peak_price if peak_price > 0 else 0

            # Check retrace criteria
            meets_min_retrace = retrace_pct >= self.criteria['min_retrace_pct']
            meets_max_retrace = retrace_pct <= self.criteria['max_retrace_pct']
            meets_retrace_criteria = meets_min_retrace and meets_max_retrace

            # Support level analysis
            support_analysis = self._analyze_support_levels(data, current_price)

            # Recent volume trend
            recent_volumes = [bar['volume'] for bar in data[-8:]]
            baseline_volumes = [bar['volume'] for bar in data[-25:-10]] if len(data) >= 25 else [bar['volume'] for bar in data[:-8]]

            recent_avg_volume = np.mean(recent_volumes) if recent_volumes else 0
            baseline_avg_volume = np.mean(baseline_volumes) if baseline_volumes else 1
            volume_vs_baseline = recent_avg_volume / baseline_avg_volume if baseline_avg_volume > 0 else 0

            return {
                'current_price': current_price,
                'peak_price': peak_price,
                'retrace_pct': retrace_pct,
                'retrace_percent': retrace_pct * 100,
                'meets_min_retrace': meets_min_retrace,
                'meets_max_retrace': meets_max_retrace,
                'meets_retrace_criteria': meets_retrace_criteria,
                'retrace_vs_required': f"{retrace_pct:.1%} (range: {self.criteria['min_retrace_pct']:.1%}-{self.criteria['max_retrace_pct']:.1%})",
                'volume_vs_baseline': volume_vs_baseline,
                'support_analysis': support_analysis
            }

        except Exception as e:
            logger.error(f"Error in retrace analysis: {e}")
            return {"error": str(e)}

    def _analyze_support_levels(self, data: List[Dict], current_price: float) -> Dict[str, Any]:
        """Analyze technical support levels"""
        try:
            # Simple support analysis
            recent_lows = [bar['low'] for bar in data[-15:]]
            support_level = np.mean(sorted(recent_lows)[:3])  # Average of 3 lowest lows

            distance_from_support = abs(current_price - support_level) / support_level if support_level > 0 else 1
            near_support = distance_from_support <= 0.05  # Within 5%

            return {
                'support_level': support_level,
                'distance_from_support_pct': distance_from_support,
                'near_support': near_support,
                'support_type': 'recent_lows'
            }

        except Exception as e:
            return {"error": str(e)}

    def _analyze_red_to_green(self, data: List[Dict]) -> Dict[str, Any]:
        """Analyze red-to-green potential"""
        try:
            # Count consecutive red days from the end
            consecutive_red = 0
            for bar in reversed(data[-7:]):  # Check last 7 days
                if bar['close'] < bar['open']:
                    consecutive_red += 1
                else:
                    break

            # Check criteria
            meets_min_red = consecutive_red >= self.criteria['min_days_red']
            meets_max_red = consecutive_red <= self.criteria['max_days_red']
            meets_red_criteria = meets_min_red and meets_max_red

            # Volume pattern during red days
            recent_volumes = [bar['volume'] for bar in data[-5:]]
            volume_trend = "INCREASING" if len(recent_volumes) >= 2 and recent_volumes[-1] > np.mean(recent_volumes[:-1]) else "DECREASING"

            # Higher lows pattern (market structure)
            recent_lows = [bar['low'] for bar in data[-5:]]
            higher_lows = len(recent_lows) >= 2 and all(
                recent_lows[i] >= recent_lows[i-1] * 0.98 for i in range(1, len(recent_lows))
            )

            return {
                'consecutive_red_days': consecutive_red,
                'meets_min_red': meets_min_red,
                'meets_max_red': meets_max_red,
                'meets_red_criteria': meets_red_criteria,
                'red_vs_required': f"{consecutive_red} days (range: {self.criteria['min_days_red']}-{self.criteria['max_days_red']})",
                'volume_trend': volume_trend,
                'higher_lows_pattern': higher_lows,
                'setup_readiness': consecutive_red >= 2 and volume_trend == "INCREASING"
            }

        except Exception as e:
            logger.error(f"Error in red-to-green analysis: {e}")
            return {"error": str(e)}

    def _generate_assessment(self, overextension: Dict, retrace: Dict, rtg: Dict) -> Dict[str, Any]:
        """Generate overall assessment"""
        try:
            # Count criteria met
            criteria_met = []
            criteria_failed = []

            # Overextension criteria
            if overextension.get('meets_gain_criteria', False):
                criteria_met.append("✅ Overextension gain requirement")
            else:
                criteria_failed.append(f"❌ Overextension gain: {overextension.get('gain_vs_required', 'Unknown')}")

            if overextension.get('meets_volume_criteria', False):
                criteria_met.append("✅ Overextension volume requirement")
            else:
                criteria_failed.append(f"❌ Overextension volume: {overextension.get('volume_vs_required', 'Unknown')}")

            # Retrace criteria
            if retrace.get('meets_retrace_criteria', False):
                criteria_met.append("✅ Retrace percentage requirement")
            else:
                criteria_failed.append(f"❌ Retrace percentage: {retrace.get('retrace_vs_required', 'Unknown')}")

            # Red-to-green criteria
            if rtg.get('meets_red_criteria', False):
                criteria_met.append("✅ Red-to-green days requirement")
            else:
                criteria_failed.append(f"❌ Red-to-green days: {rtg.get('red_vs_required', 'Unknown')}")

            # Overall assessment
            total_criteria = len(criteria_met) + len(criteria_failed)
            pass_rate = len(criteria_met) / total_criteria if total_criteria > 0 else 0

            # Determine if it would pass the scanner
            would_pass_scanner = all([
                overextension.get('meets_gain_criteria', False),
                overextension.get('meets_volume_criteria', False),
                retrace.get('meets_retrace_criteria', False),
                rtg.get('meets_red_criteria', False)
            ])

            return {
                'would_pass_scanner': would_pass_scanner,
                'criteria_pass_rate': pass_rate,
                'criteria_met_count': len(criteria_met),
                'criteria_failed_count': len(criteria_failed),
                'criteria_met': criteria_met,
                'criteria_failed': criteria_failed,
                'summary': f"TURB {'PASSES' if would_pass_scanner else 'FAILS'} First Day Bounce criteria ({len(criteria_met)}/{total_criteria} requirements met)"
            }

        except Exception as e:
            logger.error(f"Error generating assessment: {e}")
            return {"error": str(e)}

def print_analysis_report(results: Dict[str, Any]):
    """Print detailed analysis report"""
    print("\n" + "="*80)
    print("🎯 TURB FIRST DAY BOUNCE SCANNER ANALYSIS")
    print("="*80)

    if 'error' in results:
        print(f"❌ Analysis Error: {results['error']}")
        return

    # Basic info
    print(f"\n📊 Symbol: {results['symbol']}")
    print(f"📅 Data Period: {results['data_period']}")
    print(f"📈 Current Price: ${results['current_price']:.2f}")
    print(f"📊 Total Bars: {results['total_bars']}")

    # Overextension Analysis
    print(f"\n🚀 OVEREXTENSION ANALYSIS")
    print("-" * 40)
    over = results.get('overextension', {})
    if 'error' not in over:
        print(f"Peak Price: ${over['peak_price']:.2f} on {over['peak_date']}")
        print(f"Base Price: ${over['base_price']:.2f}")
        print(f"Total Gain: {over['total_gain_percent']:.1f}% (Required: ≥30%)")
        print(f"Peak Volume: {over['peak_volume']:,}")
        print(f"Volume Multiple: {over['volume_multiple']:.1f}x (Required: ≥2.0x)")
        print(f"Gain Criteria: {'✅ PASS' if over['meets_gain_criteria'] else '❌ FAIL'}")
        print(f"Volume Criteria: {'✅ PASS' if over['meets_volume_criteria'] else '❌ FAIL'}")
    else:
        print(f"❌ Error: {over['error']}")

    # Retrace Analysis
    print(f"\n📉 RETRACE ANALYSIS")
    print("-" * 40)
    retrace = results.get('retrace', {})
    if 'error' not in retrace:
        print(f"Current Price: ${retrace['current_price']:.2f}")
        print(f"Retrace from Peak: {retrace['retrace_percent']:.1f}% (Required: 20%-60%)")
        print(f"Volume vs Baseline: {retrace['volume_vs_baseline']:.1f}x")
        print(f"Retrace Criteria: {'✅ PASS' if retrace['meets_retrace_criteria'] else '❌ FAIL'}")

        support = retrace.get('support_analysis', {})
        if 'error' not in support:
            print(f"Support Level: ${support['support_level']:.2f}")
            print(f"Distance from Support: {support['distance_from_support_pct']:.1%}")
            print(f"Near Support: {'✅ YES' if support['near_support'] else '❌ NO'}")
    else:
        print(f"❌ Error: {retrace['error']}")

    # Red-to-Green Analysis
    print(f"\n💚 RED-TO-GREEN ANALYSIS")
    print("-" * 40)
    rtg = results.get('red_to_green', {})
    if 'error' not in rtg:
        print(f"Consecutive Red Days: {rtg['consecutive_red_days']} (Required: 1-7)")
        print(f"Volume Trend: {rtg['volume_trend']}")
        print(f"Higher Lows Pattern: {'✅ YES' if rtg['higher_lows_pattern'] else '❌ NO'}")
        print(f"Setup Readiness: {'✅ READY' if rtg['setup_readiness'] else '❌ NOT READY'}")
        print(f"Red Days Criteria: {'✅ PASS' if rtg['meets_red_criteria'] else '❌ FAIL'}")
    else:
        print(f"❌ Error: {rtg['error']}")

    # Overall Assessment
    print(f"\n📋 OVERALL ASSESSMENT")
    print("-" * 40)
    assessment = results.get('assessment', {})
    if 'error' not in assessment:
        print(f"Scanner Result: {'🟢 WOULD PASS' if assessment['would_pass_scanner'] else '🔴 WOULD FAIL'}")
        print(f"Criteria Pass Rate: {assessment['criteria_pass_rate']:.1%} ({assessment['criteria_met_count']}/{assessment['criteria_met_count'] + assessment['criteria_failed_count']})")
        print(f"\n{assessment['summary']}")

        if assessment['criteria_met']:
            print(f"\n✅ CRITERIA MET:")
            for criterion in assessment['criteria_met']:
                print(f"   {criterion}")

        if assessment['criteria_failed']:
            print(f"\n❌ CRITERIA FAILED:")
            for criterion in assessment['criteria_failed']:
                print(f"   {criterion}")
    else:
        print(f"❌ Error: {assessment['error']}")

    print("\n" + "="*80)

async def main():
    """Main analysis function"""
    logger.info("🎯 Starting TURB First Day Bounce Analysis")

    analyzer = TURBBounceAnalyzer()
    results = await analyzer.analyze_turb()

    print_analysis_report(results)

    logger.info("✅ Analysis complete")

if __name__ == "__main__":
    asyncio.run(main())