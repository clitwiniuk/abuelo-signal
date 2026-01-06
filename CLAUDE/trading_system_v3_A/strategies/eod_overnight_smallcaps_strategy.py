# strategies/eod_overnight_smallcaps_strategy.py
"""
End-Of-Day Overnight Smallcaps Strategy

Specialized strategy for holding smallcap positions overnight with specific risk management.
Designed for smallcaps with market caps under $500M.

Key Features:
1. EOD momentum detection (14:00-16:00 ET) optimized for smallcaps
2. Overnight hold with gap protection
3. Next-day exit logic (10:00 ET or earlier if conditions met)
4. Enhanced risk management for overnight gaps
5. Smallcap-specific volume and liquidity filters

Strategy Edge:
- Smallcaps often continue momentum overnight due to lower institutional presence
- Less after-hours trading creates momentum continuation opportunities  
- Early morning (9:30-10:30) often sees follow-through in smallcaps
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from strategies.base import BaseStrategy
from core.interfaces import Signal, Position, MarketData, SignalType

# Simple technical indicators for smallcaps
def calculate_rsi(prices, period=14):
    """Simple RSI calculation"""
    if len(prices) < period + 1:
        return pd.Series([50] * len(prices), index=prices.index)
    
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_simple_sma(prices, period):
    """Simple moving average"""
    return prices.rolling(window=period).mean()

def calculate_volume_profile(df, periods=20):
    """Volume profile for smallcaps - simpler approach"""
    if len(df) < periods:
        return df['volume'].mean()
    
    return df['volume'].rolling(window=periods).mean()

@dataclass
class OvernightPosition:
    """Track overnight positions with specific metadata"""
    symbol: str
    entry_price: float
    entry_time: datetime
    quantity: int
    side: str
    confidence: float
    target_exit_time: datetime
    max_gap_tolerance: float
    stop_loss_price: float

class EODOvernightSmallcapsStrategy(BaseStrategy):
    """
    End-Of-Day Overnight Strategy for Smallcaps
    
    Optimized for:
    - Market cap under $500M
    - Lower liquidity than large caps
    - Higher volatility and gap potential
    - Momentum continuation overnight
    """

    def __init__(self, params: Dict):
        super().__init__("eod_overnight_smallcaps", params)
        
        # Timing parameters
        self.active_start_hour = params.get('active_start_hour', 14.0)  # 14:00 ET
        self.active_end_hour = params.get('active_end_hour', 16.0)     # 16:00 ET
        self.exit_next_day_hour = params.get('exit_next_day_hour', 10.0)  # 10:00 ET next day
        self.min_time_to_close = params.get('min_time_to_close', 20)   # Min 20 min before close
        
        # Smallcap-specific volume parameters (lower thresholds)
        self.min_absolute_volume = params.get('min_absolute_volume', 25000)
        self.volume_acceleration_threshold = params.get('volume_acceleration_threshold', 1.5)
        self.volume_lookback_periods = params.get('volume_lookback_periods', 20)
        self.min_daily_volume = params.get('min_daily_volume', 100000)
        
        # Momentum parameters adjusted for smallcaps
        self.momentum_threshold = params.get('momentum_threshold', 0.02)  # 2% minimum move
        self.momentum_confirmation_bars = params.get('momentum_confirmation_bars', 3)
        self.rsi_entry_min = params.get('rsi_entry_min', 35)
        self.rsi_entry_max = params.get('rsi_entry_max', 80)
        
        # Smallcap market cap and liquidity filters
        self.max_market_cap = params.get('max_market_cap', 500000000)  # $500M max
        self.min_spread_tolerance = params.get('min_spread_tolerance', 0.02)  # 2% max spread
        self.liquidity_score_min = params.get('liquidity_score_min', 0.3)
        
        # Overnight risk management
        self.max_overnight_risk = params.get('max_overnight_risk', 0.025)  # 2.5% max risk
        self.gap_protection_enabled = params.get('gap_protection_enabled', True)
        self.max_gap_tolerance = params.get('max_gap_tolerance', 0.12)  # 12% gap max
        self.overnight_stop_buffer = params.get('overnight_stop_buffer', 0.08)  # 8% stop buffer
        
        # Position sizing for overnight holds
        self.overnight_position_factor = params.get('overnight_position_factor', 0.6)  # Reduce size 40%
        self.max_overnight_positions = params.get('max_overnight_positions', 2)
        self.min_hold_time_minutes = params.get('min_hold_time_minutes', 45)
        
        # Exit conditions
        self.profit_target_overnight = params.get('profit_target_overnight', 0.08)  # 8% profit target
        self.early_exit_profit = params.get('early_exit_profit', 0.15)  # 15% early exit
        self.max_loss_exit = params.get('max_loss_exit', 0.04)  # 4% max loss exit
        
        # Quality filters specific to smallcaps
        self.avoid_earnings_week = params.get('avoid_earnings_week', True)
        self.min_price_stability = params.get('min_price_stability', 0.5)  # Avoid penny stock pumps
        self.require_institutional_hint = params.get('require_institutional_hint', False)
        
        # Performance tracking
        self.overnight_positions: Dict[str, OvernightPosition] = {}
        self.overnight_stats = {
            'positions_opened': 0,
            'positions_closed': 0,
            'overnight_wins': 0,
            'gap_ups': 0,
            'gap_downs': 0,
            'early_exits': 0
        }
        
        # Breakout tracking for pullback entries
        self.breakout_tracking = {}  # symbol -> {'timestamp': dt, 'price': float, 'overnight_data': dict}
        
        self.logger.info(f"🌙 EOD Overnight Smallcaps Strategy initialized")
        self.logger.info(f"📊 Entry: {self.active_start_hour:.1f}h-{self.active_end_hour:.1f}h ET")
        self.logger.info(f"🌅 Exit: Next day {self.exit_next_day_hour:.1f}h ET")
        self.logger.info(f"💰 Max market cap: ${self.max_market_cap/1000000:.0f}M")

    def is_active(self, current_time: datetime) -> bool:
        """Check if strategy should be active for entries"""
        us_hour = current_time.hour + current_time.minute / 60.0
        
        # Entry window: 14:00-16:00 ET
        entry_active = self.active_start_hour <= us_hour <= self.active_end_hour
        
        # Exit window: 9:30-10:00 ET next day (for overnight positions)
        exit_active = 9.5 <= us_hour <= self.exit_next_day_hour
        
        # Always active if we have overnight positions to manage
        has_overnight = len(self.overnight_positions) > 0
        
        return entry_active or exit_active or has_overnight

    async def _initialize_strategy(self) -> None:
        """Strategy-specific initialization logic"""
        self.logger.info("🌙 EOD Overnight Smallcaps Strategy initialized")
        pass
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate signal - implement in subclasses"""
        signals = self.analyze(bar)
        return signals[0] if signals else None
    
    def analyze(self, data: MarketData) -> List[Signal]:
        """Analyze market data for EOD overnight opportunities"""
        current_time = datetime.now()
        us_hour = current_time.hour + current_time.minute / 60.0
        
        signals = []
        
        try:
            # 1. Handle overnight position exits first
            exit_signals = self._check_overnight_exits(data, current_time)
            signals.extend(exit_signals)
            
            # 2. Check for new entries (only during entry window)
            if self.active_start_hour <= us_hour <= self.active_end_hour:
                entry_signals = self._analyze_entry_opportunities(data, current_time)
                signals.extend(entry_signals)
            
            return signals
            
        except Exception as e:
            self.logger.error(f"❌ EOD Overnight analysis error for {data.symbol}: {e}")
            return []

    def _check_overnight_exits(self, data: MarketData, current_time: datetime) -> List[Signal]:
        """Check if any overnight positions should be exited"""
        if data.symbol not in self.overnight_positions:
            return []
            
        position = self.overnight_positions[data.symbol]
        us_hour = current_time.hour + current_time.minute / 60.0
        
        # Get current market data
        # TEMPORARY FIX: Skip analysis if no DataFrame available
        if not hasattr(data, 'df') or data.df is None or len(data.df) == 0:
            return []
            
        current_price = data.df['close'].iloc[-1]
        entry_price = position.entry_price
        
        # Calculate current P&L
        if position.side == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        should_exit = False
        exit_reason = ""
        
        # Exit conditions
        if us_hour >= self.exit_next_day_hour:
            should_exit = True
            exit_reason = f"scheduled_exit_{self.exit_next_day_hour:.1f}h"
            
        elif pnl_pct >= self.early_exit_profit:
            should_exit = True
            exit_reason = f"early_profit_{pnl_pct*100:.1f}%"
            self.overnight_stats['early_exits'] += 1
            
        elif pnl_pct <= -self.max_loss_exit:
            should_exit = True
            exit_reason = f"max_loss_{pnl_pct*100:.1f}%"
            
        elif current_price <= position.stop_loss_price:
            should_exit = True
            exit_reason = f"stop_loss_{position.stop_loss_price:.2f}"
        
        # Gap protection check
        elif self.gap_protection_enabled and us_hour <= 10.0:  # First hour of trading
            gap_pct = abs(pnl_pct)
            if gap_pct > position.max_gap_tolerance:
                should_exit = True
                exit_reason = f"gap_protection_{gap_pct*100:.1f}%"
                
                if pnl_pct > 0:
                    self.overnight_stats['gap_ups'] += 1
                else:
                    self.overnight_stats['gap_downs'] += 1
        
        if should_exit:
            # Create exit signal
            signal_type = SignalType.EXIT_LONG if position.side == 'LONG' else SignalType.EXIT_SHORT
            
            signal = Signal(
                strategy_name=self.name,
                symbol=data.symbol,
                signal_type=signal_type,
                confidence=0.95,  # High confidence for exits
                price=current_price,
                timestamp=current_time,
                metadata={
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct,
                    'hold_time_hours': (current_time - position.entry_time).total_seconds() / 3600,
                    'entry_price': entry_price,
                    'overnight_position': True
                }
            )
            
            # Remove from overnight tracking
            del self.overnight_positions[data.symbol]
            self.overnight_stats['positions_closed'] += 1
            
            if pnl_pct > 0:
                self.overnight_stats['overnight_wins'] += 1
            
            self.logger.info(f"🌅 Overnight exit: {data.symbol} {exit_reason} P&L: {pnl_pct*100:.1f}%")
            
            return [signal]
        
        return []

    def _analyze_entry_opportunities(self, data: MarketData, current_time: datetime) -> List[Signal]:
        """Analyze for new EOD entry opportunities"""
        # TEMPORARY FIX: Skip analysis if no DataFrame available
        if not hasattr(data, 'df') or data.df is None or len(data.df) < 50:
            return []
        
        # Check if we're at position limit
        if len(self.overnight_positions) >= self.max_overnight_positions:
            return []
        
        # Calculate time to close
        time_to_close = self._calculate_time_to_close(current_time)
        if time_to_close < self.min_time_to_close:
            return []
        
        # Calculate indicators
        indicators = self._calculate_smallcap_indicators(data.df)
        if not indicators:
            return []
        
        # Apply smallcap filters
        if not self._passes_smallcap_filters(data, indicators):
            return []
        
        # Analyze momentum patterns
        momentum_signals = self._analyze_smallcap_momentum(data, indicators, time_to_close)
        
        # Convert to overnight positions
        overnight_signals = []
        for signal in momentum_signals:
            if signal.confidence >= 0.6:  # Higher threshold for overnight
                # Add overnight metadata
                signal.metadata.update({
                    'overnight_hold': True,
                    'target_exit_time': current_time + timedelta(hours=18),  # Next day 10 AM
                    'max_gap_tolerance': self.max_gap_tolerance,
                    'overnight_risk': self.max_overnight_risk
                })
                
                # Create overnight position tracking
                stop_loss_price = self._calculate_overnight_stop(signal.price, signal.signal_type)
                
                overnight_position = OvernightPosition(
                    symbol=data.symbol,
                    entry_price=signal.price,
                    entry_time=current_time,
                    quantity=0,  # Will be set by execution stage
                    side='LONG' if signal.signal_type == SignalType.LONG else 'SHORT',
                    confidence=signal.confidence,
                    target_exit_time=current_time + timedelta(hours=18),
                    max_gap_tolerance=self.max_gap_tolerance,
                    stop_loss_price=stop_loss_price
                )
                
                self.overnight_positions[data.symbol] = overnight_position
                self.overnight_stats['positions_opened'] += 1
                
                overnight_signals.append(signal)
                
                self.logger.info(f"🌙 Overnight entry: {data.symbol} {signal.signal_type.value} "
                               f"confidence={signal.confidence:.2f} target_exit=next_day_{self.exit_next_day_hour:.1f}h")
        
        return overnight_signals

    def _calculate_time_to_close(self, current_time: datetime) -> int:
        """Calculate minutes remaining until market close"""
        current_hour = current_time.hour + current_time.minute / 60.0
        close_hour = 16.0
        
        if current_hour >= close_hour:
            return 0
        
        return int((close_hour - current_hour) * 60)

    def _calculate_smallcap_indicators(self, df: pd.DataFrame) -> Optional[Dict]:
        """Calculate indicators optimized for smallcaps"""
        try:
            latest = df.iloc[-1]
            
            # Price momentum over different periods
            momentum_5 = (latest['close'] - df['close'].iloc[-6]) / df['close'].iloc[-6] if len(df) > 5 else 0
            momentum_15 = (latest['close'] - df['close'].iloc[-16]) / df['close'].iloc[-16] if len(df) > 15 else 0
            
            # Volume indicators
            avg_volume_20 = df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else latest['volume']
            volume_accel = latest['volume'] / avg_volume_20 if avg_volume_20 > 0 else 1.0
            
            # RSI
            rsi = calculate_rsi(df['close']).iloc[-1] if len(df) > 14 else 50
            
            # Price stability (avoid pump & dumps)
            price_std = df['close'].rolling(10).std().iloc[-1] if len(df) >= 10 else 0
            price_stability = 1 - (price_std / latest['close']) if latest['close'] > 0 else 0
            
            # Simple trend
            sma_10 = df['close'].rolling(10).mean().iloc[-1] if len(df) >= 10 else latest['close']
            trend_strength = (latest['close'] - sma_10) / sma_10 if sma_10 > 0 else 0
            
            return {
                'current_price': latest['close'],
                'current_volume': latest['volume'],
                'avg_volume_20': avg_volume_20,
                'volume_accel': volume_accel,
                'momentum_5min': momentum_5,
                'momentum_15min': momentum_15,
                'rsi': rsi,
                'price_stability': price_stability,
                'trend_strength': trend_strength,
                'high_of_day': df['high'].max(),
                'low_of_day': df['low'].min(),
                'price_range': (df['high'].max() - df['low'].min()) / latest['close']
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating smallcap indicators: {e}")
            return None

    def _passes_smallcap_filters(self, data: MarketData, indicators: Dict) -> bool:
        """Apply smallcap-specific quality filters"""
        
        # Volume filter
        if indicators['current_volume'] < self.min_absolute_volume:
            return False
            
        if indicators['avg_volume_20'] < self.min_daily_volume:
            return False
        
        # Price stability (avoid penny stock pumps)
        if indicators['price_stability'] < self.min_price_stability:
            return False
        
        # Reasonable daily range (avoid manipulation)
        if indicators['price_range'] > 0.25:  # 25% daily range max
            return False
        
        # Volume acceleration should exist but not be extreme
        if indicators['volume_accel'] < self.volume_acceleration_threshold:
            return False
            
        if indicators['volume_accel'] > 10.0:  # Avoid obvious pumps
            return False
        
        return True

    def _analyze_smallcap_momentum(self, data: MarketData, indicators: Dict, time_to_close: int) -> List[Signal]:
        """Analyze momentum patterns suitable for smallcap overnight holds"""
        signals = []
        
        current_price = indicators['current_price']
        momentum_5 = indicators['momentum_5min']
        momentum_15 = indicators['momentum_15min']
        volume_accel = indicators['volume_accel']
        rsi = indicators['rsi']
        trend_strength = indicators['trend_strength']
        
        # Bullish momentum conditions
        bullish_momentum = (
            momentum_5 > self.momentum_threshold and
            momentum_15 > self.momentum_threshold * 0.5 and
            trend_strength > 0.01 and
            self.rsi_entry_min <= rsi <= self.rsi_entry_max and
            volume_accel >= self.volume_acceleration_threshold
        )
        
        # Additional confluence for bullish
        near_hod = (current_price / indicators['high_of_day']) >= 0.98
        volume_confirmation = volume_accel >= 1.8
        
        if bullish_momentum:
            # NUEVA LÓGICA: Verificar consolidación antes de entrada nocturna
            consolidation_valid = self._check_overnight_consolidation(data.df, indicators, True)
            if not consolidation_valid:
                self.logger.debug(f"[{data.symbol}] EOD setup detectado pero esperando consolidación para overnight")
                return []  # Wait for consolidation
                
            confidence = 0.5
            
            # Confidence boosters
            if near_hod:
                confidence += 0.15
            if volume_confirmation:
                confidence += 0.15  
            if momentum_15 > self.momentum_threshold:
                confidence += 0.1
            if time_to_close > 45:  # More time = better
                confidence += 0.05
            # Bonus for pullback entry
            confidence += 0.05
            
            confidence = min(0.9, confidence)
            
            if confidence >= 0.6:  # Minimum for overnight
                signal = Signal(
                    strategy_name=self.name,
                    symbol=data.symbol,
                    signal_type=SignalType.LONG,
                    confidence=confidence,
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={
                        'momentum_5min': momentum_5,
                        'momentum_15min': momentum_15,
                        'volume_accel': volume_accel,
                        'rsi': rsi,
                        'near_hod': near_hod,
                        'time_to_close': time_to_close,
                        'overnight_strategy': True
                    }
                )
                signals.append(signal)
        
        # Bearish momentum (less common for overnight smallcaps)
        bearish_momentum = (
            momentum_5 < -self.momentum_threshold and
            momentum_15 < -self.momentum_threshold * 0.5 and
            trend_strength < -0.01 and
            20 <= rsi <= 65 and  # Different RSI range for shorts
            volume_accel >= self.volume_acceleration_threshold
        )
        
        near_lod = (current_price / indicators['low_of_day']) <= 1.02
        
        if bearish_momentum and self._allow_overnight_shorts():
            confidence = 0.4  # Lower base confidence for overnight shorts
            
            if near_lod:
                confidence += 0.1
            if volume_confirmation:
                confidence += 0.1
            if momentum_15 < -self.momentum_threshold:
                confidence += 0.1
            
            confidence = min(0.8, confidence)
            
            if confidence >= 0.6:
                signal = Signal(
                    strategy_name=self.name,
                    symbol=data.symbol,
                    signal_type=SignalType.SHORT,
                    confidence=confidence,
                    price=current_price,
                    timestamp=datetime.now(),
                    metadata={
                        'momentum_5min': momentum_5,
                        'momentum_15min': momentum_15,
                        'volume_accel': volume_accel,
                        'rsi': rsi,
                        'near_lod': near_lod,
                        'time_to_close': time_to_close,
                        'overnight_strategy': True,
                        'short_position': True
                    }
                )
                signals.append(signal)
        
        return signals

    def _allow_overnight_shorts(self) -> bool:
        """Determine if overnight shorts are allowed (conservative approach)"""
        # Generally avoid overnight shorts in smallcaps due to gap risk
        return False

    def _calculate_overnight_stop(self, entry_price: float, signal_type: SignalType) -> float:
        """Calculate stop loss price for overnight positions"""
        if signal_type == SignalType.LONG:
            return entry_price * (1 - self.overnight_stop_buffer)
        else:
            return entry_price * (1 + self.overnight_stop_buffer)

    def get_overnight_stats(self) -> Dict:
        """Get overnight trading statistics"""
        stats = self.overnight_stats.copy()
        
        if stats['positions_closed'] > 0:
            stats['overnight_win_rate'] = stats['overnight_wins'] / stats['positions_closed']
            stats['gap_up_rate'] = stats['gap_ups'] / stats['positions_closed'] 
            stats['gap_down_rate'] = stats['gap_downs'] / stats['positions_closed']
            stats['early_exit_rate'] = stats['early_exits'] / stats['positions_closed']
        else:
            stats['overnight_win_rate'] = 0
            stats['gap_up_rate'] = 0
            stats['gap_down_rate'] = 0 
            stats['early_exit_rate'] = 0
        
        stats['active_overnight_positions'] = len(self.overnight_positions)
        
        return stats
    
    def _check_overnight_consolidation(self, df: pd.DataFrame, indicators: Dict, is_bullish: bool) -> bool:
        """Check if price is consolidating appropriately for overnight smallcap position"""
        try:
            if len(df) < 20:
                return False
            
            # Get recent price data (last 20 bars for smallcaps)
            recent_df = df.tail(20)
            current_price = indicators['current_price']
            
            if is_bullish:
                # For bullish overnight: Look for price consolidation pattern suitable for overnight hold
                # 1. Price range analysis - want tight consolidation
                recent_prices = recent_df['close'].tail(10)  # Last 10 bars
                recent_high = recent_df['high'].tail(10).max()
                recent_low = recent_df['low'].tail(10).min()
                
                # Calculate consolidation range
                price_range_pct = (recent_high - recent_low) / recent_low
                if price_range_pct > 0.06:  # Max 6% range for good consolidation
                    return False
                
                # 2. Volume analysis - want decreasing or stable volume (not dumping)
                recent_volumes = recent_df['volume'].tail(5)
                volume_trend = (recent_volumes.iloc[-1] - recent_volumes.iloc[0]) / recent_volumes.iloc[0]
                if volume_trend > 0.5:  # Avoid if volume spiking up too much
                    return False
                
                # 3. Price stability - current price should be in middle-upper range
                price_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5
                if price_position < 0.3 or price_position > 0.9:  # Want 30%-90% of range
                    return False
                
                # 4. Recent momentum - should not be falling sharply
                recent_change = (current_price - recent_prices.iloc[0]) / recent_prices.iloc[0]
                if recent_change < -0.03:  # Not more than 3% down recently
                    return False
                
                # 5. Volatility check - want controlled volatility
                price_std = recent_prices.std() / recent_prices.mean()
                if price_std > 0.04:  # Max 4% standard deviation
                    return False
                
                self.logger.info(f"EOD overnight consolidation confirmed: Range={price_range_pct*100:.1f}%, Position={price_position*100:.0f}%, Volatility={price_std*100:.1f}%")
                return True
                
            else:
                # For bearish overnight: We mostly focus on longs for smallcaps
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking overnight smallcap pullback: {e}")
            return False

    def get_active_overnight_positions(self) -> Dict[str, OvernightPosition]:
        """Get currently active overnight positions"""
        return self.overnight_positions.copy()
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For EODOvernight strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - required by IStrategy interface"""
        try:
            # Basic stop loss for positions
            if position.quantity > 0:  # Long position
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="EODOvernight",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            elif position.quantity < 0:  # Short position  
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 + stop_loss_pct)
                
                if current_bar.close >= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="EODOvernight",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None
