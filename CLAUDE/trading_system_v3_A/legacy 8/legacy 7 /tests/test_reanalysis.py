#!/usr/bin/env python3
"""
Test script for temporal re-analysis functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner

def test_reanalysis_logic():
    """Test the temporal re-analysis logic"""
    print("🧪 Testing Re-analysis Logic")
    print("=" * 50)
    
    # Create scanner instance
    scanner = SmallcapDailyScanner()
    
    # Test 1: Check initial state
    print("\n📊 Test 1: Initial State")
    print(f"Processed tickers: {len(scanner.processed_tickers_session)}")
    print(f"Active plays: {len(scanner.active_plays_session)}")
    print(f"Reanalysis cooldown: {scanner.reanalysis_cooldown_minutes} minutes")
    print(f"Fresh news cooldown: {scanner.fresh_news_reanalysis_minutes} minutes")
    print(f"Active plays cooldown: {scanner.active_plays_cooldown_minutes} minutes")
    
    # Test 2: Simulate processing some tickers
    print("\n📊 Test 2: Simulate Processing Tickers")
    current_time = datetime.now()
    
    # Simulate processed tickers at different times
    test_tickers = {
        'TELO': {
            'time': current_time - timedelta(minutes=25),  # 25 minutes ago (should be ready for re-analysis)
            'had_fresh_news': False
        },
        'CWD': {
            'time': current_time - timedelta(minutes=15),  # 15 minutes ago (still in cooldown)
            'had_fresh_news': False
        },
        'WHLR': {
            'time': current_time - timedelta(minutes=5),   # 5 minutes ago with fresh news
            'had_fresh_news': True
        },
        'SPRC': {
            'time': current_time - timedelta(minutes=12),  # 12 minutes ago with fresh news (should be ready)
            'had_fresh_news': True
        }
    }
    
    scanner.processed_tickers_session = test_tickers.copy()
    
    print(f"Simulated {len(test_tickers)} processed tickers:")
    for symbol, data in test_tickers.items():
        minutes_ago = (current_time - data['time']).total_seconds() / 60
        print(f"  {symbol}: {minutes_ago:.1f} minutes ago, fresh_news={data['had_fresh_news']}")
    
    # Test 3: Test re-analysis logic
    print("\n📊 Test 3: Re-analysis Decision Logic")
    
    # Create mock IBKR results
    class MockResult:
        def __init__(self, symbol):
            self.symbol = symbol
    
    mock_results = [MockResult(symbol) for symbol in test_tickers.keys()]
    
    # Simulate the filtering logic
    current_time = datetime.now()
    new_tickers = []
    already_processed = []
    reanalyzed_tickers = []
    
    for result in mock_results:
        symbol = result.symbol
        
        if symbol not in scanner.processed_tickers_session:
            new_tickers.append(result)
        else:
            last_processed = scanner.processed_tickers_session[symbol]['time']
            time_since_processed = (current_time - last_processed).total_seconds() / 60
            
            # Simulate has_active_play check
            has_active_play = False  # No active plays in this test
            
            if has_active_play:
                required_cooldown = scanner.active_plays_cooldown_minutes
            else:
                had_fresh_news = scanner.processed_tickers_session[symbol].get('had_fresh_news', False)
                required_cooldown = scanner.fresh_news_reanalysis_minutes if had_fresh_news else scanner.reanalysis_cooldown_minutes
            
            print(f"  {symbol}: {time_since_processed:.1f}min ago, need {required_cooldown}min cooldown, fresh_news={had_fresh_news}")
            
            if time_since_processed >= required_cooldown:
                new_tickers.append(result)
                reanalyzed_tickers.append(symbol)
                print(f"    ✅ READY for re-analysis")
            else:
                already_processed.append(symbol)
                print(f"    ⏱️ Still in cooldown ({required_cooldown - time_since_processed:.1f}min left)")
    
    print(f"\n📊 Results:")
    print(f"  New tickers to process: {len(new_tickers)}")
    print(f"  Re-analyzed tickers: {reanalyzed_tickers}")
    print(f"  Tickers in cooldown: {already_processed}")
    
    # Test 4: Check if logic matches expected behavior
    print("\n📊 Test 4: Validation")
    expected_reanalyzed = ['TELO', 'SPRC']  # TELO (25min > 20min), SPRC (12min > 10min fresh)
    expected_cooldown = ['CWD', 'WHLR']     # CWD (15min < 20min), WHLR (5min < 10min fresh)
    
    if set(reanalyzed_tickers) == set(expected_reanalyzed):
        print("✅ Re-analysis logic PASSED")
    else:
        print(f"❌ Re-analysis logic FAILED")
        print(f"   Expected: {expected_reanalyzed}")
        print(f"   Got: {reanalyzed_tickers}")
    
    if set(already_processed) == set(expected_cooldown):
        print("✅ Cooldown logic PASSED")
    else:
        print(f"❌ Cooldown logic FAILED")
        print(f"   Expected: {expected_cooldown}")
        print(f"   Got: {already_processed}")
    
    print("\n🎯 Test Complete!")

if __name__ == "__main__":
    test_reanalysis_logic()