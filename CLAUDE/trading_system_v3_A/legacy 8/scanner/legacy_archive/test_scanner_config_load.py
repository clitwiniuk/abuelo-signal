
import logging
from scanner.ibkr_native_scanner import IBKRNativeScanner

# Mock adapter
class MockAdapter:
    pass

def test_scanner_configs():
    print("Testing Scanner Config Loading...")
    try:
        scanner = IBKRNativeScanner(ibkr_adapter=MockAdapter())
        configs = scanner.scan_configs
        
        print(f"Loaded {len(configs)} scanner configurations:")
        for config in configs:
            print(f"- {config['name']}: Code={config['scan_code']}, Vol={config.get('above_volume')}")
            
        # Verify specific scanners exist
        names = [c['name'] for c in configs]
        assert 'gap_up_movers' in names, "gap_up_movers missing"
        assert 'early_movers' in names, "early_movers missing"
        assert 'steady_gainer' in names, "steady_gainer missing"
        
        # Verify early_movers volume
        early = next(c for c in configs if c['name'] == 'early_movers')
        print(f"\nVerifying early_movers volume: {early.get('above_volume')}")
        assert early.get('above_volume') <= 20000, "early_movers volume too high"
        
        print("\n✅ Scanner configuration verification PASSED")
    except Exception as e:
        print(f"\n❌ Scanner configuration verification FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scanner_configs()
