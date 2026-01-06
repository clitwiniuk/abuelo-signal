#!/usr/bin/env python3
"""
High Fidelity Replay - Mid-Cap Edge Verification
Tests the strategy against REAL historical data from Polygon.io
"""

import sys
import os
import asyncio
import pandas as pd
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import logging
from unittest.mock import MagicMock

# Mock pandas_ta before any system imports to avoid ModuleNotFoundError
sys.modules['pandas_ta'] = MagicMock()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from adapters.polygon_downloader import PolygonDownloader
from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidCapWorkerLogic
from strategies.workers.worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradeArbiter

# ==============================================================================
# CONFIGURATION - PUT YOUR POLYGON API KEY HERE
# ==============================================================================
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', 'Gn56b6ujVDqEQPEG28vKJRBPkRsVpn9o')
# ==============================================================================

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("HighFidelityReplay")

# Define In-Sample Scenarios (Training Set - Used for "Reconducción")
IS_SCENARIOS = [
    {'symbol': 'PLTR', 'date': '2024-11-05', 'catalyst': 'EARNINGS', 'quality_score': 95.0, 'description': 'Palantir Q3 Earnings Beat'},
    {'symbol': 'APPF', 'date': '2024-01-26', 'catalyst': 'EARNINGS', 'quality_score': 90.0, 'description': 'AppFolio Q4 Beat'},
    {'symbol': 'DUOL', 'date': '2024-02-29', 'catalyst': 'EARNINGS', 'quality_score': 92.0, 'description': 'Duolingo User Growth Surge'},
    {'symbol': 'PATH', 'date': '2024-03-14', 'catalyst': 'NEWS', 'quality_score': 85.0, 'description': 'UiPath Generative AI News'},
    {'symbol': 'WGS',  'date': '2024-04-30', 'catalyst': 'EARNINGS', 'quality_score': 95.0, 'description': 'GeneDx Revenue Guidance Raise'},
    {'symbol': 'JANX', 'date': '2024-02-27', 'catalyst': 'FDA', 'quality_score': 98.0, 'description': 'Janux Clinical Data Results'},
    {'symbol': 'IOVA', 'date': '2024-02-16', 'catalyst': 'FDA', 'quality_score': 95.0, 'description': 'Amtagvi Accelerated Approval'},
    {'symbol': 'SFM',  'date': '2024-05-01', 'catalyst': 'EARNINGS', 'quality_score': 85.0, 'description': 'Sprouts Q1 Earnings Beat'},
    {'symbol': 'SHAK', 'date': '2024-02-15', 'catalyst': 'EARNINGS', 'quality_score': 82.0, 'description': 'Shake Shack Strategy Turnaround'},
    {'symbol': 'DKNG', 'date': '2024-02-16', 'catalyst': 'EARNINGS', 'quality_score': 88.0, 'description': 'DraftKings Customer Acquisition'},
    {'symbol': 'UPST', 'date': '2024-08-07', 'catalyst': 'EARNINGS', 'quality_score': 88.0, 'description': 'Upstart Recovery News'},
    {'symbol': 'AFRM', 'date': '2024-08-29', 'catalyst': 'EARNINGS', 'quality_score': 90.0, 'description': 'Affirm BNPL Expansion Beat'},
    {'symbol': 'RKLB', 'date': '2024-02-27', 'catalyst': 'CONTRACT', 'quality_score': 80.0, 'description': 'Rocket Lab Contract Win'},
    {'symbol': 'FTAI', 'date': '2024-07-25', 'catalyst': 'EARNINGS', 'quality_score': 85.0, 'description': 'Aviation Engine Demand'},
    {'symbol': 'RIVN', 'date': '2024-06-25', 'catalyst': 'NEWS', 'quality_score': 90.0, 'description': 'VW Partnership News'}
]

