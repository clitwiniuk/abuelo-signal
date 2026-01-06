#!/usr/bin/env python3
"""
Test ML Trained Models - Verificar que el MLExitEngine carga y usa los modelos entrenados
"""

import asyncio
import logging
from core.ml_exit_engine import MLExitEngine
from core.interfaces import Position, MarketData
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_trained_models():
    """Test que los modelos entrenados se cargan y funcionan correctamente"""
    
    print("🔍 TESTING TRAINED ML MODELS")
    print("=" * 50)
    
    try:
        # Initialize MLExitEngine
        ml_engine = MLExitEngine()
        
        print(f"✅ MLExitEngine initialized")
        
        # Create test position and data
        test_position = Position(
            symbol='TEST',
            quantity=100,
            avg_price=5.00,
            market_price=5.30,
            entry_price=5.00,
            strategy='smallcap_test'
        )
        
        # Create market data
        et_tz = ZoneInfo('US/Eastern')
        test_time = datetime(2025, 9, 6, 14, 30, 0).replace(tzinfo=et_tz)  # 14:30 ET
        
        test_bar = MarketData(
            symbol='TEST',
            timestamp=test_time,
            open=5.25,
            high=5.40,
            low=5.20,
            close=5.30,
            volume=75000
        )
        
        # Create some history bars
        bars_history = []
        for i in range(10):
            price = 5.00 + i * 0.03
            bar = MarketData(
                symbol='TEST',
                timestamp=test_time,
                open=price - 0.02,
                high=price + 0.05,
                low=price - 0.03,
                close=price,
                volume=50000 + i * 5000
            )
            bars_history.append(bar)
        
        print(f"📊 Test Data:")
        print(f"   Position: {test_position.quantity} shares @ ${test_position.entry_price}")
        print(f"   Current: ${test_bar.close} ({((test_bar.close - test_position.entry_price) / test_position.entry_price):.1%} profit)")
        print(f"   History: {len(bars_history)} bars")
        
        # Test the ML decision
        print(f"\n🧠 Testing ML Exit Decision...")
        ml_decision = ml_engine.should_exit(test_position, test_bar, bars_history)
        
        print(f"\n📊 ML EXIT DECISION:")
        print(f"   Should Exit: {ml_decision.get('should_exit', False)}")
        print(f"   Exit Type: {ml_decision.get('exit_type', 'N/A')}")
        print(f"   Confidence: {ml_decision.get('confidence', 0.0):.3f}")
        print(f"   Expected Value: {ml_decision.get('expected_value', 0.0):.4f}")
        print(f"   Reasons: {ml_decision.get('reasons', [])}")
        
        # Check if models were loaded
        has_models = False
        for strategy, model in ml_engine.exit_models.items():
            if model is not None:
                print(f"✅ Loaded exit model for strategy: {strategy}")
                has_models = True
        
        for strategy, model in ml_engine.profit_predictors.items():
            if model is not None:
                print(f"✅ Loaded profit predictor for strategy: {strategy}")
                has_models = True
        
        if not has_models:
            print(f"⚠️ No trained models loaded - using heuristic fallback")
        
        # Test with different profit scenarios
        print(f"\n🧪 Testing different profit scenarios:")
        
        scenarios = [
            ("Small Loss", Position('TEST', 100, 5.00, 4.85, entry_price=5.00, strategy='test')),
            ("Break Even", Position('TEST', 100, 5.00, 5.01, entry_price=5.00, strategy='test')),
            ("Small Profit", Position('TEST', 100, 5.00, 5.15, entry_price=5.00, strategy='test')),
            ("Good Profit", Position('TEST', 100, 5.00, 5.50, entry_price=5.00, strategy='test')),
            ("High Profit", Position('TEST', 100, 5.00, 6.00, entry_price=5.00, strategy='test')),
        ]
        
        for scenario_name, position in scenarios:
            test_bar_scenario = MarketData(
                symbol='TEST',
                timestamp=test_time,
                open=position.market_price - 0.02,
                high=position.market_price + 0.05,
                low=position.market_price - 0.05,
                close=position.market_price,
                volume=75000
            )
            
            decision = ml_engine.should_exit(position, test_bar_scenario, bars_history)
            pnl_pct = (position.market_price - position.entry_price) / position.entry_price
            
            print(f"   {scenario_name:12} ({pnl_pct:+6.1%}): Exit={decision.get('should_exit', False)}, Confidence={decision.get('confidence', 0):.2f}")
        
        print("=" * 50)
        print("🎯 Trained ML Models Test Complete")
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_trained_models())