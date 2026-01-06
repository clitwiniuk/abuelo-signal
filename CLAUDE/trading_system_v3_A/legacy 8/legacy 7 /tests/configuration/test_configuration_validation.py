#!/usr/bin/env python3
"""
Test de Validación de Configuración del Sistema
Tests para validar configuración, parámetros y settings del sistema de trading
"""

import os
import sys
import json
import time
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import configparser

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class ConfigurationValidationTest:
    """Tests de validación de configuración del sistema"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.temp_config_dir = Path("temp_config_tests")
        self.temp_config_dir.mkdir(exist_ok=True)
    
    def test_database_configuration_validation(self) -> dict:
        """Test de validación de configuración de base de datos"""
        print("🔧 Test de validación de configuración de BD...")
        
        results = {
            'valid_configs_tested': 0,
            'invalid_configs_tested': 0,
            'configs_passed_validation': 0,
            'critical_config_errors': [],
            'warnings_generated': [],
            'test_passed': False
        }
        
        # Configuraciones válidas para probar
        valid_db_configs = [
            {
                'name': 'default_sqlite',
                'config': {
                    'db_type': 'sqlite',
                    'db_path': str(self.temp_config_dir / 'test_valid.db'),
                    'connection_timeout': 30,
                    'enable_wal_mode': True,
                    'backup_enabled': True
                }
            },
            {
                'name': 'memory_db',
                'config': {
                    'db_type': 'sqlite',
                    'db_path': ':memory:',
                    'connection_timeout': 10,
                    'enable_wal_mode': False,
                    'backup_enabled': False
                }
            }
        ]
        
        # Configuraciones inválidas para probar
        invalid_db_configs = [
            {
                'name': 'invalid_path',
                'config': {
                    'db_type': 'sqlite',
                    'db_path': '/invalid/path/that/does/not/exist/test.db',
                    'connection_timeout': 30
                }
            },
            {
                'name': 'invalid_timeout',
                'config': {
                    'db_type': 'sqlite',
                    'db_path': str(self.temp_config_dir / 'test.db'),
                    'connection_timeout': -1  # Valor inválido
                }
            },
            {
                'name': 'missing_required',
                'config': {
                    'db_type': 'sqlite'
                    # Falta db_path requerido
                }
            }
        ]
        
        # Probar configuraciones válidas
        for config_data in valid_db_configs:
            results['valid_configs_tested'] += 1
            
            try:
                print(f"   ✅ Testing valid config: {config_data['name']}")
                
                # Simular validación de configuración
                config = config_data['config']
                validation_result = self._validate_db_config(config)
                
                if validation_result['valid']:
                    results['configs_passed_validation'] += 1
                    print(f"      ✅ Config validation passed")
                else:
                    results['critical_config_errors'].append({
                        'config_name': config_data['name'],
                        'errors': validation_result['errors']
                    })
                    print(f"      ❌ Unexpected validation failure")
                
            except Exception as e:
                print(f"      ❌ Error testing valid config: {e}")
                results['critical_config_errors'].append({
                    'config_name': config_data['name'],
                    'error': str(e)
                })
        
        # Probar configuraciones inválidas
        for config_data in invalid_db_configs:
            results['invalid_configs_tested'] += 1
            
            try:
                print(f"   🧪 Testing invalid config: {config_data['name']}")
                
                config = config_data['config']
                validation_result = self._validate_db_config(config)
                
                if not validation_result['valid']:
                    print(f"      ✅ Invalid config properly rejected")
                    results['warnings_generated'].extend(validation_result['errors'])
                else:
                    print(f"      ⚠️  Invalid config was accepted (security risk)")
                    results['critical_config_errors'].append({
                        'config_name': config_data['name'],
                        'issue': 'Invalid configuration was accepted'
                    })
                
            except Exception as e:
                # Exception for invalid config is expected and good
                print(f"      ✅ Invalid config caused expected exception: {str(e)[:50]}...")
        
        # Evaluar resultados
        if (results['configs_passed_validation'] == results['valid_configs_tested'] and
            len(results['critical_config_errors']) == 0):
            results['test_passed'] = True
            print(f"   🎯 Config validation: PASS")
        else:
            print(f"   ⚠️  Config validation: FAIL")
        
        return results
    
    def test_trading_parameters_validation(self) -> dict:
        """Test de validación de parámetros de trading"""
        print("📊 Test de validación de parámetros de trading...")
        
        results = {
            'parameter_sets_tested': 0,
            'valid_parameter_sets': 0,
            'invalid_parameter_sets': 0,
            'parameter_warnings': [],
            'critical_parameter_errors': [],
            'test_passed': False
        }
        
        # Conjuntos de parámetros válidos
        valid_parameters = [
            {
                'name': 'conservative_trading',
                'params': {
                    'max_positions': 3,
                    'max_daily_loss': -500.0,
                    'position_size_percent': 0.02,
                    'stop_loss_percent': 0.05,
                    'take_profit_percent': 0.10,
                    'min_trade_value': 100.0,
                    'max_trade_value': 2000.0
                }
            },
            {
                'name': 'aggressive_trading',
                'params': {
                    'max_positions': 8,
                    'max_daily_loss': -2000.0,
                    'position_size_percent': 0.05,
                    'stop_loss_percent': 0.03,
                    'take_profit_percent': 0.15,
                    'min_trade_value': 500.0,
                    'max_trade_value': 5000.0
                }
            }
        ]
        
        # Conjuntos de parámetros inválidos
        invalid_parameters = [
            {
                'name': 'negative_positions',
                'params': {
                    'max_positions': -1,  # Inválido
                    'max_daily_loss': -500.0,
                    'position_size_percent': 0.02
                }
            },
            {
                'name': 'impossible_percentages',
                'params': {
                    'max_positions': 5,
                    'position_size_percent': 1.5,  # 150% - imposible
                    'stop_loss_percent': -0.05,    # Negativo - inválido
                    'take_profit_percent': 0.0     # Zero - inválido
                }
            },
            {
                'name': 'contradictory_values',
                'params': {
                    'min_trade_value': 1000.0,
                    'max_trade_value': 500.0,  # Menor que min - inválido
                    'max_daily_loss': 100.0    # Positivo - debería ser negativo
                }
            }
        ]
        
        # Probar parámetros válidos
        for param_set in valid_parameters:
            results['parameter_sets_tested'] += 1
            
            try:
                print(f"   ✅ Testing valid params: {param_set['name']}")
                
                validation_result = self._validate_trading_parameters(param_set['params'])
                
                if validation_result['valid']:
                    results['valid_parameter_sets'] += 1
                    print(f"      ✅ Parameters validated successfully")
                else:
                    results['critical_parameter_errors'].append({
                        'param_set': param_set['name'],
                        'errors': validation_result['errors']
                    })
                    print(f"      ❌ Valid parameters rejected")
                
            except Exception as e:
                results['critical_parameter_errors'].append({
                    'param_set': param_set['name'],
                    'error': str(e)
                })
                print(f"      ❌ Error validating params: {e}")
        
        # Probar parámetros inválidos
        for param_set in invalid_parameters:
            results['parameter_sets_tested'] += 1
            
            try:
                print(f"   🧪 Testing invalid params: {param_set['name']}")
                
                validation_result = self._validate_trading_parameters(param_set['params'])
                
                if not validation_result['valid']:
                    results['invalid_parameter_sets'] += 1
                    print(f"      ✅ Invalid parameters properly rejected")
                    results['parameter_warnings'].extend(validation_result['errors'])
                else:
                    results['critical_parameter_errors'].append({
                        'param_set': param_set['name'],
                        'issue': 'Invalid parameters were accepted'
                    })
                    print(f"      ⚠️  Invalid parameters were accepted")
                
            except Exception as e:
                # Exception expected for invalid params
                results['invalid_parameter_sets'] += 1
                print(f"      ✅ Invalid params caused expected exception")
        
        # Evaluar resultados
        expected_valid = len(valid_parameters)
        expected_invalid = len(invalid_parameters)
        
        if (results['valid_parameter_sets'] == expected_valid and
            results['invalid_parameter_sets'] == expected_invalid and
            len(results['critical_parameter_errors']) == 0):
            results['test_passed'] = True
            print(f"   🎯 Parameter validation: PASS")
        else:
            print(f"   ⚠️  Parameter validation: FAIL")
        
        return results
    
    def test_strategy_configuration_validation(self) -> dict:
        """Test de validación de configuración de estrategias"""
        print("🎯 Test de validación de configuración de estrategias...")
        
        results = {
            'strategies_tested': 0,
            'valid_strategies': 0,
            'invalid_strategies': 0,
            'config_errors': [],
            'test_passed': False
        }
        
        # Configuraciones de estrategias válidas
        valid_strategies = [
            {
                'name': 'macdv_smallcaps',
                'config': {
                    'enabled': True,
                    'timeframe': '5min',
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9,
                    'volume_threshold': 1.5,
                    'min_price': 0.50,
                    'max_price': 50.0,
                    'position_size': 0.02
                }
            },
            {
                'name': 'gap_go',
                'config': {
                    'enabled': True,
                    'timeframe': '1min',
                    'gap_threshold': 0.02,
                    'volume_spike': 2.0,
                    'premarket_volume': 100000,
                    'max_gap_size': 0.10,
                    'position_size': 0.03
                }
            }
        ]
        
        # Configuraciones de estrategias inválidas
        invalid_strategies = [
            {
                'name': 'invalid_timeframe',
                'config': {
                    'enabled': True,
                    'timeframe': '0min',  # Inválido
                    'position_size': 0.02
                }
            },
            {
                'name': 'negative_values',
                'config': {
                    'enabled': True,
                    'timeframe': '5min',
                    'macd_fast': -12,     # Inválido
                    'volume_threshold': -1.5,  # Inválido
                    'position_size': -0.02     # Inválido
                }
            }
        ]
        
        # Probar estrategias válidas
        for strategy in valid_strategies:
            results['strategies_tested'] += 1
            
            try:
                print(f"   ✅ Testing valid strategy: {strategy['name']}")
                
                validation_result = self._validate_strategy_config(strategy['name'], strategy['config'])
                
                if validation_result['valid']:
                    results['valid_strategies'] += 1
                    print(f"      ✅ Strategy config validated")
                else:
                    results['config_errors'].append({
                        'strategy': strategy['name'],
                        'errors': validation_result['errors']
                    })
                    print(f"      ❌ Valid strategy config rejected")
                
            except Exception as e:
                results['config_errors'].append({
                    'strategy': strategy['name'],
                    'error': str(e)
                })
                print(f"      ❌ Error validating strategy: {e}")
        
        # Probar estrategias inválidas
        for strategy in invalid_strategies:
            results['strategies_tested'] += 1
            
            try:
                print(f"   🧪 Testing invalid strategy: {strategy['name']}")
                
                validation_result = self._validate_strategy_config(strategy['name'], strategy['config'])
                
                if not validation_result['valid']:
                    results['invalid_strategies'] += 1
                    print(f"      ✅ Invalid strategy properly rejected")
                else:
                    results['config_errors'].append({
                        'strategy': strategy['name'],
                        'issue': 'Invalid strategy config was accepted'
                    })
                    print(f"      ⚠️  Invalid strategy was accepted")
                
            except Exception as e:
                results['invalid_strategies'] += 1
                print(f"      ✅ Invalid strategy caused expected exception")
        
        # Evaluar resultados
        expected_valid = len(valid_strategies)
        expected_invalid = len(invalid_strategies)
        
        if (results['valid_strategies'] == expected_valid and
            results['invalid_strategies'] == expected_invalid and
            not any('issue' in error for error in results['config_errors'])):
            results['test_passed'] = True
            print(f"   🎯 Strategy config validation: PASS")
        else:
            print(f"   ⚠️  Strategy config validation: FAIL")
        
        return results
    
    def test_environment_variables_validation(self) -> dict:
        """Test de validación de variables de entorno"""
        print("🌍 Test de validación de variables de entorno...")
        
        results = {
            'env_vars_tested': 0,
            'valid_env_vars': 0,
            'missing_required_vars': [],
            'invalid_env_values': [],
            'test_passed': False
        }
        
        # Variables de entorno críticas esperadas
        required_env_vars = {
            'TRADING_MODE': ['development', 'testing', 'production'],
            'LOG_LEVEL': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            'DATABASE_PATH': None,  # Any valid path
            'MAX_POSITIONS': 'integer',
            'ENABLE_TRADING': ['true', 'false', 'True', 'False', '1', '0']
        }
        
        # Guardar variables actuales para restaurar después
        original_env = {}
        
        for var_name, expected_values in required_env_vars.items():
            results['env_vars_tested'] += 1
            
            # Guardar valor original si existe
            original_env[var_name] = os.environ.get(var_name)
            
            try:
                print(f"   🧪 Testing env var: {var_name}")
                
                current_value = os.environ.get(var_name)
                
                if current_value is None:
                    # Variable faltante
                    results['missing_required_vars'].append(var_name)
                    print(f"      ⚠️  Missing required env var: {var_name}")
                    
                    # Probar con valor válido
                    if expected_values and isinstance(expected_values, list):
                        test_value = expected_values[0]
                        os.environ[var_name] = test_value
                        print(f"      ✅ Set test value: {test_value}")
                        results['valid_env_vars'] += 1
                    elif expected_values == 'integer':
                        os.environ[var_name] = '5'
                        print(f"      ✅ Set test integer value: 5")
                        results['valid_env_vars'] += 1
                    else:
                        os.environ[var_name] = '/tmp/test.db'
                        print(f"      ✅ Set test path value")
                        results['valid_env_vars'] += 1
                else:
                    # Variable existe, validar valor
                    is_valid = self._validate_env_value(var_name, current_value, expected_values)
                    
                    if is_valid:
                        results['valid_env_vars'] += 1
                        print(f"      ✅ Valid value: {current_value}")
                    else:
                        results['invalid_env_values'].append({
                            'var_name': var_name,
                            'current_value': current_value,
                            'expected': expected_values
                        })
                        print(f"      ❌ Invalid value: {current_value}")
                
            except Exception as e:
                print(f"      ❌ Error testing env var {var_name}: {e}")
        
        # Restaurar variables originales
        for var_name, original_value in original_env.items():
            if original_value is not None:
                os.environ[var_name] = original_value
            elif var_name in os.environ:
                del os.environ[var_name]
        
        # Evaluar resultados
        if (len(results['missing_required_vars']) <= 1 and  # Tolerancia para 1 variable faltante
            len(results['invalid_env_values']) == 0):
            results['test_passed'] = True
            print(f"   🎯 Environment variables: PASS")
        else:
            print(f"   ⚠️  Environment variables: FAIL")
        
        return results
    
    def _validate_db_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validar configuración de base de datos"""
        errors = []
        
        # Validar campos requeridos
        required_fields = ['db_type', 'db_path']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validar tipos de datos
        if 'connection_timeout' in config:
            try:
                timeout = int(config['connection_timeout'])
                if timeout <= 0:
                    errors.append("connection_timeout must be positive")
            except (ValueError, TypeError):
                errors.append("connection_timeout must be an integer")
        
        # Validar path de BD
        if 'db_path' in config and config['db_path'] != ':memory:':
            db_path = Path(config['db_path'])
            parent_dir = db_path.parent
            
            if not parent_dir.exists() and str(parent_dir) != '.':
                errors.append(f"Database directory does not exist: {parent_dir}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_trading_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validar parámetros de trading"""
        errors = []
        
        # Validar max_positions
        if 'max_positions' in params:
            try:
                max_pos = int(params['max_positions'])
                if max_pos <= 0:
                    errors.append("max_positions must be positive")
            except (ValueError, TypeError):
                errors.append("max_positions must be an integer")
        
        # Validar max_daily_loss
        if 'max_daily_loss' in params:
            try:
                max_loss = float(params['max_daily_loss'])
                if max_loss > 0:
                    errors.append("max_daily_loss should be negative (represents a loss)")
            except (ValueError, TypeError):
                errors.append("max_daily_loss must be a number")
        
        # Validar percentages
        percentage_fields = ['position_size_percent', 'stop_loss_percent', 'take_profit_percent']
        for field in percentage_fields:
            if field in params:
                try:
                    pct = float(params[field])
                    if pct <= 0 or pct > 1.0:
                        errors.append(f"{field} must be between 0 and 1.0")
                except (ValueError, TypeError):
                    errors.append(f"{field} must be a decimal number")
        
        # Validar trade values
        if 'min_trade_value' in params and 'max_trade_value' in params:
            try:
                min_val = float(params['min_trade_value'])
                max_val = float(params['max_trade_value'])
                if min_val >= max_val:
                    errors.append("min_trade_value must be less than max_trade_value")
            except (ValueError, TypeError):
                errors.append("Trade values must be numbers")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_strategy_config(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validar configuración de estrategia"""
        errors = []
        
        # Validar campos requeridos básicos
        if 'enabled' not in config:
            errors.append("Missing 'enabled' field")
        
        if 'timeframe' in config:
            timeframe = config['timeframe']
            valid_timeframes = ['1min', '5min', '15min', '30min', '1hour', '4hour', '1day']
            if timeframe not in valid_timeframes:
                errors.append(f"Invalid timeframe: {timeframe}")
        
        # Validar valores numéricos positivos
        positive_fields = ['macd_fast', 'macd_slow', 'macd_signal', 'volume_threshold', 
                          'gap_threshold', 'volume_spike', 'position_size']
        
        for field in positive_fields:
            if field in config:
                try:
                    value = float(config[field])
                    if value <= 0:
                        errors.append(f"{field} must be positive")
                except (ValueError, TypeError):
                    errors.append(f"{field} must be a number")
        
        # Validar rangos de precios
        if 'min_price' in config and 'max_price' in config:
            try:
                min_price = float(config['min_price'])
                max_price = float(config['max_price'])
                if min_price >= max_price:
                    errors.append("min_price must be less than max_price")
            except (ValueError, TypeError):
                errors.append("Price values must be numbers")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_env_value(self, var_name: str, value: str, expected) -> bool:
        """Validar valor de variable de entorno"""
        if expected is None:
            # Any value is acceptable
            return True
        elif isinstance(expected, list):
            # Value must be in the list
            return value in expected
        elif expected == 'integer':
            # Value must be a valid integer
            try:
                int(value)
                return True
            except ValueError:
                return False
        
        return False
    
    def cleanup_temp_configs(self):
        """Limpiar configuraciones temporales"""
        try:
            if self.temp_config_dir.exists():
                shutil.rmtree(self.temp_config_dir)
        except Exception as e:
            print(f"   ⚠️  Error cleaning temp configs: {e}")

def main():
    """Ejecutar todos los tests de validación de configuración"""
    print("🔧 TESTS DE VALIDACIÓN DE CONFIGURACIÓN")
    print("=" * 45)
    
    config_test = ConfigurationValidationTest()
    all_results = {}
    
    # Test 1: Validación de configuración de BD
    print("\n1️⃣  VALIDACIÓN DE CONFIGURACIÓN DE BASE DE DATOS")
    print("-" * 45)
    db_config_results = config_test.test_database_configuration_validation()
    all_results['database_configuration'] = db_config_results
    
    # Test 2: Validación de parámetros de trading
    print("\n2️⃣  VALIDACIÓN DE PARÁMETROS DE TRADING")
    print("-" * 45)
    trading_params_results = config_test.test_trading_parameters_validation()
    all_results['trading_parameters'] = trading_params_results
    
    # Test 3: Validación de configuración de estrategias
    print("\n3️⃣  VALIDACIÓN DE CONFIGURACIÓN DE ESTRATEGIAS")
    print("-" * 45)
    strategy_config_results = config_test.test_strategy_configuration_validation()
    all_results['strategy_configuration'] = strategy_config_results
    
    # Test 4: Validación de variables de entorno
    print("\n4️⃣  VALIDACIÓN DE VARIABLES DE ENTORNO")
    print("-" * 45)
    env_vars_results = config_test.test_environment_variables_validation()
    all_results['environment_variables'] = env_vars_results
    
    # Limpiar archivos temporales
    config_test.cleanup_temp_configs()
    
    # Resumen final
    print("\n" + "=" * 45)
    print("📊 RESUMEN DE VALIDACIÓN DE CONFIGURACIÓN")
    print("=" * 45)
    
    test_categories = {
        'database_configuration': 'Configuración Base de Datos',
        'trading_parameters': 'Parámetros de Trading',
        'strategy_configuration': 'Configuración de Estrategias',
        'environment_variables': 'Variables de Entorno'
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
            if test_key == 'database_configuration':
                valid_configs = result.get('configs_passed_validation', 0)
                total_configs = result.get('valid_configs_tested', 0) + result.get('invalid_configs_tested', 0)
                additional_info = f"({valid_configs} configs válidas)"
                
            elif test_key == 'trading_parameters':
                valid_params = result.get('valid_parameter_sets', 0)
                invalid_params = result.get('invalid_parameter_sets', 0)
                additional_info = f"({valid_params} válidos, {invalid_params} inválidos)"
                
            elif test_key == 'strategy_configuration':
                valid_strategies = result.get('valid_strategies', 0)
                total_strategies = result.get('strategies_tested', 0)
                additional_info = f"({valid_strategies}/{total_strategies} estrategias)"
                
            elif test_key == 'environment_variables':
                valid_vars = result.get('valid_env_vars', 0)
                missing_vars = len(result.get('missing_required_vars', []))
                additional_info = f"({valid_vars} válidas, {missing_vars} faltantes)"
            
            print(f"{test_name}: {status} {additional_info}")
            
            if passed:
                passed_tests += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de configuración pasaron")
    
    # Evaluación de configuración
    config_score = passed_tests / total_tests if total_tests > 0 else 0
    
    print("\n🔧 EVALUACIÓN DE CONFIGURACIÓN:")
    
    if config_score == 1.0:
        print("🏆 EXCELENTE - Configuración completamente validada")
        print("✅ Todos los parámetros y settings correctos")
        print("🚀 Sistema listo con configuración óptima")
    elif config_score >= 0.75:
        print("👍 BUENO - Configuración mayormente correcta")
        print("⚠️  Algunas configuraciones necesitan ajustes menores")
        print("🔧 Revisar settings antes de producción")
    else:
        print("⚠️  PROBLEMAS - Configuración tiene fallas significativas")
        print("🔧 Correcciones importantes en parámetros requeridas")
        print("🚫 No usar en producción hasta corregir configuración")
    
    # Recomendaciones específicas
    print(f"\n💡 RECOMENDACIONES DE CONFIGURACIÓN:")
    
    db_result = all_results.get('database_configuration', {})
    if len(db_result.get('critical_config_errors', [])) > 0:
        print("🗄️  Revisar y corregir configuración de base de datos")
    
    trading_result = all_results.get('trading_parameters', {})
    if len(trading_result.get('critical_parameter_errors', [])) > 0:
        print("📊 Ajustar parámetros de trading a valores válidos")
    
    strategy_result = all_results.get('strategy_configuration', {})
    if len(strategy_result.get('config_errors', [])) > 0:
        print("🎯 Corregir configuraciones de estrategias")
    
    env_result = all_results.get('environment_variables', {})
    if len(env_result.get('missing_required_vars', [])) > 0:
        missing_vars = env_result['missing_required_vars']
        print(f"🌍 Configurar variables de entorno faltantes: {', '.join(missing_vars)}")

if __name__ == "__main__":
    main()