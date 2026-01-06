"""
Módulo de ejecución de órdenes para sistemas de trading
Proporciona una interfaz simple para enviar órdenes al broker IBKR con seguimiento por estrategia
"""

import logging
import asyncio
import configparser
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any, Set, Union
import os
from enum import Enum
from decimal import Decimal
from pathlib import Path

from ib_insync import IB, Contract, Stock, MarketOrder, LimitOrder, StopOrder, util, Trade

# Configuración de logging temporal para capturar errores de importación
try:
    import logging
    logger = logging.getLogger(__name__)
except:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Configurar el path para importaciones
import sys
from pathlib import Path

# Añadir el directorio actual al path si no está
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Importar configuración y gestor de riesgo con manejo mejorado
try:
    # Primero intentar importar como paquete
    from . import config
    from .risk_manager import RiskManager, RiskParameters
except (ImportError, SystemError) as e:
    try:
        # Si falla, intentar importar directamente
        import config
        from risk_manager import RiskManager, RiskParameters
    except ImportError as ie:
        logger.error(f"Error al importar módulos: {ie}")
        # Intentar una última vez con el path absoluto
        try:
            import importlib.util
            import sys
            
            # Importar config
            config_spec = importlib.util.spec_from_file_location(
                "config", 
                str(Path(__file__).parent / "config" / "__init__.py")
            )
            config = importlib.util.module_from_spec(config_spec)
            sys.modules["config"] = config
            config_spec.loader.exec_module(config)
            
            # Importar risk_manager
            risk_spec = importlib.util.spec_from_file_location(
                "risk_manager", 
                str(Path(__file__).parent / "risk_manager.py")
            )
            risk_manager = importlib.util.module_from_spec(risk_spec)
            sys.modules["risk_manager"] = risk_manager
            risk_spec.loader.exec_module(risk_manager)
            
            from risk_manager import RiskManager, RiskParameters
            
        except Exception as e:
            logger.critical(f"No se pudieron cargar los módulos requeridos: {e}")
            raise ImportError(f"No se pudieron cargar los módulos requeridos: {e}")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('order_executor.log'),
        logging.StreamHandler()
    ]
)
# Configuración básica de logging
logger = logging.getLogger('order_executor')

# Configurar el nivel de logging para ib_insync
ib_insync_logger = logging.getLogger('ib_insync')
ib_insync_logger.setLevel(logging.WARNING)

