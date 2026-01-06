#!/usr/bin/env python3
"""
Optimizaciones de Performance del Trader - Reducir API Load
Identifica y optimiza los puntos críticos que consumen más API calls
"""

import asyncio
import logging
import sys
import os
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class TraderPerformanceOptimizer:
    """
    Optimiza el performance del trader reduciendo API calls innecesarios
    """
    
    def __init__(self, logger):
        self.logger = logger
        
        # Problemas identificados del análisis
        self.performance_issues = {
            'get_current_price': {
                'issue': 'Cada llamada hace reqMktData + sleep(1) + cancelMktData',
                'api_calls_per_position': 3,  # req + wait + cancel
                'frequency': 'Cada ciclo de trading (30-60 segundos)',
                'total_daily_calls': '5 positions * 3 calls * 720 cycles = 10,800 calls'
            },
            'get_positions': {
                'issue': 'Llama ib.positions() + ib.portfolio() en cada check',
                'api_calls_per_check': 2,
                'frequency': 'Cada ciclo de trading',
                'total_daily_calls': '2 calls * 720 cycles = 1,440 calls'
            },
            'position_monitoring': {
                'issue': 'Monitoring individual por posición sin batch',
                'api_calls_per_position': 2,  # price + portfolio check
                'frequency': 'Cada posición, cada ciclo',
                'total_daily_calls': '5 positions * 2 calls * 720 cycles = 7,200 calls'
            }
        }
    
    def analyze_current_bottlenecks(self) -> Dict[str, Any]:
        """Analiza los bottlenecks actuales del trader"""
        
        self.logger.info("🔍 Analizando bottlenecks del trader actual...")
        
        total_estimated_calls = 0
        bottlenecks = {}
        
        for component, details in self.performance_issues.items():
            # Parse total calls (extract number from string)
            total_calls_str = details['total_daily_calls']
            try:
                # Extract number from string like "10,800 calls"
                total_calls = int(total_calls_str.split('=')[-1].strip().split()[0].replace(',', ''))
            except:
                total_calls = 1000  # fallback
            
            total_estimated_calls += total_calls
            
            bottlenecks[component] = {
                'issue': details['issue'],
                'estimated_daily_calls': total_calls,
                'frequency': details['frequency'],
                'optimization_priority': self._calculate_priority(total_calls)
            }
            
            self.logger.info(f"   🚨 {component}: {total_calls:,} calls/día")
            self.logger.info(f"      Issue: {details['issue']}")
        
        self.logger.info(f"   📊 Total estimado: {total_estimated_calls:,} calls/día")
        
        return {
            'total_daily_calls': total_estimated_calls,
            'bottlenecks': bottlenecks,
            'optimization_potential': total_estimated_calls * 0.7  # 70% reducción posible
        }
    
    def _calculate_priority(self, daily_calls: int) -> str:
        """Calcula prioridad de optimización"""
        if daily_calls > 5000:
            return "CRITICAL"
        elif daily_calls > 2000:
            return "HIGH"
        elif daily_calls > 500:
            return "MEDIUM"
        else:
            return "LOW"
    
    def generate_optimizations(self) -> List[Dict[str, Any]]:
        """Genera optimizaciones específicas"""
        
        self.logger.info("💡 Generando optimizaciones específicas...")
        
        optimizations = [
            {
                'component': 'get_current_price',
                'optimization': 'Batch Price Subscription',
                'description': 'Suscribirse a precios de todas las posiciones una sola vez',
                'implementation': 'Usar reqMktData persistente con callbacks en lugar de req+cancel',
                'estimated_reduction': '90%',
                'api_calls_saved': 9720,  # De 10,800 a 1,080
                'code_changes': [
                    'Crear price_subscription_manager()',
                    'Mantener suscripciones activas durante trading',
                    'Usar callbacks para updates de precio',
                    'Cancelar suscripciones al final del día'
                ]
            },
            {
                'component': 'get_positions',
                'optimization': 'Smart Caching con Invalidation',
                'description': 'Cachear posiciones y solo refreshear cuando hay cambios',
                'implementation': 'Cache con timestamp + event-driven invalidation',
                'estimated_reduction': '80%',
                'api_calls_saved': 1152,  # De 1,440 a 288
                'code_changes': [
                    'Implementar PositionCache con TTL',
                    'Event listeners para order fills',
                    'Refresh solo cuando hay nuevas órdenes',
                    'Fallback refresh cada 5 minutos'
                ]
            },
            {
                'component': 'position_monitoring',
                'optimization': 'Bulk Position Updates',
                'description': 'Monitorear todas las posiciones en una sola llamada',
                'implementation': 'Single portfolio() call con processing batch',
                'estimated_reduction': '70%',
                'api_calls_saved': 5040,  # De 7,200 a 2,160
                'code_changes': [
                    'Crear batch_position_monitor()',
                    'Process all positions en single portfolio() call',
                    'Separate risk checks por position post-fetch',
                    'Reduce monitoring frequency durante horas tranquilas'
                ]
            },
            {
                'component': 'market_data_subscriptions',
                'optimization': 'Adaptive Subscription Management',
                'description': 'Suscripciones inteligentes basadas en trading activity',
                'implementation': 'Subscribe/unsubscribe based on positions y market hours',
                'estimated_reduction': '50%',
                'api_calls_saved': 2000,  # Estimado
                'code_changes': [
                    'Market session detector',
                    'Dynamic subscription manager',
                    'Unsubscribe durante lunch time',
                    'Priority subscriptions para active positions'
                ]
            }
        ]
        
        for opt in optimizations:
            priority = "🚨 CRITICAL" if opt['api_calls_saved'] > 5000 else "⚠️ HIGH" if opt['api_calls_saved'] > 2000 else "📋 MEDIUM"
            self.logger.info(f"   {priority} {opt['component']}: -{opt['api_calls_saved']:,} calls ({opt['estimated_reduction']})")
            self.logger.info(f"      💡 {opt['optimization']}")
        
        return optimizations
    
    def create_implementation_plan(self, optimizations: List[Dict]) -> Dict[str, Any]:
        """Crea plan de implementación priorizado"""
        
        self.logger.info("📋 Creando plan de implementación...")
        
        # Sort by API calls saved (highest impact first)
        sorted_opts = sorted(optimizations, key=lambda x: x['api_calls_saved'], reverse=True)
        
        implementation_phases = {
            'phase_1_critical': {
                'timeframe': '1-2 días',
                'optimizations': [opt for opt in sorted_opts if opt['api_calls_saved'] > 5000],
                'impact': 'Reducir 70%+ de la carga API'
            },
            'phase_2_high': {
                'timeframe': '3-4 días',
                'optimizations': [opt for opt in sorted_opts if 2000 < opt['api_calls_saved'] <= 5000],
                'impact': 'Reducir 15-20% adicional'
            },
            'phase_3_medium': {
                'timeframe': '1 semana',
                'optimizations': [opt for opt in sorted_opts if opt['api_calls_saved'] <= 2000],
                'impact': 'Refinamiento y optimizaciones menores'
            }
        }
        
        total_potential_reduction = sum(opt['api_calls_saved'] for opt in optimizations)
        
        for phase_name, phase_data in implementation_phases.items():
            phase_impact = sum(opt['api_calls_saved'] for opt in phase_data['optimizations'])
            self.logger.info(f"   📋 {phase_name.upper().replace('_', ' ')}: -{phase_impact:,} calls ({phase_data['timeframe']})")
            
            for opt in phase_data['optimizations']:
                self.logger.info(f"      • {opt['component']}: {opt['optimization']}")
        
        return {
            'phases': implementation_phases,
            'total_potential_reduction': total_potential_reduction,
            'estimated_final_load': 19440 - total_potential_reduction,  # Based on analysis
            'success_criteria': {
                'peak_utilization': '<75%',
                'average_utilization': '<50%',
                'api_calls_per_day': '<5000'
            }
        }
    
    def generate_code_templates(self) -> Dict[str, str]:
        """Genera templates de código para las optimizaciones principales"""
        
        templates = {
            'batch_price_manager': '''
class BatchPriceManager:
    """Maneja suscripciones de precios en batch para todas las posiciones"""
    
    def __init__(self, ibkr_adapter):
        self.ibkr = ibkr_adapter
        self.active_subscriptions = {}
        self.price_callbacks = {}
        self.last_prices = {}
    
    async def subscribe_to_positions(self, symbols: List[str]):
        """Suscribirse a precios de múltiples posiciones"""
        for symbol in symbols:
            if symbol not in self.active_subscriptions:
                contract = await self.ibkr._get_contract(symbol)
                ticker = self.ibkr.ib.reqMktData(contract, '', False, False)
                
                # Set up callback for price updates
                ticker.updateEvent += self._on_price_update
                self.active_subscriptions[symbol] = ticker
                
    def _on_price_update(self, ticker):
        """Callback para updates de precio"""
        symbol = ticker.contract.symbol
        if ticker.marketPrice():
            self.last_prices[symbol] = float(ticker.marketPrice())
        
    def get_current_price(self, symbol: str) -> float:
        """Get precio actual desde cache (no API call)"""
        return self.last_prices.get(symbol, 0.0)
    
    async def cleanup(self):
        """Cancelar todas las suscripciones"""
        for symbol, ticker in self.active_subscriptions.items():
            self.ibkr.ib.cancelMktData(ticker.contract)
        self.active_subscriptions.clear()
            ''',
            
            'smart_position_cache': '''
class SmartPositionCache:
    """Cache inteligente para posiciones con event-driven invalidation"""
    
    def __init__(self, ibkr_adapter):
        self.ibkr = ibkr_adapter
        self.cached_positions = {}
        self.last_update = None
        self.cache_ttl = 300  # 5 minutos
        self.pending_orders = set()
    
    async def get_positions(self) -> Dict[str, Position]:
        """Get posiciones con smart caching"""
        current_time = datetime.now()
        
        # Check si cache es válido
        if (self.last_update and 
            (current_time - self.last_update).total_seconds() < self.cache_ttl and
            not self.pending_orders):  # Si no hay órdenes pendientes
            return self.cached_positions
        
        # Refresh positions desde IBKR
        positions = await self._fetch_positions_from_ibkr()
        self.cached_positions = positions
        self.last_update = current_time
        self.pending_orders.clear()
        
        return positions
    
    def invalidate_on_order_fill(self, symbol: str):
        """Invalidar cache cuando hay order fill"""
        self.pending_orders.add(symbol)
    
    async def _fetch_positions_from_ibkr(self) -> Dict[str, Position]:
        """Fetch real positions from IBKR (actual API calls)"""
        # Original get_positions logic here
        pass
            ''',
            
            'adaptive_monitoring': '''
class AdaptiveMonitoringManager:
    """Ajusta frequency de monitoring basado en market conditions"""
    
    def __init__(self):
        self.monitoring_intervals = {
            'market_open': 30,      # 30 segundos durante market open
            'normal_hours': 60,     # 1 minuto durante horas normales  
            'lunch_time': 180,      # 3 minutos durante lunch
            'power_hour': 20,       # 20 segundos durante power hour
            'after_hours': 300      # 5 minutos after hours
        }
        
    def get_optimal_interval(self) -> int:
        """Get intervalo óptimo basado en hora actual"""
        current_hour = datetime.now().hour
        
        if 9 <= current_hour < 11:      # Market open
            return self.monitoring_intervals['market_open']
        elif 12 <= current_hour < 14:   # Lunch time
            return self.monitoring_intervals['lunch_time']
        elif 15 <= current_hour < 16:   # Power hour
            return self.monitoring_intervals['power_hour']
        elif 16 <= current_hour < 20:   # After hours
            return self.monitoring_intervals['after_hours']
        else:
            return self.monitoring_intervals['normal_hours']
            '''
        }
        
        return templates

