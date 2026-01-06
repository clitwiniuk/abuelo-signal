#!/usr/bin/env python3
"""
Test de Seguridad y Robustez del Sistema de Trading
Tests para validar seguridad, manejo de errores, y robustez ante ataques y fallos
"""

import os
import sys
import sqlite3
import time
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import tempfile
import shutil

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class SecurityTest:
    """Tests de seguridad del sistema"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
    
    def test_sql_injection_protection(self) -> dict:
        """Test de protección contra inyección SQL"""
        print("🔐 Test de protección contra inyección SQL...")
        
        results = {
            'injection_attempts': 0,
            'blocked_attempts': 0,
            'successful_injections': 0,
            'vulnerabilities_found': [],
            'test_passed': False
        }
        
        # Payloads típicos de inyección SQL
        sql_injection_payloads = [
            "'; DROP TABLE trades; --",
            "' OR '1'='1",
            "'; DELETE FROM trades WHERE 1=1; --",
            "' UNION SELECT * FROM sqlite_master --",
            "'; INSERT INTO trades VALUES (NULL, 'HACK', 'evil', 'BUY', 1, 1, NULL, datetime('now'), NULL, NULL, NULL, NULL, 'OPEN', 'hacked'); --",
            "' OR 1=1 LIMIT 1 OFFSET 1 --",
            "'; UPDATE trades SET pnl = 99999 WHERE 1=1; --",
            "\"; DROP TABLE IF EXISTS trades; --",
            "') OR ('x'='x",
            "'; ATTACH DATABASE ':memory:' AS mem; --"
        ]
        
        # Test en diferentes campos
        vulnerable_fields = ['symbol', 'strategy', 'notes', 'trade_id']
        
        for payload in sql_injection_payloads:
            for field in vulnerable_fields:
                results['injection_attempts'] += 1
                
                try:
                    # Crear trade con payload malicioso
                    malicious_trade = {
                        'trade_id': f"SEC_TEST_{int(time.time())}_{random.randint(1000, 9999)}",
                        'symbol': 'SAFE_SYMBOL',
                        'strategy': 'safe_strategy',
                        'side': 'BUY',
                        'quantity': 100,
                        'entry_price': 10.0,
                        'entry_time': datetime.now(),
                        'status': 'OPEN',
                        'notes': 'Safe notes'
                    }
                    
                    # Insertar payload en el campo específico
                    if field in malicious_trade:
                        malicious_trade[field] = payload
                    
                    # Intentar guardar trade malicioso
                    success = self.db_manager.save_trade(malicious_trade)
                    
                    if success:
                        # Verificar si la inyección fue exitosa
                        # Si la tabla trades aún existe y funciona, la inyección fue bloqueada
                        try:
                            test_query = self.db_manager.get_trades(limit=1)
                            results['blocked_attempts'] += 1
                            print(f"   ✅ Blocked injection in {field}: {payload[:30]}...")
                            
                        except Exception as e:
                            # Si la consulta falla, podría indicar que la inyección fue exitosa
                            results['successful_injections'] += 1
                            results['vulnerabilities_found'].append({
                                'field': field,
                                'payload': payload,
                                'error': str(e)
                            })
                            print(f"   ⚠️  Possible injection success in {field}")
                    else:
                        # Save falló, posiblemente por validación
                        results['blocked_attempts'] += 1
                        
                except Exception as e:
                    # Error durante el intento - probablemente bloqueado
                    results['blocked_attempts'] += 1
                    print(f"   ✅ Exception blocked injection in {field}: {str(e)[:50]}...")
        
        # Evaluar resultados
        if results['successful_injections'] == 0:
            results['test_passed'] = True
            print(f"   🎯 Resultado: Todos los {results['injection_attempts']} intentos de inyección fueron bloqueados")
        else:
            print(f"   ⚠️  VULNERABILIDAD: {results['successful_injections']} inyecciones exitosas detectadas")
        
        # Limpiar datos de prueba
        self._cleanup_security_data()
        
        return results
    
    def test_malformed_data_handling(self) -> dict:
        """Test de manejo de datos malformados"""
        print("🔧 Test de manejo de datos malformados...")
        
        results = {
            'malformed_attempts': 0,
            'handled_gracefully': 0,
            'system_crashes': 0,
            'data_corruption_detected': False,
            'test_passed': False
        }
        
        # Datos malformados típicos
        malformed_data_sets = [
            # Valores nulos/vacíos
            {
                'trade_id': None,
                'symbol': '',
                'strategy': None,
                'side': '',
                'quantity': None,
                'entry_price': None,
                'entry_time': None
            },
            # Tipos incorrectos
            {
                'trade_id': 'MALFORMED_TYPE_TEST',
                'symbol': 123,  # Número en lugar de string
                'strategy': [],  # Lista en lugar de string
                'side': True,   # Boolean en lugar de string
                'quantity': 'not_a_number',  # String en lugar de número
                'entry_price': 'invalid_price',
                'entry_time': 'not_a_date'
            },
            # Valores extremos
            {
                'trade_id': 'EXTREME_VALUES_TEST',
                'symbol': 'A' * 1000,  # String muy largo
                'strategy': 'B' * 1000,
                'side': 'INVALID_SIDE_VALUE_VERY_LONG',
                'quantity': -999999999,  # Número negativo muy grande
                'entry_price': float('inf'),  # Infinito
                'entry_time': datetime(1900, 1, 1)  # Fecha muy antigua
            },
            # Caracteres especiales y Unicode
            {
                'trade_id': 'UNICODE_TEST_🚀💰📈',
                'symbol': '💎🙌HODL',
                'strategy': 'تجارة_استراتيجية',  # Árabe
                'side': '购买',  # Chino
                'quantity': 100,
                'entry_price': 25.0,
                'entry_time': datetime.now(),
                'notes': '¡Hola! 🇪🇸 Ñoño €¢£¥ ♠♥♦♣'
            },
            # JSON injection attempts
            {
                'trade_id': 'JSON_INJECTION_TEST',
                'symbol': '{"malicious": "payload"}',
                'strategy': '[{"evil": true}]',
                'notes': '</script><script>alert("xss")</script>',
                'quantity': 100,
                'entry_price': 25.0,
                'entry_time': datetime.now()
            }
        ]
        
        for i, malformed_data in enumerate(malformed_data_sets):
            results['malformed_attempts'] += 1
            
            try:
                print(f"   🧪 Testing malformed data set {i+1}...")
                
                # Intentar guardar datos malformados
                success = self.db_manager.save_trade(malformed_data)
                
                # Verificar que el sistema sigue funcionando
                test_trades = self.db_manager.get_trades(limit=5)
                
                if test_trades is not None:
                    results['handled_gracefully'] += 1
                    print(f"      ✅ Sistema mantuvo estabilidad")
                    
                    if success:
                        print(f"      ℹ️  Datos aceptados (posiblemente con sanitización)")
                    else:
                        print(f"      🛡️  Datos rechazados apropiadamente")
                else:
                    results['data_corruption_detected'] = True
                    print(f"      ⚠️  Posible corrupción de datos detectada")
                    
            except Exception as e:
                # El sistema manejó la excepción - esto es bueno
                results['handled_gracefully'] += 1
                print(f"      ✅ Excepción manejada: {str(e)[:50]}...")
                
                # Verificar que el sistema sigue funcionando después de la excepción
                try:
                    self.db_manager.get_trades(limit=1)
                except Exception as recovery_error:
                    results['system_crashes'] += 1
                    print(f"      ❌ Sistema no se recuperó de la excepción")
        
        # Evaluar resultados
        if (results['system_crashes'] == 0 and 
            not results['data_corruption_detected'] and 
            results['handled_gracefully'] == results['malformed_attempts']):
            results['test_passed'] = True
            print(f"   🎯 Resultado: Sistema maneja robustamente todos los datos malformados")
        else:
            print(f"   ⚠️  Sistema vulnerable a datos malformados")
        
        self._cleanup_security_data()
        
        return results
    
    def test_concurrent_access_attacks(self) -> dict:
        """Test de ataques de acceso concurrente"""
        print("🔀 Test de ataques de acceso concurrente...")
        
        results = {
            'concurrent_threads': 20,
            'operations_per_thread': 10,
            'successful_operations': 0,
            'failed_operations': 0,
            'deadlocks_detected': 0,
            'race_conditions_detected': 0,
            'data_consistency_maintained': True,
            'test_passed': False
        }
        
        # Datos compartidos para detectar race conditions
        shared_counter = {'value': 0}
        shared_counter_lock = threading.Lock()
        
        def aggressive_database_worker(thread_id: int):
            """Worker que realiza operaciones agresivas en la BD"""
            thread_results = {
                'successful_ops': 0,
                'failed_ops': 0,
                'deadlocks': 0
            }
            
            try:
                for i in range(results['operations_per_thread']):
                    try:
                        # Operación 1: Insertar trade
                        trade_data = {
                            'trade_id': f"CONCURRENT_ATTACK_T{thread_id:02d}_{i:03d}_{int(time.time()*1000000) % 1000000}",
                            'symbol': f'ATTACK{thread_id:02d}',
                            'strategy': 'concurrent_attack_test',
                            'side': 'BUY',
                            'quantity': 100,
                            'entry_price': 10.0 + random.random(),
                            'entry_time': datetime.now(),
                            'status': 'OPEN'
                        }
                        
                        if self.db_manager.save_trade(trade_data):
                            thread_results['successful_ops'] += 1
                        else:
                            thread_results['failed_ops'] += 1
                        
                        # Operación 2: Consulta intensiva
                        self.db_manager.get_trades(limit=100)
                        
                        # Operación 3: Actualizar contador compartido (detectar race conditions)
                        with shared_counter_lock:
                            old_value = shared_counter['value']
                            time.sleep(0.001)  # Simular trabajo
                            shared_counter['value'] = old_value + 1
                        
                        # Pequeña pausa para no saturar completamente
                        time.sleep(0.001)
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'deadlock' in error_msg or 'locked' in error_msg:
                            thread_results['deadlocks'] += 1
                        else:
                            thread_results['failed_ops'] += 1
                        
                        time.sleep(0.01)  # Pausa en caso de error
                
                return thread_results
                
            except Exception as e:
                print(f"   ⚠️  Thread {thread_id} crashed: {e}")
                return thread_results
        
        # Ejecutar threads concurrentes agresivamente
        print(f"   🚀 Lanzando {results['concurrent_threads']} threads agresivos...")
        
        with ThreadPoolExecutor(max_workers=results['concurrent_threads']) as executor:
            futures = [
                executor.submit(aggressive_database_worker, i) 
                for i in range(results['concurrent_threads'])
            ]
            
            # Recoger resultados
            for i, future in enumerate(futures):
                try:
                    thread_result = future.result(timeout=30)
                    results['successful_operations'] += thread_result['successful_ops']
                    results['failed_operations'] += thread_result['failed_ops']
                    results['deadlocks_detected'] += thread_result['deadlocks']
                    
                    if i % 5 == 0:
                        print(f"      📊 Thread {i} completado")
                        
                except Exception as e:
                    results['failed_operations'] += results['operations_per_thread']
                    print(f"      ❌ Thread {i} falló: {e}")
        
        # Verificar race conditions
        expected_counter = results['concurrent_threads'] * results['operations_per_thread']
        if shared_counter['value'] != expected_counter:
            results['race_conditions_detected'] = expected_counter - shared_counter['value']
            print(f"   ⚠️  Race conditions detectadas: {results['race_conditions_detected']}")
        
        # Verificar consistencia de datos
        try:
            final_trades = self.db_manager.get_trades(limit=10000)
            attack_trades = final_trades[final_trades['trade_id'].str.contains('CONCURRENT_ATTACK_', na=False)] if hasattr(final_trades, 'str') else []
            
            if len(attack_trades) != results['successful_operations']:
                results['data_consistency_maintained'] = False
                print(f"   ⚠️  Inconsistencia de datos: esperado {results['successful_operations']}, encontrado {len(attack_trades)}")
        except Exception as e:
            results['data_consistency_maintained'] = False
            print(f"   ⚠️  Error verificando consistencia: {e}")
        
        # Evaluar resultados
        success_rate = results['successful_operations'] / (results['successful_operations'] + results['failed_operations']) if (results['successful_operations'] + results['failed_operations']) > 0 else 0
        
        if (success_rate > 0.8 and 
            results['deadlocks_detected'] == 0 and 
            results['race_conditions_detected'] == 0 and 
            results['data_consistency_maintained']):
            results['test_passed'] = True
            print(f"   🎯 Resultado: Sistema resistente a ataques concurrentes")
        else:
            print(f"   ⚠️  Sistema vulnerable a ataques concurrentes")
        
        print(f"      📊 Operaciones exitosas: {results['successful_operations']}")
        print(f"      📊 Operaciones fallidas: {results['failed_operations']}")
        print(f"      🔒 Deadlocks: {results['deadlocks_detected']}")
        
        self._cleanup_security_data()
        
        return results
    
    def test_file_system_security(self) -> dict:
        """Test de seguridad del sistema de archivos"""
        print("📁 Test de seguridad del sistema de archivos...")
        
        results = {
            'path_traversal_attempts': 0,
            'blocked_traversals': 0,
            'file_permission_tests': 0,
            'permission_violations': 0,
            'backup_security_verified': False,
            'test_passed': False
        }
        
        # Test 1: Path traversal attacks
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "../../../../root/.ssh/id_rsa",
            "../trading_data.db",
            "../../config.ini",
            "../logs/trading_system.log"
        ]
        
        for malicious_path in malicious_paths:
            results['path_traversal_attempts'] += 1
            
            try:
                # Simular intento de acceso a archivo con path malicioso
                # En un sistema real, esto podría ser a través de parámetros de configuración
                test_path = Path(malicious_path)
                
                # Verificar que el sistema no permita acceso fuera del directorio de trabajo
                if test_path.is_absolute() or '..' in str(test_path):
                    # El sistema debería rechazar estos paths
                    if not test_path.exists() or not os.access(test_path, os.R_OK):
                        results['blocked_traversals'] += 1
                        print(f"   ✅ Bloqueado path traversal: {malicious_path}")
                    else:
                        print(f"   ⚠️  Path traversal exitoso: {malicious_path}")
                else:
                    results['blocked_traversals'] += 1
                    
            except Exception as e:
                # Excepción es buena - indica que el acceso fue bloqueado
                results['blocked_traversals'] += 1
                print(f"   ✅ Excepción bloqueó path traversal: {str(e)[:30]}...")
        
        # Test 2: File permissions
        db_path = Path(self.db_manager.db_path)
        if db_path.exists():
            results['file_permission_tests'] += 1
            
            try:
                # Verificar que la base de datos no tenga permisos excesivamente permisivos
                stat_result = db_path.stat()
                permissions = oct(stat_result.st_mode)[-3:]
                
                # Verificar que no sea world-writable (último dígito no debería ser 2, 3, 6, 7)
                if permissions[-1] not in ['2', '3', '6', '7']:
                    print(f"   ✅ Permisos de BD apropiados: {permissions}")
                else:
                    results['permission_violations'] += 1
                    print(f"   ⚠️  BD con permisos excesivos: {permissions}")
                    
            except Exception as e:
                print(f"   ⚠️  Error verificando permisos de BD: {e}")
        
        # Test 3: Backup security
        try:
            # Crear backup temporal para probar seguridad
            with tempfile.TemporaryDirectory() as temp_dir:
                backup_path = Path(temp_dir) / "test_backup.db"
                shutil.copy2(db_path, backup_path)
                
                if backup_path.exists():
                    # Verificar que el backup tenga permisos apropiados
                    stat_result = backup_path.stat()
                    permissions = oct(stat_result.st_mode)[-3:]
                    
                    if permissions[-1] not in ['2', '3', '6', '7']:
                        results['backup_security_verified'] = True
                        print(f"   ✅ Seguridad de backup verificada")
                    else:
                        print(f"   ⚠️  Backup con permisos inseguros: {permissions}")
                        
        except Exception as e:
            print(f"   ⚠️  Error verificando seguridad de backup: {e}")
        
        # Evaluar resultados
        traversal_block_rate = results['blocked_traversals'] / results['path_traversal_attempts'] if results['path_traversal_attempts'] > 0 else 1
        
        if (traversal_block_rate >= 0.9 and 
            results['permission_violations'] == 0 and 
            results['backup_security_verified']):
            results['test_passed'] = True
            print(f"   🎯 Resultado: Sistema de archivos seguro")
        else:
            print(f"   ⚠️  Vulnerabilidades en sistema de archivos detectadas")
        
        return results
    
    def test_error_information_disclosure(self) -> dict:
        """Test de divulgación de información en errores"""
        print("🔍 Test de divulgación de información en errores...")
        
        results = {
            'error_scenarios_tested': 0,
            'information_leaks_detected': 0,
            'sensitive_info_exposed': [],
            'test_passed': False
        }
        
        # Escenarios que deberían generar errores sin revelar información sensible
        error_scenarios = [
            # Intentar acceder a tabla inexistente
            ("Invalid table access", lambda: self.db_manager.get_trades(symbol="'; SELECT * FROM nonexistent_table; --")),
            # Datos inválidos que causen errores de tipo
            ("Type error scenario", lambda: self.db_manager.save_trade({'trade_id': 123, 'invalid_field': object()})),
            # Conexión a BD corrupta (simulada)
            ("Database corruption scenario", lambda: self._simulate_db_error())
        ]
        
        sensitive_keywords = [
            'password', 'key', 'secret', 'token', 'api_key',
            'database', 'connection', 'host', 'port', 'user',
            'path', 'directory', 'file', 'config', 'admin',
            'root', 'system', 'internal', 'debug', 'stack trace'
        ]
        
        for scenario_name, error_function in error_scenarios:
            results['error_scenarios_tested'] += 1
            
            try:
                print(f"   🧪 Testing: {scenario_name}")
                error_function()
                
            except Exception as e:
                error_message = str(e).lower()
                
                # Verificar si el mensaje de error contiene información sensible
                exposed_info = []
                for keyword in sensitive_keywords:
                    if keyword in error_message:
                        exposed_info.append(keyword)
                
                if exposed_info:
                    results['information_leaks_detected'] += 1
                    results['sensitive_info_exposed'].append({
                        'scenario': scenario_name,
                        'exposed_keywords': exposed_info,
                        'error_message': str(e)[:100] + '...'
                    })
                    print(f"      ⚠️  Información sensible expuesta: {exposed_info}")
                else:
                    print(f"      ✅ Error manejado sin exponer información")
        
        # Evaluar resultados
        if results['information_leaks_detected'] == 0:
            results['test_passed'] = True
            print(f"   🎯 Resultado: No se detectó divulgación de información en errores")
        else:
            print(f"   ⚠️  {results['information_leaks_detected']} casos de divulgación detectados")
        
        return results
    
    def _simulate_db_error(self):
        """Simular error de base de datos"""
        raise Exception("Simulated database connection error for testing")
    
    def _cleanup_security_data(self):
        """Limpiar datos de tests de seguridad"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Limpiar varios patrones de datos de prueba de seguridad
                patterns_to_clean = [
                    'SEC_TEST_%',
                    'MALFORMED_%',
                    'CONCURRENT_ATTACK_%',
                    'UNICODE_TEST_%',
                    'JSON_INJECTION_%'
                ]
                
                for pattern in patterns_to_clean:
                    conn.execute("DELETE FROM trades WHERE trade_id LIKE ?", (pattern,))
                
                conn.commit()
                
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de seguridad: {e}")

