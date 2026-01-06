#!/usr/bin/env python3
"""
MACDV Parameter Audit Tool
==========================
Diagnóstico en tiempo real de parámetros MACDV vs configuración base
"""

import sys
import os
import configparser
import json
from pathlib import Path
from datetime import datetime
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def load_config_baseline():
    """Cargar configuración baseline del config.ini"""
    config = configparser.ConfigParser()
    config.read('config.ini')

    return {
        'strategy': config.get('TRADING', 'strategy'),
        'volume_threshold': 1.5,  # Default MACDV
        'macd_fast': 5,
        'macd_slow': 13,
        'macd_signal': 3,
        'min_price': 1.0,
        'max_price': 25.0,
        'volume_required': True,
        'volume_spike_threshold': 2.0,

        # ML Settings
        'enable_hybrid_learning': config.getboolean('TRADING', 'enable_hybrid_learning', fallback=True),
        'learning_enabled': config.getboolean('MULTI_STRATEGY', 'learning_enabled', fallback=True),
        'enable_strategy_selection_learning': config.getboolean('CONTINUOUS_LEARNING_SYSTEM', 'enable_strategy_selection_learning', fallback=True),
        'confidence_threshold': config.getfloat('PRODUCTION_PROFILE', 'multi_strategy_default_confidence_threshold', fallback=0.65)
    }

def check_ml_models():
    """Verificar estado de modelos ML"""
    ml_dir = Path('data/ml_models')

    models = {}
    if ml_dir.exists():
        for model_file in ml_dir.glob('*.json'):
            try:
                with open(model_file) as f:
                    data = json.load(f)
                    models[model_file.name] = {
                        'size': model_file.stat().st_size,
                        'modified': datetime.fromtimestamp(model_file.stat().st_mtime),
                        'keys': list(data.keys()) if isinstance(data, dict) else 'Not dict'
                    }
            except Exception as e:
                models[model_file.name] = f"Error: {e}"

    return models

async def get_live_strategy_instance():
    """Intentar obtener instancia live de la estrategia MACDV"""
    try:
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

        # Crear instancia del engine ML
        ml_engine = MLMultiStrategyEngine()

        # Obtener estrategias disponibles
        available_strategies = ml_engine.available_strategies
        strategy_instances = ml_engine.strategies

        # Verificar si MACDV está activa
        macdv_info = {}
        macdv_key = None

        # Buscar MACDV en estrategias disponibles
        for strategy_name in ['macdv_smallcaps', 'MACDVStrategy', 'macdv']:
            if strategy_name in available_strategies and strategy_name in strategy_instances:
                macdv_key = strategy_name
                break

        if macdv_key:
            macdv_instance = strategy_instances[macdv_key]
            macdv_info = {
                'strategy_name': macdv_instance.name,
                'parameters': macdv_instance._parameters if hasattr(macdv_instance, '_parameters') else 'No parameters',
                'active': True
            }
        else:
            macdv_info = {'active': False, 'reason': 'MACDV not found in available strategies'}

        return {
            'ml_engine_active': True,
            'strategy_count': len(available_strategies),
            'available_strategies': available_strategies,
            'loaded_strategy_instances': list(strategy_instances.keys()),
            'macdv_info': macdv_info
        }

    except Exception as e:
        return {
            'ml_engine_active': False,
            'error': str(e)
        }

def analyze_recent_trades():
    """Analizar trades recientes de AGMH en logs"""
    try:
        log_file = Path('logs/trading_system.log')
        if not log_file.exists():
            return "Log file not found"

        # Leer últimas 1000 líneas del log
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-1000:] if len(lines) > 1000 else lines

        agmh_entries = []
        for line in recent_lines:
            if 'AGMH' in line and ('BUY' in line or 'SELL' in line):
                agmh_entries.append(line.strip())

        return agmh_entries[-10:]  # Últimas 10 entradas

    except Exception as e:
        return f"Error reading logs: {e}"

