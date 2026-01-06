import asyncio
import sqlite3
import logging
import sys
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter import IBKRAdapter
from core.interfaces import MarketData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("ManualOHLCSync")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading_data.db')

class ManualOHLCSync:
    def __init__(self):
        # Use a random client ID to avoid conflict
        import random
        client_id = random.randint(10000, 20000)
        self.ibkr = IBKRAdapter(client_id=client_id)
        self.db_path = DB_PATH

    async def connect(self):
        """Connect to IBKR"""
        try:
            await self.ibkr.connect()
            # Give it a moment to stabilize
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    async def disconnect(self):
        """Disconnect from IBKR"""
        await self.ibkr.disconnect()

    def get_recent_trades(self, days: int = 1) -> List[Dict[str, Any]]:
        """Get trades from the last N days from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate cutoff date
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            query = """
                SELECT trade_id, symbol, entry_time, exit_time 
                FROM trades 
                WHERE entry_time >= ? 
                ORDER BY entry_time DESC
            """
            
            cursor.execute(query, (cutoff_date,))
            trades = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return trades
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []

    def save_ohlc_snapshot(self, trade_id: str, symbol: str, market_data: List[MarketData]):
        """Save OHLC data to trade_ohlc_snapshots table"""
        if not market_data:
            return

        max_retries = 5
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Set timeout to 30 seconds to wait for lock release
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get trade details for required fields
                cursor.execute("SELECT entry_time, entry_price FROM trades WHERE trade_id = ?", (trade_id,))
                trade_row = cursor.fetchone()
                
                if not trade_row:
                    logger.warning(f"Trade {trade_id} not found in trades table, skipping snapshot")
                    conn.close()
                    return
                    
                entry_time = trade_row['entry_time']
                entry_price = trade_row['entry_price']
                
                # Convert MarketData objects to JSON-serializable list of dicts
                ohlc_json = json.dumps([
                    {
                        'timestamp': m.timestamp.isoformat() if isinstance(m.timestamp, datetime) else m.timestamp,
                        'open': m.open,
                        'high': m.high,
                        'low': m.low,
                        'close': m.close,
                        'volume': m.volume
                    }
                    for m in market_data
                ])
                
                # Calculate day stats
                day_open = market_data[0].open
                day_high = max(m.high for m in market_data)
                day_low = min(m.low for m in market_data)
                day_close = market_data[-1].close
                day_volume = sum(m.volume for m in market_data)
                trading_date = market_data[0].timestamp.strftime('%Y-%m-%d') if isinstance(market_data[0].timestamp, datetime) else str(market_data[0].timestamp)[:10]

                # Upsert into trade_ohlc_snapshots
                cursor.execute("""
                    INSERT INTO trade_ohlc_snapshots (
                        trade_id, symbol, trading_date, 
                        day_open, day_high, day_low, day_close, day_volume,
                        intraday_bars, entry_time, entry_price, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trade_id) DO UPDATE SET
                        intraday_bars = excluded.intraday_bars,
                        day_open = excluded.day_open,
                        day_high = excluded.day_high,
                        day_low = excluded.day_low,
                        day_close = excluded.day_close,
                        day_volume = excluded.day_volume,
                        updated_at = excluded.updated_at
                """, (
                    trade_id, symbol, trading_date,
                    day_open, day_high, day_low, day_close, day_volume,
                    ohlc_json, entry_time, entry_price, datetime.now().isoformat()
                ))
                
                conn.commit()
                conn.close()
                logger.info(f"✅ Saved {len(market_data)} bars for trade {trade_id}")
                return # Success, exit loop
                
            except sqlite3.OperationalError as e:
                if "locked" in str(e):
                    logger.warning(f"Database locked for trade {trade_id} (attempt {attempt+1}/{max_retries}), retrying...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Database error for trade {trade_id}: {e}")
                    return # Fatal error
            except Exception as e:
                logger.error(f"Error saving snapshot for trade {trade_id}: {e}")
                return # Fatal error

    async def sync_trades(self):
        """Main sync logic"""
        if not await self.connect():
            print(json.dumps({"status": "error", "message": "Could not connect to IBKR"}))
            return

        try:
            trades = self.get_recent_trades(days=5) # Look back 5 days to be safe
            logger.info(f"Found {len(trades)} recent trades to check")
            
            synced_count = 0
            
            for trade in trades:
                symbol = trade['symbol']
                trade_id = trade['trade_id']
                entry_time_str = trade['entry_time']
                
                logger.info(f"Processing {symbol} (Trade ID: {trade_id})")
                
                # Calculate endDateTime based on entry_time
                # We want the end of the trading day of the entry
                try:
                    # Parse entry time (format: YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM:SS...)
                    if 'T' in entry_time_str:
                        entry_dt = datetime.fromisoformat(entry_time_str)
                    else:
                        entry_dt = datetime.strptime(entry_time_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    
                    # Set to end of that day in US/Eastern
                    # Note: IBKR expects 'YYYYMMDD HH:mm:ss' and optionally timezone
                    # We will request data ending at 23:59:59 of the entry date
                    end_date_str = entry_dt.strftime("%Y%m%d 23:59:59 US/Eastern")
                    
                except Exception as e:
                    logger.warning(f"Could not parse entry time '{entry_time_str}' for {symbol}: {e}. Using current time.")
                    end_date_str = ''

                # Get contract using adapter helper
                contract = await self.ibkr._get_contract(symbol)
                if not contract:
                    logger.warning(f"Could not get contract for {symbol}")
                    continue

                # Fetch 1 day of 1-minute bars ending at the trade date
                try:
                    bars = await self.ibkr.ib.reqHistoricalDataAsync(
                        contract=contract,
                        endDateTime=end_date_str,
                        durationStr='1 D',
                        barSizeSetting='1 min',
                        whatToShow='TRADES',
                        useRTH=False, # Include extended hours (premarket + afterhours) for accurate replay
                        timeout=20
                    )
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol}: {e}")
                    bars = []
                
                if bars:
                    # Convert IBKR bars to MarketData-like objects for the save function
                    # The save function expects objects with timestamp, open, high, low, close, volume attributes
                    # IBKR bars already have these attributes (date, open, high, low, close, volume)
                    # We just need to map 'date' to 'timestamp'
                    
                    class BarWrapper:
                        def __init__(self, bar):
                            self.timestamp = bar.date
                            self.open = bar.open
                            self.high = bar.high
                            self.low = bar.low
                            self.close = bar.close
                            self.volume = bar.volume

                    market_data = [BarWrapper(b) for b in bars]
                    
                    self.save_ohlc_snapshot(trade_id, symbol, market_data)
                    synced_count += 1
                else:
                    logger.warning(f"No data found for {symbol} on {end_date_str}")
                
                # Rate limiting pause
                await asyncio.sleep(0.5)
            
            result = {
                "status": "success", 
                "message": f"Successfully synced {synced_count} trades",
                "synced_count": synced_count,
                "total_checked": len(trades)
            }
            print(json.dumps(result))
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            print(json.dumps({"status": "error", "message": str(e)}))
        finally:
            await self.disconnect()

if __name__ == "__main__":
    syncer = ManualOHLCSync()
    asyncio.run(syncer.sync_trades())
