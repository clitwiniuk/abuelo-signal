
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from scanner.smallcap.proactive_scanner import ProactiveScanner
from adapters.ibkr_adapter import IBKRAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def main():
    print("🚀 Forcing Proactive Scanner Run...")
    
    # Initialize Adapter
    adapter = IBKRAdapter()
    if not await adapter.connect():
        print("❌ Failed to connect to IBKR")
        return

    # Initialize Scanner
    scanner = ProactiveScanner(ibkr_adapter=adapter)
    
    # FORCE RUN: Bypass should_run_now check effectively by calling 
    # scan_and_update_watchlist directly. 
    # (The method itself checks should_run_now, but we are in postmarket so it should fly)
    
    print("📋 Starting scan_and_update_watchlist...")
    try:
        await scanner.scan_and_update_watchlist()
        print("✅ Scan completed.")
    except Exception as e:
        print(f"❌ Error during scan: {e}")
        import traceback
        traceback.print_exc()
    
    # Disconnect
    await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
