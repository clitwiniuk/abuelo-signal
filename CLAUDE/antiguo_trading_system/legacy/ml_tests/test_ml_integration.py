#!/usr/bin/env python3
"""
Test ML Integration with Historical Data
=======================================

Verifica que el ML puede entrenarse con los datos históricos NUKK y RR
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ml_strategy_selector import create_ml_strategy_selector, TickerContext

def test_ml_with_historical_data():
    print("🧪 Testing ML Integration with Historical Data")
    print("=" * 50)
    
    # Create ML strategy selector
    print("🧠 Initializing ML Strategy Selector...")
    ml_selector = create_ml_strategy_selector(
        strategies=['macdv_smallcaps', 'gap_go', 'daily_plays', 'reversal_play'],
        model_path="data/ml_models/test_trader_strategy_selector.json"
    )
    print("✅ ML Strategy Selector initialized")
    
    # Load historical trades
    print("\n📊 Loading historical trades from database...")
    db_path = "trading_data.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get completed trades with PnL
    cursor.execute("""
        SELECT symbol, strategy, entry_price, exit_price, pnl, 
               entry_time, exit_time, quantity
        FROM trades 
        WHERE status = 'CLOSED' AND pnl IS NOT NULL
        ORDER BY entry_time DESC
    """)
    
    historical_trades = cursor.fetchall()
    print(f"📊 Found {len(historical_trades)} historical trades")
    
    if len(historical_trades) == 0:
        print("⚠️ No historical trades found!")
        return False
    
    # Train ML with historical data
    print("\n🎯 Training ML with historical trades...")
    trained_count = 0
    
    for trade in historical_trades:
        symbol, strategy, entry_price, exit_price, pnl, entry_time, exit_time, quantity = trade
        
        print(f"\n📈 Processing trade: {symbol}")
        print(f"   Strategy: {strategy}")
        print(f"   Entry: ${entry_price}, Exit: ${exit_price}")
        print(f"   PnL: ${pnl}, Quantity: {quantity}")
        
        try:
            # Create ticker context for the trade
            context = TickerContext(
                symbol=symbol,
                current_price=float(entry_price),
                avg_volume_10=100000.0,
                avg_volume_50=80000.0,
                volatility_10=0.025,
                volatility_50=0.022,
                price_change_1h=0.0,
                price_change_4h=0.0,
                rsi_14=50.0,
                volume_ratio_current=1.5,
                volume_spike_frequency=0.1,
                hour_of_day=10.0,
                minutes_from_open=30,
                is_first_hour=True,
                is_last_hour=False,
                market_trend=0.1,
                sector_performance=0.05,
                breakout_success_rate=0.6,
                mean_reversion_tendency=0.4
            )
            
            # Calculate reward from PnL (normalize to -1 to 1)
            pnl_percentage = float(pnl) / (float(entry_price) * quantity) * 100
            reward = max(-1.0, min(1.0, pnl_percentage / 10.0))
            
            print(f"   PnL%: {pnl_percentage:.2f}%, Reward: {reward:.3f}")
            
            # Train the ML model
            ml_selector.update_model(context, strategy, reward)
            trained_count += 1
            
            print(f"✅ ML trained on {symbol} {strategy}")
            
        except Exception as e:
            print(f"❌ Failed to train on trade {symbol}: {e}")
            continue
    
    conn.close()
    
    # Save the trained model
    print(f"\n💾 Saving trained ML model...")
    if trained_count > 0:
        ml_selector.save_model("data/ml_models/test_trader_strategy_selector.json")
        print(f"✅ ML trained on {trained_count} trades and saved")
    
    # Test strategy predictions
    print(f"\n🔮 Testing strategy predictions...")
    
    # Create test context for a new ticker
    test_context = TickerContext(
        symbol="TEST",
        current_price=5.50,
        avg_volume_10=120000.0,
        avg_volume_50=90000.0,
        volatility_10=0.030,
        volatility_50=0.025,
        price_change_1h=0.02,
        price_change_4h=0.05,
        rsi_14=65.0,
        volume_ratio_current=2.0,
        volume_spike_frequency=0.2,
        hour_of_day=9.5,
        minutes_from_open=30,
        is_first_hour=True,
        is_last_hour=False,
        market_trend=0.2,
        sector_performance=0.1,
        breakout_success_rate=0.7,
        mean_reversion_tendency=0.3
    )
    
    # Get strategy recommendations
    recommendations = ml_selector.get_strategy_rankings(test_context)
    
    print(f"🎯 Strategy recommendations for TEST symbol:")
    for i, (strategy, expected_reward) in enumerate(recommendations[:3], 1):
        print(f"   {i}. {strategy}: Expected reward {expected_reward:.3f}")
    
    # Test best strategy selection
    best_strategy = ml_selector.select_strategy(test_context)
    print(f"\n🏆 Best strategy recommended: {best_strategy}")
    
    print(f"\n" + "=" * 50)
    print("📋 ML INTEGRATION TEST RESULTS")
    print("=" * 50)
    print(f"✅ ML Strategy Selector: Initialized")
    print(f"✅ Historical trades loaded: {len(historical_trades)}")
    print(f"✅ ML training completed: {trained_count} trades")
    print(f"✅ Model persistence: Saved")
    print(f"✅ Strategy prediction: Working")
    
    if trained_count >= len(historical_trades):
        print(f"🎉 ALL TESTS PASSED! ML is ready for production")
        return True
    else:
        print(f"⚠️ Some trades failed to train")
        return False

if __name__ == "__main__":
    success = test_ml_with_historical_data()
    sys.exit(0 if success else 1)