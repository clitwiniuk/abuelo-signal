-- ============================================================================
-- SCHEMA EXTENSIONS FOR TP/SL OPTIMIZATION
-- Añade campos necesarios para Event Study y análisis de TP/SL
-- ============================================================================

-- Extender tabla 'trades' con campos para análisis de TP/SL
ALTER TABLE trades ADD COLUMN worker_name TEXT;  -- Worker que generó la señal
ALTER TABLE trades ADD COLUMN ods_classification TEXT;  -- ODS en momento de entrada
ALTER TABLE trades ADD COLUMN ods_strength REAL;  -- Strength del ODS (0-10)
ALTER TABLE trades ADD COLUMN intraday_phase TEXT;  -- Fase intraday (OPENING_DRIVE, CONTINUATION, etc.)
ALTER TABLE trades ADD COLUMN continuation_type TEXT;  -- Tipo de continuación si aplica
ALTER TABLE trades ADD COLUMN liquidity_sweep_detected BOOLEAN DEFAULT 0;  -- Sweep detectado
ALTER TABLE trades ADD COLUMN atr_percent_at_entry REAL;  -- ATR% en momento de entrada
ALTER TABLE trades ADD COLUMN invalid_price REAL;  -- Precio de invalidación estructural (SL pattern)
ALTER TABLE trades ADD COLUMN suggested_sl_price REAL;  -- SL sugerido por worker
ALTER TABLE trades ADD COLUMN suggested_tp_price REAL;  -- TP sugerido por worker
ALTER TABLE trades ADD COLUMN actual_sl_price REAL;  -- SL real usado
ALTER TABLE trades ADD COLUMN actual_tp_price REAL;  -- TP real usado

-- Forward Returns (para calcular percentiles de TP óptimo)
ALTER TABLE trades ADD COLUMN forward_return_5m REAL;  -- Return a 5 min
ALTER TABLE trades ADD COLUMN forward_return_15m REAL;  -- Return a 15 min
ALTER TABLE trades ADD COLUMN forward_return_60m REAL;  -- Return a 60 min
ALTER TABLE trades ADD COLUMN forward_return_240m REAL;  -- Return a 240 min (4h)

-- MFE/MAE (Max Favorable/Adverse Excursion)
ALTER TABLE trades ADD COLUMN mfe_percent REAL;  -- Max ganancia durante trade (%)
ALTER TABLE trades ADD COLUMN mae_percent REAL;  -- Max pérdida durante trade (%)
ALTER TABLE trades ADD COLUMN mfe_reached_at INTEGER;  -- Minutos desde entry cuando alcanzó MFE
ALTER TABLE trades ADD COLUMN mae_reached_at INTEGER;  -- Minutos desde entry cuando alcanzó MAE

-- Exit Analysis
ALTER TABLE trades ADD COLUMN touched_sl BOOLEAN DEFAULT 0;  -- ¿Tocó SL?
ALTER TABLE trades ADD COLUMN touched_tp BOOLEAN DEFAULT 0;  -- ¿Tocó TP?
ALTER TABLE trades ADD COLUMN exit_reason_detailed TEXT;  -- Razón detallada (TIME_EXIT, SL_HIT, TP_HIT, TRAILING_STOP, etc.)

-- Execution Quality
ALTER TABLE trades ADD COLUMN fill_quality TEXT;  -- FULL, PARTIAL, REJECTED
ALTER TABLE trades ADD COLUMN participation_rate REAL;  -- % del volumen del minuto usado

-- Create indexes for analysis queries
CREATE INDEX IF NOT EXISTS idx_trades_worker ON trades(worker_name);
CREATE INDEX IF NOT EXISTS idx_trades_ods ON trades(ods_classification);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason_detailed);
CREATE INDEX IF NOT EXISTS idx_trades_confidence_bucket ON trades(
    CASE
        WHEN confidence >= 80 THEN 'high'
        WHEN confidence >= 60 THEN 'med'
        ELSE 'low'
    END
);

