import sqlite3
import pandas as pd
import configparser
import os
import re
from datetime import datetime, timedelta

# Constants
DB_PATH = "trading_data.db"
CONFIG_PATH = "config.ini"
TRADER_LOG_PATH = "logs/trader.log"

# --- Database Functions ---

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    return conn

def get_active_trades():
    """
    Retrieves currently OPEN trades.
    Returns a DataFrame.
    """
    conn = get_db_connection()
    query = """
    SELECT 
        symbol, strategy, side, quantity, entry_price, 
        entry_time, pnl, current_price, current_value
    FROM (
        SELECT 
            symbol, strategy, side, quantity, entry_price, entry_time,
            actual_pnl as pnl,
            actual_exit_price as current_price, -- Assuming updated frequently for open trades or NULL
            (quantity * entry_price) as current_value -- Placeholder, refine if current_price available
        FROM trades 
        WHERE status = 'OPEN'
    )
    """ 
    # NOTE: The schema shows 'status' column. 'active_positions' might need live price updates not in DB purely.
    # For now, we pull what's in DB. The DB might not have real-time market price unless updated.
    # We will just fetch the core trade details.
    
    query_simple = """
    SELECT
        trade_id, symbol, strategy, side, quantity,
        entry_price,
        actual_entry_price,
        actual_exit_price,
        entry_time,
        actual_entry_time,
        entry_filled,
        exit_filled,
        actual_pnl,
        status,
        notes
    FROM trades
    WHERE status = 'OPEN'
    ORDER BY entry_time DESC
    """

    try:
        df = pd.read_sql_query(query_simple, conn)

        # For open positions, ensure we have pnl and current_price
        if not df.empty:
            # DATA INTEGRITY CHECK: Detect and fix inconsistencies
            for idx, row in df.iterrows():
                symbol = row['symbol']
                trade_id = row['trade_id']

                # Check 1: Validate actual_entry_price consistency
                if pd.notna(row['actual_entry_price']) and pd.notna(row['entry_price']):
                    slippage_pct = abs((row['actual_entry_price'] - row['entry_price']) / row['entry_price'] * 100)
                    if slippage_pct > 50:  # More than 50% difference is suspicious
                        print(f"⚠️ WARNING: {symbol} ({trade_id}) has suspicious entry price data:")
                        print(f"   Planned: ${row['entry_price']:.2f}")
                        print(f"   Actual: ${row['actual_entry_price']:.2f}")
                        print(f"   Difference: {slippage_pct:.1f}% - Using planned price as fallback")
                        # Use planned entry price as it's more reliable
                        df.at[idx, 'actual_entry_price'] = row['entry_price']

                # Check 2: Exit should not be filled for OPEN positions
                if row['exit_filled'] == 1:
                    print(f"⚠️ WARNING: {symbol} ({trade_id}) marked as OPEN but exit_filled=1")
                    print(f"   This is a data inconsistency - trade should be CLOSED")

            # Prioritize actual_entry_price if valid, otherwise use entry_price
            df['actual_entry_price'] = df.apply(
                lambda row: row['actual_entry_price'] if pd.notna(row['actual_entry_price']) else row['entry_price'],
                axis=1
            )

            # USE IBKR SNAPSHOT PRICES: trader_main.py updates actual_exit_price every 3 minutes
            # for OPEN trades with real-time IBKR prices via BatchPriceManager
            # This is the CORRECT source of truth for current prices
            df['current_price'] = df.apply(
                lambda row: (
                    # Use actual_exit_price if available (updated by trader_main snapshot)
                    row['actual_exit_price'] if pd.notna(row['actual_exit_price']) and row['actual_exit_price'] > 0
                    # Otherwise fallback to entry price (trade just opened, no snapshot yet)
                    else row['actual_entry_price']
                ),
                axis=1
            )

            # USE ACTUAL_PNL FROM DB: trader_main.py calculates this with IBKR prices
            # No need to recalculate - trust the DB value
            df['pnl'] = df['actual_pnl'].fillna(0.0)

        # Close connection AFTER all queries are complete
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching active trades: {e}")
        conn.close()
        return pd.DataFrame()

