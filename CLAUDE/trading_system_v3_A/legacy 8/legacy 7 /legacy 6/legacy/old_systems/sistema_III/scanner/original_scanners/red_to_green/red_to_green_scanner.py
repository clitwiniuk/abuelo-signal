#!/usr/bin/env python3
"""
Red to Green Scanner Module

Integrado en scanner_main.py para detectar setups Red to Green
Ejecuta diariamente para encontrar stocks con patrones R2G válidos
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np

class RedToGreenScanner:
    """
    Scanner módulo para detectar Red to Green setups

    Red to Green ocurre cuando:
    1. Hay una vela verde previa con volumen significativo (atrae shorts)
    2. Seguida de vela(s) roja(s) que rompen niveles clave
    3. Consolidación con volumen decreciente
    4. Ruptura convincente del nivel R2G con volumen
    """

    def __init__(self, ibkr_adapter, logger=None):
        self.ibkr_adapter = ibkr_adapter
        self.logger = logger or logging.getLogger("RedToGreenScanner")

        # Scanning parameters for R2G detection
        self.scan_params = {
            # Previous green candle validation
            'min_green_volume_ratio': 2.0,        # 2x average volume for green candle
            'min_green_move_percent': 3.0,        # Minimum 3% green move
            'max_days_back_green': 5,             # Look back max 5 days for green candle

            # Red candle validation
            'min_red_volume_vs_green': 0.5,       # Red volume ≥ 50% of green volume
            'max_time_between_green_red': 3,      # Max 3 days between green and red

            # Current setup validation
            'max_consolidation_range': 5.0,       # Max 5% price range in consolidation
            'min_consolidation_days': 1,          # Min 1 day of consolidation
            'max_consolidation_days': 10,         # Max 10 days of consolidation
            'volume_decline_required': True,      # Volume must decline in consolidation

            # R2G breakout criteria
            'min_r2g_breakout_percent': 5.0,      # Minimum 5% convincing breakout
            'breakout_volume_multiplier': 1.5,    # Breakout volume vs consolidation avg

            # Price and quality filters
            'min_price': 1.0,                     # Minimum stock price
            'max_price': 20.0,                    # Maximum stock price for small caps
            'min_daily_volume': 100000,           # Minimum average daily volume
            'max_float': 100000000,               # Maximum float (100M shares)

            # Timing filters
            'optimal_days_after_first_red': [2, 3], # Best days to find R2G setups
            'min_drawdown_from_highs': 20.0,      # Min 20% drawdown from recent highs

            # Scanning time optimization (match strategy hours)
            'scan_start_hour': 8.0,              # Start scanning at 8:00 AM (extended for testing)
            'scan_end_hour': 14.0,               # Stop scanning at 2:00 PM (no new entries after this)
            'skip_scanning_outside_hours': True,  # Skip scanning outside optimal hours
        }

        self.logger.info(f"🔴➡️🟢 Red to Green Scanner module initialized")
        self.logger.info(f"   📊 Mode: Active candidates analysis for R2G patterns")

    async def scan_r2g_candidates(self, active_symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Scan specific active symbols for Red to Green setups

        Args:
            active_symbols: List of symbols from main IBKR scanner

        Returns:
            List of dictionaries with R2G setup information
        """
        # Check if we should scan at this time (optimization)
        if not self._should_scan_now():
            self.logger.info("⏰ R2G Scanner: Outside optimal scanning hours, skipping scan")
            return []

        r2g_candidates = []

        self.logger.info(f"🔍 Scanning {len(active_symbols)} symbols for R2G setups")

        for symbol in active_symbols:
            try:
                # Get historical data for R2G analysis
                setup_data = await self._analyze_r2g_setup(symbol)

                if setup_data and setup_data['is_valid_r2g']:
                    r2g_candidates.append(setup_data)

            except Exception as e:
                self.logger.debug(f"Error analyzing {symbol} for R2G: {e}")
                continue

        # Sort by R2G quality score
        r2g_candidates.sort(key=lambda x: x['r2g_score'], reverse=True)

        self.logger.info(f"✅ Found {len(r2g_candidates)} valid R2G setups")

        return r2g_candidates

    async def _analyze_r2g_setup(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a symbol for complete R2G setup

        Returns:
            Dictionary with R2G analysis or None if not valid
        """
        try:
            # Get 15 days of historical data for pattern analysis
            historical_data = await self._get_historical_data(symbol, days=15)

            if not historical_data or len(historical_data) < 10:
                return None

            # Step 1: Find previous green candle with volume
            green_candle_data = self._find_previous_green_candle(historical_data)
            if not green_candle_data:
                return None

            # Step 2: Validate red candle sequence after green
            red_sequence_data = self._validate_red_sequence(historical_data, green_candle_data)
            if not red_sequence_data:
                return None

            # Step 3: Analyze current consolidation phase
            consolidation_data = self._analyze_consolidation_phase(historical_data)
            if not consolidation_data:
                return None

            # Step 4: Calculate R2G quality score
            r2g_score = self._calculate_r2g_score(
                green_candle_data,
                red_sequence_data,
                consolidation_data,
                historical_data
            )

            # Step 5: Determine key R2G levels and targets
            r2g_levels = self._calculate_r2g_levels(historical_data, green_candle_data)

            return {
                'symbol': symbol,
                'is_valid_r2g': True,
                'r2g_score': r2g_score,
                'scan_timestamp': datetime.now(),
                'opportunity_type': 'red_to_green',
                'strategy_targets': ['red_to_green'],

                # R2G specific data
                'green_candle_data': green_candle_data,
                'red_sequence_data': red_sequence_data,
                'consolidation_data': consolidation_data,
                'r2g_levels': r2g_levels,

                # Current market data
                'current_price': historical_data[-1]['close'],
                'current_volume': historical_data[-1]['volume'],
                'distance_to_r2g_level': r2g_levels['distance_to_breakout'],
                'volume_ratio': green_candle_data.get('volume_ratio', 0),

                # Recommendation
                'trading_recommendation': self._generate_r2g_recommendation(
                    r2g_score, r2g_levels, consolidation_data
                )
            }

        except Exception as e:
            self.logger.error(f"Error in R2G analysis for {symbol}: {e}")
            return None

    def _find_previous_green_candle(self, data: List[Dict]) -> Optional[Dict]:
        """
        Find previous green candle with significant volume

        Criteria:
        - Green candle (close > open)
        - Volume ≥ 2x average
        - Price move ≥ 3%
        - Within last 5 days
        """
        try:
            # Calculate average volume for the period
            volumes = [bar['volume'] for bar in data]
            avg_volume = np.mean(volumes)

            # Look for green candle in reverse order (most recent first)
            for i in range(len(data) - 1, max(len(data) - 6, 0), -1):
                bar = data[i]

                # Check if it's a green candle
                if bar['close'] <= bar['open']:
                    continue

                # Check volume criteria
                volume_ratio = bar['volume'] / avg_volume if avg_volume > 0 else 0
                if volume_ratio < self.scan_params['min_green_volume_ratio']:
                    continue

                # Check price move criteria
                price_move = (bar['close'] - bar['open']) / bar['open']
                if price_move < (self.scan_params['min_green_move_percent'] / 100):
                    continue

                # Valid green candle found
                return {
                    'index': i,
                    'price': bar['close'],
                    'volume': bar['volume'],
                    'volume_ratio': volume_ratio,
                    'move_percent': price_move * 100,
                    'timestamp': bar['timestamp'],
                    'open': bar['open'],
                    'high': bar['high'],
                    'low': bar['low'],
                    'close': bar['close']
                }

            return None

        except Exception as e:
            self.logger.error(f"Error finding green candle: {e}")
            return None

    def _validate_red_sequence(self, data: List[Dict], green_data: Dict) -> Optional[Dict]:
        """
        Validate red candle sequence after green candle

        Criteria:
        - Red candle(s) after green candle
        - Breaks below key levels (open or previous close)
        - Has sufficient volume (shorts entering)
        """
        try:
            green_index = green_data['index']

            # Look for red sequence after green candle
            red_candles = []
            first_red_index = None

            for i in range(green_index + 1, len(data)):
                bar = data[i]

                # Check if it's a red candle
                if bar['close'] < bar['open']:
                    if first_red_index is None:
                        first_red_index = i
                    red_candles.append({
                        'index': i,
                        'open': bar['open'],
                        'close': bar['close'],
                        'volume': bar['volume'],
                        'timestamp': bar['timestamp']
                    })
                else:
                    # Green candle breaks the red sequence
                    break

            if not red_candles:
                return None

            # Validate first red candle volume
            first_red = red_candles[0]
            green_volume = green_data['volume']
            red_volume_ratio = first_red['volume'] / green_volume

            if red_volume_ratio < self.scan_params['min_red_volume_vs_green']:
                return None

            # Check if red sequence breaks key levels
            day_open = data[first_red_index]['open']
            prev_close = data[first_red_index - 1]['close'] if first_red_index > 0 else day_open

            lowest_red_close = min(candle['close'] for candle in red_candles)
            breaks_open = lowest_red_close < day_open
            breaks_prev_close = lowest_red_close < prev_close

            return {
                'red_candles': red_candles,
                'first_red_index': first_red_index,
                'red_volume_ratio': red_volume_ratio,
                'breaks_open': breaks_open,
                'breaks_prev_close': breaks_prev_close,
                'key_level': min(day_open, prev_close),
                'lowest_price': lowest_red_close
            }

        except Exception as e:
            self.logger.error(f"Error validating red sequence: {e}")
            return None

    def _analyze_consolidation_phase(self, data: List[Dict]) -> Optional[Dict]:
        """
        Analyze current consolidation phase

        Criteria:
        - Price range within acceptable limits
        - Volume declining trend
        - Duration within limits
        """
        try:
            # Analyze last 5-10 bars for consolidation
            consolidation_period = min(10, len(data))
            recent_bars = data[-consolidation_period:]

            # Calculate price range
            highs = [bar['high'] for bar in recent_bars]
            lows = [bar['low'] for bar in recent_bars]
            price_range = (max(highs) - min(lows)) / min(lows) * 100

            if price_range > self.scan_params['max_consolidation_range']:
                return None

            # Check volume trend (should be declining)
            volumes = [bar['volume'] for bar in recent_bars]
            volume_trend = np.polyfit(range(len(volumes)), volumes, 1)[0]  # Slope

            # Calculate average consolidation volume
            avg_consolidation_volume = np.mean(volumes)

            return {
                'price_range_percent': price_range,
                'volume_trend_slope': volume_trend,
                'is_volume_declining': volume_trend < 0,
                'avg_volume': avg_consolidation_volume,
                'consolidation_high': max(highs),
                'consolidation_low': min(lows),
                'bars_in_consolidation': len(recent_bars)
            }

        except Exception as e:
            self.logger.error(f"Error analyzing consolidation: {e}")
            return None

    def _calculate_r2g_score(self, green_data: Dict, red_data: Dict,
                           consolidation_data: Dict, historical_data: List[Dict]) -> float:
        """
        Calculate quality score for R2G setup (0-100)
        """
        try:
            score = 0.0

            # Green candle quality (30 points max)
            green_volume_score = min(green_data['volume_ratio'] / 4.0, 1.0) * 15  # 15 pts
            green_move_score = min(green_data['move_percent'] / 8.0, 1.0) * 15    # 15 pts
            score += green_volume_score + green_move_score

            # Red sequence quality (25 points max)
            red_volume_score = min(red_data['red_volume_ratio'] / 1.0, 1.0) * 15  # 15 pts
            level_break_score = 10 if (red_data['breaks_open'] or red_data['breaks_prev_close']) else 0
            score += red_volume_score + level_break_score

            # Consolidation quality (25 points max)
            range_score = max(0, (10 - consolidation_data['price_range_percent']) / 10 * 15)  # 15 pts
            volume_decline_score = 10 if consolidation_data['is_volume_declining'] else 0      # 10 pts
            score += range_score + volume_decline_score

            # Timing quality (20 points max)
            current_price = historical_data[-1]['close']
            r2g_level = red_data['key_level']
            distance_to_level = abs(current_price - r2g_level) / r2g_level * 100
            proximity_score = max(0, (5 - distance_to_level) / 5 * 20)  # 20 pts
            score += proximity_score

            return min(score, 100.0)

        except Exception as e:
            self.logger.error(f"Error calculating R2G score: {e}")
            return 0.0

    def _calculate_r2g_levels(self, data: List[Dict], green_data: Dict) -> Dict:
        """
        Calculate key R2G levels and targets
        """
        try:
            current_price = data[-1]['close']

            # Key resistance level (where R2G breakout should occur)
            day_open = data[green_data['index'] + 1]['open'] if green_data['index'] + 1 < len(data) else current_price
            prev_close = green_data['close']
            r2g_level = max(day_open, prev_close)  # Higher of the two key levels

            # Calculate targets
            target_1 = r2g_level * 1.08  # 8% above R2G level
            target_2 = r2g_level * 1.15  # 15% above R2G level

            # Calculate stop loss
            recent_low = min(bar['low'] for bar in data[-5:])  # Recent 5-day low
            stop_loss = recent_low * 0.98  # 2% below recent low

            return {
                'r2g_breakout_level': r2g_level,
                'target_1': target_1,
                'target_2': target_2,
                'stop_loss': stop_loss,
                'distance_to_breakout': ((r2g_level - current_price) / current_price) * 100,
                'risk_reward_ratio': (target_1 - r2g_level) / (r2g_level - stop_loss)
            }

        except Exception as e:
            self.logger.error(f"Error calculating R2G levels: {e}")
            return {}

    def _generate_r2g_recommendation(self, score: float, levels: Dict, consolidation: Dict) -> Dict:
        """
        Generate trading recommendation for R2G setup
        """
        try:
            if score >= 75:
                recommendation = "STRONG_BUY"
                confidence = "HIGH"
            elif score >= 60:
                recommendation = "BUY"
                confidence = "MEDIUM"
            elif score >= 45:
                recommendation = "WATCH"
                confidence = "LOW"
            else:
                recommendation = "PASS"
                confidence = "VERY_LOW"

            return {
                'recommendation': recommendation,
                'confidence': confidence,
                'score': score,
                'entry_strategy': 'Wait for convincing breakout above R2G level with volume',
                'risk_management': f"Stop loss: ${levels.get('stop_loss', 0):.2f}",
                'profit_targets': [
                    f"Target 1: ${levels.get('target_1', 0):.2f}",
                    f"Target 2: ${levels.get('target_2', 0):.2f}"
                ],
                'key_levels': {
                    'r2g_breakout': levels.get('r2g_breakout_level', 0),
                    'support': levels.get('stop_loss', 0),
                    'resistance_1': levels.get('target_1', 0),
                    'resistance_2': levels.get('target_2', 0)
                }
            }

        except Exception as e:
            self.logger.error(f"Error generating recommendation: {e}")
            return {'recommendation': 'ERROR', 'confidence': 'NONE'}

    async def _get_historical_data(self, symbol: str, days: int = 15) -> Optional[List[Dict]]:
        """
        Get historical price and volume data for symbol

        Args:
            symbol: Stock symbol
            days: Number of days of historical data

        Returns:
            List of daily OHLCV data or None if error
        """
        try:
            # Use IBKR adapter to get historical data
            if not self.ibkr_adapter:
                return None

            # Request historical data using get_bars method
            historical_data = await self.ibkr_adapter.get_bars(
                symbol,
                "1 day",
                days
            )

            if not historical_data:
                return None

            # Convert to standardized format
            formatted_data = []
            for bar in historical_data:
                formatted_data.append({
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume) if bar.volume else 0
                })

            return formatted_data

        except Exception as e:
            self.logger.error(f"Error getting historical data for {symbol}: {e}")
            return None

    def get_scan_summary(self, r2g_results: List[Dict]) -> Dict[str, Any]:
        """
        Generate summary of R2G scan results
        """
        if not r2g_results:
            return {
                'total_candidates': 0,
                'avg_score': 0,
                'top_picks': [],
                'scan_timestamp': datetime.now()
            }

        scores = [result['r2g_score'] for result in r2g_results]

        return {
            'total_candidates': len(r2g_results),
            'avg_score': np.mean(scores),
            'max_score': np.max(scores),
            'min_score': np.min(scores),
            'top_picks': [
                {
                    'symbol': result['symbol'],
                    'score': result['r2g_score'],
                    'recommendation': result['trading_recommendation']['recommendation']
                }
                for result in r2g_results[:5]  # Top 5
            ],
            'scan_timestamp': datetime.now()
        }

    def _should_scan_now(self) -> bool:
        """
        Check if we should run R2G scanning at the current time
        Optimization to avoid unnecessary scanning outside trading hours

        Returns:
            True if scanning should proceed, False otherwise
        """
        if not self.scan_params.get('skip_scanning_outside_hours', True):
            return True  # Always scan if optimization is disabled

        try:
            import pytz
            # Use US Eastern Time for market hours
            eastern = pytz.timezone('US/Eastern')
            current_time = datetime.now(eastern)
            current_hour = current_time.hour + current_time.minute / 60.0

            scan_start = self.scan_params.get('scan_start_hour', 9.0)
            scan_end = self.scan_params.get('scan_end_hour', 14.0)

            # Check if we're within scanning hours
            is_within_hours = scan_start <= current_hour <= scan_end

            # Check if it's a weekday (Monday=0, Sunday=6)
            is_weekday = current_time.weekday() < 5

            should_scan = is_within_hours and is_weekday

            if not should_scan:
                self.logger.debug(f"⏰ R2G Scanner timing check: "
                                f"Current: {current_hour:.1f}, "
                                f"Window: {scan_start}-{scan_end}, "
                                f"Weekday: {is_weekday}")

            return should_scan

        except Exception as e:
            self.logger.error(f"Error checking scan timing: {e}")
            return True  # Default to scanning on error

    def _get_current_market_hour(self) -> float:
        """Get current time in decimal hour format (EST/EDT market time)"""
        try:
            current_time = datetime.now()
            return current_time.hour + current_time.minute / 60.0
        except Exception as e:
            self.logger.error(f"Error getting current market hour: {e}")
            return 12.0  # Default to noon