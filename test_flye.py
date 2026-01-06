#!/usr/bin/env python3
"""Quick test to check FLYE stock info"""

from yahooquery import Ticker
import json

symbol = 'FLYE'
ticker = Ticker(symbol)

print(f"\n{'='*60}")
print(f"Checking {symbol} info")
print(f"{'='*60}\n")

# Get quote
quote = ticker.quotes
if symbol in quote:
    data = quote[symbol]
    print(f"Symbol: {data.get('symbol', 'N/A')}")
    print(f"Name: {data.get('longName', data.get('shortName', 'N/A'))}")
    print(f"Exchange: {data.get('exchange', 'N/A')}")
    print(f"Quote Type: {data.get('quoteType', 'N/A')}")
    print(f"Price: ${data.get('regularMarketPrice', 'N/A')}")
    print(f"Volume: {data.get('regularMarketVolume', 'N/A'):,}")
    print(f"Market Cap: {data.get('marketCap', 'N/A')}")
    print(f"% Change: {data.get('regularMarketChangePercent', 'N/A'):.2f}%")
else:
    print(f"❌ No data found for {symbol}")
    print(f"Response: {quote}")
