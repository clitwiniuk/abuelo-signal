#!/usr/bin/env python3
"""
Test script for strategy optimizer fix
"""

import asyncio
from strategy_optimizer import StrategyOptimizer

async def test_optimizer():
    print("🔧 TESTING OPTIMIZER FIX")
    print("=" * 50)
    
    optimizer = StrategyOptimizer()
    
    if not await optimizer.initialize():
        print("❌ No se pudo inicializar el optimizador")
        return
    
    # Test comparación con estrategia que no genera señales
    print("\n📊 Testing VolumeMomentumStrategy (caso problemático)...")
    
    try:
        comparison = await optimizer.compare_strategy_performance('VolumeMomentumStrategy', max_events=15)
        optimizer.print_comparison_report(comparison)
        print("✅ Test exitoso - error corregido")
        
    except Exception as e:
        print(f"❌ Error persiste: {e}")

if __name__ == "__main__":
    asyncio.run(test_optimizer())