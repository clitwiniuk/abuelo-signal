#!/usr/bin/env python3
"""
Test Rápido de Integración
==========================

Verifica rápidamente que los componentes principales funcionan.
"""

import sys
import os
from datetime import date
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_quick_integration():
    """Test rápido de integración del sistema"""
    
    print("⚡ TEST RÁPIDO DE INTEGRACIÓN")
    print("=" * 40)
    
    try:
        # 1. Import components
        print("1️⃣ Importando componentes...")
        from core.database_manager import get_database_manager
        from scanner.scanner_intelligence import ScannerIntelligence, TradingResult, AutoCategorizer
        print("   ✅ Imports correctos")
        
        # 2. Initialize system
        print("\n2️⃣ Inicializando sistema...")
        db_manager = get_database_manager()
        scanner_ai = ScannerIntelligence(database_manager=db_manager)
        categorizer = AutoCategorizer()
        print("   ✅ Sistema inicializado")
        
        # 3. Test auto-categorization
        print("\n3️⃣ Probando auto-categorización...")
        result = categorizer.categorize_trade_automatically(
            ticker='TEST',
            entry_price=100.0,
            exit_price=105.0,
            trade_date=date.today(),
            hold_duration_minutes=60,
            strategy_used='test_strategy',
            pnl=500.0
        )
        print(f"   ✅ Categorizado como: {result.trade_category}")
        print(f"   ✅ Calidad: {result.execution_quality}")
        
        # 4. Test database integration
        print("\n4️⃣ Probando integración BD...")
        test_trade = TradingResult(
            ticker='QUICKTEST',
            trade_date=date.today(),
            entry_price=50.0,
            exit_price=52.5,
            pnl=250.0,
            was_profitable=True,
            hold_duration_minutes=30,
            strategy_used='quick_test',
            notes='Test rápido'
        )
        
        scanner_ai.add_trading_result(test_trade, trade_id='QUICK_TEST_001')
        print("   ✅ Trade agregado a BD principal")
        
        # 5. Test retrieval
        print("\n5️⃣ Probando recuperación de datos...")
        results = scanner_ai.get_advanced_trading_results(limit=5)
        print(f"   ✅ Recuperados {len(results)} resultados avanzados")
        
        # 6. Test stats
        print("\n6️⃣ Probando estadísticas...")
        stats = db_manager.get_today_stats()
        print(f"   ✅ Stats: {stats['total_trades']} trades, PnL: ${stats['total_pnl']:.2f}")
        
        # 7. Test learning stats (required for Streamlit)
        print("\n7️⃣ Probando get_learning_stats (Streamlit)...")
        learning_stats = scanner_ai.get_learning_stats()
        print(f"   ✅ Learning stats: {learning_stats['total_trades']} trades totales")
        print(f"   ✅ Win rate: {learning_stats['win_rate']:.1f}%")
        print(f"   ✅ Auto-categorization rate: {learning_stats['auto_categorization_rate']:.1f}%")
        
        print("\n🎉 TODOS LOS TESTS RÁPIDOS PASARON")
        print("✅ Sistema completamente integrado y funcionando")
        print("✅ Compatible con Streamlit interface")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN TEST: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_quick_integration()
    sys.exit(0 if success else 1)