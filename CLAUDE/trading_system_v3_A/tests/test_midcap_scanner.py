#!/usr/bin/env python3
"""
Quick Test Script for MidCap Scanner
Tests the scanner independently without full trader integration
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scanner.midcap.midcap_daily_scanner import MidCapDailyScanner
from adapters.ibkr_adapter import IBKRAdapter


async def test_midcap_scanner():
    """Test MidCap scanner functionality"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger("MidCapScannerTest")
    logger.info("=" * 80)
    logger.info("🏢 MIDCAP SCANNER TEST")
    logger.info("=" * 80)

    # Initialize IBKR adapter
    logger.info("📡 Connecting to IBKR...")
    ibkr = IBKRAdapter()

    try:
        await ibkr.connect()
        logger.info("✅ IBKR connected")

        # Initialize MidCap scanner
        logger.info("🔧 Initializing MidCap scanner...")
        scanner = MidCapDailyScanner(ibkr_adapter=ibkr)

        # Get scanner statistics
        stats = scanner.get_scan_statistics()
        logger.info(f"📊 Scanner Configuration:")
        logger.info(f"   Price Range: ${stats['config']['min_price']:.2f} - ${stats['config']['max_price']:.2f}")
        logger.info(f"   Market Cap: ${stats['config']['min_market_cap']:.0f}M - ${stats['config']['max_market_cap']:.0f}M")
        logger.info(f"   Min Volume: {stats['config']['min_volume']:,}")
        logger.info(f"   Min Gap: {stats['config']['min_gap_pct']:.1f}%")
        logger.info("")

        # Run scan
        logger.info("🔍 Running MidCap scan...")
        logger.info("-" * 80)

        plays = await scanner.scan_daily_plays(max_results=20)

        logger.info("-" * 80)
        logger.info(f"")

        # Display results
        if plays:
            logger.info(f"✅ FOUND {len(plays)} MIDCAP OPPORTUNITIES:")
            logger.info("")

            for i, play in enumerate(plays, 1):
                logger.info(f"{i}. {play.symbol} - {play.opportunity_type.value}")
                logger.info(f"   💰 Price: ${play.current_price:.2f} (Gap: {play.gap_percentage:+.1f}%)")
                logger.info(f"   📊 Volume: {play.volume:,} ({play.volume/play.avg_volume:.1f}x avg)")
                logger.info(f"   🏢 Market Cap: ${play.market_cap:.0f}M")
                logger.info(f"   ⭐ Quality Score: {play.quality_score:.0f}/100")

                if play.catalyst_type:
                    logger.info(f"   📰 Catalyst: {play.catalyst_type} (confidence: {play.catalyst_confidence}%)")

                logger.info(f"   🎯 Strategy Targets: {', '.join(play.strategy_targets)}")
                logger.info(f"   📈 IBKR Rank: #{play.ibkr_rank}")

                if play.vwap > 0:
                    vwap_dist = ((play.current_price - play.vwap) / play.vwap) * 100
                    logger.info(f"   📊 VWAP: ${play.vwap:.2f} (price {vwap_dist:+.1f}% from VWAP)")

                logger.info("")

            # Test dictionary conversion
            logger.info("📋 Testing dictionary conversion...")
            dict_plays = [play.to_dict() for play in plays]
            logger.info(f"✅ Successfully converted {len(dict_plays)} plays to dictionaries")

            # Display statistics
            stats = scanner.get_scan_statistics()
            logger.info("")
            logger.info(f"📊 Scanner Statistics:")
            logger.info(f"   Scans today: {stats['scans_today']}")
            logger.info(f"   Last scan: {stats['last_scan']}")
            logger.info(f"   Scan interval: {stats['scan_interval_minutes']} minutes")
            logger.info(f"   Fundamental cache: {stats['cache_stats']['fundamental_cache_size']} entries")

        else:
            logger.warning("❌ No MidCap opportunities found")
            logger.info("   This could be because:")
            logger.info("   - Market is not active right now")
            logger.info("   - No MidCaps meeting criteria ($10-$100, $2B-$50B, 5%+ gap)")
            logger.info("   - Scanner interval not reached (adaptive scanning)")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

    finally:
        # Cleanup
        logger.info("")
        logger.info("🧹 Cleaning up...")
        await ibkr.disconnect()
        logger.info("✅ IBKR disconnected")

    logger.info("=" * 80)
    logger.info("✅ TEST COMPLETE")
    logger.info("=" * 80)
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_midcap_scanner())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
