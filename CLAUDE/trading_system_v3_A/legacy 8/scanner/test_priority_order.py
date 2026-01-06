# scanner/test_priority_order.py
"""
Test the new priority order for news sources
"""

import asyncio
from news_sources import MultiSourceNewsChecker, NewsSource
from daily_plays_filter import FilterCriteria

async def test_priority_order():
    """Test the new priority order: Finviz -> SEC -> Yahoo -> NewsAPI"""
    print("🔄 Testing New Priority Order")
    print("=" * 50)
    
    # Test configuration
    config = NewsSource(newsapi_key=None, days_back=7)
    criteria = FilterCriteria()
    
    # Initialize checker
    checker = MultiSourceNewsChecker(config, criteria.catalyst_keywords)
    
    print("📊 New Priority Order:")
    print("   1️⃣ Finviz (primary)")
    print("   2️⃣ SEC EDGAR")
    print("   3️⃣ Yahoo Finance")
    print("   4️⃣ NewsAPI (last resort)")
    print()
    
    # Test with a ticker that might have news
    test_tickers = ['TSLA']  # Known to have frequent news
    
    print(f"🧪 Testing with {test_tickers[0]}...")
    print()
    
    results = await checker.check_all_sources(test_tickers)
    
    for ticker, result in results.items():
        print(f"📊 {ticker} Results:")
        print(f"   Has Catalyst: {'✅' if result['has_catalyst'] else '❌'}")
        print(f"   Summary: {result['summary']}")
        print()
        
        print("   📰 Source Check Order:")
        for i, (source, data) in enumerate(result['sources'].items(), 1):
            if 'error' in data:
                status = f"❌ Error: {data['error']}"
            elif 'skipped' in data:
                status = f"⏭️ Skipped: {data['skipped']}"
            elif data.get('has_catalyst'):
                status = f"✅ Found {data.get('relevant_articles', 0)} relevant articles"
                if data.get('keywords'):
                    status += f" (Keywords: {', '.join(data['keywords'])})"
            else:
                status = f"❌ No catalysts found ({data.get('articles_found', 0)} articles checked)"
            
            print(f"      {i}️⃣ {source}: {status}")
        
        # Show sentiment analysis if available
        if result.get('sentiment_analysis'):
            sentiment = result['sentiment_analysis']
            print(f"   🎯 Sentiment: {sentiment.sentiment.value} (confidence: {sentiment.confidence:.2f})")
            print(f"   📈 Suitable for LONG: {'✅' if result.get('has_positive_catalyst') else '❌'}")
    
    print()
    print("=" * 50)
    print("✅ Priority order test completed!")
    print()
    print("💡 How it works:")
    print("• If Finviz finds catalysts -> skips SEC, Yahoo, NewsAPI")
    print("• If Finviz fails but SEC finds catalysts -> skips Yahoo, NewsAPI")
    print("• If Finviz + SEC fail but Yahoo finds catalysts -> skips NewsAPI")
    print("• Only checks NewsAPI if all others fail")

if __name__ == "__main__":
    asyncio.run(test_priority_order())