def get_closed_trades(limit=100):
    """
    Retrieves CLOSED trades for history.
    Returns a DataFrame.
    """
    conn = get_db_connection()
    query = f"""
    SELECT 
        trade_id, symbol, strategy, side, quantity, 
        entry_price, exit_price, entry_time, exit_time, 
        pnl, commission, status, duration_minutes
    FROM trades 
    WHERE status != 'OPEN'
    ORDER BY exit_time DESC
    LIMIT {limit}
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching closed trades: {e}")
        conn.close()
        return pd.DataFrame()

def get_analytics_data():
    """
    Retrieves ALL closed trades for deep analytics.
    """
    conn = get_db_connection()
    query = """
    SELECT 
        strategy, side, quantity, entry_price, exit_price, 
        entry_time, exit_time, pnl, commission, duration_minutes
    FROM trades 
    WHERE status != 'OPEN' AND pnl IS NOT NULL
    ORDER BY exit_time ASC
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        # Ensure datetimes
        if not df.empty:
            df['entry_time'] = pd.to_datetime(df['entry_time'], format='mixed')
            df['exit_time'] = pd.to_datetime(df['exit_time'], format='mixed')
        return df
    except Exception as e:
        print(f"Error fetching analytics data: {e}")
        conn.close()
        return pd.DataFrame()

def get_scanner_feed(limit=50):
    """
    Retrieves recent scanner opportunities from DB.
    """
    conn = get_db_connection()
    query = f"""
    SELECT 
        timestamp, symbol, current_price, gap_percentage, 
        volume_ratio, quality_score, catalyst_type, opportunity_type
    FROM scanner_opportunities
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            # Parse timestamp if it's string
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
        return df
    except Exception as e:
        print(f"Error fetching scanner feed: {e}")
        conn.close()
        return pd.DataFrame()

def get_trading_metrics():
    """
    Get current trading metrics: positions, orders, last execution, trades today.
    """
    conn = get_db_connection()
    try:
        # Active positions count
        active_positions = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'").fetchone()[0] or 0
        
        # Pending orders (if we track them - for now return 0)
        pending_orders = 0
        
        # Last execution
        last_trade = conn.execute("""
            SELECT symbol, entry_time FROM trades 
            WHERE status != 'OPEN' 
            ORDER BY entry_time DESC LIMIT 1
        """).fetchone()
        last_execution = last_trade[0] if last_trade else "N/A"
        
        # Trades today
        today = datetime.now().strftime('%Y-%m-%d')
        trades_today = conn.execute(f"""
            SELECT COUNT(*) FROM trades 
            WHERE date(entry_time) = '{today}'
        """).fetchone()[0] or 0
        
        conn.close()
        return {
            "active_positions": active_positions,
            "pending_orders": pending_orders,
            "last_execution": last_execution,
            "trades_today": trades_today
        }
    except Exception as e:
        print(f"Error fetching trading metrics: {e}")
        conn.close()
        return {
            "active_positions": 0,
            "pending_orders": 0,
            "last_execution": "N/A",
            "trades_today": 0
        }

def get_risk_metrics():
    """
    Get risk management metrics: daily PnL, drawdown, max loss, exposure.
    Uses actual_pnl (IBKR execution data) when available, falls back to pnl.
    """
    conn = get_db_connection()
    try:
        # Daily PnL - Use actual_pnl when available
        today = datetime.now().strftime('%Y-%m-%d')
        daily_pnl = conn.execute(f"""
            SELECT SUM(COALESCE(actual_pnl, pnl, 0)) FROM trades
            WHERE status != 'OPEN' AND date(exit_time) = '{today}'
        """).fetchone()[0] or 0.0

        # Calculate drawdown (from peak equity) - Use actual_pnl when available
        equity_data = pd.read_sql_query("""
            SELECT exit_time, COALESCE(actual_pnl, pnl, 0) as pnl FROM trades
            WHERE status != 'OPEN' AND exit_time IS NOT NULL
            ORDER BY exit_time ASC
        """, conn)

        drawdown = 0.0
        if not equity_data.empty:
            equity_data['cumulative_pnl'] = equity_data['pnl'].cumsum()
            peak = equity_data['cumulative_pnl'].cummax()
            drawdown_series = equity_data['cumulative_pnl'] - peak
            current_drawdown = drawdown_series.iloc[-1] if len(drawdown_series) > 0 else 0.0
            drawdown = current_drawdown
        
        # Max loss allowed (from config or default)
        max_loss = 500.0  # Default, could read from config
        
        # Current exposure (sum of open position values)
        exposure_data = conn.execute("""
            SELECT SUM(entry_price * quantity) FROM trades WHERE status = 'OPEN'
        """).fetchone()[0] or 0.0
        
        conn.close()
        return {
            "daily_pnl": daily_pnl,
            "drawdown": drawdown,
            "max_loss": max_loss,
            "exposure": exposure_data
        }
    except Exception as e:
        print(f"Error fetching risk metrics: {e}")
        conn.close()
        return {
            "daily_pnl": 0.0,
            "drawdown": 0.0,
            "max_loss": 500.0,
            "exposure": 0.0
        }

def get_equity_curve():
    """
    Calculates cumulative PnL over time from closed trades.
    Uses actual_pnl when available, falls back to pnl.
    Returns a DataFrame suitable for plotting.
    """
    conn = get_db_connection()
    query = """
    SELECT
        exit_time as time,
        COALESCE(actual_pnl, pnl, 0) as pnl
    FROM trades
    WHERE status != 'OPEN' AND exit_time IS NOT NULL
    ORDER BY exit_time ASC
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Handle potential mixed formats or microseconds
            df['time'] = pd.to_datetime(df['time'], format='mixed')
            df['cumulative_pnl'] = df['pnl'].cumsum()
        return df
    except Exception as e:
        print(f"Error fetching equity curve: {e}")
        conn.close()
        return pd.DataFrame()

