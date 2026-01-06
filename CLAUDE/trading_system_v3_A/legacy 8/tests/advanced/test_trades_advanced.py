#!/usr/bin/env python3
"""
Tests Avanzados para el Sistema de Trades
Tests más completos que cubren rendimiento, concurrencia, integridad y casos edge
"""

import os
import sys
import sqlite3
import pandas as pd
import time
import asyncio
import threading
import random
from datetime import datetime, timedelta, date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class TradeTestSuite:
    """Suite completa de tests para el sistema de trades"""
    
    def __init__(self):
        self.test_results = {}
        self.performance_metrics = {}
        
    def log_result(self, test_name: str, passed: bool, metrics: dict = None):
        """Registrar resultado de un test"""
        self.test_results[test_name] = {
            'passed': passed,
            'timestamp': datetime.now(),
            'metrics': metrics or {}
        }

class DatabasePerformanceTest:
    """Tests de rendimiento de la base de datos"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        
    def test_bulk_insert_performance(self, num_trades: int = 1000) -> dict:
        """Test de inserción masiva de trades"""
        print(f"🚀 Test de rendimiento: Insertando {num_trades} trades...")
        
        try:
            # Generar datos de prueba
            test_trades = []
            strategies = ['macdv_smallcaps', 'gap_go', 'orb', 'volume_breakout']
            symbols = [f'TEST{i:03d}' for i in range(100)]  # 100 símbolos únicos
            
            start_time = time.time()
            
            for i in range(num_trades):
                trade_data = {
                    'trade_id': f"PERF_TEST_{i:06d}_{int(time.time())}",
                    'symbol': random.choice(symbols),
                    'strategy': random.choice(strategies),
                    'side': random.choice(['BUY', 'SELL']),
                    'quantity': random.randint(50, 500),
                    'entry_price': round(random.uniform(1.0, 100.0), 4),
                    'entry_time': datetime.now() - timedelta(days=random.randint(0, 30)),
                    'status': random.choice(['OPEN', 'CLOSED']),
                    'notes': f'Performance test trade {i}'
                }
                
                # Para trades cerrados, agregar datos de salida
                if trade_data['status'] == 'CLOSED':
                    entry_price = trade_data['entry_price']
                    price_change = random.uniform(-0.1, 0.1)  # ±10%
                    trade_data['exit_price'] = round(entry_price * (1 + price_change), 4)
                    trade_data['exit_time'] = trade_data['entry_time'] + timedelta(minutes=random.randint(5, 240))
                    
                    if trade_data['side'] == 'BUY':
                        trade_data['pnl'] = (trade_data['exit_price'] - entry_price) * trade_data['quantity']
                    else:
                        trade_data['pnl'] = (entry_price - trade_data['exit_price']) * trade_data['quantity']
                
                test_trades.append(trade_data)
            
            # Insertar trades uno por uno (simulando uso real)
            insert_times = []
            for trade_data in test_trades:
                insert_start = time.time()
                success = self.db_manager.save_trade(trade_data)
                insert_end = time.time()
                
                if success:
                    insert_times.append(insert_end - insert_start)
            
            total_time = time.time() - start_time
            
            metrics = {
                'total_trades': len(test_trades),
                'successful_inserts': len(insert_times),
                'total_time': total_time,
                'trades_per_second': len(insert_times) / total_time if total_time > 0 else 0,
                'avg_insert_time': sum(insert_times) / len(insert_times) if insert_times else 0,
                'max_insert_time': max(insert_times) if insert_times else 0,
                'min_insert_time': min(insert_times) if insert_times else 0
            }
            
            print(f"   ✅ Insertados {metrics['successful_inserts']}/{num_trades} trades")
            print(f"   ⏱️  Tiempo total: {total_time:.2f}s")
            print(f"   📊 Velocidad: {metrics['trades_per_second']:.1f} trades/segundo")
            print(f"   🕐 Tiempo promedio por insert: {metrics['avg_insert_time']*1000:.2f}ms")
            
            # Limpiar datos de prueba
            self._cleanup_test_trades()
            
            return metrics
            
        except Exception as e:
            print(f"   ❌ ERROR en test de rendimiento: {e}")
            return {}
    
    def test_query_performance(self) -> dict:
        """Test de rendimiento de consultas"""
        print("🔍 Test de rendimiento de consultas...")
        
        try:
            metrics = {}
            
            # Test 1: Consulta básica de todos los trades
            start_time = time.time()
            all_trades = self.db_manager.get_trades(limit=10000)
            query1_time = time.time() - start_time
            metrics['query_all_trades'] = {
                'time': query1_time,
                'results': len(all_trades)
            }
            
            # Test 2: Consulta filtrada por símbolo
            start_time = time.time()
            if not all_trades.empty:
                test_symbol = all_trades.iloc[0]['symbol']
                symbol_trades = self.db_manager.get_trades(symbol=test_symbol, limit=1000)
                query2_time = time.time() - start_time
                metrics['query_by_symbol'] = {
                    'time': query2_time,
                    'results': len(symbol_trades),
                    'symbol': test_symbol
                }
            
            # Test 3: Consulta de estadísticas diarias
            start_time = time.time()
            daily_stats = self.db_manager.calculate_daily_stats()
            query3_time = time.time() - start_time
            metrics['query_daily_stats'] = {
                'time': query3_time,
                'stats': daily_stats
            }
            
            # Test 4: Performance por estrategia
            start_time = time.time()
            strategy_perf = self.db_manager.get_strategy_performance(days=30)
            query4_time = time.time() - start_time
            metrics['query_strategy_performance'] = {
                'time': query4_time,
                'results': len(strategy_perf)
            }
            
            print(f"   ✅ Consulta todos los trades: {query1_time*1000:.1f}ms ({metrics['query_all_trades']['results']} registros)")
            if 'query_by_symbol' in metrics:
                print(f"   ✅ Consulta por símbolo: {query2_time*1000:.1f}ms ({metrics['query_by_symbol']['results']} registros)")
            print(f"   ✅ Estadísticas diarias: {query3_time*1000:.1f}ms")
            print(f"   ✅ Performance por estrategia: {query4_time*1000:.1f}ms ({metrics['query_strategy_performance']['results']} estrategias)")
            
            return metrics
            
        except Exception as e:
            print(f"   ❌ ERROR en test de consultas: {e}")
            return {}
    
    def _cleanup_test_trades(self):
        """Limpiar trades de prueba"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'PERF_TEST_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de prueba: {e}")

