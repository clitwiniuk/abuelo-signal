#!/usr/bin/env python3
"""
Test específico para diagnosticar el problema con PGEN noticias
"""

import asyncio
import logging
from finvizfinance.quote import finvizfinance
from news_sources import MultiSourceNewsChecker, NewsSource
from sentiment_analyzer import CatalystSentimentAnalyzer
import pandas as pd
from datetime import datetime, timedelta

# Setup logging para ver detalles
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_pgen_news():
    """Debug específico para PGEN"""
    
    ticker = "PGEN"
    print(f"🔍 DEBUGGING {ticker} news detection")
    print("=" * 60)
    
    # 1. Test Finviz directamente
    print("\n1️⃣ TESTING FINVIZ DIRECTLY")
    print("-" * 30)
    
    try:
        stock = finvizfinance(ticker)
        news_data = stock.ticker_news()
        
        if news_data is not None:
            if hasattr(news_data, 'empty'):  # pandas DataFrame
                print(f"✅ Found {len(news_data)} articles in Finviz")
                print("\n📰 First 5 articles:")
                
                for index, row in news_data.head().iterrows():
                    date = row.get('Date', 'No date')
                    title = row.get('Title', 'No title')
                    print(f"   [{date}] {title}")
                    
                    # Check specific PGEN news
                    title_lower = title.lower()
                    if any(word in title_lower for word in ['fda', 'approval', 'papzimeos', 'zopapogene', 'therapy']):
                        print(f"   🎯 CATALYST FOUND: {title}")
            else:
                print(f"❌ Unexpected data format: {type(news_data)}")
        else:
            print("❌ No news data returned from Finviz")
            
    except Exception as e:
        print(f"❌ Finviz error: {e}")
    
    # 2. Test con keywords específicas
    print("\n2️⃣ TESTING CATALYST KEYWORDS")
    print("-" * 30)
    
    catalyst_keywords = {
        'fda', 'approval', 'approved', 'breakthrough', 'therapy', 
        'treatment', 'clinical', 'papzimeos', 'zopapogene', 
        'respiratory', 'papillomatosis'
    }
    
    print(f"📋 Keywords to search: {catalyst_keywords}")
    
    # 3. Test MultiSourceNewsChecker
    print("\n3️⃣ TESTING MULTI-SOURCE CHECKER")
    print("-" * 30)
    
    config = NewsSource(days_back=1)  # Only today's news for intraday
    checker = MultiSourceNewsChecker(config, catalyst_keywords)
    
    results = await checker.check_all_sources([ticker])
    
    if ticker in results:
        result = results[ticker]
        print(f"✅ Has catalyst: {result['has_catalyst']}")
        print(f"✅ Has positive catalyst: {result.get('has_positive_catalyst', False)}")
        print(f"📝 Summary: {result['summary']}")
        print(f"🔑 Keywords found: {result['keywords_found']}")
        
        print("\n📊 Source breakdown:")
        for source_name, source_data in result['sources'].items():
            has_catalyst = source_data.get('has_catalyst', False)
            articles = source_data.get('articles_found', 0)
            relevant = source_data.get('relevant_articles', 0)
            error = source_data.get('error', '')
            
            status = "✅" if has_catalyst else "❌"
            print(f"   {status} {source_name}: {articles} articles, {relevant} relevant")
            if error:
                print(f"      ⚠️ Error: {error}")
        
        # Test sentiment analysis
        if result.get('sentiment_analysis'):
            sentiment = result['sentiment_analysis']
            print(f"\n🎭 Sentiment Analysis:")
            print(f"   Sentiment: {sentiment.sentiment.value}")
            print(f"   Confidence: {sentiment.confidence:.3f}")
            print(f"   Summary: {sentiment.summary}")
    else:
        print(f"❌ No results for {ticker}")
    
    # 4. Manual keyword search on specific news
    print("\n4️⃣ MANUAL SEARCH ON PGEN FDA NEWS")
    print("-" * 30)
    
    test_headline = "Precigen Announces Full FDA Approval of PAPZIMEOS (zopapogene imadenovec-drba), the First and Only Approved Therapy for the Treatment of Adults with Recurrent Respiratory Papillomatosis"
    
    print(f"Test headline: {test_headline}")
    
    found_keywords = []
    for keyword in catalyst_keywords:
        if keyword.lower() in test_headline.lower():
            found_keywords.append(keyword)
    
    print(f"🔍 Keywords found in test headline: {found_keywords}")
    
    # Test sentiment on this specific text
    sentiment_analyzer = CatalystSentimentAnalyzer()
    sentiment_result = sentiment_analyzer.analyze_text(test_headline, ticker)
    
    print(f"🎭 Sentiment of test headline:")
    print(f"   Sentiment: {sentiment_result.sentiment.value}")
    print(f"   Confidence: {sentiment_result.confidence:.3f}")
    print(f"   Is suitable for LONG: {sentiment_analyzer.is_suitable_for_long(sentiment_result)}")

if __name__ == "__main__":
    asyncio.run(debug_pgen_news())