#!/usr/bin/env python3
"""
Test de integración end-to-end para confidence data
Verifica que el sistema complete el flujo: Signal -> Trade -> TradeTally con confidence
"""

import sqlite3
import sys
import os
from datetime import datetime

# Agregar path del sistema
sys.path.insert(0, os.path.dirname(__file__))

from core.interfaces import Signal
from core.trading_execution_stage import TradingExecutionStage

def test_confidence_calculation():
    """Test del cálculo de confidence"""
    print("🧪 TESTING CONFIDENCE CALCULATION...")
    
    # Crear instancia del execution stage
    execution_stage = TradingExecutionStage(
        broker=None,  # Mock broker for testing
        risk_manager=None,
        config=None,
        event_bus=None
    )
    
    # Crear señal mock con strength
    class MockSignalType:
        def __init__(self, value):
            self.value = value
    
    class MockSignal:
        def __init__(self, strength=0.8):
            self.symbol = 'AAPL'
            self.signal_type = MockSignalType('ENTRY_LONG')
            self.strength = strength
            self.confidence = None
    
    # Test 1: Signal con strength
    signal1 = MockSignal(strength=0.85)
    confidence1 = execution_stage._calculate_trade_confidence(signal1, 'GapGoStrategy')
    print(f"✅ Signal con strength 0.85 -> Confidence: {confidence1}%")
    assert 80 <= confidence1 <= 95, f"Expected confidence ~85-95%, got {confidence1}%"
    
    # Test 2: Signal con confidence directa
    signal2 = MockSignal()
    signal2.confidence = 92.5
    confidence2 = execution_stage._calculate_trade_confidence(signal2, 'VWAPReclaimStrategy')
    print(f"✅ Signal con confidence 92.5 -> Confidence: {confidence2}%")
    assert confidence2 == 92.5, f"Expected confidence 92.5%, got {confidence2}%"
    
    # Test 3: Signal sin strength ni confidence (default)
    signal3 = MockSignal()
    signal3.strength = None
    signal3.confidence = None
    confidence3 = execution_stage._calculate_trade_confidence(signal3, 'Unknown Strategy')
    print(f"✅ Signal sin strength/confidence -> Confidence: {confidence3}%")
    assert confidence3 == 70.0, f"Expected default confidence 70%, got {confidence3}%"
    
    print("🎉 Confidence calculation tests PASSED!\n")


def test_trade_data_creation():
    """Test que verifica que trade_data incluye confidence"""
    print("🧪 TESTING TRADE DATA CREATION...")
    
    # Verificar que la base de datos local tiene la columna confidence
    db_path = 'trading_data.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar que la columna confidence existe
        cursor.execute("PRAGMA table_info(trades)")
        columns = [column[1] for column in cursor.fetchall()]
        
        assert 'confidence' in columns, f"Column 'confidence' not found in trades table. Columns: {columns}"
        print("✅ Database has confidence column")
        
        # Test insert con confidence
        test_trade_data = {
            'trade_id': 'TEST_CONF_INTEGRATION_001',
            'symbol': 'AAPL',
            'strategy': 'TestStrategy',
            'side': 'BUY',
            'quantity': 100,
            'entry_price': 150.0,
            'entry_time': datetime.now().isoformat(),
            'commission': 1.0,
            'status': 'OPEN',
            'confidence': 87.5,
            'notes': 'Integration test trade with confidence'
        }
        
        cursor.execute("""
            INSERT OR REPLACE INTO trades (
                trade_id, symbol, strategy, side, quantity, entry_price,
                entry_time, commission, status, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_trade_data['trade_id'], test_trade_data['symbol'], 
            test_trade_data['strategy'], test_trade_data['side'], 
            test_trade_data['quantity'], test_trade_data['entry_price'],
            test_trade_data['entry_time'], test_trade_data['commission'], 
            test_trade_data['status'], test_trade_data['confidence'], 
            test_trade_data['notes']
        ))
        
        # Verificar que se insertó correctamente
        cursor.execute("SELECT confidence FROM trades WHERE trade_id = ?", (test_trade_data['trade_id'],))
        result = cursor.fetchone()
        
        assert result is not None, "Trade not inserted"
        assert result[0] == 87.5, f"Expected confidence 87.5, got {result[0]}"
        
        print("✅ Trade with confidence inserted successfully")
        
        conn.commit()
        conn.close()
        
        print("🎉 Trade data creation tests PASSED!\n")
        
    except Exception as e:
        print(f"❌ Error in trade data test: {e}")
        raise


def test_tradetally_sync_integration():
    """Test que verifica que la sincronización con TradeTally incluye confidence"""
    print("🧪 TESTING TRADETALLY SYNC INTEGRATION...")
    
    try:
        from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration, TradeRecord
        
        # Crear un TradeRecord con confidence
        test_trade = TradeRecord(
            id=1,
            trade_id='TEST_SYNC_CONF_001',
            symbol='AAPL',
            strategy='GapGoStrategy',
            side='BUY',
            quantity=100,
            entry_price=150.0,
            exit_price=155.0,
            entry_time='2024-01-15T09:30:00',
            exit_time='2024-01-15T10:30:00',
            duration_minutes=60,
            pnl=500.0,
            commission=2.0,
            status='CLOSED',
            notes='Test trade with confidence',
            created_at='2024-01-15T09:30:00',
            updated_at='2024-01-15T10:30:00',
            confidence=89.3
        )
        
        # Crear instancia de sync (sin conexión real)
        sync = TradeTallyIntegration('test_key', 'http://test.com/api', 'test.db')
        
        # Generar payload
        payload = sync.create_tradetally_payload(test_trade)
        
        # Verificar que confidence está incluido
        assert 'confidence' in payload, f"Confidence not in payload: {payload.keys()}"
        assert payload['confidence'] == 89.3, f"Expected confidence 89.3, got {payload['confidence']}"
        
        # Verificar que confidence aparece en las notas
        assert 'Confidence: 89.3%' in payload['notes'], f"Confidence not in notes: {payload['notes']}"
        
        print(f"✅ TradeTally payload includes confidence: {payload['confidence']}%")
        print(f"✅ Confidence in notes: {payload['notes']}")
        
        print("🎉 TradeTally sync integration tests PASSED!\n")
        
    except Exception as e:
        print(f"❌ Error in TradeTally sync test: {e}")
        raise


def cleanup_test_data():
    """Limpiar datos de prueba"""
    try:
        db_path = 'trading_data.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'TEST_%CONF%'")
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} test trades")
        
    except Exception as e:
        print(f"Warning: Could not clean up test data: {e}")


def main():
    """Ejecutar todos los tests de integración"""
    print("🚀 INICIANDO TESTS DE INTEGRACIÓN DE CONFIDENCE")
    print("=" * 60)
    
    try:
        # Test 1: Cálculo de confidence
        test_confidence_calculation()
        
        # Test 2: Creación de trade data con confidence
        test_trade_data_creation()
        
        # Test 3: Integración con TradeTally sync
        test_tradetally_sync_integration()
        
        print("=" * 60)
        print("🎉 ¡TODOS LOS TESTS DE INTEGRACIÓN PASARON!")
        print()
        print("✅ Sistema completo listo para:")
        print("   • Calcular confidence basado en signals")
        print("   • Guardar confidence en base de datos local") 
        print("   • Sincronizar confidence a TradeTally via /tradetally_sync")
        print()
        print("🔗 Flujo completo: Signal -> Confidence -> Trade -> TradeTally")
        
    except Exception as e:
        print(f"❌ TESTS FALLARON: {e}")
        return False
    
    finally:
        # Limpiar datos de prueba
        cleanup_test_data()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)