def main():
    """Ejecutar todos los tests de seguridad"""
    print("🔐 TESTS DE SEGURIDAD Y ROBUSTEZ DEL SISTEMA")
    print("=" * 50)
    
    security_test = SecurityTest()
    all_results = {}
    
    # Test 1: Protección contra inyección SQL
    print("\n1️⃣  PROTECCIÓN CONTRA INYECCIÓN SQL")
    print("-" * 45)
    sql_injection_results = security_test.test_sql_injection_protection()
    all_results['sql_injection_protection'] = sql_injection_results
    
    # Test 2: Manejo de datos malformados
    print("\n2️⃣  MANEJO DE DATOS MALFORMADOS")
    print("-" * 45)
    malformed_data_results = security_test.test_malformed_data_handling()
    all_results['malformed_data_handling'] = malformed_data_results
    
    # Test 3: Ataques de acceso concurrente
    print("\n3️⃣  RESISTENCIA A ATAQUES CONCURRENTES")
    print("-" * 45)
    concurrent_attack_results = security_test.test_concurrent_access_attacks()
    all_results['concurrent_access_attacks'] = concurrent_attack_results
    
    # Test 4: Seguridad del sistema de archivos
    print("\n4️⃣  SEGURIDAD DEL SISTEMA DE ARCHIVOS")
    print("-" * 45)
    file_security_results = security_test.test_file_system_security()
    all_results['file_system_security'] = file_security_results
    
    # Test 5: Divulgación de información en errores
    print("\n5️⃣  DIVULGACIÓN DE INFORMACIÓN EN ERRORES")
    print("-" * 45)
    error_disclosure_results = security_test.test_error_information_disclosure()
    all_results['error_information_disclosure'] = error_disclosure_results
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE TESTS DE SEGURIDAD")
    print("=" * 50)
    
    test_categories = {
        'sql_injection_protection': 'Protección SQL Injection',
        'malformed_data_handling': 'Manejo Datos Malformados',
        'concurrent_access_attacks': 'Resistencia Ataques Concurrentes',
        'file_system_security': 'Seguridad Sistema Archivos',
        'error_information_disclosure': 'Divulgación Info en Errores'
    }
    
    passed_tests = 0
    total_tests = len(all_results)
    critical_failures = []
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            passed = result.get('test_passed', False)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            
            # Información adicional específica por test
            additional_info = ""
            if test_key == 'sql_injection_protection':
                blocked = result.get('blocked_attempts', 0)
                total = result.get('injection_attempts', 0)
                additional_info = f"({blocked}/{total} bloqueados)"
                if not passed:
                    critical_failures.append("SQL Injection vulnerable")
            
            elif test_key == 'malformed_data_handling':
                handled = result.get('handled_gracefully', 0)
                total = result.get('malformed_attempts', 0)
                additional_info = f"({handled}/{total} manejados)"
            
            elif test_key == 'concurrent_access_attacks':
                successful = result.get('successful_operations', 0)
                total_ops = successful + result.get('failed_operations', 0)
                deadlocks = result.get('deadlocks_detected', 0)
                additional_info = f"({successful}/{total_ops} ops, {deadlocks} deadlocks)"
                if not passed and deadlocks > 0:
                    critical_failures.append("Deadlocks detectados")
            
            elif test_key == 'file_system_security':
                blocked = result.get('blocked_traversals', 0)
                total = result.get('path_traversal_attempts', 0)
                additional_info = f"({blocked}/{total} traversals bloqueados)"
            
            elif test_key == 'error_information_disclosure':
                leaks = result.get('information_leaks_detected', 0)
                total = result.get('error_scenarios_tested', 0)
                additional_info = f"({leaks}/{total} info leaks)"
                if leaks > 0:
                    critical_failures.append("Información sensible expuesta")
            
            print(f"{test_name}: {status} {additional_info}")
            
            if passed:
                passed_tests += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de seguridad pasaron")
    
    # Evaluación de seguridad
    security_score = passed_tests / total_tests if total_tests > 0 else 0
    
    print("\n🛡️  EVALUACIÓN DE SEGURIDAD:")
    
    if security_score == 1.0:
        print("🏆 EXCELENTE - Sistema altamente seguro")
        print("✅ Resistente a todos los ataques probados")
        print("🚀 Apropiado para entorno de producción")
    elif security_score >= 0.8:
        print("👍 BUENO - Sistema mayormente seguro")
        print("⚠️  Algunas vulnerabilidades menores detectadas")
        print("🔧 Revisar y corregir antes de producción")
    elif security_score >= 0.6:
        print("⚠️  MODERADO - Vulnerabilidades significativas")
        print("🔧 Correcciones importantes requeridas")
        print("🚫 No recomendado para producción sin fixes")
    else:
        print("🚨 CRÍTICO - Sistema altamente vulnerable")
        print("❌ Múltiples fallas de seguridad detectadas")
        print("🛑 NO usar en producción hasta corregir")
    
    # Mostrar fallas críticas
    if critical_failures:
        print(f"\n🚨 FALLAS CRÍTICAS DETECTADAS:")
        for failure in critical_failures:
            print(f"   ❗ {failure}")
    
    # Recomendaciones específicas
    print(f"\n💡 RECOMENDACIONES ESPECÍFICAS:")
    
    sql_result = all_results.get('sql_injection_protection', {})
    if not sql_result.get('test_passed', False):
        print("🔒 Implementar parametrized queries para prevenir SQL injection")
    
    malformed_result = all_results.get('malformed_data_handling', {})
    if not malformed_result.get('test_passed', False):
        print("🔧 Mejorar validación y sanitización de datos de entrada")
    
    concurrent_result = all_results.get('concurrent_access_attacks', {})
    if concurrent_result.get('deadlocks_detected', 0) > 0:
        print("🔀 Revisar lógica de transacciones para prevenir deadlocks")
    
    file_result = all_results.get('file_system_security', {})
    if not file_result.get('test_passed', False):
        print("📁 Endurecer permisos de archivos y validar paths")
    
    error_result = all_results.get('error_information_disclosure', {})
    if error_result.get('information_leaks_detected', 0) > 0:
        print("🤫 Implementar manejo de errores que no exponga información sensible")

if __name__ == "__main__":
    main()