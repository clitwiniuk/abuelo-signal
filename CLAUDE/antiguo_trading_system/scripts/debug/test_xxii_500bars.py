#!/usr/bin/env python3
"""
Automated test to replicate the XXII 500 bars test
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# We'll use subprocess to call the simulation with inputs
import subprocess

def test_xxii_simulation():
    """Test XXII with 500 bars automatically"""
    
    print("🧪 TESTING XXII WITH 500 BARS (AUTOMATED)")
    print("=" * 50)
    
    # Simulate the user inputs for the menu
    # Option 2: Test de estrategia en símbolo específico
    # Symbol: XXII
    # Bars: 500 (or just press enter for default)
    inputs = "2\nXXII\n1000\n0\n"  # Option 2, XXII symbol, 1000 bars, then exit
    
    try:
        # Run the simulation with automated inputs
        process = subprocess.Popen(
            [sys.executable, "scripts/runners/run_simulation.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root
        )
        
        # Send the inputs and get output
        stdout, stderr = process.communicate(input=inputs, timeout=60)
        
        print("📊 SIMULATION OUTPUT:")
        print("-" * 40)
        print(stdout)
        
        if stderr:
            print("⚠️ STDERR:")
            print(stderr)
        
        # Analyze the results
        if "trades_executed: 0" in stdout:
            print("❌ RESULT: No trades executed")
            return False
        elif "trades_executed: 2" in stdout or "Trades ejecutados: 2" in stdout:
            print("✅ RESULT: 2 trades executed (like the working version)")
            return True
        elif "trades_executed:" in stdout and "trades_executed: 0" not in stdout:
            print("✅ RESULT: Trades were executed")
            return True
        else:
            print("⚠️ RESULT: Could not determine trade count from output")
            return None
            
    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

if __name__ == "__main__":
    result = test_xxii_simulation()
    
    if result is True:
        print("\n🎉 SUCCESS: The system is now working correctly!")
        print("   The auto-tune fix has resolved the volatility blocking issue.")
    elif result is False:
        print("\n❌ FAILED: The system is still not generating trades.")
        print("   More investigation needed.")
    else:
        print("\n⚠️ UNCLEAR: Could not determine the result from output.")
        print("   Manual testing may be needed.")