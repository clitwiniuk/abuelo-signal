import sys
import importlib.util
from dataclasses import dataclass
from unittest.mock import MagicMock

# Setup path
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

# Mock core.td_sequential since exhaustion_filters imports it
spec_td = importlib.util.spec_from_file_location("td_sequential", "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/core/td_sequential.py")
td_module = importlib.util.module_from_spec(spec_td)
sys.modules["core.td_sequential"] = td_module
spec_td.loader.exec_module(td_module)

TDSequentialDetector = td_module.TDSequentialDetector

# Load exhaustion_filters directly
spec_exh = importlib.util.spec_from_file_location("exhaustion_filters", "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/exhaustion_filters.py")
exh_module = importlib.util.module_from_spec(spec_exh)
sys.modules["strategies.workers.exhaustion_filters"] = exh_module
spec_exh.loader.exec_module(exh_module)

ExhaustionFilters = exh_module.ExhaustionFilters

@dataclass
class Bar:
    close: float
    timestamp: any = None
    open: float = 0
    high: float = 0
    low: float = 0
    volume: float = 1000

from dataclasses import dataclass

def test_td_sequential_logic():
    print("Testing TD Sequential Logic...")
    detector = TDSequentialDetector(setup_max=9)
    
    # Create 15 bars with increasing closes
    # To have a 9-count, we need Close > Close[t-4] for 9 consecutive bars
    bars = [Bar(close=float(10 + i)) for i in range(20)]
    
    count = detector.calculate_setup(bars)
    print(f"  Count for 20 increasing bars: {count}")
    
    report = detector.get_exhaustion_score(bars)
    print(f"  Exhaustion report: {report}")
    
    assert count >= 9, f"Expected at least 9, got {count}"
    assert report['is_exhausted'] == True
    print("✅ TD Sequential Logic Passed")

def test_exhaustion_filter_integration():
    print("\nTesting Exhaustion Filter Integration...")
    filters = ExhaustionFilters(
        demark_max_count=9, 
        enable_demark=True,
        enable_wick=False,
        enable_extension=False,
        enable_churn=False
    )
    
    # Case 1: No exhaustion (only 5 bars)
    bars_low = [Bar(close=float(10 + i)) for i in range(5)]
    is_safe, reason = filters.check_exhaustion(bars_low, 15.0)
    print(f"  5 bars test: Safe={is_safe}, Reason={reason}")
    assert is_safe == True
    
    # Case 2: DeMark Exhaustion (25 bars increasing)
    bars_high = [Bar(close=float(10 + i)) for i in range(25)]
    is_safe, reason = filters.check_exhaustion(bars_high, 35.0)
    print(f"  15 bars test: Safe={is_safe}, Reason={reason}")
    assert is_safe == False
    assert "DeMark Exhaustion" in reason
    print("✅ Exhaustion Filter Integration Passed")

if __name__ == "__main__":
    try:
        test_td_sequential_logic()
        test_exhaustion_filter_integration()
        print("\n🎉 ALL TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
