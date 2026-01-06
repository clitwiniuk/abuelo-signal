# scanner/news_sources.py
"""
Multiple news sources for catalyst detection:
1. NewsAPI - Professional news API with keyword filtering
2. SEC EDGAR - Official SEC filings and forms
3. Yahoo Finance - Fallback source
"""

import asyncio
import aiohttp
import requests
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

# News API - correct import structure
try:
    from newsapi.newsapi_client import NewsApiClient
except ImportError:
    try:
        from newsapi import NewsApiClient
    except ImportError:
        # Fallback - NewsAPI not available
        NewsApiClient = None
        logger.warning("NewsAPI library not available")

# SEC EDGAR
from sec_edgar_downloader import Downloader

# Yahoo (fallback)
from yahooquery import Ticker

# Finviz (primary source)
try:
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    FINVIZ_AVAILABLE = False
    logger.warning("finvizfinance library not available - install with: pip install finvizfinance")

# Sentiment analysis
from sentiment_analyzer import CatalystSentimentAnalyzer, SentimentType

logger = logging.getLogger(__name__)

@dataclass
class NewsSource:
    """Configuration for news sources"""
    # NewsAPI configuration (get free key at newsapi.org)
    newsapi_key: Optional[str] = None  # Set your API key here
    
    # SEC EDGAR configuration
    sec_company_name: str = "Daily Plays Scanner"  # Required by SEC
    sec_email: str = "user@example.com"  # Required by SEC
    
    # Search timeframe
    days_back: int = 7
    
    def __post_init__(self):
        if not self.newsapi_key:
            logger.warning("NewsAPI key not provided - using free tier limitations")

