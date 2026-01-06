#!/usr/bin/env python3
"""
Compara valores hardcodeados anteriores vs predicciones ML actuales
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.ml_volume_engine import MLVolumeEngine, create_market_context

def compare_volume_requirements():
    """Compara valores antiguos vs nuevos ML"""
    
    print("COMPARACIÓN: VALORES HARDCODEADOS vs ML DINÁMICO")
    print("=" * 70)
    
    # Initialize ML engine
    ml_engine = MLVolumeEngine()
    if not ml_engine.load_models():
        print("❌ Error: No se pudieron cargar los modelos ML")
        return
    
    # Old hardcoded values (from our cleanup)
    old_values = {
        'macdv_smallcaps': 1.2,
        'daily_plays': 0.8,  # Was optimized to 0.8
        'gap_go': 1.5,
        'volume_breakout': 2.0,
        'orb': 1.3
    }
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Morning Smallcap High Volume',
            'time': 10,  # 10 AM
            'data': {
                'ticker': 'AAPL', 'price': 3.50, 'market_cap': 100000000,
                'avg_volume': 50000, 'float_shares': 20000000, 'sector': 'Technology',
                'percent_var': 5.5, 'ratio_vol': 2.3, 'volatility': 0.4
            }
        },
        {
            'name': 'Afternoon Low Volume Play',
            'time': 14,  # 2 PM
            'data': {
                'ticker': 'SMALLCAP', 'price': 1.20, 'market_cap': 25000000,
                'avg_volume': 20000, 'float_shares': 15000000, 'sector': 'Healthcare', 
                'percent_var': -1.2, 'ratio_vol': 0.8, 'volatility': 0.2
            }
        },
        {
            'name': 'High Volatility Breakout',
            'time': 9.5,  # Market open
            'data': {
                'ticker': 'VOLATILE', 'price': 8.90, 'market_cap': 200000000,
                'avg_volume': 100000, 'float_shares': 30000000, 'sector': 'Energy',
                'percent_var': 15.2, 'ratio_vol': 4.1, 'volatility': 0.8
            }
        },
        {
            'name': 'End of Day Low Cap',
            'time': 15.5,  # 3:30 PM
            'data': {
                'ticker': 'EOD', 'price': 2.45, 'market_cap': 50000000,
                'avg_volume': 35000, 'float_shares': 25000000, 'sector': 'Finance',
                'percent_var': 3.1, 'ratio_vol': 1.4, 'volatility': 0.3
            }
        }
    ]
    
    strategies = ['macdv_smallcaps', 'daily_plays', 'gap_go', 'volume_breakout', 'orb']
    
    total_comparisons = 0
    more_restrictive = 0
    less_restrictive = 0
    similar = 0
    
    for scenario in scenarios:
        print(f"\n📊 ESCENARIO: {scenario['name']}")
        print(f"   Hora: {scenario['time']}:00 | Price: ${scenario['data']['price']:.2f} | " +
              f"Volume: {scenario['data']['ratio_vol']}x | Sector: {scenario['data']['sector']}")
        print("-" * 70)
        
        # Create context with specific time
        test_time = datetime.now().replace(hour=int(scenario['time']), minute=int((scenario['time'] % 1) * 60))
        context = create_market_context(scenario['data'], test_time)
        
        for strategy in strategies:
            old_req = old_values.get(strategy, 1.5)
            new_req = ml_engine.predict_volume_requirement(strategy, context)
            
            diff_pct = ((new_req - old_req) / old_req) * 100
            total_comparisons += 1
            
            if diff_pct > 5:
                trend = "📈 MÁS RESTRICTIVO"
                color = "\033[91m"  # Red
                more_restrictive += 1
            elif diff_pct < -5:
                trend = "📉 MENOS RESTRICTIVO"
                color = "\033[92m"  # Green
                less_restrictive += 1
            else:
                trend = "➡️  SIMILAR"
                color = "\033[93m"  # Yellow
                similar += 1
            
            reset_color = "\033[0m"
            
            print(f"   {strategy:18} | Antes: {old_req:.2f}x -> Ahora: {new_req:.2f}x | " +
                  f"{diff_pct:+5.1f}% {color}{trend}{reset_color}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE CAMBIOS:")
    print("=" * 70)
    
    print(f"📈 Más Restrictivo:   {more_restrictive:2d}/{total_comparisons} ({more_restrictive/total_comparisons*100:.1f}%)")
    print(f"📉 Menos Restrictivo: {less_restrictive:2d}/{total_comparisons} ({less_restrictive/total_comparisons*100:.1f}%)")  
    print(f"➡️ Similar:           {similar:2d}/{total_comparisons} ({similar/total_comparisons*100:.1f}%)")
    
    if more_restrictive > less_restrictive:
        tendency = "📈 MÁS CONSERVADOR"
        interpretation = "El sistema ML es más selectivo, requiere más volumen"
    elif less_restrictive > more_restrictive:
        tendency = "📉 MENOS CONSERVADOR"  
        interpretation = "El sistema ML es más permisivo, requiere menos volumen"
    else:
        tendency = "⚖️ EQUILIBRADO"
        interpretation = "El sistema ML mantiene niveles similares"
        
    print(f"\n🎯 TENDENCIA GENERAL: {tendency}")
    print(f"💡 INTERPRETACIÓN: {interpretation}")
    
    print("\n🔍 VENTAJAS DEL SISTEMA ML:")
    print("   • Se adapta al contexto (hora, volatilidad, sector)")
    print("   • Considera condiciones del mercado en tiempo real")
    print("   • Aprende de resultados históricos reales")
    print("   • Elimina valores arbitrarios fijos")
    print("   • Mejora automáticamente con el tiempo")

if __name__ == "__main__":
    compare_volume_requirements()