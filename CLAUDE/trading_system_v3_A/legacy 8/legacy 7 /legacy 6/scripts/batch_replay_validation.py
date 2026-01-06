#!/usr/bin/env python3
import subprocess
import sys
import time

# List of tickers to replay (Symbol, Date)
REPLAY_TARGETS = [
    ('AMST', '2025-12-17'),
    ('VERO', '2025-12-17'),
    ('RZLV', '2025-12-17'),
    ('RZLT', '2025-12-17'),
    ('RR', '2025-12-17'),
    ('RILY', '2025-12-17'),
    ('MSTX', '2025-12-17'),
    ('LAES', '2025-12-17'),
    ('BTBT', '2025-12-17'),
    ('BEAT', '2025-12-17'),
    ('ALDX', '2025-12-17'),
    ('XTKG', '2025-12-16'),
    ('TSLS', '2025-12-16'),
    ('BITF', '2025-12-16'),
    ('ABTC', '2025-12-09')
]

def run_replay(symbol, date):
    print(f"\n{'='*50}")
    print(f"🎬 REPLAYING: {symbol} on {date}")
    print(f"{'='*50}")
    
    cmd = [
        sys.executable, 'replay_testing/run_replay.py',
        '--date', date,
        '--symbols', symbol,
        '--workers', 'short_parabolic',  # Focus on the new worker, or all? User asked "if THE worker can be profitable"
        '--market-db', 'trading_data.db', 
        '--trading-db', 'trading_data.db'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # Check for trade execution in output
        if "Simulated trades: 0" in result.stdout:
            print(f"⚠️  No trades for {symbol}")
            return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error replaying {symbol}: {e}")
        print(e.stderr)
        return False

def main():
    print(f"🚀 Starting Batch Replay for {len(REPLAY_TARGETS)} tickers...")
    
    success_count = 0
    trade_count = 0
    
    for symbol, date in REPLAY_TARGETS:
        if run_replay(symbol, date):
            trade_count += 1
        success_count += 1
        
    print(f"\n🏁 BATCH COMPLETE. Executed {success_count} replays.")

if __name__ == "__main__":
    main()
