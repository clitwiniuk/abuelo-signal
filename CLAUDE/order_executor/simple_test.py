#!/usr/bin/env python3
"""
Script de prueba simplificado para el módulo order_executor
"""
import asyncio
import logging
import sys
from pathlib import Path

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('order_executor_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Configurar el path para importaciones
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent))

# Importar el módulo
try:
    from order_executor.order_executor import OrderExecutor
    logger.info("Módulo OrderExecutor importado correctamente")
except ImportError as e:
    logger.error(f"Error al importar OrderExecutor: {e}")
    logger.info("Intentando importación alternativa...")
    try:
        sys.path.insert(0, str(current_dir))
        from order_executor import OrderExecutor
        logger.info("Módulo OrderExecutor importado correctamente (ruta alternativa)")
    except ImportError as e2:
        logger.error(f"Error en importación alternativa: {e2}")
        sys.exit(1)

async def test_connection():
    """Prueba la conexión básica con IBKR"""
    logger.info("=== Iniciando prueba de conexión ===")
    
    # Ruta al archivo de configuración
    config_path = current_dir / "config" / "config.yaml"
    
    if not config_path.exists():
        logger.error(f"No se encontró el archivo de configuración: {config_path}")
        return
    
    logger.info(f"Usando configuración: {config_path}")
    
    # Crear instancia del ejecutor
    try:
        executor = OrderExecutor(config_path=config_path)
        logger.info("OrderExecutor creado correctamente")
        
        # Conectar a IBKR
        logger.info("Conectando a IBKR...")
        await executor._setup_connection()
        
        if not executor.connected:
            logger.error("No se pudo conectar a IBKR")
            return
            
        logger.info("Conexión exitosa con IBKR")
        
        # Obtener información básica de la cuenta
        try:
            logger.info("Obteniendo información de la cuenta...")
            account = await asyncio.wait_for(executor.ib.accountSummaryAsync(), timeout=10)
            
            logger.info("=== Información de la cuenta ===")
            for item in account:
                if item.tag in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue']:
                    logger.info(f"{item.tag}: {item.value}")
                    
        except asyncio.TimeoutError:
            logger.warning("Tiempo de espera agotado al obtener información de la cuenta")
        except Exception as e:
            logger.error(f"Error al obtener información de la cuenta: {e}")
        
        # Esperar un momento
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {e}", exc_info=True)
    finally:
        # Cerrar la conexión si está abierta
        if 'executor' in locals() and hasattr(executor, 'connected') and executor.connected:
            logger.info("Cerrando conexión con IBKR...")
            await executor.disconnect()
            logger.info("Conexión cerrada correctamente")
    
    logger.info("=== Prueba finalizada ===")

if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        logger.info("\nPrueba interrumpida por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
    finally:
        logger.info("=== Fin del programa ===")
