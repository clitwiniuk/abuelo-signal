#!/usr/bin/env python3
"""
Test ML Volume Engine - Verificar que los modelos entrenados funcionan correctamente
"""

import asyncio
import logging
from core.ml_volume_engine import MLVolumeEngine, MarketContext
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_volume_predictions():
    """Test que los modelos entrenados hacen predicciones correctas"""
    
    print("🔍 TESTING TRAINED ML VOLUME MODELS")
    print("=" * 50)
    
    try:
        # Initialize MLVolumeEngine
        ml_engine = MLVolumeEngine()
        
        # Load trained models
        if not ml_engine.load_models():
            print("❌ No se pudieron cargar los modelos")
            return
        
        print(f"✅ Modelos cargados para {len(ml_engine.models)} estrategias")
        
        # Create test market contexts
        test_contexts = [
            ("Low Volume Market", MarketContext(
                time_of_day=0.4,  # 9:36 AM
                day_of_week=1,    # Tuesday
                market_cap=50_000_000,
                avg_volume=100_000,
                float_shares=10_000_000,
                sector="Technology",
                recent_performance=2.5,
                market_stress=0.2,
                volume_trend=0.8,
                price_level=5.50
            )),
            ("High Volume Market", MarketContext(
                time_of_day=0.5,  # 12:00 PM
                day_of_week=2,    # Wednesday
                market_cap=100_000_000,
                avg_volume=500_000,
                float_shares=20_000_000,
                sector="Healthcare",
                recent_performance=8.0,
                market_stress=0.7,
                volume_trend=3.5,
                price_level=12.30
            )),
            ("Explosive Setup", MarketContext(
                time_of_day=0.35, # 9:26 AM (pre-market end)
                day_of_week=3,    # Thursday
                market_cap=25_000_000,
                avg_volume=75_000,
                float_shares=5_000_000,
                sector="Biotechnology",
                recent_performance=15.2,
                market_stress=0.9,
                volume_trend=8.0,
                price_level=3.75
            ))
        ]
        
        print(f"\n🧪 Testing volume predictions for different market contexts:")
        print("-" * 70)
        
        for context_name, context in test_contexts:
            print(f"\n📊 {context_name}:")
            print(f"   Market Cap: ${context.market_cap:,}")
            print(f"   Avg Volume: {context.avg_volume:,}")
            print(f"   Performance: {context.recent_performance:+.1f}%")
            print(f"   Volume Trend: {context.volume_trend:.1f}x")
            
            print(f"\n   Strategy Volume Requirements:")
            
            for strategy in ml_engine.strategies:
                if strategy in ml_engine.models:
                    try:
                        volume_req = ml_engine.predict_volume_requirement(strategy, context)
                        print(f"     {strategy:20}: {volume_req:.2f}x")
                    except Exception as e:
                        print(f"     {strategy:20}: ERROR - {e}")
                else:
                    print(f"     {strategy:20}: No model loaded")
        
        # Test prediction consistency
        print(f"\n🔄 Testing prediction consistency...")
        
        consistent_predictions = True
        for strategy in ml_engine.strategies[:3]:  # Test first 3 strategies
            if strategy in ml_engine.models:
                pred1 = ml_engine.predict_volume_requirement(strategy, test_contexts[0][1])
                pred2 = ml_engine.predict_volume_requirement(strategy, test_contexts[0][1])
                
                if abs(pred1 - pred2) > 0.001:
                    print(f"❌ Inconsistent predictions for {strategy}: {pred1} vs {pred2}")
                    consistent_predictions = False
        
        if consistent_predictions:
            print("✅ All predictions are consistent")
        
        # Test model performance info
        print(f"\n📈 Model Performance Summary:")
        for strategy in ml_engine.strategies:
            if strategy in ml_engine.models:
                print(f"   {strategy:20}: Loaded ✅")
            else:
                print(f"   {strategy:20}: Missing ❌")
        
        print("=" * 50)
        print("🎯 ML Volume Engine Test Complete")
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_volume_predictions())