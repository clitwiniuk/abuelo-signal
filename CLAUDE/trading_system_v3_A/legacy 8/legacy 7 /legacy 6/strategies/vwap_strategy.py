"""
Estrategia VWAP para Smallcaps - 100% Compatible con trading_system_v2
Basada en la estructura de OptimizedGapGoStrategy
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class VWAPSmallcapsStrategy(BaseStrategy):
    """
    Estrategia VWAP para smallcaps - 100% Compatible con trading_system_v2
    Estructura idéntica a OptimizedGapGoStrategy
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Parámetros por defecto para estrategia VWAP
        default_params = {
            # === Parámetros Técnicos ===
            'vwap_period': 20,
            'momentum_period': 5,
            
            # === Filtros Smallcaps ===
            'min_price': 1.0,
            'max_price': 20.0,
            'volatility_threshold': 0.03,
            'volume_threshold': 1.5,
            'min_volume_ratio': 0.5,
            
            # === Gestión de Riesgo ===
            'risk_management_mode': 'dynamic',
            'initial_stop_loss': 0.05,
            'trailing_stop_distance': 0.08,
            'partial_take_profit': 0.12,
            'max_hold_days': 30,
            
            # === Señales ===
            'vwap_entry_threshold': 0.99,
            'momentum_entry_threshold': 0.01,
            'vwap_exit_threshold': 1.01,
            'momentum_exit_threshold': -0.015,
            
            # === Parámetros Generales ===
            'confidence_base': 0.3,
            'confidence_multiplier': 10.0,
            'max_confidence': 0.9,
            
            # === Trading ===
            'max_position_value': 400.0,
            'min_position_value': 80.0,
            'max_risk_per_trade': 0.02,
            'min_quantity': 5,
            'position_size': 0.02,
            'max_positions': 5,
            
            # === Timing Controls ===
            'market_open_hour': 9.5,
            'no_entry_after': 13.0,
            'max_hold_time': 90,
            'cooldown_period': 60,
            
            # === Trading Limits ===
            'max_daily_trades': 5,
            'max_concurrent_positions': 3,
            'daily_loss_limit': 150.0,
            
            # === Commission & Costs ===
            'commission_per_share': 0.005,
            'min_commission': 1.0,
            'slippage_bps': 5,
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("VWAPSmallcaps", default_params)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # CRITICAL: Assign parameters as instance attributes
        for key, value in self._parameters.items():
            setattr(self, key, value)
        
        # Strategy state - IGUAL que GapGo
        self.active_positions = {}           
        self.last_trade_times = {}          
        self.daily_trades = {}              
        self.daily_pnl = {}                 
        
        # VWAP specific state
        self.vwap_cache = {}  # Cache para VWAP calculados
        self.momentum_cache = {}  # Cache para momentum
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
    async def _initialize_strategy(self) -> None:
        """Inicialización de la estrategia"""
        self.logger.info("Inicializando estrategia VWAP Smallcaps")
        self.logger.info(f"Parámetros: VWAP_period={self.vwap_period}, "
                        f"stop_loss={self.initial_stop_loss}, "
                        f"take_profit={self.partial_take_profit}")
        
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Análisis principal - ESTRUCTURA IDÉNTICA a GapGo"""
        symbol = bar.symbol
        
        # DEBUG: STOP LOSS DESACTIVADO - Comentado para debugging
        # exit_signal = await self._check_exit_conditions(symbol, bar)
        # if exit_signal:
        #     return exit_signal
        
        # 2. Si ya tiene posición, NO hacer nada más
        if symbol in self.active_positions:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Ya tiene posición activa")
            return None
        
        # 3. Control de nuevas posiciones
        if not self._can_take_new_position(symbol, bar):
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: No puede tomar nueva posición")
            return None
        
        # 4. Verificar si es suitable para smallcaps
        if not self._is_smallcap_suitable(symbol, bar):
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: No cumple criterios smallcap")
            return None
        
        # 5. Validaciones básicas
        if not self._is_valid_entry_time(bar.timestamp):
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Fuera de horario válido: {bar.timestamp.hour}:{bar.timestamp.minute}")
            return None
        
        # 6. Evaluar condiciones de entrada VWAP
        entry_analysis = await self._evaluate_vwap_entry_conditions(symbol, bar)
        
        if not entry_analysis.get('qualified', False):
            return None
        
        # 7. CREAR ENTRADA
        price = bar.close
        
        # Determinar si es entrada en largo o en corto
        vwap_value = entry_analysis.get('vwap_value', price)
        enable_shorts = getattr(self, 'enable_shorts', False)
        
        # Si el precio está por debajo del VWAP -> LONG (con pullback)
        # Si el precio está por encima del VWAP y shorts habilitados -> SHORT
        if price < vwap_value:
            # ENTRADA INMEDIATA - Sin esperar pullback
            signal_type = SignalType.LONG
            side = 'long'
            stop_loss = price * (1 - self.initial_stop_loss)
            take_profit = price * (1 + self.partial_take_profit)
            entry_type = "LONG"
        elif price > vwap_value and enable_shorts:
            signal_type = SignalType.SHORT
            side = 'short'
            stop_loss = price * (1 + self.initial_stop_loss)
            take_profit = price * (1 - self.partial_take_profit)
            entry_type = "SHORT"
        else:
            # No hay señal válida
            return None
            
        # Log unificado para entradas
        self.logger.info(f"🎯 [VWAP ENTRY] {symbol}: {entry_type} @ ${price:.2f} "
                       f"Score:{entry_analysis.get('score', 0):.2f}")
        
        
        # Registrar posición INMEDIATAMENTE
        self.active_positions[symbol] = {
            'entry_price': price,
            'entry_time': bar.timestamp,
            'highest_price': price,
            'lowest_price': price,
            'side': side,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'partial_taken': False,
            'partial_price': None,
            'max_price': price,
            'max_pnl_pct': 0.0,
            'stop_loss_price': stop_loss
        }
        
        # Update tracking
        self._update_trade_tracking(symbol, bar.timestamp)
        
        self.logger.info(f"🎯 [VWAP ENTRY] {symbol}: LONG @ ${price:.2f} "
                        f"Score:{entry_analysis.get('score', 0):.2f}")
        
        return Signal(
            signal_id=f"vwap_entry_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
            symbol=symbol,
            signal_type=signal_type,
            strength=entry_analysis.get('score', 1.0),
            price=price,
            timestamp=bar.timestamp,
            metadata={
                'strategy': 'VWAPSmallcaps',
                'vwap_value': entry_analysis.get('vwap_value', 0),
                'momentum': entry_analysis.get('momentum', 0),
                'conditions_met': entry_analysis.get('conditions_met', 0),
                'stop_loss': self.active_positions[symbol]['stop_loss'],
                'take_profit': self.active_positions[symbol]['take_profit'],
                'is_entry': True
            })
    
    def _can_take_new_position(self, symbol: str, bar: MarketData) -> bool:
        """Control de nuevas posiciones - IDÉNTICO a GapGo"""
        current_date = bar.timestamp.date()
        current_time = bar.timestamp
        
        # 1. Ya tiene posición activa
        if symbol in self.active_positions:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Ya tiene posición activa")
            return False
        
        # 2. Cooldown
        if symbol in self.last_trade_times:
            time_since_last = (current_time - self.last_trade_times[symbol]).total_seconds() / 60
            if time_since_last < self.cooldown_period:
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: En cooldown, minutos desde última operación: {time_since_last:.1f}")
                return False
        
        # 3. Límite de trades diarios
        daily_trades = self.daily_trades.get(current_date, 0)
        if daily_trades >= self.max_daily_trades:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Límite diario alcanzado: {daily_trades}/{self.max_daily_trades}")
            return False
        
        # 4. Límite de posiciones concurrentes
        if len(self.active_positions) >= self.max_concurrent_positions:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Límite de posiciones concurrentes: {len(self.active_positions)}/{self.max_concurrent_positions}")
            return False
        
        # 5. Límite de pérdida diaria
        daily_pnl = self.daily_pnl.get(current_date, 0.0)
        if daily_pnl <= -self.daily_loss_limit:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Límite de pérdida diaria alcanzado: ${daily_pnl:.2f}")
            return False
        
        # 6. Horario válido
        hour_decimal = current_time.hour + current_time.minute / 60.0
        if not (self.market_open_hour <= hour_decimal <= self.no_entry_after):
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Fuera de horario válido: {hour_decimal:.2f}, rango permitido: {self.market_open_hour}-{self.no_entry_after}")
            return False
        
        return True
    
    def _is_smallcap_suitable(self, symbol: str, bar: MarketData) -> bool:
        """Verificar si es adecuado para smallcaps"""
        try:
            current_price = bar.close
            
            # Filtro de precio
            if current_price < self.min_price or current_price > self.max_price:
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Precio fuera de rango: ${current_price:.2f}, rango permitido: ${self.min_price:.2f}-${self.max_price:.2f}")
                return False
            
            # Filtro de volumen mínimo
            if bar.volume < 10000:  # Volumen mínimo absoluto
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Volumen insuficiente: {bar.volume}, mínimo requerido: 10000")
                return False
            
            # Verificar volatilidad si hay suficiente historia
            bars = self.bars_history.get(symbol, [])
            if len(bars) >= 20:
                recent_closes = [b.close for b in bars[-20:]]
                volatility = pd.Series(recent_closes).pct_change().std()
                if volatility < self.volatility_threshold:
                    self.logger.debug(f"[VWAP-DEBUG] {symbol}: Volatilidad insuficiente: {volatility:.4f}, mínimo requerido: {self.volatility_threshold:.4f}")
                    return False
                else:
                    self.logger.debug(f"[VWAP-DEBUG] {symbol}: Volatilidad OK: {volatility:.4f} >= {self.volatility_threshold:.4f}")
            else:
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Historia insuficiente: {len(bars)} barras, mínimo requerido: 20")
            
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Cumple criterios smallcap")
            return True
            
        except Exception as e:
            self.logger.debug(f"Error checking smallcap suitability for {symbol}: {e}")
            return False
    
    async def _evaluate_vwap_entry_conditions(self, symbol: str, bar: MarketData) -> Dict:
        """Evaluar condiciones de entrada VWAP"""
        try:
            bars = self.bars_history.get(symbol, [])
            if len(bars) < max(self.vwap_period, self.momentum_period):
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Historia insuficiente: {len(bars)} barras, mínimo requerido: {max(self.vwap_period, self.momentum_period)}")
                return {'qualified': False, 'score': 0}
            
            conditions = {}
            
            # 1. Calcular VWAP
            vwap_value = self._calculate_vwap(bars, self.vwap_period)
            current_price = bar.close
            
            # 2. Condición VWAP: precio por debajo de VWAP
            conditions['price_below_vwap'] = current_price < (vwap_value * self.vwap_entry_threshold)
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Precio/VWAP: {current_price:.2f}/{vwap_value:.2f} = {current_price/vwap_value:.4f}, umbral: {self.vwap_entry_threshold} -> {conditions['price_below_vwap']}")
            
            # 3. Calcular momentum
            closes = [b.close for b in bars[-self.momentum_period-1:]]
            if len(closes) >= 2:
                momentum = (closes[-1] - closes[0]) / closes[0]
                conditions['positive_momentum'] = momentum > self.momentum_entry_threshold
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Momentum: {momentum:.4f}, umbral: {self.momentum_entry_threshold} -> {conditions['positive_momentum']}")
            else:
                momentum = 0
                conditions['positive_momentum'] = False
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Datos insuficientes para calcular momentum")
            
            # 4. Condición de volumen
            conditions['volume_ok'] = self._check_volume_condition(symbol, bar)
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Volumen OK: {conditions['volume_ok']}")
            
            # 5. Condición de precio válido
            conditions['price_in_range'] = self.min_price <= current_price <= self.max_price
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Precio en rango: {current_price:.2f} en [{self.min_price:.2f}, {self.max_price:.2f}] -> {conditions['price_in_range']}")
            
            # Scoring
            total_conditions = len(conditions)
            conditions_met = sum(conditions.values())
            score = conditions_met / total_conditions if total_conditions > 0 else 0
            
            # Requiere al menos 3 de 4 condiciones
            qualified = conditions_met >= 3
            
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Condiciones cumplidas: {conditions_met}/{total_conditions}, Score: {score:.2f}, Qualified: {qualified}")
            
            return {
                'qualified': qualified,
                'score': score,
                'conditions': conditions,
                'conditions_met': conditions_met,
                'vwap_value': vwap_value,
                'momentum': momentum
            }
            
        except Exception as e:
            self.logger.error(f"Error evaluating VWAP conditions for {symbol}: {e}")
            return {'qualified': False, 'score': 0}
    
    def _calculate_vwap(self, bars: List[MarketData], period: int) -> float:
        """Calcular VWAP móvil"""
        try:
            if len(bars) < period:
                return bars[-1].close if bars else 0
            
            # Usar últimas 'period' barras
            recent_bars = bars[-period:]
            
            total_price_volume = 0
            total_volume = 0
            
            for bar in recent_bars:
                typical_price = (bar.high + bar.low + bar.close) / 3
                total_price_volume += typical_price * bar.volume
                total_volume += bar.volume
            
            if total_volume > 0:
                return total_price_volume / total_volume
            else:
                return recent_bars[-1].close
                
        except Exception as e:
            self.logger.error(f"Error calculating VWAP: {e}")
            return bars[-1].close if bars else 0
    
    def _check_volume_condition(self, symbol: str, bar: MarketData) -> bool:
        """Verificar condición de volumen"""
        try:
            bars = self.bars_history.get(symbol, [])
            if len(bars) < 10:
                result = bar.volume > 5000  # Mínimo absoluto
                self.logger.debug(f"[VWAP-DEBUG] {symbol}: Historia insuficiente para volumen, usando mínimo absoluto: {bar.volume} > 5000 -> {result}")
                return result
            
            # Volumen promedio últimas 10 barras
            recent_volumes = [b.volume for b in bars[-10:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            # Condición: volumen actual > threshold * promedio
            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            result = volume_ratio >= self.volume_threshold
            
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Ratio volumen: {bar.volume}/{avg_volume:.1f} = {volume_ratio:.2f}, umbral: {self.volume_threshold} -> {result}")
            return result
            
        except Exception as e:
            self.logger.debug(f"[VWAP-DEBUG] {symbol}: Error en check_volume_condition: {e}")
            return bar.volume > 5000
    
    async def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Condiciones de salida - ESTRUCTURA IDÉNTICA a GapGo"""
        if symbol not in self.active_positions:
            return None
        
        position = self.active_positions[symbol]
        entry_price = position['entry_price']
        current_price = bar.close
        side = position['side']
        
        # Update position tracking
        self._update_position_risk(symbol, current_price, bar.timestamp)
        
        # Calculate PnL
        if side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        exit_reason = None
        exit_type = 'full'
        
        # 1. Ganancia parcial
        if pnl_pct >= self.partial_take_profit and not position['partial_taken']:
            exit_reason = 'partial_profit'
            exit_type = 'partial'
        
        # 2. Stop Loss
        elif pnl_pct <= -self.initial_stop_loss:
            exit_reason = 'stop_loss'
        
        # 3. Trailing Stop (si está en modo dinámico)
        elif (self.risk_management_mode == 'dynamic' and 
              pnl_pct >= 0.03 and  # Activación trailing
              current_price <= position['stop_loss_price']):
            exit_reason = 'trailing_stop'
        
        # 4. Señal técnica de salida
        elif self._check_technical_exit(symbol, bar, position):
            exit_reason = 'technical_exit'
        
        # 5. Tiempo límite
        time_held = (bar.timestamp - position['entry_time']).total_seconds() / 60
        if time_held >= self.max_hold_time:
            exit_reason = 'time_limit'
        
        # 6. Market close - convert to US Eastern timezone
        if bar.timestamp.tzinfo is None:
            us_bar_time = bar.timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
        else:
            us_bar_time = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
        
        if us_bar_time.hour >= 15 and us_bar_time.minute >= 30:
            exit_reason = 'market_close'
        
        if exit_reason:
            # Calculate position details
            position_size = self._calculate_position_size(entry_price)
            
            if side == 'long':
                trade_pnl = position_size * (current_price - entry_price)
                pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            else:  # short
                trade_pnl = position_size * (entry_price - current_price)
                pnl_pct = (entry_price - current_price) / entry_price if entry_price > 0 else 0
            
            # Subtract commissions
            commission = max(position_size * self.commission_per_share, self.min_commission)
            trade_pnl -= commission * 2
            
            # Update tracking
            is_winner = trade_pnl > 0
            self.logger.info(f"[TRADE RESULT] {symbol} {side}: PnL=${trade_pnl:.2f}, PnL%={pnl_pct*100:.2f}%, Winner={is_winner}")
            self._update_exit_tracking(symbol, bar.timestamp, trade_pnl, is_winner)
            
            # Handle position based on exit type
            if exit_type == 'partial':
                position['partial_taken'] = True
                position['partial_price'] = current_price
                self.logger.info(f"[PARTIAL EXIT] {symbol}: Taking partial profit @ ${current_price:.2f}")
            else:
                # Full exit - remove position
                self.active_positions.pop(symbol, None)
                self.logger.info(f"[FULL EXIT] {symbol}: {exit_reason} @ ${current_price:.2f} "
                               f"(PnL: {pnl_pct*100:.1f}%, ${trade_pnl:.2f})")
            
            # Create exit signal
            signal_type = SignalType.EXIT_LONG if side == 'long' else SignalType.EXIT_SHORT
            return Signal(
                signal_id=f"vwap_exit_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
                symbol=symbol,
                signal_type=signal_type,
                strength=1.0,
                price=current_price,
                timestamp=bar.timestamp,
                metadata={
                    'reason': exit_reason,
                    'exit_type': exit_type,
                    'pnl_pct': pnl_pct * 100,
                    'pnl_dollars': trade_pnl,
                    'entry_price': entry_price,
                    'position_size': position_size,
                    'time_held_minutes': time_held,
                    'is_exit': True,
                    'strategy': 'VWAPSmallcaps'
                }
            )
        
        return None
    
    def _update_position_risk(self, symbol: str, current_price: float, current_time: datetime):
        """Actualizar niveles de riesgo - IDÉNTICO a GapGo"""
        if symbol not in self.active_positions:
            return
        
        position = self.active_positions[symbol]
        entry_price = position['entry_price']
        current_pnl_pct = (current_price - entry_price) / entry_price
        
        # Update highest/lowest prices
        position['highest_price'] = max(position.get('highest_price', current_price), current_price)
        position['lowest_price'] = min(position.get('lowest_price', current_price), current_price)
        
        # Update max values
        if current_price > position['max_price']:
            position['max_price'] = current_price
            position['max_pnl_pct'] = current_pnl_pct
        
        # Update trailing stop if in dynamic mode
        if self.risk_management_mode == 'dynamic':
            max_price = position['max_price']
            trailing_stop_price = max_price * (1 - self.trailing_stop_distance)
            initial_stop_price = entry_price * (1 - self.initial_stop_loss)
            position['stop_loss_price'] = max(trailing_stop_price, initial_stop_price)
    
    def _check_technical_exit(self, symbol: str, bar: MarketData, position: Dict) -> bool:
        """Verificar condiciones técnicas de salida"""
        try:
            bars = self.bars_history.get(symbol, [])
            if len(bars) < self.vwap_period:
                return False
            
            # Calcular VWAP actual
            vwap_value = self._calculate_vwap(bars, self.vwap_period)
            current_price = bar.close
            
            # Calcular momentum
            closes = [b.close for b in bars[-self.momentum_period-1:]]
            if len(closes) >= 2:
                momentum = (closes[-1] - closes[0]) / closes[0]
            else:
                momentum = 0
            
            # Condiciones de salida técnica:
            # 1. Precio por encima de VWAP
            # 2. Momentum negativo
            # 3. Solo si hay ganancia mínima
            entry_price = position['entry_price']
            pnl_pct = (current_price - entry_price) / entry_price
            
            price_above_vwap = current_price > (vwap_value * self.vwap_exit_threshold)
            negative_momentum = momentum < self.momentum_exit_threshold
            min_profit = pnl_pct > 0.02  # 2% ganancia mínima
            
            return price_above_vwap and negative_momentum and min_profit
            
        except Exception:
            return False
    
    def _calculate_position_size(self, price: float) -> int:
        """Calcular tamaño de posición - IDÉNTICO a GapGo"""
        try:
            max_value = float(self.max_position_value)
            min_value = float(self.min_position_value)
            min_qty = int(self.min_quantity)
            
            if price <= 0:
                return min_qty
            
            # Target value
            target_value = (min_value + max_value) / 2
            target_qty = int(target_value / price)
            
            # Apply limits
            max_qty = int(max_value / price)
            min_qty_by_value = max(int(min_value / price), min_qty)
            
            quantity = max(min_qty_by_value, min(target_qty, max_qty))
            
            return max(quantity, 1)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return int(self.min_quantity)
    
    def _update_trade_tracking(self, symbol: str, timestamp: datetime):
        """Actualizar tracking de trades - IDÉNTICO a GapGo"""
        date = timestamp.date()
        self.daily_trades[date] = self.daily_trades.get(date, 0) + 1
        self.last_trade_times[symbol] = timestamp
    
    def _update_exit_tracking(self, symbol: str, timestamp: datetime, pnl: float, is_winner: bool):
        """Actualizar tracking al cerrar posición - IDÉNTICO a GapGo"""
        date = timestamp.date()
        
        self.total_trades += 1
        self.total_pnl += pnl
        
        # Corregido: Simplificar la lógica para determinar si es un trade ganador
        if pnl > 0:
            self.winning_trades += 1
            self.logger.debug(f"Trade ganador registrado: {symbol} con PnL=${pnl:.2f}")
        
        self.daily_pnl[date] = self.daily_pnl.get(date, 0.0) + pnl
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        self.logger.info(f"[TRACKING] {symbol}: PnL=${pnl:.2f} | "
                        f"Total: {self.total_trades} | WR: {win_rate:.1f}%")
    
    def _is_valid_entry_time(self, timestamp) -> bool:
        """Verificar horario válido - IDÉNTICO a GapGo"""
        try:
            hour_decimal = timestamp.hour + timestamp.minute / 60.0
            return self.market_open_hour <= hour_decimal <= self.no_entry_after
        except:
            return False
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Interface pública - IDÉNTICO a GapGo"""
        return self._calculate_position_size(signal.price)
    
    def get_strategy_status(self) -> Dict:
        """Estado actual de la estrategia - IDÉNTICO a GapGo"""
        return {
            'name': self.name,
            'active_positions': len(self.active_positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_pnl': self.total_pnl,
            'positions': list(self.active_positions.keys())
        }
    
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For VWAP strategy, we don't need special logic on position updates
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
                        strategy_name="VWAP",
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
                        strategy_name="VWAP",
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
