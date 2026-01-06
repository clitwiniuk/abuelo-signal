#!/usr/bin/env python3
"""
Test de Stress y Límites del Sistema de Trading
Tests de carga extrema, límites de memoria, y robustez bajo presión
"""

import os
import sys
import sqlite3
import pandas as pd
import time
import psutil
import threading
import random
import gc
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from memory_profiler import profile as memory_profile
import resource
import tracemalloc

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class SystemResourceMonitor:
    """Monitor de recursos del sistema durante los tests"""
    
    def __init__(self):
        self.monitoring = False
        self.stats = []
        self.peak_memory = 0
        self.peak_cpu = 0
        
    def start_monitoring(self):
        """Iniciar monitoreo de recursos"""
        self.monitoring = True
        self.stats = []
        self.peak_memory = 0
        self.peak_cpu = 0
        
        def monitor_loop():
            while self.monitoring:
                try:
                    process = psutil.Process()
                    cpu_percent = process.cpu_percent()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    self.peak_cpu = max(self.peak_cpu, cpu_percent)
                    self.peak_memory = max(self.peak_memory, memory_mb)
                    
                    self.stats.append({
                        'timestamp': datetime.now(),
                        'cpu_percent': cpu_percent,
                        'memory_mb': memory_mb,
                        'threads': threading.active_count()
                    })
                    
                    time.sleep(0.1)  # Monitor cada 100ms
                    
                except Exception:
                    pass
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Detener monitoreo y obtener estadísticas"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1.0)
        
        if not self.stats:
            return {}
        
        cpu_values = [s['cpu_percent'] for s in self.stats]
        memory_values = [s['memory_mb'] for s in self.stats]
        
        return {
            'duration_seconds': len(self.stats) * 0.1,
            'peak_cpu_percent': self.peak_cpu,
            'peak_memory_mb': self.peak_memory,
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'avg_memory_mb': sum(memory_values) / len(memory_values),
            'max_threads': max(s['threads'] for s in self.stats),
            'samples_collected': len(self.stats)
        }

