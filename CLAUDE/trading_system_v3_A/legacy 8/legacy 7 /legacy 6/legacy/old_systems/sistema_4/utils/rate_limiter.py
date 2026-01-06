"""
Rate Limiter para optimizar operaciones I/O y prevenir timeouts
"""

import asyncio
import time
from typing import Dict, Optional, Callable, Any
from functools import wraps
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuración del rate limiter"""
    calls_per_second: int = 10
    burst_limit: int = 20
    cooldown_seconds: float = 1.0


class RateLimiter:
    """
    Rate limiter asíncrono con soporte para burst y cooldown
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.call_times: Dict[str, list] = defaultdict(list)
        self.locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.burst_counts: Dict[str, int] = defaultdict(int)
        
    async def acquire(self, key: str = "default") -> bool:
        """
        Adquiere permiso para ejecutar una operación
        
        Args:
            key: Identificador único para el rate limiting
            
        Returns:
            True si se puede ejecutar, False si debe esperar
        """
        current_time = time.time()
        
        async with self.locks[key]:
            # Limpiar llamadas antiguas (más de 1 segundo)
            self.call_times[key] = [
                t for t in self.call_times[key] 
                if current_time - t < 1.0
            ]
            
            # Verificar límite de llamadas por segundo
            if len(self.call_times[key]) >= self.config.calls_per_second:
                # Verificar burst limit
                if self.burst_counts[key] >= self.config.burst_limit:
                    # Esperar cooldown
                    await asyncio.sleep(self.config.cooldown_seconds)
                    self.burst_counts[key] = 0
                    return False
                else:
                    self.burst_counts[key] += 1
            
            # Registrar llamada actual
            self.call_times[key].append(current_time)
            return True
    
    async def wait_if_needed(self, key: str = "default") -> None:
        """
        Espera si es necesario según el rate limiting
        """
        while not await self.acquire(key):
            await asyncio.sleep(0.1)


# Rate limiter global
default_rate_limiter = RateLimiter(RateLimitConfig())


def rate_limit(calls_per_second: int = 10, burst_limit: int = 20, key: Optional[str] = None):
    """
    Decorador para aplicar rate limiting a funciones asíncronas
    
    Args:
        calls_per_second: Número máximo de llamadas por segundo
        burst_limit: Límite de burst antes de cooldown
        key: Clave única para el rate limiting (auto-generada si None)
    """
    def decorator(func: Callable) -> Callable:
        limiter = RateLimiter(RateLimitConfig(calls_per_second, burst_limit))
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generar clave única si no se proporciona
            limit_key = key or f"{func.__module__}.{func.__name__}"
            
            # Esperar si es necesario
            await limiter.wait_if_needed(limit_key)
            
            # Ejecutar función original
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in rate-limited function {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator


class BatchProcessor:
    """
    Procesador de lotes para optimizar operaciones I/O
    """
    
    def __init__(self, batch_size: int = 10, max_wait_time: float = 0.5):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.pending_items = []
        self.last_batch_time = time.time()
        self.processing_lock = asyncio.Lock()
        
    async def add_item(self, item: Any, processor: Callable) -> Any:
        """
        Añade un item al lote para procesamiento
        
        Args:
            item: Item a procesar
            processor: Función que procesará el lote
            
        Returns:
            Resultado del procesamiento
        """
        async with self.processing_lock:
            self.pending_items.append(item)
            
            # Procesar si el lote está lleno o ha pasado mucho tiempo
            should_process = (
                len(self.pending_items) >= self.batch_size or
                time.time() - self.last_batch_time > self.max_wait_time
            )
            
            if should_process:
                items_to_process = self.pending_items.copy()
                self.pending_items.clear()
                self.last_batch_time = time.time()
                
                try:
                    results = await processor(items_to_process)
                    return results
                except Exception as e:
                    logger.error(f"Error in batch processing: {e}")
                    raise
            
            return None


# Instancia global del batch processor
default_batch_processor = BatchProcessor()


def batch_process(batch_size: int = 10, max_wait_time: float = 0.5):
    """
    Decorador para procesar items en lotes
    
    Args:
        batch_size: Tamaño del lote
        max_wait_time: Tiempo máximo de espera antes de procesar
    """
    def decorator(func: Callable) -> Callable:
        processor = BatchProcessor(batch_size, max_wait_time)
        
        @wraps(func)
        async def wrapper(item: Any):
            return await processor.add_item(item, func)
        
        return wrapper
    return decorator