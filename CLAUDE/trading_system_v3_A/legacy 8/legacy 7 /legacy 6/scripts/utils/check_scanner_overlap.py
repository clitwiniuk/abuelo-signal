
import asyncio
import logging
import sys
from collections import defaultdict

# Configure logging to show info
logging.basicConfig(level=logging.WARNING)

# Import system modules
sys.path.append('.')
from adapters.ibkr_adapter import IBKRAdapter
from scanner.ibkr_native_scanner import IBKRNativeScanner

async def check_overlap():
    print("🚀 Starting Scanner Overlap Analysis...")
    print("⏳ Connecting to IBKR (this may take a few seconds)...")
    
    adapter = IBKRAdapter()
    await adapter.connect()
    
    if not adapter.is_connected():
        print("❌ Failed to connect to IBKR TWS")
        return

    scanner = IBKRNativeScanner(adapter)
    
    # We will manually run specific scanner configs to compare them
    configs = scanner.scan_configs
    results_by_scanner = {}
    
    print(f"📊 Testing {len(configs)} scanner configurations...")
    
    for config in configs:
        name = config['name']
        print(f"   Running {name}...", end='', flush=True)
        try:
            results = await scanner._run_scanner_config(config)
            tickers = set(r.symbol for r in results)
            results_by_scanner[name] = tickers
            print(f" Found {len(tickers)} tickers")
            # Small delay to avoid error 162
            await asyncio.sleep(2)
        except Exception as e:
            print(f" Failed: {e}")
            results_by_scanner[name] = set()

    print("\n🔍 --- OVERLAP ANALYSIS ---")
    
    # Compare Early Movers vs Steady Gainer
    s1 = results_by_scanner.get('early_movers', set())
    s2 = results_by_scanner.get('steady_gainer', set())
    
    if s1 or s2:
        intersection = s1.intersection(s2)
        union = s1.union(s2)
        overlap_pct = (len(intersection) / len(union) * 100) if union else 0
        print(f"\n1. Early Movers vs Steady Gainer:")
        print(f"   - Early Movers: {len(s1)}")
        print(f"   - Steady Gainer: {len(s2)}")
        print(f"   - Common: {len(intersection)}")
        print(f"   - Overlap: {overlap_pct:.1f}%")
        if len(intersection) > 0:
            print(f"   - Examples: {list(intersection)[:5]}")
            
    # Check what Rel Vol is finding
    s3 = results_by_scanner.get('rel_vol_intraday', set())
    if s3:
        print(f"\n2. Rel Vol Intraday Findings:")
        print(f"   - Unique tickers found: {list(s3)}")
    else:
        print(f"\n2. Rel Vol Intraday: Returned 0 results.")

    # Check Volume Surge vs others
    s4 = results_by_scanner.get('volume_surge_movers', set())
    all_others = set().union(*[v for k,v in results_by_scanner.items() if k != 'volume_surge_movers'])
    unique_surge = s4 - all_others
    print(f"\n3. Volume Surge Uniqueness:")
    print(f"   - Total found: {len(s4)}")
    print(f"   - Unique to this scanner: {len(unique_surge)}")
    
    print("\n✅ Analysis Complete")
    adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(check_overlap())
