#!/usr/bin/env python3
"""
Analysis of Other Symbols for First Day Bounce Scanner

Analyzes the symbols that were scanned but found 0 bounce setups:
AIHS, CNFR, APVO, NAKA, SLNH, NUKK, IMTE, SNTG, OPI

For each symbol, checks:
1. Are they in momentum phase or already pulled back?
2. Do they meet overextension criteria (30%+ gain, 2x volume)?
3. Do they have required retrace (20-60% from peak)?
4. Do they have red days for potential bounce setup?

Usage:
    python analyze_other_symbols_bounce.py
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
logger = logging.getLogger("SymbolsAnalysis")

class SymbolsBounceAnalyzer:
    """Analyzer for multiple symbols bounce potential"""

    def __init__(self):
        self.ibkr = IBKRAdapter(host="127.0.0.1", port=7497, client_id=4151)

        # Symbols that were scanned but found 0 bounce setups
        self.symbols = ["AIHS", "CNFR", "APVO", "NAKA", "SLNH", "NUKK", "IMTE", "SNTG", "OPI"]

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

    async def analyze_all_symbols(self) -> Dict[str, Any]:
        """Complete analysis of all symbols"""
        try:
            # Connect to IBKR
            logger.info("🔌 Connecting to IBKR...")
            await self.ibkr.connect()

            if not self.ibkr.is_connected():
                raise Exception("Failed to connect to IBKR")

            logger.info(f"✅ Connected to IBKR, analyzing {len(self.symbols)} symbols")

            results = {
                'analysis_timestamp': datetime.now().isoformat(),
                'total_symbols': len(self.symbols),
                'criteria': self.criteria,
                'symbols': {}
            }

            # Analyze each symbol
            for symbol in self.symbols:
                try:
                    logger.info(f"📊 Analyzing {symbol}...")
                    symbol_result = await self._analyze_symbol(symbol)
                    results['symbols'][symbol] = symbol_result
                    await asyncio.sleep(1)  # Be respectful to IBKR
                except Exception as e:
                    logger.error(f"❌ Error analyzing {symbol}: {e}")
                    results['symbols'][symbol] = {"error": str(e)}

            # Generate summary
            results['summary'] = self._generate_summary(results['symbols'])

            return results

        except Exception as e:
            logger.error(f"❌ Error in analysis: {e}")
            return {"error": str(e)}

        finally:
            if self.ibkr.is_connected():
                await self.ibkr.disconnect()
                logger.info("🔌 Disconnected from IBKR")

    async def _analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """Analyze individual symbol"""
        try:
            # Get 30 days of daily data
            bars = await self.ibkr.get_bars(symbol, "1 day", 30)

            if not bars or len(bars) < 10:
                return {"error": f"Insufficient data: {len(bars) if bars else 0} bars"}

            # Convert to analysis format
            daily_data = self._convert_bars_to_analysis_format(bars)

            # Quick phase identification
            current_price = daily_data[-1]['close']
            prices = [bar['close'] for bar in daily_data]

            # Find recent peak
            recent_peak = max(prices[-10:]) if len(prices) >= 10 else max(prices)
            peak_distance = (recent_peak - current_price) / recent_peak if recent_peak > 0 else 0

            # Quick overextension check
            if len(daily_data) >= 20:
                base_price = np.mean(prices[-25:-15]) if len(prices) >= 25 else np.mean(prices[:-10])
                total_gain = (recent_peak - base_price) / base_price if base_price > 0 else 0
            else:
                base_price = prices[0] if prices else current_price
                total_gain = (recent_peak - base_price) / base_price if base_price > 0 else 0

            # Count red days
            consecutive_red = 0
            for bar in reversed(daily_data[-7:]):
                if bar['close'] < bar['open']:
                    consecutive_red += 1
                else:
                    break

            # Volume analysis
            volumes = [bar['volume'] for bar in daily_data]
            recent_volume = np.mean(volumes[-3:]) if len(volumes) >= 3 else volumes[-1] if volumes else 0
            baseline_volume = np.mean(volumes[-20:-10]) if len(volumes) >= 20 else np.mean(volumes[:-3]) if len(volumes) > 3 else recent_volume
            volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 0

            # Determine phase
            if peak_distance < 0.05:  # Within 5% of peak
                phase = "MOMENTUM_PHASE"
                phase_description = "Still at or near peak - no meaningful pullback yet"
            elif peak_distance < 0.20:
                phase = "EARLY_PULLBACK"
                phase_description = f"Small pullback ({peak_distance:.1%}) - needs more retrace for bounce setup"
            elif peak_distance > 0.60:
                phase = "DEEP_PULLBACK"
                phase_description = f"Deep pullback ({peak_distance:.1%}) - may have overshot bounce range"
            else:
                phase = "POTENTIAL_BOUNCE_ZONE"
                phase_description = f"In bounce zone ({peak_distance:.1%} retrace)"

            return {
                'current_price': current_price,
                'recent_peak': recent_peak,
                'peak_distance_pct': peak_distance,
                'total_gain_from_base': total_gain,
                'consecutive_red_days': consecutive_red,
                'volume_ratio': volume_ratio,
                'data_bars': len(bars),
                'phase': phase,
                'phase_description': phase_description,
                'meets_overextension_gain': total_gain >= self.criteria['min_gain_pct'],
                'meets_volume_criteria': volume_ratio >= self.criteria['min_volume_multiple'],
                'meets_retrace_range': self.criteria['min_retrace_pct'] <= peak_distance <= self.criteria['max_retrace_pct'],
                'meets_red_days': self.criteria['min_days_red'] <= consecutive_red <= self.criteria['max_days_red'],
                'would_pass_scanner': all([
                    total_gain >= self.criteria['min_gain_pct'],
                    volume_ratio >= self.criteria['min_volume_multiple'],
                    self.criteria['min_retrace_pct'] <= peak_distance <= self.criteria['max_retrace_pct'],
                    self.criteria['min_days_red'] <= consecutive_red <= self.criteria['max_days_red']
                ])
            }

        except Exception as e:
            return {"error": str(e)}

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

    def _generate_summary(self, symbols_data: Dict) -> Dict[str, Any]:
        """Generate summary of all symbols"""
        try:
            total_symbols = len(symbols_data)
            symbols_with_errors = sum(1 for data in symbols_data.values() if 'error' in data)
            valid_symbols = total_symbols - symbols_with_errors

            if valid_symbols == 0:
                return {"error": "No valid symbol data available"}

            # Count by phase
            phase_counts = {}
            criteria_failures = {
                'overextension_gain': 0,
                'volume': 0,
                'retrace_range': 0,
                'red_days': 0
            }

            for symbol, data in symbols_data.items():
                if 'error' in data:
                    continue

                phase = data.get('phase', 'UNKNOWN')
                phase_counts[phase] = phase_counts.get(phase, 0) + 1

                # Count criteria failures
                if not data.get('meets_overextension_gain', False):
                    criteria_failures['overextension_gain'] += 1
                if not data.get('meets_volume_criteria', False):
                    criteria_failures['volume'] += 1
                if not data.get('meets_retrace_range', False):
                    criteria_failures['retrace_range'] += 1
                if not data.get('meets_red_days', False):
                    criteria_failures['red_days'] += 1

            # Most common failure reason
            most_common_failure = max(criteria_failures.items(), key=lambda x: x[1])

            return {
                'total_analyzed': valid_symbols,
                'symbols_with_errors': symbols_with_errors,
                'phase_distribution': phase_counts,
                'criteria_failures': criteria_failures,
                'most_common_failure': most_common_failure[0],
                'most_common_failure_count': most_common_failure[1],
                'symbols_that_would_pass': sum(1 for data in symbols_data.values()
                                              if 'error' not in data and data.get('would_pass_scanner', False)),
                'conclusion': self._generate_conclusion(phase_counts, criteria_failures, valid_symbols)
            }

        except Exception as e:
            return {"error": str(e)}

    def _generate_conclusion(self, phase_counts: Dict, criteria_failures: Dict, total: int) -> str:
        """Generate conclusion about why scanner finds 0 bounce setups"""
        # Find dominant phase
        dominant_phase = max(phase_counts.items(), key=lambda x: x[1]) if phase_counts else ("UNKNOWN", 0)

        # Find most common failure
        most_common_failure = max(criteria_failures.items(), key=lambda x: x[1])

        conclusions = []

        if dominant_phase[0] == "MOMENTUM_PHASE":
            conclusions.append(f"Most symbols ({dominant_phase[1]}/{total}) are still in momentum phase - haven't pulled back yet")
        elif dominant_phase[0] == "EARLY_PULLBACK":
            conclusions.append(f"Most symbols ({dominant_phase[1]}/{total}) have only small pullbacks - need deeper retraces")
        elif dominant_phase[0] == "DEEP_PULLBACK":
            conclusions.append(f"Most symbols ({dominant_phase[1]}/{total}) have pulled back too much - overshot bounce zone")

        if most_common_failure[1] > total * 0.6:  # If >60% fail the same criteria
            failure_descriptions = {
                'overextension_gain': "lack sufficient initial gain (need 30%+)",
                'volume': "lack volume confirmation (need 2x+ volume)",
                'retrace_range': "are not in the correct retrace range (need 20-60%)",
                'red_days': "don't have enough red days for bounce setup (need 1-7 red days)"
            }
            conclusions.append(f"Primary issue: most symbols {failure_descriptions.get(most_common_failure[0], 'fail criteria')}")

        if not conclusions:
            conclusions.append("Mixed issues across different criteria prevent bounce setups")

        return ". ".join(conclusions) + "."

def print_analysis_report(results: Dict[str, Any]):
    """Print detailed analysis report"""
    print("\n" + "="*80)
    print("🎯 MULTIPLE SYMBOLS FIRST DAY BOUNCE SCANNER ANALYSIS")
    print("="*80)

    if 'error' in results:
        print(f"❌ Analysis Error: {results['error']}")
        return

    print(f"\n📊 Analysis Overview")
    print(f"📅 Timestamp: {results['analysis_timestamp']}")
    print(f"🔢 Total Symbols Analyzed: {results['total_symbols']}")

    summary = results.get('summary', {})
    if 'error' not in summary:
        print(f"✅ Successfully Analyzed: {summary['total_analyzed']}")
        print(f"❌ Symbols with Errors: {summary['symbols_with_errors']}")
        print(f"🎯 Symbols that Would Pass Scanner: {summary['symbols_that_would_pass']}")

    # Phase Distribution
    print(f"\n📊 MARKET PHASE DISTRIBUTION")
    print("-" * 50)
    if 'error' not in summary:
        for phase, count in summary['phase_distribution'].items():
            print(f"{phase}: {count} symbols")

    # Criteria Failures
    print(f"\n❌ CRITERIA FAILURE ANALYSIS")
    print("-" * 50)
    if 'error' not in summary:
        total_analyzed = summary['total_analyzed']
        for criteria, count in summary['criteria_failures'].items():
            percentage = (count / total_analyzed * 100) if total_analyzed > 0 else 0
            print(f"{criteria.replace('_', ' ').title()}: {count}/{total_analyzed} ({percentage:.1f}%)")

    # Individual Symbol Details
    print(f"\n📋 INDIVIDUAL SYMBOL ANALYSIS")
    print("-" * 50)
    for symbol, data in results['symbols'].items():
        if 'error' in data:
            print(f"❌ {symbol}: {data['error']}")
        else:
            phase_emoji = {
                "MOMENTUM_PHASE": "🚀",
                "EARLY_PULLBACK": "📉",
                "POTENTIAL_BOUNCE_ZONE": "🎯",
                "DEEP_PULLBACK": "⬇️"
            }.get(data['phase'], "❓")

            print(f"{phase_emoji} {symbol}: ${data['current_price']:.2f} | "
                  f"Phase: {data['phase']} | "
                  f"Pullback: {data['peak_distance_pct']:.1%} | "
                  f"Red Days: {data['consecutive_red_days']} | "
                  f"{'✅ PASS' if data['would_pass_scanner'] else '❌ FAIL'}")

    # Conclusion
    print(f"\n🎯 CONCLUSION")
    print("-" * 50)
    if 'error' not in summary:
        print(summary['conclusion'])
    else:
        print(f"❌ Unable to generate conclusion: {summary['error']}")

    print("\n" + "="*80)

async def main():
    """Main analysis function"""
    logger.info("🎯 Starting Multiple Symbols First Day Bounce Analysis")

    analyzer = SymbolsBounceAnalyzer()
    results = await analyzer.analyze_all_symbols()

    print_analysis_report(results)

    logger.info("✅ Analysis complete")

if __name__ == "__main__":
    asyncio.run(main())