def print_audit_report(config_baseline, ml_models, live_strategy, recent_trades):
    """Imprimir reporte completo de auditoría"""
    print("🔍 MACDV PARAMETER AUDIT REPORT")
    print("=" * 60)
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Configuración Base
    print("📋 BASELINE CONFIGURATION (config.ini):")
    print(f"   Strategy: {config_baseline['strategy']}")
    print(f"   Volume Threshold: {config_baseline['volume_threshold']}")
    print(f"   MACD Parameters: {config_baseline['macd_fast']}, {config_baseline['macd_slow']}, {config_baseline['macd_signal']}")
    print(f"   Price Range: ${config_baseline['min_price']} - ${config_baseline['max_price']}")
    print(f"   Volume Required: {config_baseline['volume_required']}")
    print(f"   Confidence Threshold: {config_baseline['confidence_threshold']}")
    print()

    # ML Status
    print("🤖 ML SYSTEM STATUS:")
    print(f"   Hybrid Learning: {config_baseline['enable_hybrid_learning']}")
    print(f"   Learning Enabled: {config_baseline['learning_enabled']}")
    print(f"   Strategy Selection Learning: {config_baseline['enable_strategy_selection_learning']}")
    print()

    # ML Models
    print("📊 ML MODELS:")
    if ml_models:
        for model_name, info in ml_models.items():
            if isinstance(info, dict):
                print(f"   {model_name}:")
                print(f"     Size: {info['size']} bytes")
                print(f"     Modified: {info['modified']}")
                print(f"     Keys: {info['keys']}")
            else:
                print(f"   {model_name}: {info}")
    else:
        print("   No ML models found")
    print()

    # Live Strategy Status
    print("⚡ LIVE STRATEGY STATUS:")
    if live_strategy['ml_engine_active']:
        print(f"   ML Engine: ✅ Active")
        print(f"   Available Strategies: {len(live_strategy['available_strategies'])}")
        print(f"   Strategies: {live_strategy['available_strategies']}")
        print(f"   Loaded Strategy Instances: {len(live_strategy['loaded_strategy_instances'])}")
        print(f"   Instances: {live_strategy['loaded_strategy_instances']}")

        if live_strategy['macdv_info']['active']:
            macdv = live_strategy['macdv_info']
            print(f"   MACDV Status: ✅ Active")
            print(f"   MACDV Name: {macdv['strategy_name']}")
            if isinstance(macdv['parameters'], dict):
                print("   MACDV Live Parameters:")
                for key, value in macdv['parameters'].items():
                    baseline_val = config_baseline.get(key, 'N/A')
                    status = "✅" if value == baseline_val else "⚠️"
                    print(f"     {status} {key}: {value} (baseline: {baseline_val})")
        else:
            print(f"   MACDV Status: ❌ Not Active - {live_strategy['macdv_info'].get('reason', 'Unknown')}")
    else:
        print(f"   ML Engine: ❌ Error - {live_strategy['error']}")
    print()

    # Recent Trades
    print("📈 RECENT AGMH TRADES:")
    if recent_trades and isinstance(recent_trades, list):
        for trade in recent_trades:
            print(f"   {trade}")
    else:
        print(f"   {recent_trades}")
    print()

    # Analysis
    print("🎯 ANALYSIS:")
    if config_baseline['strategy'] == 'ml_multi_strategy':
        print("   ⚠️  Using ML Multi Strategy - parameters may be dynamically modified")
    else:
        print("   ✅ Using static strategy")

    if config_baseline['enable_hybrid_learning']:
        print("   ⚠️  Hybrid learning enabled - ML may override validations")
    else:
        print("   ✅ Hybrid learning disabled")

    print("\n" + "=" * 60)

async def main():
    """Ejecutar auditoría completa"""
    print("🚀 Starting MACDV Parameter Audit...")

    # 1. Cargar configuración baseline
    config_baseline = load_config_baseline()

    # 2. Verificar modelos ML
    ml_models = check_ml_models()

    # 3. Obtener instancia live de estrategia
    live_strategy = await get_live_strategy_instance()

    # 4. Analizar trades recientes
    recent_trades = analyze_recent_trades()

    # 5. Generar reporte
    print_audit_report(config_baseline, ml_models, live_strategy, recent_trades)

if __name__ == "__main__":
    asyncio.run(main())