#!/usr/bin/env python3
"""
Improved Simple Explosion Strategy
==================================

Versión mejorada que es MÁS SELECTIVA pero mantiene la simplicidad.
Agrega filtros de calidad para evitar señales de baja probabilidad.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData
from .base import BaseStrategy


class ImprovedSimpleExplosionStrategy(BaseStrategy):
    """
    Versión mejorada de la estrategia simple con filtros de calidad
    
    MEJORAS vs UltraSimple:
    1. Filtros de volumen más estrictos
    2. Confirmación de momentum direccional
    3. Evitar reversiones (entrar solo a favor de la tendencia)
    4. Better position sizing basado en volatilidad
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        self._name = "ImprovedSimpleExplosion"
        self.logger = logging.getLogger(f"Strategy.{self._name}")
        
        # Parámetros MEJORADOS - más selectivos
        default_params = {
            # FILTROS DE VOLUMEN (más estrictos)
            'volume_threshold': 2.5,              # 2.5x para ser más selectivo
            'min_volume_absolute': 10000,         # Volumen mínimo absoluto
            'volume_consistency_bars': 3,         # Confirmar volumen en últimas 3 barras
            
            # FILTROS DE MOMENTUM (más sofisticados)
            'momentum_threshold': 0.008,          # 0.8% momentum mínimo (más estricto)
            'momentum_bars': 3,                   # 3 barras para confirmación
            'trend_confirmation_bars': 5,         # Confirmar tendencia en 5 barras
            
            # FILTROS DE CALIDAD DE PRECIO
            'min_price': 1.0,                     # Precio mínimo
            'max_price': 50.0,                    # Precio máximo para smallcaps
            'price_volatility_threshold': 0.05,   # Máximo 5% volatilidad reciente
            
            # CONTROL TEMPORAL
            'min_history_bars': 10,               # Más historia necesaria
            'cooldown_minutes': 15,               # Cooldown más largo
            'max_daily_signals': 8,               # Menos señales por día (mejor calidad)
            
            # HORARIOS (evitar períodos problemáticos)
            'start_hour': 10.0,                   # 10:00 AM (después del ruido inicial)
            'end_hour': 15.0,                     # 3:00 PM (antes del cierre)
            'avoid_lunch_hour': True,             # Evitar 12:00-13:00
            
            # GESTIÓN DE RIESGO
            'max_position_value': 400.0,          
            'position_size_adjustment': True,      # Ajustar por volatilidad
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("ImprovedSimpleExplosion", default_params)
        
        # Estado mejorado
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.last_signal_time: Dict[str, datetime] = {}
        self.daily_signals_count = 0
        self.last_date = None
        self.volatility_cache: Dict[str, float] = {}
        
        self.logger.info("🎯 Improved Simple Explosion Strategy - SELECTIVE MODE!")
    
    async def _initialize_strategy(self) -> None:
        """Initialize strategy"""
        self.logger.info("🚀 Initializing Improved Simple Explosion Strategy")
        self.logger.info(f"💎 SELECTIVE MODE: vol_threshold={self._parameters['volume_threshold']:.1f}x")
        self.logger.info(f"📈 Momentum requirement: {self._parameters['momentum_threshold']:.1f}%")
        self.logger.info(f"🎯 Max daily signals: {self._parameters['max_daily_signals']}")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar with improved filters"""
        return await self.on_bar(bar)
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Improved processing with quality filters"""
        
        symbol = bar.symbol
        
        # Reset daily counter
        self._reset_daily_counter(bar.timestamp)
        
        # Daily limit
        if self.daily_signals_count >= self._parameters['max_daily_signals']:
            return None
        
        # Trading hours with lunch break
        if not self._is_good_trading_time(bar.timestamp):
            return None
        
        # Price range filter
        if not self._is_valid_price_range(bar.close):
            return None
        
        # Update history
        self._update_bars_history(bar)
        
        # Need sufficient history
        if len(self.bars_history.get(symbol, [])) < self._parameters['min_history_bars']:
            return None
        
        # Cooldown
        if self._is_in_cooldown(symbol, bar.timestamp):
            return None
        
        # Update volatility cache
        self._update_volatility_cache(symbol)
        
        # FILTER 1: High quality volume explosion
        if not self._has_quality_volume_explosion(bar):
            return None
        
        # FILTER 2: Confirmar momentum direccional
        if not self._has_directional_momentum(bar):
            return None
        
        # FILTER 3: Confirmar tendencia favorable
        if not self._has_favorable_trend(bar):
            return None
        
        # FILTER 4: Evitar alta volatilidad reciente
        if not self._is_acceptable_volatility(symbol):
            return None
        
        # ✅ GENERATE SIGNAL - Pasó todos los filtros de calidad
        signal = Signal(
            signal_id=f"improved_{symbol}_{int(bar.timestamp.timestamp())}",
            signal_type=SignalType.LONG,
            symbol=symbol,
            strength=self._calculate_signal_strength(bar),
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name="ImprovedSimpleExplosion",
            metadata={
                'strategy': 'ImprovedSimpleExplosion',
                'volume': bar.volume,
                'volume_ratio': self._get_volume_ratio(bar),
                'momentum': self._get_momentum(bar),
                'trend_strength': self._get_trend_strength(bar),
                'volatility': self.volatility_cache.get(symbol, 0.0),
                'entry_type': 'quality_explosion'
            }
        )
        
        # Update state
        self.last_signal_time[symbol] = bar.timestamp
        self.daily_signals_count += 1
        
        self.logger.info(
            f"💎 QUALITY ENTRY: {symbol} @ ${bar.close:.2f} | "
            f"Vol: {self._get_volume_ratio(bar):.1f}x | "
            f"Momentum: {self._get_momentum(bar):+.2%} | "
            f"Strength: {signal.strength:.2f}"
        )
        
        return signal
    
    def _has_quality_volume_explosion(self, bar: MarketData) -> bool:
        """FILTER 1: Quality volume explosion detection"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        # Need sufficient history
        consistency_bars = self._parameters['volume_consistency_bars']
        if len(bars) < consistency_bars + 2:
            return False
        
        # Check absolute volume minimum
        if bar.volume < self._parameters['min_volume_absolute']:
            return False
        
        # Calculate volume ratio vs recent average
        recent_volumes = [b.volume for b in bars[-(consistency_bars+1):-1]]
        avg_volume = np.mean(recent_volumes)
        
        if avg_volume <= 0:
            return False
        
        volume_ratio = bar.volume / avg_volume
        
        # Must exceed threshold
        if volume_ratio < self._parameters['volume_threshold']:
            return False
        
        # Volume consistency: should be building up, not just a single spike
        recent_ratios = []
        for i in range(len(bars)-consistency_bars, len(bars)):
            if i > 0:
                prev_avg = np.mean([b.volume for b in bars[max(0,i-consistency_bars):i]])
                if prev_avg > 0:
                    recent_ratios.append(bars[i].volume / prev_avg)
        
        # At least 50% of recent bars should show elevated volume
        elevated_count = sum(1 for ratio in recent_ratios if ratio >= 1.5)
        return elevated_count >= len(recent_ratios) * 0.5
    
    def _has_directional_momentum(self, bar: MarketData) -> bool:
        """FILTER 2: Directional momentum confirmation"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        momentum_bars = self._parameters['momentum_bars']
        if len(bars) < momentum_bars + 1:
            return False
        
        # Calculate momentum over specified period
        old_price = bars[-(momentum_bars + 1)].close
        current_price = bar.close
        momentum = (current_price - old_price) / old_price
        
        # Must meet minimum momentum requirement
        if momentum < self._parameters['momentum_threshold']:
            return False
        
        # Additional check: momentum should be consistent (not whipsaw)
        price_changes = []
        for i in range(len(bars)-momentum_bars, len(bars)):
            if i > 0:
                change = (bars[i].close - bars[i-1].close) / bars[i-1].close
                price_changes.append(change)
        
        # At least 60% of moves should be in same direction
        positive_moves = sum(1 for change in price_changes if change > 0)
        consistency_ratio = positive_moves / len(price_changes) if price_changes else 0
        
        return consistency_ratio >= 0.6
    
    def _has_favorable_trend(self, bar: MarketData) -> bool:
        """FILTER 3: Favorable trend confirmation"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        trend_bars = self._parameters['trend_confirmation_bars']
        if len(bars) < trend_bars + 1:
            return False
        
        # Calculate simple moving average trend
        recent_prices = [b.close for b in bars[-trend_bars:]]
        earlier_prices = [b.close for b in bars[-(trend_bars*2):-trend_bars]]
        
        if not earlier_prices:
            return True  # Not enough data, give benefit of doubt
        
        recent_avg = np.mean(recent_prices)
        earlier_avg = np.mean(earlier_prices)
        
        # Recent prices should be higher than earlier prices (uptrend)
        trend_strength = (recent_avg - earlier_avg) / earlier_avg
        return trend_strength > 0.005  # At least 0.5% uptrend
    
    def _is_acceptable_volatility(self, symbol: str) -> bool:
        """FILTER 4: Volatility filter"""
        
        volatility = self.volatility_cache.get(symbol, 0.0)
        max_volatility = self._parameters['price_volatility_threshold']
        
        # Avoid highly volatile stocks (too risky)
        return volatility <= max_volatility
    
    def _update_volatility_cache(self, symbol: str) -> None:
        """Update volatility cache for the symbol"""
        
        bars = self.bars_history[symbol]
        if len(bars) < 10:
            return
        
        # Calculate recent price volatility (last 10 bars)
        recent_prices = [b.close for b in bars[-10:]]
        returns = []
        for i in range(1, len(recent_prices)):
            ret = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
            returns.append(ret)
        
        if returns:
            volatility = np.std(returns)
            self.volatility_cache[symbol] = volatility
    
    def _calculate_signal_strength(self, bar: MarketData) -> float:
        """Calculate signal strength based on multiple factors"""
        
        strength = 0.6  # Base strength
        
        # Bonus for volume strength
        volume_ratio = self._get_volume_ratio(bar)
        if volume_ratio > 4.0:
            strength += 0.2
        elif volume_ratio > 3.0:
            strength += 0.1
        
        # Bonus for momentum strength
        momentum = self._get_momentum(bar)
        if momentum > 0.02:  # >2%
            strength += 0.15
        elif momentum > 0.015:  # >1.5%
            strength += 0.1
        
        # Bonus for trend alignment
        trend_strength = self._get_trend_strength(bar)
        if trend_strength > 0.015:  # >1.5% trend
            strength += 0.1
        
        return min(strength, 0.95)
    
    def _get_trend_strength(self, bar: MarketData) -> float:
        """Get trend strength"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 10:
            return 0.0
        
        recent_avg = np.mean([b.close for b in bars[-5:]])
        earlier_avg = np.mean([b.close for b in bars[-10:-5]])
        
        if earlier_avg <= 0:
            return 0.0
        
        return (recent_avg - earlier_avg) / earlier_avg
    
    def _is_good_trading_time(self, timestamp: datetime) -> bool:
        """Check if it's a good time to trade (avoid problematic periods)"""
        
        if timestamp.weekday() >= 5:
            return False
        
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        
        # Basic trading hours
        if not (self._parameters['start_hour'] <= hour_decimal <= self._parameters['end_hour']):
            return False
        
        # Avoid lunch hour if enabled
        if self._parameters.get('avoid_lunch_hour', False):
            if 12.0 <= hour_decimal <= 13.0:
                return False
        
        return True
    
    def _is_valid_price_range(self, price: float) -> bool:
        """Check if price is in valid range"""
        min_price = self._parameters['min_price']
        max_price = self._parameters['max_price']
        return min_price <= price <= max_price
    
    # Helper methods (reuse from UltraSimple)
    def _get_volume_ratio(self, bar: MarketData) -> float:
        """Helper: volume ratio"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 4:
            return 1.0
        
        recent_volumes = [b.volume for b in bars[-4:-1]]
        avg_volume = np.mean(recent_volumes)
        
        return bar.volume / avg_volume if avg_volume > 0 else 1.0
    
    def _get_momentum(self, bar: MarketData) -> float:
        """Helper: momentum"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        momentum_bars = self._parameters['momentum_bars']
        
        if len(bars) < momentum_bars + 1:
            return 0.0
        
        old_price = bars[-(momentum_bars + 1)].close
        return (bar.close - old_price) / old_price
    
    def _update_bars_history(self, bar: MarketData) -> None:
        """Maintain history"""
        symbol = bar.symbol
        
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        self.bars_history[symbol].append(bar)
        
        # Keep reasonable history
        if len(self.bars_history[symbol]) > 50:
            self.bars_history[symbol] = self.bars_history[symbol][-50:]
    
    def _is_in_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """Cooldown check"""
        if symbol not in self.last_signal_time:
            return False
        
        time_diff = current_time - self.last_signal_time[symbol]
        return time_diff.total_seconds() / 60 < self._parameters['cooldown_minutes']
    
    def _reset_daily_counter(self, current_time: datetime) -> None:
        """Reset daily counter"""
        current_date = current_time.date()
        
        if self.last_date != current_date:
            self.daily_signals_count = 0
            self.last_date = current_date
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Strategy info"""
        return {
            'name': 'ImprovedSimpleExplosionStrategy',
            'version': '1.0',
            'description': 'Selective explosion strategy with quality filters',
            'complexity_score': 6,  # Medium complexity
            'conditions_count': 4,   # 4 quality filters
            'parameters': {
                'volume_threshold': self._parameters['volume_threshold'],
                'momentum_threshold': self._parameters['momentum_threshold'],
                'max_daily_signals': self._parameters['max_daily_signals']
            },
            'daily_signals_used': f"{self.daily_signals_count}/{self._parameters['max_daily_signals']}",
            'optimal_for': [
                'quality_explosions',
                'selective_entry',
                'better_risk_reward',
                'smallcaps_trading'
            ],
            'entry_style': 'selective_quality',
            'risk_profile': 'medium'
        }
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For ImprovedSimpleExplosion strategy, we don't need special logic on position updates
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
                        strategy_name="ImprovedSimpleExplosion",
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
                        strategy_name="ImprovedSimpleExplosion",
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
