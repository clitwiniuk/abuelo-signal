# data_sources/data_pipeline.py
"""
Unified Data Pipeline: FINVIZ + IBKR + Alpha Vantage + Tiingo
Intelligent data fusion and fallback system for comprehensive market analysis
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

# Import our data providers
from .finviz_provider import FinvizProvider, FinvizScreenerResult, FinvizStockData
from .alpha_vantage_provider import AlphaVantageProvider, AlphaVantageQuote, TechnicalIndicator, CompanyOverview

# Import existing providers
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scanner.tiingo_data_provider import TiingoDataProvider, TiingoQuote
    from scanner.hybrid_scanner import HybridScanner, HybridScanResult
    from adapters.ibkr_adapter import IBKRAdapter
except ImportError as e:
    logging.warning(f"Some data providers not available: {e}")

logger = logging.getLogger(__name__)

class DataSource(Enum):
    FINVIZ = "FINVIZ"
    ALPHA_VANTAGE = "ALPHA_VANTAGE"
    TIINGO = "TIINGO"
    IBKR = "IBKR"
    HYBRID = "HYBRID"

@dataclass
class DataSourceStatus:
    """Data source availability and performance"""
    source: DataSource
    available: bool
    last_success: Optional[datetime]
    error_count: int
    avg_response_time: float
    rate_limit_remaining: int

@dataclass
class UnifiedMarketData:
    """Unified market data from multiple sources"""
    symbol: str
    timestamp: datetime
    
    # Price data (real-time priority: Tiingo > IBKR > Alpha Vantage)
    current_price: float
    previous_close: float
    gap_percentage: float
    volume: int
    avg_volume: int
    high: float
    low: float
    open_price: float
    
    # Technical indicators (Alpha Vantage)
    rsi: Optional[float] = None
    macd: Optional[Dict[str, float]] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    bollinger_bands: Optional[Dict[str, float]] = None
    
    # Fundamental data (FINVIZ + Alpha Vantage)
    market_cap: Optional[str] = None
    pe_ratio: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    insider_ownership: Optional[float] = None
    institutional_ownership: Optional[float] = None
    float_shares: Optional[int] = None
    short_float: Optional[float] = None
    
    # Screening signals (FINVIZ)
    finviz_score: Optional[float] = None
    finviz_rank: Optional[int] = None
    
    # Data quality and sources
    primary_price_source: DataSource = DataSource.HYBRID
    data_quality: str = "MEDIUM"
    sources_used: List[DataSource] = None
    
    def __post_init__(self):
        if self.sources_used is None:
            self.sources_used = []

class DataPipeline:
    """
    Unified data pipeline combining all data sources
    
    Architecture:
    1. FINVIZ: Screening and fundamental data
    2. Hybrid Scanner (IBKR + Tiingo): Real-time prices and gaps
    3. Alpha Vantage: Technical indicators and additional fundamentals
    4. Intelligent fallback and data fusion
    """
    
    def __init__(self, 
                 ibkr_adapter: Optional[IBKRAdapter] = None,
                 tiingo_api_key: Optional[str] = None,
                 alpha_vantage_api_key: Optional[str] = None):
        
        self.logger = logging.getLogger(f"{__name__}.DataPipeline")
        
        # Initialize data providers
        self.finviz = None
        self.alpha_vantage = None
        self.hybrid_scanner = None
        self.tiingo = None
        
        # Configuration
        self.config = {
            'prefer_real_time': True,
            'max_data_age_minutes': 15,
            'parallel_requests': True,
            'fallback_enabled': True,
            'cache_duration': 300,  # 5 minutes
        }
        
        # Provider status tracking
        self.provider_status = {
            DataSource.FINVIZ: DataSourceStatus(
                DataSource.FINVIZ, True, None, 0, 0.0, 1000
            ),
            DataSource.ALPHA_VANTAGE: DataSourceStatus(
                DataSource.ALPHA_VANTAGE, bool(alpha_vantage_api_key), None, 0, 0.0, 5
            ),
            DataSource.TIINGO: DataSourceStatus(
                DataSource.TIINGO, bool(tiingo_api_key), None, 0, 0.0, 1000
            ),
            DataSource.IBKR: DataSourceStatus(
                DataSource.IBKR, bool(ibkr_adapter), None, 0, 0.0, 1000
            )
        }
        
        # Store API keys and adapters
        self.api_keys = {
            'tiingo': tiingo_api_key,
            'alpha_vantage': alpha_vantage_api_key
        }
        self.ibkr_adapter = ibkr_adapter
        
        # Data cache
        self.cache = {}
        
        self.logger.info("DataPipeline initialized")
        self._log_provider_status()
    
    def _log_provider_status(self):
        """Log provider availability status"""
        for source, status in self.provider_status.items():
            icon = "✅" if status.available else "❌"
            self.logger.info(f"   {icon} {source.value}: {'Available' if status.available else 'Not available'}")
    
    async def initialize_providers(self):
        """Initialize all available data providers"""
        try:
            # Initialize FINVIZ (always available - web scraping)
            self.finviz = FinvizProvider()
            
            # Initialize Alpha Vantage if API key available
            if self.api_keys['alpha_vantage']:
                self.alpha_vantage = AlphaVantageProvider(self.api_keys['alpha_vantage'])
            
            # Initialize Hybrid Scanner (IBKR + Tiingo)
            if self.ibkr_adapter or self.api_keys['tiingo']:
                self.hybrid_scanner = HybridScanner(
                    ibkr_adapter=self.ibkr_adapter,
                    tiingo_api_key=self.api_keys['tiingo']
                )
            
            # Initialize Tiingo separately if needed
            if self.api_keys['tiingo']:
                self.tiingo = TiingoDataProvider(self.api_keys['tiingo'])
            
            self.logger.info("✅ Data providers initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing providers: {e}")
    
    async def screen_opportunities(self, 
                                 min_gap_percent: float = 0.08,
                                 min_volume_ratio: float = 2.0,
                                 min_price: float = 0.50,
                                 max_price: float = 15.00,
                                 max_results: int = 20) -> List[UnifiedMarketData]:
        """
        Screen for trading opportunities using all available sources
        
        Pipeline:
        1. FINVIZ screening for fundamental quality
        2. Hybrid scanner for real-time gaps and volume
        3. Alpha Vantage for technical indicators
        4. Data fusion and ranking
        """
        self.logger.info("🔍 Starting unified opportunity screening...")
        
        opportunities = []
        
        try:
            # Ensure providers are initialized
            if not self.finviz:
                await self.initialize_providers()
            
            # Step 1: Get candidates from multiple sources in parallel
            screening_tasks = []
            
            # FINVIZ screening
            if self.finviz:
                screening_tasks.append(
                    self._run_finviz_screening(min_volume_ratio * 100000, min_price, max_price)
                )
            
            # Hybrid scanner screening
            if self.hybrid_scanner:
                screening_tasks.append(
                    self._run_hybrid_screening(min_gap_percent, min_volume_ratio, min_price, max_price)
                )
            
            # Execute screenings in parallel
            screening_results = await asyncio.gather(*screening_tasks, return_exceptions=True)
            
            # Step 2: Combine and deduplicate results
            all_symbols = set()
            finviz_results = []
            hybrid_results = []
            
            for i, result in enumerate(screening_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Screening task {i} failed: {result}")
                    continue
                
                if i == 0 and self.finviz:  # FINVIZ results
                    finviz_results = result
                    all_symbols.update([r.symbol for r in result])
                elif i == 1 and self.hybrid_scanner:  # Hybrid results
                    hybrid_results = result
                    all_symbols.update([r.symbol for r in result])
            
            # Step 3: Create unified data for each symbol
            symbol_list = list(all_symbols)[:max_results]  # Limit for API efficiency
            
            self.logger.info(f"📊 Creating unified data for {len(symbol_list)} symbols...")
            
            for symbol in symbol_list:
                try:
                    unified_data = await self._create_unified_data(
                        symbol, finviz_results, hybrid_results
                    )
                    
                    if unified_data:
                        opportunities.append(unified_data)
                    
                except Exception as e:
                    self.logger.error(f"Error creating unified data for {symbol}: {e}")
                    continue
            
            # Step 4: Sort by combined quality score
            opportunities.sort(key=lambda x: self._calculate_unified_score(x), reverse=True)
            
            self.logger.info(f"🎯 Pipeline complete: {len(opportunities)} unified opportunities")
            
            return opportunities[:max_results]
            
        except Exception as e:
            self.logger.error(f"Error in screening pipeline: {e}")
            return []
    
    async def _run_finviz_screening(self, min_volume: int, min_price: float, max_price: float) -> List[FinvizScreenerResult]:
        """Run FINVIZ screening"""
        try:
            async with self.finviz:
                results = await self.finviz.screen_smallcap_opportunities(
                    min_volume=min_volume,
                    min_price=min_price,
                    max_price=max_price,
                    min_insider_own=5.0
                )
            
            self.provider_status[DataSource.FINVIZ].last_success = datetime.now()
            self.logger.info(f"📊 FINVIZ found {len(results)} candidates")
            return results
            
        except Exception as e:
            self.provider_status[DataSource.FINVIZ].error_count += 1
            self.logger.error(f"FINVIZ screening failed: {e}")
            return []
    
    async def _run_hybrid_screening(self, min_gap: float, min_volume_ratio: float, 
                                   min_price: float, max_price: float) -> List[HybridScanResult]:
        """Run hybrid scanner screening"""
        try:
            results = await self.hybrid_scanner.scan_daily_plays(
                min_gap_percent=min_gap,
                min_volume_ratio=min_volume_ratio,
                min_price=min_price,
                max_price=max_price,
                max_results=50
            )
            
            # Update provider status
            if self.ibkr_adapter:
                self.provider_status[DataSource.IBKR].last_success = datetime.now()
            if self.api_keys['tiingo']:
                self.provider_status[DataSource.TIINGO].last_success = datetime.now()
            
            self.logger.info(f"🔄 Hybrid scanner found {len(results)} candidates")
            return results
            
        except Exception as e:
            self.logger.error(f"Hybrid screening failed: {e}")
            return []
    
    async def _create_unified_data(self, symbol: str, 
                                 finviz_results: List[FinvizScreenerResult],
                                 hybrid_results: List[HybridScanResult]) -> Optional[UnifiedMarketData]:
        """Create unified market data for a symbol"""
        try:
            # Find data from each source
            finviz_data = next((r for r in finviz_results if r.symbol == symbol), None)
            hybrid_data = next((r for r in hybrid_results if r.symbol == symbol), None)
            
            # Determine primary price source and data
            if hybrid_data:
                # Use hybrid data for price (real-time priority)
                current_price = hybrid_data.current_price
                previous_close = hybrid_data.previous_close
                gap_percentage = hybrid_data.gap_percentage
                volume = hybrid_data.volume
                avg_volume = hybrid_data.avg_volume
                primary_source = hybrid_data.primary_source
                data_quality = hybrid_data.data_quality
                sources_used = [primary_source]
                
                # Extract OHLC if available
                high = current_price * 1.02  # Approximate
                low = current_price * 0.98   # Approximate
                open_price = previous_close * (1 + gap_percentage)
                
            elif finviz_data:
                # Use FINVIZ data as fallback
                current_price = finviz_data.price
                previous_close = current_price / (1 + finviz_data.change_pct / 100)
                gap_percentage = finviz_data.change_pct / 100
                volume = finviz_data.volume
                avg_volume = volume // 2  # Rough estimate
                primary_source = DataSource.FINVIZ
                data_quality = "MEDIUM"
                sources_used = [DataSource.FINVIZ]
                
                high = current_price
                low = current_price
                open_price = previous_close
                
            else:
                # No price data available
                return None
            
            # Get technical indicators from Alpha Vantage (if available)
            technical_data = await self._get_technical_data(symbol)
            
            # Get detailed fundamental data from FINVIZ (if not already obtained)
            fundamental_data = await self._get_fundamental_data(symbol, finviz_data)
            
            # Create unified data object
            unified_data = UnifiedMarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=current_price,
                previous_close=previous_close,
                gap_percentage=gap_percentage,
                volume=volume,
                avg_volume=avg_volume,
                high=high,
                low=low,
                open_price=open_price,
                primary_price_source=primary_source,
                data_quality=data_quality,
                sources_used=sources_used
            )
            
            # Add technical indicators
            if technical_data:
                unified_data.rsi = technical_data.get('rsi')
                unified_data.macd = technical_data.get('macd')
                unified_data.sma_20 = technical_data.get('sma_20')
                unified_data.sma_50 = technical_data.get('sma_50')
                unified_data.bollinger_bands = technical_data.get('bollinger_bands')
                if DataSource.ALPHA_VANTAGE not in unified_data.sources_used:
                    unified_data.sources_used.append(DataSource.ALPHA_VANTAGE)
            
            # Add fundamental data
            if fundamental_data:
                unified_data.market_cap = fundamental_data.get('market_cap')
                unified_data.pe_ratio = fundamental_data.get('pe_ratio')
                unified_data.sector = fundamental_data.get('sector')
                unified_data.industry = fundamental_data.get('industry')
                unified_data.insider_ownership = fundamental_data.get('insider_ownership')
                unified_data.institutional_ownership = fundamental_data.get('institutional_ownership')
                unified_data.float_shares = fundamental_data.get('float_shares')
                unified_data.short_float = fundamental_data.get('short_float')
            
            # Add FINVIZ screening score
            if finviz_data:
                unified_data.finviz_score = finviz_data.score
                # Calculate rank among FINVIZ results
                finviz_sorted = sorted(finviz_results, key=lambda x: x.score, reverse=True)
                unified_data.finviz_rank = next((i+1 for i, r in enumerate(finviz_sorted) if r.symbol == symbol), 999)
            
            return unified_data
            
        except Exception as e:
            self.logger.error(f"Error creating unified data for {symbol}: {e}")
            return None
    
    async def _get_technical_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get technical indicators from Alpha Vantage"""
        if not self.alpha_vantage:
            return None
        
        try:
            # Get RSI (most important for momentum)
            rsi_data = await self.alpha_vantage.get_technical_indicator(symbol, 'RSI', 14)
            rsi = rsi_data[0].value if rsi_data else None
            
            # Note: Additional indicators would require more API calls
            # For efficiency, we'll limit to RSI for now
            
            return {
                'rsi': rsi,
                'macd': None,  # Would need additional API call
                'sma_20': None,  # Would need additional API call
                'sma_50': None,  # Would need additional API call
                'bollinger_bands': None  # Would need additional API call
            }
            
        except Exception as e:
            self.logger.warning(f"Error getting technical data for {symbol}: {e}")
            return None
    
    async def _get_fundamental_data(self, symbol: str, finviz_data: Optional[FinvizScreenerResult]) -> Optional[Dict[str, Any]]:
        """Get detailed fundamental data"""
        if finviz_data:
            # Use existing FINVIZ data
            return {
                'market_cap': finviz_data.market_cap,
                'pe_ratio': finviz_data.pe_ratio,
                'sector': None,  # Would need detailed FINVIZ call
                'industry': None,  # Would need detailed FINVIZ call
                'insider_ownership': None,
                'institutional_ownership': None,
                'float_shares': None,
                'short_float': None
            }
        
        # Could get from Alpha Vantage company overview if available
        # But this would use another API call
        return None
    
    def _calculate_unified_score(self, data: UnifiedMarketData) -> float:
        """Calculate unified quality score for ranking"""
        score = 0.0
        
        # Gap momentum (0-30 points)
        gap_score = min(abs(data.gap_percentage) * 300, 30)
        score += gap_score
        
        # Volume surge (0-25 points)
        if data.avg_volume > 0:
            volume_ratio = data.volume / data.avg_volume
            volume_score = min(volume_ratio * 5, 25)
            score += volume_score
        
        # RSI momentum (0-20 points)
        if data.rsi:
            if data.rsi < 30:  # Oversold bounce potential
                score += 20
            elif data.rsi > 70:  # Overbought momentum
                score += 15
            elif 40 <= data.rsi <= 60:  # Neutral
                score += 10
        
        # FINVIZ fundamental score (0-15 points)
        if data.finviz_score:
            score += min(data.finviz_score * 1.5, 15)
        
        # Data quality bonus (0-10 points)
        quality_bonus = {
            'HIGH': 10,
            'MEDIUM': 6,
            'LOW': 2
        }.get(data.data_quality, 0)
        score += quality_bonus
        
        return score
    
    def format_opportunities(self, opportunities: List[UnifiedMarketData]) -> str:
        """Format unified opportunities for display"""
        if not opportunities:
            return "No unified opportunities found."
        
        output = f"🎯 UNIFIED PIPELINE RESULTS ({len(opportunities)} opportunities):\n"
        
        # Source summary
        source_counts = {}
        for opp in opportunities:
            for source in opp.sources_used:
                source_counts[source.value] = source_counts.get(source.value, 0) + 1
        
        output += "📊 Data Sources Used:\n"
        for source, count in source_counts.items():
            output += f"   {source}: {count} symbols\n"
        
        output += f"\n📋 Top Opportunities:\n"
        
        for i, opp in enumerate(opportunities[:10], 1):
            score = self._calculate_unified_score(opp)
            gap_direction = "↗" if opp.gap_percentage > 0 else "↘"
            
            output += f"{i}. {opp.symbol} {gap_direction} (Score: {score:.0f})\n"
            output += f"   Price: ${opp.current_price:.2f} | Gap: {opp.gap_percentage*100:+.1f}%\n"
            output += f"   Volume: {opp.volume:,} ({opp.volume/opp.avg_volume:.1f}x avg)\n"
            
            if opp.rsi:
                output += f"   RSI: {opp.rsi:.1f}"
            if opp.pe_ratio:
                output += f" | P/E: {opp.pe_ratio:.1f}"
            if opp.market_cap:
                output += f" | Cap: {opp.market_cap}"
            
            output += f"\n   Sources: {', '.join([s.value for s in opp.sources_used])}\n"
            output += f"   Quality: {opp.data_quality}\n\n"
        
        return output
    
    async def cleanup(self):
        """Cleanup all providers"""
        try:
            if self.finviz:
                await self.finviz._close_session()
            if self.alpha_vantage:
                await self.alpha_vantage._close_session()
            if self.hybrid_scanner and hasattr(self.hybrid_scanner, 'tiingo_provider'):
                await self.hybrid_scanner.tiingo_provider._close_session()
            if self.tiingo:
                await self.tiingo._close_session()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

# Convenience function for testing
async def test_data_pipeline(tiingo_key: str = None, alpha_vantage_key: str = None):
    """Test the unified data pipeline"""
    print("🧪 Testing Unified Data Pipeline...")
    
    pipeline = DataPipeline(
        tiingo_api_key=tiingo_key,
        alpha_vantage_api_key=alpha_vantage_key
    )
    
    try:
        await pipeline.initialize_providers()
        
        opportunities = await pipeline.screen_opportunities(
            min_gap_percent=0.05,  # 5% for testing
            min_volume_ratio=1.5,
            max_results=10
        )
        
        print(pipeline.format_opportunities(opportunities))
        
        return opportunities
        
    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        return []
    
    finally:
        await pipeline.cleanup()

if __name__ == "__main__":
    # Test with Tiingo key
    tiingo_key = "ac3776a5f4afaef00823a68b0e8ef7e43d28092b"
    asyncio.run(test_data_pipeline(tiingo_key=tiingo_key))