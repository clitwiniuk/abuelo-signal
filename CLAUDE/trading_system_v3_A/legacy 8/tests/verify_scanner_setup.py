import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Mock IBKR Adapter and other dependencies
class MockIBKRAdapter:
    def is_connected(self):
        return True

async def verify_scanner_config():
    try:
        from scanner.ibkr_native_scanner import IBKRNativeScanner
        
        print("🔍 Initializing IBKRNativeScanner...")
        scanner = IBKRNativeScanner(ibkr_adapter=MockIBKRAdapter())
        
        configs = scanner.scan_configs
        
        print(f"✅ Loaded {len(configs)} scanner configs")
        
        # Verify Small Cap limits
        small_cap_scanners = [c for c in configs if c['name'] in ['volume_surge_movers', 'early_movers']]
        for sc in small_cap_scanners:
            print(f"🔹 Checking {sc['name']} (Small Cap):")
            print(f"   - Max Market Cap: {sc.get('market_cap_below')}M (Expected: 2000)")
            print(f"   - Min Price: ${sc.get('above_price')} (Expected: 0.5)")
            
            if sc.get('market_cap_below') != 2000:
                print("❌ FAILED: Small Cap limit incorrect")
            else:
                print("✅ PASSED")

        # Verify Mid Cap limits
        mid_cap_scanner = next((c for c in configs if c['name'] == 'mid_cap_movers'), None)
        
        if mid_cap_scanner:
            print(f"🔸 Checking {mid_cap_scanner['name']} (Mid Cap):")
            print(f"   - Min Market Cap: {mid_cap_scanner.get('market_cap_above')}M (Expected: 2000)")
            print(f"   - Max Market Cap: {mid_cap_scanner.get('market_cap_below')}M (Expected: 50000)")
            print(f"   - Min Price: ${mid_cap_scanner.get('above_price')} (Expected: 10.0)")
            print(f"   - Max Price: ${mid_cap_scanner.get('below_price')} (Expected: 200.0)")
            
            if (mid_cap_scanner.get('market_cap_above') == 2000 and 
                mid_cap_scanner.get('market_cap_below') == 50000):
                 print("✅ PASSED: Mid Cap limits correct")
            else:
                 print("❌ FAILED: Mid Cap limits incorrect")
        else:
            print("❌ FAILED: mid_cap_movers profile NOT FOUND")

    except Exception as e:
        print(f"❌ Error verifying config: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_scanner_config())
