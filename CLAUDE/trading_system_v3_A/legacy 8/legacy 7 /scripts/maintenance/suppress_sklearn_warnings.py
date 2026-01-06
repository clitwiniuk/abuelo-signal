#!/usr/bin/env python3
"""
Suprimir warnings de sklearn - Solución para advertencias de feature names
Ubicación: scripts/maintenance/ (estructura organizada)
"""

import sys
import os
import warnings

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def apply_sklearn_warning_fixes():
    """Aplica filtros para suprimir warnings específicos de sklearn"""
    print("🔧 APLICANDO FILTROS PARA WARNINGS SKLEARN")
    print("=" * 50)
    
    # Suprimir warning específico de feature names
    warnings.filterwarnings('ignore', 
                           message='X does not have valid feature names, but StandardScaler was fitted with feature names',
                           category=UserWarning,
                           module='sklearn')
    
    print("✅ Filtro aplicado para: 'X does not have valid feature names'")
    
    # Test para verificar que funciona
    print("\n🧪 TESTING SUPRESIÓN DE WARNINGS")
    test_ml_volume_with_suppression()
    
    print("\n💡 RECOMENDACIÓN:")
    print("   Agregar este código al inicio de los scripts principales:")
    print("   - trader_main.py")  
    print("   - scanner_main.py")
    print("   - simple_main.py")

def test_ml_volume_with_suppression():
    """Test del ML Volume Engine con warnings suprimidos"""
    try:
        from core.ml_volume_engine import MLVolumeEngine, MarketContext
        
        engine = MLVolumeEngine()
        if engine.load_models():
            print(f"✅ {len(engine.models)} modelos cargados")
            
            # Test context
            context = MarketContext(
                time_of_day=0.4, day_of_week=1, market_cap=50_000_000,
                avg_volume=200_000, float_shares=10_000_000, sector="Technology",
                recent_performance=3.5, market_stress=0.5, volume_trend=1.8, price_level=8.50
            )
            
            # Test predicciones (deberían ser silenciosas ahora)
            print("📊 Testing predicciones (sin warnings):")
            for strategy in list(engine.models.keys())[:3]:
                try:
                    volume_req = engine.predict_volume_requirement(strategy, context)
                    print(f"   ✅ {strategy}: {volume_req:.2f}x")
                except Exception as e:
                    print(f"   ❌ {strategy}: Error - {e}")
                    
        print("🎯 Test completado - ¿Viste warnings? (No deberías)")
        
    except Exception as e:
        print(f"❌ Error en test: {e}")

def generate_fix_code():
    """Genera código para agregar a los archivos principales"""
    fix_code = '''
# Suprimir warnings sklearn específicos (agregar al inicio del archivo)
import warnings
warnings.filterwarnings('ignore', 
                       message='X does not have valid feature names, but StandardScaler was fitted with feature names',
                       category=UserWarning,
                       module='sklearn')
'''
    
    print("\n📝 CÓDIGO PARA AGREGAR A LOS ARCHIVOS PRINCIPALES:")
    print("=" * 50)
    print(fix_code)
    print("=" * 50)
    
    return fix_code

def main():
    """Función principal"""
    print("🛠️  HERRAMIENTA DE SUPRESIÓN DE WARNINGS SKLEARN")
    print("📍 Desde: scripts/maintenance/suppress_sklearn_warnings.py")
    print("=" * 60)
    
    # Aplicar y testear
    apply_sklearn_warning_fixes()
    
    # Generar código
    generate_fix_code()
    
    print("\n✅ Proceso completado")
    print("💡 Los warnings sklearn están suprimidos para esta sesión")
    print("💡 Para solución permanente, agregar el código a los archivos principales")

if __name__ == "__main__":
    main()