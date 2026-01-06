# Learning System - Arquitectura Técnica

## 🏗️ Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND                      │
│                quality_trading_standalone.py               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                ADVANCED SETUP ANALYZER                     │
│           quality_core/advanced_setup_analyzer.py          │
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────┐ │
│  │Consolidation│ │   Timing    │ │   Volume    │ │  News  │ │
│  │ Analysis    │ │  Analysis   │ │  Analysis   │ │Analysis│ │
│  │   (30%)     │ │   (25%)     │ │   (25%)     │ │ (20%)  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 LEARNING SYSTEM                             │
│             quality_core/learning_system.py                │
│                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │ PredictionTracker│ │WeightLearning   │ │ AutoLearning  │ │
│  │                 │ │System           │ │ System        │ │
│  │ • Log predictions│ │ • Optimize      │ │ • Integration │ │
│  │ • Track results │ │   weights       │ │   layer       │ │
│  │ • SQLite DB     │ │ • Correlation   │ │ • Unified API │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 PERSISTENCE LAYER                           │
│                learning_system.db (SQLite)                 │
│                                                             │
│  ┌─────────────────┐ ┌─────────────────────────────────────┐ │
│  │   predictions   │ │        prediction_results           │ │
│  │                 │ │                                     │ │
│  │ • timestamp     │ │ • prediction_id (FK)                │ │
│  │ • ticker        │ │ • price_30min, 1h, 2h, eod         │ │
│  │ • factor_scores │ │ • return_30min, 1h, 2h, eod        │ │
│  │ • weights_used  │ │ • final_result (win/loss/neutral)   │ │
│  │ • prediction    │ │ • max_gain_pct, max_loss_pct        │ │
│  └─────────────────┘ └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Flujo de Datos

### 1. **Análisis de Setup**
```python
# User input desde Streamlit
ticker = "PPSI"
price = 4.42
volume = 80_600_000
gap_pct = 42.1

# Advanced Analyzer procesamiento
analyzer = AdvancedSetupAnalyzer(learning_db_path="learning_system.db")
analysis = analyzer.comprehensive_setup_analysis(ticker, price, volume, gap_pct)

# Output: SetupAnalysis object con grade, score, recommendation, etc.
```

### 2. **Factor Analysis Pipeline**
```python
# Cada factor se analiza independientemente
consolidation = analyze_consolidation_pattern(data, current_price)
timing = analyze_timing_and_movement(ticker, current_price)  
volume = analyze_volume_profile(ticker, current_volume)
news = get_news_sentiment(ticker)

# Weighted scoring con pesos dinámicos del learning system
weights = learning_system.get_current_weights()
overall_score = (
    consolidation['score'] * weights['consolidation'] +
    timing['score'] * weights['timing'] +
    volume['score'] * weights['volume'] +
    news['score'] * weights['news']
)
```

### 3. **Learning Pipeline**
```python
# Logging automático de predicción
prediction_id = learning_system.log_prediction(ticker, analysis_result, weights)

# Más tarde... actualización de resultados
learning_system.update_results_and_learn()

# Optimización de pesos basada en correlaciones
new_weights = learning_system.optimize_weights(historical_data)
```

## 🧠 Learning Algorithm

### **Weight Optimization Process**

```python
def optimize_weights(data: pd.DataFrame) -> Dict:
    # 1. Calcular correlaciones entre factores y éxito
    correlations = {}
    for factor in ['consolidation', 'timing', 'volume', 'news']:
        correlation = data[f'{factor}_score'].corr(data['success'])
        correlations[factor] = correlation
    
    # 2. Calcular nuevos pesos proporcionales a correlación
    total_correlation = sum(abs(corr) for corr in correlations.values())
    new_weights = {}
    for factor, corr in correlations.items():
        new_weight = abs(corr) / total_correlation
        
        # 3. Aplicar learning rate para cambio gradual
        current_weight = self.current_weights[factor]
        updated_weight = current_weight + learning_rate * (new_weight - current_weight)
        
        # 4. Aplicar bounds para evitar extremos
        updated_weight = max(0.05, min(0.50, updated_weight))
        new_weights[factor] = updated_weight
    
    # 5. Normalizar para que sumen 1.0
    total_weight = sum(new_weights.values())
    for factor in new_weights:
        new_weights[factor] /= total_weight
    
    return new_weights
```

