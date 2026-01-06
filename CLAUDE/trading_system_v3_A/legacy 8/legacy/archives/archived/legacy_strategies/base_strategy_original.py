# strategies/base.py
"""
Base strategy classes and common functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from core.interfaces import (
    IStrategy, Signal, Position, MarketData, EventBus,
    SignalType, OrderSide
)
from core.events import EventHandlerMixin, event_handler


class BaseStrategy(IStrategy, EventHandlerMixin):
    """
    Base strategy class that provides common functionality.
    All strategies should inherit from this class.
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self._name = name
        self._parameters = parameters or {}
        self.logger = logging.getLogger(f"Strategy.{name}")
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_generated: Dict[str, List[Signal]] = {}
        
        # Performance tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Event bus will be set during initialization
        self.event_bus: Optional[EventBus] = None
        
        # Initialize with empty event bus initially
        super().__init__(None)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters.copy()
    
    async def initialize(self, event_bus: EventBus) -> None:
        """Initialize strategy with event bus"""
        self.event_bus = event_bus
        
        # Register event handlers
        self._register_event_handlers()
        
        # Strategy-specific initialization
        await self._initialize_strategy()
        
        self.logger.info(f"Strategy {self.name} initialized with parameters: {self.parameters}")
    
    @abstractmethod
    async def _initialize_strategy(self) -> None:
        """Strategy-specific initialization logic"""
        pass
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new bar data"""
        try:
            # Store bar in history
            if bar.symbol not in self.bars_history:
                self.bars_history[bar.symbol] = []
            
            # Check for duplicate timestamp before adding
            # Optimised duplicate handling: if the new bar has same timestamp as the last, replace it
            if self.bars_history[bar.symbol] and bar.timestamp == self.bars_history[bar.symbol][-1].timestamp:
                self.bars_history[bar.symbol][-1] = bar  # overwrite with latest values
            elif self.bars_history[bar.symbol] and bar.timestamp < self.bars_history[bar.symbol][-1].timestamp:
                # Out-of-order bar, ignore silently to avoid noise
                return None
            else:
                self.bars_history[bar.symbol].append(bar)
            
            # Keep only last N bars (configurable)
            max_bars = self._parameters.get('max_history_bars', 1500)
            if len(self.bars_history[bar.symbol]) > max_bars:
                self.bars_history[bar.symbol] = self.bars_history[bar.symbol][-max_bars:]
            
            # Generate signal
            signal = await self._analyze_bar(bar)
            
            if signal:
                # Store signal
                if bar.symbol not in self.signals_generated:
                    self.signals_generated[bar.symbol] = []
                self.signals_generated[bar.symbol].append(signal)
                
                self.logger.info(f"Signal generated for {bar.symbol}: {signal.signal_type}")
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error processing bar for {bar.symbol}: {e}")
            return None
    
    @abstractmethod
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate signal - implement in subclasses"""
        pass
    
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates"""
        try:
            self.positions[position.symbol] = position
            
            # Check for exit conditions
            if position.symbol in self.bars_history and self.bars_history[position.symbol]:
                latest_bar = self.bars_history[position.symbol][-1]
                return self.should_exit(position, latest_bar)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error handling position update for {position.symbol}: {e}")
            return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited"""
        try:
            # Check basic exit conditions
            exit_reasons = []
            
            # Stop loss
            if self._check_stop_loss(position, current_bar):
                exit_reasons.append("stop_loss")
            
            # Take profit
            if self._check_take_profit(position, current_bar):
                exit_reasons.append("take_profit")
            
            # Time exit
            if self._check_time_exit(position):
                exit_reasons.append("time_exit")
            
            # Strategy-specific exit conditions
            strategy_exit = self._check_strategy_exit(position, current_bar)
            if strategy_exit:
                exit_reasons.append(strategy_exit)
            
            if exit_reasons:
                signal_type = SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT
                
                return Signal(
                    signal_id="",
                    symbol=position.symbol,
                    signal_type=signal_type,
                    strength=1.0,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    metadata={"exit_reasons": exit_reasons}
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions for {position.symbol}: {e}")
            return None
    
    def _check_stop_loss(self, position: Position, current_bar: MarketData) -> bool:
        """Check stop loss condition"""
        stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)  # 5% default
        
        if position.quantity > 0:  # Long position
            stop_price = position.avg_price * (1 - stop_loss_pct)
            return current_bar.close <= stop_price
        else:  # Short position
            stop_price = position.avg_price * (1 + stop_loss_pct)
            return current_bar.close >= stop_price
    
    def _check_take_profit(self, position: Position, current_bar: MarketData) -> bool:
        """Check take profit condition"""
        take_profit_pct = self._parameters.get('take_profit_pct', 0.10)  # 10% default
        
        if position.quantity > 0:  # Long position
            target_price = position.avg_price * (1 + take_profit_pct)
            return current_bar.close >= target_price
        else:  # Short position
            target_price = position.avg_price * (1 - take_profit_pct)
            return current_bar.close <= target_price
    
    def _check_time_exit(self, position: Position) -> bool:
        """Check time-based exit condition"""
        max_hold_hours = self._parameters.get('max_hold_hours', 24)  # 24 hours default
        
        # Fix datetime timezone issue
        current_time = datetime.now(timezone.utc)
        
        # Make sure both timestamps are timezone-aware
        if position.entry_time.tzinfo is None:
            entry_time = position.entry_time.replace(tzinfo=timezone.utc)
        else:
            entry_time = position.entry_time
            
        hold_time = current_time - entry_time
        return hold_time > timedelta(hours=max_hold_hours)
    
    def _check_strategy_exit(self, position: Position, current_bar: MarketData) -> Optional[str]:
        """Override in subclasses for strategy-specific exit logic"""
        # Check Bollinger Climax Exit (solo en tendencia)
        bollinger_exit = self._check_bollinger_climax_exit(position, current_bar)
        if bollinger_exit:
            return bollinger_exit
        
        return None
    
    def _check_bollinger_climax_exit(self, position: Position, current_bar: MarketData) -> Optional[str]:
        """
        Bollinger Climax Exit: Salida cuando vela grande penetra >50% Bollinger superior
        SOLO en tendencia alcista (no en rebotes)
        """
        try:
            symbol = position.symbol
            
            # Solo para posiciones largas
            if position.quantity <= 0:
                return None
            
            # 1. Verificar si estamos en tendencia alcista
            if not self._is_in_uptrend(symbol, current_bar):
                return None
            
            # 2. Calcular Bollinger Bands
            bollinger_data = self._calculate_bollinger_bands(symbol)
            if not bollinger_data:
                return None
            
            upper_band = bollinger_data['upper']
            
            # 3. Verificar penetración de la vela (>50% por encima banda superior)
            vela_range = current_bar.high - current_bar.low
            penetration = max(0, current_bar.high - upper_band)
            
            if vela_range > 0 and (penetration / vela_range) < 0.5:
                return None  # Menos del 50% penetración
            
            # 4. Verificar que es una vela "grande" comparada con las anteriores
            if not self._is_large_candle(symbol, current_bar):
                return None
            
            self.logger.info(f"🎯 BOLLINGER CLIMAX EXIT detected for {symbol}: "
                           f"Penetration {penetration/vela_range*100:.1f}%, Large candle detected")
            
            return "bollinger_climax"
            
        except Exception as e:
            self.logger.error(f"Error checking Bollinger climax exit for {position.symbol}: {e}")
            return None
    
    def _is_in_uptrend(self, symbol: str, current_bar: MarketData) -> bool:
        """Detectar si estamos en tendencia alcista (no rebote)"""
        try:
            # Obtener datos históricos del símbolo
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return False
            
            bars = self.bars_history[symbol]
            if len(bars) < 50:
                return False
            
            # Calcular SMAs
            closes = [bar.close for bar in bars[-50:]]
            sma_20 = sum(closes[-20:]) / 20
            sma_50 = sum(closes) / 50
            
            # Condiciones de tendencia alcista:
            # 1. SMA(20) > SMA(50)
            # 2. Precio actual > SMA(20)
            # 3. Pendiente alcista en SMA(20)
            current_price = current_bar.close
            
            if len(closes) >= 25:
                sma_20_prev = sum(closes[-25:-5]) / 20
                slope_positive = sma_20 > sma_20_prev
            else:
                slope_positive = True
            
            # 4. Bollinger Bands en expansión (opcional)
            bollinger_expanding = self._is_bollinger_expanding(symbol)
            
            trend_conditions = [
                sma_20 > sma_50,           # Trend structure
                current_price > sma_20,    # Price above trend
                slope_positive,            # Ascending trend
                bollinger_expanding        # Expanding volatility
            ]
            
            trend_score = sum(trend_conditions)
            is_uptrend = trend_score >= 3  # Al menos 3 de 4 condiciones
            
            if is_uptrend:
                self.logger.debug(f"📈 {symbol} in uptrend: SMA20={sma_20:.3f}, SMA50={sma_50:.3f}, "
                                 f"Price={current_price:.3f}, Score={trend_score}/4")
            
            return is_uptrend
            
        except Exception as e:
            self.logger.error(f"Error detecting uptrend for {symbol}: {e}")
            return False
    
    def _calculate_bollinger_bands(self, symbol: str, period: int = 20, std_dev: float = 2.0) -> Optional[dict]:
        """Calcular Bollinger Bands"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return None
            
            bars = self.bars_history[symbol]
            if len(bars) < period:
                return None
            
            closes = [bar.close for bar in bars[-period:]]
            sma = sum(closes) / period
            
            # Calcular desviación estándar
            variance = sum((close - sma) ** 2 for close in closes) / period
            std = variance ** 0.5
            
            return {
                'middle': sma,
                'upper': sma + (std_dev * std),
                'lower': sma - (std_dev * std),
                'std': std
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating Bollinger Bands for {symbol}: {e}")
            return None
    
    def _is_large_candle(self, symbol: str, current_bar: MarketData, lookback: int = 15, multiplier: float = 1.5) -> bool:
        """Verificar si la vela actual es 'grande' comparada con las anteriores"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return False
            
            bars = self.bars_history[symbol]
            if len(bars) < lookback + 1:
                return False
            
            # Calcular tamaño promedio de las últimas velas (excluyendo la actual)
            recent_bars = bars[-(lookback+1):-1]  # Últimas N velas sin incluir actual
            avg_range = sum(bar.high - bar.low for bar in recent_bars) / len(recent_bars)
            
            # Tamaño de la vela actual
            current_range = current_bar.high - current_bar.low
            
            is_large = current_range >= (avg_range * multiplier)
            
            if is_large:
                self.logger.debug(f"📏 {symbol} Large candle: Current={current_range:.3f} vs "
                                 f"Avg={avg_range:.3f} (x{current_range/avg_range:.2f})")
            
            return is_large
            
        except Exception as e:
            self.logger.error(f"Error checking large candle for {symbol}: {e}")
            return False
    
    def _is_bollinger_expanding(self, symbol: str, lookback: int = 10) -> bool:
        """Verificar si las Bollinger Bands están en expansión"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return False
            
            bars = self.bars_history[symbol]
            if len(bars) < 30:
                return False
            
            # Comparar ancho de Bollinger actual vs anterior
            current_bb = self._calculate_bollinger_bands(symbol)
            if not current_bb:
                return False
            
            # Calcular BB width actual
            current_width = current_bb['upper'] - current_bb['lower']
            
            # Calcular BB width promedio de períodos anteriores
            past_widths = []
            for i in range(lookback):
                if len(bars) >= 20 + i + 1:
                    past_bars = bars[-(20+i+1):-(i+1)] if i > 0 else bars[-20:]
                    if len(past_bars) >= 20:
                        closes = [bar.close for bar in past_bars]
                        sma = sum(closes) / 20
                        variance = sum((close - sma) ** 2 for close in closes) / 20
                        std = variance ** 0.5
                        width = 2 * 2.0 * std  # 2 std devs * 2 (upper and lower)
                        past_widths.append(width)
            
            if not past_widths:
                return False
            
            avg_past_width = sum(past_widths) / len(past_widths)
            is_expanding = current_width > avg_past_width
            
            if is_expanding:
                self.logger.debug(f"📊 {symbol} Bollinger expanding: Current={current_width:.3f} vs "
                                 f"Past={avg_past_width:.3f}")
            
            return is_expanding
            
        except Exception as e:
            self.logger.error(f"Error checking Bollinger expansion for {symbol}: {e}")
            return False
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """
        Calculate position size - VERSIÓN SIMPLIFICADA Y ROBUSTA
        """
        try:
            # Parámetros básicos
            max_position_value = float(self._parameters.get('max_position_value', 1000.0))
            min_position_value = float(self._parameters.get('min_position_value', 100.0))
            min_quantity = int(self._parameters.get('min_quantity', 1))
            
            price = float(signal.price)
            
            if price <= 0:
                self.logger.warning(f"Invalid price {price} for {signal.symbol}")
                return 0
            
            # LÓGICA SIMPLIFICADA: Usar valor target
            target_value = min(max_position_value, capital * 0.1)  # Máximo 10% del capital
            target_value = max(target_value, min_position_value)   # Mínimo valor requerido
            
            # Calcular cantidad
            quantity = int(target_value / price)
            
            # Aplicar límites
            quantity = max(quantity, min_quantity)
            
            # Verificar que no exceda el capital disponible
            position_value = quantity * price
            commission = max(quantity * 0.005, 1.0)  # Commission estimate
            total_cost = position_value + commission
            
            if total_cost > capital:
                # Reducir cantidad para que quepa en el capital
                available_for_position = capital - commission
                if available_for_position > 0:
                    quantity = max(int(available_for_position / price), 1)
                else:
                    return 0
            
            # Verificar límites finales
            final_value = quantity * price
            if final_value > max_position_value * 1.1:  # 10% tolerance
                quantity = int(max_position_value / price)
            
            self.logger.debug(
                f"Position size for {signal.symbol}: {quantity} shares "
                f"@ ${price:.2f} = ${final_value:.2f}"
            )
            
            return max(quantity, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {signal.symbol}: {e}")
            return 0
            
            # Calculate maximum possible quantity based on max position value
            max_possible_quantity = int(max_position_value // signal.price)
            
            # If we can't even buy the minimum quantity within position limits, return 0
            if max_possible_quantity < min_quantity:
                self.logger.warning(
                    f"Cannot meet minimum quantity {min_quantity} for {signal.symbol} "
                    f"at ${signal.price:.2f} within max position value ${max_position_value:.2f}"
                )
                return 0
                
            # Start with the maximum possible quantity within position limits
            quantity = max_possible_quantity
            
            # Calculate position value
            position_value = signal.price * quantity
            
            # Ensure we don't exceed max position value (handle floating point precision)
            while position_value > max_position_value * 1.001 and quantity > 0:  # 0.1% tolerance
                quantity -= 1
                position_value = signal.price * quantity
            
            # Final validation
            if quantity < min_quantity or position_value > max_position_value * 1.001:
                self.logger.error(
                    f"Failed to calculate valid position size for {signal.symbol}: "
                    f"price=${signal.price:.2f}, qty={quantity}, value=${position_value:.2f}, "
                    f"max=${max_position_value:.2f}, min_qty={min_quantity}"
                )
                return 0
                
            self.logger.debug(
                f"Position size for {signal.symbol}: {quantity} shares at ${signal.price:.2f} "
                f"= ${position_value:.2f} (max: ${max_position_value:.2f})"
            )
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {signal.symbol}: {e}")
            return 0
    
    # Helper methods for technical analysis
    def get_bars_df(self, symbol: str, count: Optional[int] = None) -> pd.DataFrame:
        """Get bars as pandas DataFrame"""
        if symbol not in self.bars_history:
            return pd.DataFrame()
        
        bars = self.bars_history[symbol]
        if count:
            bars = bars[-count:]
        
        data = []
        for bar in bars:
            data.append({
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def calculate_sma(self, symbol: str, period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        return df['close'].tail(period).mean()
    
    def calculate_ema(self, symbol: str, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        df = self.get_bars_df(symbol, period * 2)  # Get more data for EMA
        if len(df) < period:
            return None
        
        return df['close'].ewm(span=period).mean().iloc[-1]
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        df = self.get_bars_df(symbol, period * 2)
        if len(df) < period + 1:
            return None
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    
    def calculate_macd(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
        """Calculate MACD"""
        df = self.get_bars_df(symbol, slow * 3)
        if len(df) < slow:
            return None
        
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line.iloc[-1],
            'signal': signal_line.iloc[-1],
            'histogram': histogram.iloc[-1]
        }
    
    def calculate_bollinger_bands(self, symbol: str, period: int = 20, std_dev: float = 2) -> Optional[dict]:
        """Calculate Bollinger Bands"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        closes = df['close'].tail(period)
        sma = closes.mean()
        std = closes.std()
        
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }
    
    def calculate_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        df = self.get_bars_df(symbol, period + 1)
        if len(df) < period:
            return None
        
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1]
    
    # Event handlers
    @event_handler("position_opened")
    async def on_position_opened(self, event):
        """Handle position opened events"""
        position = event.data["position"]
        self.logger.info(f"Position opened: {position.symbol} {position.quantity}@{position.avg_price}")
    
    @event_handler("position_closed")
    async def on_position_closed(self, event):
        """Handle position closed events"""
        position = event.data["position"]
        self.trades_count += 1
        
        if position.unrealized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.logger.info(f"Position closed: {position.symbol} PnL: {position.unrealized_pnl:.2f}")
    
    # Performance metrics
    def get_performance_stats(self) -> dict:
        """Get strategy performance statistics"""
        win_rate = (self.winning_trades / self.trades_count * 100) if self.trades_count > 0 else 0
        
        return {
            "trades_count": self.trades_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "active_positions": len(self.positions)
        }
    
    def _can_open_new_position(self, symbol: str, current_price: float, signal_type: str = 'long') -> dict:
        """
        🚫 SISTEMA ANTI-MARTINGALA CON PIRAMIDACIÓN INTELIGENTE
        
        Determina si se puede abrir una nueva posición, evitando martingala 
        y permitiendo piramidación cuando hay tendencia alcista.
        
        Args:
            symbol: Símbolo a evaluar
            current_price: Precio actual de la acción
            signal_type: Tipo de señal ('long' o 'short')
            
        Returns:
            dict: {
                'can_open': bool,
                'reason': str,
                'position_action': str  # 'new', 'pyramid', 'blocked'
            }
        """
        try:
            # Configuración desde parámetros
            allow_pyramiding = self._parameters.get('allow_pyramiding', False)
            max_pyramid_levels = self._parameters.get('max_pyramid_levels', 2)
            pyramid_price_threshold = self._parameters.get('pyramid_price_threshold', 0.02)  # +2% mínimo
            
            # VERIFICAR LÍMITES DE EXPOSICIÓN ANTES DE CUALQUIER POSICIÓN
            exposure_check = self._check_portfolio_exposure_limits(symbol, current_price)
            if not exposure_check['can_open']:
                return exposure_check
            
            # Verificar si ya existe posición
            existing_position = self._get_existing_position_info(symbol)
            
            if not existing_position:
                # No hay posición existente - permitir nueva posición
                return {
                    'can_open': True,
                    'reason': 'Nueva posición',
                    'position_action': 'new'
                }
            
            # Ya existe posición - evaluar martingala vs piramidación
            avg_entry_price = existing_position.get('avg_price', current_price)
            current_quantity = existing_position.get('quantity', 0)
            entry_count = existing_position.get('entry_count', 1)
            
            # REGLA 1: Nunca permitir posiciones en dirección opuesta
            existing_direction = 'long' if current_quantity > 0 else 'short'
            if signal_type != existing_direction:
                return {
                    'can_open': False,
                    'reason': f'Posición existente es {existing_direction}, señal es {signal_type}',
                    'position_action': 'blocked'
                }
            
            # REGLA 2: Lógica inteligente - distinguir entre MARTINGALA y PULLBACK permitido
            price_change_pct = (current_price - avg_entry_price) / avg_entry_price
            
            # Primero analizar oportunidad de piramidación (incluye pullbacks)
            pyramid_analysis = self._analyze_pyramid_opportunity(symbol, current_price, avg_entry_price, existing_position)
            
            # Si el análisis de piramidación lo rechaza Y es precio por debajo, entonces es martingala
            if not pyramid_analysis['can_pyramid'] and current_price < avg_entry_price * (1 - 0.003):  # -0.3% tolerancia estricta
                return {
                    'can_open': False,
                    'reason': f'🚫 MARTINGALA DETECTADA: {pyramid_analysis["reason"]}',
                    'position_action': 'blocked'
                }
            
            # REGLA 3: Evaluar PIRAMIDACIÓN (solo si está habilitada)
            if not allow_pyramiding:
                return {
                    'can_open': False,
                    'reason': 'Piramidación deshabilitada en configuración',
                    'position_action': 'blocked'
                }
            
            # REGLA 4: Verificar límites de piramidación
            if entry_count >= max_pyramid_levels:
                return {
                    'can_open': False,
                    'reason': f'Máximo {max_pyramid_levels} niveles de piramidación alcanzado',
                    'position_action': 'blocked'
                }
            
            # REGLA 5: Usar el análisis de piramidación ya calculado
            if not pyramid_analysis['can_pyramid']:
                return {
                    'can_open': False,
                    'reason': pyramid_analysis['reason'],
                    'position_action': 'blocked'
                }
            
            # REGLA 6: Verificar tendencia alcista para piramidación
            if not self._is_in_uptrend_for_pyramiding(symbol, current_price):
                return {
                    'can_open': False,
                    'reason': 'No hay tendencia alcista confirmada para piramidación',
                    'position_action': 'blocked'
                }
            
            # ✅ PIRAMIDACIÓN PERMITIDA
            return {
                'can_open': True,
                'reason': f'🔼 PIRAMIDACIÓN {pyramid_analysis["type"]}: {pyramid_analysis["description"]} (nivel {entry_count + 1}/{max_pyramid_levels})',
                'position_action': 'pyramid'
            }
            
        except Exception as e:
            self.logger.error(f"Error evaluating position control for {symbol}: {e}")
            return {
                'can_open': False,
                'reason': f'Error en evaluación: {e}',
                'position_action': 'blocked'
            }
    
    def _get_existing_position_info(self, symbol: str) -> Optional[dict]:
        """
        Obtener información de posición existente desde entry_signals
        """
        try:
            # Verificar en entry_signals (usado por estrategias individuales)
            if hasattr(self, 'entry_signals') and isinstance(self.entry_signals, dict):
                if symbol in self.entry_signals:
                    info = self.entry_signals[symbol]
                    return {
                        'avg_price': info.get('entry_price', 0),
                        'quantity': info.get('quantity', 100),  # Estimado
                        'entry_count': info.get('entry_count', 1),
                        'direction': info.get('direction', 'long')
                    }
            
            # Verificar en positions (usado por el sistema)
            if hasattr(self, 'positions') and isinstance(self.positions, dict):
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    return {
                        'avg_price': pos.avg_price,
                        'quantity': pos.quantity,
                        'entry_count': getattr(pos, 'entry_count', 1),
                        'direction': 'long' if pos.quantity > 0 else 'short'
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting existing position info for {symbol}: {e}")
            return None
    
    def _is_in_uptrend_for_pyramiding(self, symbol: str, current_price: float) -> bool:
        """
        Verificar tendencia alcista específicamente para piramidación
        Criterios más estrictos que para entrada inicial
        """
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return False
            
            bars = self.bars_history[symbol]
            if len(bars) < 20:
                return False
            
            # Criterios para piramidación (más estrictos)
            recent_bars = bars[-20:]
            closes = [bar.close for bar in recent_bars]
            
            # 1. SMA corto > SMA largo
            sma_5 = sum(closes[-5:]) / 5
            sma_10 = sum(closes[-10:]) / 10
            sma_20 = sum(closes) / 20
            
            # 2. Precio actual por encima de SMAs
            above_smas = current_price > sma_5 > sma_10 > sma_20
            
            # 3. Pendiente alcista en SMA corto
            sma_5_prev = sum(closes[-8:-3]) / 5
            sma_slope_positive = sma_5 > sma_5_prev
            
            # 4. Volumen por encima del promedio (si disponible)
            volume_ok = True
            if len(recent_bars) >= 10:
                recent_volumes = [bar.volume for bar in recent_bars[-10:]]
                avg_volume = sum(recent_volumes[:-1]) / (len(recent_volumes) - 1)
                current_volume = recent_bars[-1].volume
                volume_ok = current_volume >= avg_volume * 0.8  # Al menos 80% del promedio
            
            # 5. Sin caídas bruscas recientes
            max_recent_drop = 0
            for i in range(1, min(5, len(closes))):
                drop = (closes[-i-1] - closes[-i]) / closes[-i-1]
                max_recent_drop = max(max_recent_drop, drop)
            
            no_sharp_drops = max_recent_drop < 0.03  # Máximo 3% de caída
            
            conditions = [above_smas, sma_slope_positive, volume_ok, no_sharp_drops]
            uptrend_score = sum(conditions)
            
            is_uptrend = uptrend_score >= 3  # Al menos 3 de 4 condiciones
            
            if is_uptrend:
                self.logger.debug(f"📈 {symbol} uptrend for pyramiding: SMAs({sma_5:.2f}>{sma_10:.2f}>{sma_20:.2f}), "
                                f"Score: {uptrend_score}/4")
            
            return is_uptrend
            
        except Exception as e:
            self.logger.error(f"Error checking uptrend for pyramiding {symbol}: {e}")
            return False
    
    def _analyze_pyramid_opportunity(self, symbol: str, current_price: float, avg_entry_price: float, existing_position: dict) -> dict:
        """
        🔼 ANÁLISIS INTELIGENTE DE PIRAMIDACIÓN
        
        Determina si es momento adecuado para piramidación considerando:
        A) BREAKOUT: Precio rompe por encima con momentum
        B) PULLBACK: Retroceso controlado en tendencia alcista fuerte
        
        Returns:
            dict: {
                'can_pyramid': bool,
                'type': str,  # 'BREAKOUT' o 'PULLBACK'
                'reason': str,
                'description': str
            }
        """
        try:
            # Configuración
            breakout_threshold = self._parameters.get('pyramid_price_threshold', 0.025)  # +2.5% para breakout
            pullback_max = self._parameters.get('pyramid_pullback_max', 0.015)         # -1.5% máximo pullback
            pullback_min = self._parameters.get('pyramid_pullback_min', 0.005)         # -0.5% mínimo pullback
            
            price_change_pct = (current_price - avg_entry_price) / avg_entry_price
            
            # ESCENARIO A: BREAKOUT (precio por encima con momentum)
            if price_change_pct >= breakout_threshold:
                # Verificar que tenga momentum alcista reciente
                if self._has_recent_momentum(symbol, current_price):
                    return {
                        'can_pyramid': True,
                        'type': 'BREAKOUT',
                        'reason': f'Breakout +{price_change_pct*100:.1f}% con momentum',
                        'description': f'Precio ${current_price:.2f} vs promedio ${avg_entry_price:.2f}'
                    }
                else:
                    return {
                        'can_pyramid': False,
                        'type': 'BREAKOUT_NO_MOMENTUM',
                        'reason': f'Breakout +{price_change_pct*100:.1f}% pero sin momentum reciente',
                        'description': 'Falta confirmación de momentum'
                    }
            
            # ESCENARIO B: PULLBACK (retroceso controlado en tendencia fuerte)
            elif -pullback_max <= price_change_pct <= -pullback_min:
                # Verificar que estemos en tendencia alcista fuerte
                trend_strength = self._get_trend_strength(symbol, current_price)
                
                if trend_strength >= 0.75:  # Tendencia fuerte (75%+ score)
                    # Verificar que el pullback no sea demasiado rápido/violento
                    pullback_quality = self._analyze_pullback_quality(symbol, current_price)
                    
                    if pullback_quality['is_healthy']:
                        return {
                            'can_pyramid': True,
                            'type': 'PULLBACK',
                            'reason': f'Pullback saludable {price_change_pct*100:.1f}% en tendencia fuerte',
                            'description': f'Tendencia {trend_strength*100:.0f}%, pullback controlado'
                        }
                    else:
                        return {
                            'can_pyramid': False,
                            'type': 'PULLBACK_UNHEALTHY',
                            'reason': f'Pullback {price_change_pct*100:.1f}% demasiado violento: {pullback_quality["reason"]}',
                            'description': 'Pullback de mala calidad'
                        }
                else:
                    return {
                        'can_pyramid': False,
                        'type': 'PULLBACK_WEAK_TREND',
                        'reason': f'Pullback {price_change_pct*100:.1f}% pero tendencia débil ({trend_strength*100:.0f}%)',
                        'description': 'Tendencia insuficiente para pullback'
                    }
            
            # ESCENARIO C: FUERA DE RANGO (ni breakout ni pullback válido)
            else:
                if price_change_pct > 0:
                    return {
                        'can_pyramid': False,
                        'type': 'INSUFFICIENT_BREAKOUT',
                        'reason': f'Precio +{price_change_pct*100:.1f}% insuficiente (necesita +{breakout_threshold*100:.1f}%)',
                        'description': 'Breakout insuficiente'
                    }
                else:
                    return {
                        'can_pyramid': False,
                        'type': 'EXCESSIVE_PULLBACK',
                        'reason': f'Pullback {price_change_pct*100:.1f}% excesivo (máximo -{pullback_max*100:.1f}%)',
                        'description': 'Pullback demasiado profundo'
                    }
            
        except Exception as e:
            self.logger.error(f"Error analyzing pyramid opportunity for {symbol}: {e}")
            return {
                'can_pyramid': False,
                'type': 'ERROR',
                'reason': f'Error en análisis: {e}',
                'description': 'Error técnico'
            }
    
    def _has_recent_momentum(self, symbol: str, current_price: float) -> bool:
        """Verificar momentum alcista reciente para breakouts"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return False
            
            bars = self.bars_history[symbol]
            if len(bars) < 5:
                return False
            
            # Verificar momentum en últimas 3-5 velas
            recent_bars = bars[-5:]
            closes = [bar.close for bar in recent_bars]
            
            # 1. Precio actual > precio de hace 3 velas
            momentum_check1 = current_price > closes[-4] if len(closes) >= 4 else True
            
            # 2. Tendencia creciente en precio
            price_trend = sum(closes[i] > closes[i-1] for i in range(1, len(closes)))
            momentum_check2 = price_trend >= len(closes) * 0.6  # 60% de velas alcistas
            
            # 3. Volumen por encima del promedio (más permisivo para testing)
            if len(recent_bars) >= 3:
                recent_volumes = [bar.volume for bar in recent_bars[-3:]]
                avg_volume = sum(recent_volumes) / len(recent_volumes)
                current_volume = recent_bars[-1].volume
                momentum_check3 = current_volume >= avg_volume * 0.6  # Más permisivo: 60%
            else:
                momentum_check3 = True
            
            has_momentum = momentum_check1 and momentum_check2 and momentum_check3
            
            if has_momentum:
                self.logger.debug(f"📈 {symbol} has recent momentum: price_trend={price_trend}/{len(closes)}, volume_ok={momentum_check3}")
            
            return has_momentum
            
        except Exception as e:
            self.logger.error(f"Error checking recent momentum for {symbol}: {e}")
            return False
    
    def _get_trend_strength(self, symbol: str, current_price: float) -> float:
        """Obtener fuerza de tendencia (0.0 - 1.0)"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return 0.0
            
            bars = self.bars_history[symbol]
            if len(bars) < 20:
                return 0.0
            
            recent_bars = bars[-20:]
            closes = [bar.close for bar in recent_bars]
            
            # Múltiples indicadores de fuerza de tendencia
            strength_factors = []
            
            # 1. SMAs alineadas
            sma_5 = sum(closes[-5:]) / 5
            sma_10 = sum(closes[-10:]) / 10
            sma_20 = sum(closes) / 20
            
            if current_price > sma_5 > sma_10 > sma_20:
                strength_factors.append(1.0)
            elif current_price > sma_5 > sma_10:
                strength_factors.append(0.7)
            elif current_price > sma_5:
                strength_factors.append(0.4)
            else:
                strength_factors.append(0.0)
            
            # 2. Pendiente de SMA corta
            if len(closes) >= 8:
                sma_5_prev = sum(closes[-8:-3]) / 5
                slope_strength = min((sma_5 - sma_5_prev) / sma_5_prev / 0.02, 1.0)  # Normalizar a 2%
                strength_factors.append(max(slope_strength, 0.0))
            else:
                strength_factors.append(0.5)
            
            # 3. Consistencia alcista
            up_candles = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
            consistency = up_candles / (len(closes) - 1)
            strength_factors.append(consistency)
            
            # 4. Distancia del precio respecto a SMA larga
            price_distance = (current_price - sma_20) / sma_20
            distance_strength = min(price_distance / 0.05, 1.0)  # Normalizar a 5%
            strength_factors.append(max(distance_strength, 0.0))
            
            # Promedio ponderado
            trend_strength = sum(strength_factors) / len(strength_factors)
            
            return min(max(trend_strength, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating trend strength for {symbol}: {e}")
            return 0.0
    
    def _analyze_pullback_quality(self, symbol: str, current_price: float) -> dict:
        """Analizar calidad del pullback (saludable vs violento)"""
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return {'is_healthy': False, 'reason': 'Sin datos históricos'}
            
            bars = self.bars_history[symbol]
            if len(bars) < 10:
                return {'is_healthy': False, 'reason': 'Historial insuficiente'}
            
            recent_bars = bars[-10:]
            
            # 1. Velocidad del pullback (no debe ser demasiado rápido)
            closes = [bar.close for bar in recent_bars]
            max_single_drop = 0
            for i in range(1, len(closes)):
                drop = (closes[i-1] - closes[i]) / closes[i-1]
                max_single_drop = max(max_single_drop, drop)
            
            # No más de 3% de caída en una sola vela
            speed_ok = max_single_drop <= 0.03
            
            # 2. Volumen durante pullback (no debe ser pánico)
            if len(recent_bars) >= 5:
                pullback_volumes = [bar.volume for bar in recent_bars[-5:]]
                normal_volumes = [bar.volume for bar in recent_bars[-10:-5]]
                
                avg_pullback_vol = sum(pullback_volumes) / len(pullback_volumes)
                avg_normal_vol = sum(normal_volumes) / len(normal_volumes)
                
                # Volumen de pullback no debe ser > 2x el volumen normal
                volume_ok = avg_pullback_vol <= avg_normal_vol * 2.0
            else:
                volume_ok = True
            
            # 3. Patrón de pullback (no debe ser colapso continuo)
            consecutive_down = 0
            max_consecutive_down = 0
            for i in range(1, len(closes)):
                if closes[i] < closes[i-1]:
                    consecutive_down += 1
                    max_consecutive_down = max(max_consecutive_down, consecutive_down)
                else:
                    consecutive_down = 0
            
            # No más de 3 velas consecutivas bajando
            pattern_ok = max_consecutive_down <= 3
            
            # Evaluación final
            quality_checks = [speed_ok, volume_ok, pattern_ok]
            healthy_count = sum(quality_checks)
            
            is_healthy = healthy_count >= 2  # Al menos 2 de 3 criterios
            
            if not is_healthy:
                reasons = []
                if not speed_ok:
                    reasons.append(f'caída rápida {max_single_drop*100:.1f}%')
                if not volume_ok:
                    reasons.append(f'volumen excesivo {avg_pullback_vol/avg_normal_vol:.1f}x')
                if not pattern_ok:
                    reasons.append(f'colapso {max_consecutive_down} velas')
                
                reason = ', '.join(reasons)
            else:
                reason = 'Pullback controlado y saludable'
            
            return {
                'is_healthy': is_healthy,
                'reason': reason,
                'speed_ok': speed_ok,
                'volume_ok': volume_ok,
                'pattern_ok': pattern_ok
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing pullback quality for {symbol}: {e}")
            return {'is_healthy': False, 'reason': f'Error: {e}'}
    
    def _check_portfolio_exposure_limits(self, symbol: str, current_price: float) -> dict:
        """
        Verificar límites de exposición del portfolio ANTES de generar señales
        
        Args:
            symbol: Símbolo a evaluar
            current_price: Precio actual
            
        Returns:
            dict: {'can_open': bool, 'reason': str, 'position_action': str}
        """
        try:
            # Obtener límites desde parámetros (con fallbacks)
            max_position_value = self._parameters.get('max_position_value', 100.0)
            
            # Calcular valor estimado de nueva posición
            min_quantity = self._parameters.get('min_quantity', 5)
            estimated_position_value = current_price * min_quantity
            
            # 1. VERIFICAR LÍMITE POR POSICIÓN INDIVIDUAL
            if estimated_position_value > max_position_value:
                return {
                    'can_open': False,
                    'reason': f'Posición estimada ${estimated_position_value:.2f} excede límite ${max_position_value:.2f}',
                    'position_action': 'blocked'
                }
            
            # 2. VERIFICAR EXPOSICIÓN TOTAL DEL PORTFOLIO (si tenemos acceso al trading engine)
            if hasattr(self, '_trading_engine') and self._trading_engine:
                current_exposure = self._calculate_current_exposure()
                max_portfolio_exposure = self._parameters.get('max_portfolio_exposure', 100.0)
                
                projected_exposure = current_exposure + estimated_position_value
                if projected_exposure > max_portfolio_exposure:
                    return {
                        'can_open': False,
                        'reason': f'Exposición proyectada ${projected_exposure:.2f} excede límite ${max_portfolio_exposure:.2f}',
                        'position_action': 'blocked'
                    }
            
            # Todo OK - puede abrir posición
            return {
                'can_open': True,
                'reason': 'Límites de exposición OK',
                'position_action': 'new'
            }
            
        except Exception as e:
            self.logger.error(f"Error checking portfolio exposure limits: {e}")
            return {
                'can_open': False,
                'reason': f'Error verificando límites: {e}',
                'position_action': 'blocked'
            }
    
    def _calculate_current_exposure(self) -> float:
        """Calcular exposición actual del portfolio"""
        try:
            if not hasattr(self, '_trading_engine') or not self._trading_engine:
                return 0.0
            
            total_exposure = 0.0
            for symbol, position in self._trading_engine.positions.items():
                if hasattr(position, 'market_value'):
                    total_exposure += abs(position.market_value)
                elif hasattr(position, 'quantity') and hasattr(position, 'current_price'):
                    total_exposure += abs(position.quantity * position.current_price)
            
            return total_exposure
            
        except Exception as e:
            self.logger.error(f"Error calculating current exposure: {e}")
            return 0.0