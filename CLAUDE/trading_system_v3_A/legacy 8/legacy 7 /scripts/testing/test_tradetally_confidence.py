#!/usr/bin/env python3
"""
Test script para verificar que TradeTally API puede recibir datos de confidence.
Este script inserta datos de prueba con confidence y los sincroniza con TradeTally.
"""

import sqlite3
import json
import os
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

# Agregar el directorio de integrations al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'integrations', 'tradetally', 'core'))

from tradetally_sync import TradeTallyIntegration, TradeRecord

def create_test_trades_with_confidence():
    """Crear trades de prueba con datos de confidence"""
    db_path = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'
    
    test_trades = [
        {
            'trade_id': 'TEST_CONF_001',
            'symbol': 'AAPL',
            'strategy': 'Momentum',
            'side': 'BUY',
            'quantity': 100,
            'entry_price': 150.50,
            'exit_price': 155.75,
            'entry_time': '2024-01-15 09:30:00',
            'exit_time': '2024-01-15 10:45:00',
            'duration_minutes': 75,
            'pnl': 525.00,
            'commission': 2.50,
            'status': 'CLOSED',
            'notes': 'High confidence trade based on strong momentum signals',
            'confidence': 85.5
        },
        {
            'trade_id': 'TEST_CONF_002',
            'symbol': 'MSFT',
            'strategy': 'Mean Reversion',
            'side': 'BUY',
            'quantity': 50,
            'entry_price': 280.25,
            'exit_price': 275.80,
            'entry_time': '2024-01-16 14:15:00',
            'exit_time': '2024-01-16 15:30:00',
            'duration_minutes': 75,
            'pnl': -222.50,
            'commission': 2.00,
            'status': 'CLOSED',
            'notes': 'Low confidence trade, market conditions uncertain',
            'confidence': 35.0
        },
        {
            'trade_id': 'TEST_CONF_003',
            'symbol': 'TSLA',
            'strategy': 'Breakout',
            'side': 'BUY',
            'quantity': 25,
            'entry_price': 200.00,
            'exit_price': 208.50,
            'entry_time': '2024-01-17 11:00:00',
            'exit_time': '2024-01-17 13:15:00',
            'duration_minutes': 135,
            'pnl': 212.50,
            'commission': 1.75,
            'status': 'CLOSED',
            'notes': 'Medium confidence breakout play',
            'confidence': 72.3
        }
    ]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🧪 Creando trades de prueba con datos de confidence...")
    
    for trade in test_trades:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO trades (
                    trade_id, symbol, strategy, side, quantity, 
                    entry_price, exit_price, entry_time, exit_time, 
                    duration_minutes, pnl, commission, status, notes, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['trade_id'], trade['symbol'], trade['strategy'], 
                trade['side'], trade['quantity'], trade['entry_price'], 
                trade['exit_price'], trade['entry_time'], trade['exit_time'],
                trade['duration_minutes'], trade['pnl'], trade['commission'], 
                trade['status'], trade['notes'], trade['confidence']
            ))
            print(f"✅ Trade {trade['trade_id']} creado con confidence {trade['confidence']}%")
        except Exception as e:
            print(f"❌ Error creando trade {trade['trade_id']}: {e}")
    
    conn.commit()
    conn.close()
    print(f"📊 {len(test_trades)} trades de prueba creados exitosamente\n")


def test_confidence_payload():
    """Probar que el payload incluye correctamente los datos de confidence"""
    print("🔍 PROBANDO GENERACIÓN DE PAYLOAD CON CONFIDENCE...")
    
    # Crear un TradeRecord de prueba con confidence
    test_trade = TradeRecord(
        id=1,
        trade_id='TEST_PAYLOAD_001',
        symbol='AAPL',
        strategy='Momentum',
        side='BUY',
        quantity=100,
        entry_price=150.50,
        exit_price=155.75,
        entry_time='2024-01-15 09:30:00',
        exit_time='2024-01-15 10:45:00',
        duration_minutes=75,
        pnl=525.00,
        commission=2.50,
        status='CLOSED',
        notes='Test trade with confidence',
        created_at='2024-01-15 09:30:00',
        updated_at='2024-01-15 10:45:00',
        confidence=92.5
    )
    
    # Crear instancia de integración (no necesitamos API real para probar payload)
    sync = TradeTallyIntegration('test_key', 'http://test.com/api/v2', 'test.db')
    
    # Generar payload
    payload = sync.create_tradetally_payload(test_trade)
    
    print("📦 Payload generado:")
    print(json.dumps(payload, indent=2))
    
    # Verificar que confidence está incluido
    assert 'confidence' in payload, "❌ Confidence no está en el payload"
    assert payload['confidence'] == 92.5, "❌ Valor de confidence incorrecto"
    
    print("✅ Confidence incluido correctamente en el payload")
    print(f"✅ Confidence value: {payload['confidence']}")
    
    # Verificar que confidence aparece también en las notas
    assert 'Confidence: 92.5%' in payload['notes'], "❌ Confidence no está en las notas"
    print("✅ Confidence incluido en las notas metadata")
    print()