-- ============================================================================
-- Nueva tabla: signal_events (captura TODAS las señales, no solo trades)
-- ============================================================================
CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificación
    signal_id TEXT UNIQUE NOT NULL,  -- UUID
    symbol TEXT NOT NULL,
    worker_name TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- Señal generada
    entered BOOLEAN DEFAULT 0,  -- ¿Se entró al trade?
    rejection_reason TEXT,  -- Si no entró, ¿por qué?
    trade_id TEXT,  -- Link a trades table si se ejecutó

    -- Precios
    entry_price REAL NOT NULL,
    invalid_price REAL,  -- Invalidación estructural
    suggested_sl REAL,
    suggested_tp REAL,

    -- Contexto ODS/Structure
    ods_classification TEXT,
    ods_strength REAL,
    ods_direction TEXT,  -- BULLISH, BEARISH, NEUTRAL
    intraday_phase TEXT,
    continuation_type TEXT,
    liquidity_sweep_detected BOOLEAN DEFAULT 0,
    sweep_direction TEXT,

    -- Métricas
    confidence REAL,
    quality_score REAL,
    atr_percent REAL,
    volume_ratio REAL,
    gap_percentage REAL,
    catalyst_type TEXT,
    catalyst_strength INTEGER,

    -- Forward tracking (populated later)
    forward_return_5m REAL,
    forward_return_15m REAL,
    forward_return_60m REAL,
    forward_return_240m REAL,
    max_price_reached REAL,
    min_price_reached REAL,
    mfe_percent REAL,
    mae_percent REAL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    forward_tracked_at TIMESTAMP,  -- Cuando se capturaron forward returns

    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

CREATE INDEX IF NOT EXISTS idx_signal_events_worker ON signal_events(worker_name);
CREATE INDEX IF NOT EXISTS idx_signal_events_symbol ON signal_events(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_events_timestamp ON signal_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_signal_events_entered ON signal_events(entered);
CREATE INDEX IF NOT EXISTS idx_signal_events_ods ON signal_events(ods_classification);

-- ============================================================================
-- Nueva tabla: tp_sl_performance (análisis agregado por worker/bucket)
-- ============================================================================
CREATE TABLE IF NOT EXISTS tp_sl_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificación
    worker_name TEXT NOT NULL,
    confidence_bucket TEXT NOT NULL,  -- 'high', 'med', 'low'
    ods_classification TEXT,  -- NULL = all ODS types

    -- Período de análisis
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    sample_size INTEGER NOT NULL,

    -- Percentiles de forward returns (60min)
    p50_return REAL,  -- Mediana
    p60_return REAL,
    p70_return REAL,
    p75_return REAL,
    p80_return REAL,
    p90_return REAL,

    -- Win rate por TP level
    win_rate_p60 REAL,  -- Si usamos P60 como TP, ¿qué WR?
    win_rate_p70 REAL,
    win_rate_p80 REAL,

    -- Expectancy por TP level
    expectancy_p60 REAL,  -- Expected value si TP=P60
    expectancy_p70 REAL,
    expectancy_p80 REAL,

    -- Recomendación óptima
    optimal_tp_pct REAL,  -- TP que maximiza expectancy
    optimal_sl_pct REAL,  -- SL promedio de invalidaciones
    optimal_r_r REAL,  -- R:R óptimo

    -- Métricas adicionales
    avg_mfe REAL,
    avg_mae REAL,
    avg_hold_time_minutes INTEGER,
    sl_hit_rate REAL,  -- % que toca SL antes de TP

    -- Metadata
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    UNIQUE(worker_name, confidence_bucket, ods_classification, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_tp_sl_perf_worker ON tp_sl_performance(worker_name);
CREATE INDEX IF NOT EXISTS idx_tp_sl_perf_period ON tp_sl_performance(period_start, period_end);

-- ============================================================================
-- View: Latest TP/SL Recommendations
-- ============================================================================
CREATE VIEW IF NOT EXISTS latest_tp_sl_recommendations AS
SELECT
    worker_name,
    confidence_bucket,
    ods_classification,
    optimal_tp_pct,
    optimal_sl_pct,
    optimal_r_r,
    expectancy_p70 as expected_payoff,
    sample_size,
    period_end as last_updated
FROM tp_sl_performance
WHERE (worker_name, confidence_bucket, ods_classification, calculated_at) IN (
    SELECT worker_name, confidence_bucket, ods_classification, MAX(calculated_at)
    FROM tp_sl_performance
    GROUP BY worker_name, confidence_bucket, ods_classification
)
ORDER BY worker_name, confidence_bucket;