### **Bias Prevention**

1. **No Look-Ahead Bias**: Solo usa datos históricos hasta el momento de predicción
2. **No Survivorship Bias**: Incluye todos los trades, ganadores y perdedores  
3. **No Selection Bias**: Sistema automático sin intervención manual

## 📊 Database Schema

### **predictions table**
```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,                    -- Momento de predicción
    ticker TEXT NOT NULL,                       -- Símbolo analizado
    prediction_time TEXT NOT NULL,              -- Timestamp formateado
    
    -- Inputs de la predicción
    current_price REAL NOT NULL,                -- Precio al momento
    volume INTEGER NOT NULL,                    -- Volumen actual
    premarket_gap_pct REAL NOT NULL,            -- Gap premarket %
    
    -- Factor scores calculados
    consolidation_score REAL NOT NULL,          -- Score 0-100
    timing_score REAL NOT NULL,                 -- Score 0-100
    volume_score REAL NOT NULL,                 -- Score 0-100
    news_score REAL NOT NULL,                   -- Score 0-100
    
    -- Predicción realizada
    predicted_grade TEXT NOT NULL,              -- A+, A, A-, B+, B, C, D
    predicted_score INTEGER NOT NULL,           -- Score final 0-100
    recommendation TEXT NOT NULL,               -- STRONG BUY, BUY, etc.
    
    -- Pesos usados (para auditoría)
    weight_consolidation REAL NOT NULL,         -- Peso usado 0-1
    weight_timing REAL NOT NULL,                -- Peso usado 0-1
    weight_volume REAL NOT NULL,                -- Peso usado 0-1
    weight_news REAL NOT NULL,                  -- Peso usado 0-1
    
    -- Estado
    result_tracked BOOLEAN DEFAULT FALSE,       -- ¿Resultado actualizado?
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **prediction_results table**
```sql
CREATE TABLE prediction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL,             -- FK a predictions
    ticker TEXT NOT NULL,                       -- Redundante para queries
    
    -- Precios en diferentes timeframes
    price_30min REAL,                           -- Precio 30min después
    price_1h REAL,                              -- Precio 1h después
    price_2h REAL,                              -- Precio 2h después
    price_eod REAL,                             -- Precio end of day
    
    -- Returns calculados
    return_30min REAL,                          -- % return 30min
    return_1h REAL,                             -- % return 1h
    return_2h REAL,                             -- % return 2h
    return_eod REAL,                            -- % return EOD
    
    -- Métricas de performance
    max_gain_pct REAL,                          -- Máximo gain intraday
    max_loss_pct REAL,                          -- Máximo loss intraday
    final_result TEXT,                          -- 'win', 'loss', 'neutral'
    
    result_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prediction_id) REFERENCES predictions (id)
);
```

## 🎯 Factor Analysis Deep Dive

### **1. Consolidation Analysis**
```python
def analyze_consolidation_pattern(data: pd.DataFrame, current_price: float):
    # Calcular volatilidad rolling (20-day windows)
    returns = np.diff(closes) / closes[:-1]
    rolling_volatility = [np.std(returns[i-19:i+1]) for i in range(19, len(returns))]
    
    # Identificar períodos de baja volatilidad (bottom 30%)
    vol_threshold = np.percentile(rolling_volatility, 30)
    low_vol_periods = np.array(rolling_volatility) <= vol_threshold
    
    # Contar días consecutivos de consolidación
    consolidation_months = max_consecutive_days / 22  # ~22 trading days/month
    
    # Buscar resistencias históricas
    historical_highs = find_significant_highs(data, current_price)
    
    # Scoring: 40pts consolidation + 40pts room to run + 20pts volume consistency
    return {
        'consolidation_months': consolidation_months,
        'historical_highs': historical_highs,
        'score': calculate_consolidation_score(...)
    }
