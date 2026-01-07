"""
Small Cap VWAP Runner - Worker Logic

Entry: Quality + VWAP + Green bar
Stop: Initial Risk or Trailing Stop
Exit: Hard Stop, VWAP Break, or Trailing Stop

100% reproducible en replay
"""

from typing import Dict, Any, Tuple
from strategies.workers.base_worker_logic import BaseWorkerLogic

class SmallcapVwapRunnerWorker(BaseWorkerLogic):
    """
    Worker minimalista para small caps con gestión de salida mejorada (Trailing Stop).
    """

    def __init__(self, execution_engine, **kwargs):
        super().__init__("smallcap_vwap_runner", execution_engine, **kwargs)

        # Cargar configuración centralizada
        self.min_quality = self.config.getfloat('SMALLCAP_VWAP_RUNNER', 'min_quality', fallback=65.0)
        # Stop loss fijo de 5% (como buy_and_hold) en lugar de 2% dinámico
        self.stop_loss_pct = self.config.getfloat('SMALLCAP_VWAP_RUNNER', 'stop_loss_pct', fallback=0.05)
        self.vwap_buffer = self.config.getfloat('SMALLCAP_VWAP_RUNNER', 'vwap_buffer_pct', fallback=0.01)
        self.trailing_stop_pct = self.config.getfloat('SMALLCAP_VWAP_RUNNER', 'trailing_stop_pct', fallback=0.03)
        self.risk_per_trade = self.config.getfloat('SMALLCAP_VWAP_RUNNER', 'risk_per_trade', fallback=0.01)

        # === STOP MANAGER INITIALIZATION ===
        from .worker_stop_manager import create_worker_stop_manager, WorkerStopManager, WorkerStopConfig
        if self.config:
            self.stop_manager = create_worker_stop_manager(self.config, 'SMALLCAP_VWAP_RUNNER')
        else:
            # Default stop manager configuration
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,           # 5% stop loss
                take_profit_pct=15.0,        # 15% profit target
                quick_target_pct=0.0,        # No quick target
                trailing_activation=8.0,     # Trailing at 8% profit
                trailing_distance=3.0,       # 3% trailing distance
                max_position_hours=24.0      # 1 day max
            ))

        self.logger.info(f"🚀 Initialized SmallcapVwapRunner: Q>={self.min_quality}, Stop={self.stop_loss_pct:.1%}, Trail={self.trailing_stop_pct:.1%}")

    def _get_current_time_decimal(self, current_bar: Dict[str, Any]) -> float:
        """Helper to get current time in decimal hours from bar or now"""
        # Try to get timestamp from bar if available (replay compatible)
        if 'timestamp' in current_bar:
             ts = current_bar['timestamp']
             # Assuming ts is datetime object or equivalent
             import datetime
             if isinstance(ts, datetime.datetime):
                 return ts.hour + ts.minute / 60.0
        
        # Fallback to system time (live)
        from datetime import datetime
        now = datetime.now()
        return now.hour + now.minute / 60.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> Tuple[bool, float, str]:
        """Entry: 3 checks simples (Quality, VWAP, Green bar)"""

        symbol = opportunity.get('symbol', 'UNKNOWN')

        # 1. Quality (de scanner_signals DB)
        quality = opportunity.get('quality_score', 0)
        if quality < self.min_quality:
            return False, 0.0, f"Quality {quality:.1f} < {self.min_quality}"

        # 2. VWAP (calculable de OHLCV)
        current_price = opportunity.get('current_price', 0)
        vwap = opportunity.get('vwap', 0)

        if vwap == 0:
            return False, 0.0, "No VWAP data"

        if current_price <= vwap:
            return False, 0.0, f"Below VWAP ({current_price:.2f} <= {vwap:.2f})"

        # 3. Green bar (OHLCV)
        # La oportunidad suele traer 'open' y 'close' del último timeframe
        bar_open = opportunity.get('open', 0)
        bar_close = opportunity.get('close', current_price)
        
        # Si no están en opportunity top-level, buscar en 'bar' object si existe
        if bar_open == 0 and 'bar' in opportunity:
             bar = opportunity['bar']
             bar_open = bar.get('open', 0)
             bar_close = bar.get('close', 0)

        if bar_close <= bar_open:
            return False, 0.0, "Red bar"

        # Pattern completion = quality directamente
        pattern_completion = float(quality)

        return True, pattern_completion, f"Q={quality:.0f}, Price={current_price:.2f}, VWAP={vwap:.2f}"

    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        opportunity: Dict[str, Any]
    ) -> int:
        """
        Position size usando configuración centralizada
        """
        vwap = opportunity.get('vwap', entry_price)
        initial_stop = self._calculate_initial_stop(entry_price, vwap)

        # Riesgo por acción
        risk_per_share = entry_price - initial_stop

        if risk_per_share <= 0:
            self.logger.warning(f"⚠️ {symbol}: Invalid risk per share (Stop >= Entry). Defaulting to min size.")
            return 10

        # Capital total (mockeado o del sistema)
        # Idealmente: self.execution_engine.get_account_balance()
        # Por simplicidad y robustez usamos base 100k si no hay info, o un valor conservador
        account_size = 100_000 # Valor base para cálculo consistente
        
        risk_amount = account_size * self.risk_per_trade

        shares = int(risk_amount / risk_per_share)
        
        # Límites hardcodeados de seguridad por si acaso
        shares = max(10, min(shares, 5000))

        return shares

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_bar: Any = None,
        current_price: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Exit logic mejorada: Hard Stop, Trailing Stop, VWAP Break, y EOD
        """
        # Helper to get attributes safe
        def get_val(obj, key, default=0):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        # Determine Price
        if current_bar:
            current_price = get_val(current_bar, 'close', current_price)
        
        if current_price == 0:
             return False, "No Price Data"

        # 0. EOD Check (Safety Exit before market close)
        # 15.9 = 15:54 ET. Force exit to avoid overnight hold.
        # Need current_time. If current_bar is None, we can't check time accurately unless passed 
        # or we use system time (which fails in replay). 
        # But we will rely on valid current_bar being passed or fallback to skip.
        if current_bar:
             current_time = self._get_current_time_decimal(current_bar.__dict__ if hasattr(current_bar, '__dict__') else current_bar)
             if current_time >= 15.9:
                 return True, "EOD Exit (15:54 ET)"
        
        
        # Recuperar estado de la posición (High Water Mark)
        # active_positions se gestiona en BaseWorkerLogic, pero aquí recibimos 'position' 
        # que suele ser el dict interno. Necesitamos acceder al estado persistente del worker.
        
        worker_pos_data = self.active_positions.get(symbol, {})

        # 1. Recuperar o inicializar Stop Price actual
        # CRITICAL: Try to restore from opportunity_data first (persisted state)
        if 'dynamic_stop_price' not in worker_pos_data:
            # Try to restore from database
            opp_data = worker_pos_data.get('opportunity_data', {})
            restored_stop = opp_data.get('vwap_dynamic_stop_price')
            restored_hwm = opp_data.get('vwap_high_water_mark')

            if restored_stop and restored_stop > 0:
                # Successfully restored from database
                worker_pos_data['dynamic_stop_price'] = restored_stop
                if restored_hwm and restored_hwm > 0:
                    worker_pos_data['high_water_mark'] = restored_hwm

                self.logger.info(
                    f"🔄 {symbol}: Restored VWAP trailing state from DB "
                    f"(Stop: ${restored_stop:.2f}, HWM: ${restored_hwm:.2f})"
                )
            else:
                # Fallback: Calculate initial stop (new position or old trade without persisted state)
                entry_price = worker_pos_data.get('entry_price', getattr(worker_pos_data.get('position'), 'entry_price', current_price))
                vwap_entry = get_val(current_bar, 'vwap', entry_price) if current_bar else entry_price

                worker_pos_data['dynamic_stop_price'] = self._calculate_initial_stop(entry_price, vwap_entry)

                self.logger.debug(
                    f"🆕 {symbol}: Initialized new stop at ${worker_pos_data['dynamic_stop_price']:.2f}"
                )

        current_stop = worker_pos_data['dynamic_stop_price']

        # 2. Chequear Take Profit (NUEVO - antes faltaba)
        # Recuperar el take profit desde la posición
        take_profit_price = position.get('take_profit_price', 0)
        if take_profit_price > 0 and current_price >= take_profit_price:
            return True, f"Take Profit hit: {current_price:.2f} >= {take_profit_price:.2f}"

        # 3. Chequear Hard Stop / Trailing Stop Hit
        if current_price <= current_stop:
            return True, f"Stop hit: {current_price:.2f} <= {current_stop:.2f}"

        # 4. VWAP Break (DISABLED - causaba salidas prematuras)
        # Ya no usamos VWAP break como exit, solo el stop loss fijo
        # vwap = get_val(current_bar, 'vwap', 0) if current_bar else 0
        # if vwap > 0 and current_price < vwap:
        #     return True, f"VWAP break: {current_price:.2f} < {vwap:.2f}"

        vwap = get_val(current_bar, 'vwap', 0) if current_bar else 0
        return False, f"Hold (Price={current_price:.2f}, Stop={current_stop:.2f}, TP={take_profit_price:.2f}, VWAP={vwap:.2f})"

    async def update_position(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_bar: Any
    ):
        """
        Actualizar trailing stop basado en High Water Mark
        """
        def get_val(obj, key, default=0):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        current_price = get_val(current_bar, 'close', 0)
        worker_pos_data = self.active_positions.get(symbol)
        
        if not worker_pos_data:
            return

        # Inicializar High Water Mark si no existe
        if 'high_water_mark' not in worker_pos_data:
             worker_pos_data['high_water_mark'] = current_price
        
        # Actualizar High Water Mark
        hwm_changed = False
        stop_changed = False

        if current_price > worker_pos_data['high_water_mark']:
            worker_pos_data['high_water_mark'] = current_price
            hwm_changed = True

        # Calcular nuevo stop potencial basado en el nuevo High
        # Trailing Stop = High * (1 - trailing_pct)
        new_potential_stop = worker_pos_data['high_water_mark'] * (1 - self.trailing_stop_pct)

        # Recuperar stop actual
        current_stop = worker_pos_data.get('dynamic_stop_price', 0)

        # Solo subir el stop (nunca bajarlo)
        if new_potential_stop > current_stop:
            worker_pos_data['dynamic_stop_price'] = new_potential_stop
            stop_changed = True
            # Loguear solo cambios significativos para no saturar
            if new_potential_stop > current_stop * 1.005:
                self.logger.debug(f"↗️ {symbol}: Trailing Stop raised to {new_potential_stop:.2f} (High: {worker_pos_data['high_water_mark']:.2f})")

        # CRITICAL: Persist trailing state if changed
        if hwm_changed or stop_changed:
            await self._persist_vwap_trailing_state(symbol, worker_pos_data)

    async def _persist_vwap_trailing_state(self, symbol: str, worker_pos_data: Dict[str, Any]):
        """
        Persiste el estado del trailing stop VWAP al opportunity_data

        CRITICAL: Previene pérdida de dynamic_stop_price y high_water_mark en restart
        """
        try:
            # Get current state
            high_water_mark = worker_pos_data.get('high_water_mark', 0.0)
            dynamic_stop_price = worker_pos_data.get('dynamic_stop_price', 0.0)

            # Update opportunity_data in memory
            if 'opportunity_data' not in worker_pos_data:
                worker_pos_data['opportunity_data'] = {}

            worker_pos_data['opportunity_data']['vwap_high_water_mark'] = high_water_mark
            worker_pos_data['opportunity_data']['vwap_dynamic_stop_price'] = dynamic_stop_price

            # Persist to database via ExecutionEngine
            await self.execution_engine.update_position_metadata(
                symbol=symbol,
                strategy=self.worker_name,
                opportunity_data=worker_pos_data['opportunity_data']
            )

            self.logger.debug(
                f"💾 {symbol}: Persisted VWAP trailing state "
                f"(HWM: ${high_water_mark:.2f}, Stop: ${dynamic_stop_price:.2f})"
            )

        except Exception as e:
            self.logger.error(f"❌ Error persisting VWAP trailing state for {symbol}: {e}")

    def _calculate_initial_stop(self, entry_price: float, vwap: float) -> float:
        """
        Cálculo del stop inicial: Stop fijo basado en % (simplificado como buy_and_hold)
        Ya no usamos VWAP para calcular el stop, solo un % fijo desde entry
        """
        # Stop simple: Entry - Stop% (como buy_and_hold)
        # Ejemplo: Entry $3.42, Stop 5% -> $3.25
        stop_price = entry_price * (1 - self.stop_loss_pct)

        return round(stop_price, 2)
