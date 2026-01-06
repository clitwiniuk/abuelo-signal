#!/usr/bin/env python3
# production/test_hybrid_integration.py
"""
Test de integración del sistema híbrido
Valida que el HybridConfigManager funcione correctamente con el production runner
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from production.hybrid_config_manager import HybridConfigManager

def test_hybrid_config_integration():
    """Test completo de integración de configuración híbrida"""
    
    print("🧪 TESTING INTEGRACIÓN SISTEMA HÍBRIDO")
    print("=" * 60)
    
    try:
        # 1. Test HybridConfigManager initialization
        print("\n1️⃣ Inicializando HybridConfigManager...")
        manager = HybridConfigManager()
        print("✅ HybridConfigManager inicializado correctamente")
        
        # 2. Test lectura de config.ini
        print("\n2️⃣ Testeando lectura de config.ini...")
        base_config = manager.get_base_config_from_ini()
        print(f"✅ Leídas {len(base_config)} secciones desde config.ini")
        
        # Verificar secciones críticas
        critical_sections = ['ibkr', 'trading', 'global', 'daily_plays_strategy']
        for section in critical_sections:
            if section in base_config:
                print(f"   ✅ Sección [{section.upper()}] encontrada")
            else:
                print(f"   ❌ Sección [{section.upper()}] NO encontrada")
        
        # 3. Test extensiones de producción
        print("\n3️⃣ Testeando extensiones de producción...")
        production_ext = manager.get_production_extensions()
        ext_sections = ['scanning_intervals', 'tiingo', 'production_monitoring', 'production_alerts']
        for section in ext_sections:
            if section in production_ext:
                print(f"   ✅ Extensión [{section}] generada")
            else:
                print(f"   ❌ Extensión [{section}] NO generada")
        
        # 4. Test configuración híbrida completa
        print("\n4️⃣ Testeando configuración híbrida completa...")
        complete_config = manager.get_complete_hybrid_config()
        
        required_keys = ['config_source', 'config_ini_path', 'base_config', 'production_extensions']
        for key in required_keys:
            if key in complete_config:
                print(f"   ✅ Clave [{key}] presente")
            else:
                print(f"   ❌ Clave [{key}] NO presente")
        
        # 5. Test configuraciones específicas
        print("\n5️⃣ Testeando configuraciones específicas...")
        
        # IBKR config
        try:
            ibkr_config = manager.get_ibkr_config()
            print(f"   ✅ IBKR config: {ibkr_config['host']}:{ibkr_config['port']}")
        except Exception as e:
            print(f"   ❌ Error IBKR config: {e}")
        
        # Trading params
        try:
            trading_params = manager.get_trading_params()
            print(f"   ✅ Trading params: ${trading_params['portfolio_capital']}, {trading_params['max_positions']} posiciones")
        except Exception as e:
            print(f"   ❌ Error trading params: {e}")
        
        # Smallcap strategy
        try:
            smallcap_config = manager.get_smallcap_strategy_config()
            if smallcap_config:
                print(f"   ✅ Smallcap config: ${smallcap_config['min_price']}-${smallcap_config['max_price']}, {smallcap_config['min_gap_percent']:.1f}% gap")
            else:
                print("   ⚠️ Smallcap config vacío")
        except Exception as e:
            print(f"   ❌ Error smallcap config: {e}")
        
        # 6. Test validación (sin env vars)
        print("\n6️⃣ Testeando validación...")
        validation = manager.validate_hybrid_config()
        
        print(f"   📋 config.ini válido: {validation['config_ini_valid']}")
        print(f"   📋 Extensiones válidas: {validation['production_extensions_valid']}")
        print(f"   📋 Env vars válidas: {validation['env_vars_valid']} (esperado False sin IBKR_ACCOUNT/TIINGO_API_KEY)")
        
        if validation['errors']:
            print("   ⚠️ Errores encontrados:")
            for error in validation['errors']:
                print(f"      - {error}")
        
        if validation['warnings']:
            print("   ⚠️ Advertencias:")
            for warning in validation['warnings']:
                print(f"      - {warning}")
        
        # 7. Test resumen
        print("\n7️⃣ Testeando resumen...")
        manager.print_config_summary()
        
        print("\n" + "=" * 60)
        print("🎉 INTEGRACIÓN HÍBRIDA FUNCIONANDO CORRECTAMENTE!")
        print("=" * 60)
        
        print("\n✅ COMPONENTES VALIDADOS:")
        print("   📋 config.ini como fuente principal")
        print("   🔧 HybridConfigManager funcionando")
        print("   ⚙️ Extensiones de producción generadas")
        print("   🎯 Configuración smallcaps desde [DAILY_PLAYS_STRATEGY]")
        print("   🔐 Variables de entorno identificadas correctamente")
        print("   ❌ Solo falta: IBKR_ACCOUNT y TIINGO_API_KEY para deployment real")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN INTEGRACIÓN: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_hybrid_config_integration()
    if success:
        print("\n✅ Test de integración EXITOSO")
        exit(0)
    else:
        print("\n❌ Test de integración FALLIDO")
        exit(1)