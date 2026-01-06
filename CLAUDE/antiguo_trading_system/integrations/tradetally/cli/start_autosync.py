#!/usr/bin/env python3
"""
Start TradeTally Auto-Sync Daemon
==================================

Inicia sincronización automática en tiempo real con WebSocket.
No requiere sincronización manual!
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from integrations.tradetally.core.tradetally_autosync import start_autosync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment
env_path = Path(__file__).parent.parent.parent.parent / '.env.local'
if env_path.exists():
    load_dotenv(env_path)


def main():
    print("""
╔═══════════════════════════════════════════════════╗
║   TradeTally Auto-Sync - Real-Time WebSocket     ║
╚═══════════════════════════════════════════════════╝
""")

    # Get configuration
    api_key = os.getenv('TRADETALLY_API_KEY')
    base_url = os.getenv('TRADETALLY_BASE_URL', 'http://localhost:8001')
    db_path = os.getenv('TRADING_DB_PATH', 'trading_data.db')

    if not api_key:
        print("❌ TRADETALLY_API_KEY not found in environment")
        print("💡 Please set it in .env.local")
        sys.exit(1)

    print(f"📋 Configuration:")
    print(f"   API Key: {api_key[:20]}...")
    print(f"   Server: {base_url}")
    print(f"   Database: {db_path}")
    print()

    # Start auto-sync
    autosync = start_autosync(
        api_key=api_key,
        base_url=base_url,
        db_path=db_path
    )

    if autosync:
        print("\n✅ Auto-sync session completed")
        stats = autosync.get_stats()
        print(f"📊 Stats:")
        print(f"   Synced: {stats['synced']}")
        print(f"   Errors: {stats['errors']}")
    else:
        print("\n❌ Auto-sync failed to start")
        sys.exit(1)


if __name__ == '__main__':
    main()