def get_intraday_equity():
    """
    Get today's equity curve for intraday visualization.
    """
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    query = f"""
    SELECT 
        exit_time as time, 
        pnl
    FROM trades 
    WHERE status != 'OPEN' AND exit_time IS NOT NULL
    AND date(exit_time) = '{today}'
    ORDER BY exit_time ASC
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'], format='mixed')
            df['cumulative_pnl'] = df['pnl'].cumsum()
        return df
    except Exception as e:
        print(f"Error fetching intraday equity: {e}")
        conn.close()
        return pd.DataFrame()

def get_pnl_distribution():
    """
    Get PnL values for all closed trades for histogram.
    """
    conn = get_db_connection()
    query = """
    SELECT pnl FROM trades 
    WHERE status != 'OPEN' AND pnl IS NOT NULL
    """
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching PnL distribution: {e}")
        conn.close()
        return pd.DataFrame()

# --- Notes Feature Functions ---
NOTES_FILE = "dashboard_notes.txt"

def get_notes():
    """Reads notes from the local text file."""
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_note(note):
    """Appends a new note to the file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTES_FILE, "a") as f:
        f.write(f"[{timestamp}] {note}\n")

def clear_notes():
    """Clears all notes."""
    if os.path.exists(NOTES_FILE):
        os.remove(NOTES_FILE)

def get_pnl_stats():
    """
    Calculates aggregate PnL statistics.
    Uses actual_pnl (from IBKR execution data) when available, falls back to pnl for legacy trades.
    """
    conn = get_db_connection()
    try:
        # Total PnL - Use actual_pnl when available, fallback to pnl
        total_pnl = conn.execute("SELECT SUM(COALESCE(actual_pnl, pnl, 0)) FROM trades WHERE status != 'OPEN'").fetchone()[0] or 0.0

        # Today's PnL - Use actual_pnl when available
        today = datetime.now().strftime('%Y-%m-%d')
        today_pnl = conn.execute(f"SELECT SUM(COALESCE(actual_pnl, pnl, 0)) FROM trades WHERE status != 'OPEN' AND date(exit_time) = '{today}'").fetchone()[0] or 0.0

        # Win Rate - Use actual_pnl when available
        total_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE status != 'OPEN'").fetchone()[0] or 0
        winning_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE status != 'OPEN' AND COALESCE(actual_pnl, pnl, 0) > 0").fetchone()[0] or 0

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        conn.close()

        return {
            "total_pnl": total_pnl,
            "today_pnl": today_pnl,
            "win_rate": win_rate,
            "total_trades": total_trades
        }
    except Exception as e:
        print(f"Error fetching Stats: {e}")
        conn.close()
        return {
            "total_pnl": 0.0,
            "today_pnl": 0.0,
            "win_rate": 0.0,
            "total_trades": 0
        }

# --- Config Functions ---

def read_config():
    """Reads the entire config.ini file."""
    config = configparser.ConfigParser()
    # Preserve case sensitivity if needed, but standard INI is usually case-insensitive.
    # ConfigParser defaults to lowercase keys. To preserve case, we can override optionxform.
    config.optionxform = str 
    try:
        config.read(CONFIG_PATH)
        return config
    except Exception as e:
        print(f"Error reading config: {e}")
        return None

