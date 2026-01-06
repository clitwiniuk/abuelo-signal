#!/usr/bin/env python3
"""
Herramienta de debug para TradeTally Integration
Diagnostica problemas de sincronización y verifica datos
"""

import sys
import json
import requests
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.append(str(Path(__file__).parent.parent))

from integrations.tradetally_sync import TradeTallyIntegration
from config.tradetally_config import config

def test_api_endpoints():
    """Probar diferentes endpoints de TradeTally"""
    print("🔍 DIAGNÓSTICO DE API ENDPOINTS")
    print("=" * 50)
    
    if not config.is_configured():
        print("❌ API Key no configurada")
        return False
    
    headers = {
        'Authorization': f'Bearer {config.api_key}',
        'Content-Type': 'application/json'
    }
    
    # Test endpoints
    endpoints = [
        ('/trades', 'GET', 'Obtener trades'),
        ('/trades?limit=5', 'GET', 'Obtener 5 trades'),
        ('/analytics/overview', 'GET', 'Estadísticas generales')
    ]
    
    for endpoint, method, description in endpoints:
        try:
            url = f"{config.base_url}{endpoint}"
            print(f"\n🌐 Probando: {description}")
            print(f"   URL: {url}")
            
            response = requests.get(url, headers=headers, timeout=30)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if endpoint.startswith('/trades'):
                    trades = data.get('trades', [])
                    print(f"   ✅ Trades encontrados: {len(trades)}")
                    
                    # Mostrar algunos trades
                    for i, trade in enumerate(trades[:3]):
                        symbol = trade.get('symbol', 'N/A')
                        side = trade.get('side', 'N/A')
                        pnl = trade.get('pnl', 0)
                        created = trade.get('createdAt', 'N/A')
                        print(f"     {i+1}. {symbol} {side} PnL:${pnl} Created:{created}")
                
                elif endpoint.startswith('/analytics'):
                    total_trades = data.get('totalTrades', 0)
                    total_pnl = data.get('totalPnl', 0)
                    print(f"   ✅ Total trades: {total_trades}, PnL: ${total_pnl}")
            
            elif response.status_code == 401:
                print(f"   ❌ Error de autenticación - verificar API key")
                return False
            
            elif response.status_code == 403:
                print(f"   ❌ Sin permisos - verificar permisos del API key")
                return False
            
            else:
                print(f"   ⚠️ Error {response.status_code}: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Error de conexión: {e}")
    
    return True

def check_sync_state():
    """Verificar el estado de sincronización local"""
    print("\n📊 ESTADO DE SINCRONIZACIÓN LOCAL")
    print("=" * 50)
    
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        status = sync.get_sync_status()
        
        print(f"📅 Última sincronización: {status['last_sync']}")
        print(f"📈 Total sincronizados: {status['total_synced']}")
        print(f"❌ Fallos de sync: {status['failed_syncs']}")
        
        # Mostrar IDs sincronizados
        if status['total_synced'] > 0:
            print(f"\n🔗 Trade IDs sincronizados:")
            sync_state = sync.sync_state
            for i, trade_id in enumerate(sync_state['synced_trade_ids'][:10]):
                print(f"   {i+1}. {trade_id}")
            
            if len(sync_state['synced_trade_ids']) > 10:
                print(f"   ... y {len(sync_state['synced_trade_ids']) - 10} más")
        
        # Mostrar errores si los hay
        if status['failed_syncs'] > 0:
            print(f"\n❌ Errores de sincronización:")
            for error in sync.sync_state['failed_syncs']:
                print(f"   • {error['trade_id']}: {error['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo estado: {e}")
        return False

def verify_trade_format():
    """Verificar el formato de un trade antes de enviar"""
    print("\n🔍 VERIFICACIÓN DE FORMATO DE TRADES")
    print("=" * 50)
    
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        trades = sync.get_local_trades(only_new=False)  # Obtener todos
        
        if not trades:
            print("❌ No hay trades en la base de datos local")
            return False
        
        # Tomar el primer trade como ejemplo
        trade = trades[0]
        payload = sync.create_tradetally_payload(trade)
        
        print(f"📋 Ejemplo de payload enviado a TradeTally:")
        print(json.dumps(payload, indent=2))
        
        # Verificar campos requeridos
        required_fields = ['symbol', 'side', 'entryTime', 'entryPrice', 'quantity']
        missing_fields = [field for field in required_fields if field not in payload]
        
        if missing_fields:
            print(f"\n❌ Campos faltantes: {missing_fields}")
        else:
            print(f"\n✅ Todos los campos requeridos están presentes")
        
        # Verificar formatos
        print(f"\n🔍 Verificación de formatos:")
        print(f"   Symbol: {payload.get('symbol')} (tipo: {type(payload.get('symbol'))})")
        print(f"   Side: {payload.get('side')} (debe ser 'long' o 'short')")
        print(f"   EntryTime: {payload.get('entryTime')}")
        print(f"   EntryPrice: {payload.get('entryPrice')} (tipo: {type(payload.get('entryPrice'))})")
        print(f"   Quantity: {payload.get('quantity')} (tipo: {type(payload.get('quantity'))})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando formato: {e}")
        return False

