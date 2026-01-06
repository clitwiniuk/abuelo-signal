
import sqlite3
import json
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic
from unittest.mock import MagicMock

async def run_debug():
    # 1. Load Data
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT intraday_bars FROM trade_ohlc_snapshots WHERE symbol='TURB' AND trading_date='2025-09-16'")
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("No data for TURB")
        return

    data = json.loads(row[0])
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 2. Setup Worker
    execution_engine = MagicMock()
    execution_engine.broker = MagicMock()
    # Mock ETB returning True
    f = asyncio.Future()
    f.set_result({'is_etb': True, 'shortable_shares': 50000, 'short_status': 'Available'})
    execution_engine.broker.get_short_data = MagicMock(return_value=f)
    
    risk_manager = MagicMock()
    
    worker = ShortParabolicWorkerLogic("short_parabolic", execution_engine, risk_manager)
    # Force context engine to exist if needed by detector (mock it)
    worker.context_engine = MagicMock()
    worker.context_engine.get_context.return_value = {'market_regime': 'NEUTRAL', 'volatility': 'HIGH'}

    print(f"DEBUG: Processing {len(df)} bars for TURB...")
    
    # 3. Iterate
    for i in range(50, len(df)): # Start after some warm up
        current_bar = df.iloc[i]
        # Build history
        history = [type('Bar', (object,), {'high': r['high'], 'low': r['low'], 'close': r['close'], 'open': r['open'], 'volume': r['volume']})() for _, r in df.iloc[:i+1].iterrows()]
        
        # Build opportunity dict
        opp = {
            'symbol': 'TURB',
            'current_price': current_bar['close'],
            'time': current_bar['timestamp'],
            'volume': current_bar['volume'],
            'bars_history': history,
            # We need to let the worker CALCULATE parabolic data internally usually? 
            # No, `should_enter` expects `parabolic_data` in opportunity?
            # Let's check the code. The worker usually receives opportunity produced by a scanner/detector.
            # IN REPLAY: The replay engine calls `worker.process_bar` or `worker.should_enter`?
            # ReplayEngine calls `worker.evaluate_decision`.
            # But the worker logic `should_enter` USES `parabolic_data`.
            # Where does it get it?
            # Ah, the `BaseWorkerLogic` or `ReplayEngine` usually runs the detector.
        }
        
        # We need to run the detector manually here to populate 'parabolic_data'
        # The worker has a detector: `worker.parabolic_detector`
        # We need to feed it the DF properly.
        
        # Let's slice the DF up to current index
        current_slice = df.iloc[:i+1].copy()
        p_data = worker.parabolic_detector.detect_parabolic_extension(current_slice)
        opp['parabolic_data'] = p_data

        # Now call should_enter
        decision = await worker.should_enter(opp)
        
        if decision:
            print(f"✅ TRADE ACCEPTED at {current_bar['timestamp']} Price={current_bar['close']}")
            break # Found it!
        else:
            # We want to see WHY it failed for interesting bars (High price area)
            if current_bar['close'] > 18.0 or i % 30 == 0:
                print(f"{current_bar['timestamp']}: Price={current_bar['close']} Stage={p_data.get('stage')} Exh={p_data.get('exhaustion_score',0):.2f}")

if __name__ == "__main__":
    asyncio.run(run_debug())
