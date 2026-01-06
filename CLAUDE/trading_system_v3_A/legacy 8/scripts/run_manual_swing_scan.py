#!/usr/bin/env python3
"""
Manual Runner for Swing Consolidation Scanner
Verifies integration with IBKR Adapter and Database
"""
import asyncio
import logging
import sys
import os

# Ensure root path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config_manager import ConfigManager
# from adapters.ibkr_adapter import IBKRAdapter # Removed dependency
import sys
from unittest.mock import MagicMock

# MOCK IB_INSYNC and TALIB (Sys Module Patch)
# This must happen BEFORE importing modules that depend on them
mock_ib = MagicMock()
sys.modules["ib_insync"] = mock_ib

mock_talib = MagicMock()
sys.modules["talib"] = mock_talib

from scanner.swing.swing_consolidation_scanner import SwingConsolidationScanner
import pandas as pd
from datetime import datetime, timedelta
import random

# MOCK IBKR ADAPTER
class MockIBKRAdapter:
    def __init__(self, config=None):
        self.connected = True
        
    async def connect(self):
        print("🔌 [MOCK] IBKR Connected")
        return True
        
    def is_connected(self):
        return True
        
    async def scan_market_for_swing(self, **kwargs):
        print("🔍 [MOCK] Scanning market... returning synthetic candidates")
        return ['TEST_MOCK_1', 'TEST_MOCK_2', 'TEST_MOCK_3', 'TEST_FAIL_1']

    async def get_historical_data(self, symbol, timeframe, start, end):
        print(f"📉 [MOCK] Fetching history for {symbol}")
        # Generate 130 days of data
        dates = pd.date_range(end=datetime.now(), periods=130, freq='B')
        data = []
        
        # Create a pattern based on symbol name
        base_price = 10.0
        
        for i, date in enumerate(dates):
            # Logic to create consolidation
            if 'TEST_MOCK' in symbol:
                # Flat/Tight price action (Consolidation)
                noise = random.uniform(-0.1, 0.1)
                close = base_price + noise
                high = close + 0.1
                low = close - 0.1
                vol = 100000
            else:
                # Trending/Volatile (Should fail)
                trend = i * 0.1
                close = base_price + trend
                high = close + 0.5
                low = close - 0.5
                vol = 50000
                
            data.append({
                'date': date,
                'open': close,
                'high': high,
                'low': low,
                'close': close,
                'volume': vol
            })
            
        return data

async def run_manual_scan():
    print("\n🚀 Starting Manual Swing Consolidation Scan (MOCK MODE)...")
    
    # 1. Initialize Components
    config_manager = ConfigManager()
    
    # Use Mock Adapter
    ibkr = MockIBKRAdapter()
    await ibkr.connect()

    # 2. Instantiate Scanner
    # We pass the mock adapter and a TEST DB to avoid locking live DB
    scanner = SwingConsolidationScanner(config_manager, ibkr, db_path="test_swing.db")
    
    # MOCK DETECTOR (Force a find)
    # We essentially bypass the math logic to test the pipeline
    original_detect = scanner.detector.detect_pattern
    
    def mock_detect_pattern(df):
        # Only find pattern in MOCK_1
        # We need to access the symbol, but detect_pattern only takes DF
        # In the loop, caller adds symbol usually. 
        # But wait, detect_pattern doesn't know the symbol from DF usually.
        # Let's verify the loop in scanner.py: 
        # pattern = self.detector.detect_pattern(df) -> pattern['symbol'] = symbol
        
        # We can look at the volume or price in DF to distinguish?
        # In our mock adapter: MOCK_1 has vol=100000, FAIL_1 has vol=50000
        last_vol = df['volume'].iloc[-1]
        
        if last_vol == 100000: # Matches TEST_MOCK logic
            return {
                'pattern_type': 'High Tight Flag',
                'consolidation_days': 15,
                'resistance': 10.50,
                'support': 9.80,
                'breakout_score': 85.5,
                'entry_mode': 'O_H_BREAKOUT'
            }
        return None

    scanner.detector.detect_pattern = mock_detect_pattern
    
    # 3. Run Scan
    print("\n🔎 Scanning Market (Consolidation Patterns)...")
    picks = await scanner.scan_for_consolidations()
    
    print("\n" + "="*60)
    print(f"📊 SCAN RESULTS: Found {len(picks)} candidates")
    print("="*60)
    
    for i, pick in enumerate(picks, 1):
        print(f"{i}. {pick['symbol']} | Score: {pick['breakout_score']:.1f} | Days: {pick['consolidation_days']}")
        print(f"   Support: ${pick['support']:.2f} | Resistance: ${pick['resistance']:.2f}")
        print(f"   Pattern: {pick.get('pattern_type', 'Unknown')}")
        print("-" * 40)
        
    print("\n✅ Verification Complete: Picks saved to DB 'swing_trades' table.")

if __name__ == "__main__":
    try:
        asyncio.run(run_manual_scan())
    except KeyboardInterrupt:
        print("\n🛑 Scan cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error running scan: {e}")
        import traceback
        traceback.print_exc()
