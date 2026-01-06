#!/usr/bin/env python3
"""
Debug script que simula exactamente los imports de Streamlit
"""

import sys
from pathlib import Path
import configparser
import traceback

print("🔍 DEBUGGING STREAMLIT IMPORTS...")
print("=" * 60)

# Simular exactamente lo que hace streamlit_app_v2.py
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print(f"📂 Working directory: {current_dir}")
print(f"📂 Python path: {sys.path[0]}")

try:
    print("\n1️⃣ Importando módulos básicos...")
    from core.interfaces import TradingConfig
    print("✅ TradingConfig imported")
    
    from strategies import register_strategy, list_strategies
    print("✅ strategies module imported")
    
    print("\n2️⃣ Verificando estrategias disponibles...")
    available_strategies = list_strategies()
    print(f"✅ Estrategias: {available_strategies}")
    print(f"✅ multi_strategy presente: {'multi_strategy' in available_strategies}")
    
    print("\n3️⃣ Cargando configuración...")
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
    print(f"✅ Config strategy: {strategy_name}")
    
    print("\n4️⃣ Simulando selectbox de Streamlit...")
    
    # Priorizar multi_strategy (nuevo código de Streamlit)
    if 'multi_strategy' in available_strategies:
        available_strategies.remove('multi_strategy')
        available_strategies.insert(0, 'multi_strategy')
        print(f"✅ Estrategias reordenadas: {available_strategies}")
    
    # Calcular índice por defecto
    default_index = 0
    if strategy_name in available_strategies:
        default_index = available_strategies.index(strategy_name)
    
    print(f"✅ Índice por defecto: {default_index}")
    print(f"✅ Estrategia seleccionada: {available_strategies[default_index]}")
    
    # Verificar mensaje de debug
    if strategy_name == 'multi_strategy':
        print("✅ DEBERÍA mostrar: 'Multi-strategy configurada por defecto'")
    
    print("\n5️⃣ Test de instanciación...")
    from strategies import get_strategy_class
    cls = get_strategy_class('multi_strategy')
    instance = cls()
    print(f"✅ Instanciación exitosa: {instance.name}")
    
    print("\n" + "=" * 60)
    print("🎉 TODO FUNCIONA CORRECTAMENTE")
    print("🎉 STREAMLIT DEBERÍA CARGAR multi_strategy")
    
except Exception as e:
    print(f"\n❌ ERROR ENCONTRADO: {e}")
    print("\n📋 TRACEBACK COMPLETO:")
    traceback.print_exc()
    
    print("\n🔧 POSIBLES CAUSAS:")
    print("- Problema con imports")
    print("- Error en la configuración")
    print("- Caché de Python/Streamlit")
    print("- Error en el path")