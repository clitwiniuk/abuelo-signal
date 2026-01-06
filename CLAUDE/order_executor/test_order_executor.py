#!/usr/bin/env python3
"""
Script de prueba para el módulo order_executor
"""
import asyncio
import logging
import sys
from pathlib import Path
import os

# Configurar el nivel de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_executor.log')
    ]
)
logger = logging.getLogger(__name__)

# Añadir el directorio padre al path para importaciones
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent))

# Importar después de configurar el path
try:
    from order_executor import OrderExecutor, OrderRequest
except ImportError as e:
    logger.error(f"Error al importar módulos: {e}")
    sys.exit(1)

async def test_connection():
    """Prueba la conexión y muestra información de la cuenta"""
    try:
        # Usar la configuración por defecto (buscará en config/config.yaml)
        config_path = current_dir / "config" / "config.yaml"
        
        if not config_path.exists():
            logger.error(f"No se encontró el archivo de configuración: {config_path}")
            return
            
        logger.info(f"Iniciando prueba con configuración: {config_path.absolute()}")
        
        # Mostrar configuración cargada
        logger.info("=== Configuración cargada ===")
        with open(config_path, 'r') as f:
            logger.info(f"\n{f.read()}")
        
        # Crear instancia del ejecutor
        logger.info("Inicializando OrderExecutor...")
        executor = OrderExecutor(config_path=config_path)
        
        try:
            # Conectar manualmente para mejor control
            logger.info("Conectando a IBKR...")
            await executor._setup_connection()
            
            if not executor.connected:
                logger.error("No se pudo establecer la conexión con IBKR")
                return
                
            # Mostrar información de la cuenta
            logger.info("\n=== Información de la cuenta ===")
            try:
                account = await asyncio.wait_for(executor.ib.accountSummaryAsync(), timeout=10)
                for item in account:
                    if item.tag in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue']:
                        logger.info(f"{item.tag}: {item.value}")
            except asyncio.TimeoutError:
                logger.warning("Tiempo de espera agotado al obtener información de la cuenta")
            except Exception as e:
                logger.error(f"Error al obtener información de la cuenta: {e}")
            
            # Mostrar resumen de riesgo
            logger.info("\n=== Resumen de Riesgo ===")
            try:
                risk_summary = executor.get_risk_summary()
                for key, value in risk_summary.items():
                    if isinstance(value, (int, float)) and key != 'account_value':
                        logger.info(f"{key}: {value:.2f}%")
                    else:
                        logger.info(f"{key}: {value}")
            except Exception as e:
                logger.error(f"Error al obtener resumen de riesgo: {e}")
            
            # Mantener la conexión abierta por 10 segundos
            logger.info("\nManteniendo la conexión abierta por 10 segundos...")
            logger.info("Presiona Ctrl+C para salir antes")
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                logger.info("\nCerrando conexión...")
                
        except Exception as e:
            logger.error(f"Error durante la ejecución: {e}", exc_info=True)
            raise
            
        finally:
            # Asegurarse de que la conexión se cierre correctamente
            if executor.connected:
                logger.info("Cerrando conexión con IBKR...")
                await executor.disconnect()
                logger.info("Conexión cerrada correctamente")
    
    except Exception as e:
        logger.error(f"Error durante la prueba: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        logger.info("=== Iniciando prueba del OrderExecutor ===")
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        logger.info("\nPrueba interrumpida por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
    finally:
        logger.info("=== Prueba finalizada ===\n")
