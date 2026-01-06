#!/usr/bin/env python3
"""
Test auto-tune with debug logging
"""

import subprocess
import sys

def test_with_debug_logging():
    """Run the simulation with debug logging to see auto-tune"""
    
    print("🔧 TESTING AUTO-TUNE WITH DEBUG LOGGING")
    print("=" * 50)
    
    # Simulate the user inputs for the menu
    inputs = "2\nXXII\n300\n0\n"  # Option 2, XXII symbol, 300 bars, then exit
    
    try:
        # Run the simulation with automated inputs
        process = subprocess.Popen(
            [sys.executable, "scripts/runners/run_simulation.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PYTHONPATH": "."}
        )
        
        # Send the inputs and get output
        stdout, stderr = process.communicate(input=inputs, timeout=30)
        
        # Look for auto-tune related logs
        print("🔍 SEARCHING FOR AUTO-TUNE LOGS:")
        print("-" * 40)
        
        for line in (stdout + stderr).split('\n'):
            if any(keyword in line.lower() for keyword in ['auto-tune', 'debug', 'counter=', 'vol_min=', '📉', '🔍']):
                print(f">>> {line}")
        
        print("-" * 40)
        
        # Check if trades were executed
        if "trades_executed: 0" in stdout:
            print("📊 RESULT: No trades executed")
        else:
            print("📊 RESULT: Trades may have been executed")
            
        return True
            
    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

if __name__ == "__main__":
    test_with_debug_logging()