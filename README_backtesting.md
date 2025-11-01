# Sistema de Backtesting Intraday para Workers

Un framework comprehensivo para probar y evaluar workers de trading de manera fácil y eficiente.

## 🎯 Características Principales

- **Generación automática de patrones sintéticos** - Crea datos realistas que simulan oportunidades del scanner
- **Testing de múltiples workers en paralelo** - Compara performance entre diferentes workers
- **Métricas detalladas de performance** - Win rate, profit factor, Sharpe ratio, etc.
- **Visualizaciones automáticas** - Gráficos y charts para análisis visual
- **Configuración flexible** - Personalizable por tipo de worker y estrategia
- **Benchmark integrado** - Comparación con estándares de la industria

## 🚀 Uso Rápido

### Instalación de Dependencias

```bash
# Dependencias básicas
pip install numpy pandas matplotlib seaborn

# Para el sistema completo (opcional)
pip install asyncio-logging
```

### Ejemplo Básico

```python
import asyncio
from run_backtest_intraday import BacktestRunner

async def ejemplo_basico():
    # Crear runner
    runner = BacktestRunner()
    
    # Probar un worker específico
    metrics = await runner.run_single_worker_test(
        worker_name="macdv",
        num_patterns=50,
        visualize=True
    )
    
    print(f"Win Rate: {metrics.get('win_rate', 0):.1%}")

# Ejecutar
asyncio.run(ejemplo_basico())
```

### Uso desde Línea de Comandos

```bash
# Probar un worker específico
python run_backtest_intraday.py --worker macdv --patterns 100 --visualize

# Comparar múltiples workers
python run_backtest_intraday.py --workers macdv,daily_plays,bull_flag --patterns 50

# Benchmark completo
python run_backtest_intraday.py --benchmark --all-workers --patterns 75

# Listar workers disponibles
python run_backtest_intraday.py --list-workers
```

## 📊 Tipos de Testing

### 1. Test Individual de Worker
```python
# Test detallado de un worker
metrics = await runner.run_single_worker_test(
    worker_name="bull_flag",
    num_patterns=100,
    visualize=True,
    detailed=True
)
```

### 2. Comparación Multi-Worker
```python
# Comparar performance entre workers
results = await runner.run_multi_worker_comparison(
    worker_names=["macdv", "daily_plays", "vwap_breakout"],
    num_patterns=100,
    visualize=True
)
```

### 3. Benchmark Completo
```python
# Benchmark de todos los workers disponibles
benchmark_report = await runner.run_benchmark(
    worker_names=None,  # Todos los disponibles
    num_patterns=100
)
```

## 🔧 Configuración de Workers

### Workers Soportados

| Worker | Descripción | Patrones Sugeridos | Win Rate Típico |
|--------|-------------|-------------------|-----------------|
| `macdv` | MACD Divergence Strategy | 100 | 65% |
| `daily_plays` | Daily Catalyst Plays | 150 | 70% |
| `vwap` | VWAP Strategy | 120 | 68% |
| `momentum_breakout` | Momentum Breakout Strategy | 100 | 63% |
| `vcp_smallcap` | VCP Smallcap Strategy | 80 | 60% |
| `volume_absorption` | Volume Absorption Strategy | 90 | 62% |
| `generic_01` | Generic Worker Strategy | 50 | 50% |

### Workers Mock (Sin Dependencias)

Si no tienes las dependencias completas del sistema, puedes usar workers mock:

```python
# Lista automáticamente workers disponibles
runner = BacktestRunner()
runner.list_available_workers()

# Los workers mock simulan comportamiento realista
```

## 📈 Métricas Calculadas

### Métricas Financieras
- **Win Rate**: Porcentaje de trades ganadores
- **Average Return**: Retorno promedio por trade
- **Profit Factor**: Ratio ganancia/pérdida
- **Sharpe Ratio**: Retorno ajustado por riesgo
- **Maximum Drawdown**: Pérdida máxima

### Métricas de Calidad
- **Signal Quality**: Calidad promedio de señales
- **Execution Rate**: Porcentaje de oportunidades ejecutadas
- **Pattern Recognition**: Performance por tipo de patrón

### Métricas de Eficiencia
- **Response Time**: Tiempo de respuesta del worker
- **Processing Speed**: Trades procesados por segundo
- **Consistency**: Consistencia en decisiones

## 📊 Visualizaciones Generadas

### Por Worker Individual
1. **Win Rate Pie Chart** - Distribución wins/losses
2. **Performance Metrics Bar** - Métricas principales normalizadas
3. **Response Time Histogram** - Distribución de tiempos de respuesta
4. **Pattern Type Performance** - Performance por tipo de patrón
5. **Quality vs Performance Scatter** - Correlación calidad-performance
6. **Cumulative PnL** - Curva de PnL acumulativo

### Comparación Multi-Worker
1. **Win Rate Comparison** - Barras comparativas
2. **Average Return Comparison** - Retornos promedio
3. **Profit Factor Comparison** - Factores de profit
4. **Performance Heatmap** - Mapa de calor de métricas
5. **Radar Chart** - Comparación multidimensional
6. **Volume vs Quality Scatter** - Volumen vs calidad

