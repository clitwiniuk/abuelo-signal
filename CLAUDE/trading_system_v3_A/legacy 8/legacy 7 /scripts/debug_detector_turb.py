
import sqlite3
import json
import pandas as pd
from core.parabolic_extension_detector import ParabolicExtensionDetector

def run_debug():
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
    # Ensure correct columns
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    detector = ParabolicExtensionDetector()
    
    print(f"DEBUG: Analyze {len(df)} bars for TURB (2025-09-16)...")
    print("-" * 60)
    print(f"{'Time':<25} {'Price':<10} {'Stage':<10} {'Exhaust':<10} {'Signal':<10}")
    print("-" * 60)
    
    # Simulate streaming: Feed growing DF
    for i in range(50, len(df)):
        current_slice = df.iloc[:i+1].copy()
        current_bar = df.iloc[i]
        
        # Convert slice to list of dicts (compatible with MarketData defined in detector)
        bars_list = []
        for _, row in current_slice.iterrows():
            bars_list.append({
                'timestamp': row['timestamp'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })
        
        # Run detector with correct signature: symbol, bars
        # Note: detector expects objects with attributes or named tuples.
        # Let's check if it handles dicts. Looking at code: uses `bars[-1].close` etc.
        # So we need objects.
        class BarObj:
            def __init__(self, d):
                self.__dict__ = d
        
        obj_list = [BarObj(b) for b in bars_list]

        result = detector.detect_parabolic_extension("TURB", obj_list)
        
        if not result: continue
        
        # Unpack result (it returns ParabolicSignal object or dict? Data class!)
        # So result.stage, result.exhaustion_score
        
        # Filter for interesting moments (High price or signal)
        stage = getattr(result, 'stage', 'N/A')
        exhaustion = getattr(result, 'exhaustion_score', 0.0)
        signal = getattr(result, 'short_entry_opportunity', False)
        
        is_interesting = (
            stage == 'LATE' or 
            exhaustion > 0.5 or 
            current_bar['close'] > 18.0 or
            signal
        )
        
        if is_interesting:
            print(f"{current_bar['timestamp']:<25} {current_bar['close']:<10.2f} {stage:<10} {exhaustion:<10.2f} {signal}")

if __name__ == "__main__":
    run_debug()
