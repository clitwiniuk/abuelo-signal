#!/usr/bin/env python3
"""
Punto de entrada principal para el módulo order_executor.
Permite ejecutar el módulo con: python -m order_executor
"""
import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Configurar logging básico temporal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None) -> None:
    """Configura el sistema de logging"""
    # Niveles de log válidos
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configurar handlers
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Aplicar configuración
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Reducir el nivel de log de algunas librerías ruidosas
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

async def run_executor(config_path: Path) -> None:
    """Ejecuta el OrderExecutor con la configuración proporcionada"""
    try:
        # Importar aquí para evitar problemas de importación circular
        from order_executor.order_executor import OrderExecutor
        
        logger.info(f"Iniciando OrderExecutor con configuración: {config_path}")
        
        async with OrderExecutor(config_path=config_path) as executor:
            if not executor.connected:
                logger.error("No se pudo conectar a IBKR")
                return
            
            logger.info("Conexión exitosa con IBKR")
            
            # Mostrar información de la cuenta
            logger.info("=== Información de la cuenta ===")
            try:
                account = await executor.ib.accountSummaryAsync()
                for item in account:
                    if item.tag in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue', 'AvailableFunds']:
                        logger.info(f"{item.tag}: {item.value}")
            except Exception as e:
                logger.error(f"Error al obtener información de la cuenta: {e}")
            
            # Mantener el programa en ejecución
            logger.info("\nOrderExecutor en ejecución. Presiona Ctrl+C para salir...")
            while True:
                await asyncio.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("\nDeteniendo OrderExecutor...")
    except Exception as e:
        logger.error(f"Error en OrderExecutor: {e}", exc_info=True)
        raise

def parse_arguments() -> Dict[str, Any]:
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='Ejecuta el OrderExecutor para operaciones de trading.')
    
    parser.add_argument(
        '--config',
        type=str,
        default=str(Path(__file__).parent / 'config' / 'config.yaml'),
        help='Ruta al archivo de configuración YAML'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='order_executor.log',
        help='Archivo de log (opcional)'
    )
    
    return vars(parser.parse_args())

def main() -> None:
    """Función principal"""
    try:
        # Parsear argumentos
        args = parse_arguments()
        
        # Configurar logging
        setup_logging(args['log_level'], args['log_file'])
        
        # Verificar archivo de configuración
        config_path = Path(args['config']).resolve()
        if not config_path.exists():
            logger.error(f"No se encontró el archivo de configuración: {config_path}")
            sys.exit(1)
        
        # Ejecutar el bucle de eventos
        asyncio.run(run_executor(config_path))
        
    except KeyboardInterrupt:
        logger.info("\nAplicación detenida por el usuario")
    except Exception as e:
        logger.critical(f"Error crítico: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Ordenador de ejecución detenido")

if __name__ == "__main__":
    main()
