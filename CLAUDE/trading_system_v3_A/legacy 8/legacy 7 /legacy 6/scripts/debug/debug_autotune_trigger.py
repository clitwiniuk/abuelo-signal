#!/usr/bin/env python3
"""
Debug why auto-tune is not triggering
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_autotune_logic():
    """Test the auto-tune trigger logic"""
    
    print("🔧 TESTING AUTO-TUNE TRIGGER LOGIC")
    print("=" * 50)
    
    # Simulate the counter logic
    _no_signal_counter = 0
    
    for bar_num in range(1, 201):  # Test 200 bars
        # Simulate no candidate signals (like in XXII)
        candidate_signals = []
        
        if candidate_signals:
            # Reset counter if signals found
            _no_signal_counter = 0
            print(f"Bar {bar_num}: Signals found, counter reset to 0")
        else:
            # Increment counter
            _no_signal_counter += 1
            
            # Check if should adjust
            should_adjust = (_no_signal_counter % 100 == 0)
            
            if should_adjust:
                print(f"🎯 Bar {bar_num}: AUTO-TUNE SHOULD TRIGGER! Counter: {_no_signal_counter}")
            elif bar_num % 25 == 0:  # Show progress every 25 bars
                print(f"Bar {bar_num}: Counter: {_no_signal_counter}, Next trigger at: {(_no_signal_counter // 100 + 1) * 100}")
    
    print(f"\n📊 Final counter: {_no_signal_counter}")
    print("✅ Logic test complete - auto-tune should have triggered at bars 100 and 200")

if __name__ == "__main__":
    test_autotune_logic()