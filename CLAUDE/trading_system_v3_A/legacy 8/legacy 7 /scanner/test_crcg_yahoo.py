#!/usr/bin/env python3
"""
Test if CRCG exists in Yahoo Finance
"""

import sys
from yahooquery import Ticker

def test_crcg_yahoo():
    """Test Yahoo Finance with CRCG"""
    symbol = 'CRCG'

    print(f"\n{'='*60}")
    print(f"Testing Yahoo Finance with symbol: {symbol}")
    print(f"{'='*60}\n")

    try:
        # Test basic quote
        print("Step 1: Testing quote data...")
        ticker = Ticker(symbol)
        quote = ticker.quotes

        if isinstance(quote, dict) and symbol in quote:
            data = quote[symbol]
            if 'symbol' in data:
                print(f"✅ Symbol found: {data.get('symbol')}")
                print(f"   Long Name: {data.get('longName', 'N/A')}")
                print(f"   Exchange: {data.get('exchange', 'N/A')}")
                print(f"   Quote Type: {data.get('quoteType', 'N/A')}")
                print(f"   Market: {data.get('market', 'N/A')}")
            else:
                print(f"⚠️  Quote returned but no symbol field")
                print(f"   Data: {data}")
        else:
            print(f"❌ Symbol not found or error")
            print(f"   Response: {quote}")

        # Test news
        print("\nStep 2: Testing news data...")
        news_data = ticker.news()

        if isinstance(news_data, dict) and symbol in news_data:
            ticker_news = news_data[symbol]
            if isinstance(ticker_news, list):
                print(f"✅ News found: {len(ticker_news)} articles")
                if ticker_news:
                    print(f"\n   Sample article:")
                    article = ticker_news[0]
                    print(f"   - Title: {article.get('title', 'N/A')}")
                    print(f"   - Publisher: {article.get('publisher', 'N/A')}")
                    print(f"   - Published: {article.get('providerPublishTime', 'N/A')}")
            else:
                print(f"⚠️  News returned but not a list: {type(ticker_news)}")
        else:
            print(f"❌ No news found")
            print(f"   Response: {news_data}")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crcg_yahoo()
