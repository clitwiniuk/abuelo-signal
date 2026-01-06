#!/usr/bin/env python3
"""
FOMO Threshold Analysis Tool
Quick test to understand current FOMO detection thresholds
"""

import logging
import sys
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_fomo_thresholds():
    """Analyze current FOMO detection thresholds"""
    
    logger.info("🔍 FOMO EXIT THRESHOLD ANALYSIS")
    logger.info("="*50)
    
    # Current thresholds from the code
    thresholds = {
        'min_profit_general': 0.03,      # 3% minimum profit for any FOMO exit
        'min_profit_volume_exit': 0.05,  # 5% minimum profit for volume spike exit
        'volume_spike_multiplier': 2.5,  # Volume must be 2.5x average
        'price_stall_threshold': 0.01,   # Price must be within 1% of recent high
        'velocity_threshold': 0.7,       # Velocity decay factor
        'rsi_oversold': 70,              # RSI threshold for momentum exhaustion
    }
    
    logger.info("📊 CURRENT THRESHOLDS:")
    for key, value in thresholds.items():
        if 'profit' in key:
            logger.info(f"   {key}: {value:.1%}")
        elif 'multiplier' in key:
            logger.info(f"   {key}: {value:.1f}x")
        elif 'threshold' in key:
            logger.info(f"   {key}: {value:.1%}")
        else:
            logger.info(f"   {key}: {value}")
    
    # Simulate different scenarios
    logger.info(f"\n🧪 SCENARIO ANALYSIS:")
    
    scenarios = [
        {
            'name': 'Typical smallcap move',
            'profit': 0.08,     # 8%
            'volume_mult': 2.0, # 2x volume
            'price_stall': 0.005, # 0.5% from high
        },
        {
            'name': 'Strong momentum play',
            'profit': 0.15,     # 15%
            'volume_mult': 4.0, # 4x volume
            'price_stall': 0.02, # 2% from high
        },
        {
            'name': 'Modest gain with spike',
            'profit': 0.04,     # 4%
            'volume_mult': 3.0, # 3x volume
            'price_stall': 0.008, # 0.8% from high
        },
        {
            'name': 'Large gain, normal volume',
            'profit': 0.12,     # 12%
            'volume_mult': 1.5, # 1.5x volume
            'price_stall': 0.005, # 0.5% from high
        }
    ]
    
    for scenario in scenarios:
        logger.info(f"\n   📈 {scenario['name']}:")
        logger.info(f"      Profit: {scenario['profit']:.1%}")
        logger.info(f"      Volume: {scenario['volume_mult']:.1f}x average")
        logger.info(f"      Distance from high: {scenario['price_stall']:.1%}")
        
        # Check conditions
        meets_min_profit = scenario['profit'] >= thresholds['min_profit_general']
        meets_volume_profit = scenario['profit'] >= thresholds['min_profit_volume_exit']
        has_volume_spike = scenario['volume_mult'] >= thresholds['volume_spike_multiplier']
        has_price_stall = scenario['price_stall'] < thresholds['price_stall_threshold']
        
        # Volume spike exit logic
        would_exit_volume = meets_min_profit and meets_volume_profit and has_volume_spike and has_price_stall
        
        logger.info(f"      Conditions:")
        logger.info(f"         Min profit (3%): {'✅' if meets_min_profit else '❌'}")
        logger.info(f"         Volume exit profit (5%): {'✅' if meets_volume_profit else '❌'}")
        logger.info(f"         Volume spike (2.5x): {'✅' if has_volume_spike else '❌'}")
        logger.info(f"         Price stall (1%): {'✅' if has_price_stall else '❌'}")
        logger.info(f"      RESULT: {'🚨 WOULD EXIT' if would_exit_volume else '⚠️ NO EXIT'}")
    
    # Recommendations
    logger.info(f"\n💡 THRESHOLD RECOMMENDATIONS:")
    
    logger.info(f"\n   🔧 If exits are TOO RARE:")
    logger.info(f"      - Lower volume spike: 2.5x → 2.0x or 1.8x")
    logger.info(f"      - Lower min profit: 3% → 2%") 
    logger.info(f"      - Lower volume exit profit: 5% → 3%")
    logger.info(f"      - Relax price stall: 1% → 1.5%")
    
    logger.info(f"\n   🔧 If exits are TOO FREQUENT:")
    logger.info(f"      - Raise volume spike: 2.5x → 3.0x")
    logger.info(f"      - Raise min profit: 3% → 4%")
    logger.info(f"      - Raise volume exit profit: 5% → 7%")
    logger.info(f"      - Tighten price stall: 1% → 0.5%")
    
    # Quick threshold test
    logger.info(f"\n🎯 QUICK THRESHOLD TEST:")
    test_profits = [0.02, 0.03, 0.04, 0.05, 0.08, 0.10, 0.15]
    
    for profit in test_profits:
        meets_min = profit >= thresholds['min_profit_general']
        meets_volume = profit >= thresholds['min_profit_volume_exit']
        
        status_min = "✅" if meets_min else "❌"
        status_volume = "✅" if meets_volume else "❌"
        
        logger.info(f"   {profit:.1%} profit: General {status_min} | Volume exit {status_volume}")

def check_current_code_thresholds():
    """Extract and display thresholds from actual code"""
    logger.info(f"\n🔍 CHECKING ACTUAL CODE THRESHOLDS:")
    
    try:
        # Read the actual strategy file
        with open('strategies/multi_strategy_engine_ml.py', 'r') as f:
            content = f.read()
        
        # Extract key threshold values
        import re
        
        patterns = {
            'min_profit': r'profit_pct < (0\.\d+)',
            'volume_spike': r'avg_volume \* ([\d\.]+)',
            'price_stall': r'recent_high < (0\.\d+)',
            'volume_exit_profit': r'profit_pct > (0\.\d+).*volume_spike'
        }
        
        logger.info("📄 Extracted from source code:")
        
        for name, pattern in patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                logger.info(f"   {name}: {matches}")
            else:
                logger.info(f"   {name}: Not found")
                
    except Exception as e:
        logger.error(f"Could not read strategy file: {e}")

if __name__ == "__main__":
    analyze_fomo_thresholds()
    check_current_code_thresholds()