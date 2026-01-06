#!/usr/bin/env python3
"""
Worker Lab Runner
=================
Script to run a specific worker logic against historical data for testing and debugging.
Exposes results as JSON for the TradeTally UI.

Usage:
    python3 run_worker_test.py --worker [worker_name] --symbol [symbol] --date [YYYY-MM-DD]
"""

import sys
import json
import argparse
import asyncio
import logging

# --- CRITICAL: Redirect all stdout to stderr to prevent JSON corruption ---
# Some modules print() during import. We must catch this.
class StderrRedirect:
    def write(self, message):
        sys.stderr.write(message)
    def flush(self):
        sys.stderr.flush()

original_stdout = sys.stdout
# sys.stdout = StderrRedirect()
# --------------------------------------------------------------------------

import sqlite3
import numpy as np
import traceback
import pytz
from datetime import datetime, time, timedelta, timezone, date

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load configuration globally
import configparser
config = configparser.ConfigParser()
config.read(PROJECT_ROOT / 'config.ini')

# Import strategies
from strategies.workers.orb_worker_logic import ORBWorkerLogic
# GapGo logic seems to be within the strategy file or different name, removing for now if not found
# from strategies.workers.gap_go_worker_logic import GapGoWorkerLogic 
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
from strategies.workers.buy_the_dip_worker_logic import BuyTheDipWorkerLogic
from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
from strategies.workers.livermore_intraday_worker_logic import LivermoreIntradayWorkerLogic
from strategies.workers.parabolic_worker_logic import ParabolicWorkerLogic
from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from strategies.workers.gap_fade_worker_logic import GapFadeWorkerLogic
from strategies.workers.buy_and_hold_worker_logic import BuyAndHoldWorkerLogic
from strategies.workers.holy_grail_worker_logic import HolyGrailWorkerLogic
from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic
from strategies.workers.smallcaps_short_reversal_worker_logic import SmallCapsShortReversalWorkerLogic
from strategies.workers.catalyst_dna_worker_logic import CatalystDNAWorkerLogic
from strategies.workers.smallcaps_long_worker_logic import SmallCapsLongWorkerLogic
from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic
from strategies.workers.balance_day_worker_logic import BalanceDayWorkerLogic
from strategies.workers.generic_01_worker_logic import Generic01WorkerLogic
from strategies.workers.outlier_penny_extreme_worker_logic import OutlierPennyExtremeWorkerLogic
from strategies.workers.ods_universal_worker_logic import ODSUniversalWorkerLogic
from strategies.workers.ods_swing_universal_worker_logic import ODSSwingUniversalWorkerLogic
from strategies.workers.vcp_strict_long_worker_logic import VCPStrictLongWorkerLogic
from strategies.workers.vcp_strict_short_worker_logic import VCPStrictShortWorkerLogic
from strategies.workers.trend_surfer_worker_logic import TrendSurferWorkerLogic
# Import daily_plays_midcap if it exists, otherwise map to daily_plays or generic?
# Assuming daily_plays_midcap_worker_logic.py exists or is same class with different config
try:
    from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidcapWorkerLogic
except ImportError:
    DailyPlaysMidcapWorkerLogic = DailyPlaysWorkerLogic # Fallback

# Map names to classes
WORKER_MAP = {
    'orb': ORBWorkerLogic,
    'daily_plays': DailyPlaysWorkerLogic,
    'daily_plays_midcap': DailyPlaysMidcapWorkerLogic,
    'buy_the_dip': BuyTheDipWorkerLogic,
    'volume_absorption': VolumeAbsorptionWorkerLogic,
    'vcp_smallcap': VCPSmallcapWorkerLogic,
    'livermore_intraday': LivermoreIntradayWorkerLogic,
    'parabolic': ParabolicWorkerLogic,
    'short_parabolic': ShortParabolicWorkerLogic,
    'short_squeeze': ShortSqueezeWorkerLogic,
    'gap_fade': GapFadeWorkerLogic,
    'buy_and_hold': BuyAndHoldWorkerLogic,
    'holy_grail': HolyGrailWorkerLogic,
    'smallcaps_long': SmallCapsLongWorkerLogic,
    'smallcaps_short_reversal': SmallCapsShortReversalWorkerLogic,
    'catalyst_dna': CatalystDNAWorkerLogic,
    'vwap': VWAPWorkerLogic,
    'momentum_breakout': MomentumBreakoutWorkerLogic,
    'balance_day': BalanceDayWorkerLogic,
    'generic_01': Generic01WorkerLogic,
    'outlier_penny_extreme': OutlierPennyExtremeWorkerLogic,
    'ods_universal': ODSUniversalWorkerLogic,
    'ods_swing_universal': ODSSwingUniversalWorkerLogic,
    'vcp_strict_long': VCPStrictLongWorkerLogic,
    'vcp_strict_short': VCPStrictShortWorkerLogic,
    'trend_surfer': TrendSurferWorkerLogic
}

class MockExecutionEngine:
    """Mock execution engine for testing"""
    def __init__(self, broker=None):
        self.worker_positions = {}
        self.broker = broker # Mock if needed

    async def enter_position(self, symbol, strategy, opportunity_data, **kwargs):
        """Mock enter_position method for WorkerLab testing"""
        # Extract entry price from opportunity data
        entry_price = opportunity_data.get('current_price', 0)

        # Return a mock position object matching the expected format
        return {
            'symbol': symbol,
            'strategy': strategy,
            'quantity': 100,  # Mock quantity
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'status': 'FILLED',
            'order_id': f'MOCK_{symbol}_{int(datetime.now().timestamp())}'
        }

class MockRiskManager:
    """Mock risk manager for testing"""
    def __init__(self):
        self.broker_positions = {}
        
    async def check_entry(self, *args, **kwargs):
        return True

class JsonLogHandler(logging.Handler):
    """Log handler that captures logs in memory"""
    def __init__(self):
        super().__init__()
        self.logs = []
        self.current_bar_time = None  # Will be set during simulation loop

    def emit(self, record):
        try:
            msg = self.format(record)
            # Use bar time if available, otherwise system time
            if self.current_bar_time:
                # Convert to ET timezone for display
                et_tz = pytz.timezone('America/New_York')
                bar_time_et = self.current_bar_time

                # Ensure timezone aware
                if bar_time_et.tzinfo is None:
                    bar_time_et = pytz.utc.localize(bar_time_et)

                # Convert to ET
                bar_time_et = bar_time_et.astimezone(et_tz)
                time_str = bar_time_et.strftime('%H:%M ET')
            else:
                time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

            self.logs.append({
                'time': time_str,
                'level': record.levelname,
                'message': msg
            })
        except Exception:
            self.handleError(record)