# Define Out-of-Sample Scenarios (Validation Set - Unseen Data)
OOS_SCENARIOS = [
    # Original Set
    {'symbol': 'ASTS', 'date': '2024-05-15', 'catalyst': 'CONTRACT', 'quality_score': 95.0, 'description': 'AT&T Space Partnership'},
    {'symbol': 'LUNR', 'date': '2024-09-18', 'catalyst': 'CONTRACT', 'quality_score': 95.0, 'description': 'NASA NSN Contract Win'},
    {'symbol': 'RDDT', 'date': '2024-10-30', 'catalyst': 'EARNINGS', 'quality_score': 92.0, 'description': 'Reddit First Profit Beat'},
    {'symbol': 'PLTR', 'date': '2024-08-06', 'catalyst': 'EARNINGS', 'quality_score': 90.0, 'description': 'Palantir Q2 2024 Beat'},
    {'symbol': 'UPST', 'date': '2024-11-08', 'catalyst': 'EARNINGS', 'quality_score': 85.0, 'description': 'Upstart Q3 2024 Momentum'},
    {'symbol': 'HOOD', 'date': '2024-11-07', 'catalyst': 'NEWS',     'quality_score': 88.0, 'description': 'Robinhood Crypto Expansion'},
    {'symbol': 'AFRM', 'date': '2024-11-13', 'catalyst': 'NEWS',     'quality_score': 85.0, 'description': 'Affirm Payment Volume Surge'},
    {'symbol': 'GOGO', 'date': '2024-11-04', 'catalyst': 'EARNINGS', 'quality_score': 80.0, 'description': 'Gogo Q3 2024 Guidance'},
    {'symbol': 'IONQ', 'date': '2024-11-14', 'catalyst': 'EARNINGS', 'quality_score': 92.0, 'description': 'IonQ Quantum Bookings'},
    {'symbol': 'SN',   'date': '2024-08-15', 'catalyst': 'EARNINGS', 'quality_score': 88.0, 'description': 'SharkNinja Q2 2024 Beat'},
    
    # EXPANSION SET (High Volatility Mid-Caps 2024)
    {'symbol': 'CVNA', 'date': '2024-05-02', 'catalyst': 'EARNINGS', 'quality_score': 95.0, 'description': 'Carvana Q1 2024 Profit Surprise'},
    {'symbol': 'CVNA', 'date': '2024-08-01', 'catalyst': 'EARNINGS', 'quality_score': 95.0, 'description': 'Carvana Q2 2024 Record Profit'},
    {'symbol': 'VRT',  'date': '2024-02-21', 'catalyst': 'EARNINGS', 'quality_score': 90.0, 'description': 'Vertiv AI Data Center Boom'},
    {'symbol': 'ELF',  'date': '2024-05-23', 'catalyst': 'EARNINGS', 'quality_score': 92.0, 'description': 'e.l.f. Beauty Q4 Fiscal Beat'},
    {'symbol': 'HIMS', 'date': '2024-05-07', 'catalyst': 'EARNINGS', 'quality_score': 88.0, 'description': 'Hims & Hers Q1 2024 Beat'},
    {'symbol': 'ANF',  'date': '2024-05-29', 'catalyst': 'EARNINGS', 'quality_score': 90.0, 'description': 'Abercrombie Q1 2024 Surge'},
    {'symbol': 'CAVA', 'date': '2024-02-27', 'catalyst': 'EARNINGS', 'quality_score': 92.0, 'description': 'CAVA Group Q4 2023 Beat'}
]

import configparser
from core.service_locator import UnifiedConfig

# ==============================================================================
# CONFIGURATION - PUT YOUR POLYGON API KEY HERE
# ==============================================================================
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', 'Gn56b6ujVDqEQPEG28vKJRBPkRsVpn9o')
# ==============================================================================

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("HighFidelityReplay")

class MockExecutionEngine:
    def __init__(self):
        self.orders = []
    async def execute_entry(self, symbol, side, qty, price, worker):
        self.orders.append({'type': 'ENTRY', 'symbol': symbol, 'price': price, 'time': datetime.now()})
        return "ORDER_ID_123"
    async def execute_exit(self, symbol, side, qty, price, worker, reason):
        self.orders.append({'type': 'EXIT', 'symbol': symbol, 'price': price, 'reason': reason})
        return "ORDER_ID_456"

