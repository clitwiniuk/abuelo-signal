#!/usr/bin/env python3
"""
Worker Lab Replay Script
========================
Diagnostic tool to replay a worker's logic with specific input data.
Used by the Worker Lab UI to debug why a worker accepted or rejected a trade.

Usage:
    python3 scripts/worker_lab_replay.py --worker_name buy_and_hold --data '{"symbol": "MSTX", "current_price": 1.5, ...}'

Output:
    JSON object with:
    - decision: "ACCEPTED" | "REJECTED"
    - logs: List of log messages generated during execution
    - checks: List of specific checks passed/failed (inferred from logs)
"""

import sys
import os
import json
import argparse
import logging
import io
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.buy_and_hold_worker_logic import BuyAndHoldWorkerLogic
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
from strategies.workers.orb_worker_logic import ORBWorkerLogic
from strategies.workers.buy_the_dip_worker_logic import BuyTheDipWorkerLogic
from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic
from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
from strategies.workers.parabolic_worker_logic import ParabolicWorkerLogic
from strategies.workers.livermore_intraday_worker_logic import LivermoreIntradayWorkerLogic 

# Mock Classes
class MockIB:
    async def reqHistoricalDataAsync(self, *args, **kwargs):
        return []

    async def reqHistoricalTicksAsync(self, *args, **kwargs):
        # Mock Tick Data for CVD Replay
        # Return a simple list of objects with price/size attributes
        from types import SimpleNamespace
        # Create a dummy uptrend to yield positive CVD
        t1 = SimpleNamespace(price=10.00, size=100)
        t2 = SimpleNamespace(price=10.01, size=200) # Buy (Uptick)
        t3 = SimpleNamespace(price=10.02, size=200) # Buy (Uptick)
        return [t1, t2, t3]

    def qualifyContracts(self, *args):
        # Return the contracts passed as arguments (acting as pass-through)
        # args[0] is usually the contract or list of contracts
        if args and isinstance(args[0], list):
             return args[0]
        return list(args)

class MockBroker:
    def __init__(self):
        self.ib = MockIB()

class MockExecutionEngine:
    def __init__(self):
        self.positions = {}
    
    async def get_positions(self):
        return self.positions

class MockRiskManager:
    def __init__(self):
        pass
        
    def check_risk(self, *args, **kwargs):
        return True

class MockConfig:
    def __init__(self, config_dict=None):
        self.config = config_dict or {}
        
    def get(self, *args, **kwargs):
        # Handle various signatures:
        # 1. get(key, default=None)
        # 2. get(section, option, fallback=None) - ConfigParser style
        
        fallback = kwargs.get('fallback', None)
        
        if len(args) == 2 and isinstance(args[1], str):
            # Likely (section, option)
            key = args[1]
        elif len(args) >= 1:
             key = args[0]
        else:
            return fallback

        val = self.config.get(key)
        
        # If val is missing, return fallback (or default from args if 2nd arg wasn't option)
        if val is None:
            if len(args) == 2 and not isinstance(args[1], str):
                 # get(key, default) case
                 return args[1]
            return fallback
            
        return val

    # Helper for nested dictionary access simulating sections
    def get_section(self, section, key, fallback=None):
        # We flatten the config for mock simplicity, or try to find section-prefixed keys
        # If config has { "ORB_STRATEGY": { "min_price": 0.5 } } -> handle that
        # Or simpler: just look for key in root dict
        return self.get(key, fallback=fallback)
    
    def getint(self, section, option, fallback=None):
        try:
           val = self.get_section(section, option, fallback)
           return int(val) if val is not None else fallback
        except (ValueError, TypeError):
           return fallback

    def getfloat(self, section, option, fallback=None):
        try:
           val = self.get_section(section, option, fallback)
           return float(val) if val is not None else fallback
        except (ValueError, TypeError):
           return fallback
           
    def getboolean(self, section, option, fallback=None):
        try:
           val = self.get_section(section, option, fallback)
           if isinstance(val, bool): return val
           if str(val).lower() in ['true', '1', 'yes', 'on']: return True
           if str(val).lower() in ['false', '0', 'no', 'off']: return False
           return fallback
        except (ValueError, TypeError):
           return fallback
    
    def __getattr__(self, name):
        if name in self.config:
            return self.config[name]
        # Raise AttributeError so getattr(config, 'attr', default) works correctly
        raise AttributeError(f"'MockConfig' object has no attribute '{name}'")

