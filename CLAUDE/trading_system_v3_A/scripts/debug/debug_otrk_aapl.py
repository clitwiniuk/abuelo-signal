#!/usr/bin/env python3
"""
Specific debug script for OTRK and AAPL symbol issues
"""

import asyncio
import logging
from datetime import datetime, timedelta
from ib_insync import IB, Stock

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_specific_symbols():
    """Debug OTRK and AAPL specifically"""
    
    # Symbols reported as problematic
    test_symbols = ['OTRK', 'AAPL']
    
    print("🔍 Debugging OTRK and AAPL specifically...")
    
    # Connect to IBKR
    ib = IB()
    try:
        print("🔌 Connecting to IBKR...")
        await ib.connectAsync('127.0.0.1', 7497, clientId=9998)
        print("✅ Connected to IBKR")
        
        for symbol in test_symbols:
            print(f"\n" + "="*50)
            print(f"📊 TESTING SYMBOL: {symbol}")
            print("="*50)
            
            # Step 1: Create contract
            print(f"Step 1: Creating contract for {symbol}")
            contract = Stock(symbol, 'SMART', 'USD')
            print(f"   Contract created: {contract}")
            
            # Step 2: Get contract details
            print(f"Step 2: Getting contract details...")
            try:
                details = await asyncio.wait_for(
                    ib.reqContractDetailsAsync(contract), 
                    timeout=15
                )
                
                if details:
                    print(f"   ✅ Found {len(details)} contract details")
                    for i, detail in enumerate(details):
                        print(f"   Detail {i+1}:")
                        print(f"      Symbol: {detail.contract.symbol}")
                        print(f"      Exchange: {detail.contract.exchange}")
                        print(f"      Primary Exchange: {detail.contract.primaryExchange}")
                        print(f"      Currency: {detail.contract.currency}")
                        print(f"      Market Name: {detail.marketName}")
                        print(f"      Trading Hours: {detail.tradingHours}")
                        print(f"      Valid Exchanges: {detail.validExchanges}")
                        
                        # Use the first valid contract
                        if i == 0:
                            contract = detail.contract
                            print(f"   Using contract: {contract}")
                else:
                    print(f"   ❌ No contract details found for {symbol}")
                    continue
                    
            except asyncio.TimeoutError:
                print(f"   ⏰ Timeout getting contract details for {symbol}")
                continue
            except Exception as e:
                print(f"   ❌ Error getting contract details: {e}")
                continue
            
            # Step 3: Test different historical data requests
            print(f"Step 3: Testing historical data requests...")
            
            test_requests = [
                # (duration, bar_size, use_rth, what_to_show)
                ('1 D', '1 min', True, 'TRADES'),
                ('1 D', '1 min', False, 'TRADES'),
                ('2 D', '5 mins', True, 'TRADES'),
                ('1 W', '1 hour', True, 'TRADES'),
                ('1 D', '1 min', True, 'MIDPOINT'),
                ('1 D', '1 min', True, 'BID_ASK'),
            ]
            
            for duration, bar_size, use_rth, what_to_show in test_requests:
                print(f"   🔄 Trying: {duration}, {bar_size}, RTH={use_rth}, {what_to_show}")
                
                try:
                    bars = await asyncio.wait_for(
                        ib.reqHistoricalDataAsync(
                            contract=contract,
                            endDateTime='',
                            durationStr=duration,
                            barSizeSetting=bar_size,
                            whatToShow=what_to_show,
                            useRTH=use_rth,
                            timeout=20
                        ),
                        timeout=25
                    )
                    
                    if bars:
                        print(f"   ✅ SUCCESS: Got {len(bars)} bars")
                        if len(bars) > 0:
                            print(f"      Latest bar: {bars[-1].date} - O:{bars[-1].open} H:{bars[-1].high} L:{bars[-1].low} C:{bars[-1].close} V:{bars[-1].volume}")
                        # If we get data, no need to try more combinations
                        break
                    else:
                        print(f"   ⚠️  No bars returned")
                        
                except asyncio.TimeoutError:
                    print(f"   ⏰ Timeout requesting historical data")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    
            # Step 4: Test current market data
            print(f"Step 4: Testing current market data...")
            try:
                print(f"   🔄 Requesting market data...")
                ticker = ib.reqMktData(contract, '', False, False)
                
                # Wait for data with multiple checks
                for i in range(10):
                    await asyncio.sleep(0.5)
                    if ticker.last and ticker.last > 0:
                        print(f"   ✅ Current price: ${ticker.last}")
                        break
                    elif ticker.close and ticker.close > 0:
                        print(f"   ✅ Last close: ${ticker.close}")
                        break
                    elif ticker.bid and ticker.ask:
                        print(f"   ✅ Bid/Ask: ${ticker.bid}/${ticker.ask}")
                        break
                else:
                    print(f"   ❌ No current price data after 5 seconds")
                    print(f"       Ticker state: last={ticker.last}, close={ticker.close}, bid={ticker.bid}, ask={ticker.ask}")
                    
                # Cancel market data subscription
                ib.cancelMktData(contract)
                    
            except Exception as e:
                print(f"   ❌ Error getting current data: {e}")
            
            # Step 5: Check if symbol is actively traded
            print(f"Step 5: Additional checks...")
            print(f"   Contract exchange: {contract.exchange}")
            print(f"   Contract primary exchange: {contract.primaryExchange}")
            
            # Try a different exchange if SMART didn't work
            if symbol == 'OTRK':
                print(f"   🔄 Trying OTRK on NASDAQ exchange...")
                nasdaq_contract = Stock(symbol, 'NASDAQ', 'USD')
                try:
                    nasdaq_details = await asyncio.wait_for(
                        ib.reqContractDetailsAsync(nasdaq_contract), 
                        timeout=10
                    )
                    if nasdaq_details:
                        print(f"   ✅ NASDAQ contract found for {symbol}")
                    else:
                        print(f"   ❌ No NASDAQ contract for {symbol}")
                except Exception as e:
                    print(f"   ❌ Error with NASDAQ contract: {e}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected from IBKR")

if __name__ == "__main__":
    asyncio.run(debug_specific_symbols())