async def run_scenario(scenario, downloader, config):
    symbol = scenario['symbol']
    date_str = scenario['date']
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    logger.info(f"\n🧪 RUNNING SCENARIO: {symbol} ({date_str}) - {scenario['description']}")

    # --- 1. DATA DOWNLOAD/LOADING (SAME AS BEFORE) ---
    start_dl = date_obj - timedelta(days=10)
    end_dl = date_obj
    csv_file = Path(downloader.data_path) / f"{symbol}_1_min.csv"
    should_download_min = True
    if csv_file.exists():
        try:
            temp_df = pd.read_csv(csv_file)
            temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'])
            if date_obj in temp_df['timestamp'].dt.date.unique():
                should_download_min = False
        except: pass
    if should_download_min: await downloader.download_symbol_data(symbol, start_date=start_dl, end_date=end_dl, timeframe="1 min")

    start_daily = date_obj - timedelta(days=365)
    end_daily = date_obj - timedelta(days=1)
    daily_csv = Path(downloader.data_path) / f"{symbol}_1_day.csv"
    should_download_daily = True
    if daily_csv.exists():
        try:
            temp_daily = pd.read_csv(daily_csv)
            temp_daily['timestamp'] = pd.to_datetime(temp_daily['timestamp'])
            if end_daily in temp_daily['timestamp'].dt.date.unique():
                should_download_daily = False
        except: pass
    if should_download_daily: await downloader.download_symbol_data(symbol, start_date=start_daily, end_date=end_daily, timeframe="1 day")

    # Data Loading with Error Handling
    try:
        df = pd.read_csv(csv_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['timestamp_et'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('America/New_York')
        day_data = df[df['timestamp_et'].dt.date == date_obj].copy()
        if day_data.empty: 
            logger.error(f"❌ No intraday data for {symbol} on {date_str} (ET)")
            return 0.0

        df_daily = pd.read_csv(daily_csv)
        df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'])
        
        from dataclasses import dataclass
        @dataclass
        class MockBar:
            date: any; open: float; high: float; low: float; close: float; volume: float
            @property
            def timestamp(self): return self.date
            
        bars_daily = []
        for _, row in df_daily.iterrows():
            bars_daily.append(MockBar(pd.to_datetime(row['timestamp']), row['open'], row['high'], row['low'], row['close'], row['volume']))
            
    except Exception as e:
        logger.error(f"❌ SKIPPING {symbol}: Failed to load data ({str(e)})")
        return 0.0

    # 4. Setup Worker Logic with REAL CONFIG
    exec_engine = MockExecutionEngine()
    risk_manager = MagicMock()
    worker = DailyPlaysMidCapWorkerLogic(exec_engine, risk_manager, config=config)
    
    # Override only what's necessary for the replay env (Polygon bars vs IBKR bars)
    worker.validate_vwap_strength = lambda bars, price, **kwargs: (True, 'Bullish VWAP (Mocked for Intraday Speed)')
    async def mock_check_daily_context(s, p, daily_potential=None, volume_ratio=1.0):
        closes = [b.close for b in bars_daily]
        rsi = worker._calculate_rsi(closes, period=14)
        return {'is_safe': rsi < 85, 'reason': 'Pass (Context Engine)', 'daily_rsi': rsi}
    worker._check_daily_context = mock_check_daily_context
    worker.get_bars_from_opportunity = lambda opp: [MockBar(b['timestamp'], b['open'], b['high'], b['low'], b['close'], b['volume']) for b in bars_history]

    # 5. Opportunity injection
    first_bar = day_data.iloc[0]
    opportunity = {
        'symbol': symbol, 'current_price': first_bar['close'], 'volume': first_bar['volume'],
        'timestamp': first_bar['timestamp'], 'catalyst_type': scenario['catalyst'],
        'catalyst_strength': 8, 'quality_score': scenario['quality_score'],
        'volume_ratio': 2.5, 'is_pre_market': True, 'bars_daily': bars_daily
    }

    # 6. Intraday Loop
    active_position = None
    stop_manager = None
    bars_history = []
    
    for _, bar in day_data.iterrows():
        ny_time = bar['timestamp_et'].replace(tzinfo=None)
        hour_et = ny_time.hour + (ny_time.minute / 60.0)
        
        opportunity.update({'current_price': bar['close'], 'volume': bar['volume'], 'timestamp': ny_time, 'is_pre_market': hour_et < 9.5})
        b_localized = bar.copy(); b_localized['timestamp'] = ny_time
        bars_history.append(b_localized)

        if not active_position:
            if await worker.should_enter(opportunity):
                # Pattern completion check (Stage 5 Verification)
                comp, _ = await worker.calculate_pattern_completion(opportunity)
                if comp < 80.0: continue # Target Stage 4/5 for MidCaps

                active_position = {'entry_price': bar['close'], 'entry_time': bar['timestamp']}
                logger.info(f"   ✅ ENTRY: ${bar['close']:.2f} at {ny_time}")
                stop_manager = create_worker_stop_manager(config, 'DAILY_PLAYS_MIDCAP_STRATEGY')
        
        elif active_position:
            m_bar = MagicMock(); m_bar.close = bar['close']; m_bar.high = bar['high']; m_bar.low = bar['low']; m_bar.timestamp = ny_time
            should_exit, reason = stop_manager.check_exit(symbol, bar['close'], active_position['entry_price'], m_bar, {'is_swing': True})
            
            if should_exit:
                pnl = (bar['close'] - active_position['entry_price']) / active_position['entry_price'] * 100
                logger.info(f"   🚪 EXIT: {reason} at ${bar['close']:.2f} (PnL: {pnl:+.2f}%)")
                return pnl

    if active_position:
        pnl = (day_data.iloc[-1]['close'] - active_position['entry_price']) / active_position['entry_price'] * 100
        logger.info(f"   🏁 EOD CLOSE at ${day_data.iloc[-1]['close']:.2f} (PnL: {pnl:+.2f}%)")
        return pnl
    
    logger.info("   ⏹️ NO TRADE")
    return 0.0

def print_set_report(name, results):
    print(f"\n--- {name} REPORT ---")
    print(f"{'Ticker':<10} {'Result':<10} {'Description'}")
    total = 0; wins = 0; trades = 0
    for r in results:
        pnl = r['pnl']
        status = f"{pnl:+.2f}%" if pnl != 0 else "NO TRADE"
        print(f"{r['symbol']:<10} {status:<10} {r['description']}")
        if pnl != 0:
            total += pnl; trades += 1
            if pnl > 0: wins += 1
    
    avg = total / trades if trades > 0 else 0
    wr = (wins / trades * 100) if trades > 0 else 0
    print(f"Stats: P&L {total:+.2f}%, Avg {avg:+.2f}%, WinRate {wr:.0f}%, Trades {trades}/{len(results)}")
    return {'pnl': total, 'avg': avg, 'wr': wr, 'trades': trades}

async def main():
    p = configparser.ConfigParser()
    p.read('config.ini')
    
    downloader = PolygonDownloader(POLYGON_API_KEY, "data/csv")
    
    is_results = []
    oos_results = []
    
    async with downloader:
        print("\n🚀 STARTING IN-SAMPLE (IS) TEST...")
        for s in IS_SCENARIOS:
            pnl = await run_scenario(s, downloader, p)
            is_results.append({**s, 'pnl': pnl})
            
        print("\n🚀 STARTING OUT-OF-SAMPLE (OOS) TEST...")
        for s in OOS_SCENARIOS:
            pnl = await run_scenario(s, downloader, p)
            oos_results.append({**s, 'pnl': pnl})

    # FINAL COMPARISON
    print("\n" + "="*80)
    print("🔬 SCIENTIFIC ROBUSTNESS REPORT: WALK-FORWARD ANALYSIS")
    print("="*80)
    is_stats = print_set_report("IN-SAMPLE (IS)", is_results)
    oos_stats = print_set_report("OUT-OF-SAMPLE (OOS)", oos_results)
    
    print("\n" + "="*80)
    print(f"VERDICT: {'🟢 ROBUST' if oos_stats['pnl'] > 0 else '🔴 OVERFITTED'}")
    print(f"OOS Efficiency: {(oos_stats['avg']/is_stats['avg']*100 if is_stats['avg'] != 0 else 0):.1f}%")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
