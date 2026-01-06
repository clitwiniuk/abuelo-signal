# Circuit Breaker Implementation - News Fetching Resilience

## Overview

Implementación del patrón **Circuit Breaker** para mejorar la resiliencia del sistema de noticias multi-fuente, eliminando el problema crítico de cascading failures cuando Finviz u otras fuentes fallan.

## Problema Resuelto

### Antes (Sin Circuit Breaker)
```
Finviz falla → 200 símbolos × 10s timeout = 2000s (33+ minutos) bloqueados
                ↓
         Scan completamente inútil
         Sistema paralizado esperando timeouts
         No hay fallback efectivo
```

### Después (Con Circuit Breaker)
```
Finviz falla 5 veces → Circuit ABRE → Finviz skipped
                          ↓
                   Fallback automático: Finnhub + Yahoo
                   200 símbolos × 2s = 400s (6-7 minutos)
                   Sistema operativo con fuentes secundarias
                          ↓
                   Después de 5 minutos → Circuit intenta recuperación
```

## Arquitectura

### 1. Clase NewsCircuitBreaker

Ubicación: [multi_source_news.py:92-185](../scanner/smallcap/multi_source_news.py#L92-L185)

```python
class NewsCircuitBreaker:
    """
    Estados del Circuit Breaker:
    - CLOSED: Operación normal, todas las llamadas permitidas
    - OPEN: Fallo detectado, llamadas bloqueadas
    - HALF-OPEN: Timeout expiró, intentando recuperación
    """

    def __init__(self, source_name, failure_threshold=5, timeout_seconds=300):
        self.failure_threshold = 5      # 5 fallos consecutivos → OPEN
        self.timeout_seconds = 300      # 5 minutos de espera
        self.consecutive_failures = 0
        self.is_open = False
```

### 2. Integración en MultiSourceNewsChecker

Cada fuente de noticias tiene su propio circuit breaker:

```python
self.circuit_breakers = {
    'finviz': NewsCircuitBreaker('Finviz', failure_threshold=5, timeout_seconds=300),
    'finnhub': NewsCircuitBreaker('Finnhub', failure_threshold=5, timeout_seconds=300),
    'yahoo': NewsCircuitBreaker('Yahoo', failure_threshold=5, timeout_seconds=300),
    'polygon': NewsCircuitBreaker('Polygon', failure_threshold=5, timeout_seconds=300),
    'newsapi': NewsCircuitBreaker('NewsAPI', failure_threshold=5, timeout_seconds=300),
}
```

## Flujo de Ejecución

### Caso 1: Fuente Saludable
```
Symbol: AAPL
    ↓
circuit_breakers['finviz'].should_attempt_call() → True
    ↓
_check_finviz('AAPL') → Success (3 headlines)
    ↓
circuit_breakers['finviz'].record_success()
    ↓
consecutive_failures = 0 (reset)
```

### Caso 2: Fuente Fallando (< Threshold)
```
Symbol: TSLA
    ↓
circuit_breakers['finviz'].should_attempt_call() → True
    ↓
_check_finviz('TSLA') → Timeout Error
    ↓
circuit_breakers['finviz'].record_failure()
    ↓
consecutive_failures = 1 (< 5)
circuit still CLOSED
```

### Caso 3: Circuit Opening (≥ Threshold)
```
Symbol: NVDA (5th consecutive failure)
    ↓
circuit_breakers['finviz'].should_attempt_call() → True
    ↓
_check_finviz('NVDA') → Timeout Error
    ↓
circuit_breakers['finviz'].record_failure()
    ↓
consecutive_failures = 5 (== threshold)
    ↓
⚠️ Circuit OPENS
    ↓
Logger: "🔴 Finviz Circuit OPENED - 5 consecutive failures. Will retry in 300s"
```

### Caso 4: Fuente Skipped (Circuit Open)
```
Symbol: META (circuit already open)
    ↓
circuit_breakers['finviz'].should_attempt_call() → False
    ↓
⚡ Skip Finviz, usar fallbacks
    ↓
_check_finnhub('META') → 2 headlines
_check_yahoo('META') → 3 headlines
    ↓
✓ Resultado: 5 headlines (sin Finviz)
Sin timeout, sin bloqueo
```

### Caso 5: Recuperación Automática
```
300 segundos después...
    ↓
Symbol: AMD
    ↓
circuit_breakers['finviz'].should_attempt_call() → True (timeout expiró)
    ↓
Logger: "🔄 Finviz Circuit half-open - attempting retry after 300s"
    ↓
_check_finviz('AMD') → Success (4 headlines)
    ↓
circuit_breakers['finviz'].record_success()
    ↓
✅ Circuit CLOSES
Logger: "✅ Finviz Circuit CLOSED - Service recovered"
```

## Código Implementado

### Verificación de Circuit Antes de Llamada

[multi_source_news.py:392-401](../scanner/smallcap/multi_source_news.py#L392-L401)

```python
# En _check_all_sources_for_symbol()
if FINVIZ_AVAILABLE:
    if self.circuit_breakers['finviz'].should_attempt_call():
        tasks.append(('finviz', self._check_finviz(symbol)))
    else:
        skipped_sources.append('finviz')
        source_results['finviz'] = {
            'headlines': [],
            'error': 'Circuit breaker OPEN - source temporarily disabled',
            'circuit_open': True
        }
```

### Registro de Éxitos/Fallos

[multi_source_news.py:458-505](../scanner/smallcap/multi_source_news.py#L458-L505)

```python
# Procesamiento de resultados
for i, (source_name, _) in enumerate(tasks):
    if isinstance(results[i], Exception):
        # Error de conexión/timeout
        failed_sources.append(source_name)
        if source_name in self.circuit_breakers:
            self.circuit_breakers[source_name].record_failure()
    else:
        result = results[i]
        if result.get('headlines'):
            # Éxito con headlines
            successful_sources.append(source_name)
            if source_name in self.circuit_breakers:
                self.circuit_breakers[source_name].record_success()
        elif result.get('error'):
            # Error retornado (no exception)
            failed_sources.append(source_name)
            if source_name in self.circuit_breakers:
                self.circuit_breakers[source_name].record_failure()
```

### Protección Especial para Yahoo

Yahoo es la fuente crítica de fallback, por lo que tiene protección especial:

```python
# Yahoo always runs (critical fallback)
if self.circuit_breakers['yahoo'].should_attempt_call():
    tasks.append(('yahoo', self._check_yahoo(symbol)))
else:
    # Yahoo is critical - log warning but still attempt
    self.logger.warning("Yahoo circuit open but attempting anyway (critical fallback)")
    tasks.append(('yahoo', self._check_yahoo(symbol)))
```

## Métricas y Monitorización

### Obtener Estadísticas

```python
# En código
stats = news_checker.get_circuit_breaker_stats()

# Output:
{
    'finviz': {
        'source': 'Finviz',
        'is_open': True,
        'consecutive_failures': 5,
        'total_failures': 12,
        'total_successes': 45,
        'success_rate': '78.9%',
        'time_since_open': 145.2  # segundos
    },
    'yahoo': {
        'source': 'Yahoo',
        'is_open': False,
        'consecutive_failures': 0,
        'total_failures': 2,
        'total_successes': 55,
        'success_rate': '96.5%',
        'time_since_open': None
    }
}
```

### Reporte Formateado

```python
news_checker.print_circuit_breaker_report()
```

Output:
```
============================================================
CIRCUIT BREAKER STATUS REPORT
============================================================
🔴 FINVIZ
   Status: OPEN
   Success Rate: 78.9%
   Total Calls: 57
   Failures: 12 (consecutive: 5)
   Open for: 145s
------------------------------------------------------------
✅ YAHOO
   Status: CLOSED
   Success Rate: 96.5%
   Total Calls: 57
   Failures: 2 (consecutive: 0)
------------------------------------------------------------
```

## Testing

### Script de Prueba

Ubicación: [tests/test_circuit_breaker.py](../tests/test_circuit_breaker.py)

```bash
# Ejecutar tests
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python tests/test_circuit_breaker.py
```

### Tests Incluidos

1. **test_circuit_breaker_basic()**: Prueba funcionalidad básica
2. **test_multi_source_with_circuit_breaker()**: Integración con news checker
3. **test_circuit_breaker_under_load()**: Comportamiento bajo carga

## Configuración

### Parámetros Ajustables

```python
# En MultiSourceNewsChecker.__init__()
self.circuit_breakers = {
    'finviz': NewsCircuitBreaker(
        'Finviz',
        failure_threshold=5,    # Cambiar para más/menos tolerancia
        timeout_seconds=300     # Cambiar tiempo de espera antes de retry
    ),
    # ...
}
```

### Valores Recomendados por Entorno

**Producción** (conservador):
```python
failure_threshold=3    # Abre rápido ante fallos
timeout_seconds=600    # 10 minutos de cooldown
```

**Testing** (permisivo):
```python
failure_threshold=10   # Más tolerante a fallos transitorios
timeout_seconds=60     # 1 minuto de cooldown
```

**Development**:
```python
failure_threshold=5    # Balance
timeout_seconds=300    # 5 minutos
```

## Beneficios Medibles

### Performance

| Escenario | Sin Circuit Breaker | Con Circuit Breaker | Mejora |
|-----------|---------------------|---------------------|--------|
| Finviz OK | 200 símbolos × 2s = 400s | 200 símbolos × 2s = 400s | 0% |
| Finviz timeout (10s) | 200 × 10s = 2000s (33min) | 5 × 10s + 195 × 2s = 440s (7min) | **78% faster** |
| Finviz down (completo) | 200 × 10s = 2000s (33min) | 5 × 10s + 195 × 2s = 440s (7min) | **78% faster** |

### Reliability

- **Graceful degradation**: Sistema sigue funcionando con fuentes secundarias
- **Auto-recovery**: Intenta recuperación automática cada 5 minutos
- **No cascading failures**: Un fallo no paraliza todo el sistema

### Observability

- **Stats tracking**: Success rate, failure count por fuente
- **Logging detallado**: Estado del circuit breaker en tiempo real
- **Alertas proactivas**: Logs cuando circuit abre/cierra

## Logs Típicos

### Operación Normal
```
INFO - MultiSourceNewsChecker initialized with sources: ['finviz', 'finnhub', 'yahoo']
INFO - Circuit breakers enabled for all sources
INFO - News sources successful for AAPL: finviz(3), yahoo(2)
```

### Circuit Opening
```
WARNING - 🔴 Finviz Circuit OPENED - 5 consecutive failures. Will retry in 300s
INFO - ⚡ Circuit breakers OPEN for TSLA: finviz
INFO - News sources successful for TSLA: yahoo(3), finnhub(2)
INFO - News sources failed for TSLA: finviz - using fallback sources
```

### Circuit Recovery
```
INFO - 🔄 Finviz Circuit half-open - attempting retry after 300s
INFO - ✅ Finviz Circuit CLOSED - Service recovered
INFO - News sources successful for NVDA: finviz(4), yahoo(2)
```

## Próximos Pasos (Opcional)

### Posibles Mejoras Futuras

1. **Exponential Backoff**: Incrementar timeout después de múltiples re-aperturas
2. **Adaptive Thresholds**: Ajustar threshold basado en success rate histórico
3. **Alertas Telegram**: Notificar cuando circuit abre (crítico para producción)
4. **Persistence**: Guardar estado del circuit breaker en DB entre reinicios
5. **Dashboard**: Visualización de métricas en tiempo real

### Monitorización Recomendada

```python
# Agregar a scanner_main.py (cada hora)
if hour % 1 == 0:  # Cada hora
    stats = proactive_scanner.news_checker.get_circuit_breaker_stats()

    for source, data in stats.items():
        if data['is_open']:
            logger.warning(f"⚠️ {source} circuit still OPEN after {data['time_since_open']}s")

        if data['success_rate'] < 80.0:
            logger.warning(f"⚠️ {source} success rate low: {data['success_rate']}")
```

## Conclusión

La implementación del Circuit Breaker elimina el problema crítico de **cascading failures** en el sistema de noticias, reduciendo el tiempo de scan de 33+ minutos a 6-7 minutos en el peor caso, mientras mantiene la disponibilidad del sistema mediante fallbacks inteligentes.

**Estado**: ✅ IMPLEMENTADO Y LISTO PARA USO

**Testing**: ⚠️ Ejecutar [tests/test_circuit_breaker.py](../tests/test_circuit_breaker.py) antes de despliegue

**Mantenimiento**: Revisar logs periódicamente para ajustar thresholds si es necesario
