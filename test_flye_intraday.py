#!/usr/bin/env python3
"""Check FLYE intraday movement to understand why scanner missed it"""

from yahooquery import Ticker
from datetime import datetime, timedelta
import pandas as pd

symbol = 'FLYE'

print(f"\n{'='*70}")
print(f"Analyzing {symbol} intraday movement - Dec 1, 2025")
print(f"{'='*70}\n")

ticker = Ticker(symbol)

# Get current price info
quote = ticker.quotes.get(symbol, {})
current_price = quote.get('regularMarketPrice', 'N/A')
prev_close = quote.get('regularMarketPreviousClose', 'N/A')
open_price = quote.get('regularMarketOpen', 'N/A')
volume = quote.get('regularMarketVolume', 'N/A')
change_pct = quote.get('regularMarketChangePercent', 'N/A')

print(f"📊 Current Status:")
print(f"   Previous Close: ${prev_close:.2f}")
print(f"   Open: ${open_price:.2f}")
print(f"   Current: ${current_price:.2f}")
print(f"   Change: {change_pct:.2f}%")
print(f"   Volume: {volume:,}")

# Try to get intraday data
print(f"\n📈 Attempting to fetch intraday bars...")

try:
    # Get 1-day history with 1-minute interval
    history = ticker.history(period='1d', interval='1m')

    if not history.empty:
        print(f"\n✅ Got {len(history)} 1-minute bars\n")

        # Show first few bars (market open)
        print("🔔 Market Open (First 10 bars):")
        print(history.head(10)[['open', 'high', 'low', 'close', 'volume']].to_string())

        # Show recent bars
        print("\n🕐 Recent Activity (Last 10 bars):")
        print(history.tail(10)[['open', 'high', 'low', 'close', 'volume']].to_string())

        # Key levels
        day_low = history['low'].min()
        day_high = history['high'].max()
        first_bar_close = history.iloc[0]['close']

        print(f"\n📊 Key Levels:")
        print(f"   First bar close: ${first_bar_close:.2f}")
        print(f"   Day low: ${day_low:.2f}")
        print(f"   Day high: ${day_high:.2f}")
        print(f"   Low → High move: {((day_high - day_low) / day_low * 100):.1f}%")

        # Check when it crossed $15
        above_15 = history[history['high'] > 15.0]
        if not above_15.empty:
            first_above_15 = above_15.index[0]
            print(f"\n⚠️  Crossed $15 at: {first_above_15}")
            print(f"   Time since market open: {(first_above_15 - history.index[0]).total_seconds() / 60:.0f} minutes")
    else:
        print("❌ No intraday data available")

except Exception as e:
    print(f"❌ Error fetching intraday data: {e}")

# Check if it was a pre-market mover
print(f"\n🌅 Pre-market Analysis:")
print(f"   Previous Close: ${prev_close:.2f}")
print(f"   Market Open: ${open_price:.2f}")
pre_market_gap = ((open_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
print(f"   Pre-market Gap: {pre_market_gap:.2f}%")

if pre_market_gap > 50:
    print(f"   🚀 MASSIVE pre-market gap! This explains the move.")
