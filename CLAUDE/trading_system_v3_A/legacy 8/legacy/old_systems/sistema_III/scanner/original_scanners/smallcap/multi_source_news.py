# scanner/smallcap/multi_source_news.py
"""
Multiple news sources for catalyst detection - Optimized for SmallcapDailyScanner:
1. Finviz - Primary source (best quality, real-time data)
2. YahooQuery API - Secondary source (already integrated)
3. NewsAPI - Professional news API (optional, requires key)
4. SEC EDGAR - Official SEC filings (for major catalysts)

Priority: Finviz -> YahooQuery -> NewsAPI -> SEC
Both primary sources are scanned for comprehensive coverage
"""

import asyncio
import aiohttp
import requests
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import time
try:
    from urllib3.exceptions import RemoteDisconnected
except ImportError:
    try:
        from http.client import RemoteDisconnected
    except ImportError:
        # Fallback for when RemoteDisconnected is not available
        class RemoteDisconnected(Exception):
            pass

from requests.exceptions import ConnectionError, Timeout

# Telegram integration
try:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from notifications.telegram_client import send_message as send_telegram_message, is_enabled as telegram_enabled
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    def send_telegram_message(text: str, **kwargs):
        pass
    def telegram_enabled():
        return False

# Primary sources
from yahooquery import Ticker  # Already in use

# Finviz (primary source)
try:
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    FINVIZ_AVAILABLE = False

# News API (optional professional source)
try:
    from newsapi.newsapi_client import NewsApiClient
    NEWSAPI_AVAILABLE = True
except ImportError:
    try:
        from newsapi import NewsApiClient
        NEWSAPI_AVAILABLE = True
    except ImportError:
        NEWSAPI_AVAILABLE = False
        NewsApiClient = None

# SEC EDGAR (for major filings)
try:
    from sec_edgar_downloader import Downloader
    SEC_AVAILABLE = True
except ImportError:
    SEC_AVAILABLE = False

logger = logging.getLogger(f"{__name__}.MultiSourceNewsChecker")

@dataclass
class NewsSourceConfig:
    """Configuration for multi-source news fetching"""
    # NewsAPI configuration (optional - get free key at newsapi.org)
    newsapi_key: Optional[str] = None
    
    # SEC EDGAR configuration (required if using SEC)
    sec_company_name: str = "SmallcapScanner"
    sec_email: str = "scanner@trading.com"
    
    # Search timeframe
    days_back: int = 7
    max_headlines_per_source: int = 5
    
    # Priority order for sources
    primary_sources: List[str] = None
    
    def __post_init__(self):
        if self.primary_sources is None:
            self.primary_sources = ['finviz', 'yahoo', 'newsapi', 'sec']
        
        if not self.newsapi_key and NEWSAPI_AVAILABLE:
            logger.info("NewsAPI key not provided - using free tier limitations")

