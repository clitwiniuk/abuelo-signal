from yahooquery import Ticker
import pandas as pd

symbols = ['AAPL', 'TSLA', 'GME', 'AMC']
print(f"Fetching stats for: {symbols}")

t = Ticker(symbols)
modules = 'defaultKeyStatistics summaryDetail'
data = t.get_modules(modules)

for symbol in symbols:
    print(f"\n--- {symbol} ---")
    try:
        stats = data[symbol]['defaultKeyStatistics']
        summary = data[symbol]['summaryDetail']
        
        float_shares = stats.get('floatShares')
        short_ratio = stats.get('shortRatio')
        short_percent = stats.get('shortPercentOfFloat')
        
        print(f"Float: {float_shares}")
        print(f"Short Ratio: {short_ratio}")
        print(f"Short % of Float: {short_percent}")
    except Exception as e:
        print(f"Error: {e}")
