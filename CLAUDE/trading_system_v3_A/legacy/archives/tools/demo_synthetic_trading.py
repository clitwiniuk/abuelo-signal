#!/usr/bin/env python3
"""
Demo Synthetic Trading

Script para demostrar el trading system funcionando con datos sintéticos
en modo TESTING (usando MockAdapter + CSVDataProvider).
"""

import sys
import os
import asyncio
import configparser
from pathlib import Path

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import TradingConfig
from main import TradingSystemManager

async def demo_synthetic_trading():
    """Demo del sistema de trading con datos sintéticos"""
    
    print("🎯 DEMO: TRADING SYSTEM CON DATOS SINTÉTICOS")
    print("=" * 60)
    print("Ejecutando sistema de trading con eventos sintéticos reales")
    print("Modo: TESTING (MockAdapter + CSVDataProvider con datos sintéticos)")
    print()
    
    # Force TESTING mode by temporarily modifying config
    config_file = Path("config.ini")
    original_content = None
    
    try:
        # Read original config
        if config_file.exists():
            with open(config_file, 'r') as f:
                original_content = f.read()
        
        # Write temporary TESTING config
        config = configparser.ConfigParser()
        config['TRADING'] = {
            'active_profile': 'TESTING',
            'default_symbols': 'AAAA,AAAB,AAAC,AAAD,AAAE'  # First 5 synthetic symbols
        }
        
        with open(config_file, 'w') as f:
            config.write(f)
        
        print("✅ Configuración temporal establecida (modo TESTING)")
        print("📊 Símbolos de prueba: AAAA, AAAB, AAAC, AAAD, AAAE")
        print()
        
        # Create configuration with synthetic data enabled
        trading_config = TradingConfig(
            max_positions=5,
            max_risk_per_trade=0.02,
            max_daily_loss=-500.0,
            max_daily_trades=20,
            strategy_name="macdv",
            timeframe="1 min",
            log_level="INFO",
            use_synthetic_data=True  # Enable synthetic data mode
        )
        
        # Create and initialize system
        print("🚀 Inicializando sistema de trading...")
        system = TradingSystemManager(trading_config, in_streamlit=False)
        
        await system.initialize()
        print("✅ Sistema inicializado exitosamente")
        
        # Check data provider mode
        if hasattr(system.data_provider, 'is_synthetic_mode'):
            is_synthetic = system.data_provider.is_synthetic_mode()
            print(f"🎯 Modo de datos sintéticos: {is_synthetic}")
            
            if is_synthetic:
                symbols = system.data_provider.get_available_symbols()
                print(f"📊 Símbolos sintéticos disponibles: {len(symbols)}")
                
                # Test loading data for first symbol
                if symbols:
                    test_symbol = symbols[0]
                    print(f"\n📈 Probando carga de datos para: {test_symbol}")
                    
                    bars = await system.data_provider.get_bars(test_symbol, "1 min", 10)
                    if bars:
                        print(f"✅ Cargadas {len(bars)} barras")
                        print(f"   📅 Rango: {bars[0].timestamp} a {bars[-1].timestamp}")
                        print(f"   💰 Precios: ${bars[0].close:.2f} - ${bars[-1].close:.2f}")
                        
                        # Show event info
                        event_info = system.data_provider.get_event_info_for_symbol(test_symbol)
                        if event_info:
                            print(f"   🚀 Evento original: {event_info.get('original_ticker')}")
                            print(f"   📊 Ratio volumen: {event_info.get('ratio_vol', 0):.1f}x")
                    else:
                        print(f"❌ No se pudieron cargar datos para {test_symbol}")
        
        print(f"\n🎉 DEMO COMPLETADO EXITOSAMENTE!")
        print("✅ El sistema está listo para operar con datos sintéticos")
        print()
        print("💡 Para ejecutar el sistema completo:")
        print("   1. Mantener config.ini en modo TESTING")
        print("   2. Ejecutar: python main.py")
        print("   3. Agregar símbolos sintéticos: add AAAA")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la demo: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Restore original config
        if original_content is not None:
            try:
                with open(config_file, 'w') as f:
                    f.write(original_content)
                print("\n🔄 Configuración original restaurada")
            except:
                pass
        
        # Stop system
        try:
            await system.stop()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(demo_synthetic_trading())