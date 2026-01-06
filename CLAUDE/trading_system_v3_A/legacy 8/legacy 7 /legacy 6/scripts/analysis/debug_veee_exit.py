#!/usr/bin/env python3
"""
Debug VEEE exit behavior - Verificar por qué no está saliendo correctamente
"""

import asyncio
import logging
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
from core.interfaces import Position, MarketData
from datetime import datetime
from core.ml_exit_engine import MLExitEngine

# Setup detailed logging
logging.basicConfig(level=logging.INFO)

async def debug_veee_exit():
    """Test specifically VEEE exit behavior"""
    
    print("🔍 DEBUGGING VEEE EXIT BEHAVIOR")
    print("=" * 50)
    
    try:
        # Create ML Exit Engine directly
        ml_exit_engine = MLExitEngine()
        print(f"✅ MLExitEngine initialized: {type(ml_exit_engine)}")
        
        # Create VEEE position (current position from logs)
        veee_position = Position(
            symbol='VEEE',
            quantity=73,
            avg_price=2.74,
            market_price=2.85,  # Recent price from logs
            entry_price=2.74,
            strategy='smallcap_bandit'
        )
        
        print(f"📊 VEEE Position:")
        print(f"   Quantity: {veee_position.quantity}")
        print(f"   Entry Price: ${veee_position.entry_price}")
        print(f"   Current Price: ${veee_position.market_price}")
        print(f"   Unrealized P&L: {(veee_position.market_price - veee_position.entry_price) * veee_position.quantity:.2f}")
        
        # Create current bar data
        from datetime import datetime as dt_class
        current_bar = MarketData(
            symbol='VEEE',
            timestamp=dt_class.now(),
            open=2.80,
            high=2.90,
            low=2.75,
            close=2.85,
            volume=150000
        )
        
        # Create bars history (simulate some historical data)
        bars_history = []
        base_prices = [2.70, 2.72, 2.74, 2.78, 2.82, 2.85]
        for i, price in enumerate(base_prices):
            bar = MarketData(
                symbol='VEEE',
                timestamp=dt_class.now(),
                open=price - 0.02,
                high=price + 0.05,
                low=price - 0.05,
                close=price,
                volume=100000 + i * 10000
            )
            bars_history.append(bar)
        
        print(f"\n📈 Market Data:")
        print(f"   Current: ${current_bar.close} (Vol: {current_bar.volume:,})")
        print(f"   High: ${current_bar.high}")
        print(f"   Low: ${current_bar.low}")
        print(f"   Bars history: {len(bars_history)} bars")
        
        # Test ML Exit Engine decision
        print(f"\n🧠 Testing ML Exit Engine decision...")
        ml_decision = ml_exit_engine.should_exit(veee_position, current_bar, bars_history)
        
        print(f"ML Decision: {ml_decision}")
        print(f"Should Exit: {ml_decision.get('should_exit', False)}")
        print(f"Reason: {ml_decision.get('reason', 'N/A')}")
        print(f"Exit Type: {ml_decision.get('exit_type', 'N/A')}")
        print(f"Confidence: {ml_decision.get('confidence', 0.0)}")
        
        # Test with different scenarios
        print(f"\n🧪 Testing different scenarios:")
        
        # Scenario 1: Higher profit
        high_profit_position = Position(
            symbol='VEEE',
            quantity=73,
            avg_price=2.50,  # Lower entry price
            market_price=2.85,
            entry_price=2.50,
            strategy='smallcap_bandit'
        )
        
        ml_decision_profit = ml_exit_engine.should_exit(high_profit_position, current_bar, bars_history)
        print(f"High Profit Scenario: {ml_decision_profit.get('should_exit', False)} - {ml_decision_profit.get('reason', 'N/A')}")
        
        # Scenario 2: Loss position
        loss_position = Position(
            symbol='VEEE',
            quantity=73,
            avg_price=3.00,  # Higher entry price
            market_price=2.85,
            entry_price=3.00,
            strategy='smallcap_bandit'
        )
        
        ml_decision_loss = ml_exit_engine.should_exit(loss_position, current_bar, bars_history)
        print(f"Loss Scenario: {ml_decision_loss.get('should_exit', False)} - {ml_decision_loss.get('reason', 'N/A')}")
        
        # Now test with the full ML Multi Strategy Engine
        print(f"\n🔬 Testing with MLMultiStrategyEngine...")
        
        engine = MLMultiStrategyEngine()
        # Initialize ML Exit Engine manually
        engine.ml_exit_engine = ml_exit_engine
        engine.positions['VEEE'] = veee_position
        
        # Test _check_exit_conditions
        exit_signal = await engine._check_exit_conditions('VEEE', current_bar)
        
        if exit_signal:
            print(f"✅ Exit Signal Generated:")
            print(f"   Signal Type: {exit_signal.signal_type}")
            print(f"   Strength: {exit_signal.strength}")
            print(f"   Price: ${exit_signal.price}")
            print(f"   Metadata: {exit_signal.metadata}")
        else:
            print(f"❌ No exit signal generated")
            
            # Let's check why - look at current time
            current_time = dt_class.now()
            print(f"   Current time: {current_time}")
            print(f"   Is after 15:55 ET? {current_time.hour >= 15 and current_time.minute >= 55}")
            
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(debug_veee_exit())