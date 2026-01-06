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
import sqlite3
import numpy as np
import traceback
import pytz
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
    'smallcaps_short_reversal': SmallCapsShortReversalWorkerLogic,
    'catalyst_dna': CatalystDNAWorkerLogic
}

class MockExecutionEngine:
    """Mock execution engine for testing"""
    def __init__(self):
        self.worker_positions = {}
        self.broker = None # Mock if needed

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

def get_scanner_detection_time(symbol, date_str):
    """
    Get the first scanner detection timestamp for a symbol on a specific date

    Args:
        symbol: Stock ticker symbol
        date_str: Date in YYYY-MM-DD format

    Returns:
        ISO format timestamp string or None if not found
    """
    db_path = PROJECT_ROOT / 'trading_data.db'
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get first scanner detection for this symbol on this date
        query = """
            SELECT MIN(timestamp) as first_detection
            FROM scanner_opportunities
            WHERE symbol = ? AND date(timestamp) = date(?)
        """

        cursor.execute(query, (symbol.upper(), date_str))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            # Convert to datetime and return ISO format
            try:
                dt = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                return dt.isoformat()
            except:
                return row[0]  # Return as-is if conversion fails

        return None

    except Exception as e:
        print(f"Warning: Could not fetch scanner detection time: {e}", file=sys.stderr)
        return None

