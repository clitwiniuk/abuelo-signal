#!/usr/bin/env python3
"""
Diagnóstico del Service Locator Pattern - ¿Por qué falla la conexión IBKR?
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

try:
    from core.service_manager import service_manager
    from core.trading_service import get_trading_service
    from engine.trading_engine import TradingEngine
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Probablemente el Service Manager no está disponible en el entorno actual.")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def diagnose_service_pattern():
    """Diagnosticar problemas con el Service Locator Pattern"""
    
    print("🔍 DIAGNÓSTICO: Service Locator Pattern Issues")
    print("="*60)
    
    try:
        print("\n🎯 Paso 1: Verificar múltiples accesos al Service Manager")
        
        # Simular comportamiento de Streamlit (múltiples llamadas)
        services = []
        for i in range(5):
            service = get_trading_service("streamlit_test")
            services.append(service)
            print(f"Service {i+1} session: {service.session_id[:8]}...")
        
        # ¿Son todas la misma instancia?
        all_same = all(s.session_id == services[0].session_id for s in services)
        print(f"¿Todas las instancias de servicio son iguales? {all_same}")
        
        print("\n📊 Paso 2: Verificar Service Manager state")
        all_services = service_manager.list_services()
        print(f"Total services registrados: {len(all_services)}")
        for key, info in all_services.items():
            print(f"  - {key}: state={info.state.value}, accesses={info.access_count}")
        
        print("\n🔍 Paso 3: Verificar engines y brokers")
        from core.interfaces import TradingConfig
        config = TradingConfig(
            broker_host="127.0.0.1",
            broker_port=7497,
            broker_client_id=170
        )
        
        # Intentar obtener engines múltiples veces
        engines = []
        for i in range(3):
            engine = services[i].get_engine(config)
            engines.append(engine)
            print(f"Engine {i+1}: {id(engine)} - Broker: {id(engine.broker) if hasattr(engine, 'broker') else 'No broker'}")
        
        # ¿Son el mismo engine?
        engines_same = all(id(e) == id(engines[0]) for e in engines)
        print(f"¿Todos los engines son el mismo objeto? {engines_same}")
        
        # ¿Tienen el mismo broker?
        if all(hasattr(e, 'broker') for e in engines):
            brokers_same = all(id(e.broker) == id(engines[0].broker) for e in engines)
            print(f"¿Todos los brokers son el mismo objeto? {brokers_same}")
        
        print("\n⚠️ Paso 4: Verificar problemas de client_id")
        for i, engine in enumerate(engines[:2]):  # Solo 2 para evitar conflictos
            if hasattr(engine, 'broker') and hasattr(engine.broker, 'client_id'):
                print(f"Engine {i+1} broker client_id: {engine.broker.client_id}")
        
        print("\n🧹 Paso 5: Cleanup test")
        for service in services:
            service.cleanup()
        
        final_services = service_manager.list_services()
        print(f"Services después de cleanup: {len(final_services)}")
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_service_pattern())