def update_config(section, key, value):
    """Updates a specific key in the config file."""
    config = read_config()
    if config:
        if not config.has_section(section):
            return False, f"Section {section} not found"
        
        config.set(section, key, str(value))
        
        try:
            with open(CONFIG_PATH, 'w') as configfile:
                config.write(configfile)
            return True, "Config updated successfully"
        except Exception as e:
            return False, f"Error writing config: {e}"
    return False, "Could not load config"

# --- Log Functions ---

def read_log_tail(lines=100, level_filter=None):
    """
    Reads the last N lines of the trader log.
    Optional level_filter (e.g., 'ERROR', 'WARNING').
    """
    if not os.path.exists(TRADER_LOG_PATH):
        return []

    log_entries = []
    
    try:
        # Better to read file in reverse if large, but simple tail for now
        with open(TRADER_LOG_PATH, 'r') as f:
            all_lines = f.readlines()
            
        last_n = all_lines[-lines:]
        
        for line in last_n:
            if level_filter and level_filter not in line:
                continue
            
            # Basic parsing if needed, or just return raw line
            log_entries.append(line.strip())
            
        return log_entries[::-1] # Reverse to show newest on top
    except Exception as e:
        print(f"Error reading logs: {e}")
        return []

def parse_log_events(lines=200):
    """
    Parses logs into structured events for the Live Console.
    Returns a list of dicts: {'time', 'type', 'message', 'icon'}
    """
    raw_logs = read_log_tail(lines)
    events = []
    
    for line in raw_logs:
        # Extract timestamp
        ts_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if not ts_match:
            continue
            
        timestamp = ts_match.group(1).split(' ')[1] # HH:MM:SS
        msg_content = line.split(' - ')[-1].strip()
        
        event_type = 'INFO'
        icon = 'ℹ️'
        
        if 'ERROR' in line:
            event_type = 'ERROR'
            icon = '🚨'
        elif 'WARNING' in line:
            event_type = 'WARNING'
            icon = '⚠️'
        elif 'Opportunity' in msg_content:
            event_type = 'SIGNAL'
            icon = '🎯'
        elif 'BUY' in msg_content or 'born' in msg_content:
            event_type = 'ENTRY'
            icon = '🚀'
        elif 'SELL' in msg_content or 'died' in msg_content or 'Target hit' in msg_content:
            event_type = 'EXIT'
            icon = '💰'
        elif 'initialized' in msg_content:
            event_type = 'SYSTEM'
            icon = '🖥️'
            
        events.append({
            'time': timestamp,
            'type': event_type,
            'message': msg_content,
            'icon': icon,
            'raw': line
        })
        
    return events

def get_worker_statuses():
    """
    Returns a dictionary of worker statuses based on config.
    """
    config = read_config()
    workers = {}
    
    if config:
        # This assumes your config has sections ending in _STRATEGY logic
        # OR uses the worker list in [TRADING] if defined. 
        # Making it generic for now based on typical [SECTION] enabled=true
        
        for section in config.sections():
            if section.endswith('_STRATEGY'):
                name = section.replace('_STRATEGY', '').title()
                enabled = config.getboolean(section, 'enabled', fallback=False)
                workers[name] = {'status': 'active' if enabled else 'disabled'}
                
    return workers

def generate_mock_data():
    """Generates mock data for demonstration purposes."""
    import random
    
    # Mock Active Trades
    mock_trades = []
    
    tickers = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'SPY']
    strategies = ['Gap Go', 'Orb Breakout', 'Dip Buy']
    
    for _ in range(random.randint(1, 4)):
        symbol = random.choice(tickers)
        entry = random.uniform(100, 300)
        current = entry * random.uniform(0.98, 1.05)
        pnl = (current - entry) * 100 # Assuming 100 shares
        
        mock_trades.append({
            'symbol': symbol,
            'strategy': random.choice(strategies),
            'entry_price': entry,
            'current_price': current,
            'pnl': pnl,
            'entry_time': datetime.now().strftime('%H:%M:%S'),
            'quantity': 100,
            'side': 'BUY'
        })
        
    return pd.DataFrame(mock_trades)
    
