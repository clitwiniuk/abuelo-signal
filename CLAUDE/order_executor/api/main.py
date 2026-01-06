"""
API principal para el Order Executor.
Expone endpoints REST para la ejecución de órdenes y consulta de estado.
"""
import logging
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
from pathlib import Path
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from order_executor import OrderExecutor
except ImportError:
    logger.error("No se pudo importar OrderExecutor. Asegúrate de que el módulo está instalado correctamente.")
    raise

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Order Executor API",
    description="API para la ejecución de órdenes de trading",
    version="0.1.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables globales
executor = None

# Modelos Pydantic
class SignalRequest(BaseModel):
    """Modelo para las señales de trading"""
    strategy_id: str = Field(..., description="ID único de la estrategia")
    ticker: str = Field(..., description="Símbolo del activo")
    signal: str = Field(..., description="Tipo de señal: BUY, SELL o CLOSE")
    quantity: Optional[int] = Field(1, description="Cantidad a operar")
    price: Optional[float] = Field(None, description="Precio límite (opcional)")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Metadatos adicionales"
    )

class SignalResponse(BaseModel):
    """Respuesta a una señal de trading"""
    success: bool
    order_id: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None

class PositionResponse(BaseModel):
    """Información de una posición abierta"""
    strategy_id: str
    ticker: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float

# Eventos de la aplicación
@app.on_event("startup")
async def startup_event():
    """Inicializa el OrderExecutor al arrancar la API"""
    global executor
    try:
        logger.info("Inicializando OrderExecutor...")
        executor = OrderExecutor()
        logger.info("OrderExecutor inicializado correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar OrderExecutor: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cierra las conexiones al detener la API"""
    if executor:
        logger.info("Cerrando conexión con IBKR...")
        await executor.disconnect()
        logger.info("Conexión cerrada correctamente")

# Endpoints
@app.post("/signal", response_model=SignalResponse)
async def send_signal(signal: SignalRequest):
    """
    Procesa una señal de trading (BUY/SELL/CLOSE)
    """
    if not executor:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OrderExecutor no inicializado"
        )
    
    try:
        # Validar la señal
        signal.signal = signal.signal.upper()
        if signal.signal not in ["BUY", "SELL", "CLOSE"]:
            raise ValueError(f"Señal inválida: {signal.signal}. Debe ser BUY, SELL o CLOSE")
        
        # Procesar la señal
        if signal.signal == "BUY":
            order_request = {
                "ticker": signal.ticker,
                "action": "BUY",
                "quantity": signal.quantity,
                "strategy_id": signal.strategy_id,
                "order_type": "MKT" if signal.price is None else "LMT",
                "limit_price": signal.price,
                "metadata": signal.metadata
            }
            response = await executor.execute_order(order_request)
            
        elif signal.signal == "SELL":
            order_request = {
                "ticker": signal.ticker,
                "action": "SELL",
                "quantity": signal.quantity,
                "strategy_id": signal.strategy_id,
                "order_type": "MKT" if signal.price is None else "LMT",
                "limit_price": signal.price,
                "metadata": signal.metadata
            }
            response = await executor.execute_order(order_request)
            
        elif signal.signal == "CLOSE":
            # Cerrar posición completa
            positions = await get_positions(signal.strategy_id, signal.ticker)
            if not positions:
                return SignalResponse(
                    success=False,
                    message=f"No hay posición abierta para {signal.ticker}"
                )
            
            position = positions[0]
            order_request = {
                "ticker": signal.ticker,
                "action": "SELL" if position.quantity > 0 else "BUY",
                "quantity": abs(position.quantity),
                "strategy_id": signal.strategy_id,
                "order_type": "MKT",
                "metadata": {"is_close": True, **signal.metadata}
            }
            response = await executor.execute_order(order_request)
        
        return SignalResponse(
            success=response.get("success", False),
            order_id=response.get("order_id"),
            message=response.get("message", ""),
            details=response
        )
        
    except Exception as e:
        logger.error(f"Error al procesar señal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.get("/positions", response_model=List[PositionResponse])
async def get_positions(strategy_id: Optional[str] = None, ticker: Optional[str] = None):
    """
    Obtiene las posiciones abiertas
    """
    if not executor:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OrderExecutor no inicializado"
        )
    
    try:
        positions = executor.positions
        result = []
        
        for pos_id, position in positions.items():
            # Filtrar por estrategia y ticker si se especifican
            if strategy_id and position.strategy_id != strategy_id:
                continue
            if ticker and position.ticker != ticker.upper():
                continue
                
            result.append({
                "strategy_id": position.strategy_id,
                "ticker": position.ticker,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "pnl": position.pnl,
                "pnl_pct": position.pnl_pct
            })
            
        return result
        
    except Exception as e:
        logger.error(f"Error al obtener posiciones: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener posiciones"
        )

@app.get("/health")
async def health_check():
    """Endpoint de salud"""
    return {
        "status": "ok",
        "connected": executor.connected if executor else False,
        "active_orders": len(executor.active_orders) if executor else 0,
        "open_positions": len(executor.positions) if executor else 0
    }

def run_api(host: str = "0.0.0.0", port: int = 8000):
    """Inicia el servidor de la API"""
    uvicorn.run(
        "order_executor.api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    run_api()