## 🎛️ Configuración Avanzada

### Personalizar Patrones Sintéticos

```python
from tests.pattern_generator import PatternGenerator

# Crear generador personalizado
generator = PatternGenerator(seed=42)

# Generar patrones específicos
gap_go_patterns = generator.generate_patterns_by_type('gap_go', 50)
mixed_patterns = generator.generate_mixed_patterns(200)

# Personalizar parámetros
pattern = generator.generate_single_pattern('bull_flag')
```

### Configurar Métricas y Benchmarks

```python
from tests.metrics_calculator import MetricsCalculator

# Crear calculador personalizado
calculator = MetricsCalculator()

# Configurar benchmarks personalizados
calculator.benchmark_metrics['mi_worker'] = {
    'win_rate': 0.75,
    'avg_return': 0.12,
    'profit_factor': 1.5
}

# Calcular métricas específicas
metrics = calculator.calculate_all_metrics(results)
report = calculator.generate_performance_report(metrics, "MiWorker")
```

### Configurar Visualizaciones

```python
from tests.visualization_utils import VisualizationUtils

# Crear visualizador con directorio personalizado
visualizer = VisualizationUtils(output_dir="mis_graficos")

# Generar gráficos específicos
await visualizer.create_worker_analysis_charts("macdv", results, metrics)
await visualizer.create_worker_comparison_charts(comparison_metrics)

# Crear dashboard resumen
dashboard = visualizer.create_summary_dashboard(all_metrics)
print(dashboard)
```

## 🔍 Análisis Detallado

### Performance por Tipo de Patrón

El sistema analiza automáticamente la performance de cada worker por tipo de patrón:

```python
# Los resultados incluyen análisis por patrón
pattern_results = results.pattern_type_results

for pattern_type, data in pattern_results.items():
    print(f"{pattern_type}:")
    print(f"  - Win Rate: {data['wins'] / data['count']:.1%}")
    print(f"  - Samples: {data['count']}")
    print(f"  - Total PnL: {data['total_pnl']:.2f}%")
```

### Consistencia y Confiabilidad

```python
# Métricas de consistencia
consistency = metrics.get('worker_consistency', 0)
response_time = metrics.get('avg_response_time', 0)

print(f"Consistencia: {consistency:.2f}")
print(f"Tiempo respuesta: {response_time:.3f}s")
```

## 🚨 Troubleshooting

### Problemas Comunes

1. **Error de Importaciones**
   ```bash
   # Instalar dependencias
   pip install numpy pandas matplotlib seaborn
   ```

2. **Workers No Encontrados**
   ```bash
   # Usar workers mock automáticamente
   python run_backtest_intraday.py --list-workers
   ```

3. **Errores de Visualización**
   ```bash
   # Instalar backend de matplotlib
   pip install matplotlib
   ```

### Logs y Debugging

```python
import logging

# Habilitar logging detallado
logging.basicConfig(level=logging.DEBUG)

# Los logs incluyen información detallada de cada test
```

## 📝 Ejemplo Completo

```python
import asyncio
from run_backtest_intraday import BacktestRunner

async def ejemplo_completo():
    # Crear runner
    runner = BacktestRunner()
    
    # 1. Listar workers disponibles
    runner.list_available_workers()
    
    # 2. Test individual con visualización
    print("\n=== Testing MacDV Worker ===")
    macdv_metrics = await runner.run_single_worker_test(
        worker_name="macdv",
        num_patterns=100,
        visualize=True,
        detailed=True
    )
    
    # 3. Comparación multi-worker
    print("\n=== Comparing Workers ===")
    comparison_results = await runner.run_multi_worker_comparison(
        worker_names=["macdv", "daily_plays", "bull_flag"],
        num_patterns=75,
        visualize=True
    )
    
    # 4. Benchmark completo
    print("\n=== Running Benchmark ===")
    benchmark_report = await runner.run_benchmark(
        worker_names=["macdv", "daily_plays"],
        num_patterns=50
    )
    
    # 5. Mostrar resultados
    print("\n=== Results Summary ===")
    for worker, metrics in comparison_results.items():
        if 'error' not in metrics:
            print(f"{worker}: {metrics.get('win_rate', 0):.1%} win rate, "
                  f"{metrics.get('avg_return', 0):+.2f}% avg return")

if __name__ == "__main__":
    asyncio.run(ejemplo_completo())
```

## 🤝 Integración con Sistema Existente

El framework está diseñado para integrarse fácilmente con el sistema de trading existente:

```python
# Importar workers reales
from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic

# Usar el framework de testing
from tests.worker_tester import WorkerTester

# Testear workers reales
tester = WorkerTester("macdv", MacdvWorkerLogic)
results = await tester.run_comprehensive_test(patterns)
```

## 📞 Soporte

Para reportar issues o solicitar nuevas características:

1. Verificar que estás usando la versión correcta de dependencias
2. Revisar los logs para errores específicos
3. Usar workers mock si hay problemas de dependencias
4. Consultar la documentación de cada módulo específico

---

**Desarrollado para facilitar el testing y optimización de workers de trading** 🎯