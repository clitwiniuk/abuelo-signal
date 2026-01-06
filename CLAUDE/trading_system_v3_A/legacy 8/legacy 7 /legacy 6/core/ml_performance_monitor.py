#!/usr/bin/env python3
"""
ML Performance Monitor - Sistema de monitoreo y drift detection
Monitorea performance de modelos ML y triggea reentrenamientos automáticos
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import json
from threading import Timer
import asyncio

@dataclass
class PerformanceAlert:
    """Alerta de performance del sistema ML"""
    strategy: str
    alert_type: str  # 'DRIFT', 'ACCURACY_DROP', 'DATA_ISSUE'
    severity: str    # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    current_value: float
    baseline_value: float
    threshold: float
    description: str
    timestamp: datetime

class MLPerformanceMonitor:
    """
    Monitor de performance para modelos ML con drift detection automático
    """
    
    def __init__(self, trading_db_path: str = "trading_data.db"):
        self.trading_db_path = trading_db_path
        self.logger = logging.getLogger(__name__)
        
        # Thresholds para alertas
        self.thresholds = {
            'accuracy_drop': 0.15,      # 15% drop in accuracy
            'precision_drop': 0.20,     # 20% drop in precision
            'data_staleness_days': 7,   # Data older than 7 days
            'min_samples_for_eval': 20, # Minimum samples for evaluation
            'critical_accuracy': 0.50   # Below 50% accuracy = critical
        }
        
        # Performance history
        self.performance_history = {}
        self.baseline_performance = {}
        
        # Monitoring timer
        self._monitor_timer = None
        self._monitoring_active = False
        
    def start_monitoring(self, interval_hours: int = 6):
        """Inicia monitoreo automático cada N horas"""
        if self._monitoring_active:
            self.logger.warning("Performance monitoring already active")
            return
            
        self._monitoring_active = True
        self._schedule_next_check(interval_hours * 3600)  # Convert to seconds
        
        self.logger.info(f"🔍 Performance monitoring started (interval: {interval_hours}h)")
        
    def stop_monitoring(self):
        """Detiene el monitoreo automático"""
        if self._monitor_timer:
            self._monitor_timer.cancel()
            self._monitor_timer = None
            
        self._monitoring_active = False
        self.logger.info("🛑 Performance monitoring stopped")
        
    def _schedule_next_check(self, interval_seconds: int):
        """Programa la siguiente verificación de performance"""
        if not self._monitoring_active:
            return
            
        self._monitor_timer = Timer(interval_seconds, self._perform_monitoring_check)
        self._monitor_timer.daemon = True
        self._monitor_timer.start()
        
    def _perform_monitoring_check(self):
        """Ejecuta verificación de performance"""
        try:
            self.logger.info("🔍 Performing automated performance check...")
            
            # Get current performance metrics
            current_metrics = self.calculate_current_performance()
            
            # Check for alerts
            alerts = self.detect_performance_issues(current_metrics)
            
            # Process alerts
            for alert in alerts:
                self._handle_performance_alert(alert)
            
            # Update performance history
            self._update_performance_history(current_metrics)
            
            # Schedule next check
            if self._monitoring_active:
                self._schedule_next_check(6 * 3600)  # 6 hours
                
        except Exception as e:
            self.logger.error(f"❌ Error in monitoring check: {e}")
            # Retry in 1 hour on error
            if self._monitoring_active:
                self._schedule_next_check(3600)
                
    def calculate_current_performance(self) -> Dict[str, Dict[str, float]]:
        """
        Calcula métricas de performance actuales para todas las estrategias
        """
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                # Get recent performance data (last 30 days)
                query = """
                    SELECT 
                        vf.strategy,
                        COUNT(*) as total_predictions,
                        AVG(CASE WHEN vf.trade_success THEN 1.0 ELSE 0.0 END) as accuracy,
                        AVG(CASE WHEN vf.trade_success THEN 1.0 ELSE 0.0 END) as precision,
                        AVG(CASE WHEN vf.trade_success THEN 1.0 ELSE 0.0 END) as recall,
                        AVG(vf.pnl) as avg_pnl,
                        COUNT(DISTINCT DATE(vf.feedback_time)) as active_days
                    FROM volume_feedback vf
                    WHERE vf.feedback_time >= date('now', '-30 days')
                    GROUP BY vf.strategy
                """
                
                df = pd.read_sql_query(query, conn)
                
                # Convert to nested dictionary format
                performance = {}
                for _, row in df.iterrows():
                    strategy = row['strategy']
                    performance[strategy] = {
                        'accuracy': row['accuracy'],
                        'precision': row['precision'],
                        'recall': row['recall'],
                        'total_samples': row['total_predictions'],
                        'avg_pnl': row['avg_pnl'],
                        'active_days': row['active_days'],
                        'f1_score': 2 * (row['precision'] * row['recall']) / (row['precision'] + row['recall']) if (row['precision'] + row['recall']) > 0 else 0
                    }
                
                return performance
                
        except Exception as e:
            self.logger.error(f"❌ Error calculating performance: {e}")
            return {}
            
    def detect_performance_issues(self, current_metrics: Dict[str, Dict[str, float]]) -> List[PerformanceAlert]:
        """Detecta problemas de performance y genera alertas"""
        alerts = []
        
        for strategy, metrics in current_metrics.items():
            try:
                # Get baseline performance
                baseline = self.baseline_performance.get(strategy, {})
                
                # Check accuracy drop
                current_accuracy = metrics.get('accuracy', 0)
                baseline_accuracy = baseline.get('accuracy', current_accuracy)
                
                if baseline_accuracy > 0:
                    accuracy_drop = (baseline_accuracy - current_accuracy) / baseline_accuracy
                    
                    if accuracy_drop >= self.thresholds['accuracy_drop']:
                        severity = 'CRITICAL' if current_accuracy < self.thresholds['critical_accuracy'] else 'HIGH'
                        
                        alerts.append(PerformanceAlert(
                            strategy=strategy,
                            alert_type='ACCURACY_DROP',
                            severity=severity,
                            current_value=current_accuracy,
                            baseline_value=baseline_accuracy,
                            threshold=self.thresholds['accuracy_drop'],
                            description=f"Accuracy dropped {accuracy_drop:.2%} from baseline",
                            timestamp=datetime.now()
                        ))
                
                # Check insufficient data
                if metrics.get('total_samples', 0) < self.thresholds['min_samples_for_eval']:
                    alerts.append(PerformanceAlert(
                        strategy=strategy,
                        alert_type='DATA_ISSUE',
                        severity='MEDIUM',
                        current_value=metrics.get('total_samples', 0),
                        baseline_value=self.thresholds['min_samples_for_eval'],
                        threshold=self.thresholds['min_samples_for_eval'],
                        description=f"Insufficient samples for reliable evaluation",
                        timestamp=datetime.now()
                    ))
                
                # Check data staleness
                active_days = metrics.get('active_days', 0)
                if active_days == 0:
                    alerts.append(PerformanceAlert(
                        strategy=strategy,
                        alert_type='DATA_ISSUE',
                        severity='HIGH',
                        current_value=0,
                        baseline_value=1,
                        threshold=1,
                        description="No recent trading activity for strategy",
                        timestamp=datetime.now()
                    ))
                
            except Exception as e:
                self.logger.error(f"❌ Error detecting issues for {strategy}: {e}")
                
        return alerts
        
    def _handle_performance_alert(self, alert: PerformanceAlert):
        """Maneja una alerta de performance"""
        try:
            # Log the alert
            severity_emoji = {
                'LOW': '🟡',
                'MEDIUM': '🟠', 
                'HIGH': '🔴',
                'CRITICAL': '🚨'
            }
            
            emoji = severity_emoji.get(alert.severity, '⚠️')
            
            self.logger.warning(
                f"{emoji} PERFORMANCE ALERT [{alert.severity}] {alert.strategy}: "
                f"{alert.alert_type} - {alert.description}"
            )
            
            # Store alert in database
            self._store_performance_alert(alert)
            
            # Take action based on severity
            if alert.severity in ['HIGH', 'CRITICAL']:
                if alert.alert_type == 'ACCURACY_DROP':
                    self._trigger_emergency_retrain(alert.strategy)
                    
            elif alert.severity == 'MEDIUM':
                if alert.alert_type == 'DATA_ISSUE':
                    self._trigger_data_collection_review(alert.strategy)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling performance alert: {e}")
            
    def _store_performance_alert(self, alert: PerformanceAlert):
        """Almacena alerta en base de datos"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO performance_alerts (
                        strategy, alert_type, severity, current_value, baseline_value,
                        threshold_value, description, alert_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.strategy, alert.alert_type, alert.severity,
                    alert.current_value, alert.baseline_value, alert.threshold,
                    alert.description, alert.timestamp
                ))
                
                # Create table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS performance_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy TEXT,
                        alert_type TEXT,
                        severity TEXT,
                        current_value REAL,
                        baseline_value REAL,
                        threshold_value REAL,
                        description TEXT,
                        alert_time TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_time TIMESTAMP
                    )
                """)
                
        except Exception as e:
            self.logger.error(f"❌ Error storing alert: {e}")
            
    def _trigger_emergency_retrain(self, strategy: str):
        """Triggea reentrenamiento de emergencia para una estrategia"""
        try:
            self.logger.warning(f"🚨 Triggering emergency retrain for {strategy}")
            
            # Import here to avoid circular imports
            from core.continuous_learning_engine import get_global_learning_engine
            
            learning_engine = get_global_learning_engine()
            
            # Force immediate retrain
            learning_engine.force_retrain()
            
            self.logger.info(f"🔄 Emergency retrain completed for {strategy}")
            
        except Exception as e:
            self.logger.error(f"❌ Error triggering emergency retrain: {e}")
            
    def _trigger_data_collection_review(self, strategy: str):
        """Triggea revisión de recolección de datos"""
        self.logger.info(f"📊 Data collection review needed for {strategy}")
        
        # Log the need for data collection review
        with sqlite3.connect(self.trading_db_path) as conn:
            conn.execute("""
                INSERT INTO learning_events (event_type, description, strategies_affected)
                VALUES ('DATA_REVIEW_NEEDED', ?, ?)
            """, (
                f"Strategy {strategy} needs more data for reliable performance evaluation",
                json.dumps([strategy])
            ))
            
    def _update_performance_history(self, metrics: Dict[str, Dict[str, float]]):
        """Actualiza historial de performance"""
        try:
            timestamp = datetime.now()
            
            for strategy, strategy_metrics in metrics.items():
                if strategy not in self.performance_history:
                    self.performance_history[strategy] = []
                
                # Add timestamp to metrics
                timestamped_metrics = strategy_metrics.copy()
                timestamped_metrics['timestamp'] = timestamp.isoformat()
                
                self.performance_history[strategy].append(timestamped_metrics)
                
                # Keep only last 30 entries (30 monitoring cycles)
                if len(self.performance_history[strategy]) > 30:
                    self.performance_history[strategy] = self.performance_history[strategy][-30:]
                
                # Update baseline if this is better performance
                current_accuracy = strategy_metrics.get('accuracy', 0)
                baseline_accuracy = self.baseline_performance.get(strategy, {}).get('accuracy', 0)
                
                if current_accuracy > baseline_accuracy:
                    self.baseline_performance[strategy] = strategy_metrics.copy()
                    
        except Exception as e:
            self.logger.error(f"❌ Error updating performance history: {e}")
            
    def get_performance_summary(self) -> Dict[str, any]:
        """Obtiene resumen de performance actual"""
        try:
            current_metrics = self.calculate_current_performance()
            alerts = self.detect_performance_issues(current_metrics)
            
            return {
                'monitoring_active': self._monitoring_active,
                'last_check': datetime.now().isoformat(),
                'strategies_monitored': len(current_metrics),
                'active_alerts': len([a for a in alerts if a.severity in ['HIGH', 'CRITICAL']]),
                'total_alerts': len(alerts),
                'average_accuracy': np.mean([m.get('accuracy', 0) for m in current_metrics.values()]) if current_metrics else 0,
                'alerts_by_severity': {
                    severity: len([a for a in alerts if a.severity == severity])
                    for severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
                },
                'performance_trends': self._calculate_performance_trends()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting performance summary: {e}")
            return {'error': str(e)}
            
    def _calculate_performance_trends(self) -> Dict[str, str]:
        """Calcula tendencias de performance (improving, stable, declining)"""
        trends = {}
        
        for strategy, history in self.performance_history.items():
            if len(history) < 2:
                trends[strategy] = 'insufficient_data'
                continue
                
            # Compare recent vs older accuracy
            recent_accuracy = np.mean([h.get('accuracy', 0) for h in history[-5:]])  # Last 5 checks
            older_accuracy = np.mean([h.get('accuracy', 0) for h in history[:5]])    # First 5 checks
            
            if recent_accuracy > older_accuracy * 1.05:  # 5% improvement
                trends[strategy] = 'improving'
            elif recent_accuracy < older_accuracy * 0.95:  # 5% decline
                trends[strategy] = 'declining'
            else:
                trends[strategy] = 'stable'
                
        return trends

# Global monitor instance
_global_performance_monitor = None

def get_global_performance_monitor() -> MLPerformanceMonitor:
    """Obtiene instancia global del performance monitor"""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = MLPerformanceMonitor()
    return _global_performance_monitor