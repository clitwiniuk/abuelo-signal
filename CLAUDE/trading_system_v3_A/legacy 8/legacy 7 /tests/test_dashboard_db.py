import dashboard.dashboard_utils as utils
import sys

def test_db():
    print("Testing get_pnl_stats()...")
    stats = utils.get_pnl_stats()
    print(f"Stats: {stats}")
    
    print("\nTesting get_active_trades()...")
    active = utils.get_active_trades()
    print(f"Active Trades Count: {len(active)}")
    if not active.empty:
        print(active.head())
        
    print("\nTesting get_equity_curve()...")
    equity = utils.get_equity_curve()
    print(f"Equity Curve Points: {len(equity)}")
    
    print("\nTesting get_closed_trades()...")
    closed = utils.get_closed_trades(limit=5)
    print(f"Closed Trades Count: {len(closed)}")
    
    print("\nTesting read_config()...")
    config = utils.read_config()
    if config:
        sections = config.sections()
        print(f"Config Sections: {len(sections)}")
        print(f"First 3 Sections: {sections[:3]}")
    else:
        print("Config failed to load.")

if __name__ == "__main__":
    try:
        test_db()
        print("\n✅ Dashboard Utils Test Passed")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        sys.exit(1)
