#!/usr/bin/env python3
"""
Gap&Crap Reversal Strategy

Busca el escenario fallido del Gap&Crap, anticipando desde el double bottom o doble piso,
estando la acción roja en el día y por debajo de VWAP.

Descripción:
La acción abre con gap up significativo (30-40%) y se pone roja en el día.
Baja de VWAP y forma un soporte. Los shorts atacan pero la acción no cae más,
generando un short squeeze que hace nuevos máximos.

Entry: Cerca del último low con stop loss justo debajo
Exits: VWAP (25%) -> Open (25%) -> HOD (25%) -> HOD Breakout (25%)
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class GapCrapReversalStrategy(BaseStrategy):
    """
    Gap&Crap Reversal Strategy implementation

    Entry Conditions:
    1. Gap up 30-40%+ en premarket
    2. Volumen histórico/cerca histórico
    3. Precio rojo en el día (below open)
    4. Trading below VWAP
    5. Dejó de hacer nuevos lows (consolidación)
    6. Risk/Reward > 3:1

    Exit Conditions:
    1. 25% at VWAP (first resistance)
    2. 25% at day open (second resistance)
    3. 25% at HOD (third resistance)
    4. 25% at HOD breakout (final exit)
    5. Stop loss: 1-2% below último low
    """

    def __init__(self, parameters: Dict = None, data_provider=None, config=None):
        # GAP CRAP REVERSAL STRATEGY DEFAULTS - RELAXED FOR SMALLCAPS
        fallback_defaults = {
            # Gap requirements - RELAXED FOR SMALLCAPS
            'min_gap_percent': 8.0,
            'max_gap_percent': 200.0,
            'min_premarket_volume': 200000,
            'volume_vs_avg_ratio': 2.0,

            # Price action requirements - RELAXED FOR SMALLCAPS
            'require_red_day': False,
            'require_below_vwap': False,
            'max_new_low_time': 60,
            'min_consolidation_time': 5,

            # Entry criteria - RELAXED FOR SMALLCAPS
            'max_distance_from_low': 0.05,
            'min_risk_reward_ratio': 2.0,
            'max_stop_distance': 0.04,

            # Price range filters - OPTIMIZED FOR SMALLCAPS
            'min_price': 0.5,
            'max_price': 25.0,
            'max_float': 25_000_000,

            # Timing - RELAXED FOR SMALLCAPS
            'entry_start_time': 9.5,
            'entry_end_time': 15.5,

            # Multi-target exits
            'target_1_vwap': 0.25,           # 25% at VWAP
            'target_2_open': 0.25,           # 25% at day open
            'target_3_hod': 0.25,            # 25% at HOD
            'target_4_breakout': 0.25,       # 25% at HOD breakout

            # Risk management
            'max_position_size': 1000,       # Max 1000 shares
            'portfolio_risk_percent': 0.02,  # 2% portfolio risk per trade
        }

        # Initialize with fallback defaults first to get logger
        super().__init__("Gap&Crap Reversal", fallback_defaults)

        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('GAP_CRAP_REVERSAL_STRATEGY', fallback_defaults)

            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)

            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for Gap Crap Reversal strategy: {e}")
            # Keep fallback defaults

        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🔄 GapCrapReversal received parameters: {parameters}")

        # Initialize centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()

        # State tracking
        self._vwap_cache = {}
        self._consolidation_tracker = {}
        self._entry_signals = {}
        self.position_highest_prices = {}  # Track highest prices for trailing stops

        self.logger.info("🔄 Gap&Crap Reversal Strategy initialized")
        self.logger.info(f"   📊 Min gap: {self._parameters['min_gap_percent']}%")
        self.logger.info(f"   📈 Min volume ratio: {self._parameters['volume_vs_avg_ratio']}x")
        self.logger.info(f"   🎯 Min R/R ratio: {self._parameters['min_risk_reward_ratio']}:1")

    def analyze(self, symbol: str, data: MarketData) -> Optional[Signal]:
        """
        Analyze market data for Gap&Crap Reversal opportunities
        """
        try:
            current_time = datetime.now()
            current_hour = current_time.hour + current_time.minute / 60.0

            # Check trading window
            if not (self._parameters['entry_start_time'] <= current_hour <= self._parameters['entry_end_time']):
                return None

            # Step 1: Verify gap up requirements
            gap_analysis = self._analyze_gap_requirements(symbol, data)
            if not gap_analysis['valid']:
                return None

            # Step 2: Check current price action (red day, below VWAP)
            price_action = self._analyze_price_action(symbol, data)
            if not price_action['valid']:
                return None

            # Step 3: Detect consolidation pattern (stopped making new lows)
            consolidation = self._analyze_consolidation_pattern(symbol, data)
            if not consolidation['valid']:
                return None

            # Step 4: Calculate risk/reward and entry levels
            entry_analysis = self._calculate_entry_levels(symbol, data, consolidation)
            if not entry_analysis['valid']:
                return None

            # Step 5: Generate signal if all conditions met
            confidence = self._calculate_confidence_score(gap_analysis, price_action, consolidation, entry_analysis)

            if confidence >= 0.7:  # High confidence threshold
                return self._create_gap_crap_signal(symbol, data, entry_analysis, confidence)

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} for Gap&Crap Reversal: {e}")
            return None

    def _analyze_gap_requirements(self, symbol: str, data: MarketData) -> Dict[str, Any]:
        """Analyze if gap requirements are met"""
        try:
            if not data.current_bar or not data.historical_data or len(data.historical_data) < 2:
                return {'valid': False, 'reason': 'Insufficient data'}

            current_bar = data.current_bar
            prev_close = data.historical_data[-1].close
            current_open = current_bar.open

            # Calculate gap percentage
            gap_percent = ((current_open - prev_close) / prev_close) * 100

            # Gap must be upward and within range
            if gap_percent < self._parameters['min_gap_percent']:
                return {'valid': False, 'reason': f'Gap {gap_percent:.1f}% < {self._parameters["min_gap_percent"]}%'}

            if gap_percent > self._parameters['max_gap_percent']:
                return {'valid': False, 'reason': f'Gap {gap_percent:.1f}% too extreme'}

            # Volume requirements
            current_volume = current_bar.volume or 0
            avg_volume = np.mean([bar.volume for bar in data.historical_data[-10:] if bar.volume])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

            if volume_ratio < self._parameters['volume_vs_avg_ratio']:
                return {'valid': False, 'reason': f'Volume {volume_ratio:.1f}x < {self._parameters["volume_vs_avg_ratio"]}x'}

            if current_volume < self._parameters['min_premarket_volume']:
                return {'valid': False, 'reason': f'Volume {current_volume:,} < {self._parameters["min_premarket_volume"]:,}'}

            return {
                'valid': True,
                'gap_percent': gap_percent,
                'volume_ratio': volume_ratio,
                'prev_close': prev_close,
                'current_open': current_open
            }

        except Exception as e:
            self.logger.error(f"Error analyzing gap requirements for {symbol}: {e}")
            return {'valid': False, 'reason': f'Analysis error: {e}'}

    def _analyze_price_action(self, symbol: str, data: MarketData) -> Dict[str, Any]:
        """Check if price action shows red day and below VWAP"""
        try:
            current_bar = data.current_bar
            if not current_bar:
                return {'valid': False, 'reason': 'No current bar'}

            current_price = current_bar.close
            day_open = current_bar.open

            # Must be red in the day (below open)
            if self._parameters['require_red_day'] and current_price >= day_open:
                return {'valid': False, 'reason': f'Not red: ${current_price:.2f} >= ${day_open:.2f}'}

            # Calculate VWAP
            vwap = self._calculate_vwap(symbol, data)
            if vwap is None:
                return {'valid': False, 'reason': 'Cannot calculate VWAP'}

            # Must be below VWAP
            if self._parameters['require_below_vwap'] and current_price >= vwap:
                return {'valid': False, 'reason': f'Above VWAP: ${current_price:.2f} >= ${vwap:.2f}'}

            # Price range check
            if current_price < self._parameters['min_price'] or current_price > self._parameters['max_price']:
                return {'valid': False, 'reason': f'Price ${current_price:.2f} outside range'}

            return {
                'valid': True,
                'current_price': current_price,
                'day_open': day_open,
                'vwap': vwap,
                'red_amount': ((day_open - current_price) / day_open) * 100
            }

        except Exception as e:
            self.logger.error(f"Error analyzing price action for {symbol}: {e}")
            return {'valid': False, 'reason': f'Price action error: {e}'}

    def _analyze_consolidation_pattern(self, symbol: str, data: MarketData) -> Dict[str, Any]:
        """Detect if stock stopped making new lows (consolidation)"""
        try:
            if not data.intraday_bars or len(data.intraday_bars) < 5:
                return {'valid': False, 'reason': 'Insufficient intraday data'}

            recent_bars = data.intraday_bars[-15:]  # Last 15 bars
            if len(recent_bars) < 5:
                return {'valid': False, 'reason': 'Need more intraday bars'}

            # Find the lowest point (support)
            lows = [bar.low for bar in recent_bars]
            lowest_price = min(lows)
            lowest_index = lows.index(lowest_price)

            # Check if we stopped making new lows
            recent_lows = lows[lowest_index+1:]  # Bars after the lowest point
            if len(recent_lows) < 3:
                return {'valid': False, 'reason': 'Need more bars after low'}

            # Verify no new lows in recent bars
            new_lows = [low for low in recent_lows if low < lowest_price * 1.005]  # 0.5% tolerance
            if len(new_lows) > 0:
                return {'valid': False, 'reason': 'Still making new lows'}

            # Check consolidation time (must be at least X minutes)
            consolidation_bars = len(recent_lows)
            if consolidation_bars < self._parameters['min_consolidation_time'] / 5:  # Assuming 5min bars
                return {'valid': False, 'reason': f'Consolidation too short: {consolidation_bars} bars'}

            return {
                'valid': True,
                'support_level': lowest_price,
                'consolidation_bars': consolidation_bars,
                'recent_lows': recent_lows,
                'stopped_declining': True
            }

        except Exception as e:
            self.logger.error(f"Error analyzing consolidation for {symbol}: {e}")
            return {'valid': False, 'reason': f'Consolidation error: {e}'}

    def _calculate_entry_levels(self, symbol: str, data: MarketData, consolidation: Dict) -> Dict[str, Any]:
        """Calculate entry, stop, and target levels"""
        try:
            current_price = data.current_bar.close
            support_level = consolidation['support_level']
            day_open = data.current_bar.open

            # Calculate VWAP and HOD
            vwap = self._calculate_vwap(symbol, data)
            hod = max([bar.high for bar in data.intraday_bars]) if data.intraday_bars else current_price

            # Entry: Close to support but not too far
            distance_from_support = (current_price - support_level) / support_level
            if distance_from_support > self._parameters['max_distance_from_low']:
                return {'valid': False, 'reason': f'Too far from support: {distance_from_support*100:.1f}%'}

            # Stop loss: Just below support
            stop_loss = support_level * 0.98  # 2% below support
            stop_distance = (current_price - stop_loss) / current_price

            if stop_distance > self._parameters['max_stop_distance']:
                return {'valid': False, 'reason': f'Stop too far: {stop_distance*100:.1f}%'}

            # Targets (multi-level exits)
            target_1_vwap = vwap
            target_2_open = day_open
            target_3_hod = hod
            target_4_breakout = hod * 1.05  # 5% above HOD

            # Risk/Reward calculation (to first target)
            risk = current_price - stop_loss
            reward = target_1_vwap - current_price
            risk_reward_ratio = reward / risk if risk > 0 else 0

            if risk_reward_ratio < self._parameters['min_risk_reward_ratio']:
                return {'valid': False, 'reason': f'R/R {risk_reward_ratio:.1f} < {self._parameters["min_risk_reward_ratio"]}'}

            return {
                'valid': True,
                'entry_price': current_price,
                'stop_loss': stop_loss,
                'support_level': support_level,
                'targets': {
                    'vwap': target_1_vwap,
                    'open': target_2_open,
                    'hod': target_3_hod,
                    'breakout': target_4_breakout
                },
                'risk_reward_ratio': risk_reward_ratio,
                'stop_distance_percent': stop_distance * 100
            }

        except Exception as e:
            self.logger.error(f"Error calculating entry levels for {symbol}: {e}")
            return {'valid': False, 'reason': f'Entry calculation error: {e}'}

    def _calculate_vwap(self, symbol: str, data: MarketData) -> Optional[float]:
        """Calculate Volume Weighted Average Price"""
        try:
            if not data.intraday_bars or len(data.intraday_bars) < 3:
                return None

            total_volume = 0
            total_value = 0

            for bar in data.intraday_bars:
                if bar.volume and bar.volume > 0:
                    typical_price = (bar.high + bar.low + bar.close) / 3
                    total_value += typical_price * bar.volume
                    total_volume += bar.volume

            if total_volume > 0:
                vwap = total_value / total_volume
                self._vwap_cache[symbol] = vwap
                return vwap

            return self._vwap_cache.get(symbol)

        except Exception as e:
            self.logger.error(f"Error calculating VWAP for {symbol}: {e}")
            return None

    def _calculate_confidence_score(self, gap_analysis: Dict, price_action: Dict,
                                  consolidation: Dict, entry_analysis: Dict) -> float:
        """Calculate overall confidence score (0-1)"""
        try:
            score = 0.0

            # Gap quality (25 points)
            gap_percent = gap_analysis.get('gap_percent', 0)
            volume_ratio = gap_analysis.get('volume_ratio', 0)
            gap_score = min(gap_percent / 50.0, 1.0) * 0.15  # 15% weight
            volume_score = min(volume_ratio / 10.0, 1.0) * 0.10  # 10% weight
            score += gap_score + volume_score

            # Price action quality (25 points)
            red_amount = price_action.get('red_amount', 0)
            red_score = min(red_amount / 10.0, 1.0) * 0.15  # More red = better
            vwap_distance = abs(price_action['current_price'] - price_action['vwap']) / price_action['vwap']
            vwap_score = min(vwap_distance / 0.05, 1.0) * 0.10  # Further below VWAP = better
            score += red_score + vwap_score

            # Consolidation quality (25 points)
            consolidation_bars = consolidation.get('consolidation_bars', 0)
            consolidation_score = min(consolidation_bars / 10.0, 1.0) * 0.25
            score += consolidation_score

            # Risk/Reward quality (25 points)
            rr_ratio = entry_analysis.get('risk_reward_ratio', 0)
            rr_score = min(rr_ratio / 5.0, 1.0) * 0.25  # Up to 5:1 R/R
            score += rr_score

            return min(score, 1.0)

        except Exception as e:
            self.logger.error(f"Error calculating confidence score: {e}")
            return 0.0

    def _create_gap_crap_signal(self, symbol: str, data: MarketData,
                               entry_analysis: Dict, confidence: float) -> Signal:
        """Create Gap&Crap Reversal signal"""
        try:
            current_price = entry_analysis['entry_price']
            stop_loss = entry_analysis['stop_loss']
            targets = entry_analysis['targets']

            # Calculate position size based on risk
            risk_per_share = current_price - stop_loss
            portfolio_risk = self._parameters['portfolio_risk_percent'] * 100000  # Assuming $100k portfolio
            position_size = min(
                int(portfolio_risk / risk_per_share),
                self._parameters['max_position_size']
            )

            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                entry_price=current_price,
                stop_loss=stop_loss,
                target_price=targets['vwap'],  # Primary target
                confidence=confidence,
                timestamp=datetime.now(),
                metadata={
                    'strategy': 'gap_crap_reversal',
                    'setup_type': 'reversal_from_support',
                    'gap_percent': entry_analysis.get('gap_percent', 0),
                    'risk_reward_ratio': entry_analysis['risk_reward_ratio'],
                    'support_level': entry_analysis['support_level'],
                    'all_targets': targets,
                    'multi_target_exits': {
                        'vwap_exit': self._parameters['target_1_vwap'],    # 25%
                        'open_exit': self._parameters['target_2_open'],    # 25%
                        'hod_exit': self._parameters['target_3_hod'],      # 25%
                        'breakout_exit': self._parameters['target_4_breakout'] # 25%
                    },
                    'entry_reasoning': f"Gap&Crap reversal from ${entry_analysis['support_level']:.2f} support",
                    'position_size': position_size
                }
            )

            # Register position with centralized stop_loss_manager
            self._register_position_with_stop_manager(symbol, bar, signal)

            self.logger.info(f"🔄 Gap&Crap signal: {symbol} @ ${current_price:.2f}")
            self.logger.info(f"   📊 R/R: {entry_analysis['risk_reward_ratio']:.1f}:1")
            self.logger.info(f"   🎯 Targets: VWAP=${targets['vwap']:.2f}, Open=${targets['open']:.2f}, HOD=${targets['hod']:.2f}")
            self.logger.info(f"   🛑 Stop: ${stop_loss:.2f} ({entry_analysis['stop_distance_percent']:.1f}%)")

            return signal

        except Exception as e:
            self.logger.error(f"Error creating Gap&Crap signal for {symbol}: {e}")
            return None

    def should_exit(self, symbol: str, position: Position, current_data: MarketData) -> Optional[Signal]:
        """
        SMALLCAP-OPTIMIZED Multi-target exit strategy for Gap&Crap Reversal + centralized stop_manager
        """
        try:
            if not position or not current_data.current_bar:
                return None

            current_price = current_data.current_bar.close
            entry_metadata = position.metadata or {}
            targets = entry_metadata.get('all_targets', {})

            # PRIORITY 1: Strategy-specific multi-target exits (keep this unique logic)
            # Force exit near market close
            current_time = datetime.now()
            current_hour = current_time.hour + current_time.minute / 60.0

            if current_hour >= self._parameters['force_exit_time']:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    entry_price=current_price,
                    confidence=0.9,
                    timestamp=datetime.now(),
                    metadata={'exit_reason': 'force_exit_eod', 'exit_percentage': 1.0, 'strategy': 'GapCrapReversal_Smallcaps'}
                )

            # Multi-target profit taking (strategy-specific logic)
            if targets:
                # 25% at VWAP
                if current_price >= targets.get('vwap', float('inf')):
                    return self._create_partial_exit_signal(symbol, current_price, 'vwap', 0.25)

                # 25% at day open
                if current_price >= targets.get('open', float('inf')):
                    return self._create_partial_exit_signal(symbol, current_price, 'open', 0.25)

                # 25% at HOD
                if current_price >= targets.get('hod', float('inf')):
                    return self._create_partial_exit_signal(symbol, current_price, 'hod', 0.25)

                # Final 25% at HOD breakout
                if current_price >= targets.get('breakout', float('inf')):
                    return self._create_partial_exit_signal(symbol, current_price, 'breakout', 0.25)

            # PRIORITY 2: SMALLCAP-OPTIMIZED centralized stop_manager (as backup for stop losses)
            if hasattr(self, 'stop_manager') and self.stop_manager:
                exit_signal = self.stop_manager.check_exit_conditions(
                    symbol=symbol,
                    current_bar=current_data.current_bar
                )

                if exit_signal:
                    return Signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        entry_price=current_price,
                        confidence=0.9,
                        timestamp=current_data.current_bar.timestamp,
                        metadata={
                            'exit_reason': exit_signal.get('reason', 'stop_manager'),
                            'exit_type': 'smallcap_stop_protection',
                            'pnl_pct': exit_signal.get('pnl_pct', 0),
                            'strategy': 'GapCrapReversal_Smallcaps_Optimized'
                        }
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error checking exit for {symbol}: {e}")
            return None

    def _create_partial_exit_signal(self, symbol: str, current_price: float,
                                   level: str, percentage: float) -> Signal:
        """Create partial exit signal"""
        return Signal(
            symbol=symbol,
            signal_type=SignalType.SELL,
            entry_price=current_price,
            confidence=0.8,
            timestamp=datetime.now(),
            metadata={
                'exit_reason': f'target_{level}_hit',
                'exit_percentage': percentage,
                'target_level': level,
                'price_level': current_price
            }
        )

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Analyze individual bar for Gap&Crap opportunities
        Required by BaseStrategy abstract method
        """
        # This method is called by the base class for each bar
        # We redirect to our main analyze method that expects MarketData
        return self.analyze(bar.symbol, bar)

    def on_position_update(self, symbol: str, position: Position) -> None:
        """
        Handle position updates
        Required by BaseStrategy abstract method
        """
        try:
            if position and symbol in self._entry_signals:
                # Track position performance for ML feedback
                entry_signal = self._entry_signals[symbol]
                current_price = position.current_price if hasattr(position, 'current_price') else 0

                # Update highest price for trailing stops
                if symbol not in self.position_highest_prices:
                    self.position_highest_prices[symbol] = position.entry_price

                if current_price > self.position_highest_prices[symbol]:
                    self.position_highest_prices[symbol] = current_price

                # Log position status
                pnl = (current_price - position.entry_price) * position.quantity
                pnl_percent = ((current_price - position.entry_price) / position.entry_price) * 100

                self.logger.debug(f"📊 {symbol} position update: {current_price:.2f} "
                                f"P&L: ${pnl:.2f} ({pnl_percent:.1f}%)")

        except Exception as e:
            self.logger.error(f"Error in position update for {symbol}: {e}")

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information and current state"""
        return {
            'name': self.name,
            'type': 'Gap&Crap Reversal',
            'description': 'Reversal strategy for failed gap ups with short squeeze potential',
            'entry_criteria': [
                'Gap up 30-40%+ with high volume',
                'Red in the day, below VWAP',
                'Stopped making new lows (consolidation)',
                'R/R ratio > 3:1',
                'Entry near support level'
            ],
            'exit_strategy': [
                '25% at VWAP',
                '25% at day open',
                '25% at HOD',
                '25% at HOD breakout'
            ],
            'parameters': self._parameters,
            'current_vwap_cache': len(self._vwap_cache),
            'consolidation_tracker': len(self._consolidation_tracker)
        }

    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS GAP&CRAP: Use global config.ini parameters optimized for smallcaps
        # This strategy has its own multi-target exits, but needs stop loss protection
        # - fallback_stop_loss_pct = 0.06 (6% for volatility protection)
        # - enable_dynamic_ema_trailing = true (as backup to multi-target)
        # - max_hold_minutes = 180 (3 hours max - reversal plays are time-sensitive)
        stop_params = create_stop_params_from_config(self._parameters)

        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.BUY else 'bearish'

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.entry_price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="GapCrapReversal_Smallcaps_Optimized",
            stop_params=stop_params
        )

        self.logger.info(f"📊 {symbol}: GAP&CRAP SMALLCAP-OPTIMIZED - "
                        f"Multi-target exits + 6% stop protection + 3h time limit")