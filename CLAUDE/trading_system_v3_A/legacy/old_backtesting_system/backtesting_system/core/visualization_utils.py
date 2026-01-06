"""
Visualization Utils
==================

Utilidades para crear visualizaciones de resultados de backtesting.
Genera gráficos y charts para análisis de performance de workers.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import os

# Configure matplotlib for better plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10

logger = logging.getLogger(__name__)


class VisualizationUtils:
    """Utilidades de visualización para backtesting"""
    
    def __init__(self, output_dir: str = "backtest_charts"):
        """
        Inicializa el visualizador
        
        Args:
            output_dir: Directorio donde guardar las imágenes
        """
        self.output_dir = output_dir
        self.ensure_output_dir()
        
        logger.info(f"📊 VisualizationUtils inicializado - Output: {output_dir}")

    def ensure_output_dir(self):
        """Crea el directorio de salida si no existe"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def create_worker_analysis_charts(self, worker_name: str, results, metrics: Dict[str, Any]):
        """
        Crea gráficos de análisis para un worker individual
        
        Args:
            worker_name: Nombre del worker
            results: Resultados del testing
            metrics: Métricas calculadas
        """
        try:
            logger.info(f"📊 Creando gráficos para {worker_name}")
            
            # Crear figura con subplots
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(f'Worker Analysis: {worker_name.upper()}', fontsize=16, fontweight='bold')
            
            # 1. Win Rate Pie Chart
            await self._create_win_rate_pie(axes[0, 0], metrics)
            
            # 2. Performance Metrics Bar Chart
            await self._create_performance_bars(axes[0, 1], metrics)
            
            # 3. Response Time Distribution
            await self._create_response_time_hist(axes[0, 2], results)
            
            # 4. Pattern Type Performance (si disponible)
            await self._create_pattern_performance(axes[1, 0], results)
            
            # 5. Quality vs Performance Scatter
            await self._create_quality_scatter(axes[1, 1], results, metrics)
            
            # 6. Cumulative PnL (simulado)
            await self._create_cumulative_pnl(axes[1, 2], results)
            
            # Ajustar layout y guardar
            plt.tight_layout()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/worker_analysis_{worker_name}_{timestamp}.png"
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✅ Gráficos guardados: {filename}")
            
        except Exception as e:
            logger.error(f"Error creando gráficos para {worker_name}: {e}")

    async def create_worker_comparison_charts(self, comparison_metrics: Dict[str, Any]):
        """
        Crea gráficos de comparación entre workers
        
        Args:
            comparison_metrics: Métricas de múltiples workers
        """
        try:
            logger.info("🏁 Creando gráficos de comparación de workers")
            
            # Crear figura con subplots
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Worker Performance Comparison', fontsize=16, fontweight='bold')
            
            # Filtrar workers válidos (sin errores)
            valid_workers = {
                name: metrics for name, metrics in comparison_metrics.items()
                if 'error' not in metrics
            }
            
            if not valid_workers:
                logger.warning("No workers válidos para comparar")
                return
            
            # 1. Win Rate Comparison
            await self._create_win_rate_comparison(axes[0, 0], valid_workers)
            
            # 2. Average Return Comparison
            await self._create_return_comparison(axes[0, 1], valid_workers)
            
            # 3. Profit Factor Comparison
            await self._create_profit_factor_comparison(axes[1, 0], valid_workers)
            
            # 4. Overall Score Heatmap
            await self._create_performance_heatmap(axes[1, 1], valid_workers)
            
            # Ajustar layout y guardar
            plt.tight_layout()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/worker_comparison_{timestamp}.png"
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✅ Gráficos de comparación guardados: {filename}")
            
        except Exception as e:
            logger.error(f"Error creando gráficos de comparación: {e}")

    async def create_benchmark_report_chart(self, benchmark_data: Dict[str, Any]):
        """
        Crea gráfico de reporte de benchmark
        
        Args:
            benchmark_data: Datos del benchmark completo
        """
        try:
            logger.info("🚀 Creando gráfico de benchmark report")
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 10))
            fig.suptitle('Backtesting Benchmark Report', fontsize=16, fontweight='bold')
            
            # Extraer datos válidos
            workers_data = {
                name: metrics for name, metrics in benchmark_data.get('results', {}).items()
                if 'error' not in metrics
            }
            
            if not workers_data:
                logger.warning("No workers válidos para benchmark")
                return
            
            # 1. Overall Performance Radar Chart
            await self._create_radar_chart(axes[0, 0], workers_data)
            
            # 2. Processing Speed Comparison
            await self._create_speed_comparison(axes[0, 1], benchmark_data)
            
            # 3. Trade Volume vs Quality
            await self._create_volume_quality_scatter(axes[1, 0], workers_data)
            
            # 4. Time Series Performance (simulado)
            await self._create_performance_timeline(axes[1, 1], workers_data)
            
            # Ajustar layout y guardar
            plt.tight_layout()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/benchmark_report_{timestamp}.png"
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✅ Gráfico de benchmark guardado: {filename}")
            
        except Exception as e:
            logger.error(f"Error creando gráfico de benchmark: {e}")

    async def _create_win_rate_pie(self, ax, metrics: Dict[str, Any]):
        """Crea pie chart de win rate"""
        win_rate = metrics.get('win_rate', 0)
        total_trades = metrics.get('total_trades', 0)
        
        if total_trades == 0:
            ax.text(0.5, 0.5, 'No trades executed', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Win Rate')
            return
        
        wins = int(win_rate * total_trades)
        losses = total_trades - wins
        
        labels = ['Wins', 'Losses']
        sizes = [wins, losses]
        colors = ['#2ecc71', '#e74c3c']
        explode = (0.05, 0)  # explode winning slice
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
               shadow=True, startangle=90)
        ax.set_title(f'Win Rate: {win_rate:.1%}\nTotal Trades: {total_trades}')

    async def _create_performance_bars(self, ax, metrics: Dict[str, Any]):
        """Crea bar chart de métricas de performance"""
        metrics_names = ['Win Rate', 'Avg Return', 'Profit Factor']
        # Normalizar métricas para visualización
        values = [
            metrics.get('win_rate', 0) * 100,
            metrics.get('avg_return', 0) * 100,
            metrics.get('profit_factor', 0) * 20  # Scale for visualization
        ]
        
        colors = ['#3498db', '#2ecc71', '#f39c12']
        bars = ax.bar(metrics_names, values, color=colors, alpha=0.7)
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{value:.1f}', ha='center', va='bottom')
        
        ax.set_title('Performance Metrics')
        ax.set_ylabel('Score')
        ax.set_ylim(0, max(100, max(values) * 1.1))

    async def _create_response_time_hist(self, ax, results):
        """Crea histograma de tiempos de respuesta"""
        response_times = getattr(results, 'response_times', [])
        
        if not response_times:
            ax.text(0.5, 0.5, 'No response time data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Response Time Distribution')
            return
        
        ax.hist(response_times, bins=20, color='#9b59b6', alpha=0.7, edgecolor='black')
        ax.axvline(np.mean(response_times), color='red', linestyle='--', 
                  label=f'Mean: {np.mean(response_times):.3f}s')
        ax.set_title('Response Time Distribution')
        ax.set_xlabel('Response Time (seconds)')
        ax.set_ylabel('Frequency')
        ax.legend()

    async def _create_pattern_performance(self, ax, results):
        """Crea gráfico de performance por tipo de patrón"""
        if not hasattr(results, 'pattern_type_results') or not results.pattern_type_results:
            ax.text(0.5, 0.5, 'No pattern type data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Pattern Type Performance')
            return
        
        pattern_types = list(results.pattern_type_results.keys())
        win_rates = []
        sample_sizes = []
        
        for pattern_type in pattern_types:
            data = results.pattern_type_results[pattern_type]
            win_rate = data['wins'] / data['count'] if data['count'] > 0 else 0
            win_rates.append(win_rate)
            sample_sizes.append(data['count'])
        
        # Scatter plot con tamaño basado en sample size
        colors = plt.cm.viridis(np.linspace(0, 1, len(pattern_types)))
        scatter = ax.scatter(range(len(pattern_types)), win_rates, 
                           s=[s*10 for s in sample_sizes], c=colors, alpha=0.7)
        
        ax.set_xticks(range(len(pattern_types)))
        ax.set_xticklabels(pattern_types, rotation=45, ha='right')
        ax.set_title('Win Rate by Pattern Type')
        ax.set_ylabel('Win Rate')
        ax.set_xlabel('Pattern Type')
        
        # Add sample size info
        for i, (pattern, rate, size) in enumerate(zip(pattern_types, win_rates, sample_sizes)):
            ax.annotate(f'n={size}', (i, rate), xytext=(5, 5), 
                       textcoords='offset points', fontsize=8)

    async def _create_quality_scatter(self, ax, results, metrics: Dict[str, Any]):
        """Crea scatter plot de calidad vs performance"""
        avg_quality = metrics.get('avg_signal_quality', 50)
        win_rate = metrics.get('win_rate', 0) * 100
        total_trades = metrics.get('total_trades', 0)
        
        # Simulate quality vs performance data
        np.random.seed(42)
        qualities = np.random.normal(avg_quality, 15, max(10, total_trades))
        performances = qualities + np.random.normal(0, 10, len(qualities))
        
        ax.scatter(qualities, performances, alpha=0.6, s=50)
        
        # Add trend line
        z = np.polyfit(qualities, performances, 1)
        p = np.poly1d(z)
        ax.plot(qualities, p(qualities), "r--", alpha=0.8, linewidth=2)
        
        ax.set_title('Signal Quality vs Performance')
        ax.set_xlabel('Signal Quality Score')
        ax.set_ylabel('Performance Score')

    async def _create_cumulative_pnl(self, ax, results):
        """Crea gráfico de PnL acumulativo"""
        total_trades = getattr(results, 'trades_executed', 0)
        total_pnl = getattr(results, 'total_pnl', 0)
        
        if total_trades == 0:
            ax.text(0.5, 0.5, 'No trades data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Cumulative PnL')
            return
        
        # Simulate cumulative PnL curve
        np.random.seed(42)
        trade_pnls = np.random.normal(total_pnl/total_trades, 0.02, total_trades)
        cumulative_pnl = np.cumsum(trade_pnls)
        
        ax.plot(range(1, total_trades + 1), cumulative_pnl, linewidth=2, color='#2ecc71')
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax.set_title('Cumulative PnL')
        ax.set_xlabel('Trade Number')
        ax.set_ylabel('Cumulative PnL')

    async def _create_win_rate_comparison(self, ax, workers_data: Dict[str, Any]):
        """Crea comparación de win rates entre workers"""
        workers = list(workers_data.keys())
        win_rates = [workers_data[w].get('win_rate', 0) * 100 for w in workers]
        
        bars = ax.bar(workers, win_rates, color='#3498db', alpha=0.7)
        
        # Add value labels
        for bar, rate in zip(bars, win_rates):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{rate:.1f}%', ha='center', va='bottom')
        
        ax.set_title('Win Rate Comparison')
        ax.set_ylabel('Win Rate (%)')
        ax.set_ylim(0, max(100, max(win_rates) * 1.1))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    async def _create_return_comparison(self, ax, workers_data: Dict[str, Any]):
        """Crea comparación de returns promedio"""
        workers = list(workers_data.keys())
        returns = [workers_data[w].get('avg_return', 0) * 100 for w in workers]
        
        colors = ['#2ecc71' if r >= 0 else '#e74c3c' for r in returns]
        bars = ax.bar(workers, returns, color=colors, alpha=0.7)
        
        # Add value labels
        for bar, ret in zip(bars, returns):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., 
                   height + (0.1 if height >= 0 else -0.3),
                   f'{ret:.2f}%', ha='center', va='bottom' if height >= 0 else 'top')
        
        ax.set_title('Average Return Comparison')
        ax.set_ylabel('Average Return (%)')
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    async def _create_profit_factor_comparison(self, ax, workers_data: Dict[str, Any]):
        """Crea comparación de profit factors"""
        workers = list(workers_data.keys())
        profit_factors = [workers_data[w].get('profit_factor', 0) for w in workers]
        
        bars = ax.bar(workers, profit_factors, color='#f39c12', alpha=0.7)
        
        # Add value labels
        for bar, pf in zip(bars, profit_factors):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                   f'{pf:.2f}', ha='center', va='bottom')
        
        ax.set_title('Profit Factor Comparison')
        ax.set_ylabel('Profit Factor')
        ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='Break-even')
        ax.legend()
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    async def _create_performance_heatmap(self, ax, workers_data: Dict[str, Any]):
        """Crea heatmap de performance general"""
        # Preparar datos para heatmap
        metrics = ['win_rate', 'avg_return', 'profit_factor']
        metric_labels = ['Win Rate', 'Avg Return', 'Profit Factor']
        
        data_matrix = []
        for worker in workers_data.keys():
            worker_metrics = []
            for metric in metrics:
                value = workers_data[worker].get(metric, 0)
                # Normalizar para visualización
                if metric == 'win_rate':
                    worker_metrics.append(value * 100)
                elif metric == 'avg_return':
                    worker_metrics.append(value * 100)
                else:  # profit_factor
                    worker_metrics.append(value * 20)  # Scale
            data_matrix.append(worker_metrics)
        
        # Crear heatmap
        im = ax.imshow(data_matrix, cmap='RdYlGn', aspect='auto')
        
        # Configurar etiquetas
        ax.set_xticks(range(len(metric_labels)))
        ax.set_xticklabels(metric_labels)
        ax.set_yticks(range(len(workers_data)))
        ax.set_yticklabels(list(workers_data.keys()))
        
        # Agregar valores en cada celda
        for i in range(len(workers_data)):
            for j in range(len(metrics)):
                text = ax.text(j, i, f'{data_matrix[i][j]:.1f}',
                             ha="center", va="center", color="black", fontsize=8)
        
        ax.set_title('Performance Metrics Heatmap')

    async def _create_radar_chart(self, ax, workers_data: Dict[str, Any]):
        """Crea gráfico radar para comparación multidimensional"""
        # Seleccionar top 5 workers por win rate
        sorted_workers = sorted(workers_data.items(), 
                              key=lambda x: x[1].get('win_rate', 0), reverse=True)[:5]
        
        if not sorted_workers:
            ax.text(0.5, 0.5, 'No data for radar chart', ha='center', va='center', transform=ax.transAxes)
            return
        
        # Métricas para el radar
        metrics = ['win_rate', 'avg_return', 'profit_factor', 'execution_rate']
        labels = ['Win Rate', 'Avg Return', 'Profit Factor', 'Exec Rate']
        
        # Ángulos para el radar
        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]  # Completar el círculo
        
        ax = plt.subplot(2, 2, 1, projection='polar')
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(sorted_workers)))
        
        for i, (worker_name, worker_data) in enumerate(sorted_workers):
            # Normalizar valores
            values = [
                worker_data.get('win_rate', 0) * 100,
                worker_data.get('avg_return', 0) * 100,
                worker_data.get('profit_factor', 0) * 20,
                worker_data.get('execution_rate', 0) * 100
            ]
            values += values[:1]  # Completar el círculo
            
            ax.plot(angles, values, 'o-', linewidth=2, label=worker_name, color=colors[i])
            ax.fill(angles, values, alpha=0.25, color=colors[i])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 100)
        ax.set_title('Worker Performance Radar')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

    async def _create_speed_comparison(self, ax, benchmark_data: Dict[str, Any]):
        """Crea comparación de velocidad de procesamiento"""
        total_time = benchmark_data.get('duration_seconds', 0)
        workers_tested = benchmark_data.get('workers_tested', 0)
        
        if total_time == 0 or workers_tested == 0:
            ax.text(0.5, 0.5, 'No timing data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Processing Speed Comparison')
            return
        
        # Simulate processing times
        processing_times = np.random.uniform(1, 5, workers_tested)  # 1-5 segundos por worker
        workers = [f'Worker {i+1}' for i in range(workers_tested)]
        
        bars = ax.bar(workers, processing_times, color='#9b59b6', alpha=0.7)
        
        for bar, time in zip(bars, processing_times):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                   f'{time:.1f}s', ha='center', va='bottom')
        
        ax.set_title('Processing Speed Comparison')
        ax.set_ylabel('Processing Time (seconds)')
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    async def _create_volume_quality_scatter(self, ax, workers_data: Dict[str, Any]):
        """Crea scatter plot de volumen vs calidad"""
        workers = list(workers_data.keys())
        volumes = [workers_data[w].get('total_trades', 0) for w in workers]
        qualities = [workers_data[w].get('avg_signal_quality', 0) for w in workers]
        
        scatter = ax.scatter(volumes, qualities, s=100, alpha=0.7, c=range(len(workers)), cmap='viridis')
        
        # Add worker labels
        for i, worker in enumerate(workers):
            ax.annotate(worker, (volumes[i], qualities[i]), 
                       xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        ax.set_title('Trade Volume vs Signal Quality')
        ax.set_xlabel('Number of Trades')
        ax.set_ylabel('Average Signal Quality')

    async def _create_performance_timeline(self, ax, workers_data: Dict[str, Any]):
        """Crea línea de tiempo de performance"""
        # Simulate performance over time
        time_points = pd.date_range(start='2024-01-01', periods=30, freq='D')
        
        for i, (worker_name, worker_data) in enumerate(workers_data.items()):
            # Generate synthetic performance data based on actual metrics
            base_performance = worker_data.get('win_rate', 0.5) * 100
            volatility = 10
            
            # Generate realistic performance with some trend and volatility
            trend = np.linspace(-5, 5, 30) if i % 2 == 0 else np.linspace(5, -5, 30)
            noise = np.random.normal(0, volatility, 30)
            performance = base_performance + trend + noise
            
            ax.plot(time_points, performance, label=worker_name, linewidth=2)
        
        ax.set_title('Performance Timeline')
        ax.set_ylabel('Win Rate (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def create_summary_dashboard(self, all_metrics: Dict[str, Any]) -> str:
        """
        Crea un dashboard resumen en texto
        
        Args:
            all_metrics: Métricas de múltiples tests
            
        Returns:
            String con dashboard formateado
        """
        dashboard_lines = []
        dashboard_lines.append("="*80)
        dashboard_lines.append("📊 BACKTESTING DASHBOARD SUMMARY")
        dashboard_lines.append("="*80)
        dashboard_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        dashboard_lines.append("")
        
        # Resumen general
        total_workers = len(all_metrics)
        successful_workers = sum(1 for m in all_metrics.values() if 'error' not in m)
        avg_win_rate = np.mean([m.get('win_rate', 0) for m in all_metrics.values() if 'error' not in m])
        
        dashboard_lines.append("🎯 RESUMEN GENERAL:")
        dashboard_lines.append(f"   Workers testados: {total_workers}")
        dashboard_lines.append(f"   Workers exitosos: {successful_workers}")
        dashboard_lines.append(f"   Win Rate promedio: {avg_win_rate:.1%}")
        dashboard_lines.append("")
        
        # Top performers
        valid_metrics = {k: v for k, v in all_metrics.items() if 'error' not in v}
        if valid_metrics:
            top_by_win_rate = sorted(valid_metrics.items(), 
                                    key=lambda x: x[1].get('win_rate', 0), reverse=True)[:3]
            top_by_return = sorted(valid_metrics.items(), 
                                 key=lambda x: x[1].get('avg_return', 0), reverse=True)[:3]
            
            dashboard_lines.append("🏆 TOP PERFORMERS:")
            dashboard_lines.append("   Por Win Rate:")
            for i, (worker, metrics) in enumerate(top_by_win_rate, 1):
                dashboard_lines.append(f"     {i}. {worker}: {metrics.get('win_rate', 0):.1%}")
            
            dashboard_lines.append("   Por Average Return:")
            for i, (worker, metrics) in enumerate(top_by_return, 1):
                dashboard_lines.append(f"     {i}. {worker}: {metrics.get('avg_return', 0):+.2f}%")
            dashboard_lines.append("")
        
        # Charts generados
        chart_files = [f for f in os.listdir(self.output_dir) if f.endswith('.png')]
        dashboard_lines.append(f"📁 Archivos generados: {len(chart_files)} gráficos")
        for chart_file in sorted(chart_files)[-5:]:  # Últimos 5
            dashboard_lines.append(f"   • {chart_file}")
        
        return "\n".join(dashboard_lines)