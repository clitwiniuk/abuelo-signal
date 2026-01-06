# 🧪 Guía Completa de Tests - Optimización News Aging

## 🎯 Tests Creados para Validar la Implementación

He creado una suite completa de tests para validar todas las mejoras implementadas en la optimización de news aging para smallcaps intraday:

### 📁 Estructura de Tests Creada

```
tests/news_aging_optimization/
├── README.md                           # Documentación completa
├── TESTING_GUIDE.md                    # Esta guía
├── run_all_tests.py                    # ✅ Ejecutor principal (executable)
├── test_catalyst_analyzer_aging.py     # ✅ Test 1: Aging diferenciado
├── test_smallcap_scanner_filters.py    # ✅ Test 2: Filtros optimizados  
├── test_time_decay_multipliers.py      # ✅ Test 3: Multipliers agresivos
├── test_session_based_filtering.py     # ✅ Test 4: Filtrado por horario
├── test_end_to_end_integration.py      # ✅ Test 5: Integración completa
└── test_data/
    └── catalyst_examples.json          # ✅ Datos de prueba
```

## 🚀 Cómo Ejecutar los Tests

### Opción 1: Ejecutar Todos los Tests (Recomendado)
```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python tests/news_aging_optimization/run_all_tests.py
```

### Opción 2: Ejecutar Tests Individuales
```bash
# Test 1: CatalystAnalyzer aging diferenciado
python -m pytest tests/news_aging_optimization/test_catalyst_analyzer_aging.py -v

# Test 2: SmallcapDailyScanner filtros optimizados  
python -m pytest tests/news_aging_optimization/test_smallcap_scanner_filters.py -v

# Test 3: Time decay multipliers agresivos
python -m pytest tests/news_aging_optimization/test_time_decay_multipliers.py -v

# Test 4: Filtrado inteligente por horario
python -m pytest tests/news_aging_optimization/test_session_based_filtering.py -v

# Test 5: Integración end-to-end completa
python -m pytest tests/news_aging_optimization/test_end_to_end_integration.py -v
```

### Opción 3: Ejecutar con Coverage
```bash
python -m pytest tests/news_aging_optimization/ --cov=scanner.smallcap --cov-report=html -v
```

## 🔍 Qué Valida Cada Test

### Test 1: `test_catalyst_analyzer_aging.py`
**Valida CatalystAnalyzer con aging diferenciado por tipo:**
- ✅ Límites específicos por catalyst type (FDA: 4h, M&A: 6h, EARNINGS: 8h, etc.)
- ✅ Multipliers de time decay agresivos (fresh: 1.0, recent: 0.8, stale: 0.5, expired: 0.0)
- ✅ Detección automática de session (premarket vs market hours)
- ✅ Filtrado inteligente basado en viabilidad intraday
- ✅ Manejo de negative keywords que reducen strength

### Test 2: `test_smallcap_scanner_filters.py`
**Valida SmallcapDailyScanner con filtros optimizados:**
- ✅ Reducción de max_news_age_hours: 48h → 8h (83% reducción)
- ✅ Aumento de min_catalyst_strength: 1 → 5 (5x más selectivo)
- ✅ Filtrado específico por catalyst type vs límite global
- ✅ Integración correcta con CatalystAnalyzer optimizado
- ✅ Comparación performance legacy vs optimized

### Test 3: `test_time_decay_multipliers.py`
**Valida system de time decay agresivo:**
- ✅ Fresh news (0-2h): 100% strength preservation
- ✅ Recent news (2-6h): 80% strength reduction
- ✅ Stale news (6-12h): 50% strength reduction  
- ✅ Expired news (12h+): 0% strength (rechazo completo)
- ✅ Transiciones suaves entre categorías
- ✅ Edge cases y boundary values

### Test 4: `test_session_based_filtering.py`
**Valida filtrado inteligente por horario:**
- ✅ Premarket (4:00-9:30 AM): Permite noticias overnight hasta 16h
- ✅ Market Hours (9:30-16:00): Límites estrictos por catalyst type
- ✅ Detección automática de session
- ✅ Transiciones suaves entre sessions
- ✅ Scenarios de overnight news realistas

### Test 5: `test_end_to_end_integration.py`
**Valida integración completa del sistema:**
- ✅ Flujo completo: IBKR Scanner → Catalyst Analysis → Filtering → Quality Scoring
- ✅ Métricas de performance: precision, recall, noise reduction
- ✅ Comparación ANTES vs DESPUÉS de optimización
- ✅ Casos de uso realistas con datos de mercado simulados
- ✅ Stress test con datasets grandes (50+ symbols)

## 📊 Métricas de Éxito Esperadas

### Performance Targets
- **Precision**: >80% de plays seleccionados son high quality (strength ≥6, quality ≥7)
- **Selectivity**: ≤60% de symbols pasan filtering (alta selectividad)
- **Noise Reduction**: ≥50% menos plays vs configuración legacy
- **Average Quality**: ≥6.0 quality score promedio
- **Average Strength**: ≥5.0 catalyst strength promedio
- **Freshness Rate**: ≥50% de plays con noticias ≤2h

### Technical Validation
- ✅ **FDA news >4h**: Rechazado en market hours, permitido en premarket
- ✅ **M&A news >6h**: Rechazado en market hours, permitido en premarket
- ✅ **EARNINGS news ≤8h**: Aceptado en market hours
- ✅ **CONTRACT news ≤12h**: Aceptado en market hours
- ✅ **Time decay**: Fresh=100%, Recent=80%, Stale=50%, Expired=0%

## 🔧 Troubleshooting

### Error: ModuleNotFoundError
```bash
# Asegurar que estás en el directorio correcto
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Verificar PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

### Error: Import Issues
```bash
# Instalar dependencias si es necesario
pip install pytest pytest-asyncio pytest-cov
```

### Tests Lentos
```bash
# Ejecutar solo tests críticos
python -m pytest tests/news_aging_optimization/test_catalyst_analyzer_aging.py tests/news_aging_optimization/test_time_decay_multipliers.py -v
```

## 📈 Interpretación de Resultados

### ✅ Todos los Tests Pasan
- **Excelente**: La implementación está funcionando correctamente
- **Acción**: Deploy a producción, monitoring continuo

### ⚠️ Algunos Tests Fallan
- **Revisar**: Logs detallados de tests fallidos
- **Acción**: Corregir implementación, re-ejecutar tests

### ❌ Múltiples Tests Fallan
- **Crítico**: Problema en implementación base
- **Acción**: Revisar configuración, debug código core

## 🚨 Tests Críticos (No Pueden Fallar)

1. **test_catalyst_type_specific_aging_limits**: Validación core del aging diferenciado
2. **test_time_decay_multiplier_precision**: Precisión de multipliers
3. **test_end_to_end_workflow_legacy_vs_optimized**: Comparación de performance
4. **test_performance_metrics_validation**: Targets de performance

## 💾 Resultados y Reporting

Los tests generan:
- **Stdout**: Resultados detallados en tiempo real
- **JSON Report**: `test_results_YYYYMMDD_HHMMSS.json` con métricas completas
- **Coverage Report**: HTML coverage report (si se ejecuta con --cov)

## 🔄 Integración Continua

Recomendado ejecutar estos tests:
- **Pre-commit**: Tests críticos (1, 3)
- **Daily**: Suite completa
- **Pre-deployment**: Suite completa + stress tests
- **Post-deployment**: Subset de validación

---

**Creado**: 2025-01-21  
**Versión**: 1.0.0  
**Autor**: Trading System v3 - News Aging Optimization