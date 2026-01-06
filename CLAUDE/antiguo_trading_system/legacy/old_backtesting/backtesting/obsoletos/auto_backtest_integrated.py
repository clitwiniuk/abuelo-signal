#!/usr/bin/env python3
"""
Backtesting integrado automatizado
Usa el sistema de backtesting integrado pero sin inputs manuales
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Monkey patch para evitar inputs manuales
import builtins
original_input = builtins.input

def auto_input(prompt):
    """Auto-responder para inputs del backtesting"""
    print(prompt, end="")
    
    if "estrategia" in prompt or "strategy" in prompt:
        print("1")  # Seleccionar MACD-V
        return "1"
    elif "símbolo" in prompt or "symbol" in prompt:
        print("XXII")
        return "XXII"  
    elif "barras" in prompt or "bars" in prompt:
        print("1000")
        return "1000"
    elif "continuar" in prompt or "continue" in prompt:
        print("n")
        return "n"
    else:
        print("1")  # Default
        return "1"

# Patch input function
builtins.input = auto_input

async def run_integrated_backtest():
    """Ejecutar el backtesting integrado automáticamente"""
    
    print("🚀 BACKTESTING INTEGRADO - MODO AUTOMÁTICO")
    print("=" * 50)
    print("🎯 Ejecutando backtesting con configuración automática:")
    print("   - Estrategia: MACD-V")
    print("   - Símbolo: XXII") 
    print("   - Barras: 1000")
    
    try:
        # Import the main function from run_backtest.py
        from scripts.runners.run_backtest import main as backtest_main
        
        # Run the integrated backtest
        await backtest_main()
        
        print("\n✅ Backtesting integrado completado!")
        
    except Exception as e:
        print(f"❌ Error en backtesting integrado: {e}")
        import traceback
        traceback.print_exc()
        
        print(f"\n💡 ALTERNATIVA: Puedes usar el backtesting manual:")
        print(f"   python comprehensive_backtest.py")
    finally:
        # Restore original input
        builtins.input = original_input

if __name__ == "__main__":
    asyncio.run(run_integrated_backtest())