# data_sources/alpha_vantage_provider.py
"""
Alpha Vantage Data Provider for comprehensive market analysis
Provides technical indicators, fundamental data, and economic indicators
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
import json
import time

logger = logging.getLogger(__name__)

@dataclass
class AlphaVantageQuote:
    """Alpha Vantage real-time quote"""
    symbol: str
    price: float
    change: float
    change_percent: str
    volume: int
    previous_close: float
    open_price: float
    high: float
    low: float
    timestamp: datetime

@dataclass
class TechnicalIndicator:
    """Technical indicator data point"""
    symbol: str
    indicator: str
    date: datetime
    value: float
    additional_values: Dict[str, float]  # For multi-value indicators

@dataclass
class EconomicIndicator:
    """Economic indicator data"""
    indicator: str
    date: datetime
    value: float
    unit: str
    description: str

@dataclass
class CompanyOverview:
    """Company fundamental overview"""
    symbol: str
    name: str
    sector: str
    industry: str
    market_cap: int
    pe_ratio: float
    peg_ratio: float
    dividend_yield: float
    eps: float
    revenue: int
    gross_profit_margin: float
    ebitda: int
    beta: float
    week_52_high: float
    week_52_low: float
    analyst_target_price: float
    shares_outstanding: int

class AlphaVantageProvider:
    """
    Alpha Vantage API provider for comprehensive market data
    
    Key features:
    - Real-time and historical quotes
    - Technical indicators (RSI, MACD, SMA, etc.)
    - Fundamental data and company overviews
    - Economic indicators (GDP, inflation, etc.)
    - Earnings data and estimates
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.session = None
        self.logger = logging.getLogger(f"{__name__}.AlphaVantageProvider")
        
        # Rate limiting (5 API calls per minute on free tier)
        self.rate_limit = {
            'calls_per_minute': 5,
            'delay_between_calls': 12,  # 12 seconds between calls
            'last_call_time': 0
        }
        
        # Cache for reducing API calls
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        
        self.logger.info("AlphaVantageProvider initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_session()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is available"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _rate_limited_request(self, params: Dict[str, str]) -> Optional[Dict]:
        """Make rate-limited API request"""
        await self._ensure_session()
        
        # Rate limiting
        current_time = time.time()
        time_since_last_call = current_time - self.rate_limit['last_call_time']
        
        if time_since_last_call < self.rate_limit['delay_between_calls']:
            sleep_time = self.rate_limit['delay_between_calls'] - time_since_last_call
            self.logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s")
            await asyncio.sleep(sleep_time)
        
        # Check cache first
        cache_key = str(sorted(params.items()))
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            if current_time - cache_time < self.cache_duration:
                self.logger.debug(f"Using cached data for {params.get('symbol', 'request')}")
                return cached_data
        
        # Add API key to params
        params['apikey'] = self.api_key
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                self.rate_limit['last_call_time'] = time.time()
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for API errors
                    if 'Error Message' in data:
                        self.logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                        return None
                    
                    if 'Note' in data:
                        self.logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                        return None
                    
                    # Cache successful response
                    self.cache[cache_key] = (data, current_time)
                    return data
                    
                else:
                    self.logger.error(f"Alpha Vantage request failed: {response.status}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error in Alpha Vantage request: {e}")
            return None
    
    async def get_real_time_quote(self, symbol: str) -> Optional[AlphaVantageQuote]:
        """Get real-time quote for symbol"""
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol
        }
        
        data = await self._rate_limited_request(params)
        if not data or 'Global Quote' not in data:
            return None
        
        try:
            quote_data = data['Global Quote']
            
            quote = AlphaVantageQuote(
                symbol=quote_data.get('01. symbol', symbol),
                price=float(quote_data.get('05. price', 0)),
                change=float(quote_data.get('09. change', 0)),
                change_percent=quote_data.get('10. change percent', '0%'),
                volume=int(quote_data.get('06. volume', 0)),
                previous_close=float(quote_data.get('08. previous close', 0)),
                open_price=float(quote_data.get('02. open', 0)),
                high=float(quote_data.get('03. high', 0)),
                low=float(quote_data.get('04. low', 0)),
                timestamp=datetime.now()
            )
            
            return quote
            
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error parsing quote data for {symbol}: {e}")
            return None
    
    async def get_technical_indicator(self, symbol: str, indicator: str, 
                                    time_period: int = 14, 
                                    series_type: str = 'close') -> List[TechnicalIndicator]:
        """
        Get technical indicator data
        
        Supported indicators: RSI, MACD, SMA, EMA, STOCH, ADX, CCI, AROON, BBANDS
        """
        function_map = {
            'RSI': 'RSI',
            'MACD': 'MACD',
            'SMA': 'SMA',
            'EMA': 'EMA',
            'STOCH': 'STOCH',
            'ADX': 'ADX',
            'CCI': 'CCI',
            'AROON': 'AROON',
            'BBANDS': 'BBANDS'
        }
        
        if indicator not in function_map:
            self.logger.error(f"Unsupported indicator: {indicator}")
            return []
        
        params = {
            'function': function_map[indicator],
            'symbol': symbol,
            'interval': 'daily',
            'time_period': str(time_period),
            'series_type': series_type
        }
        
        data = await self._rate_limited_request(params)
        if not data:
            return []
        
        return self._parse_technical_indicator(symbol, indicator, data)
    
    def _parse_technical_indicator(self, symbol: str, indicator: str, data: Dict) -> List[TechnicalIndicator]:
        """Parse technical indicator response"""
        indicators = []
        
        try:
            # Find the technical analysis data key
            tech_key = None
            for key in data.keys():
                if 'Technical Analysis' in key:
                    tech_key = key
                    break
            
            if not tech_key:
                return indicators
            
            tech_data = data[tech_key]
            
            for date_str, values in tech_data.items():
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    if indicator == 'MACD':
                        # MACD has multiple values
                        macd_value = float(values.get('MACD', 0))
                        additional = {
                            'MACD_Signal': float(values.get('MACD_Signal', 0)),
                            'MACD_Hist': float(values.get('MACD_Hist', 0))
                        }
                        
                        indicator_obj = TechnicalIndicator(
                            symbol=symbol,
                            indicator=indicator,
                            date=date,
                            value=macd_value,
                            additional_values=additional
                        )
                        
                    elif indicator == 'STOCH':
                        # Stochastic has %K and %D
                        stoch_k = float(values.get('SlowK', 0))
                        additional = {
                            'SlowD': float(values.get('SlowD', 0))
                        }
                        
                        indicator_obj = TechnicalIndicator(
                            symbol=symbol,
                            indicator=indicator,
                            date=date,
                            value=stoch_k,
                            additional_values=additional
                        )
                        
                    elif indicator == 'BBANDS':
                        # Bollinger Bands have upper, middle, lower
                        middle_band = float(values.get('Real Middle Band', 0))
                        additional = {
                            'Upper_Band': float(values.get('Real Upper Band', 0)),
                            'Lower_Band': float(values.get('Real Lower Band', 0))
                        }
                        
                        indicator_obj = TechnicalIndicator(
                            symbol=symbol,
                            indicator=indicator,
                            date=date,
                            value=middle_band,
                            additional_values=additional
                        )
                        
                    else:
                        # Single value indicators (RSI, SMA, EMA, etc.)
                        value_key = list(values.keys())[0]  # Get first (usually only) value
                        value = float(values[value_key])
                        
                        indicator_obj = TechnicalIndicator(
                            symbol=symbol,
                            indicator=indicator,
                            date=date,
                            value=value,
                            additional_values={}
                        )
                    
                    indicators.append(indicator_obj)
                    
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Error parsing indicator data for {date_str}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing technical indicator for {symbol}: {e}")
        
        return indicators
    
    async def get_company_overview(self, symbol: str) -> Optional[CompanyOverview]:
        """Get company fundamental overview"""
        params = {
            'function': 'OVERVIEW',
            'symbol': symbol
        }
        
        data = await self._rate_limited_request(params)
        if not data:
            return None
        
        try:
            overview = CompanyOverview(
                symbol=data.get('Symbol', symbol),
                name=data.get('Name', ''),
                sector=data.get('Sector', ''),
                industry=data.get('Industry', ''),
                market_cap=self._safe_int(data.get('MarketCapitalization', 0)),
                pe_ratio=self._safe_float(data.get('PERatio', 0)),
                peg_ratio=self._safe_float(data.get('PEGRatio', 0)),
                dividend_yield=self._safe_float(data.get('DividendYield', 0)),
                eps=self._safe_float(data.get('EPS', 0)),
                revenue=self._safe_int(data.get('RevenueTTM', 0)),
                gross_profit_margin=self._safe_float(data.get('GrossProfitMargin', 0)),
                ebitda=self._safe_int(data.get('EBITDA', 0)),
                beta=self._safe_float(data.get('Beta', 0)),
                week_52_high=self._safe_float(data.get('52WeekHigh', 0)),
                week_52_low=self._safe_float(data.get('52WeekLow', 0)),
                analyst_target_price=self._safe_float(data.get('AnalystTargetPrice', 0)),
                shares_outstanding=self._safe_int(data.get('SharesOutstanding', 0))
            )
            
            return overview
            
        except Exception as e:
            self.logger.error(f"Error parsing company overview for {symbol}: {e}")
            return None
    
    async def get_economic_indicators(self, indicator: str) -> List[EconomicIndicator]:
        """
        Get economic indicators
        
        Supported: GDP, INFLATION, UNEMPLOYMENT, FEDERAL_FUNDS_RATE, CPI, RETAIL_SALES
        """
        function_map = {
            'GDP': 'REAL_GDP',
            'INFLATION': 'INFLATION',
            'UNEMPLOYMENT': 'UNEMPLOYMENT',
            'FEDERAL_FUNDS_RATE': 'FEDERAL_FUNDS_RATE',
            'CPI': 'CPI',
            'RETAIL_SALES': 'RETAIL_SALES'
        }
        
        if indicator not in function_map:
            self.logger.error(f"Unsupported economic indicator: {indicator}")
            return []
        
        params = {
            'function': function_map[indicator],
            'interval': 'monthly'
        }
        
        data = await self._rate_limited_request(params)
        if not data:
            return []
        
        return self._parse_economic_indicator(indicator, data)
    
    def _parse_economic_indicator(self, indicator: str, data: Dict) -> List[EconomicIndicator]:
        """Parse economic indicator response"""
        indicators = []
        
        try:
            # Find the data key
            data_key = None
            for key in data.keys():
                if 'data' in key.lower():
                    data_key = key
                    break
            
            if not data_key:
                return indicators
            
            indicator_data = data[data_key]
            
            for entry in indicator_data:
                try:
                    date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    value = float(entry['value'])
                    
                    econ_indicator = EconomicIndicator(
                        indicator=indicator,
                        date=date,
                        value=value,
                        unit=data.get('unit', ''),
                        description=data.get('name', indicator)
                    )
                    
                    indicators.append(econ_indicator)
                    
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Error parsing economic indicator entry: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing economic indicator {indicator}: {e}")
        
        return indicators
    
    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, AlphaVantageQuote]:
        """Get quotes for multiple symbols (rate-limited)"""
        quotes = {}
        
        for symbol in symbols:
            quote = await self.get_real_time_quote(symbol)
            if quote:
                quotes[symbol] = quote
            
            # Small delay between symbols to respect rate limits
            await asyncio.sleep(1)
        
        return quotes
    
    async def get_market_sentiment_indicators(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        """Get key sentiment indicators for symbols"""
        sentiment_data = {}
        
        for symbol in symbols:
            try:
                # Get RSI (overbought/oversold)
                rsi_data = await self.get_technical_indicator(symbol, 'RSI', time_period=14)
                latest_rsi = rsi_data[0].value if rsi_data else 50
                
                # Get company overview for fundamental sentiment
                overview = await self.get_company_overview(symbol)
                
                sentiment_data[symbol] = {
                    'rsi': latest_rsi,
                    'rsi_signal': 'oversold' if latest_rsi < 30 else 'overbought' if latest_rsi > 70 else 'neutral',
                    'pe_ratio': overview.pe_ratio if overview else 0,
                    'beta': overview.beta if overview else 1.0,
                    'analyst_target_upside': 0 if not overview else (overview.analyst_target_price / overview.week_52_high - 1) * 100
                }
                
                # Add delay for rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error getting sentiment for {symbol}: {e}")
                sentiment_data[symbol] = {
                    'rsi': 50,
                    'rsi_signal': 'neutral',
                    'pe_ratio': 0,
                    'beta': 1.0,
                    'analyst_target_upside': 0
                }
        
        return sentiment_data
    
    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float"""
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '').replace('$', '')
                if value in ['None', 'N/A', '-', '']:
                    return 0.0
            return float(value)
        except:
            return 0.0
    
    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int"""
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '')
                if value in ['None', 'N/A', '-', '']:
                    return 0
            return int(float(value))
        except:
            return 0

