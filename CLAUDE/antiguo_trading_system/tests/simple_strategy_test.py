#!/usr/bin/env python3
"""
Script simplificado para diagnosticar por qué las estrategias no generan señales
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_strategy_conditions():
    """Probar condiciones básicas que podrían impedir la generación de señales"""
    print("🔍 DIAGNÓSTICO SIMPLIFICADO DE ESTRATEGIAS")
    print("=" * 50)
    
    # 1. Verificar configuración básica
    print("📋 Verificando configuración...")
    
    config_file = "config.ini"
    if os.path.exists(config_file):
        print(f"✅ Archivo de configuración encontrado: {config_file}")
        
        # Leer configuración básica
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        # Verificar configuraciones críticas
        critical_configs = [
            'trading_enabled',
            'min_volume',
            'min_price',
            'max_position_value',
            'trading_hours'
        ]
        
        for config in critical_configs:
            if config in config_content:
                # Extraer valor
                lines = config_content.split('\n')
                for line in lines:
                    if line.strip().startswith(config):
                        print(f"   {config}: {line.split('=')[1].strip() if '=' in line else 'N/A'}")
                        break
            else:
                print(f"   ❌ {config}: No encontrado")
    else:
        print(f"❌ Archivo de configuración no encontrado: {config_file}")
    
    # 2. Verificar horarios de trading
    print(f"\n🕐 Verificando horarios de trading...")
    current_time = datetime.now()
    print(f"   Hora actual: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Día de la semana: {current_time.strftime('%A')}")
    
    # Horarios típicos de mercado (EST)
    market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if current_time.weekday() < 5:  # Lunes a Viernes
        if market_open <= current_time <= market_close:
            print("   ✅ Dentro del horario de mercado")
        else:
            print("   ⚠️ Fuera del horario de mercado regular")
            print("   💡 Esto podría explicar por qué no se generan señales")
    else:
        print("   ❌ Fin de semana - mercado cerrado")
        print("   💡 Esto explica por qué no se generan señales")
    
    # 3. Verificar datos de mercado recientes
    print(f"\n📊 Verificando disponibilidad de datos...")
    
    # Buscar archivos de datos
    data_dirs = ['data', 'temp', '.']
    data_files_found = []
    
    for data_dir in data_dirs:
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                if any(ext in file.lower() for ext in ['.csv', '.json', '.db']):
                    data_files_found.append(f"{data_dir}/{file}")
    
    if data_files_found:
        print(f"   ✅ Encontrados {len(data_files_found)} archivos de datos")
        for file in data_files_found[:5]:  # Mostrar solo los primeros 5
            print(f"      - {file}")
        if len(data_files_found) > 5:
            print(f"      ... y {len(data_files_found) - 5} más")
    else:
        print("   ❌ No se encontraron archivos de datos")
        print("   💡 Falta de datos podría impedir la generación de señales")
    
    # 4. Verificar logs recientes para patrones
    print(f"\n📋 Analizando patrones en logs...")
    
    log_file = "trading_system.log"
    if os.path.exists(log_file):
        print(f"   ✅ Archivo de log encontrado: {log_file}")
        
        # Leer últimas líneas del log
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            recent_lines = lines[-50:]  # Últimas 50 líneas
            
            # Buscar patrones importantes
            patterns = {
                'signals_generated': 0,
                'ml_selections': 0,
                'no_signals': 0,
                'strategy_errors': 0,
                'market_closed': 0
            }
            
            for line in recent_lines:
                if 'ML selected strategies' in line:
                    patterns['ml_selections'] += 1
                elif 'generated no signals' in line:
                    patterns['no_signals'] += 1
                elif 'signals generated' in line:
                    patterns['signals_generated'] += 1
                elif 'Error' in line and 'strategy' in line.lower():
                    patterns['strategy_errors'] += 1
                elif 'market' in line.lower() and 'closed' in line.lower():
                    patterns['market_closed'] += 1
            
            print("   📊 Patrones encontrados en logs recientes:")
            for pattern, count in patterns.items():
                status = "✅" if count > 0 else "❌"
                print(f"      {status} {pattern}: {count}")
            
            # Análisis de patrones
            if patterns['ml_selections'] > 0 and patterns['no_signals'] > 0:
                print("\n   💡 DIAGNÓSTICO: ML selecciona estrategias pero no generan señales")
                print("      Posibles causas:")
                print("      - Condiciones de mercado no cumplen criterios de estrategia")
                print("      - Parámetros de estrategia muy restrictivos")
                print("      - Horario fuera de trading")
                print("      - Volumen o precio insuficiente")
            
        except Exception as e:
            print(f"   ❌ Error leyendo log: {e}")
    else:
        print(f"   ❌ Archivo de log no encontrado: {log_file}")
    
    # 5. Recomendaciones
    print(f"\n🎯 RECOMENDACIONES")
    print("=" * 50)
    print("1. ✅ Verificar que el sistema esté ejecutándose en horario de mercado")
    print("2. ✅ Revisar parámetros de estrategia (min_volume, min_price, etc.)")
    print("3. ✅ Confirmar que hay datos de mercado disponibles y actualizados")
    print("4. ✅ Considerar ajustar temporalmente los parámetros para testing")
    print("5. ✅ Verificar que las estrategias seleccionadas sean apropiadas para el mercado actual")
    
    print(f"\n🚀 SIGUIENTE PASO SUGERIDO:")
    print("Ejecutar el sistema en modo de prueba con parámetros más permisivos")
    print("para confirmar que el flujo ML → Estrategia → Señal funciona correctamente.")

if __name__ == "__main__":
    test_strategy_conditions()
