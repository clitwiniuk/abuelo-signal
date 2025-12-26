"""
Base Worker Logic - Clase abstracta para workers lógicos
Proporciona funcionalidad común de ejecución y monitoreo
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

from core.trade_arbiter import TradingHorizon


class BarDataWrapper:
    """Wrapper to convert dict bars to object with attributes (for JSON-serialized bars)"""
    def __init__(self, bar_dict: Dict[str, Any]):
        self.timestamp = bar_dict.get('timestamp')
        self.open = bar_dict.get('open')
        self.high = bar_dict.get('high')
        self.low = bar_dict.get('low')
        self.close = bar_dict.get('close')
        self.volume = bar_dict.get('volume')


class BaseWorkerLogic(ABC):
    """
    Clase base para todos los workers lógicos.

    Responsabilidades:
    - Procesar oportunidades del scanner
    - Evaluar entrada con estrategia específica
    - Ejecutar trades usando ExecutionEngine compartido
    - Monitorear posiciones activas
    - Ejecutar salidas según estrategia

    Workers NO son procesos separados, son async tasks dentro de trader_main.py
    """

    def __init__(
        self,
        worker_name: str,
        execution_engine: Any,  # ExecutionEngine
        risk_manager: Any,  # RiskManager
        config: Any = None,  # UnifiedConfig (optional)
    ):
        """
        Inicializa worker lógico

        Args:
            worker_name: Identificador único del worker (ej: 'gap_go', 'daily_plays')
            execution_engine: ExecutionEngine compartido para ejecutar trades
            risk_manager: RiskManager compartido para validaciones
            config: UnifiedConfig object (optional, for accessing configuration)
        """
        self.worker_name = worker_name
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.config = config  # Store config for use in methods

        # Posiciones activas gestionadas por este worker
        # {symbol: {position, entry_time, opportunity_data}}
        self.active_positions: Dict[str, Dict[str, Any]] = {}

        # Failed entry tracking - max 2 attempts, then blacklist until restart
        # {symbol: {'attempts': int, 'reason': str}}
        self.failed_entries: Dict[str, Dict[str, Any]] = {}
        self.max_entry_attempts = 2  # Máximo 2 intentos, después bloqueado permanentemente

        # Replay/testing support - injected by replay engine
        self._replay_date = None  # datetime.date object for replay mode

        # Setup worker-specific logging
        from utils.log_config import setup_worker_logging
        self.logger = setup_worker_logging(worker_name, level="INFO")

        # ODS Classifier service (shared singleton)
        from core.service_locator import get_service_locator
        self.service_locator = get_service_locator()
        self.ods_classifier = self.service_locator.get_ods_classifier()

        # Trade Event Logger (for TP/SL optimization)
        from core.trade_event_logger import TradeEventLogger
        self.event_logger = TradeEventLogger()

        # Swing Transition Analyzer (for EOD overnight hold decisions)
        from core.swing_transition_analyzer import SwingTransitionAnalyzer
        self.swing_analyzer = SwingTransitionAnalyzer(config=config)

        # Swing transition tracking
        self._swing_transition_done_today = False  # Reset daily at market open
        self._swing_transition_enabled = getattr(config, 'swing_transition_enabled', True)

        # Estado
        self.is_running = False

        self.logger.info(f"🔧 Worker {worker_name} initialized with separate logging + ODS support + Event Logger + Swing Transition")

    def set_replay_date(self, date_str: str):
        """
        Set replay date for testing/replay purposes
        
        Args:
            date_str: Date string in format 'YYYY-MM-DD'
        """
        from datetime import datetime
        self._replay_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        self.logger.debug(f"🔄 Replay date set to: {self._replay_date}")

    async def _restore_active_positions(self):
        """
        Restaura posiciones activas del worker después de un reinicio

        Flujo:
        1. Consulta RiskManager (fuente única de verdad - sincronizado con broker)
        2. Consulta ExecutionEngine.worker_positions (posiciones de workers)
        3. Filtra por strategy == self.worker_name
        4. Restaura a self.active_positions para monitoreo
        """
        try:
            restored_count = 0

            # SOURCE 1: ExecutionEngine worker_positions (preferred - has strategy info)
            if hasattr(self.execution_engine, 'worker_positions'):
                for symbol, pos_data in self.execution_engine.worker_positions.items():
                    if pos_data.get('strategy') == self.worker_name:
                        restored_count += 1
                        self._restore_position(symbol, pos_data)

            # SOURCE 2: RiskManager broker_positions (fallback - if worker_positions empty)
            # Only restore if we didn't find any positions from ExecutionEngine
            if restored_count == 0 and hasattr(self.risk_manager, 'broker_positions'):
                for symbol, broker_pos in self.risk_manager.broker_positions.items():
                    # Match by checking if trade_id exists in our ExecutionEngine history
                    # This prevents stealing positions from other strategies
                    if await self._should_restore_from_broker(symbol, broker_pos):
                        restored_count += 1
                        self._restore_position_from_broker(symbol, broker_pos)

            if restored_count > 0:
                self.logger.info(
                    f"✅ Restored {restored_count} active position(s) for {self.worker_name}"
                )
            else:
                self.logger.debug(f"No active positions to restore for {self.worker_name}")

        except Exception as e:
            self.logger.error(f"❌ Error restoring positions: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _restore_position(self, symbol: str, position_data: Dict[str, Any]):
        """Restore position from ExecutionEngine worker_positions"""
        self.active_positions[symbol] = {
            'position': position_data,
            'entry_time': position_data.get('entry_time'),
            'entry_price': position_data.get('entry_price', 0),
            'quantity': position_data.get('quantity', 0),
            'opportunity_data': position_data.get('opportunity_data', {})
        }

        # CRITICAL FIX: Ensure SL/TP parameters exist
        # If restored from old DB schema, these might be missing. Inject defaults.
        opp_data = self.active_positions[symbol]['opportunity_data']
        if 'stop_loss_pct' not in opp_data:
            # Inject default safety parameters
            from strategies.workers.worker_stop_manager import WorkerStopManager
            defaults = WorkerStopManager.config.get(self.worker_name, WorkerStopManager.config['default'])
            
            opp_data['stop_loss_pct'] = defaults.get('stop_loss_pct', 0.05)
            opp_data['take_profit_pct'] = defaults.get('take_profit_pct', 0.20)
            opp_data['trailing_activation_pct'] = defaults.get('trailing_activation_pct', 0.10)
            opp_data['trailing_distance_pct'] = defaults.get('trailing_distance_pct', 0.05)
            
            self.logger.warning(f"⚠️ {symbol}: Injected default SL/TP parameters for restored position (missing in DB)")

        # Register with stop manager
        if position_data.get('entry_time'):
            self.stop_manager.register_position(symbol, position_data['entry_time'])

        self.logger.info(
            f"🔄 Restored: {symbol} @ ${position_data.get('entry_price', 0):.2f} "
            f"x {position_data.get('quantity', 0)} shares"
        )

    def _restore_position_from_broker(self, symbol: str, broker_position: Any):
        """Restore position from RiskManager broker_positions (fallback)"""
        # Extract data from broker position object
        entry_price = getattr(broker_position, 'avgCost', 0) or getattr(broker_position, 'entry_price', 0)
        quantity = getattr(broker_position, 'position', 0) or getattr(broker_position, 'quantity', 0)

        from datetime import datetime

        self.active_positions[symbol] = {
            'position': {
                'symbol': symbol,
                'entry_price': entry_price,
                'quantity': quantity,
                'strategy': self.worker_name
            },
            'entry_time': datetime.now(),  # Approximation - real entry time unknown
            'entry_price': entry_price,
            'quantity': quantity,
            'opportunity_data': {}
        }

        # Register with stop manager
        self.stop_manager.register_position(symbol, datetime.now())

        self.logger.warning(
            f"⚠️ Restored from broker (approximate entry time): {symbol} @ "
            f"${entry_price:.2f} x {quantity} shares"
        )

    async def _should_restore_from_broker(self, symbol: str, broker_position: Any) -> bool:
        """
        Determina si una posición del broker debería ser restaurada por este worker

        Previene robar posiciones de otros workers/strategies
        Solo restaura si no hay información de strategy disponible
        """
        # For now, we don't restore from broker positions unless explicitly needed
        # This prevents conflicts between workers claiming the same position
        return False

    async def run(self):
        """
        Loop principal del worker - monitoreo continuo de posiciones
        Este método corre como async task en background
        """
        self.is_running = True
        self.logger.info(f"🚀 Worker {self.worker_name} starting monitoring loop")

        # CRITICAL: Restore active positions from ExecutionEngine after restart
        await self._restore_active_positions()

        try:
            while self.is_running:
                try:
                    await self._monitor_positions()
                except Exception as e:
                    self.logger.error(f"❌ Error in monitoring loop: {e}")

                # Ejecutar tarea periódica (hook para subclases)
                try:
                    await self._periodic_task()
                except Exception as e:
                    self.logger.error(f"❌ Error in periodic task for {self.worker_name}: {e}")

                # Check cada segundo
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info(f"🛑 Worker {self.worker_name} cancelled")
            raise
        except Exception as e:
            self.logger.error(f"❌ Worker {self.worker_name} crashed: {e}")
        finally:
            self.is_running = False

    async def _periodic_task(self):
        """
        Hook para tareas periódicas en las subclases (ej. Surveillance Mode)
        Por defecto no hace nada.
        """
        pass

    async def _analyze_smallcap_fundamentals(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza fundamentales críticos para Small Caps:
        1. Float Rotation: Volumen / Float (Combustible)
        2. PMH (Pre-Market High): Nivel clave de breakout
        3. Halt Awareness: Proximidad a bandas LULD
        
        Args:
            opportunity: Datos de la oportunidad
            
        Returns:
            Dict con métricas mejoradas
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        current_price = opportunity.get('current_price', 0)
        volume = opportunity.get('current_volume', opportunity.get('volume', 0))
        
        result = {
            'float_shares': 0,
            'rotation_factor': 0.0,
            'is_high_rotation': False,
            'pmh': 0.0,
            'dist_to_pmh': 999.0,
            'luld_high': 0.0,
            'dist_to_halt': 999.0,
            'is_halt_risk': False
        }
        
        try:
            # 1. FLOAT & ROTATION
            # Try to get float from opportunity or fetch it
            float_shares = opportunity.get('float_shares', 0)
            if not float_shares:
                # Try to fetch from Finviz (better than IBKR for fundamentals)
                try:
                    from finvizfinance.quote import finvizfinance
                    stock = finvizfinance(symbol)
                    fundamentals = stock.ticker_fundament()
                    if fundamentals:
                        # Get float shares from Finviz ('Shs Float' field)
                        shs_float_str = fundamentals.get('Shs Float', '0')
                        # Parse format like "12.34M" or "1.5B"
                        if shs_float_str and shs_float_str != '-':
                            shs_float_str = shs_float_str.replace(',', '').strip()
                            if shs_float_str.endswith('B'):
                                float_shares = int(float(shs_float_str[:-1]) * 1_000_000_000)
                            elif shs_float_str.endswith('M'):
                                float_shares = int(float(shs_float_str[:-1]) * 1_000_000)
                            elif shs_float_str.endswith('K'):
                                float_shares = int(float(shs_float_str[:-1]) * 1_000)
                            else:
                                float_shares = int(float(shs_float_str))
                            # Cache back to opportunity
                            opportunity['float_shares'] = float_shares
                            self.logger.debug(f"📊 {symbol}: Float from Finviz: {float_shares:,} shares")
                except Exception as e:
                    # Silently fail - float is optional
                    self.logger.debug(f"Could not fetch float from Finviz for {symbol}: {e}")
            
            result['float_shares'] = float_shares
            
            if float_shares > 0 and volume > 0:
                rotation = volume / float_shares
                result['rotation_factor'] = rotation
                # >1.0x rotation is explosive
                if rotation > 1.0:
                    result['is_high_rotation'] = True
                    self.logger.info(f"🌪️ {symbol}: HIGH ROTATION DETECTED ({rotation:.2f}x float)")

            # 2. PRE-MARKET HIGH (PMH)
            # We assume bars[0] starts at 9:30 if RTH=True. 
            # If we requested daily bars/premarket implicitly, we might check high of day so far vs open.
            # Best proxy without explicit PM data: Day High if we are near open and price < DayHigh
            day_high = opportunity.get('high', current_price)
            # Logic: If current price is clearly below Day High and it's early, Day High might be PMH
            # TODO: Improve with explicit Pre-Market request in future
            result['pmh'] = day_high
            if current_price > 0:
                 result['dist_to_pmh'] = ((day_high - current_price) / current_price) * 100

            # 3. LULD HALT BANDS (Volatility Halt Protection)
            # Rule: Price > $3.00 -> 10% bands (20% first 15m). Price < $3.00 -> 20% bands (40% first 15m)
            # Reference price is usually avg of last 5 min.
            
            bars = self.get_bars_from_opportunity(opportunity)
            if bars and len(bars) >= 5:
                # Calculate reference price (simple 5-min avg)
                last_5_bars = bars[-5:]
                ref_price = sum(b.close for b in last_5_bars) / len(last_5_bars)
                
                now = datetime.now().time()
                is_market_open_15m = now < datetime.strptime("09:45", "%H:%M").time()
                
                # Determine Tier band percentage
                if ref_price > 3.0:
                    band_pct = 0.20 if is_market_open_15m else 0.10
                else:
                     band_pct = 0.40 if is_market_open_15m else 0.20
                
                luld_high = ref_price * (1 + band_pct)
                dist_to_halt = ((luld_high - current_price) / current_price) * 100
                
                result['luld_high'] = luld_high
                result['dist_to_halt'] = dist_to_halt
                
                # If we are within 2% of halt band, FLAG IT
                if 0 < dist_to_halt < 2.5:
                    result['is_halt_risk'] = True
                    self.logger.warning(f"🛑 {symbol}: HALT RISK! Dist to LULD: {dist_to_halt:.1f}% (Ref: {ref_price:.2f})")
            
        except Exception as e:
            self.logger.error(f"Error in smallcap fundamentals analysis: {e}")
            
        return result

    async def process_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """
        Procesa una oportunidad del scanner y decide si ejecutar entrada

        Flujo:
        1. Verifica si ya tenemos posición en el símbolo
        2. Valida con risk manager
        3. Evalúa entrada con estrategia específica (should_enter)
        4. Si cumple criterios, ejecuta entrada

        Args:
            opportunity: Dict con datos de la oportunidad del scanner

        Returns:
            True si se ejecutó entrada, False si no
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # Log que estamos procesando (INFO level para visibilidad)
            self.logger.info(
                f"🔍 {symbol}: Evaluating opportunity - "
                f"gap={abs(opportunity.get('gap_percentage', 0)):.1f}%, "
                f"vol={opportunity.get('volume_ratio', 0):.1f}x, "
                f"catalyst={opportunity.get('catalyst_type', 'NONE')}, "
                f"Q={opportunity.get('quality_score', 0):.1f}"
            )

            # Check 1: ¿Ya tenemos posición?
            if symbol in self.active_positions:
                self.logger.debug(f"⏭️ {symbol}: Already in position, skipping")
                return False

            # Check 2: ¿Entrada falló previamente? (Max 2 attempts)
            if symbol in self.failed_entries:
                failure_data = self.failed_entries[symbol]
                attempts = failure_data['attempts']

                if attempts >= self.max_entry_attempts:
                    # Ya intentó 2 veces, bloqueado permanentemente
                    self.logger.debug(
                        f"🚫 {symbol}: Blacklisted after {attempts} failed attempts "
                        f"(blocked until restart)"
                    )
                    return False
                else:
                    # Primer intento falló, permitir segundo intento
                    self.logger.info(
                        f"♻️ {symbol}: Allowing retry (attempt #{attempts + 1}/{self.max_entry_attempts})"
                    )

            # Check 3: Risk manager permite?
            if not await self._check_risk_approval(symbol):
                self.logger.debug(f"🚫 {symbol}: Risk manager denied")
                return False

            # Check 4: Estrategia específica aprueba entrada?
            entry_approved = await self.should_enter(opportunity)

            if entry_approved:
                self.logger.info(f"✅ {symbol}: Entry criteria met for {self.worker_name}")

                # Calculate pattern completion for entry priority (if multiple workers compete)
                result = await self.calculate_pattern_completion(opportunity)

                # Handle both return types: float or Tuple[float, float]
                if isinstance(result, tuple):
                    pattern_completion, support_level = result
                    opportunity['support_level'] = support_level
                else:
                    pattern_completion = result

                opportunity['pattern_completion'] = pattern_completion

                self.logger.debug(
                    f"📊 {symbol}: Pattern completion = {pattern_completion:.1f}% for {self.worker_name}"
                )

                # Log signal event (ENTRY)
                try:
                    self.event_logger.log_signal_event(
                        worker_name=self.worker_name,
                        symbol=symbol,
                        entry_price=opportunity.get('current_price', 0.0),
                        opportunity=opportunity,
                        entered=True,
                        rejection_reason=None,
                        trade_id=None  # Will be filled after execution
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to log entry signal: {e}")

                return await self._execute_entry(opportunity)
            else:
                self.logger.info(f"⚪ {symbol}: Entry criteria not met (rejected by strategy)")

                # Log signal event (REJECTION)
                try:
                    self.event_logger.log_signal_event(
                        worker_name=self.worker_name,
                        symbol=symbol,
                        entry_price=opportunity.get('current_price', 0.0),
                        opportunity=opportunity,
                        entered=False,
                        rejection_reason="Strategy entry criteria not met",
                        trade_id=None
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to log rejection signal: {e}")

                return False

        except Exception as e:
            self.logger.error(f"❌ Error processing opportunity {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula el porcentaje de completitud del patrón (0-100%)

        EARLY ENTRY STRATEGY:
        - Objetivo: Detectar patrones al 80% de completitud
        - Entrar ANTES de que el patrón complete al 100%
        - Evitar llegar tarde al movimiento

        Implementación por defecto retorna 0% (sin patrón detectado)
        Cada worker debe sobrescribir este método con su lógica específica

        Ejemplos:
        - Gap-Go: 80% = consolidación debajo PMH + volumen building
        - Bull Flag: 80% = flag formado + volumen declinando (antes de breakout)
        - MACDV: 80% = divergencia formándose (antes de cruce)
        - Daily Plays: 80% = catalyst + contexto diario alineado

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            Porcentaje de completitud (0.0-100.0)
            - 0-79%: Patrón no completo suficiente
            - 80-99%: Patrón en etapa de early entry (ÓPTIMO)
            - 100%: Patrón completo (tarde, ya movió)
        """
        return 0.0  # Default: no pattern detected

    def _calculate_atr_from_bars(self, bars: list, period: int = 14) -> float:
        """
        Calculate ATR (Average True Range) from bars

        Args:
            bars: List of OHLC bars
            period: ATR period (default 14)

        Returns:
            ATR value (absolute price)
        """
        try:
            if len(bars) < period + 1:
                return 0.0

            true_ranges = []
            for i in range(len(bars) - period, len(bars)):
                high = bars[i].high
                low = bars[i].low
                prev_close = bars[i-1].close if i > 0 else bars[i].close

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            atr = sum(true_ranges) / len(true_ranges)
            return atr

        except Exception as e:
            self.logger.debug(f"Error calculating ATR: {e}")
            return 0.0

    def _find_smart_resistance(
        self,
        bars: List[Any],
        current_price: float,
        lookback_days: int = 90
    ) -> Dict[str, Any]:
        """
        Detecta niveles de resistencia 'inteligentes' usando Price Clustering.
        
        Mejoras vs Máximo Simple:
        1. Clustering: Agrupa precios donde hubo rechazo (pivots).
        2. Polarity Flip: Detecta antiguos soportes que ahora son resistencia.
        3. Proximidad: Encuentra la resistencia INMEDIATA, no solo la más alta.
        
        Args:
            bars: Lista de barras diarias (se asume timeframe diario o 4h)
            current_price: Precio actual
            lookback_days: Días hacia atrás para analizar (default 90)
            
        Returns:
            Dict con info de resistencia:
            {
                'level': float (precio resistencia),
                'distance_pct': float (distancia en %),
                'type': str ('HIGH', 'PIVOT', 'SUPPORT_FLIP'),
                'strength': int (número de toques)
            }
        """
        try:
            if not bars or len(bars) < 10:
                return {'level': None, 'distance_pct': 999.0, 'type': 'NONE', 'strength': 0}
                
            # 1. Identificar Pivots (Highs y Lows locales)
            pivots = []
            
            # Usar ventana deslizante de 5 días para encontrar pivots reales
            # Pivot High: High[i] > High[i-1] y High[i] > High[i+1]
            # Pivot Low: Low[i] < Low[i-1] y Low[i] < Low[i+1]
            
            recent_bars = bars[-lookback_days:] if len(bars) > lookback_days else bars
            
            for i in range(2, len(recent_bars) - 2):
                prev_bar = recent_bars[i-1]
                curr_bar = recent_bars[i]
                next_bar = recent_bars[i+1]
                
                # Check Pivot High
                if curr_bar.high > prev_bar.high and curr_bar.high > next_bar.high:
                    pivots.append({'price': curr_bar.high, 'type': 'RESISTANCE'})
                    
                # Check Pivot Low (Support) - Important for Support Flip detection
                if curr_bar.low < prev_bar.low and curr_bar.low < next_bar.low:
                    pivots.append({'price': curr_bar.low, 'type': 'SUPPORT'})
            
            # Si no hay pivots, usar el máximo absoluto
            if not pivots:
                max_h = max(b.high for b in recent_bars)
                dist = ((max_h - current_price) / current_price) * 100
                return {'level': max_h, 'distance_pct': dist, 'type': 'MAX_HIGH', 'strength': 1}
                
            # 2. Clustering: Agrupar pivots cercanos (dentro del 1.5%)
            clusters = []
            sorted_pivots = sorted(pivots, key=lambda x: x['price'])
            
            current_cluster = [sorted_pivots[0]]
            
            for i in range(1, len(sorted_pivots)):
                pivot = sorted_pivots[i]
                avg_cluster_price = sum(p['price'] for p in current_cluster) / len(current_cluster)
                
                # Si está dentro del 1.5% del promedio del cluster, añadirlo
                if abs(pivot['price'] - avg_cluster_price) / avg_cluster_price < 0.015:
                    current_cluster.append(pivot)
                else:
                    # Cerrar cluster anterior y empezar uno nuevo
                    clusters.append(current_cluster)
                    current_cluster = [pivot]
            
            clusters.append(current_cluster) # Añadir último
            
            # 3. Analizar Clusters Overhead (por encima del precio actual)
            # Solo nos importan resistencias (precio > current_price)
            overhead_clusters = []
            
            for cluster in clusters:
                avg_price = sum(p['price'] for p in cluster) / len(cluster)
                
                # Si está por debajo o muy cerca (< 0.2%), es soporte o ruido
                if avg_price <= current_price * 1.002:
                    continue
                    
                touch_count = len(cluster)
                # Clasificar tipo: Si contiene soportes previos, es FLIP
                has_support = any(p['type'] == 'SUPPORT' for p in cluster)
                r_type = 'SUPPORT_FLIP' if has_support else 'PIVOT_RESISTANCE'
                
                overhead_clusters.append({
                    'level': avg_price,
                    'distance_pct': ((avg_price - current_price) / current_price) * 100,
                    'type': r_type,
                    'strength': touch_count
                })
                
            # 4. Seleccionar la resistencia más relevante
            # Buscamos la más cercana, pero ignoramos las muy débiles (1 toque) si hay una fuerte cerca
            if not overhead_clusters:
                # BLUE SKY: No historical overhead resistance found
                return {'level': None, 'distance_pct': 999.0, 'type': 'BLUE_SKY', 'strength': 0}
            
            # Ordenar por distancia
            overhead_clusters.sort(key=lambda x: x['distance_pct'])
            
            nearest = overhead_clusters[0]
            
            self.logger.debug(f"🧱 Smart Resistance for Price ${current_price:.2f}: Found {nearest['type']} at ${nearest['level']:.2f} (+{nearest['distance_pct']:.1f}%) with {nearest['strength']} touches")
            
            return nearest
            
        except Exception as e:
            self.logger.error(f"Error finding smart resistance: {e}")
            return {'level': None, 'distance_pct': 999.0, 'type': 'ERROR', 'strength': 0}
    async def _analyze_daily_potential_for_signal(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze daily timeframe potential for signal

        This method is called EARLY in evaluation (before VWAP filter) to determine
        if the ticker has multi-day potential (SWING) or just intraday (SCALP/INTRADAY)

        Args:
            opportunity: Signal data including symbol, price, bars

        Returns:
            Daily potential dict with can_swing, can_swing_short, resistance, support, etc.
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        daily_potential = {
            'can_swing': False,
            'can_swing_short': True,
            'reasons': ['Daily bars not available'],
            'rsi_daily': 50,
            'distance_to_resistance': 100,
            'distance_to_support': 100
        }

        try:
            # Fetch daily bars if not already present
            if 'bars_daily' not in opportunity or not opportunity['bars_daily']:
                self.logger.debug(f"📈 {symbol}: Fetching daily bars for horizon analysis")
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars_daily = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='12 M',  # 12 months (1 year) for 52-week high/low analysis
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True
                )
                opportunity['bars_daily'] = bars_daily if bars_daily else []
            else:
                bars_daily = opportunity['bars_daily']

            # Analyze daily potential using Context Engine
            if bars_daily and len(bars_daily) >= 30:
                from core.context_engine import get_context_engine
                context_engine = get_context_engine()

                daily_potential = context_engine.analyze_daily_potential({
                    'symbol': symbol,
                    'bars_daily': bars_daily,
                    'current_price': opportunity.get('current_price', 0)
                })

                # --- GLOBAL SMART RESISTANCE INTEGRATION ---
                # Calculate Smart Resistance using BaseWorkerLogic's shared method
                # This makes it available to ALL workers (Parabolic, VCP, Daily Plays)
                smart_resistance = self._find_smart_resistance(
                    bars=bars_daily,
                    current_price=opportunity.get('current_price', 0)
                )
                
                # Injection: Add to daily_potential so workers can access it directly
                daily_potential['smart_resistance'] = smart_resistance
                
                # Update legacy fields for backward compatibility, but using SMART values
                if smart_resistance['level']:
                    daily_potential['distance_to_resistance'] = smart_resistance['distance_pct']
                    daily_potential['resistance_level'] = smart_resistance['level']
                    daily_potential['resistance_type'] = smart_resistance['type']

                # Log daily context (handle None resistance)
                resistance_str = (
                    f"'{smart_resistance['type']}' @ ${smart_resistance['level']:.2f} (+{smart_resistance['distance_pct']:.1f}%)"
                    if smart_resistance['level'] is not None
                    else f"'{smart_resistance['type']}' (no overhead resistance)"
                )
                self.logger.info(
                    f"📊 {symbol}: Daily context - "
                    f"RSI={daily_potential['rsi_daily']:.1f}, "
                    f"Resistance={resistance_str}"
                )
            else:
                self.logger.warning(
                    f"⚠️ {symbol}: Insufficient daily bars ({len(bars_daily) if bars_daily else 0}) for daily analysis"
                )

        except Exception as e:
            self.logger.warning(f"⚠️ {symbol}: Could not analyze daily potential: {e}")
            # Continue with conservative defaults (no swing)

        # Store in opportunity for later use in _execute_entry()
        opportunity['daily_potential'] = daily_potential

        return daily_potential

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina el horizonte temporal de trading para esta señal específica

        SIGNAL-SPECIFIC HORIZON:
        El horizonte NO es fijo por worker, sino que depende de la señal.
        Factores: confidence, context, risk_reward, volume, market conditions

        Workers pueden sobrescribir este método con lógica específica.

        Args:
            signal_data: Dict con información de la señal:
                - confidence: float (0-100)
                - context: MarketContext
                - risk_reward: float
                - volume_zscore: float
                - current_price: float
                - entry_price: float
                - stop_loss: float
                - take_profit: float

        Returns:
            Tuple[TradingHorizon, expected_hold_hours]

        Examples:
            - High confidence (>75%) + strong context -> SWING (48h)
            - Medium confidence (60-75%) + ok context -> SWING_SHORT (24h)
            - Lower confidence (45-60%) + volatile -> INTRADAY (6h)
            - Weak signal (<45%) or range-bound -> SCALP (0.5h) or reject
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)

        # Default implementation - workers should override with specific logic

        # High quality signal -> SWING
        if confidence > 75 and risk_reward > 2.5 and volume_zscore > 2.0:
            return TradingHorizon.SWING, 48.0

        # Good signal -> SWING_SHORT
        elif confidence > 60 and risk_reward > 2.0:
            return TradingHorizon.SWING_SHORT, 24.0

        # Decent signal -> INTRADAY
        elif confidence > 50 and risk_reward > 1.5:
            return TradingHorizon.INTRADAY, 6.0

        # Weak signal -> SCALP (or reject)
        else:
            return TradingHorizon.SCALP, 0.5

    async def get_ods_for_symbol(
        self,
        symbol: str,
        bars: List[Any],
        premarket_data: Optional[Dict] = None
    ):
        """
        Obtener ODS classification para el símbolo

        Workers pueden usar esto para filtrar entradas basadas en tipo de día.

        Args:
            symbol: Símbolo a clasificar
            bars: Bars históricos
            premarket_data: Datos de premarket (opcional)

        Returns:
            ODSData con clasificación del día

        Example:
            ods = await self.get_ods_for_symbol(symbol, bars)
            if ods.day_type == ODSDayType.FAILED_DRIVE:
                return False  # Skip trade
        """
        try:
            return await self.ods_classifier.classify_symbol_ods(
                symbol=symbol,
                bars=bars,
                premarket_data=premarket_data
            )
        except Exception as e:
            self.logger.warning(f"⚠️ {symbol}: ODS classification failed: {e}")
            # Return PENDING if classification fails (non-blocking)
            from core.ods_classifier import ODSData, ODSDayType
            return ODSData(day_type=ODSDayType.PENDING)

    async def get_intraday_structure_for_symbol(
        self,
        symbol: str,
        bars: List[Any],
        current_time: Optional[Any] = None
    ):
        """
        Obtener clasificación completa de estructura intraday (6 patrones)

        Workers pueden usar esto para filtrar/boost entradas según contexto temporal.

        Args:
            symbol: Símbolo a clasificar
            bars: Bars históricos 1-min desde 9:30 AM
            current_time: Tiempo actual (opcional, default: now)

        Returns:
            IntradayStructureData con clasificación de 6 patrones temporales:
            - ODS (0-12 min): Opening Drive
            - Continuation (12-30 min): Pullbacks, VWAP rotation
            - Liquidity Sweep (30-120 min): Stop hunting
            - Midday Balance (120-210 min): Consolidación/breakout
            - Trap Reversals (210-330 min): Stop runs
            - Final Drive (330-390 min): Closing bias

        Example:
            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Filter based on current phase
            if structure.current_phase == IntradayPhase.MIDDAY:
                if structure.midday_structure == "BALANCE":
                    return False  # Skip chop zone

                if structure.midday_structure == "IMBALANCE_BULLISH":
                    confidence *= 1.3  # Boost entry

            # Filter liquidity sweeps
            if structure.liquidity_sweep_detected:
                if structure.sweep_direction == "BULLISH_RECLAIM":
                    # High probability setup
                    pass
        """
        try:
            # Get intraday structure classifier from ServiceLocator
            intraday_classifier = self.service_locator.get_intraday_structure_classifier()

            return await intraday_classifier.classify_symbol(
                symbol=symbol,
                bars=bars,
                current_time=current_time
            )
        except Exception as e:
            self.logger.warning(f"⚠️ {symbol}: Intraday structure classification failed: {e}")
            # Return empty structure if classification fails (non-blocking)
            from core.intraday_structure_classifier import IntradayStructureData, IntradayPhase
            return IntradayStructureData(
                symbol=symbol,
                current_phase=IntradayPhase.OPENING_DRIVE
            )

    def calculate_adaptive_risk(
        self,
        opportunity: Dict[str, Any],
        ods_data: Optional[Any] = None,
        intraday_structure: Optional[Any] = None,
        structural_exits: Optional[Dict] = None
    ) -> float:
        """
        Calcula el tamaño de riesgo adaptativo basado en:
        - Calidad del setup (quality_score)
        - Alineación de patrones estructurales
        - Volatilidad del símbolo
        - Expected Value (EV) del trade
        - Risk:Reward ratio

        Args:
            opportunity: Diccionario con datos de la oportunidad
            ods_data: Clasificación ODS (opcional)
            intraday_structure: Clasificación de estructura intraday (opcional)
            structural_exits: Datos del Structural Exit Calculator (opcional)

        Returns:
            float: Riesgo ajustado (config min_risk - max_risk, default 0.8% - 2.0%)
        """
        try:
            # Load config from ServiceLocator
            config = self.service_locator.get_config()

            # Check if adaptive risk sizing is enabled
            if not getattr(config, 'enable_adaptive_risk_sizing', True):
                base_risk = getattr(config, 'base_risk_percent', 1.2) / 100.0
                return base_risk

            # Get configuration parameters
            base_risk = getattr(config, 'base_risk_percent', 1.2) / 100.0  # Convert % to decimal
            min_risk = getattr(config, 'min_risk_percent', 0.8) / 100.0
            max_risk = getattr(config, 'max_risk_percent', 2.0) / 100.0
            quality_threshold = getattr(config, 'quality_boost_threshold', 80)
            quality_boost = getattr(config, 'quality_boost_amount', 0.3) / 100.0
            pattern_threshold = getattr(config, 'pattern_alignment_threshold', 2)
            pattern_boost = getattr(config, 'pattern_alignment_boost', 0.2) / 100.0
            volatility_threshold = getattr(config, 'high_volatility_threshold', 8.0)
            volatility_reduction = getattr(config, 'high_volatility_reduction', 0.2) / 100.0

            risk = base_risk

            # 1. QUALITY BOOST
            quality_score = opportunity.get('quality_score', 0)
            if quality_score > quality_threshold:
                risk += quality_boost
                self.logger.debug(
                    f"📊 Quality boost: {quality_score}/100 -> +{quality_boost*100:.1f}% risk"
                )

            # 2. PATTERN ALIGNMENT BOOST
            patterns_aligned = 0

            # Check ODS alignment
            if ods_data and hasattr(ods_data, 'classification'):
                if ods_data.classification in ['STRONG_BULLISH', 'MODERATE_BULLISH']:
                    patterns_aligned += 1

            # Check Intraday Structure alignment
            if intraday_structure:
                # Check continuation pattern
                if hasattr(intraday_structure, 'continuation_type'):
                    if intraday_structure.continuation_type in ['PULLBACK_TO_VWAP', 'HIGHER_LOW']:
                        patterns_aligned += 1

                # Check liquidity sweep
                if hasattr(intraday_structure, 'liquidity_sweep_type'):
                    if intraday_structure.liquidity_sweep_type == 'BULLISH_RECLAIM':
                        patterns_aligned += 1

                # Check midday imbalance
                if hasattr(intraday_structure, 'midday_structure_type'):
                    if intraday_structure.midday_structure_type == 'IMBALANCE_BULLISH':
                        patterns_aligned += 1

            if patterns_aligned >= pattern_threshold:
                risk += pattern_boost
                self.logger.debug(
                    f"🎯 Pattern alignment: {patterns_aligned} patterns -> +{pattern_boost*100:.1f}% risk"
                )

            # 3. VOLATILITY ADJUSTMENT
            atr_pct = opportunity.get('atr_percent', 0)
            if atr_pct > volatility_threshold:
                risk -= volatility_reduction
                self.logger.debug(
                    f"⚠️ High volatility: ATR {atr_pct:.1f}% -> -{volatility_reduction*100:.1f}% risk"
                )

            # 4. EXPECTED VALUE BOOST (from Structural Exit Calculator)
            if structural_exits and 'expected_value_pct' in structural_exits:
                ev_pct = structural_exits['expected_value_pct']

                # Get EV boost thresholds from config
                ev_exceptional_threshold = getattr(config, 'ev_boost_threshold_exceptional', 5.0)
                ev_exceptional_boost = getattr(config, 'ev_boost_amount_exceptional', 0.5) / 100.0
                ev_high_threshold = getattr(config, 'ev_boost_threshold_high', 3.0)
                ev_high_boost = getattr(config, 'ev_boost_amount_high', 0.3) / 100.0
                ev_good_threshold = getattr(config, 'ev_boost_threshold_good', 2.0)
                ev_good_boost = getattr(config, 'ev_boost_amount_good', 0.2) / 100.0

                if ev_pct > ev_exceptional_threshold:
                    risk += ev_exceptional_boost
                    self.logger.debug(
                        f"💎 Exceptional EV ({ev_pct:.1f}%) -> +{ev_exceptional_boost*100:.1f}% risk"
                    )
                elif ev_pct >= ev_high_threshold:
                    risk += ev_high_boost
                    self.logger.debug(
                        f"💰 High EV ({ev_pct:.1f}%) -> +{ev_high_boost*100:.1f}% risk"
                    )
                elif ev_pct >= ev_good_threshold:
                    risk += ev_good_boost
                    self.logger.debug(
                        f"✅ Good EV ({ev_pct:.1f}%) -> +{ev_good_boost*100:.1f}% risk"
                    )

            # 5. RISK:REWARD BOOST (from Structural Exit Calculator)
            if structural_exits and 'risk_reward' in structural_exits:
                rr = structural_exits['risk_reward']

                # Get R:R boost thresholds from config
                rr_exceptional_threshold = getattr(config, 'rr_boost_threshold_exceptional', 5.0)
                rr_exceptional_boost = getattr(config, 'rr_boost_amount_exceptional', 0.2) / 100.0
                rr_good_threshold = getattr(config, 'rr_boost_threshold_good', 3.5)
                rr_good_boost = getattr(config, 'rr_boost_amount_good', 0.1) / 100.0

                if rr >= rr_exceptional_threshold:
                    risk += rr_exceptional_boost
                    self.logger.debug(
                        f"🚀 Exceptional R:R ({rr:.1f}:1) -> +{rr_exceptional_boost*100:.1f}% risk"
                    )
                elif rr >= rr_good_threshold:
                    risk += rr_good_boost
                    self.logger.debug(
                        f"📈 Good R:R ({rr:.1f}:1) -> +{rr_good_boost*100:.1f}% risk"
                    )

            # 6. CAP LIMITS
            risk = max(min_risk, min(max_risk, risk))

            risk_pct = risk * 100

            # Build log message with all factors
            log_parts = [f"quality={quality_score}", f"patterns={patterns_aligned}"]
            if atr_pct > 0:
                log_parts.append(f"atr={atr_pct:.1f}%")
            if structural_exits:
                if 'expected_value_pct' in structural_exits:
                    log_parts.append(f"ev={structural_exits['expected_value_pct']:.1f}%")
                if 'risk_reward' in structural_exits:
                    log_parts.append(f"rr={structural_exits['risk_reward']:.1f}")

            self.logger.info(
                f"💰 Adaptive Risk: {risk_pct:.2f}% ({', '.join(log_parts)})"
            )

            return risk

        except Exception as e:
            # Fallback to base risk on error
            base_risk = 0.012
            self.logger.warning(
                f"⚠️ Adaptive risk calculation failed: {e}, using default base risk {base_risk*100:.1f}%"
            )
            return base_risk

    def classify_trade_tier(
        self,
        ev_pct: float,
        risk_pct: float,
        quality_score: float,
        rr: float
    ) -> str:
        """
        Clasifica el trade en Tiers A/B/C/D para análisis y visibilidad

        TIER A: Trades excepcionales (1-2/mes)
            - EV >= 6.0%
            - Risk >= 3.5%
            - Quality >= 85
            - R:R >= 4.0

        TIER B: Trades de alta calidad (1-2/semana)
            - EV >= 4.0%
            - Risk >= 2.5%
            - Quality >= 75
            - R:R >= 3.0

        TIER C: Trades buenos (3-5/semana)
            - EV >= 2.5%
            - Risk >= 1.5%
            - Quality >= 60
            - R:R >= 2.0

        TIER D: Trades marginales (diario)
            - EV >= 2.0% (minimum for entry)
            - Resto

        Args:
            ev_pct: Expected Value percentage
            risk_pct: Adaptive risk percentage (decimal, e.g., 0.035 = 3.5%)
            quality_score: Quality score (0-100)
            rr: Risk:Reward ratio

        Returns:
            str: 'A', 'B', 'C', or 'D'
        """
        # Convert risk to percentage for comparison
        risk_pct_value = risk_pct * 100

        # TIER A: Exceptional (4x base position sizing)
        if (ev_pct >= 6.0 and
            risk_pct_value >= 3.5 and
            quality_score >= 85 and
            rr >= 4.0):
            return 'A'

        # TIER B: High Quality (2.5x base position sizing)
        elif (ev_pct >= 4.0 and
              risk_pct_value >= 2.5 and
              quality_score >= 75 and
              rr >= 3.0):
            return 'B'

        # TIER C: Good (1.5x base position sizing)
        elif (ev_pct >= 2.5 and
              risk_pct_value >= 1.5 and
              quality_score >= 60 and
              rr >= 2.0):
            return 'C'

        # TIER D: Marginal (0.5-1x base position sizing)
        else:
            return 'D'

    def is_within_entry_hours(self, symbol: str = "", timestamp: Optional[datetime] = None) -> Tuple[bool, float]:
        """
        Centralized hour validation - ALL workers must use this method

        Checks if current time is within allowed entry window defined in config.ini:
        - Global defaults: market_open_time (09:30), no_entry_after (15:45 ET)
        - Strategy-specific overrides: strategy_start_time, strategy_end_time (optional)

        Strategy-specific example (config.ini):
        [GENERIC_01_STRATEGY]
        strategy_start_time = 09:30
        strategy_end_time = 11:30  # Only first 2 hours

        Args:
            symbol: Symbol being evaluated (for logging)
            timestamp: Optional timestamp to check (for backtesting/replay). 
                       If None, uses datetime.now()

        Returns:
            Tuple[bool, float]: (is_valid, current_hour_decimal)
                - is_valid: True if within entry hours, False otherwise
                - current_hour_decimal: Current hour in decimal format (e.g., 15.75 = 15:45)
        """
        from datetime import datetime
        import pytz

        # Get current ET time
        et_tz = pytz.timezone('America/New_York')
        
        
        if timestamp:
            # Convert to datetime first if it's a string or other type
            if isinstance(timestamp, str):
                try:
                    from dateutil import parser
                    timestamp = parser.parse(timestamp)
                except Exception as e:
                    self.logger.warning(f"Failed to parse timestamp string '{timestamp}': {e}")
                    timestamp = None
            elif isinstance(timestamp, (int, float)):
                from datetime import datetime as dt_class
                timestamp = dt_class.fromtimestamp(timestamp)
            elif not isinstance(timestamp, datetime):
                # If not a valid type, fall back to current time
                timestamp = None

            # Validate timestamp is datetime before accessing tzinfo
            if timestamp and not isinstance(timestamp, datetime):
                self.logger.warning(f"timestamp is not datetime after conversion: {type(timestamp)}")
                timestamp = None

            # Now safe to access tzinfo
            if timestamp:
                if timestamp.tzinfo is None:
                    # If naive, assume it's already in the target timezone or handle carefully
                    # For replay, we usually get timestamps that might be naive but represent market time
                    # Let's assume input timestamp is correct relative to market hours
                    current_et = timestamp
                else:
                    current_et = timestamp.astimezone(et_tz)
            else:
                # Fallback to current time if conversion failed
                current_et = datetime.now(et_tz)
        else:
            # Use current wall clock time
            current_et = datetime.now(et_tz)
            
        current_hour = current_et.hour + current_et.minute / 60.0

        # Check for strategy-specific overrides first
        strategy_start_str = getattr(self.config, 'strategy_start_time', None)
        strategy_end_str = getattr(self.config, 'strategy_end_time', None)

        if strategy_start_str and strategy_end_str:
            # Use strategy-specific hours (e.g., GENERIC_01: 09:30-11:30)
            try:
                start_parts = strategy_start_str.split(':')
                start_hour = int(start_parts[0]) + int(start_parts[1]) / 60.0

                end_parts = strategy_end_str.split(':')
                end_hour = int(end_parts[0]) + int(end_parts[1]) / 60.0

                is_valid = start_hour <= current_hour <= end_hour

                if not is_valid and symbol:
                    symbol_str = f" for {symbol}" if symbol else ""
                    self.logger.warning(
                        f"⏰ Entry rejected{symbol_str}: Current time {current_hour:.2f} "
                        f"outside strategy-specific window [{start_hour:.2f} - {end_hour:.2f}] "
                        f"({strategy_start_str} - {strategy_end_str})"
                    )

                return is_valid, current_hour
            except Exception as e:
                self.logger.warning(f"Error parsing strategy-specific hours: {e}, falling back to global")

        # Fallback to global centralized values
        enable_extended = getattr(self.config, 'enable_extended_hours_trading', False)
        allow_premarket = getattr(self.config, 'allow_premarket_entries', False)
        
        if enable_extended and allow_premarket:
            # Use premarket start time (e.g., 04:00 or 07:00)
            market_open_str = getattr(self.config, 'premarket_start', '04:00')
            hours_mode_log = "EXTENDED (Premarket)"
        else:
            # Use regular market open (09:30)
            market_open_str = getattr(self.config, 'market_open_time', '09:30')
            hours_mode_log = "REGULAR"

        no_entry_after = float(getattr(self.config, 'no_entry_after', 15.75))
        
        # Convert market_open_time string (HH:MM) to decimal
        try:
            open_parts = market_open_str.split(':')
            market_open = int(open_parts[0]) + int(open_parts[1]) / 60.0
        except:
            market_open = 9.5 if not (enable_extended and allow_premarket) else 4.0

        # Optional: Allow after-hours if configured
        allow_afterhours = getattr(self.config, 'allow_afterhours_entries', False)
        if enable_extended and allow_afterhours:
             # Extend entry window to afterhours end (e.g. 20:00)
             afterhours_end_str = getattr(self.config, 'afterhours_end', '20:00')
             try:
                 ah_parts = afterhours_end_str.split(':')
                 ah_end = int(ah_parts[0]) + int(ah_parts[1]) / 60.0
                 no_entry_after = max(no_entry_after, ah_end)
                 hours_mode_log += " + AFTERHOURS"
             except:
                 pass

        self.logger.debug(
            f"DEBUG: is_within_entry_hours ({hours_mode_log}) - "
            f"window=[{market_open:.2f} - {no_entry_after:.2f}], current={current_hour:.2f}"
        )

        # Validate
        is_valid = market_open <= current_hour <= no_entry_after

        if not is_valid and symbol:
            symbol_str = f" for {symbol}" if symbol else ""
            # Only warn if it's significantly outside (avoid spamming logs for slight deviations)
            self.logger.warning(
                f"⏰ Entry rejected{symbol_str}: Current time {current_hour:.2f} "
                f"outside {hours_mode_log} window [{market_open:.2f} - {no_entry_after:.2f}]"
            )

        return is_valid, current_hour

    async def check_ods_filters(self, symbol: str, bars: List[Any], opportunity: Dict[str, Any]) -> Tuple[bool, float]:
        """
        [STANDARDIZED] Check Opening Drive Structure (ODS) Filters
        
        Evaluates market structure using pure price action (no external API needed).
        Applies confidence boosts or reductions based on the Day Type.
        
        Logic:
        1. Check if 'enable_ods_filters' is True in config.
        2. Calculate ODS Day Type (Trend Drive, Balance, Failed Drive).
        3. Apply boost/reduction to confidence.
        
        Args:
            symbol: Ticker symbol
            bars: List of bar objects
            opportunity: Opportunity dict (modified in-place if ODS data is added)
            
        Returns:
            Tuple[bool, float]: (is_allowed, confidence_boost)
                - is_allowed: True if trade is allowed, False if rejected by ODS
                - confidence_boost: Multiplier for confidence (e.g. 1.3 for Bullish Trend)
        """
        # 1. READ CONFIG
        section = self.worker_name.upper() + '_STRATEGY' if hasattr(self, 'worker_name') else 'GLOBAL'
        
        # Use fallback if not found
        enable_filters = True
        if self.config:
            # Helper to get config safely
            # Check strategy specific, then global?
            # Configparser usually handles defaults if set up right, but here we manually check.
            
            # Try specific section
            val = getattr(self.config, 'getboolean', lambda s, k, fallback=None: fallback)(section, 'enable_ods_filters', fallback=None)
            
            if val is not None:
                enable_filters = val
            else:
                # Try GLOBAL/default fallback or attribute
                enable_filters = getattr(self, 'enable_ods_filters', True)
        
        if not enable_filters:
            # Log only once per symbol debug to avoid spam
            # self.logger.debug(f"ℹ️ {symbol}: ODS filters DISABLED by config")
            return True, 1.0

        # 2. CALCULATE ODS
        try:
            from core.ods_classifier import ODSDayType
            
            # Use cached classifier service
            if not hasattr(self, 'ods_classifier'):
                 from core.service_locator import get_service_locator
                 self.ods_classifier = get_service_locator().get_ods_classifier()
                 
            ods = await self.ods_classifier.classify_symbol_ods(symbol, bars)
            
            # Store ODS data in opportunity for downstream usage (sizing, logging)
            opportunity['ods_data'] = ods
            
            # 3. APPLY RULES
            confidence_boost = 1.0
            
            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.3
                self.logger.info(f"✅ {symbol}: ODS BOOST - Bullish Trend Drive (score={ods.strength:.1f})")
            
            elif ods.day_type == ODSDayType.STRONG_BULLISH_OPEN:
                confidence_boost = 1.4
                self.logger.info(f"🔥 {symbol}: ODS STRONG BOOST - Strong Bullish Open")
                
            elif ods.day_type == ODSDayType.MODERATE_BULLISH_OPEN:
                confidence_boost = 1.2
                self.logger.info(f"✅ {symbol}: ODS Moderate Boost")
                
            elif ods.day_type == ODSDayType.FAILED_DRIVE:
                # Check config if we should REJECT or REDUCE
                # Default: REDUCE (don't block totally unless strict)
                reject_failed = getattr(self.config, 'getboolean', lambda s, k, fallback=False: fallback)(section, 'ods_filter_failed_drive', fallback=False)
                
                if reject_failed:
                    self.logger.info(f"⚪ {symbol}: ODS REJECT - Failed Drive Day (strict filter on)")
                    return False, 0.0
                else:
                    confidence_boost = 0.7
                    self.logger.info(f"⚠️ {symbol}: ODS REDUCTION - Failed Drive (reducing confidence)")
            
            elif ods.day_type == ODSDayType.BALANCE_DAY:
                 # Check config if we should REJECT or REDUCE
                reject_balance = getattr(self.config, 'getboolean', lambda s, k, fallback=False: fallback)(section, 'ods_filter_balance_day', fallback=False)
                
                if reject_balance:
                    self.logger.info(f"⚪ {symbol}: ODS REJECT - Balance Day (strict filter on)")
                    return False, 0.0
                else:
                    confidence_boost = 0.8
                    self.logger.info(f"⚠️ {symbol}: ODS REDUCTION - Balance Day (chop zone)")
            
            return True, confidence_boost
            
        except Exception as e:
            self.logger.warning(f"ODS Check failed: {e}")
            return True, 1.0 # Fail open if analysis breaks
            
    async def get_ods_for_symbol(self, symbol: str, bars: List[Any]):
        """Legacy helper - prefer check_ods_filters"""
        if not hasattr(self, 'ods_classifier'):
             from core.service_locator import get_service_locator
             self.ods_classifier = get_service_locator().get_ods_classifier()
        return await self.ods_classifier.classify_symbol_ods(symbol, bars)

    @abstractmethod
    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Lógica de entrada específica de cada worker

        EARLY ENTRY IMPLEMENTATION:
        Este método debe usar calculate_pattern_completion() para decidir:
        - Si completion >= 80%: Considerar entrada (early entry)
        - Si completion >= 100%: Evaluar si ya es tarde

        Debe ser implementado por cada worker concreto con sus criterios específicos
        Ej: Gap-Go verifica gap >= 8% y volume_ratio >= 2.0

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            True si debe entrar, False si no
        """
        pass

    @abstractmethod
    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Lógica de salida específica de cada worker

        Debe ser implementado por cada worker concreto
        Ej: Gap-Go usa take profit 15% y stop loss 3%

        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            (should_exit, reason): Tupla con decisión y motivo
        """
        pass

    async def _check_risk_approval(self, symbol: str) -> bool:
        """
        Valida con risk manager si podemos tomar posición

        NOTA: La validación real la hace ExecutionEngine.enter_position()
        que llama a risk_manager.validate_signal() y validate_order()
        Este método simplemente retorna True para continuar el flujo.

        Returns:
            True siempre (validación se hace en ExecutionEngine)
        """
        # La validación completa se hace en ExecutionEngine.enter_position()
        # que usa risk_manager.validate_signal() y validate_order()
        return True

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """
        Ejecuta entrada en posición usando ExecutionEngine compartido

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            True si entrada exitosa, False si falla
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            self.logger.info(f"🎯 {self.worker_name}: Executing entry for {symbol}")

            # EXTENDED HOURS CHECK: Verificar si podemos operar en extended hours
            if not self._is_extended_hours_allowed(symbol):
                return False

            # CRITICAL: Check with UnifiedPositionManager before executing entry
            # This prevents duplicate positions across all workers
            try:
                from core.service_locator import get_unified_position_manager
                unified_manager = await get_unified_position_manager()

                if unified_manager:
                    # Calculate position value for UnifiedPositionManager check
                    position_value = opportunity.get('current_price', 0) * opportunity.get('quantity', 1)

                    can_open, reason = unified_manager.can_open_position(
                        symbol=symbol,
                        strategy_type=self.worker_name,  # Pass actual worker name (e.g., 'volume_absorption')
                        position_value=position_value
                    )

                    if not can_open:
                        self.logger.warning(
                            f"🚫 {self.worker_name}: UNIFIED POSITION MANAGER BLOCKED entry for {symbol}: {reason}"
                        )
                        return False
                    else:
                        self.logger.debug(
                            f"✅ {self.worker_name}: UnifiedPositionManager approved entry for {symbol}"
                        )
                else:
                    self.logger.warning(
                        f"⚠️ {self.worker_name}: UnifiedPositionManager not available for {symbol} - proceeding anyway"
                    )

            except Exception as e:
                self.logger.error(
                    f"❌ {self.worker_name}: Error checking UnifiedPositionManager for {symbol}: {e} - proceeding anyway"
                )

            # DAILY POTENTIAL ANALYSIS: Retrieve from opportunity (already analyzed in should_enter())
            daily_potential = opportunity.get('daily_potential', {
                'can_swing': False,
                'can_swing_short': True,
                'reasons': ['Daily bars not available'],
                'rsi_daily': 50,
                'distance_to_resistance': 100,
                'distance_to_support': 100
            })

            # If not already analyzed (legacy path), analyze now
            if 'daily_potential' not in opportunity:
                daily_potential = await self._analyze_daily_potential_for_signal(opportunity)

            self.logger.debug(
                f"📊 {symbol}: Using daily analysis - "
                f"swing={daily_potential['can_swing']}, "
                f"swing_short={daily_potential['can_swing_short']}"
            )

            # TRADING HORIZON DETERMINATION: Determinar horizonte temporal de la señal
            signal_data = {
                'confidence': opportunity.get('quality_score', 50),  # Use quality_score as proxy
                'risk_reward': opportunity.get('risk_reward', 1.5),
                'volume_zscore': opportunity.get('volume_zscore', 0),
                'volume_ratio': opportunity.get('volume_ratio', 0),  # For fallback when R:R not available
                'catalyst_strength': opportunity.get('catalyst_strength', 0),  # For fallback when R:R not available
                'current_price': opportunity.get('current_price', 0),
                'entry_price': opportunity.get('entry_price', 0),
                'stop_loss': opportunity.get('stop_loss', 0),
                'take_profit': opportunity.get('take_profit', 0),
                'daily_potential': daily_potential  # NEW: Daily analysis results
            }

            # Determinar horizonte y tiempo esperado
            trading_horizon, expected_hold_hours = self._determine_trading_horizon(signal_data)
            
            # Calcular si es seguro para EOD (End-of-Day closure)
            # INTRADAY y SCALP deben cerrarse antes de EOD
            # SWING_SHORT y SWING pueden quedar overnight
            eod_safe = trading_horizon in [TradingHorizon.SWING, TradingHorizon.SWING_SHORT]

            # STRUCTURAL EXIT CALCULATOR: Calculate TP/SL based on market structure + Expected Value
            try:
                from core.structural_exit_calculator import get_structural_exit_calculator

                # Pass config dict to use parameters from config.ini
                exit_calculator = get_structural_exit_calculator(config=self.config)

                # Calculate ATR from daily bars if available
                atr = 0.0
                if 'bars_daily' in opportunity and opportunity['bars_daily']:
                    atr = self._calculate_atr_from_bars(opportunity['bars_daily'])

                # Add ATR to opportunity for calculator
                opportunity['atr'] = atr

                # Determine trading_horizon string for structural exit calculator
                # Map TradingHorizon enum to string expected by calculator
                if trading_horizon == TradingHorizon.INTRADAY:
                    horizon_str = "INTRADAY"
                elif trading_horizon == TradingHorizon.SWING_SHORT:
                    horizon_str = "SWING_SHORT"
                else:  # SWING
                    horizon_str = "SWING"

                # Calculate structural exits with R:R and EV validation
                # Pass trading_horizon to use appropriate support levels and max SL distance
                result = exit_calculator.calculate_exits(opportunity, trading_horizon=horizon_str)

                # Check if trade was REJECTED
                if result is None or not result.get('approved', False):
                    rejection_reason = result.get('rejection_reason', 'Unknown') if result else 'Calculation error'
                    self.logger.info(
                        f"❌ {symbol}: Trade REJECTED by structural exit calculator - {rejection_reason}"
                    )
                    if result:
                        # Show configured minimums from config.ini
                        min_rr = getattr(self.config, 'min_risk_reward_ratio', 2.0)
                        min_ev = getattr(self.config, 'min_expected_value_pct', 2.0)

                        if 'risk_reward' in result:
                            self.logger.info(f"   R:R: {result['risk_reward']:.2f} (min: {min_rr})")
                        if 'expected_value_pct' in result:
                            self.logger.info(f"   EV: {result['expected_value_pct']:.2f}% (min: {min_ev}%)")

                    # REJECT TRADE - return None to skip execution
                    return None

                # Trade APPROVED - apply structural exits
                opportunity['take_profit'] = result['tp_price']
                opportunity['take_profit_pct'] = result['tp_pct']
                opportunity['stop_loss'] = result['sl_price']
                opportunity['stop_loss_pct'] = result['sl_pct']
                opportunity['risk_reward'] = result['risk_reward']
                opportunity['expected_value_pct'] = result['expected_value_pct']
                opportunity['win_probability'] = result['win_probability']
                opportunity['position_size_adjustment'] = 1.0  # No adjustment (EV-based rejection instead)

                self.logger.info(
                    f"✅ {symbol}: Structural exits - "
                    f"TP=${result['tp_price']:.2f} ({result['tp_pct']:.1f}%), "
                    f"SL=${result['sl_price']:.2f} ({result['sl_pct']:.1f}%), "
                    f"R:R={result['risk_reward']:.2f}, "
                    f"EV={result['expected_value_pct']:.2f}%"
                )

                # Log reasoning
                for reason in result.get('reasoning', []):
                    self.logger.info(f"   • {reason}")

                # ADAPTIVE RISK SIZING: Calculate dynamic position size based on quality & patterns
                try:
                    # Get ODS and Intraday Structure classifications (if available)
                    ods_data = opportunity.get('ods_data', None)
                    intraday_structure = opportunity.get('intraday_structure', None)

                    # Calculate adaptive risk percentage (with EV and R:R boost from structural exits)
                    adaptive_risk_pct = self.calculate_adaptive_risk(
                        opportunity=opportunity,
                        ods_data=ods_data,
                        intraday_structure=intraday_structure,
                        structural_exits=result  # Pass structural exit data for EV/RR boost
                    )

                    # Store in opportunity for ExecutionEngine
                    opportunity['adaptive_risk_percent'] = adaptive_risk_pct

                    # CLASSIFY TRADE TIER (A/B/C/D) for visibility and analytics
                    trade_tier = self.classify_trade_tier(
                        ev_pct=result.get('expected_value_pct', 0),
                        risk_pct=adaptive_risk_pct,
                        quality_score=opportunity.get('quality_score', 0),
                        rr=result.get('risk_reward', 0)
                    )

                    # Store tier in opportunity for database
                    opportunity['trade_tier'] = trade_tier

                    # Log with tier for visibility
                    tier_emoji = {
                        'A': '🌟',  # Exceptional
                        'B': '💎',  # High Quality
                        'C': '✅',  # Good
                        'D': '⚪'   # Marginal
                    }.get(trade_tier, '❓')

                    self.logger.info(
                        f"💰 {symbol}: Adaptive risk sizing = {adaptive_risk_pct*100:.2f}% of capital | "
                        f"Trade Tier: {tier_emoji} {trade_tier}"
                    )

                except Exception as e:
                    self.logger.warning(f"⚠️ {symbol}: Adaptive risk calculation failed: {e}")
                    # Fallback to default if calculation fails
                    opportunity['adaptive_risk_percent'] = 0.012  # 1.2% default
                    opportunity['trade_tier'] = 'D'  # Default to marginal tier

                # VALIDATE: If support detected, wait for BOUNCE from support before entry
                # Strategy: Wait for pullback TO support, then buy the BOUNCE (0-1% above support)
                # support_level = opportunity.get('support_level', 0.0) # ALREADY DEFINED
                
                # Check directly from result which is more reliable
                # But logic below uses opportunity.get('support_level')
                # Let's trust logic below, just need to close block correctly
                 
                support_level = opportunity.get('support_level', 0.0)
                current_price = opportunity.get('current_price', 0)

                if support_level > 0 and current_price > 0:
                    # RELAXED PULLBACK LOGIC: More flexible entry criteria
                    # Problem: Old logic was too strict - required exact support touch, missed many opportunities
                    # Solution: Allow entry if price is NEAR support OR showing strength above support
                    bars = opportunity.get('bars', [])
                    has_touched_support = False
                    is_bouncing = False
                    is_near_support = False

                    if len(bars) >= 10:
                        # Check last 10 bars for support test
                        recent_bars = bars[-10:]
                        recent_lows = [bar.low for bar in recent_bars]

                        # Support touched if any recent low came within 1.0% of support (RELAXED from 0.5%)
                        for low in recent_lows:
                            distance_to_support = abs((low - support_level) / support_level) * 100
                            if distance_to_support <= 1.0:  # RELAXED: Within 1.0% = touched (was 0.5%)
                                has_touched_support = True
                                break

                        # Check if bouncing (last 3 bars trending up from support)
                        if has_touched_support and len(recent_bars) >= 3:
                            last_3_closes = [bar.close for bar in recent_bars[-3:]]
                            # Bouncing if closes are rising
                            is_bouncing = last_3_closes[-1] > last_3_closes[0]

                    distance_from_support_pct = ((current_price - support_level) / support_level) * 100
                    MAX_BOUNCE_FROM_SUPPORT = 2.5  # RELAXED: Entry zone 0-2.5% above support (was 1.0%)

                    # Check if price is near support (within 1.5% above)
                    is_near_support = 0 <= distance_from_support_pct <= 1.5

                    # RELAXED Entry conditions (any of these):
                    # OPTION A: Traditional pullback - touched support + bouncing + in entry zone
                    # OPTION B: Near support - price is close enough to support (within 1.5%)
                    # OPTION C: Above support but not extended - within 2.5% above support (still good R:R)

                    traditional_entry = has_touched_support and is_bouncing and distance_from_support_pct <= MAX_BOUNCE_FROM_SUPPORT
                    near_support_entry = is_near_support  # Within 1.5% is good enough
                    above_support_entry = 0 <= distance_from_support_pct <= MAX_BOUNCE_FROM_SUPPORT  # Within 2.5%

                    # If none of the entry conditions are met, check why
                    if not (traditional_entry or near_support_entry or above_support_entry):
                        if distance_from_support_pct < 0:
                            self.logger.info(
                                f"⏳ {symbol}: Below support - Price ${current_price:.2f} is {abs(distance_from_support_pct):.1f}% "
                                f"below support ${support_level:.2f} - wait for bounce"
                            )
                            return False
                        elif distance_from_support_pct > MAX_BOUNCE_FROM_SUPPORT:
                            self.logger.info(
                                f"⏳ {symbol}: Too extended - Price ${current_price:.2f} is {distance_from_support_pct:.1f}% "
                                f"above support ${support_level:.2f} (max {MAX_BOUNCE_FROM_SUPPORT}%) - missed entry zone"
                            )
                            return False
                        else:
                            # This shouldn't happen, but log for debugging
                            self.logger.info(
                                f"⏳ {symbol}: Waiting for better entry - Price ${current_price:.2f} vs support ${support_level:.2f}"
                            )
                            return False

                    # Determine which entry type was triggered
                    if traditional_entry:
                        entry_type = "TRADITIONAL PULLBACK"
                    elif near_support_entry:
                        entry_type = "NEAR SUPPORT"
                    else:
                        entry_type = "ABOVE SUPPORT"

                    # All conditions met - ready to enter
                    self.logger.info(
                        f"✅ {symbol}: {entry_type} ENTRY - Price ${current_price:.2f} at {distance_from_support_pct:.1f}% "
                        f"above support ${support_level:.2f} - Entry zone confirmed"
                    )

                # REJECT if R:R is too poor (TP must be at least equal to SL)
                # FIX: Use 'result' instead of undefined 'targets'
                if result['risk_reward'] < 1.0:
                    self.logger.warning(
                        f"❌ {symbol}: REJECTED - Poor risk/reward ratio ({result['risk_reward']:.2f}) - "
                        f"TP={result['tp_pct']:.1f}% < SL={result['sl_pct']:.1f}%"
                    )
                    return False

            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Could not calculate quality targets: {e} - using defaults")

            # Agregar metadatos del horizonte a la oportunidad
            opportunity['trading_horizon'] = trading_horizon.value
            opportunity['expected_hold_hours'] = expected_hold_hours
            opportunity['EOD_safe'] = eod_safe

            self.logger.info(
                f"📅 {symbol}: Trading horizon = {trading_horizon.value} "
                f"({expected_hold_hours:.1f}h expected, EOD_safe={eod_safe})"
            )

            # Ejecutar entrada usando ExecutionEngine compartido
            position = await self.execution_engine.enter_position(
                symbol=symbol,
                strategy=self.worker_name,
                opportunity_data=opportunity
            )

            if position:
                # Entry successful - clear any previous failures
                if symbol in self.failed_entries:
                    del self.failed_entries[symbol]

                # Guardar posición en tracking del worker con metadatos del horizonte
                self.active_positions[symbol] = {
                    'position': position,
                    'entry_time': datetime.now(),
                    'entry_price': position.get('entry_price', 0),
                    'quantity': position.get('quantity', 0),
                    'opportunity_data': opportunity,
                    # Trading horizon metadata
                    'trading_horizon': trading_horizon.value,
                    'expected_hold_hours': expected_hold_hours,
                    'EOD_safe': eod_safe
                }

                self.logger.info(
                    f"✅ {self.worker_name}: Position opened - "
                    f"{symbol} @ ${position.get('entry_price', 0):.2f} "
                    f"x {position.get('quantity', 0)} shares "
                    f"[{trading_horizon.value}, {expected_hold_hours:.1f}h]"
                )
                return True
            else:
                # Entry failed - register failure (max 2 attempts)
                attempts = 1
                if symbol in self.failed_entries:
                    attempts = self.failed_entries[symbol]['attempts'] + 1

                self.failed_entries[symbol] = {
                    'reason': 'Entry returned no position (order rejected or failed)',
                    'attempts': attempts
                }

                if attempts >= self.max_entry_attempts:
                    self.logger.warning(
                        f"❌ {symbol}: Entry failed (attempt #{attempts}/{self.max_entry_attempts}) - "
                        f"BLACKLISTED until restart"
                    )
                else:
                    self.logger.warning(
                        f"⚠️ {symbol}: Entry failed (attempt #{attempts}/{self.max_entry_attempts}) - "
                        f"will retry once more"
                    )
                return False

        except Exception as e:
            # Entry exception - register failure (max 2 attempts)
            attempts = 1
            if symbol in self.failed_entries:
                attempts = self.failed_entries[symbol]['attempts'] + 1

            self.failed_entries[symbol] = {
                'reason': f'Entry exception: {str(e)[:100]}',
                'attempts': attempts
            }

            if attempts >= self.max_entry_attempts:
                self.logger.error(
                    f"❌ {self.worker_name}: Entry failed for {symbol} "
                    f"(attempt #{attempts}/{self.max_entry_attempts}): {e} - BLACKLISTED until restart"
                )
            else:
                self.logger.error(
                    f"⚠️ {self.worker_name}: Entry failed for {symbol} "
                    f"(attempt #{attempts}/{self.max_entry_attempts}): {e} - will retry once more"
                )

            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def _monitor_positions(self):
        """
        Monitorea todas las posiciones activas del worker
        Evalúa salidas y ejecuta si es necesario

        NUEVO: A las 15:30 ET, evalúa swing transitions (mantener overnight)
        """
        if not self.active_positions:
            return

        # SWING TRANSITION CHECK (15:30 ET - once per day)
        await self._check_swing_transition()

        # Iterar sobre copia para poder modificar dict durante iteración
        for symbol, data in list(self.active_positions.items()):
            try:
                # Obtener precio actual
                current_price = await self._get_current_price(symbol)

                if current_price <= 0:
                    self.logger.warning(f"⚠️ {symbol}: Invalid price {current_price}")
                    continue

                # Use entry_price from position data (already set correctly from IBKR during entry)
                position_data = data['position'].copy()

                # Evaluate exit with strategy-specific logic
                should_exit, reason = await self.should_exit(
                    symbol=symbol,
                    position=position_data,
                    current_price=current_price
                )

                if should_exit:
                    await self._execute_exit(symbol, reason, current_price)
                else:
                    # Log estado periódico (cada minuto)
                    self._log_position_status(symbol, data, current_price)

            except Exception as e:
                self.logger.error(f"❌ Error monitoring {symbol}: {e}")

    async def _get_current_price(self, symbol: str) -> float:
        """
        Obtiene precio actual del símbolo usando BatchPriceManager si disponible

        Returns:
            Precio actual, 0 si error
        """
        try:
            # PRIORITY 1: Use BatchPriceManager for guaranteed fresh prices
            if hasattr(self.execution_engine, 'broker') and hasattr(self.execution_engine.broker, 'batch_price_manager'):
                bpm = self.execution_engine.broker.batch_price_manager

                # Check if price is fresh (< 5 seconds old)
                if bpm.is_price_fresh(symbol, max_age_seconds=5):
                    price = bpm.get_current_price(symbol)
                    if price > 0:
                        self.logger.debug(f"💰 {symbol}: Using fresh BatchPriceManager price: ${price:.2f}")
                        return price

                # Price is stale or not available - try to get fresh one
                self.logger.debug(f"⚠️ {symbol}: BatchPriceManager price stale, attempting refresh...")

                # Check if symbol is subscribed, if not, subscribe it
                if not bpm.is_subscribed(symbol):
                    self.logger.debug(f"📡 {symbol}: Not subscribed, attempting subscription...")
                    success = await bpm.add_symbol_subscription(symbol)
                    if success:
                        self.logger.debug(f"✅ {symbol}: Successfully subscribed for fresh price")
                        # Wait a moment for price to arrive
                        await asyncio.sleep(0.5)
                        if bpm.is_price_fresh(symbol, max_age_seconds=5):
                            price = bpm.get_current_price(symbol)
                            if price > 0:
                                return price

            # PRIORITY 2: Fallback to ExecutionEngine methods
            price = await self.execution_engine.get_current_price(symbol)
            if price and price > 0:
                self.logger.debug(f"💰 {symbol}: Using ExecutionEngine fallback price: ${price:.2f}")
                return price

            return 0.0

        except Exception as e:
            self.logger.error(f"❌ Error getting price for {symbol}: {e}")
            return 0.0

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """
        Ejecuta salida de posición usando ExecutionEngine compartido

        Args:
            symbol: Símbolo a cerrar
            reason: Motivo de salida (para logs)
            current_price: Precio actual (para cálculo de PnL)
        """
        try:
            position_data = self.active_positions.get(symbol)
            if not position_data:
                self.logger.warning(f"⚠️ {symbol}: No position data for exit")
                return

            entry_price = position_data.get('entry_price', 0)
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

            self.logger.info(
                f"🚪 {self.worker_name}: Exiting {symbol} - "
                f"{reason} (PnL: {pnl_pct:+.2f}%)"
            )

            # Ejecutar cierre usando ExecutionEngine compartido
            await self.execution_engine.close_position(
                symbol=symbol,
                reason=reason
            )

            # Remover de tracking
            del self.active_positions[symbol]

            # Unlock ticker in Trade Arbiter with cooldown based on exit reason
            try:
                from core.trade_arbiter import get_trade_arbiter
                arbiter = get_trade_arbiter()
                arbiter.unlock_ticker(symbol, exit_reason=reason)
            except Exception as e:
                self.logger.debug(f"Could not unlock ticker {symbol} in arbiter: {e}")

            self.logger.info(f"✅ {self.worker_name}: Position closed - {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Exit failed for {symbol}: {e}")

    def _log_position_status(self, symbol: str, data: Dict, current_price: float):
        """
        Log periódico del estado de posición (cada minuto aprox)
        """
        try:
            # Solo log cada 60 checks (1 por minuto si check es cada segundo)
            if not hasattr(self, '_log_counter'):
                self._log_counter = {}

            self._log_counter[symbol] = self._log_counter.get(symbol, 0) + 1

            if self._log_counter[symbol] % 60 == 0:
                entry_price = data.get('entry_price', 0)
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                self.logger.debug(
                    f"📊 {symbol}: ${current_price:.2f} (PnL: {pnl_pct:+.2f}%)"
                )

        except Exception:
            pass

    def _is_extended_hours_allowed(self, symbol: str) -> bool:
        """
        Verifica si está permitido operar en extended hours para este símbolo

        Returns:
            True si está permitido, False si no
        """
        try:
            # Get config from service locator instead of self.config
            from core.service_locator import get_service_locator
            config = get_service_locator().get_config()

            # Handle UnifiedConfig dataclass - use dot notation instead of get()
            extended_hours_enabled = getattr(config, 'enable_extended_hours_trading', False)
            allow_premarket = getattr(config, 'allow_premarket_entries', False)
            allow_afterhours = getattr(config, 'allow_afterhours_entries', False)

            # Si extended hours está habilitado globalmente, permitir todo
            if extended_hours_enabled:
                return True

            # Si extended hours no está habilitado globalmente, verificar sesiones específicas
            from core.extended_hours_manager import ExtendedHoursManager
            extended_manager = ExtendedHoursManager()
            current_session = extended_manager.get_market_session()

            if current_session.name in ['PREMARKET', 'AFTERHOURS']:
                # Permitir premarket si está habilitado específicamente
                if current_session.name == 'PREMARKET' and allow_premarket:
                    self.logger.info(
                        f"✅ {self.worker_name}: Premarket trading ALLOWED for {symbol} - "
                        f"Current session: {current_session.name}"
                    )
                    return True
                # Permitir afterhours si está habilitado específicamente
                elif current_session.name == 'AFTERHOURS' and allow_afterhours:
                    self.logger.info(
                        f"✅ {self.worker_name}: Afterhours trading ALLOWED for {symbol} - "
                        f"Current session: {current_session.name}"
                    )
                    return True
                else:
                    self.logger.warning(
                        f"🚫 {self.worker_name}: Extended hours trading DISABLED for {symbol} - "
                        f"Current session: {current_session.name}"
                    )
                    return False

            # Estamos en regular hours, permitir
            return True

        except Exception as e:
            self.logger.error(f"❌ Error checking extended hours for {symbol}: {e}")
            return False

    def get_active_positions_count(self) -> int:
        """Retorna número de posiciones activas"""
        return len(self.active_positions)

    def get_active_symbols(self) -> list:
        """Retorna lista de símbolos con posiciones activas"""
        return list(self.active_positions.keys())

    async def stop(self):
        """Detiene el worker"""
        self.logger.info(f"🛑 Stopping worker {self.worker_name}")
        self.is_running = False

        # Cerrar todas las posiciones abiertas
        if self.active_positions:
            self.logger.warning(
                f"⚠️ Closing {len(self.active_positions)} open positions"
            )
            for symbol in list(self.active_positions.keys()):
                try:
                    await self._execute_exit(symbol, "SHUTDOWN", 0.0)
                except Exception as e:
                    self.logger.error(f"Error closing {symbol}: {e}")

    # ============================================================================
    # HELPER FUNCTIONS FOR BAR ANALYSIS
    # ============================================================================

    def calculate_vwap_from_bars(self, bars: list) -> Optional[float]:
        """
        Calcula VWAP (Volume Weighted Average Price) desde lista de barras

        Args:
            bars: Lista de barras de 1 minuto (objetos Bar de ib_insync)

        Returns:
            VWAP calculado o None si no se puede calcular
        """
        try:
            if not bars or len(bars) == 0:
                return None

            total_pv = 0.0
            total_volume = 0.0

            for bar in bars:
                # Typical price = (high + low + close) / 3
                typical_price = (bar.high + bar.low + bar.close) / 3
                total_pv += typical_price * bar.volume
                total_volume += bar.volume

            if total_volume == 0:
                return None

            vwap = total_pv / total_volume
            return vwap

        except Exception as e:
            self.logger.debug(f"Error calculating VWAP from bars: {e}")
            return None

    def calculate_pmh_from_bars(self, bars: list, market_open_hour: int = 9, market_open_minute: int = 30) -> Optional[float]:
        """
        Calcula Pre-Market High (PMH) desde lista de barras

        Args:
            bars: Lista de barras de 1 minuto
            market_open_hour: Hora de apertura del mercado (default: 9)
            market_open_minute: Minuto de apertura del mercado (default: 30)

        Returns:
            PMH (precio más alto pre-market) o None si no hay barras pre-market
        """
        try:
            if not bars or len(bars) == 0:
                return None

            pmh = None

            for bar in bars:
                # Extraer hora de la barra
                bar_time = bar.date if hasattr(bar, 'date') else bar.time

                # Si es datetime, extraer hora/minuto
                if hasattr(bar_time, 'hour'):
                    hour = bar_time.hour
                    minute = bar_time.minute

                    # Check if pre-market (antes de market_open)
                    is_premarket = (hour < market_open_hour) or (hour == market_open_hour and minute < market_open_minute)

                    if is_premarket:
                        if pmh is None or bar.high > pmh:
                            pmh = bar.high

            return pmh

        except Exception as e:
            self.logger.debug(f"Error calculating PMH from bars: {e}")
            return None

    def detect_consolidation_from_bars(self, bars: list, window: int = 15, threshold_pct: float = 3.0) -> bool:
        """
        Detecta si hay consolidación en las últimas N barras

        Args:
            bars: Lista de barras de 1 minuto
            window: Número de barras a analizar (default: 15 = últimos 15 minutos)
            threshold_pct: Rango de consolidación aceptable en % (default: 3%)

        Returns:
            True si está consolidando, False si no
        """
        try:
            if not bars or len(bars) < window:
                return False

            # Analizar últimas N barras
            recent_bars = bars[-window:]

            highs = [bar.high for bar in recent_bars]
            lows = [bar.low for bar in recent_bars]

            max_high = max(highs)
            min_low = min(lows)

            # Calcular rango de precio
            price_range = max_high - min_low
            mid_price = (max_high + min_low) / 2

            # Calcular rango como % del precio medio
            range_pct = (price_range / mid_price) * 100

            # Si el rango es menor al threshold, está consolidando
            is_consolidating = range_pct < threshold_pct

            return is_consolidating

        except Exception as e:
            self.logger.debug(f"Error detecting consolidation from bars: {e}")
            return False

    def calculate_rsi_from_bars(self, bars: list, period: int = 14) -> Optional[float]:
        """
        Calcula RSI (Relative Strength Index) desde lista de barras

        Args:
            bars: Lista de barras de 1 minuto
            period: Período para cálculo RSI (default: 14)

        Returns:
            RSI calculado (0-100) o None si no hay suficientes barras
        """
        try:
            if not bars or len(bars) < period + 1:
                return None

            # Calcular cambios de precio
            closes = [bar.close for bar in bars]
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]

            # Separar ganancias y pérdidas
            gains = [max(change, 0) for change in changes]
            losses = [abs(min(change, 0)) for change in changes]

            # Calcular promedio de ganancias y pérdidas (últimos N períodos)
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                return 100.0  # Sin pérdidas = RSI máximo

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.debug(f"Error calculating RSI from bars: {e}")
            return None

    def get_bars_from_opportunity(self, opportunity: Dict[str, Any]) -> list:
        """
        Extrae bars_history del opportunity dict de forma segura

        Args:
            opportunity: Opportunity dict del scanner

        Returns:
            Lista de barras o lista vacía si no disponible
        """
        # Try both 'bars_history' (scanner format) and 'bars' (engine-fetched format)
        bars = opportunity.get('bars_history', opportunity.get('bars', []))
        if bars and len(bars) > 0:
            # Convert dict bars to BarDataWrapper objects if needed
            if isinstance(bars[0], dict):
                return [BarDataWrapper(bar) for bar in bars]
            return bars
        return []

    def validate_vwap_strength(
        self,
        bars: list,
        current_price: float,
        vwap_window_minutes: int = 60,
        trend_lookback_minutes: int = 10,
        opportunity: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Valida que el precio esté por encima del VWAP y que VWAP tenga tendencia positiva/plana

        FILTRO CRÍTICO: Evita entradas en acciones con debilidad institucional

        Validaciones:
        1. Precio actual >= VWAP rolling (fuerza compradora)
        2. VWAP actual >= VWAP anterior (sin presión vendedora)

        VWAP ROLLING: Usa solo últimas N barras (default 60min = 1 hora)
        - Smallcaps volátiles: 30 minutos
        - Momentum plays: 60 minutos (recomendado)
        - Plays conservadores: 120 minutos

        Args:
            bars: Lista de barras de 1 minuto desde apertura
            current_price: Precio actual del ticker
            vwap_window_minutes: Ventana rolling del VWAP en minutos (default: 60)
            trend_lookback_minutes: Minutos hacia atrás para calcular tendencia VWAP (default: 10)

        Returns:
            Tuple (is_valid, reason):
                - is_valid: True si pasa validación, False si no
                - reason: Mensaje explicativo
        """
        try:
            if not bars or len(bars) < trend_lookback_minutes:
                return False, f"Insufficient bars for VWAP validation (need {trend_lookback_minutes}, got {len(bars)})"

            # VWAP ROLLING: Usar solo últimas N barras (60 min por defecto)
            # Esto hace que el VWAP sea más reactivo al momentum reciente
            recent_bars = bars[-vwap_window_minutes:] if len(bars) >= vwap_window_minutes else bars

            actual_window = len(recent_bars)

            # Calculate current VWAP (últimas N barras)
            current_vwap = self.calculate_vwap_from_bars(recent_bars)

            if current_vwap is None:
                return False, "Could not calculate current VWAP"

            # VALIDATION 1: Price must be close to VWAP (within 2% below - institutional strength)
            # ADAPTIVE: Auto-adjust based on market regime + CATALYST OVERRIDE for smallcaps
            try:
                from core.adaptive_threshold_manager import get_adaptive_threshold_manager
                threshold_mgr = get_adaptive_threshold_manager()
                # SMALLCAP-AWARE: Pass opportunity for catalyst override
                thresholds = threshold_mgr.get_thresholds(opportunity=opportunity)
                vwap_tolerance_pct = thresholds.vwap_price_tolerance_pct
            except Exception:
                # Fallback: Manual Friday adjustment if adaptive system not available
                from datetime import datetime
                import pytz
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(eastern)
                vwap_tolerance_pct = 2.0  # Default
                if now_et.weekday() == 4:  # Friday
                    vwap_tolerance_pct = 3.5  # Friday relaxation

            # Cache thresholds to avoid duplicate logs
            cached_thresholds = thresholds if 'thresholds' in locals() else None

            # QUALITY-AWARE VWAP FILTER: Relax tolerance for high-quality setups
            quality_score = opportunity.get('quality_score', 0) if opportunity else 0
            if quality_score >= 85:  # A+ setups
                vwap_tolerance_pct = max(vwap_tolerance_pct, 4.0)  # Relaxed to 4.0%
            elif quality_score >= 75:  # A setups
                vwap_tolerance_pct = max(vwap_tolerance_pct, 3.5)  # Relaxed to 3.5% (was 2.5%)

            min_acceptable_price = current_vwap * (1 - vwap_tolerance_pct / 100)

            if current_price < min_acceptable_price:
                return False, f"Price ${current_price:.2f} more than {vwap_tolerance_pct}% below VWAP ${current_vwap:.2f} (min: ${min_acceptable_price:.2f}, {actual_window}min window)"

            # VALIDATION 2: VWAP must have positive or flat trend (no selling pressure)
            # Calculate VWAP from N minutes ago (dentro de la ventana rolling)
            if len(recent_bars) <= trend_lookback_minutes:
                # No hay suficientes barras para calcular tendencia, pero precio cerca de VWAP es suficiente
                return True, f"Price ${current_price:.2f} within 2% of VWAP ${current_vwap:.2f} ✓ ({actual_window}min)"

            # Comparar VWAP actual vs VWAP de hace N minutos (dentro de ventana rolling)
            bars_until_lookback = recent_bars[:-trend_lookback_minutes]
            previous_vwap = self.calculate_vwap_from_bars(bars_until_lookback)

            if previous_vwap is None:
                # If we can't calculate previous VWAP, accept if price > current VWAP
                return True, f"Price ${current_price:.2f} > VWAP ${current_vwap:.2f} ✓ ({actual_window}min)"

            # Check VWAP trend
            vwap_trend_pct = ((current_vwap - previous_vwap) / previous_vwap) * 100

            # ADAPTIVE: Auto-adjust based on market regime + CATALYST OVERRIDE
            try:
                # Use cached thresholds if available, otherwise get fresh ones
                if cached_thresholds is not None:
                    thresholds = cached_thresholds
                else:
                    from core.adaptive_threshold_manager import get_adaptive_threshold_manager
                    threshold_mgr = get_adaptive_threshold_manager()
                    # SMALLCAP-AWARE: Use same thresholds object (already includes catalyst override)
                    thresholds = threshold_mgr.get_thresholds(opportunity=opportunity)
                max_vwap_decline = thresholds.vwap_trend_tolerance_pct
            except Exception:
                # Fallback: Manual Friday adjustment if adaptive system not available
                from datetime import datetime
                import pytz
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(eastern)
                max_vwap_decline = 0.0  # Default: no decline
                if now_et.weekday() == 4:  # Friday
                    max_vwap_decline = -0.15  # Friday relaxation

            if vwap_trend_pct < max_vwap_decline:
                return False, f"VWAP declining ({vwap_trend_pct:+.2f}% in last {trend_lookback_minutes}min) - selling pressure"

            # PASSED ALL VALIDATIONS
            return True, f"Price ${current_price:.2f} within 2% of VWAP ${current_vwap:.2f} ({actual_window}min), trend {vwap_trend_pct:+.2f}% ✓"

        except Exception as e:
            self.logger.error(f"Error validating VWAP strength: {e}")
            return False, f"VWAP validation error: {str(e)}"

    def check_multi_timeframe_trend(
        self,
        bars: List,
        symbol: str = "UNKNOWN"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifica que la tendencia sea alcista en múltiples timeframes

        MULTI-TIMEFRAME TREND ANALYSIS:
        - Analiza EMA 9/21 en diferentes ventanas temporales
        - Timeframes: 5min, 15min, 60min (short, medium, long)
        - Requiere alineación: TODOS alcistas o al menos 2/3 alcistas

        Args:
            bars: Lista de barras de 1min
            symbol: Símbolo del ticker

        Returns:
            Tuple[bool, str, Dict]: (es_alcista, razón, detalles)

        TREND DETECTION LOGIC:
        - EMA9 > EMA21 = Alcista ✅
        - EMA9 < EMA21 = Bajista ❌
        - EMA9 ≈ EMA21 (±0.3%) = Lateral ➡️
        """
        try:
            if not bars or len(bars) < 60:  # Mínimo 60 barras (1h)
                return False, f"Insufficient bars ({len(bars) if bars else 0}/60)", {}

            # ========================================================================
            # TIMEFRAME WINDOWS (usando barras de 1min)
            # ========================================================================
            # 5min = últimas 5 barras
            # 15min = últimas 15 barras
            # 60min = últimas 60 barras

            timeframes = {
                '5min': 5,
                '15min': 15,
                '60min': 60
            }

            trends = {}

            for tf_name, window_size in timeframes.items():
                if len(bars) < window_size:
                    trends[tf_name] = {
                        'trend': 'UNKNOWN',
                        'reason': f'Insufficient bars ({len(bars)}/{window_size})',
                        'ema9': None,
                        'ema21': None
                    }
                    continue

                # Get window of bars for this timeframe
                tf_bars = bars[-window_size:]

                # Calculate EMAs
                ema9 = self._calculate_ema(tf_bars, period=min(9, window_size))
                ema21 = self._calculate_ema(tf_bars, period=min(21, window_size))

                if ema9 is None or ema21 is None:
                    trends[tf_name] = {
                        'trend': 'UNKNOWN',
                        'reason': 'EMA calculation failed',
                        'ema9': ema9,
                        'ema21': ema21
                    }
                    continue

                # Determine trend
                diff_pct = ((ema9 - ema21) / ema21) * 100

                if diff_pct > 0.3:  # EMA9 > EMA21 (+0.3%)
                    trend = 'BULLISH'
                    emoji = '📈'
                elif diff_pct < -0.3:  # EMA9 < EMA21 (-0.3%)
                    trend = 'BEARISH'
                    emoji = '📉'
                else:  # -0.3% <= diff <= +0.3%
                    trend = 'SIDEWAYS'
                    emoji = '➡️'

                trends[tf_name] = {
                    'trend': trend,
                    'diff_pct': diff_pct,
                    'ema9': ema9,
                    'ema21': ema21,
                    'emoji': emoji
                }

            # ========================================================================
            # TREND ALIGNMENT ANALYSIS
            # ========================================================================
            bullish_count = sum(1 for tf in trends.values() if tf.get('trend') == 'BULLISH')
            bearish_count = sum(1 for tf in trends.values() if tf.get('trend') == 'BEARISH')
            sideways_count = sum(1 for tf in trends.values() if tf.get('trend') == 'SIDEWAYS')
            total_valid = bullish_count + bearish_count + sideways_count

            # Build summary string
            summary = []
            for tf_name in ['5min', '15min', '60min']:
                tf_data = trends.get(tf_name, {})
                trend = tf_data.get('trend', 'UNKNOWN')
                emoji = tf_data.get('emoji', '❓')
                diff_pct = tf_data.get('diff_pct', 0)
                summary.append(f"{tf_name}:{emoji}{trend}({diff_pct:+.1f}%)")

            summary_str = " | ".join(summary)

            # ========================================================================
            # VALIDATION LOGIC
            # ========================================================================
            # STRICT MODE: Requiere mayoría alcista (al menos 2/3)
            # PERMISSIVE MODE: Permite si no hay mayoría bajista

            if total_valid == 0:
                return False, f"No valid timeframes analyzed", trends

            # STRICT: At least 2/3 must be bullish
            bullish_threshold = 2  # At least 2 out of 3

            if bullish_count >= bullish_threshold:
                self.logger.info(
                    f"✅ {symbol}: Multi-timeframe BULLISH aligned "
                    f"({bullish_count}/{total_valid} bullish) - {summary_str}"
                )
                return True, f"MTF Bullish ({bullish_count}/{total_valid})", trends

            # If bearish dominates, reject
            if bearish_count >= 2:
                self.logger.warning(
                    f"❌ {symbol}: Multi-timeframe BEARISH trend detected "
                    f"({bearish_count}/{total_valid} bearish) - {summary_str}"
                )
                return False, f"MTF Bearish ({bearish_count}/{total_valid})", trends

            # Mixed or sideways
            self.logger.warning(
                f"⚠️ {symbol}: Multi-timeframe MIXED/SIDEWAYS "
                f"(bullish:{bullish_count}, bearish:{bearish_count}, sideways:{sideways_count}) - {summary_str}"
            )
            return False, f"MTF Mixed (need {bullish_threshold}/3 bullish, got {bullish_count})", trends

        except Exception as e:
            self.logger.error(f"❌ Error checking multi-timeframe trend: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False, f"MTF analysis error: {str(e)}", {}

    def _calculate_ema(self, bars: List, period: int) -> Optional[float]:
        """
        Calcula EMA (Exponential Moving Average)

        Args:
            bars: Lista de barras con .close
            period: Período de la EMA (ej: 9, 21)

        Returns:
            EMA actual o None si falla
        """
        try:
            if not bars or len(bars) < period:
                return None

            # Get closing prices
            closes = []
            for bar in bars:
                if hasattr(bar, 'close'):
                    closes.append(float(bar.close))
                elif isinstance(bar, dict):
                    closes.append(float(bar.get('close', 0)))
                else:
                    return None

            if len(closes) < period:
                return None

            # Calculate EMA
            multiplier = 2.0 / (period + 1)

            # Start with SMA as seed
            ema = sum(closes[:period]) / period

            # Calculate EMA for rest of bars
            for close in closes[period:]:
                ema = (close - ema) * multiplier + ema

            return ema

        except Exception as e:
            self.logger.error(f"Error calculating EMA: {e}")
            return None

    def _is_price_action_weak(self, bars: list, current_price: float, lookback_periods: int = 6) -> bool:
        """
        Detecta si el price action muestra debilidad/distribución

        FILTRO ANTI-TRAMPA: Evita comprar techos de premarket, resistencias históricas,
        o fases de distribución en smallcaps.

        Señales de debilidad:
        1. Mayoría de barras bajistas recientes (distribution)
        2. Máximos decrecientes / Lower highs (rejection)
        3. Volumen en barras bajistas > volumen en alcistas (institutional selling)
        4. Precio cayendo significativamente desde máximo reciente (resistance hit)

        Args:
            bars: Historical bars (intraday 5min recommended)
            current_price: Current price
            lookback_periods: Periodos a analizar (default: 6 = 30 min con barras 5min)

        Returns:
            True si muestra debilidad/distribución

        Example:
            >>> if self._is_price_action_weak(bars, current_price):
            >>>     self.logger.info(f"{symbol}: Weak price action - REJECTING")
            >>>     return False
        """
        try:
            if not bars or len(bars) < 10:
                return False

            symbol = getattr(self, 'current_symbol', 'UNKNOWN')
            recent_bars = bars[-lookback_periods:] if len(bars) >= lookback_periods else bars

            # SEÑAL 1: Mayoría de barras bajistas (distribution pattern)
            bearish_count = sum(1 for bar in recent_bars if bar.close < bar.open)
            bearish_ratio = bearish_count / len(recent_bars)

            if bearish_ratio >= 0.67:  # 67%+ barras bajistas (4+ de 6)
                self.logger.debug(
                    f"⚠️ {symbol}: Weak PA detected - {bearish_count}/{len(recent_bars)} bearish bars "
                    f"({bearish_ratio*100:.0f}%)"
                )
                return True

            # SEÑAL 2: Lower highs (máximos decrecientes = rejection pattern)
            if len(recent_bars) >= 4:
                highs = [bar.high for bar in recent_bars]
                # Verificar si los últimos 3 máximos son decrecientes
                if len(highs) >= 3 and highs[-1] < highs[-2] < highs[-3]:
                    self.logger.debug(f"⚠️ {symbol}: Weak PA detected - Lower highs pattern")
                    return True

            # SEÑAL 3: Caída significativa desde máximo reciente
            # Mirar últimas 20 barras (100 min) para capturar resistencias/techos
            lookback_for_high = min(20, len(bars))
            recent_high = max(bar.high for bar in bars[-lookback_for_high:])
            decline_from_high = ((recent_high - current_price) / recent_high) * 100

            if decline_from_high > 4.0:  # Más de 4% por debajo del máximo reciente
                self.logger.debug(
                    f"⚠️ {symbol}: Weak PA detected - Price {decline_from_high:.1f}% below "
                    f"recent high ${recent_high:.2f} (potential resistance/top)"
                )
                return True

            # SEÑAL 4: Volumen en barras bajistas > alcistas (institutional distribution)
            bearish_vol = sum(bar.volume for bar in recent_bars if bar.close < bar.open)
            bullish_vol = sum(bar.volume for bar in recent_bars if bar.close >= bar.open)

            if bullish_vol > 0 and bearish_vol > bullish_vol * 1.5:  # 50% más volumen en bajistas
                self.logger.debug(
                    f"⚠️ {symbol}: Weak PA detected - Distribution volume pattern "
                    f"(bearish vol {bearish_vol/bullish_vol:.1f}x > bullish vol)"
                )
                return True

            # No se detectó debilidad
            return False

        except Exception as e:
            self.logger.error(f"Error checking price action weakness: {e}")
            # En caso de error, ser conservador y asumir debilidad
            return True

    async def _check_resistance_proximity(
        self,
        opportunity: Dict[str, Any],
        min_distance_pct: float = 5.0
    ) -> Tuple[bool, float]:
        """
        Verifica si el precio está muy cerca de resistencia histórica

        FILTRO ANTI-TRAMPA: Evita entrar cuando hay resistencia cercana que podría
        causar rechazo. Usa análisis de Daily Potential que detecta resistencias
        semanales/mensuales, no solo premarket.

        Args:
            opportunity: Opportunity dict with symbol and price data
            min_distance_pct: Distancia mínima segura a resistencia (default: 5%)

        Returns:
            Tuple (is_too_close, distance_to_resistance)
            - is_too_close: True si está muy cerca de resistencia
            - distance_to_resistance: Distancia % a la resistencia

        Example:
            >>> is_risky, distance = await self._check_resistance_proximity(opportunity)
            >>> if is_risky:
            >>>     self.logger.info(f"{symbol}: Too close to resistance ({distance:.1f}%) - REJECTING")
            >>>     return False
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Usar análisis de Daily Potential (detecta resistencias históricas)
            # Este método ya existe en BaseWorkerLogic y analiza weekly/monthly resistance
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)

            if not daily_potential:
                # Si no hay datos, asumir que es seguro (no rechazar por falta de datos)
                return False, 100.0

            distance_to_resistance = daily_potential.get('distance_to_resistance', 100.0)

            # Si está muy cerca de resistencia, es arriesgado
            is_too_close = distance_to_resistance < min_distance_pct

            if is_too_close:
                self.logger.debug(
                    f"⚠️ {symbol}: Close to resistance - {distance_to_resistance:.1f}% away "
                    f"(min safe distance: {min_distance_pct:.1f}%)"
                )

            return is_too_close, distance_to_resistance

        except Exception as e:
            self.logger.error(f"Error checking resistance proximity: {e}")
            # En caso de error, ser conservador y asumir que NO está cerca de resistencia
            # (no rechazar la entrada por error técnico)
            return False, 100.0

    async def _check_swing_transition(self):
        """
        Check if any positions should transition to swing (overnight hold)

        TIMING: Ejecuta UNA VEZ al día a las 15:30 ET
        DECISION: Evalúa cada posición INTRADAY/SCALP para posible swing transition

        Flujo:
        1. Verificar timing (15:30-15:35 ET window)
        2. Para cada posición INTRADAY/SCALP:
           - Evaluar con SwingTransitionAnalyzer (scoring 80/100 min)
           - Si aprueba: Actualizar trading_horizon, EOD_safe=True, reducir 40%
           - Si rechaza: Mantener EOD_safe=False (cierra a las 15:50)

        Safety Limits:
        - Max 3 swing transitions por día
        - Requiere catalyst confirmado
        - Reduce posición 40% antes de overnight
        """
        if not self._swing_transition_enabled:
            return  # Feature disabled

        if not self.active_positions:
            return  # No positions to evaluate

        try:
            from datetime import datetime, time
            from zoneinfo import ZoneInfo

            # Get current ET time
            current_time_et = datetime.now(ZoneInfo('US/Eastern'))
            current_time_obj = current_time_et.time()

            # Only execute between 15:30 - 15:35 ET (5-minute window)
            if current_time_obj < time(15, 30) or current_time_obj > time(15, 35):
                return

            # Only execute ONCE per day
            if self._swing_transition_done_today:
                return

            self._swing_transition_done_today = True

            self.logger.info("=" * 80)
            self.logger.info("🌙 SWING TRANSITION ANALYSIS - 15:30 ET")
            self.logger.info("=" * 80)

            # Evaluate each position
            transitions_approved = 0
            transitions_rejected = 0

            for symbol, pos_data in list(self.active_positions.items()):
                try:
                    # Only evaluate INTRADAY/SCALP positions (already SWING -> skip)
                    trading_horizon = pos_data.get('trading_horizon', 'SCALP')

                    if trading_horizon in ['SWING', 'SWING_SHORT']:
                        self.logger.debug(
                            f"⏭️ {symbol}: Already SWING - skipping transition analysis"
                        )
                        continue

                    # Get current price
                    current_price = await self._get_current_price(symbol)
                    if current_price <= 0:
                        self.logger.warning(f"⚠️ {symbol}: Invalid price - skipping")
                        continue

                    # Fetch bars for analysis
                    bars_1min = await self._fetch_bars_for_swing_analysis(symbol, '1 min')
                    bars_daily = await self._fetch_bars_for_swing_analysis(symbol, '1 day')

                    # Evaluate transition
                    can_swing, reason, analysis = await self.swing_analyzer.can_transition_to_swing(
                        symbol=symbol,
                        position_data=pos_data,
                        current_price=current_price,
                        bars_1min=bars_1min,
                        bars_daily=bars_daily
                    )

                    if can_swing:
                        # ✅ APPROVED FOR SWING
                        self.logger.warning(
                            f"🌙 {symbol}: SWING TRANSITION APPROVED | {reason}"
                        )

                        # Log detailed analysis
                        for reason_detail in analysis.get('reasons', []):
                            self.logger.info(f"   ✅ {reason_detail}")

                        for warning in analysis.get('warnings', []):
                            self.logger.warning(f"   ⚠️ {warning}")

                        # UPDATE position metadata
                        pos_data['trading_horizon'] = 'SWING_SHORT'
                        pos_data['EOD_safe'] = True
                        pos_data['swing_transition_time'] = current_time_et
                        pos_data['swing_transition_analysis'] = analysis

                        # REDUCE position by 40% (take partial profit)
                        await self._reduce_position_for_swing(symbol, current_price)

                        transitions_approved += 1

                    else:
                        # ❌ REJECTED - will close at 15:50
                        self.logger.info(
                            f"📅 {symbol}: WILL CLOSE AT EOD | {reason}"
                        )

                        # Log rejection reasons
                        for warning in analysis.get('warnings', []):
                            self.logger.debug(f"   ⚠️ {warning}")

                        transitions_rejected += 1

                except Exception as e:
                    self.logger.error(f"Error evaluating {symbol} for swing transition: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

            # Summary
            total_evaluated = transitions_approved + transitions_rejected
            self.logger.info("=" * 80)
            self.logger.info(
                f"🌙 SWING TRANSITION SUMMARY: "
                f"{transitions_approved} approved, {transitions_rejected} rejected "
                f"(total: {total_evaluated})"
            )
            self.logger.info("=" * 80)

            # Log swing analyzer stats
            stats = self.swing_analyzer.get_transition_stats()
            self.logger.info(
                f"📊 Today's transitions: {stats['transitions_today']}/{stats['max_allowed']} max | "
                f"Symbols: {stats['symbols']}"
            )

        except Exception as e:
            self.logger.error(f"Error in swing transition check: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def _fetch_bars_for_swing_analysis(
        self,
        symbol: str,
        bar_size: str
    ) -> Optional[List]:
        """
        Fetch bars for swing transition analysis

        Args:
            symbol: Symbol to fetch
            bar_size: '1 min' or '1 day'

        Returns:
            List of bars or None
        """
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')

            # Duration based on bar size
            if bar_size == '1 min':
                duration = '1 D'  # 1 day of 1-min bars
            elif bar_size == '1 day':
                duration = '60 D'  # 60 days of daily bars
            else:
                duration = '1 D'

            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True
            )

            return bars if bars else []

        except Exception as e:
            self.logger.warning(f"⚠️ {symbol}: Could not fetch {bar_size} bars: {e}")
            return []

    async def _reduce_position_for_swing(self, symbol: str, current_price: float):
        """
        Reduce position by configured percentage before overnight hold

        This locks in profit and reduces overnight risk.

        Args:
            symbol: Symbol to reduce
            current_price: Current market price
        """
        try:
            pos_data = self.active_positions.get(symbol)
            if not pos_data:
                return

            reduction_pct = self.swing_analyzer.position_reduction_pct  # Default 0.40 (40%)

            position = pos_data.get('position', {})
            current_quantity = position.get('quantity', 0)

            if current_quantity <= 0:
                self.logger.warning(f"⚠️ {symbol}: Cannot reduce - invalid quantity")
                return

            # Calculate shares to sell (40% of position)
            shares_to_sell = int(current_quantity * reduction_pct)

            if shares_to_sell < 1:
                self.logger.info(
                    f"📉 {symbol}: Position too small to reduce ({current_quantity} shares)"
                )
                return

            # Calculate PnL on reduction
            entry_price = position.get('entry_price', 0)
            pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            self.logger.warning(
                f"📉 {symbol}: REDUCING POSITION for swing | "
                f"Selling {shares_to_sell}/{current_quantity} shares ({reduction_pct*100:.0f}%) @ ${current_price:.2f} | "
                f"PnL: +{pnl_pct:.1f}%"
            )

            # Execute partial exit via execution engine
            await self.execution_engine.exit_position(
                symbol=symbol,
                strategy=self.worker_name,
                exit_reason=f"swing_transition_reduction_{reduction_pct*100:.0f}pct",
                quantity=shares_to_sell,  # Partial exit
                exit_type='SWING_TRANSITION_REDUCTION'
            )

            # Update position data
            new_quantity = current_quantity - shares_to_sell
            position['quantity'] = new_quantity
            pos_data['position'] = position

            self.logger.info(
                f"✅ {symbol}: Position reduced | Remaining: {new_quantity} shares for overnight hold"
            )

        except Exception as e:
            self.logger.error(f"❌ Error reducing position for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())