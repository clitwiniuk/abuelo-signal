#!/usr/bin/env python3
"""
Check XXII data time coverage and trading hours
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.csv_data_provider import CSVDataProvider

async def check_xxii_hours():
    """Check what hours XXII data covers"""
    
    print("🕐 CHECKING XXII DATA HOURS AND TRADING RESTRICTIONS")
    print("=" * 60)
    
    try:
        data_provider = CSVDataProvider()
        await data_provider.connect()
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 1000)
        if not bars:
            print("❌ No XXII data available")
            return
        
        print(f"📊 Got {len(bars)} bars for XXII")
        
        # Analyze time distribution
        times = []
        for bar in bars:
            timestamp = pd.to_datetime(bar.timestamp)
            times.append(timestamp)
        
        print(f"\n📅 DATE RANGE:")
        print(f"   From: {min(times)}")
        print(f"   To:   {max(times)}")
        
        # Check hours distribution
        hours = [t.hour for t in times]
        hour_counts = pd.Series(hours).value_counts().sort_index()
        
        print(f"\n🕐 HOUR DISTRIBUTION:")
        for hour, count in hour_counts.items():
            time_str = f"{hour:02d}:00-{hour:02d}:59"
            bar_pct = (count / len(bars)) * 100
            print(f"   {time_str}: {count:4d} bars ({bar_pct:5.1f}%)")
        
        # Check specific time ranges
        print(f"\n⏰ TRADING HOURS ANALYSIS:")
        
        # Market hours (9:30-16:00 ET)
        market_hours = [t for t in times if 9 <= t.hour < 16 or (t.hour == 9 and t.minute >= 30)]
        print(f"   Market hours (9:30-16:00): {len(market_hours)} bars ({len(market_hours)/len(bars)*100:.1f}%)")
        
        # ORB hours (9:30-13:00)
        orb_hours = [t for t in times if 9 <= t.hour < 13 or (t.hour == 9 and t.minute >= 30)]
        print(f"   ORB hours (9:30-13:00): {len(orb_hours)} bars ({len(orb_hours)/len(bars)*100:.1f}%)")
        
        # MACDV restricted hours (avoid first/last 30 min)
        macdv_hours = [t for t in times if 
                      (10 <= t.hour < 15) or  # Full hours 10:00-15:00
                      (t.hour == 15 and t.minute < 30)]  # 15:00-15:30
        print(f"   MACDV hours (10:00-15:30): {len(macdv_hours)} bars ({len(macdv_hours)/len(bars)*100:.1f}%)")
        
        # Extended hours
        extended_hours = [t for t in times if t.hour < 9 or t.hour >= 16]
        print(f"   Extended hours (pre/after): {len(extended_hours)} bars ({len(extended_hours)/len(bars)*100:.1f}%)")
        
        print(f"\n🔍 SAMPLE TIMESTAMPS:")
        for i in [0, len(bars)//4, len(bars)//2, 3*len(bars)//4, -1]:
            bar = bars[i]
            dt = pd.to_datetime(bar.timestamp)
            print(f"   Bar {i+1:4d}: {dt} (Hour: {dt.hour:02d}, Price: ${bar.close:.2f})")
        
        await data_provider.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_xxii_hours())