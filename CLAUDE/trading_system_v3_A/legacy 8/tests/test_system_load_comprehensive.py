#!/usr/bin/env python3
"""
Test Comprensivo de Carga del Sistema Trading Completo
Analiza la carga conjunta: Scanner + Trader + Analysis + Risk Management + Orders
Incluye simulación realista de trading en diferentes horarios del mercado
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Tuple
import random
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class SystemLoadAnalyzer:
    """
    Analiza la carga completa del sistema trading considerando:
    1. Scanner (adaptativo)
    2. Trader (posiciones activas)
    3. Analysis (ML + backtesting)
    4. Risk Management
    5. Order Management
    6. Market Data subscriptions
    """
    
    def __init__(self, logger):
        self.logger = logger
        
        # Import adaptive cache manager
        try:
            from core.adaptive_cache_manager import adaptive_cache_manager
            self.adaptive_cache = adaptive_cache_manager
        except ImportError:
            self.logger.warning("⚠️ Adaptive cache manager not available")
            self.adaptive_cache = None
        
        # IBKR Rate limits (conservador)
        self.ibkr_limits = {
            'market_data_per_minute': 100,      # Real-time market data
            'historical_data_per_minute': 60,   # Historical requests
            'account_data_per_minute': 30,      # Account/position updates
            'order_management_per_minute': 50,  # Order placement/modification
            'scanner_data_per_minute': 25,      # Market scanner data
        }
        
        # Sistema components base load (calls per minute)
        self.base_system_load = {
            'market_data_subscriptions': 15,     # Real-time quotes for positions
            'account_updates': 5,                # Portfolio, cash, positions
            'risk_management': 8,                # Stop-loss monitoring, risk checks
            'performance_tracking': 3,           # P&L, statistics updates
            'telegram_notifications': 1,        # Status updates, alerts
        }
        
        # Trading scenarios by market period
        self.trading_scenarios = {
            'premarket': {
                'active_positions': 0,           # Usually no overnight positions
                'new_positions_per_hour': 1,     # Conservative premarket trading
                'analysis_intensity': 'MEDIUM',  # Preparing for market open
                'scanner_priority': 'HIGH',      # Looking for gaps
            },
            'market_open': {
                'active_positions': 3,           # Peak trading activity
                'new_positions_per_hour': 8,     # High frequency trading
                'analysis_intensity': 'CRITICAL', # Real-time analysis crucial
                'scanner_priority': 'CRITICAL',  # Must catch breakouts
            },
            'morning_session': {
                'active_positions': 4,           # Maintaining positions
                'new_positions_per_hour': 4,     # Moderate activity
                'analysis_intensity': 'HIGH',    # Active management
                'scanner_priority': 'MEDIUM',    # Looking for new setups
            },
            'lunch_time': {
                'active_positions': 2,           # Some positions closed
                'new_positions_per_hour': 1,     # Low activity
                'analysis_intensity': 'LOW',     # Maintenance mode
                'scanner_priority': 'LOW',       # Market quiet
            },
            'afternoon': {
                'active_positions': 3,           # Re-entering positions
                'new_positions_per_hour': 3,     # Moderate activity
                'analysis_intensity': 'MEDIUM',  # Preparing for close
                'scanner_priority': 'MEDIUM',    # Finding late day plays
            },
            'power_hour': {
                'active_positions': 5,           # Maximum positions
                'new_positions_per_hour': 6,     # High activity
                'analysis_intensity': 'HIGH',    # Critical decisions
                'scanner_priority': 'HIGH',      # Late day momentum
            },
            'after_hours': {
                'active_positions': 1,           # Mostly closed out
                'new_positions_per_hour': 0,     # No new positions
                'analysis_intensity': 'LOW',     # Post-session analysis
                'scanner_priority': 'LOW',       # Limited after-hours activity
            }
        }
    
    def calculate_trader_load(self, scenario: Dict[str, Any], period_name: str) -> Dict[str, int]:
        """Calcula la carga del trader para un escenario específico"""
        
        active_positions = scenario['active_positions']
        new_positions_per_hour = scenario['new_positions_per_hour']
        analysis_intensity = scenario['analysis_intensity']
        
        # Base trader load
        trader_load = {
            'position_monitoring': active_positions * 2,        # 2 calls/min por posición activa
            'market_data_realtime': active_positions * 3,      # 3 calls/min por posición (precio, volumen)
            'stop_loss_monitoring': active_positions * 1,      # 1 call/min por stop-loss
            'new_position_analysis': new_positions_per_hour // 6, # Análisis para nuevas posiciones
            'order_management': max(1, new_positions_per_hour // 10), # Órdenes nuevas/modificaciones
        }
        
        # Analysis intensity multiplier
        intensity_multipliers = {
            'LOW': 0.5,
            'MEDIUM': 1.0,
            'HIGH': 1.5,
            'CRITICAL': 2.0
        }
        
        multiplier = intensity_multipliers.get(analysis_intensity, 1.0)
        
        # Apply intensity multiplier to analysis-heavy tasks
        analysis_tasks = ['new_position_analysis', 'position_monitoring']
        for task in analysis_tasks:
            if task in trader_load:
                trader_load[task] = int(trader_load[task] * multiplier)
        
        self.logger.info(f"   🔄 Trader load for {period_name}:")
        total_trader_load = sum(trader_load.values())
        for component, load in trader_load.items():
            self.logger.info(f"      • {component}: {load} calls/min")
        self.logger.info(f"      📊 Total trader load: {total_trader_load} calls/min")
        
        return trader_load
    
    def calculate_scanner_load(self, period_name: str) -> Dict[str, int]:
        """Calcula la carga del scanner para un período específico"""
        
        if self.adaptive_cache:
            # Usar configuración adaptativa
            period_config = self.adaptive_cache.market_periods.get(period_name, {})
            refresh_minutes = period_config.get('refresh_minutes', 15)
        else:
            refresh_minutes = 15  # Fallback
        
        # Estimación de calls por refresh del scanner
        calls_per_refresh = 4  # Market scanner + symbol details + news check + validation
        refreshes_per_hour = 60 // refresh_minutes
        scanner_calls_per_minute = (refreshes_per_hour * calls_per_refresh) / 60
        
        scanner_load = {
            'market_scanner_api': int(scanner_calls_per_minute * 0.4),    # 40% - IBKR scanner calls
            'symbol_data_fetch': int(scanner_calls_per_minute * 0.3),     # 30% - Price, volume data
            'news_data_fetch': int(scanner_calls_per_minute * 0.2),       # 20% - News APIs
            'validation_checks': int(scanner_calls_per_minute * 0.1),     # 10% - Additional validation
        }
        
        total_scanner_load = sum(scanner_load.values())
        
        self.logger.info(f"   🔍 Scanner load for {period_name} ({refresh_minutes}min intervals):")
        for component, load in scanner_load.items():
            self.logger.info(f"      • {component}: {load} calls/min")
        self.logger.info(f"      📊 Total scanner load: {total_scanner_load} calls/min")
        
        return scanner_load
    
    def calculate_total_system_load(self, period_name: str) -> Dict[str, Any]:
        """Calcula la carga total del sistema para un período"""
        
        # Get trading scenario for this period
        scenario = self.trading_scenarios.get(period_name, self.trading_scenarios['afternoon'])
        
        self.logger.info(f"📊 Calculating total system load for {period_name}")
        self.logger.info(f"   📈 Trading scenario: {scenario['active_positions']} positions, "
                        f"{scenario['new_positions_per_hour']} new/hour, "
                        f"{scenario['analysis_intensity']} analysis")
        
        # Calculate component loads
        base_load = sum(self.base_system_load.values())
        trader_load_detail = self.calculate_trader_load(scenario, period_name)
        scanner_load_detail = self.calculate_scanner_load(period_name)
        
        trader_load = sum(trader_load_detail.values())
        scanner_load = sum(scanner_load_detail.values())
        
        total_load = base_load + trader_load + scanner_load
        
        # Calculate capacity utilization
        relevant_limit = min(
            self.ibkr_limits['market_data_per_minute'],
            self.ibkr_limits['account_data_per_minute'] + self.ibkr_limits['scanner_data_per_minute']
        )
        
        utilization_percentage = (total_load / relevant_limit) * 100
        
        # Determine risk level
        if utilization_percentage < 50:
            risk_level = "LOW"
        elif utilization_percentage < 75:
            risk_level = "MEDIUM"
        elif utilization_percentage < 90:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
        
        return {
            'period_name': period_name,
            'loads': {
                'base_system': base_load,
                'trader': trader_load,
                'scanner': scanner_load,
                'total': total_load
            },
            'load_details': {
                'base_system': self.base_system_load,
                'trader': trader_load_detail,
                'scanner': scanner_load_detail
            },
            'capacity': {
                'api_limit': relevant_limit,
                'utilization_percentage': utilization_percentage,
                'available_capacity': relevant_limit - total_load,
                'risk_level': risk_level
            },
            'scenario': scenario
        }
    
    def analyze_critical_periods(self) -> Dict[str, Any]:
        """Identifica períodos críticos donde la carga puede ser problemática"""
        
        self.logger.info("🔍 Analyzing critical periods for system load...")
        
        period_analysis = {}
        critical_periods = []
        
        for period_name in self.trading_scenarios.keys():
            load_analysis = self.calculate_total_system_load(period_name)
            period_analysis[period_name] = load_analysis
            
            if load_analysis['capacity']['risk_level'] in ['HIGH', 'CRITICAL']:
                critical_periods.append({
                    'period': period_name,
                    'utilization': load_analysis['capacity']['utilization_percentage'],
                    'risk_level': load_analysis['capacity']['risk_level'],
                    'total_load': load_analysis['loads']['total']
                })
        
        # Sort by utilization
        critical_periods.sort(key=lambda x: x['utilization'], reverse=True)
        
        self.logger.info(f"⚠️ Found {len(critical_periods)} critical periods:")
        for cp in critical_periods:
            self.logger.info(f"   🚨 {cp['period']}: {cp['utilization']:.1f}% utilization ({cp['risk_level']})")
        
        return {
            'all_periods': period_analysis,
            'critical_periods': critical_periods,
            'max_utilization': max(pa['capacity']['utilization_percentage'] for pa in period_analysis.values()),
            'average_utilization': sum(pa['capacity']['utilization_percentage'] for pa in period_analysis.values()) / len(period_analysis)
        }
    
    def recommend_optimizations(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Recomienda optimizaciones basadas en el análisis de carga"""
        
        recommendations = []
        
        max_utilization = analysis['max_utilization']
        critical_periods = analysis['critical_periods']
        
        if max_utilization > 90:
            recommendations.append({
                'priority': 'CRITICAL',
                'category': 'Rate Limiting',
                'issue': f'Peak utilization {max_utilization:.1f}% exceeds safe limits',
                'solution': 'Implement request queuing and priority-based throttling'
            })
        
        if len(critical_periods) > 2:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Adaptive Cache',
                'issue': f'{len(critical_periods)} periods with high load',
                'solution': 'Increase cache intervals during peak trading periods'
            })
        
        # Check specific high-load periods
        market_open_data = analysis['all_periods'].get('market_open', {})
        if market_open_data.get('capacity', {}).get('utilization_percentage', 0) > 80:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Market Open',
                'issue': 'Market open period shows excessive load',
                'solution': 'Consider 4-5min scanner intervals during market open instead of 3min'
            })
        
        power_hour_data = analysis['all_periods'].get('power_hour', {})
        if power_hour_data.get('capacity', {}).get('utilization_percentage', 0) > 75:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Power Hour',
                'issue': 'Power hour period approaching capacity limits',
                'solution': 'Reduce non-essential analysis during power hour'
            })
        
        # Check if scanner load is disproportionate
        avg_scanner_percentage = 0
        for period_data in analysis['all_periods'].values():
            scanner_load = period_data['loads']['scanner']
            total_load = period_data['loads']['total']
            avg_scanner_percentage += (scanner_load / total_load) * 100
        
        avg_scanner_percentage /= len(analysis['all_periods'])
        
        if avg_scanner_percentage > 40:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Scanner Optimization',
                'issue': f'Scanner represents {avg_scanner_percentage:.1f}% of total load',
                'solution': 'Implement more aggressive caching for scanner results'
            })
        
        return recommendations

