# strategies/test_daily_plays_strategy.py
"""
Test script for Daily Plays Strategy
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, time
from daily_plays_strategy import DailyPlaysStrategy, DailyPlaysConfig
from core.data_types import MarketData

def create_test_bar(open_price, high, low, close, volume, timestamp=None):
    """Create a test market data bar"""
    return {
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'timestamp': timestamp or datetime.now()
    }

def test_daily_plays_strategy():
    """Test the Daily Plays Strategy with simulated data"""
    print("🧪 Testing Daily Plays Strategy")
    print("=" * 60)
    
    # Initialize strategy
    config = DailyPlaysConfig()
    strategy = DailyPlaysStrategy(config)
    
    # Display strategy info
    info = strategy.get_strategy_info()
    print(f"📊 Strategy: {info['name']}")
    print(f"📋 Description: {info['description']}")
    print(f"⏰ Timeframe: {info['timeframe']}")
    print()
    
    print("📈 Entry Conditions:")
    for i, condition in enumerate(info['conditions'], 1):
        print(f"   {i}. {condition}")
    print()
    
    print("⚙️ Parameters:")
    for key, value in info['parameters'].items():
        print(f"   {key}: {value}")
    print()
    
    # Simulate market data scenario
    print("🎬 Simulating Trading Scenario:")
    print("-" * 30)
    
    ticker = "TESTPLAY"
    
    # Create realistic intraday data scenario
    # Pre-market and first 30 minutes (9:30-10:00)
    first_half_hour_bars = [
        create_test_bar(5.00, 5.20, 4.95, 5.15, 50000),   # 9:30 bar
        create_test_bar(5.15, 5.25, 5.10, 5.22, 45000),   # 9:31 bar
        create_test_bar(5.22, 5.30, 5.18, 5.28, 60000),   # 9:32 bar - high of first 30min
        create_test_bar(5.28, 5.29, 5.20, 5.24, 40000),   # More bars...
        create_test_bar(5.24, 5.27, 5.19, 5.21, 35000),
        create_test_bar(5.21, 5.26, 5.18, 5.23, 42000),
        create_test_bar(5.23, 5.25, 5.17, 5.19, 38000),
        create_test_bar(5.19, 5.22, 5.15, 5.20, 41000),
        create_test_bar(5.20, 5.24, 5.16, 5.18, 39000),
        create_test_bar(5.18, 5.21, 5.14, 5.16, 37000),   # End of first 30 minutes
    ]
    
    print(f"📊 First 30 minutes data for {ticker}:")
    for i, bar in enumerate(first_half_hour_bars):
        print(f"   Bar {i+1}: H=${bar['high']:.2f} L=${bar['low']:.2f} C=${bar['close']:.2f} V={bar['volume']:,}")
    
    # Find the first 30-minute high
    first_30min_high = max(bar['high'] for bar in first_half_hour_bars)
    print(f"   📈 First 30-minute high: ${first_30min_high:.2f}")
    print()
    
    # Simulate tracking first 30 minutes
    for bar in first_half_hour_bars:
        strategy._track_first_half_hour_high(ticker, bar)
    
    # Mark first 30 minutes as complete
    strategy.first_half_hour_tracked[ticker] = True
    
    # Now simulate breakout scenario after 10:00 AM
    print("🚀 Breakout Scenario (after 10:00 AM):")
    print("-" * 30)
    
    # Create additional bars leading to breakout
    breakout_bars = first_half_hour_bars + [
        # Consolidation phase
        create_test_bar(5.16, 5.19, 5.12, 5.15, 35000),
        create_test_bar(5.15, 5.18, 5.11, 5.17, 33000),
        create_test_bar(5.17, 5.20, 5.14, 5.19, 36000),
        create_test_bar(5.19, 5.22, 5.16, 5.21, 38000),
        
        # Volume building
        create_test_bar(5.21, 5.24, 5.18, 5.23, 45000),
        create_test_bar(5.23, 5.26, 5.20, 5.25, 52000),
        create_test_bar(5.25, 5.28, 5.22, 5.27, 58000),
        
        # BREAKOUT BAR - breaks first 30min high with 2x volume
        create_test_bar(5.27, 5.35, 5.26, 5.33, 85000),  # 2x+ volume, breaks 5.30
    ]
    
    # Test the breakout bar
    print(f"🎯 Testing breakout bar:")
    breakout_bar = breakout_bars[-1]
    print(f"   High: ${breakout_bar['high']:.2f} (breaks ${first_30min_high:.2f})")
    print(f"   Volume: {breakout_bar['volume']:,}")
    print(f"   Close: ${breakout_bar['close']:.2f}")
    print()
    
    # Test strategy analysis
    print("📊 Strategy Analysis:")
    print("-" * 20)
    
    signal = strategy.analyze(ticker, breakout_bars, {})
    
    if signal:
        print(f"✅ SIGNAL GENERATED!")
        print(f"   Ticker: {signal.ticker}")
        print(f"   Action: {signal.action}")
        print(f"   Quantity: {signal.quantity}")
        print(f"   Price: ${signal.price:.2f}")
        print(f"   Confidence: {signal.confidence:.2f}")
        print(f"   Strategy: {signal.strategy}")
        
        if signal.metadata:
            print(f"   Metadata:")
            for key, value in signal.metadata.items():
                if key == 'conditions_met':
                    print(f"      {key}:")
                    for condition, met in value.items():
                        status = "✅" if met else "❌"
                        print(f"         {status} {condition}")
                else:
                    print(f"      {key}: {value}")
    else:
        print("❌ No signal generated")
        print("   Checking individual conditions...")
        
        # Manual condition checks for debugging
        breakout_ok = strategy._check_price_breakout(ticker, breakout_bar)
        volume_ok = strategy._check_volume_condition(ticker, breakout_bars)
        ema_ok = strategy._check_ema_condition(ticker, breakout_bars)
        
        print(f"   📈 Breakout condition: {'✅' if breakout_ok else '❌'}")
        print(f"   📊 Volume condition: {'✅' if volume_ok else '❌'}")
        print(f"   📉 EMA condition: {'✅' if ema_ok else '❌'}")
    
    print()
    print("=" * 60)
    print("✅ Daily Plays Strategy test completed!")

if __name__ == "__main__":
    test_daily_plays_strategy()