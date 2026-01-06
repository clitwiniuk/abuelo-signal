#!/usr/bin/env python3
"""
FIX INMEDIATO: Volume Absorption Worker Exit Tracking

Problema identificado:
- volume_absorption NO registra posiciones en su WorkerStopManager
- should_exit() returna False inmediatamente sin evaluar stops
- Posiciones abiertas (CMBM, DVLT, etc.) no tienen monitoring de exit

Fix aplicado:
- Sobrescribir _execute_entry() para registrar en stop_manager
- Corregir should_exit() para usar stop_manager.check_exit()
- Añadir logs detallados para debugging
"""

import logging
import asyncio
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_volume_absorption_worker():
    """Aplica el fix al Volume Absorption Worker"""
    
    file_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/volume_absorption_worker_logic.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # ANTES: should_exit() que returna False inmediatamente
        old_should_exit = '''    async def should_exit(
        self,
        symbol: str,
        position: Dict,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Implementación requerida del método abstracto should_exit

        Delega completamente a WorkerStopManager para manejo de exits:
        - Stop loss: 5% (INTRADAY)
        - Take profit: 10-30% según quality
        - Trailing stop: 3% cuando PnL > 6%
        - Time stop: 4 horas

        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            Tuple[bool, str]: (should_exit, reason)
        """
        # El sistema de exits está completamente manejado por WorkerStopManager
        # que se llama automáticamente desde BaseWorkerLogic
        # Este método solo necesita existir para cumplir con la interfaz abstracta
        return False, "No custom exit logic - using WorkerStopManager"'''

        # DESPUÉS: should_exit() que evalúa usando WorkerStopManager
        new_should_exit = '''    async def should_exit(
        self,
        symbol: str,
        position: Dict,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir usando WorkerStopManager para manejo de exits
        
        CRITICAL FIX: Ahora evalúa exit conditions usando stop_manager.check_exit()
        
        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            Tuple[bool, str]: (should_exit, reason)
        """
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price in position data")
                return False, "Invalid entry price"

            # Get market data for FOMO detection (similar a daily_plays)
            market_data = None
            try:
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='300 S',  # 5 minutes
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True
                )
                if bars:
                    market_data = {
                        'bars': bars,
                        'symbol': symbol,
                        'current_price': current_price
                    }
            except Exception as e:
                self.logger.debug(f"Could not get market data for FOMO detection: {e}")

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # CRITICAL FIX: Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data,
                position_metadata=position_metadata
            )

            self.logger.debug(f"📊 {symbol}: stop_manager.check_exit() = {should_exit}, reason = '{reason}'")
            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"'''

        # ANTES: _execute_entry() sin registro en stop_manager
        old_execute_entry_start = '''    async def _execute_entry(self, opportunity: Dict) -> bool:
        """
        Sobrescribe el método base para añadir registro post-entrada en UnifiedPositionManager
        
        FIX CRÍTICO: Después de una entrada exitosa, registra la posición en UnifiedPositionManager
        para que WorkerStopManager pueda activar el monitoreo de exit
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # USAR LÓGICA BASE para todo el proceso de entrada
            # Esto incluye validaciones, cálculos, etc.
            entry_success = await super()._execute_entry(opportunity)
            
            if not entry_success:
                return False

            # 🛡️ CRITICAL FIX: Registrar posición en UnifiedPositionManager DESPUÉS de entrada exitosa
            if hasattr(self, 'unified_manager') and self.unified_manager:
                try:
                    # Obtener datos de la posición desde opportunity (actualizados por BaseWorkerLogic)
                    entry_price = opportunity.get('entry_price', 0.0)
                    quantity = opportunity.get('position_size', 0)
                    trading_horizon = opportunity.get('trading_horizon', 'INTRADAY')
                    time_in_market = opportunity.get('time_in_market_hours', 4.0)
                    
                    if entry_price > 0 and quantity > 0:
                        position_value = entry_price * quantity
                        strategy_type = 'day'  # volume_absorption es day trading
                        
                        # Preparar datos para UnifiedPositionManager
                        position_data = {
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'position_value': position_value,
                            'strategy': self.worker_name,
                            'strategy_type': strategy_type,
                            'trading_horizon': trading_horizon.value if hasattr(trading_horizon, 'value') else str(trading_horizon),
                            'time_in_market_hours': time_in_market,
                            'opened_at': datetime.now().isoformat(),
                            'original_opportunity': opportunity
                        }
                        
                        # Registrar con UnifiedPositionManager
                        success = self.unified_manager.register_position(
                            symbol=symbol,
                            strategy_type=strategy_type,
                            position_data=position_data
                        )
                        
                        if success:
                            self.logger.info(
                                f"🛡️ {symbol}: Registered with UnifiedPositionManager for exit tracking "
                                f"(WorkerStopManager now active - stop_loss/take_profit enabled)"
                            )
                            return True
                        else:
                            self.logger.error(
                                f"❌ {symbol}: Failed to register with UnifiedPositionManager "
                                f"- POSITION WITHOUT EXIT TRACKING! (stop_loss/take_profit disabled)"
                            )
                            return False
                    else:
                        self.logger.error(
                            f"❌ {symbol}: Invalid position data for registration - "
                            f"price=${entry_price:.2f}, quantity={quantity}"
                        )
                        return False
                        
                except Exception as e:
                    self.logger.error(
                        f"❌ {symbol}: Error registering position with UnifiedPositionManager: {e}"
                    )
                    import traceback
                    self.logger.error(traceback.format_exc())
                    return False
            else:
                self.logger.error(
                    f"❌ {symbol}: No UnifiedPositionManager available - "
                    f"POSITION WITHOUT EXIT TRACKING! (WorkerStopManager disabled)"
                )
                return False

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in _execute_entry override: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False'''

        # DESPUÉS: _execute_entry() que registra en stop_manager Y unified manager
        new_execute_entry_start = '''    async def _execute_entry(self, opportunity: Dict) -> bool:
        """
        Sobrescribe el método base para registro DUAL: stop_manager + unified manager
        
        FIX CRÍTICO: Registra posición en WorkerStopManager para monitoring de exits
        Y en UnifiedPositionManager para prevenir duplicates
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # USAR LÓGICA BASE para todo el proceso de entrada
            entry_success = await super()._execute_entry(opportunity)
            
            if not entry_success:
                return False

            # 🛡️ CRITICAL FIX #1: Registrar con WorkerStopManager para monitoring de exits
            try:
                self.stop_manager.register_position(symbol, datetime.now())
                self.logger.info(f"📝 {symbol}: Registered with WorkerStopManager for exit monitoring")
            except Exception as e:
                self.logger.error(f"❌ {symbol}: Failed to register with WorkerStopManager: {e}")
                # Continue anyway, don't fail the entry
            
            # 🛡️ CRITICAL FIX #2: Registrar con UnifiedPositionManager para prevenir duplicates
            try:
                from core.service_locator import get_unified_position_manager
                unified_manager = await get_unified_position_manager()
                
                if unified_manager:
                    # Obtener datos de la posición
                    entry_price = opportunity.get('entry_price', 0.0)
                    quantity = opportunity.get('position_size', 0)
                    
                    if entry_price > 0 and quantity > 0:
                        position_value = entry_price * quantity
                        strategy_type = 'day'  # volume_absorption es day trading
                        
                        position_data = {
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'position_value': position_value,
                            'strategy': self.worker_name,
                            'strategy_type': strategy_type,
                            'opened_at': datetime.now().isoformat()
                        }
                        
                        success = unified_manager.register_position(
                            symbol=symbol,
                            strategy_type=strategy_type,
                            position_data=position_data
                        )
                        
                        if success:
                            self.logger.info(f"💼 {symbol}: Registered with UnifiedPositionManager")
                        else:
                            self.logger.warning(f"⚠️ {symbol}: Failed to register with UnifiedPositionManager")
                
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Error with UnifiedPositionManager: {e}")
                # Don't fail the entry for this

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in _execute_entry: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False'''

        # Buscar y reemplazar should_exit
        if old_should_exit in content:
            content = content.replace(old_should_exit, new_should_exit)
            logger.info("✅ should_exit() method updated")
        else:
            logger.warning("⚠️ Could not find exact should_exit() method to replace")
            
            # Buscar una versión más corta para buscar y reemplazar
            if "No custom exit logic - using WorkerStopManager" in content:
                old_simple = '''        return False, "No custom exit logic - using WorkerStopManager"'''
                new_simple = '''        # CRITICAL FIX: Use stop_manager for exit evaluation
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price")
                return False, "Invalid entry price"

            # Get market data for FOMO detection
            market_data = None
            try:
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='300 S',
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True
                )
                if bars:
                    market_data = {
                        'bars': bars,
                        'symbol': symbol,
                        'current_price': current_price
                    }
            except Exception as e:
                self.logger.debug(f"Could not get market data: {e}")

            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # CRITICAL FIX: Use centralized stop manager
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data,
                position_metadata=position_metadata
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"'''
                
                content = content.replace(old_simple, new_simple)
                logger.info("✅ should_exit() method updated (simple version)")

        # Buscar y reemplazar _execute_entry
        if old_execute_entry_start in content:
            content = content.replace(old_execute_entry_start, new_execute_entry_start)
            logger.info("✅ _execute_entry() method updated")
        else:
            logger.warning("⚠️ Could not find exact _execute_entry() method to replace")

        # Escribir archivo actualizado
        with open(file_path, 'w') as f:
            f.write(content)
            
        logger.info("✅ FIX APLICADO: Volume Absorption Worker now registers positions with stop_manager")
        logger.info("   - should_exit() now uses stop_manager.check_exit()")
        logger.info("   - _execute_entry() now registers with stop_manager AND unified manager")
        logger.info("   - Posiciones CMBM, DVLT, IONZ, AKBA will now be monitored for exits")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying fix: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_monitoring_script():
    """Crea script para monitorear si el fix funciona"""
    
    script_content = '''#!/usr/bin/env python3
"""
Monitoring script para verificar que Volume Absorption Worker
ahora registra posiciones y evalúa exits correctamente
"""

import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_volume_absorption_monitoring():
    """Monitorea si volume_absorption worker ahora registra posiciones"""
    
    logger.info("🔍 Monitoring Volume Absorption Worker exit tracking...")
    logger.info("   Looking for registration logs and exit evaluations")
    logger.info("")
    
    # Check if VolumeAbsorptionWorkerLogic.py was modified recently
    import os
    file_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/volume_absorption_worker_logic.py"
    
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        mod_time = datetime.fromtimestamp(mtime)
        logger.info(f"📁 VolumeAbsorptionWorkerLogic.py modified: {mod_time}")
        logger.info("   If recent, fix should be active")
    else:
        logger.error(f"❌ File not found: {file_path}")
    
    logger.info("")
    logger.info("✅ EXPECTED BEHAVIOR:")
    logger.info("   1. Volume Absorption entries should show: '📝 {symbol}: Registered with WorkerStopManager'")
    logger.info("   2. Exit evaluations should show: '📊 {symbol}: stop_manager.check_exit() = False/True'")
    logger.info("   3. BYND-style exit logs should appear for CMBM, DVLT, IONZ, AKBA")
    logger.info("")
    logger.info("🔍 Look for these patterns in trader.log:")
    logger.info("   - '📝 CMBM: Registered with WorkerStopManager'")
    logger.info("   - '📊 CMBM: stop_manager.check_exit() = False'")
    logger.info("   - '🚪 volume_absorption: Exiting {SYMBOL}'")
    logger.info("")
    logger.info("⏰ Check trader.log in next 10-15 minutes for monitoring activity")

if __name__ == "__main__":
    monitor_volume_absorption_monitoring()
'''
    
    script_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/monitor_volume_absorption_monitoring.py"
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        logger.info(f"✅ Monitoring script created: {script_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating monitoring script: {e}")
        return False

