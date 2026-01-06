#!/usr/bin/env python3
"""
Simple Polygon downloader that matches the user's original working script.
Downloads data exactly as it comes from Polygon API without complex timezone conversions.
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

# Global rate limiting shared across all instances
_global_request_times = []
_requests_per_minute = 5

class SimplePolygonDownloader:
    """
    Simple downloader that replicates the original working script logic.
    Downloads raw data without complex timezone conversions.
    """
    
    def __init__(self, api_key: str, data_path: str = "data/csv"):
        self.api_key = api_key
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    def _check_rate_limit(self):
        """Rate limiting for free tier: 5 calls per minute (global across all instances)"""
        global _global_request_times, _requests_per_minute
        
        now = time.time()
        # Remove requests older than 60 seconds
        _global_request_times = [t for t in _global_request_times if now - t < 60]
        
        # If we have reached the limit (5 requests), wait
        if len(_global_request_times) >= _requests_per_minute:
            sleep_time = 60 - (now - _global_request_times[0]) + 2  # Extra 2 seconds for safety
            if sleep_time > 0:
                print(f"⏳ Rate limit reached ({len(_global_request_times)}/5). Waiting {sleep_time:.0f}s...")
                time.sleep(sleep_time)
                # Clear old requests after waiting
                now = time.time()
                _global_request_times = [t for t in _global_request_times if now - t < 60]
        
        _global_request_times.append(now)
    
    def download_symbol(self, symbol: str, start_date_str: str = None, end_date_str: str = None, days: int = 10) -> bool:
        """
        Download symbol data using original working script logic.
        No complex timezone conversions - just download raw data.
        """
        try:
            # Calculate date range
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                # Use recent date range with free account considerations
                # Free accounts may have 1-2 day delay
                end_datetime = datetime.now() - timedelta(days=2)  # Account for potential delay
                end_date = end_datetime.date()
                start_date = (end_datetime - timedelta(days=days)).date()
            
            print(f"📥 Downloading {symbol} from {start_date} to {end_date}")
            
            # Rate limiting
            self._check_rate_limit()
            
            # Build URL - same as original script
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{start_date}/{end_date}"
            
            params = {
                'apikey': self.api_key,
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000
            }
            
            # Make request
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 429:
                print(f"⏳ {symbol}: Rate limited, waiting 65s and retrying...")
                time.sleep(65)
                # Retry once
                response = requests.get(url, params=params, timeout=30)
                if response.status_code != 200:
                    print(f"❌ {symbol}: HTTP {response.status_code} after retry")
                    return False
            elif response.status_code != 200:
                print(f"❌ {symbol}: HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            if data.get('status') != 'OK' or 'results' not in data:
                print(f"❌ {symbol}: No data available - Status: {data.get('status', 'Unknown')}")
                if 'message' in data:
                    print(f"    API message: {data['message']}")
                return False
            
            results = data['results']
            if not results:
                print(f"❌ {symbol}: Empty results")
                return False
            
            # Process data - original working script logic
            bars = []
            for result in results:
                # Convert timestamp from milliseconds (original working logic)
                timestamp = datetime.fromtimestamp(result['t'] / 1000)
                
                # Skip weekend data only
                if timestamp.weekday() >= 5:
                    continue
                
                # Original script: No additional filtering
                # Just take the data as-is from Polygon
                bar = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': result['o'],
                    'high': result['h'],
                    'low': result['l'],
                    'close': result['c'],
                    'volume': result['v']
                }
                bars.append(bar)
            
            if not bars:
                print(f"❌ {symbol}: No valid bars after filtering")
                return False
            
            # Save to CSV
            df = pd.DataFrame(bars)
            filepath = self.data_path / f"{symbol}_1_min.csv"
            df.to_csv(filepath, index=False)
            
            print(f"✅ {symbol}: {len(bars)} bars saved to {filepath}")
            print(f"    First timestamp: {bars[0]['timestamp']}")
            print(f"    Last timestamp: {bars[-1]['timestamp']}")
            return True
            
        except Exception as e:
            print(f"❌ {symbol}: Error - {str(e)}")
            return False
    
    def download_multiple(self, symbols: list, days: int = 10) -> dict:
        """Download multiple symbols"""
        results = {}
        
        print(f"🚀 Downloading {len(symbols)} symbols...")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] ", end="")
            results[symbol] = self.download_symbol(symbol, days)
            
            # Small delay between requests
            if i < len(symbols):
                time.sleep(1)
        
        # Summary
        successful = sum(results.values())
        print(f"\n📊 Results: {successful}/{len(symbols)} successful")
        
        return results

def main():
    """Test the simple downloader"""
    
    # Load API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ Set POLYGON_API_KEY environment variable")
        return
    
    downloader = SimplePolygonDownloader(api_key)
    
    # Test with the problematic symbols using the same date range as existing data
    test_symbols = ['AAPL', 'XXII']
    
    print("🔬 TESTING SIMPLE DOWNLOADER (Original Script Logic)")
    print("=" * 60)
    print("This should produce the same results as the original working script")
    print("Using same date range as existing data: 2025-07-21 to 2025-08-01")
    print()
    
    # Test individual symbol with specific date range
    print("Testing XXII with specific date range...")
    success = downloader.download_symbol('XXII', '2025-07-21', '2025-08-01')
    results = {'XXII': success}
    
    print("\n📊 COMPARISON:")
    for symbol in test_symbols:
        if results[symbol]:
            filepath = Path(f"data/csv/{symbol}_1_min.csv")
            if filepath.exists():
                df = pd.read_csv(filepath)
                print(f"{symbol}: {len(df)} lines (vs current: complex timezone logic)")
                
                # Show first and last timestamps
                if len(df) > 0:
                    first_time = df.iloc[0]['timestamp']
                    last_time = df.iloc[-1]['timestamp']
                    print(f"  Time range: {first_time} to {last_time}")

if __name__ == "__main__":
    main()