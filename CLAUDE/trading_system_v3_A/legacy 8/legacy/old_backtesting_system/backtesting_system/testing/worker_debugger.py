"""
Worker Debugger
===============

Herramienta para debugging visual de decisiones de workers
"""

import asyncio
from typing import Dict, Any, List
import pandas as pd

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from core.realistic_workers import get_realistic_worker_class


class WorkerDebugger:
    """Debugger interactivo para workers"""
    
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.worker_class = get_realistic_worker_class(worker_name)
        self.worker = None
        
    async def debug_opportunity(self, opportunity: Dict[str, Any]):
        """Debuggear una oportunidad específica"""
        
        print(f"🔍 DEBUGGEANDO WORKER: {self.worker_name.upper()}")
        print("="*60)
        print()
        
        # Inicializar worker
        self.worker = self.worker_class(self.worker_name)
        
        # Mostrar datos de entrada
        self._print_opportunity_data(opportunity)
        print()
        
        # Evaluar paso a paso
        result = await self._debug_evaluation_process(opportunity)
        
        print()
        self._print_final_result(result)
        
        return result
    
    def _print_opportunity_data(self, opportunity: Dict[str, Any]):
        """Imprimir datos de la oportunidad"""
        print("📊 DATOS DE ENTRADA:")
        print("-" * 30)
        
        key_fields = [
            ('symbol', 'Símbolo'),
            ('gap_percentage', 'Gap (%)'),
            ('volume_ratio', 'Volumen Ratio'),
            ('current_price', 'Precio Actual'),
            ('quality_score', 'Quality Score'),
            ('catalyst_type', 'Catalizador'),
            ('pattern_type', 'Tipo de Patrón')
        ]
        
        for field, label in key_fields:
            value = opportunity.get(field, 'N/A')
            if isinstance(value, float):
                print(f"   {label:<20}: {value:.2f}")
            else:
                print(f"   {label:<20}: {value}")
    
    async def _debug_evaluation_process(self, opportunity: Dict[str, Any]):
        """Debuggear el proceso de evaluación paso a paso"""
        print("🧠 PROCESO DE EVALUACIÓN:")
        print("-" * 30)
        
        try:
            # Llamar al método de evaluación
            decision, reason, confidence = self.worker.evaluate_opportunity(opportunity)
            
            print(f"   🔍 Evaluación Iniciada...")
            
            # Mostrar el resultado completo
            print(f"   📝 Razón completa: {reason}")
            print(f"   📊 Confianza: {confidence:.1f}%")
            print(f"   🎯 Decisión: {'✅ APROBADO' if decision else '❌ RECHAZADO'}")
            
            return {
                'decision': decision,
                'reason': reason,
                'confidence': confidence,
                'success': True
            }
            
        except Exception as e:
            print(f"   ❌ ERROR EN EVALUACIÓN: {e}")
            return {
                'decision': False,
                'reason': f"Error: {e}",
                'confidence': 0,
                'success': False
            }
    
    def _print_final_result(self, result: Dict[str, Any]):
        """Imprimir resultado final"""
        print("🎯 RESULTADO FINAL:")
        print("-" * 30)
        
        if result['success']:
            status = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
            print(f"   Estado: {status}")
            print(f"   Confianza: {result['confidence']:.1f}%")
            print(f"   Razón: {result['reason']}")
        else:
            print(f"   ❌ ERROR: {result['reason']}")


async def debug_real_opportunities():
    """Debuggear oportunidades reales desde la base de datos"""
    
    print("🔍 WORKER DEBUGGER - OPORTUNIDADES REALES")
    print("="*50)
    print()
    
    # Cargar oportunidades reales
    try:
        from core.data_loader_real import DataLoaderReal
        
        data_loader = DataLoaderReal()
        opportunities = data_loader.load_real_opportunities(
            symbols=None,
            start_date=None,
            end_date=None,
            min_volume=10000,
            pattern_type='all'
        )
        
        # Filtrar únicas
        unique_opportunities = []
        seen_combinations = set()
        
        for opp in opportunities:
            symbol = opp.get('symbol', '')
            timestamp = opp.get('timestamp', '')
            date_part = timestamp[:10] if len(timestamp) >= 10 else timestamp
            unique_key = f"{symbol}_{date_part}"
            
            if unique_key not in seen_combinations:
                seen_combinations.add(unique_key)
                unique_opportunities.append(opp)
        
        print(f"📊 Cargadas {len(unique_opportunities)} oportunidades únicas")
        print()
        
        # Debuggear algunas oportunidades
        workers_to_debug = ['macdv', 'daily_plays', 'vwap']
        
        for i, opportunity in enumerate(unique_opportunities[:3]):  # Solo las primeras 3
            print(f"\n{'='*60}")
            print(f"🔍 OPORTUNIDAD {i+1}/3: {opportunity.get('symbol', 'N/A')}")
            print(f"{'='*60}")
            
            for worker_name in workers_to_debug:
                print(f"\n🧪 WORKER: {worker_name.upper()}")
                print("-" * 40)
                
                debugger = WorkerDebugger(worker_name)
                await debugger.debug_opportunity(opportunity)
                
                print()
        
    except Exception as e:
        print(f"❌ Error cargando oportunidades: {e}")


async def debug_custom_opportunity():
    """Debuggear una oportunidad personalizada"""
    
    print("🔍 WORKER DEBUGGER - OPORTUNIDAD PERSONALIZADA")
    print("="*50)
    print()
    
    # Crear oportunidad personalizada para testing
    custom_opportunity = {
        'symbol': 'TEST_STOCK',
        'gap_percentage': 3.5,
        'volume_ratio': 1.8,
        'current_price': 9.25,
        'quality_score': 72,
        'catalyst_type': 'FDA',
        'pattern_type': 'breakout',
        'bars': []  # Simular barras mínimas
    }
    
    workers_to_debug = ['macdv', 'daily_plays', 'vwap']
    
    for worker_name in workers_to_debug:
        print(f"\n🧪 WORKER: {worker_name.upper()}")
        print("-" * 40)
        
        debugger = WorkerDebugger(worker_name)
        await debugger.debug_opportunity(custom_opportunity)
        
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "real":
        # Debuggear oportunidades reales
        asyncio.run(debug_real_opportunities())
    elif len(sys.argv) > 1 and sys.argv[1] == "custom":
        # Debuggear oportunidad personalizada
        asyncio.run(debug_custom_opportunity())
    else:
        print("🔍 WORKER DEBUGGER")
        print("="*30)
        print()
        print("Uso:")
        print("   python worker_debugger.py real     # Debuggear oportunidades reales")
        print("   python worker_debugger.py custom   # Debuggear oportunidad personalizada")
        print()
        print("Ejemplos de debugging disponibles:")
        print("   - Ver por qué un worker aprueba/rechaza")
        print("   - Analizar criterios específicos")
        print("   - Comparar workers en la misma oportunidad")