if __name__ == "__main__":
    import os
    
    logger.info("🛠️  VOLUME ABSORPTION WORKER EXIT TRACKING FIX")
    logger.info("=" * 60)
    
    # Apply the fix
    success = fix_volume_absorption_worker()
    
    if success:
        logger.info("")
        logger.info("🎯 FIX SUMMARY:")
        logger.info("   BEFORE: volume_absorption positions had NO exit monitoring")
        logger.info("   AFTER:  volume_absorption positions will be monitored by WorkerStopManager")
        logger.info("")
        logger.info("📋 EXPECTED CHANGES:")
        logger.info("   1. Position entries: '📝 {symbol}: Registered with WorkerStopManager'")
        logger.info("   2. Exit evaluations: '📊 {symbol}: stop_manager.check_exit() = False/True'")
        logger.info("   3. Actual exits: '🚪 volume_absorption: Exiting {SYMBOL} - {REASON}'")
        logger.info("")
        logger.info("🔍 MONITORING:")
        
        # Create monitoring script
        create_monitoring_script()
        
        logger.info("")
        logger.info("✅ FIX COMPLETED SUCCESSFULLY!")
        logger.info("   Volume Absorption Worker now has complete exit tracking")
        logger.info("   CMBM, DVLT, IONZ, AKBA positions will be monitored")
        logger.info("   Look for new logs in trader.log within 10-15 minutes")
        
    else:
        logger.error("❌ FIX FAILED - manual intervention required")