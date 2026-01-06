CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                side TEXT NOT NULL, -- 'BUY' or 'SELL'
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                duration_minutes INTEGER,
                pnl REAL,
                commission REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN', -- 'OPEN', 'CLOSED', 'CANCELLED'
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , confidence DECIMAL(5,2) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 100)), actual_entry_price REAL, actual_exit_price REAL, actual_entry_time TIMESTAMP, actual_exit_time TIMESTAMP, entry_slippage REAL, exit_slippage REAL, entry_slippage_pct REAL, exit_slippage_pct REAL, total_slippage_impact REAL, planned_pnl REAL, actual_pnl REAL, entry_filled BOOLEAN DEFAULT 0, exit_filled BOOLEAN DEFAULT 0, broker_order_id_entry TEXT, broker_order_id_exit TEXT, recent_high_5d REAL DEFAULT 0.0, recent_low_5d REAL DEFAULT 0.0, recent_avg_price REAL DEFAULT 0.0, price_momentum REAL DEFAULT 0.0, volume_trend REAL DEFAULT 1.0, relative_position REAL DEFAULT 0.5, symbol_strength REAL DEFAULT 0.0, market_context TEXT DEFAULT "NEUTRAL", order_flow_boost INTEGER DEFAULT 0, order_flow_signals TEXT, entry_bid REAL, entry_ask REAL, entry_bid_size INTEGER, entry_ask_size INTEGER, entry_spread_pct REAL, bid_pressure REAL, institutional_activity BOOLEAN DEFAULT 0, aggressive_buying BOOLEAN DEFAULT 0, pressure_building BOOLEAN DEFAULT 0, volume_at_ask_ratio REAL, volume_at_bid_ratio REAL, spread_compression_ratio REAL, volume_multiplier REAL, strategy_confidence DECIMAL(5,2), ml_signal_quality DECIMAL(5,2), market_context_score DECIMAL(5,2), trade_session VARCHAR(20), volume_ratio DECIMAL(8,2), gap_percentage DECIMAL(8,4), signal_strength DECIMAL(5,2), trading_horizon TEXT DEFAULT 'INTRADAY', expected_hold_hours REAL DEFAULT 6.0, daily_rsi REAL DEFAULT 50.0, distance_to_resistance_pct REAL DEFAULT 100.0, resistance_price REAL DEFAULT 0.0, EOD_safe BOOLEAN DEFAULT 0, worker_name TEXT, ods_classification TEXT, ods_strength REAL, intraday_phase TEXT, continuation_type TEXT, liquidity_sweep_detected BOOLEAN DEFAULT 0, atr_percent_at_entry REAL, invalid_price REAL, suggested_sl_price REAL, suggested_tp_price REAL, actual_sl_price REAL, actual_tp_price REAL, forward_return_5m REAL, forward_return_15m REAL, forward_return_60m REAL, forward_return_240m REAL, mfe_percent REAL, mae_percent REAL, mfe_reached_at INTEGER, mae_reached_at INTEGER, touched_sl BOOLEAN DEFAULT 0, touched_tp BOOLEAN DEFAULT 0, exit_reason_detailed TEXT, fill_quality TEXT, participation_rate REAL, expected_value_pct REAL, risk_reward_ratio REAL, win_probability REAL, trade_tier TEXT, adaptive_risk_pct REAL, deleted BOOLEAN DEFAULT 0, user_id TEXT);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE trading_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                market_notes TEXT,
                strategy_notes TEXT,
                lessons_learned TEXT,
                mood_rating INTEGER CHECK(mood_rating >= 1 AND mood_rating <= 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE position_risk_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                stop_loss_price REAL,
                take_profit_price REAL,
                trailing_stop_activation_price REAL,
                trailing_stop_distance_pct REAL DEFAULT 0.05,
                max_hold_time_minutes INTEGER DEFAULT 240,
                strategy_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1, entry_time TIMESTAMP, side TEXT DEFAULT 'BUY', highest_price REAL, lowest_price REAL, trailing_activated INTEGER DEFAULT 0, ema_trailing_active INTEGER DEFAULT 0, last_ema_value REAL, partial_profit_taken INTEGER DEFAULT 0, atr_at_entry REAL,
                UNIQUE(symbol, entry_price, quantity)
            );