class MultiSourceNewsChecker:
    """Enhanced news checker with multiple sources"""
    
    def __init__(self, config: NewsSource = None, catalyst_keywords: Set[str] = None):
        self.config = config or NewsSource()
        self.catalyst_keywords = catalyst_keywords or set()
        
        # Initialize sentiment analyzer
        self.sentiment_analyzer = CatalystSentimentAnalyzer()
        
        # Initialize clients
        self.newsapi_client = None
        if self.config.newsapi_key and NewsApiClient is not None:
            try:
                self.newsapi_client = NewsApiClient(api_key=self.config.newsapi_key)
                logger.info("✅ NewsAPI initialized")
            except Exception as e:
                logger.warning(f"NewsAPI initialization failed: {e}")
        elif NewsApiClient is None:
            logger.warning("NewsAPI library not properly installed - using Yahoo + SEC only")
        
        # SEC EDGAR downloader
        try:
            self.sec_downloader = Downloader(
                company_name=self.config.sec_company_name,
                email_address=self.config.sec_email
            )
            logger.info("✅ SEC EDGAR initialized")
        except Exception as e:
            logger.warning(f"SEC EDGAR initialization failed: {e}")
            self.sec_downloader = None
    
    async def check_all_sources(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """Check all news sources for catalysts"""
        results = {}
        
        for ticker in tickers:
            logger.info(f"🔍 Checking news sources for {ticker}")
            
            # Initialize result structure
            ticker_result = {
                'has_catalyst': False,
                'has_positive_catalyst': False,  # NEW: For long strategies
                'sentiment_analysis': None,
                'sources': {},
                'keywords_found': [],
                'summary': 'No catalysts found'
            }
            
            # Check sources in priority order: Finviz -> SEC -> Yahoo -> NewsAPI
            sources_to_check = [
                ('finviz', self._check_finviz),
                ('sec_edgar', self._check_sec_edgar),
                ('yahoo', self._check_yahoo),
                ('newsapi', self._check_newsapi)
            ]
            
            # Priority-based checking: if any high-priority source finds news, skip remaining sources
            catalyst_found = False
            
            for source_name, check_func in sources_to_check:
                try:
                    # Skip remaining sources if a higher priority source already found catalysts
                    if catalyst_found:
                        ticker_result['sources'][source_name] = {'skipped': 'Higher priority source found catalysts'}
                        continue
                    
                    source_result = await check_func(ticker)
                    ticker_result['sources'][source_name] = source_result
                    
                    if source_result.get('has_catalyst', False):
                        ticker_result['has_catalyst'] = True
                        ticker_result['keywords_found'].extend(source_result.get('keywords', []))
                        
                        # Mark flag to skip remaining lower-priority sources
                        catalyst_found = True
                        logger.info(f"{ticker}: ✅ {source_name} found catalysts - skipping remaining sources")
                        
                except Exception as e:
                    logger.warning(f"Error checking {source_name} for {ticker}: {e}")
                    ticker_result['sources'][source_name] = {'error': str(e)}
            
            # Perform sentiment analysis if we found any catalysts
            if ticker_result['has_catalyst']:
                # Combine all text from sources for sentiment analysis
                combined_text = ""
                for source_name, source_data in ticker_result['sources'].items():
                    if source_data.get('sample_text'):
                        combined_text += " " + source_data['sample_text']
                
                if combined_text.strip():
                    sentiment_result = self.sentiment_analyzer.analyze_text(combined_text, ticker)
                    ticker_result['sentiment_analysis'] = sentiment_result
                    
                    # Check if suitable for LONG positions
                    ticker_result['has_positive_catalyst'] = self.sentiment_analyzer.is_suitable_for_long(sentiment_result)
                    
                    # Update summary with sentiment
                    sources_with_catalysts = [s for s, data in ticker_result['sources'].items() 
                                            if data.get('has_catalyst', False)]
                    sentiment_label = sentiment_result.sentiment.value.upper()
                    confidence = sentiment_result.confidence
                    
                    ticker_result['summary'] = f"{sentiment_label} catalysts (confidence: {confidence:.2f}) in {', '.join(sources_with_catalysts)}"
                else:
                    # Fallback without sentiment analysis
                    sources_with_catalysts = [s for s, data in ticker_result['sources'].items() 
                                            if data.get('has_catalyst', False)]
                    unique_keywords = list(set(ticker_result['keywords_found']))
                    ticker_result['summary'] = f"Catalysts found in {', '.join(sources_with_catalysts)}: {', '.join(unique_keywords[:3])}"
            
            results[ticker] = ticker_result
            
            # Small delay between tickers
            await asyncio.sleep(0.2)
        
        return results
    
    async def _check_finviz(self, ticker: str) -> Dict[str, Any]:
        """Check Finviz for recent news (primary source)"""
        if not FINVIZ_AVAILABLE:
            return {'has_catalyst': False, 'error': 'finvizfinance not available'}
        
        try:
            # Initialize Finviz for this ticker
            stock = finvizfinance(ticker)
            
            # Get news data
            news_data = stock.ticker_news()
            
            found_keywords = []
            relevant_articles = 0
            sample_text = ""
            total_articles = 0
            # Handle DataFrame format from finvizfinance
            if news_data is not None:
                # Check if it's a DataFrame
                if hasattr(news_data, 'empty'):  # pandas DataFrame
                    if not news_data.empty:
                        total_articles = len(news_data)
                        
                        # Finviz DataFrame has columns: ['Date', 'Title', 'Link', 'Source']
                        for index, row in news_data.head(10).iterrows():  # First 10 articles
                            try:
                                
                                # Get title from the 'Title' column
                                if 'Title' in row:
                                    title = str(row['Title']).lower()
                                    
                                    # Check for catalyst keywords in title
                                    for keyword in self.catalyst_keywords:
                                        if keyword.lower() in title:
                                            found_keywords.append(keyword)
                                            relevant_articles += 1
                                            break
                                    
                                    # Collect sample text for sentiment analysis
                                    if len(sample_text) < 400:  # Limit total text
                                        sample_text += f"{row['Title']}. "
                                        
                            except Exception as e:
                                logger.debug(f"Error processing Finviz row for {ticker}: {e}")
                                continue
                
                # Handle list format (if any)
                elif isinstance(news_data, list):
                    total_articles = len(news_data)
                    for article in news_data[:10]:  # Check first 10 articles
                        try:
                            # Finviz news format: [date, title, link] or similar
                            if len(article) >= 2:
                                title = str(article[1]).lower()  # Title is usually index 1
                                
                                # Check for catalyst keywords in title
                                for keyword in self.catalyst_keywords:
                                    if keyword.lower() in title:
                                        found_keywords.append(keyword)
                                        relevant_articles += 1
                                        break
                                
                                # Collect sample text for sentiment analysis
                                if len(sample_text) < 400:  # Limit total text
                                    sample_text += f"{article[1]}. "
                                    
                        except Exception as e:
                            logger.debug(f"Error processing Finviz article for {ticker}: {e}")
                            continue
            
            has_catalyst = len(found_keywords) > 0
            
            # Enhanced logging
            if has_catalyst:
                logger.info(f"✅ {ticker} - Finviz found {relevant_articles} relevant articles with keywords: {list(set(found_keywords))}")
            else:
                logger.info(f"❌ {ticker} - Finviz found no catalysts in {total_articles} articles")
            
            return {
                'has_catalyst': has_catalyst,
                'keywords': list(set(found_keywords)),
                'articles_found': total_articles,
                'relevant_articles': relevant_articles,
                'source': 'Finviz',
                'sample_text': sample_text[:500]  # Limit text length
            }
            
        except Exception as e:
            logger.warning(f"Finviz error for {ticker}: {e}")
            return {'has_catalyst': False, 'error': str(e)}
    
    async def _check_newsapi(self, ticker: str) -> Dict[str, Any]:
        """Check NewsAPI for catalyst keywords"""
        if not self.newsapi_client:
            return {'has_catalyst': False, 'error': 'NewsAPI not available'}
        
        try:
            # Search for ticker + keywords
            search_query = f"{ticker} AND ({' OR '.join(list(self.catalyst_keywords)[:10])})"  # Limit query length
            
            # Get news from last week
            from_date = datetime.now() - timedelta(days=self.config.days_back)
            
            # Search in business/financial sources
            articles = self.newsapi_client.get_everything(
                q=search_query,
                language='en',
                sort_by='publishedAt',
                from_param=from_date.strftime('%Y-%m-%d'),
                page_size=20,
                sources='bloomberg,reuters,cnbc,marketwatch,the-wall-street-journal'
            )
            
            found_keywords = []
            relevant_articles = 0
            
            if articles.get('status') == 'ok' and articles.get('articles'):
                for article in articles['articles'][:10]:  # Check first 10 articles
                    title = article.get('title', '').lower()
                    description = article.get('description', '').lower()
                    content = f"{title} {description}"
                    
                    # Check for keywords
                    for keyword in self.catalyst_keywords:
                        if keyword.lower() in content:
                            found_keywords.append(keyword)
                            relevant_articles += 1
                            break
            
            has_catalyst = len(found_keywords) > 0
            
            # Get sample text for sentiment analysis
            sample_text = ""
            if articles.get('status') == 'ok' and articles.get('articles'):
                for article in articles['articles'][:3]:  # First 3 articles
                    title = article.get('title', '')
                    description = article.get('description', '')
                    sample_text += f"{title}. {description}. "
            
            return {
                'has_catalyst': has_catalyst,
                'keywords': list(set(found_keywords)),
                'articles_found': articles.get('totalResults', 0),
                'relevant_articles': relevant_articles,
                'source': 'NewsAPI',
                'sample_text': sample_text[:500]  # Limit text length
            }
            
        except Exception as e:
            logger.warning(f"NewsAPI error for {ticker}: {e}")
            return {'has_catalyst': False, 'error': str(e)}
    
    async def _check_sec_edgar(self, ticker: str) -> Dict[str, Any]:
        """Check SEC EDGAR for recent filings"""
        if not self.sec_downloader:
            return {'has_catalyst': False, 'error': 'SEC EDGAR not available'}
        
        try:
            # Important SEC form types that often contain catalysts
            important_forms = ['8-K', '10-Q', '10-K', 'DEF 14A', 'SC 13D', 'SC 13G']
            
            found_filings = []
            catalyst_forms = []
            
            # Check recent filings (note: this might be slow for real-time use)
            # In production, you might want to cache this or use a different approach
            
            # For now, we'll simulate this check or use a lightweight approach
            # The full implementation would download and parse recent filings
            
            # Placeholder implementation - in real use, you'd:
            # 1. Get recent filings list for ticker
            # 2. Check filing types and dates
            # 3. Look for catalyst keywords in filing summaries
            
            return {
                'has_catalyst': False,  # Would be determined by actual filing analysis
                'keywords': [],
                'recent_filings': found_filings,
                'catalyst_forms': catalyst_forms,
                'source': 'SEC EDGAR',
                'note': 'SEC checking requires full implementation for production use'
            }
            
        except Exception as e:
            logger.warning(f"SEC EDGAR error for {ticker}: {e}")
            return {'has_catalyst': False, 'error': str(e)}
    
    async def _check_yahoo(self, ticker: str) -> Dict[str, Any]:
        """Check Yahoo Finance news (fallback)"""
        try:
            ticker_obj = Ticker(ticker)
            news_data = ticker_obj.news()
            
            found_keywords = []
            relevant_articles = 0
            ticker_news = []
            
            if ticker in news_data:
                ticker_news = news_data[ticker]
                
                if isinstance(ticker_news, list) and ticker_news:
                    for article in ticker_news[:5]:  # Check first 5 articles
                        try:
                            title = article.get('title', '').lower()
                            summary = article.get('summary', '').lower()
                            content = f"{title} {summary}"
                            
                            # Check for catalyst keywords
                            for keyword in self.catalyst_keywords:
                                if keyword.lower() in content:
                                    found_keywords.append(keyword)
                                    relevant_articles += 1
                                    break
                                    
                        except Exception:
                            continue
            
            has_catalyst = len(found_keywords) > 0
            
            # Get sample text for sentiment analysis
            sample_text = ""
            if isinstance(ticker_news, list) and ticker_news:
                for article in ticker_news[:3]:  # First 3 articles
                    title = article.get('title', '')
                    summary = article.get('summary', '')
                    sample_text += f"{title}. {summary}. "
            
            return {
                'has_catalyst': has_catalyst,
                'keywords': list(set(found_keywords)),
                'articles_found': len(ticker_news) if isinstance(ticker_news, list) else 0,
                'relevant_articles': relevant_articles,
                'source': 'Yahoo Finance',
                'sample_text': sample_text[:500]  # Limit text length
            }
            
        except Exception as e:
            logger.warning(f"Yahoo Finance error for {ticker}: {e}")
            return {'has_catalyst': False, 'error': str(e)}

# Quick test function
async def test_news_sources():
    """Test the multi-source news checker"""
    
    # Test configuration
    config = NewsSource(
        newsapi_key=None,  # Add your NewsAPI key here for testing
        days_back=7
    )
    
    # Test keywords
    keywords = {
        'fda', 'earnings', 'acquisition', 'merger', 'clinical', 
        'breakthrough', 'partnership', 'contract'
    }
    
    # Initialize checker
    checker = MultiSourceNewsChecker(config, keywords)
    
    # Test tickers
    test_tickers = ['AAPL', 'GEVO']
    
    print("🧪 Testing Multi-Source News Checker")
    print("=" * 50)
    
    results = await checker.check_all_sources(test_tickers)
    
    for ticker, result in results.items():
        print(f"\n📊 {ticker}:")
        print(f"   Has Catalyst: {result['has_catalyst']}")
        print(f"   Summary: {result['summary']}")
        
        for source, data in result['sources'].items():
            status = "✅" if data.get('has_catalyst') else "❌"
            print(f"   {status} {source}: {data.get('articles_found', 0)} articles")

if __name__ == "__main__":
    asyncio.run(test_news_sources())