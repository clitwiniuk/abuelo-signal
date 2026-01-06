#!/usr/bin/env python3
"""
Test de Migración de Datos del Sistema de Trades
Tests específicos para migración, backup/restore y consistencia de datos
"""

import os
import sys
import sqlite3
import pandas as pd
import time
import json
import shutil
from datetime import datetime, timedelta, date
from pathlib import Path

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class DataMigrationTest:
    """Tests de migración y mantenimiento de datos"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.backup_dir = Path("test_backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def test_strategy_migration(self) -> dict:
        """Test de migración de estrategias unknown a reales"""
        print("🔄 Test de migración de estrategias...")
        
        results = {
            'migration_successful': False,
            'trades_migrated': 0,
            'strategies_before': [],
            'strategies_after': [],
            'errors': []
        }
        
        try:
            # Crear datos de prueba con estrategias 'unknown'
            test_trades = self._create_migration_test_data()
            
            # Obtener estrategias antes de la migración
            trades_df = self.db_manager.get_trades(limit=1000)
            migration_trades = trades_df[trades_df['trade_id'].str.contains('MIGRATION_TEST_')]
            results['strategies_before'] = migration_trades['strategy'].unique().tolist()
            
            print(f"   📋 Creados {len(migration_trades)} trades de prueba")
            print(f"   🔍 Estrategias antes: {results['strategies_before']}")
            
            # Ejecutar migración
            migrated_count = self.db_manager.migrate_strategy_names(placeholder='unknown')
            results['trades_migrated'] = migrated_count
            
            # Verificar resultados después de migración
            trades_df_after = self.db_manager.get_trades(limit=1000)
            migration_trades_after = trades_df_after[trades_df_after['trade_id'].str.contains('MIGRATION_TEST_')]
            results['strategies_after'] = migration_trades_after['strategy'].unique().tolist()
            
            print(f"   ✅ Migrados {migrated_count} trades")
            print(f"   🔍 Estrategias después: {results['strategies_after']}")
            
            # Verificar que no quedan estrategias 'unknown'
            unknown_after = len(migration_trades_after[migration_trades_after['strategy'] == 'unknown'])
            if unknown_after == 0:
                results['migration_successful'] = True
                print("   ✅ No quedan estrategias 'unknown'")
            else:
                results['errors'].append(f"Quedan {unknown_after} trades con estrategia 'unknown'")
            
            # Limpiar datos de prueba
            self._cleanup_migration_test_data()
            
        except Exception as e:
            results['errors'].append(f"Error en migración: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def test_backup_restore(self) -> dict:
        """Test de backup y restore de la base de datos"""
        print("💾 Test de backup y restore...")
        
        results = {
            'backup_created': False,
            'backup_size': 0,
            'restore_successful': False,
            'data_integrity_verified': False,
            'errors': []
        }
        
        try:
            # Obtener estado inicial
            initial_trades = self.db_manager.get_trades(limit=1000)
            initial_count = len(initial_trades)
            
            # Crear backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.backup_dir / f"test_backup_{timestamp}.db"
            
            shutil.copy2(self.db_manager.db_path, backup_path)
            
            if backup_path.exists():
                results['backup_created'] = True
                results['backup_size'] = backup_path.stat().st_size
                print(f"   ✅ Backup creado: {backup_path.name} ({results['backup_size']} bytes)")
            
            # Crear algunos cambios en la DB original
            test_trade = {
                'trade_id': f"BACKUP_TEST_{timestamp}",
                'symbol': 'BACKUP_SYMBOL',
                'strategy': 'backup_test_strategy',
                'side': 'BUY',
                'quantity': 100,
                'entry_price': 25.0,
                'entry_time': datetime.now(),
                'status': 'OPEN',
                'notes': 'Trade para test de backup/restore'
            }
            
            self.db_manager.save_trade(test_trade)
            modified_trades = self.db_manager.get_trades(limit=1000)
            modified_count = len(modified_trades)
            
            print(f"   📝 Trade agregado (total: {initial_count} -> {modified_count})")
            
            # Simular restore (copiar backup de vuelta)
            original_path = Path(self.db_manager.db_path)
            temp_original = original_path.with_suffix('.temp')
            
            # Mover original temporalmente
            shutil.move(original_path, temp_original)
            
            # Restaurar desde backup
            shutil.copy2(backup_path, original_path)
            
            # Verificar que el restore funcionó
            # Necesitamos crear nueva instancia del DB manager para refrescar conexión
            from core.database_manager import DatabaseManager
            restored_db = DatabaseManager(str(original_path))
            
            restored_trades = restored_db.get_trades(limit=1000)
            restored_count = len(restored_trades)
            
            if restored_count == initial_count:
                results['restore_successful'] = True
                print(f"   ✅ Restore exitoso (recuperados {restored_count} trades)")
            else:
                results['errors'].append(f"Restore incompleto: esperado {initial_count}, obtenido {restored_count}")
            
            # Verificar integridad de datos
            if results['restore_successful']:
                # Comparar algunos campos clave
                integrity_ok = True
                
                # Verificar que las columnas principales existen
                try:
                    sample_trade = restored_trades.iloc[0] if not restored_trades.empty else None
                    if sample_trade is not None:
                        required_columns = ['trade_id', 'symbol', 'strategy', 'side', 'entry_price']
                        for col in required_columns:
                            if col not in sample_trade or pd.isna(sample_trade[col]):
                                integrity_ok = False
                                break
                    
                    if integrity_ok:
                        results['data_integrity_verified'] = True
                        print("   ✅ Integridad de datos verificada")
                    else:
                        results['errors'].append("Faltan campos requeridos después del restore")
                
                except Exception as e:
                    results['errors'].append(f"Error verificando integridad: {e}")
            
            # Restaurar estado original
            shutil.move(temp_original, original_path)
            
            # Limpiar archivos de prueba
            backup_path.unlink(missing_ok=True)
            
        except Exception as e:
            results['errors'].append(f"Error en backup/restore: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def test_data_cleanup(self) -> dict:
        """Test de limpieza de datos antiguos"""
        print("🧹 Test de limpieza de datos...")
        
        results = {
            'cleanup_successful': False,
            'old_trades_identified': 0,
            'trades_cleaned': 0,
            'space_recovered': 0,
            'errors': []
        }
        
        try:
            # Crear datos antiguos de prueba
            old_trades_created = self._create_old_test_data()
            
            # Identificar trades antiguos (más de 90 días)
            cutoff_date = date.today() - timedelta(days=90)
            
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM trades 
                    WHERE date(entry_time) < ? AND trade_id LIKE 'OLD_TEST_%'
                """, (cutoff_date.isoformat(),))
                
                old_count = cursor.fetchone()[0]
                results['old_trades_identified'] = old_count
                
                print(f"   📊 Identificados {old_count} trades antiguos para limpieza")
                
                # Obtener tamaño de DB antes
                db_size_before = Path(self.db_manager.db_path).stat().st_size
                
                # Ejecutar limpieza (solo de datos de prueba)
                cursor.execute("""
                    DELETE FROM trades 
                    WHERE date(entry_time) < ? AND trade_id LIKE 'OLD_TEST_%'
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                # VACUUM para recuperar espacio
                conn.execute("VACUUM")
                
                results['trades_cleaned'] = deleted_count
                
                # Obtener tamaño después
                db_size_after = Path(self.db_manager.db_path).stat().st_size
                results['space_recovered'] = db_size_before - db_size_after
                
                print(f"   ✅ Eliminados {deleted_count} trades antiguos")
                print(f"   💽 Espacio recuperado: {results['space_recovered']} bytes")
                
                if deleted_count == old_count:
                    results['cleanup_successful'] = True
                else:
                    results['errors'].append(f"Limpieza incompleta: esperado {old_count}, eliminado {deleted_count}")
            
        except Exception as e:
            results['errors'].append(f"Error en limpieza: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def test_database_maintenance(self) -> dict:
        """Test de mantenimiento de base de datos (VACUUM, REINDEX, etc.)"""
        print("🔧 Test de mantenimiento de base de datos...")
        
        results = {
            'vacuum_successful': False,
            'reindex_successful': False,
            'analyze_successful': False,
            'size_before': 0,
            'size_after': 0,
            'maintenance_time': 0,
            'errors': []
        }
        
        try:
            # Obtener tamaño inicial
            db_path = Path(self.db_manager.db_path)
            results['size_before'] = db_path.stat().st_size
            
            start_time = time.time()
            
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # VACUUM - compactar base de datos
                print("   🗜️  Ejecutando VACUUM...")
                conn.execute("VACUUM")
                results['vacuum_successful'] = True
                
                # REINDEX - reconstruir índices
                print("   📇 Ejecutando REINDEX...")
                conn.execute("REINDEX")
                results['reindex_successful'] = True
                
                # ANALYZE - actualizar estadísticas del query planner
                print("   📊 Ejecutando ANALYZE...")
                conn.execute("ANALYZE")
                results['analyze_successful'] = True
                
            maintenance_time = time.time() - start_time
            results['maintenance_time'] = maintenance_time
            
            # Obtener tamaño final
            results['size_after'] = db_path.stat().st_size
            space_saved = results['size_before'] - results['size_after']
            
            print(f"   ✅ Mantenimiento completado en {maintenance_time:.2f}s")
            print(f"   💽 Tamaño: {results['size_before']} -> {results['size_after']} bytes")
            if space_saved > 0:
                print(f"   🎯 Espacio liberado: {space_saved} bytes")
            
        except Exception as e:
            results['errors'].append(f"Error en mantenimiento: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def test_schema_validation(self) -> dict:
        """Test de validación del schema de la base de datos"""
        print("📋 Test de validación del schema...")
        
        results = {
            'schema_valid': False,
            'tables_found': [],
            'missing_tables': [],
            'missing_columns': [],
            'extra_tables': [],
            'errors': []
        }
        
        expected_schema = {
            'trades': [
                'id', 'trade_id', 'symbol', 'strategy', 'side', 'quantity',
                'entry_price', 'exit_price', 'entry_time', 'exit_time',
                'duration_minutes', 'pnl', 'commission', 'status', 'notes',
                'created_at', 'updated_at'
            ],
            'daily_stats': [
                'id', 'date', 'total_trades', 'winning_trades', 'losing_trades',
                'total_pnl', 'gross_profit', 'gross_loss', 'max_win', 'max_loss',
                'win_rate', 'avg_win', 'avg_loss', 'profit_factor', 'created_at'
            ],
            'trading_journal': [
                'id', 'date', 'market_notes', 'strategy_notes', 'lessons_learned',
                'mood_rating', 'created_at', 'updated_at'
            ],
            'manual_symbols': [
                'id', 'symbol', 'added_at', 'is_active', 'notes'
            ],
            'position_risk_config': [
                'id', 'symbol', 'entry_price', 'quantity', 'stop_loss_price',
                'take_profit_price', 'trailing_stop_activation_price',
                'trailing_stop_distance_pct', 'max_hold_time_minutes',
                'strategy_used', 'created_at', 'updated_at', 'is_active'
            ]
        }
        
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Obtener todas las tablas
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                actual_tables = {row[0] for row in cursor.fetchall()}
                
                expected_tables = set(expected_schema.keys())
                results['tables_found'] = list(actual_tables)
                
                # Verificar tablas faltantes
                results['missing_tables'] = list(expected_tables - actual_tables)
                results['extra_tables'] = list(actual_tables - expected_tables)
                
                print(f"   📋 Tablas encontradas: {len(actual_tables)}")
                if results['missing_tables']:
                    print(f"   ⚠️  Tablas faltantes: {results['missing_tables']}")
                if results['extra_tables']:
                    print(f"   ℹ️  Tablas adicionales: {results['extra_tables']}")
                
                # Verificar columnas para cada tabla esperada
                all_columns_ok = True
                for table_name, expected_columns in expected_schema.items():
                    if table_name in actual_tables:
                        cursor = conn.execute(f"PRAGMA table_info({table_name})")
                        actual_columns = {row[1] for row in cursor.fetchall()}
                        
                        missing_columns = set(expected_columns) - actual_columns
                        if missing_columns:
                            results['missing_columns'].extend([
                                f"{table_name}.{col}" for col in missing_columns
                            ])
                            all_columns_ok = False
                            print(f"   ⚠️  {table_name}: faltan columnas {list(missing_columns)}")
                        else:
                            print(f"   ✅ {table_name}: todas las columnas presentes")
                
                # Schema válido si no faltan tablas ni columnas críticas
                if not results['missing_tables'] and all_columns_ok:
                    results['schema_valid'] = True
                    print("   ✅ Schema de base de datos válido")
                else:
                    results['errors'].append("Schema incompleto o inválido")
            
        except Exception as e:
            results['errors'].append(f"Error validando schema: {e}")
            print(f"   ❌ ERROR: {e}")
        
        return results
    
    def _create_migration_test_data(self) -> list:
        """Crear datos de prueba para migración de estrategias"""
        test_trades = []
        symbols = ['MIG_A', 'MIG_B', 'MIG_C']
        
        # Crear trades con 'unknown' strategy que necesitan migración
        for i in range(10):
            trade_data = {
                'trade_id': f"MIGRATION_TEST_{i:03d}_{int(time.time())}",
                'symbol': symbols[i % len(symbols)],
                'strategy': 'unknown',
                'side': 'BUY',
                'quantity': 100,
                'entry_price': 15.0,
                'entry_time': datetime.now() - timedelta(days=i),
                'status': 'CLOSED',
                'exit_price': 16.0,
                'exit_time': datetime.now() - timedelta(days=i, hours=-2),
                'pnl': 100.0,
                'notes': f'Migration test trade {i}'
            }
            
            self.db_manager.save_trade(trade_data)
            test_trades.append(trade_data)
        
        # Crear algunos trades con estrategias reales (para que la migración tenga referencia)
        for i, symbol in enumerate(symbols):
            real_strategy_trade = {
                'trade_id': f"MIGRATION_REF_{i}_{int(time.time())}",
                'symbol': symbol,
                'strategy': ['macdv_smallcaps', 'gap_go', 'orb'][i],
                'side': 'BUY',
                'quantity': 150,
                'entry_price': 20.0,
                'entry_time': datetime.now() - timedelta(days=i+20),
                'status': 'CLOSED',
                'exit_price': 21.0,
                'exit_time': datetime.now() - timedelta(days=i+20, hours=-3),
                'pnl': 150.0,
                'notes': f'Reference trade for migration {i}'
            }
            
            self.db_manager.save_trade(real_strategy_trade)
            test_trades.append(real_strategy_trade)
        
        return test_trades
    
    def _create_old_test_data(self) -> int:
        """Crear datos antiguos para test de limpieza"""
        old_trades_count = 0
        
        # Crear trades de hace 120 días (deberían ser limpiados)
        for i in range(15):
            trade_data = {
                'trade_id': f"OLD_TEST_{i:03d}_{int(time.time())}",
                'symbol': f'OLD{i:02d}',
                'strategy': 'old_test_strategy',
                'side': 'BUY',
                'quantity': 50,
                'entry_price': 5.0,
                'entry_time': datetime.now() - timedelta(days=120),
                'status': 'CLOSED',
                'exit_price': 5.25,
                'exit_time': datetime.now() - timedelta(days=120, hours=-1),
                'pnl': 12.5,
                'notes': f'Old test trade {i}'
            }
            
            if self.db_manager.save_trade(trade_data):
                old_trades_count += 1
        
        return old_trades_count
    
    def _cleanup_migration_test_data(self):
        """Limpiar datos de prueba de migración"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'MIGRATION_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de migración: {e}")
    
    def cleanup_test_directories(self):
        """Limpiar directorios de prueba"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
        except Exception as e:
            print(f"   ⚠️  Error limpiando directorios de prueba: {e}")

def main():
    """Ejecutar todos los tests de migración"""
    print("🔄 TESTS DE MIGRACIÓN Y MANTENIMIENTO DE DATOS")
    print("=" * 55)
    
    migration_test = DataMigrationTest()
    all_results = {}
    
    # Test 1: Migración de estrategias
    print("\n1️⃣  TEST DE MIGRACIÓN DE ESTRATEGIAS")
    print("-" * 40)
    strategy_results = migration_test.test_strategy_migration()
    all_results['strategy_migration'] = strategy_results
    
    # Test 2: Backup y Restore
    print("\n2️⃣  TEST DE BACKUP Y RESTORE")
    print("-" * 40)
    backup_results = migration_test.test_backup_restore()
    all_results['backup_restore'] = backup_results
    
    # Test 3: Limpieza de datos
    print("\n3️⃣  TEST DE LIMPIEZA DE DATOS")
    print("-" * 40)
    cleanup_results = migration_test.test_data_cleanup()
    all_results['data_cleanup'] = cleanup_results
    
    # Test 4: Mantenimiento de DB
    print("\n4️⃣  TEST DE MANTENIMIENTO DE DB")
    print("-" * 40)
    maintenance_results = migration_test.test_database_maintenance()
    all_results['db_maintenance'] = maintenance_results
    
    # Test 5: Validación de Schema
    print("\n5️⃣  TEST DE VALIDACIÓN DE SCHEMA")
    print("-" * 40)
    schema_results = migration_test.test_schema_validation()
    all_results['schema_validation'] = schema_results
    
    # Limpiar archivos de prueba
    migration_test.cleanup_test_directories()
    
    # Resumen final
    print("\n" + "=" * 55)
    print("📊 RESUMEN DE TESTS DE MIGRACIÓN")
    print("=" * 55)
    
    test_categories = {
        'strategy_migration': 'Migración de Estrategias',
        'backup_restore': 'Backup y Restore',
        'data_cleanup': 'Limpieza de Datos',
        'db_maintenance': 'Mantenimiento de DB',
        'schema_validation': 'Validación de Schema'
    }
    
    passed_categories = 0
    total_categories = len(all_results)
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            
            # Determinar si pasó basado en criterios específicos
            passed = False
            if test_key == 'strategy_migration':
                passed = result.get('migration_successful', False)
            elif test_key == 'backup_restore':
                passed = result.get('backup_created', False) and result.get('restore_successful', False)
            elif test_key == 'data_cleanup':
                passed = result.get('cleanup_successful', False)
            elif test_key == 'db_maintenance':
                passed = all([
                    result.get('vacuum_successful', False),
                    result.get('reindex_successful', False),
                    result.get('analyze_successful', False)
                ])
            elif test_key == 'schema_validation':
                passed = result.get('schema_valid', False)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status}")
            
            if passed:
                passed_categories += 1
            
            # Mostrar métricas específicas
            if test_key == 'strategy_migration' and result.get('trades_migrated', 0) > 0:
                print(f"   📊 Trades migrados: {result['trades_migrated']}")
            elif test_key == 'backup_restore' and result.get('backup_size', 0) > 0:
                print(f"   💾 Tamaño backup: {result['backup_size']} bytes")
            elif test_key == 'data_cleanup' and result.get('trades_cleaned', 0) > 0:
                print(f"   🧹 Trades limpiados: {result['trades_cleaned']}")
            elif test_key == 'db_maintenance' and result.get('maintenance_time', 0) > 0:
                print(f"   ⏱️  Tiempo mantenimiento: {result['maintenance_time']:.2f}s")
            
            # Mostrar errores si los hay
            errors = result.get('errors', [])
            if errors and not passed:
                print(f"   ⚠️  Errores: {len(errors)}")
    
    print(f"\n🎯 RESULTADO FINAL: {passed_categories}/{total_categories} categorías pasaron")
    
    # Recomendaciones
    print("\n💡 RECOMENDACIONES:")
    if passed_categories == total_categories:
        print("🎉 ¡Excelente! Todos los tests de migración pasaron.")
        print("✅ El sistema está preparado para operaciones de mantenimiento.")
    elif passed_categories >= total_categories * 0.8:
        print("👍 La mayoría de tests pasaron.")
        print("🔧 Revisar y corregir las categorías que fallaron.")
    else:
        print("⚠️  Varios tests de migración fallaron.")
        print("❗ Importante revisar el mantenimiento de datos antes de producción.")
    
    # Generar reporte JSON para análisis posterior
    report_file = f"migration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        # Convertir datetime objects a strings para serialización JSON
        json_results = {}
        for key, value in all_results.items():
            json_results[key] = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, datetime):
                    json_results[key][sub_key] = sub_value.isoformat()
                else:
                    json_results[key][sub_key] = sub_value
        
        with open(report_file, 'w') as f:
            json.dump({
                'test_timestamp': datetime.now().isoformat(),
                'summary': {
                    'passed_categories': passed_categories,
                    'total_categories': total_categories,
                    'success_rate': passed_categories / total_categories if total_categories > 0 else 0
                },
                'detailed_results': json_results
            }, f, indent=2)
        
        print(f"\n📄 Reporte detallado guardado en: {report_file}")
        
    except Exception as e:
        print(f"⚠️  No se pudo guardar reporte: {e}")

if __name__ == "__main__":
    main()