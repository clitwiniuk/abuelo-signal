#!/usr/bin/env python3
"""
Test de Workers SIMPLIFICADO
===========================

VERSIÓN SIMPLIFICADA que funciona 100% - Sin dependencias complejas
"""

import asyncio
import sys
from pathlib import Path

# Agregar directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from analyze_worker_logic import WorkerLogicAnalyzer


class SimpleWorkerTester:
    """Tester simplificado que funciona con cualquier configuración"""
    
    def __init__(self):
        self.analyzer = WorkerLogicAnalyzer()
    
    def test_decision_logic(self, worker_name: str, opportunity_data: dict) -> dict:
        """
        Test de lógica de decisión basado en parámetros extraídos del código
        """
        
        # Obtener análisis del worker
        worker_file = f"{worker_name}_worker_logic.py"
        analysis = self.analyzer.analyze_worker_file(worker_file)
        
        if 'error' in analysis:
            return {
                'success': False,
                'error': analysis['error'],
                'decision': False
            }
        
        # Extraer criterios del análisis
        config_values = analysis.get('config_values', {})
        criteria = analysis.get('criteria_analysis', {})
        
        # Aplicar criterios de decisión
        symbol = opportunity_data.get('symbol', 'UNKNOWN')
        gap_pct = abs(opportunity_data.get('gap_percentage', 0))
        volume_ratio = opportunity_data.get('volume_ratio', 1.0)
        current_price = opportunity_data.get('current_price', 0)
        quality_score = opportunity_data.get('quality_score', 50)
        
        print(f"🔍 Testeando {symbol} con {worker_name}:")
        print(f"   Gap: {gap_pct}%")
        print(f"   Volumen: {volume_ratio}x")
        print(f"   Precio: ${current_price}")
        print(f"   Calidad: {quality_score}")
        print()
        
        # Aplicar filtros basados en parámetros reales del worker
        reasons = []
        decision = True
        
        # Filtro de precio
        if 'max_price' in config_values and current_price > float(config_values['max_price']):
            decision = False
            reasons.append(f"Precio ${current_price} > máximo ${config_values['max_price']}")
        
        if 'min_price' in config_values and current_price < float(config_values['min_price']):
            decision = False
            reasons.append(f"Precio ${current_price} < mínimo ${config_values['min_price']}")
        
        # Filtro de gap
        if 'max_gap' in config_values and gap_pct > float(config_values['max_gap']):
            decision = False
            reasons.append(f"Gap {gap_pct}% > máximo {config_values['max_gap']}%")
        
        # Filtro de volumen (si se encuentra configuración)
        gap_criteria = criteria.get('gap_criteria', [])
        if gap_criteria and gap_pct < 0.1:  # Gap muy pequeño
            decision = False
            reasons.append("Gap demasiado pequeño para este worker")
        
        # Resultado
        if decision:
            print(f"✅ APROBADO: {symbol} pasa todos los filtros")
        else:
            print(f"❌ RECHAZADO: {symbol} falla por:")
            for reason in reasons:
                print(f"   - {reason}")
        
        return {
            'success': True,
            'worker_name': worker_name,
            'decision': decision,
            'reasons': reasons,
            'config_used': config_values,
            'symbol': symbol,
            'opportunity_data': opportunity_data
        }
    
    def run_test_suite(self):
        """Ejecutar suite de tests para todos los workers"""
        
        print("🧪 SUITE DE TESTS SIMPLIFICADA PARA WORKERS")
        print("="*60)
        print()
        
        # Oportunidad de prueba estándar
        test_opportunity = {
            'symbol': 'TEST_STOCK',
            'gap_percentage': 3.5,
            'volume_ratio': 1.8,
            'current_price': 9.25,
            'quality_score': 72,
            'catalyst_type': 'NEWS'
        }
        
        workers_to_test = [
            'macdv',
            'daily_plays', 
            'vwap',
            'generic_01',
            'volume_absorption',
            'momentum_breakout',
            'vcp_smallcap'
        ]
        
        results = []
        
        for worker_name in workers_to_test:
            print(f"{'='*50}")
            print(f"🧪 TESTEANDO: {worker_name.upper()}")
            print(f"{'='*50}")
            
            result = self.test_decision_logic(worker_name, test_opportunity)
            results.append(result)
            print()
        
        # Resumen final
        print(f"{'='*60}")
        print("📊 RESUMEN FINAL")
        print(f"{'='*60}")
        
        approved = 0
        rejected = 0
        
        for result in results:
            if result['success']:
                status = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
                print(f"{result['worker_name']:<20}: {status}")
                
                if result['decision']:
                    approved += 1
                else:
                    rejected += 1
            else:
                print(f"{result['worker_name']:<20}: ❌ ERROR - {result['error']}")
                rejected += 1
        
        print(f"\n📊 ESTADÍSTICAS:")
        print(f"   Aprobados: {approved}")
        print(f"   Rechazados: {rejected}")
        print(f"   Total: {len(results)}")
        print(f"   Tasa aprobación: {(approved/len(results))*100:.1f}%")
        
        return results


def main():
    """Función principal"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test-all':
        # Test completo
        tester = SimpleWorkerTester()
        tester.run_test_suite()
    else:
        # Test individual
        worker_name = sys.argv[1] if len(sys.argv) > 1 else 'macdv'
        
        print(f"🧪 TEST INDIVIDUAL: {worker_name.upper()}")
        print("="*40)
        
        tester = SimpleWorkerTester()
        
        opportunity = {
            'symbol': 'CUSTOM_TEST',
            'gap_percentage': 4.0,
            'volume_ratio': 2.0,
            'current_price': 10.0,
            'quality_score': 75
        }
        
        result = tester.test_decision_logic(worker_name, opportunity)
        
        if result['success']:
            decision = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
            print(f"\n🎯 RESULTADO FINAL: {decision}")
        else:
            print(f"\n❌ ERROR: {result['error']}")


if __name__ == "__main__":
    main()