CREATE TABLE sqlite_stat1(tbl,idx,stat);
CREATE TABLE advanced_trading_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT,
                        ticker TEXT NOT NULL,
                        trade_date DATE NOT NULL,
                        pnl REAL,
                        trade_category TEXT,
                        context_type TEXT,
                        market_context TEXT,
                        why_in_play TEXT,
                        daily_volume_context TEXT,
                        intraday_volume_context TEXT,
                        daily_chart_analysis TEXT,
                        intraday_chart_analysis TEXT,
                        how_you_traded TEXT,
                        followed_system BOOLEAN,
                        sizing_appropriate BOOLEAN,
                        execution_quality TEXT,
                        how_should_have_traded TEXT,
                        key_takeaways TEXT,
                        changes_to_make TEXT,
                        entry_price REAL,
                        exit_price REAL,
                        hold_duration_minutes INTEGER,
                        strategy_used TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                    );
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_strategy ON trades(strategy);
CREATE INDEX idx_trades_date ON trades(date(entry_time));
CREATE TABLE volume_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    volume_requirement_predicted REAL NOT NULL,
                    actual_volume_ratio REAL NOT NULL,
                    market_context TEXT,  -- JSON serialized context
                    trade_success BOOLEAN NOT NULL,
                    pnl REAL,
                    duration_minutes INTEGER,
                    feedback_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model_version TEXT,
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                );
CREATE VIEW strategy_outcomes AS
SELECT 
    t.id as id,
    NULL as id_event, -- No direct mapping to scanner events for now
    t.strategy as strategy_name,
    CASE 
        WHEN t.pnl > 0 THEN 1 
        ELSE 0 
    END as success,
    CASE 
        WHEN t.entry_price > 0 THEN (t.pnl / (t.entry_price * t.quantity)) * 100
        ELSE NULL 
    END as pnl_pct,
    t.duration_minutes,
    CASE 
        WHEN t.pnl > 0 THEN 'profit'
        WHEN t.pnl <= 0 THEN 'stop'  
        ELSE 'unknown'
    END as exit_reason,
    1.5 as volume_requirement_used, -- Default value
    t.entry_price,
    t.exit_price,
    t.pnl as max_pnl_reached, -- Simplified: use final PnL
    CASE WHEN t.pnl < 0 THEN t.pnl ELSE 0 END as min_pnl_reached,
    t.exit_time as timestamp_calculated
FROM trades t 
WHERE t.status = 'CLOSED' 
  AND t.pnl IS NOT NULL
  AND t.entry_price IS NOT NULL