def get_additional_metrics():
    """
    Get additional trading metrics for deeper analysis:
    - Sharpe Ratio
    - Max Drawdown
    - Average Trade Duration
    - Best/Worst Day
    - Consecutive Wins/Losses
    """
    conn = get_db_connection()
    try:
        # Get all closed trades
        df = pd.read_sql_query("""
            SELECT pnl, entry_time, exit_time, duration_minutes
            FROM trades
            WHERE status != 'OPEN' AND pnl IS NOT NULL AND exit_time IS NOT NULL
            ORDER BY exit_time ASC
        """, conn)
        conn.close()

        if df.empty:
            return {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'avg_duration_minutes': 0.0,
                'best_day_pnl': 0.0,
                'worst_day_pnl': 0.0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'current_streak': 0,
                'current_streak_type': 'None'
            }

        # Sharpe Ratio (assuming 252 trading days, 0% risk-free rate)
        if len(df) > 1:
            returns = df['pnl']
            sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # Max Drawdown
        df['cumulative_pnl'] = df['pnl'].cumsum()
        running_max = df['cumulative_pnl'].cummax()
        drawdown = df['cumulative_pnl'] - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / running_max.max() * 100) if running_max.max() > 0 else 0.0

        # Average Trade Duration
        avg_duration = df['duration_minutes'].mean()

        # Best/Worst Day
        df['exit_time'] = pd.to_datetime(df['exit_time'], format='mixed')
        df['date'] = df['exit_time'].dt.date
        daily_pnl = df.groupby('date')['pnl'].sum()
        best_day = daily_pnl.max() if not daily_pnl.empty else 0.0
        worst_day = daily_pnl.min() if not daily_pnl.empty else 0.0

        # Consecutive Wins/Losses
        df['is_win'] = df['pnl'] > 0
        max_consec_wins = 0
        max_consec_losses = 0
        current_streak = 0
        current_streak_type = 'None'

        if not df.empty:
            wins = 0
            losses = 0
            for is_win in df['is_win']:
                if is_win:
                    wins += 1
                    losses = 0
                    max_consec_wins = max(max_consec_wins, wins)
                else:
                    losses += 1
                    wins = 0
                    max_consec_losses = max(max_consec_losses, losses)

            # Current streak
            last_trades = df.tail(10)
            if not last_trades.empty:
                current_is_win = last_trades.iloc[-1]['is_win']
                current_streak = 1
                for i in range(len(last_trades) - 2, -1, -1):
                    if last_trades.iloc[i]['is_win'] == current_is_win:
                        current_streak += 1
                    else:
                        break
                current_streak_type = 'Wins' if current_is_win else 'Losses'

        return {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_duration_minutes': avg_duration,
            'best_day_pnl': best_day,
            'worst_day_pnl': worst_day,
            'max_consecutive_wins': max_consec_wins,
            'max_consecutive_losses': max_consec_losses,
            'current_streak': current_streak,
            'current_streak_type': current_streak_type
        }
    except Exception as e:
        print(f"Error fetching additional metrics: {e}")
        conn.close()
        return {
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'avg_duration_minutes': 0.0,
            'best_day_pnl': 0.0,
            'worst_day_pnl': 0.0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'current_streak': 0,
            'current_streak_type': 'None'
        }

def get_daily_pnl_series():
    """
    Get daily P&L for calendar heatmap visualization
    Returns DataFrame with date and daily_pnl columns
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT exit_time, pnl
            FROM trades
            WHERE status != 'OPEN' AND exit_time IS NOT NULL
            ORDER BY exit_time ASC
        """, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        df['exit_time'] = pd.to_datetime(df['exit_time'], format='mixed')
        df['date'] = df['exit_time'].dt.date
        daily_pnl = df.groupby('date')['pnl'].sum().reset_index()
        daily_pnl.columns = ['date', 'daily_pnl']
        return daily_pnl
    except Exception as e:
        print(f"Error fetching daily P&L series: {e}")
        conn.close()
        return pd.DataFrame()

