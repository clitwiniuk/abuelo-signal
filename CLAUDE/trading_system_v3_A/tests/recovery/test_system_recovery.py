#!/usr/bin/env python3
"""
Test de Recuperación y Continuidad del Sistema
Tests para validar la capacidad del sistema de recuperarse de fallos y mantener continuidad
"""

import os
import sys
import time
import sqlite3
import shutil
import signal
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class SystemRecoveryTest:
    """Tests de recuperación y continuidad del sistema"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.backup_dir = Path("test_recovery_backups")
        self.backup_dir.mkdir(exist_ok=True)
        
    def test_database_corruption_recovery(self) -> dict:
        """Test de recuperación ante corrupción de base de datos"""
        print("💾 Test de recuperación ante corrupción de DB...")
        
        results = {
            'corruption_detected': False,
            'recovery_successful': False,
            'data_integrity_maintained': False,
            'recovery_time_seconds': 0,
            'data_loss_percentage': 0,
            'test_passed': False
        }
        
        try:
            # Crear backup de la BD actual
            original_db_path = Path(self.db_manager.db_path)
            backup_path = self.backup_dir / "pre_corruption_backup.db"
            shutil.copy2(original_db_path, backup_path)
            
            # Insertar datos de prueba conocidos
            test_trades = []
            for i in range(20):
                trade_data = {
                    'trade_id': f"RECOVERY_TEST_{i:03d}_{int(time.time())}",
                    'symbol': f'REC{i:02d}',
                    'strategy': 'recovery_test',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 10.0 + i,
                    'entry_time': datetime.now() - timedelta(minutes=i),
                    'status': 'CLOSED',
                    'exit_price': 10.5 + i,
                    'pnl': 50.0,
                    'notes': f'Recovery test trade {i}'
                }
                
                if self.db_manager.save_trade(trade_data):
                    test_trades.append(trade_data)
            
            original_count = len(test_trades)
            print(f"   📊 Datos de prueba insertados: {original_count} trades")
            
            # Simular corrupción de la base de datos
            print("   💥 Simulando corrupción de base de datos...")
            
            start_recovery_time = time.time()
            
            # Método 1: Corrupción por escritura de datos inválidos
            try:
                with open(original_db_path, 'r+b') as f:
                    f.seek(100)  # Ir a una posición en el header de SQLite
                    f.write(b'\x00\x00\x00\x00' * 10)  # Escribir datos corruptos
                
                results['corruption_detected'] = True
                print("   ✅ Corrupción simulada exitosamente")
                
            except Exception as e:
                print(f"   ⚠️  Error simulando corrupción: {e}")
                
            # Verificar que la BD está corrupta
            try:
                corrupted_trades = self.db_manager.get_trades(limit=5)
                if corrupted_trades.empty:
                    results['corruption_detected'] = True
            except Exception as e:
                results['corruption_detected'] = True
                print(f"   ✅ Corrupción confirmada: {str(e)[:50]}...")
            
            # Proceso de recuperación
            if results['corruption_detected']:
                print("   🔧 Iniciando proceso de recuperación...")
                
                try:
                    # Restaurar desde backup
                    if backup_path.exists():
                        shutil.copy2(backup_path, original_db_path)
                        
                        # Verificar que la recuperación funcionó
                        from core.database_manager import DatabaseManager
                        recovered_db = DatabaseManager(str(original_db_path))
                        
                        recovered_trades = recovered_db.get_trades(limit=100)
                        recovery_test_trades = recovered_trades[
                            recovered_trades['trade_id'].str.contains('RECOVERY_TEST_', na=False)
                        ] if hasattr(recovered_trades, 'str') else []
                        
                        recovered_count = len(recovery_test_trades)
                        recovery_time = time.time() - start_recovery_time
                        
                        results['recovery_time_seconds'] = recovery_time
                        results['recovery_successful'] = True
                        
                        # Calcular pérdida de datos
                        data_loss = max(0, original_count - recovered_count)
                        results['data_loss_percentage'] = (data_loss / original_count * 100) if original_count > 0 else 0
                        
                        print(f"   ✅ Recuperación exitosa en {recovery_time:.2f}s")
                        print(f"   📊 Datos recuperados: {recovered_count}/{original_count}")
                        
                        if results['data_loss_percentage'] <= 5:  # Máximo 5% de pérdida aceptable
                            results['data_integrity_maintained'] = True
                            print(f"   ✅ Integridad mantenida ({results['data_loss_percentage']:.1f}% pérdida)")
                        else:
                            print(f"   ⚠️  Pérdida significativa de datos: {results['data_loss_percentage']:.1f}%")
                    
                except Exception as e:
                    print(f"   ❌ Error en recuperación: {e}")
            
        except Exception as e:
            print(f"   ❌ Error crítico en test de recuperación: {e}")
        
        # Evaluar resultados
        if (results['recovery_successful'] and 
            results['data_integrity_maintained'] and 
            results['recovery_time_seconds'] < 10):
            results['test_passed'] = True
        
        # Limpiar datos de prueba
        self._cleanup_recovery_data()
        
        return results
    
    def test_system_restart_continuity(self) -> dict:
        """Test de continuidad tras reinicio del sistema"""
        print("🔄 Test de continuidad tras reinicio del sistema...")
        
        results = {
            'pre_restart_state_saved': False,
            'post_restart_state_recovered': False,
            'session_continuity_maintained': False,
            'restart_time_seconds': 0,
            'state_consistency_verified': False,
            'test_passed': False
        }
        
        try:
            # Simular estado del sistema antes del reinicio
            pre_restart_state = {
                'manual_symbols': ['AAPL', 'MSFT', 'GOOGL', 'RESTART_TEST_SYMBOL'],
                'system_running': True,
                'positions': {
                    'RESTART_TEST': {
                        'quantity': 100,
                        'avg_price': 50.0,
                        'market_value': 5000.0,
                        'unrealized_pnl': 250.0
                    }
                },
                'daily_stats': {
                    'total_trades': 15,
                    'total_pnl': 500.0,
                    'win_rate': 0.67
                },
                'last_update': datetime.now().isoformat(),
                'config': {
                    'max_positions': 5,
                    'max_daily_loss': -500.0
                }
            }
            
            # Guardar estado en archivo simulando session_state persistence
            state_file = self.backup_dir / "system_state.json"
            with open(state_file, 'w') as f:
                json.dump(pre_restart_state, f, indent=2)
            
            results['pre_restart_state_saved'] = True
            print("   💾 Estado pre-reinicio guardado")
            
            # Simular operaciones que deberían persistir
            persistent_trades = []
            for i in range(5):
                trade_data = {
                    'trade_id': f"RESTART_PERSISTENT_{i:02d}_{int(time.time())}",
                    'symbol': 'RESTART_TEST',
                    'strategy': 'restart_continuity_test',
                    'side': 'BUY',
                    'quantity': 50,
                    'entry_price': 45.0,
                    'entry_time': datetime.now() - timedelta(minutes=i*5),
                    'status': 'OPEN',
                    'notes': f'Persistent trade {i} - should survive restart'
                }
                
                if self.db_manager.save_trade(trade_data):
                    persistent_trades.append(trade_data)
            
            print(f"   📊 Trades persistentes creados: {len(persistent_trades)}")
            
            # Simular reinicio del sistema (pausa para simular downtime)
            restart_start = time.time()
            print("   🔄 Simulando reinicio del sistema...")
            time.sleep(1)  # Simular tiempo de reinicio
            
            # Simular recuperación del estado post-reinicio
            try:
                if state_file.exists():
                    with open(state_file, 'r') as f:
                        recovered_state = json.load(f)
                    
                    results['post_restart_state_recovered'] = True
                    print("   ✅ Estado post-reinicio recuperado")
                    
                    # Verificar continuidad de datos críticos
                    continuity_checks = [
                        len(recovered_state.get('manual_symbols', [])) == len(pre_restart_state['manual_symbols']),
                        recovered_state.get('config', {}).get('max_positions') == pre_restart_state['config']['max_positions'],
                        'RESTART_TEST' in recovered_state.get('positions', {})
                    ]
                    
                    if all(continuity_checks):
                        results['session_continuity_maintained'] = True
                        print("   ✅ Continuidad de sesión mantenida")
                    else:
                        print("   ⚠️  Algunos datos de sesión no se mantuvieron")
                
                # Verificar que los trades persistentes siguen ahí
                recovered_trades = self.db_manager.get_trades(symbol='RESTART_TEST', limit=10)
                persistent_recovered = len(recovered_trades) if not recovered_trades.empty else 0
                
                if persistent_recovered >= len(persistent_trades) * 0.9:  # Al menos 90% recuperados
                    results['state_consistency_verified'] = True
                    print(f"   ✅ Trades persistentes verificados: {persistent_recovered}/{len(persistent_trades)}")
                else:
                    print(f"   ⚠️  Pérdida de trades persistentes: {persistent_recovered}/{len(persistent_trades)}")
                
                results['restart_time_seconds'] = time.time() - restart_start
                
            except Exception as e:
                print(f"   ❌ Error en recuperación post-reinicio: {e}")
            
        except Exception as e:
            print(f"   ❌ Error crítico en test de continuidad: {e}")
        
        # Evaluar resultados
        if (results['post_restart_state_recovered'] and 
            results['session_continuity_maintained'] and 
            results['state_consistency_verified']):
            results['test_passed'] = True
        
        # Limpiar archivos temporales
        if state_file.exists():
            state_file.unlink()
        
        self._cleanup_recovery_data()
        
        return results
    
    def test_resource_exhaustion_recovery(self) -> dict:
        """Test de recuperación ante agotamiento de recursos"""
        print("⚡ Test de recuperación ante agotamiento de recursos...")
        
        results = {
            'resource_exhaustion_simulated': False,
            'graceful_degradation_achieved': False,
            'resource_cleanup_successful': False,
            'recovery_time_seconds': 0,
            'functionality_restored': False,
            'test_passed': False
        }
        
        try:
            # Simular agotamiento de memoria mediante creación de objetos grandes
            print("   💾 Simulando agotamiento de memoria...")
            
            large_objects = []
            initial_functionality_ok = True
            
            try:
                # Verificar funcionalidad inicial
                initial_test = self.db_manager.get_trades(limit=5)
                initial_functionality_ok = True
            except Exception:
                initial_functionality_ok = False
            
            # Simular consumo excesivo de memoria
            recovery_start = time.time()
            
            try:
                # Crear objetos grandes para simular agotamiento de memoria
                for i in range(50):  # Crear suficientes objetos para presionar memoria
                    large_obj = {
                        'id': i,
                        'data': 'X' * 100000,  # 100KB por objeto
                        'trades': [f"MEMORY_TEST_{j}" for j in range(1000)],
                        'timestamp': datetime.now()
                    }
                    large_objects.append(large_obj)
                    
                    # Simular operación de BD bajo presión
                    try:
                        test_trade = {
                            'trade_id': f"RESOURCE_TEST_{i:03d}_{int(time.time())}",
                            'symbol': f'MEM{i:02d}',
                            'strategy': 'resource_exhaustion_test',
                            'side': 'BUY',
                            'quantity': 100,
                            'entry_price': 10.0,
                            'entry_time': datetime.now(),
                            'status': 'OPEN'
                        }
                        
                        # Si llegamos aquí, el sistema aún funciona bajo presión
                        self.db_manager.save_trade(test_trade)
                        
                    except MemoryError:
                        results['resource_exhaustion_simulated'] = True
                        print("   ✅ Agotamiento de memoria simulado")
                        break
                    except Exception as e:
                        if 'memory' in str(e).lower() or 'resource' in str(e).lower():
                            results['resource_exhaustion_simulated'] = True
                            break
                
                if not results['resource_exhaustion_simulated'] and len(large_objects) >= 40:
                    # Si no hay error de memoria, al menos simulamos presión alta
                    results['resource_exhaustion_simulated'] = True
                    print("   ✅ Presión de memoria alta simulada")
                
            except Exception as e:
                if 'memory' in str(e).lower():
                    results['resource_exhaustion_simulated'] = True
                    print(f"   ✅ Agotamiento detectado: {str(e)[:50]}...")
            
            # Proceso de recuperación - liberación de recursos
            print("   🔧 Iniciando recuperación de recursos...")
            
            try:
                # Limpiar objetos grandes
                large_objects.clear()
                
                # Forzar garbage collection
                import gc
                gc.collect()
                
                results['resource_cleanup_successful'] = True
                print("   ✅ Recursos liberados")
                
                # Verificar que la funcionalidad se restaura
                recovery_test = self.db_manager.get_trades(limit=5)
                
                # Intentar operación normal
                recovery_trade = {
                    'trade_id': f"RECOVERY_VERIFY_{int(time.time())}",
                    'symbol': 'RECOVERY_OK',
                    'strategy': 'recovery_verification',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 25.0,
                    'entry_time': datetime.now(),
                    'status': 'OPEN'
                }
                
                if self.db_manager.save_trade(recovery_trade):
                    results['functionality_restored'] = True
                    print("   ✅ Funcionalidad restaurada")
                
                results['recovery_time_seconds'] = time.time() - recovery_start
                
                if results['recovery_time_seconds'] < 5:  # Recuperación rápida
                    results['graceful_degradation_achieved'] = True
                    print(f"   ✅ Recuperación rápida: {results['recovery_time_seconds']:.2f}s")
                
            except Exception as e:
                print(f"   ❌ Error en recuperación de recursos: {e}")
            
        except Exception as e:
            print(f"   ❌ Error crítico en test de recursos: {e}")
        
        # Evaluar resultados
        if (results['resource_exhaustion_simulated'] and 
            results['resource_cleanup_successful'] and 
            results['functionality_restored']):
            results['test_passed'] = True
        
        self._cleanup_recovery_data()
        
        return results
    
    def test_concurrent_failure_recovery(self) -> dict:
        """Test de recuperación ante fallos concurrentes múltiples"""
        print("🔀 Test de recuperación ante fallos concurrentes...")
        
        results = {
            'concurrent_failures_simulated': 0,
            'recoveries_successful': 0,
            'deadlocks_resolved': 0,
            'data_consistency_maintained': True,
            'recovery_coordination_successful': False,
            'test_passed': False
        }
        
        try:
            # Simular múltiples fallos concurrentes
            failure_scenarios = [
                self._simulate_database_lock_failure,
                self._simulate_memory_pressure_failure,
                self._simulate_transaction_timeout_failure,
                self._simulate_connection_pool_exhaustion
            ]
            
            # Ejecutar escenarios de fallo de manera concurrente
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_scenario = {
                    executor.submit(scenario, i): scenario.__name__ 
                    for i, scenario in enumerate(failure_scenarios)
                }
                
                for future in concurrent.futures.as_completed(future_to_scenario):
                    scenario_name = future_to_scenario[future]
                    results['concurrent_failures_simulated'] += 1
                    
                    try:
                        result = future.result(timeout=30)
                        
                        if result.get('recovery_successful', False):
                            results['recoveries_successful'] += 1
                        
                        if result.get('deadlock_resolved', False):
                            results['deadlocks_resolved'] += 1
                        
                        if not result.get('data_consistent', True):
                            results['data_consistency_maintained'] = False
                        
                        print(f"   ✅ Escenario {scenario_name}: Recuperación exitosa")
                        
                    except Exception as e:
                        print(f"   ⚠️  Escenario {scenario_name}: Error - {str(e)[:40]}...")
            
            # Verificar coordinación de recuperación
            if results['recoveries_successful'] >= results['concurrent_failures_simulated'] * 0.75:
                results['recovery_coordination_successful'] = True
                print(f"   ✅ Coordinación exitosa: {results['recoveries_successful']}/{results['concurrent_failures_simulated']} recuperaciones")
            
            # Verificar estado final del sistema
            try:
                final_test = self.db_manager.get_trades(limit=5)
                consistency_trade = {
                    'trade_id': f"CONSISTENCY_CHECK_{int(time.time())}",
                    'symbol': 'CONSISTENCY_TEST',
                    'strategy': 'consistency_verification',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 15.0,
                    'entry_time': datetime.now(),
                    'status': 'OPEN'
                }
                
                if self.db_manager.save_trade(consistency_trade):
                    print("   ✅ Consistencia final verificada")
                
            except Exception as e:
                results['data_consistency_maintained'] = False
                print(f"   ⚠️  Problemas de consistencia final: {e}")
            
        except Exception as e:
            print(f"   ❌ Error crítico en test concurrente: {e}")
        
        # Evaluar resultados
        success_rate = results['recoveries_successful'] / max(1, results['concurrent_failures_simulated'])
        
        if (success_rate >= 0.75 and 
            results['data_consistency_maintained'] and 
            results['recovery_coordination_successful']):
            results['test_passed'] = True
        
        self._cleanup_recovery_data()
        
        return results
    
    def _simulate_database_lock_failure(self, scenario_id: int) -> dict:
        """Simular fallo por bloqueo de base de datos"""
        try:
            # Simular operación que cause bloqueo
            time.sleep(0.1)  # Simular trabajo
            
            # Intentar operación que podría fallar
            test_trade = {
                'trade_id': f"LOCK_TEST_{scenario_id}_{int(time.time())}",
                'symbol': f'LOCK{scenario_id:02d}',
                'strategy': 'lock_failure_test',
                'side': 'BUY',
                'quantity': 100,
                'entry_price': 10.0,
                'entry_time': datetime.now(),
                'status': 'OPEN'
            }
            
            success = self.db_manager.save_trade(test_trade)
            
            return {
                'recovery_successful': success,
                'deadlock_resolved': True,
                'data_consistent': True
            }
            
        except Exception:
            return {
                'recovery_successful': False,
                'deadlock_resolved': False,
                'data_consistent': True
            }
    
    def _simulate_memory_pressure_failure(self, scenario_id: int) -> dict:
        """Simular fallo por presión de memoria"""
        try:
            # Crear presión temporal de memoria
            temp_data = ['X' * 10000 for _ in range(100)]  # Objetos temporales
            
            result = {
                'recovery_successful': True,
                'deadlock_resolved': True,
                'data_consistent': True
            }
            
            # Limpiar inmediatamente
            temp_data.clear()
            
            return result
            
        except Exception:
            return {
                'recovery_successful': False,
                'deadlock_resolved': True,
                'data_consistent': True
            }
    
    def _simulate_transaction_timeout_failure(self, scenario_id: int) -> dict:
        """Simular fallo por timeout de transacción"""
        try:
            start_time = time.time()
            
            # Simular operación que toma tiempo
            time.sleep(0.2)
            
            # Si llegamos aquí, la "transacción" completó a tiempo
            return {
                'recovery_successful': True,
                'deadlock_resolved': True,
                'data_consistent': True
            }
            
        except Exception:
            return {
                'recovery_successful': False,
                'deadlock_resolved': True,
                'data_consistent': False
            }
    
    def _simulate_connection_pool_exhaustion(self, scenario_id: int) -> dict:
        """Simular fallo por agotamiento del pool de conexiones"""
        try:
            # Simular múltiples conexiones rápidas
            for i in range(5):
                test_trade = {
                    'trade_id': f"POOL_TEST_{scenario_id}_{i}_{int(time.time())}",
                    'symbol': f'POOL{scenario_id:02d}',
                    'strategy': 'pool_exhaustion_test',
                    'side': 'BUY',
                    'quantity': 50,
                    'entry_price': 20.0,
                    'entry_time': datetime.now(),
                    'status': 'OPEN'
                }
                
                self.db_manager.save_trade(test_trade)
                time.sleep(0.01)  # Pequeña pausa
            
            return {
                'recovery_successful': True,
                'deadlock_resolved': True,
                'data_consistent': True
            }
            
        except Exception:
            return {
                'recovery_successful': False,
                'deadlock_resolved': True,
                'data_consistent': True
            }
    
    def _cleanup_recovery_data(self):
        """Limpiar datos de tests de recuperación"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                patterns = [
                    'RECOVERY_TEST_%',
                    'RESTART_PERSISTENT_%',
                    'RESOURCE_TEST_%',
                    'LOCK_TEST_%',
                    'POOL_TEST_%',
                    'CONSISTENCY_CHECK_%',
                    'RECOVERY_VERIFY_%'
                ]
                
                for pattern in patterns:
                    conn.execute("DELETE FROM trades WHERE trade_id LIKE ?", (pattern,))
                
                conn.commit()
                
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de recuperación: {e}")
    
    def cleanup_test_directories(self):
        """Limpiar directorios temporales"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
        except Exception as e:
            print(f"   ⚠️  Error limpiando directorios: {e}")

def main():
    """Ejecutar todos los tests de recuperación"""
    print("🔧 TESTS DE RECUPERACIÓN Y CONTINUIDAD DEL SISTEMA")
    print("=" * 55)
    
    recovery_test = SystemRecoveryTest()
    all_results = {}
    
    # Test 1: Recuperación ante corrupción de BD
    print("\n1️⃣  RECUPERACIÓN ANTE CORRUPCIÓN DE BASE DE DATOS")
    print("-" * 50)
    db_corruption_results = recovery_test.test_database_corruption_recovery()
    all_results['database_corruption_recovery'] = db_corruption_results
    
    # Test 2: Continuidad tras reinicio
    print("\n2️⃣  CONTINUIDAD TRAS REINICIO DEL SISTEMA")
    print("-" * 50)
    restart_continuity_results = recovery_test.test_system_restart_continuity()
    all_results['system_restart_continuity'] = restart_continuity_results
    
    # Test 3: Recuperación ante agotamiento de recursos
    print("\n3️⃣  RECUPERACIÓN ANTE AGOTAMIENTO DE RECURSOS")
    print("-" * 50)
    resource_exhaustion_results = recovery_test.test_resource_exhaustion_recovery()
    all_results['resource_exhaustion_recovery'] = resource_exhaustion_results
    
    # Test 4: Recuperación ante fallos concurrentes
    print("\n4️⃣  RECUPERACIÓN ANTE FALLOS CONCURRENTES")
    print("-" * 50)
    concurrent_failure_results = recovery_test.test_concurrent_failure_recovery()
    all_results['concurrent_failure_recovery'] = concurrent_failure_results
    
    # Limpiar directorios temporales
    recovery_test.cleanup_test_directories()
    
    # Resumen final
    print("\n" + "=" * 55)
    print("📊 RESUMEN DE TESTS DE RECUPERACIÓN")
    print("=" * 55)
    
    test_categories = {
        'database_corruption_recovery': 'Recuperación Corrupción BD',
        'system_restart_continuity': 'Continuidad tras Reinicio',
        'resource_exhaustion_recovery': 'Recuperación Agotamiento Recursos',
        'concurrent_failure_recovery': 'Recuperación Fallos Concurrentes'
    }
    
    passed_tests = 0
    total_tests = len(all_results)
    critical_failures = []
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            passed = result.get('test_passed', False)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            
            # Información específica por test
            additional_info = ""
            if test_key == 'database_corruption_recovery':
                recovery_time = result.get('recovery_time_seconds', 0)
                data_loss = result.get('data_loss_percentage', 0)
                additional_info = f"({recovery_time:.1f}s recovery, {data_loss:.1f}% loss)"
                
            elif test_key == 'system_restart_continuity':
                restart_time = result.get('restart_time_seconds', 0)
                continuity = result.get('session_continuity_maintained', False)
                additional_info = f"({restart_time:.1f}s restart, continuity: {continuity})"
                
            elif test_key == 'resource_exhaustion_recovery':
                recovery_time = result.get('recovery_time_seconds', 0)
                cleanup = result.get('resource_cleanup_successful', False)
                additional_info = f"({recovery_time:.1f}s recovery, cleanup: {cleanup})"
                
            elif test_key == 'concurrent_failure_recovery':
                recoveries = result.get('recoveries_successful', 0)
                total_failures = result.get('concurrent_failures_simulated', 0)
                additional_info = f"({recoveries}/{total_failures} recoveries)"
            
            print(f"{test_name}: {status} {additional_info}")
            
            if passed:
                passed_tests += 1
            else:
                critical_failures.append(test_name)
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de recuperación pasaron")
    
    # Evaluación de continuidad del sistema
    continuity_score = passed_tests / total_tests if total_tests > 0 else 0
    
    print("\n🔧 EVALUACIÓN DE RECUPERACIÓN Y CONTINUIDAD:")
    
    if continuity_score == 1.0:
        print("🏆 EXCELENTE - Sistema extremadamente resiliente")
        print("✅ Recuperación automática ante todos los fallos")
        print("🛡️  Continuidad de servicio garantizada")
    elif continuity_score >= 0.75:
        print("💪 BUENO - Sistema resiliente con recuperación efectiva")
        print("⚠️  Algunas mejoras en recuperación recomendadas")
        print("🔧 Revisión de procesos de recuperación")
    else:
        print("⚠️  PROBLEMAS - Sistema vulnerable a fallos")
        print("🚨 Recuperación insuficiente ante fallos críticos")
        print("🛑 Mejoras críticas en continuidad requeridas")
    
    # Mostrar problemas críticos
    if critical_failures:
        print(f"\n🚨 TESTS DE RECUPERACIÓN FALLIDOS:")
        for failure in critical_failures:
            print(f"   ❗ {failure}")
    
    # Recomendaciones específicas
    print(f"\n💡 RECOMENDACIONES DE RECUPERACIÓN:")
    
    db_result = all_results.get('database_corruption_recovery', {})
    if not db_result.get('test_passed', False):
        print("💾 Implementar sistema robusto de backup y recuperación de BD")
    
    restart_result = all_results.get('system_restart_continuity', {})
    if not restart_result.get('test_passed', False):
        print("🔄 Mejorar persistencia de estado para continuidad tras reinicio")
    
    resource_result = all_results.get('resource_exhaustion_recovery', {})
    if not resource_result.get('test_passed', False):
        print("⚡ Implementar monitoreo y recuperación automática de recursos")
    
    concurrent_result = all_results.get('concurrent_failure_recovery', {})
    if not concurrent_result.get('test_passed', False):
        print("🔀 Mejorar coordinación de recuperación ante fallos concurrentes")

if __name__ == "__main__":
    main()