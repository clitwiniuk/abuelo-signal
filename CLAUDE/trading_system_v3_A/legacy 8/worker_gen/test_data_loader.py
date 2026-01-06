from core.data_manager import DataManager
import os

# Create an instance
print("Initializing DataManager...")
dm = DataManager(input_dir='worker_gen/input')

# Load data
print("Loading data...")
dm.load_all()

# Verify
data = dm.get_data()
if not data:
    print("❌ No data loaded!")
else:
    for name, df in data.items():
        print(f"\n--- Checking {name} ---")
        print("Columns found:", df.columns.tolist())
        print("\nLast 3 rows:")
        print(df[['timestamp', 'close', 'ema_9', 'rsi_14', 'vwap']].tail(3))
        
        if 'ema_9' in df.columns:
            print("\n✅ Features calculated successfully")
        else:
            print("\n❌ Features missing")
