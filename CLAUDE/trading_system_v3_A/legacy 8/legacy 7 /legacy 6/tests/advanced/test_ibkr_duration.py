"""
Script para probar el cálculo de duración en IBKRAdapter.

This script is intended to be run manually, **not** as part of the automated pytest
suite. Setting `__test__ = False` prevents pytest from collecting it and
eliminates collection-time coroutine warnings.
"""

# Prevent pytest from collecting this module as a test file
__test__ = False



import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Añadir el directorio raíz al path para importaciones
sys.path.append(str(Path(__file__).parent.absolute()))

from adapters.ibkr_adapter import IBKRAdapter

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def test_duration_calculation():
    """Prueba el cálculo de duración para diferentes timeframes."""
    # Configuración de prueba
    config = {
        'ibkr': {
            'host': '127.0.0.1',  # TWS o Gateway
            'port': 7497,         # Puerto de TWS (7497 para TWS, 4001 para IB Gateway)
            'client_id': 1,       # ID de cliente
            'read_only': False    # Modo de solo lectura
        }
    }
    
    # Símbolos para probar
    symbols = ['AAPL', 'MSFT', 'TSLA']
    
    # Timeframes a probar
    timeframes = [
        '1 min', '5 mins', '15 mins', '30 mins',  # Intradía
        '1 hour', '4 hours',                      # Horario
        '1 day'                                   # Diario
    ]
    
    # Crear instancia del adaptador
    adapter = IBKRAdapter(config)
    
    try:
        # Conectar a IBKR
        logger.info("Conectando a IBKR...")
        await adapter.connect()
        
        # Probar cada combinación de símbolo y timeframe
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    logger.info(f"\nProbando {symbol} con timeframe {timeframe}")
                    
                    # Obtener datos históricos
                    logger.info(f"Solicitando datos para {symbol} ({timeframe})...")
                    bars = await adapter.get_bars(
                        symbol=symbol,
                        timeframe=timeframe,
                        limit=100  # Número de barras a solicitar
                    )
                    
                    if bars and len(bars) > 0:
                        logger.info(f"✓ Datos recibidos: {len(bars)} barras")
                        # Mostrar información de las primeras y últimas barras
                        first_bar = bars[0]
                        last_bar = bars[-1]
                        logger.info(f"  Primera barra: {first_bar['datetime']} - O: {first_bar['open']}, H: {first_bar['high']}, L: {first_bar['low']}, C: {first_bar['close']}")
                        logger.info(f"  Última barra:  {last_bar['datetime']} - O: {last_bar['open']}, H: {last_bar['high']}, L: {last_bar['low']}, C: {last_bar['close']}")
                    else:
                        logger.warning("✗ No se recibieron datos")
                        
                except Exception as e:
                    logger.error(f"Error al obtener datos para {symbol} ({timeframe}): {str(e)}")
                
                # Pequeña pausa entre solicitudes
                await asyncio.sleep(1)
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}")
    finally:
        # Desconectar
        logger.info("Desconectando de IBKR...")
        await adapter.disconnect()
        logger.info("Prueba completada")

if __name__ == "__main__":
    asyncio.run(test_duration_calculation())
