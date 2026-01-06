#!/usr/bin/env python3
"""
Check ML Training Results
========================

Verifica los resultados del entrenamiento histórico del ML
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ml_strategy_selector import create_ml_strategy_selector, TickerContext

def check_training_results():
    print("📋 Checking ML Training Results")
    print("=" * 50)
    
    # Check if model exists
    model_path = "data/ml_models/historical_trained_selector.json"
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return False
        
    # Load and analyze model
    try:
        with open(model_path, 'r') as f:
            model_data = json.load(f)
            
        print(f"✅ Model loaded successfully")
        print(f"📅 Last updated: {model_data.get('timestamp', 'Unknown')}")
        print(f"🎯 Strategies trained: {model_data.get('strategies', [])}")
        
        # Analyze strategy statistics
        print(f"\n📊 Strategy Performance:")
        strategy_stats = model_data.get('strategy_stats', {})
        
        total_trades = 0
        total_wins = 0
        total_pnl = 0.0
        
        for strategy, stats in strategy_stats.items():
            trades = stats.get('total_trades', 0)
            wins = stats.get('winning_trades', 0)
            pnl = stats.get('total_pnl', 0.0)
            win_rate = stats.get('win_rate', 0.0)
            avg_pnl = stats.get('avg_pnl', 0.0)
            
            total_trades += trades
            total_wins += wins
            total_pnl += pnl
            
            print(f"   {strategy:15} {trades:3d} trades | {win_rate:5.1%} WR | {avg_pnl:+6.3f} avg PnL")
        
        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        print(f"\n🎯 Overall Results:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Total Wins: {total_wins}")
        print(f"   Overall Win Rate: {overall_wr:.1f}%")
        print(f"   Total PnL (rewards): {total_pnl:+.3f}")
        print(f"   Avg PnL per Trade: {avg_pnl_per_trade:+.3f}")
        
        # Test strategy selection
        print(f"\n🔮 Testing Strategy Selection:")
        
        # Load ML selector
        ml_selector = create_ml_strategy_selector(
            strategies=['gap_go', 'macdv_smallcaps', 'daily_plays', 'reversal_play'],
            model_path=model_path
        )
        
        # Test different scenarios
        test_scenarios = [
            {
                'name': 'High Volume Smallcap',
                'context': TickerContext(
                    symbol='TEST1',
                    current_price=3.50,
                    avg_volume_10=150000,
                    avg_volume_50=100000,
                    volatility_10=0.45,
                    volatility_50=0.35,
                    price_change_1h=0.08,
                    price_change_4h=0.12,
                    rsi_14=65,
                    volume_ratio_current=3.5,
                    volume_spike_frequency=0.3,
                    hour_of_day=9.5,
                    minutes_from_open=30,
                    is_first_hour=True,
                    is_last_hour=False,
                    market_trend=0.2,
                    sector_performance=0.1,
                    breakout_success_rate=0.8,
                    mean_reversion_tendency=0.3
                )
            },
            {
                'name': 'Oversold Reversal Setup',
                'context': TickerContext(
                    symbol='TEST2',
                    current_price=6.80,
                    avg_volume_10=80000,
                    avg_volume_50=60000,
                    volatility_10=0.65,
                    volatility_50=0.55,
                    price_change_1h=-0.12,
                    price_change_4h=-0.18,
                    rsi_14=28,
                    volume_ratio_current=2.8,
                    volume_spike_frequency=0.4,
                    hour_of_day=14.5,
                    minutes_from_open=300,
                    is_first_hour=False,
                    is_last_hour=False,
                    market_trend=-0.1,
                    sector_performance=-0.05,
                    breakout_success_rate=0.4,
                    mean_reversion_tendency=0.8
                )
            },
            {
                'name': 'Stable Daily Play',
                'context': TickerContext(
                    symbol='TEST3',
                    current_price=8.20,
                    avg_volume_10=200000,
                    avg_volume_50=180000,
                    volatility_10=0.25,
                    volatility_50=0.22,
                    price_change_1h=0.03,
                    price_change_4h=0.05,
                    rsi_14=55,
                    volume_ratio_current=1.8,
                    volume_spike_frequency=0.1,
                    hour_of_day=11.0,
                    minutes_from_open=90,
                    is_first_hour=False,
                    is_last_hour=False,
                    market_trend=0.05,
                    sector_performance=0.02,
                    breakout_success_rate=0.6,
                    mean_reversion_tendency=0.4
                )
            }
        ]
        
        for scenario in test_scenarios:
            strategy = ml_selector.select_strategy(scenario['context'])
            rankings = ml_selector.get_strategy_rankings(scenario['context'])
            
            print(f"\n   📈 {scenario['name']}:")
            print(f"      Best Strategy: {strategy}")
            print(f"      Rankings:")
            for i, (strat, reward) in enumerate(rankings[:3], 1):
                print(f"         {i}. {strat}: {reward:+.3f}")
        
        # Training quality assessment
        print(f"\n🧠 Training Quality Assessment:")
        
        if total_trades >= 200:
            quality = "🎉 EXCELLENT"
        elif total_trades >= 100:
            quality = "✅ GOOD"
        elif total_trades >= 50:
            quality = "⚠️ MODERATE"
        else:
            quality = "❌ INSUFFICIENT"
            
        print(f"   Training Data: {quality} ({total_trades} trades)")
        
        if overall_wr >= 65:
            performance = "🏆 OUTSTANDING"
        elif overall_wr >= 55:
            performance = "✅ GOOD"
        elif overall_wr >= 45:
            performance = "⚠️ AVERAGE"
        else:
            performance = "❌ POOR"
            
        print(f"   Win Rate: {performance} ({overall_wr:.1f}%)")
        
        # Final assessment
        print(f"\n" + "=" * 50)
        print("📋 FINAL ASSESSMENT")
        print("=" * 50)
        
        if total_trades >= 100 and overall_wr >= 50:
            print("🎉 ML MODEL READY FOR PRODUCTION!")
            print("✅ Sufficient training data")
            print("✅ Acceptable performance")
            print("✅ Strategy selection working")
            print("🚀 You can now use this model in live trading")
            
            return True
        else:
            print("⚠️ Model needs more training or tuning")
            if total_trades < 100:
                print("❌ Insufficient training data")
            if overall_wr < 50:
                print("❌ Poor win rate")
            return False
            
    except Exception as e:
        print(f"❌ Error analyzing model: {e}")
        return False

if __name__ == "__main__":
    success = check_training_results()
    sys.exit(0 if success else 1)