#!/usr/bin/env python3
"""
Test script específico para verificar la detección de noticias de PGEN
"""

import asyncio
import logging
from daily_plays_filter import FilterCriteria
from news_sources import MultiSourceNewsChecker, NewsSource

# Setup logging para ver todos los detalles
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_pgen_news():
    """Test específico para PGEN news detection"""
    
    print("🔍 Testing PGEN news detection...")
    print("=" * 60)
    
    # Configurar criterios con todas las palabras clave
    criteria = FilterCriteria()
    
    print(f"📰 Total catalyst keywords: {len(criteria.catalyst_keywords)}")
    print(f"📰 Positive keywords: {len(criteria.positive_catalysts)}")
    print(f"📰 Negative keywords: {len(criteria.negative_catalysts)}")
    
    # Verificar que las palabras clave relevantes están incluidas
    relevant_keywords = ['announces', 'fda approval', 'approved', 'approval']
    print(f"\n🎯 Checking for relevant keywords:")
    for keyword in relevant_keywords:
        is_present = keyword in criteria.catalyst_keywords
        status = "✅" if is_present else "❌"
        print(f"   {status} '{keyword}': {is_present}")
    
    # Configurar news checker
    config = NewsSource(days_back=7)  # Last 7 days
    checker = MultiSourceNewsChecker(config, criteria.catalyst_keywords)
    
    print(f"\n🔍 Testing news detection for PGEN...")
    print("-" * 40)
    
    # Test PGEN specifically
    ticker = "PGEN"
    
    try:
        # Check all sources for PGEN
        results = await checker.check_all_sources([ticker])
        
        if ticker in results:
            result = results[ticker]
            
            print(f"\n📊 RESULTS FOR {ticker}:")
            print(f"   Has catalyst: {result.get('has_catalyst', False)}")
            print(f"   Has positive catalyst: {result.get('has_positive_catalyst', False)}")
            print(f"   Keywords found: {result.get('keywords_found', [])}")
            print(f"   Summary: {result.get('summary', 'N/A')}")
            
            # Check each source
            sources = result.get('sources', {})
            for source_name, source_data in sources.items():
                print(f"\n   📰 {source_name.upper()}:")
                if 'error' in source_data:
                    print(f"      ❌ Error: {source_data['error']}")
                elif 'skipped' in source_data:
                    print(f"      ⏭️  Skipped: {source_data['skipped']}")
                else:
                    print(f"      Has catalyst: {source_data.get('has_catalyst', False)}")
                    print(f"      Articles found: {source_data.get('articles_found', 0)}")
                    print(f"      Relevant articles: {source_data.get('relevant_articles', 0)}")
                    print(f"      Keywords: {source_data.get('keywords', [])}")
                    if source_data.get('sample_text'):
                        sample = source_data['sample_text'][:200]
                        print(f"      Sample text: {sample}...")
            
            # Sentiment analysis
            sentiment = result.get('sentiment_analysis')
            if sentiment:
                print(f"\n   🎭 SENTIMENT ANALYSIS:")
                print(f"      Sentiment: {sentiment.sentiment.value}")
                print(f"      Confidence: {sentiment.confidence:.2f}")
                print(f"      Suitable for long: {checker.sentiment_analyzer.is_suitable_for_long(sentiment)}")
        else:
            print(f"❌ No results found for {ticker}")
            
    except Exception as e:
        print(f"❌ Error testing {ticker}: {e}")
        import traceback
        traceback.print_exc()

async def test_finviz_directly():
    """Test Finviz directly to see raw data"""
    print(f"\n🔬 DIRECT FINVIZ TEST FOR PGEN:")
    print("-" * 40)
    
    try:
        from finvizfinance.quote import finvizfinance
        
        stock = finvizfinance("PGEN")
        news_data = stock.ticker_news()
        
        if news_data is not None and hasattr(news_data, 'empty') and not news_data.empty:
            print(f"📰 Found {len(news_data)} articles from Finviz:")
            
            # Show first 5 articles with all details
            for i, (index, row) in enumerate(news_data.head(5).iterrows()):
                print(f"\n   Article {i+1}:")
                print(f"      Date: {row.get('Date', 'N/A')}")
                print(f"      Title: {row.get('Title', 'N/A')}")
                print(f"      Source: {row.get('Source', 'N/A')}")
                
                # Check if this specific article contains our keywords
                title = str(row.get('Title', '')).lower()
                found_keywords = []
                test_keywords = ['announces', 'fda', 'approval', 'approved']
                for keyword in test_keywords:
                    if keyword in title:
                        found_keywords.append(keyword)
                
                if found_keywords:
                    print(f"      🎯 KEYWORDS FOUND: {found_keywords}")
                else:
                    print(f"      ❌ No test keywords found")
        else:
            print("❌ No news data returned from Finviz")
            
    except Exception as e:
        print(f"❌ Error in direct Finviz test: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    await test_pgen_news()
    await test_finviz_directly()
    
    print(f"\n" + "=" * 60)
    print("🏁 Test completed!")

if __name__ == "__main__":
    asyncio.run(main())
