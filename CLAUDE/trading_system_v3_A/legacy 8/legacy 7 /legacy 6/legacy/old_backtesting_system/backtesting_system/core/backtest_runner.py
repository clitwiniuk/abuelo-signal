#!/usr/bin/env python3
"""
Professional Backtest Runner
============================

Runner principal para ejecutar backtests de workers de trading.
Sistema profesional con workers reales del directorio /strategies/workers/.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import sys
import json

# Agregar el directorio raíz al PYTHONPATH para poder importar strategies
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# AGREGAR DIRECTORIOS ADICIONALES NECESARIOS
strategies_dir = os.path.join(base_dir, 'strategies')
workers_dir = os.path.join(strategies_dir, 'workers')
core_dir = os.path.join(base_dir, 'core')

for directory in [strategies_dir, workers_dir, core_dir]:
    if directory not in sys.path:
        sys.path.insert(0, directory)

# Importar componentes locales
from .worker_tester import WorkerTester
from .metrics_calculator import MetricsCalculator
from .visualization_utils import VisualizationUtils
from .intraday_backtester import IntradayBacktester

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Runner principal para ejecutar backtests de workers"""
    
    def __init__(self, output_dir: str = "results"):
        """
        Inicializa el runner de backtests
        
        Args:
            output_dir: Directorio de salida para resultados
        """
        # Directorio base del proyecto
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Configurar directorio de salida
        self.output_dir = os.path.join(self.base_dir, "CLAUDE/trading_system_v3/backtesting_system", output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Subdirectorios
        self.results_dir = os.path.join(self.output_dir, "results")
        self.charts_dir = os.path.join(self.output_dir, "charts")
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.charts_dir, exist_ok=True)
        
        # Inicializar componentes
        self.metrics_calculator = MetricsCalculator()
        self.visualizer = VisualizationUtils(self.charts_dir)
        self.backtester = IntradayBacktester()
        
        # Inicializar data loader con datos reales
        try:
            from .data_loader_real import DataLoaderReal
            self.data_loader = DataLoaderReal()
            logger.info(f"📊 DataLoaderReal inicializado")
            logger.info(f"📊 Base de datos: {self.data_loader.db_path}")
        except Exception as e:
            logger.error(f"❌ Error inicializando DataLoaderReal: {e}")
            raise
        
        # Workers disponibles (con clases reales del sistema)
        self.available_workers = {
            'macdv': 'strategies.workers.macdv_worker_logic.MacdvWorkerLogic',
            'daily_plays': 'strategies.workers.daily_plays_worker_logic.DailyPlaysWorkerLogic',
            'vwap': 'strategies.workers.vwap_worker_logic.VWAPWorkerLogic',
            'momentum_breakout': 'strategies.workers.momentum_breakout_worker_logic.MomentumBreakoutWorkerLogic',
            'vcp_smallcap': 'strategies.workers.vcp_smallcap_worker_logic.VCPSmallcapWorkerLogic',
            'volume_absorption': 'strategies.workers.volume_absorption_worker_logic.VolumeAbsorptionWorkerLogic',
            'generic_01': 'strategies.workers.generic_01_worker_logic.Generic01WorkerLogic'
        }
        
        logger.info("🚀 Professional BacktestRunner inicializado")
        logger.info(f"   Output Directory: {self.output_dir}")
        logger.info(f"   Workers Available: {len(self.available_workers)}")
        logger.info(f"   Data Source: Real (market_data.db)")

    def list_available_workers(self):
        """Lista todos los workers disponibles para testing"""
        print("\n📋 Workers Disponibles para Backtesting:")
        print("="*50)
        
        worker_descriptions = {
            'macdv': 'MACD Divergence Strategy',
            'daily_plays': 'Daily Catalyst Plays',
            'vwap': 'VWAP Strategy',
            'momentum_breakout': 'Momentum Breakout Strategy',
            'vcp_smallcap': 'VCP Smallcap Strategy',
            'volume_absorption': 'Volume Absorption Strategy',
            'generic_01': 'Generic Worker Strategy'
        }
        
        for worker_name in self.available_workers.keys():
            description = worker_descriptions.get(worker_name, 'Worker Strategy')
            print(f"  • {worker_name:<20}: {description}")
        
        print(f"\n💡 Total: {len(self.available_workers)} workers disponibles")
        print("📝 Usando workers reales del sistema de trading")

    def _load_worker_class(self, class_path: str):
        """Carga dinámicamente una clase de worker"""
        if class_path is None:
            return None
            
        try:
            # Split path en module y class
            module_path, class_name = class_path.rsplit('.', 1)
            
            # Importar módulo
            import importlib
            module = importlib.import_module(module_path)
            
            # Obtener clase
            worker_class = getattr(module, class_name)
            
            logger.info(f"✅ Worker class cargada: {class_path}")
            return worker_class
            
        except Exception as e:
            logger.warning(f"⚠️ Error cargando worker {class_path}: {e}")
            return None

    async def run_single_worker_test(self, worker_name: str, num_patterns: int = 50, 
                                   visualize: bool = True, detailed: bool = True) -> Dict[str, Any]:
        """
        Ejecuta test individual de un worker específico
        
        Args:
            worker_name: Nombre del worker a testear
            num_patterns: Número de patrones sintéticos a generar
            visualize: Si generar visualizaciones
            detailed: Si incluir análisis detallado
            
        Returns:
            Métricas calculadas del test
        """
        if worker_name not in self.available_workers:
            raise ValueError(f"Worker '{worker_name}' no disponible. Use --list-workers para ver opciones.")
        
        logger.info(f"🧪 Iniciando test individual: {worker_name}")
        logger.info(f"   Patrones: {num_patterns}")
        logger.info(f"   Visualización: {visualize}")
        
        try:
            # Cargar oportunidades reales desde market_data.db
            logger.info("📊 Cargando oportunidades reales desde market_data.db...")
            all_opportunities = self.data_loader.load_real_opportunities(
                symbols=None,  # Todos los símbolos disponibles
                start_date=None,  # Todos los datos
                end_date=None,
                min_volume=10000,
                pattern_type='all'
            )
            
            # FILTRO CRÍTICO: Garantizar unicidad por ticker + fecha + patrón
            unique_opportunities = self._ensure_unique_opportunities(all_opportunities)
            
            # Limitar a num_patterns de las únicas
            patterns = unique_opportunities[:num_patterns]
            
            logger.info(f"✅ {len(patterns)} oportunidades REALES únicas cargadas")
            logger.info(f"   📊 Total original: {len(all_opportunities)}")
            logger.info(f"   🔍 Únicas: {len(unique_opportunities)}")
            
            # Calcular calidad promedio
            if patterns:
                avg_quality = sum(p.get('quality_score', 50) for p in patterns) / len(patterns)
                logger.info(f"⭐ Quality promedio: {avg_quality:.1f}/100")
            else:
                raise Exception("No se encontraron oportunidades reales en la base de datos")
            
            # USAR WORKERS REALISTAS EN LUGAR DE WORKERS REALES (ARREGLA IMPORT ERROR)
            try:
                logger.info(f"🧠 Cargando worker realista: {worker_name}")
                from .realistic_workers import get_realistic_worker_class
                
                # Obtener LA CLASE del worker realista (no la instancia)
                worker_class = get_realistic_worker_class(worker_name)
                logger.info(f"✅ Worker realista cargado: {worker_name} (clase: {worker_class.__name__})")
                
                # Crear tester con worker CLASE
                tester = WorkerTester(worker_name, worker_class)
                
            except Exception as e:
                logger.warning(f"⚠️ Error cargando worker realista {worker_name}: {e}")
                logger.warning(f"⚠️ Error detallado: {e}")
                
                # Fallback: usar MockWorker interno
                tester = WorkerTester(worker_name, None)
                logger.info(f"🔄 Usando worker mock de respaldo: {worker_name}")
            
            # Ejecutar test
            logger.info("🔄 Ejecutando test del worker...")
            results = await tester.run_comprehensive_test(patterns, detailed=detailed)
            
            # Calcular métricas
            logger.info("📈 Calculando métricas...")
            metrics = self.metrics_calculator.calculate_all_metrics(results)
            
            # Generar visualizaciones si se solicita
            if visualize:
                logger.info("🎨 Generando visualizaciones...")
                try:
                    await self.visualizer.create_worker_analysis_charts(worker_name, results, metrics)
                    logger.info("✅ Visualizaciones generadas")
                except Exception as e:
                    logger.warning(f"⚠️ Error generando visualizaciones: {e}")
            
            # Guardar resultados
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = os.path.join(self.results_dir, f"{worker_name}_{timestamp}.json")
            self.metrics_calculator.save_metrics_to_file(metrics, results_file)
            
            logger.info(f"✅ Test completado exitosamente")
            logger.info(f"📁 Resultados guardados en: {results_file}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error en test de {worker_name}: {e}")
            return {'error': str(e), 'worker_name': worker_name}

    async def run_multi_worker_comparison(self, worker_names: List[str], num_patterns: int = 50,
                                        visualize: bool = True) -> Dict[str, Any]:
        """
        Ejecuta comparación entre múltiples workers
        
        Args:
            worker_names: Lista de nombres de workers a comparar
            num_patterns: Número de patrones por worker
            visualize: Si generar gráficos de comparación
            
        Returns:
            Dict con métricas de todos los workers
        """
        logger.info("🏁 Iniciando comparación multi-worker")
        logger.info(f"   Workers: {', '.join(worker_names)}")
        logger.info(f"   Patrones por worker: {num_patterns}")
        
        results = {}
        
        # Ejecutar tests en paralelo
        tasks = []
        for worker_name in worker_names:
            if worker_name in self.available_workers:
                task = self.run_single_worker_test(worker_name, num_patterns, visualize=False, detailed=False)
                tasks.append((worker_name, task))
            else:
                logger.warning(f"⚠️ Worker '{worker_name}' no disponible, saltando...")
                results[worker_name] = {'error': 'Worker no disponible'}
        
        # Ejecutar todos los tests
        if tasks:
            completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            for (worker_name, _), result in zip(tasks, completed_tasks):
                if isinstance(result, Exception):
                    logger.error(f"❌ Error en {worker_name}: {result}")
                    results[worker_name] = {'error': str(result)}
                else:
                    results[worker_name] = result
        
        # Generar comparación visual si se solicita
        if visualize and len([r for r in results.values() if 'error' not in r]) > 1:
            logger.info("🎨 Generando gráficos de comparación...")
            try:
                await self.visualizer.create_worker_comparison_charts(results)
                logger.info("✅ Gráficos de comparación generados")
            except Exception as e:
                logger.warning(f"⚠️ Error generando comparación: {e}")
        
        # Crear dashboard resumen
        dashboard = self.visualizer.create_summary_dashboard(results)
        print("\n" + dashboard)
        
        logger.info("✅ Comparación multi-worker completada")
        return results

    async def run_benchmark(self, worker_names: Optional[List[str]] = None, num_patterns: int = 75) -> Dict[str, Any]:
        """
        Ejecuta benchmark completo del sistema
        
        Args:
            worker_names: Lista de workers (None para todos disponibles)
            num_patterns: Número de patrones por worker
            
        Returns:
            Dict con reporte completo del benchmark
        """
        logger.info("🚀 Iniciando benchmark completo del sistema")
        
        # Determinar workers a testear
        if worker_names is None:
            worker_names = list(self.available_workers.keys())
        else:
            worker_names = [w for w in worker_names if w in self.available_workers]
        
        if not worker_names:
            raise ValueError("No workers válidos para benchmark")
        
        logger.info(f"   Workers en benchmark: {len(worker_names)}")
        logger.info(f"   Patrones por worker: {num_patterns}")
        
        start_time = datetime.now()
        
        try:
            # Ejecutar comparación multi-worker
            results = await self.run_multi_worker_comparison(worker_names, num_patterns, visualize=True)
            
            # Crear reporte de benchmark
            benchmark_report = {
                'timestamp': start_time.isoformat(),
                'duration_seconds': (datetime.now() - start_time).total_seconds(),
                'workers_tested': len(worker_names),
                'num_patterns_per_worker': num_patterns,
                'results': results,
                'summary': self._create_benchmark_summary(results)
            }
            
            # Guardar reporte
            timestamp = start_time.strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(self.results_dir, f"benchmark_report_{timestamp}.json")
            self.metrics_calculator.save_metrics_to_file(benchmark_report, report_file)
            
            # Generar visualizaciones de benchmark
            try:
                await self.visualizer.create_benchmark_report_chart(benchmark_report)
            except Exception as e:
                logger.warning(f"⚠️ Error generando charts de benchmark: {e}")
            
            logger.info(f"✅ Benchmark completado en {benchmark_report['duration_seconds']:.1f} segundos")
            logger.info(f"📁 Reporte guardado en: {report_file}")
            
            return benchmark_report
            
        except Exception as e:
            logger.error(f"❌ Error en benchmark: {e}")
            return {'error': str(e), 'workers_tested': len(worker_names)}

    def _create_benchmark_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Crea resumen estadístico del benchmark"""
        valid_results = {k: v for k, v in results.items() if 'error' not in v}
        
        if not valid_results:
            return {'error': 'No hay resultados válidos'}
        
        # Calcular estadísticas agregadas
        win_rates = [r.get('win_rate', 0) for r in valid_results.values()]
        avg_returns = [r.get('avg_return', 0) for r in valid_results.values()]
        profit_factors = [r.get('profit_factor', 0) for r in valid_results.values()]
        total_trades = [r.get('total_trades', 0) for r in valid_results.values()]
        
        summary = {
            'total_workers': len(results),
            'successful_workers': len(valid_results),
            'failed_workers': len(results) - len(valid_results),
            
            'aggregate_win_rate': sum(win_rates) / len(win_rates),
            'aggregate_avg_return': sum(avg_returns) / len(avg_returns),
            'aggregate_profit_factor': sum(profit_factors) / len(profit_factors),
            'total_trades_processed': sum(total_trades),
            
            'best_performer': max(valid_results.items(), key=lambda x: x[1].get('win_rate', 0))[0],
            'worst_performer': min(valid_results.items(), key=lambda x: x[1].get('win_rate', 0))[0],
            
            'consistency_score': self._calculate_benchmark_consistency(valid_results)
        }
        
        return summary

    def _calculate_benchmark_consistency(self, results: Dict[str, Any]) -> float:
        """Calcula score de consistencia del benchmark"""
        if len(results) < 2:
            return 0.0
        
        win_rates = [r.get('win_rate', 0) for r in results.values()]
        return 1 - (max(win_rates) - min(win_rates))  # Menor spread = mayor consistencia

    def _ensure_unique_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        CRÍTICO: Garantizar que cada oportunidad sea única por ticker + fecha (NO por patrón)
        
        Args:
            opportunities: Lista de oportunidades cargadas
            
        Returns:
            Lista filtrada con oportunidades únicas (1 por ticker+fecha)
        """
        unique_opportunities = []
        seen_combinations = set()
        
        for opp in opportunities:
            # Crear clave única: ticker + fecha (SIN patrón)
            symbol = opp.get('symbol', '')
            timestamp = opp.get('timestamp', '')
            
            # Extraer fecha (solo YYYY-MM-DD, sin hora)
            date_part = timestamp[:10] if len(timestamp) >= 10 else timestamp
            unique_key = f"{symbol}_{date_part}"
            
            # Solo agregar si es la primera vez que vemos este ticker+fecha
            if unique_key not in seen_combinations:
                seen_combinations.add(unique_key)
                unique_opportunities.append(opp)
                logger.debug(f"✅ Evento único: {unique_key} ({opp.get('pattern_type', 'unknown')})")
            else:
                logger.debug(f"⚠️ Saltando patrón adicional para {unique_key} ({opp.get('pattern_type', 'unknown')})")
        
        logger.info(f"🔍 Filtrado: {len(opportunities)} -> {len(unique_opportunities)} eventos únicos")
        logger.info(f"   📊 Criterio: 1 evento por ticker + fecha (independiente del patrón)")
        
        return unique_opportunities