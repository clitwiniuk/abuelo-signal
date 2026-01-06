#!/usr/bin/env python3
"""
Test EOD Exit Priority - Verificar que EOD exits son incondicionales
"""

import asyncio
import logging
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
from core.interfaces import Position, MarketData
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_eod_exit_priority():
    """Test que EOD exits tienen prioridad absoluta"""
    
    print("🔍 TESTING EOD EXIT PRIORITY")
    print("=" * 50)
    
    try:
        # Create engine
        engine = MLMultiStrategyEngine()
        
        # Create test position
        test_position = Position(
            symbol='TEST',
            quantity=100,
            avg_price=5.00,
            market_price=5.50,
            entry_price=5.00,
            strategy='test_strategy'
        )
        
        # Add position to engine
        engine.positions['TEST'] = test_position
        
        print(f"📊 Test Position: {test_position.quantity} shares @ ${test_position.entry_price}")
        
        # Test 1: BEFORE EOD time (should return None)
        et_tz = ZoneInfo('US/Eastern')
        before_eod_time = datetime(2025, 9, 6, 15, 50, 0).replace(tzinfo=et_tz)  # 15:50 ET
        
        before_eod_bar = MarketData(
            symbol='TEST',
            timestamp=before_eod_time,
            open=5.40,
            high=5.60,
            low=5.30,
            close=5.50,
            volume=100000
        )
        
        print(f"🕐 Testing BEFORE EOD (15:50 ET)...")
        eod_signal_before = await engine._check_eod_exit('TEST', before_eod_bar, test_position)
        
        if eod_signal_before:
            print(f"❌ UNEXPECTED: EOD signal generated before 15:55")
        else:
            print(f"✅ CORRECT: No EOD signal before 15:55")
        
        # Test 2: AT EOD time (should return EXIT signal)  
        at_eod_time = datetime(2025, 9, 6, 15, 55, 0).replace(tzinfo=et_tz)  # 15:55 ET
        
        at_eod_bar = MarketData(
            symbol='TEST',
            timestamp=at_eod_time,
            open=5.45,
            high=5.60,
            low=5.40,
            close=5.50,
            volume=50000
        )
        
        print(f"🕐 Testing AT EOD (15:55 ET)...")
        eod_signal_at = await engine._check_eod_exit('TEST', at_eod_bar, test_position)
        
        if eod_signal_at:
            print(f"✅ CORRECT: EOD signal generated at 15:55")
            print(f"   Signal Type: {eod_signal_at.signal_type}")
            print(f"   Strength: {eod_signal_at.strength}")
            print(f"   Reason: {eod_signal_at.metadata.get('reason')}")
            print(f"   Exit Time: {eod_signal_at.metadata.get('exit_time')}")
        else:
            print(f"❌ PROBLEM: No EOD signal generated at 15:55")
        
        # Test 3: FULL exit conditions check (should prioritize EOD)
        print(f"🧪 Testing full _check_exit_conditions at 15:55...")
        
        # Add some bars history to avoid fallback
        engine.bars_history['TEST'] = [before_eod_bar, at_eod_bar]
        
        full_exit_signal = await engine._check_exit_conditions('TEST', at_eod_bar)
        
        if full_exit_signal:
            print(f"✅ FULL EXIT SIGNAL GENERATED:")
            print(f"   Type: {full_exit_signal.signal_type}")
            print(f"   Strength: {full_exit_signal.strength}")
            print(f"   Metadata: {full_exit_signal.metadata}")
            
            # Verify it's EOD signal (not ML)
            if full_exit_signal.metadata.get('reason') == 'end_of_day_exit':
                print(f"✅ PRIORITY CORRECT: EOD signal has priority over ML")
            else:
                print(f"⚠️ PRIORITY ISSUE: Non-EOD signal generated")
                
        else:
            print(f"❌ CRITICAL PROBLEM: No exit signal generated at all")
            
        print("=" * 50)
        print("🎯 EOD Exit Priority Test Complete")
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_eod_exit_priority())