/* strategy_outcomes(id,id_event,strategy_name,success,pnl_pct,duration_minutes,exit_reason,volume_requirement_used,entry_price,exit_price,max_pnl_reached,min_pnl_reached,timestamp_calculated) */;
CREATE TABLE realtime_ev_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                strategy_name VARCHAR(50) NOT NULL,
                
                -- Market Data Input
                current_price DECIMAL(10,4) NOT NULL,
                resistance_level DECIMAL(10,4),
                support_level DECIMAL(10,4),
                volume_ratio DECIMAL(6,2),
                rsi_14 DECIMAL(5,2),
                market_conditions VARCHAR(20),
                
                -- EV Calculation Components
                base_win_rate DECIMAL(5,4) NOT NULL,
                condition_multiplier DECIMAL(4,2) NOT NULL,
                adjusted_win_rate DECIMAL(5,4) NOT NULL,
                potential_reward DECIMAL(10,4) NOT NULL,
                potential_risk DECIMAL(10,4) NOT NULL,
                expected_value DECIMAL(10,4) NOT NULL,
                
                -- Selection Result
                was_selected BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE strategy_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                opportunity_id VARCHAR(50),
                
                -- Available options
                available_strategies TEXT NOT NULL, -- JSON array
                strategy_ev_results TEXT NOT NULL,  -- JSON with all EV calculations
                
                -- Final decision
                selected_strategy VARCHAR(50),
                selected_ev DECIMAL(10,4),
                selection_reasoning TEXT,
                
                -- Execution tracking
                trade_executed BOOLEAN DEFAULT NULL,
                execution_result TEXT, -- JSON with trade outcome
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_realtime_ev_timestamp ON realtime_ev_calculations(timestamp);
CREATE INDEX idx_realtime_ev_symbol ON realtime_ev_calculations(symbol);
CREATE INDEX idx_strategy_selections_timestamp ON strategy_selections(timestamp);
CREATE INDEX idx_strategy_selections_symbol ON strategy_selections(symbol);
CREATE TABLE trade_ohlc_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        trading_date TEXT NOT NULL,

                        -- Datos del día
                        day_open REAL NOT NULL,
                        day_high REAL NOT NULL,
                        day_low REAL NOT NULL,
                        day_close REAL,
                        day_volume INTEGER,

                        -- Datos del trade
                        entry_time TIMESTAMP NOT NULL,
                        entry_price REAL NOT NULL,
                        entry_bar TEXT, -- JSON
                        exit_time TIMESTAMP,
                        exit_price REAL,
                        exit_bar TEXT, -- JSON

                        -- Datos adicionales
                        premarket_high REAL,
                        gap_percent REAL,
                        market_open_price REAL,

                        -- Barras completas del día
                        intraday_bars TEXT, -- JSON con todas las barras

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
CREATE TABLE trade_intraday_bars (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT NOT NULL,
                        bar_timestamp TIMESTAMP NOT NULL,
                        timeframe TEXT DEFAULT '1min',
                        open_price REAL NOT NULL,
                        high_price REAL NOT NULL,
                        low_price REAL NOT NULL,
                        close_price REAL NOT NULL,
                        volume INTEGER NOT NULL,
                        bar_sequence INTEGER,
                        is_entry_bar BOOLEAN DEFAULT 0,
                        is_exit_bar BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, session_type TEXT DEFAULT 'regular',
                        FOREIGN KEY (trade_id) REFERENCES trades(trade_id),
                        UNIQUE(trade_id, bar_timestamp)
                    );
CREATE INDEX idx_trade_ohlc_symbol ON trade_ohlc_snapshots(symbol);
CREATE INDEX idx_trade_ohlc_date ON trade_ohlc_snapshots(trading_date);
CREATE INDEX idx_trade_bars_trade_id ON trade_intraday_bars(trade_id);
CREATE INDEX idx_trade_bars_timestamp ON trade_intraday_bars(bar_timestamp);
CREATE TABLE swing_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT DEFAULT 'swing_consolidation_breakout',

                -- Scan & Entry
                scan_date DATE NOT NULL,           -- Day detected by EOD scanner
                entry_date DATE,                   -- Day entered (NULL if not executed)
                entry_price REAL,
                quantity INTEGER,
                entry_commission REAL DEFAULT 0,

                -- Setup details (from scanner)
                consolidation_days INTEGER,        -- Length of consolidation (20-120 days)
                resistance_level REAL,             -- Upper consolidation bound
                support_level REAL,                -- Lower consolidation bound
                breakout_score REAL,               -- 0-100 composite score
                pattern_type TEXT,                 -- TRIANGLE, CUP_HANDLE, BULL_FLAG, FLAT_BASE

                -- Exit
                exit_date DATE,
                exit_price REAL,
                exit_commission REAL DEFAULT 0,
                exit_reason TEXT,

                -- Performance
                pnl_gross REAL,
                pnl_net REAL,
                pnl_percentage REAL,
                days_held INTEGER,

                status TEXT DEFAULT 'PENDING',     -- PENDING, OPEN, CLOSED, CANCELLED

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE swing_picks_cache (
                symbol TEXT PRIMARY KEY,
                last_pick_date DATE NOT NULL,
                pick_count INTEGER DEFAULT 1,
                last_breakout_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_swing_symbol ON swing_trades(symbol);
CREATE INDEX idx_swing_status ON swing_trades(status);
CREATE INDEX idx_swing_scan_date ON swing_trades(scan_date);
CREATE INDEX idx_swing_entry_date ON swing_trades(entry_date);
CREATE TABLE market_intraday_bars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    bar_timestamp TIMESTAMP NOT NULL,
                    timeframe TEXT DEFAULT '1min',
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    vwap REAL,
                    transactions INTEGER,
                    source TEXT DEFAULT 'polygon',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, bar_timestamp, timeframe)
                );
