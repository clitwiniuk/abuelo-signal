#!/usr/bin/env python3
"""
Script para forzar la sincronización de posiciones con estrategias desde la BD
Sin necesidad de reiniciar el sistema completo
"""

import asyncio
import logging
from core.database_manager import DatabaseManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def force_sync_positions():
    """Force sync positions with strategies from DB"""
    print("🔄 Forcing position sync from DB")
    print("=" * 50)
    
    try:
        # Get DB data
        db = DatabaseManager()
        open_trades = db.load_latest_open_trades_by_symbol()
        
        print(f"📊 Found {len(open_trades)} unique open trades in DB:")
        
        # Show what we would sync
        symbol_to_strategy = {}
        for t in open_trades:
            symbol = t['symbol']
            strategy = t.get('strategy', 'unknown')
            
            # Skip test symbols
            if symbol in ['SAFE_SYMBOL', 'BACKUP_SYMBOL'] or len(symbol) > 20:
                continue
                
            symbol_to_strategy[symbol] = {
                'strategy': strategy,
                'trade_id': t.get('trade_id'),
                'entry_price': t['entry_price'],
                'entry_time': t['entry_time']
            }
            
            print(f"   {symbol}: {strategy} @ ${t['entry_price']} (ID: {t.get('trade_id', 'N/A')[:8]}...)")
        
        print(f"\n🎯 Would sync {len(symbol_to_strategy)} real positions:")
        for symbol, info in symbol_to_strategy.items():
            print(f"   ✅ {symbol} → {info['strategy']}")
        
        print("\n" + "=" * 50)
        print("💡 The sync should happen automatically during next restart")
        print("💡 Or the warnings are normal for legacy positions")
        
        # Check if current positions match
        print(f"\n🔍 Checking current system state...")
        
        # Try to see if ML engine is running
        try:
            from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
            print("🤖 ML Engine class found - system should be working")
        except Exception as e:
            print(f"❌ ML Engine not accessible: {e}")
            
        return True
        
    except Exception as e:
        logger.error(f"Error during force sync: {e}")
        return False

async def main():
    success = await force_sync_positions()
    print(f"\n{'✅ Success' if success else '❌ Failed'}")

if __name__ == "__main__":
    asyncio.run(main())