class OrderStatus(str, Enum):
    """Estados posibles de una orden"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Position:
    """Representa una posición abierta en una estrategia"""
    ticker: str
    strategy_id: str
    quantity: int
    entry_price: float
    current_price: float
    entry_time: datetime
    pnl: float = 0.0
    pnl_pct: float = 0.0
    order_ids: List[str] = field(default_factory=list)  # IDs de órdenes asociadas
    metadata: Dict[str, Any] = field(default_factory=dict)  # Metadatos adicionales
    
    def update_price(self, new_price: float):
        """Actualiza el precio actual y recalcula P&L"""
        self.current_price = new_price
        self.pnl = (new_price - self.entry_price) * self.quantity
        self.pnl_pct = (new_price / self.entry_price - 1) * 100 if self.entry_price != 0 else 0

@dataclass
class OrderRequest:
    """Solicitud de orden para el ejecutor"""
    ticker: str
    action: str  # 'BUY' o 'SELL'
    quantity: int
    strategy_id: str  # Identificador único de la estrategia
    order_type: str = 'MKT'  # 'MKT', 'LMT', 'STP'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: Optional[str] = None  # ID opcional para rastrear la orden
    metadata: Dict[str, Any] = field(default_factory=dict)  # Metadatos adicionales

@dataclass
class OrderResponse:
    """Respuesta de la orden ejecutada"""
    success: bool
    order_id: str
    status: OrderStatus
    message: str
    position_id: Optional[str] = None  # ID de la posición si la orden abrió/cerró una posición
    details: Optional[Dict[str, Any]] = None

class OrderExecutor:
    """
    Clase para ejecutar y rastrear órdenes de trading a través de IBKR con soporte para múltiples estrategias
    """
    
    def __init__(
        self,
        config_path: Union[str, Path, None] = None,
        ib: Optional[IB] = None,
        risk_manager: Optional[RiskManager] = None,
        **kwargs
    ):
        """
        Inicializa el OrderExecutor.

        Args:
            config_path: Ruta al archivo de configuración YAML.
            ib: Instancia opcional de IB (para testing o inyección de dependencias).
            risk_manager: Instancia opcional de RiskManager.
            **kwargs: Configuración adicional que sobrescribe la configuración cargada.
        """
        # Inicializar atributos básicos primero
        self.ib = ib or IB()
        self.connected = False
        self.active_orders = {}
        self.positions = {}
        self._order_status_callbacks = {}
        self._shutdown = False
        self._connection_lock = asyncio.Lock()
        self._order_lock = asyncio.Lock()
        
        # Configurar logging básico temporal
        self._logger = logging.getLogger(__name__)
        if not self._logger.handlers:
            logging.basicConfig(level=logging.INFO)
        
        # Cargar configuración
        try:
            if config_path:
                try:
                    from .config_loader import load_config
                    self._config = load_config(config_path)
                except ImportError:
                    # Si falla la importación relativa, intentar absoluta
                    import sys
                    sys.path.insert(0, str(Path(__file__).parent.parent))
                    from order_executor.config_loader import load_config
                    self._config = load_config(config_path)
            else:
                self._config = config
                
            # Inicializar el gestor de riesgo si no se proporciona uno
            if risk_manager is None:
                # Usar getattr con valores por defecto para evitar errores si la configuración no existe
                risk_config = getattr(self._config, 'risk', {})
                risk_params = RiskParameters(
                    max_position_size_pct=getattr(risk_config, 'max_position_size_pct', 10.0),
                    max_strategy_risk_pct=getattr(risk_config, 'max_strategy_risk_pct', 20.0),
                    max_daily_loss_pct=getattr(risk_config, 'max_daily_loss_pct', 5.0),
                    max_leverage=getattr(risk_config, 'max_leverage', 4.0),
                    max_orders_per_day=getattr(risk_config, 'max_orders_per_day', 50),
                    blacklisted_symbols=getattr(risk_config, 'blacklisted_symbols', [])
                )
                self.risk_manager = RiskManager(risk_params)
            else:
                self.risk_manager = risk_manager
                
            # Configurar logging desde la configuración
            self._setup_logging()
            
        except Exception as e:
            self._logger.error(f"Error al inicializar la configuración: {e}")
            # Configuración por defecto si hay un error
            self._config = {}
            
            # Crear parámetros de riesgo por defecto
            default_risk_params = RiskParameters(
                max_position_size_pct=10.0,
                max_strategy_risk_pct=20.0,
                max_daily_loss_pct=5.0,
                max_leverage=4.0,
                max_orders_per_day=50,
                blacklisted_symbols=[]
            )
            self.risk_manager = RiskManager(default_risk_params)
            
            # Configurar logging básico
            logging.basicConfig(level=logging.INFO)
            self._logger = logging.getLogger(__name__)
        
        # Conectar a IBKR
        asyncio.create_task(self._setup_connection())
    
    def _setup_logging(self):
        """Configura el sistema de logging según la configuración"""
        log_config = self._config.logging
        
        # Configurar nivel de log
        log_level = getattr(logging, log_config.level.upper(), logging.INFO)
        
        # Configurar formateador
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Configurar handler de consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configurar handler de archivo
        file_handler = logging.handlers.RotatingFileHandler(
            log_config.file,
            maxBytes=log_config.max_size_mb * 1024 * 1024,
            backupCount=log_config.backup_count
        )
        file_handler.setFormatter(formatter)
        
        # Configurar logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        # Configurar logger de ib_insync
        ib_logger = logging.getLogger('ib_insync')
        ib_logger.setLevel(max(log_level, logging.WARNING))  # No más detallado que WARNING para ib_insync
        
        logger.info("Logging configurado correctamente")

    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        """Carga la configuración desde el archivo"""
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            logger.warning(f"Archivo de configuración {config_file} no encontrado. Usando configuración por defecto.")
            config['IBKR'] = {
                'host': '127.0.0.1',
                'port': '7497',
                'client_id': '1',
                'timeout': '30'
            }
        else:
            config.read(config_file)
        return config
    
    async def _setup_connection(self):
        """Establece la conexión con IBKR y actualiza el valor de la cuenta"""
        try:
            ib_config = self._config.ibkr
            
            logger.info(f"Conectando a IBKR en {ib_config.host}:{ib_config.port}...")
            
            await self.ib.connectAsync(
                host=ib_config.host,
                port=ib_config.port,
                clientId=ib_config.client_id,
                timeout=ib_config.timeout,
                readonly=False
            )
            
            self.connected = True
            logger.info("Conexión establecida con IBKR")
            
            # Actualizar el valor de la cuenta en el RiskManager
            await self._update_account_value()
            
            # Suscribirse a actualizaciones de la cuenta
            self.ib.accountSummaryEvent += self._on_account_update
            
            logger.info("Configuración de conexión completada")
            
        except Exception as e:
            logger.error(f"Error al conectar con IBKR: {e}")
            self.connected = False
            raise
            
    def _on_account_update(self, account_values):
        """Manejador de actualizaciones de la cuenta"""
        try:
            net_liquidation = next(
                (item for item in account_values if item.tag == 'NetLiquidation'),
                None
            )
            if net_liquidation:
                account_value = float(net_liquidation.value)
                self.risk_manager.account_value = account_value
                logger.debug(f"Valor de la cuenta actualizado: ${account_value:,.2f}")
        except Exception as e:
            logger.error(f"Error al procesar actualización de cuenta: {e}")
    
    async def _update_account_value(self):
        """Actualiza el valor de la cuenta en el RiskManager"""
        try:
            # Forzar una actualización de la cuenta
            account_values = await self.ib.accountSummaryAsync()
            self._on_account_update(account_values)
        except Exception as e:
            logger.error(f"Error al actualizar el valor de la cuenta: {e}")
            # Intentar nuevamente después de un breve retraso
            await asyncio.sleep(5)
            try:
                account_values = await self.ib.accountSummaryAsync()
                self._on_account_update(account_values)
            except Exception as e2:
                logger.error(f"Error en reintento de actualización de cuenta: {e2}")
    
    def _create_contract(self, ticker: str) -> Contract:
        """Crea un contrato IBKR para el ticker dado"""
        # Por defecto asumimos acciones de EEUU
        # Puedes extender esto para soportar otros mercados
        return Stock(ticker, 'SMART', 'USD')
    
    async def execute_order(self, order_request: OrderRequest) -> OrderResponse:
        """
        Ejecuta una orden de trading
        
        Args:
            order_request: Solicitud de orden a ejecutar
            
        Returns:
            OrderResponse con el resultado de la ejecución
        """
        if not self.connected:
            try:
                self._setup_connection()
            except Exception as e:
                return OrderResponse(
                    success=False,
                    order_id=order_request.order_id or '',
                    message=f"No se pudo conectar a IBKR: {e}"
                )
        
        try:
            # Crear contrato
            contract = self._create_contract(order_request.ticker)
            
            # Crear orden según el tipo
            if order_request.order_type.upper() == 'MKT':
                order = MarketOrder(
                    order_request.action.upper(),
                    order_request.quantity
                )
            elif order_request.order_type.upper() == 'LMT' and order_request.limit_price is not None:
                order = LimitOrder(
                    order_request.action.upper(),
                    order_request.quantity,
                    order_request.limit_price
                )
            elif order_request.order_type.upper() == 'STP' and order_request.stop_price is not None:
                order = StopOrder(
                    order_request.action.upper(),
                    order_request.quantity,
                    order_request.stop_price
                )
            else:
                return OrderResponse(
                    success=False,
                    order_id=order_request.order_id or '',
                    message=f"Tipo de orden no soportado o parámetros faltantes: {order_request}"
                )
            
            # Asignar ID de orden si se proporciona
            if order_request.order_id:
                order.orderId = int(order_request.order_id)
            
            # Validar la orden con el gestor de riesgo
            is_buy = order_request.action.upper() == 'BUY'
            
            # Obtener el precio actual para la validación de riesgo
            contract = self._create_contract(order_request.ticker)
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(1)  # Esperar por el precio
            
            price = ticker.last if ticker.last > 0 else (ticker.bid + ticker.ask) / 2
            
            # Validar la orden con el gestor de riesgo
            is_valid, reason = self.risk_manager.validate_order(
                ticker=order_request.ticker,
                quantity=order_request.quantity,
                price=price,
                action=order_request.action,
                strategy_id=order_request.strategy_id
            )
            
            if not is_valid:
                return OrderResponse(
                    success=False,
                    order_id=order_request.order_id or str(uuid.uuid4()),
                    status=OrderStatus.REJECTED,
                    message=f"Orden rechazada por gestión de riesgo: {reason}",
                    details={'reason': reason}
                )
            
            # Verificar si ya existe una posición para esta estrategia y ticker
            existing_position = self.get_position(order_request.ticker, order_request.strategy_id)
            
            # Enviar orden
            trade = self.ib.placeOrder(contract, order)
            
            # Esperar confirmación (sin bloquear el bucle de eventos)
            await trade.updateEvent
            
            # Procesar la respuesta
            order_status = trade.orderStatus.status.upper()
            is_filled = order_status == 'FILLED'
            
            position_id = None
            
            # Actualizar el gestor de riesgo
            if is_filled and trade.orderStatus.filled > 0:
                fill_price = float(trade.orderStatus.avgFillPrice)
                filled_qty = int(trade.orderStatus.filled)
                
                # Actualizar el gestor de riesgo
                self.risk_manager.update_position(
                    ticker=order_request.ticker,
                    quantity=filled_qty,
                    price=fill_price,
                    action=order_request.action,
                    strategy_id=order_request.strategy_id
                )
                
                # Actualizar el valor de la cuenta después de la operación
                await self._update_account_value()
            
            if is_filled and trade.orderStatus.filled > 0:
                fill_price = float(trade.orderStatus.avgFillPrice)
                filled_qty = int(trade.orderStatus.filled)
                
                if existing_position:
                    # Actualizar posición existente
                    self._update_position(
                        existing_position, 
                        str(trade.order.orderId),
                        fill_price,
                        filled_qty,
                        is_buy
                    )
                    position_id = existing_position.ticker
                else:
                    # Crear nueva posición solo para órdenes de compra
                    if is_buy:
                        new_position = Position(
                            ticker=order_request.ticker,
                            strategy_id=order_request.strategy_id,
                            quantity=filled_qty,
                            entry_price=fill_price,
                            current_price=fill_price,
                            entry_time=datetime.now(),
                            order_ids=[str(trade.order.orderId)],
                            metadata=order_request.metadata
                        )
                        self._add_position(new_position)
                        position_id = new_position.ticker
            
            return OrderResponse(
                success=is_filled,
                order_id=str(trade.order.orderId),
                status=OrderStatus(order_status),
                position_id=position_id,
                message=(
                    f"Orden {order_request.action} de {order_request.quantity} {order_request.ticker} "
                    f"{'ejecutada' if is_filled else f'en estado {order_status}'}"
                ),
                details={
                    'status': trade.orderStatus.status,
                    'filled': trade.orderStatus.filled,
                    'remaining': trade.orderStatus.remaining,
                    'avg_fill_price': trade.orderStatus.avgFillPrice,
                    'strategy_id': order_request.strategy_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error al ejecutar orden {order_request}: {e}")
            return OrderResponse(
                success=False,
                order_id=order_request.order_id or '',
                message=str(e)
            )
    
    def sync_positions(self) -> Dict[str, Position]:
        """
        Sincroniza las posiciones con IBKR
        
        Returns:
            Dict con las posiciones actualizadas
        """
        if not self.connected:
            try:
                self._setup_connection()
            except Exception as e:
                logger.error(f"No se pudo conectar a IBKR: {e}")
                return {}
        
        try:
            # Obtener posiciones de IBKR
            ib_positions = {}
            for pos in self.ib.positions():
                contract = pos.contract
                if contract.secType == 'STK':
                    ib_positions[contract.symbol] = {
                        'position': pos.position,
                        'avg_cost': pos.avgCost
                    }
            
            # Actualizar precios de posiciones existentes
            updated_positions = {}
            for symbol, pos_data in ib_positions.items():
                # Obtener precio de mercado
                try:
                    ticker = self.ib.reqMktData(Stock(symbol, 'SMART', 'USD'))
                    self.ib.sleep(1)  # Esperar por el precio
                    
                    if ticker.last > 0:
                        current_price = ticker.last
                    else:
                        current_price = (ticker.bid + ticker.ask) / 2 if ticker.bid > 0 and ticker.ask > 0 else 0
                    
                    # Actualizar posición si existe
                    if symbol in self.positions:
                        position = self.positions[symbol]
                        position.current_price = current_price
                        position.update_price(current_price)
                        updated_positions[symbol] = position
                    
                except Exception as e:
                    logger.error(f"Error actualizando precio para {symbol}: {e}")
            
            return updated_positions
            
        except Exception as e:
            logger.error(f"Error al sincronizar posiciones: {e}")
            return {}
    
    async def disconnect(self):
        """Cierra la conexión con IBKR de forma segura"""
        if self.connected:
            try:
                # Desuscribirse de las actualizaciones de la cuenta
                if hasattr(self, 'ib') and hasattr(self.ib, 'accountSummaryEvent'):
                    self.ib.accountSummaryEvent -= self._on_account_update
                
                # Cerrar la conexión
                if self.ib.isConnected():
                    await self.ib.disconnectAsync()
                    
                self.connected = False
                logger.info("Desconexión de IBKR completada")
                
                # Reiniciar estadísticas diarias al final del día
                self.risk_manager.reset_daily_stats()
                
            except Exception as e:
                logger.error(f"Error al desconectar de IBKR: {e}")
                raise
    
    def get_risk_summary(self) -> Dict:
        """
        Obtiene un resumen del estado actual de riesgo
        
        Returns:
            Dict con el resumen de riesgo
        """
        return self.risk_manager.get_risk_summary()
    
    async def __aenter__(self):
        """Permite usar el ejecutor en un contexto async with"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asegura que la conexión se cierre correctamente al salir del contexto"""
        await self.disconnect()
    
    def __del__(self):
        """Asegura que la conexión se cierre correctamente"""
        if hasattr(self, 'connected') and self.connected:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.disconnect())
                else:
                    loop.run_until_complete(self.disconnect())
            except Exception as e:
                if logger:
                    logger.error(f"Error al cerrar la conexión en el destructor: {e}")

