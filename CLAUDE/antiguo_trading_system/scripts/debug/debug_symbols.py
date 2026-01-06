#!/usr/bin/env python3
"""
Debug script to investigate why specific symbols don't return data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from ib_insync import IB, Stock

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_symbol_data():
    """Debug specific symbols to understand why they don't return data"""
    
    # Symbols that are failing
    problem_symbols = ['BZAI', 'MEIP', 'SVRE', 'BTOG', 'TELO', 'XPON', 'GVH']
    
    # Working symbols for comparison
    working_symbols = ['AAPL', 'MSFT', 'GOOGL']
    
    print("🔍 Debugging symbol data issues...")
    
    # Connect to IBKR
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 7497, clientId=9997)
        print("✅ Connected to IBKR")
        
        # Test each problematic symbol
        for symbol in problem_symbols:
            print(f"\n📊 Testing symbol: {symbol}")
            
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Try to get contract details first
            try:
                details = await ib.reqContractDetailsAsync(contract)
                if details:
                    print(f"   ✅ Contract details found: {len(details)} contracts")
                    for detail in details:
                        print(f"      - Exchange: {detail.contract.exchange}")
                        print(f"      - Primary Exchange: {detail.contract.primaryExchange}")
                        print(f"      - Market Name: {detail.marketName}")
                        print(f"      - Valid Exchanges: {detail.validExchanges}")
                else:
                    print(f"   ❌ No contract details found")
                    continue
                    
            except Exception as e:
                print(f"   ❌ Error getting contract details: {e}")
                continue
            
            # Try different duration/timeframe combinations
            test_combinations = [
                ('1 day', '1 min', 10),
                ('1 day', '5 mins', 10),
                ('5 D', '1 hour', 10),
                ('1 Y', '1 day', 50),
            ]
            
            for duration, bar_size, count in test_combinations:
                try:
                    print(f"   🔄 Trying: {duration}, {bar_size}, {count} bars")
                    
                    bars = await ib.reqHistoricalDataAsync(
                        contract=contract,
                        endDateTime='',
                        durationStr=duration,
                        barSizeSetting=bar_size,
                        whatToShow='TRADES',
                        useRTH=True,
                        timeout=10
                    )
                    
                    if bars:
                        print(f"   ✅ Got {len(bars)} bars")
                        if len(bars) > 0:
                            print(f"      First bar: {bars[0].date} - O:{bars[0].open} H:{bars[0].high} L:{bars[0].low} C:{bars[0].close}")
                            break
                    else:
                        print(f"   ⚠️  No bars returned")
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    
            # Try to get current market data
            try:
                print(f"   🔄 Trying current market data...")
                ticker = ib.reqMktData(contract, '', False, False)
                await asyncio.sleep(2)  # Wait for data
                
                if ticker.last and ticker.last > 0:
                    print(f"   ✅ Current price: ${ticker.last}")
                elif ticker.close and ticker.close > 0:
                    print(f"   ✅ Last close: ${ticker.close}")
                else:
                    print(f"   ❌ No current price data")
                    
                ib.cancelMktData(contract)
                    
            except Exception as e:
                print(f"   ❌ Error getting current data: {e}")
        
        # Test working symbols for comparison
        print(f"\n✅ Testing working symbols for comparison:")
        for symbol in working_symbols[:1]:  # Just test AAPL
            print(f"\n📊 Testing working symbol: {symbol}")
            
            contract = Stock(symbol, 'SMART', 'USD')
            
            try:
                bars = await ib.reqHistoricalDataAsync(
                    contract=contract,
                    endDateTime='',
                    durationStr='1 D',
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True,
                    timeout=10
                )
                
                if bars:
                    print(f"   ✅ Got {len(bars)} bars")
                else:
                    print(f"   ❌ No bars returned")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected from IBKR")

if __name__ == "__main__":
    asyncio.run(debug_symbol_data())