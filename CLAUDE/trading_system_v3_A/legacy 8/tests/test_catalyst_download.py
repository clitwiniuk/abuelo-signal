#!/usr/bin/env python3
"""
Test script to verify ProactiveScanner catalyst download functionality
Tests the intelligent catalyst age logic with real news data
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scanner.smallcap.multi_source_news import MultiSourceNewsChecker, NewsSourceConfig
from datetime import datetime, timedelta
import configparser

async def test_catalyst_download():
    """Test catalyst download and age filtering"""

    print("=" * 80)
    print("ProactiveScanner Catalyst Download Test")
    print("=" * 80)

    # Load config
    config = configparser.ConfigParser()
    config.read('../config.ini')

    # Get catalyst age settings
    catalyst_max_age_weekday = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_weekday', fallback=30)
    catalyst_max_age_monday = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_monday', fallback=84)
    catalyst_max_age_fda = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_fda', fallback=168)
    catalyst_max_age_earnings = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_earnings', fallback=72)

    print(f"\n📋 Catalyst Age Configuration:")
    print(f"   Weekday (Tue-Fri): {catalyst_max_age_weekday}h")
    print(f"   Monday: {catalyst_max_age_monday}h")
    print(f"   FDA: {catalyst_max_age_fda}h")
    print(f"   Earnings: {catalyst_max_age_earnings}h")

    # Determine current day logic
    now = datetime.now()
    weekday = now.weekday()
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    base_age = catalyst_max_age_monday if weekday == 0 else catalyst_max_age_weekday

    print(f"\n📅 Today is: {weekday_names[weekday]}")
    print(f"   Base catalyst age limit: {base_age}h ({base_age/24:.1f} days)")

    # Initialize news checker
    news_config = NewsSourceConfig(
        max_headlines_per_source=5,
        days_back=4
    )
    news_checker = MultiSourceNewsChecker(news_config)

    # Test symbols (including SIM_RUNNER from database)
    test_symbols = ['SIM_RUNNER', 'AAPL', 'TSLA', 'NVDA']

    print(f"\n🔍 Testing catalyst download for {len(test_symbols)} symbols:")
    print(f"   Symbols: {', '.join(test_symbols)}")

    # Download news
    print(f"\n📰 Downloading news from MultiSourceNewsChecker...")
    news_dict = await news_checker.get_news_for_symbols(test_symbols)

    print(f"\n✅ News download complete!")
    print(f"   Total symbols with news: {len(news_dict)}")

    # Analyze each symbol
    for symbol in test_symbols:
        print(f"\n{'='*80}")
        print(f"📊 Symbol: {symbol}")
        print(f"{'='*80}")

        if symbol not in news_dict or not news_dict[symbol]:
            print(f"   ❌ No news found")
            continue

        headlines = news_dict[symbol]
        print(f"   ✅ Found {len(headlines)} headline(s)")

        for i, (headline_text, news_timestamp) in enumerate(headlines[:3], 1):
            # Calculate news age
            if news_timestamp:
                news_dt = datetime.fromtimestamp(news_timestamp) if isinstance(news_timestamp, (int, float)) else news_timestamp
                news_age_hours = (datetime.now() - news_dt).total_seconds() / 3600
            else:
                news_age_hours = 0.0

            # Detect catalyst type
            headline_lower = headline_text.lower()
            if any(word in headline_lower for word in ['fda', 'approval', 'approved']):
                catalyst_type = 'FDA'
                max_age = max(base_age, catalyst_max_age_fda)
            elif any(word in headline_lower for word in ['earning', 'earnings', 'eps']):
                catalyst_type = 'EARNINGS'
                max_age = max(base_age, catalyst_max_age_earnings)
            elif any(word in headline_lower for word in ['merger', 'acquisition', 'm&a']):
                catalyst_type = 'M&A'
                max_age = max(base_age, 48)
            else:
                catalyst_type = 'OTHER'
                max_age = base_age

            # Determine if catalyst is valid
            is_valid = news_age_hours <= max_age

            # Format output
            status_icon = "✅" if is_valid else "⏰"
            status_text = "VALID" if is_valid else "TOO OLD"

            print(f"\n   {status_icon} Headline #{i}: {status_text}")
            print(f"      Type: {catalyst_type}")
            print(f"      Age: {news_age_hours:.1f}h ({news_age_hours/24:.1f} days)")
            print(f"      Max: {max_age:.1f}h ({max_age/24:.1f} days)")
            print(f"      Text: {headline_text[:80]}{'...' if len(headline_text) > 80 else ''}")

    print(f"\n{'='*80}")
    print("✅ Catalyst Download Test Complete!")
    print(f"{'='*80}")

    # Summary
    total_with_news = len([s for s in test_symbols if s in news_dict and news_dict[s]])
    print(f"\n📈 Summary:")
    print(f"   Symbols tested: {len(test_symbols)}")
    print(f"   Symbols with news: {total_with_news}")
    print(f"   Success rate: {total_with_news/len(test_symbols)*100:.0f}%")

if __name__ == '__main__':
    asyncio.run(test_catalyst_download())
