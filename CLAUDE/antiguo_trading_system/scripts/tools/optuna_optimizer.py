#!/usr/bin/env python3
"""
MÓDULO DE OPTIMIZACIÓN CON OPTUNA - VERSIÓN LIMPIA
==================================================

Este módulo se integra con tu debug_backtest.py existente para optimizar parámetros.
No reemplaza nada, solo añade optimización inteligente.

INSTALACIÓN REQUERIDA:
pip install optuna optuna-dashboard

USO:
python optuna_optimizer.py

VISUALIZACIÓN:
optuna-dashboard sqlite:///optuna_studies.db
"""

import asyncio
import optuna
import logging
from datetime import datetime
from pathlib import Path
import json
import sys
import sqlite3
import os

# Importar TU sistema existente (sin modificar nada)
sys.path.append(str(Path(__file__).parent))

# Usar EXACTAMENTE tu debug_backtest.py existente
from debug_backtest import (
    load_symbol_data_directly,
    normalize_timezone,
    EnhancedDiagnosticMonitor
)

# Usar TU configuración existente
from backtesting import BacktestEngine, BacktestConfig
from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
from backtests.backtest_config import StrategyConfigurations


class OptunaOptimizer:
    """Optimizador que usa Optuna + TU sistema existente"""
    
    def __init__(self):
        self.logger = logging.getLogger("OptunaOptimizer")
        
        # TU configuración base (igual que en debug_backtest.py)
        self.base_config = BacktestConfig(
            start_date=datetime(2025, 4, 1),
            end_date=datetime(2025, 6, 1),
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,
            slippage_pct=0.001
        )
        
        # TUS parámetros base actuales
        self.base_params = StrategyConfigurations.get_optimized_gap_go_params()
        
        # TUS mejores símbolos (como en tu output)
        self.test_symbols = ['ACDC', 'ADGM', 'ADVM', 'AEHR', 'AEVA', 'AFRI', 'AGEN', 'AGRO', 'AIFF', 'AIRS']  # Top 5
        
        # Configurar base de datos
        self.db_path = "optuna_studies.db"
        self.storage_url = f"sqlite:///{self.db_path}"
        
        print(f"✅ Configuración base cargada:")
        print(f"   Período: {self.base_config.start_date.date()} - {self.base_config.end_date.date()}")
        print(f"   Símbolos: {', '.join(self.test_symbols)}")
        print(f"   Capital inicial: ${self.base_config.initial_capital:,}")
        print(f"   Base de datos: {self.db_path}")
    
    def initialize_optuna_database(self):
        """Inicializar correctamente la base de datos de Optuna"""
        try:
            # Crear el storage y forzar inicialización
            storage = optuna.storages.RDBStorage(
                url=self.storage_url,
                engine_kwargs={
                    "pool_pre_ping": True,
                    "connect_args": {"check_same_thread": False}
                }
            )
            
            # Crear un estudio temporal para inicializar las tablas
            temp_study_name = f"temp_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_study = optuna.create_study(
                study_name=temp_study_name,
                storage=storage,
                direction='maximize'
            )
            
            # Eliminar el estudio temporal
            optuna.delete_study(study_name=temp_study_name, storage=storage)
            
            print(f"✅ Base de datos Optuna inicializada correctamente: {self.db_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error inicializando base de datos: {e}")
            # Intentar crear una nueva base de datos limpia
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.db_path, backup_path)
                print(f"📦 Base de datos anterior respaldada como: {backup_path}")
            
            try:
                # Crear nueva base de datos
                storage = optuna.storages.RDBStorage(self.storage_url)
                print(f"✅ Nueva base de datos creada: {self.db_path}")
                return True
            except Exception as e2:
                print(f"❌ Error creando nueva base de datos: {e2}")
                return False
    
    def create_data_loader(self):
        """TU data loader exacto (copiado de debug_backtest.py)"""
        def data_loader(symbol: str, start_date: datetime, end_date: datetime):
            df = load_symbol_data_directly(symbol, "data")
            
            if df.empty:
                return df
            
            df = normalize_timezone(df, target_tz=None)
            
            if hasattr(start_date, 'tz') and start_date.tz is not None:
                start_date = start_date.replace(tzinfo=None)
            if hasattr(end_date, 'tz') and end_date.tz is not None:
                end_date = end_date.replace(tzinfo=None)
            
            try:
                mask = (df.index >= start_date) & (df.index <= end_date)
                filtered_df = df[mask]
                
                if filtered_df.empty:
                    filtered_df = df.tail(1000)
                
                return filtered_df
                
            except Exception as e:
                self.logger.warning(f"Error filtrando {symbol}: {e}")
                return df.tail(1000)
        
        return data_loader
    
    def objective(self, trial):
        """Función objetivo SÍNCRONA para Optuna"""
        
        try:
            # Crear parámetros combinando base + sugerencias de Optuna
            optimized_params = self.base_params.copy()
            
            # PARÁMETROS CRÍTICOS A OPTIMIZAR (basados en tu estrategia)
            optimized_params.update({
                # Gap Detection - Los más importantes
                'gap_percent_threshold': trial.suggest_float('gap_percent_threshold', 0.8, 2.5, step=0.1),
                'min_gap_percent': trial.suggest_float('min_gap_percent', 1.2, 3.5, step=0.1),
                'max_gap_percent': trial.suggest_float('max_gap_percent', 15.0, 30.0, step=2.5),
                
                # Risk Management - Críticos para mejorar win rate
                'stop_loss_pct': trial.suggest_float('stop_loss_pct', 0.015, 0.045, step=0.005),
                'take_profit_pct': trial.suggest_float('take_profit_pct', 0.035, 0.085, step=0.005),
                'trailing_stop_pct': trial.suggest_float('trailing_stop_pct', 0.01, 0.025, step=0.0025),
                
                # Volume - Importantes para filtrar
                'volume_multiplier': trial.suggest_float('volume_multiplier', 1.3, 2.8, step=0.1),
                'min_volume': trial.suggest_int('min_volume', 8000, 20000, step=2000),
                'min_daily_volume': trial.suggest_int('min_daily_volume', 60000, 150000, step=15000),
                
                # Trading Controls - Para evitar overtrading
                'max_daily_trades': trial.suggest_int('max_daily_trades', 2, 6),
                'max_concurrent_positions': trial.suggest_int('max_concurrent_positions', 1, 3),
                'no_entry_after': trial.suggest_float('no_entry_after', 12.5, 15.0, step=0.5),
                
                # Position Sizing
                'max_position_value': trial.suggest_float('max_position_value', 300.0, 600.0, step=50.0),
                'max_risk_per_trade': trial.suggest_float('max_risk_per_trade', 0.015, 0.035, step=0.005),
                
                # Timing
                'max_hold_time': trial.suggest_int('max_hold_time', 90, 300, step=30),
                'cooldown_period': trial.suggest_int('cooldown_period', 20, 90, step=10),
            })
            
            # Crear TU estrategia con parámetros optimizados
            strategy = OptimizedGapGoStrategy(optimized_params)
            
            # Crear TU engine exacto
            engine = BacktestEngine(self.base_config)
            engine.add_strategy(strategy)
            engine.set_data_loader(self.create_data_loader())
            
            # Crear monitor para tracking
            monitor = EnhancedDiagnosticMonitor()
            engine.set_external_monitor(monitor)
            
            # Ejecutar TU backtest exacto - VERSIÓN SÍNCRONA
            # Crear un nuevo loop para este trial
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(engine.run_backtest(self.test_symbols))
            finally:
                loop.close()
                # No reiniciar event loop para evitar problemas
            
            if not results or results.total_trades < 10:
                # Si muy pocos trades, penalizar
                return -100.0
            
            # MÉTRICA OBJETIVO: Combinación de Sharpe + Win Rate + Return
            # (puedes ajustar estos pesos según tus preferencias)
            sharpe_ratio = getattr(results, 'sharpe_ratio', -10)
            win_rate = getattr(results, 'win_rate', 0) / 100  # 0-1
            total_return = getattr(results, 'total_return_pct', -50) / 100  # 0-1
            max_dd = abs(getattr(results, 'max_drawdown_pct', 50)) / 100  # 0-1
            
            # Score compuesto (puedes modificar pesos)
            objective_score = (
                sharpe_ratio * 0.4 +           # 40% Sharpe (risk-adjusted)
                win_rate * 0.3 +               # 30% Win rate 
                total_return * 0.2 +           # 20% Total return
                (1 - max_dd) * 0.1             # 10% Drawdown penalty
            )
            
            # Log progreso cada 10 trials
            if trial.number % 10 == 0:
                print(f"Trial {trial.number}: Score={objective_score:.3f}, "
                      f"Sharpe={sharpe_ratio:.3f}, WR={win_rate*100:.1f}%, "
                      f"Return={total_return*100:.2f}%")
            
            return objective_score
            
        except Exception as e:
            self.logger.error(f"Error in trial {trial.number}: {e}")
            return -100.0  # Penalización por error
    
    def optimize(self, n_trials: int = 100):
        """Ejecutar optimización con Optuna - VERSIÓN SÍNCRONA"""
        
        print(f"\n🚀 INICIANDO OPTIMIZACIÓN CON OPTUNA")
        print(f"   Trials: {n_trials}")
        print(f"   Algoritmo: TPE (Tree-structured Parzen Estimator)")
        print(f"   Objetivo: Maximizar Sharpe + Win Rate + Return")
        print("=" * 60)
        
        # Inicializar base de datos
        if not self.initialize_optuna_database():
            print("❌ No se pudo inicializar la base de datos. Abortando.")
            return None
        
        # Crear estudio Optuna
        study_name = f"gap_go_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Crear storage
            storage = optuna.storages.RDBStorage(
                url=self.storage_url,
                engine_kwargs={
                    "pool_pre_ping": True,
                    "connect_args": {"check_same_thread": False}
                }
            )
            
            # Crear estudio
            study = optuna.create_study(
                study_name=study_name,
                storage=storage,
                direction='maximize',  # Maximizar la métrica objetivo
                sampler=optuna.samplers.TPESampler(seed=42),  # Reproducible
                pruner=optuna.pruners.MedianPruner(n_warmup_steps=10),  # Pruning inteligente
                load_if_exists=True  # Continuar si existe
            )
            
            print(f"📊 Estudio creado: {study_name}")
            print(f"💾 Base de datos: {self.storage_url}")
            
        except Exception as e:
            print(f"❌ Error creando estudio: {e}")
            return None
        
        # Ejecutar optimización usando el método estándar de Optuna
        try:
            study.optimize(self.objective, n_trials=n_trials, timeout=3600)  # 1 hora max
            
        except KeyboardInterrupt:
            print("\n⚠️  Optimización interrumpida por usuario")
        except Exception as e:
            print(f"\n❌ Error durante optimización: {e}")
            import traceback
            traceback.print_exc()
        
        # Análisis de resultados
        return self.analyze_results(study)
    
    def analyze_results(self, study):
        """Analizar resultados de optimización"""
        
        print(f"\n" + "=" * 60)
        print("📊 RESULTADOS DE OPTIMIZACIÓN OPTUNA")
        print("=" * 60)
        
        # Verificar que hay trials completados
        completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if not completed_trials:
            print("❌ No hay trials completados para analizar")
            return None
        
        # Mejor trial
        best_trial = study.best_trial
        
        print(f"\n🏆 MEJOR CONFIGURACIÓN ENCONTRADA:")
        print(f"   Número de trial: {best_trial.number}")
        print(f"   Valor objetivo: {best_trial.value:.4f}")
        print(f"   Estado: {best_trial.state}")
        
        print(f"\n🎯 MEJORES PARÁMETROS:")
        for param_name, param_value in best_trial.params.items():
            current_value = self.base_params.get(param_name, 'N/A')
            print(f"   {param_name:25s}: {param_value:>8} (actual: {current_value})")
        
        # Estadísticas del estudio
        print(f"\n📈 ESTADÍSTICAS DE OPTIMIZACIÓN:")
        print(f"   Total trials: {len(study.trials)}")
        print(f"   Trials completados: {len(completed_trials)}")
        print(f"   Trials fallidos: {len([t for t in study.trials if t.state == optuna.trial.TrialState.FAIL])}")
        print(f"   Mejor valor: {study.best_value:.4f}")
        
        # Top 5 trials
        top_trials = sorted(completed_trials, key=lambda t: t.value if t.value else -100, reverse=True)[:5]
        
        print(f"\n🔝 TOP 5 CONFIGURACIONES:")
        for i, trial in enumerate(top_trials, 1):
            if trial.value:
                print(f"   #{i}: Trial {trial.number} - Score: {trial.value:.4f}")
        
        # Guardar resultados
        self.save_optimization_results(study, best_trial)
        
        # Importancia de parámetros
        try:
            if len(completed_trials) >= 10:  # Necesario mínimo para calcular importancia
                param_importance = optuna.importance.get_param_importances(study)
                print(f"\n📊 IMPORTANCIA DE PARÁMETROS:")
                for param, importance in sorted(param_importance.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"   {param:25s}: {importance:.4f}")
            else:
                print(f"\n⚠️  Necesitas al menos 10 trials completados para calcular importancia")
        except Exception as e:
            print(f"\n⚠️  No se pudo calcular importancia de parámetros: {e}")
        
        return {
            'study': study,
            'best_trial': best_trial,
            'best_params': best_trial.params,
            'best_value': best_trial.value,
            'study_name': study.study_name
        }
    
    def save_optimization_results(self, study, best_trial):
        """Guardar resultados de optimización"""
        
        output_dir = Path("optimization_results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Guardar mejores parámetros
        best_params_file = output_dir / f"best_parameters_{timestamp}.json"
        
        results_data = {
            'optimization_timestamp': timestamp,
            'study_name': study.study_name,
            'total_trials': len(study.trials),
            'best_trial_number': best_trial.number,
            'best_objective_value': best_trial.value,
            'best_parameters': best_trial.params,
            'current_parameters': self.base_params,
            'parameter_improvements': {},
            'optuna_database': self.db_path
        }
        
        # Calcular mejoras
        for param_name, new_value in best_trial.params.items():
            current_value = self.base_params.get(param_name, None)
            if current_value is not None:
                if isinstance(new_value, (int, float)) and isinstance(current_value, (int, float)):
                    improvement = ((new_value - current_value) / current_value * 100) if current_value != 0 else 0
                    results_data['parameter_improvements'][param_name] = f"{improvement:+.1f}%"
        
        with open(best_params_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        print(f"\n💾 Resultados guardados en:")
        print(f"   📊 {best_params_file}")
        print(f"   📈 {self.db_path} (para dashboard)")
        
        # Crear archivo de configuración listo para usar
        config_file = output_dir / f"optimized_config_{timestamp}.ini"
        self.create_config_file(best_trial.params, config_file)
        
        print(f"   ⚙️  {config_file} (listo para reemplazar config.ini)")
    
    def create_config_file(self, optimized_params, config_file):
        """Crear archivo config.ini con parámetros optimizados"""
        
        # Combinar parámetros base con optimizados
        final_params = self.base_params.copy()
        final_params.update(optimized_params)
        
        config_content = "[OPTIMIZED_GAP_GO_STRATEGY]\n"
        config_content += f"# Generado por Optuna el {datetime.now()}\n"
        config_content += f"# Mejores parámetros encontrados\n\n"
        
        for param_name, param_value in final_params.items():
            if isinstance(param_value, bool):
                config_content += f"{param_name} = {'true' if param_value else 'false'}\n"
            else:
                config_content += f"{param_name} = {param_value}\n"
        
        with open(config_file, 'w') as f:
            f.write(config_content)
    
    def test_dashboard_connection(self):
        """Probar que el dashboard puede conectarse a la base de datos"""
        try:
            # Intentar abrir la base de datos directamente
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar tablas necesarias
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            required_tables = ['studies', 'trials', 'trial_params', 'trial_values']
            existing_tables = [table[0] for table in tables]
            
            print(f"\n🔍 VERIFICACIÓN DE BASE DE DATOS:")
            print(f"   Archivo: {self.db_path}")
            print(f"   Tablas encontradas: {existing_tables}")
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            if missing_tables:
                print(f"   ⚠️  Tablas faltantes: {missing_tables}")
            else:
                print(f"   ✅ Todas las tablas necesarias están presentes")
            
            conn.close()
            
            print(f"\n📊 COMANDO PARA DASHBOARD:")
            print(f"   optuna-dashboard sqlite:///{self.db_path}")
            print(f"   Luego abrir: http://localhost:8080")
            
            return len(missing_tables) == 0
            
        except Exception as e:
            print(f"❌ Error verificando base de datos: {e}")
            return False


def main():
    """Función principal - completamente síncrona"""
    
    print("🚀 OPTIMIZADOR OPTUNA PARA TU ESTRATEGIA GAP & GO - VERSIÓN LIMPIA")
    print("=" * 70)
    print("Usa tu debug_backtest.py existente + algoritmos inteligentes de Optuna")
    print("Versión completamente síncrona para evitar problemas de asyncio")
    print()
    
    # Verificar instalación de Optuna
    try:
        import optuna
        print("✅ Optuna instalado correctamente")
    except ImportError:
        print("❌ Optuna no instalado. Ejecuta: pip install optuna optuna-dashboard")
        return
    
    # Configurar logging
    logging.basicConfig(level=logging.WARNING)  # Reducir ruido
    
    # Crear optimizador
    optimizer = OptunaOptimizer()
    
    # Preguntar número de trials
    try:
        n_trials = input("¿Cuántos trials quieres ejecutar? (recomendado: 50-200): ").strip()
        n_trials = int(n_trials) if n_trials else 100
    except:
        n_trials = 100
    
    print(f"\n🧪 Ejecutando {n_trials} trials en modo síncrono...")
    
    # Ejecutar optimización
    results = optimizer.optimize(n_trials=n_trials)
    
    if results:
        print(f"\n🎉 OPTIMIZACIÓN COMPLETADA!")
        
        # Probar conexión del dashboard
        print(f"\n🔧 PROBANDO DASHBOARD...")
        dashboard_ok = optimizer.test_dashboard_connection()
        
        if dashboard_ok:
            print(f"\n✅ Dashboard listo para usar!")
        else:
            print(f"\n⚠️  Posible problema con dashboard")
        
        print(f"\n💡 PRÓXIMOS PASOS:")
        print(f"1. Revisar resultados arriba")
        print(f"2. Copiar optimized_config_*.ini a config.ini")
        print(f"3. Ejecutar: python debug_backtest.py")
        print(f"4. Comparar performance vs configuración anterior")
        print(f"\n📊 VER DASHBOARD INTERACTIVO:")
        print(f"   optuna-dashboard sqlite:///{optimizer.db_path}")
        print(f"   Luego abrir: http://localhost:8080")
    else:
        print(f"\n❌ Optimización falló. Revisa los logs arriba.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Optimización cancelada por usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()