# Capture Logger
class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []
        
    def emit(self, record):
        self.log_records.append({
            "level": record.levelname,
            "message": self.format(record),
            "timestamp": datetime.fromtimestamp(record.created).isoformat()
        })

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        try:
            return str(obj)
        except:
            return super().default(obj)

async def replay_worker(worker_name, opportunity_data, config_overrides=None, args=None):
    """
    Instantiate and run a worker logic class against opportunity data.
    """
    # 1. Map frontend bar format (bars_1min) to worker format (bars)
    # 1. Map frontend bar format (bars_1min) to worker format (bars)
    if 'bars_1min' in opportunity_data and ('bars' not in opportunity_data or not opportunity_data['bars']):
        # If 'bars' is empty (default from frontend), populate it with 'bars_1min'
        opportunity_data['bars'] = opportunity_data['bars_1min']

    # 1.5 Convert bars from dicts to objects (SimpleNamespace) if needed
    # Workers expect bar.timestamp, not bar['timestamp']
    from types import SimpleNamespace
    
    def dict_to_bar_obj(bar_dict):
        if not isinstance(bar_dict, dict): return bar_dict
        # Ensure timestamp is parsed if string
        if isinstance(bar_dict.get('timestamp'), str):
            try:
                # Basic ISO parsing
                from datetime import datetime
                bar_dict['timestamp'] = datetime.fromisoformat(bar_dict['timestamp'].replace('Z', '+00:00'))
            except: 
                pass
        return SimpleNamespace(**bar_dict)

    if 'bars' in opportunity_data and isinstance(opportunity_data['bars'], list):
        opportunity_data['bars'] = [dict_to_bar_obj(b) for b in opportunity_data['bars']]

    if 'bars_1min' in opportunity_data and isinstance(opportunity_data['bars_1min'], list):
         opportunity_data['bars_1min'] = [dict_to_bar_obj(b) for b in opportunity_data['bars_1min']]

    # CRITICAL FIX: Filter bars by replay timestamp to simulate real-time data availability
    # This ensures VWAP and other indicators match what the live system saw at that moment
    if args and args.timestamp:
        try:
            # Parse replay timestamp
            replay_cutoff = datetime.fromisoformat(args.timestamp.replace('Z', '+00:00'))

            # Filter bars - only keep bars BEFORE or AT the replay timestamp
            def filter_bars_by_time(bars_list, cutoff_time):
                """Filter bars to only include those up to cutoff_time"""
                if not bars_list:
                    return bars_list

                filtered_bars = []
                for bar in bars_list:
                    bar_time = bar.timestamp if hasattr(bar, 'timestamp') else None

                    if bar_time is None:
                        # No timestamp, keep it (shouldn't happen but be safe)
                        filtered_bars.append(bar)
                        continue

                    # Ensure bar_time is datetime
                    if isinstance(bar_time, str):
                        try:
                            bar_time = datetime.fromisoformat(bar_time.replace('Z', '+00:00'))
                        except:
                            filtered_bars.append(bar)  # Can't parse, keep it
                            continue

                    # Only include bars <= replay_cutoff
                    if bar_time <= cutoff_time:
                        filtered_bars.append(bar)

                return filtered_bars

            # Apply filtering
            if 'bars' in opportunity_data:
                original_count = len(opportunity_data['bars'])
                opportunity_data['bars'] = filter_bars_by_time(opportunity_data['bars'], replay_cutoff)
                filtered_count = len(opportunity_data['bars'])

                if original_count > filtered_count:
                    # Log to stderr so it doesn't interfere with JSON output
                    sys.stderr.write(
                        f"🔍 REPLAY FILTER: Reduced bars from {original_count} to {filtered_count} "
                        f"(cutoff: {replay_cutoff.strftime('%H:%M:%S')})\n"
                    )

            if 'bars_1min' in opportunity_data:
                original_count = len(opportunity_data['bars_1min'])
                opportunity_data['bars_1min'] = filter_bars_by_time(opportunity_data['bars_1min'], replay_cutoff)
                filtered_count = len(opportunity_data['bars_1min'])

                if original_count > filtered_count:
                    sys.stderr.write(
                        f"🔍 REPLAY FILTER: Reduced bars_1min from {original_count} to {filtered_count} "
                        f"(cutoff: {replay_cutoff.strftime('%H:%M:%S')})\n"
                    )

        except Exception as e:
            sys.stderr.write(f"⚠️ Warning: Could not filter bars by timestamp: {e}\n")

    # Setup Logging Capture
    logger = logging.getLogger(worker_name)
    logger.setLevel(logging.DEBUG)
    # Remove existing handlers to avoid noise
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        
    list_handler = ListHandler()
    formatter = logging.Formatter('%(message)s')
    list_handler.setFormatter(formatter)
    logger.addHandler(list_handler)
    
    # Create mock execution components
    execution_engine = MockExecutionEngine()
    execution_engine.broker = MockBroker()
    risk_manager = MockRiskManager()
    
    # Load config defaults
    config_defaults = {
        'min_price': 1.0,
        'max_price': 20.0,
        'min_quality_score': 60,
        # Add VCP defaults explicitly just in case
        'vcp_min_price': 1.0,
        'vcp_max_price': 25.0,
        'enable_ods_filters': True # Default to True if config load fails
    }

    # Try to load from config.ini
    import configparser
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    if os.path.exists(config_path):
        real_config = configparser.ConfigParser(interpolation=None)
        real_config.read(config_path)
        
        # Flatten relevant sections into config_defaults for MockConfig
        # This is a simple strategy: Read ALL sections and merge into our flat dict
        for section in real_config.sections():
            for key, value in real_config.items(section):
                # Strip inline comments
                if '#' in value:
                    value = value.split('#')[0].strip()
                if ';' in value:
                    value = value.split(';')[0].strip()

                # Try to convert to appropriate types
                if value.lower() in ['true', 'yes', 'on']:
                    config_defaults[key] = True
                elif value.lower() in ['false', 'no', 'off']:
                    config_defaults[key] = False
                else:
                    try:
                        if '.' in value:
                           config_defaults[key] = float(value)
                        else:
                           config_defaults[key] = int(value)
                    except ValueError:
                        config_defaults[key] = value

    # Apply config_overrides on top of config_defaults
    final_config = {**config_defaults, **(config_overrides or {})}
    config = MockConfig(final_config)
    
    # Instantiate Worker
    worker = None
    
    try:
        # Worker Mapping
        worker_map = {
            "buy_and_hold": BuyAndHoldWorkerLogic,
            "daily_plays": DailyPlaysWorkerLogic,
            "vcp_smallcap": VCPSmallcapWorkerLogic,
            "volume_absorption": VolumeAbsorptionWorkerLogic,
            "orb": ORBWorkerLogic,
            "buy_the_dip": BuyTheDipWorkerLogic,
            "momentum_breakout": MomentumBreakoutWorkerLogic,
            "vwap": VWAPWorkerLogic,
            "parabolic": ParabolicWorkerLogic,
            "livermore_intraday": LivermoreIntradayWorkerLogic
        }

        if worker_name in worker_map:
            worker_class = worker_map[worker_name]
            
            # Define Mixin to override time checks
            class ReplayTimeMixin:
                def __init__(self, *args, **kwargs):
                    self._replay_timestamp = kwargs.pop('replay_timestamp', None)
                    super().__init__(*args, **kwargs)
                    
                def is_within_entry_hours(self, symbol: str = "", timestamp = None):
                    # Force the replay timestamp if provided
                    ts = self._replay_timestamp if self._replay_timestamp else timestamp
                    return super().is_within_entry_hours(symbol, timestamp=ts)

                # Monkey patch for VolumeAbsorption which uses _is_trading_hours instead
                def _is_trading_hours(self):
                    # Redirect to standard logic which uses our mocked timestamp
                    # CRITICAL: is_within_entry_hours returns (bool, float). We need bool.
                    return self.is_within_entry_hours()[0]

            # Dynamic subclass to add replay capability
            class ReplayWorker(ReplayTimeMixin, worker_class):
                pass
                
            replay_timestamp = None
            if args and args.timestamp:
                try:
                    # Basic ISO parsing
                    replay_timestamp = datetime.fromisoformat(args.timestamp.replace('Z', '+00:00'))
                except ValueError:
                    pass

            if worker_name == "daily_plays" or worker_name == "livermore_intraday":
                 # DailyPlays and Livermore hardcode worker_name internally
                 worker = ReplayWorker(
                    execution_engine, 
                    risk_manager, 
                    config,
                    replay_timestamp=replay_timestamp
                )
            else:
                # Standard signature
                worker = ReplayWorker(
                    worker_name, 
                    execution_engine, 
                    risk_manager, 
                    config,
                    replay_timestamp=replay_timestamp
                )
            
            logger.info(f"🔧 Worker {worker_name} initialized with separate logging + ODS support + Replay Time Override")
            
            # Setup Logging Capture AFTER instantiation
            logger_name = f"Worker.{worker_name}"
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            
            # We don't remove existing handlers (console/file), just add ours
            list_handler = ListHandler()
            formatter = logging.Formatter('%(message)s')
            list_handler.setFormatter(formatter)
            logger.addHandler(list_handler)
        else:
            logger.error(f"Unknown worker: {worker_name}")
            return {
                "worker": worker_name,
                "decision": "ERROR",
                "logs": [{"level": "ERROR", "message": f"Unknown worker: {worker_name}"}],
                "checks": []
            }
        
        # Run Evaluation
        result = False
        
        # Check for Scan Mode (Iterate through the day)
        if hasattr(args, 'scan_mode') and args.scan_mode and 'bars_1min' in opportunity_data:
            bars_1min = opportunity_data['bars_1min']
            logger.info(f"🔄 Scanning {len(bars_1min)} bars for valid entry...")
            
            # Start from index 30 (allow warmup)
            start_idx = 30
            step = 1 # Check every bar
            
            for i in range(start_idx, len(bars_1min), step):
                # Slice data up to current moment
                current_bars = bars_1min[:i+1]
                current_bar = current_bars[-1]
                
                # Extract timestamp
                ts_extract = current_bar.get('timestamp') if isinstance(current_bar, dict) else current_bar.timestamp
                try:
                    if isinstance(ts_extract, datetime):
                        ts = ts_extract
                    else:
                        ts = datetime.fromisoformat(ts_extract.replace('Z', '+00:00'))
                    
                    # Update Worker Time (Mixin magic)
                    worker._replay_timestamp = ts
                    
                    # Update Opportunity Data with partial history
                    # Some workers use 'bars_1min', others 'bars'
                    opp_slice = opportunity_data.copy()
                    opp_slice['bars_1min'] = current_bars
                    opp_slice['bars'] = current_bars
                    opp_slice['current_price'] = current_bar.get('close') if isinstance(current_bar, dict) else current_bar.close
                    
                    # Hack: Clean logs for this iteration to avoid clutter? 
                    # No, we want to see logs of the successful one. 
                    # But if we run 300 times, logs will be huge.
                    # We should capture logs only if result is True?
                    # For performance, clear list_handler if False?
                    list_handler.log_records = [] 
                    
                    result = await worker.should_enter(opp_slice)
                    
                    if result:
                        logger.info(f"✅ FOUND ENTRY at {ts.isoformat()}")
                        break
                        
                except Exception as e:
                    import traceback
                    logger.warning(f"⚠️ Scan iteration {i} failed: {e}")
                    logger.warning(traceback.format_exc())
                    pass
        else:
            # Standard Single Point Evaluation
            result = await worker.should_enter(opportunity_data)
        
        decision = "ACCEPTED" if result else "REJECTED"
        
        # Parse Logs to infer checks (Heuristic) -> Use logs from the LAST run (Successful one or Last failed)
        checks = []
        for log in list_handler.log_records:
            msg = log["message"]
            if "REJECTED" in msg or "Rejected" in msg:
                checks.append({"status": "FAIL", "message": msg})
            elif "✅" in msg:
                checks.append({"status": "PASS", "message": msg})
            elif "⚠️" in msg:
                checks.append({"status": "WARNING", "message": msg})
            elif "⚪" in msg:
                 checks.append({"status": "INFO", "message": msg})

        decision = "ACCEPTED" if result else "REJECTED"
        
        # SCRIPT ADDITION: Full Trade Simulation
        outcome = None
        if decision == "ACCEPTED" and 'bars' in opportunity_data:
            try:
                bars = opportunity_data['bars']
                # Determine Entry Time/Price matching the accepted decision
                entry_time = None
                entry_price = 0
                entry_idx = -1
                
                # Check for Scan Mode variable leakage
                if hasattr(args, 'scan_mode') and args.scan_mode:
                    try:
                        # 'i' is the loop variable from the scan loop above. 
                        # It holds the index where the break happened.
                        # 'bars_1min' in opportunity_data holds the FULL data.
                        bars = opportunity_data.get('bars_1min', bars)
                        entry_idx = i
                        bar = bars[entry_idx]
                        
                        ts_val = bar.get('timestamp') if isinstance(bar, dict) else bar.timestamp
                        if isinstance(ts_val, str):
                            entry_time = datetime.fromisoformat(ts_val.replace('Z', '+00:00'))
                        else:
                            entry_time = ts_val
                            
                        entry_price = float(bar.get('close') if isinstance(bar, dict) else bar.close)
                        
                        # Fix for WorkerStopManager which uses datetime.now() (naive)
                        if entry_time and entry_time.tzinfo:
                            entry_time = entry_time.replace(tzinfo=None)
                            
                    except Exception as e:
                        logging.warning(f"Failed to retrieve scan index: {e}")
                        pass

                if entry_idx == -1 and args and args.timestamp:
                    try:
                        ts_str = args.timestamp.replace('Z', '+00:00')
                        target_ts = datetime.fromisoformat(ts_str)
                        for idx, bar in enumerate(bars):
                            b_ts = bar.get('timestamp') if isinstance(bar, dict) else bar.timestamp
                            if isinstance(b_ts, str):
                                b_ts = datetime.fromisoformat(b_ts.replace('Z', '+00:00'))
                                
                            if b_ts >= target_ts:
                                entry_idx = idx
                                entry_time = b_ts
                                # Fix for WorkerStopManager
                                if entry_time and entry_time.tzinfo:
                                    entry_time = entry_time.replace(tzinfo=None)
                                    
                                entry_price = float(bar.get('close') if isinstance(bar, dict) else bar.close)
                                break
                    except:
                        pass
                
                if entry_idx == -1 and len(bars) > 0:
                     entry_idx = len(bars) - 1
                     entry_price = float(bars[-1].close)
                     entry_time = datetime.now() 

                if entry_idx != -1:
                    symbol = opportunity_data.get('symbol', 'UNKNOWN')
                    logging.info(f"🚀 Simulating Trade Management for {symbol} from Entry @ {entry_price:.2f}...")
                    
                    # DISABLE TIME CHECKS FOR REPLAY (Avoid stale date issues)
                    worker.stop_manager.config.max_position_hours = None
                    
                    # Register position 
                    worker.stop_manager.register_position(symbol, entry_time=entry_time)
                    
                    max_price = entry_price
                    exit_price = None
                    exit_reason = None
                    exit_time_val = None
                    
                    future_bars = bars[entry_idx+1:]
                    for fb in future_bars:
                        fb_ts = fb.timestamp if hasattr(fb, 'timestamp') else datetime.fromisoformat(fb.get('timestamp').replace('Z', '+00:00'))
                        fb_close = float(fb.close if hasattr(fb, 'close') else fb.get('close'))
                        
                        if fb_close > max_price:
                            max_price = fb_close
                            
                        # Check exit
                        should_exit, reason = worker.stop_manager.check_exit(
                            symbol=symbol,
                            current_price=fb_close,
                            entry_price=entry_price,
                            market_data=None
                        )
                        
                        if should_exit:
                            exit_price = fb_close
                            exit_reason = reason
                            exit_time_val = fb_ts
                            logging.info(f"🛑 EXIT TRIGGERED at {fb_ts}: {reason} @ {exit_price:.2f}")
                            break
                            
                    if exit_price:
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                        max_gain = ((max_price - entry_price) / entry_price) * 100
                        logging.info(f"💰 TRADE RESULT: PnL={pnl_pct:.2f}% | MaxRun={max_gain:.2f}% | Reason={exit_reason}")
                        outcome = {
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "pnl_pct": round(pnl_pct, 2),
                            "max_run_pct": round(max_gain, 2),
                            "exit_reason": exit_reason,
                            "exit_time": exit_time_val.isoformat()
                        }
                    else:
                        last_price = float(bars[-1].close if hasattr(bars[-1], 'close') else bars[-1].get('close'))
                        pnl_pct = ((last_price - entry_price) / entry_price) * 100
                        logging.info(f"⚠️ TRADE OPEN AT END OF DATA: PnL={pnl_pct:.2f}% (Price: {last_price:.2f})")
                        outcome = {
                            "status": "OPEN",
                            "current_pnl": round(pnl_pct, 2)
                        }

            except Exception as e:
                logging.error(f"Error in trade simulation: {e}")
                import traceback
                logging.error(traceback.format_exc())
                pass

        return {
            "worker": worker_name,
            "decision": decision,
            "logs": list_handler.log_records,
            "checks": checks,
            "input_data": opportunity_data,
            "outcome": outcome
        }
        
    except Exception as e:
        import traceback
        return {
            "decision": "ERROR",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "logs": list_handler.log_records
        }