```

### **2. Timing Analysis**
```python
def analyze_timing_and_movement(ticker: str, current_price: float):
    # Gap premarket vs yesterday close
    yesterday_close = get_yesterday_close(ticker)
    premarket_gap = (current_price - yesterday_close) / yesterday_close
    
    # Regular hours performance si disponible
    intraday_data = get_intraday_data(ticker)
    if intraday_data:
        market_open_price = intraday_data.iloc[0]['Open']
        regular_hours_move = (current_price - market_open_price) / market_open_price
    
    # Red flags: >80% move in premarket
    red_flags = []
    if abs(premarket_gap) > 0.8:
        red_flags.append("Excessive premarket movement - likely exhausted")
    
    return {
        'premarket_gap_pct': premarket_gap * 100,
        'regular_hours_move_pct': regular_hours_move * 100,
        'red_flags': red_flags,
        'score': calculate_timing_score(...)
    }
```

### **3. Volume Analysis**
```python
def analyze_volume_profile(ticker: str, current_volume: int):
    data = get_historical_data(ticker)
    
    # Volume ratios
    avg_volume_20d = np.mean(data['Volume'][-20:])
    volume_ratio = current_volume / avg_volume_20d
    
    # Price-volume correlation (accumulation vs distribution)
    price_changes = np.diff(data['Close'][-20:])
    volume_changes = np.diff(data['Volume'][-20:])
    correlation = np.corrcoef(price_changes, volume_changes[:-1])[0,1]
    
    pattern = 'accumulation' if correlation > 0.3 else 'distribution' if correlation < -0.3 else 'neutral'
    
    return {
        'volume_ratio_20d': volume_ratio,
        'pattern': pattern,  # accumulation/distribution/neutral
        'score': calculate_volume_score(...)
    }
```

## 🔧 Integration Points

### **Streamlit Integration**
```python
# quality_trading_standalone.py
def classify_setup_quality(setup, classifier=None):
    if ADVANCED_ANALYZER_AVAILABLE:
        # Usar advanced analyzer con learning
        result = analyze_setup_comprehensive(
            ticker=setup['ticker'],
            current_price=setup['price'],
            current_volume=setup['volume'],
            premarket_gap_pct=setup['pct_change']
        )
        return convert_to_display_format(result)
    else:
        # Fallback a análisis básico
        return basic_classification(setup)
```

### **CLI Tools Integration**
```python
# quality_core/learning_monitor.py
def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    
    # stats, update, predictions, reset, export commands
    if args.command == 'stats':
        display_learning_stats(db_path)
    elif args.command == 'update':
        update_pending_results(db_path, args.dry_run)
    # ... etc
```

## 🚀 Performance Considerations

### **Caching Strategy**
- Historical data cacheado por ticker/timeframe
- Learning weights cacheados hasta próxima optimización
- Database connections pooled para múltiples requests

### **Async Processing**
- Result updates pueden ejecutarse en background
- Batch processing para múltiples setups
- Rate limiting para APIs externas (yfinance, news)

### **Scalability**
- SQLite suficiente para miles de predicciones
- Upgrade path a PostgreSQL si necesario
- Horizontal scaling vía microservices si requerido

## 🛡️ Error Handling

### **Graceful Degradation**
1. Si no hay datos históricos → usar análisis básico
2. Si learning system falla → usar pesos default
3. Si factor individual falla → excluir del scoring
4. Si todo falla → fallback a clasificación simple

### **Logging Strategy**
```python
import logging

logger = logging.getLogger(__name__)

# Info level para operaciones normales
logger.info(f"Prediction logged for {ticker} with ID {prediction_id}")

# Warning level para degradación
logger.warning(f"Failed to get learned weights: {e}")

# Error level para fallos críticos
logger.error(f"Error in comprehensive analysis for {ticker}: {e}")
```

Esta arquitectura asegura un sistema robusto, escalable y maintainable que puede evolucionar con nuevos requerimientos. 🎯