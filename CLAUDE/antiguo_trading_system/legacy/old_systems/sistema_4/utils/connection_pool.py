"""
Connection Pool para IBKR para optimizar conexiones y prevenir timeouts
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager
import time

from ib_insync import IB

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Configuración de conexión IBKR"""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id_start: int = 100
    max_connections: int = 5
    connection_timeout: float = 10.0
    idle_timeout: float = 300.0  # 5 minutos
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class ConnectionInfo:
    """Información de una conexión"""
    ib: IB
    client_id: int
    created_at: datetime
    last_used: datetime
    is_active: bool = True
    usage_count: int = 0


class IBKRConnectionPool:
    """
    Pool de conexiones para IBKR que maneja múltiples conexiones
    para evitar timeouts y optimizar performance
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connections: Dict[int, ConnectionInfo] = {}
        self.available_connections: asyncio.Queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.is_initialized = False
        
        # Estadísticas
        self.stats = {
            'total_requests': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'recycled_connections': 0,
            'timeouts': 0
        }
        
    async def initialize(self):
        """Inicializa el pool de conexiones"""
        if self.is_initialized:
            return
            
        async with self.lock:
            if self.is_initialized:
                return
                
            logger.info(f"Inicializando pool de conexiones IBKR (max: {self.config.max_connections})")
            
            # Crear conexiones iniciales
            for i in range(min(2, self.config.max_connections)):  # Empezar con 2 conexiones
                await self._create_connection()
            
            self.is_initialized = True
            
            # Iniciar tarea de limpieza
            asyncio.create_task(self._cleanup_task())
    
    async def _create_connection(self) -> Optional[ConnectionInfo]:
        """Crea una nueva conexión IBKR"""
        client_id = self.config.client_id_start + len(self.connections)
        
        try:
            ib = IB()
            await asyncio.wait_for(
                ib.connectAsync(
                    self.config.host,
                    self.config.port,
                    clientId=client_id,
                    timeout=self.config.connection_timeout
                ),
                timeout=self.config.connection_timeout
            )
            
            connection_info = ConnectionInfo(
                ib=ib,
                client_id=client_id,
                created_at=datetime.now(),
                last_used=datetime.now(),
                is_active=True
            )
            
            self.connections[client_id] = connection_info
            await self.available_connections.put(connection_info)
            
            self.stats['active_connections'] += 1
            
            logger.info(f"Conexión IBKR creada: client_id={client_id}")
            return connection_info
            
        except Exception as e:
            logger.error(f"Error creando conexión IBKR {client_id}: {e}")
            self.stats['failed_connections'] += 1
            return None
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager para obtener una conexión del pool
        
        Usage:
            async with connection_pool.get_connection() as ib:
                # Usar la conexión
                positions = await ib.reqPositionsAsync()
        """
        if not self.is_initialized:
            await self.initialize()
        
        self.stats['total_requests'] += 1
        connection_info = None
        
        try:
            # Intentar obtener conexión disponible
            try:
                connection_info = await asyncio.wait_for(
                    self.available_connections.get(),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # Si no hay conexiones disponibles, crear una nueva
                if len(self.connections) < self.config.max_connections:
                    connection_info = await self._create_connection()
                else:
                    # Esperar por una conexión disponible
                    connection_info = await self.available_connections.get()
            
            if not connection_info or not connection_info.is_active:
                raise Exception("No hay conexiones disponibles")
            
            # Verificar que la conexión esté activa
            if not connection_info.ib.isConnected():
                await self._reconnect_connection(connection_info)
            
            # Actualizar estadísticas de uso
            connection_info.last_used = datetime.now()
            connection_info.usage_count += 1
            
            yield connection_info.ib
            
        except Exception as e:
            logger.error(f"Error obteniendo conexión: {e}")
            self.stats['timeouts'] += 1
            raise
            
        finally:
            # Devolver conexión al pool
            if connection_info and connection_info.is_active:
                await self.available_connections.put(connection_info)
    
    async def _reconnect_connection(self, connection_info: ConnectionInfo):
        """Reconecta una conexión desconectada"""
        try:
            await connection_info.ib.connectAsync(
                self.config.host,
                self.config.port,
                clientId=connection_info.client_id,
                timeout=self.config.connection_timeout
            )
            logger.info(f"Conexión IBKR reconectada: client_id={connection_info.client_id}")
            
        except Exception as e:
            logger.error(f"Error reconectando: {e}")
            connection_info.is_active = False
            raise
    
    async def _cleanup_task(self):
        """Tarea de limpieza que se ejecuta periódicamente"""
        while True:
            try:
                await asyncio.sleep(60)  # Limpiar cada minuto
                await self._cleanup_idle_connections()
                await self._log_stats()
                
            except Exception as e:
                logger.error(f"Error en tarea de limpieza: {e}")
    
    async def _cleanup_idle_connections(self):
        """Limpia conexiones inactivas"""
        now = datetime.now()
        idle_threshold = now - timedelta(seconds=self.config.idle_timeout)
        
        async with self.lock:
            connections_to_remove = []
            
            for client_id, conn_info in self.connections.items():
                if (conn_info.last_used < idle_threshold and 
                    conn_info.usage_count > 0):
                    connections_to_remove.append(client_id)
            
            for client_id in connections_to_remove:
                await self._remove_connection(client_id)
                self.stats['recycled_connections'] += 1
    
    async def _remove_connection(self, client_id: int):
        """Remueve una conexión del pool"""
        if client_id in self.connections:
            conn_info = self.connections[client_id]
            
            try:
                if conn_info.ib.isConnected():
                    conn_info.ib.disconnect()
            except Exception as e:
                logger.warning(f"Error desconectando {client_id}: {e}")
            
            del self.connections[client_id]
            self.stats['active_connections'] -= 1
            
            logger.info(f"Conexión IBKR removida: client_id={client_id}")
    
    async def _log_stats(self):
        """Log estadísticas del pool"""
        if self.stats['total_requests'] % 100 == 0:  # Log cada 100 requests
            logger.info(f"Pool stats: {self.stats}")
    
    async def close_all(self):
        """Cierra todas las conexiones"""
        async with self.lock:
            for client_id in list(self.connections.keys()):
                await self._remove_connection(client_id)
            
            self.is_initialized = False
            logger.info("Pool de conexiones IBKR cerrado")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pool"""
        return {
            **self.stats,
            'pool_size': len(self.connections),
            'available_connections': self.available_connections.qsize()
        }


# Instancia global del pool
_connection_pool: Optional[IBKRConnectionPool] = None


def get_connection_pool() -> IBKRConnectionPool:
    """Obtiene la instancia global del pool de conexiones"""
    global _connection_pool
    
    if _connection_pool is None:
        config = ConnectionConfig()
        _connection_pool = IBKRConnectionPool(config)
    
    return _connection_pool


async def initialize_connection_pool(config: Optional[ConnectionConfig] = None):
    """Inicializa el pool de conexiones global"""
    global _connection_pool
    
    if config is None:
        config = ConnectionConfig()
    
    _connection_pool = IBKRConnectionPool(config)
    await _connection_pool.initialize()


async def close_connection_pool():
    """Cierra el pool de conexiones global"""
    global _connection_pool
    
    if _connection_pool:
        await _connection_pool.close_all()
        _connection_pool = None