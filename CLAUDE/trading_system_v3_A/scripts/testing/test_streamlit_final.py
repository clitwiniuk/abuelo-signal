#!/usr/bin/env python3
"""
Test final para verificar la carga de multi_strategy en Streamlit
"""

import sys
from pathlib import Path
import configparser

# Añadir el directorio actual al path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from strategies import list_strategies

def simulate_streamlit_logic():
    """Simular exactamente la nueva lógica de Streamlit"""
    
    print("🚀 SIMULANDO NUEVA LÓGICA DE STREAMLIT...")
    print("=" * 60)
    
    # Step 1: Cargar config
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
    print(f"📋 Config.ini strategy: {strategy_name}")
    
    # Step 2: Cargar y reordenar estrategias (nueva lógica)
    try:
        available_strategies = list_strategies()
        print(f"📦 Estrategias originales: {available_strategies}")
        
        # Priorizar multi_strategy (nuevo código)
        if 'multi_strategy' in available_strategies:
            available_strategies.remove('multi_strategy')
            available_strategies.insert(0, 'multi_strategy')
            print(f"🔄 Estrategias reordenadas: {available_strategies}")
        
        # Calcular índice por defecto
        default_index = 0
        if strategy_name in available_strategies:
            default_index = available_strategies.index(strategy_name)
        
        print(f"🎯 Índice por defecto: {default_index}")
        print(f"🎯 Estrategia por defecto: {available_strategies[default_index]}")
        
        # Verificar si aparecerá el mensaje de éxito
        if strategy_name == 'multi_strategy':
            print("✅ Mensaje de éxito: 'Multi-strategy configurada por defecto'")
        
        print("=" * 60)
        print("🏆 RESULTADO FINAL:")
        if available_strategies[default_index] == 'multi_strategy':
            print("   ✅ STREAMLIT CARGARÁ multi_strategy por defecto")
            print("   ✅ multi_strategy aparecerá PRIMERA en la lista")
        else:
            print("   ❌ Algo sigue mal")
        
    except Exception as e:
        print(f"❌ Error en try: {e}")
        # Simular fallback
        available_strategies = ['multi_strategy', 'macdv', 'gap_go']
        default_fallback_index = 0 if strategy_name == 'multi_strategy' else 1
        print(f"🔄 FALLBACK: {available_strategies}")
        print(f"🎯 Índice fallback: {default_fallback_index}")
        print(f"🎯 Estrategia fallback: {available_strategies[default_fallback_index]}")

if __name__ == "__main__":
    simulate_streamlit_logic()