def resample_bars(bars, timeframe_str):
    """
    Resample bars to a different timeframe.
    Timeframe format: '1m', '5m', '15m'.
    """
    if not bars or not timeframe_str or timeframe_str == '1m':
        return bars
        
    try:
        minutes = int(timeframe_str.replace('m', ''))
    except:
        return bars
        
    if minutes <= 1:
        return bars

    from strategies.workers.base_worker_logic import BarDataWrapper
    
    resampled = []
    bucket_bars = []
    bucket_ts_limit = None
    
    # Ensure bars are sorted
    sorted_bars = sorted(bars, key=lambda b: b.timestamp)
    
    for bar in sorted_bars:
        ts = bar.timestamp
        # Calculate bucket start time (floor to nearest N minutes)
        # Minute 0-4 -> 0, 5-9 -> 5
        bucket_minute = (ts.minute // minutes) * minutes
        bucket_start = ts.replace(minute=bucket_minute, second=0, microsecond=0)
        
        # Logic to handle bucket transition
        if bucket_ts_limit is None or bucket_start != bucket_ts_limit:
            # Close previous bucket
            if bucket_bars:
                resampled.append(_create_aggregated_bar(bucket_bars, bucket_ts_limit, BarDataWrapper))
            
            # Start new bucket
            bucket_bars = []
            bucket_ts_limit = bucket_start
            
        bucket_bars.append(bar)
        
    # Close last bucket
    if bucket_bars:
        resampled.append(_create_aggregated_bar(bucket_bars, bucket_ts_limit, BarDataWrapper))
        
    return resampled

def _create_aggregated_bar(bars, timestamp, wrapper_class):
    o = bars[0].open
    h = max(b.high for b in bars)
    l = min(b.low for b in bars)
    c = bars[-1].close
    v = sum(b.volume for b in bars)
    
    return wrapper_class({
        'timestamp': timestamp,
        'open': o,
        'high': h,
        'low': l,
        'close': c,
        'volume': v
    })


def get_market_bars(symbol, date_str):
    """
    Obtiene barras de mercado de trading_data.db desde trade_ohlc_snapshots
    Similar logic to analyze_worker_with_charts.py but focuses on getting raw data
    """
    db_path = PROJECT_ROOT / 'trading_data.db'
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    query = """
    SELECT intraday_bars, trading_date
    FROM trade_ohlc_snapshots
    WHERE symbol = ?
        AND trading_date = ?
    ORDER BY created_at DESC
    LIMIT 1
    """

    cursor.execute(query, (symbol, date_str))
    row = cursor.fetchone()

    if row and row[0]:
        import json as json_lib
        bars_data = json_lib.loads(row[0])
        
        if bars_data:
            from strategies.workers.base_worker_logic import BarDataWrapper
            bars_objects = []
            for b in bars_data:
                if isinstance(b['timestamp'], str):
                     try:
                         b['timestamp'] = datetime.fromisoformat(b['timestamp'].replace('Z', '+00:00'))
                     except:
                         pass
                bars_objects.append(BarDataWrapper(b))
            conn.close()
            return bars_objects

    # Fallback: Check trade_intraday_bars
    # This matches the logic in forensic_bridge.py
    query_fallback = """
        SELECT b.bar_timestamp, b.open_price, b.high_price, b.low_price, b.close_price, b.volume 
        FROM trade_intraday_bars b
        JOIN trades t ON b.trade_id = t.trade_id
        WHERE t.symbol = ? AND date(b.bar_timestamp) = ?
        ORDER BY b.bar_timestamp ASC
    """
    cursor.execute(query_fallback, (symbol, date_str))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    from strategies.workers.base_worker_logic import BarDataWrapper
    bars_objects = []
    
    for row in rows:
        ts_str = row[0]
        try:
            dt = datetime.fromisoformat(ts_str)
        except:
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            
        # Ensure timezone awareness (assume UTC if naive, or match system)
        # Using +00:00 for consistency with snapshots
        if dt.tzinfo is None:
             dt = dt.replace(tzinfo=timezone.utc)
             
        bars_objects.append(BarDataWrapper({
            'timestamp': dt,
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'volume': row[5]
        }))

    return bars_objects

def get_real_trades(symbol, date_str):
    """
    Fetches real trades from the production database (trading_system_v3_A)
    """
    prod_db_path = PROJECT_ROOT.parent / 'trading_system_v3_A' / 'trading_data.db'
    if not prod_db_path.exists():
        # Fallback to local db if prod not found (for single repo setup)
        prod_db_path = PROJECT_ROOT / 'trading_data.db'
        
    if not prod_db_path.exists(): return []

    try:
        conn = sqlite3.connect(str(prod_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            conn.close()
            return []

        query = """
            SELECT entry_time, entry_price, actual_entry_price, exit_price, 
                   actual_exit_price, exit_time, side, quantity, pnl, strategy, commission 
            FROM trades 
            WHERE symbol = ? AND date(entry_time) = date(?) 
            ORDER BY entry_time ASC
        """
        cursor.execute(query, (symbol.upper(), date_str))
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        madrid = pytz.timezone('Europe/Madrid')
        
        for r in rows:
            d = dict(r)
            # Use actual prices if available
            if d['actual_entry_price']: d['entry_price'] = d['actual_entry_price']
            if d['actual_exit_price']: d['exit_price'] = d['actual_exit_price']
            
            # Normalize dates
            for f in ['entry_time', 'exit_time']:
                if d[f]:
                   try:
                       # Handle various formats
                       ts = d[f].split('+')[0].replace('Z','')
                       dt = datetime.fromisoformat(ts)
                       if dt.tzinfo is None:
                           # DB stores naive time in Europe/Madrid (Legacy behavior)
                           # Must localize to Madrid, then convert to UTC for valid ISO
                           dt = madrid.localize(dt)
                       
                       # Ensure it's UTC for JSON output
                       dt_utc = dt.astimezone(pytz.utc)
                       d[f] = dt_utc.isoformat()
                   except: 
                       # Fallback to keep original string if parsing fails
                       pass
            trades.append(d)
        return trades
    except Exception as e:
        print(f"Error fetching real trades: {e}", file=sys.stderr)
        return []

def get_historical_scanner_data(symbol, date_str):
    """
    Fetch full scanner data for the symbol on the given date.
    Returns dict with gap, volume_ratio, etc. defaulting to None if not found.
    """
    db_path = PROJECT_ROOT / 'trading_data.db'
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get first scanner detection for this symbol on this date
        query = """
            SELECT gap_percentage, volume_ratio, quality_score, catalyst_type, timestamp
            FROM scanner_opportunities
            WHERE symbol = ? AND date(timestamp) = date(?)
            ORDER BY timestamp ASC
            LIMIT 1
        """

        cursor.execute(query, (symbol.upper(), date_str))
        row = cursor.fetchone()
        conn.close()

        if row:
            # Convert row to dict and ensure timestamp is ISO
            data = dict(row)
            # Handle timestamp conversion if needed
            ts = data.get('timestamp')
            if ts and 'T' not in str(ts): # Simple check if likely not ISO
                 try:
                     # Try to convert common sql formats
                      dt = datetime.strptime(str(ts), '%Y-%m-%d %H:%M:%S')
                      data['timestamp'] = dt.isoformat()
                 except: pass # Keep as is
            return data

        return {}

    except Exception as e:
        print(f"Warning: Could not fetch scanner data: {e}", file=sys.stderr)
        return {}

def calculate_advanced_metrics(completed_trades, max_drawdown, initial_cash):
    """
    Calculate advanced performance metrics from completed trades.
    
    Args:
        completed_trades: List of trade dictionaries
        max_drawdown: Maximum drawdown percentage observed
        initial_cash: Starting capital
        
    Returns:
        Dictionary of advanced metrics
    """
    if not completed_trades:
        return {
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'expectancy': 0.0,
            'expectancy_pct': 0.0,
            'risk_reward_ratio': 0.0,
            'recovery_factor': 0.0,
            'avg_trade_duration_minutes': 0.0,
            'sharpe_ratio': 0.0,
            'max_win_streak': 0,
            'max_loss_streak': 0,
            'max_drawdown_pct': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0
        }
    
    # Separate wins and losses
    wins = [t for t in completed_trades if t['is_win']]
    losses = [t for t in completed_trades if not t['is_win']]
    
    # Win Rate
    win_rate = (len(wins) / len(completed_trades)) * 100
    
    # Profit Factor
    gross_profit = sum(t['pnl'] for t in wins) if wins else 0
    gross_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.99 if gross_profit > 0 else 0.0
    
    # Average Win/Loss
    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    
    # Largest Win/Loss
    largest_win = max((t['pnl'] for t in wins), default=0)
    largest_loss = min((t['pnl'] for t in losses), default=0)
    
    # Expectancy (Dollar)
    expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
    
    # Expectancy % (Per trade)
    returns_pct = [(t['exit_price'] - t['entry_price']) / t['entry_price'] * 100 for t in completed_trades]
    expectancy_pct = np.mean(returns_pct) if returns_pct else 0
    
    # Risk/Reward (R)
    risk_reward = avg_win / avg_loss if avg_loss > 0 else 999.99 if avg_win > 0 else 0.0
    
    # Recovery Factor (PnL / Max Drawdown Amount)
    total_pnl = sum(t['pnl'] for t in completed_trades)
    # Calculate Max DD in Dollars (simplified based on max_drawdown_pct and peak equity)
    # Actually, it's better to pass peak_drawdown_amount if we had it.
    # For now, if max_drawdown is 0, recovery factor is info or 0.
    recovery_factor = total_pnl / (abs(max_drawdown) * initial_cash / 100) if max_drawdown > 0 else (total_pnl if total_pnl > 0 else 0)

    # Average Trade Duration
    avg_duration = sum(t['duration_minutes'] for t in completed_trades) / len(completed_trades)
    
    # Sharpe Ratio (simplified for intraday)
    returns = [t['pnl'] / initial_cash for t in completed_trades]
    avg_return = np.mean(returns) if returns else 0
    std_return = np.std(returns) if len(returns) > 1 else 0
    sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0  # Annualized
    
    # Consecutive Wins/Losses
    streaks = []
    current_streak = 0
    for t in completed_trades:
        if t['is_win']:
            current_streak = current_streak + 1 if current_streak > 0 else 1
        else:
            current_streak = current_streak - 1 if current_streak < 0 else -1
        streaks.append(current_streak)
    
    max_win_streak = max((s for s in streaks if s > 0), default=0)
    max_loss_streak = abs(min((s for s in streaks if s < 0), default=0))
    
    return {
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'largest_win': round(largest_win, 2),
        'largest_loss': round(largest_loss, 2),
        'expectancy': round(expectancy, 2),
        'expectancy_pct': round(expectancy_pct, 2),
        'risk_reward_ratio': round(risk_reward, 2),
        'recovery_factor': round(recovery_factor, 2),
        'avg_trade_duration_minutes': round(avg_duration, 2),
        'sharpe_ratio': round(sharpe, 2),
        'max_win_streak': max_win_streak,
        'max_loss_streak': max_loss_streak,
        'max_drawdown_pct': round(max_drawdown, 2),
        'total_trades': len(completed_trades),
        'winning_trades': len(wins),
        'losing_trades': len(losses)
    }



class MockConfig:
    def __init__(self, overrides=None):
        self.config = config
        self.overrides = overrides or {}
        
        # Inject dynamic overrides into config object if needed for direct access
        # But mostly workers use .get()
        
    def __getattr__(self, name):
        # 1. Check overrides first
        if name in self.overrides:
            return self.overrides[name]
            
        # 2. Check underlying config object
        if hasattr(self.config, name):
             return getattr(self.config, name)
             
        # 3. Defaults for known attributes logic expects (if missing in config object)
        # These are commonly accessed directly by some workers
        known_defaults = {
            'premarket_start': "04:00",
            'premarket_end': "09:30", 
            'market_open_time': "09:30",
            'market_close_time': "16:00",
            'afterhours_start': "16:00",
            'afterhours_end': "20:00",
            'no_entry_after': 15.75,
            'max_position_value': 2000.0,
            'max_daily_loss_pct': 5.0
        }

        if name in known_defaults:
             try:
                 val = self.config.get('GLOBAL', name)
                 if name == 'no_entry_after': return float(val)
                 return val
             except:
                 return known_defaults[name]
                 
        raise AttributeError(f"'MockConfig' object has no attribute '{name}'")

    def get(self, key, default=None):
        """Intercept get calls to check overrides first"""
        if key in self.overrides:
            return self.overrides[key]
        
        # Check if attribute was set directly (like .timeframe)
        if key in self.__dict__:
            return self.__dict__[key]
            
        # Fallback to underlying config
        # This assumes the underlying config.get can handle a single key argument
        # which is not typical for configparser.ConfigParser.get.
        # It's safer to assume this `get` is for direct attribute access or a simplified config.
        if hasattr(self.config, 'get') and len(self.config.get.__code__.co_varnames) <= 2: # Check if it expects only key and default
            return self.config.get(key, default)
        
        # If the underlying config.get expects section, or if it's not a method,
        # try to get it as an attribute.
        return getattr(self, key, default)
        
    def get_section_key(self, section, key, fallback=None): # Renamed to avoid conflict
        if key in self.overrides:
            return self.overrides[key]
        return self.config.get(section, key, fallback)

    def getfloat(self, section, key, fallback=None):
        if key in self.overrides:
            val = self.overrides[key]
            try: return float(val)
            except: pass
            
        # Manual fallback to avoid RawConfigParser issues (takes 3 positional args error)
        try:
            val = self.config.get(section, key)
            return float(val)
        except:
            return fallback

    def getint(self, section, key, fallback=None):
        if key in self.overrides:
            val = self.overrides[key]
            try: return int(val)
            except: pass
            
        try:
            val = self.config.get(section, key)
            return int(val)
        except:
            return fallback

    def getboolean(self, section, key, fallback=None):
        if key in self.overrides:
             val = self.overrides[key]
             if isinstance(val, bool): return val
             return str(val).lower() in ('true', '1', 'yes', 'on')
             
        # Mock specific extended hours behavior if not overridden
        val_bool = self._manual_getboolean(section, key, fallback)
        
        if key == 'enable_extended_hours_trading':
             return getattr(self, 'enable_extended_hours_trading', val_bool)
        if key == 'allow_premarket_entries':
             return getattr(self, 'allow_premarket_entries', val_bool)
             
        return val_bool

    def _manual_getboolean(self, section, key, fallback):
        try:
            val = self.config.get(section, key)
            if isinstance(val, bool): return val
            return str(val).lower() in ('true', '1', 'yes', 'on')
        except:
            return fallback

async def run_worker_simulation(worker_name, symbol, date_str, momentum_indicator=None, extended_hours=True, config_overrides=None, cached_data=None, pos_value=None, pos_size=None, timeframe='1m'):
    """
    Runs a simulation for a specific worker on a specific day using historical data.

    Args:
        worker_name: Name of the worker to test
        symbol: Stock symbol
        date_str: Date in YYYY-MM-DD format
        momentum_indicator: 'vwap_slope' or 'roc' (defaults to 'roc' if not specified)
        extended_hours: Boolean indicating whether to enable extended hours trading.
    """
    result = {
        'status': 'error',
        'logs': [],
        'decisions': [],
        'indicators': [],
        'chart_data': [],
        'scanner_detection_time': None,
        'summary': {
            'realized_pnl': 0.0,
            'open_pnl': 0.0,
            'total_pnl': 0.0,
            'gross_pnl': 0.0,
            'total_commission': 0.0,
            'trades_count': 0,
            'win_rate': 0.0
        },
        'summary_real': {
            'total_pnl': 0.0,
            'trades_count': 0,
            'win_rate': 0.0
        },
        'real_trades': []
    }

    # --- SIMULATION CONFIGURATION ---
    SIM_SLIPPAGE_PCT = 0.001       # 0.1% Slippage default
    SIM_COMMISSION_MIN = 1.0       # $1.00 minimum commission
    SIM_COMMISSION_PER_SHARE = 0.005 # $0.005 per share
    
    # Setup logging capture
    log_handler = JsonLogHandler()
    log_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    log_handler.setFormatter(formatter)

    # Get the worker class
    worker_class = WORKER_MAP.get(worker_name)
    if not worker_class:
        result['error'] = f"Unknown worker: {worker_name}"
        return result

    # Instantiate worker with mocks
    engine = MockExecutionEngine()
    risk = MockRiskManager()
    
    # Normalize timeframe (1min -> 1m, 5min -> 5m)
    timeframe = timeframe.replace('min', 'm')

    # Ensure timeframe is in overrides so MockConfig.get() finds it
    if config_overrides is None:
        config_overrides = {}
    config_overrides['timeframe'] = timeframe

    # Use the versatile MockConfig with overrides
    mock_config = MockConfig(overrides=config_overrides)
    
    # Manually inject dynamic attributes that logic requires directly as attributes (not just .get())
    mock_config.enable_extended_hours_trading = extended_hours
    mock_config.allow_premarket_entries = extended_hours
    mock_config.timeframe = timeframe # CRITICAL: Inform worker of the actual timeframe
    
    # Set default values for other attributes if they are not in config.ini or overrides
    # (These were hardcoded in the old nested class, now we rely on config.ini + overrides,
    # but for safety we can set defaults if needed, or let worker logic handle defaults)
    # For now, we trust config.ini + overrides.
            

    
    try:
        # Instantiate worker
        # Different workers might have different signatures.
        # Base expects: worker_name, execution_engine, risk_manager, config
        # But derived classes might hardcode worker_name or expect other args.
        
        # Prepare SimulatedBroker
        from core.brokers.simulated_broker import SimulatedBroker
        sim_broker = SimulatedBroker(initial_cash=100000.0)
        
        # Determine instantiation method
        try:
            # Try with broker argument + worker_name (Generic/Base Workers)
            worker = worker_class(
                worker_name=worker_name,
                broker=sim_broker,
                risk_manager=risk,
                config=mock_config
            )
        except TypeError:
            # Try with broker argument WITHOUT worker_name (Refactored Specific Workers)
            try:
                worker = worker_class(
                    broker=sim_broker,
                    risk_manager=risk,
                    config=mock_config
                )
            except TypeError as e:
                # Try Positional Arguments (broker, risk, config, execution_engine=None)
                # This fixes issues where keyword names might mismatch in subclassing chains
                try:
                    worker = worker_class(sim_broker, risk, mock_config)
                except TypeError as e2:
                    # DEBUG: Silent now, assume fallback or error out naturally
                    pass
                    
                    # Fallback for legacy workers that strictly require execution_engine
                print(f"⚠️ Worker init failed with broker, trying legacy keys: {e}")
                try:
                    worker = worker_class(
                        worker_name=worker_name,
                        execution_engine=engine,
                        risk_manager=risk,
                        config=mock_config
                    )
                except TypeError:
                    # Last resort (legacy, no worker_name arg)
                    worker = worker_class(
                        execution_engine=engine,
                        risk_manager=risk,
                        config=mock_config
                    )
            
        # Override logger to capture output
        worker.logger.addHandler(log_handler)
        worker.logger.setLevel(logging.DEBUG)
        
        worker.set_replay_date(date_str)
        
        # Get historical data (Use Cache if available)
        if cached_data:
            bars = cached_data.get('bars', [])
        else:
            bars = get_market_bars(symbol, date_str)
            
        # Apply Resampling if requested
        if timeframe != '1m':
            worker.logger.info(f"⌛ Resampling bars to {timeframe}...")
            bars = resample_bars(bars, timeframe)
            
        if not bars:
            result['error'] = f"No data found for {symbol} on {date_str}"
            # Add logs captured so far
            result['logs'] = log_handler.logs
            return result

        worker.logger.info(f"Loaded {len(bars)} bars for {symbol}")

        # Get scanner detection data for visualization and logic
        if cached_data:
            scanner_data = cached_data.get('scanner_data', {})
        else:
            scanner_data = get_historical_scanner_data(symbol, date_str)
        
        scanner_detection_time = scanner_data.get('timestamp')
        result['scanner_detection_time'] = scanner_detection_time
        
        if scanner_detection_time:
            worker.logger.info(f"📡 Scanner first detected {symbol} at {scanner_detection_time}")
            if 'gap_percentage' in scanner_data:
                worker.logger.info(f"   Gap: {scanner_data['gap_percentage']}% | Vol Ratio: {scanner_data.get('volume_ratio')}")

        # Calculate Real Trades Summary
        if cached_data:
            real_trades = cached_data.get('real_trades', [])
        else:
            real_trades = get_real_trades(symbol, date_str)
        result['real_trades'] = real_trades
        
        real_total_pnl = 0.0
        real_realized_pnl = 0.0
        real_open_pnl = 0.0
        real_trades_count = len(real_trades)
        real_winning_trades = 0
        
        # Get last price for Open PnL calculation
        last_price = bars[-1].close if bars else 0.0

        for t in real_trades:
            # PnL is usually stored in DB. 
            # If closed, it's realized. If open, it might be None or 0.
            pnl = t.get('pnl') or 0.0
            
            # Check if trade is closed (has exit time)
            is_closed = t.get('exit_time') is not None
            
            if is_closed:
                real_realized_pnl += pnl
                if pnl > 0:
                    real_winning_trades += 1
            else:
                # Estimate Open PnL if not provided
                entry_price = t.get('entry_price') or t.get('actual_entry_price')
                quantity = t.get('quantity')
                if entry_price and quantity and last_price > 0:
                     # Simple Open PnL calc
                     est_open_pnl = (last_price - entry_price) * quantity
                     real_open_pnl += est_open_pnl
                elif pnl != 0:
                     # Use DB value if provided even if open
                     real_open_pnl += pnl

        real_total_pnl = real_realized_pnl + real_open_pnl
        real_win_rate = (real_winning_trades / real_trades_count * 100) if real_trades_count > 0 else 0.0

        result['summary_real'] = {
            'total_pnl': round(real_total_pnl, 2),
            'realized_pnl': round(real_realized_pnl, 2),
            'open_pnl': round(real_open_pnl, 2),
            'trades_count': real_trades_count,
            'win_rate': round(real_win_rate, 1)
        }

        # --- SIMULATION LOOP ---
        # We need to simulate the "process_opportunity" call which is normally driven by the scanner.
        # But we also have "monitor_positions".
        # For simplicity in this "Lab", we will iterate through bars and "trigger" the worker logic
        # as if the scanner found an opportunity at each new bar (or N bars).
        
        # Prepare chart data
        chart_data = []
        
        # PnL Tracking
        initial_cash = 100000.0  # Starting capital
        realized_pnl = 0.0
        cum_gross_pnl = 0.0
        cum_commission = 0.0
        trades_count = 0
        winning_trades = 0
        
        # Advanced Metrics Tracking
        equity_curve = []  # List of {timestamp, equity}
        completed_trades = []  # List of detailed trade records
        peak_equity = initial_cash
        max_drawdown = 0.0
        
        # Active position tracking for trade records
        active_entry_time = None
        active_entry_price_for_record = None


        # --- MOCKS FOR SPEED ---
        async def mock_fundamentals(*args, **kwargs):
            return {
                'float_shares': 10000000,
                'rotation_factor': 0.5,
                'is_high_rotation': False,
                'pmh': 0.0,
                'dist_to_pmh': 99.0,
                'luld_high': 999.0,
                'dist_to_halt': 99.0,
                'is_halt_risk': False
            }
        worker._analyze_smallcap_fundamentals = mock_fundamentals

        async def mock_daily(*args, **kwargs):
            return {
                'can_swing': False,
                'can_swing_short': True,
                'reasons': [],
                'rsi_daily': 50,
                'distance_to_resistance': 100,
                'distance_to_support': 100,
                'smart_resistance': {'level': None, 'type': 'NONE', 'distance_pct': 999.0}
            }
        worker._analyze_daily_potential_for_signal = mock_daily
        
        # --- MONKEY PATCH FOR VISUALIZATION GUARANTEE ---
        # User wants to see "The Entry Point". Strict VCP logic often rejects random data.
        # We override should_enter to FORCE an entry for specific timestamps/conditions
        # to ensure the UI elements (White Line, Arrows) are rendered.
        
        original_should_enter = worker.should_enter
        
        async def forced_should_enter(opportunity):
            # Try original logic first (so logs are generated)
            result = await original_should_enter(opportunity)
            
            # If rejected, FORCE entry if we are in a "nice" spot (e.g. middle of chart)
            # Enabled for ALL workers in Lab to ensure visualization if strategy is strict
            # DISABLE FORCED ENTRY NOW THAT VISUALIZATION IS CONFIRMED
            if not result and False: # DISABLED to show REAL strategy results
                # Check for "fake" VCP conditions to trigger just for visualization
                # Trigger around bar 50-60 if not entered yet
                bars_len = len(opportunity.get('bars', []))
                # Only force once to avoid spamming entries (though active_positions prevents duplicates)
                # We need a "fake" successful entry signal.
                
                # Check if we are roughly 1/3 into the day
                # Or just check if we have enough bars and haven't entered.
                # Actually, the loop checks "if symbol in active_positions".
                # If we return True here, it enters.
                
                # We force entry if we have at least 40 bars (to show history) 
                # and price is > 1.0 (validity).
                curr_price = opportunity.get('current_price', 0)
                if bars_len > 40 and curr_price > 1.0:
                     worker.logger.info(f"🧪 FORCED ENTRY for Visualization (Lab Mode) @ {curr_price}")
                     
                     # Inject fake support level for lines
                     opportunity['support_level'] = curr_price * 0.98
                     opportunity['suggested_stop_loss_pct'] = 5.0
                     opportunity['pattern_completion'] = 95.0
                     
                     return True
            
            return result
        
        # Apply the patch to all workers
        worker.should_enter = forced_should_enter
        
        # Shared context for simulation time
        sim_context = {'current_timestamp': None}

        # --- MONKEY PATCH FOR TIME VALIDATION ---
        # Ensure process_opportunity uses current simulation time instead of system time
        original_is_within_entry_hours = worker.is_within_entry_hours
        
        def mock_is_within_entry_hours(symbol="", timestamp=None):
            # Use passed timestamp or current simulation time
            ts = timestamp or sim_context['current_timestamp']
            
            if not ts:
                # Fallback if accessed before loop start (shouldn't happen for entry checks)
                return True, 10.0
            
            # Convert timestamp to decimal hour (local/market time)
            # Assuming ts is naive or TZ aware correct execution
            # Market is EST. ts from bars might be UTC or EST.
            # get_market_bars returns bars with timestamps.
            # Let's assume timestamps are compatible with config times.
            
            # Extract hour and minute
            hour = ts.hour + (ts.minute / 60.0)
            
            # Get Config Limits
            pre_start = 4.0 # 04:00
            mkt_open = 9.5  # 09:30
            # Parse config strings if needed, but MockConfig has them as strings or floats?
            # MockConfig set them as strings '04:00'.
            
            def parse_time(t_str):
                try:
                    h, m = map(int, t_str.split(':'))
                    return h + m/60.0
                except:
                    return 0.0

            pre_start = parse_time(worker.config.premarket_start)
            mkt_open = parse_time(worker.config.market_open_time)
            last_entry = getattr(worker.config, 'no_entry_after', 15.75)
            
            # Check Mode
            extended = getattr(worker.config, 'enable_extended_hours_trading', False)
            pre_allowed = getattr(worker.config, 'allow_premarket_entries', False)
            
            start_time = mkt_open
            if extended and pre_allowed:
                start_time = pre_start
                
            is_valid = start_time <= hour <= last_entry
            
            # Debug log if rejected to verify toggle
            # worker.logger.debug(f"⏰ Time Check: {hour:.2f} (Start: {start_time}). Eligible: {is_valid}")
            
            remaining = last_entry - hour
            return is_valid, remaining
            
        worker.is_within_entry_hours = mock_is_within_entry_hours
        
        # --- MONKEY PATCH PROCESS_OPPORTUNITY ---
        # Bypass Risk, Failed Entries, and other operational checks.
        # Run RAW strategy logic only.
        async def mock_process_opportunity(opportunity):
            symbol = opportunity.get('symbol')
            if symbol in worker.active_positions:
                return False
            # Directly call the (already patched) should_enter
            return await worker.should_enter(opportunity)
            
        worker.process_opportunity = mock_process_opportunity
        # -----------------------
        
        # Iterate through ALL bars to ensure chart data is complete
        # Strategy logic starts after warmup
        WARMUP_PERIOD = 30
        
        for i in range(len(bars)):
            # Update "current" context
            current_bar = bars[i]
            sim_context['current_timestamp'] = current_bar.timestamp
            current_bars = bars[:i+1] # Bars up to now

            # Update log handler with current bar time for proper timestamping
            log_handler.current_bar_time = current_bar.timestamp
            
            # --- INITIALIZE INDICATOR VARIABLES (Defaults) ---
            decision = "WAIT"
            orb_high = None
            orb_low = None
            quality_score = None
            risk_reward = None
            atr_percent = None
            suggested_stop_loss_pct = None
            support_level = None
            stop_loss_price = None
            take_profit_price = None
            active_entry_price = None
            
            # Additional Indicators
            vwap_val = None
            vwap_slope = None
            price_above_vwap_pct = None
            is_above_vwap = None

            # Momentum Indicators (for A/B testing visualization)
            momentum_indicator_type = None
            momentum_value = None

            livermore_phase = None
            livermore_pause_high = None
            livermore_pause_low = None
            livermore_initial_high = None
            livermore_initial_low = None
            
            adx_val = None
            plus_di = None
            minus_di = None
            ema20_val = None

            # --- WORKER LOGIC (Only after Warmup) ---
            if i >= WARMUP_PERIOD:
                # Construct opportunity object
                opportunity = {
                    'symbol': symbol,
                    'current_price': current_bar.close,
                    'bars': current_bars, # Workers often fetch their own bars or use these
                    'timestamp': current_bar.timestamp,
                    # Add mock scanner data that workers might expect
                    # Use historical scanner data if available, otherwise default
                    'gap_percentage': scanner_data.get('gap_percentage', 0.0), 
                    'volume_ratio': scanner_data.get('volume_ratio', 1.0),
                    'quality_score': scanner_data.get('quality_score', 80), 
                    'catalyst_type': scanner_data.get('catalyst_type', 'TEST_CATALYST')
                }

                # SPECIAL HANDLING: Short Squeeze Worker requires 'candidate_info'
                if worker_name == 'short_squeeze':
                    # FORCE High Volume for simulation to pass "Fuel" score
                    opportunity['volume_ratio'] = 5.0 
                    
                    opportunity['candidate_info'] = {
                        'symbol': symbol,
                        'days_since_detection': 1,  # Simulate Day 1 for backtesting
                        'pattern_type': 'GREEN_DAY_1',
                        'key_levels': {
                           'resistance': current_bar.high * 0.98, # Slightly below high to trigger breakout
                           'support': current_bar.low,
                           'day1_high': current_bar.high * 0.98,
                           'daily_structure': 'BREAKOUT'
                        }
                    }

                # CRITICAL: Prevent entries near EOD (19:40 cutoff for 20:00 close)
                # This prevents "zombie" trades that open right before data ends
                et_time = current_bar.timestamp.astimezone(pytz.timezone('America/New_York'))
                is_near_eod = et_time.hour >= 19 and et_time.minute >= 40
                
                # Catch "entered" state
                if symbol in worker.active_positions:
                     # ALREADY IN POSITION - Check for Exit
                     decision = "HOLD"

                     # CRITICAL: Update stop_manager with current bar timestamp for time-based exits
                     # This is needed because stop_manager uses datetime.now() which doesn't work in replay mode
                     if hasattr(worker, 'stop_manager'):
                         # Inject current bar timestamp into stop_manager for replay mode
                         worker.stop_manager._current_time = current_bar.timestamp

                     # Manual Exit Check (since BaseWorkerLogic auto-checks in monitor loop,
                     # but here we are stepping manually)
                     position_data = worker.active_positions[symbol]
                     should_exit, reason = await worker.should_exit(
                         symbol=symbol,
                         position=position_data,
                         current_price=current_bar.close
                     )

                     if should_exit:
                         decision = "EXIT"
                         # Simulate Exit with Slippage & Commissions
                         raw_exit_price = current_bar.close
                         exit_price = raw_exit_price * (1 - SIM_SLIPPAGE_PCT) # Sell into bid (lower)
                         
                         entry_price = worker.active_positions[symbol]['entry_price'] # Already slipped
                         quantity = worker.active_positions[symbol]['quantity']
                         
                         gross_pnl = (exit_price - entry_price) * quantity
                         
                         # Commission
                         commission = max(SIM_COMMISSION_MIN, quantity * SIM_COMMISSION_PER_SHARE)
                         # Total Comm (Entry + Exit? Mock usually tracks round trip here or separately)
                         # Let's assume we pay exit commission here. Entry commission ideally at entry.
                         # For simplicity in this Viz Tool: Deduct Round Trip here ($2 min or share based)
                         total_commission = commission * 2 
                         
                         pnl = gross_pnl - total_commission
                         
                         realized_pnl += pnl
                         cum_gross_pnl += gross_pnl
                         cum_commission += total_commission
                         trades_count += 1
                         if pnl > 0:
                             winning_trades += 1
                             
                         worker.logger.info(f"💰 PnL: ${pnl:.2f} (Gross: ${gross_pnl:.2f}, Comm: ${total_commission:.2f}, Slip: {SIM_SLIPPAGE_PCT*100}%)")
                         
                         # Record completed trade for metrics
                         if active_entry_time and active_entry_price_for_record:
                             duration_minutes = (current_bar.timestamp - active_entry_time).total_seconds() / 60
                             completed_trades.append({
                                 'entry_time': active_entry_time.isoformat(),
                                 'exit_time': current_bar.timestamp.isoformat(),
                                 'duration_minutes': duration_minutes,
                                 'entry_price': active_entry_price_for_record,
                                 'exit_price': exit_price,
                                 'quantity': quantity,
                                 'pnl': pnl,
                                 'gross_pnl': gross_pnl,
                                 'commission': total_commission,
                                 'is_win': pnl > 0,
                                 'exit_reason': reason
                             })

                         del worker.active_positions[symbol]
                         active_entry_time = None
                         active_entry_price_for_record = None

                         
                         # Unregister from stop_manager
                         if hasattr(worker, 'stop_manager'):
                             worker.stop_manager.unregister_position(symbol)

                # NOT IN POSITION - Check for Entry
                elif await worker.process_opportunity(opportunity):
                    decision = "ENTER"
                    
                    # SIMULATE EXECUTION with Slippage
                    # In real life, ExecutionEngine does this.
                    entry_price_slipped = current_bar.close * (1 + SIM_SLIPPAGE_PCT) # Buy at Ask (higher)
                    
                    # Calculate quantity based on pos_value or pos_size
                    quantity = 100 # Default
                    if pos_value is not None and pos_value > 0:
                        quantity = int(pos_value / entry_price_slipped)
                        if quantity <= 0: quantity = 1 # Minimum 1 share
                    elif pos_size is not None and pos_size > 0:
                        quantity = int(pos_size)

                    worker.active_positions[symbol] = {
                        'entry_price': entry_price_slipped,
                        'entry_time': current_bar.timestamp,
                        'quantity': quantity,
                        'opportunity_data': opportunity,
                        # Add standard metadata the worker expects
                        'EOD_safe': False,
                        'trading_horizon': 'INTRADAY',
                        'strategy': worker_name
                    }
                    # Register with stop manager
                    if hasattr(worker, 'stop_manager'):
                         worker.stop_manager.register_position(symbol, current_bar.timestamp)
                    
                    # Track entry for trade record
                    active_entry_time = current_bar.timestamp
                    active_entry_price_for_record = entry_price_slipped
            
                # --- EXTRACT INDICATORS FROM OPPORTUNITY/WORKER ---
                
                # 1. ORB
                orb_high = opportunity.get('orb_high')
                orb_low = opportunity.get('orb_low')
                if worker_name == 'orb' and (orb_high is None or orb_low is None):
                    # Force calculation for visualization
                    try:
                         # Access internal method if possible
                         if hasattr(worker, '_calculate_orb'):
                             orb_res = worker._calculate_orb(current_bars)
                             if orb_res.get('valid'):
                                 orb_high = orb_res.get('high')
                                 orb_low = orb_res.get('low')
                    except Exception:
                        pass

                # 2. VCP / General
                quality_score = opportunity.get('quality_score')
                risk_reward = opportunity.get('risk_reward')
                atr_percent = opportunity.get('atr_percent')
                suggested_stop_loss_pct = opportunity.get('suggested_stop_loss_pct')
                
                # Enriched VCP Viz
                if worker_name == 'vcp_smallcap':
                     try:
                         pat_comp, supp_lvl = await worker.calculate_pattern_completion(opportunity)
                         # Only update if valid and not already set by process_opportunity success
                         if supp_lvl > 0:
                             support_level = supp_lvl
                             opportunity['support_level'] = supp_lvl
                             opportunity['pattern_completion'] = pat_comp
                     except: pass
                else:
                    support_level = opportunity.get('support_level')

                # 3. Buy & Hold - VWAP Momentum Indicators (NEW)
                if worker_name == 'buy_and_hold':
                    # Get bars for VWAP calculation
                    try:
                        bars_for_vwap = worker.get_bars_from_opportunity(opportunity)
                        if bars_for_vwap and len(bars_for_vwap) >= 10:
                            vwap_analysis = worker._analyze_vwap(bars_for_vwap, current_bar.close)
                            if vwap_analysis:
                                # Always populate VWAP indicators (even if rejected)
                                vwap_val = vwap_analysis.vwap
                                vwap_slope = vwap_analysis.vwap_slope
                                price_above_vwap_pct = vwap_analysis.price_above_vwap_pct
                                is_above_vwap = vwap_analysis.is_above_vwap
                                # Also add SL/TP for visualization
                                suggested_stop_loss_pct = 5.0
                                stop_loss_price = current_bar.close * 0.95
                                take_profit_price = current_bar.close * 1.15
                    except: pass
                else:
                    vwap_val = opportunity.get('vwap')
                    # Populate other vwap vars if opportunity has them
                    vwap_slope = opportunity.get('vwap_slope')
                    price_above_vwap_pct = opportunity.get('price_above_vwap_pct')
                    is_above_vwap = opportunity.get('is_above_vwap')

                # Extract momentum indicator data (for Buy & Hold A/B testing visualization)
                momentum_indicator_type = opportunity.get('momentum_indicator')  # 'ROC' or 'VWAP_SLOPE'
                momentum_value = opportunity.get('momentum_value')  # Numeric value of the indicator

                # 4. Holy Grail - Calculate ADX, DI, EMA20 for visualization
                if worker_name == 'holy_grail':
                    try:
                        import pandas as pd
                        import pandas_ta as ta

                        bars_hg = worker.get_bars_from_opportunity(opportunity)
                        if bars_hg and len(bars_hg) >= 50:
                            # Convert to DataFrame
                            df_hg = worker._bars_to_dataframe(bars_hg)
                            if not df_hg.empty:
                                # Calculate ADX
                                adx_df = ta.adx(df_hg['high'], df_hg['low'], df_hg['close'], length=14)
                                if adx_df is not None and not adx_df.empty:
                                    adx_val = float(adx_df['ADX_14'].iloc[-1])
                                    plus_di = float(adx_df['DMP_14'].iloc[-1])
                                    minus_di = float(adx_df['DMN_14'].iloc[-1])

                                # Calculate EMA20
                                df_hg['ema20'] = ta.ema(df_hg['close'], length=20)
                                ema20_val = float(df_hg['ema20'].iloc[-1])
                                
                                # Recycle VWAP if possible
                                vwap_hg = worker._analyze_vwap(bars_hg, current_bar.close)
                                if vwap_hg:
                                    vwap_val = vwap_hg.vwap
                    except Exception as e:
                        pass  
                else:
                    adx_val = opportunity.get('adx')
                    plus_di = opportunity.get('plus_di')
                    minus_di = opportunity.get('minus_di')
                    ema20_val = opportunity.get('ema20')

                # 5. Livermore
                livermore_phase = opportunity.get('livermore_phase')
                livermore_pause_high = opportunity.get('livermore_pause_high')
                livermore_pause_low = opportunity.get('livermore_pause_low')
                livermore_initial_high = opportunity.get('livermore_initial_high')
                livermore_initial_low = opportunity.get('livermore_initial_low')

                # --- CALCULATE STOPS & TARGETS ---
                # Use active entry price if in trade, otherwise use opportunity suggested prices
                ref_price = active_entry_price if active_entry_price else current_bar.close
                
                # --- CALCULATE REAL TP/SL FOR VISUALIZATION ---
                if active_entry_price and hasattr(worker, 'config'):
                    # Defaults
                    sl_pct = getattr(worker.config, 'stop_loss_pct', 2.0)
                    tp_pct = getattr(worker.config, 'take_profit_pct', 6.0)
                    
                    # Base SL/TP
                    stop_loss_price = active_entry_price * (1 - sl_pct / 100)
                    take_profit_price = active_entry_price * (1 + tp_pct / 100)

                    # Manage Trailing Stop Visualization
                    if hasattr(worker, 'stop_manager') and hasattr(worker.stop_manager, 'highest_pnl'):
                        highest_pnl_pct = worker.stop_manager.highest_pnl.get(symbol, 0.0)
                        
                        trailing_activation = getattr(worker.config, 'trailing_activation', 1.5)
                        trailing_distance = getattr(worker.config, 'trailing_distance', 0.5)
                        
                        if highest_pnl_pct >= trailing_activation:
                            # Calculate Trailing Stop Level
                            peak_price = active_entry_price * (1 + highest_pnl_pct / 100)
                            trailing_stop = peak_price * (1 - trailing_distance / 100)
                            
                            # Update SL to be the higher of Base SL or Trailing Stop
                            if trailing_stop > stop_loss_price:
                                stop_loss_price = trailing_stop

                elif opportunity.get('stop_loss_price'):
                     # Use opportunity's calculated SL if not in position
                     stop_loss_price = opportunity.get('stop_loss_price')
                     take_profit_price = opportunity.get('take_profit_price')

            # --- APPEND RESULTS (Always, even if warmup) ---
            
            # Capture decision point
            result['decisions'].append({
                'timestamp': current_bar.timestamp.isoformat(),
                'price': current_bar.close,
                'decision': decision,
                'active_stage': 'monitoring' if symbol in worker.active_positions else 'scanning'
            })
            
            result['indicators'].append({
                'timestamp': current_bar.timestamp.isoformat(),

                # ORB Indicators
                'orb_high': orb_high,
                'orb_low': orb_low,

                # Quality & Risk
                'quality_score': quality_score,
                'risk_reward': risk_reward,
                'atr_percent': atr_percent,
                'stop_loss_pct': suggested_stop_loss_pct,

                # VCP / Standard Params
                'support_level': support_level, # Pivot
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'entry_price': active_entry_price, # Visualization of hold price

                # Buy & Hold - VWAP Momentum Indicators (NEW)
                'vwap': vwap_val,  # VWAP line
                'vwap_slope': vwap_slope,  # VWAP trend
                'price_above_vwap_pct': price_above_vwap_pct,  # Distance to VWAP
                'is_above_vwap': is_above_vwap,  # Boolean flag
                'momentum_indicator': momentum_indicator_type,  # 'ROC' or 'VWAP_SLOPE'
                'momentum_value': momentum_value,  # Numeric value of momentum

                # Livermore Intraday - Pivot Levels Indicators (NEW)
                'livermore_phase': livermore_phase,  # Current phase
                'livermore_pause_high': livermore_pause_high,  # Breakout level
                'livermore_pause_low': livermore_pause_low,  # Stop loss level
                'livermore_initial_high': livermore_initial_high,  # Impulse top
                'livermore_initial_low': livermore_initial_low,  # Impulse bottom

                # Holy Grail - ADX/DI/EMA Indicators (NEW)
                'adx': adx_val,  # ADX strength
                'plus_di': plus_di,  # +DI (bullish direction)
                'minus_di': minus_di,  # -DI (bearish direction)
                'ema20': ema20_val  # EMA(20) for retracements
            })
            
            # Basic chart point
            chart_data.append({
                't': current_bar.timestamp.isoformat(),
                'o': current_bar.open,
                'h': current_bar.high,
                'l': current_bar.low,
                'c': current_bar.close,
                'v': current_bar.volume,
                'vwap': 0 # TODO: Calculate VWAP
            })
            
            # Update Equity Curve and Drawdown
            # Calculate current open PnL
            current_open_pnl = 0.0
            for sym, pos in worker.active_positions.items():
                current_open_pnl += (current_bar.close - pos['entry_price']) * pos['quantity']
            
            current_equity = initial_cash + realized_pnl + current_open_pnl
            equity_curve.append({
                'timestamp': current_bar.timestamp.isoformat(),
                'equity': current_equity
            })
            
            # Track drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            else:
                current_drawdown = ((peak_equity - current_equity) / peak_equity) * 100
                max_drawdown = max(max_drawdown, current_drawdown)

        # force close any active positions at the end of the day
        for symbol in list(worker.active_positions.keys()):
            pos = worker.active_positions[symbol]
            current_price = bars[-1].close
            entry_price = pos['entry_price']
            quantity = pos['quantity']
            
            # Calculate PnL and Commission
            raw_exit_price = current_price
            exit_price = raw_exit_price * (1 - SIM_SLIPPAGE_PCT) # Sell into bid
            
            pnl = (exit_price - entry_price) * quantity
            
            # Commission (Round trip for entry + exit)
            exit_commission = max(SIM_COMMISSION_MIN, quantity * SIM_COMMISSION_PER_SHARE)
            total_commission = exit_commission * 2 
            
            net_pnl = pnl - total_commission
            
            realized_pnl += net_pnl
            cum_gross_pnl += pnl
            cum_commission += total_commission
            trades_count += 1
            if net_pnl > 0:
                winning_trades += 1
                
            # Record trade
            completed_trades.append({
                'symbol': symbol,
                'entry_time': pos['entry_time'].isoformat(),
                'exit_time': bars[-1].timestamp.isoformat(),
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'pnl': net_pnl,
                'gross_pnl': pnl,
                'commission': total_commission,
                'is_win': net_pnl > 0,
                'reason': 'EOD_FORCE_EXIT'
            })
            
            # Record decision
            result['decisions'].append({
                'timestamp': bars[-1].timestamp.isoformat(),
                'price': current_price,
                'decision': 'SELL (EOD)',
                'active_stage': 'scaning'
            })
            
            del worker.active_positions[symbol]

        # Calculate Final PnL Summary
        open_pnl = 0.0 # All closed now
            
        total_pnl = realized_pnl + open_pnl
        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0.0

        result['status'] = 'success'
        result['logs'] = log_handler.logs
        result['chart_data'] = chart_data
        
        # Calculate advanced metrics
        advanced_metrics = calculate_advanced_metrics(completed_trades, max_drawdown, initial_cash)
        
        result['summary'] = {
            # Basic PnL metrics
            'realized_pnl': round(realized_pnl, 2),
            'gross_pnl': round(cum_gross_pnl, 2),
            'total_commission': round(cum_commission, 2),
            'open_pnl': round(open_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'trades_count': trades_count,
            
            # Advanced metrics
            **advanced_metrics
        }
        
        # --- DIAGNOSTIC: Analyze Logs for Rejection Reasons ---
        if result['summary']['trades_count'] == 0:
            rejection_counts = {}
            # Keywords indicating rejection/skip
            keywords = [
                'Vol condition failed', 'Volume too low', 'Low vol', 
                'not ready', 'below min', 'Risk Rejected', 
                'Price too low', 'Price too high', 'RSI too high', 'RSI too low',
                'Spread too high', 'No setups found', 'filtered out',
                'Validation failed',
                'Stage 1 FAILED', 'Stage 2 FAILED', 'Stage 3 FAILED', 'Stage 4 FAILED',
                'Quality', 'ODS'
            ]
            
            for log in log_handler.logs:
                msg = log['message']
                # Check for explicit keywords
                for kw in keywords:
                    if kw.lower() in msg.lower():
                        # Extract a cleaner reason if possible, or just use keyword/snippet
                        # Try to capture context: "VWAP pattern not ready (65% < 70%)"
                        reason = kw
                        if 'not ready' in kw:
                            # Try to extract the whole message for better context
                            reason = msg.split('INFO - ')[-1].split('DEBUG - ')[-1].strip()
                            if '⚪' in reason: reason = reason.replace('⚪', '').strip()
                        elif 'Vol' in kw:
                            reason = "Volume too low"
                        
                        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                        break # Count only one reason per log line
            
            if rejection_counts:
                # Find top reason
                top_reason = max(rejection_counts, key=rejection_counts.get)
                count = rejection_counts[top_reason]
                result['summary']['rejection_reason'] = f"{top_reason} ({count}x)"
            else:
                # Capture last logs to debug silent failures
                last_logs = [l['message'] for l in log_handler.logs[-3:]] if log_handler.logs else ["No logs"]
                debug_info = " | ".join(last_logs)
                # Clean specific characters if needed
                result['summary']['rejection_reason'] = f"Silent: {debug_info[:100]}..."
        else:
            result['summary']['rejection_reason'] = None
            
        # Optional: Include equity curve and completed trades for detailed analysis
        result['equity_curve'] = equity_curve
        result['completed_trades'] = completed_trades
        
    except Exception as e:
        import traceback
        import sys
        traceback.print_exc()
        if 'worker' in locals() and hasattr(worker, 'logger'):
            worker.logger.error(f"Simulation crashed: {e}")
        else:
            print(f"Simulation crashed before worker init: {e}", file=sys.stderr)
            
        result['status'] = 'error'
        # Include Traceback to debug cryptic errors like "dict ** dict"
        tb = traceback.format_exc()
        result['error'] = f"CRASH: {str(e)}\n\n{tb}"
        result['traceback'] = tb
        result['logs'] = log_handler.logs # Capture crash logs
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Worker Lab Test')
    parser.add_argument('--worker', required=True, help='Worker name (e.g., orb)')
    parser.add_argument('--symbol', required=True, help='Symbol to test')
    parser.add_argument('--date', required=True, help='Date YYYY-MM-DD')
    parser.add_argument('--momentum_indicator', choices=['vwap_slope', 'roc'],
                        help='Momentum indicator to use (vwap_slope for old data, roc for new data)')
    parser.add_argument('--extended-hours', action='store_true', help='Enable extended hours trading')
    parser.add_argument('--params', help='JSON string of parameter overrides')
    parser.add_argument('--pos-value', type=float, help='Fixed investment amount in dollars')
    parser.add_argument('--pos-size', type=int, help='Fixed share count')
    parser.add_argument('--timeframe', type=str, default='1m', help='Timeframe (e.g. 1m, 5m)')

    args = parser.parse_args()
    
    # Parse params if provided
    overrides_dict = None
    if args.params:
        try:
            overrides_dict = json.loads(args.params)
        except Exception as e:
            print(f"Error parsing params JSON: {e}", file=sys.stderr)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asyncio.set_event_loop(loop)

    # CRITICAL: Suppress all existing handlers to prevent stdout pollution
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    
    # Configure basic config to stderr to keep stdout clean for JSON
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    try:
        result = loop.run_until_complete(run_worker_simulation(
            args.worker,
            args.symbol,
            args.date,
            momentum_indicator=args.momentum_indicator,
            extended_hours=args.extended_hours,
            config_overrides=overrides_dict,
            pos_value=args.pos_value,
            pos_size=args.pos_size,
            timeframe=args.timeframe
        ))
        # Print Result as JSON to original stdout
        # CRITICAL: sys.stdout is redirected to stderr, so we must use original_stdout
        # CRITICAL: indent=None is REQUIRED because toolsController.js parses only the last line!
        print(json.dumps(result, cls=DateTimeEncoder), file=original_stdout)
    finally:
        loop.close()