def get_trade_duration_analysis():
    """
    Analyze trade durations and their correlation with P&L
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT duration_minutes, pnl, strategy
            FROM trades
            WHERE status != 'OPEN' AND duration_minutes IS NOT NULL
            ORDER BY duration_minutes ASC
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching duration analysis: {e}")
        conn.close()
        return pd.DataFrame()

def is_process_running(process_name="trader_main.py"):
    """Check if the trading process is running."""
    # Simple check using ps/grep
    try:
        # This is basic; psutil is better if installed
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            if process_name in ' '.join(proc.info['cmdline'] or []):
                return True
        return False
    except ImportError:
        # Fallback to shell if psutil missing (though it was used in emergency_kill.py so likely present)
        import subprocess
        try:
            res = subprocess.check_output(["pgrep", "-f", process_name])
            return True if res else False
        except subprocess.CalledProcessError:
            return False

# ===== MARKET CONTEXT FUNCTIONS =====

def get_market_indices():
    """
    Get current market indices data (SPY, QQQ, IWM, VIX)
    In production, this would fetch from live data source
    For now, returns mock data
    """
    # TODO: Integrate with real-time market data feed (IBKR, Alpha Vantage, etc.)
    return {
        'SPY_price': 450.25,
        'SPY_change': 0.75,
        'QQQ_price': 375.80,
        'QQQ_change': 1.20,
        'IWM_price': 195.40,
        'IWM_change': -0.35,
        'VIX': 16.50,
        'market_breadth': 125  # Advances - Declines
    }

def get_trading_session_info():
    """
    Get current trading session information
    """
    from datetime import datetime
    import pytz

    try:
        et_tz = pytz.timezone('US/Eastern')
        current_time_et = datetime.now(et_tz)
        current_hour = current_time_et.hour
        current_minute = current_time_et.minute

        # Determine market status
        market_open_time = 9 * 60 + 30  # 9:30 AM in minutes
        market_close_time = 16 * 60  # 4:00 PM in minutes
        current_minutes = current_hour * 60 + current_minute

        if market_open_time <= current_minutes < market_close_time:
            status = 'OPEN'
        elif 4 * 60 <= current_minutes < market_open_time:
            status = 'PRE-MARKET'
        elif market_close_time <= current_minutes < 20 * 60:
            status = 'AFTER-HOURS'
        else:
            status = 'CLOSED'

        # Check if weekend
        if current_time_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
            status = 'CLOSED (WEEKEND)'

        return {
            'market_status': status,
            'current_time': current_time_et.strftime('%I:%M %p'),
            'premarket_time': '4:00 AM - 9:30 AM',
            'regular_time': '9:30 AM - 4:00 PM',
            'afterhours_time': '4:00 PM - 8:00 PM'
        }
    except:
        return {
            'market_status': 'UNKNOWN',
            'current_time': 'N/A',
            'premarket_time': '4:00 AM - 9:30 AM',
            'regular_time': '9:30 AM - 4:00 PM',
            'afterhours_time': '4:00 PM - 8:00 PM'
        }

def get_sector_performance():
    """
    Get sector performance for today
    TODO: Integrate with real sector ETF data
    """
    return {
        'Technology': 1.25,
        'Healthcare': 0.45,
        'Financial': -0.30,
        'Energy': -1.10,
        'Consumer': 0.60,
        'Industrial': 0.20,
        'Materials': -0.15,
        'Utilities': 0.10,
        'Real Estate': -0.25,
        'Communication': 0.85
    }

def get_volume_metrics():
    """
    Get volume and liquidity metrics
    TODO: Integrate with real market data
    """
    return {
        'nyse_volume': 3500,  # in millions
        'nyse_vs_avg': 15,  # % vs 20-day average
        'nasdaq_volume': 4200,
        'nasdaq_vs_avg': 10,
        'new_highs': 42,
        'new_lows': 18
    }

def get_smallcap_movers(limit=5):
    """
    Get top smallcap movers for the day
    TODO: Integrate with scanner database
    """
    conn = get_db_connection()
    try:
        # Try to get from scanner_opportunities table
        query = """
        SELECT symbol, current_price as price, gap_percentage as change_pct,
               volume_ratio * 1000000 as volume, float_shares / 1000000 as float
        FROM scanner_opportunities
        WHERE timestamp >= date('now')
        ORDER BY ABS(gap_percentage) DESC
        LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()

        if df.empty:
            # Return mock data if no scanner data
            return pd.DataFrame({
                'symbol': ['EXAMPLE'],
                'price': [5.25],
                'change_pct': [15.5],
                'volume': [2500000],
                'float': [10.5]
            })

        return df
    except:
        conn.close()
        return pd.DataFrame()

