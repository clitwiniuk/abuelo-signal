# scanner/debug_yahooquery.py
"""
Debug script to understand yahooquery data structure
"""

from yahooquery import Ticker
import json

def debug_ticker_data(symbol):
    """Debug what data yahooquery returns"""
    print(f"\n🔍 Debugging {symbol}")
    print("=" * 40)
    
    try:
        ticker = Ticker(symbol)
        
        # Test different data endpoints
        print("📊 Available methods:")
        methods = ['summary_detail', 'key_stats', 'financial_data', 'default_key_statistics']
        
        for method in methods:
            try:
                data = getattr(ticker, method)
                print(f"\n✅ {method}:")
                if isinstance(data, dict) and symbol in data:
                    ticker_data = data[symbol]
                    if isinstance(ticker_data, dict):
                        # Look for float-related fields
                        float_fields = [k for k in ticker_data.keys() if 'float' in k.lower() or 'share' in k.lower()]
                        if float_fields:
                            print(f"   Float fields found: {float_fields}")
                            for field in float_fields:
                                print(f"   {field}: {ticker_data[field]}")
                        else:
                            print("   No float fields found")
                            print(f"   Available fields: {list(ticker_data.keys())[:10]}...")  # First 10 fields
                    else:
                        print(f"   Data type: {type(ticker_data)}")
                else:
                    print(f"   Data structure: {type(data)}")
                    if hasattr(data, 'keys'):
                        print(f"   Keys: {list(data.keys())}")
                        
            except Exception as e:
                print(f"❌ {method}: {e}")
        
        # Test news
        print(f"\n📰 News data:")
        try:
            news = ticker.news()
            if symbol in news:
                news_data = news[symbol]
                print(f"   News articles: {len(news_data) if isinstance(news_data, list) else 'N/A'}")
                if isinstance(news_data, list) and news_data:
                    first_article = news_data[0]
                    print(f"   First article title: {first_article.get('title', 'N/A')}")
            else:
                print(f"   No news data for {symbol}")
        except Exception as e:
            print(f"❌ News error: {e}")
            
    except Exception as e:
        print(f"❌ General error for {symbol}: {e}")

def main():
    """Test multiple tickers"""
    test_symbols = ["AAPL", "TSLA", "GEVO"]
    
    print("🧪 Yahooquery Debug Session")
    print("=" * 60)
    
    for symbol in test_symbols:
        debug_ticker_data(symbol)
    
    print("\n" + "=" * 60)
    print("🔍 Summary: Look for the method that contains float data")

if __name__ == "__main__":
    main()