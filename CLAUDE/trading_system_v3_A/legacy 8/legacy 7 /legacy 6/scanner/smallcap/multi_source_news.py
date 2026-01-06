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

# Finnhub (free news source)
try:
    import finnhub
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False

# Polygon (free news source)
try:
    from polygon import RESTClient
    POLYGON_AVAILABLE = True
except ImportError:
    POLYGON_AVAILABLE = False

# SEC EDGAR (for major filings)
try:
    from sec_edgar_downloader import Downloader
    SEC_AVAILABLE = True
except ImportError:
    SEC_AVAILABLE = False

logger = logging.getLogger(f"{__name__}.MultiSourceNewsChecker")

class NewsCircuitBreaker:
    """
    Circuit Breaker pattern for unreliable news sources.

    Prevents cascading failures when a news source becomes unstable:
    - After N consecutive failures, "opens" the circuit (skips source)
    - After timeout period, attempts to "close" circuit (retry)
    - Tracks success/failure metrics for monitoring
    """

    def __init__(self, source_name: str, failure_threshold: int = 5, timeout_seconds: int = 300):
        """
        Args:
            source_name: Name of the news source (e.g., 'Finviz')
            failure_threshold: Number of consecutive failures before opening circuit
            timeout_seconds: How long to wait before attempting retry (default: 5 minutes)
        """
        self.source_name = source_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds

        # State tracking
        self.consecutive_failures = 0
        self.total_failures = 0
        self.total_successes = 0
        self.circuit_open_time = None
        self.is_open = False

        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker.{source_name}")

    def record_success(self):
        """Record a successful call - resets consecutive failures"""
        self.consecutive_failures = 0
        self.total_successes += 1

        # Close circuit if it was open
        if self.is_open:
            self.logger.info(f"✅ {self.source_name} Circuit CLOSED - Service recovered")
            self.is_open = False
            self.circuit_open_time = None

    def record_failure(self):
        """Record a failed call - may open circuit"""
        self.consecutive_failures += 1
        self.total_failures += 1

        # Open circuit if threshold exceeded
        if not self.is_open and self.consecutive_failures >= self.failure_threshold:
            self.is_open = True
            self.circuit_open_time = time.time()
            self.logger.warning(
                f"🔴 {self.source_name} Circuit OPENED - "
                f"{self.consecutive_failures} consecutive failures. "
                f"Will retry in {self.timeout_seconds}s"
            )

    def should_attempt_call(self) -> bool:
        """
        Check if we should attempt to call this source.

        Returns:
            True if call should proceed, False if circuit is open
        """
        if not self.is_open:
            return True

        # Check if timeout has elapsed
        time_since_open = time.time() - self.circuit_open_time
        if time_since_open >= self.timeout_seconds:
            self.logger.info(
                f"🔄 {self.source_name} Circuit half-open - attempting retry after {time_since_open:.0f}s"
            )
            # Half-open state: try one request
            # If it succeeds, record_success() will close circuit
            # If it fails, record_failure() will re-open circuit
            return True

        # Circuit still open
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        total_calls = self.total_successes + self.total_failures
        success_rate = (self.total_successes / total_calls * 100) if total_calls > 0 else 0

        return {
            'source': self.source_name,
            'is_open': self.is_open,
            'consecutive_failures': self.consecutive_failures,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'success_rate': f"{success_rate:.1f}%",
            'time_since_open': time.time() - self.circuit_open_time if self.circuit_open_time else None
        }

