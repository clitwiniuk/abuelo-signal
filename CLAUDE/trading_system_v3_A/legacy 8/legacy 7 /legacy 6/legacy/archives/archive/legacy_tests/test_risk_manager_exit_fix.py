#!/usr/bin/env python3
"""
Test Risk Manager Exit Fix
Verify that exit orders bypass position value limits
"""

import asyncio
import logging
import sys
from datetime import datetime

# Add project root to path
sys.path.append('.')

from core.risk_manager import RiskManager
from core.interfaces import Order, OrderSide, OrderType, TradingConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_risk_manager_exit_fix():
    """Test that exit orders bypass position value limits"""
    
    logger.info("🧪 Testing Risk Manager Exit Order Fix")
    logger.info("="*50)
    
    # Create config with strict limits
    config = TradingConfig()
    config.max_position_value = 200.0  # $200 limit (same as in logs)
    config.max_daily_trades = 50
    config.max_daily_loss = -1000.0
    
    # Initialize risk manager
    risk_manager = RiskManager(config)
    
    # Test scenarios
    test_cases = [
        {
            'name': 'EXIT order above position limit',
            'symbol': 'IPA',
            'side': OrderSide.SELL,
            'quantity': 78,
            'price': 2.67,  # ~$208 value (above $200 limit)
            'is_exit': True,
            'should_pass': True  # Should pass because it's an exit
        },
        {
            'name': 'BUY order above position limit',
            'symbol': 'TEST',
            'side': OrderSide.BUY,
            'quantity': 100,
            'price': 2.50,  # $250 value (above $200 limit)
            'is_exit': False,
            'should_pass': False  # Should fail because it's a buy
        },
        {
            'name': 'EXIT order within limit',
            'symbol': 'SMALL',
            'side': OrderSide.SELL,
            'quantity': 50,
            'price': 3.00,  # $150 value (within $200 limit)
            'is_exit': True,
            'should_pass': True  # Should pass
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"\n📋 Testing: {test_case['name']}")
        logger.info(f"   Symbol: {test_case['symbol']}")
        logger.info(f"   Order: {test_case['side'].value} {test_case['quantity']} @ ${test_case['price']:.2f}")
        logger.info(f"   Value: ${test_case['quantity'] * test_case['price']:.2f}")
        logger.info(f"   Is Exit: {test_case['is_exit']}")
        logger.info(f"   Expected: {'PASS' if test_case['should_pass'] else 'FAIL'}")
        
        # Create order
        order = Order(
            order_id=f"test_{test_case['symbol']}_{datetime.now().timestamp()}",
            symbol=test_case['symbol'],
            side=test_case['side'],
            quantity=test_case['quantity'],
            order_type=OrderType.MARKET,
            price=test_case['price'],
            timestamp=datetime.now()
        )
        
        # Test validation
        try:
            is_valid = await risk_manager.validate_order_with_signal_context(
                order, 
                is_exit_order=test_case['is_exit']
            )
            
            # Check result
            success = is_valid == test_case['should_pass']
            result_text = "✅ PASS" if success else "❌ FAIL"
            
            logger.info(f"   Result: {result_text} (validation returned {is_valid})")
            
            results.append({
                'test': test_case['name'],
                'expected': test_case['should_pass'],
                'actual': is_valid,
                'success': success
            })
            
        except Exception as e:
            logger.error(f"   Error: {e}")
            results.append({
                'test': test_case['name'],
                'expected': test_case['should_pass'],
                'actual': 'ERROR',
                'success': False
            })
    
    # Summary
    logger.info(f"\n📊 TEST RESULTS SUMMARY:")
    logger.info("="*50)
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    logger.info(f"Tests passed: {passed}/{total}")
    logger.info(f"Success rate: {passed/total*100:.1f}%")
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        logger.info(f"   {status} {result['test']}")
        if not result['success']:
            logger.info(f"      Expected: {result['expected']}, Got: {result['actual']}")
    
    if passed == total:
        logger.info(f"\n🎉 ALL TESTS PASSED! Risk Manager exit fix is working correctly.")
    else:
        logger.warning(f"\n⚠️ {total - passed} tests failed. Risk Manager may need additional fixes.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(test_risk_manager_exit_fix())
    sys.exit(0 if success else 1)