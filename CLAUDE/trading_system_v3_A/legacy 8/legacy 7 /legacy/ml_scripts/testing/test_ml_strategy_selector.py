#!/usr/bin/env python3
"""
Test ML Strategy Selector - Verificar selección inteligente de estrategias
"""

import asyncio
import logging
from strategies.ml_strategy_selector import (
    create_ml_strategy_selector,
    TickerContext
)
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_strategy_selection():
    """Test que el ML Strategy Selector hace selecciones inteligentes"""
    
    print("🔍 TESTING ML STRATEGY SELECTOR")
    print("=" * 50)
    
    try:
        # Definir estrategias como en el training
        # 7 estrategias específicas entrenadas con datos de calidad
        strategies = [
            'orb', 'gap_go', 'macdv', 'vwap', 
            'catalyst_momentum', 'eod_momentum', 'explosive_volume'
        ]
        
        # Initialize ML Strategy Selector (should load trained model)
        ml_selector = create_ml_strategy_selector(
            strategies,
            "data/ml_models/strategy_selector.json"
        )
        
        print(f"✅ ML Strategy Selector cargado con {len(strategies)} estrategias")
        
        # Test scenarios based on your requirements
        test_scenarios = [
            # Morning Power (9:30-11:00)
            ("Morning Gap Up", TickerContext(
                symbol='TSLA',
                current_price=15.50,
                avg_volume_10=500_000,
                avg_volume_50=300_000,
                volatility_10=0.08,
                volatility_50=0.06,
                price_change_1h=0.08,  # 8% gap up
                price_change_4h=0.08,
                rsi_14=65,
                volume_ratio_current=3.5,  # High volume
                volume_spike_frequency=0.3,
                hour_of_day=9.5,  # 9:30 AM
                minutes_from_open=0,
                is_first_hour=True,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.6,
                mean_reversion_tendency=0.4
            )),
            
            # All-Day Core (12:00 PM)
            ("Midday Tech Stock", TickerContext(
                symbol='AAPL',
                current_price=8.75,
                avg_volume_10=200_000,
                avg_volume_50=150_000,
                volatility_10=0.04,
                volatility_50=0.03,
                price_change_1h=0.025,  # 2.5% move
                price_change_4h=0.04,
                rsi_14=55,
                volume_ratio_current=1.8,
                volume_spike_frequency=0.2,
                hour_of_day=12.0,  # 12:00 PM
                minutes_from_open=150,
                is_first_hour=False,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.5,
                mean_reversion_tendency=0.5
            )),
            
            # Event-Driven (Catalyst)
            ("Major Catalyst", TickerContext(
                symbol='NVDA',
                current_price=22.30,
                avg_volume_10=100_000,
                avg_volume_50=75_000,
                volatility_10=0.15,
                volatility_50=0.08,
                price_change_1h=0.12,  # 12% move
                price_change_4h=0.15,
                rsi_14=75,
                volume_ratio_current=6.0,  # Explosive volume
                volume_spike_frequency=0.4,
                hour_of_day=13.5,  # 1:30 PM
                minutes_from_open=240,
                is_first_hour=False,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.7,
                mean_reversion_tendency=0.3
            )),
            
            # End of Day (15:30)
            ("EOD Momentum", TickerContext(
                symbol='AMD',
                current_price=12.15,
                avg_volume_10=300_000,
                avg_volume_50=250_000,
                volatility_10=0.06,
                volatility_50=0.05,
                price_change_1h=0.045,  # 4.5% EOD move
                price_change_4h=0.06,
                rsi_14=62,
                volume_ratio_current=2.2,
                volume_spike_frequency=0.25,
                hour_of_day=15.5,  # 3:30 PM
                minutes_from_open=360,
                is_first_hour=False,
                is_last_hour=True,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.55,
                mean_reversion_tendency=0.45
            )),
            
            # Explosive Volume Setup
            ("Volume Explosion", TickerContext(
                symbol='MEME',
                current_price=3.85,
                avg_volume_10=50_000,
                avg_volume_50=30_000,
                volatility_10=0.20,
                volatility_50=0.12,
                price_change_1h=0.18,  # 18% move
                price_change_4h=0.25,
                rsi_14=80,
                volume_ratio_current=12.0,  # Massive volume spike
                volume_spike_frequency=0.5,
                hour_of_day=11.25,  # 11:15 AM
                minutes_from_open=105,
                is_first_hour=False,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.8,
                mean_reversion_tendency=0.2
            ))
        ]
        
        print(f"\n🧪 Testing strategy selections for different scenarios:")
        print("-" * 70)
        
        # Test each scenario multiple times to see variety
        for scenario_name, context in test_scenarios:
            print(f"\n📊 {scenario_name}:")
            print(f"   Time: {context.hour_of_day:.1f} hours ({context.minutes_from_open} min from open)")
            print(f"   Price Change: {context.price_change_1h:+.1%}")
            print(f"   Volume Ratio: {context.volume_ratio_current:.1f}x")
            
            # Make 5 selections to see the variety (Thompson Sampling)
            selections = []
            for i in range(5):
                selected = ml_selector.select_strategy(context)
                selections.append(selected)
            
            # Count frequency
            from collections import Counter
            selection_counts = Counter(selections)
            
            print(f"   Strategy Selections (5 attempts):")
            for strategy, count in selection_counts.most_common():
                percentage = (count / 5) * 100
                print(f"     {strategy:20}: {count}/5 ({percentage:.0f}%)")
        
        # Test consistency for same inputs
        print(f"\n🔄 Testing selection consistency...")
        test_context = test_scenarios[0][1]  # Use first scenario
        
        selections_batch1 = [ml_selector.select_strategy(test_context) for _ in range(10)]
        selections_batch2 = [ml_selector.select_strategy(test_context) for _ in range(10)]
        
        # Should have some variance due to Thompson Sampling
        unique_batch1 = len(set(selections_batch1))
        unique_batch2 = len(set(selections_batch2))
        
        print(f"   Batch 1 unique strategies: {unique_batch1}/10")
        print(f"   Batch 2 unique strategies: {unique_batch2}/10")
        
        if unique_batch1 > 1 and unique_batch2 > 1:
            print("✅ Good exploration - Thompson Sampling working correctly")
        else:
            print("⚠️ Limited exploration - may need more training data")
        
        # Test model statistics  
        print(f"\n📈 Model Statistics:")
        print("-" * 40)
        
        for strategy in strategies[:5]:  # Show first 5 strategies
            stats = ml_selector.strategy_stats[strategy]
            if stats.total_trades > 0:
                avg_pnl = stats.total_pnl / max(stats.total_trades, 1)
                print(f"{strategy:20} | Trades: {stats.total_trades:4d} | "
                      f"Avg PnL: {avg_pnl:+.3f} | "
                      f"Win Rate: {stats.win_rate:.1%}")
        
        print("=" * 50)
        print("🎯 ML Strategy Selector Test Complete")
        
        # Expected behavior summary
        print(f"\n💡 Expected Strategy Selection Patterns:")
        print(f"   🌅 Morning (9:30-11:00): gap_go, orb")
        print(f"   🕐 All-Day (11:00-15:00): macdv, vwap_reclaim, vwap_smallcaps") 
        print(f"   📰 Event-Driven (high vol/move): catalyst_momentum")
        print(f"   🌆 End-of-Day (15:00+): eod_momentum")
        print(f"   💥 Volume Explosion (8x+ vol): explosive_volume")
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_strategy_selection())