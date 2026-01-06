# scanner/ibkr_native_scanner.py
"""
IBKR Native Scanner - Reemplaza ProRealTime para scanning automático
Utiliza IBKR Market Scanner API para encontrar daily plays automáticamente
"""

import asyncio
import logging
import configparser
import os
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, time
from dataclasses import dataclass
import pandas as pd

from ib_insync import IB, ScannerSubscription, Contract, Stock, util
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

@dataclass
class IBKRScanResult:
    """Resultado de IBKR Market Scanner"""
    symbol: str
    contract: Contract
    rank: int
    distance: str  # Distance from filter criteria
    benchmark: str  # What triggered the scan
    projection: str  # Market projection
    legs: str  # Options legs if applicable
    
    # Additional data we'll fetch
    current_price: float = 0.0
    previous_close: float = 0.0
    gap_percentage: float = 0.0
    volume: int = 0
    avg_volume: int = 0
    market_cap: float = 0.0
    
    # Rel-Vol Intraday specific fields
    rel_vol_5min: float = 0.0           # 5-minute relative volume vs 5-day avg
    momentum_confirmed: bool = False     # Current 5min bar closes above open
    estimated_float: float = 0.0        # Estimated shares outstanding

class IBKRNativeScanner:
    """
    Scanner nativo de IBKR que reemplaza completamente ProRealTime
    
    Utiliza IBKR Market Scanner para encontrar:
    1. Gaps significativos (>8%)
    2. Volume surges (>2x average)  
    3. Pre-market movers
    4. Earnings movers
    5. News-driven moves
    """
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.logger = logging.getLogger(f"{__name__}.IBKRNativeScanner")
        
        # Use provided adapter or create new one
        self.ibkr = ibkr_adapter
        self._own_connection = ibkr_adapter is None
        
        if self._own_connection:
            self.ibkr = IBKRAdapter()
        
        # Load exchange filter from config.ini
        self.exchange_filter = self._load_exchange_filter()
        
        # Scanner configurations
        self.scan_configs = self._get_scanner_configurations()
        
        # Cache for avoiding duplicate API calls with timestamp tracking
        self._price_cache = {}
        self._volume_cache = {}
        self._fundamental_cache = {}
        
        # Adaptive cache refresh system - intervals adapt to market periods
        self._last_cache_refresh = datetime.now()
        
        # Import adaptive cache manager
        try:
            from core.adaptive_cache_manager import adaptive_cache_manager
            self._adaptive_cache_manager = adaptive_cache_manager
            self._use_adaptive_cache = True
            self.logger.info("🧠 Adaptive cache system enabled - intervals adjust by market period")
        except ImportError as e:
            # Fallback to fixed interval if adaptive manager not available
            self._cache_refresh_interval = 15 * 60  # 15 minutes fallback
            self._use_adaptive_cache = False
            self.logger.warning(f"⚠️ Adaptive cache not available ({e}), using fixed 15min intervals")
        
        self.logger.info(f"IBKR Native Scanner initialized - Exchange filter: {self.exchange_filter}")
        
        if self._use_adaptive_cache:
            self.logger.info("🔄 Adaptive cache refresh enabled - intervals adjust by market period")
        else:
            self.logger.info(f"🔄 Fixed cache refresh enabled: every {self._cache_refresh_interval // 60} minutes")
    
    def _check_and_refresh_cache(self) -> bool:
        """
        Check if cache should be refreshed using adaptive intervals
        Returns True if cache was refreshed
        """
        current_time = datetime.now()
        
        if self._use_adaptive_cache:
            # Use adaptive cache manager
            should_refresh, refresh_info = self._adaptive_cache_manager.should_refresh_cache(
                self._last_cache_refresh, current_time
            )
            
            if should_refresh:
                period_name = refresh_info['period_name']
                priority = refresh_info['priority']
                interval = refresh_info['required_interval_minutes']
                
                self.logger.info(f"🔄 Adaptive cache refresh triggered ({period_name}, {priority})")
                self.logger.info(f"   ⏱️ Interval: {interval:.1f}min, Time elapsed: {refresh_info['time_since_refresh_minutes']:.1f}min")
                
                # Clear all caches
                cache_sizes = {
                    'price': len(self._price_cache),
                    'volume': len(self._volume_cache), 
                    'fundamental': len(self._fundamental_cache)
                }
                
                self._price_cache.clear()
                self._volume_cache.clear()
                self._fundamental_cache.clear()
                self._last_cache_refresh = current_time
                
                total_cleared = sum(cache_sizes.values())
                self.logger.info(f"✅ Adaptive cache refreshed: cleared {total_cleared} entries ({cache_sizes})")
                return True
        else:
            # Fallback to fixed interval
            time_since_refresh = (current_time - self._last_cache_refresh).total_seconds()
            
            if time_since_refresh >= self._cache_refresh_interval:
                self.logger.info(f"🔄 Fixed cache refresh triggered after {time_since_refresh // 60:.1f} minutes")
                
                # Clear all caches
                cache_sizes = {
                    'price': len(self._price_cache),
                    'volume': len(self._volume_cache), 
                    'fundamental': len(self._fundamental_cache)
                }
                
                self._price_cache.clear()
                self._volume_cache.clear()
                self._fundamental_cache.clear()
                self._last_cache_refresh = current_time
                
                total_cleared = sum(cache_sizes.values())
                self.logger.info(f"✅ Fixed cache refreshed: cleared {total_cleared} entries ({cache_sizes})")
                return True
        
        return False
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get current cache status and timing information"""
        current_time = datetime.now()
        time_since_refresh = (current_time - self._last_cache_refresh).total_seconds()
        minutes_until_refresh = max(0, (self._cache_refresh_interval - time_since_refresh) // 60)
        
        return {
            'last_refresh': self._last_cache_refresh.isoformat(),
            'time_since_refresh_minutes': time_since_refresh // 60,
            'minutes_until_next_refresh': int(minutes_until_refresh),
            'cache_sizes': {
                'price': len(self._price_cache),
                'volume': len(self._volume_cache),
                'fundamental': len(self._fundamental_cache)
            },
            'refresh_interval_minutes': self._cache_refresh_interval // 60
        }
    
    def force_cache_refresh(self) -> bool:
        """
        Manually trigger cache refresh - useful for testing and manual refresh
        Returns True if cache was refreshed
        """
        cache_sizes = {
            'price': len(self._price_cache),
            'volume': len(self._volume_cache), 
            'fundamental': len(self._fundamental_cache)
        }
        
        # Clear all caches
        self._price_cache.clear()
        self._volume_cache.clear()
        self._fundamental_cache.clear()
        self._last_cache_refresh = datetime.now()
        
        total_cleared = sum(cache_sizes.values())
        self.logger.info(f"🔄 Manual IBKR cache refresh: cleared {total_cleared} entries ({cache_sizes})")
        self.logger.info("✅ Fresh market data will be fetched on next scan")
        
        return True
    
    def _load_exchange_filter(self) -> str:
        """Load exchange filter from config.ini"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
            config.read(config_path)
            
            exchange_filter = config.get('GLOBAL', 'exchange_filter', fallback='STK.NASDAQ')
            self.logger.info(f"Loaded exchange filter from config: {exchange_filter}")
            return exchange_filter
            
        except Exception as e:
            self.logger.warning(f"Could not load exchange filter from config: {e}, using default STK.NASDAQ")
            return 'STK.NASDAQ'
    
    def _get_scanner_configurations(self) -> List[Dict[str, Any]]:
        """
        Define scanner configurations for different types of daily plays
        """
        # REMOVED GAP_UP scanner - it's disabled and causes hanging
        return [
            {
                'name': 'volume_surge_movers',
                'scan_code': 'MOST_ACTIVE',
                'instrument': 'STK',
                'location_code': self.exchange_filter,
                'stock_type': 'ALL',
                'above_price': 0.5,
                'below_price': 15.0,
                'above_volume': 1000000,  # Higher volume threshold
                'market_cap_below': 2000,
                'exclude_convertible': True
            },
            {
                'name': 'premarket_gaps',
                'scan_code': 'GAP_UP',  # FIXED: Use gap scanner for premarket too
                'instrument': 'STK',
                'location_code': self.exchange_filter,
                'stock_type': 'ALL',
                'above_price': 0.5,
                'below_price': 15.0,
                'scan_time': 'PREMARKET',  # Pre-market specific
                'exclude_convertible': True
            },
            {
                'name': 'gap_down_movers',
                'scan_code': 'GAP_DOWN',  # Gap down for potential reversals
                'instrument': 'STK',
                'location_code': self.exchange_filter,
                'stock_type': 'ALL',
                'above_price': 0.5,
                'below_price': 15.0,
                'above_volume': 500000,
                'market_cap_below': 2000,
                'exclude_convertible': True
            },
            {
                'name': 'hot_by_price',
                'scan_code': 'HOT_BY_PRICE',
                'instrument': 'STK',
                'location_code': self.exchange_filter,
                'stock_type': 'ALL',
                'above_price': 0.5,
                'below_price': 15.0,
                'exclude_convertible': True
            },
            {
                'name': 'rel_vol_intraday',
                'scan_code': 'MOST_ACTIVE',  # Base: most active for volume
                'instrument': 'STK',
                'location_code': self.exchange_filter,
                'stock_type': 'ALL',
                'above_price': 1.0,         # $1-$10 range for nano/low float
                'below_price': 10.0,
                'above_volume': 200000,     # Min volume for 5min calculations
                'market_cap_below': 500,    # <$500M for true small/nano caps
                'exclude_convertible': True,
                'requires_custom_filtering': True,  # Flag for custom rel-vol logic
                'target_rel_vol': 3.0,     # Target: 5min volume ≥ 3x avg 5min
                'max_float': 50000000      # Float ≤ 50M
            }
        ]
    
    async def scan_daily_plays(self, max_results: int = 50) -> List[IBKRScanResult]:
        """
        Main scanning function - finds daily plays using IBKR Market Scanner
        
        Args:
            max_results: Maximum number of results to return
            
        Returns:
            List of IBKRScanResult objects with enhanced data
        """
        self.logger.info("🔍 Starting IBKR Native Scanner...")
        
        try:
            # Check and refresh cache if needed (15-minute intervals)
            cache_refreshed = self._check_and_refresh_cache()
            if cache_refreshed:
                self.logger.info("🔄 Fresh market data will be fetched due to cache refresh")
            
            # Ensure connection
            if not await self._ensure_connection():
                self.logger.error("Failed to connect to IBKR")
                return []
            
            all_results = []
            
            # Run each scanner configuration SEQUENTIALLY with proper cleanup
            for i, config in enumerate(self.scan_configs):
                try:
                    self.logger.info(f"   📊 Running scanner: {config['name']}")
                    results = await self._run_scanner_config(config)
                    self.logger.info(f"   📊 Scanner {config['name']} returned {len(results)} results")
                    all_results.extend(results)
                    
                    # INCREASED delay to ensure IBKR processes cancellations
                    if i < len(self.scan_configs) - 1:  # Don't wait after last scanner
                        await asyncio.sleep(3)  # Increased from 2 to 3 seconds
                    
                except Exception as e:
                    self.logger.error(f"Error in scanner {config['name']}: {e}")
                    # Still wait on error to prevent cascading failures
                    await asyncio.sleep(1)
                    continue
            
            # Check if we got any results from scanners
            self.logger.info(f"🔍 Total results from all scanners: {len(all_results)}")
            
            if not all_results:
                self.logger.warning("⚠️ No results from IBKR scanners - using fallback method")
                # Fallback: create some basic scan results from recent movers
                all_results = await self._create_fallback_results()
                self.logger.info(f"📋 Fallback provided {len(all_results)} results")
            
            # Remove duplicates and rank by quality
            self.logger.info("🔄 Starting deduplication...")
            unique_results = self._deduplicate_results(all_results)
            self.logger.info(f"✅ Deduplication complete: {len(unique_results)} unique results")
            
            # Enhance with additional data (skip volume data if causing issues)
            self.logger.info("🔄 Starting enhancement...")
            enhanced_results = await self._enhance_scan_results(unique_results)
            self.logger.info(f"✅ Enhancement complete: {len(enhanced_results)} enhanced results")
            
            # Filter and rank
            self.logger.info("🔄 Starting filtering and ranking...")
            filtered_results = self._filter_and_rank_results(enhanced_results)
            self.logger.info(f"✅ Filtering complete: {len(filtered_results)} filtered results")
            
            # Limit results
            final_results = filtered_results[:max_results]
            
            self.logger.info(f"🎯 IBKR Scanner found {len(final_results)} daily plays")
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Error in scan_daily_plays: {e}")
            return []
    
    async def _ensure_connection(self) -> bool:
        """Ensure IBKR connection is active"""
        try:
            if not self.ibkr.is_connected():
                await self.ibkr.connect()
            return self.ibkr.is_connected()
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
    
    async def _run_scanner_config(self, config: Dict[str, Any]) -> List[IBKRScanResult]:
        """Run a single scanner configuration"""
        try:
            # Create scanner subscription
            scanner_sub = ScannerSubscription(
                instrument=config['instrument'],
                locationCode=config['location_code'],
                scanCode=config['scan_code'],
                abovePrice=config.get('above_price'),
                belowPrice=config.get('below_price'),
                aboveVolume=config.get('above_volume'),
                marketCapBelow=config.get('market_cap_below'),
                stockTypeFilter=config.get('stock_type', 'ALL')
            )
            
            # Request scanner data with reduced timeout
            scanner_data = await asyncio.wait_for(
                self._request_scanner_data(scanner_sub),
                timeout=5.0  # Reduced to 5 seconds - fail fast
            )
            
            results = []
            for scan_data in scanner_data:
                try:
                    # Debug: log the actual structure of scan_data
                    self.logger.debug(f"ScanData attributes: {dir(scan_data)}")
                    
                    # The correct attributes for ib_insync ScanData are:
                    # contractDetails, rank, distance, benchmark, projection, legsStr
                    contract = scan_data.contractDetails.contract if hasattr(scan_data, 'contractDetails') else None
                    
                    if contract is None:
                        self.logger.warning(f"No contract found in scan data")
                        continue
                    
                    result = IBKRScanResult(
                        symbol=contract.symbol,
                        contract=contract,
                        rank=getattr(scan_data, 'rank', 0),
                        distance=getattr(scan_data, 'distance', ''),
                        benchmark=getattr(scan_data, 'benchmark', ''),
                        projection=getattr(scan_data, 'projection', ''),
                        legs=getattr(scan_data, 'legsStr', '')  # Note: legsStr not legs
                    )
                    results.append(result)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing scan result: {e}")
                    # Log more details for debugging
                    self.logger.debug(f"ScanData object: {scan_data}")
                    continue
            
            # Apply custom filtering for rel-vol intraday scanner
            if config.get('requires_custom_filtering') and config['name'] == 'rel_vol_intraday':
                results = await self._apply_rel_vol_filtering(results, config)
            
            return results
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Scanner {config['name']} timed out - likely subscription cancelled")
            return []
        except Exception as e:
            self.logger.error(f"Error running scanner {config['name']}: {e}")
            return []
    
    async def _request_scanner_data(self, scanner_sub: ScannerSubscription) -> List:
        """Make scanner request to IBKR with proper error handling"""
        try:
            ib = self.ibkr.ib
            
            # Request scanner data with timeout
            scanner_data = await asyncio.wait_for(
                ib.reqScannerDataAsync(scanner_sub),
                timeout=5.0  # Increased timeout for better reliability
            )
            
            return scanner_data if scanner_data else []
            
        except asyncio.TimeoutError:
            self.logger.warning("Scanner request timed out")
            return []
        except Exception as e:
            # Handle specific IBKR errors
            if "322" in str(e) and "10 simultaneous" in str(e):
                self.logger.warning("⚠️ IBKR scanner limit reached - waiting for cleanup")
                await asyncio.sleep(2)  # Wait for automatic cleanup
                return []
            elif "162" in str(e) or "cancelled" in str(e).lower():
                # Error 162 is normal - means scanner completed and was auto-cancelled
                self.logger.debug("Scanner auto-cancelled by IBKR (normal)")
                return []
            else:
                self.logger.error(f"Scanner error: {e}")
                return []
    
    
    def _deduplicate_results(self, results: List[IBKRScanResult]) -> List[IBKRScanResult]:
        """Remove duplicate symbols, keeping the best ranked one"""
        seen_symbols = {}
        
        for result in results:
            symbol = result.symbol
            
            if symbol not in seen_symbols or result.rank < seen_symbols[symbol].rank:
                seen_symbols[symbol] = result
        
        return list(seen_symbols.values())
    
    async def _create_fallback_results(self) -> List[IBKRScanResult]:
        """Create fallback scan results when IBKR scanners fail"""
        fallback_results = []
        
        # List of active smallcap symbols to scan as fallback
        fallback_symbols = [
            'AMC', 'SNDL', 'AAPL', 'TSLA', 'GME', 'PLTR', 'NIO', 'F', 'SOFI', 'WISH',
            'CLOV', 'BB', 'NOK', 'SENS', 'CLNE', 'RKT', 'UWMC', 'WKHS', 'RIDE', 'SPCE'
        ]
        
        try:
            ib = self.ibkr.ib
            
            for symbol in fallback_symbols[:10]:  # Limit to 10 symbols
                try:
                    # Create stock contract
                    contract = Stock(symbol, 'SMART', 'USD')
                    
                    # Create basic scan result
                    scan_result = IBKRScanResult(
                        rank=len(fallback_results) + 1,
                        contract=contract,
                        distance="",
                        benchmark="",
                        projection="",
                        scanner_name="fallback"
                    )
                    
                    fallback_results.append(scan_result)
                    
                except Exception as e:
                    self.logger.debug(f"Error creating fallback result for {symbol}: {e}")
                    continue
                    
            self.logger.info(f"✅ Created {len(fallback_results)} fallback scan results")
            return fallback_results
            
        except Exception as e:
            self.logger.error(f"Error creating fallback results: {e}")
            return []
    
    async def _enhance_scan_results(self, results: List[IBKRScanResult]) -> List[IBKRScanResult]:
        """Enhance scan results with additional market data"""
        enhanced_results = []
        
        self.logger.info(f"🔍 Enhancing {len(results)} results...")
        
        for i, result in enumerate(results):
            try:
                # Get current price and gap data
                price_data = await self._get_price_data(result.contract)
                
                # Skip symbols with no price data
                if price_data.get('current_price') is None or price_data.get('current_price') == 0.0:
                    self.logger.warning(f"Skipping {result.symbol}: No price data available")
                    continue
                    
                result.current_price = price_data.get('current_price', 0.0)
                result.previous_close = price_data.get('previous_close', result.current_price)
                
                # Calculate gap percentage
                if result.previous_close > 0:
                    result.gap_percentage = (result.current_price - result.previous_close) / result.previous_close
                
                # Get volume data from the same price request (more reliable)
                result.volume = price_data.get('current_volume', 0)
                
                # For avg_volume, use reasonable defaults based on market cap/price
                if result.volume > 0:
                    # If we have current volume, estimate avg volume
                    result.avg_volume = max(result.volume // 2, 100_000)  # Conservative estimate
                else:
                    # Use default values for volume ratio calculations
                    result.volume = 50_000  # Reasonable default for smallcaps
                    result.avg_volume = 100_000  # Default average
                
                # Get fundamental data
                fundamental_data = await self._get_fundamental_data(result.contract)
                result.market_cap = fundamental_data.get('market_cap', 0.0)
                
                enhanced_results.append(result)
                
                # Progress logging every 25 results  
                if (i + 1) % 25 == 0:
                    self.logger.info(f"   📊 Enhanced {i + 1}/{len(results)} results...")
                
                # Rate limiting
                await asyncio.sleep(0.1)  # Reduced from 0.5 to 0.1
                
            except Exception as e:
                self.logger.warning(f"Error enhancing {result.symbol}: {e}")
                # Add with default values
                enhanced_results.append(result)
                continue
        
        return enhanced_results
    
    async def _get_price_data(self, contract: Contract) -> Dict[str, float]:
        """Get current price and previous close for contract"""
        symbol = contract.symbol
        
        if symbol in self._price_cache:
            return self._price_cache[symbol]
        
        try:
            # Request market data with timeout
            ib = self.ibkr.ib
            
            # Use timeout to avoid hanging
            async def get_market_data():
                ib.reqMktData(contract, '', False, False)
                await asyncio.sleep(1.5)  # Increased wait time for better data
                ticker = ib.ticker(contract)
                ib.cancelMktData(contract)
                return ticker
            
            ticker = await asyncio.wait_for(get_market_data(), timeout=3.0)
            
            # Better price extraction with fallbacks
            current_price = 0.0
            current_volume = 0
            if ticker:
                # Try multiple price sources
                current_price = (
                    ticker.marketPrice() or 
                    ticker.last or 
                    ticker.bid or 
                    ticker.ask or 
                    ticker.close or 
                    0.0
                )
                
                # Get volume from the same ticker
                current_volume = ticker.volume if ticker.volume and ticker.volume > 0 else 0
                
            previous_close = ticker.close if ticker else 0.0
            
            # If still no price, try alternative method
            if current_price == 0.0:
                try:
                    # Try getting last trade price via historical data
                    bars = await ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime='',
                        durationStr='1 D',
                        barSizeSetting='1 min',
                        whatToShow='TRADES',
                        useRTH=False,
                        formatDate=1
                    )
                    if bars:
                        current_price = float(bars[-1].close)
                        if previous_close == 0.0:
                            previous_close = float(bars[0].open)
                except:
                    pass
            
            price_data = {
                'current_price': current_price,
                'previous_close': previous_close,
                'current_volume': current_volume
            }
            
            self._price_cache[symbol] = price_data
            return price_data
            
        except Exception as e:
            self.logger.warning(f"Error getting price data for {symbol}: {e}")
            # Don't return 0.0 - return None to indicate no data
            return {'current_price': None, 'previous_close': None}
    
    async def _get_volume_data(self, contract: Contract) -> Dict[str, int]:
        """Get volume data for contract"""
        symbol = contract.symbol
        
        if symbol in self._volume_cache:
            return self._volume_cache[symbol]
        
        try:
            # Request historical data for volume analysis
            ib = self.ibkr.ib
            
            bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='5 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if bars:
                # Current volume (today's volume)
                current_volume = int(bars[-1].volume) if bars else 0
                
                # Average volume (last 5 days)
                volumes = [int(bar.volume) for bar in bars[:-1]]  # Exclude today
                avg_volume = sum(volumes) // len(volumes) if volumes else 100000  # Default fallback
                
                volume_data = {
                    'current_volume': current_volume,
                    'avg_volume': avg_volume
                }
                
                self._volume_cache[symbol] = volume_data
                return volume_data
            
        except Exception as e:
            self.logger.warning(f"Error getting volume data for {symbol}: {e}")
        
        return {'current_volume': 50000, 'avg_volume': 100000}  # Reasonable defaults
    
    async def _get_fundamental_data(self, contract: Contract) -> Dict[str, float]:
        """Get fundamental data like market cap"""
        symbol = contract.symbol
        
        if symbol in self._fundamental_cache:
            return self._fundamental_cache[symbol]
        
        try:
            # Request fundamental data
            ib = self.ibkr.ib
            
            # This is a simplified version - IBKR fundamental data is complex
            fundamental_data = {
                'market_cap': 500_000_000  # Default estimate for smallcaps
            }
            
            self._fundamental_cache[symbol] = fundamental_data
            return fundamental_data
            
        except Exception as e:
            self.logger.warning(f"Error getting fundamental data for {symbol}: {e}")
            return {'market_cap': 500_000_000}
    
    def _filter_and_rank_results(self, results: List[IBKRScanResult]) -> List[IBKRScanResult]:
        """Filter and rank results by quality for daily plays"""
        filtered = []
        
        for result in results:
            # NASDAQ Smallcap specific filters
            # Price range for smallcaps: $1-$10 (typical smallcap range)
            if result.current_price < 1.0 or result.current_price > 10.0:
                continue
            
            # Smallcaps can move with smaller gaps - 3% is significant
            if abs(result.gap_percentage) < 0.03:  # Less than 3% gap
                continue
            
            # Smallcaps typically have lower volume than large caps
            if hasattr(result, 'volume') and result.volume > 0 and result.volume < 50_000:  # 50K minimum
                continue
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(result)
            result.quality_score = quality_score
            
            filtered.append(result)
        
        # Sort by quality score
        filtered.sort(key=lambda r: r.quality_score, reverse=True)
        
        return filtered
    
    def _calculate_quality_score(self, result: IBKRScanResult) -> float:
        """Calculate quality score for ranking results"""
        score = 0.0
        
        # Gap score (0-30 points)
        gap_abs = abs(result.gap_percentage)
        if gap_abs > 0.25:  # 25%+
            score += 30
        elif gap_abs > 0.15:  # 15%+
            score += 20
        elif gap_abs > 0.08:  # 8%+
            score += 10
        
        # Volume score (0-30 points)
        if result.avg_volume > 0:
            volume_ratio = result.volume / result.avg_volume
            if volume_ratio > 5.0:  # 5x volume
                score += 30
            elif volume_ratio > 3.0:  # 3x volume
                score += 20
            elif volume_ratio > 2.0:  # 2x volume
                score += 10
        
        # Price range preference (0-20 points)
        if 1.0 <= result.current_price <= 8.0:  # Sweet spot for smallcaps
            score += 20
        elif 0.5 <= result.current_price <= 15.0:
            score += 10
        
        # Ranking bonus (0-20 points)
        if result.rank <= 10:
            score += 20 - result.rank
        
        return score
    
    async def get_formatted_results(self, results: List[IBKRScanResult]) -> str:
        """Format results for display"""
        if not results:
            return "No daily plays found in IBKR scanner."
        
        output = f"🎯 IBKR NATIVE SCANNER ({len(results)} plays found):\n"
        
        # Symbols for easy copy-paste
        symbols = [r.symbol for r in results]
        output += f"📋 Symbols: {', '.join(symbols)}\n\n"
        
        # Detailed breakdown
        output += "📊 SCAN DETAILS:\n"
        for i, result in enumerate(results, 1):
            gap_direction = "↗" if result.gap_percentage > 0 else "↘"
            volume_multiple = result.volume / result.avg_volume if result.avg_volume > 0 else 0
            
            output += f"{i}. {result.symbol} {gap_direction} (Score: {result.quality_score:.0f})\n"
            output += f"   Gap: {result.gap_percentage*100:+.1f}% | Price: ${result.current_price:.2f}\n"
            output += f"   Volume: {result.volume:,} ({volume_multiple:.1f}x avg)\n"
            
            # Add rel-vol specific info if available
            if hasattr(result, 'rel_vol_5min') and result.rel_vol_5min > 0:
                momentum_icon = "🚀" if result.momentum_confirmed else "⏸️"
                output += f"   🔥 Rel-Vol 5min: {result.rel_vol_5min:.1f}x | Float: {result.estimated_float/1e6:.0f}M | Momentum: {momentum_icon}\n"
            
            output += f"   IBKR Rank: #{result.rank} | Scan: {result.benchmark}\n\n"
        
        return output
    
    async def disconnect(self):
        """Disconnect from IBKR if we own the connection"""
        if self._own_connection and self.ibkr:
            await self.ibkr.disconnect()
    
    async def _apply_rel_vol_filtering(self, results: List[IBKRScanResult], config: Dict[str, Any]) -> List[IBKRScanResult]:
        """
        Apply Rel-Vol intraday filtering logic:
        - 5min volume ≥ 3x avg 5min volume (5-day)
        - Float ≤ 50M
        - Momentum confirmation (closes above open)
        """
        self.logger.info(f"🔍 Applying Rel-Vol filtering to {len(results)} candidates...")
        
        filtered_results = []
        target_rel_vol = config.get('target_rel_vol', 3.0)
        max_float = config.get('max_float', 50000000)
        
        for result in results:
            try:
                # Get 5-minute intraday rel-vol data
                rel_vol_data = await self._calculate_5min_rel_vol(result.contract)
                
                if not rel_vol_data:
                    continue
                
                # Filter 1: 5min rel-vol ≥ target (3x default)
                current_5min_rel_vol = rel_vol_data.get('rel_vol_5min', 0.0)
                if current_5min_rel_vol < target_rel_vol:
                    self.logger.debug(f"{result.symbol}: Rel-vol {current_5min_rel_vol:.1f}x < {target_rel_vol}x required")
                    continue
                
                # Filter 2: Float ≤ 50M (simplified - would need real float data)
                estimated_float = rel_vol_data.get('estimated_float', max_float + 1)
                if estimated_float > max_float:
                    self.logger.debug(f"{result.symbol}: Float {estimated_float/1e6:.0f}M > {max_float/1e6:.0f}M limit")
                    continue
                
                # Filter 3: Momentum confirmation (current 5min candle closes above open)
                momentum_confirmed = rel_vol_data.get('momentum_confirmed', False)
                if not momentum_confirmed:
                    self.logger.debug(f"{result.symbol}: No momentum confirmation (not closing above open)")
                    continue
                
                # Passed all filters - add rel-vol specific data
                result.rel_vol_5min = current_5min_rel_vol
                result.momentum_confirmed = momentum_confirmed
                result.estimated_float = estimated_float
                
                filtered_results.append(result)
                self.logger.info(f"✅ {result.symbol}: Rel-Vol {current_5min_rel_vol:.1f}x, Float {estimated_float/1e6:.0f}M, Momentum ✓")
                
            except Exception as e:
                self.logger.warning(f"Error filtering {result.symbol}: {e}")
                continue
        
        self.logger.info(f"🎯 Rel-Vol filtering: {len(filtered_results)}/{len(results)} symbols passed")
        return filtered_results
    
    async def _calculate_5min_rel_vol(self, contract: Contract) -> Optional[Dict[str, Any]]:
        """
        Calculate 5-minute relative volume vs 5-day average
        
        Returns:
            Dict with rel_vol_5min, momentum_confirmed, estimated_float
        """
        try:
            ib = self.ibkr.ib
            
            # Get current 5-minute bar data
            current_5min_bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='5 mins',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not current_5min_bars or len(current_5min_bars) < 2:
                return None
            
            # Get 5-day average for 5-minute bars (same time of day)
            historical_5min_bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='5 D',
                barSizeSetting='5 mins',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not historical_5min_bars:
                return None
            
            # Calculate rel-vol: current 5min volume / avg 5min volume (same time)
            current_bar = current_5min_bars[-1]
            current_5min_volume = current_bar.volume
            
            # Get same time bars from previous days
            current_time = current_bar.date.time()
            same_time_volumes = []
            
            for bar in historical_5min_bars:
                # Compare time (allowing 5min window)
                bar_time = bar.date.time()
                time_diff = abs((bar.date.hour * 60 + bar.date.minute) - (current_time.hour * 60 + current_time.minute))
                
                if time_diff <= 5 and bar.volume > 0:  # Same 5min window
                    same_time_volumes.append(bar.volume)
            
            if not same_time_volumes:
                return None
            
            # Calculate average volume for this time period
            avg_5min_volume = sum(same_time_volumes) / len(same_time_volumes)
            rel_vol_5min = current_5min_volume / avg_5min_volume if avg_5min_volume > 0 else 0.0
            
            # Momentum confirmation: current bar closes above open
            momentum_confirmed = current_bar.close > current_bar.open
            
            # Estimate float (simplified - would use real data in production)
            # For now, estimate based on volume patterns
            total_daily_volume = sum(bar.volume for bar in current_5min_bars)
            estimated_float = min(total_daily_volume * 10, 100_000_000)  # Conservative estimate
            
            return {
                'rel_vol_5min': rel_vol_5min,
                'momentum_confirmed': momentum_confirmed,
                'estimated_float': estimated_float,
                'current_5min_volume': current_5min_volume,
                'avg_5min_volume': avg_5min_volume
            }
            
        except Exception as e:
            self.logger.warning(f"Error calculating 5min rel-vol for {contract.symbol}: {e}")
            return None

    def __del__(self):
        """Cleanup on destruction"""
        try:
            if self._own_connection and self.ibkr:
                # Don't create async tasks in destructor - just log cleanup needed
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("IBKRNativeScanner destructor: connection cleanup skipped (use explicit disconnect())")
        except:
            pass