class MultiSourceNewsChecker:
    """
    Enhanced news checker with multiple sources optimized for smallcap catalyst detection
    
    Uses priority-based source checking:
    1. Finviz (primary) - Best quality financial news
    2. YahooQuery (secondary) - Reliable fallback, already integrated
    3. NewsAPI (optional) - Professional news aggregation
    4. SEC EDGAR (specialized) - Official filings for major catalysts
    """
    
    def __init__(self, config: NewsSourceConfig = None, catalyst_keywords: Set[str] = None):
        self.config = config or NewsSourceConfig()
        self.catalyst_keywords = catalyst_keywords or self._get_default_catalyst_keywords()
        
        # Initialize clients
        self._init_clients()
        
        # Cache for avoiding duplicate API calls
        self._news_cache = {}
        
        # Rate limiting for Finviz
        self._last_finviz_call = 0
        self._finviz_rate_limit = 1.0  # 1 second between calls
        
        logger.info(f"MultiSourceNewsChecker initialized with sources: {self._get_available_sources()}")
    
    def _get_default_catalyst_keywords(self) -> Set[str]:
        """Default catalyst keywords for smallcap trading"""
        return {
            # FDA/Biotech catalysts
            'fda', 'fda approval', 'clinical trial', 'phase i', 'phase ii', 'phase iii',
            'breakthrough therapy', 'orphan drug', 'fast track', 'priority review',
            'biologics', 'drug approval', 'regulatory approval', 'medical device',
            
            # M&A catalysts
            'acquisition', 'merger', 'buyout', 'takeover', 'acquired by', 'agrees to acquire',
            'purchase agreement', 'definitive agreement', 'cash offer', 'tender offer',
            
            # Earnings catalysts  
            'earnings', 'quarterly results', 'revenue beat', 'earnings beat',
            'guidance raised', 'guidance increased', 'outlook', 'record revenue',
            
            # Contract catalysts
            'contract', 'agreement', 'deal', 'awarded', 'selected', 'partnership',
            'collaboration', 'license agreement', 'government contract', 'wins contract',
            
            # Breakthrough catalysts
            'breakthrough', 'innovation', 'patent', 'patent approval', 'revolutionary',
            'game changing', 'first of its kind', 'proprietary', 'exclusive'
        }
    
    def _init_clients(self):
        """Initialize news source clients"""
        # NewsAPI client
        self.newsapi_client = None
        if self.config.newsapi_key and NEWSAPI_AVAILABLE:
            try:
                self.newsapi_client = NewsApiClient(api_key=self.config.newsapi_key)
                logger.info("✅ NewsAPI client initialized")
            except Exception as e:
                logger.warning(f"NewsAPI initialization failed: {e}")
        
        # SEC EDGAR downloader
        self.sec_downloader = None
        if SEC_AVAILABLE:
            try:
                self.sec_downloader = Downloader(
                    company_name=self.config.sec_company_name,
                    email_address=self.config.sec_email
                )
                logger.info("✅ SEC EDGAR client initialized")
            except Exception as e:
                logger.warning(f"SEC EDGAR initialization failed: {e}")
    
    def _get_available_sources(self) -> List[str]:
        """Get list of available news sources"""
        sources = []
        if FINVIZ_AVAILABLE:
            sources.append('finviz')
        sources.append('yahoo')  # Always available (YahooQuery)
        if self.newsapi_client:
            sources.append('newsapi')
        if self.sec_downloader:
            sources.append('sec')
        return sources
    
    async def get_news_for_symbols(self, symbols: List[str]) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get news from multiple sources for catalyst analysis
        
        Returns format compatible with SmallcapDailyScanner:
        {
            'SYMBOL': [(headline, age_hours), ...]
        }
        """
        news_results = {}
        
        for symbol in symbols:
            symbol_headlines = []
            
            # Get news from each available source
            source_results = await self._check_all_sources_for_symbol(symbol)
            
            # Combine headlines from all sources, prioritizing by source quality
            for source_name in self.config.primary_sources:
                if source_name in source_results and source_results[source_name].get('headlines'):
                    headlines = source_results[source_name]['headlines']
                    symbol_headlines.extend(headlines)
            
            # Remove duplicates while preserving order
            seen_headlines = set()
            unique_headlines = []
            for headline, age_hours in symbol_headlines:
                headline_lower = headline.lower()
                if headline_lower not in seen_headlines:
                    seen_headlines.add(headline_lower)
                    unique_headlines.append((headline, age_hours))
            
            # Limit to max headlines and sort by age (newest first)
            unique_headlines.sort(key=lambda x: x[1])  # Sort by age
            news_results[symbol] = unique_headlines[:self.config.max_headlines_per_source * 2]  # Allow more since we have multiple sources
            
            # General rate limiting between symbols
            await asyncio.sleep(0.1)
        
        return news_results
    
    async def _check_all_sources_for_symbol(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        """Check all available sources for a single symbol"""
        source_results = {}
        
        # Check sources with proper error handling and fallback
        tasks = []
        
        # Finviz first (primary source with enhanced error handling)
        if FINVIZ_AVAILABLE:
            tasks.append(('finviz', self._check_finviz(symbol)))
        
        # Other sources in parallel
        tasks.append(('yahoo', self._check_yahoo(symbol)))
        
        if self.newsapi_client:
            tasks.append(('newsapi', self._check_newsapi(symbol)))
        
        if self.sec_downloader:
            tasks.append(('sec', self._check_sec_edgar(symbol)))
        
        # Execute all tasks concurrently with graceful error handling and timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=15.0  # 15 second timeout for all news sources
            )
        except asyncio.TimeoutError:
            logger.warning(f"News sources timeout for {symbol} - using fallback sources")
            # Create timeout results for all sources
            results = [{'headlines': [], 'error': 'Timeout'} for _ in tasks]
        
        # Process results with enhanced logging
        successful_sources = []
        failed_sources = []
        
        for i, (source_name, _) in enumerate(tasks):
            try:
                if isinstance(results[i], Exception):
                    error_msg = str(results[i])
                    logger.warning(f"{source_name.title()} connection error for {symbol}: {error_msg}")
                    source_results[source_name] = {'headlines': [], 'error': error_msg}
                    failed_sources.append(source_name)
                else:
                    result = results[i]
                    source_results[source_name] = result
                    if result.get('headlines'):
                        successful_sources.append(f"{source_name}({len(result['headlines'])})")
                    else:
                        failed_sources.append(source_name)
            except Exception as e:
                error_msg = f"Processing error: {str(e)}"
                logger.warning(f"Error processing {source_name} result for {symbol}: {error_msg}")
                source_results[source_name] = {'headlines': [], 'error': error_msg}
                failed_sources.append(source_name)
        
        # Log summary for graceful degradation visibility
        if successful_sources:
            logger.info(f"News sources successful for {symbol}: {', '.join(successful_sources)}")
        if failed_sources:
            logger.info(f"News sources failed for {symbol}: {', '.join(failed_sources)} - using fallback sources")
            
            # Send Telegram alert for source fallback (only if Finviz failed and others succeeded)
            if TELEGRAM_AVAILABLE and telegram_enabled() and 'finviz' in failed_sources and successful_sources:
                telegram_alert = f"🔄 **NEWS SOURCE FALLBACK**\n\n📊 Symbol: {symbol}\n❌ Failed: {', '.join(failed_sources)}\n✅ Working: {', '.join(successful_sources)}\n\n💡 Scanner continuing with backup sources"
                try:
                    send_telegram_message(telegram_alert, parse_mode="Markdown")
                except:
                    pass
        
        return source_results
    
    async def _check_finviz(self, symbol: str) -> Dict[str, Any]:
        """Check Finviz for recent news (primary source) with timeout protection and error handling"""
        if not FINVIZ_AVAILABLE:
            return {'headlines': [], 'error': 'finvizfinance not available'}
        
        # Rate limiting: ensure 1 second between Finviz calls
        current_time = time.time()
        time_since_last_call = current_time - self._last_finviz_call
        if time_since_last_call < self._finviz_rate_limit:
            sleep_time = self._finviz_rate_limit - time_since_last_call
            await asyncio.sleep(sleep_time)
        
        self._last_finviz_call = time.time()
        
        try:
            # Timeout protection: maximum 10 seconds per Finviz call
            timeout_task = asyncio.create_task(asyncio.sleep(10))
            finviz_task = asyncio.create_task(self._fetch_finviz_news(symbol))
            
            done, pending = await asyncio.wait(
                [finviz_task, timeout_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel the remaining task
            for task in pending:
                task.cancel()
            
            if finviz_task in done:
                return finviz_task.result()
            else:
                logger.warning(f"Finviz timeout for {symbol}: Operation took longer than 10 seconds")
                return {
                    'headlines': [], 
                    'error': 'Timeout after 10 seconds',
                    'source': 'Finviz'
                }
                
        except (RemoteDisconnected, ConnectionError) as e:
            error_msg = f"Finviz connection error for {symbol}: Connection error..."
            logger.warning(error_msg)
            
            # Send Telegram alert for connection errors
            if TELEGRAM_AVAILABLE and telegram_enabled():
                telegram_alert = f"⚠️ **FINVIZ CONNECTION ERROR**\n\n📊 Symbol: {symbol}\n❌ Error: Connection error\n🔄 Fallback: Using Yahoo/NewsAPI"
                try:
                    send_telegram_message(telegram_alert, parse_mode="Markdown")
                except:
                    pass  # Don't let Telegram errors break the main flow
                    
            return {
                'headlines': [], 
                'error': f'Connection error: {str(e)}',
                'source': 'Finviz'
            }
        except Timeout as e:
            error_msg = f"Finviz timeout error for {symbol}: Request timeout..."
            logger.warning(error_msg)
            
            # Send Telegram alert for timeout
            if TELEGRAM_AVAILABLE and telegram_enabled():
                telegram_alert = f"⚠️ **FINVIZ TIMEOUT**\n\n📊 Symbol: {symbol}\n⏱️ Error: Request timeout (>10s)\n🔄 Fallback: Using Yahoo/NewsAPI"
                try:
                    send_telegram_message(telegram_alert, parse_mode="Markdown")
                except:
                    pass
                    
            return {
                'headlines': [], 
                'error': f'Request timeout: {str(e)}',
                'source': 'Finviz'
            }
        except Exception as e:
            error_msg = f"Finviz unexpected error for {symbol}: {type(e).__name__}..."
            logger.warning(error_msg)
            
            # Send Telegram alert for unexpected errors
            if TELEGRAM_AVAILABLE and telegram_enabled():
                telegram_alert = f"🚨 **FINVIZ ERROR**\n\n📊 Symbol: {symbol}\n❌ Error: {type(e).__name__}\n🔄 Fallback: Using Yahoo/NewsAPI"
                try:
                    send_telegram_message(telegram_alert, parse_mode="Markdown")
                except:
                    pass
                    
            return {
                'headlines': [], 
                'error': f'{type(e).__name__}: {str(e)}',
                'source': 'Finviz'
            }
    
    async def _fetch_finviz_news(self, symbol: str) -> Dict[str, Any]:
        """Fetch news from Finviz (separated for timeout handling)"""
        def sync_fetch():
            stock = finvizfinance(symbol)
            return stock.ticker_news()
        
        # Run the synchronous Finviz call in a thread pool
        loop = asyncio.get_event_loop()
        news_data = await loop.run_in_executor(None, sync_fetch)
        
        headlines = []
        current_time = datetime.now()
        
        if news_data is not None and hasattr(news_data, 'empty') and not news_data.empty:
            # Finviz DataFrame format: ['Date', 'Title', 'Link', 'Source']
            for index, row in news_data.head(self.config.max_headlines_per_source).iterrows():
                try:
                    if 'Title' in row:
                        title = str(row['Title'])
                        
                        # Simplified age calculation - focus on getting TODAY's news
                        age_hours = self._get_simple_finviz_age(row.get('Date', ''))
                        
                        # Only include recent news (last 16 hours = today)
                        if age_hours <= 16.0:
                            headlines.append((title, age_hours))
                
                except Exception as e:
                    logger.debug(f"Error processing Finviz row for {symbol}: {e}")
                    continue
        
        return {
            'headlines': headlines,
            'source': 'Finviz',
            'articles_found': len(headlines)
        }
    
    def _get_simple_finviz_age(self, date_str: str) -> float:
        """Parse Finviz date format - REAL format is 'YYYY-MM-DD HH:MM:SS'"""
        if not date_str:
            return 24.0  # No date = old
            
        date_str = str(date_str).strip()
        
        try:
            from datetime import datetime
            
            # Pattern: '2025-08-20 10:30:00' (actual Finviz format)
            if len(date_str) >= 10 and '-' in date_str:
                # Extract date part
                date_part = date_str[:10]  # '2025-08-20'
                today = datetime.now().strftime('%Y-%m-%d')
                
                if date_part == today:
                    # It's today's news - calculate age from time
                    try:
                        news_datetime = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
                        current_datetime = datetime.now()
                        age_hours = (current_datetime - news_datetime).total_seconds() / 3600
                        return max(0.1, min(age_hours, 12.0))  # 0.1h to 12h
                    except:
                        return 2.0  # Today but can't parse time
                else:
                    # Not today = old news
                    return 24.0
            
            # Legacy patterns for backward compatibility
            import re
            
            # Pattern: "Today 10:30AM" 
            if date_str.lower().startswith('today'):
                time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', date_str.lower())
                if time_match:
                    return self._calculate_hours_from_time(time_match)
                return 2.0  # Today without specific time
            
            # Pattern: "08:00AM" (just time = today)
            time_only_match = re.match(r'^(\d{1,2}):(\d{2})\s*(am|pm)\s*$', date_str.lower())
            if time_only_match:
                return self._calculate_hours_from_time(time_only_match)
            
        except Exception as e:
            logger.debug(f"Error parsing date '{date_str}': {e}")
        
        # Everything else is old
        return 24.0
    
    def _calculate_hours_from_time(self, time_match) -> float:
        """Calculate hours ago from time match"""
        try:
            hour = int(time_match.group(1))
            am_pm = time_match.group(3)
            
            # Convert to 24h format
            if am_pm == 'pm' and hour != 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0
            
            from datetime import timezone, timedelta
            est_timezone = timezone(timedelta(hours=-5))
            current_hour = datetime.now(est_timezone).hour
            
            if current_hour >= hour:
                age_hours = current_hour - hour
            else:
                # Handle overnight case (rare but possible)
                age_hours = current_hour + 24 - hour
            
            return max(0.5, min(age_hours, 12.0))  # 0.5h to 12h max
            
        except:
            return 2.0  # Fallback for parsing errors

    async def _fetch_yahoo_news(self, symbol: str):
        """Fetch news from Yahoo API - separated for timeout handling"""
        ticker_obj = Ticker(symbol)
        return ticker_obj.news()

    async def _check_yahoo(self, symbol: str) -> Dict[str, Any]:
        """Check YahooQuery for news (secondary source) with timeout protection"""
        try:
            # Add timeout protection for Yahoo API calls
            yahoo_task = asyncio.create_task(self._fetch_yahoo_news(symbol))
            try:
                news_data = await asyncio.wait_for(yahoo_task, timeout=8.0)  # 8 second timeout
            except asyncio.TimeoutError:
                logger.warning(f"Yahoo news timeout for {symbol}")
                return {'headlines': [], 'error': 'Yahoo timeout', 'source': 'Yahoo Finance'}
            
            headlines = []
            current_time = datetime.now()
            
            if isinstance(news_data, dict) and symbol in news_data:
                ticker_news = news_data[symbol]
                
                if isinstance(ticker_news, list) and ticker_news:
                    for article in ticker_news[:self.config.max_headlines_per_source]:
                        try:
                            title = article.get('title', '')
                            pub_time = datetime.fromtimestamp(article.get('providerPublishTime', 0))
                            age_hours = (current_time - pub_time).total_seconds() / 3600
                            
                            headlines.append((title, age_hours))
                            
                        except Exception as e:
                            logger.debug(f"Error processing Yahoo article for {symbol}: {e}")
                            continue
            
            return {
                'headlines': headlines,
                'source': 'Yahoo Finance',
                'articles_found': len(headlines)
            }
            
        except Exception as e:
            logger.warning(f"Yahoo Finance error for {symbol}: {e}")
            return {'headlines': [], 'error': str(e)}
    
    async def _check_newsapi(self, symbol: str) -> Dict[str, Any]:
        """Check NewsAPI for catalyst keywords (optional professional source)"""
        if not self.newsapi_client:
            return {'headlines': [], 'error': 'NewsAPI not available'}
        
        try:
            # Search for ticker + catalyst keywords
            search_query = f"{symbol} AND ({' OR '.join(list(self.catalyst_keywords)[:10])})"
            
            from_date = datetime.now() - timedelta(days=self.config.days_back)
            
            articles = self.newsapi_client.get_everything(
                q=search_query,
                language='en',
                sort_by='publishedAt',
                from_param=from_date.strftime('%Y-%m-%d'),
                page_size=self.config.max_headlines_per_source,
                sources='bloomberg,reuters,cnbc,marketwatch,the-wall-street-journal'
            )
            
            headlines = []
            current_time = datetime.now()
            
            if articles.get('status') == 'ok' and articles.get('articles'):
                for article in articles['articles']:
                    try:
                        title = article.get('title', '')
                        pub_time = datetime.fromisoformat(article.get('publishedAt', '').replace('Z', '+00:00'))
                        age_hours = (current_time - pub_time).total_seconds() / 3600
                        
                        headlines.append((title, age_hours))
                        
                    except Exception as e:
                        logger.debug(f"Error processing NewsAPI article for {symbol}: {e}")
                        continue
            
            return {
                'headlines': headlines,
                'source': 'NewsAPI',
                'articles_found': len(headlines)
            }
            
        except Exception as e:
            logger.warning(f"NewsAPI error for {symbol}: {e}")
            return {'headlines': [], 'error': str(e)}
    
    async def _check_sec_edgar(self, symbol: str) -> Dict[str, Any]:
        """Check SEC EDGAR for recent filings (specialized for major catalysts)"""
        if not self.sec_downloader:
            return {'headlines': [], 'error': 'SEC EDGAR not available'}
        
        # For now, return placeholder - SEC implementation would be complex
        # and might be too slow for real-time scanning
        return {
            'headlines': [],
            'source': 'SEC EDGAR',
            'note': 'SEC filing analysis not implemented for real-time use'
        }

# Convenience functions for easy integration

async def get_multi_source_news(symbols: List[str], config: NewsSourceConfig = None) -> Dict[str, List[Tuple[str, float]]]:
    """
    Convenience function to get news from multiple sources
    
    Args:
        symbols: List of ticker symbols
        config: Optional configuration
    
    Returns:
        Dictionary compatible with SmallcapDailyScanner format
    """
    checker = MultiSourceNewsChecker(config)
    return await checker.get_news_for_symbols(symbols)

def create_news_config(newsapi_key: str = None, max_headlines: int = 5) -> NewsSourceConfig:
    """Create a news configuration with common settings"""
    return NewsSourceConfig(
        newsapi_key=newsapi_key,
        max_headlines_per_source=max_headlines,
        days_back=7
    )

# Test function
async def test_multi_source_news():
    """Test the multi-source news system"""
    config = NewsSourceConfig(max_headlines_per_source=3)
    checker = MultiSourceNewsChecker(config)
    
    test_symbols = ['AAPL', 'TSLA']
    
    print(f"🧪 Testing Multi-Source News System")
    print(f"Available sources: {checker._get_available_sources()}")
    print("=" * 50)
    
    results = await checker.get_news_for_symbols(test_symbols)
    
    for symbol, headlines in results.items():
        print(f"\n📰 {symbol} ({len(headlines)} headlines):")
        for i, (headline, age_hours) in enumerate(headlines, 1):
            print(f"  {i}. {headline[:80]}... (Age: {age_hours:.1f}h)")

if __name__ == "__main__":
    asyncio.run(test_multi_source_news())