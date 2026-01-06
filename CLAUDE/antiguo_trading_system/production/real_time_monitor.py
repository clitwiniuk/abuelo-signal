# production/real_time_monitor.py
"""
Monitor en Tiempo Real para Sistema Smallcaps Intraday
Aprovecha HybridConfigManager y AlertSystem para monitoreo completo
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path

# Aprovechar sistema híbrido y alertas
from production.hybrid_config_manager import HybridConfigManager
from production.alert_system import SmallcapAlertSystem, AlertLevel, Alert

@dataclass
class SystemMetrics:
    """Métricas del sistema en tiempo real"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    operations_per_minute: int
    error_rate_percent: float
    scanner_latency_ms: float
    positions_count: int
    pnl_today: float
    alerts_sent_last_hour: int

@dataclass
class TradingMetrics:
    """Métricas específicas de trading"""
    timestamp: datetime
    scans_completed: int
    plays_found: int
    positions_opened: int
    positions_closed: int
    win_rate_percent: float
    avg_hold_time_minutes: float
    best_performer: Optional[str]
    worst_performer: Optional[str]
    total_pnl: float
    daily_volume_processed: int

class SmallcapRealTimeMonitor:
    """
    Monitor en tiempo real para sistema de smallcaps intraday
    Integra con HybridConfigManager y AlertSystem
    """
    
    def __init__(self):
        self.logger = logging.getLogger("RealTimeMonitor")
        
        # Cargar configuración híbrida
        try:
            self.hybrid_config = HybridConfigManager()
            self.config = self._load_monitor_config()
            self.logger.info("✅ Configuración híbrida cargada para monitor")
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración: {e}")
            raise
        
        # Sistema de alertas
        try:
            self.alert_system = SmallcapAlertSystem(self.config.get("alerts"))
            self.logger.info("✅ Sistema de alertas inicializado")
        except Exception as e:
            self.logger.error(f"❌ Error inicializando alertas: {e}")
            self.alert_system = None
        
        # Estado del monitor
        self.is_monitoring = False
        self.metrics_history = []
        self.trading_history = []
        self.start_time = None
        self.last_metrics = None
        
        # Contadores
        self.operation_counter = 0
        self.error_counter = 0
        self.alert_counter = 0
        
        # Thread safety
        self.metrics_lock = threading.Lock()
        
    def _load_monitor_config(self) -> Dict[str, Any]:
        """Cargar configuración de monitoreo usando sistema híbrido"""
        complete_config = self.hybrid_config.get_complete_hybrid_config()
        production_ext = complete_config["production_extensions"]
        
        return {
            # Configuración de monitoreo desde extensiones
            "monitoring": production_ext["production_monitoring"],
            
            # Alertas desde extensiones
            "alerts": production_ext["production_alerts"],
            
            # Thresholds específicos para smallcaps intraday
            "performance_thresholds": {
                "max_cpu_percent": 80.0,
                "max_memory_percent": 70.0,
                "max_memory_mb": 500.0,
                "max_scanner_latency_ms": 5000.0,
                "min_operations_per_minute": 1.0,
                "max_error_rate_percent": 5.0,
                "max_positions": 10,
                "daily_loss_limit": -100.0
            },
            
            # Trading específico desde config.ini
            "trading_config": self.hybrid_config.get_trading_params(),
            "smallcap_config": self.hybrid_config.get_smallcap_strategy_config(),
            
            # Configuración de archivos
            "files": {
                "metrics_log": "logs/real_time_metrics.jsonl",
                "status_file": "production/status.json",
                "dashboard_data": "production/dashboard_data.json"
            }
        }
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Recopilar métricas del sistema"""
        # Métricas de sistema
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Métricas de red (simuladas)
        active_connections = len(psutil.net_connections())
        
        # Métricas de aplicación (desde contadores)
        with self.metrics_lock:
            operations_per_minute = self.operation_counter * 60 / max(
                (datetime.now() - self.start_time).total_seconds(), 1
            ) if self.start_time else 0
            
            error_rate = (self.error_counter / max(self.operation_counter, 1)) * 100
        
        # Simular métricas específicas de trading
        scanner_latency = 150.0  # ms - sería medido en scanner real
        positions_count = 3  # Sería obtenido del mayordomo
        pnl_today = 45.67  # Sería calculado desde posiciones
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024*1024),
            disk_usage_percent=disk.percent,
            active_connections=active_connections,
            operations_per_minute=operations_per_minute,
            error_rate_percent=error_rate,
            scanner_latency_ms=scanner_latency,
            positions_count=positions_count,
            pnl_today=pnl_today,
            alerts_sent_last_hour=self.alert_counter
        )
    
    def _collect_trading_metrics(self) -> TradingMetrics:
        """Recopilar métricas específicas de trading"""
        # En implementación real, estos datos vendrían de:
        # - Scanner híbrido
        # - Mayordomo de posiciones
        # - ML Engine
        # - Base de datos de trades
        
        return TradingMetrics(
            timestamp=datetime.now(),
            scans_completed=147,  # Desde scanner
            plays_found=23,       # Desde scanner + filtros
            positions_opened=5,   # Desde mayordomo
            positions_closed=2,   # Desde mayordomo
            win_rate_percent=65.0, # Calculado desde historial
            avg_hold_time_minutes=45.3, # Desde historial de posiciones
            best_performer="HYPE", # Desde análisis de posiciones
            worst_performer="FAIL", # Desde análisis de posiciones
            total_pnl=123.45,     # Suma de todas las posiciones
            daily_volume_processed=2500000 # Volumen total procesado
        )
    
    async def _check_performance_thresholds(self, metrics: SystemMetrics):
        """Verificar thresholds y enviar alertas si es necesario"""
        if not self.alert_system:
            return
        
        thresholds = self.config["performance_thresholds"]
        
        # CPU threshold
        if metrics.cpu_percent > thresholds["max_cpu_percent"]:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Alto uso de CPU",
                message=f"CPU en {metrics.cpu_percent:.1f}% (límite: {thresholds['max_cpu_percent']:.1f}%)",
                component="SystemMonitor",
                timestamp=datetime.now(),
                data={"cpu_percent": metrics.cpu_percent}
            )
            await self.alert_system.send_alert(alert)
        
        # Memory threshold
        if metrics.memory_percent > thresholds["max_memory_percent"]:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Alto uso de memoria",
                message=f"Memoria en {metrics.memory_percent:.1f}% (límite: {thresholds['max_memory_percent']:.1f}%)",
                component="SystemMonitor",
                timestamp=datetime.now(),
                data={"memory_percent": metrics.memory_percent}
            )
            await self.alert_system.send_alert(alert)
        
        # Scanner latency threshold
        if metrics.scanner_latency_ms > thresholds["max_scanner_latency_ms"]:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="Latencia alta del scanner",
                message=f"Scanner latency: {metrics.scanner_latency_ms:.0f}ms (límite: {thresholds['max_scanner_latency_ms']:.0f}ms)",
                component="HybridScanner",
                timestamp=datetime.now(),
                data={"latency_ms": metrics.scanner_latency_ms}
            )
            await self.alert_system.send_alert(alert)
        
        # Error rate threshold
        if metrics.error_rate_percent > thresholds["max_error_rate_percent"]:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="Alta tasa de errores",
                message=f"Error rate: {metrics.error_rate_percent:.1f}% (límite: {thresholds['max_error_rate_percent']:.1f}%)",
                component="SystemMonitor",
                timestamp=datetime.now(),
                data={"error_rate": metrics.error_rate_percent}
            )
            await self.alert_system.send_alert(alert)
        
        # PnL threshold
        if metrics.pnl_today < thresholds["daily_loss_limit"]:
            alert = Alert(
                level=AlertLevel.EMERGENCY,
                title="Límite de pérdida diaria alcanzado",
                message=f"P&L hoy: ${metrics.pnl_today:.2f} (límite: ${thresholds['daily_loss_limit']:.2f})",
                component="RiskManager",
                timestamp=datetime.now(),
                data={"pnl_today": metrics.pnl_today}
            )
            await self.alert_system.send_alert(alert)
    
    def _save_metrics_to_file(self, system_metrics: SystemMetrics, trading_metrics: TradingMetrics):
        """Guardar métricas en archivos"""
        try:
            # Crear directorios si no existen
            os.makedirs("logs", exist_ok=True)
            os.makedirs("production", exist_ok=True)
            
            # Guardar en log de métricas (JSONL)
            metrics_log = self.config["files"]["metrics_log"]
            with open(metrics_log, 'a') as f:
                combined_metrics = {
                    "system": asdict(system_metrics),
                    "trading": asdict(trading_metrics)
                }
                f.write(json.dumps(combined_metrics, default=str) + '\n')
            
            # Actualizar archivo de status
            status_file = self.config["files"]["status_file"]
            status_data = {
                "is_running": self.is_monitoring,
                "last_update": datetime.now().isoformat(),
                "scan_count": trading_metrics.scans_completed,
                "total_plays_found": trading_metrics.plays_found,
                "positions_count": system_metrics.positions_count,
                "pnl_today": system_metrics.pnl_today,
                "ibkr_connected": True,  # Sería verificado en implementación real
                "ml_engine_enabled": True,  # Sería verificado en implementación real
                "last_scan_time": datetime.now().isoformat(),
                "system_health": "healthy" if system_metrics.error_rate_percent < 5 else "degraded"
            }
            
            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2, default=str)
            
            # Actualizar datos del dashboard
            dashboard_file = self.config["files"]["dashboard_data"]
            dashboard_data = {
                "timestamp": datetime.now().isoformat(),
                "system_metrics": asdict(system_metrics),
                "trading_metrics": asdict(trading_metrics),
                "performance_summary": {
                    "system_status": "healthy" if system_metrics.error_rate_percent < 5 else "warning",
                    "trading_status": "active" if trading_metrics.positions_opened > 0 else "monitoring",
                    "daily_performance": system_metrics.pnl_today,
                    "win_rate": trading_metrics.win_rate_percent
                }
            }
            
            with open(dashboard_file, 'w') as f:
                json.dump(dashboard_data, f, indent=2, default=str)
                
        except Exception as e:
            self.logger.error(f"Error guardando métricas: {e}")
    
    async def _monitoring_cycle(self):
        """Ciclo principal de monitoreo"""
        try:
            # Recopilar métricas
            system_metrics = self._collect_system_metrics()
            trading_metrics = self._collect_trading_metrics()
            
            # Guardar en historial
            with self.metrics_lock:
                self.metrics_history.append(system_metrics)
                self.trading_history.append(trading_metrics)
                
                # Mantener solo últimas 1000 métricas
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                if len(self.trading_history) > 1000:
                    self.trading_history = self.trading_history[-1000:]
            
            # Verificar thresholds y enviar alertas
            await self._check_performance_thresholds(system_metrics)
            
            # Guardar en archivos
            self._save_metrics_to_file(system_metrics, trading_metrics)
            
            # Actualizar última métrica
            self.last_metrics = system_metrics
            
            # Log periódico
            if system_metrics.timestamp.second % 30 == 0:  # Cada 30 segundos
                self.logger.info(
                    f"📊 Monitor: CPU {system_metrics.cpu_percent:.1f}%, "
                    f"Mem {system_metrics.memory_percent:.1f}%, "
                    f"P&L ${system_metrics.pnl_today:.2f}, "
                    f"Pos {system_metrics.positions_count}"
                )
            
            # Simular actividad
            with self.metrics_lock:
                self.operation_counter += 1
                
                # Simular errores ocasionales
                if self.operation_counter % 50 == 0:
                    self.error_counter += 1
                
                # Simular alertas ocasionales
                if self.operation_counter % 100 == 0:
                    self.alert_counter += 1
                    
        except Exception as e:
            self.logger.error(f"Error en ciclo de monitoreo: {e}")
            with self.metrics_lock:
                self.error_counter += 1
    
    async def start_monitoring(self):
        """Iniciar monitoreo en tiempo real"""
        if self.is_monitoring:
            self.logger.warning("Monitor ya está ejecutándose")
            return
        
        self.logger.info("🚀 INICIANDO MONITOR EN TIEMPO REAL")
        self.is_monitoring = True
        self.start_time = datetime.now()
        
        # Configurar intervalo de monitoreo
        monitoring_config = self.config["monitoring"]
        interval = monitoring_config.get("metrics_collection_interval", 5)  # segundos
        
        try:
            while self.is_monitoring:
                await self._monitoring_cycle()
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            self.logger.info("Monitor cancelado")
        except Exception as e:
            self.logger.error(f"Error en monitoreo: {e}")
        finally:
            self.is_monitoring = False
            self.logger.info("🛑 Monitor detenido")
    
    def stop_monitoring(self):
        """Detener monitoreo"""
        self.logger.info("⏹️ Deteniendo monitor...")
        self.is_monitoring = False
    
    def get_current_status(self) -> Dict[str, Any]:
        """Obtener status actual del sistema"""
        if not self.last_metrics:
            return {"status": "no_data", "message": "Monitor no ha recopilado datos aún"}
        
        with self.metrics_lock:
            trading_latest = self.trading_history[-1] if self.trading_history else None
        
        status = {
            "monitoring_active": self.is_monitoring,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "system_metrics": asdict(self.last_metrics),
            "trading_metrics": asdict(trading_latest) if trading_latest else None,
            "operation_count": self.operation_counter,
            "error_count": self.error_counter,
            "alert_count": self.alert_counter,
            "health_status": "healthy" if self.last_metrics.error_rate_percent < 5 else "degraded"
        }
        
        return status
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtener resumen de performance"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        with self.metrics_lock:
            recent_metrics = self.metrics_history[-60:]  # Último minuto
            
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            avg_latency = sum(m.scanner_latency_ms for m in recent_metrics) / len(recent_metrics)
            avg_ops_per_min = sum(m.operations_per_minute for m in recent_metrics) / len(recent_metrics)
        
        return {
            "period_minutes": 1,
            "avg_cpu_percent": avg_cpu,
            "avg_memory_percent": avg_memory,
            "avg_scanner_latency_ms": avg_latency,
            "avg_operations_per_minute": avg_ops_per_min,
            "total_operations": self.operation_counter,
            "total_errors": self.error_counter,
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
        }

# Función de conveniencia para uso externo
_monitor_instance = None

def get_monitor_instance() -> SmallcapRealTimeMonitor:
    """Obtener instancia singleton del monitor"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SmallcapRealTimeMonitor()
    return _monitor_instance

