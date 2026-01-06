#!/usr/bin/env python3
"""
Script de prueba independiente para verificar la conexión con IBKR
"""
import asyncio
import logging
from pathlib import Path
from ib_insync import IB

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ibkr_connection_test.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_ibkr_connection(host='127.0.0.1', port=7497, client_id=1, timeout=30):
    """Prueba la conexión con IBKR"""
    ib = IB()
    connected = False
    
    try:
        logger.info(f"Conectando a IBKR en {host}:{port}...")
        await ib.connectAsync(
            host=host,
            port=port,
            clientId=client_id,
            timeout=timeout,
            readonly=True  # Modo solo lectura para pruebas
        )
        connected = True
        logger.info("Conexión exitosa con IBKR")
        
        # Obtener información de la cuenta
        logger.info("Obteniendo información de la cuenta...")
        account = await ib.accountSummaryAsync()
        
        logger.info("=== Información de la cuenta ===")
        for item in account:
            if item.tag in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue', 'AvailableFunds']:
                logger.info(f"{item.tag}: {item.value}")
        
        # Obtener la hora del servidor
        server_time = await ib.reqCurrentTimeAsync()
        logger.info(f"Hora del servidor IBKR: {server_time}")
        
        return True
        
    except asyncio.TimeoutError:
        logger.error("Tiempo de espera agotado al conectar con IBKR")
        return False
    except ConnectionRefusedError:
        logger.error("No se pudo conectar con el TWS/IB Gateway. ¿Está en ejecución?")
        return False
    except Exception as e:
        logger.error(f"Error al conectar con IBKR: {e}")
        return False
    finally:
        if connected:
            logger.info("Cerrando conexión con IBKR...")
            ib.disconnect()
            logger.info("Conexión cerrada correctamente")

if __name__ == "__main__":
    logger.info("=== Iniciando prueba de conexión con IBKR ===")
    
    # Configuración por defecto (puedes modificar estos valores)
    config = {
        'host': '127.0.0.1',  # Cambia esto si IBKR no está en localhost
        'port': 7497,         # Puerto TWS: 7496 (live) o 7497 (paper)
        'client_id': 1,       # ID de cliente único
        'timeout': 30         # Tiempo de espera en segundos
    }
    
    try:
        # Ejecutar la prueba
        success = asyncio.run(test_ibkr_connection(**config))
        
        if success:
            logger.info("=== Prueba completada con éxito ===")
        else:
            logger.error("=== La prueba ha fallado ===")
            
    except KeyboardInterrupt:
        logger.info("\nPrueba interrumpida por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
    finally:
        logger.info("=== Fin de la prueba ===")