# Convenience function for testing
async def test_alpha_vantage_provider(api_key: str):
    """Test Alpha Vantage provider functionality"""
    async with AlphaVantageProvider(api_key) as av:
        print("🧪 Testing Alpha Vantage provider...")
        
        test_symbol = 'AAPL'
        
        # Test quote
        print(f"📊 Getting quote for {test_symbol}...")
        quote = await av.get_real_time_quote(test_symbol)
        if quote:
            print(f"✅ {test_symbol}: ${quote.price:.2f} ({quote.change_percent})")
        
        # Test technical indicator
        print(f"📈 Getting RSI for {test_symbol}...")
        rsi_data = await av.get_technical_indicator(test_symbol, 'RSI')
        if rsi_data:
            latest_rsi = rsi_data[0]
            print(f"✅ Latest RSI: {latest_rsi.value:.2f} ({latest_rsi.date})")
        
        # Test company overview
        print(f"🏢 Getting company overview for {test_symbol}...")
        overview = await av.get_company_overview(test_symbol)
        if overview:
            print(f"✅ {overview.name} - Sector: {overview.sector}")
            print(f"   Market Cap: ${overview.market_cap:,} | P/E: {overview.pe_ratio}")
        
        return True

if __name__ == "__main__":
    # Test with demo key (limited functionality)
    demo_key = "demo"
    asyncio.run(test_alpha_vantage_provider(demo_key))