CREATE INDEX idx_market_bars_symbol
                ON market_intraday_bars(symbol)
            ;
CREATE INDEX idx_market_bars_timestamp
                ON market_intraday_bars(bar_timestamp)
            ;
CREATE INDEX idx_market_bars_symbol_timestamp
                ON market_intraday_bars(symbol, bar_timestamp)
            ;
CREATE TABLE scanner_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Datos de la oportunidad detectada
    current_price REAL,
    gap_percentage REAL,
    volume_ratio REAL,
    quality_score REAL,
    catalyst_type TEXT,
    catalyst_strength INTEGER,
    opportunity_type TEXT,
    
    -- Datos técnicos adicionales
    recent_high_5d REAL,
    recent_low_5d REAL,
    volume_trend REAL,
    price_momentum REAL,
    
    -- Contexto de mercado
    market_context TEXT,
    trade_session TEXT
);
CREATE INDEX idx_scanner_opps_symbol ON scanner_opportunities(symbol);
CREATE INDEX idx_scanner_opps_timestamp ON scanner_opportunities(timestamp);
CREATE INDEX idx_scanner_opps_catalyst ON scanner_opportunities(catalyst_type);
CREATE INDEX idx_scanner_opps_quality ON scanner_opportunities(quality_score);
CREATE TABLE daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                gross_profit REAL DEFAULT 0,
                gross_loss REAL DEFAULT 0,
                max_win REAL DEFAULT 0,
                max_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                avg_win REAL DEFAULT 0,
                avg_loss REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE manual_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT
            );
CREATE INDEX idx_trades_worker ON trades(worker_name);
CREATE INDEX idx_trades_ods ON trades(ods_classification);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason_detailed);
CREATE INDEX idx_trades_confidence_bucket ON trades(
    CASE
        WHEN confidence >= 80 THEN 'high'
        WHEN confidence >= 60 THEN 'med'
        ELSE 'low'
    END
);
CREATE TABLE signal_events (
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
CREATE INDEX idx_signal_events_worker ON signal_events(worker_name);
CREATE INDEX idx_signal_events_symbol ON signal_events(symbol);
CREATE INDEX idx_signal_events_timestamp ON signal_events(timestamp);
CREATE INDEX idx_signal_events_entered ON signal_events(entered);
CREATE INDEX idx_signal_events_ods ON signal_events(ods_classification);
CREATE TABLE tp_sl_performance (
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
CREATE INDEX idx_tp_sl_perf_worker ON tp_sl_performance(worker_name);
CREATE INDEX idx_tp_sl_perf_period ON tp_sl_performance(period_start, period_end);
CREATE VIEW latest_tp_sl_recommendations AS
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
ORDER BY worker_name, confidence_bucket
/* latest_tp_sl_recommendations(worker_name,confidence_bucket,ods_classification,optimal_tp_pct,optimal_sl_pct,optimal_r_r,expected_payoff,sample_size,last_updated) */;
CREATE TABLE volume_watchlist (symbol TEXT PRIMARY KEY, avg_volume REAL, volume_ratio REAL, high_volume_days INTEGER, last_updated TEXT, active_until TEXT);
CREATE TABLE vcp_watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    scan_date TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    avg_volume REAL NOT NULL,
                    num_contractions INTEGER NOT NULL,
                    quality_score REAL NOT NULL,
                    breakout_level REAL NOT NULL,
                    support_level REAL NOT NULL,
                    pivot_high REAL NOT NULL,
                    proximity_pct REAL NOT NULL,
                    contractions_data TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, scan_date)
                );
