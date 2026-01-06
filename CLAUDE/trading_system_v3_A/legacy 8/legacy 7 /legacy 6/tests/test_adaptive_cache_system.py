#!/usr/bin/env python3
"""
Test para Sistema de Cache Adaptativo - Balanceo inteligente
Considera la carga total del sistema trading + análisis + scanner
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta, time
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class AdaptiveCacheAnalyzer:
    """
    Analiza sistema de cache adaptativo que considera:
    1. Carga total del sistema
    2. Horarios críticos del mercado
    3. Volatilidad actual
    4. Rate limits de IBKR
    """
    
    def __init__(self, logger):
        self.logger = logger
        
        # Estimaciones de carga actual del sistema
        self.system_load = {
            'trader_api_calls_per_minute': 20,      # Monitoreo posiciones, precios
            'analysis_api_calls_per_minute': 10,    # Análisis de trades
            'risk_management_calls_per_minute': 5,  # Risk checks
            'order_management_calls_per_minute': 3, # Órdenes ocasionales
        }
        
        # Rate limits estimados de IBKR (conservador)
        self.ibkr_limits = {
            'market_data_per_minute': 100,      # 100 req/min market data
            'historical_data_per_minute': 60,   # 60 req/min historical
            'scanner_data_per_minute': 30,      # 30 req/min scanner (más restrictivo)
        }
        
        # Horarios críticos para trading de smallcaps
        self.market_periods = {
            'premarket': {'start': time(4, 0), 'end': time(9, 30), 'intensity': 'HIGH'},
            'market_open': {'start': time(9, 30), 'end': time(10, 30), 'intensity': 'CRITICAL'},
            'morning_session': {'start': time(10, 30), 'end': time(12, 0), 'intensity': 'MEDIUM'},
            'lunch_time': {'start': time(12, 0), 'end': time(14, 0), 'intensity': 'LOW'},
            'afternoon': {'start': time(14, 0), 'end': time(15, 30), 'intensity': 'MEDIUM'},
            'power_hour': {'start': time(15, 30), 'end': time(16, 0), 'intensity': 'HIGH'},
        }
        
    def calculate_current_system_load(self) -> Dict[str, Any]:
        """Calcula la carga actual total del sistema"""
        
        total_calls_per_minute = sum(self.system_load.values())
        
        # Calcular disponibilidad restante
        available_market_data = self.ibkr_limits['market_data_per_minute'] - total_calls_per_minute
        available_scanner = self.ibkr_limits['scanner_data_per_minute'] - (total_calls_per_minute * 0.3)  # 30% uso scanner
        
        self.logger.info(f"📊 Carga actual del sistema:")
        for component, calls in self.system_load.items():
            self.logger.info(f"   • {component}: {calls} calls/min")
        
        self.logger.info(f"   📈 Total sistema: {total_calls_per_minute} calls/min")
        self.logger.info(f"   🔓 Disponible market data: {available_market_data:.1f} calls/min")
        self.logger.info(f"   🔓 Disponible scanner: {available_scanner:.1f} calls/min")
        
        return {
            'total_current_load': total_calls_per_minute,
            'available_market_data': max(0, available_market_data),
            'available_scanner': max(0, available_scanner),
            'load_percentage': (total_calls_per_minute / self.ibkr_limits['market_data_per_minute']) * 100
        }
    
    def design_adaptive_cache_strategy(self, system_load: Dict) -> Dict[str, Any]:
        """Diseña estrategia de cache adaptativo"""
        
        self.logger.info("🎯 Diseñando estrategia de cache adaptativo...")
        
        # Calcular refresh intervals por período
        adaptive_strategy = {}
        
        for period_name, period_info in self.market_periods.items():
            intensity = period_info['intensity']
            
            # Asignar refresh interval basado en intensidad + carga disponible
            if intensity == 'CRITICAL' and system_load['available_scanner'] > 10:
                refresh_minutes = 2  # Muy agresivo solo si hay capacidad
            elif intensity == 'HIGH' and system_load['available_scanner'] > 5:
                refresh_minutes = 5  # Agresivo con capacidad
            elif intensity == 'MEDIUM':
                refresh_minutes = 8  # Moderado
            else:  # LOW intensity o poca capacidad disponible
                refresh_minutes = 15 # Conservador
                
            adaptive_strategy[period_name] = {
                'refresh_minutes': refresh_minutes,
                'intensity': intensity,
                'start': period_info['start'].strftime('%H:%M'),
                'end': period_info['end'].strftime('%H:%M'),
                'estimated_calls_per_hour': (60 // refresh_minutes) * 3  # 3 calls por refresh
            }
            
            self.logger.info(f"   • {period_name} ({intensity}): {refresh_minutes}min refresh")
        
        return adaptive_strategy
    
    def calculate_daily_api_impact(self, adaptive_strategy: Dict) -> Dict[str, Any]:
        """Calcula impacto total de API calls por día"""
        
        total_daily_calls = 0
        period_breakdown = {}
        
        for period_name, config in adaptive_strategy.items():
            # Calcular duración del período
            start_time = datetime.strptime(config['start'], '%H:%M').time()
            end_time = datetime.strptime(config['end'], '%H:%M').time()
            
            # Calcular duración en minutos
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            duration_minutes = end_minutes - start_minutes
            
            # Calcular calls en este período
            refreshes_in_period = duration_minutes // config['refresh_minutes']
            calls_in_period = refreshes_in_period * 3  # 3 calls por refresh
            
            period_breakdown[period_name] = {
                'duration_minutes': duration_minutes,
                'refreshes': refreshes_in_period,
                'api_calls': calls_in_period,
                'refresh_minutes': config['refresh_minutes']
            }
            
            total_daily_calls += calls_in_period
            
            self.logger.info(f"   📞 {period_name}: {calls_in_period} calls ({refreshes_in_period} refreshes)")
        
        return {
            'total_daily_scanner_calls': total_daily_calls,
            'period_breakdown': period_breakdown,
            'average_calls_per_hour': total_daily_calls / 11.5  # ~11.5 horas de trading
        }
    
    def compare_with_fixed_intervals(self, adaptive_impact: Dict) -> Dict[str, Any]:
        """Compara con intervalos fijos"""
        
        self.logger.info("⚖️ Comparando con intervalos fijos...")
        
        market_minutes = 11.5 * 60  # 690 minutos de trading extendido
        
        fixed_scenarios = {
            '3_minutes': (market_minutes // 3) * 3,
            '5_minutes': (market_minutes // 5) * 3, 
            '10_minutes': (market_minutes // 10) * 3,
            '15_minutes': (market_minutes // 15) * 3,
        }
        
        adaptive_calls = adaptive_impact['total_daily_scanner_calls']
        
        comparison = {}
        for scenario, calls in fixed_scenarios.items():
            difference = calls - adaptive_calls
            percentage_diff = (difference / adaptive_calls) * 100 if adaptive_calls > 0 else 0
            
            comparison[scenario] = {
                'daily_calls': int(calls),
                'difference_vs_adaptive': int(difference),
                'percentage_diff': percentage_diff
            }
            
            status = "🔴 MÁS" if difference > 0 else "🟢 MENOS"
            self.logger.info(f"   {status} {scenario}: {int(calls)} calls ({percentage_diff:+.1f}%)")
        
        self.logger.info(f"   🎯 Adaptativo: {adaptive_calls} calls (BASELINE)")
        
        return comparison

async def main():
    """Test principal para cache adaptativo"""
    logger = setup_logging()
    
    print("🧠 ANÁLISIS DE CACHE ADAPTATIVO - SISTEMA COMPLETO")
    print("=" * 65)
    print("Considerando: Scanner + Trader + Analysis + Rate Limits IBKR")
    print("=" * 65)
    
    analyzer = AdaptiveCacheAnalyzer(logger)
    
    # 1. Analizar carga actual del sistema
    logger.info("🔍 PASO 1: Analizando carga actual del sistema completo")
    system_load = analyzer.calculate_current_system_load()
    
    if system_load['load_percentage'] > 80:
        logger.warning("⚠️ SISTEMA CON ALTA CARGA - Cache muy conservador recomendado")
    
    # 2. Diseñar estrategia adaptativa
    logger.info("\n🎯 PASO 2: Diseñando cache adaptativo")
    adaptive_strategy = analyzer.design_adaptive_cache_strategy(system_load)
    
    # 3. Calcular impacto total
    logger.info("\n📊 PASO 3: Calculando impacto total de API")
    adaptive_impact = analyzer.calculate_daily_api_impact(adaptive_strategy)
    
    # 4. Comparar con intervalos fijos
    logger.info("\n⚖️ PASO 4: Comparando con estrategias fijas")
    comparison = analyzer.compare_with_fixed_intervals(adaptive_impact)
    
    # Recomendación final
    print("\n" + "=" * 65)
    print("🏆 RECOMENDACIÓN: CACHE ADAPTATIVO")
    print("=" * 65)
    
    print("📊 HORARIOS Y REFRESH INTERVALS:")
    for period, config in adaptive_strategy.items():
        print(f"   • {config['start']}-{config['end']} ({config['intensity']}): {config['refresh_minutes']}min")
    
    print(f"\n📞 IMPACTO API DIARIO:")
    print(f"   • Total scanner calls: {adaptive_impact['total_daily_scanner_calls']}")
    print(f"   • Promedio por hora: {adaptive_impact['average_calls_per_hour']:.1f}")
    print(f"   • Carga sistema actual: {system_load['load_percentage']:.1f}%")
    
    print(f"\n🎯 VENTAJAS vs CACHE FIJO:")
    print("   ✅ Más eficiente durante horas tranquilas")
    print("   ✅ Más agresivo durante horas críticas")
    print("   ✅ Se adapta a la carga real del sistema")
    print("   ✅ Respeta rate limits de IBKR")
    
    if system_load['available_scanner'] < 5:
        print(f"\n⚠️ ADVERTENCIA: Poca capacidad disponible ({system_load['available_scanner']:.1f} calls/min)")
        print("   Considera optimizar otros componentes del sistema")
    
    print("=" * 65)
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)