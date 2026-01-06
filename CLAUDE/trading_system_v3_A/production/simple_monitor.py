# production/simple_monitor.py
"""
Monitor Simple en Tiempo Real para Sistema Smallcaps Intraday
Versión simplificada que aprovecha HybridConfigManager sin dependencias externas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path

# Solo aprovechar sistema híbrido (sin alertas complejas)
from production.hybrid_config_manager import HybridConfigManager

@dataclass
class SimpleSystemMetrics:
    """Métricas simplificadas del sistema"""
    timestamp: datetime
    operations_count: int
    errors_count: int
    uptime_seconds: float
    scans_completed: int
    plays_found: int
    positions_active: int
    pnl_today: float
    system_health: str
    last_operation: str

class SimpleSmallcapMonitor:
    """
    Monitor simplificado para sistema de smallcaps intraday
    Enfocado en métricas de trading sin dependencias externas
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SimpleMonitor")
        
        # Cargar configuración híbrida
        try:
            self.hybrid_config = HybridConfigManager()
            self.config = self._load_simple_config()
            self.logger.info("✅ Configuración híbrida cargada para monitor simple")
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración: {e}")
            raise
        
        # Estado del monitor
        self.is_monitoring = False
        self.start_time = None
        self.metrics_history = []
        
        # Contadores thread-safe
        self.operations_count = 0
        self.errors_count = 0
        self.scans_completed = 0
        self.plays_found = 0
        self.positions_active = 3  # Simulated
        self.pnl_today = 0.0
        self.last_operation = "system_startup"
        
        self.lock = threading.Lock()
        
    def _load_simple_config(self) -> Dict[str, Any]:
        """Cargar configuración simplificada"""
        try:
            complete_config = self.hybrid_config.get_complete_hybrid_config()
            production_ext = complete_config["production_extensions"]
            
            return {
                # Configuración de monitoreo simplificada
                "monitoring_interval": 5,  # segundos
                "metrics_retention": 100,  # número de métricas a mantener
                
                # Thresholds desde extensiones
                "thresholds": production_ext["production_monitoring"]["performance_alert_thresholds"],
                
                # Trading config desde config.ini
                "trading": self.hybrid_config.get_trading_params(),
                "smallcap": self.hybrid_config.get_smallcap_strategy_config(),
                
                # Archivos de output
                "status_file": "production/simple_status.json",
                "metrics_file": "logs/simple_metrics.jsonl"
            }
        except Exception as e:
            self.logger.error(f"Error en configuración: {e}")
            # Configuración fallback
            return {
                "monitoring_interval": 5,
                "metrics_retention": 100,
                "thresholds": {
                    "error_rate_percent": 5.0,
                    "memory_usage_mb": 500
                },
                "status_file": "production/simple_status.json",
                "metrics_file": "logs/simple_metrics.jsonl"
            }
    
    def _collect_metrics(self) -> SimpleSystemMetrics:
        """Recopilar métricas simplificadas"""
        now = datetime.now()
        uptime = (now - self.start_time).total_seconds() if self.start_time else 0
        
        with self.lock:
            # Calcular health basado en error rate
            error_rate = (self.errors_count / max(self.operations_count, 1)) * 100
            health = "healthy" if error_rate < 5.0 else "degraded"
            
            metrics = SimpleSystemMetrics(
                timestamp=now,
                operations_count=self.operations_count,
                errors_count=self.errors_count,
                uptime_seconds=uptime,
                scans_completed=self.scans_completed,
                plays_found=self.plays_found,
                positions_active=self.positions_active,
                pnl_today=self.pnl_today,
                system_health=health,
                last_operation=self.last_operation
            )
        
        return metrics
    
    def _save_metrics(self, metrics: SimpleSystemMetrics):
        """Guardar métricas en archivos"""
        try:
            # Crear directorios
            os.makedirs("logs", exist_ok=True)
            os.makedirs("production", exist_ok=True)
            
            # Guardar métricas en JSONL
            metrics_file = self.config["metrics_file"]
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(asdict(metrics), default=str) + '\n')
            
            # Guardar status actual
            status_file = self.config["status_file"]
            status = {
                "monitoring_active": self.is_monitoring,
                "last_update": metrics.timestamp.isoformat(),
                "system_health": metrics.system_health,
                "operations_total": metrics.operations_count,
                "errors_total": metrics.errors_count,
                "uptime_minutes": metrics.uptime_seconds / 60,
                "scans_completed": metrics.scans_completed,
                "plays_found": metrics.plays_found,
                "positions_active": metrics.positions_active,
                "pnl_today": metrics.pnl_today,
                "last_operation": metrics.last_operation,
                "error_rate_percent": (metrics.errors_count / max(metrics.operations_count, 1)) * 100
            }
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2, default=str)
                
        except Exception as e:
            self.logger.error(f"Error guardando métricas: {e}")
    
    def _check_thresholds(self, metrics: SimpleSystemMetrics):
        """Verificar thresholds y log alertas simples"""
        thresholds = self.config["thresholds"]
        
        error_rate = (metrics.errors_count / max(metrics.operations_count, 1)) * 100
        
        if error_rate > thresholds.get("error_rate_percent", 5.0):
            self.logger.warning(
                f"⚠️ Alta tasa de errores: {error_rate:.1f}% "
                f"(threshold: {thresholds['error_rate_percent']:.1f}%)"
            )
        
        if metrics.pnl_today < -100.0:  # Daily loss limit
            self.logger.critical(
                f"🚨 Límite de pérdida diaria: ${metrics.pnl_today:.2f}"
            )
    
    def simulate_trading_activity(self):
        """Simular actividad de trading para demo"""
        with self.lock:
            self.operations_count += 1
            
            # Simular diferentes operaciones
            if self.operations_count % 10 == 0:
                self.scans_completed += 1
                self.last_operation = "market_scan"
                
                # Simular encontrar plays ocasionalmente
                if self.operations_count % 30 == 0:
                    self.plays_found += 1
                    self.last_operation = "play_found"
                    
                    # Simular cambios en P&L
                    import random
                    pnl_change = random.uniform(-5.0, 10.0)
                    self.pnl_today += pnl_change
            
            elif self.operations_count % 7 == 0:
                self.last_operation = "ml_analysis"
                
            elif self.operations_count % 15 == 0:
                self.last_operation = "position_update"
                
            # Simular errores ocasionales
            if self.operations_count % 50 == 0:
                self.errors_count += 1
                self.last_operation = "error_occurred"
    
    async def _monitoring_cycle(self):
        """Ciclo principal de monitoreo"""
        try:
            # Simular actividad
            self.simulate_trading_activity()
            
            # Recopilar métricas
            metrics = self._collect_metrics()
            
            # Agregar al historial
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.config["metrics_retention"]:
                self.metrics_history = self.metrics_history[-self.config["metrics_retention"]:]
            
            # Verificar thresholds
            self._check_thresholds(metrics)
            
            # Guardar métricas
            self._save_metrics(metrics)
            
            # Log periódico cada 30 segundos
            if metrics.timestamp.second % 30 == 0:
                self.logger.info(
                    f"📊 Status: {metrics.system_health} | "
                    f"Ops: {metrics.operations_count} | "
                    f"Errors: {metrics.errors_count} | "
                    f"Scans: {metrics.scans_completed} | "
                    f"Plays: {metrics.plays_found} | "
                    f"P&L: ${metrics.pnl_today:.2f} | "
                    f"Last: {metrics.last_operation}"
                )
                
        except Exception as e:
            self.logger.error(f"Error en ciclo de monitoreo: {e}")
            with self.lock:
                self.errors_count += 1
                self.last_operation = "monitoring_error"
    
    async def start_monitoring(self, duration_seconds: Optional[int] = None):
        """Iniciar monitoreo"""
        if self.is_monitoring:
            self.logger.warning("Monitor ya está ejecutándose")
            return
        
        self.logger.info("🚀 INICIANDO MONITOR SIMPLE EN TIEMPO REAL")
        self.is_monitoring = True
        self.start_time = datetime.now()
        
        interval = self.config["monitoring_interval"]
        end_time = datetime.now() + timedelta(seconds=duration_seconds) if duration_seconds else None
        
        try:
            while self.is_monitoring:
                await self._monitoring_cycle()
                
                # Verificar si debe terminar
                if end_time and datetime.now() >= end_time:
                    break
                    
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
        self.is_monitoring = False
    
    def get_current_status(self) -> Dict[str, Any]:
        """Obtener status actual"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        return asdict(latest)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas resumidas"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        with self.lock:
            latest = self.metrics_history[-1]
            uptime_hours = latest.uptime_seconds / 3600
            
            # Calcular promedios de última hora (o todos los datos si < 1 hora)
            recent_metrics = [m for m in self.metrics_history 
                            if (latest.timestamp - m.timestamp).total_seconds() <= 3600]
            
            if recent_metrics:
                avg_ops_per_hour = len(recent_metrics) * 60 / max(
                    (latest.timestamp - recent_metrics[0].timestamp).total_seconds() / 60, 1
                )
            else:
                avg_ops_per_hour = 0
        
        return {
            "monitoring_active": self.is_monitoring,
            "uptime_hours": uptime_hours,
            "total_operations": latest.operations_count,
            "total_errors": latest.errors_count,
            "total_scans": latest.scans_completed,
            "total_plays": latest.plays_found,
            "current_positions": latest.positions_active,
            "pnl_today": latest.pnl_today,
            "system_health": latest.system_health,
            "error_rate_percent": (latest.errors_count / max(latest.operations_count, 1)) * 100,
            "avg_operations_per_hour": avg_ops_per_hour,
            "last_operation": latest.last_operation
        }
    
    def print_dashboard(self):
        """Imprimir dashboard en consola"""
        if not self.metrics_history:
            print("📊 Monitor: Sin datos disponibles")
            return
        
        latest = self.metrics_history[-1]
        stats = self.get_summary_stats()
        
        print("\n" + "="*60)
        print("📊 DASHBOARD MONITOR SMALLCAPS INTRADAY")
        print("="*60)
        
        # Status general
        health_emoji = "✅" if latest.system_health == "healthy" else "⚠️"
        print(f"\n{health_emoji} ESTADO GENERAL: {latest.system_health.upper()}")
        print(f"⏱️ Uptime: {stats['uptime_hours']:.1f} horas")
        print(f"🔄 Última operación: {latest.last_operation}")
        
        # Métricas de operaciones
        print(f"\n📈 MÉTRICAS DE OPERACIONES:")
        print(f"   🔢 Total operaciones: {latest.operations_count:,}")
        print(f"   ❌ Total errores: {latest.errors_count}")
        print(f"   📊 Tasa de error: {stats['error_rate_percent']:.2f}%")
        print(f"   ⚡ Ops/hora promedio: {stats['avg_operations_per_hour']:.1f}")
        
        # Métricas de trading
        print(f"\n💼 MÉTRICAS DE TRADING:")
        print(f"   🔍 Scans completados: {latest.scans_completed}")
        print(f"   🎯 Plays encontrados: {latest.plays_found}")
        print(f"   📋 Posiciones activas: {latest.positions_active}")
        
        # Performance financiera
        pnl_emoji = "💰" if latest.pnl_today >= 0 else "📉"
        print(f"\n{pnl_emoji} PERFORMANCE HOY:")
        print(f"   💵 P&L: ${latest.pnl_today:+.2f}")
        
        if latest.plays_found > 0:
            success_rate = (latest.plays_found / max(latest.scans_completed, 1)) * 100
            print(f"   🎯 Success rate: {success_rate:.1f}%")
        
        print("\n" + "="*60)

async def main():
    """Demo del monitor simple"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = SimpleSmallcapMonitor()
    
    print("🚀 DEMO MONITOR SIMPLE SMALLCAPS INTRADAY")
    print("=" * 60)
    print("Ejecutándose por 30 segundos...")
    print("Presiona Ctrl+C para detener antes\n")
    
    try:
        # Crear task de monitoreo
        monitoring_task = asyncio.create_task(
            monitor.start_monitoring(duration_seconds=30)
        )
        
        # Mostrar dashboard cada 10 segundos
        for i in range(3):
            await asyncio.sleep(10)
            print(f"\n📊 DASHBOARD UPDATE {i+1}/3:")
            monitor.print_dashboard()
        
        # Esperar a que termine el monitoreo
        await monitoring_task
        
        # Dashboard final
        print(f"\n📊 DASHBOARD FINAL:")
        monitor.print_dashboard()
        
        # Resumen
        stats = monitor.get_summary_stats()
        print(f"\n✅ DEMO COMPLETADO EXITOSAMENTE")
        print(f"   Operaciones totales: {stats['total_operations']}")
        print(f"   Estado final: {stats['system_health']}")
        print(f"   P&L final: ${stats['pnl_today']:+.2f}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 Demo detenido por usuario")
        monitor.stop_monitoring()
        return True
    except Exception as e:
        print(f"\n❌ Error en demo: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)