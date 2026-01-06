"""
Suite de Verificación de Workers
================================

Herramientas para verificar si los workers están funcionando correctamente
sin necesidad de backtesting.
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Any
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class WorkerVerificationSuite:
    """Suite de verificación para workers"""
    
    def __init__(self, worker):
        self.worker = worker
        self.test_results = []
    
    def add_test_case(self, name: str, opportunity: Dict[str, Any], 
                     expected_decision: bool, expected_reason_contains: str = None):
        """Agregar caso de prueba conocido"""
        self.test_results.append({
            'name': name,
            'opportunity': opportunity,
            'expected_decision': expected_decision,
            'expected_reason_contains': expected_reason_contains,
            'actual_decision': None,
            'actual_reason': None,
            'actual_confidence': None,
            'passed': False
        })
    
    async def run_verification(self):
        """Ejecutar todos los casos de prueba"""
        logger.info(f"🧪 Iniciando verificación para {self.worker.worker_name}")
        
        for test_case in self.test_results:
            await self._run_single_test(test_case)
        
        # Generar reporte
        passed = sum(1 for t in self.test_results if t['passed'])
        total = len(self.test_results)
        
        logger.info(f"📊 Verificación completada: {passed}/{total} tests pasados")
        
        return self._generate_report()
    
    async def _run_single_test(self, test_case: Dict[str, Any]):
        """Ejecutar un caso de prueba específico"""
        try:
            opportunity = test_case['opportunity']
            
            # Obtener decisión del worker
            decision, reason, confidence = self.worker.evaluate_opportunity(opportunity)
            
            # Guardar resultados
            test_case['actual_decision'] = decision
            test_case['actual_reason'] = reason
            test_case['actual_confidence'] = confidence
            
            # Verificar decisión
            if test_case['expected_decision'] == decision:
                # Verificar razón si se especificó
                if test_case['expected_reason_contains']:
                    if test_case['expected_reason_contains'].lower() in reason.lower():
                        test_case['passed'] = True
                    else:
                        logger.warning(f"⚠️ Razón no coincide: esperado '{test_case['expected_reason_contains']}', obtenido '{reason}'")
                else:
                    test_case['passed'] = True
            else:
                logger.warning(f"⚠️ Decisión incorrecta: esperado {test_case['expected_decision']}, obtenido {decision}")
                
            # Log del resultado
            status = "✅ PASADO" if test_case['passed'] else "❌ FALLADO"
            logger.info(f"   {test_case['name']}: {status}")
            
        except Exception as e:
            logger.error(f"❌ Error en test {test_case['name']}: {e}")
            test_case['passed'] = False
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generar reporte de verificación"""
        passed = sum(1 for t in self.test_results if t['passed'])
        total = len(self.test_results)
        
        failed_tests = [t for t in self.test_results if not t['passed']]
        
        return {
            'worker_name': self.worker.worker_name,
            'total_tests': total,
            'passed_tests': passed,
            'failed_tests': total - passed,
            'success_rate': passed / total if total > 0 else 0,
            'failed_test_details': failed_tests
        }


def create_macdv_test_cases():
    """Crear casos de prueba conocidos para MACDV"""
    
    return [
        # Caso 1: GAP PEQUEÑO + VOLUMEN NORMAL = DEBE APROBAR
        {
            'name': 'Gap pequeño con volumen normal',
            'opportunity': {
                'symbol': 'TEST1',
                'gap_percentage': 2.5,
                'volume_ratio': 1.5,
                'current_price': 8.5,
                'quality_score': 70,
                'catalyst_type': 'NEWS',
                'bars': []  # Simular barras mínimas
            },
            'expected_decision': True,
            'expected_reason_contains': 'APPROVED'
        },
        
        # Caso 2: GAP GRANDE = DEBE RECHAZAR (MACDV evita gaps parabólicos)
        {
            'name': 'Gap muy grande debe rechazar',
            'opportunity': {
                'symbol': 'TEST2',
                'gap_percentage': 15.0,  # Gap muy grande
                'volume_ratio': 1.2,
                'current_price': 12.0,
                'quality_score': 80,
                'catalyst_type': 'NEWS',
                'bars': []
            },
            'expected_decision': False,
            'expected_reason_contains': 'Gap'
        },
        
        # Caso 3: PRECIO FUERA DE RANGO = DEBE RECHAZAR
        {
            'name': 'Precio fuera de rango smallcap',
            'opportunity': {
                'symbol': 'TEST3',
                'gap_percentage': 3.0,
                'volume_ratio': 2.0,
                'current_price': 45.0,  # Precio muy alto para MACDV
                'quality_score': 75,
                'catalyst_type': 'NEWS',
                'bars': []
            },
            'expected_decision': False,
            'expected_reason_contains': 'Price'
        },
        
        # Caso 4: VOLUMEN BAJO = DEBE RECHAZAR
        {
            'name': 'Volumen insuficiente',
            'opportunity': {
                'symbol': 'TEST4',
                'gap_percentage': 3.0,
                'volume_ratio': 0.3,  # Volumen muy bajo
                'current_price': 9.5,
                'quality_score': 65,
                'catalyst_type': 'NEWS',
                'bars': []
            },
            'expected_decision': False,
            'expected_reason_contains': 'Volume'
        }
    ]