async def start_monitoring():
    """Iniciar monitoreo en tiempo real"""
    monitor = get_monitor_instance()
    await monitor.start_monitoring()

def stop_monitoring():
    """Detener monitoreo"""
    monitor = get_monitor_instance()
    monitor.stop_monitoring()

def get_system_status() -> Dict[str, Any]:
    """Obtener status actual del sistema"""
    monitor = get_monitor_instance()
    return monitor.get_current_status()

async def main():
    """Función principal para testing del monitor"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = SmallcapRealTimeMonitor()
    
    print("🚀 INICIANDO MONITOR EN TIEMPO REAL - DEMO")
    print("=" * 60)
    print("Presiona Ctrl+C para detener...")
    
    try:
        # Ejecutar por 30 segundos para demo
        monitoring_task = asyncio.create_task(monitor.start_monitoring())
        
        # Esperar y mostrar status cada 10 segundos
        for i in range(3):
            await asyncio.sleep(10)
            status = monitor.get_current_status()
            perf = monitor.get_performance_summary()
            
            print(f"\n📊 STATUS ({i+1}/3):")
            print(f"   Uptime: {status['uptime_seconds']:.1f}s")
            print(f"   Operations: {status['operation_count']}")
            print(f"   Errors: {status['error_count']}")
            print(f"   Health: {status['health_status']}")
            
            if perf.get('avg_cpu_percent'):
                print(f"   Avg CPU: {perf['avg_cpu_percent']:.1f}%")
                print(f"   Avg Mem: {perf['avg_memory_percent']:.1f}%")
                print(f"   Avg Ops/min: {perf['avg_operations_per_minute']:.1f}")
        
        monitoring_task.cancel()
        await monitoring_task
        
        print("\n✅ Demo completado exitosamente")
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 Monitor detenido por usuario")
        return True
    except Exception as e:
        print(f"\n❌ Error en monitor: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)