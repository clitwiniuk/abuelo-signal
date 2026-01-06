# strategies/optimized_gap_go_strategy.py
"""
Gap & Go Strategy: FIXED VERSION - REALISTIC PARAMETERS
Corrige problemas de overtrading, exit conditions y position sizing
VERSION ULTRA-CORREGIDA para generar trades reales
"""

from typing import Optional, Dict, Any, Deque, List
import numpy as np
import pandas as pd
import logging
import collections
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position


class OptimizedGapGoStrategy(BaseStrategy):
    """
    Gap & Go Strategy optimizada - VERSION REALISTA
    
    FIXES APLICADOS:
    1. Parámetros más realistas y alcanzables
    2. Condiciones de entrada más flexibles
    3. Volúmenes más bajos y reales
    4. Horario de trading extendido
    5. Menos restricciones de overtrading
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Parámetros REALISTAS y ALCANZABLES
        default_params = {
            # Gap Detection - MODERADAMENTE ESTRICTO
            'gap_percent_threshold': 1.5,        # Era 2.5 → Reducir a 1.5% (más gaps detectados)
            'min_gap_percent': 2.0,              # Era 3.0 → Reducir a 2.0% (más alcanzable)
            'max_gap_percent': 20.0,             # Era 15.0 → Volver a 20% (más rango)
            'gap_confirmation_bars': 0,          # Era 1 → Sin confirmación (más rápido)
            
            # Volume Requirements - MODERADAMENTE EXIGENTE
            'volume_multiplier': 1.8,            # Era 2.5 → Reducir a 1.8x (más alcanzable)
            'min_volume': 15000,                 # Era 25000 → Reducir a 15K (más accesible)
            'volume_confirmation_bars': 1,       # Era 2 → Reducir a 1 (más rápido)
            'min_daily_volume': 100000,          # Era 200000 → Reducir a 100K (más stocks)
            
            # Entry Conditions - MODERADAMENTE SELECTIVO
            'breakout_buffer': 0.008,            # Era 0.005 → Aumentar ligeramente
            'momentum_confirmation': True,       # Mantener True pero hacer más permisivo
            'min_conditions_met': 3,             # Era 4 → Reducir a 3 de 5 condiciones (60%)
            
            # Risk Management - BALANCEADO
            'stop_loss_pct': 0.03,               # Era 0.025 → Aumentar a 3% (menos stops)
            'take_profit_pct': 0.06,             # Era 0.05 → Aumentar a 6% (más paciencia)
            'trailing_stop_pct': 0.018,          # Era 0.015 → Aumentar ligeramente
            'trailing_activation': 0.025,        # Era 0.02 → Activar más tarde
            
            # Position Sizing - MODERADO
            'max_position_value': 400.0,         # Era 300.0 → Aumentar a $400
            'min_position_value': 80.0,          # Era 100.0 → Reducir a $80
            'max_risk_per_trade': 0.02,          # Era 0.015 → Aumentar a 2%
            'min_quantity': 5,                   # Era 10 → Reducir a 5 (más accesible)
            
            # Timing Controls - MÁS FLEXIBLE
            'market_open_hour': 9.5,             # 9:30 AM
            'no_entry_after': 12.0,              # Era 11.0 → Extender a 12:00 PM (2.5 horas)
            'max_hold_time': 90,                 # Era 60 → Aumentar a 1.5 horas
            'cooldown_period': 60,               # Era 120 → Reducir a 1 hora
            
            # Trading Limits - MODERADAMENTE ESTRICTO
            'max_daily_trades': 3,               # Era 2 → Aumentar a 3 trades por día
            'max_concurrent_positions': 2,       # Era 1 → Permitir 2 posiciones simultáneas
            'daily_loss_limit': 150.0,           # Era 100.0 → Aumentar a $150
            
            # Quality Filters - MODERADO
            'min_price': 1.5,                   # Era 2.0 → Reducir a $1.5 (más stocks)
            'max_price': 75.0,                  # Era 50.0 → Aumentar a $75
            
            # Commission & Costs
            'commission_per_share': 0.005,       # Mantener
            'min_commission': 1.0,               # Mantener
            'slippage_bps': 5,                   # Mantener
            
            # Scanner Integration - BALANCEADO
            'trust_scanner_gap': True,
            'scanner_gap_timeout': 75,           # Era 60 → Aumentar a 75 min (más tiempo)
            'auto_detect_gaps': True,            # Mantener activo
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("OptimizedGapGo", default_params)

        # CRITICAL FIX: Assign parameters as instance attributes
        # This fixes the bug where parameters were not accessible in the strategy
        for key, value in self._parameters.items():
            setattr(self, key, value)
        
        # Verify critical parameters are set
        self.stop_loss_pct = self._parameters.get('stop_loss_pct', 0.03)
        self.take_profit_pct = self._parameters.get('take_profit_pct', 0.06)
        self.gap_percent_threshold = self._parameters.get('gap_percent_threshold', 1.5)
        self.min_gap_percent = self._parameters.get('min_gap_percent', 2.0)
        self.max_daily_trades = self._parameters.get('max_daily_trades', 3)
        
        # Debug logging
        self.logger.info(f"PARAMS ASSIGNED: stop_loss={self.stop_loss_pct:.1f}%, "
                        f"take_profit={self.take_profit_pct*100:.1f}%, "
                        f"gap_threshold={self.gap_percent_threshold:.1f}%")
        
        # Strategy state
        self.scanner_gaps = {}
        self.active_positions = {}           
        self.last_trade_times = {}          
        self.daily_trades = {}              
        self.daily_pnl = {}                 
        self.prev_closes = {}               
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
    async def _initialize_strategy(self) -> None:
        """Inicialización de la estrategia"""
        self.logger.info("Inicializando estrategia Gap & Go optimizada - VERSION CORREGIDA")
        self.logger.info(f"Parámetros clave: gap_min={self._parameters['min_gap_percent']}%, "
                        f"stop_loss={self._parameters['stop_loss_pct']}%, "
                        f"max_daily_trades={self._parameters['max_daily_trades']}")
        
    async def add_scanner_gap(self, symbol: str, gap_data: Dict) -> None:
        """Añadir gap detectado por scanner externo"""
        if abs(gap_data['gap_percentage']) < self._parameters['min_gap_percent']:
            return
            
        self.scanner_gaps[symbol] = {
            'gap_percent': gap_data['gap_percentage'],
            'direction': 'up' if gap_data['gap_percentage'] > 0 else 'down',
            'volume_ratio': gap_data.get('volume_ratio', 0),
            'price': gap_data['current_price'],
            'timestamp': gap_data.get('timestamp', datetime.now()),
            'scanner_score': gap_data.get('score', 0),
            'confirmed': True,  # Auto-confirmed para ser menos restrictivo
            'confirmation_bars': 1
        }
        
        self.logger.info(f"Scanner gap added: {symbol} {gap_data['gap_percentage']:.1f}%")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Análisis con logging mejorado"""
        symbol = bar.symbol
        
        # LOGGING TEMPORAL PARA DEBUG
        if not hasattr(self, '_analyze_counter'):
            self._analyze_counter = 0
        self._analyze_counter += 1
        
        # Log cada 200 barras para no saturar
        if self._analyze_counter % 200 == 0:
            self.logger.info(f"[ANALYZE_DEBUG] Processing bar #{self._analyze_counter} at {bar.timestamp}")
            self.logger.info(f"[ANALYZE_DEBUG] prev_closes: {len(self.prev_closes)} symbols")
            self.logger.info(f"[ANALYZE_DEBUG] scanner_gaps: {len(self.scanner_gaps)} symbols")
        
        # 1. Check exit conditions PRIMERO
        exit_signal = await self._check_exit_conditions(symbol, bar)
        if exit_signal:
            return exit_signal
        
        # 2. Si ya tiene posición, NO hacer nada más
        if symbol in self.active_positions:
            return None
        
        # 3. Control MÁS FLEXIBLE de nuevas posiciones
        if not self._can_take_new_position_flexible(symbol, bar):
            return None
        
        # 4. Auto-detect gaps (con logging mejorado)
        if self._parameters.get('auto_detect_gaps', True):
            self._auto_detect_gap(symbol, bar)
        
        # 5. Si no hay gap detectado, salir
        if symbol not in self.scanner_gaps:
            # Log solo si es horario de trading temprano
            current_hour = bar.timestamp.hour
            current_minute = bar.timestamp.minute
            if current_hour == 9 and current_minute >= 30 and current_minute <= 35:
                self.logger.debug(f"[ANALYZE_DEBUG] {symbol}: No gap detected at {bar.timestamp}")
            return None
        
        gap_data = self.scanner_gaps[symbol]
        
        # Log cuando encontramos un gap para analizar
        self.logger.info(f"[ANALYZE_WITH_GAP] {symbol}: Analyzing with gap {gap_data['gap_percent']:.1f}% at {bar.timestamp}")
        
        # 6. Validaciones básicas
        if not self._is_valid_entry_time(bar.timestamp):
            self.logger.debug(f"[{symbol}] Fuera de horario de entrada")
            return None
        
        if self._is_gap_expired(gap_data, bar.timestamp):
            self.scanner_gaps.pop(symbol, None)
            self.logger.debug(f"[{symbol}] Gap expirado")
            return None
        
        # 7. ENTRADA MÁS FLEXIBLE: Solo verificar condiciones básicas
        entry_analysis = await self._evaluate_entry_conditions_flexible(symbol, bar, gap_data)
        
        if not entry_analysis.get('qualified', False):
            score = entry_analysis.get('score', 0)
            conditions_met = entry_analysis.get('conditions_met', 0)
            total_conditions = len(entry_analysis.get('conditions', {}))
            self.logger.info(f"[{symbol}] Entry conditions not met: {conditions_met}/{total_conditions} (score: {score:.2f})")
            return None
        
        # SI LLEGAMOS AQUÍ: CREAR ENTRADA
        gap_pct = abs(gap_data.get('gap_percent', 0))
        price = bar.close
        signal_type = SignalType.LONG  # Solo longs
        
        # Registrar posición INMEDIATAMENTE
        self.active_positions[symbol] = {
            'gap_data': gap_data,
            'entry_price': price,
            'entry_time': bar.timestamp,
            'highest_price': price,
            'lowest_price': price,
            'side': 'long',
            'stop_loss': price * (1 - self._parameters.get('stop_loss_pct', 0.04)),
            'take_profit': price * (1 + self._parameters.get('take_profit_pct', 0.08))
        }
        
        # Update tracking
        self._update_trade_tracking(symbol, bar.timestamp)
        
        self.logger.info(f"🎯 [ENTRY CONFIRMED] {symbol}: LONG @ ${price:.2f} "
                        f"Gap:{gap_pct:.1f}% Score:{entry_analysis.get('score', 0):.2f}")
        
        return Signal(
            signal_id=f"entry_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
            symbol=symbol,
            signal_type=signal_type,
            strength=entry_analysis.get('score', 1.0),
            price=price,
            timestamp=bar.timestamp,
            metadata={
                'strategy': 'OptimizedGapGo',
                'gap_percent': gap_pct,
                'conditions_met': entry_analysis.get('conditions_met', 0),
                'total_conditions': len(entry_analysis.get('conditions', {})),
                'stop_loss': self.active_positions[symbol]['stop_loss'],
                'take_profit': self.active_positions[symbol]['take_profit'],
                'is_entry': True
            })
    
    def _can_take_new_position_flexible(self, symbol: str, bar: MarketData) -> bool:
        """Control MÁS FLEXIBLE de nuevas posiciones"""
        current_date = bar.timestamp.date()
        current_time = bar.timestamp
        
        # 1. Ya tiene posición activa en este símbolo
        if symbol in self.active_positions:
            return False
        
        # 2. Cooldown más corto (30 min vs 2 horas)
        if symbol in self.last_trade_times:
            time_since_last = (current_time - self.last_trade_times[symbol]).total_seconds() / 60
            if time_since_last < self._parameters.get('cooldown_period', 30):
                return False
        
        # 3. Más trades diarios permitidos (5 vs 1)
        daily_trades = self.daily_trades.get(current_date, 0)
        if daily_trades >= self._parameters.get('max_daily_trades', 5):
            return False
        
        # 4. Más posiciones concurrentes (3 vs 1)
        if len(self.active_positions) >= self._parameters.get('max_concurrent_positions', 3):
            return False
        
        # 5. Límite de pérdida diaria más alto ($200 vs $25)
        daily_pnl = self.daily_pnl.get(current_date, 0.0)
        if daily_pnl <= -self._parameters.get('daily_loss_limit', 200.0):
            return False
        
        # 6. Horario extendido (9:30-14:00 vs 9:30-10:30)
        hour_decimal = current_time.hour + current_time.minute / 60.0
        if not (self._parameters['market_open_hour'] <= hour_decimal <= self._parameters['no_entry_after']):
            return False
        
        # 7. REMOVIDO: Restricción de días de la semana (permitir todos los días)
        
        return True
    
    async def _evaluate_entry_conditions_flexible(self, symbol: str, bar: MarketData, gap_data: Dict) -> Dict:
        """Evaluación MÁS FLEXIBLE de condiciones de entrada"""
        conditions = {}
        
        # 1. PRECIO - Gap y precio en rango
        gap_pct = abs(gap_data.get('gap_percent', 0))
        conditions['gap_size_adequate'] = gap_pct >= self._parameters.get('min_gap_percent', 1.5)
        
        # 2. PRECIO EN RANGO
        price = bar.close
        conditions['price_adequate'] = (self._parameters.get('min_price', 1.0) <= 
                                       price <= self._parameters.get('max_price', 100.0))
        
        # 3. DIRECCIÓN (solo gaps UP)
        conditions['direction_ok'] = gap_data.get('direction') == 'up'
        
        # 4. VOLUMEN (más flexible)
        conditions['volume_ok'] = await self._check_volume_conditions_flexible(symbol, bar)
        
        # 5. OPCIONAL: Momentum (si está habilitado)
        if self._parameters.get('momentum_confirmation', False):
            conditions['momentum_ok'] = self._check_momentum_confirmation(symbol, bar, gap_data)
        
        # 6. OPCIONAL: No gap fill (más permisivo)
        conditions['no_gap_fill'] = self._check_gap_fill_risk_flexible(bar, gap_data)
        
        # Scoring MÁS FLEXIBLE
        total_conditions = len(conditions)
        conditions_met = sum(conditions.values())
        score = conditions_met / total_conditions if total_conditions > 0 else 0
        
        # Requiere solo MAYORÍA de condiciones (60% vs 100%)
        min_conditions_needed = max(2, int(total_conditions * 0.6))  # Al menos 2, o 60%
        qualified = conditions_met >= min_conditions_needed
        
        self.logger.debug(f"[{symbol}] Entry conditions: {conditions_met}/{total_conditions} "
                         f"(score: {score:.2f}, qualified: {qualified}, need: {min_conditions_needed})")
        
        return {
            'qualified': qualified,
            'score': score,
            'conditions': conditions,
            'conditions_met': conditions_met
        }
    
    async def _check_volume_conditions_flexible(self, symbol: str, bar: MarketData) -> bool:
        """Verificar condiciones de volumen MÁS FLEXIBLES"""
        try:
            bars = self.bars_history.get(symbol, [])
            if len(bars) < 10:  # Menos historial requerido (10 vs 20)
                return True  # Aceptar si no hay suficiente historia
            
            # Volumen promedio últimas 10 barras (vs 20)
            recent_volumes = [b.volume for b in bars[-10:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            # Condiciones más flexibles
            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            min_multiplier = self._parameters.get('volume_multiplier', 1.5)  # 1.5x vs 2.5x
            min_absolute = self._parameters.get('min_volume', 5000)  # 5K vs 200K
            
            # Solo UNA condición necesaria (vs ambas)
            relative_ok = volume_ratio >= min_multiplier
            absolute_ok = bar.volume >= min_absolute
            
            result = relative_ok or absolute_ok  # OR vs AND
            
            self.logger.debug(f"[{symbol}] Volume: {bar.volume:,} "
                             f"(ratio: {volume_ratio:.1f}x vs {min_multiplier}x, "
                             f"absolute: {absolute_ok}, relative: {relative_ok}) = {result}")
            
            return result
            
        except Exception as e:
            self.logger.debug(f"Volume check error for {symbol}: {e}")
            return True  # Default to accept on error
    
    def _check_gap_fill_risk_flexible(self, bar: MarketData, gap_data: Dict) -> bool:
        """Verificar riesgo de gap fill MÁS PERMISIVO"""
        try:
            gap_pct = abs(gap_data.get('gap_percent', 0)) / 100.0
            
            # Solo preocuparse por gaps grandes (>5%)
            if gap_pct < 0.05:
                return True  # Gaps pequeños, no importa
            
            # Para gaps grandes, verificar que no esté llenando demasiado
            current_price = bar.close
            
            if gap_data.get('direction') == 'up':
                estimated_prev_close = bar.open / (1 + gap_pct)
                # Más permisivo: solo rechazar si está muy cerca del fill
                fill_threshold = estimated_prev_close * (1 + 0.005)  # 0.5% buffer vs 2%
                return current_price > fill_threshold
            
            return True  # Default to accept
            
        except Exception:
            return True
    
    def _check_momentum_confirmation(self, symbol: str, bar: MarketData, gap_data: Dict) -> bool:
        """Confirmar momentum en la dirección del gap"""
        try:
            bars = self.bars_history.get(symbol, [])
            if len(bars) < 2:  # Menos historia requerida
                return True
            
            # Solo verificar última barra
            if gap_data.get('direction') == 'up':
                # Para gap up: precio actual por encima de apertura
                return bar.close >= bar.open
            else:
                # Para gap down: precio actual por debajo de apertura
                return bar.close <= bar.open
                
        except Exception:
            return True  # Default to accept if can't calculate
    
    async def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Exit conditions MEJORADAS"""
        if symbol not in self.active_positions:
            return None
        
        position = self.active_positions[symbol]
        entry_price = position['entry_price']
        current_price = bar.close
        side = position['side']
        
        # Update highest/lowest prices para trailing stop
        position['highest_price'] = max(position.get('highest_price', current_price), current_price)
        position['lowest_price'] = min(position.get('lowest_price', current_price), current_price)
        
        # Calculate PnL percentage
        if side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        exit_reason = None
        
        # 1. STOP LOSS
        stop_loss_threshold = self._parameters['stop_loss_pct']
        if pnl_pct <= -stop_loss_threshold:
            exit_reason = 'stop_loss'
        
        # 2. TAKE PROFIT
        elif pnl_pct >= self._parameters['take_profit_pct']:
            exit_reason = 'take_profit'
        
        # 3. TRAILING STOP
        elif pnl_pct >= self._parameters.get('trailing_activation', 0.03):
            trailing_distance = self._parameters['trailing_stop_pct']
            
            if side == 'long':
                trailing_stop_price = position['highest_price'] * (1 - trailing_distance)
                if current_price <= trailing_stop_price:
                    exit_reason = 'trailing_stop'
        
        # 4. TIME LIMIT
        time_held = (bar.timestamp - position['entry_time']).total_seconds() / 60
        if time_held >= self._parameters['max_hold_time']:
            exit_reason = 'time_limit'
        
        # 5. MARKET CLOSE
        elif bar.timestamp.hour >= 15 and bar.timestamp.minute >= 30:
            exit_reason = 'market_close'
        
        if exit_reason:
            # Calculate position size and final PnL
            position_size = self._calculate_position_size(entry_price)
            
            # Calculate P&L in dollars
            if side == 'long':
                trade_pnl = position_size * (current_price - entry_price)
            else:
                trade_pnl = position_size * (entry_price - current_price)
            
            # Subtract commissions
            commission = max(position_size * self._parameters.get('commission_per_share', 0.005), 
                           self._parameters.get('min_commission', 1.0))
            trade_pnl -= commission * 2  # Entry + Exit commissions
            
            # Update tracking
            is_winner = trade_pnl > 0
            self._update_exit_tracking(symbol, bar.timestamp, trade_pnl, is_winner)
            
            # Clean up position ANTES de crear la señal
            self.active_positions.pop(symbol, None)
            
            self.logger.info(f"[EXIT] {symbol}: {exit_reason} @ ${current_price:.2f} "
                           f"(Entry: ${entry_price:.2f}, PnL: {pnl_pct*100:.1f}%, ${trade_pnl:.2f})")
            
            # Crear señal de salida
            signal_type = SignalType.EXIT_LONG if side == 'long' else SignalType.EXIT_SHORT
            return Signal(
                signal_id=f"exit_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
                symbol=symbol,
                signal_type=signal_type,
                strength=1.0,
                price=current_price,
                timestamp=bar.timestamp,
                metadata={
                    'reason': exit_reason,
                    'pnl_pct': pnl_pct * 100,
                    'pnl_dollars': trade_pnl,
                    'entry_price': entry_price,
                    'position_size': position_size,
                    'time_held_minutes': time_held,
                    'is_exit': True,
                    'strategy': 'OptimizedGapGo'
                }
            )
        
        return None
    
    def _calculate_position_size(self, price: float) -> int:
        """Calcular tamaño de posición MEJORADO"""
        try:
            max_value = self._parameters['max_position_value']
            min_value = self._parameters['min_position_value']
            min_qty = self._parameters['min_quantity']
            
            if price <= 0:
                return min_qty
            
            # Cantidad basada en valor target (promedio entre min y max)
            target_value = (min_value + max_value) / 2
            target_qty = int(target_value / price)
            
            # Aplicar límites
            max_qty_by_value = int(max_value / price)
            min_qty_by_value = max(int(min_value / price), min_qty)
            
            # Usar target pero dentro de límites
            quantity = max(min_qty_by_value, min(target_qty, max_qty_by_value))
            
            position_value = quantity * price
            
            self.logger.debug(f"Position sizing: price=${price:.2f}, qty={quantity}, "
                             f"value=${position_value:.2f}")
            
            return max(quantity, 1)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return self._parameters.get('min_quantity', 5)
    
    def _update_trade_tracking(self, symbol: str, timestamp: datetime):
        """Actualizar tracking de trades"""
        date = timestamp.date()
        
        # Update daily trades count
        self.daily_trades[date] = self.daily_trades.get(date, 0) + 1
        
        # Update last trade time for symbol
        self.last_trade_times[symbol] = timestamp
        
        self.logger.info(f"[TRADE TRACKING] {symbol} - Daily trades: {self.daily_trades[date]}")
    
    def _update_exit_tracking(self, symbol: str, timestamp: datetime, pnl: float, is_winner: bool):
        """Actualizar tracking al cerrar posición"""
        date = timestamp.date()
        
        # Update totals
        self.total_trades += 1
        self.total_pnl += pnl
        
        if is_winner and pnl > 0:
            self.winning_trades += 1
        
        # Update daily P&L
        self.daily_pnl[date] = self.daily_pnl.get(date, 0.0) + pnl
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        self.logger.info(f"[EXIT TRACKING] {symbol}: PnL=${pnl:.2f} ({'WIN' if is_winner and pnl > 0 else 'LOSS'}) "
                        f"| Total: {self.total_trades} | WR: {win_rate:.1f}%")
    
    def _auto_detect_gap(self, symbol: str, bar: MarketData) -> None:
        """Auto-detectar gaps CORREGIDO - Cambiar hora de guardado"""
        try:
            current_time = bar.timestamp
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_date = current_time.date()
            
            # LOGGING DETALLADO - TEMPORAL PARA DEBUG
            if not hasattr(self, '_log_counter'):
                self._log_counter = 0
            self._log_counter += 1
            
            # Log cada 100 barras para no saturar
            if self._log_counter % 100 == 0:
                self.logger.info(f"[GAP_DEBUG] {symbol} #{self._log_counter}: {current_time} (h={current_hour}, m={current_minute})")
            
            # PARTE 1: GUARDAR PREV_CLOSE AL FINAL DEL DÍA (CAMBIAR HORA)
            # CAMBIO CRÍTICO: Guardar a las 14:00+ en lugar de 15:00+ porque muchos días terminan antes
            if current_hour >= 14:  # 2:00 PM en adelante (CAMBIADO de 15 a 14)
                daily_key = f"{symbol}_{current_date}"
                
                if not hasattr(self, '_daily_closes_saved'):
                    self._daily_closes_saved = set()
                
                if daily_key not in self._daily_closes_saved:
                    self._daily_closes_saved.add(daily_key)
                    self.prev_closes[symbol] = bar.close
                    
                    self.logger.info(f"🔹 [PREV_CLOSE] {symbol} {current_date}: ${bar.close:.2f} SAVED (14:00+ rule)")
                else:
                    # Actualizar siempre el último close del día
                    self.prev_closes[symbol] = bar.close
                    self.logger.debug(f"[PREV_CLOSE] {symbol} {current_date}: ${bar.close:.2f} UPDATED")
            
            # PARTE 2: DETECTAR GAPS en horario temprano
            is_early_trading = (current_hour == 9 and current_minute >= 30) or (current_hour == 10 and current_minute <= 15)
            
            if is_early_trading:
                self.logger.debug(f"[GAP_DEBUG] {symbol}: Early trading time detected at {current_time}")
                
                if symbol in self.prev_closes:
                    prev_close = self.prev_closes[symbol]
                    self.logger.debug(f"[GAP_DEBUG] {symbol}: Found prev_close = ${prev_close:.2f}")
                    
                    # Verificar que no hayamos ya chequeado este día
                    gap_key = f"{symbol}_gap_{current_date}"
                    if not hasattr(self, '_daily_gaps_checked'):
                        self._daily_gaps_checked = set()
                    
                    if gap_key not in self._daily_gaps_checked:
                        self._daily_gaps_checked.add(gap_key)
                        
                        # CALCULAR GAP
                        if prev_close > 0:
                            gap_pct = (bar.open - prev_close) / prev_close * 100.0
                            threshold = self._parameters.get('gap_percent_threshold', 1.0)
                            
                            self.logger.info(f"🔍 [GAP CHECK] {symbol} {current_date}: "
                                        f"Open=${bar.open:.2f} vs PrevClose=${prev_close:.2f} "
                                        f"= {gap_pct:.2f}% (threshold: {threshold}%)")
                            
                            if abs(gap_pct) >= threshold:
                                direction = 'up' if gap_pct > 0 else 'down'
                                
                                self.logger.info(f"🔍 [GAP FOUND] {symbol}: {gap_pct:.1f}% {direction.upper()}")
                                
                                # SOLO GAPS UP para esta estrategia
                                if direction == 'up' and gap_pct >= threshold:  # Explicit UP and positive threshold
                                    self.scanner_gaps[symbol] = {
                                        'gap_percent': gap_pct,
                                        'direction': direction,
                                        'volume_ratio': 1.0,
                                        'price': bar.open,
                                        'timestamp': current_time,
                                        'scanner_score': abs(gap_pct),
                                        'confirmed': True,
                                        'confirmation_bars': 1,
                                        'prev_close': prev_close,
                                        'gap_date': str(current_date)
                                    }
                                    
                                    self.logger.info(f"🚀 [GAP DETECTED & STORED] {symbol}: {gap_pct:.1f}% UP "
                                                f"@ ${bar.open:.2f} vs ${prev_close:.2f} on {current_date}")
                                else:
                                    self.logger.info(f"[GAP IGNORED] {symbol}: {gap_pct:.1f}% {direction.upper()} "
                                                f"(strategy only trades UP gaps with +{threshold}% threshold)")
                            else:
                                self.logger.debug(f"[GAP TOO SMALL] {symbol}: {gap_pct:.2f}% < {threshold}%")
                        else:
                            self.logger.warning(f"[GAP ERROR] {symbol}: Invalid prev_close = {prev_close}")
                    else:
                        self.logger.debug(f"[GAP_DEBUG] {symbol}: Already checked gap for {current_date}")
                else:
                    self.logger.debug(f"[GAP_DEBUG] {symbol}: No prev_close available (keys: {list(self.prev_closes.keys())})")
            
            # PARTE 3: LIMPIAR GAPS EXPIRADOS
            if symbol in self.scanner_gaps:
                gap_age_minutes = (current_time - self.scanner_gaps[symbol]['timestamp']).total_seconds() / 60
                if gap_age_minutes > self._parameters.get('scanner_gap_timeout', 90):
                    self.logger.info(f"[GAP EXPIRED] {symbol}: {gap_age_minutes:.0f} min old, removing")
                    self.scanner_gaps.pop(symbol, None)
                    
        except Exception as e:
            self.logger.error(f"Auto gap detection error for {symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _is_valid_entry_time(self, timestamp) -> bool:
        """Verificar horario válido para entry"""
        try:
            hour_decimal = timestamp.hour + timestamp.minute / 60.0
            return (self._parameters['market_open_hour'] <= hour_decimal <= 
                   self._parameters['no_entry_after'])
        except:
            return False
    
    def _is_gap_expired(self, gap_data: Dict, current_timestamp) -> bool:
        """Verificar si gap ha expirado"""
        try:
            gap_time = gap_data['timestamp']
            time_diff = (current_timestamp - gap_time).total_seconds() / 60
            return time_diff > self._parameters['scanner_gap_timeout']
        except:
            return True
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Interface pública para calcular position size"""
        return self._calculate_position_size(signal.price)
    
    def debug_gap_detection(self, symbol: str) -> Dict:
        """Función mejorada para debuggear la detección de gaps"""
        bars = self.bars_history.get(symbol, [])
        
        debug_info = {
            "symbol": symbol,
            "total_bars": len(bars),
            "prev_closes_stored": symbol in self.prev_closes,
            "gaps_detected": symbol in self.scanner_gaps,
            "recent_gaps": [],
            "sample_bars": [],
            "gap_checks_done": getattr(self, '_daily_gaps_checked', set())
        }
        
        if symbol in self.prev_closes:
            debug_info["current_prev_close"] = self.prev_closes[symbol]
        
        if symbol in self.scanner_gaps:
            debug_info["current_gap"] = self.scanner_gaps[symbol]
        
        # Analizar barras por día para encontrar posibles gaps
        daily_bars = {}
        for bar in bars:
            date = bar.timestamp.date()
            if date not in daily_bars:
                daily_bars[date] = []
            daily_bars[date].append(bar)
        
        # Buscar gaps entre días
        sorted_dates = sorted(daily_bars.keys())
        for i in range(1, len(sorted_dates)):
            prev_date = sorted_dates[i-1]
            curr_date = sorted_dates[i]
            
            # Último close del día anterior
            prev_day_bars = daily_bars[prev_date]
            prev_close = prev_day_bars[-1].close if prev_day_bars else None
            
            # Primer open del día actual
            curr_day_bars = daily_bars[curr_date]
            curr_open = curr_day_bars[0].open if curr_day_bars else None
            
            if prev_close and curr_open and prev_close > 0:
                gap_pct = (curr_open - prev_close) / prev_close * 100.0
                threshold = self._parameters.get('gap_percent_threshold', 1.0)
                
                debug_info["recent_gaps"].append({
                    "prev_date": str(prev_date),
                    "curr_date": str(curr_date),
                    "prev_close": prev_close,
                    "curr_open": curr_open,
                    "gap_pct": gap_pct,
                    "meets_threshold": abs(gap_pct) >= threshold,
                    "direction": "up" if gap_pct > 0 else "down"
                })
        
        # Sample de las últimas 10 barras
        for bar in bars[-10:]:
            debug_info["sample_bars"].append({
                "timestamp": str(bar.timestamp),
                "date": str(bar.timestamp.date()),
                "hour": bar.timestamp.hour,
                "minute": bar.timestamp.minute,
                "open": bar.open,
                "close": bar.close,
                "volume": bar.volume
            })
        
        return debug_info
        
    def get_strategy_status(self) -> Dict:
        """Obtener estado actual de la estrategia"""
        return {
            'name': self.name,
            'active_positions': len(self.active_positions),
            'tracked_gaps': len(self.scanner_gaps),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_pnl': self.total_pnl,
            'positions': list(self.active_positions.keys()),
            'gaps': list(self.scanner_gaps.keys())
        }