CREATE INDEX idx_vcp_watchlist_symbol_date
                ON vcp_watchlist(symbol, scan_date)
            ;
CREATE INDEX idx_vcp_watchlist_status_quality
                ON vcp_watchlist(status, quality_score)
            ;
CREATE INDEX idx_vcp_watchlist_status
            ON vcp_watchlist(status)
        ;
CREATE TABLE users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      , full_name TEXT, avatar_url TEXT, is_verified INTEGER DEFAULT 0, timezone TEXT DEFAULT 'UTC', two_factor_enabled INTEGER DEFAULT 0, admin_approved INTEGER DEFAULT 1, two_factor_secret TEXT, two_factor_backup_codes TEXT, verification_token TEXT, verification_expires TEXT, reset_token TEXT, reset_expires TEXT, import_settings TEXT DEFAULT "{}", default_tags TEXT, theme TEXT DEFAULT 'light', refresh_token TEXT, refresh_token_expires_at TEXT);
CREATE TABLE settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        setting_key TEXT NOT NULL,
        setting_value TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(user_id, setting_key)
      );
CREATE TABLE saved_filters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        filter_json TEXT NOT NULL,
        is_favorite INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
      );
CREATE TABLE api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        api_key TEXT NOT NULL,
        model TEXT,
        base_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(user_id, provider)
      );
CREATE TABLE migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
        checksum TEXT NOT NULL
      );
CREATE TABLE user_settings (
        id TEXT PRIMARY KEY,
        user_id TEXT UNIQUE NOT NULL,
        email_notifications INTEGER DEFAULT 1,
        public_profile INTEGER DEFAULT 0,
        default_tags TEXT,
        import_settings TEXT DEFAULT '{}',
        theme TEXT DEFAULT 'light',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
      );
CREATE TABLE custom_patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, color TEXT DEFAULT '#3b82f6', created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE pattern_labels (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, date TEXT NOT NULL, pattern_name TEXT NOT NULL, is_match BOOLEAN DEFAULT 1, start_bar INTEGER, end_bar INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE daily_bars_cache (
                    symbol TEXT,
                    date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    updated_at TEXT,
                    PRIMARY KEY (symbol, date)
                );
CREATE TABLE intraday_bars (
            symbol TEXT,
            bar_timestamp TEXT,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume INTEGER,
            vwap REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, bar_timestamp)
        );
CREATE TABLE proactive_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                detection_date DATE NOT NULL,
                pattern_type TEXT NOT NULL,         -- 'GREEN_DAY_1', 'FAKE_BREAKDOWN', etc.
                status TEXT DEFAULT 'WATCHING',     -- 'WATCHING', 'TRIGGERED', 'EXPIRED', 'TRADED'
                
                -- JSON fields for flexible data storage
                metrics TEXT,                       -- JSON: {float, short_interest, rel_vol, etc.}
                key_levels TEXT,                    -- JSON: {day1_high, support, resistance, vwap_at_detection}
                
                -- Tracking metadata
                days_since_detection INTEGER DEFAULT 0,
                last_check_time TIMESTAMP,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_proactive_symbol ON proactive_candidates(symbol);
CREATE INDEX idx_proactive_date ON proactive_candidates(detection_date);
CREATE INDEX idx_proactive_status ON proactive_candidates(status);