async def run_comprehensive_load_test():
    """Test principal de carga comprensiva del sistema"""
    logger = setup_logging()
    
    print("🏗️ ANÁLISIS COMPRENSIVO DE CARGA DEL SISTEMA TRADING")
    print("=" * 70)
    print("Scanner + Trader + Analysis + Risk Management + Orders")
    print("Simulación realista de carga por período del mercado")
    print("=" * 70)
    
    analyzer = SystemLoadAnalyzer(logger)
    
    # Realizar análisis completo
    logger.info("🔍 Starting comprehensive system load analysis...")
    analysis = analyzer.analyze_critical_periods()
    
    # Generar recomendaciones
    logger.info("\n💡 Generating optimization recommendations...")
    recommendations = analyzer.recommend_optimizations(analysis)
    
    # Resumen ejecutivo
    print("\n" + "=" * 70)
    print("📊 RESUMEN EJECUTIVO - CARGA DEL SISTEMA")
    print("=" * 70)
    
    print(f"🎯 Utilización máxima: {analysis['max_utilization']:.1f}%")
    print(f"📈 Utilización promedio: {analysis['average_utilization']:.1f}%")
    print(f"⚠️ Períodos críticos: {len(analysis['critical_periods'])}")
    
    if analysis['critical_periods']:
        print(f"\n🚨 PERÍODOS DE MAYOR RIESGO:")
        for cp in analysis['critical_periods'][:3]:  # Top 3
            print(f"   • {cp['period'].upper()}: {cp['utilization']:.1f}% ({cp['risk_level']})")
    
    print(f"\n💡 RECOMENDACIONES ({len(recommendations)}):")
    for rec in recommendations:
        priority_icon = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📋"}.get(rec['priority'], "📝")
        print(f"   {priority_icon} {rec['category']}: {rec['solution']}")
    
    # Decisión sobre cache adaptativo actual
    if analysis['max_utilization'] < 80:
        print(f"\n✅ CACHE ADAPTATIVO ACTUAL: ÓPTIMO")
        print("   El sistema actual (3min market open) es sostenible")
        print("   Balance correcto entre detección y carga API")
    elif analysis['max_utilization'] < 90:
        print(f"\n⚠️ CACHE ADAPTATIVO ACTUAL: ACEPTABLE CON MONITOREO")
        print("   Funcional pero cerca de límites, monitorear en producción")
    else:
        print(f"\n🚨 CACHE ADAPTATIVO ACTUAL: NECESITA AJUSTES")
        print("   Considerar intervalos más conservadores")
    
    print("=" * 70)
    
    # Guardar análisis detallado
    with open('system_load_analysis.json', 'w') as f:
        json.dump({
            'analysis': analysis,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2, default=str)
    
    logger.info("💾 Detailed analysis saved to system_load_analysis.json")
    
    return analysis['max_utilization'] < 90  # Return success if under 90% utilization

async def main():
    """Main function"""
    try:
        success = await run_comprehensive_load_test()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error in comprehensive load test: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)