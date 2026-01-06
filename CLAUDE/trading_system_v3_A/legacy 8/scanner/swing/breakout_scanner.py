"""
Breakout Scanner (Qullamaggie-style)

Scans for leading stocks making consolidation breakouts after big moves.

Strategy Pattern:
1. Big move higher (30-100%+) in past 1-3 months
2. Orderly pullback/consolidation with higher lows (2 weeks to 2 months)
3. Price "surfing" 10-day, 20-day (sometimes 50-day) MA
4. Range expansion breakout with volume

Universe Selection:
- Top 1-2% performers over 1-month, 3-month, and 6-month timeframes
- Leading stocks in current market environment

Data Source:
- Yahoo Finance for historical returns and MA calculations
- IBKR for real-time validation
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from yahooquery import Ticker, Screener
import pandas as pd
import numpy as np

class BreakoutScanner:
    """
    Scanner for Qullamaggie-style consolidation breakouts.

    Identifies stocks that:
    1. Are top performers (1-2%) over 1M, 3M, 6M
    2. Made a big move (30-100%+) recently
    3. Are consolidating orderly (higher lows, tightening range)
    4. Are near breakout from consolidation (surfing 10/20-day MA)
    """

    def __init__(self, ibkr_adapter=None, logger=None):
        self.logger = logger or logging.getLogger("BreakoutScanner")
        self.ibkr_adapter = ibkr_adapter

        # Performance Thresholds (Top Performers)
        self.min_1m_gain_pct = 15.0      # Top ~5% = 15%+ in 1 month
        self.min_3m_gain_pct = 30.0      # Top ~2% = 30%+ in 3 months
        self.min_6m_gain_pct = 50.0      # Top ~1% = 50%+ in 6 months

        # Move Characteristics
        self.min_big_move_pct = 30.0     # Minimum "big move" = 30%
        self.max_big_move_days = 60      # Big move should be within 60 days

        # Consolidation Characteristics
        self.min_consolidation_days = 10  # Minimum 10 days (2 weeks)
        self.max_consolidation_days = 60  # Maximum 60 days (2 months)
        self.max_consolidation_depth_pct = 50.0  # Max 50% pullback from high

        # Price/MA Relationship
        self.ma_periods = [10, 20, 50]   # Track 10, 20, 50-day MAs
        self.max_distance_from_ma_pct = 5.0  # Should be within 5% of MA

        # Breakout Criteria
        self.min_volume_ratio = 1.5      # 1.5x average volume on breakout
        self.max_distance_to_breakout_pct = 3.0  # Within 3% of breakout level

        # Universe Filters
        self.min_price = 5.0             # Min $5 (avoid penny stocks)
        self.max_price = 100.0           # Max $100
        self.min_avg_volume = 500000     # Min 500K average volume (liquidity)
        self.min_market_cap = 100_000_000  # Min $100M market cap

        self.logger.info("📈🔥 Breakout Scanner (Qullamaggie) initialized")
        self.logger.info(f"   Performance Thresholds: 1M>{self.min_1m_gain_pct}%, 3M>{self.min_3m_gain_pct}%, 6M>{self.min_6m_gain_pct}%")

    async def scan_eod_breakouts(self) -> List[Dict[str, Any]]:
        """
        EOD scan for breakout setups.

        Returns:
            List of breakout opportunities with setup data
        """
        try:
            self.logger.info("🔍 Starting EOD Breakout Scan...")

            # 1. Get Top Performers Universe
            candidates = await self._get_top_performers()

            if not candidates:
                self.logger.warning("⚠️ No top performers found")
                return []

            self.logger.info(f"✅ Found {len(candidates)} top performers to analyze")

            # 2. Analyze Each Candidate
            breakout_opportunities = []
            for symbol in candidates:
                opportunity = await self._analyze_breakout_setup(symbol)
                if opportunity:
                    breakout_opportunities.append(opportunity)

            self.logger.info(f"🎯 Found {len(breakout_opportunities)} breakout setups")
            return breakout_opportunities

        except Exception as e:
            self.logger.error(f"❌ Error in scan_eod_breakouts: {e}", exc_info=True)
            return []

    async def _get_top_performers(self) -> List[str]:
        """
        Get top 1-2% performing stocks over multiple timeframes.

        Uses Yahoo Finance Screener API and manual filtering.
        """
        try:
            loop = asyncio.get_event_loop()
            symbols = await loop.run_in_executor(None, self._get_top_performers_sync)
            return symbols
        except Exception as e:
            self.logger.error(f"❌ Error getting top performers: {e}")
            return []

    def _get_top_performers_sync(self) -> List[str]:
        """Synchronous implementation of top performers fetch"""
        try:
            # Use Yahoo Finance Screener for most active stocks with gains
            # Screener ID for "Day Gainers" or "Most Actives"
            screener = Screener()

            # Get multiple screener results and merge
            symbols_set = set()

            # Day Gainers (potential candidates)
            try:
                day_gainers = screener.get_screeners('day_gainers', count=250)
                if 'quotes' in day_gainers.get('day_gainers', {}):
                    for quote in day_gainers['day_gainers']['quotes']:
                        symbol = quote.get('symbol')
                        if symbol and '.' not in symbol:  # Avoid ADRs
                            symbols_set.add(symbol)
            except:
                pass

            # Most Actives (volume leaders)
            try:
                most_active = screener.get_screeners('most_actives', count=250)
                if 'quotes' in most_active.get('most_actives', {}):
                    for quote in most_active['most_actives']['quotes']:
                        symbol = quote.get('symbol')
                        if symbol and '.' not in symbol:
                            symbols_set.add(symbol)
            except:
                pass

            # Growth Technology Stocks (potential leaders)
            try:
                growth_tech = screener.get_screeners('growth_technology_stocks', count=250)
                if 'quotes' in growth_tech.get('growth_technology_stocks', {}):
                    for quote in growth_tech['growth_technology_stocks']['quotes']:
                        symbol = quote.get('symbol')
                        if symbol and '.' not in symbol:
                            symbols_set.add(symbol)
            except:
                pass

            symbols = list(symbols_set)
            self.logger.info(f"📊 Screener returned {len(symbols)} candidates")

            # Filter by performance metrics
            filtered = self._filter_by_performance(symbols)
            return filtered

        except Exception as e:
            self.logger.error(f"Error in _get_top_performers_sync: {e}")
            return []

    def _filter_by_performance(self, symbols: List[str]) -> List[str]:
        """
        Filter symbols by 1M, 3M, 6M performance.
        Keep only top performers.
        """
        if not symbols:
            return []

        try:
            # Fetch historical data for all symbols
            ticker = Ticker(symbols, asynchronous=True)

            # Get end date (today) and start date (6 months ago)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)

            # Fetch history
            history = ticker.history(start=start_date, end=end_date, interval='1d')

            if history is None or history.empty:
                return []

            top_performers = []

            for symbol in symbols:
                try:
                    if symbol not in history.index.get_level_values(0):
                        continue

                    df = history.loc[symbol].copy()

                    if df.empty or len(df) < 20:
                        continue

                    # Calculate returns
                    current_price = df['close'].iloc[-1]

                    # 1-month return
                    month_ago_idx = max(0, len(df) - 20)
                    price_1m_ago = df['close'].iloc[month_ago_idx]
                    return_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100 if price_1m_ago > 0 else 0

                    # 3-month return
                    three_months_ago_idx = max(0, len(df) - 60)
                    price_3m_ago = df['close'].iloc[three_months_ago_idx]
                    return_3m = ((current_price - price_3m_ago) / price_3m_ago) * 100 if price_3m_ago > 0 else 0

                    # 6-month return
                    price_6m_ago = df['close'].iloc[0]
                    return_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100 if price_6m_ago > 0 else 0

                    # Check if it meets ANY of the performance thresholds (OR logic)
                    is_top_performer = (
                        return_1m >= self.min_1m_gain_pct or
                        return_3m >= self.min_3m_gain_pct or
                        return_6m >= self.min_6m_gain_pct
                    )

                    if is_top_performer:
                        self.logger.debug(f"✅ {symbol}: Top Performer (1M: {return_1m:.1f}%, 3M: {return_3m:.1f}%, 6M: {return_6m:.1f}%)")
                        top_performers.append(symbol)

                except Exception as e:
                    continue

            self.logger.info(f"🎯 Filtered to {len(top_performers)} top performers")
            return top_performers

        except Exception as e:
            self.logger.error(f"Error filtering by performance: {e}")
            return []

    async def _analyze_breakout_setup(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single symbol for breakout setup.

        Returns opportunity dict if setup is valid, None otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            opportunity = await loop.run_in_executor(None, self._analyze_breakout_setup_sync, symbol)
            return opportunity
        except Exception as e:
            self.logger.debug(f"Error analyzing {symbol}: {e}")
            return None

    def _analyze_breakout_setup_sync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Synchronous breakout analysis"""
        try:
            # Fetch 6 months of daily data
            ticker = Ticker(symbol, asynchronous=False)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)

            df = ticker.history(start=start_date, end=end_date, interval='1d')

            if df is None or df.empty or len(df) < 60:
                return None

            # Calculate indicators
            df['ma_10'] = df['close'].rolling(window=10).mean()
            df['ma_20'] = df['close'].rolling(window=20).mean()
            df['ma_50'] = df['close'].rolling(window=50).mean()
            df['volume_ma'] = df['volume'].rolling(window=20).mean()

            # Current values
            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume_ma'].iloc[-1]

            # 1. Price Filters
            if current_price < self.min_price or current_price > self.max_price:
                return None

            # 2. Volume Filter
            if avg_volume < self.min_avg_volume:
                return None

            # 3. Find the "Big Move"
            big_move_data = self._find_big_move(df)
            if not big_move_data:
                return None

            # 4. Analyze Consolidation
            consolidation_data = self._analyze_consolidation(df, big_move_data['peak_idx'])
            if not consolidation_data:
                return None

            # 5. Check MA Relationship (surfing 10/20-day MA)
            ma_data = self._check_ma_relationship(df)
            if not ma_data:
                return None

            # 6. Calculate Breakout Proximity
            breakout_level = consolidation_data['resistance']
            distance_to_breakout_pct = ((breakout_level - current_price) / current_price) * 100

            if distance_to_breakout_pct > self.max_distance_to_breakout_pct:
                return None  # Too far from breakout

            # 7. Calculate Quality Score
            quality_score = self._calculate_quality_score(
                big_move_data,
                consolidation_data,
                ma_data,
                distance_to_breakout_pct
            )

            # 8. Create Opportunity
            opportunity = {
                'symbol': symbol,
                'opportunity_type': 'BREAKOUT',
                'strategy_targets': ['breakout'],
                'current_price': float(current_price),
                'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                'quality_score': quality_score,
                'breakout_data': {
                    'big_move_pct': big_move_data['move_pct'],
                    'big_move_days': big_move_data['move_days'],
                    'consolidation_days': consolidation_data['days'],
                    'consolidation_depth_pct': consolidation_data['depth_pct'],
                    'resistance': float(breakout_level),
                    'support': float(consolidation_data['support']),
                    'distance_to_breakout_pct': float(distance_to_breakout_pct),
                    'ma_10': float(df['ma_10'].iloc[-1]),
                    'ma_20': float(df['ma_20'].iloc[-1]),
                    'ma_50': float(df['ma_50'].iloc[-1]),
                    'surfing_ma': ma_data['surfing_ma'],
                    'atr': float(self._calculate_atr(df)),
                },
                'timestamp': datetime.now().isoformat()
            }

            self.logger.info(
                f"🎯 BREAKOUT SETUP: {symbol} @ ${current_price:.2f} "
                f"(Move: {big_move_data['move_pct']:.0f}%, Cons: {consolidation_data['days']}d, "
                f"Score: {quality_score}, To Breakout: {distance_to_breakout_pct:.1f}%)"
            )

            return opportunity

        except Exception as e:
            self.logger.debug(f"Error in _analyze_breakout_setup_sync for {symbol}: {e}")
            return None

    def _find_big_move(self, df: pd.DataFrame) -> Optional[Dict]:
        """Find the 'big move' (30-100%+ move in past 60 days)"""
        try:
            # Look for peak in last 90 days
            lookback_days = min(90, len(df))
            recent_df = df.tail(lookback_days)

            peak_idx = recent_df['high'].idxmax()
            peak_price = recent_df.loc[peak_idx, 'high']
            peak_position = len(recent_df) - list(recent_df.index).index(peak_idx) - 1

            # Find the low before the peak (max 60 days before peak)
            start_idx = max(0, list(df.index).index(peak_idx) - 60)
            pre_peak_df = df.iloc[start_idx:list(df.index).index(peak_idx)]

            if pre_peak_df.empty:
                return None

            low_price = pre_peak_df['low'].min()
            low_idx = pre_peak_df['low'].idxmin()

            # Calculate move
            move_pct = ((peak_price - low_price) / low_price) * 100
            move_days = (peak_idx - low_idx).days if hasattr(peak_idx - low_idx, 'days') else abs(list(df.index).index(peak_idx) - list(df.index).index(low_idx))

            if move_pct >= self.min_big_move_pct and move_days <= self.max_big_move_days:
                return {
                    'peak_idx': peak_idx,
                    'peak_price': peak_price,
                    'low_idx': low_idx,
                    'low_price': low_price,
                    'move_pct': move_pct,
                    'move_days': move_days
                }

            return None

        except Exception as e:
            return None

    def _analyze_consolidation(self, df: pd.DataFrame, peak_idx) -> Optional[Dict]:
        """Analyze consolidation phase after the big move"""
        try:
            # Get data after the peak
            peak_position = list(df.index).index(peak_idx)
            post_peak_df = df.iloc[peak_position:]

            consolidation_days = len(post_peak_df)

            # Check consolidation duration
            if consolidation_days < self.min_consolidation_days or consolidation_days > self.max_consolidation_days:
                return None

            # Consolidation high/low
            cons_high = post_peak_df['high'].max()
            cons_low = post_peak_df['low'].min()

            # Depth of pullback from peak
            depth_pct = ((cons_high - cons_low) / cons_high) * 100

            if depth_pct > self.max_consolidation_depth_pct:
                return None  # Too deep pullback

            # Check for higher lows (orderly consolidation)
            # Split consolidation into 2 halves
            mid_point = len(post_peak_df) // 2
            first_half_low = post_peak_df.iloc[:mid_point]['low'].min()
            second_half_low = post_peak_df.iloc[mid_point:]['low'].min()

            has_higher_lows = second_half_low >= first_half_low * 0.95  # Allow 5% tolerance

            if not has_higher_lows:
                return None  # Not orderly

            return {
                'days': consolidation_days,
                'resistance': float(cons_high),
                'support': float(cons_low),
                'depth_pct': float(depth_pct),
                'orderly': has_higher_lows
            }

        except Exception as e:
            return None

    def _check_ma_relationship(self, df: pd.DataFrame) -> Optional[Dict]:
        """Check if price is surfing 10/20/50-day MA"""
        try:
            current_price = df['close'].iloc[-1]
            ma_10 = df['ma_10'].iloc[-1]
            ma_20 = df['ma_20'].iloc[-1]
            ma_50 = df['ma_50'].iloc[-1]

            # Check distance from each MA
            dist_10 = abs((current_price - ma_10) / ma_10) * 100
            dist_20 = abs((current_price - ma_20) / ma_20) * 100
            dist_50 = abs((current_price - ma_50) / ma_50) * 100

            # Should be near at least one MA
            surfing_ma = None
            if dist_10 <= self.max_distance_from_ma_pct:
                surfing_ma = 'MA_10'
            elif dist_20 <= self.max_distance_from_ma_pct:
                surfing_ma = 'MA_20'
            elif dist_50 <= self.max_distance_from_ma_pct * 1.5:  # Allow wider tolerance for 50-day
                surfing_ma = 'MA_50'

            if not surfing_ma:
                return None

            # MAs should be rising (uptrend)
            ma_10_slope = (df['ma_10'].iloc[-1] - df['ma_10'].iloc[-5]) / df['ma_10'].iloc[-5] if len(df) >= 5 else 0
            ma_20_slope = (df['ma_20'].iloc[-1] - df['ma_20'].iloc[-10]) / df['ma_20'].iloc[-10] if len(df) >= 10 else 0

            if ma_10_slope < -0.05 or ma_20_slope < -0.05:  # Declining MAs
                return None

            return {
                'surfing_ma': surfing_ma,
                'dist_10': float(dist_10),
                'dist_20': float(dist_20),
                'dist_50': float(dist_50),
                'ma_10_slope': float(ma_10_slope),
                'ma_20_slope': float(ma_20_slope)
            }

        except Exception as e:
            return None

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            high = df['high']
            low = df['low']
            close = df['close'].shift(1)

            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]

            return atr

        except:
            return 0.0

    def _calculate_quality_score(
        self,
        big_move_data: Dict,
        consolidation_data: Dict,
        ma_data: Dict,
        distance_to_breakout_pct: float
    ) -> int:
        """
        Calculate quality score (0-100).

        Factors:
        - Size of big move (bigger = better)
        - Consolidation characteristics (orderly, right duration)
        - MA relationship (surfing 10-day best)
        - Proximity to breakout (closer = better)
        """
        score = 50  # Base score

        # Big Move Score (0-20 points)
        move_pct = big_move_data['move_pct']
        if move_pct >= 100:
            score += 20
        elif move_pct >= 70:
            score += 15
        elif move_pct >= 50:
            score += 10
        else:
            score += 5

        # Consolidation Score (0-20 points)
        cons_days = consolidation_data['days']
        if 15 <= cons_days <= 40:  # Sweet spot: 3-8 weeks
            score += 20
        elif 10 <= cons_days <= 60:
            score += 10

        # Orderly consolidation bonus
        if consolidation_data['orderly']:
            score += 10

        # MA Relationship Score (0-15 points)
        if ma_data['surfing_ma'] == 'MA_10':
            score += 15
        elif ma_data['surfing_ma'] == 'MA_20':
            score += 10
        elif ma_data['surfing_ma'] == 'MA_50':
            score += 5

        # Proximity to Breakout Score (0-15 points)
        if distance_to_breakout_pct <= 1.0:
            score += 15
        elif distance_to_breakout_pct <= 2.0:
            score += 10
        elif distance_to_breakout_pct <= 3.0:
            score += 5

        return min(score, 99)  # Cap at 99