@dataclass
class NewsSourceConfig:
    """Configuration for multi-source news fetching"""
    # NewsAPI configuration (optional - get free key at newsapi.org)
    newsapi_key: Optional[str] = None

    # Finnhub configuration (free - get key at finnhub.io)
    finnhub_key: Optional[str] = None

    # Polygon configuration (free - get key at polygon.io)
    polygon_key: Optional[str] = None

    # SEC EDGAR configuration (required if using SEC)
    sec_company_name: str = "SmallcapScanner"
    sec_email: str = "scanner@trading.com"

    # Search timeframe
    days_back: int = 7
    max_headlines_per_source: int = 5

    # Priority order for sources (quality first)
    primary_sources: List[str] = None

    def __post_init__(self):
        if self.primary_sources is None:
            # Quality-first priority: Finviz -> Finnhub -> Yahoo -> Polygon -> NewsAPI -> SEC
            self.primary_sources = ['finviz', 'finnhub', 'yahoo', 'polygon', 'newsapi', 'sec']

        if not self.newsapi_key and NEWSAPI_AVAILABLE:
            logger.info("NewsAPI key not provided - using free tier limitations")
        if not self.finnhub_key and FINNHUB_AVAILABLE:
            logger.info("Finnhub key not provided - news functionality limited")
        if not self.polygon_key and POLYGON_AVAILABLE:
            logger.info("Polygon key not provided - news functionality limited")

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

        # Circuit Breakers for each news source
        self.circuit_breakers = {
            'finviz': NewsCircuitBreaker('Finviz', failure_threshold=5, timeout_seconds=300),
            'finnhub': NewsCircuitBreaker('Finnhub', failure_threshold=5, timeout_seconds=300),
            'yahoo': NewsCircuitBreaker('Yahoo', failure_threshold=5, timeout_seconds=300),
            'polygon': NewsCircuitBreaker('Polygon', failure_threshold=5, timeout_seconds=300),
            'newsapi': NewsCircuitBreaker('NewsAPI', failure_threshold=5, timeout_seconds=300),
        }

        logger.info(f"MultiSourceNewsChecker initialized with sources: {self._get_available_sources()}")
        logger.info("Circuit breakers enabled for all sources")
    
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

        # Finnhub client
        self.finnhub_client = None
        if self.config.finnhub_key and FINNHUB_AVAILABLE:
            try:
                self.finnhub_client = finnhub.Client(api_key=self.config.finnhub_key)
                logger.info("✅ Finnhub client initialized")
            except Exception as e:
                logger.warning(f"Finnhub initialization failed: {e}")

        # Polygon client
        self.polygon_client = None
        if self.config.polygon_key and POLYGON_AVAILABLE:
            try:
                self.polygon_client = RESTClient(api_key=self.config.polygon_key)
                logger.info("✅ Polygon client initialized")
            except Exception as e:
                logger.warning(f"Polygon initialization failed: {e}")

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
        if self.finnhub_client:
            sources.append('finnhub')
        sources.append('yahoo')  # Always available (YahooQuery)
        if self.polygon_client:
            sources.append('polygon')
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
        """Check all available sources for a single symbol with circuit breaker protection"""
        source_results = {}

        # Check sources with proper error handling and fallback
        tasks = []
        skipped_sources = []

        # Quality-first priority: Finviz -> Finnhub -> Yahoo -> Polygon -> NewsAPI -> SEC
        # Only add tasks if circuit breaker allows
        if FINVIZ_AVAILABLE:
            if self.circuit_breakers['finviz'].should_attempt_call():
                tasks.append(('finviz', self._check_finviz(symbol)))
            else:
                skipped_sources.append('finviz')
                source_results['finviz'] = {
                    'headlines': [],
                    'error': 'Circuit breaker OPEN - source temporarily disabled',
                    'circuit_open': True
                }

        if self.finnhub_client:
            if self.circuit_breakers['finnhub'].should_attempt_call():
                tasks.append(('finnhub', self._check_finnhub(symbol)))
            else:
                skipped_sources.append('finnhub')
                source_results['finnhub'] = {
                    'headlines': [],
                    'error': 'Circuit breaker OPEN',
                    'circuit_open': True
                }

        # Yahoo always runs (no circuit breaker for critical fallback)
        if self.circuit_breakers['yahoo'].should_attempt_call():
            tasks.append(('yahoo', self._check_yahoo(symbol)))
        else:
            # Yahoo is critical - log warning but still attempt
            self.logger.warning(f"Yahoo circuit open but attempting anyway (critical fallback)")
            tasks.append(('yahoo', self._check_yahoo(symbol)))

        if self.polygon_client:
            if self.circuit_breakers['polygon'].should_attempt_call():
                tasks.append(('polygon', self._check_polygon(symbol)))
            else:
                skipped_sources.append('polygon')
                source_results['polygon'] = {
                    'headlines': [],
                    'error': 'Circuit breaker OPEN',
                    'circuit_open': True
                }

        if self.newsapi_client:
            if self.circuit_breakers['newsapi'].should_attempt_call():
                tasks.append(('newsapi', self._check_newsapi(symbol)))
            else:
                skipped_sources.append('newsapi')
                source_results['newsapi'] = {
                    'headlines': [],
                    'error': 'Circuit breaker OPEN',
                    'circuit_open': True
                }

        if self.sec_downloader:
            tasks.append(('sec', self._check_sec_edgar(symbol)))

        # Log skipped sources
        if skipped_sources:
            self.logger.info(f"⚡ Circuit breakers OPEN for {symbol}: {', '.join(skipped_sources)}")

        # Execute all tasks concurrently with graceful error handling
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # Process results with enhanced logging and circuit breaker tracking
        successful_sources = []
        failed_sources = []

        for i, (source_name, _) in enumerate(tasks):
            try:
                if isinstance(results[i], Exception):
                    error_msg = str(results[i])
                    logger.warning(f"{source_name.title()} connection error for {symbol}: {error_msg}")
                    source_results[source_name] = {'headlines': [], 'error': error_msg}
                    failed_sources.append(source_name)

                    # Record failure in circuit breaker
                    if source_name in self.circuit_breakers:
                        self.circuit_breakers[source_name].record_failure()

                else:
                    result = results[i]
                    source_results[source_name] = result

                    # Check if result has headlines OR if it's an error response
                    has_error = result.get('error') is not None and result.get('error') != ''
                    has_headlines = bool(result.get('headlines'))

                    if has_headlines:
                        successful_sources.append(f"{source_name}({len(result['headlines'])})")

                        # Record success in circuit breaker
                        if source_name in self.circuit_breakers:
                            self.circuit_breakers[source_name].record_success()
                    else:
                        # No headlines (could be error or empty result)
                        if has_error:
                            failed_sources.append(source_name)

                            # Record failure in circuit breaker
                            if source_name in self.circuit_breakers:
                                self.circuit_breakers[source_name].record_failure()
                        else:
                            # Empty but not error - neutral (don't count as failure)
                            if source_name in self.circuit_breakers:
                                self.circuit_breakers[source_name].record_success()

            except Exception as e:
                error_msg = f"Processing error: {str(e)}"
                logger.warning(f"Error processing {source_name} result for {symbol}: {error_msg}")
                source_results[source_name] = {'headlines': [], 'error': error_msg}
                failed_sources.append(source_name)

                # Record failure in circuit breaker
                if source_name in self.circuit_breakers:
                    self.circuit_breakers[source_name].record_failure()
        
        # Log summary for graceful degradation visibility and update reliability metrics
        if successful_sources:
            logger.info(f"News sources successful for {symbol}: {', '.join(successful_sources)}")
        if failed_sources:
            logger.info(f"News sources failed for {symbol}: {', '.join(failed_sources)} - using fallback sources")

            # Update reliability metrics in parent scanner if available
            if hasattr(self, '_parent_scanner') and hasattr(self._parent_scanner, 'update_source_reliability'):
                for source in failed_sources:
                    self._parent_scanner.update_source_reliability(source, False)
                for source_info in successful_sources:
                    # Extract source name from "source(count)" format
                    source_name = source_info.split('(')[0]
                    self._parent_scanner.update_source_reliability(source_name, True)

            # Send Telegram alert for source fallback (only if Finviz failed and others succeeded)
            if TELEGRAM_AVAILABLE and telegram_enabled() and 'finviz' in failed_sources and successful_sources:
                telegram_alert = f"🔄 **NEWS SOURCE FALLBACK**\n\n📊 Symbol: {symbol}\n❌ Failed: {', '.join(failed_sources)}\n✅ Working: {', '.join(successful_sources)}\n\n💡 Scanner continuing with backup sources"
                try:
                    send_telegram_message(telegram_alert, parse_mode="Markdown")
                except:
                    pass
        
        return source_results

    def get_circuit_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all circuit breakers.

        Returns:
            Dictionary mapping source name to statistics
        """
        stats = {}
        for source_name, breaker in self.circuit_breakers.items():
            stats[source_name] = breaker.get_stats()
        return stats

    def print_circuit_breaker_report(self):
        """Print a formatted report of circuit breaker statistics"""
        stats = self.get_circuit_breaker_stats()

        logger.info("=" * 60)
        logger.info("CIRCUIT BREAKER STATUS REPORT")
        logger.info("=" * 60)

        for source, data in stats.items():
            status_emoji = "🔴" if data['is_open'] else "✅"
            logger.info(f"{status_emoji} {source.upper()}")
            logger.info(f"   Status: {'OPEN' if data['is_open'] else 'CLOSED'}")
            logger.info(f"   Success Rate: {data['success_rate']}")
            logger.info(f"   Total Calls: {data['total_successes'] + data['total_failures']}")
            logger.info(f"   Failures: {data['total_failures']} (consecutive: {data['consecutive_failures']})")

            if data['is_open'] and data['time_since_open']:
                logger.info(f"   Open for: {data['time_since_open']:.0f}s")

            logger.info("-" * 60)

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
            error_msg = f"Finviz unexpected error for {symbol}: {type(e).__name__}: {str(e)}"
            logger.warning(error_msg)

            # Send Telegram alert for unexpected errors with more detail
            if TELEGRAM_AVAILABLE and telegram_enabled():
                # Create more descriptive error message
                error_detail = str(e)[:80] if len(str(e)) > 80 else str(e)

                # Special message for common AttributeError
                if isinstance(e, AttributeError) and "'NoneType' object has no attribute" in str(e):
                    telegram_alert = f"⚠️ **FINVIZ SYMBOL NOT FOUND**\n\n📊 Symbol: {symbol}\n❌ Finviz page not available or invalid symbol\n🔄 Switching to: Yahoo Finance + NewsAPI\n\n💡 This is normal for OTC/unlisted stocks"
                else:
                    telegram_alert = f"🚨 **FINVIZ ERROR**\n\n📊 Symbol: {symbol}\n❌ Error: {type(e).__name__}\n📝 Detail: {error_detail}\n🔄 Fallback: Using Yahoo/NewsAPI"

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
            try:
                stock = finvizfinance(symbol)
                return stock.ticker_news()
            except AttributeError as e:
                # This usually means the HTML structure is different or symbol doesn't exist
                error_msg = str(e)
                if "'NoneType' object has no attribute" in error_msg:
                    logger.warning(f"Finviz HTML parsing failed for {symbol} - symbol may not exist or page structure changed")
                else:
                    logger.error(f"Finviz AttributeError for {symbol}: {error_msg}")
                # Return None to indicate failure instead of raising
                return None
            except Exception as e:
                logger.error(f"Finviz fetch error for {symbol}: {str(e)}")
                # Return None to indicate failure
                return None

        # Run the synchronous Finviz call in a thread pool
        loop = asyncio.get_event_loop()
        news_data = await loop.run_in_executor(None, sync_fetch)

        headlines = []
        current_time = datetime.now()

        # Enhanced validation for news_data with better error handling
        try:
            # Check if news_data is valid
            if news_data is None:
                logger.warning(f"Finviz returned None for {symbol}")
                return {
                    'headlines': [],
                    'source': 'Finviz',
                    'articles_found': 0,
                    'error': 'No data returned'
                }

            # Check if it's a DataFrame with data
            is_dataframe = hasattr(news_data, 'empty') and hasattr(news_data, 'iterrows')
            if not is_dataframe:
                logger.warning(f"Finviz returned unexpected data type for {symbol}: {type(news_data)}")
                return {
                    'headlines': [],
                    'source': 'Finviz',
                    'articles_found': 0,
                    'error': f'Unexpected data type: {type(news_data)}'
                }

            # Check if DataFrame is empty
            if news_data.empty:
                logger.debug(f"Finviz returned empty DataFrame for {symbol}")
                return {
                    'headlines': [],
                    'source': 'Finviz',
                    'articles_found': 0,
                    'error': 'Empty DataFrame'
                }

            # Process DataFrame rows
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

        except AttributeError as e:
            # Specific handling for AttributeError
            error_msg = f"AttributeError accessing Finviz data: {str(e)}"
            logger.error(f"{error_msg} for {symbol}")
            return {
                'headlines': [],
                'source': 'Finviz',
                'articles_found': 0,
                'error': error_msg
            }
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"Unexpected error processing Finviz data: {str(e)}"
            logger.error(f"{error_msg} for {symbol}")
            return {
                'headlines': [],
                'source': 'Finviz',
                'articles_found': 0,
                'error': error_msg
            }

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
    
    
    async def _check_yahoo(self, symbol: str) -> Dict[str, Any]:
        """Check YahooQuery for news (secondary source)"""
        try:
            ticker_obj = Ticker(symbol)
            news_data = ticker_obj.news()
            
            headlines = []
            current_time = datetime.now()
            
            if isinstance(news_data, dict) and symbol in news_data:
                ticker_news = news_data[symbol]
                
                if isinstance(ticker_news, list) and ticker_news:
                    for article in ticker_news[:self.config.max_headlines_per_source]:
                        try:
                            title = article.get('title', '')
                            pub_timestamp = article.get('providerPublishTime', None)

                            # Calculate age_hours, defaulting to very old if no timestamp or invalid timestamp
                            if pub_timestamp and pub_timestamp > 31536000:  # After 1971-01-01 (1 year from epoch)
                                pub_time = datetime.fromtimestamp(pub_timestamp)
                                age_hours = (current_time - pub_time).total_seconds() / 3600
                            else:
                                # No timestamp or invalid timestamp (too old/zero) - mark as very old
                                # 999999h = ~114 years, will be filtered out by age check
                                age_hours = 999999.0

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
        """Check NewsAPI for catalyst keywords (quinary source - requires paid key)"""
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
    
    async def _check_finnhub(self, symbol: str) -> Dict[str, Any]:
        """Check Finnhub for news (tertiary source - high quality, free tier)"""
        if not self.finnhub_client:
            return {'headlines': [], 'error': 'Finnhub client not available'}

        try:
            # Get company news from Finnhub (free tier: 60 calls/minute)
            from_date = (datetime.now() - timedelta(days=self.config.days_back)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')

            news_data = self.finnhub_client.company_news(symbol, _from=from_date, to=to_date)

            headlines = []
            current_time = datetime.now()

            if news_data and isinstance(news_data, list):
                for article in news_data[:self.config.max_headlines_per_source]:
                    try:
                        title = article.get('headline', '')
                        if not title:
                            continue

                        # Finnhub provides datetime directly
                        pub_timestamp = article.get('datetime', 0)
                        if pub_timestamp:
                            pub_time = datetime.fromtimestamp(pub_timestamp)
                            age_hours = (current_time - pub_time).total_seconds() / 3600
                        else:
                            age_hours = 24.0  # Default to old if no timestamp

                        # Only include recent news (last 16 hours for intraday)
                        if age_hours <= 16.0:
                            headlines.append((title, age_hours))

                    except Exception as e:
                        logger.debug(f"Error processing Finnhub article for {symbol}: {e}")
                        continue

            return {
                'headlines': headlines,
                'source': 'Finnhub',
                'articles_found': len(headlines)
            }

        except Exception as e:
            logger.warning(f"Finnhub error for {symbol}: {e}")
            return {'headlines': [], 'error': str(e)}

    async def _check_polygon(self, symbol: str) -> Dict[str, Any]:
        """Check Polygon for news (quaternary source - reliable, free tier)"""
        if not self.polygon_client:
            return {'headlines': [], 'error': 'Polygon client not available'}

        try:
            # Get ticker news from Polygon (free tier: 5 calls/minute)
            from polygon import RESTClient
            from_date = (datetime.now() - timedelta(days=self.config.days_back)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')

            # Use ticker_news endpoint for company-specific news
            news_data = []
            try:
                async for news in self.polygon_client.list_ticker_news(symbol, limit=self.config.max_headlines_per_source):
                    news_data.append(news)
            except:
                # Fallback to general news search
                pass

            headlines = []
            current_time = datetime.now()

            for article in news_data[:self.config.max_headlines_per_source]:
                try:
                    title = article.title if hasattr(article, 'title') else article.get('title', '')
                    if not title:
                        continue

                    # Polygon provides published_utc
                    pub_time_str = article.published_utc if hasattr(article, 'published_utc') else article.get('published_utc', '')
                    if pub_time_str:
                        try:
                            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                            age_hours = (current_time - pub_time).total_seconds() / 3600
                        except:
                            age_hours = 12.0  # Default to recent
                    else:
                        age_hours = 12.0

                    # Only include recent news (last 16 hours for intraday)
                    if age_hours <= 16.0:
                        headlines.append((title, age_hours))

                except Exception as e:
                    logger.debug(f"Error processing Polygon article for {symbol}: {e}")
                    continue

            return {
                'headlines': headlines,
                'source': 'Polygon',
                'articles_found': len(headlines)
            }

        except Exception as e:
            logger.warning(f"Polygon error for {symbol}: {e}")
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