def get_trading_conditions():
    """
    Calculate overall trading conditions score
    """
    market_data = get_market_indices()

    # Simple scoring logic (can be enhanced)
    spy_change = market_data.get('SPY_change', 0)
    iwm_change = market_data.get('IWM_change', 0)
    vix = market_data.get('VIX', 20)
    breadth = market_data.get('market_breadth', 0)

    # Trend score (0-100)
    trend_score = 50 + (spy_change * 10) + (breadth / 10)
    trend_score = max(0, min(100, trend_score))

    # Volatility score (0-100, higher = more volatile)
    volatility_score = min(100, vix * 3)

    # Opportunity score based on multiple factors
    opportunity_score = 50
    if iwm_change > 0.5:
        opportunity_score += 20
    if vix < 20:
        opportunity_score += 15
    if breadth > 100:
        opportunity_score += 15
    opportunity_score = max(0, min(100, opportunity_score))

    # Generate recommendation
    if trend_score > 60 and volatility_score < 50 and opportunity_score > 60:
        recommendation = "✅ Market conditions favorable for trading"
    elif trend_score < 40 or volatility_score > 70:
        recommendation = "⚠️ Exercise caution - Elevated risk environment"
    else:
        recommendation = "📊 Monitor market conditions - Neutral environment"

    return {
        'trend_score': int(trend_score),
        'volatility_score': int(volatility_score),
        'opportunity_score': int(opportunity_score),
        'recommendation': recommendation
    }

# ===== RISK MONITOR FUNCTIONS =====

def get_comprehensive_risk_metrics():
    """
    Get comprehensive risk metrics for risk monitor page
    """
    conn = get_db_connection()

    try:
        # Get active positions exposure
        active_df = pd.read_sql_query("""
            SELECT quantity, actual_entry_price, entry_price
            FROM trades WHERE status = 'OPEN'
        """, conn)

        current_exposure = 0
        if not active_df.empty:
            for _, row in active_df.iterrows():
                price = row['actual_entry_price'] if pd.notna(row['actual_entry_price']) else row['entry_price']
                current_exposure += row['quantity'] * price

        # Get daily P&L
        today_df = pd.read_sql_query("""
            SELECT SUM(actual_pnl) as daily_pnl
            FROM trades
            WHERE DATE(entry_time) = DATE('now') OR DATE(exit_time) = DATE('now')
        """, conn)
        daily_pnl = today_df['daily_pnl'].iloc[0] if not today_df.empty and pd.notna(today_df['daily_pnl'].iloc[0]) else 0

        # Get position count
        active_positions = len(active_df)

        # Calculate max concentration
        max_concentration = 0
        if current_exposure > 0 and not active_df.empty:
            exposures = []
            for _, row in active_df.iterrows():
                price = row['actual_entry_price'] if pd.notna(row['actual_entry_price']) else row['entry_price']
                exposures.append(row['quantity'] * price)
            if exposures:
                max_concentration = (max(exposures) / current_exposure * 100)

        conn.close()

        return {
            'current_exposure': current_exposure,
            'max_exposure': 10000,  # TODO: Get from config
            'daily_pnl': daily_pnl,
            'max_loss_limit': -500,  # TODO: Get from config
            'active_positions': active_positions,
            'max_positions': 5,  # TODO: Get from config
            'max_position_concentration': max_concentration
        }
    except Exception as e:
        print(f"Error getting risk metrics: {e}")
        conn.close()
        return {
            'current_exposure': 0,
            'max_exposure': 10000,
            'daily_pnl': 0,
            'max_loss_limit': -500,
            'active_positions': 0,
            'max_positions': 5,
            'max_position_concentration': 0
        }

def get_position_breakdown():
    """
    Get position breakdown for pie chart
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT symbol, quantity,
                   COALESCE(actual_entry_price, entry_price) as price
            FROM trades WHERE status = 'OPEN'
        """, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        df['exposure'] = df['quantity'] * df['price']
        return df[['symbol', 'exposure']]
    except:
        conn.close()
        return pd.DataFrame()

def get_risk_limits():
    """
    Get configured risk limits
    TODO: Read from config
    """
    return {
        'max_daily_loss': 500,
        'max_positions': 5,
        'max_exposure': 10000
    }

def get_position_risk_details():
    """
    Get detailed risk analysis for each position
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT symbol, strategy, quantity,
                   COALESCE(actual_entry_price, entry_price) as entry_price,
                   COALESCE(actual_pnl, 0) as unrealized_pnl,
                   stop_loss_price
            FROM trades WHERE status = 'OPEN'
        """, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        df['exposure'] = df['quantity'] * df['entry_price']

        # Calculate risk score (0-100, higher = riskier)
        df['risk_score'] = 50  # Base score

        # Calculate distance to stop loss
        df['distance_to_stop'] = 0
        if 'stop_loss_price' in df.columns:
            mask = pd.notna(df['stop_loss_price']) & (df['stop_loss_price'] > 0)
            df.loc[mask, 'distance_to_stop'] = ((df.loc[mask, 'entry_price'] - df.loc[mask, 'stop_loss_price']) / df.loc[mask, 'entry_price'] * 100)

        df['stop_loss'] = df['stop_loss_price'].fillna(0)

        return df[['symbol', 'strategy', 'exposure', 'unrealized_pnl', 'risk_score', 'stop_loss', 'distance_to_stop']]
    except Exception as e:
        print(f"Error getting position risk details: {e}")
        conn.close()
        return pd.DataFrame()