async def run_worker_simulation(worker_name, symbol, date_str, momentum_indicator=None):
    """
    Run the simulation for a specific worker

    Args:
        worker_name: Name of the worker to test
        symbol: Stock symbol
        date_str: Date in YYYY-MM-DD format
        momentum_indicator: 'vwap_slope' or 'roc' (defaults to 'roc' if not specified)
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
    
    # Create a permissive mock config for testing visualization
    class MockConfig:
        def __init__(self):
            # VCP Relaxed Params
            self.vcp_min_contractions = 1
            self.vcp_max_contraction_minutes = 60
            self.vcp_entry_threshold = 95.0
            self.vcp_min_price = 0.5
            self.vcp_max_price = 200.0
            self.vcp_min_volume_ratio = 0.5
            self.vcp_min_quality_score = 0.0 # Accept anything
            self.enable_ods_filters = False
            self.vcp_use_multitimeframe = False
            self.vcp_require_catalyst = False
            
            # Universal Stops (for stop manager)
            # NOTE: Values in decimal format to match config.ini (0.05 = 5%)
            # create_worker_stop_manager() will multiply by 100
            self.stop_loss_pct = 0.05      # 5%
            self.take_profit_pct = 0.15    # 15%
            self.trailing_activation = 0.08  # 8%
            self.trailing_distance = 0.04   # 4%
            self.max_position_hours = 6.0
            
            # Others
            self.swing_transition_enabled = False

            # Extended hours support - CRITICAL for accurate replay
            self.enable_extended_hours_trading = True
            self.allow_premarket_entries = True
            self.allow_afterhours_entries = False
            self.premarket_start = '04:00'
            self.market_open_time = '09:30'
            self.no_entry_after = 15.75

            # Momentum indicator configuration for Buy & Hold worker A/B testing
            # Default to ROC (current) if not specified
            if momentum_indicator == 'vwap_slope':
                self.use_roc_momentum = False  # Use VWAP Slope (old method)
                self.min_vwap_slope = 0.00001
                self.min_price_above_vwap_pct = 0.5
            elif momentum_indicator == 'roc':
                self.use_roc_momentum = True  # Use ROC (new method)
                self.roc_period = 5
                self.roc_min_threshold = 1.0
                self.min_price_above_vwap_pct = 0.5
            else:
                # Default to ROC if not specified
                self.use_roc_momentum = True
                self.roc_period = 5
                self.roc_min_threshold = 1.0
                self.min_price_above_vwap_pct = 0.5

    mock_config = MockConfig()
    
    try:
        # Instantiate worker
        # Different workers might have different signatures.
        # Base expects: worker_name, execution_engine, risk_manager, config
        # But derived classes might hardcode worker_name or expect other args.
        
        try:
            # Try with worker_name first (standard BaseWorkerLogic signature)
            worker = worker_class(
                worker_name=worker_name,
                execution_engine=engine,
                risk_manager=risk,
                config=mock_config # Pass relaxed config
            )
        except TypeError:
            # Fallback: some workers might not accept worker_name if they hardcode it
            worker = worker_class(
                execution_engine=engine,
                risk_manager=risk,
                config=mock_config
            )
            
        # Override logger to capture output
        worker.logger.addHandler(log_handler)
        worker.logger.setLevel(logging.DEBUG)
        
        worker.set_replay_date(date_str)
        
        # Get historical data
        bars = get_market_bars(symbol, date_str)
        if not bars:
            result['error'] = f"No data found for {symbol} on {date_str}"
            # Add logs captured so far
            result['logs'] = log_handler.logs
            return result

        worker.logger.info(f"Loaded {len(bars)} bars for {symbol}")

        # Get scanner detection time for visualization
        scanner_detection_time = get_scanner_detection_time(symbol, date_str)
        result['scanner_detection_time'] = scanner_detection_time
        if scanner_detection_time:
            worker.logger.info(f"📡 Scanner first detected {symbol} at {scanner_detection_time}")

        # Calculate Real Trades Summary
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
        realized_pnl = 0.0
        trades_count = 0
        winning_trades = 0


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
            if not result and worker_name == 'vcp_smallcap':
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
        
        # Apply the patch
        if worker_name == 'vcp_smallcap':
            worker.should_enter = forced_should_enter
        
        # --- MONKEY PATCH FOR TIME VALIDATION ---
        # Ensure process_opportunity uses current simulation time instead of system time
        original_is_within_entry_hours = worker.is_within_entry_hours
        
        def mock_is_within_entry_hours(symbol="", timestamp=None):
            # If no timestamp provided (default call from process_opportunity), use simulation time
            if timestamp is None:
                timestamp = log_handler.current_bar_time
            return original_is_within_entry_hours(symbol, timestamp=timestamp)
            
        worker.is_within_entry_hours = mock_is_within_entry_hours
        # -----------------------
        
        # Iterate through ALL bars to ensure chart data is complete
        # Strategy logic starts after warmup
        WARMUP_PERIOD = 30
        
        for i in range(len(bars)):
            # Update "current" context
            current_bar = bars[i]
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
                    'gap_percentage': 0.0, 
                    'volume_ratio': 1.0,
                    'quality_score': 80, # Default high quality to test logic
                    'catalyst_type': 'TEST_CATALYST'
                }
                
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
                         # Simulate Exit
                         exit_price = current_bar.close
                         entry_price = worker.active_positions[symbol]['entry_price']
                         quantity = worker.active_positions[symbol]['quantity']
                         
                         pnl = (exit_price - entry_price) * quantity
                         # Adjust for short if needed (mock logic assumes long, but let's be safe)
                         # If quantity is negative for short? Not in this mock.
                         # Assuming mock is long-only for now unless side is stored.
                         
                         realized_pnl += pnl
                         trades_count += 1
                         if pnl > 0:
                             winning_trades += 1
                             
                         worker.logger.info(f"💰 PnL Realized: ${pnl:.2f}")

                         del worker.active_positions[symbol]

                         
                         # Unregister from stop_manager
                         if hasattr(worker, 'stop_manager'):
                             worker.stop_manager.unregister_position(symbol)

                # NOT IN POSITION - Check for Entry
                elif await worker.process_opportunity(opportunity):
                    decision = "ENTER"
                    
                    # SIMULATE EXECUTION
                    # In real life, ExecutionEngine does this.
                    worker.active_positions[symbol] = {
                        'entry_price': current_bar.close,
                        'entry_time': current_bar.timestamp,
                        'quantity': 100, # Mock
                        'opportunity_data': opportunity,
                        # Add standard metadata the worker expects
                        'EOD_safe': False,
                        'trading_horizon': 'INTRADAY',
                        'strategy': worker_name
                    }
                    # Register with stop manager
                    if hasattr(worker, 'stop_manager'):
                         worker.stop_manager.register_position(symbol, current_bar.timestamp)
            
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
                # Determine active entry price (for visualization)
                if symbol in worker.active_positions:
                     active_entry_price = worker.active_positions[symbol]['entry_price']

                # Use active entry price if in trade, otherwise use opportunity suggested prices
                ref_price = active_entry_price if active_entry_price else current_bar.close
                
                if active_entry_price:
                    # We are IN a position - use real SL/TP
                    if support_level:
                        # If pivot detected, SL is usually below support
                        stop_loss_price = support_level * 0.99
                    elif opportunity.get('stop_loss_price'):
                        # Use opportunity's calculated SL
                        stop_loss_price = opportunity.get('stop_loss_price')
                    else:
                        # Fallback: Default 5% stop
                        stop_loss_price = active_entry_price * 0.95

                    if opportunity.get('take_profit_price'):
                        take_profit_price = opportunity.get('take_profit_price')
                    else:
                        # Default 15% TP
                        take_profit_price = active_entry_price * 1.15
                else:
                    # NO position yet - use opportunity's suggested prices for visualization
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

        # Calculate Final PnL Summary
        open_pnl = 0.0
        for symbol, pos in worker.active_positions.items():
            current_price = bars[-1].close
            entry_price = pos['entry_price']
            quantity = pos['quantity']
            open_pnl += (current_price - entry_price) * quantity
            
        total_pnl = realized_pnl + open_pnl
        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0.0

        result['status'] = 'success'
        result['logs'] = log_handler.logs
        result['chart_data'] = chart_data
        result['summary'] = {
            'realized_pnl': round(realized_pnl, 2),
            'open_pnl': round(open_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'trades_count': trades_count,
            'win_rate': round(win_rate, 1)
        }
        
    except Exception as e:
        import traceback
        import sys
        traceback.print_exc()
        if 'worker' in locals() and hasattr(worker, 'logger'):
            worker.logger.error(f"Simulation crashed: {e}")
        else:
            print(f"Simulation crashed before worker init: {e}", file=sys.stderr)
            
        result['status'] = 'error'
        result['error'] = str(e)
        result['traceback'] = traceback.format_exc()
        result['logs'] = log_handler.logs # Capture crash logs
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Worker Lab Test')
    parser.add_argument('--worker', required=True, help='Worker name (e.g., orb)')
    parser.add_argument('--symbol', required=True, help='Symbol to test')
    parser.add_argument('--date', required=True, help='Date YYYY-MM-DD')
    parser.add_argument('--momentum_indicator', choices=['vwap_slope', 'roc'],
                        help='Momentum indicator to use (vwap_slope for old data, roc for new data)')

    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(run_worker_simulation(
            args.worker,
            args.symbol,
            args.date,
            momentum_indicator=args.momentum_indicator
        ))
        print(json.dumps(result, cls=json.JSONEncoder)) # Output ONLY JSON to stdout
    finally:
        loop.close()
