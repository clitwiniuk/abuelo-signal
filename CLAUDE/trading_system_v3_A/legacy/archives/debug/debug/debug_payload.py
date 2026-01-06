#!/usr/bin/env python3
"""
Debug the complete payload generation for IPM confidence
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from integrations.tradetally_sync import TradeTallyIntegration, TradeRecord

def debug_payload_generation():
    """Debug the complete payload generation process"""

    # Database path
    db_path = "trading_data.db"

    print("🔍 Debug Complete Payload Generation")
    print("=" * 50)

    # 1. Create TradeTally integration instance
    integration = TradeTallyIntegration(
        api_key="test",
        base_url="test",
        db_path=db_path
    )

    # 2. Get IPM trade data
    print("\n1. Fetch IPM trade from database:")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE symbol = 'IPM' ORDER BY entry_time DESC LIMIT 1")
    row = cursor.fetchone()

    if not row:
        print("  ❌ No IPM trade found!")
        return

    # 3. Create TradeRecord
    print("\n2. Create TradeRecord object:")
    try:
        trade = TradeRecord(
            id=row['id'],
            trade_id=row['trade_id'],
            symbol=row['symbol'],
            strategy=row['strategy'],
            side=row['side'],
            quantity=row['quantity'],
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            entry_time=row['entry_time'],
            exit_time=row['exit_time'],
            duration_minutes=row['duration_minutes'],
            pnl=row['pnl'],
            commission=row['commission'] or 0,
            status=row['status'],
            notes=row['notes'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            # ML fields as direct attributes
            confidence=row['confidence'] if 'confidence' in row.keys() else None,
            strategy_confidence=row['strategy_confidence'] if 'strategy_confidence' in row.keys() else None,
            ml_signal_quality=row['ml_signal_quality'] if 'ml_signal_quality' in row.keys() else None,
            market_context_score=row['market_context_score'] if 'market_context_score' in row.keys() else None,
            trade_session=row['trade_session'] if 'trade_session' in row.keys() else None,
            volume_ratio=row['volume_ratio'] if 'volume_ratio' in row.keys() else None,
            gap_percentage=row['gap_percentage'] if 'gap_percentage' in row.keys() else None
        )

        print(f"  ✅ TradeRecord created successfully")
        print(f"     confidence: {trade.confidence}")
        print(f"     strategy_confidence: {trade.strategy_confidence}")
        print(f"     ml_signal_quality: {trade.ml_signal_quality}")
        print(f"     market_context_score: {trade.market_context_score}")

    except Exception as e:
        print(f"  ❌ Error creating TradeRecord: {e}")
        return

    # 4. Generate TradeTally payload
    print("\n3. Generate TradeTally payload:")
    try:
        payload = integration.create_tradetally_payload(trade)

        print(f"  ✅ Payload generated successfully")
        print(f"  📋 Relevant fields in payload:")
        for key in ['confidence', 'strategyConfidence', 'mlSignalQuality', 'marketContextScore', 'tradeSession']:
            if key in payload:
                print(f"     {key}: {payload[key]}")
            else:
                print(f"     {key}: [MISSING]")

        print(f"\n  📄 Complete payload:")
        import json
        print(json.dumps(payload, indent=2))

    except Exception as e:
        print(f"  ❌ Error generating payload: {e}")
        import traceback
        print(traceback.format_exc())

    conn.close()

if __name__ == "__main__":
    debug_payload_generation()