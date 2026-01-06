import sys
from pathlib import Path
import traceback

# Add root dir
root_dir = str(Path(__file__).parent)
sys.path.append(root_dir)

print(f"Root dir: {root_dir}")
print(f"Sys path: {sys.path}")

try:
    print("Attempting to import strategies.base...")
    import strategies.base
    print("strategies.base imported successfully")
    print(f"BaseStrategy in strategies.base: {'BaseStrategy' in dir(strategies.base)}")
except Exception:
    traceback.print_exc()

try:
    print("\nAttempting to import strategies...")
    import strategies
    print("strategies imported successfully")
except Exception:
    traceback.print_exc()
