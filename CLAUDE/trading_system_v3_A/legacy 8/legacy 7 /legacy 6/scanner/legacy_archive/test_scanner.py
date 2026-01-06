# scanner/test_scanner.py
"""
Test script para verificar que el scanner funciona correctamente con yahooquery
"""

import asyncio
from daily_plays_filter import DailyPlaysFilter, FilterCriteria

# Sample data de ProRealTime para testing
SAMPLE_PRT_DATA = '''
"Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"
"TLRY"    "TILRAY BRANDS INC."    "6"    "+0,34%"    "+0,0031"    "20:03:57"    "0,9231"    "289M"
"GEVO"    "GEVO INC."    "2"    "+56,00%"    "+0,70"    "22:30:04"    "1,95"    "81,7M"
"AAPL"    "APPLE INC."    "3"    "+2,00%"    "+3,50"    "22:10:09"    "180,00"    "50M"
"TSLA"    "TESLA INC."    "2"    "+5,00%"    "+12,00"    "22:15:00"    "250,00"    "75M"
'''

async def test_scanner():
    """Test básico del scanner"""
    print("🧪 Testing Daily Plays Filter with yahooquery...")
    print("=" * 50)
    
    # Criterios de prueba
    criteria = FilterCriteria(
        max_float_shares=100_000_000  # 100M shares
    )
    
    try:
        async with DailyPlaysFilter(criteria) as filter_tool:
            print("✅ Scanner initialized successfully")
            
            # Test parsing
            print("\n1️⃣ Testing ProRealTime data parsing...")
            ticker_data = filter_tool.parse_prt_data(SAMPLE_PRT_DATA)
            print(f"✅ Parsed {len(ticker_data)} tickers")
            for td in ticker_data:
                print(f"   - {td.ticker}: {td.var_pct:+.2f}% @ ${td.last_price}")
            
            # Test full filtering process
            print("\n2️⃣ Testing full filtering process...")
            result_tickers = await filter_tool.filter_tickers(SAMPLE_PRT_DATA)
            
            if result_tickers:
                print(f"✅ Filter completed successfully!")
                print(f"📊 Final tickers: {', '.join(result_tickers)}")
            else:
                print("⚠️ No tickers passed all filters (normal for test data)")
            
            print("\n3️⃣ Testing output formatting...")
            output = filter_tool.format_output(result_tickers)
            print(f"📋 Formatted output: {output}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Scanner test completed successfully!")
    return True

async def test_individual_components():
    """Test componentes individuales"""
    print("\n🔧 Testing individual components...")
    
    criteria = FilterCriteria()
    
    async with DailyPlaysFilter(criteria) as filter_tool:
        # Test float data for known tickers
        print("\n📊 Testing float data retrieval...")
        test_tickers = ["AAPL", "TSLA", "GEVO"]
        float_data = await filter_tool.get_float_data(test_tickers)
        
        for ticker, float_shares in float_data.items():
            if float_shares:
                print(f"   {ticker}: {float_shares:,.0f} shares")
            else:
                print(f"   {ticker}: No float data")
        
        # Test news data
        print("\n📰 Testing news data retrieval...")
        news_data = await filter_tool.get_news_data(test_tickers[:2])  # Limit to 2 for speed
        
        for ticker, has_catalyst in news_data.items():
            status = "✅ Has catalyst" if has_catalyst else "❌ No catalyst"
            print(f"   {ticker}: {status}")

if __name__ == "__main__":
    print("🚀 Starting Yahoo Query Scanner Tests")
    print("=" * 60)
    
    # Run basic test
    success = asyncio.run(test_scanner())
    
    if success:
        # Run component tests
        asyncio.run(test_individual_components())
        
        print("\n" + "=" * 60)
        print("🎉 All tests completed!")
        print("📝 The scanner is ready to use with yahooquery")
        print("\nNext steps:")
        print("1. pip install -r requirements.txt")
        print("2. streamlit run web_interface.py")
    else:
        print("\n❌ Tests failed. Check the errors above.")