def main():
    parser = argparse.ArgumentParser(description="Replay Worker Logic")
    parser.add_argument("--worker_name", required=True, help="Name of the worker (e.g., buy_and_hold)")
    parser.add_argument("--data", required=False, help="JSON string of opportunity data (or pass via stdin)")
    parser.add_argument("--data_file", required=False, help="Path to JSON file containing opportunity data (bypass CLI limit)")
    parser.add_argument("--config", help="JSON string of config overrides")
    parser.add_argument("--timestamp", help="ISO format timestamp for replay (e.g. 2025-12-12T09:30:00)")
    parser.add_argument('--scan_mode', action='store_true', help='Iterate through all bars to find an entry')
    
    args = parser.parse_args()
    
    args = parser.parse_args()
    
    # DEBUG: Print received arguments to stderr/stdout so it shows in logs
    print(f"DEBUG: Replay Args received: timestamp='{args.timestamp}' worker='{args.worker_name}'")
    
    try:
        # Get Data (File > Arg > Stdin)
        data_str = None
        
        if args.data_file:
            try:
                with open(args.data_file, 'r') as f:
                    data_str = f.read()
            except Exception as e:
                raise ValueError(f"Failed to read data file: {e}")
        elif args.data:
            data_str = args.data
        else:
            if not sys.stdin.isatty():
                data_str = sys.stdin.read()
            else:
                data_str = None
                
        if not data_str:
            raise ValueError("Empty data provided. Pass --data_file, --data arg, or pipe JSON to stdin.")
            
        opportunity_data = json.loads(data_str)
        config_overrides = json.loads(args.config) if args.config else {}
        
        # Run Async Logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(replay_worker(args.worker_name, opportunity_data, config_overrides, args))
        
        # Output JSON to stdout
        print(json.dumps(result, indent=2, cls=CustomJSONEncoder))
        
    except json.JSONDecodeError:
        print(json.dumps({"decision": "ERROR", "error": "Invalid JSON in input data", "logs": []}))
    except Exception as e:
        import traceback
        error_result = {
            "decision": "ERROR",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "logs": [{"level": "ERROR", "message": f"Critical Failure: {str(e)}"}]
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(0) # Exit 0 so backend doesn't think the process failed unexpectedly, but we handle error in JSON

if __name__ == "__main__":
    main()
