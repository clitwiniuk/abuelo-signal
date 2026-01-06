#!/usr/bin/env python3
"""
Script para verificar si ib_insync está disponible para modo PRODUCTION
"""
import sys

print("🔍 VERIFICACIÓN DE DEPENDENCIAS PARA MODO PRODUCTION")
print("=" * 60)

def check_ib_insync():
    """Verificar si ib_insync está disponible"""
    try:
        import ib_insync
        version = getattr(ib_insync, '__version__', 'unknown')
        print(f"✅ ib_insync está instalado (versión: {version})")
        
        # Test basic functionality
        try:
            from ib_insync import IB, Stock, MarketOrder, LimitOrder, util
            print("✅ Componentes principales de ib_insync importados correctamente")
            return True
        except ImportError as e:
            print(f"⚠️ ib_insync instalado pero falta algún componente: {e}")
            return False
            
    except ImportError:
        print("❌ ib_insync NO está instalado")
        return False

def check_optional_deps():
    """Verificar dependencias opcionales"""
    optional_deps = {
        'streamlit': 'Interfaz web (streamlit_app_v2.py)',
        'matplotlib': 'Gráficos y visualizaciones',
        'plotly': 'Gráficos interactivos'
    }
    
    print("\n📦 VERIFICACIÓN DE DEPENDENCIAS OPCIONALES:")
    results = {}
    
    for dep, desc in optional_deps.items():
        try:
            __import__(dep)
            print(f"✅ {dep}: {desc}")
            results[dep] = True
        except ImportError:
            print(f"❌ {dep}: {desc} - NO DISPONIBLE")
            results[dep] = False
    
    return results

def check_other_deps():
    """Verificar otras dependencias importantes"""
    deps = {
        'pandas': 'Análisis de datos',
        'numpy': 'Cálculos numéricos', 
        'asyncio': 'Programación asíncrona',
        'configparser': 'Configuración',
        'pathlib': 'Manejo de archivos'
    }
    
    print("\n📦 VERIFICACIÓN DE OTRAS DEPENDENCIAS:")
    all_ok = True
    
    for dep, desc in deps.items():
        try:
            __import__(dep)
            print(f"✅ {dep}: {desc}")
        except ImportError:
            print(f"❌ {dep}: {desc} - NO DISPONIBLE")
            all_ok = False
    
    return all_ok

def main():
    # Check ib_insync
    ib_ok = check_ib_insync()
    
    # Check other dependencies
    other_ok = check_other_deps()
    
    # Check optional dependencies
    optional = check_optional_deps()
    
    print("\n" + "=" * 60)
    print("📋 RESUMEN:")
    
    if ib_ok:
        print("✅ MODO PRODUCTION: Disponible (ib_insync instalado)")
        print("📈 Puedes usar active_profile = PRODUCTION en config.ini")
    else:
        print("❌ MODO PRODUCTION: No disponible (falta ib_insync)")
        print("💡 Para instalar: pip install ib_insync")
        print("🔄 Alternativa: usar active_profile = TESTING")
    
    print("✅ MODO TESTING: Siempre disponible (usa datos CSV)")
    
    # Optional features
    print("\n📱 FUNCIONALIDADES OPCIONALES:")
    if optional.get('streamlit', False):
        print("✅ Interfaz web disponible: python streamlit_app_v2.py")
    else:
        print("❌ Interfaz web no disponible (falta streamlit)")
        print("💡 Para instalar: pip install streamlit")
    
    if optional.get('matplotlib', False):
        print("✅ Gráficos disponibles")
    else:
        print("❌ Gráficos no disponibles (falta matplotlib)")
        print("💡 Para instalar: pip install matplotlib")
    
    if not other_ok:
        print("⚠️ Algunas dependencias básicas faltan")
    
    print("\n🎯 RECOMENDACIÓN:")
    if ib_ok and other_ok:
        print("   🟢 Sistema listo para modo PRODUCTION y TESTING")
    elif other_ok:
        print("   🟡 Sistema listo solo para modo TESTING")
        print("   📋 Instalar ib_insync para habilitar modo PRODUCTION")
    else:
        print("   🔴 Faltan dependencias críticas")
        print("   📋 Revisar instalación de Python y dependencias")
    
    print("\n💡 COMANDOS DE INSTALACIÓN:")
    if not ib_ok:
        print("   pip install ib_insync")
    if not optional.get('streamlit', False):
        print("   pip install streamlit")
    if not optional.get('matplotlib', False):
        print("   pip install matplotlib")
    
    print("\n🚀 FORMAS DE EJECUTAR EL SISTEMA:")
    print("   python start.py              # Menú principal")
    print("   python main.py               # Sistema directo")
    if optional.get('streamlit', False):
        print("   python streamlit_app_v2.py   # Interfaz web")
    print("   python comprehensive_backtest.py  # Backtesting rápido")

if __name__ == "__main__":
    main()