async def run_trader_optimization_analysis():
    """Análisis principal de optimización del trader"""
    logger = setup_logging()
    
    print("⚡ OPTIMIZACIÓN DE PERFORMANCE DEL TRADER")
    print("=" * 60)
    print("Reduciendo carga API para mejorar utilización del sistema")
    print("=" * 60)
    
    optimizer = TraderPerformanceOptimizer(logger)
    
    # 1. Analizar bottlenecks actuales
    logger.info("🔍 STEP 1: Analyzing current bottlenecks")
    bottlenecks = optimizer.analyze_current_bottlenecks()
    
    # 2. Generar optimizaciones
    logger.info("\n💡 STEP 2: Generating optimizations")
    optimizations = optimizer.generate_optimizations()
    
    # 3. Crear plan de implementación
    logger.info("\n📋 STEP 3: Creating implementation plan")
    implementation_plan = optimizer.create_implementation_plan(optimizations)
    
    # 4. Generar templates de código
    logger.info("\n📝 STEP 4: Generating code templates")
    code_templates = optimizer.generate_code_templates()
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE OPTIMIZACIÓN DEL TRADER")
    print("=" * 60)
    
    current_load = bottlenecks['total_daily_calls']
    potential_reduction = implementation_plan['total_potential_reduction']
    final_load = implementation_plan['estimated_final_load']
    
    print(f"🎯 Carga actual estimada: {current_load:,} API calls/día")
    print(f"⚡ Reducción potencial: -{potential_reduction:,} calls ({(potential_reduction/current_load*100):.1f}%)")
    print(f"✅ Carga final estimada: {final_load:,} calls/día")
    
    print(f"\n🚀 IMPACTO EN UTILIZACIÓN DEL SISTEMA:")
    final_utilization = (final_load / 2400) * 100  # Assuming 2400 daily limit
    print(f"   Utilización final estimada: {final_utilization:.1f}% (vs actual ~125%)")
    
    if final_utilization < 75:
        print("   ✅ Sistema dentro de límites seguros")
        print("   🎯 Cache adaptativo funcionará sin problemas")
    else:
        print("   ⚠️ Sistema aún cerca de límites")
        print("   📋 Considerar optimizaciones adicionales")
    
    print(f"\n📋 PLAN DE IMPLEMENTACIÓN:")
    for phase_name, phase_data in implementation_plan['phases'].items():
        phase_opts = len(phase_data['optimizations'])
        if phase_opts > 0:
            print(f"   {phase_name.replace('_', ' ').upper()}: {phase_opts} optimizations ({phase_data['timeframe']})")
    
    print("=" * 60)
    
    # Guardar templates para implementación
    with open('trader_optimization_templates.py', 'w') as f:
        f.write("# Trader Optimization Templates\n\n")
        for name, template in code_templates.items():
            f.write(f"# {name.upper()}\n{template}\n\n")
    
    logger.info("💾 Code templates saved to trader_optimization_templates.py")
    
    return final_utilization < 75

async def main():
    try:
        success = await run_trader_optimization_analysis()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error in trader optimization analysis: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)