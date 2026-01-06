"""
Módulo para monitorear el rendimiento y uso de recursos del sistema de trading.
"""

import os
import time
import psutil
import threading
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Monitor de rendimiento para el sistema de trading.
    Recopila métricas de uso de CPU, memoria y tiempo de procesamiento.
    """
    
    def __init__(self, sampling_interval: float = 5.0):
        """
        Inicializar el monitor de rendimiento.
        
        Args:
            sampling_interval: Intervalo en segundos entre muestras de rendimiento
        """
        self.sampling_interval = sampling_interval
        self.process = psutil.Process(os.getpid())
        self.running = False
        
        # OPTIMIZACIONES AÑADIDAS
        self.max_history_size = 500  # Limitar historial
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutos
        self.monitor_thread = None
        
        # Métricas
        self.metrics_history = {
            'timestamp': [],
            'cpu_percent': [],
            'memory_percent': [],
            'memory_mb': [],
            'num_threads': [],
            'strategy_metrics': {}
        }
        
        # Métricas por estrategia
        self.strategy_processing_times = {}  # strategy_id -> list of processing times
        self.strategy_signal_counts = {}     # strategy_id -> count of signals
        
        # Límites para alertas
        self.cpu_threshold = 80.0  # porcentaje
        self.memory_threshold = 70.0  # porcentaje
        
        logger.info("Monitor de rendimiento inicializado")
    
    def start(self):
        """Iniciar el monitoreo en segundo plano"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Monitor de rendimiento iniciado")
    
    def stop(self):
        """Detener el monitoreo"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("Monitor de rendimiento detenido")
    
    def _monitor_loop(self):
        """Bucle principal de monitoreo"""
        while self.running:
            try:
                # Recopilar métricas
                self._collect_metrics()
                
                # Verificar alertas
                self._check_alerts()
                
                # Esperar hasta la próxima muestra
                time.sleep(self.sampling_interval)
            except Exception as e:
                logger.error(f"Error en monitor de rendimiento: {e}")
    
    def _collect_metrics(self):
        """Recopilar métricas de rendimiento"""
        try:
            # Obtener métricas del proceso
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convertir a MB
            num_threads = len(self.process.threads())
            
            # Guardar métricas
            now = datetime.now()
            self.metrics_history['timestamp'].append(now)
            self.metrics_history['cpu_percent'].append(cpu_percent)
            self.metrics_history['memory_percent'].append(memory_percent)
            self.metrics_history['memory_mb'].append(memory_mb)
            self.metrics_history['num_threads'].append(num_threads)
            
            # Limitar historial (mantener últimas 24 horas con muestras cada 5 segundos)
            max_samples = int(24 * 60 * 60 / self.sampling_interval)
            if len(self.metrics_history['timestamp']) > max_samples:
                for key in ['timestamp', 'cpu_percent', 'memory_percent', 'memory_mb', 'num_threads']:
                    self.metrics_history[key] = self.metrics_history[key][-max_samples:]
            
            # Registrar métricas cada 12 muestras (aprox. cada minuto con intervalo de 5s)
            if len(self.metrics_history['timestamp']) % 12 == 0:
                logger.debug(f"Métricas: CPU={cpu_percent:.1f}%, Memoria={memory_mb:.1f}MB ({memory_percent:.1f}%), Hilos={num_threads}")
                
        except Exception as e:
            logger.error(f"Error recopilando métricas: {e}")
    
    def _check_alerts(self):
        """Verificar si hay métricas que superan los umbrales"""
        if not self.metrics_history['cpu_percent']:
            return
        
        # Obtener últimas métricas
        cpu = self.metrics_history['cpu_percent'][-1]
        mem = self.metrics_history['memory_percent'][-1]
        
        # Verificar umbrales
        if cpu > self.cpu_threshold:
            logger.warning(f"ALERTA: Uso de CPU alto ({cpu:.1f}%)")
        
        if mem > self.memory_threshold:
            logger.warning(f"ALERTA: Uso de memoria alto ({mem:.1f}%)")
    
    def record_strategy_processing(self, strategy_id: str, processing_time_ms: float):
        """
        Registrar tiempo de procesamiento para una estrategia
        
        Args:
            strategy_id: ID de la estrategia
            processing_time_ms: Tiempo de procesamiento en milisegundos
        """
        if strategy_id not in self.strategy_processing_times:
            self.strategy_processing_times[strategy_id] = []
        
        self.strategy_processing_times[strategy_id].append(processing_time_ms)
        
        # Limitar historial a 1000 muestras por estrategia
        if len(self.strategy_processing_times[strategy_id]) > 1000:
            self.strategy_processing_times[strategy_id] = self.strategy_processing_times[strategy_id][-1000:]
    
    def record_strategy_signal(self, strategy_id: str):
        """
        Registrar una señal generada por una estrategia
        
        Args:
            strategy_id: ID de la estrategia
        """
        if strategy_id not in self.strategy_signal_counts:
            self.strategy_signal_counts[strategy_id] = 0
        
        self.strategy_signal_counts[strategy_id] += 1
    
    def record_event(self, event_name: str):
        """
        Registrar un evento general del sistema
        
        Args:
            event_name: Nombre del evento (ej: 'scan_started', 'scan_error')
        """
        # Para eventos generales, simplemente los logueamos
        # También podríamos expandir esto para mantener contadores de eventos
        current_time = datetime.now()
        
        if not hasattr(self, 'event_counts'):
            self.event_counts = {}
        
        if event_name not in self.event_counts:
            self.event_counts[event_name] = 0
        
        self.event_counts[event_name] += 1
        
        # Log solo para eventos importantes
        if event_name in ['scan_started', 'scan_error', 'system_startup', 'system_shutdown']:
            logger.debug(f"Event recorded: {event_name} (count: {self.event_counts[event_name]})")
    
    def get_event_counts(self) -> Dict[str, int]:
        """
        Obtener contadores de eventos
        
        Returns:
            Diccionario con contadores de eventos
        """
        return getattr(self, 'event_counts', {})
    
    def get_metrics(self, timeframe: str = 'hour') -> Dict[str, Any]:
        """
        Obtener métricas de rendimiento
        
        Args:
            timeframe: Período de tiempo para las métricas ('hour', 'day', 'all')
            
        Returns:
            Diccionario con métricas de rendimiento
        """
        if not self.metrics_history['timestamp']:
            return {
                'cpu_current': 0,
                'cpu_avg': 0,
                'cpu_max': 0,
                'memory_current_mb': 0,
                'memory_avg_mb': 0,
                'memory_max_mb': 0,
                'memory_current_percent': 0,
                'threads': 0,
                'strategy_metrics': {},
                'event_counts': self.get_event_counts()
            }
        
        # Filtrar por timeframe
        now = datetime.now()
        if timeframe == 'hour':
            cutoff = now - timedelta(hours=1)
        elif timeframe == 'day':
            cutoff = now - timedelta(days=1)
        else:  # 'all'
            cutoff = datetime.min
        
        # Filtrar métricas por tiempo
        timestamps = self.metrics_history['timestamp']
        cpu_values = []
        memory_values = []
        memory_percent_values = []
        
        for i, ts in enumerate(timestamps):
            if ts >= cutoff:
                cpu_values.append(self.metrics_history['cpu_percent'][i])
                memory_values.append(self.metrics_history['memory_mb'][i])
                memory_percent_values.append(self.metrics_history['memory_percent'][i])
        
        # Si no hay datos en el timeframe, usar el último valor disponible
        if not cpu_values:
            cpu_values = [self.metrics_history['cpu_percent'][-1]]
            memory_values = [self.metrics_history['memory_mb'][-1]]
            memory_percent_values = [self.metrics_history['memory_percent'][-1]]
        
        # Calcular métricas de estrategias
        strategy_metrics = {}
        for strategy_id, times in self.strategy_processing_times.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                signal_count = self.strategy_signal_counts.get(strategy_id, 0)
                
                strategy_metrics[strategy_id] = {
                    'avg_processing_time_ms': avg_time,
                    'max_processing_time_ms': max_time,
                    'signal_count': signal_count
                }
        
        # Construir resultado
        return {
            'cpu_current': cpu_values[-1],
            'cpu_avg': sum(cpu_values) / len(cpu_values),
            'cpu_max': max(cpu_values),
            'memory_current_mb': memory_values[-1],
            'memory_avg_mb': sum(memory_values) / len(memory_values),
            'memory_max_mb': max(memory_values),
            'memory_current_percent': memory_percent_values[-1],
            'threads': self.metrics_history['num_threads'][-1] if self.metrics_history['num_threads'] else 0,
            'strategy_metrics': strategy_metrics,
            'event_counts': self.get_event_counts()
        }


# Instancia global para usar en toda la aplicación
performance_monitor = PerformanceMonitor()