class ConcurrencyTest:
    """Tests de concurrencia y threading"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
    
    def test_concurrent_inserts(self, num_threads: int = 5, trades_per_thread: int = 20) -> dict:
        """Test de inserción concurrente desde múltiples threads"""
        print(f"🔀 Test de concurrencia: {num_threads} threads, {trades_per_thread} trades cada uno...")
        
        results = {
            'successful_threads': 0,
            'total_trades_inserted': 0,
            'errors': [],
            'thread_times': []
        }
        
        def insert_trades_worker(thread_id: int):
            """Worker function para insertar trades"""
            try:
                start_time = time.time()
                successful_inserts = 0
                
                for i in range(trades_per_thread):
                    trade_data = {
                        'trade_id': f"CONC_T{thread_id:02d}_{i:03d}_{int(time.time()*1000)}",
                        'symbol': f'CONC{random.randint(100, 999)}',
                        'strategy': random.choice(['macdv_smallcaps', 'gap_go', 'orb']),
                        'side': random.choice(['BUY', 'SELL']),
                        'quantity': random.randint(50, 200),
                        'entry_price': round(random.uniform(5.0, 50.0), 4),
                        'entry_time': datetime.now(),
                        'status': 'OPEN',
                        'notes': f'Concurrency test - Thread {thread_id}, Trade {i}'
                    }
                    
                    if self.db_manager.save_trade(trade_data):
                        successful_inserts += 1
                    
                    # Pequeña pausa para simular procesamiento real
                    time.sleep(0.01)
                
                thread_time = time.time() - start_time
                
                return {
                    'thread_id': thread_id,
                    'successful_inserts': successful_inserts,
                    'time': thread_time
                }
                
            except Exception as e:
                return {
                    'thread_id': thread_id,
                    'error': str(e),
                    'successful_inserts': 0,
                    'time': 0
                }
        
        # Ejecutar threads concurrentemente
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_thread = {
                executor.submit(insert_trades_worker, i): i 
                for i in range(num_threads)
            }
            
            for future in future_to_thread:
                try:
                    result = future.result(timeout=30)  # 30 second timeout
                    
                    if 'error' in result:
                        results['errors'].append(f"Thread {result['thread_id']}: {result['error']}")
                    else:
                        results['successful_threads'] += 1
                        results['total_trades_inserted'] += result['successful_inserts']
                        results['thread_times'].append(result['time'])
                        
                        print(f"   ✅ Thread {result['thread_id']}: {result['successful_inserts']} trades en {result['time']:.2f}s")
                
                except Exception as e:
                    thread_id = future_to_thread[future]
                    results['errors'].append(f"Thread {thread_id}: {str(e)}")
        
        total_time = time.time() - start_time
        results['total_time'] = total_time
        
        print(f"   📊 Resumen: {results['total_trades_inserted']} trades insertados en {total_time:.2f}s")
        print(f"   🎯 Threads exitosos: {results['successful_threads']}/{num_threads}")
        if results['errors']:
            print(f"   ⚠️  Errores: {len(results['errors'])}")
        
        # Limpiar datos de prueba
        self._cleanup_concurrent_test_trades()
        
        return results
    
    def _cleanup_concurrent_test_trades(self):
        """Limpiar trades de concurrencia"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'CONC_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de concurrencia: {e}")