def get_drawdown_series():
    """
    Get drawdown series for chart
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT DATE(exit_time) as date, SUM(pnl) as daily_pnl
            FROM trades
            WHERE status != 'OPEN' AND exit_time IS NOT NULL
            GROUP BY DATE(exit_time)
            ORDER BY date ASC
        """, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        df['cumulative_pnl'] = df['daily_pnl'].cumsum()
        df['running_max'] = df['cumulative_pnl'].cummax()
        df['drawdown'] = ((df['cumulative_pnl'] - df['running_max']) / df['running_max'] * 100).fillna(0)

        return df[['date', 'drawdown']]
    except:
        conn.close()
        return pd.DataFrame()

def get_risk_distribution():
    """
    Get risk distribution (low, medium, high risk positions)
    """
    # Mock data for now
    return {
        'Low Risk': 2,
        'Medium Risk': 1,
        'High Risk': 0
    }

def get_active_risk_alerts():
    """
    Get currently active risk alerts
    """
    alerts = []

    # Check risk metrics and generate alerts
    risk_metrics = get_comprehensive_risk_metrics()

    # Check exposure
    exposure_pct = (risk_metrics['current_exposure'] / risk_metrics['max_exposure'] * 100) if risk_metrics['max_exposure'] > 0 else 0
    if exposure_pct > 90:
        alerts.append({
            'severity': 'critical',
            'title': 'Capital Utilization Critical',
            'message': f"Using {exposure_pct:.1f}% of available capital. Consider reducing exposure.",
            'timestamp': datetime.now().strftime('%I:%M %p')
        })
    elif exposure_pct > 80:
        alerts.append({
            'severity': 'warning',
            'title': 'High Capital Utilization',
            'message': f"Using {exposure_pct:.1f}% of available capital.",
            'timestamp': datetime.now().strftime('%I:%M %p')
        })

    # Check daily loss
    if risk_metrics['daily_pnl'] < risk_metrics['max_loss_limit']:
        alerts.append({
            'severity': 'critical',
            'title': 'Daily Loss Limit Breached',
            'message': f"Daily P&L (${risk_metrics['daily_pnl']:.2f}) exceeded max loss limit (${risk_metrics['max_loss_limit']:.2f}).",
            'timestamp': datetime.now().strftime('%I:%M %p')
        })

    return alerts

# ===== ALERTS FUNCTIONS =====

ALERTS_FILE = "data/alerts_history.json"

def get_recent_alerts(limit=20):
    """
    Get recent alerts from history
    """
    import json

    # Check for active risk alerts first
    risk_alerts = get_active_risk_alerts()

    # Try to load from file
    try:
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, 'r') as f:
                all_alerts = json.load(f)

            # Combine with risk alerts
            all_alerts = risk_alerts + all_alerts
            return all_alerts[:limit]
    except:
        pass

    # Return mock data if no file or error
    return risk_alerts if risk_alerts else []

def save_alert_config(config_type, config_data):
    """
    Save alert configuration
    TODO: Implement persistent storage
    """
    import json

    config_file = f"data/alert_config_{config_type}.json"
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    try:
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving alert config: {e}")
        return False

def get_alert_statistics():
    """
    Get alert statistics for the dashboard
    """
    alerts = get_recent_alerts(limit=100)

    critical = sum(1 for a in alerts if a.get('severity') == 'critical')
    warnings = sum(1 for a in alerts if a.get('severity') == 'warning')
    info_count = sum(1 for a in alerts if a.get('severity') == 'info')

    # Find most frequent type
    categories = [a.get('category', 'Unknown') for a in alerts]
    most_frequent = max(set(categories), key=categories.count) if categories else 'N/A'

    return {
        'total_24h': len(alerts),
        'critical': critical,
        'warnings': warnings,
        'info': info_count,
        'most_frequent_type': most_frequent
    }

def clear_alerts_history():
    """
    Clear alerts history
    """
    try:
        if os.path.exists(ALERTS_FILE):
            os.remove(ALERTS_FILE)
        return True
    except:
        return False
