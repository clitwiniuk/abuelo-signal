# scanner/check_news_dates.py
"""
Check what date ranges each news source is using
"""

from datetime import datetime, timedelta
import asyncio
from news_sources import MultiSourceNewsChecker, NewsSource
from daily_plays_filter import FilterCriteria

try:
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    FINVIZ_AVAILABLE = False

async def check_news_dates():
    """Check what date ranges each news source covers"""
    print("📅 Checking News Date Ranges")
    print("=" * 50)
    
    # Current configuration
    config = NewsSource(days_back=7)  # Default: 7 days
    
    print(f"📊 Current Configuration:")
    print(f"   Days back: {config.days_back} days")
    print(f"   From date: {(datetime.now() - timedelta(days=config.days_back)).strftime('%Y-%m-%d')}")
    print(f"   To date: {datetime.now().strftime('%Y-%m-%d')} (today)")
    print()
    
    # Test each source individually
    test_ticker = "AAPL"  # Well-known stock
    
    print(f"🔍 Testing with {test_ticker} to check actual dates returned:")
    print()
    
    # 1. Finviz check
    if FINVIZ_AVAILABLE:
        print("📰 Finviz:")
        try:
            stock = finvizfinance(test_ticker)
            news_data = stock.ticker_news()
            
            if news_data is not None and not news_data.empty:
                print(f"   Articles found: {len(news_data)}")
                print(f"   Date range in data:")
                
                # Check first few articles for dates
                for i, row in news_data.head(5).iterrows():
                    date = row['Date'] if 'Date' in row else 'No date'
                    title = row['Title'][:50] if 'Title' in row else 'No title'
                    print(f"      {date}: {title}...")
                    
                # Check if dates are recent
                if 'Date' in news_data.columns:
                    latest_date = news_data['Date'].max()
                    oldest_date = news_data['Date'].min()
                    print(f"   Latest news: {latest_date}")
                    print(f"   Oldest news: {oldest_date}")
                    
                    # Check how recent
                    today = datetime.now()
                    if hasattr(latest_date, 'date'):
                        days_old = (today.date() - latest_date.date()).days
                        print(f"   Latest news is {days_old} days old")
            else:
                print("   No news data available")
                
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("📰 Finviz: Not available (library not installed)")
    
    print()
    
    # 2. NewsAPI check (theoretical - since we don't have key)
    print("📰 NewsAPI:")
    print(f"   Configured range: Last {config.days_back} days")
    print(f"   From: {(datetime.now() - timedelta(days=config.days_back)).strftime('%Y-%m-%d')}")
    print(f"   To: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"   Status: {'Available' if config.newsapi_key else 'No API key configured'}")
    print()
    
    # 3. Yahoo Finance check
    print("📰 Yahoo Finance:")
    try:
        from yahooquery import Ticker
        ticker_obj = Ticker(test_ticker)
        news_data = ticker_obj.news()
        
        if test_ticker in news_data and isinstance(news_data[test_ticker], list):
            articles = news_data[test_ticker]
            print(f"   Articles found: {len(articles)}")
            
            if articles:
                print(f"   Sample dates:")
                for i, article in enumerate(articles[:5]):
                    if 'providerPublishTime' in article:
                        pub_time = datetime.fromtimestamp(article['providerPublishTime'])
                        title = article.get('title', 'No title')[:50]
                        print(f"      {pub_time.strftime('%Y-%m-%d %H:%M')}: {title}...")
                        
                        if i == 0:  # Check how recent the latest is
                            days_old = (datetime.now() - pub_time).days
                            print(f"   Latest news is {days_old} days old")
        else:
            print("   No news data available")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    print("=" * 50)
    print("📋 Summary:")
    print("• Finviz: Uses recent news (typically last few days to weeks)")
    print("• NewsAPI: Configurable (currently 7 days back)")
    print("• Yahoo Finance: Recent news (no specific date filter)")
    print("• SEC EDGAR: Recent filings (implementation needed)")
    print()
    print("💡 To change the date range, modify 'days_back' in NewsSource config")

if __name__ == "__main__":
    asyncio.run(check_news_dates())