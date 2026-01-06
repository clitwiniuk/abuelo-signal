"""
Ejemplo de estrategia que utiliza la API del Order Executor
"""
import asyncio
import random
import logging
import aiohttp
from typing import Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EstrategiaEjemplo")

class EstrategiaEjemplo:
    """Estrategia de ejemplo que envía señales a la API"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip('/')
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def enviar_señal(self, señal: Dict[str, Any]) -> Dict[str, Any]:
        """Envía una señal a la API"""
        try:
            url = f"{self.api_url}/signal"
            async with self.session.post(url, json=señal) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Error al enviar señal: {error}")
                    return {"success": False, "error": error}
                return await response.json()
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def obtener_posiciones(self, estrategia_id: str = None) -> Dict[str, Any]:
        """Obtiene las posiciones abiertas"""
        try:
            params = {}
            if estrategia_id:
                params["strategy_id"] = estrategia_id
                
            url = f"{self.api_url}/positions"
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Error al obtener posiciones: {error}")
                    return []
                return await response.json()
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            return []

async def estrategia_media_movil():
    """Estrategia de ejemplo basada en medias móviles"""
    estrategia_id = "media_movil_1"
    ticker = "AAPL"
    
    async with EstrategiaEjemplo() as ej:
        logger.info(f"Iniciando estrategia {estrategia_id} para {ticker}")
        
        # Simular lógica de estrategia
        while True:
            # En una estrategia real, aquí iría la lógica de análisis
            # Por ahora, usamos un número aleatorio para el ejemplo
            señal = random.choice(["BUY", "SELL", "CLOSE"])
            cantidad = random.randint(1, 10)
            
            logger.info(f"Señal generada: {señal} {cantidad} {ticker}")
            
            # Enviar señal
            respuesta = await ej.enviar_señal({
                "strategy_id": estrategia_id,
                "ticker": ticker,
                "signal": señal,
                "quantity": cantidad,
                "metadata": {
                    "notas": "Ejemplo de estrategia",
                    "precio_entrada": 150.0
                }
            })
            
            if respuesta.get("success"):
                logger.info(f"Señal ejecutada: {respuesta}")
            else:
                logger.error(f"Error en señal: {respuesta}")
            
            # Ver posiciones actuales
            posiciones = await ej.obtener_posiciones(estrategia_id)
            logger.info(f"Posiciones actuales: {posiciones}")
            
            # Esperar antes de la siguiente iteración
            await asyncio.sleep(30)  # 30 segundos entre señales

if __name__ == "__main__":
    asyncio.run(estrategia_media_movil())
