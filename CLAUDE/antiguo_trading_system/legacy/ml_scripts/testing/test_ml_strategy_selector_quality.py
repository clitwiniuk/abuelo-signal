#!/usr/bin/env python3
"""
Test ML Strategy Selector - Validar el selector optimizado con database_quality.db
Verificar que la selección inteligente funciona correctamente
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import os
import sys
from typing import Dict, List, Tuple
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ml_strategy_selector import (
    ContextualBandit, 
    TickerContext,
    TickerProfiler,
    create_ml_strategy_selector,
    create_ticker_profiler
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyValidationTest:
    """Validador del ML Strategy Selector optimizado"""
    
    def __init__(self, db_path: str = "database_quality.db", model_path: str = "data/ml_models/strategy_selector.json"):
        self.db_path = db_path
        self.model_path = model_path
        
        # ✅ SOLO ESTRATEGIAS HABILITADAS EN config.ini (7 estrategias activas)
        self.strategies = [
            # 🌅 Morning Power
            'orb', 'gap_go',
            # 🕐 All-Day Core  
            'macdv_smallcaps', 'vwap_reclaim',
            # 📰 Event-Driven
            'catalyst_momentum',
            # 🌆 Specialized
            'eod_momentum', 'volume_breakout'
        ]
        
    def validate_model_exists(self) -> bool:
        """Valida que el modelo entrenado existe"""
        print(f"🔍 Validando existencia del modelo...")
        
        if not os.path.exists(self.model_path):
            print(f"❌ Modelo no encontrado en: {self.model_path}")
            return False
            
        # Verificar contenido del modelo
        try:
            with open(self.model_path, 'r') as f:
                model_data = json.load(f)
                
            model_strategies = model_data.get('strategies', [])
            print(f"✅ Modelo encontrado con {len(model_strategies)} estrategias")
            
            # Verificar que contiene las estrategias correctas
            missing_strategies = set(self.strategies) - set(model_strategies)
            if missing_strategies:
                print(f"⚠️  Estrategias faltantes en modelo: {missing_strategies}")
            
            print(f"📊 Modelo timestamp: {model_data.get('timestamp', 'N/A')}")
            return True
            
        except Exception as e:
            print(f"❌ Error leyendo modelo: {e}")
            return False
    
    def load_model(self) -> ContextualBandit:
        """Carga el modelo entrenado"""
        print(f"📂 Cargando modelo ML Strategy Selector...")
        
        model = create_ml_strategy_selector(self.strategies, self.model_path)
        
        # Mostrar estadísticas del modelo
        print(f"\n📈 ESTADÍSTICAS DEL MODELO CARGADO:")
        print(f"=" * 50)
        
        for strategy in self.strategies:
            if strategy in model.strategy_stats:
                stats = model.strategy_stats[strategy]
                print(f"{strategy:20} | Trades: {stats.total_trades:4d} | "
                      f"Avg PnL: {stats.avg_pnl:+.3f} | "
                      f"Win Rate: {stats.win_rate:.1%}")
        
        return model
    
    def create_test_scenarios(self) -> List[Dict]:
        """Crea escenarios de prueba diversos"""
        print(f"\n🎯 Creando escenarios de prueba...")
        
        scenarios = [
            # Morning Gap Scenario
            {
                'name': 'Morning Gap (Gap&Go expected)',
                'symbol': 'SPRT',
                'current_price': 15.50,
                'avg_volume_10': 2500000,
                'avg_volume_50': 800000,
                'volatility_10': 0.08,
                'volatility_50': 0.06,
                'price_change_1h': 0.12,  # 12% gap up
                'price_change_4h': 0.12,
                'rsi_14': 75.0,
                'volume_ratio_current': 3.5,
                'volume_spike_frequency': 0.3,
                'hour_of_day': 9.75,  # 9:45 AM
                'minutes_from_open': 15,
                'is_first_hour': True,
                'is_last_hour': False,
                'market_trend': 0.5,
                'sector_performance': 0.3,
                'breakout_success_rate': 0.7,
                'mean_reversion_tendency': 0.3
            },
            
            # ORB Scenario  
            {
                'name': 'Opening Range Breakout (ORB expected)',
                'symbol': 'PROG',
                'current_price': 8.25,
                'avg_volume_10': 1800000,
                'avg_volume_50': 950000,
                'volatility_10': 0.05,
                'volatility_50': 0.04,
                'price_change_1h': 0.06,  # 6% up
                'price_change_4h': 0.06,
                'rsi_14': 68.0,
                'volume_ratio_current': 2.1,
                'volume_spike_frequency': 0.2,
                'hour_of_day': 10.25,  # 10:15 AM
                'minutes_from_open': 45,
                'is_first_hour': True,
                'is_last_hour': False,
                'market_trend': 0.2,
                'sector_performance': 0.1,
                'breakout_success_rate': 0.6,
                'mean_reversion_tendency': 0.4
            },
            
            # MACDV SmallCaps Scenario
            {
                'name': 'SmallCaps Momentum (MACDV expected)',
                'symbol': 'IMUX',
                'current_price': 4.80,
                'avg_volume_10': 650000,
                'avg_volume_50': 420000,
                'volatility_10': 0.04,
                'volatility_50': 0.03,
                'price_change_1h': 0.04,  # 4% up
                'price_change_4h': 0.08,  # 8% sustained move
                'rsi_14': 62.0,
                'volume_ratio_current': 1.8,
                'volume_spike_frequency': 0.15,
                'hour_of_day': 13.5,  # 1:30 PM
                'minutes_from_open': 240,
                'is_first_hour': False,
                'is_last_hour': False,
                'market_trend': 0.3,
                'sector_performance': 0.2,
                'breakout_success_rate': 0.5,
                'mean_reversion_tendency': 0.5
            },
            
            # VWAP Reclaim Scenario
            {
                'name': 'VWAP Reclaim (VWAP expected)',
                'symbol': 'BBIG',
                'current_price': 12.10,
                'avg_volume_10': 1200000,
                'avg_volume_50': 980000,
                'volatility_10': 0.03,
                'volatility_50': 0.035,
                'price_change_1h': 0.02,  # 2% up (reclaim)
                'price_change_4h': -0.01,  # Was down, now reclaiming
                'rsi_14': 55.0,
                'volume_ratio_current': 1.6,
                'volume_spike_frequency': 0.12,
                'hour_of_day': 11.75,  # 11:45 AM
                'minutes_from_open': 135,
                'is_first_hour': False,
                'is_last_hour': False,
                'market_trend': 0.1,
                'sector_performance': -0.1,
                'breakout_success_rate': 0.4,
                'mean_reversion_tendency': 0.6
            },
            
            # Catalyst Momentum Scenario
            {
                'name': 'Breaking News Catalyst (Catalyst expected)',
                'symbol': 'DWAC',
                'current_price': 28.50,
                'avg_volume_10': 8500000,
                'avg_volume_50': 2100000,
                'volatility_10': 0.15,
                'volatility_50': 0.09,
                'price_change_1h': 0.22,  # 22% explosive move
                'price_change_4h': 0.25,
                'rsi_14': 85.0,
                'volume_ratio_current': 6.5,
                'volume_spike_frequency': 0.4,
                'hour_of_day': 12.25,  # 12:15 PM
                'minutes_from_open': 165,
                'is_first_hour': False,
                'is_last_hour': False,
                'market_trend': 0.6,
                'sector_performance': 0.4,
                'breakout_success_rate': 0.8,
                'mean_reversion_tendency': 0.2
            },
            
            # End of Day Momentum Scenario
            {
                'name': 'End of Day Push (EOD expected)',
                'symbol': 'RDBX',
                'current_price': 6.75,
                'avg_volume_10': 980000,
                'avg_volume_50': 750000,
                'volatility_10': 0.06,
                'volatility_50': 0.05,
                'price_change_1h': 0.08,  # 8% late day move
                'price_change_4h': 0.12,
                'rsi_14': 72.0,
                'volume_ratio_current': 2.2,
                'volume_spike_frequency': 0.25,
                'hour_of_day': 15.25,  # 3:15 PM
                'minutes_from_open': 345,
                'is_first_hour': False,
                'is_last_hour': True,
                'market_trend': 0.2,
                'sector_performance': 0.1,
                'breakout_success_rate': 0.6,
                'mean_reversion_tendency': 0.4
            },
            
            # Volume Breakout Scenario
            {
                'name': 'Volume Breakout (Volume Breakout expected)',
                'symbol': 'AMC',
                'current_price': 18.90,
                'avg_volume_10': 5200000,
                'avg_volume_50': 3100000,
                'volatility_10': 0.07,
                'volatility_50': 0.08,
                'price_change_1h': 0.05,  # 5% with volume
                'price_change_4h': 0.07,
                'rsi_14': 65.0,
                'volume_ratio_current': 4.8,  # Heavy volume
                'volume_spike_frequency': 0.35,
                'hour_of_day': 14.5,  # 2:30 PM
                'minutes_from_open': 300,
                'is_first_hour': False,
                'is_last_hour': False,
                'market_trend': 0.4,
                'sector_performance': 0.3,
                'breakout_success_rate': 0.7,
                'mean_reversion_tendency': 0.3
            }
        ]
        
        print(f"✅ Creados {len(scenarios)} escenarios de prueba")
        return scenarios
    
    def test_strategy_selection(self, model: ContextualBandit) -> Dict:
        """Prueba la selección de estrategias con escenarios diversos"""
        print(f"\n🧪 EJECUTANDO TESTS DE SELECCIÓN DE ESTRATEGIAS")
        print(f"=" * 65)
        
        scenarios = self.create_test_scenarios()
        results = []
        
        for scenario in scenarios:
            # Crear contexto del ticker
            context = TickerContext(
                symbol=scenario['symbol'],
                current_price=scenario['current_price'],
                avg_volume_10=scenario['avg_volume_10'],
                avg_volume_50=scenario['avg_volume_50'],
                volatility_10=scenario['volatility_10'],
                volatility_50=scenario['volatility_50'],
                price_change_1h=scenario['price_change_1h'],
                price_change_4h=scenario['price_change_4h'],
                rsi_14=scenario['rsi_14'],
                volume_ratio_current=scenario['volume_ratio_current'],
                volume_spike_frequency=scenario['volume_spike_frequency'],
                hour_of_day=scenario['hour_of_day'],
                minutes_from_open=scenario['minutes_from_open'],
                is_first_hour=scenario['is_first_hour'],
                is_last_hour=scenario['is_last_hour'],
                market_trend=scenario['market_trend'],
                sector_performance=scenario['sector_performance'],
                breakout_success_rate=scenario['breakout_success_rate'],
                mean_reversion_tendency=scenario['mean_reversion_tendency']
            )
            
            # Seleccionar estrategia
            selected_strategy = model.select_strategy(context)
            
            # Obtener ranking completo
            rankings = model.get_strategy_rankings(context)
            
            result = {
                'scenario': scenario['name'],
                'symbol': scenario['symbol'],
                'selected_strategy': selected_strategy,
                'rankings': rankings[:3]  # Top 3
            }
            results.append(result)
            
            # Mostrar resultado
            print(f"\n🎯 {scenario['name']}")
            print(f"   Ticker: {scenario['symbol']} | Selected: {selected_strategy}")
            print(f"   Top 3 Rankings:")
            for i, (strategy, score) in enumerate(rankings[:3], 1):
                mark = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                print(f"      {mark} {strategy:20} | Score: {score:+.4f}")
        
        return results
    
    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analiza los resultados de las pruebas"""
        print(f"\n📊 ANÁLISIS DE RESULTADOS")
        print(f"=" * 40)
        
        # Contar selecciones por estrategia
        strategy_selections = {}
        for result in results:
            strategy = result['selected_strategy']
            strategy_selections[strategy] = strategy_selections.get(strategy, 0) + 1
        
        print(f"\n🔍 Distribución de selecciones:")
        for strategy, count in sorted(strategy_selections.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(results)) * 100
            print(f"   {strategy:20} | {count:2d} selecciones ({percentage:4.1f}%)")
        
        # Verificar diversidad de selecciones
        unique_strategies = len(strategy_selections)
        total_strategies = len(self.strategies)
        diversity_score = unique_strategies / total_strategies
        
        print(f"\n📈 Métricas de diversidad:")
        print(f"   Estrategias únicas seleccionadas: {unique_strategies}/{total_strategies}")
        print(f"   Puntuación diversidad: {diversity_score:.2f}")
        
        # Evaluar si hay concentración excesiva
        max_selections = max(strategy_selections.values()) if strategy_selections else 0
        concentration_ratio = max_selections / len(results)
        
        print(f"   Concentración máxima: {concentration_ratio:.1%}")
        
        if concentration_ratio > 0.6:
            print(f"   ⚠️  ADVERTENCIA: Alta concentración en una estrategia")
        elif diversity_score >= 0.7:
            print(f"   ✅ Buena diversidad de selecciones")
        else:
            print(f"   ⚠️  Diversidad moderada")
        
        return {
            'strategy_selections': strategy_selections,
            'diversity_score': diversity_score,
            'concentration_ratio': concentration_ratio,
            'total_tests': len(results)
        }
    
    def run_validation(self):
        """Ejecuta la validación completa"""
        print(f"🧪 VALIDACIÓN ML STRATEGY SELECTOR OPTIMIZADO")
        print(f"=" * 60)
        print(f"Database: {self.db_path}")
        print(f"Model: {self.model_path}")
        print(f"Strategies: {len(self.strategies)} estrategias habilitadas")
        
        # 1. Validar existencia del modelo
        if not self.validate_model_exists():
            print(f"❌ Validación fallida: modelo no existe")
            return False
        
        # 2. Cargar modelo
        try:
            model = self.load_model()
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            return False
        
        # 3. Ejecutar tests de selección
        try:
            results = self.test_strategy_selection(model)
        except Exception as e:
            print(f"❌ Error ejecutando tests: {e}")
            return False
        
        # 4. Analizar resultados
        try:
            analysis = self.analyze_results(results)
        except Exception as e:
            print(f"❌ Error analizando resultados: {e}")
            return False
        
        # 5. Veredicto final
        print(f"\n🎯 VEREDICTO FINAL")
        print(f"=" * 30)
        
        success = True
        if analysis['diversity_score'] < 0.5:
            print(f"❌ Diversidad insuficiente ({analysis['diversity_score']:.2f})")
            success = False
        
        if analysis['concentration_ratio'] > 0.7:
            print(f"❌ Concentración excesiva ({analysis['concentration_ratio']:.1%})")
            success = False
        
        if success:
            print(f"✅ VALIDACIÓN EXITOSA")
            print(f"   - Modelo cargado correctamente")
            print(f"   - {analysis['total_tests']} tests ejecutados")
            print(f"   - Diversidad: {analysis['diversity_score']:.2f}")
            print(f"   - Concentración: {analysis['concentration_ratio']:.1%}")
            print(f"🚀 ML Strategy Selector listo para producción")
        else:
            print(f"⚠️  VALIDACIÓN CON ADVERTENCIAS")
            print(f"El modelo funciona pero podría necesitar ajustes")
        
        return success

def main():
    """Función principal de validación"""
    validator = StrategyValidationTest()
    success = validator.run_validation()
    
    if success:
        print(f"\n🎉 Validación completada exitosamente")
    else:
        print(f"\n⚠️  Validación completada con advertencias")

if __name__ == "__main__":
    main()