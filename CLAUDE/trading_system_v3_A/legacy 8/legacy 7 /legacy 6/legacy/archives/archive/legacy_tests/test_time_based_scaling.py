#!/usr/bin/env python3
"""
Test Time-based Scaling for FOMO Exits
Verify that thresholds adjust correctly based on time of day
"""

import logging
from datetime import datetime, timezone, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_time_based_scaling():
    """Test time-based scaling logic"""
    
    logger.info("🕐 TESTING TIME-BASED SCALING FOR FOMO EXITS")
    logger.info("="*60)
    
    # Test different times throughout the trading day
    test_times = [
        {'time': '10:30', 'period': 'conservative', 'description': 'Morning momentum'},
        {'time': '11:45', 'period': 'conservative', 'description': 'Late morning'},
        {'time': '13:30', 'period': 'conservative', 'description': 'Midday'},
        {'time': '14:15', 'period': 'intermediate', 'description': 'Early afternoon'},
        {'time': '14:45', 'period': 'intermediate', 'description': 'Mid afternoon'},
        {'time': '15:05', 'period': 'aggressive', 'description': 'Late afternoon'},
        {'time': '15:30', 'period': 'aggressive', 'description': 'Pre-close'},
        {'time': '15:50', 'period': 'aggressive', 'description': 'Near close'}
    ]
    
    # Expected thresholds for each period
    thresholds = {
        'conservative': {
            'volume_multiplier': 2.0,
            'price_stall_pct': 0.015,
            'min_profit_volume': 0.03,
            'min_profit_velocity': 0.05
        },
        'intermediate': {
            'volume_multiplier': 1.8,
            'price_stall_pct': 0.02,
            'min_profit_volume': 0.025,
            'min_profit_velocity': 0.04
        },
        'aggressive': {
            'volume_multiplier': 1.5,
            'price_stall_pct': 0.025,
            'min_profit_volume': 0.02,
            'min_profit_velocity': 0.03
        }
    }
    
    # Test scenarios for each time period
    test_scenarios = [
        {
            'name': 'Modest volume spike with stall',
            'volume_mult': 1.6,  # Only triggers in aggressive mode
            'profit': 0.04,      # 4%
            'price_distance': 0.01  # 1% from high
        },
        {
            'name': 'Medium volume spike',
            'volume_mult': 1.9,  # Triggers in intermediate + aggressive
            'profit': 0.035,     # 3.5%
            'price_distance': 0.015  # 1.5% from high
        },
        {
            'name': 'Strong volume spike',
            'volume_mult': 2.2,  # Triggers in all modes
            'profit': 0.06,      # 6%
            'price_distance': 0.01   # 1% from high
        }
    ]
    
    logger.info("📊 TESTING THRESHOLDS BY TIME PERIOD:")
    logger.info("-" * 60)
    
    for time_test in test_times:
        time_str = time_test['time']
        hour = int(time_str.split(':')[0])
        minute = int(time_str.split(':')[1])
        expected_period = time_test['period']
        
        # Apply time-based logic (same as in code)
        if hour < 14:
            actual_period = "conservative"
        elif hour < 15:
            actual_period = "intermediate"
        else:
            actual_period = "aggressive"
        
        # Verify period matches expectation
        period_match = actual_period == expected_period
        status = "✅" if period_match else "❌"
        
        logger.info(f"\n{status} {time_str} ET - {time_test['description']}")
        logger.info(f"   Expected: {expected_period}, Actual: {actual_period}")
        
        if period_match:
            thresh = thresholds[actual_period]
            logger.info(f"   Volume threshold: {thresh['volume_multiplier']}x")
            logger.info(f"   Price stall: {thresh['price_stall_pct']:.1%}")
            logger.info(f"   Min profit (volume): {thresh['min_profit_volume']:.1%}")
            logger.info(f"   Min profit (velocity): {thresh['min_profit_velocity']:.1%}")
    
    logger.info(f"\n🧪 TESTING SCENARIOS ACROSS TIME PERIODS:")
    logger.info("="*60)
    
    for scenario in test_scenarios:
        logger.info(f"\n📋 SCENARIO: {scenario['name']}")
        logger.info(f"   Volume: {scenario['volume_mult']:.1f}x average")
        logger.info(f"   Profit: {scenario['profit']:.1%}")
        logger.info(f"   Distance from high: {scenario['price_distance']:.1%}")
        
        logger.info(f"\n   RESULTS BY TIME PERIOD:")
        
        for period_name, thresh in thresholds.items():
            # Check volume spike condition
            volume_spike = scenario['volume_mult'] >= thresh['volume_multiplier']
            
            # Check price stall condition
            price_stall = scenario['price_distance'] < thresh['price_stall_pct']
            
            # Check profit condition
            profit_ok = scenario['profit'] > thresh['min_profit_volume']
            
            # Overall FOMO trigger
            would_trigger = volume_spike and price_stall and profit_ok
            
            result = "🚨 TRIGGER" if would_trigger else "⚠️ NO EXIT"
            
            logger.info(f"      {period_name.upper()}: {result}")
            logger.info(f"        Volume: {'✅' if volume_spike else '❌'} ({scenario['volume_mult']:.1f}x >= {thresh['volume_multiplier']:.1f}x)")
            logger.info(f"        Price:  {'✅' if price_stall else '❌'} ({scenario['price_distance']:.1%} < {thresh['price_stall_pct']:.1%})")
            logger.info(f"        Profit: {'✅' if profit_ok else '❌'} ({scenario['profit']:.1%} > {thresh['min_profit_volume']:.1%})")
    
    logger.info(f"\n💡 EXPECTED BEHAVIOR:")
    logger.info("="*60)
    logger.info(f"""
🌅 MORNING (9:30-14:00): CONSERVATIVE
   - Maximiza profits en momentum fuerte
   - Volume threshold alto (2.0x)
   - Solo exits con señales muy claras
   
🌆 AFTERNOON (14:00-15:00): INTERMEDIATE  
   - Balance entre profit y protección
   - Volume threshold medio (1.8x)
   - Empieza a proteger más
   
🌇 LATE DAY (15:00-15:55): AGGRESSIVE
   - Protege profits activamente  
   - Volume threshold bajo (1.5x)
   - Mejor captura reversals
   
📈 RESULTADO ESPERADO:
   - Escenario 1: Solo triggerea en AGGRESSIVE (late day)
   - Escenario 2: Triggerea en INTERMEDIATE + AGGRESSIVE  
   - Escenario 3: Triggerea en TODOS los períodos
   
🎯 BENEFICIO:
   - Mantiene profits corriendo en la mañana
   - Protege gains progresivamente en la tarde
   - Evita exits prematuros pero captura reversals
""")

if __name__ == "__main__":
    test_time_based_scaling()