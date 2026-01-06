# scanner/debug_sentiment.py
"""
Debug script to see what's happening with sentiment analysis
"""

import asyncio
from news_sources import MultiSourceNewsChecker, NewsSource
from daily_plays_filter import FilterCriteria

async def debug_sentiment():
    """Debug sentiment analysis for specific tickers"""
    print("🔍 Debugging Sentiment Analysis")
    print("=" * 50)
    
    # Test tickers that showed catalysts
    test_tickers = ['BSLK', 'CGTX', 'UPXI']
    
    # Initialize checker
    config = NewsSource(newsapi_key=None, days_back=7)
    criteria = FilterCriteria()
    checker = MultiSourceNewsChecker(config, criteria.catalyst_keywords)
    
    print(f"🧪 Testing sentiment for: {test_tickers}")
    print()
    
    results = await checker.check_all_sources(test_tickers)
    
    for ticker in test_tickers:
        if ticker in results:
            result = results[ticker]
            print(f"📊 {ticker} Analysis:")
            print(f"   Has Catalyst: {result.get('has_catalyst', False)}")
            print(f"   Has POSITIVE Catalyst: {result.get('has_positive_catalyst', False)}")
            
            # Show Finviz results specifically
            finviz_data = result.get('sources', {}).get('finviz', {})
            if finviz_data.get('has_catalyst'):
                print(f"   ✅ Finviz found: {finviz_data.get('keywords', [])} keywords")
                print(f"   📰 Sample text: {finviz_data.get('sample_text', '')[:200]}...")
            
            # Show sentiment analysis details
            sentiment_analysis = result.get('sentiment_analysis')
            if sentiment_analysis:
                print(f"   🎯 Sentiment: {sentiment_analysis.sentiment.value}")
                print(f"   📊 Confidence: {sentiment_analysis.confidence:.2f}")
                print(f"   ✅ Positive keywords: {sentiment_analysis.positive_keywords}")
                print(f"   ❌ Negative keywords: {sentiment_analysis.negative_keywords}")
                print(f"   📝 Summary: {sentiment_analysis.summary}")
                
                # Check if suitable for long
                is_suitable = checker.sentiment_analyzer.is_suitable_for_long(sentiment_analysis)
                print(f"   📈 Suitable for LONG: {is_suitable}")
            else:
                print(f"   ⚠️ No sentiment analysis performed")
            
            print(f"   💬 Overall summary: {result.get('summary', 'No summary')}")
            print()

if __name__ == "__main__":
    asyncio.run(debug_sentiment())