def create_daily_plays_test_cases():
    """Crear casos de prueba para Daily Plays"""
    
    return [
        # Caso 1: CATALYST FUERTE + CALIDAD ALTA = DEBE APROBAR
        {
            'name': 'Catalyst fuerte con calidad alta',
            'opportunity': {
                'symbol': 'TEST1',
                'gap_percentage': 5.0,
                'volume_ratio': 2.0,
                'current_price': 15.0,
                'quality_score': 85,
                'catalyst_type': 'FDA',  # Catalyst muy fuerte
                'bars': []
            },
            'expected_decision': True,
            'expected_reason_contains': 'APPROVED'
        },
        
        # Caso 2: SIN CATALYST = DEBE RECHAZAR (Daily plays requieren catalyst)
        {
            'name': 'Sin catalyst debe rechazar',
            'opportunity': {
                'symbol': 'TEST2',
                'gap_percentage': 4.0,
                'volume_ratio': 1.5,
                'current_price': 12.0,
                'quality_score': 60,
                'catalyst_type': 'NONE',  # Sin catalyst
                'bars': []
            },
            'expected_decision': False,
            'expected_reason_contains': 'quality'
        }
    ]


async def verify_all_workers():
    """Verificar todos los workers disponibles"""
    
    # Importar workers realistas
    from ..core.realistic_workers import get_realistic_worker_class
    
    workers_to_test = ['macdv', 'daily_plays', 'vwap']
    verification_results = {}
    
    for worker_name in workers_to_test:
        try:
            # Obtener clase del worker
            worker_class = get_realistic_worker_class(worker_name)
            worker = worker_class(worker_name)
            
            # Crear suite de verificación
            suite = WorkerVerificationSuite(worker)
            
            # Agregar casos de prueba específicos del worker
            if worker_name == 'macdv':
                test_cases = create_macdv_test_cases()
            elif worker_name == 'daily_plays':
                test_cases = create_daily_plays_test_cases()
            else:
                # Caso genérico
                test_cases = []
            
            for test_case in test_cases:
                suite.add_test_case(
                    name=test_case['name'],
                    opportunity=test_case['opportunity'],
                    expected_decision=test_case['expected_decision'],
                    expected_reason_contains=test_case.get('expected_reason_contains')
                )
            
            # Ejecutar verificación
            result = await suite.run_verification()
            verification_results[worker_name] = result
            
        except Exception as e:
            logger.error(f"❌ Error verificando {worker_name}: {e}")
            verification_results[worker_name] = {'error': str(e)}
    
    return verification_results


if __name__ == "__main__":
    # Ejecutar verificación completa
    async def main():
        results = await verify_all_workers()
        
        print("\n📊 REPORTE DE VERIFICACIÓN DE WORKERS")
        print("="*50)
        
        for worker_name, result in results.items():
            if 'error' in result:
                print(f"\n❌ {worker_name}: ERROR - {result['error']}")
            else:
                print(f"\n✅ {worker_name}:")
                print(f"   Tests: {result['passed_tests']}/{result['total_tests']} ({result['success_rate']:.1%})")
                if result['failed_tests'] > 0:
                    print(f"   Tests fallidos: {result['failed_tests']}")
    
    # Ejecutar
    asyncio.run(main())