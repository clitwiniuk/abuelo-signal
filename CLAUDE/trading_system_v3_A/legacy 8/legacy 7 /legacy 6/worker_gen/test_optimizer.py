from core.data_manager import DataManager
from core.optimizer import Optimizer
import os

# 1. Setup Data
print("Initializing DataManager...")
dm = DataManager(input_dir='worker_gen/input')
dm.load_all()

# 2. Setup Optimizer
print("Initializing Optimizer...")
opt = Optimizer(dm)

# 3. Run
# We run small iteration count for testing
best = opt.optimize(iterations=200)

if best:
    print("\n✅ OPTIMIZATION SUCCESS")
    print("=" * 40)
    print(f"BEST STRATEGY FOUND (Score: {best.fitness:.2f})")
    print(f"SL: {best.stop_loss_pct}%")
    print(f"TP: {best.take_profit_pct}%")
    print(f"Time Limit: {best.time_limit_bars} bars")
    print("Entry Rules:")
    for c in best.entry_conditions:
        print(f"  - {c}")
    print("=" * 40)
else:
    print("\n❌ Failed to find a valid strategy")
