#!/usr/bin/env python3
"""
Strategy Optimizer
==================

Sistema para optimizar estrategias reales comparando con potencial teórico
y sugiriendo mejoras específicas basadas en análisis de datos.
"""

import pandas as pd
import numpy as np
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import STRATEGY_REGISTRY
from core.interfaces import MarketData, SignalType
from tools.fixed_real_strategy_backtester import FixedRealStrategyBacktester
from tools.improved_strategy_backtester import ImprovedStrategyBacktester

class StrategyOptimizer:
    """Optimizador de estrategias reales"""
    
    def __init__(self):
        self.real_backtester = FixedRealStrategyBacktester()
        self.simulated_backtester = ImprovedStrategyBacktester()
        self.analysis_results = {}
        
        # Parámetros comunes a optimizar
        self.optimization_params = {
            'volume_thresholds': [1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
            'stop_loss_pcts': [0.03, 0.04, 0.05, 0.06, 0.08],
            'take_profit_pcts': [0.08, 0.10, 0.12, 0.15, 0.20],
            'rsi_thresholds': [(20, 80), (25, 75), (30, 70), (35, 65)],
            'position_sizes': [0.01, 0.015, 0.02, 0.025, 0.03]
        }
        
    async def initialize(self):
        """Inicializar backtesters"""
        success1 = self.real_backtester.load_events_metadata()
        success2 = self.simulated_backtester.load_metadata()
        return success1 and success2
    
    async def compare_strategy_performance(self, strategy_name: str, max_events: int = 20) -> Dict:
        """Comparar rendimiento entre estrategia real y simulada"""
        
        print(f"\n🔬 ANÁLISIS COMPARATIVO: {strategy_name}")
        print("=" * 60)
        
        # Mapear nombre de estrategia real a simulada
        simulated_mapping = {
            'MACDVStrategy': 'MACDV_Momentum',
            'VolumeBreakoutStrategy': 'Volume_Breakout',
            'GapGoStrategy': 'Gap_Momentum',
            'ExplosiveVolumeStrategy': 'Explosive_Scalp',
            'VolumeMomentumStrategy': 'Volume_Breakout'
        }
        
        simulated_name = simulated_mapping.get(strategy_name, 'Volume_Breakout')
        
        # Ejecutar backtests
        print("📊 Ejecutando backtest real...")
        await self.real_backtester.run_mass_backtest(strategy_name, max_events=max_events)
        real_stats = self.real_backtester.analyze_results()
        
        print("\n📊 Ejecutando backtest simulado...")
        simulated_stats = await self.simulated_backtester.run_backtest(simulated_name, max_events=max_events)
        
        # Análisis comparativo
        comparison = {
            'strategy_name': strategy_name,
            'real_stats': real_stats,
            'simulated_stats': simulated_stats,
            'gaps': self._calculate_performance_gaps(real_stats, simulated_stats),
            'improvement_opportunities': self._identify_improvements(real_stats, simulated_stats)
        }
        
        self.analysis_results[strategy_name] = comparison
        return comparison
    
    def _calculate_performance_gaps(self, real_stats: Dict, simulated_stats: Dict) -> Dict:
        """Calcular gaps de rendimiento"""
        
        real_trades = real_stats.get('total_trades', 0)
        sim_trades = simulated_stats.get('total_trades', 0)
        
        if real_trades == 0:
            return {
                'signal_generation_gap': 100.0,  # No genera señales
                'win_rate_gap': 0,
                'return_gap': 0,
                'completion_gap': simulated_stats.get('completion_rate', 100) - real_stats.get('completion_rate', 0),
                'severity': 'CRÍTICO'
            }
        
        gaps = {
            'signal_generation_gap': ((sim_trades - real_trades) / max(sim_trades, 1)) * 100,
            'win_rate_gap': simulated_stats.get('win_rate', 0) - real_stats.get('win_rate', 0),
            'return_gap': simulated_stats.get('total_return_pct', 0) - real_stats.get('total_return_pct', 0),
            'completion_gap': simulated_stats.get('completion_rate', 100) - real_stats.get('completion_rate', 0)
        }
        
        # Determinar severidad
        if gaps['signal_generation_gap'] > 80 or gaps['return_gap'] > 3.0:
            gaps['severity'] = 'CRÍTICO'
        elif gaps['signal_generation_gap'] > 50 or gaps['return_gap'] > 1.5:
            gaps['severity'] = 'ALTO'
        elif gaps['signal_generation_gap'] > 20 or gaps['return_gap'] > 0.5:
            gaps['severity'] = 'MEDIO'
        else:
            gaps['severity'] = 'BAJO'
            
        return gaps
    
    def _identify_improvements(self, real_stats: Dict, simulated_stats: Dict) -> List[Dict]:
        """Identificar oportunidades de mejora"""
        improvements = []
        
        real_trades = real_stats.get('total_trades', 0)
        sim_trades = simulated_stats.get('total_trades', 0)
        
        # 1. Gap de generación de señales
        if real_trades < sim_trades * 0.5:
            improvements.append({
                'type': 'SIGNAL_GENERATION',
                'priority': 'ALTA',
                'issue': f'Solo genera {real_trades} señales vs {sim_trades} esperadas',
                'solutions': [
                    'Reducir thresholds de volumen',
                    'Ampliar rangos de RSI',
                    'Reducir períodos de confirmación',
                    'Incluir más timeframes'
                ]
            })
        
        # 2. Gap de win rate
        win_rate_gap = simulated_stats.get('win_rate', 0) - real_stats.get('win_rate', 0)
        if win_rate_gap > 15:
            improvements.append({
                'type': 'WIN_RATE',
                'priority': 'ALTA',
                'issue': f'Win rate {win_rate_gap:.1f}% menor que potencial',
                'solutions': [
                    'Ajustar stops más dinámicos',
                    'Mejorar timing de entrada',
                    'Añadir filtros de confirmación',
                    'Optimizar take profit levels'
                ]
            })
        
        # 3. Gap de retorno
        return_gap = simulated_stats.get('total_return_pct', 0) - real_stats.get('total_return_pct', 0)
        if return_gap > 1.0:
            improvements.append({
                'type': 'RETURN_OPTIMIZATION',
                'priority': 'MEDIA',
                'issue': f'Retorno {return_gap:.2f}% menor que potencial',
                'solutions': [
                    'Optimizar position sizing',
                    'Ajustar risk/reward ratios',
                    'Implementar trailing stops',
                    'Mejorar exit signals'
                ]
            })
        
        # 4. Gap de completion rate
        completion_gap = simulated_stats.get('completion_rate', 100) - real_stats.get('completion_rate', 0)
        if completion_gap > 30:
            improvements.append({
                'type': 'DATA_UTILIZATION',
                'priority': 'MEDIA',
                'issue': f'Solo usa {real_stats.get("completion_rate", 0):.1f}% de eventos disponibles',
                'solutions': [
                    'Mejorar filtros de calidad de datos',
                    'Reducir requisitos mínimos de barras',
                    'Ampliar ventana de horario operativo',
                    'Optimizar manejo de datos dispersos'
                ]
            })
        
        return improvements
    
    async def optimize_specific_parameters(self, strategy_name: str, param_type: str = 'volume_threshold') -> Dict:
        """Optimizar parámetros específicos de una estrategia"""
        
        print(f"\n🔧 OPTIMIZANDO {param_type.upper()} para {strategy_name}")
        print("=" * 50)
        
        base_params = {
            'max_position_value': 500.0,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.12,
        }
        
        optimization_results = []
        
        if param_type == 'volume_threshold':
            test_values = self.optimization_params['volume_thresholds']
            param_key = 'volume_threshold'
        elif param_type == 'stop_loss':
            test_values = self.optimization_params['stop_loss_pcts']
            param_key = 'stop_loss_pct'
        elif param_type == 'take_profit':
            test_values = self.optimization_params['take_profit_pcts']
            param_key = 'take_profit_pct'
        else:
            test_values = [2.0, 3.0, 4.0]  # Default
            param_key = 'volume_threshold'
        
        for value in test_values:
            test_params = base_params.copy()
            test_params[param_key] = value
            
            print(f"   🧪 Testing {param_key}={value}...")
            
            await self.real_backtester.run_mass_backtest(
                strategy_name, max_events=15, strategy_params=test_params
            )
            
            stats = self.real_backtester.analyze_results()
            
            result = {
                'parameter_value': value,
                'total_trades': stats.get('total_trades', 0),
                'win_rate': stats.get('win_rate', 0),
                'total_return_pct': stats.get('total_return_pct', 0),
                'profit_factor': stats.get('profit_factor', 0),
                'max_drawdown': stats.get('max_drawdown', 0)
            }
            
            optimization_results.append(result)
            
            if result['total_trades'] > 0:
                print(f"      Trades: {result['total_trades']}, WR: {result['win_rate']:.1f}%, Return: {result['total_return_pct']:+.2f}%")
            else:
                print(f"      No trades generated")
        
        # Encontrar mejor configuración
        valid_results = [r for r in optimization_results if r['total_trades'] > 0]
        
        if valid_results:
            best_result = max(valid_results, key=lambda x: x['total_return_pct'])
            
            print(f"\n🏆 MEJOR CONFIGURACIÓN:")
            print(f"   {param_key} = {best_result['parameter_value']}")
            print(f"   Trades: {best_result['total_trades']}")
            print(f"   Win Rate: {best_result['win_rate']:.1f}%")
            print(f"   Return: {best_result['total_return_pct']:+.2f}%")
            print(f"   Profit Factor: {best_result['profit_factor']:.2f}")
        else:
            print("❌ No se encontraron configuraciones válidas")
            best_result = None
        
        return {
            'parameter_type': param_type,
            'results': optimization_results,
            'best_config': best_result,
            'recommendations': self._generate_param_recommendations(optimization_results, param_type)
        }
    
    def _generate_param_recommendations(self, results: List[Dict], param_type: str) -> List[str]:
        """Generar recomendaciones basadas en optimización"""
        recommendations = []
        
        valid_results = [r for r in results if r['total_trades'] > 0]
        
        if not valid_results:
            recommendations.append(f"❌ Ningún valor de {param_type} genera trades - considera rangos más amplios")
            return recommendations
        
        # Análisis de trade generation
        trade_counts = [r['total_trades'] for r in valid_results]
        if max(trade_counts) - min(trade_counts) > 5:
            recommendations.append(f"📊 {param_type} tiene gran impacto en generación de señales")
        
        # Análisis de win rate
        win_rates = [r['win_rate'] for r in valid_results if r['win_rate'] > 0]
        if win_rates and max(win_rates) - min(win_rates) > 20:
            recommendations.append(f"🎯 {param_type} afecta significativamente el win rate")
        
        # Análisis de returns
        returns = [r['total_return_pct'] for r in valid_results]
        best_return = max(returns)
        worst_return = min(returns)
        
        if best_return - worst_return > 1.0:
            recommendations.append(f"💰 Optimizar {param_type} puede mejorar returns en {best_return - worst_return:.2f}%")
        
        return recommendations
    
    def print_comparison_report(self, comparison: Dict):
        """Imprimir reporte de comparación detallado"""
        
        strategy_name = comparison['strategy_name']
        real_stats = comparison['real_stats']
        sim_stats = comparison['simulated_stats']
        gaps = comparison['gaps']
        improvements = comparison['improvement_opportunities']
        
        print(f"\n📊 REPORTE DE OPTIMIZACIÓN - {strategy_name}")
        print("=" * 70)
        
        print("📈 COMPARACIÓN DE RENDIMIENTO:")
        print(f"                    {'REAL':<15} {'SIMULADO':<15} {'GAP':<15}")
        print("-" * 50)
        print(f"Total Trades        {real_stats.get('total_trades', 0):<15} {sim_stats.get('total_trades', 0):<15} {gaps['signal_generation_gap']:+.1f}%")
        print(f"Win Rate           {real_stats.get('win_rate', 0):<15.1f} {sim_stats.get('win_rate', 0):<15.1f} {gaps['win_rate_gap']:+.1f}%")
        print(f"Return Total       {real_stats.get('total_return_pct', 0):<15.2f} {sim_stats.get('total_return_pct', 0):<15.2f} {gaps['return_gap']:+.2f}%")
        print(f"Completion Rate    {real_stats.get('completion_rate', 0):<15.1f} {sim_stats.get('completion_rate', 100):<15.1f} {gaps.get('completion_gap', 0):+.1f}%")
        
        severity_colors = {
            'CRÍTICO': '🔴',
            'ALTO': '🟠', 
            'MEDIO': '🟡',
            'BAJO': '🟢'
        }
        
        print(f"\n🚨 SEVERIDAD DEL GAP: {severity_colors.get(gaps['severity'], '⚪')} {gaps['severity']}")
        
        if improvements:
            print(f"\n💡 OPORTUNIDADES DE MEJORA ({len(improvements)} identificadas):")
            for i, improvement in enumerate(improvements, 1):
                print(f"\n   {i}. {improvement['type']} (Prioridad: {improvement['priority']})")
                print(f"      ❌ Problema: {improvement['issue']}")
                print(f"      ✅ Soluciones:")
                for solution in improvement['solutions']:
                    print(f"         • {solution}")
        
        print("\n🎯 RECOMENDACIONES ESPECÍFICAS:")
        if gaps['severity'] == 'CRÍTICO':
            print("   🔴 ACCIÓN INMEDIATA REQUERIDA:")
            print("     • Revisar lógica de generación de señales")
            print("     • Reducir filtros restrictivos")
            print("     • Validar indicadores técnicos")
        elif gaps['severity'] == 'ALTO':
            print("   🟠 OPTIMIZACIÓN PRIORITARIA:")
            print("     • Ajustar parámetros principales")
            print("     • Mejorar timing de entrada/salida")
        else:
            print("   🟢 FINE-TUNING:")
            print("     • Optimizar detalles menores")
            print("     • Considerar nuevos filtros")
        
        print("=" * 70)

async def main():
    """Interfaz principal del optimizador"""
    
    print("🔬 STRATEGY OPTIMIZER")
    print("=" * 60)
    print("Sistema de optimización de estrategias reales")
    print()
    
    optimizer = StrategyOptimizer()
    
    if not await optimizer.initialize():
        print("❌ No se pudo inicializar el optimizador")
        return
    
    # Mostrar estrategias disponibles
    available_strategies = list(STRATEGY_REGISTRY.keys())
    print("📋 ESTRATEGIAS DISPONIBLES:")
    for i, strategy in enumerate(available_strategies, 1):
        print(f"   {i}. {strategy}")
    
    try:
        print(f"\n🎯 OPCIONES DE OPTIMIZACIÓN:")
        print("1. Análisis comparativo completo")
        print("2. Optimización de parámetros específicos")
        print("3. Análisis de múltiples estrategias")
        
        choice = input("\n🎯 Selecciona opción (1-3): ").strip()
        
        if choice == "1":
            # Análisis comparativo
            strategy_choice = input("Nombre o número de estrategia: ").strip()
            
            if strategy_choice.isdigit():
                idx = int(strategy_choice) - 1
                if 0 <= idx < len(available_strategies):
                    selected_strategy = available_strategies[idx]
                else:
                    selected_strategy = available_strategies[0]
            else:
                selected_strategy = None
                for strategy in available_strategies:
                    if strategy_choice.lower() in strategy.lower():
                        selected_strategy = strategy
                        break
                if not selected_strategy:
                    selected_strategy = available_strategies[0]
            
            events = input("Eventos a analizar (20 por defecto): ").strip()
            max_events = int(events) if events.isdigit() else 20
            
            comparison = await optimizer.compare_strategy_performance(selected_strategy, max_events)
            optimizer.print_comparison_report(comparison)
            
        elif choice == "2":
            # Optimización de parámetros
            strategy_choice = input("Nombre o número de estrategia: ").strip()
            
            if strategy_choice.isdigit():
                idx = int(strategy_choice) - 1
                if 0 <= idx < len(available_strategies):
                    selected_strategy = available_strategies[idx]
                else:
                    selected_strategy = available_strategies[0]
            else:
                selected_strategy = available_strategies[0]
            
            print("\n📊 PARÁMETROS DISPONIBLES:")
            print("1. volume_threshold")
            print("2. stop_loss")
            print("3. take_profit")
            
            param_choice = input("Parámetro a optimizar (1-3): ").strip()
            param_map = {'1': 'volume_threshold', '2': 'stop_loss', '3': 'take_profit'}
            param_type = param_map.get(param_choice, 'volume_threshold')
            
            result = await optimizer.optimize_specific_parameters(selected_strategy, param_type)
            
        elif choice == "3":
            # Análisis múltiple
            print("\n🔄 Analizando múltiples estrategias...")
            strategies_to_test = ['MACDVStrategy', 'VolumeBreakoutStrategy', 'GapGoStrategy']
            
            for strategy in strategies_to_test:
                if strategy in available_strategies:
                    comparison = await optimizer.compare_strategy_performance(strategy, 15)
                    print(f"\n--- RESUMEN {strategy} ---")
                    gaps = comparison['gaps']
                    print(f"Severidad: {gaps['severity']}")
                    print(f"Gap de señales: {gaps['signal_generation_gap']:+.1f}%")
                    print(f"Gap de retorno: {gaps['return_gap']:+.2f}%")
        
    except KeyboardInterrupt:
        print("\n👋 Optimización cancelada")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())