# Ejemplo de uso
async def example_usage():
    # Crear ejecutor
    executor = OrderExecutor()
    
    try:
        # ID de estrategia único
        strategy_id = "mean_reversion_1h"
        
        # Verificar si ya tenemos una posición
        if not executor.has_position("AAPL", strategy_id):
            # Ejecutar una orden de compra de mercado
            response = await executor.execute_order(
                OrderRequest(
                    ticker="AAPL",
                    action="BUY",
                    quantity=10,
                    strategy_id=strategy_id,
                    order_type="MKT",
                    order_id=f"{strategy_id}_entry_{int(datetime.now().timestamp())}",
                    metadata={
                        'signal_strength': 0.85,
                        'entry_condition': 'rsi_oversold'
                    }
                )
            )
            print(f"Respuesta de entrada: {response}")
            
            # Verificar si la orden se llenó
            if response.success and response.position_id:
                print(f"Posición abierta: {response.position_id}")
                
                # Esperar un tiempo (simulando tiempo de espera)
                await asyncio.sleep(5)
                
                # Cerrar la posición
                close_response = await executor.execute_order(
                    OrderRequest(
                        ticker="AAPL",
                        action="SELL",
                        quantity=10,  # Misma cantidad que la compra
                        strategy_id=strategy_id,
                        order_type="MKT",
                        order_id=f"{strategy_id}_exit_{int(datetime.now().timestamp())}",
                        metadata={
                            'exit_reason': 'take_profit',
                            'pnl_pct': 0.0  # Se actualizará con el P&L real
                        }
                    )
                )
                print(f"Respuesta de salida: {close_response}")
        else:
            print("Ya existe una posición abierta para esta estrategia")
            
        # Mostrar posiciones por estrategia
        positions = executor.get_positions(strategy_id)
        print(f"Posiciones para {strategy_id}: {positions}")
        
        # Sincronizar posiciones con IBKR
        print("Sincronizando posiciones con IBKR...")
        updated = executor.sync_positions()
        print(f"Posiciones actualizadas: {updated}")
        
    finally:
        # Siempre desconectar al terminar
        executor.disconnect()

