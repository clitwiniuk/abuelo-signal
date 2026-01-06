import asyncio
import sqlite3
import logging
import sys
import json
import os
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter import IBKRAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("FetchDayData")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading_data.db')

class DayDataFetcher:
    def __init__(self):
        import random
        # Use random client ID to avoid conflicts
        self.ibkr = IBKRAdapter(client_id=random.randint(20000, 30000))
        self.db_path = DB_PATH
        
    async def connect(self):
        try:
            await self.ibkr.connect()
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
            
    async def disconnect(self):
        await self.ibkr.disconnect()

    def save_bars(self, symbol: str, bars):
        if not bars:
            return 0
            
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            count = 0
            from datetime import timezone
            for bar in bars:
                # Convert to UTC Naive
                # bar.date is typically timezone aware (Exchange Time) or naive (if no lib support)
                # We want to ensure it is UTC.
                
                dt = bar.date
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    # If naive, assume it's exchange time (EST/EDT) and convert? 
                    # OR just assume it's already what we want? 
                    # Usually ib_insync returns aware datetimes if useRTH=True/False depending on version.
                    # Safest is to handle aware. If naive, we might need manual offset. 
                    # But for now, let's assume if it is naive, we leave it (or it's already UTC).
                    pass
                
                ts_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # VWAP might be available in bar.wap if using TRADES
                vwap = getattr(bar, 'wap', 0.0)
                
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO market_intraday_bars 
                        (symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume, vwap, timeframe, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '1min', 'Backtest')
                    """, (
                        symbol, ts_str, 
                        bar.open, bar.high, bar.low, bar.close, int(bar.volume), vwap
                    ))
                    if cursor.rowcount > 0:
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert bar {ts_str}: {e}")
                    
            conn.commit()
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Database error: {e}")
            return 0

    async def fetch_polygon(self, symbol: str, date_str: str, api_key: str):
        import requests
        from collections import namedtuple
        
        Bar = namedtuple('Bar', ['date', 'open', 'high', 'low', 'close', 'volume', 'wap'])
        
        try:
            # Polygon expects YYYY-MM-DD
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{date_str}/{date_str}?adjusted=true&sort=asc&limit=50000&apiKey={api_key}"
            logger.info(f"Fetching Polygon data for {symbol}...")
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('status') != 'OK' and data.get('resultsCount', 0) == 0:
                logger.warning(f"Polygon returned no data for {symbol}: {data.get('status')}")
                return []
                
            bars = []
            results = data.get('results', [])
            
            for r in results:
                # Polygon timestamp is in milliseconds UTC
                dt = datetime.fromtimestamp(r['t'] / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
                # Ensure we skip if it's outside the request date (shouldn't happen with API logic but safety check)
                
                # Polygon fields: o, h, l, c, v, vw (volume weighted average price)
                vw = r.get('vw', 0.0)
                
                b = Bar(date=dt, open=float(r['o']), high=float(r['h']), low=float(r['l']), close=float(r['c']), volume=int(r['v']), wap=float(vw))
                bars.append(b)
                
            return bars
            
        except Exception as e:
            logger.error(f"Polygon fetch failed for {symbol}: {e}")
            return []

    async def fetch_batch(self, symbols: str, date_str: str, polygon_key: str = None):
        if not await self.connect():
            return {"status": "error", "message": "Connection failed"}

        results = []
        symbol_list = [s.strip() for s in symbols.split(',')]
        
        try:
            # Date string is YYYY-MM-DD
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            # EndDateTime for IBKR reqHistoricalData should be end of that day
            end_str = target_date.strftime("%Y%m%d 23:59:59 US/Eastern")
            
            # Counter for Polygon rate limiting (Free tier: 5 calls / min)
            polygon_calls = 0

            for symbol in symbol_list:
                bars = []
                source = "IBKR"
                
                try:
                    contract = await self.ibkr._get_contract(symbol)
                    if contract:
                        logger.info(f"Fetching IBKR data for {symbol}")
                        bars = await self.ibkr.ib.reqHistoricalDataAsync(
                            contract=contract,
                            endDateTime=end_str,
                            durationStr='1 D',
                            barSizeSetting='1 min',
                            whatToShow='TRADES',
                            useRTH=False, 
                            timeout=30
                        )
                    
                    if not bars or len(bars) == 0:
                        logger.warning(f"IBKR returned no bars for {symbol}")
                        # Fallback to Polygon if key provided
                        if polygon_key:
                            # RATE LIMIT CHECK
                            if polygon_calls > 0 and polygon_calls % 5 == 0:
                                logger.info(f"Polygon Free Tier Limit (5 req/min). Sleeping 65s to reset quota...")
                                await asyncio.sleep(65)

                            logger.info(f"Falling back to Polygon for {symbol}")
                            bars = await self.fetch_polygon(symbol, date_str, polygon_key)
                            polygon_calls += 1 # Count the attempt
                            
                            if bars:
                                source = "Polygon"
                        else:
                             # If no polygon key, we just have empty bars
                             pass
                    elif len(bars) > 0 and polygon_key:
                        # IBKR gave us something, so we don't fallback by default.
                        pass

                    if not bars:
                         results.append({"symbol": symbol, "status": "warning", "message": "No bars found (IBKR & Polygon)"})
                         continue

                    saved_count = self.save_bars(symbol, bars)
                    results.append({"symbol": symbol, "status": "success", "fetched": len(bars), "saved": saved_count, "source": source})
                    
                    # Pace requests slightly
                    await asyncio.sleep(0.5)
                    
                except Exception as ex:
                    logger.error(f"Error fetching {symbol}: {ex}")
                    # Try Polygon on Exception too
                    if polygon_key:
                        try:
                            # RATE LIMIT CHECK (Duplicate logic for exception path)
                            if polygon_calls > 0 and polygon_calls % 5 == 0:
                                logger.info(f"Polygon Free Tier Limit (5 req/min). Sleeping 65s to reset quota...")
                                await asyncio.sleep(65)

                            logger.info(f"Exception fallback to Polygon for {symbol}")
                            bars = await self.fetch_polygon(symbol, date_str, polygon_key)
                            polygon_calls += 1
                            
                            if bars:
                                saved_count = self.save_bars(symbol, bars)
                                results.append({"symbol": symbol, "status": "success", "fetched": len(bars), "saved": saved_count, "source": "Polygon"})
                                continue
                        except Exception as p_ex:
                            logger.error(f"Polygon fallback also failed: {p_ex}")

                    results.append({"symbol": symbol, "status": "error", "message": str(ex)})

            return results
            
        except Exception as e:
            logger.error(f"Batch Fetch error: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            await self.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", required=True, help="Ticker symbols (comma separated)")
    parser.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    parser.add_argument("--polygon-key", required=False, help="Polygon.io API Key", default=None)
    
    args = parser.parse_args()
    
    fetcher = DayDataFetcher()
    result = asyncio.run(fetcher.fetch_batch(args.symbols, args.date, args.polygon_key))
    print(json.dumps(result))
