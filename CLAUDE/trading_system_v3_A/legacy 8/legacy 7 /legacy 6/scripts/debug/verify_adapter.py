#!/usr/bin/env python3
"""
Verificar que el sistema esté usando el nuevo thread-safe adapter
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TradingSystemManager
from core.interfaces import TradingConfig
from adapters.thread_safe_ibkr_adapter import ThreadSafeIBKRAdapter

def verify_adapter():
    """Verificar que se esté usando el adapter correcto"""
    
    print("🔍 Verificando adapter...")
    
    # Crear configuración de prueba
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        broker_host="127.0.0.1",
        broker_port=7497,
        broker_client_id=9998,
        strategy_name="macdv",
        timeframe="1 min",
        log_level="INFO",
        log_file="test_adapter.log"
    )
    
    # Crear sistema
    system = TradingSystemManager(config, in_streamlit=False)
    
    # Inicializar
    import asyncio
    
    async def test():
        try:
            await system.initialize()
            
            # Verificar que el data_provider es el correcto
            print(f"Data provider type: {type(system.data_provider)}")
            print(f"Broker type: {type(system.broker)}")
            
            if isinstance(system.data_provider, ThreadSafeIBKRAdapter):
                print("✅ Sistema está usando ThreadSafeIBKRAdapter")
                return True
            else:
                print("❌ Sistema NO está usando ThreadSafeIBKRAdapter")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    return asyncio.run(test())

if __name__ == "__main__":
    success = verify_adapter()
    sys.exit(0 if success else 1)