class StressTest:
    """Tests de stress del sistema"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.monitor = SystemResourceMonitor()
    
    def test_massive_insert_stress(self, num_trades: int = 10000) -> dict:
        """Test de inserción masiva bajo stress"""
        print(f"💥 Test de stress: Insertando {num_trades:,} trades...")
        
        results = {
            'target_trades': num_trades,
            'successful_inserts': 0,
            'failed_inserts': 0,
            'total_time': 0,
            'trades_per_second': 0,
            'memory_usage': {},
            'errors': []
        }
        
        # Iniciar monitoreo de memoria
        tracemalloc.start()
        self.monitor.start_monitoring()
        
        try:
            strategies = ['macdv_smallcaps', 'gap_go', 'orb', 'volume_breakout', 'vwap_smallcaps']
            symbols = [f'STRESS{i:04d}' for i in range(500)]  # 500 símbolos únicos
            
            start_time = time.time()
            
            # Generar y insertar trades en lotes para eficiencia
            batch_size = 100
            total_batches = num_trades // batch_size
            
            for batch_num in range(total_batches):
                batch_trades = []
                
                for i in range(batch_size):
                    trade_id = f"STRESS_MASSIVE_{batch_num:04d}_{i:03d}_{int(time.time())}"
                    
                    trade_data = {
                        'trade_id': trade_id,
                        'symbol': random.choice(symbols),
                        'strategy': random.choice(strategies),
                        'side': random.choice(['BUY', 'SELL']),
                        'quantity': random.randint(50, 1000),
                        'entry_price': round(random.uniform(0.5, 200.0), 4),
                        'entry_time': datetime.now() - timedelta(
                            days=random.randint(0, 365),
                            hours=random.randint(0, 23),
                            minutes=random.randint(0, 59)
                        ),
                        'status': random.choice(['OPEN', 'CLOSED']),
                        'notes': f'Stress test massive insert batch {batch_num}'
                    }
                    
                    # Para trades cerrados, agregar datos de salida
                    if trade_data['status'] == 'CLOSED':
                        entry_price = trade_data['entry_price']
                        price_change = random.uniform(-0.3, 0.5)  # -30% a +50%
                        trade_data['exit_price'] = round(entry_price * (1 + price_change), 4)
                        trade_data['exit_time'] = trade_data['entry_time'] + timedelta(
                            minutes=random.randint(5, 1440)  # 5min a 24h
                        )
                        
                        if trade_data['side'] == 'BUY':
                            trade_data['pnl'] = (trade_data['exit_price'] - entry_price) * trade_data['quantity']
                        else:
                            trade_data['pnl'] = (entry_price - trade_data['exit_price']) * trade_data['quantity']
                    
                    batch_trades.append(trade_data)
                
                # Insertar lote
                batch_success = 0
                for trade_data in batch_trades:
                    try:
                        if self.db_manager.save_trade(trade_data):
                            batch_success += 1
                        else:
                            results['failed_inserts'] += 1
                    except Exception as e:
                        results['failed_inserts'] += 1
                        if len(results['errors']) < 10:  # Limitar errores mostrados
                            results['errors'].append(f"Batch {batch_num}: {str(e)}")
                
                results['successful_inserts'] += batch_success
                
                # Mostrar progreso cada 1000 trades
                if (batch_num + 1) % 10 == 0:
                    processed = (batch_num + 1) * batch_size
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    print(f"   📊 Procesados {processed:,}/{num_trades:,} trades ({rate:.0f}/s)")
                
                # Forzar garbage collection periódicamente
                if batch_num % 50 == 0:
                    gc.collect()
            
            total_time = time.time() - start_time
            results['total_time'] = total_time
            results['trades_per_second'] = results['successful_inserts'] / total_time if total_time > 0 else 0
            
            # Obtener estadísticas de memoria
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            results['memory_usage'] = {
                'current_mb': current / 1024 / 1024,
                'peak_mb': peak / 1024 / 1024
            }
            
            # Detener monitoreo de recursos
            resource_stats = self.monitor.stop_monitoring()
            results['resource_stats'] = resource_stats
            
            print(f"   ✅ Completado: {results['successful_inserts']:,} trades en {total_time:.1f}s")
            print(f"   📈 Velocidad: {results['trades_per_second']:.0f} trades/segundo")
            print(f"   💾 Memoria pico: {results['memory_usage']['peak_mb']:.1f} MB")
            print(f"   🖥️  CPU pico: {resource_stats.get('peak_cpu_percent', 0):.1f}%")
            
            if results['failed_inserts'] > 0:
                print(f"   ⚠️  Inserciones fallidas: {results['failed_inserts']}")
            
            # Limpiar datos de prueba
            self._cleanup_stress_data()
            
        except Exception as e:
            results['errors'].append(f"Error crítico en stress test: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def test_concurrent_extreme_load(self, num_threads: int = 20, trades_per_thread: int = 100) -> dict:
        """Test de carga extrema con muchos threads concurrentes"""
        print(f"🔥 Test de carga extrema: {num_threads} threads, {trades_per_thread} trades cada uno...")
        
        results = {
            'num_threads': num_threads,
            'trades_per_thread': trades_per_thread,
            'successful_threads': 0,
            'total_trades_inserted': 0,
            'total_time': 0,
            'thread_results': [],
            'resource_usage': {},
            'errors': []
        }
        
        self.monitor.start_monitoring()
        
        def extreme_worker(thread_id: int, trades_count: int):
            """Worker extremo con inserción rápida"""
            thread_result = {
                'thread_id': thread_id,
                'successful_inserts': 0,
                'failed_inserts': 0,
                'execution_time': 0,
                'errors': []
            }
            
            try:
                start_time = time.time()
                
                for i in range(trades_count):
                    trade_data = {
                        'trade_id': f"EXTREME_T{thread_id:03d}_{i:04d}_{int(time.time()*1000000) % 1000000}",
                        'symbol': f'EXT{random.randint(1000, 9999)}',
                        'strategy': random.choice(['extreme_test', 'load_test', 'stress_test']),
                        'side': random.choice(['BUY', 'SELL']),
                        'quantity': random.randint(10, 500),
                        'entry_price': round(random.uniform(1.0, 100.0), 4),
                        'entry_time': datetime.now() - timedelta(seconds=random.randint(0, 3600)),
                        'status': 'OPEN',
                        'notes': f'Extreme load test T{thread_id}#{i}'
                    }
                    
                    try:
                        if self.db_manager.save_trade(trade_data):
                            thread_result['successful_inserts'] += 1
                        else:
                            thread_result['failed_inserts'] += 1
                    except Exception as e:
                        thread_result['failed_inserts'] += 1
                        if len(thread_result['errors']) < 5:
                            thread_result['errors'].append(str(e))
                    
                    # Sin pausa - máxima velocidad
                
                thread_result['execution_time'] = time.time() - start_time
                return thread_result
                
            except Exception as e:
                thread_result['errors'].append(f"Thread error: {e}")
                return thread_result
        
        # Ejecutar threads con máxima concurrencia
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Enviar todos los trabajos
            futures = [
                executor.submit(extreme_worker, i, trades_per_thread) 
                for i in range(num_threads)
            ]
            
            # Recoger resultados conforme completan
            completed = 0
            for future in as_completed(futures):
                try:
                    thread_result = future.result(timeout=60)  # 1 minuto timeout por thread
                    results['thread_results'].append(thread_result)
                    
                    if thread_result['successful_inserts'] > 0:
                        results['successful_threads'] += 1
                    
                    results['total_trades_inserted'] += thread_result['successful_inserts']
                    
                    completed += 1
                    if completed % 5 == 0:
                        print(f"   📊 Completados {completed}/{num_threads} threads")
                    
                except Exception as e:
                    results['errors'].append(f"Future error: {e}")
        
        total_time = time.time() - start_time
        results['total_time'] = total_time
        
        # Obtener estadísticas de recursos
        resource_stats = self.monitor.stop_monitoring()
        results['resource_usage'] = resource_stats
        
        # Mostrar resultados
        print(f"   ✅ Threads exitosos: {results['successful_threads']}/{num_threads}")
        print(f"   📊 Trades insertados: {results['total_trades_inserted']:,}")
        print(f"   ⏱️  Tiempo total: {total_time:.2f}s")
        print(f"   📈 Velocidad promedio: {results['total_trades_inserted']/total_time:.0f} trades/s")
        print(f"   💾 Memoria pico: {resource_stats.get('peak_memory_mb', 0):.1f} MB")
        print(f"   🖥️  CPU pico: {resource_stats.get('peak_cpu_percent', 0):.1f}%")
        
        if results['errors']:
            print(f"   ⚠️  Errores: {len(results['errors'])}")
        
        # Limpiar datos de prueba
        self._cleanup_extreme_data()
        
        return results
    
    def test_memory_leak_detection(self, iterations: int = 100) -> dict:
        """Test de detección de memory leaks"""
        print(f"🔍 Test de memory leaks: {iterations} iteraciones...")
        
        results = {
            'iterations': iterations,
            'memory_samples': [],
            'leak_detected': False,
            'memory_growth_mb': 0,
            'peak_memory_mb': 0,
            'avg_memory_mb': 0
        }
        
        # Forzar garbage collection inicial
        gc.collect()
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        print(f"   📊 Memoria inicial: {initial_memory:.1f} MB")
        
        for i in range(iterations):
            # Operación que podría causar memory leak
            test_trades = []
            for j in range(50):  # 50 trades por iteración
                trade_data = {
                    'trade_id': f"LEAK_TEST_{i:04d}_{j:03d}_{int(time.time())}",
                    'symbol': f'LEAK{j:03d}',
                    'strategy': 'memory_leak_test',
                    'side': 'BUY',
                    'quantity': 100,
                    'entry_price': 25.0,
                    'entry_time': datetime.now(),
                    'status': 'CLOSED',
                    'exit_price': 26.0,
                    'exit_time': datetime.now() + timedelta(minutes=30),
                    'pnl': 100.0,
                    'notes': f'Memory leak test iteration {i}'
                }
                
                self.db_manager.save_trade(trade_data)
                test_trades.append(trade_data)
            
            # Realizar consultas que podrían acumular memoria
            self.db_manager.get_trades(limit=100)
            self.db_manager.calculate_daily_stats()
            self.db_manager.get_strategy_performance(days=30)
            
            # Medir memoria cada 10 iteraciones
            if i % 10 == 0:
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                results['memory_samples'].append({
                    'iteration': i,
                    'memory_mb': current_memory
                })
                
                print(f"   📊 Iteración {i}: {current_memory:.1f} MB")
                
                # Forzar garbage collection
                gc.collect()
        
        # Análisis final de memoria
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        results['memory_growth_mb'] = final_memory - initial_memory
        results['peak_memory_mb'] = max(s['memory_mb'] for s in results['memory_samples'])
        results['avg_memory_mb'] = sum(s['memory_mb'] for s in results['memory_samples']) / len(results['memory_samples'])
        
        # Detectar leak (crecimiento > 50MB considerado sospechoso)
        if results['memory_growth_mb'] > 50:
            results['leak_detected'] = True
            print(f"   ⚠️  POSIBLE MEMORY LEAK detectado: +{results['memory_growth_mb']:.1f} MB")
        else:
            print(f"   ✅ No se detectó memory leak: +{results['memory_growth_mb']:.1f} MB")
        
        print(f"   📊 Memoria final: {final_memory:.1f} MB")
        print(f"   📈 Memoria pico: {results['peak_memory_mb']:.1f} MB")
        
        # Limpiar datos de prueba
        self._cleanup_leak_test_data()
        
        return results
    
    def test_database_size_limits(self) -> dict:
        """Test de límites de tamaño de base de datos"""
        print("💽 Test de límites de tamaño de base de datos...")
        
        results = {
            'initial_size_mb': 0,
            'final_size_mb': 0,
            'size_growth_mb': 0,
            'trades_added': 0,
            'vacuum_effectiveness': 0,
            'query_performance_degradation': {}
        }
        
        try:
            # Tamaño inicial
            db_path = Path(self.db_manager.db_path)
            results['initial_size_mb'] = db_path.stat().st_size / 1024 / 1024
            print(f"   📊 Tamaño inicial: {results['initial_size_mb']:.1f} MB")
            
            # Medir performance de consulta inicial
            start_time = time.time()
            initial_trades = self.db_manager.get_trades(limit=1000)
            initial_query_time = time.time() - start_time
            
            # Agregar datos hasta alcanzar límite razonable (100MB adicionales)
            target_growth = 100  # MB
            trades_added = 0
            
            while True:
                current_size = db_path.stat().st_size / 1024 / 1024
                growth = current_size - results['initial_size_mb']
                
                if growth >= target_growth:
                    break
                
                # Agregar lote de trades grandes (con notas extensas)
                batch_size = 500
                for i in range(batch_size):
                    # Crear trades con datos grandes para aumentar tamaño rápidamente
                    large_notes = "SIZE_TEST_" + "X" * 1000  # 1KB de notas
                    
                    trade_data = {
                        'trade_id': f"SIZE_TEST_{trades_added:08d}_{int(time.time())}",
                        'symbol': f'SIZE{trades_added % 1000:03d}',
                        'strategy': 'database_size_test_strategy_with_long_name',
                        'side': 'BUY',
                        'quantity': random.randint(1000, 5000),
                        'entry_price': round(random.uniform(10.0, 1000.0), 4),
                        'entry_time': datetime.now() - timedelta(days=random.randint(0, 1000)),
                        'status': 'CLOSED',
                        'exit_price': round(random.uniform(10.0, 1000.0), 4),
                        'exit_time': datetime.now() - timedelta(days=random.randint(0, 1000)),
                        'pnl': round(random.uniform(-1000.0, 2000.0), 2),
                        'notes': large_notes
                    }
                    
                    if self.db_manager.save_trade(trade_data):
                        trades_added += 1
                
                if trades_added % 5000 == 0:
                    current_size = db_path.stat().st_size / 1024 / 1024
                    print(f"   📊 Agregados {trades_added:,} trades, tamaño: {current_size:.1f} MB")
            
            results['trades_added'] = trades_added
            results['final_size_mb'] = db_path.stat().st_size / 1024 / 1024
            results['size_growth_mb'] = results['final_size_mb'] - results['initial_size_mb']
            
            print(f"   ✅ Agregados {trades_added:,} trades")
            print(f"   💽 Crecimiento: +{results['size_growth_mb']:.1f} MB")
            
            # Medir degradación de performance
            start_time = time.time()
            final_trades = self.db_manager.get_trades(limit=1000)
            final_query_time = time.time() - start_time
            
            degradation = ((final_query_time - initial_query_time) / initial_query_time * 100) if initial_query_time > 0 else 0
            results['query_performance_degradation'] = {
                'initial_query_ms': initial_query_time * 1000,
                'final_query_ms': final_query_time * 1000,
                'degradation_percent': degradation
            }
            
            print(f"   📊 Performance consulta: {initial_query_time*1000:.1f}ms → {final_query_time*1000:.1f}ms")
            if degradation > 0:
                print(f"   📈 Degradación: +{degradation:.1f}%")
            else:
                print(f"   📉 Mejora: {abs(degradation):.1f}%")
            
            # Test efectividad de VACUUM
            pre_vacuum_size = db_path.stat().st_size / 1024 / 1024
            
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("VACUUM")
            
            post_vacuum_size = db_path.stat().st_size / 1024 / 1024
            space_recovered = pre_vacuum_size - post_vacuum_size
            results['vacuum_effectiveness'] = space_recovered
            
            print(f"   🗜️  VACUUM recuperó: {space_recovered:.1f} MB")
            
            # Limpiar datos de prueba
            self._cleanup_size_test_data()
            
        except Exception as e:
            print(f"   ❌ ERROR en test de límites: {e}")
        
        return results
    
    def _cleanup_stress_data(self):
        """Limpiar datos de test de stress"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'STRESS_MASSIVE_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando stress data: {e}")
    
    def _cleanup_extreme_data(self):
        """Limpiar datos de test extremo"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'EXTREME_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando extreme data: {e}")
    
    def _cleanup_leak_test_data(self):
        """Limpiar datos de test de memory leak"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'LEAK_TEST_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando leak test data: {e}")
    
    def _cleanup_size_test_data(self):
        """Limpiar datos de test de tamaño"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'SIZE_TEST_%'")
                conn.commit()
                # VACUUM después de eliminar datos grandes
                conn.execute("VACUUM")
        except Exception as e:
            print(f"   ⚠️  Error limpiando size test data: {e}")

def main():
    """Ejecutar todos los tests de stress"""
    print("💥 TESTS DE STRESS Y LÍMITES DEL SISTEMA")
    print("=" * 50)
    
    # Verificar que memory_profiler está disponible
    try:
        import memory_profiler
    except ImportError:
        print("⚠️  memory_profiler no instalado. Instalar con: pip install memory-profiler")
        print("   Continuando sin profiling detallado de memoria...")
    
    stress_test = StressTest()
    all_results = {}
    
    # Test 1: Inserción masiva bajo stress
    print("\n1️⃣  TEST DE INSERCIÓN MASIVA BAJO STRESS")
    print("-" * 45)
    massive_results = stress_test.test_massive_insert_stress(5000)  # 5K trades
    all_results['massive_insert_stress'] = massive_results
    
    # Test 2: Carga extrema concurrente
    print("\n2️⃣  TEST DE CARGA EXTREMA CONCURRENTE")
    print("-" * 45)
    extreme_results = stress_test.test_concurrent_extreme_load(10, 50)  # 10 threads, 50 trades c/u
    all_results['extreme_concurrent_load'] = extreme_results
    
    # Test 3: Detección de memory leaks
    print("\n3️⃣  TEST DE DETECCIÓN DE MEMORY LEAKS")
    print("-" * 45)
    leak_results = stress_test.test_memory_leak_detection(50)  # 50 iteraciones
    all_results['memory_leak_detection'] = leak_results
    
    # Test 4: Límites de tamaño de base de datos
    print("\n4️⃣  TEST DE LÍMITES DE TAMAÑO DE DB")
    print("-" * 45)
    size_results = stress_test.test_database_size_limits()
    all_results['database_size_limits'] = size_results
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE TESTS DE STRESS")
    print("=" * 50)
    
    test_categories = {
        'massive_insert_stress': 'Inserción Masiva Bajo Stress',
        'extreme_concurrent_load': 'Carga Extrema Concurrente',
        'memory_leak_detection': 'Detección de Memory Leaks',
        'database_size_limits': 'Límites de Tamaño de DB'
    }
    
    passed_tests = 0
    total_tests = len(all_results)
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            
            # Determinar si pasó basado en criterios específicos
            passed = False
            metrics_info = ""
            
            if test_key == 'massive_insert_stress':
                success_rate = result.get('successful_inserts', 0) / result.get('target_trades', 1)
                passed = success_rate > 0.95  # 95% de éxito mínimo
                tps = result.get('trades_per_second', 0)
                metrics_info = f"({tps:.0f} trades/s, {success_rate*100:.1f}% éxito)"
                
            elif test_key == 'extreme_concurrent_load':
                thread_success_rate = result.get('successful_threads', 0) / result.get('num_threads', 1)
                passed = thread_success_rate > 0.8  # 80% de threads exitosos
                total_trades = result.get('total_trades_inserted', 0)
                metrics_info = f"({total_trades:,} trades, {thread_success_rate*100:.0f}% threads OK)"
                
            elif test_key == 'memory_leak_detection':
                passed = not result.get('leak_detected', True)
                growth = result.get('memory_growth_mb', 0)
                metrics_info = f"(+{growth:.1f} MB crecimiento)"
                
            elif test_key == 'database_size_limits':
                # Pasó si completó sin errores críticos
                passed = result.get('trades_added', 0) > 1000
                size_growth = result.get('size_growth_mb', 0)
                trades_added = result.get('trades_added', 0)
                metrics_info = f"({trades_added:,} trades, +{size_growth:.1f} MB)"
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status} {metrics_info}")
            
            if passed:
                passed_tests += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de stress pasaron")
    
    # Recomendaciones específicas de stress
    print("\n💡 RECOMENDACIONES DE STRESS:")
    
    if passed_tests == total_tests:
        print("🏆 ¡Sistema extremadamente robusto!")
        print("✅ Maneja cargas pesadas sin problemas")
        print("🚀 Listo para alto volumen de producción")
    elif passed_tests >= total_tests * 0.75:
        print("💪 Sistema robusto con limitaciones menores")
        print("⚠️  Revisar tests fallidos para optimización")
        print("📊 Considerar límites de carga en producción")
    else:
        print("⚠️  Sistema necesita optimización para cargas pesadas")
        print("🔧 Crítico mejorar rendimiento antes de producción")
        print("📉 Establecer límites de carga conservadores")
    
    # Recomendaciones específicas por resultados
    massive_result = all_results.get('massive_insert_stress', {})
    if massive_result.get('trades_per_second', 0) < 100:
        print("📊 Optimizar velocidad de inserción (< 100 trades/s)")
    
    leak_result = all_results.get('memory_leak_detection', {})
    if leak_result.get('leak_detected', False):
        print("🔍 Investigar y corregir memory leaks detectados")
    
    extreme_result = all_results.get('extreme_concurrent_load', {})
    if extreme_result.get('successful_threads', 0) < extreme_result.get('num_threads', 1) * 0.8:
        print("🔀 Mejorar manejo de concurrencia extrema")

if __name__ == "__main__":
    main()