def test_manual_trade_creation():
    """Probar creación manual de un trade simple"""
    print("\n🧪 PRUEBA DE CREACIÓN MANUAL")
    print("=" * 50)
    
    if not config.is_configured():
        print("❌ API Key no configurada")
        return False
    
    # Trade de prueba muy simple
    test_trade = {
        'symbol': 'TEST',
        'side': 'long',
        'entryTime': '2024-08-15T14:30:00.000Z',
        'entryPrice': 100.0,
        'quantity': 100,
        'exitTime': '2024-08-15T15:30:00.000Z',
        'exitPrice': 105.0,
        'commission': 1.0,
        'strategy': 'Manual Test',
        'broker': 'Test Broker',
        'notes': 'Trade de prueba manual para debugging'
    }
    
    headers = {
        'Authorization': f'Bearer {config.api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        print(f"📤 Enviando trade de prueba:")
        print(json.dumps(test_trade, indent=2))
        
        response = requests.post(
            f"{config.base_url}/trades",
            headers=headers,
            json=test_trade,
            timeout=30
        )
        
        print(f"\n📥 Respuesta del servidor:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.text:
            try:
                response_data = response.json()
                print(f"   Response JSON:")
                print(json.dumps(response_data, indent=4))
            except:
                print(f"   Response Text: {response.text}")
        
        if response.status_code in [200, 201]:
            print(f"\n✅ Trade creado exitosamente!")
            return True
        else:
            print(f"\n❌ Error creando trade")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba manual: {e}")
        return False

def check_tradetally_filters():
    """Verificar si hay filtros en TradeTally que oculten los trades"""
    print("\n🔍 VERIFICACIÓN DE FILTROS EN TRADETALLY")
    print("=" * 50)
    
    print("""
🤔 Posibles razones por las que no ves los trades en TradeTally:

1. 📅 FILTROS DE FECHA:
   • ¿Estás viendo el rango de fechas correcto?
   • Los trades de prueba van desde hace 30 días hasta hoy
   • Verifica que no tengas filtros de fecha activos

2. 📊 FILTROS DE SÍMBOLO:
   • ¿Hay filtros por símbolo activos?
   • Los trades incluyen: AAPL, MSFT, GOOGL, AMZN, etc.

3. 🏷️ FILTROS DE ESTRATEGIA/BROKER:
   • ¿Hay filtros por estrategia o broker?
   • Broker: "IBKR"
   • Estrategias: "Gap Go Strategy", "Volume Explosion", etc.

4. 👀 VISTA/PÁGINA INCORRECTA:
   • ¿Estás en la sección de trades/journal correcta?
   • ¿Has refrescado la página?

5. 🔄 SINCRONIZACIÓN RETRASADA:
   • Algunos sistemas pueden tener delay
   • Intenta esperar unos minutos y refrescar

6. 🏢 CUENTA/WORKSPACE:
   • ¿Estás en la cuenta/workspace correcta?
   • ¿El API key corresponde a la cuenta que estás viendo?
""")

def main():
    """Función principal de debug"""
    print("""
🔧 HERRAMIENTA DE DEBUG TRADETALLY
=================================
Esta herramienta te ayudará a diagnosticar por qué no ves
los trades en TradeTally después de una sincronización exitosa.
""")
    
    # 1. Verificar configuración
    print(f"🔑 API Key configurada: {'✅' if config.is_configured() else '❌'}")
    print(f"🌐 Base URL: {config.base_url}")
    print(f"💾 Base de datos: {config.db_path}")
    
    if not config.is_configured():
        print("\n❌ Configura tu API Key primero con: python tradetally_cli.py setup")
        return
    
    # 2. Test endpoints
    if not test_api_endpoints():
        print("\n❌ Problema con la API. Revisar configuración.")
        return
    
    # 3. Verificar estado local
    check_sync_state()
    
    # 4. Verificar formato de trades
    verify_trade_format()
    
    # 5. Prueba manual
    print(f"\n❓ ¿Quieres crear un trade de prueba manual para verificar? (y/n): ", end="")
    if input().lower().startswith('y'):
        test_manual_trade_creation()
    
    # 6. Mostrar posibles causas
    check_tradetally_filters()
    
    print(f"""
🎯 SIGUIENTES PASOS RECOMENDADOS:
1. Verificar filtros de fecha en TradeTally (últimos 30 días)
2. Buscar el símbolo "TEST" o "AAPL" en TradeTally
3. Verificar que estás en la cuenta/workspace correcta
4. Contactar soporte de TradeTally si el problema persiste

📧 Si necesitas más ayuda, guarda este output y compártelo.
""")

if __name__ == "__main__":
    main()