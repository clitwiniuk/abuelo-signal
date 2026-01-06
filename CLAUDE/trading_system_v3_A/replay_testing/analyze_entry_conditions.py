#!/usr/bin/env python3
"""
Analizar condiciones exactas de POM en el momento de entrada real
"""

import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('trading_data.db')
cursor = conn.cursor()

# Get all bars for POM on 2025-12-05 up to entry time (15:44)
cursor.execute("""
SELECT 
    bar_timestamp,
    open_price, high_price, low_price, close_price,
    volume
FROM trade_intraday_bars tib
JOIN trades t ON tib.trade_id = t.trade_id
WHERE t.symbol = 'POM' 
  AND date(bar_timestamp) = '2025-12-05'
  AND bar_timestamp <= '2025-12-05 15:44:00'
ORDER BY bar_timestamp
""")

bars = cursor.fetchall()

print(f"Total bars up to 15:44: {len(bars)}")
print()

# Calculate VWAP for last 20 bars (as worker does)
if len(bars) >= 20:
    recent_bars = bars[-20:]
    
    total_pv = sum(close * vol for _, _, _, _, close, vol in recent_bars)
    total_volume = sum(vol for _, _, _, _, _, vol in recent_bars)
    
    vwap = total_pv / total_volume if total_volume > 0 else 0
    
    # Get last bar (15:44)
    last_bar = bars[-1]
    timestamp, open_p, high, low, close, volume = last_bar
    
    price_above_vwap_pct = ((close - vwap) / vwap * 100) if vwap > 0 else 0
    
    print(f"📊 Análisis de la barra de 15:44 (momento de entrada real):")
    print(f"   Timestamp: {timestamp}")
    print(f"   Close: ${close:.2f}")
    print(f"   VWAP (last 20 bars): ${vwap:.2f}")
    print(f"   Price above VWAP: {price_above_vwap_pct:.2f}%")
    print(f"   ✅ Cumple umbral 0.5%: {'SÍ' if price_above_vwap_pct >= 0.5 else 'NO'}")
    print()
    
    # Calculate VWAP slope
    if len(bars) >= 10:
        mid_bars = bars[-10:-5]
        recent_bars_slope = bars[-5:]
        
        vwap_mid = sum(c * v for _, _, _, _, c, v in mid_bars) / sum(v for _, _, _, _, _, v in mid_bars) if sum(v for _, _, _, _, _, v in mid_bars) > 0 else vwap
        vwap_recent = sum(c * v for _, _, _, _, c, v in recent_bars_slope) / sum(v for _, _, _, _, _, v in recent_bars_slope) if sum(v for _, _, _, _, _, v in recent_bars_slope) > 0 else vwap
        
        vwap_slope = (vwap_recent - vwap_mid) / vwap_mid if vwap_mid > 0 else 0
        
        print(f"   VWAP Slope: {vwap_slope:.6f}")
        print(f"   ✅ Cumple umbral 0.0001: {'SÍ' if vwap_slope >= 0.0001 else 'NO'}")
        print()

# Show bars around entry time
print(f"📈 Barras alrededor de la entrada (15:43-15:46):")
print(f"{'Timestamp':<25} {'Open':<8} {'High':<8} {'Low':<8} {'Close':<8} {'Volume':<10}")
print("-" * 80)

for bar in bars[-5:]:
    timestamp, open_p, high, low, close, volume = bar
    print(f"{timestamp:<25} ${open_p:<7.2f} ${high:<7.2f} ${low:<7.2f} ${close:<7.2f} {volume:<10}")

conn.close()
