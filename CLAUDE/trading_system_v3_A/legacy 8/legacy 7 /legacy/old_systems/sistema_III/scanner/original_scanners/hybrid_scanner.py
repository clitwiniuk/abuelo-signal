# scanner/hybrid_scanner.py
"""
Hybrid Scanner - IBKR + Tiingo Intelligent Combination
Uses IBKR for symbols with data, Tiingo for real-time smallcap gaps
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .tiingo_data_provider import TiingoDataProvider, TiingoScanResult, TiingoQuote
from .ibkr_native_scanner import IBKRNativeScanner, IBKRScanResult
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

class DataSource(Enum):
    IBKR = "IBKR"
    TIINGO = "TIINGO"
    HYBRID = "HYBRID"

@dataclass
class HybridScanResult:
    """Unified result from hybrid scanning"""
    symbol: str
    current_price: float
    previous_close: float
    gap_percentage: float
    volume: int
    avg_volume: int
    volume_ratio: float
    
    # Source information
    primary_source: DataSource
    data_quality: str  # 'HIGH', 'MEDIUM', 'LOW'
    
    # Ranking and scoring
    overall_score: float
    gap_rank: int
    volume_rank: int
    
    # Market timing
    market_session: str
    timestamp: datetime
    
    # Source-specific data
    ibkr_data: Optional[IBKRScanResult] = None
    tiingo_data: Optional[TiingoScanResult] = None

class HybridScanner:
    """
    Intelligent hybrid scanner that combines IBKR + Tiingo
    
    Strategy:
    1. Try IBKR scanner first (fast, integrated with execution)
    2. For symbols without IBKR data, use Tiingo real-time
    3. Cross-validate results where both sources available
    4. Intelligent failover and data fusion
    """
    
    def __init__(self, 
                 ibkr_adapter: Optional[IBKRAdapter] = None,
                 tiingo_api_key: Optional[str] = None):
        
        self.logger = logging.getLogger(f"{__name__}.HybridScanner")
        
        # Initialize data providers
        self.ibkr_scanner = IBKRNativeScanner(ibkr_adapter) if ibkr_adapter else None
        self.tiingo_provider = None
        self.tiingo_api_key = tiingo_api_key
        
        # Configuration
        self.config = {
            'prefer_ibkr': True,  # Prefer IBKR when available
            'cross_validate': True,  # Validate results across sources
            'max_price_deviation': 0.05,  # 5% max price difference between sources
            'min_data_quality': 'MEDIUM',  # Minimum acceptable data quality
            'timeout_seconds': 45,  # Timeout for small caps (often slower data)
        }
        
        # Stats tracking
        self.scan_stats = {
            'ibkr_success': 0,
            'tiingo_success': 0,
            'hybrid_success': 0,
            'failures': 0
        }
        
        self.logger.info("HybridScanner initialized")
        self.logger.info(f"   IBKR Available: {'✅' if self.ibkr_scanner else '❌'}")
        self.logger.info(f"   Tiingo Available: {'✅' if tiingo_api_key else '❌'}")
    
    async def scan_daily_plays(self, 
                             min_gap_percent: float = 0.08,
                             min_volume_ratio: float = 2.0,
                             min_price: float = 0.50,
                             max_price: float = 15.00,
                             max_results: int = 20) -> List[HybridScanResult]:
        """
        Main scanning function using hybrid approach
        
        Returns ranked list of daily plays with best available data
        """
        self.logger.info("🔍 Starting Hybrid Scanner (IBKR + Tiingo)...")
        
        try:
            # Initialize Tiingo if needed
            if self.tiingo_api_key and not self.tiingo_provider:
                self.tiingo_provider = TiingoDataProvider(self.tiingo_api_key)
                await self.tiingo_provider._ensure_session()
            
            # Run both scanners concurrently
            ibkr_task = self._run_ibkr_scanner() if self.ibkr_scanner else None
            tiingo_task = self._run_tiingo_scanner(min_gap_percent, min_price, max_price) if self.tiingo_provider else None
            
            # Wait for results
            ibkr_results = []
            tiingo_results = []
            
            if ibkr_task:
                try:
                    ibkr_results = await asyncio.wait_for(ibkr_task, timeout=self.config['timeout_seconds'])
                    self.scan_stats['ibkr_success'] += 1
                except asyncio.TimeoutError:
                    self.logger.warning("IBKR scanner timed out")
                except Exception as e:
                    self.logger.error(f"IBKR scanner error: {e}")
            
            if tiingo_task:
                try:
                    tiingo_results = await asyncio.wait_for(tiingo_task, timeout=self.config['timeout_seconds'])
                    self.scan_stats['tiingo_success'] += 1
                except asyncio.TimeoutError:
                    self.logger.warning("Tiingo scanner timed out")
                except Exception as e:
                    self.logger.error(f"Tiingo scanner error: {e}")
            
            # Combine and rank results
            hybrid_results = await self._combine_results(ibkr_results, tiingo_results)
            
            # Filter and rank
            filtered_results = self._filter_results(hybrid_results, min_gap_percent, min_volume_ratio)
            final_results = filtered_results[:max_results]
            
            self.logger.info(f"🎯 Hybrid scan complete: {len(final_results)} plays found")
            self.logger.info(f"   IBKR results: {len(ibkr_results)}")
            self.logger.info(f"   Tiingo results: {len(tiingo_results)}")
            self.logger.info(f"   Combined: {len(hybrid_results)}")
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Error in hybrid scan: {e}")
            self.scan_stats['failures'] += 1
            return []
        finally:
            # Cleanup Tiingo session
            if self.tiingo_provider:
                await self.tiingo_provider._close_session()
    
    async def _run_ibkr_scanner(self) -> List[IBKRScanResult]:
        """Run IBKR native scanner"""
        try:
            self.logger.info("   📊 Running IBKR scanner...")
            results = await self.ibkr_scanner.scan_daily_plays(max_results=50)
            self.logger.info(f"   ✅ IBKR found {len(results)} candidates")
            return results
        except Exception as e:
            self.logger.error(f"IBKR scanner failed: {e}")
            return []
    
    async def _run_tiingo_scanner(self, min_gap_percent: float, min_price: float, max_price: float) -> List[TiingoScanResult]:
        """Run Tiingo gap scanner"""
        try:
            self.logger.info("   📈 Running Tiingo scanner...")
            results = await self.tiingo_provider.scan_gap_movers(
                min_gap_percent=min_gap_percent,
                min_price=min_price,
                max_price=max_price,
                max_results=50
            )
            self.logger.info(f"   ✅ Tiingo found {len(results)} candidates")
            return results
        except Exception as e:
            self.logger.error(f"Tiingo scanner failed: {e}")
            return []
    
    async def _combine_results(self, 
                             ibkr_results: List[IBKRScanResult],
                             tiingo_results: List[TiingoScanResult]) -> List[HybridScanResult]:
        """
        Intelligently combine results from both sources
        """
        self.logger.info("   🔄 Combining results from both sources...")
        
        combined = []
        processed_symbols = set()
        
        # Process IBKR results first (preferred source)
        for ibkr_result in ibkr_results:
            symbol = ibkr_result.symbol
            
            # Find matching Tiingo result if available
            tiingo_match = None
            for tr in tiingo_results:
                if tr.symbol == symbol:
                    tiingo_match = tr
                    break
            
            # Create hybrid result
            hybrid = await self._create_hybrid_result(ibkr_result, tiingo_match)
            if hybrid:
                combined.append(hybrid)
                processed_symbols.add(symbol)
        
        # Process remaining Tiingo results (not in IBKR)
        for tiingo_result in tiingo_results:
            symbol = tiingo_result.symbol
            
            if symbol not in processed_symbols:
                # Tiingo-only result
                hybrid = await self._create_hybrid_result(None, tiingo_result)
                if hybrid:
                    combined.append(hybrid)
                    processed_symbols.add(symbol)
        
        self.logger.info(f"   ✅ Created {len(combined)} hybrid results")
        return combined
    
    async def _create_hybrid_result(self, 
                                  ibkr_result: Optional[IBKRScanResult],
                                  tiingo_result: Optional[TiingoScanResult]) -> Optional[HybridScanResult]:
        """
        Create hybrid result from available data sources
        """
        if not ibkr_result and not tiingo_result:
            return None
        
        # Determine primary source and data quality
        if ibkr_result and tiingo_result:
            # Both sources available - validate and merge
            if self.config['cross_validate']:
                is_valid = self._cross_validate_results(ibkr_result, tiingo_result)
                if not is_valid:
                    self.logger.warning(f"Cross-validation failed for {ibkr_result.symbol}")
            
            primary_source = DataSource.IBKR if self.config['prefer_ibkr'] else DataSource.TIINGO
            data_quality = 'HIGH'
            
            # Use IBKR data as primary
            symbol = ibkr_result.symbol
            current_price = ibkr_result.current_price
            previous_close = ibkr_result.previous_close
            gap_percentage = ibkr_result.gap_percentage
            volume = ibkr_result.volume
            avg_volume = ibkr_result.avg_volume
            
        elif ibkr_result:
            # IBKR only
            primary_source = DataSource.IBKR
            data_quality = 'HIGH'
            
            symbol = ibkr_result.symbol
            current_price = ibkr_result.current_price
            previous_close = ibkr_result.previous_close
            gap_percentage = ibkr_result.gap_percentage
            volume = ibkr_result.volume
            avg_volume = ibkr_result.avg_volume
            
        else:
            # Tiingo only
            primary_source = DataSource.TIINGO
            data_quality = 'MEDIUM'  # Slightly lower because no execution integration
            
            quote = tiingo_result.quote
            symbol = quote.symbol
            current_price = quote.last_price
            previous_close = quote.previous_close
            gap_percentage = quote.gap_percentage
            volume = quote.volume
            avg_volume = quote.avg_volume_30d
        
        # Calculate volume ratio
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        
        # Calculate scoring
        overall_score = self._calculate_hybrid_score(
            gap_percentage, volume_ratio, primary_source, data_quality
        )
        
        return HybridScanResult(
            symbol=symbol,
            current_price=current_price,
            previous_close=previous_close,
            gap_percentage=gap_percentage,
            volume=volume,
            avg_volume=avg_volume,
            volume_ratio=volume_ratio,
            primary_source=primary_source,
            data_quality=data_quality,
            overall_score=overall_score,
            gap_rank=0,  # Will be calculated after all results
            volume_rank=0,  # Will be calculated after all results
            market_session='premarket',  # Simplified
            timestamp=datetime.now(),
            ibkr_data=ibkr_result,
            tiingo_data=tiingo_result
        )
    
    def _cross_validate_results(self, ibkr: IBKRScanResult, tiingo: TiingoScanResult) -> bool:
        """
        Cross-validate results between IBKR and Tiingo
        Check for significant discrepancies
        """
        # Price validation
        price_diff = abs(ibkr.current_price - tiingo.quote.last_price)
        price_deviation = price_diff / ibkr.current_price if ibkr.current_price > 0 else 1.0
        
        if price_deviation > self.config['max_price_deviation']:
            self.logger.warning(f"Price deviation {price_deviation:.2%} for {ibkr.symbol}")
            return False
        
        # Gap validation (should be similar)
        gap_diff = abs(ibkr.gap_percentage - tiingo.quote.gap_percentage)
        if gap_diff > 0.05:  # 5% gap difference threshold
            self.logger.warning(f"Gap deviation {gap_diff:.2%} for {ibkr.symbol}")
            return False
        
        return True
    
    def _calculate_hybrid_score(self, gap_percentage: float, volume_ratio: float, 
                              source: DataSource, quality: str) -> float:
        """Calculate overall score for hybrid result"""
        # Base scoring
        gap_score = abs(gap_percentage) * 100  # 0-50+ points
        volume_score = min(volume_ratio * 20, 50)  # 0-50 points
        
        # Source bonus (IBKR preferred for execution)
        source_bonus = 0
        if source == DataSource.IBKR:
            source_bonus = 20
        elif source == DataSource.TIINGO:
            source_bonus = 15
        elif source == DataSource.HYBRID:
            source_bonus = 25  # Highest for validated hybrid data
        
        # Quality bonus
        quality_bonus = 0
        if quality == 'HIGH':
            quality_bonus = 15
        elif quality == 'MEDIUM':
            quality_bonus = 10
        elif quality == 'LOW':
            quality_bonus = 5
        
        return gap_score + volume_score + source_bonus + quality_bonus
    
    def _filter_results(self, results: List[HybridScanResult], 
                       min_gap_percent: float, min_volume_ratio: float) -> List[HybridScanResult]:
        """Filter and rank results"""
        # Filter by criteria
        filtered = []
        for result in results:
            if (abs(result.gap_percentage) >= min_gap_percent and
                result.volume_ratio >= min_volume_ratio and
                result.data_quality in ['HIGH', 'MEDIUM']):
                filtered.append(result)
        
        # Calculate ranks
        filtered.sort(key=lambda x: abs(x.gap_percentage), reverse=True)
        for i, result in enumerate(filtered):
            result.gap_rank = i + 1
        
        filtered.sort(key=lambda x: x.volume_ratio, reverse=True)
        for i, result in enumerate(filtered):
            result.volume_rank = i + 1
        
        # Final sort by overall score
        filtered.sort(key=lambda x: x.overall_score, reverse=True)
        
        return filtered
    
    def format_results(self, results: List[HybridScanResult]) -> str:
        """Format hybrid results for display"""
        if not results:
            return "No plays found meeting criteria."
        
        output = f"🎯 HYBRID SCANNER RESULTS ({len(results)} plays):\n"
        
        # Summary by source
        ibkr_count = sum(1 for r in results if r.primary_source == DataSource.IBKR)
        tiingo_count = sum(1 for r in results if r.primary_source == DataSource.TIINGO)
        hybrid_count = sum(1 for r in results if r.primary_source == DataSource.HYBRID)
        
        output += f"📊 Sources: IBKR({ibkr_count}) + Tiingo({tiingo_count}) + Hybrid({hybrid_count})\n"
        
        # Symbols list
        symbols = [r.symbol for r in results]
        output += f"📋 Symbols: {', '.join(symbols)}\n\n"
        
        # Detailed results
        output += "📈 DETAILED RESULTS:\n"
        for i, result in enumerate(results, 1):
            gap_direction = "↗" if result.gap_percentage > 0 else "↘"
            source_icon = {"IBKR": "🏦", "TIINGO": "📡", "HYBRID": "🔄"}[result.primary_source.value]
            
            output += f"{i}. {result.symbol} {gap_direction} (Score: {result.overall_score:.0f}) {source_icon}\n"
            output += f"   Gap: {result.gap_percentage*100:+.1f}% | Price: ${result.current_price:.2f}\n"
            output += f"   Volume: {result.volume:,} ({result.volume_ratio:.1f}x avg)\n"
            output += f"   Source: {result.primary_source.value} | Quality: {result.data_quality}\n"
            output += f"   Ranks: Gap #{result.gap_rank}, Volume #{result.volume_rank}\n\n"
        
        return output
    
    def get_scan_statistics(self) -> Dict[str, Any]:
        """Get scanning statistics"""
        total_scans = sum(self.scan_stats.values())
        
        return {
            'total_scans': total_scans,
            'success_rate': (total_scans - self.scan_stats['failures']) / total_scans * 100 if total_scans > 0 else 0,
            'source_stats': self.scan_stats.copy(),
            'data_sources': {
                'ibkr_available': self.ibkr_scanner is not None,
                'tiingo_available': self.tiingo_provider is not None
            }
        }