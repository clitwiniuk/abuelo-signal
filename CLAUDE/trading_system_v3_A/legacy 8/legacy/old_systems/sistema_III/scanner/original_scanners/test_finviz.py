# scanner/test_finviz.py
"""
Test script specifically for Finviz integration
"""

import asyncio
from news_sources import MultiSourceNewsChecker, NewsSource
from daily_plays_filter import FilterCriteria

async def test_finviz_integration():
    """Test Finviz as primary news source"""
    print("🔍 Testing Finviz Integration")
    print("=" * 50)
    
    # Test configuration - no NewsAPI key needed for Finviz
    config = NewsSource(
        newsapi_key=None,  # Will skip NewsAPI
        days_back=7
    )
    
    # Enhanced keywords including crypto-related terms
    criteria = FilterCriteria()
    
    print(f"📰 Keywords to check: {len(criteria.catalyst_keywords)} total")
    print(f"   Crypto-related: crypto, bitcoin, ethereum, stake, investment")
    print(f"   M&A related: acquisition, merger, partnership")
    print(f"   Business: earnings, revenue, contract")
    print()
    
    # Initialize checker with Finviz priority
    checker = MultiSourceNewsChecker(config, criteria.catalyst_keywords)
    
    # Test tickers - mix of potentially active stocks
    test_tickers = [
        'NVDA',   # Often has news
        'AAPL',   # Regular news
        'TSLA',   # Frequent news
        'GEVO',   # Biotech - might have catalysts
        # Add your ETHZilla example if you know the symbol
    ]
    
    print(f"🧪 Testing {len(test_tickers)} tickers with Finviz priority...")
    print()
    
    try:
        results = await checker.check_all_sources(test_tickers)
        
        for ticker, result in results.items():
            print(f"📊 {ticker}:")
            print(f"   Has Catalyst: {'✅' if result['has_catalyst'] else '❌'}")
            print(f"   Summary: {result['summary']}")
            
            # Show source performance
            for source, data in result['sources'].items():
                if 'error' in data:
                    print(f"   ❌ {source}: {data['error']}")
                elif 'skipped' in data:
                    print(f"   ⏭️ {source}: {data['skipped']}")
                else:
                    status = "✅" if data.get('has_catalyst') else "❌"
                    articles = data.get('articles_found', 'N/A')
                    relevant = data.get('relevant_articles', 0)
                    print(f"   {status} {source}: {relevant}/{articles} relevant articles")
                    
                    if data.get('keywords'):
                        print(f"      Keywords found: {', '.join(data['keywords'])}")
            
            # Show sentiment analysis if available
            if result.get('sentiment_analysis'):
                sentiment = result['sentiment_analysis']
                print(f"   🎯 Sentiment: {sentiment.sentiment.value} (confidence: {sentiment.confidence:.2f})")
                print(f"   📈 Suitable for LONG: {'✅' if result.get('has_positive_catalyst') else '❌'}")
            
            print()
    
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("=" * 50)
    print("🎉 Finviz integration test completed!")
    print()
    print("📝 Note: To test ETHZilla specifically, you would need:")
    print("1. The correct ticker symbol")
    print("2. Run: test_tickers = ['ETHZILLA_SYMBOL']")
    print("3. The news should show 'Peter Thiel buys stake' = positive catalyst")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_finviz_integration())