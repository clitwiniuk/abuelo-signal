#!/usr/bin/env python3
"""
Verification Script for Scanner -> Trader Data Flow
Verifies that SmallcapPlay objects are correctly serialized with UPPERCASE opportunity types.
"""

import sys
import os
import json
import logging
from datetime import datetime
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay, OpportunityType, SmallcapContext

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

def test_serialization():
    logger.info("🧪 Testing SmallcapPlay Serialization...")

    # 1. Create Dummy Context
    context = SmallcapContext(
        symbol="TEST",
        timestamp=datetime.now(),
        current_price=10.50,
        gap_percentage=5.5,
        premarket_high=11.00,
        premarket_low=10.00,
        premarket_volume=500000,
        avg_daily_volume=100000,
        premarket_volume_ratio=5.0,
        news_catalyst_type="UNKNOWN",
        news_age_hours=0.0,
        catalyst_strength=0,
        float_size=5000000,
        market_cap=100000000,
        price_vs_premarket_high=0.95,
        volume_spike_confirmed=True,
        market_fear_level="LOW"
    )

    # 2. Create Dummy Play with GAP_BREAKOUT (formerly gap_breakout)
    play = SmallcapPlay(
        symbol="TEST",
        context=context,
        catalyst=None,
        quality_score=8.5,
        trading_recommendation={'action': 'LONG', 'entry_type': 'GAP_BREAKOUT'},
        scan_timestamp=datetime.now(),
        ibkr_rank=1,
        opportunity_type=OpportunityType.GAP_BREAKOUT, # <--- Testing this
        strategy_targets=['gap_go']
    )

    # 3. Serialize
    data_dict = play.to_dict()
    
    # 4. Verify Opportunity Type
    opp_type = data_dict['opportunity_type']
    logger.info(f"🔍 Serialized opportunity_type: '{opp_type}'")

    if opp_type == "GAP_BREAKOUT":
        logger.info("✅ SUCCESS: Opportunity Type is UPPERCASE")
    else:
        logger.error(f"❌ FAILURE: Opportunity Type is '{opp_type}' (Expected 'GAP_BREAKOUT')")
        sys.exit(1)

    # 5. Verify JSON Serialization (simulating Redis message)
    try:
        json_payload = json.dumps(data_dict)
        logger.info("✅ SUCCESS: Object is JSON serializable")
        logger.info(f"📦 Payload snippet: {json_payload[:100]}...")
    except Exception as e:
        logger.error(f"❌ FAILURE: JSON serialization error: {e}")
        sys.exit(1)

    # 6. Check Short Squeeze Type
    logger.info("\n🧪 Testing Short Squeeze Type...")
    play_squeeze = SmallcapPlay(
        symbol="SQUEEZE",
        context=context,
        catalyst=None,
        quality_score=9.0,
        trading_recommendation={'action': 'LONG'},
        scan_timestamp=datetime.now(),
        ibkr_rank=2,
        opportunity_type=OpportunityType.SHORT_SQUEEZE,
        strategy_targets=['squeeze']
    )
    data_squeeze = play_squeeze.to_dict()
    if data_squeeze['opportunity_type'] == "SHORT_SQUEEZE":
        logger.info("✅ SUCCESS: SHORT_SQUEEZE is UPPERCASE")
    else:
        logger.error(f"❌ FAILURE: SHORT_SQUEEZE is '{data_squeeze['opportunity_type']}'")

if __name__ == "__main__":
    test_serialization()
