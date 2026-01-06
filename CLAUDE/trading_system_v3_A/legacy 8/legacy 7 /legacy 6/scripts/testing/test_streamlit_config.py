#!/usr/bin/env python3
"""
Test script para simular exactamente lo que hace Streamlit al cargar la configuración
"""

import sys
from pathlib import Path
import configparser

# Añadir el directorio actual al path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from strategies import list_strategies

def load_config_from_ini():
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    
    class Config:
        def __init__(self):
            # Trading config - exactamente como lo hace Streamlit
            self.strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
    
    return Config()

def main():
    print("🧪 SIMULANDO CARGA DE STREAMLIT...")
    print("=" * 50)
    
    # Step 1: Cargar estrategias disponibles
    try:
        available_strategies = list_strategies()
        print(f"✅ Estrategias cargadas: {available_strategies}")
        print(f"✅ multi_strategy disponible: {'multi_strategy' in available_strategies}")
    except Exception as e:
        print(f"❌ Error cargando estrategias: {e}")
        return
    
    # Step 2: Cargar config
    try:
        config = load_config_from_ini()
        print(f"✅ Estrategia del config.ini: {config.strategy_name}")
    except Exception as e:
        print(f"❌ Error cargando config: {e}")
        return
    
    # Step 3: Encontrar índice por defecto (como lo hace Streamlit)
    default_index = 0
    if config.strategy_name in available_strategies:
        default_index = available_strategies.index(config.strategy_name)
        print(f"✅ Índice por defecto: {default_index}")
        print(f"✅ Estrategia por defecto: {available_strategies[default_index]}")
        print("✅ STREAMLIT DEBERÍA seleccionar multi_strategy automáticamente")
    else:
        print(f"❌ PROBLEMA: '{config.strategy_name}' no está en las estrategias disponibles")
        print("❌ STREAMLIT usará índice 0 por defecto")
    
    print("=" * 50)
    print("🎯 RESULTADO: ", end="")
    if config.strategy_name == 'multi_strategy' and 'multi_strategy' in available_strategies:
        print("✅ TODO CORRECTO - multi_strategy debería cargar por defecto")
    else:
        print("❌ PROBLEMA DETECTADO")

if __name__ == "__main__":
    main()