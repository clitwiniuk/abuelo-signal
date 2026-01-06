# Tests para Optimización News Aging Smallcaps Intraday

Este directorio contiene tests completos para validar la implementación de optimización de filtrado de noticias para smallcaps intraday.

## 🎯 Características Implementadas a Testear

### 1. CatalystAnalyzer - Aging Diferenciado
- ✅ Límites específicos por tipo de catalyst (FDA: 4h, M&A: 6h, EARNINGS: 8h, etc.)
- ✅ Multipliers de time decay agresivos (fresh: 1.0, recent: 0.8, stale: 0.5, expired: 0.0)
- ✅ Detección automática de session (premarket vs market hours)

### 2. SmallcapDailyScanner - Filtros Optimizados
- ✅ max_news_age_hours: 48h → 8h (reducción del 83%)
- ✅ min_catalyst_strength: 1 → 5 (5x más selectivo)
- ✅ max_news_age_premarket: 16h para overnight news
- ✅ Filtrado específico por catalyst type

### 3. Time Decay System
- ✅ Fresh news (0-2h): 100% strength
- ✅ Recent news (2-6h): 80% strength  
- ✅ Stale news (6-12h): 50% strength
- ✅ Expired news (12h+): 0% strength (rechazado)

### 4. Session-Based Logic
- ✅ Premarket (4:00-9:30 AM): Allows overnight news up to 16h
- ✅ Market Hours (9:30-16:00): Strict limits per catalyst type
- ✅ Automatic session detection

## 📁 Estructura de Tests

```
tests/news_aging_optimization/
├── README.md                           # Este archivo
├── test_catalyst_analyzer_aging.py     # Test aging diferenciado
├── test_smallcap_scanner_filters.py    # Test filtros optimizados
├── test_time_decay_multipliers.py      # Test multipliers agresivos
├── test_session_based_filtering.py     # Test filtrado por horario
├── test_end_to_end_integration.py      # Test integración completa
└── test_data/                          # Datos de prueba
    ├── sample_news_fresh.json          # Noticias frescas (0-2h)
    ├── sample_news_recent.json         # Noticias recientes (2-6h)
    ├── sample_news_stale.json          # Noticias stale (6-12h)
    ├── sample_news_expired.json        # Noticias expired (12h+)
    └── catalyst_examples.json          # Ejemplos por tipo catalyst
```

## 🚀 Cómo Ejecutar los Tests

```bash
# Ejecutar todos los tests
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python -m pytest tests/news_aging_optimization/ -v

# Ejecutar test específico
python -m pytest tests/news_aging_optimization/test_catalyst_analyzer_aging.py -v

# Ejecutar con coverage
python -m pytest tests/news_aging_optimization/ --cov=scanner.smallcap --cov-report=html
```

## 📊 Métricas de Éxito Esperadas

- **Precision**: >90% de noticias relevantes para intraday
- **Recall**: <10% de noticias stale/expired passed through
- **Performance**: >80% reducción de noticias procesadas
- **Quality**: Catalyst strength promedio >6.0
- **Timing**: Session detection 100% accurate

## 🔧 Configuración Optimizada Testeada

```python
# ANTES vs AHORA
OLD_CONFIG = {
    'max_news_age_hours': 48,     # vs 8 (83% reduction)
    'min_catalyst_strength': 1,   # vs 5 (5x stricter)
}

NEW_CONFIG = {
    'catalyst_max_age': {
        'FDA': 4, 'M&A': 6, 'EARNINGS': 8, 'CONTRACT': 12
    },
    'news_age_multipliers': {
        'fresh': 1.0, 'recent': 0.8, 'stale': 0.5, 'expired': 0.0
    }
}
```

Fecha creación: 2025-01-21
Versión: 1.0.0
Autor: Trading System v3 - News Aging Optimization