"""
Base Worker Logic - Clase abstracta para workers lógicos
Proporciona funcionalidad común de ejecución y monitoreo
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
from datetime import datetime


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
    ):
        """
        Inicializa worker lógico

        Args:
            worker_name: Identificador único del worker (ej: 'gap_go', 'daily_plays')
            execution_engine: ExecutionEngine compartido para ejecutar trades
            risk_manager: RiskManager compartido para validaciones
        """
        self.worker_name = worker_name
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager

        # Posiciones activas gestionadas por este worker
        # {symbol: {position, entry_time, opportunity_data}}
        self.active_positions: Dict[str, Dict[str, Any]] = {}

        # Setup worker-specific logging
        from utils.log_config import setup_worker_logging
        self.logger = setup_worker_logging(worker_name, level="INFO")

        # Estado
        self.is_running = False

        self.logger.info(f"🔧 Worker {worker_name} initialized with separate logging")

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

                # Check cada segundo
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info(f"🛑 Worker {self.worker_name} cancelled")
            raise
        except Exception as e:
            self.logger.error(f"❌ Worker {self.worker_name} crashed: {e}")
        finally:
            self.is_running = False

    async def process_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """
        Procesa una oportunidad del scanner

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

            # Check 2: Risk manager permite?
            if not await self._check_risk_approval(symbol):
                self.logger.debug(f"🚫 {symbol}: Risk manager denied")
                return False

            # Check 3: Estrategia específica aprueba entrada?
            if await self.should_enter(opportunity):
                self.logger.info(f"✅ {symbol}: Entry criteria met for {self.worker_name}")
                return await self._execute_entry(opportunity)
            else:
                self.logger.info(f"⚪ {symbol}: Entry criteria not met (rejected by strategy)")
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

            # Ejecutar entrada usando ExecutionEngine compartido
            position = await self.execution_engine.enter_position(
                symbol=symbol,
                strategy=self.worker_name,
                opportunity_data=opportunity
            )

            if position:
                # Guardar posición en tracking del worker
                self.active_positions[symbol] = {
                    'position': position,
                    'entry_time': datetime.now(),
                    'entry_price': position.get('entry_price', 0),
                    'quantity': position.get('quantity', 0),
                    'opportunity_data': opportunity
                }

                self.logger.info(
                    f"✅ {self.worker_name}: Position opened - "
                    f"{symbol} @ ${position.get('entry_price', 0):.2f} "
                    f"x {position.get('quantity', 0)} shares"
                )
                return True
            else:
                self.logger.warning(f"⚠️ {symbol}: Entry returned no position")
                return False

        except Exception as e:
            self.logger.error(f"❌ {self.worker_name}: Entry failed for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def _monitor_positions(self):
        """
        Monitorea todas las posiciones activas del worker
        Evalúa salidas y ejecuta si es necesario
        """
        if not self.active_positions:
            return

        # Iterar sobre copia para poder modificar dict durante iteración
        for symbol, data in list(self.active_positions.items()):
            try:
                # Obtener precio actual
                current_price = await self._get_current_price(symbol)

                if current_price <= 0:
                    self.logger.warning(f"⚠️ {symbol}: Invalid price {current_price}")
                    continue

                # Evaluar salida con estrategia específica
                should_exit, reason = await self.should_exit(
                    symbol=symbol,
                    position=data['position'],
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
        Obtiene precio actual del símbolo

        Returns:
            Precio actual, 0 si error
        """
        try:
            # Usar ExecutionEngine para obtener precio
            price = await self.execution_engine.get_current_price(symbol)
            return price if price else 0.0
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
        bars = opportunity.get('bars_history', [])
        if bars and len(bars) > 0:
            return bars
        return []