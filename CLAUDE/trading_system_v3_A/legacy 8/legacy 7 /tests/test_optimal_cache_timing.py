#!/usr/bin/env python3
"""
Test para determinar el timing óptimo de cache refresh para smallcaps
Simula diferentes escenarios de timing para encontrar el balance perfecto
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class SmallcapTimingAnalyzer:
    """
    Analiza diferentes timing de cache refresh para smallcaps
    """
    
    def __init__(self, logger):
        self.logger = logger
        
        # Escenarios de timing a probar
        self.timing_scenarios = {
            'aggressive': 5 * 60,    # 5 minutos
            'balanced': 10 * 60,     # 10 minutos  
            'conservative': 15 * 60, # 15 minutos
            'ultra_fast': 3 * 60,    # 3 minutos (experimental)
        }
        
        # Tipos de events de smallcaps y su duración típica
        self.smallcap_events = {
            'breaking_news': 2,      # 2 minutos para actuar
            'volume_spike': 5,       # 5 minutos ventana
            'premarket_gap': 8,      # 8 minutos premarket
            'catalyst_reaction': 3,  # 3 minutos post-catalyst
            'momentum_breakout': 7,  # 7 minutos momentum
        }
        
    def analyze_detection_delay(self) -> Dict[str, Any]:
        """
        Analiza el delay de detección para cada timing
        """
        self.logger.info("📊 Analizando delay de detección para diferentes timings...")
        
        results = {}
        
        for timing_name, refresh_interval_sec in self.timing_scenarios.items():
            refresh_minutes = refresh_interval_sec // 60
            self.logger.info(f"   🔍 Analizando timing: {timing_name} ({refresh_minutes}min)")
            
            missed_opportunities = 0
            caught_opportunities = 0
            
            for event_type, event_duration_min in self.smallcap_events.items():
                # Simular: ¿El refresh interval permite capturar este event?
                if refresh_minutes <= event_duration_min:
                    caught_opportunities += 1
                    status = "✅ CAUGHT"
                else:
                    missed_opportunities += 1
                    status = "❌ MISSED"
                
                self.logger.info(f"      {status}: {event_type} (dura {event_duration_min}min)")
            
            success_rate = (caught_opportunities / len(self.smallcap_events)) * 100
            
            results[timing_name] = {
                'refresh_minutes': refresh_minutes,
                'caught': caught_opportunities,
                'missed': missed_opportunities,
                'success_rate': success_rate
            }
            
            self.logger.info(f"      📈 Success rate: {success_rate:.1f}% ({caught_opportunities}/{len(self.smallcap_events)})")
        
        return results
    
    def calculate_api_impact(self) -> Dict[str, Any]:
        """
        Calcula el impacto en número de API calls por timing
        """
        self.logger.info("📊 Calculando impacto en API calls...")
        
        # Assumptions para cálculo
        market_hours = 6.5  # 9:30-16:00 EST
        market_minutes = market_hours * 60  # 390 minutos
        
        api_impact = {}
        
        for timing_name, refresh_interval_sec in self.timing_scenarios.items():
            refresh_minutes = refresh_interval_sec // 60
            
            # Calcular calls por día de mercado
            calls_per_day = market_minutes // refresh_minutes
            
            # Estimar costo (asumiendo 2-3 calls por refresh)
            estimated_calls_per_refresh = 3
            total_daily_calls = calls_per_day * estimated_calls_per_refresh
            
            api_impact[timing_name] = {
                'refresh_minutes': refresh_minutes,
                'calls_per_day': calls_per_day,
                'total_daily_calls': total_daily_calls,
                'load_level': self._get_load_level(total_daily_calls)
            }
            
            self.logger.info(f"   📞 {timing_name}: {calls_per_day} refreshes/día = ~{total_daily_calls} API calls ({api_impact[timing_name]['load_level']})")
        
        return api_impact
    
    def _get_load_level(self, daily_calls: int) -> str:
        """Clasifica el nivel de carga de API"""
        if daily_calls < 100:
            return "LOW"
        elif daily_calls < 300:
            return "MEDIUM"
        elif daily_calls < 500:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def recommend_optimal_timing(self, detection_results: Dict, api_impact: Dict) -> Dict[str, Any]:
        """
        Recomienda el timing óptimo basado en análisis
        """
        self.logger.info("🎯 Calculando recomendación óptima...")
        
        # Score cada timing (balance entre success rate y API impact)
        recommendations = {}
        
        for timing_name in self.timing_scenarios.keys():
            success_rate = detection_results[timing_name]['success_rate']
            load_level = api_impact[timing_name]['load_level']
            
            # Scoring system
            load_penalty = {
                'LOW': 0,
                'MEDIUM': -10,
                'HIGH': -25,
                'VERY_HIGH': -50
            }
            
            total_score = success_rate + load_penalty.get(load_level, -50)
            
            recommendations[timing_name] = {
                'success_rate': success_rate,
                'load_level': load_level,
                'total_score': total_score,
                'refresh_minutes': detection_results[timing_name]['refresh_minutes']
            }
            
            self.logger.info(f"   📊 {timing_name}: Score {total_score:.1f} (success: {success_rate:.1f}%, load: {load_level})")
        
        # Find best option
        best_timing = max(recommendations.keys(), key=lambda k: recommendations[k]['total_score'])
        
        return {
            'recommended': best_timing,
            'all_scores': recommendations,
            'best_config': recommendations[best_timing]
        }

async def main():
    """Test principal para timing óptimo"""
    logger = setup_logging()
    
    print("🧪 ANÁLISIS DE TIMING ÓPTIMO PARA SMALLCAPS")
    print("=" * 60)
    print("Determinando el mejor intervalo de cache refresh")
    print("Considerando: velocidad de detección vs carga de API")
    print("=" * 60)
    
    analyzer = SmallcapTimingAnalyzer(logger)
    
    # 1. Análisis de detección
    logger.info("🔍 PASO 1: Análisis de capacidad de detección")
    detection_results = analyzer.analyze_detection_delay()
    
    # 2. Análisis de impacto API
    logger.info("\n📞 PASO 2: Análisis de impacto en API calls")
    api_impact = analyzer.calculate_api_impact()
    
    # 3. Recomendación final
    logger.info("\n🎯 PASO 3: Generando recomendación óptima")
    recommendation = analyzer.recommend_optimal_timing(detection_results, api_impact)
    
    # Resumen final
    print("\n" + "=" * 60)
    print("🏆 RECOMENDACIÓN FINAL")
    print("=" * 60)
    
    best = recommendation['recommended']
    best_config = recommendation['best_config']
    
    print(f"✅ TIMING RECOMENDADO: {best}")
    print(f"   📊 Refresh cada: {best_config['refresh_minutes']} minutos")
    print(f"   📈 Success rate: {best_config['success_rate']:.1f}%")
    print(f"   📞 Load level: {best_config['load_level']}")
    print(f"   🎯 Score total: {best_config['total_score']:.1f}")
    
    print(f"\n🔧 IMPLEMENTACIÓN:")
    print(f"   Cambiar _cache_refresh_interval = {best_config['refresh_minutes']} * 60")
    print(f"   En ambos archivos: ibkr_native_scanner.py y smallcap_daily_scanner.py")
    
    if best_config['success_rate'] < 80:
        print(f"\n⚠️ ADVERTENCIA: Success rate bajo ({best_config['success_rate']:.1f}%)")
        print("   Considera timing más agresivo si pierdes oportunidades")
    
    if best_config['load_level'] in ['HIGH', 'VERY_HIGH']:
        print(f"\n⚠️ ADVERTENCIA: High API load ({best_config['load_level']})")
        print("   Monitorea rate limits y costos de API")
    
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)