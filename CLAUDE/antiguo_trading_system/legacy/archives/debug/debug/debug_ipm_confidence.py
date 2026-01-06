#!/usr/bin/env python3
"""
Debug IPM confidence extraction
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from integrations.tradetally_sync import TradeTallyIntegration, TradeRecord

def debug_ipm_confidence():
    """Debug why IPM confidence is not being extracted"""

    # Database path
    db_path = "trading_data.db"

    print("🔍 Debug IPM Confidence Extraction")
    print("=" * 50)

    # 1. Check database value
    print("\n1. Database values:")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT trade_id, symbol, confidence, strategy_confidence,
               ml_signal_quality, market_context_score, trade_session
        FROM trades
        WHERE symbol = 'IPM'
        ORDER BY entry_time DESC LIMIT 1
    """)
    row = cursor.fetchone()

    if row:
        print(f"  trade_id: {row['trade_id']}")
        print(f"  confidence: {row['confidence']} (type: {type(row['confidence'])})")
        print(f"  strategy_confidence: {row['strategy_confidence']} (type: {type(row['strategy_confidence'])})")
        print(f"  ml_signal_quality: {row['ml_signal_quality']}")
        print(f"  market_context_score: {row['market_context_score']}")
        print(f"  trade_session: {row['trade_session']}")

    # 2. Test TradeRecord creation
    print("\n2. TradeRecord creation:")
    cursor.execute("SELECT * FROM trades WHERE symbol = 'IPM' ORDER BY entry_time DESC LIMIT 1")
    row = cursor.fetchone()

    if row:
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

            print(f"  TradeRecord.confidence: {trade.confidence} (hasattr: {hasattr(trade, 'confidence')})")
            print(f"  TradeRecord.strategy_confidence: {trade.strategy_confidence} (hasattr: {hasattr(trade, 'strategy_confidence')})")
            print(f"  TradeRecord.ml_signal_quality: {trade.ml_signal_quality}")
            print(f"  TradeRecord.market_context_score: {trade.market_context_score}")
            print(f"  TradeRecord.trade_session: {trade.trade_session}")

        except Exception as e:
            print(f"  Error creating TradeRecord: {e}")

    # 3. Test hybrid extraction logic
    print("\n3. Hybrid extraction logic test:")
    if 'trade' in locals():
        confidence_value = None

        # Priority 1: Use database columns (new system)
        print(f"  Checking trade.confidence: {getattr(trade, 'confidence', 'NO_ATTR')} (not None: {getattr(trade, 'confidence', None) is not None})")
        if hasattr(trade, 'confidence') and trade.confidence is not None:
            confidence_value = float(trade.confidence)
            print(f"  ✅ Using confidence: {confidence_value}")
        elif hasattr(trade, 'strategy_confidence') and trade.strategy_confidence is not None:
            confidence_value = float(trade.strategy_confidence)
            print(f"  ✅ Using strategy_confidence: {confidence_value}")
        else:
            print(f"  ❌ No confidence values found")
            print(f"      hasattr(confidence): {hasattr(trade, 'confidence')}")
            print(f"      hasattr(strategy_confidence): {hasattr(trade, 'strategy_confidence')}")
            if hasattr(trade, 'confidence'):
                print(f"      trade.confidence value: {trade.confidence}")
            if hasattr(trade, 'strategy_confidence'):
                print(f"      trade.strategy_confidence value: {trade.strategy_confidence}")

        print(f"  Final confidence_value: {confidence_value}")

    conn.close()

if __name__ == "__main__":
    debug_ipm_confidence()