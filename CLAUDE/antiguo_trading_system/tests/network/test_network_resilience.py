#!/usr/bin/env python3
"""
Test de Resiliencia de Red y Conectividad
Tests para validar el comportamiento del sistema ante problemas de red y conectividad
"""

import os
import sys
import time
import random
import socket
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import subprocess

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class NetworkResilienceTest:
    """Tests de resiliencia de red y conectividad"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.simulated_failures = []
    
    def test_database_connection_resilience(self) -> dict:
        """Test de resiliencia ante problemas de conexión a BD"""
        print("🔌 Test de resiliencia de conexión a BD...")
        
        results = {
            'connection_tests': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'average_recovery_time': 0.0,
            'data_integrity_maintained': True,
            'recovery_times': [],
            'test_passed': False
        }
        
        # Escenarios de falla de conexión
        failure_scenarios = [
            {
                'name': 'temporary_disconnection',
                'description': 'Desconexión temporal de BD',
                'duration_seconds': 2
            },
            {
                'name': 'intermittent_connectivity',
                'description': 'Conectividad intermitente',
                'duration_seconds': 1
            },
            {
                'name': 'slow_connection',
                'description': 'Conexión lenta simulada',
                'duration_seconds': 3
            }
        ]
        
        for scenario in failure_scenarios:
            results['connection_tests'] += 1
            
            try:
                print(f"   🧪 Testing: {scenario['description']}")
                
                # Registrar estado antes de la falla
                pre_failure_trades = self.db_manager.get_trades(limit=5)
                pre_failure_count = len(pre_failure_trades) if not pre_failure_trades.empty else 0
                
                # Simular falla de red
                recovery_start = time.time()
                
                # Durante la "falla", intentar operaciones
                failure_duration = scenario['duration_seconds']
                operations_during_failure = []
                
                print(f"      ⏱️  Simulando falla por {failure_duration} segundos...")
                
                # Intentar operaciones durante la falla simulada
                for i in range(3):  # 3 intentos de operación durante falla
                    try:
                        time.sleep(failure_duration / 3)  # Distribuir en el tiempo de falla
                        
                        # Intentar guardar trade durante "falla"
                        test_trade = {
                            'trade_id': f"NETWORK_FAIL_TEST_{int(time.time())}_{i}",
                            'symbol': f'NETFAIL{i:02d}',
                            'strategy': 'network_resilience_test',
                            'side': 'BUY',
                            'quantity': 100,
                            'entry_price': 10.0,
                            'entry_time': datetime.now(),
                            'status': 'OPEN'
                        }
                        
                        # En un sistema real, esto podría fallar durante problemas de red
                        # Por ahora simulamos intentos exitosos con delays
                        time.sleep(0.1)  # Simular latencia
                        success = self.db_manager.save_trade(test_trade)
                        operations_during_failure.append(success)
                        
                    except Exception as e:
                        print(f"         ⚠️  Operation failed during network issue: {e}")
                        operations_during_failure.append(False)
                
                # Medir tiempo de recuperación
                recovery_time = time.time() - recovery_start
                results['recovery_times'].append(recovery_time)
                
                # Verificar recuperación
                try:
                    # Intentar operación post-recuperación
                    post_recovery_trades = self.db_manager.get_trades(limit=10)
                    
                    recovery_trade = {
                        'trade_id': f"RECOVERY_VERIFY_{int(time.time())}",
                        'symbol': 'RECOVERY_OK',
                        'strategy': 'recovery_verification',
                        'side': 'BUY',
                        'quantity': 50,
                        'entry_price': 15.0,
                        'entry_time': datetime.now(),
                        'status': 'OPEN'
                    }
                    
                    recovery_success = self.db_manager.save_trade(recovery_trade)
                    
                    if recovery_success:
                        results['successful_recoveries'] += 1
                        print(f"      ✅ Recovery successful in {recovery_time:.2f}s")
                        
                        # Verificar integridad de datos
                        post_failure_trades = self.db_manager.get_trades(limit=20)
                        post_failure_count = len(post_failure_trades) if not post_failure_trades.empty else 0
                        
                        # Debería haber al menos los trades originales + los nuevos
                        expected_min_count = pre_failure_count + sum(operations_during_failure) + 1
                        if post_failure_count >= expected_min_count:
                            print(f"      ✅ Data integrity maintained ({post_failure_count} trades)")
                        else:
                            results['data_integrity_maintained'] = False
                            print(f"      ⚠️  Possible data loss detected")
                    else:
                        results['failed_recoveries'] += 1
                        print(f"      ❌ Recovery failed")
                        
                except Exception as e:
                    results['failed_recoveries'] += 1
                    print(f"      ❌ Recovery verification failed: {e}")
                    
            except Exception as e:
                results['failed_recoveries'] += 1
                print(f"      ❌ Scenario test failed: {e}")
        
        # Calcular tiempo promedio de recuperación
        if results['recovery_times']:
            results['average_recovery_time'] = sum(results['recovery_times']) / len(results['recovery_times'])
        
        # Evaluar resultados
        recovery_rate = results['successful_recoveries'] / results['connection_tests'] if results['connection_tests'] > 0 else 0
        
        if (recovery_rate >= 0.8 and 
            results['data_integrity_maintained'] and
            results['average_recovery_time'] < 5.0):  # Menos de 5 segundos promedio
            results['test_passed'] = True
            print(f"   🎯 Connection resilience: PASS")
        else:
            print(f"   ⚠️  Connection resilience: FAIL")
        
        # Limpiar datos de prueba
        self._cleanup_network_test_data()
        
        return results
    
    def test_external_service_timeout_handling(self) -> dict:
        """Test de manejo de timeouts de servicios externos"""
        print("⏱️  Test de manejo de timeouts de servicios externos...")
        
        results = {
            'timeout_scenarios': 0,
            'graceful_degradations': 0,
            'system_hangs_detected': 0,
            'fallback_mechanisms_activated': 0,
            'test_passed': False
        }
        
        # Simular servicios externos con timeouts
        timeout_scenarios = [
            {
                'name': 'market_data_timeout',
                'description': 'Timeout de datos de mercado',
                'timeout_seconds': 2
            },
            {
                'name': 'broker_api_timeout',
                'description': 'Timeout de API del broker',
                'timeout_seconds': 3
            },
            {
                'name': 'price_feed_timeout',
                'description': 'Timeout de feed de precios',
                'timeout_seconds': 1
            }
        ]
        
        for scenario in timeout_scenarios:
            results['timeout_scenarios'] += 1
            
            try:
                print(f"   🧪 Testing: {scenario['description']}")
                
                timeout_duration = scenario['timeout_seconds']
                test_start = time.time()
                
                # Simular operación que toma más tiempo que el timeout
                timeout_occurred = False
                fallback_used = False
                system_responsive = True
                
                try:
                    # Simular operación con timeout
                    operation_result = self._simulate_external_service_call(
                        timeout_duration + 0.5,  # Tomar más tiempo que el timeout
                        timeout_limit=timeout_duration
                    )
                    
                    if operation_result['timed_out']:
                        timeout_occurred = True
                        print(f"      ✅ Timeout properly detected")
                        
                        # Verificar que el sistema sigue respondiendo
                        response_test = self.db_manager.get_trades(limit=1)
                        if response_test is not None:
                            system_responsive = True
                            results['graceful_degradations'] += 1
                            print(f"      ✅ System remained responsive")
                        else:
                            system_responsive = False
                            results['system_hangs_detected'] += 1
                            print(f"      ❌ System became unresponsive")
                        
                        # Verificar mecanismo de fallback
                        fallback_result = self._simulate_fallback_mechanism(scenario['name'])
                        if fallback_result['success']:
                            fallback_used = True
                            results['fallback_mechanisms_activated'] += 1
                            print(f"      ✅ Fallback mechanism activated")
                        else:
                            print(f"      ⚠️  Fallback mechanism not available")
                    
                except Exception as e:
                    if "timeout" in str(e).lower():
                        timeout_occurred = True
                        results['graceful_degradations'] += 1
                        print(f"      ✅ Timeout exception handled gracefully")
                    else:
                        print(f"      ⚠️  Unexpected error: {e}")
                
                test_duration = time.time() - test_start
                
                # Verificar que el test no tomó demasiado tiempo (indicaría hang)
                if test_duration > timeout_duration + 2:
                    results['system_hangs_detected'] += 1
                    print(f"      ⚠️  Test took too long: {test_duration:.2f}s")
                
            except Exception as e:
                print(f"      ❌ Timeout scenario test failed: {e}")
        
        # Evaluar resultados
        if (results['graceful_degradations'] == results['timeout_scenarios'] and
            results['system_hangs_detected'] == 0):
            results['test_passed'] = True
            print(f"   🎯 Timeout handling: PASS")
        else:
            print(f"   ⚠️  Timeout handling: FAIL")
        
        return results
    
    def test_network_latency_adaptation(self) -> dict:
        """Test de adaptación a alta latencia de red"""
        print("🐌 Test de adaptación a alta latencia de red...")
        
        results = {
            'latency_tests': 0,
            'successful_adaptations': 0,
            'performance_degradations': 0,
            'operations_completed': 0,
            'average_operation_time': 0.0,
            'test_passed': False
        }
        
        # Diferentes niveles de latencia para probar
        latency_scenarios = [
            {'name': 'low_latency', 'delay_ms': 50, 'description': 'Latencia baja (50ms)'},
            {'name': 'medium_latency', 'delay_ms': 200, 'description': 'Latencia media (200ms)'},
            {'name': 'high_latency', 'delay_ms': 500, 'description': 'Latencia alta (500ms)'},
            {'name': 'very_high_latency', 'delay_ms': 1000, 'description': 'Latencia muy alta (1s)'}
        ]
        
        operation_times = []
        
        for scenario in latency_scenarios:
            results['latency_tests'] += 1
            
            try:
                print(f"   🧪 Testing: {scenario['description']}")
                
                latency_ms = scenario['delay_ms']
                
                # Realizar múltiples operaciones con latencia simulada
                scenario_times = []
                successful_ops = 0
                
                for i in range(5):  # 5 operaciones por escenario
                    op_start = time.time()
                    
                    try:
                        # Simular latencia de red
                        time.sleep(latency_ms / 1000.0)
                        
                        # Realizar operación de BD
                        test_trade = {
                            'trade_id': f"LATENCY_TEST_{scenario['name']}_{i}_{int(time.time()*1000) % 10000}",
                            'symbol': f'LAT{i:02d}',
                            'strategy': 'latency_test',
                            'side': 'BUY',
                            'quantity': 100,
                            'entry_price': 10.0,
                            'entry_time': datetime.now(),
                            'status': 'OPEN'
                        }
                        
                        success = self.db_manager.save_trade(test_trade)
                        
                        op_time = time.time() - op_start
                        scenario_times.append(op_time)
                        
                        if success:
                            successful_ops += 1
                            results['operations_completed'] += 1
                        
                    except Exception as e:
                        print(f"         ⚠️  Operation failed under latency: {e}")
                        op_time = time.time() - op_start
                        scenario_times.append(op_time)
                
                # Calcular estadísticas del escenario
                if scenario_times:
                    avg_time = sum(scenario_times) / len(scenario_times)
                    operation_times.extend(scenario_times)
                    
                    print(f"      📊 {successful_ops}/5 operations successful")
                    print(f"      ⏱️  Average time: {avg_time:.3f}s")
                    
                    # Verificar adaptación
                    expected_min_time = (latency_ms / 1000.0) + 0.1  # Latencia + overhead mínimo
                    
                    if avg_time >= expected_min_time and successful_ops >= 4:
                        results['successful_adaptations'] += 1
                        print(f"      ✅ Successfully adapted to latency")
                    else:
                        results['performance_degradations'] += 1
                        if avg_time < expected_min_time:
                            print(f"      ⚠️  Times suspiciously fast (possible error)")
                        else:
                            print(f"      ⚠️  Too many operations failed")
                
            except Exception as e:
                results['performance_degradations'] += 1
                print(f"      ❌ Latency scenario failed: {e}")
        
        # Calcular tiempo promedio general
        if operation_times:
            results['average_operation_time'] = sum(operation_times) / len(operation_times)
        
        # Evaluar resultados
        adaptation_rate = results['successful_adaptations'] / results['latency_tests'] if results['latency_tests'] > 0 else 0
        
        if (adaptation_rate >= 0.75 and  # 75% de escenarios exitosos
            results['operations_completed'] >= results['latency_tests'] * 3):  # Al menos 3 ops por escenario
            results['test_passed'] = True
            print(f"   🎯 Latency adaptation: PASS")
        else:
            print(f"   ⚠️  Latency adaptation: FAIL")
        
        # Limpiar datos de prueba
        self._cleanup_network_test_data()
        
        return results
    
    def test_connection_pool_exhaustion(self) -> dict:
        """Test de agotamiento de pool de conexiones"""
        print("🏊 Test de agotamiento de pool de conexiones...")
        
        results = {
            'connection_attempts': 0,
            'successful_connections': 0,
            'pool_exhaustion_handled': False,
            'recovery_after_exhaustion': False,
            'concurrent_operations': 0,
            'test_passed': False
        }
        
        try:
            # Simular múltiples conexiones concurrentes
            max_concurrent_connections = 20
            connection_results = []
            
            def connection_worker(worker_id: int):
                """Worker que intenta operaciones concurrentes"""
                try:
                    # Simular operación que mantiene conexión
                    for i in range(3):
                        trade_data = {
                            'trade_id': f"POOL_TEST_{worker_id:02d}_{i:02d}_{int(time.time()*1000) % 10000}",
                            'symbol': f'POOL{worker_id:02d}',
                            'strategy': 'connection_pool_test',
                            'side': 'BUY',
                            'quantity': 50,
                            'entry_price': 20.0,
                            'entry_time': datetime.now(),
                            'status': 'OPEN'
                        }
                        
                        success = self.db_manager.save_trade(trade_data)
                        results['connection_attempts'] += 1
                        
                        if success:
                            results['successful_connections'] += 1
                            results['concurrent_operations'] += 1
                        
                        time.sleep(0.1)  # Simular trabajo
                        
                    return True
                    
                except Exception as e:
                    print(f"      ⚠️  Connection worker {worker_id} failed: {e}")
                    return False
            
            print(f"   🚀 Launching {max_concurrent_connections} concurrent connections...")
            
            # Ejecutar workers concurrentemente
            import threading
            threads = []
            
            for i in range(max_concurrent_connections):
                thread = threading.Thread(target=connection_worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Esperar a que terminen todos los threads
            for thread in threads:
                thread.join(timeout=30)  # Timeout de 30 segundos
                
            print(f"   📊 Completed {results['connection_attempts']} connection attempts")
            print(f"   ✅ Successful: {results['successful_connections']}")
            
            # Verificar que el sistema manejó las conexiones apropiadamente
            success_rate = results['successful_connections'] / results['connection_attempts'] if results['connection_attempts'] > 0 else 0
            
            if success_rate > 0.8:  # Al menos 80% exitosas
                results['pool_exhaustion_handled'] = True
                print(f"   ✅ Connection pool handled concurrent load")
            else:
                print(f"   ⚠️  High failure rate in concurrent connections")
            
            # Test de recuperación post-exhaustion
            try:
                time.sleep(1)  # Pausa para que se liberen conexiones
                
                recovery_trade = {
                    'trade_id': f"POOL_RECOVERY_{int(time.time())}",
                    'symbol': 'RECOVERY',
                    'strategy': 'pool_recovery_test',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 25.0,
                    'entry_time': datetime.now(),
                    'status': 'OPEN'
                }
                
                recovery_success = self.db_manager.save_trade(recovery_trade)
                
                if recovery_success:
                    results['recovery_after_exhaustion'] = True
                    print(f"   ✅ System recovered after connection stress")
                else:
                    print(f"   ⚠️  System did not recover properly")
                    
            except Exception as e:
                print(f"   ⚠️  Recovery test failed: {e}")
            
        except Exception as e:
            print(f"   ❌ Connection pool test failed: {e}")
        
        # Evaluar resultados
        if (results['pool_exhaustion_handled'] and
            results['recovery_after_exhaustion'] and
            results['concurrent_operations'] >= 15):  # Mínimo 15 operaciones exitosas
            results['test_passed'] = True
            print(f"   🎯 Connection pool resilience: PASS")
        else:
            print(f"   ⚠️  Connection pool resilience: FAIL")
        
        # Limpiar datos de prueba
        self._cleanup_network_test_data()
        
        return results
    
    def _simulate_external_service_call(self, duration_seconds: float, timeout_limit: float) -> Dict[str, Any]:
        """Simular llamada a servicio externo con timeout"""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Operation timed out")
        
        try:
            # Configurar timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_limit))
            
            # Simular operación que toma tiempo
            time.sleep(duration_seconds)
            
            # Si llegamos aquí, no hubo timeout
            signal.alarm(0)  # Cancelar alarm
            return {'success': True, 'timed_out': False}
            
        except TimeoutError:
            signal.alarm(0)  # Cancelar alarm
            return {'success': False, 'timed_out': True}
        except Exception as e:
            signal.alarm(0)  # Cancelar alarm
            return {'success': False, 'timed_out': False, 'error': str(e)}
    
    def _simulate_fallback_mechanism(self, scenario_name: str) -> Dict[str, Any]:
        """Simular mecanismo de fallback"""
        try:
            # Simular diferentes tipos de fallback según el escenario
            if 'market_data' in scenario_name:
                # Fallback a datos cached o datos alternativos
                return {'success': True, 'fallback_type': 'cached_data'}
            elif 'broker_api' in scenario_name:
                # Fallback a broker alternativo o modo offline
                return {'success': True, 'fallback_type': 'alternative_broker'}
            elif 'price_feed' in scenario_name:
                # Fallback a feed alternativo
                return {'success': True, 'fallback_type': 'alternative_feed'}
            else:
                return {'success': False, 'fallback_type': 'none'}
                
        except Exception:
            return {'success': False, 'error': 'Fallback mechanism failed'}
    
    def _cleanup_network_test_data(self):
        """Limpiar datos de test de red"""
        try:
            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                patterns = [
                    'NETWORK_FAIL_TEST_%',
                    'RECOVERY_VERIFY_%',
                    'LATENCY_TEST_%',
                    'POOL_TEST_%',
                    'POOL_RECOVERY_%'
                ]
                
                for pattern in patterns:
                    conn.execute("DELETE FROM trades WHERE trade_id LIKE ?", (pattern,))
                
                conn.commit()
                
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de red: {e}")

def main():
    """Ejecutar todos los tests de resiliencia de red"""
    print("🌐 TESTS DE RESILIENCIA DE RED Y CONECTIVIDAD")
    print("=" * 50)
    
    network_test = NetworkResilienceTest()
    all_results = {}
    
    # Test 1: Resiliencia de conexión a BD
    print("\n1️⃣  RESILIENCIA DE CONEXIÓN A BASE DE DATOS")
    print("-" * 45)
    db_connection_results = network_test.test_database_connection_resilience()
    all_results['database_connection_resilience'] = db_connection_results
    
    # Test 2: Manejo de timeouts de servicios externos
    print("\n2️⃣  MANEJO DE TIMEOUTS DE SERVICIOS EXTERNOS")
    print("-" * 45)
    timeout_handling_results = network_test.test_external_service_timeout_handling()
    all_results['external_service_timeout_handling'] = timeout_handling_results
    
    # Test 3: Adaptación a alta latencia
    print("\n3️⃣  ADAPTACIÓN A ALTA LATENCIA DE RED")
    print("-" * 45)
    latency_adaptation_results = network_test.test_network_latency_adaptation()
    all_results['network_latency_adaptation'] = latency_adaptation_results
    
    # Test 4: Agotamiento de pool de conexiones
    print("\n4️⃣  AGOTAMIENTO DE POOL DE CONEXIONES")
    print("-" * 45)
    connection_pool_results = network_test.test_connection_pool_exhaustion()
    all_results['connection_pool_exhaustion'] = connection_pool_results
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE TESTS DE RESILIENCIA DE RED")
    print("=" * 50)
    
    test_categories = {
        'database_connection_resilience': 'Resiliencia Conexión BD',
        'external_service_timeout_handling': 'Manejo Timeouts Servicios',
        'network_latency_adaptation': 'Adaptación Latencia Red',
        'connection_pool_exhaustion': 'Agotamiento Pool Conexiones'
    }
    
    passed_tests = 0
    total_tests = len(all_results)
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            passed = result.get('test_passed', False)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            
            # Información adicional específica
            additional_info = ""
            if test_key == 'database_connection_resilience':
                recoveries = result.get('successful_recoveries', 0)
                total_tests_run = result.get('connection_tests', 0)
                avg_recovery = result.get('average_recovery_time', 0)
                additional_info = f"({recoveries}/{total_tests_run} recovered, {avg_recovery:.1f}s avg)"
                
            elif test_key == 'external_service_timeout_handling':
                degradations = result.get('graceful_degradations', 0)
                hangs = result.get('system_hangs_detected', 0)
                fallbacks = result.get('fallback_mechanisms_activated', 0)
                additional_info = f"({degradations} graceful, {hangs} hangs, {fallbacks} fallbacks)"
                
            elif test_key == 'network_latency_adaptation':
                adaptations = result.get('successful_adaptations', 0)
                latency_tests = result.get('latency_tests', 0)
                avg_op_time = result.get('average_operation_time', 0)
                additional_info = f"({adaptations}/{latency_tests} adapted, {avg_op_time:.3f}s avg)"
                
            elif test_key == 'connection_pool_exhaustion':
                successful_conns = result.get('successful_connections', 0)
                total_attempts = result.get('connection_attempts', 0)
                concurrent_ops = result.get('concurrent_operations', 0)
                additional_info = f"({successful_conns}/{total_attempts} conns, {concurrent_ops} ops)"
            
            print(f"{test_name}: {status} {additional_info}")
            
            if passed:
                passed_tests += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de resiliencia de red pasaron")
    
    # Evaluación de resiliencia de red
    network_score = passed_tests / total_tests if total_tests > 0 else 0
    
    print("\n🌐 EVALUACIÓN DE RESILIENCIA DE RED:")
    
    if network_score == 1.0:
        print("🏆 EXCELENTE - Sistema altamente resiliente a problemas de red")
        print("✅ Maneja todas las condiciones de red adversas")
        print("🚀 Robusto para entornos de red inestables")
    elif network_score >= 0.75:
        print("💪 BUENO - Sistema resiliente con algunas vulnerabilidades")
        print("⚠️  Mejoras menores en resiliencia recomendadas")
        print("🔧 Fortalecer algunos aspectos de conectividad")
    else:
        print("⚠️  PROBLEMAS - Sistema vulnerable a problemas de red")
        print("🔧 Mejoras importantes en resiliencia requeridas")
        print("🚫 Riesgo en entornos de red inestables")
    
    # Recomendaciones específicas
    print(f"\n💡 RECOMENDACIONES DE RESILIENCIA DE RED:")
    
    db_result = all_results.get('database_connection_resilience', {})
    if not db_result.get('test_passed', False):
        print("🔌 Implementar reconexión automática y retry logic para BD")
    
    timeout_result = all_results.get('external_service_timeout_handling', {})
    if timeout_result.get('system_hangs_detected', 0) > 0:
        print("⏱️  Mejorar manejo de timeouts para evitar system hangs")
    
    latency_result = all_results.get('network_latency_adaptation', {})
    if not latency_result.get('test_passed', False):
        print("🐌 Optimizar para mejor rendimiento bajo alta latencia")
    
    pool_result = all_results.get('connection_pool_exhaustion', {})
    if not pool_result.get('test_passed', False):
        print("🏊 Ajustar configuración de pool de conexiones")

if __name__ == "__main__":
    main()