class DataIntegrityTest:
    """Tests de integridad de datos"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
    
    def test_data_constraints(self) -> dict:
        """Test de restricciones y validaciones de datos"""
        print("🔒 Test de integridad de datos...")
        
        results = {
            'constraint_tests': [],
            'validation_errors': [],
            'data_consistency_issues': []
        }
        
        try:
            # Test 1: Trade ID único
            duplicate_trade_id = f"INTEGRITY_TEST_{int(time.time())}"
            
            trade1 = {
                'trade_id': duplicate_trade_id,
                'symbol': 'TEST1',
                'strategy': 'test_strategy',
                'side': 'BUY',
                'quantity': 100,
                'entry_price': 10.0,
                'entry_time': datetime.now(),
                'status': 'OPEN'
            }
            
            trade2 = trade1.copy()
            trade2['symbol'] = 'TEST2'
            
            # Primer insert debe funcionar
            success1 = self.db_manager.save_trade(trade1)
            # Segundo insert debe actualizar (no duplicar)
            success2 = self.db_manager.save_trade(trade2)
            
            # Verificar que no hay duplicados
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE trade_id = ?", (duplicate_trade_id,))
                count = cursor.fetchone()[0]
            
            if count == 1:
                results['constraint_tests'].append("✅ Trade ID único: PASS")
            else:
                results['constraint_tests'].append(f"❌ Trade ID único: FAIL (encontrados {count} trades)")
            
            # Test 2: Validación de precios negativos
            negative_price_trade = {
                'trade_id': f"NEG_PRICE_{int(time.time())}",
                'symbol': 'NEGTEST',
                'strategy': 'test_strategy',
                'side': 'BUY',
                'quantity': 100,
                'entry_price': -5.0,  # Precio negativo
                'entry_time': datetime.now(),
                'status': 'OPEN'
            }
            
            success_negative = self.db_manager.save_trade(negative_price_trade)
            if success_negative:
                results['validation_errors'].append("⚠️  Precio negativo aceptado (debería rechazarse)")
            else:
                results['constraint_tests'].append("✅ Validación precio negativo: PASS")
            
            # Test 3: Consistencia de datos PnL
            self._test_pnl_consistency(results)
            
            # Test 4: Consistencia de fechas
            self._test_date_consistency(results)
            
            # Limpiar datos de prueba
            self._cleanup_integrity_test_trades()
            
        except Exception as e:
            results['validation_errors'].append(f"Error en test de integridad: {e}")
        
        # Mostrar resultados
        for test in results['constraint_tests']:
            print(f"   {test}")
        
        for error in results['validation_errors']:
            print(f"   {error}")
        
        for issue in results['data_consistency_issues']:
            print(f"   {issue}")
        
        return results
    
    def _test_pnl_consistency(self, results: dict):
        """Test de consistencia de cálculos PnL"""
        try:
            # Obtener trades cerrados con PnL
            trades_df = self.db_manager.get_trades(limit=100)
            closed_trades = trades_df[
                (trades_df['status'] == 'CLOSED') & 
                (trades_df['pnl'].notna()) & 
                (trades_df['exit_price'].notna())
            ]
            
            pnl_errors = 0
            for _, trade in closed_trades.iterrows():
                expected_pnl = 0
                if trade['side'] == 'BUY':
                    expected_pnl = (trade['exit_price'] - trade['entry_price']) * trade['quantity']
                else:  # SELL
                    expected_pnl = (trade['entry_price'] - trade['exit_price']) * trade['quantity']
                
                # Tolerancia de 0.01 por errores de redondeo
                if abs(trade['pnl'] - expected_pnl) > 0.01:
                    pnl_errors += 1
            
            if pnl_errors == 0:
                results['constraint_tests'].append("✅ Consistencia PnL: PASS")
            else:
                results['data_consistency_issues'].append(f"⚠️  {pnl_errors} trades con PnL inconsistente")
            
        except Exception as e:
            results['validation_errors'].append(f"Error verificando PnL: {e}")
    
    def _test_date_consistency(self, results: dict):
        """Test de consistencia de fechas"""
        try:
            trades_df = self.db_manager.get_trades(limit=100)
            closed_trades = trades_df[
                (trades_df['status'] == 'CLOSED') & 
                (trades_df['exit_time'].notna())
            ]
            
            date_errors = 0
            for _, trade in closed_trades.iterrows():
                entry_time = pd.to_datetime(trade['entry_time'])
                exit_time = pd.to_datetime(trade['exit_time'])
                
                if exit_time <= entry_time:
                    date_errors += 1
            
            if date_errors == 0:
                results['constraint_tests'].append("✅ Consistencia fechas: PASS")
            else:
                results['data_consistency_issues'].append(f"⚠️  {date_errors} trades con fechas inconsistentes")
            
        except Exception as e:
            results['validation_errors'].append(f"Error verificando fechas: {e}")
    
    def _cleanup_integrity_test_trades(self):
        """Limpiar trades de integridad"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'INTEGRITY_TEST_%' OR trade_id LIKE 'NEG_PRICE_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de integridad: {e}")