async def example_with_risk_management():
    # Configuración personalizada de riesgo
    risk_params = RiskParameters(
        max_position_size_pct=10.0,  # 10% del capital por posición
        max_strategy_risk_pct=30.0,  # 30% del capital por estrategia
        max_daily_loss_pct=2.0,      # 2% de pérdida diaria máxima
        max_leverage=3.0,            # Apalancamiento máximo 3x
        max_orders_per_day=100,       # Máximo 100 operaciones por día
        blacklist=['TSLA', 'GME']     # Símbolos bloqueados
    )
    
    # Crear ejecutor con gestión de riesgo personalizada
    executor = OrderExecutor(risk_manager=RiskManager(account_value=100000, risk_params=risk_params))
    
    try:
        # ID de estrategia único
        strategy_id = "mean_reversion_1h"
        
        # Verificar riesgo antes de operar
        risk_summary = executor.get_risk_summary()
        print("Resumen de riesgo inicial:", risk_summary)
        
        # Resto del código de ejemplo...
        await example_usage()
        
    finally:
        # Mostrar resumen de riesgo al finalizar
        risk_summary = executor.get_risk_summary()
        print("\nResumen de riesgo final:")
        import json
        print(json.dumps(risk_summary, indent=2, default=str))
        
        # Siempre desconectar al terminar
        executor.disconnect()

async def main():
    # Ejemplo de uso con configuración personalizada
    config_path = Path("config/config.yaml")
    
    # Usar el ejecutor en un contexto async with
    async with OrderExecutor(config_path=config_path) as executor:
        # Aquí iría el código de tu estrategia
        print("Ejecutando con configuración:", config_path)
        
        # Obtener resumen de riesgo
        risk_summary = executor.get_risk_summary()
        print("Resumen de riesgo:")
        import json
        print(json.dumps(risk_summary, indent=2, default=str))
        
        # Aquí podrías ejecutar tu estrategia o interactuar con el ejecutor
        print("Listo para operar. Presiona Ctrl+C para salir.")
        
        # Mantener el programa en ejecución
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSaliendo...")
    except Exception as e:
        print(f"Error inesperado: {e}")
        raise
