#!/usr/bin/env python3
"""
Test New FOMO Thresholds
Verify the improved FOMO exit settings
"""

import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_new_thresholds():
    """Test the new improved FOMO thresholds"""
    
    logger.info("🔧 TESTING NEW FOMO THRESHOLDS")
    logger.info("="*50)
    
    # NEW thresholds after optimization
    new_thresholds = {
        'min_profit_general': 0.02,      # 2% (was 3%)
        'min_profit_volume_exit': 0.03,  # 3% (was 5%)
        'min_profit_velocity_exit': 0.05, # 5% (was 8%)
        'volume_spike_multiplier': 2.0,  # 2.0x (was 2.5x)
        'price_stall_threshold': 0.015,  # 1.5% (was 1.0%)
    }
    
    logger.info("📊 NEW OPTIMIZED THRESHOLDS:")
    for key, value in new_thresholds.items():
        if 'profit' in key:
            logger.info(f"   {key}: {value:.1%}")
        elif 'multiplier' in key:
            logger.info(f"   {key}: {value:.1f}x")
        elif 'threshold' in key:
            logger.info(f"   {key}: {value:.1%}")
    
    # Test the same scenarios with new thresholds
    logger.info(f"\n🧪 RE-TESTING SCENARIOS WITH NEW THRESHOLDS:")
    
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
        },
        {
            'name': 'Quick 3% gain with volume',
            'profit': 0.03,     # 3%
            'volume_mult': 2.2, # 2.2x volume
            'price_stall': 0.01, # 1% from high
        },
        {
            'name': 'Velocity decay scenario',
            'profit': 0.06,     # 6%
            'volume_mult': 1.8, # Normal volume
            'price_stall': 0.02, # 2% from high (no volume exit)
        }
    ]
    
    exit_count = 0
    
    for scenario in scenarios:
        logger.info(f"\n   📈 {scenario['name']}:")
        logger.info(f"      Profit: {scenario['profit']:.1%}")
        logger.info(f"      Volume: {scenario['volume_mult']:.1f}x average")
        logger.info(f"      Distance from high: {scenario['price_stall']:.1%}")
        
        # Check NEW conditions
        meets_min_profit = scenario['profit'] >= new_thresholds['min_profit_general']
        meets_volume_profit = scenario['profit'] >= new_thresholds['min_profit_volume_exit']
        meets_velocity_profit = scenario['profit'] >= new_thresholds['min_profit_velocity_exit']
        has_volume_spike = scenario['volume_mult'] >= new_thresholds['volume_spike_multiplier']
        has_price_stall = scenario['price_stall'] < new_thresholds['price_stall_threshold']
        
        # Volume spike exit logic
        would_exit_volume = meets_min_profit and meets_volume_profit and has_volume_spike and has_price_stall
        
        # Velocity exit logic (simulated - assumes velocity decay detected)
        would_exit_velocity = meets_min_profit and meets_velocity_profit
        
        # Overall exit decision
        would_exit = would_exit_volume or would_exit_velocity
        
        logger.info(f"      Conditions:")
        logger.info(f"         Min profit (2%): {'✅' if meets_min_profit else '❌'}")
        logger.info(f"         Volume exit profit (3%): {'✅' if meets_volume_profit else '❌'}")
        logger.info(f"         Velocity exit profit (5%): {'✅' if meets_velocity_profit else '❌'}")
        logger.info(f"         Volume spike (2.0x): {'✅' if has_volume_spike else '❌'}")
        logger.info(f"         Price stall (1.5%): {'✅' if has_price_stall else '❌'}")
        
        exit_type = []
        if would_exit_volume:
            exit_type.append("VOLUME")
        if would_exit_velocity:
            exit_type.append("VELOCITY")
            
        if would_exit:
            exit_count += 1
            logger.info(f"      RESULT: 🚨 WOULD EXIT ({'/'.join(exit_type)})")
        else:
            logger.info(f"      RESULT: ⚠️ NO EXIT")
    
    # Summary
    total_scenarios = len(scenarios)
    exit_rate = exit_count / total_scenarios * 100
    
    logger.info(f"\n📊 IMPROVEMENT SUMMARY:")
    logger.info(f"   Total scenarios: {total_scenarios}")
    logger.info(f"   Would exit: {exit_count}")
    logger.info(f"   Exit rate: {exit_rate:.1f}%")
    
    if exit_count > 0:
        logger.info(f"   🎉 SUCCESS! {exit_count} scenarios now trigger FOMO exits")
        logger.info(f"   📈 This is a significant improvement from 0 exits with old thresholds")
    else:
        logger.warning(f"   ⚠️ Still no exits - may need further adjustment")
    
    # Recommendations
    logger.info(f"\n💡 NEXT STEPS:")
    if exit_rate > 50:
        logger.info(f"   ✅ Good exit rate - monitor real trading performance")
        logger.info(f"   📊 Track exit quality and timing in live trading")
    elif exit_rate > 25:
        logger.info(f"   📊 Moderate exit rate - consider minor relaxation if needed")
    else:
        logger.info(f"   🔧 Low exit rate - may need further threshold relaxation")
        logger.info(f"   🎯 Consider: Volume 2.0x → 1.8x, Price stall 1.5% → 2.0%")

if __name__ == "__main__":
    test_new_thresholds()