class AdvancedQueryTest:
    """Tests de consultas y filtros avanzados"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
    
    def test_complex_filters(self) -> dict:
        """Test de filtros complejos y consultas avanzadas"""
        print("🔍 Test de consultas y filtros avanzados...")
        
        results = {
            'filter_tests': [],
            'performance_metrics': {},
            'data_accuracy': []
        }
        
        try:
            # Crear datos de prueba variados
            self._create_test_data_for_filters()
            
            # Test 1: Filtro por rango de fechas
            start_time = time.time()
            date_filtered = self.db_manager.get_trades(
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                limit=1000
            )
            filter_time1 = time.time() - start_time
            
            results['filter_tests'].append(f"✅ Filtro por fechas: {len(date_filtered)} trades en {filter_time1*1000:.1f}ms")
            
            # Test 2: Filtro múltiple (símbolo + estrategia)
            if not date_filtered.empty:
                test_symbol = date_filtered.iloc[0]['symbol']
                test_strategy = date_filtered.iloc[0]['strategy']
                
                start_time = time.time()
                multi_filtered = self.db_manager.get_trades(
                    symbol=test_symbol,
                    strategy=test_strategy,
                    limit=100
                )
                filter_time2 = time.time() - start_time
                
                results['filter_tests'].append(f"✅ Filtro múltiple: {len(multi_filtered)} trades en {filter_time2*1000:.1f}ms")
            
            # Test 3: Performance por estrategia con diferentes períodos
            for days in [7, 30, 90]:
                start_time = time.time()
                strategy_perf = self.db_manager.get_strategy_performance(days=days)
                perf_time = time.time() - start_time
                
                results['performance_metrics'][f'{days}_days'] = {
                    'time': perf_time,
                    'strategies': len(strategy_perf)
                }
                
                results['filter_tests'].append(f"✅ Performance {days}d: {len(strategy_perf)} estrategias en {perf_time*1000:.1f}ms")
            
            # Test 4: Consultas SQL directas complejas
            self._test_complex_sql_queries(results)
            
            # Limpiar datos de prueba
            self._cleanup_filter_test_trades()
            
        except Exception as e:
            results['filter_tests'].append(f"❌ Error en filtros: {e}")
        
        # Mostrar resultados
        for test in results['filter_tests']:
            print(f"   {test}")
        
        for accuracy in results['data_accuracy']:
            print(f"   {accuracy}")
        
        return results
    
    def _create_test_data_for_filters(self):
        """Crear datos de prueba para filtros"""
        strategies = ['macdv_smallcaps', 'gap_go', 'orb', 'volume_breakout']
        symbols = ['FILTER_A', 'FILTER_B', 'FILTER_C']
        
        for i in range(50):  # 50 trades de prueba
            days_ago = random.randint(0, 100)
            entry_time = datetime.now() - timedelta(days=days_ago)
            
            trade_data = {
                'trade_id': f"FILTER_TEST_{i:03d}_{int(time.time())}",
                'symbol': random.choice(symbols),
                'strategy': random.choice(strategies),
                'side': random.choice(['BUY', 'SELL']),
                'quantity': random.randint(50, 300),
                'entry_price': round(random.uniform(5.0, 100.0), 4),
                'entry_time': entry_time,
                'status': random.choice(['OPEN', 'CLOSED']),
                'notes': f'Filter test trade {i}'
            }
            
            # Para trades cerrados, agregar exit data
            if trade_data['status'] == 'CLOSED':
                exit_days_later = random.randint(0, 5)
                trade_data['exit_time'] = entry_time + timedelta(days=exit_days_later)
                
                price_change = random.uniform(-0.2, 0.3)  # -20% a +30%
                trade_data['exit_price'] = round(trade_data['entry_price'] * (1 + price_change), 4)
                
                if trade_data['side'] == 'BUY':
                    trade_data['pnl'] = (trade_data['exit_price'] - trade_data['entry_price']) * trade_data['quantity']
                else:
                    trade_data['pnl'] = (trade_data['entry_price'] - trade_data['exit_price']) * trade_data['quantity']
            
            self.db_manager.save_trade(trade_data)
    
    def _test_complex_sql_queries(self, results: dict):
        """Test de consultas SQL complejas"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Query 1: Top símbolos por volumen de trading
                query1 = """
                    SELECT symbol, 
                           COUNT(*) as total_trades,
                           SUM(quantity * entry_price) as total_volume,
                           AVG(pnl) as avg_pnl
                    FROM trades 
                    WHERE status = 'CLOSED' AND pnl IS NOT NULL
                    GROUP BY symbol
                    HAVING total_trades >= 1
                    ORDER BY total_volume DESC
                    LIMIT 10
                """
                
                start_time = time.time()
                cursor = conn.execute(query1)
                top_symbols = cursor.fetchall()
                query1_time = time.time() - start_time
                
                results['data_accuracy'].append(f"✅ Top símbolos por volumen: {len(top_symbols)} resultados en {query1_time*1000:.1f}ms")
                
                # Query 2: Análisis de win rate por día de la semana
                query2 = """
                    SELECT strftime('%w', entry_time) as day_of_week,
                           COUNT(*) as total_trades,
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                           ROUND(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate
                    FROM trades
                    WHERE status = 'CLOSED' AND pnl IS NOT NULL
                    GROUP BY strftime('%w', entry_time)
                    ORDER BY day_of_week
                """
                
                start_time = time.time()
                cursor = conn.execute(query2)
                day_analysis = cursor.fetchall()
                query2_time = time.time() - start_time
                
                results['data_accuracy'].append(f"✅ Análisis por día semana: {len(day_analysis)} días en {query2_time*1000:.1f}ms")
                
        except Exception as e:
            results['data_accuracy'].append(f"❌ Error en consultas SQL complejas: {e}")
    
    def _cleanup_filter_test_trades(self):
        """Limpiar trades de filtros"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'FILTER_TEST_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de filtros: {e}")

def main():
    """Ejecutar todos los tests avanzados"""
    print("🧪 SUITE DE TESTS AVANZADOS PARA SISTEMA DE TRADES")
    print("=" * 60)
    
    test_suite = TradeTestSuite()
    
    # Test 1: Rendimiento de base de datos
    print("\n1️⃣  TESTS DE RENDIMIENTO")
    print("-" * 40)
    perf_test = DatabasePerformanceTest()
    
    # Test inserción masiva
    insert_metrics = perf_test.test_bulk_insert_performance(100)  # 100 trades para no saturar
    test_suite.log_result("bulk_insert", bool(insert_metrics), insert_metrics)
    
    # Test consultas
    query_metrics = perf_test.test_query_performance()
    test_suite.log_result("query_performance", bool(query_metrics), query_metrics)
    
    # Test 2: Concurrencia
    print("\n2️⃣  TESTS DE CONCURRENCIA")
    print("-" * 40)
    concurrency_test = ConcurrencyTest()
    
    conc_results = concurrency_test.test_concurrent_inserts(3, 10)  # 3 threads, 10 trades cada uno
    test_suite.log_result("concurrency", conc_results['successful_threads'] > 0, conc_results)
    
    # Test 3: Integridad de datos
    print("\n3️⃣  TESTS DE INTEGRIDAD")
    print("-" * 40)
    integrity_test = DataIntegrityTest()
    
    integrity_results = integrity_test.test_data_constraints()
    passed_constraints = len([t for t in integrity_results['constraint_tests'] if '✅' in t])
    test_suite.log_result("data_integrity", passed_constraints > 0, integrity_results)
    
    # Test 4: Filtros avanzados
    print("\n4️⃣  TESTS DE CONSULTAS AVANZADAS")
    print("-" * 40)
    query_test = AdvancedQueryTest()
    
    filter_results = query_test.test_complex_filters()
    passed_filters = len([t for t in filter_results['filter_tests'] if '✅' in t])
    test_suite.log_result("advanced_queries", passed_filters > 0, filter_results)
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL DE TESTS AVANZADOS")
    print("=" * 60)
    
    total_tests = len(test_suite.test_results)
    passed_tests = sum(1 for result in test_suite.test_results.values() if result['passed'])
    
    print(f"🎯 RESULTADO GENERAL: {passed_tests}/{total_tests} categorías pasaron")
    print()
    
    # Detalles por categoría
    category_names = {
        'bulk_insert': 'Inserción Masiva',
        'query_performance': 'Rendimiento de Consultas',
        'concurrency': 'Concurrencia',
        'data_integrity': 'Integridad de Datos',
        'advanced_queries': 'Consultas Avanzadas'
    }
    
    for test_name, result in test_suite.test_results.items():
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        category = category_names.get(test_name, test_name)
        print(f"{category}: {status}")
        
        # Mostrar métricas clave si están disponibles
        if result['metrics']:
            if test_name == 'bulk_insert' and 'trades_per_second' in result['metrics']:
                print(f"   📈 Velocidad: {result['metrics']['trades_per_second']:.1f} trades/segundo")
            elif test_name == 'concurrency' and 'total_trades_inserted' in result['metrics']:
                print(f"   🔀 Trades concurrentes: {result['metrics']['total_trades_inserted']}")
    
    print()
    
    # Recomendaciones finales
    print("💡 RECOMENDACIONES:")
    
    if passed_tests == total_tests:
        print("🎉 ¡Excelente! El sistema pasa todos los tests avanzados.")
        print("✅ El sistema está listo para producción con alto volumen de trades.")
    elif passed_tests >= total_tests * 0.8:
        print("👍 El sistema funciona bien en general.")
        print("⚠️  Revisar las categorías que fallaron para optimización.")
    else:
        print("🔧 El sistema necesita mejoras antes de manejar alto volumen.")
        print("❗ Priorizar las correcciones de rendimiento y concurrencia.")
    
    # Métricas de rendimiento específicas
    if 'bulk_insert' in test_suite.test_results:
        metrics = test_suite.test_results['bulk_insert']['metrics']
        if metrics and 'trades_per_second' in metrics:
            tps = metrics['trades_per_second']
            if tps > 50:
                print(f"🚀 Excelente rendimiento: {tps:.1f} trades/segundo")
            elif tps > 20:
                print(f"👍 Buen rendimiento: {tps:.1f} trades/segundo")
            else:
                print(f"⚠️  Rendimiento bajo: {tps:.1f} trades/segundo - considerar optimización")

if __name__ == "__main__":
    main()