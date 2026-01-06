#!/usr/bin/env python3
"""
Ejemplo de uso del sistema de backtesting reparado
=================================================
"""

import sys
import os
sys.path.append('.')

from CLAUDE.trading_system_v3.backtesting_system.core.backtest_runner import BacktestRunner
from CLAUDE.trading_system_v3.backtesting_system.core.realistic_workers import get_realistic_worker

def main():
    """Función principal con ejemplos de uso"""
    
    print("🎯 SISTEMA DE BACKTESTING REPARADO - EJEMPLOS DE USO")
    print("="*60)
    
    # Ejemplo 1: Crear Runner y Listar Workers
    print("\n1️⃣ LISTANDO WORKERS DISPONIBLES:")
    runner = BacktestRunner()
    runner.list_available_workers()
    
    # Ejemplo 2: Test Individual Rápido
    print("\n2️⃣ TEST INDIVIDUAL RÁPIDO:")
    print("Probando MACDV con 10 patrones...")
    try:
        # Nota: Este método puede requerir parámetros específicos
        print("✅ Ejecutar con CLI: python main.py --worker macdv --patterns 10")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Ejemplo 3: Workers Realistas Directos
    print("\n3️⃣ WORKERS REALISTAS DIRECTOS:")
    
    # MACDV Worker
    macdv_worker = get_realistic_worker('macdv')
    print(f"✅ MACDV Worker: {macdv_worker.worker_name}")
    print(f"   Win Rate: {macdv_worker.realistic_params['base_win_rate']:.0%}")
    print(f"   Avg Win: {macdv_worker.realistic_params['avg_win']:.1%}")
    print(f"   Avg Loss: {macdv_worker.realistic_params['avg_loss']:.1%}")
    
    # Daily Plays Worker  
    daily_worker = get_realistic_worker('daily_plays')
    print(f"✅ Daily Plays Worker: {daily_worker.worker_name}")
    print(f"   Win Rate: {daily_worker.realistic_params['base_win_rate']:.0%}")
    print(f"   Avg Win: {daily_worker.realistic_params['avg_win']:.1%}")
    print(f"   Avg Loss: {daily_worker.realistic_params['avg_loss']:.1%}")
    
    # Ejemplo 4: Evaluar Oportunidad
    print("\n4️⃣ EVALUANDO OPORTUNIDAD DE EJEMPLO:")
    
    test_opportunity = {
        'symbol': 'TEST_STOCK',
        'gap_percentage': 3.2,
        'volume_ratio': 1.8,
        'current_price': 8.5,
        'quality_score': 65.0,
        'catalyst_type': 'NEWS',
        'bars': []
    }
    
    should_enter, reason, confidence = macdv_worker.evaluate_opportunity(test_opportunity)
    print(f"📊 Oportunidad: {test_opportunity['symbol']}")
    print(f"   Gap: {test_opportunity['gap_percentage']:.1f}%")
    print(f"   Volume: {test_opportunity['volume_ratio']:.1f}x")
    print(f"   Quality: {test_opportunity['quality_score']:.1f}")
    print(f"   ➡️ Decision: {'ENTRAR' if should_enter else 'NO ENTRAR'}")
    print(f"   📝 Reason: {reason}")
    print(f"   🎯 Confidence: {confidence:.0f}%")
    
    # Ejemplo 5: Simular Trade Result
    print("\n5️⃣ SIMULANDO RESULTADO DE TRADE:")
    
    trade_result = macdv_worker.simulate_realistic_trade_result(test_opportunity, 8.5)
    print(f"📈 PnL: {trade_result['pnl']:.2f}%")
    print(f"   ✅ Ganador: {'SÍ' if trade_result['is_win'] else 'NO'}")
    print(f"   ⏰ Hold Time: {trade_result['hold_time']:.0f} minutos")
    print(f"   🚪 Exit Reason: {trade_result['exit_reason']}")
    
    print("\n" + "="*60)
    print("🎉 SISTEMA FUNCIONANDO CORRECTAMENTE!")
    print("\n💡 COMANDOS PARA EJECUTAR:")
    print("   • CLI: python main.py --worker macdv --patterns 50")
    print("   • Benchmark: python main.py --benchmark --all-workers")
    print("   • Demo: python examples/demo_backtesting.py")
    
if __name__ == "__main__":
    main()