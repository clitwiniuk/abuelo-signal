# scanner/test_enhanced_scanner.py
"""
Test script for the enhanced scanner with multiple news sources
"""

import asyncio
from daily_plays_filter import DailyPlaysFilter, FilterCriteria
from config import ScannerConfig, SETUP_INSTRUCTIONS

# Sample data with some tickers that might have news
ENHANCED_SAMPLE_DATA = '''
"Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"
"GEVO"    "GEVO INC."    "2"    "+56,00%"    "+0,70"    "22:30:04"    "1,95"    "81,7M"
"NVDA"    "NVIDIA CORP."    "3"    "+12,00%"    "+30,00"    "22:15:00"    "280,00"    "95M"
"AMD"    "ADVANCED MICRO DEVICES"    "2"    "+8,50%"    "+12,50"    "22:20:00"    "160,00"    "75M"
"PLUG"    "PLUG POWER INC."    "4"    "+15,20%"    "+0,25"    "22:25:00"    "1,89"    "60M"
'''

async def test_enhanced_scanner():
    """Test the enhanced scanner with multiple news sources"""
    print("🚀 Testing Enhanced Daily Plays Filter")
    print("=" * 60)
    
    # Check configuration
    print("🔧 Configuration Check:")
    if ScannerConfig.has_newsapi_key():
        print("✅ NewsAPI key available")
    else:
        print("⚠️ NewsAPI key not found (will use free sources only)")
        print("\n📝 To get NewsAPI key:")
        print("   1. Visit: https://newsapi.org/register")
        print("   2. Set environment: export NEWSAPI_API_KEY=your_key")
        print("   3. Or edit config.py directly")
    
    print(f"✅ SEC EDGAR: Available (free)")
    print(f"✅ Yahoo Finance: Available (free)")
    print()
    
    # Initialize scanner with enhanced news checking
    criteria = FilterCriteria(max_float_shares=200_000_000)  # Higher limit for testing
    newsapi_key = ScannerConfig.get_newsapi_key()
    
    try:
        async with DailyPlaysFilter(criteria, newsapi_key) as filter_tool:
            print("✅ Enhanced scanner initialized")
            
            # Test parsing
            print("\n1️⃣ Testing ProRealTime data parsing...")
            ticker_data = filter_tool.parse_prt_data(ENHANCED_SAMPLE_DATA)
            print(f"✅ Parsed {len(ticker_data)} tickers")
            
            for td in ticker_data:
                print(f"   - {td.ticker}: {td.var_pct:+.2f}% @ ${td.last_price}")
            
            # Test enhanced filtering
            print("\n2️⃣ Testing enhanced filtering with multiple news sources...")
            result_tickers = await filter_tool.filter_tickers(ENHANCED_SAMPLE_DATA)
            
            print(f"\n📊 Final Results:")
            if result_tickers:
                print(f"✅ {len(result_tickers)} tickers passed all filters:")
                for ticker in result_tickers:
                    print(f"   - {ticker}")
                
                # Show detailed news results if available
                if hasattr(filter_tool, 'detailed_news_results'):
                    print(f"\n📰 Detailed News Analysis:")
                    for ticker in result_tickers:
                        if ticker in filter_tool.detailed_news_results:
                            result = filter_tool.detailed_news_results[ticker]
                            print(f"\n   🎯 {ticker}:")
                            print(f"      Summary: {result['summary']}")
                            
                            for source, data in result['sources'].items():
                                status = "✅" if data.get('has_catalyst') else "❌"
                                articles = data.get('articles_found', 0)
                                relevant = data.get('relevant_articles', 0)
                                print(f"      {status} {source}: {relevant}/{articles} relevant articles")
                                
                                if data.get('keywords'):
                                    print(f"         Keywords: {', '.join(data['keywords'])}")
            else:
                print("⚠️ No tickers passed all filters")
                print("   This is normal - the enhanced filters are quite strict")
            
            # Test individual news sources
            print(f"\n3️⃣ Testing individual news source performance...")
            test_tickers = ["NVDA", "GEVO"]  # Known active stocks
            
            if hasattr(filter_tool, 'news_checker'):
                detailed_results = await filter_tool.news_checker.check_all_sources(test_tickers)
                
                print(f"\n📊 News Source Performance:")
                for ticker, result in detailed_results.items():
                    print(f"\n   📈 {ticker}:")
                    for source, data in result['sources'].items():
                        if 'error' in data:
                            print(f"      ❌ {source}: {data['error']}")
                        else:
                            status = "✅" if data.get('has_catalyst') else "❌"
                            articles = data.get('articles_found', 'N/A')
                            print(f"      {status} {source}: {articles} articles found")
            
    except Exception as e:
        print(f"❌ Error during enhanced testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("🎉 Enhanced scanner testing completed!")
    print("\n📝 Next Steps:")
    print("1. Get NewsAPI key for better news coverage")
    print("2. Use streamlit run web_interface.py for GUI")
    print("3. Test with real ProRealTime data")
    
    return True

if __name__ == "__main__":
    print(SETUP_INSTRUCTIONS)
    print("\n" + "=" * 60)
    asyncio.run(test_enhanced_scanner())