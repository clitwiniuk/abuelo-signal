-- Enhanced trades schema for real execution price tracking
-- Adds support for planned vs actual prices and slippage calculation

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    
    -- PLANNED PRICES (from trading strategy)
    entry_price REAL NOT NULL,           -- Original planned entry price
    exit_price REAL,                     -- Original planned exit price
    
    -- ACTUAL EXECUTION PRICES (from broker)
    actual_entry_price REAL,             -- Real executed entry price from broker
    actual_exit_price REAL,              -- Real executed exit price from broker
    actual_entry_time TIMESTAMP,         -- Actual execution time for entry
    actual_exit_time TIMESTAMP,          -- Actual execution time for exit
    
    -- SLIPPAGE METRICS
    entry_slippage REAL,                 -- actual_entry_price - entry_price
    exit_slippage REAL,                  -- actual_exit_price - exit_price
    entry_slippage_pct REAL,             -- (actual_entry_price - entry_price) / entry_price * 100
    exit_slippage_pct REAL,              -- (actual_exit_price - exit_price) / exit_price * 100
    total_slippage_impact REAL,          -- Impact on P&L due to slippage
    
    -- P&L CALCULATIONS (both planned and actual)
    planned_pnl REAL,                    -- P&L based on planned prices
    actual_pnl REAL,                     -- P&L based on actual execution prices
    
    -- ORIGINAL FIELDS
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    duration_minutes INTEGER,
    pnl REAL,                           -- Keep for backward compatibility (will be actual_pnl)
    commission REAL DEFAULT 0,
    status TEXT DEFAULT 'OPEN',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence DECIMAL(5,2),
    
    -- EXECUTION TRACKING
    entry_filled BOOLEAN DEFAULT 0,     -- Flag to track if entry was executed
    exit_filled BOOLEAN DEFAULT 0,      -- Flag to track if exit was executed
    broker_order_id_entry TEXT,         -- Broker's order ID for entry
    broker_order_id_exit TEXT           -- Broker's order ID for exit
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_actual_times ON trades(actual_entry_time, actual_exit_time);

-- Create view for easy slippage analysis
CREATE VIEW IF NOT EXISTS slippage_analysis AS
SELECT 
    trade_id,
    symbol,
    strategy,
    side,
    
    -- Planned vs Actual
    entry_price as planned_entry,
    actual_entry_price,
    exit_price as planned_exit,
    actual_exit_price,
    
    -- Slippage metrics
    entry_slippage,
    exit_slippage,
    entry_slippage_pct,
    exit_slippage_pct,
    total_slippage_impact,
    
    -- P&L comparison
    planned_pnl,
    actual_pnl,
    (actual_pnl - planned_pnl) as pnl_difference,
    
    -- Execution status
    entry_filled,
    exit_filled,
    
    actual_entry_time,
    actual_exit_time
FROM trades
WHERE entry_filled = 1;  -- Only show executed trades

-- Create view for TradeTally sync (uses actual prices)
CREATE VIEW IF NOT EXISTS trades_for_tradetally AS
SELECT 
    trade_id,
    symbol,
    strategy,
    side,
    quantity,
    
    -- Use actual prices if available, fallback to planned
    COALESCE(actual_entry_price, entry_price) as final_entry_price,
    COALESCE(actual_exit_price, exit_price) as final_exit_price,
    COALESCE(actual_entry_time, entry_time) as final_entry_time,
    COALESCE(actual_exit_time, exit_time) as final_exit_time,
    
    -- Use actual P&L if available, fallback to planned
    COALESCE(actual_pnl, planned_pnl, pnl) as final_pnl,
    
    commission,
    notes,
    status,
    created_at,
    updated_at,
    confidence,
    
    -- Slippage info for notes
    entry_slippage,
    exit_slippage,
    entry_slippage_pct,
    exit_slippage_pct
FROM trades;