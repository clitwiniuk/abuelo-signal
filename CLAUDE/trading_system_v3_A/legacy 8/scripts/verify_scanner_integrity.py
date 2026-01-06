
import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmokeTest")

print("🔍 Starting Smoke Test: Dependency Verification")

try:
    print("1. Testing Imports...")
    from scanner_main import IndependentScanner
    print("   ✅ scanner_main imported successfully")
    
    from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
    print("   ✅ SmallcapDailyScanner imported successfully")
    
    from scanner.midcap.midcap_daily_scanner import MidCapDailyScanner
    print("   ✅ MidCapDailyScanner imported successfully")
    
    print("\n2. Testing Initialization (Dry Run)...")
    # Attempt to instantiate scanner to check for missing config/dependencies
    # We won't start it, just init
    scanner_process = IndependentScanner()
    print("   ✅ IndependentScanner initialized successfully")
    
    if hasattr(scanner_process, 'opportunity_tracker'):
        print(f"   ✅ OpportunityTracker Present: {scanner_process.opportunity_tracker is not None}")
        
    print("\n✅ SMOKE TEST PASSED: No missing dependencies found after cleanup.")
    sys.exit(0)

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("The cleanup might have deleted a file that is still imported.")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ RUNTIME ERROR: {e}")
    sys.exit(1)
