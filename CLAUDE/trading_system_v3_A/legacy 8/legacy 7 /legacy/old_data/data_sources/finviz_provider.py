# data_sources/finviz_provider.py
"""
FINVIZ Data Provider for market screening and analysis
Provides fundamental data, screener results, and insider activity
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
import json
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

@dataclass
class FinvizStockData:
    """FINVIZ stock fundamental data"""
    symbol: str
    company: str
    sector: str
    industry: str
    country: str
    market_cap: str
    pe_ratio: float
    price: float
    change: float
    volume: int
    float_shares: int
    insider_own: float
    institutional_own: float
    short_float: float
    avg_volume: int
    rsi: float
    quick_ratio: float
    current_ratio: float
    debt_equity: float
    roa: float
    roe: float
    profit_margin: float
    earnings_date: str
    target_price: float
    analyst_recom: str
    timestamp: datetime

@dataclass
class FinvizScreenerResult:
    """FINVIZ screener result"""
    symbol: str
    company: str
    price: float
    change_pct: float
    volume: int
    market_cap: str
    pe_ratio: float
    eps_growth: float
    revenue_growth: float
    score: float
    meets_criteria: bool

@dataclass 
class FinvizInsiderTrade:
    """FINVIZ insider trading data"""
    symbol: str
    company: str
    insider: str
    relationship: str
    date: datetime
    transaction: str
    cost: float
    shares: int
    value: int
    shares_total: int
    sec_form: str

class FinvizProvider:
    """
    FINVIZ data provider for screening and fundamental analysis
    
    Key features:
    - Stock screener with custom filters
    - Fundamental data extraction
    - Insider trading activity
    - Market heat maps and trends
    - Earnings calendar
    """
    
    def __init__(self):
        self.base_url = "https://finviz.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = None
        self.logger = logging.getLogger(f"{__name__}.FinvizProvider")
        
        # Screener filters for smallcaps
        self.smallcap_filters = {
            'market_cap': ['Small Cap', 'Micro Cap'],
            'price_range': [0.50, 15.00],
            'volume_min': 100000,
            'float_min': 5000000,  # 5M minimum float
            'insider_ownership_min': 5.0,  # 5% minimum insider ownership
        }
        
        self.logger.info("FinvizProvider initialized")
    
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
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def screen_smallcap_opportunities(self, 
                                          min_volume: int = 100000,
                                          min_price: float = 0.50,
                                          max_price: float = 15.00,
                                          min_insider_own: float = 5.0) -> List[FinvizScreenerResult]:
        """
        Screen for smallcap daily play opportunities
        
        Filters:
        - Price range for smallcaps
        - Minimum volume for liquidity
        - Insider ownership (skin in the game)
        - Recent momentum indicators
        """
        await self._ensure_session()
        
        self.logger.info(f"🔍 Screening smallcap opportunities...")
        
        # Build FINVIZ screener URL
        screener_params = {
            'v': '111',  # Overview view
            'f': self._build_screener_filters(min_volume, min_price, max_price, min_insider_own),
            'o': '-volume'  # Sort by volume desc
        }
        
        url = f"{self.base_url}/screener.ashx"
        
        try:
            async with self.session.get(url, params=screener_params) as response:
                if response.status == 200:
                    html = await response.text()
                    results = self._parse_screener_results(html)
                    
                    self.logger.info(f"✅ Found {len(results)} screener results")
                    return results
                else:
                    self.logger.error(f"FINVIZ screener request failed: {response.status}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"Error in screener request: {e}")
            return []
    
    def _build_screener_filters(self, min_volume: int, min_price: float, 
                               max_price: float, min_insider_own: float) -> str:
        """Build FINVIZ filter string"""
        filters = []
        
        # Volume filter
        if min_volume >= 1000000:
            filters.append(f"sh_avgvol_o{min_volume//1000000}")  # Million shares
        elif min_volume >= 100000:
            filters.append(f"sh_avgvol_o{min_volume//100000}00")  # Hundred thousands
        
        # Price range
        if min_price > 0:
            filters.append(f"sh_price_o{min_price}")
        if max_price < 1000:
            filters.append(f"sh_price_u{max_price}")
        
        # Market cap (smallcap focus)
        filters.append("cap_smallover")  # Small cap and above
        
        # Insider ownership
        if min_insider_own > 0:
            filters.append(f"sh_insiderown_o{int(min_insider_own)}")
        
        # Additional quality filters
        filters.extend([
            "sh_curvol_o500",  # Current volume > 500K
            "ta_change_u",     # Positive change today
            "geo_usa"          # USA only
        ])
        
        return ",".join(filters)
    
    def _parse_screener_results(self, html: str) -> List[FinvizScreenerResult]:
        """Parse FINVIZ screener results from HTML"""
        results = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the screener table
            table = soup.find('table', {'class': 'screener_table'})
            if not table:
                return results
            
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 11:  # Basic validation
                    continue
                
                try:
                    symbol = cells[1].text.strip()
                    company = cells[2].text.strip()
                    price = float(cells[8].text.strip().replace('$', ''))
                    change_pct = float(cells[9].text.strip().replace('%', ''))
                    volume_str = cells[10].text.strip()
                    market_cap = cells[6].text.strip()
                    
                    # Parse volume (handle K, M suffixes)
                    volume = self._parse_volume(volume_str)
                    
                    # Parse PE ratio
                    pe_str = cells[7].text.strip()
                    pe_ratio = float(pe_str) if pe_str != '-' else 0.0
                    
                    # Calculate basic score
                    score = self._calculate_opportunity_score(
                        price, change_pct, volume, pe_ratio
                    )
                    
                    result = FinvizScreenerResult(
                        symbol=symbol,
                        company=company,
                        price=price,
                        change_pct=change_pct,
                        volume=volume,
                        market_cap=market_cap,
                        pe_ratio=pe_ratio,
                        eps_growth=0.0,  # Would need detailed page
                        revenue_growth=0.0,  # Would need detailed page
                        score=score,
                        meets_criteria=score >= 6.0
                    )
                    
                    results.append(result)
                    
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Error parsing row: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing screener results: {e}")
        
        return results
    
    def _parse_volume(self, volume_str: str) -> int:
        """Parse volume string with K/M suffixes"""
        try:
            volume_str = volume_str.replace(',', '').strip()
            
            if volume_str.endswith('M'):
                return int(float(volume_str[:-1]) * 1_000_000)
            elif volume_str.endswith('K'):
                return int(float(volume_str[:-1]) * 1_000)
            else:
                return int(volume_str)
        except:
            return 0
    
    def _calculate_opportunity_score(self, price: float, change_pct: float, 
                                   volume: int, pe_ratio: float) -> float:
        """Calculate opportunity score for screening"""
        score = 0.0
        
        # Price momentum (0-3 points)
        if change_pct > 5:
            score += 3
        elif change_pct > 2:
            score += 2
        elif change_pct > 0:
            score += 1
        
        # Volume (0-2 points)
        if volume > 1_000_000:
            score += 2
        elif volume > 500_000:
            score += 1
        
        # Valuation (0-2 points)
        if 0 < pe_ratio < 15:
            score += 2
        elif 0 < pe_ratio < 25:
            score += 1
        
        # Price range preference (0-3 points)
        if 1.0 <= price <= 10.0:
            score += 3
        elif 0.5 <= price <= 15.0:
            score += 2
        elif price > 0.1:
            score += 1
        
        return score
    
    async def get_stock_details(self, symbol: str) -> Optional[FinvizStockData]:
        """Get detailed stock information from FINVIZ"""
        await self._ensure_session()
        
        url = f"{self.base_url}/quote.ashx?t={symbol}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_stock_details(symbol, html)
                else:
                    self.logger.error(f"Stock details request failed for {symbol}: {response.status}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error getting stock details for {symbol}: {e}")
            return None
    
    def _parse_stock_details(self, symbol: str, html: str) -> Optional[FinvizStockData]:
        """Parse detailed stock data from FINVIZ quote page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract data from the fundamentals table
            data = {}
            
            # Find all table cells with data
            tables = soup.find_all('table', {'class': 'snapshot-table2'})
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    for i in range(0, len(cells), 2):
                        if i + 1 < len(cells):
                            key = cells[i].text.strip()
                            value = cells[i + 1].text.strip()
                            data[key] = value
            
            # Extract key metrics
            stock_data = FinvizStockData(
                symbol=symbol,
                company=data.get('Company', ''),
                sector=data.get('Sector', ''),
                industry=data.get('Industry', ''),
                country=data.get('Country', ''),
                market_cap=data.get('Market Cap', ''),
                pe_ratio=self._safe_float(data.get('P/E', '0')),
                price=self._safe_float(data.get('Price', '0')),
                change=self._safe_float(data.get('Change', '0').replace('%', '')),
                volume=self._safe_int(data.get('Volume', '0')),
                float_shares=self._safe_int(data.get('Shs Float', '0')),
                insider_own=self._safe_float(data.get('Insider Own', '0').replace('%', '')),
                institutional_own=self._safe_float(data.get('Inst Own', '0').replace('%', '')),
                short_float=self._safe_float(data.get('Short Float', '0').replace('%', '')),
                avg_volume=self._safe_int(data.get('Avg Volume', '0')),
                rsi=self._safe_float(data.get('RSI (14)', '0')),
                quick_ratio=self._safe_float(data.get('Quick Ratio', '0')),
                current_ratio=self._safe_float(data.get('Current Ratio', '0')),
                debt_equity=self._safe_float(data.get('Debt/Eq', '0')),
                roa=self._safe_float(data.get('ROA', '0').replace('%', '')),
                roe=self._safe_float(data.get('ROE', '0').replace('%', '')),
                profit_margin=self._safe_float(data.get('Profit M', '0').replace('%', '')),
                earnings_date=data.get('Earnings', ''),
                target_price=self._safe_float(data.get('Target Price', '0')),
                analyst_recom=data.get('Recom', ''),
                timestamp=datetime.now()
            )
            
            return stock_data
            
        except Exception as e:
            self.logger.error(f"Error parsing stock details for {symbol}: {e}")
            return None
    
    def _safe_float(self, value: str) -> float:
        """Safely convert string to float"""
        try:
            # Handle special cases
            value = value.replace(',', '').replace('$', '').replace('%', '')
            if value in ['-', 'N/A', '']:
                return 0.0
            return float(value)
        except:
            return 0.0
    
    def _safe_int(self, value: str) -> int:
        """Safely convert string to int"""
        try:
            # Handle K/M/B suffixes
            value = value.replace(',', '').strip()
            if value.endswith('B'):
                return int(float(value[:-1]) * 1_000_000_000)
            elif value.endswith('M'):
                return int(float(value[:-1]) * 1_000_000)
            elif value.endswith('K'):
                return int(float(value[:-1]) * 1_000)
            else:
                return int(float(value))
        except:
            return 0
    
    async def get_insider_activity(self, days: int = 7) -> List[FinvizInsiderTrade]:
        """Get recent insider trading activity"""
        await self._ensure_session()
        
        url = f"{self.base_url}/insidertrading.ashx"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_insider_activity(html, days)
                else:
                    self.logger.error(f"Insider activity request failed: {response.status}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"Error getting insider activity: {e}")
            return []
    
    def _parse_insider_activity(self, html: str, days: int) -> List[FinvizInsiderTrade]:
        """Parse insider trading activity"""
        trades = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find insider trading table
            table = soup.find('table', {'class': 'body-table'})
            if not table:
                return trades
            
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 10:
                    continue
                
                try:
                    # Parse trade data
                    symbol = cells[0].text.strip()
                    company = cells[1].text.strip()
                    insider = cells[2].text.strip()
                    relationship = cells[3].text.strip()
                    date_str = cells[4].text.strip()
                    transaction = cells[5].text.strip()
                    cost = self._safe_float(cells[6].text.strip())
                    shares = self._safe_int(cells[7].text.strip())
                    value = self._safe_int(cells[8].text.strip())
                    shares_total = self._safe_int(cells[9].text.strip())
                    sec_form = cells[10].text.strip() if len(cells) > 10 else ''
                    
                    # Parse date
                    trade_date = datetime.strptime(date_str, '%b %d')
                    trade_date = trade_date.replace(year=datetime.now().year)
                    
                    # Filter by date
                    if trade_date >= cutoff_date:
                        trade = FinvizInsiderTrade(
                            symbol=symbol,
                            company=company,
                            insider=insider,
                            relationship=relationship,
                            date=trade_date,
                            transaction=transaction,
                            cost=cost,
                            shares=shares,
                            value=value,
                            shares_total=shares_total,
                            sec_form=sec_form
                        )
                        trades.append(trade)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing insider trade row: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing insider activity: {e}")
        
        return trades
    
    def format_screener_results(self, results: List[FinvizScreenerResult]) -> str:
        """Format screener results for display"""
        if not results:
            return "No opportunities found with current criteria."
        
        output = f"🎯 FINVIZ SCREENER ({len(results)} opportunities):\n"
        
        # Filter for high-quality plays
        quality_plays = [r for r in results if r.meets_criteria]
        
        if quality_plays:
            symbols = [r.symbol for r in quality_plays]
            output += f"📋 Quality Symbols: {', '.join(symbols)}\n\n"
            
            output += "📊 TOP OPPORTUNITIES:\n"
            for i, result in enumerate(quality_plays[:10], 1):
                output += f"{i}. {result.symbol} - ${result.price:.2f} ({result.change_pct:+.1f}%)\n"
                output += f"   {result.company}\n"
                output += f"   Volume: {result.volume:,} | Cap: {result.market_cap} | Score: {result.score:.1f}\n\n"
        else:
            output += "ℹ️ No high-quality opportunities found. Consider adjusting criteria.\n"
        
        return output

# Convenience function for testing
async def test_finviz_screener():
    """Test FINVIZ screener functionality"""
    async with FinvizProvider() as finviz:
        print("🧪 Testing FINVIZ screener...")
        
        results = await finviz.screen_smallcap_opportunities(
            min_volume=100000,
            min_price=0.50,
            max_price=15.00,
            min_insider_own=5.0
        )
        
        print(finviz.format_screener_results(results))
        
        # Test individual stock details
        if results:
            test_symbol = results[0].symbol
            print(f"\n🔍 Testing stock details for {test_symbol}...")
            
            details = await finviz.get_stock_details(test_symbol)
            if details:
                print(f"✅ Got details for {test_symbol}")
                print(f"   Sector: {details.sector}")
                print(f"   Market Cap: {details.market_cap}")
                print(f"   Insider Own: {details.insider_own}%")
            else:
                print(f"❌ Failed to get details for {test_symbol}")
        
        return results

if __name__ == "__main__":
    asyncio.run(test_finviz_screener())