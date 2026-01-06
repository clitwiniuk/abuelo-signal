#!/usr/bin/env python3
"""
TradeTally CLI - New API-First Version
=======================================

Uses REST API instead of direct PostgreSQL access.

Architecture:
- SQLite (trading_data.db) -> TradeTally API -> PostgreSQL (metadata only)
- Clean separation of concerns
- More robust and scalable
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / '.env.local'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"✅ Loaded environment from {env_path}")
else:
    logger.warning(f"⚠️ .env.local not found at {env_path}")


def print_banner():
    """Print TradeTally banner"""
    banner = """
████████╗██████╗  █████╗ ██████╗ ███████╗████████╗ █████╗ ██╗     ██╗     ██╗   ██╗
╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║     ██║     ╚██╗ ██╔╝
   ██║   ██████╔╝███████║██║  ██║█████╗     ██║   ███████║██║     ██║      ╚████╔╝
   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝     ██║   ██╔══██║██║     ██║       ╚██╔╝
   ██║   ██║  ██║██║  ██║██████╔╝███████╗   ██║   ██║  ██║███████╗███████╗   ██║
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝

                    🔗 API-First Architecture - Trading System v3
    """
    print(banner)


def get_client() -> TradeTallyAPIClient:
    """
    Create TradeTally API client from environment variables

    Returns:
        TradeTallyAPIClient instance
    """
    api_key = os.getenv('TRADETALLY_API_KEY')
    base_url = os.getenv('TRADETALLY_BASE_URL', 'http://localhost:8001')
    db_path = os.getenv('TRADING_DB_PATH', 'trading_data.db')

    if not api_key:
        logger.error("❌ TRADETALLY_API_KEY not found in environment")
        logger.info("💡 Please set TRADETALLY_API_KEY in .env.local")
        sys.exit(1)

    return TradeTallyAPIClient(
        api_key=api_key,
        base_url=base_url,
        db_path=db_path
    )


def cmd_test(args):
    """Test connection to TradeTally API"""
    print_banner()
    logger.info("🔍 Testing connection to TradeTally API...")
    print("=" * 50)

    client = get_client()

    if client.test_connection():
        logger.info("✅ Connection successful!")
        print("\n💚 Operation successful")
    else:
        logger.error("❌ Connection failed")
        print("\n💥 Operation failed")
        sys.exit(1)


def cmd_status(args):
    """Get sync status"""
    print_banner()
    logger.info("📊 Getting sync status...")
    print("=" * 50)

    client = get_client()
    status = client.get_sync_status()

    if status.get('success'):
        sync_status = status.get('status', {})
        print(f"\n📊 Sync Status:")
        print(f"   Total metadata: {sync_status.get('total_metadata', 0)}")
        print(f"   Public trades: {sync_status.get('public_count', 0)}")
        print(f"   Last sync: {sync_status.get('last_sync', 'Never')}")
        print("\n💚 Operation successful")
    else:
        logger.error(f"❌ Failed to get status: {status.get('error')}")
        print("\n💥 Operation failed")
        sys.exit(1)


def cmd_sync(args):
    """Sync trades metadata to TradeTally"""
    print_banner()
    logger.info("🔄 Syncing trades metadata...")
    print("=" * 50)

    client = get_client()

    # Test connection first
    if not client.test_connection():
        logger.error("❌ Connection test failed. Aborting sync.")
        print("\n💥 Operation failed")
        sys.exit(1)

    # Sync trades
    only_today = args.only_today if hasattr(args, 'only_today') else False
    result = client.sync_all_trades(only_today=only_today)

    if result.get('success'):
        print(f"\n✅ Sync completed successfully!")
        print(f"   Synced: {result.get('synced', 0)} / {result.get('total', 0)}")
        print(f"   Errors: {result.get('errors', 0)}")

        if result.get('error_details'):
            print(f"\n⚠️ Error details:")
            for error in result.get('error_details', [])[:5]:  # Show first 5 errors
                print(f"   - Trade {error.get('trade_id')}: {error.get('error')}")

        print("\n💚 Operation successful")
    else:
        logger.error(f"❌ Sync failed: {result.get('error')}")
        print("\n💥 Operation failed")
        sys.exit(1)


def cmd_config(args):
    """Show current configuration"""
    print_banner()
    logger.info("⚙️ Current configuration...")
    print("=" * 50)

    api_key = os.getenv('TRADETALLY_API_KEY', 'Not set')
    base_url = os.getenv('TRADETALLY_BASE_URL', 'http://localhost:8001')
    db_path = os.getenv('TRADING_DB_PATH', 'trading_data.db')

    print(f"\n📋 Configuration:")
    print(f"   API Key: {api_key[:20]}..." if len(api_key) > 20 else f"   API Key: {api_key}")
    print(f"   Base URL: {base_url}")
    print(f"   DB Path: {db_path}")
    print(f"   Architecture: API-First (REST)")
    print("\n💚 Configuration loaded")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='TradeTally API Client - Sync trade metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tradetally_cli_new.py test          # Test API connection
  python tradetally_cli_new.py status        # Get sync status
  python tradetally_cli_new.py sync          # Sync all trades metadata
  python tradetally_cli_new.py sync --today  # Sync only today's trades
  python tradetally_cli_new.py config        # Show configuration
        """
    )

    parser.add_argument(
        'command',
        choices=['test', 'status', 'sync', 'config'],
        help='Command to execute'
    )

    parser.add_argument(
        '--today',
        action='store_true',
        dest='only_today',
        help='Sync only today\'s trades'
    )

    args = parser.parse_args()

    # Execute command
    commands = {
        'test': cmd_test,
        'status': cmd_status,
        'sync': cmd_sync,
        'config': cmd_config
    }

    command_func = commands.get(args.command)
    if command_func:
        try:
            command_func(args)
        except KeyboardInterrupt:
            print("\n\n⚠️ Operation cancelled by user")
            sys.exit(130)
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
