#!/usr/bin/env python3
"""
Script de emergencia para limpiar suscripciones IBKR activas.
Útil cuando hay errores 322 (Maximum account summary requests exceeded)
"""

import asyncio
import logging
from ib_insync import IB

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cleanup_ibkr_subscriptions():
    """
    Conecta a IBKR y cancela todas las suscripciones activas
    """
    ib = IB()

    try:
        # Conectar a TWS/Gateway
        logger.info("Conectando a IBKR...")
        await ib.connectAsync(
            host='127.0.0.1',
            port=7497,  # TWS Paper
            clientId=9999  # ID único para este script
        )

        logger.info("✅ Conectado a IBKR")

        # Cancelar todas las suscripciones de account summary
        logger.info("Cancelando suscripciones de account summary...")
        try:
            # Intentar cancelar con diferentes accounts
            for account in ['', 'All']:
                try:
                    await ib.reqAccountUpdatesAsync(subscribe=False, acctCode=account)
                    logger.info(f"   ✅ Cancelado account updates para '{account}'")
                except Exception as e:
                    logger.debug(f"   Account '{account}': {e}")
        except Exception as e:
            logger.warning(f"Error cancelando account updates: {e}")

        # Cancelar market data subscriptions
        logger.info("Cancelando suscripciones de market data...")
        try:
            # Obtener todos los tickers activos y cancelarlos
            tickers = ib.tickers()
            for ticker in tickers:
                try:
                    ib.cancelMktData(ticker.contract)
                except:
                    pass
            logger.info(f"   ✅ Canceladas {len(tickers)} suscripciones de market data")
        except Exception as e:
            logger.warning(f"Error cancelando market data: {e}")

        # Esperar un momento para que las cancelaciones se procesen
        await asyncio.sleep(2)

        logger.info("🎉 Limpieza completada exitosamente")

    except Exception as e:
        logger.error(f"❌ Error durante limpieza: {e}")
        raise

    finally:
        # Desconectar
        if ib.isConnected():
            ib.disconnect()
            logger.info("Desconectado de IBKR")

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║  IBKR Subscription Cleanup Script                        ║
║                                                           ║
║  Este script limpiará todas las suscripciones activas    ║
║  de IBKR para resolver errores 322.                      ║
║                                                           ║
║  ANTES DE EJECUTAR:                                      ║
║  1. Detener todos los procesos de trading                ║
║  2. Reiniciar TWS/Gateway                                ║
║  3. Ejecutar este script                                 ║
╚═══════════════════════════════════════════════════════════╝
    """)

    input("Presiona ENTER para continuar...")

    asyncio.run(cleanup_ibkr_subscriptions())

    print("""
╔═══════════════════════════════════════════════════════════╗
║  Limpieza completada                                     ║
║                                                           ║
║  PRÓXIMOS PASOS:                                         ║
║  1. Esperar 30 segundos                                  ║
║  2. Reiniciar tus procesos de trading                    ║
║  3. Monitorear logs para confirmar que no hay error 322  ║
╚═══════════════════════════════════════════════════════════╝
    """)