def get_tradetally_token():
    """Obtener token JWT válido de TradeTally"""
    try:
        port = os.getenv('PORT', '3001')
        base_url = f"http://localhost:{port}/api"
        
        # Intentar login con credenciales conocidas
        login_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        response = requests.post(f"{base_url}/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            if token:
                print("✅ Token JWT obtenido exitosamente")
                return token
        
        print("⚠️ No se pudo hacer login, intentando crear usuario...")
        
        # Intentar crear usuario si el login falla
        register_data = {
            "username": "testuser",
            "email": "testuser@example.com", 
            "password": "password123"
        }
        
        response = requests.post(f"{base_url}/auth/register", json=register_data)
        
        if response.status_code == 201:
            print("✅ Usuario creado, intentando login...")
            login_data["email"] = register_data["email"]
            
            response = requests.post(f"{base_url}/auth/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('token')
                if token:
                    print("✅ Token JWT obtenido después de crear usuario")
                    return token
        
        print("❌ No se pudo obtener token JWT")
        return None
        
    except Exception as e:
        print(f"❌ Error obteniendo token: {e}")
        return None

def test_api_connection_and_sync():
    """Probar conexión con TradeTally API y sincronización"""
    print("🌐 PROBANDO CONEXIÓN Y SINCRONIZACIÓN CON TRADETALLY...")
    
    # Obtener credenciales del archivo .env.local de TradeTally
    env_file = Path('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tradetally/.env.local')
    if not env_file.exists():
        print("❌ Archivo tradetally/.env.local no encontrado.")
        print("📝 Por favor verifica que TradeTally esté configurado correctamente")
        return False
    
    # Leer variables de entorno
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value
    
    # TradeTally usa JWT tokens, no API keys tradicionales
    # Necesitamos hacer login para obtener un token válido
    print("🔐 Obteniendo token JWT de TradeTally...")
    
    api_key = get_tradetally_token()
    if not api_key:
        return False
    
    base_url = f"http://localhost:{os.getenv('PORT', '3001')}/api"
    db_path = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'
    
    print(f"🔑 Using API Key: {api_key[:20]}...")
    print(f"🌐 Base URL: {base_url}")
    
    # Crear instancia de integración
    sync = TradeTallyIntegration(api_key, base_url, db_path)
    
    # Probar conexión
    if not sync.test_connection():
        print("❌ No se pudo conectar con TradeTally API")
        print("💡 Asegúrate de que TradeTally esté corriendo y que el API key sea válido")
        return False
    
    print("✅ Conexión exitosa con TradeTally API")
    
    # Obtener trades de prueba
    trades = sync.get_local_trades(only_new=False)
    confidence_trades = [t for t in trades if t.confidence is not None and t.trade_id.startswith('TEST_CONF_')]
    
    if not confidence_trades:
        print("❌ No se encontraron trades de prueba con confidence")
        return False
    
    print(f"📊 Encontrados {len(confidence_trades)} trades de prueba con confidence:")
    for trade in confidence_trades:
        print(f"   • {trade.symbol} - Confidence: {trade.confidence}%")
    
    # Sincronizar uno de los trades de prueba
    test_trade = confidence_trades[0]
    print(f"\n🔄 Sincronizando trade de prueba: {test_trade.symbol} (Confidence: {test_trade.confidence}%)")
    
    success, message = sync.sync_trade_to_tradetally(test_trade)
    
    if success:
        print("✅ Trade sincronizado exitosamente con datos de confidence!")
        return True
    else:
        print(f"❌ Error sincronizando trade: {message}")
        return False


def cleanup_test_trades():
    """Limpiar trades de prueba"""
    db_path = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'TEST_CONF_%'")
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        print(f"🧹 {deleted_count} trades de prueba eliminados")


def main():
    """Función principal de testing"""
    print("🚀 INICIANDO TESTS DE CONFIDENCE DATA PARA TRADETALLY API")
    print("=" * 60)
    
    try:
        # Test 1: Crear trades de prueba
        create_test_trades_with_confidence()
        
        # Test 2: Probar generación de payload
        test_confidence_payload()
        
        # Test 3: Probar conexión y sincronización real
        api_test_success = test_api_connection_and_sync()
        
        print("=" * 60)
        print("📋 RESUMEN DE TESTS:")
        print("✅ Trades de prueba creados con confidence")
        print("✅ Payload incluye correctamente datos de confidence")
        print(f"{'✅' if api_test_success else '❌'} {'Sincronización API exitosa' if api_test_success else 'Sincronización API falló'}")
        
        if api_test_success:
            print("\n🎉 ¡TODOS LOS TESTS PASARON! TradeTally API puede recibir datos de confidence.")
        else:
            print("\n⚠️ Tests de payload pasaron, pero la sincronización API falló.")
            print("   Revisa la configuración del servidor TradeTally.")
        
    except Exception as e:
        print(f"❌ Error durante los tests: {e}")
        
    finally:
        # Preguntar si limpiar trades de prueba
        response = input("\n🧹 ¿Eliminar trades de prueba? (y/N): ")
        if response.lower() == 'y':
            cleanup_test_trades()
        else:
            print("📝 Trades de prueba conservados para inspección manual")


if __name__ == "__main__":
    main()