# production/alert_system.py
"""
Sistema de Alertas para Smallcaps Intraday Production
Aprovecha la infraestructura de logging existente y la extiende
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import smtplib
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from dataclasses import dataclass
from enum import Enum

# Aprovechar logging existente
try:
    from utils.log_config import configure_strategy_logging
except ImportError:
    def configure_strategy_logging(loggers):
        pass  # Fallback

class AlertLevel(Enum):
    """Niveles de alerta"""
    INFO = "INFO"
    WARNING = "WARNING" 
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"

@dataclass
class Alert:
    """Estructura de alerta"""
    level: AlertLevel
    title: str
    message: str
    component: str
    timestamp: datetime
    data: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data or {}
        }

class SmallcapAlertSystem:
    """
    Sistema de alertas optimizado para smallcaps intraday
    Aprovecha infraestructura de logging existente
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger("SmallcapAlerts")
        self.config = config or self._get_default_config()
        
        # Estado del sistema de alertas
        self.alerts_sent = {}
        self.alert_history = []
        self.rate_limits = {}
        
        # Configurar canales de alerta
        self.channels = {
            "slack": self._setup_slack_channel(),
            "email": self._setup_email_channel(),
            "file": self._setup_file_channel(),
            "console": self._setup_console_channel()
        }
        
        self.logger.info("🚨 Sistema de alertas SmallcapAlertSystem inicializado")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto optimizada para smallcaps"""
        return {
            # Configuración de canales
            "slack": {
                "enabled": bool(os.getenv("SLACK_WEBHOOK_URL")),
                "webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
                "channel": "#smallcap-trading",
                "username": "SmallcapBot",
                "icon_emoji": ":chart_with_upwards_trend:"
            },
            
            "email": {
                "enabled": bool(os.getenv("EMAIL_SMTP_SERVER")),
                "smtp_server": os.getenv("EMAIL_SMTP_SERVER", ""),
                "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
                "username": os.getenv("EMAIL_USERNAME", ""),
                "password": os.getenv("EMAIL_PASSWORD", ""),
                "from_email": os.getenv("EMAIL_FROM", "smallcap-system@trading.com"),
                "to_emails": os.getenv("EMAIL_TO", "").split(",") if os.getenv("EMAIL_TO") else []
            },
            
            "file": {
                "enabled": True,
                "alerts_file": "logs/smallcap_alerts.log",
                "max_size_mb": 50,
                "backup_count": 10
            },
            
            "console": {
                "enabled": True,
                "colored_output": True
            },
            
            # Rate limiting para evitar spam
            "rate_limits": {
                "INFO": {"max_per_hour": 60, "cooldown_minutes": 1},
                "WARNING": {"max_per_hour": 20, "cooldown_minutes": 5},
                "CRITICAL": {"max_per_hour": 10, "cooldown_minutes": 10},
                "EMERGENCY": {"max_per_hour": 5, "cooldown_minutes": 30}
            },
            
            # Alertas específicas para smallcaps
            "smallcap_alerts": {
                "exceptional_play_found": {
                    "enabled": True,
                    "min_gap": 0.15,  # 15% gap para alerta
                    "min_volume_ratio": 5.0,  # 5x volumen
                    "min_quality_score": 8.0  # Score > 8
                },
                "position_opened": {
                    "enabled": True,
                    "alert_level": "INFO"
                },
                "position_closed": {
                    "enabled": True,
                    "alert_level": "INFO"
                },
                "risk_limit_exceeded": {
                    "enabled": True,
                    "alert_level": "CRITICAL"
                },
                "scanner_failure": {
                    "enabled": True,
                    "alert_level": "CRITICAL"
                },
                "connection_lost": {
                    "enabled": True,
                    "alert_level": "EMERGENCY"
                }
            }
        }
    
    def _setup_slack_channel(self) -> Dict[str, Any]:
        """Setup canal Slack"""
        return {
            "enabled": self.config["slack"]["enabled"],
            "send_func": self._send_slack_alert
        }
    
    def _setup_email_channel(self) -> Dict[str, Any]:
        """Setup canal Email"""
        return {
            "enabled": self.config["email"]["enabled"],
            "send_func": self._send_email_alert
        }
    
    def _setup_file_channel(self) -> Dict[str, Any]:
        """Setup canal File (aprovecha logging existente)"""
        return {
            "enabled": self.config["file"]["enabled"],
            "send_func": self._send_file_alert
        }
    
    def _setup_console_channel(self) -> Dict[str, Any]:
        """Setup canal Console"""
        return {
            "enabled": self.config["console"]["enabled"],
            "send_func": self._send_console_alert
        }
    
    def _check_rate_limit(self, alert: Alert) -> bool:
        """Verificar rate limiting"""
        now = datetime.now()
        level = alert.level.value
        
        # Configuración de rate limit para este nivel
        rate_config = self.config["rate_limits"].get(level, {})
        max_per_hour = rate_config.get("max_per_hour", 10)
        cooldown_minutes = rate_config.get("cooldown_minutes", 5)
        
        # Verificar cooldown
        last_sent_key = f"{alert.component}_{level}"
        if last_sent_key in self.alerts_sent:
            last_sent = self.alerts_sent[last_sent_key]
            if (now - last_sent).total_seconds() < cooldown_minutes * 60:
                return False
        
        # Verificar rate limit por hora
        hour_key = f"{level}_{now.hour}"
        if hour_key not in self.rate_limits:
            self.rate_limits[hour_key] = 0
        
        if self.rate_limits[hour_key] >= max_per_hour:
            return False
        
        return True
    
    def _update_rate_limit(self, alert: Alert):
        """Actualizar contadores de rate limiting"""
        now = datetime.now()
        level = alert.level.value
        
        # Actualizar último envío
        last_sent_key = f"{alert.component}_{level}"
        self.alerts_sent[last_sent_key] = now
        
        # Actualizar contador horario
        hour_key = f"{level}_{now.hour}"
        if hour_key not in self.rate_limits:
            self.rate_limits[hour_key] = 0
        self.rate_limits[hour_key] += 1
    
    async def send_alert(self, alert: Alert) -> bool:
        """Enviar alerta por todos los canales habilitados"""
        
        # Verificar rate limiting
        if not self._check_rate_limit(alert):
            self.logger.debug(f"Alerta rate limited: {alert.title}")
            return False
        
        # Agregar a historial
        self.alert_history.append(alert)
        
        # Mantener solo últimas 1000 alertas
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        success = True
        
        # Enviar por cada canal habilitado
        for channel_name, channel_config in self.channels.items():
            if channel_config["enabled"]:
                try:
                    await channel_config["send_func"](alert)
                    self.logger.debug(f"Alerta enviada por {channel_name}: {alert.title}")
                except Exception as e:
                    self.logger.error(f"Error enviando alerta por {channel_name}: {e}")
                    success = False
        
        # Actualizar rate limiting
        self._update_rate_limit(alert)
        
        return success
    
    async def _send_slack_alert(self, alert: Alert):
        """Enviar alerta por Slack"""
        if not self.config["slack"]["webhook_url"]:
            return
        
        # Determinar color basado en nivel
        color_map = {
            "INFO": "#36a64f",      # Verde
            "WARNING": "#ff9500",   # Naranja
            "CRITICAL": "#ff0000",  # Rojo
            "EMERGENCY": "#8B0000"  # Rojo oscuro
        }
        
        # Emoji basado en nivel
        emoji_map = {
            "INFO": ":information_source:",
            "WARNING": ":warning:",
            "CRITICAL": ":exclamation:",
            "EMERGENCY": ":rotating_light:"
        }
        
        payload = {
            "channel": self.config["slack"]["channel"],
            "username": self.config["slack"]["username"],
            "icon_emoji": self.config["slack"]["icon_emoji"],
            "attachments": [{
                "color": color_map.get(alert.level.value, "#000000"),
                "title": f"{emoji_map.get(alert.level.value, '')} {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Componente",
                        "value": alert.component,
                        "short": True
                    },
                    {
                        "title": "Nivel",
                        "value": alert.level.value,
                        "short": True
                    },
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "short": True
                    }
                ],
                "footer": "Smallcap Trading System",
                "ts": int(alert.timestamp.timestamp())
            }]
        }
        
        # Agregar datos adicionales si existen
        if alert.data:
            payload["attachments"][0]["fields"].append({
                "title": "Datos adicionales",
                "value": json.dumps(alert.data, indent=2),
                "short": False
            })
        
        # Enviar webhook
        async with asyncio.timeout(10):
            response = requests.post(
                self.config["slack"]["webhook_url"],
                json=payload,
                timeout=10
            )
            response.raise_for_status()
    
    async def _send_email_alert(self, alert: Alert):
        """Enviar alerta por email"""
        if not self.config["email"]["to_emails"]:
            return
        
        # Crear mensaje
        msg = MimeMultipart()
        msg['From'] = self.config["email"]["from_email"]
        msg['To'] = ", ".join(self.config["email"]["to_emails"])
        msg['Subject'] = f"[{alert.level.value}] Smallcap Alert: {alert.title}"
        
        # Cuerpo del email
        body = f"""
Alerta del Sistema de Trading Smallcaps

Nivel: {alert.level.value}
Componente: {alert.component}
Timestamp: {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}

Mensaje:
{alert.message}
"""
        
        if alert.data:
            body += f"\n\nDatos adicionales:\n{json.dumps(alert.data, indent=2)}"
        
        body += "\n\n---\nSistema de Trading Smallcaps Intraday"
        
        msg.attach(MimeText(body, 'plain'))
        
        # Enviar email
        with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
            server.starttls()
            server.login(self.config["email"]["username"], self.config["email"]["password"])
            server.send_message(msg)
    
    async def _send_file_alert(self, alert: Alert):
        """Enviar alerta a archivo (aprovecha logging existente)"""
        
        # Formatear mensaje para archivo
        alert_data = alert.to_dict()
        alert_line = json.dumps(alert_data)
        
        # Usar logger específico para alertas
        alert_logger = logging.getLogger("smallcap_alerts")
        
        # Log basado en nivel
        if alert.level == AlertLevel.INFO:
            alert_logger.info(alert_line)
        elif alert.level == AlertLevel.WARNING:
            alert_logger.warning(alert_line)
        elif alert.level == AlertLevel.CRITICAL:
            alert_logger.critical(alert_line)
        elif alert.level == AlertLevel.EMERGENCY:
            alert_logger.critical(f"EMERGENCY: {alert_line}")
    
    async def _send_console_alert(self, alert: Alert):
        """Enviar alerta a consola con colores"""
        
        # Colores ANSI si están habilitados
        if self.config["console"]["colored_output"]:
            color_map = {
                "INFO": "\033[92m",      # Verde
                "WARNING": "\033[93m",   # Amarillo
                "CRITICAL": "\033[91m",  # Rojo
                "EMERGENCY": "\033[95m"  # Magenta
            }
            reset = "\033[0m"
            color = color_map.get(alert.level.value, "")
        else:
            color = reset = ""
        
        # Emoji para consola
        emoji_map = {
            "INFO": "ℹ️ ",
            "WARNING": "⚠️ ",
            "CRITICAL": "🚨",
            "EMERGENCY": "🆘"
        }
        
        emoji = emoji_map.get(alert.level.value, "")
        
        # Formatear mensaje
        timestamp = alert.timestamp.strftime("%H:%M:%S")
        console_msg = f"{color}{emoji} [{timestamp}] [{alert.level.value}] {alert.title}: {alert.message}{reset}"
        
        print(console_msg)
    
    # ===== MÉTODOS DE CONVENIENCIA PARA SMALLCAPS =====
    
    async def alert_exceptional_play(self, play_data: Dict[str, Any]):
        """Alerta para play excepcional encontrado"""
        if not self.config["smallcap_alerts"]["exceptional_play_found"]["enabled"]:
            return
        
        gap = play_data.get("gap_percentage", 0)
        volume_ratio = play_data.get("volume_ratio", 0)
        quality_score = play_data.get("quality_score", 0)
        
        # Verificar si cumple criterios para alerta
        min_gap = self.config["smallcap_alerts"]["exceptional_play_found"]["min_gap"]
        min_volume = self.config["smallcap_alerts"]["exceptional_play_found"]["min_volume_ratio"]
        min_quality = self.config["smallcap_alerts"]["exceptional_play_found"]["min_quality_score"]
        
        if gap >= min_gap or volume_ratio >= min_volume or quality_score >= min_quality:
            alert = Alert(
                level=AlertLevel.INFO,
                title=f"🎯 Play Excepcional: {play_data.get('symbol', 'UNKNOWN')}",
                message=f"Gap {gap*100:+.1f}%, Vol {volume_ratio:.1f}x, Score {quality_score:.1f}",
                component="SmallcapScanner",
                timestamp=datetime.now(),
                data=play_data
            )
            
            await self.send_alert(alert)
    
    async def alert_position_opened(self, symbol: str, price: float, size: int):
        """Alerta cuando se abre una posición"""
        if not self.config["smallcap_alerts"]["position_opened"]["enabled"]:
            return
        
        alert = Alert(
            level=AlertLevel.INFO,
            title=f"📈 Posición Abierta: {symbol}",
            message=f"Precio: ${price:.2f}, Tamaño: {size} acciones",
            component="SmallcapMayordomo",
            timestamp=datetime.now(),
            data={"symbol": symbol, "price": price, "size": size}
        )
        
        await self.send_alert(alert)
    
    async def alert_position_closed(self, symbol: str, pnl: float, reason: str):
        """Alerta cuando se cierra una posición"""
        if not self.config["smallcap_alerts"]["position_closed"]["enabled"]:
            return
        
        level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
        emoji = "💰" if pnl >= 0 else "📉"
        
        alert = Alert(
            level=level,
            title=f"{emoji} Posición Cerrada: {symbol}",
            message=f"P&L: ${pnl:+.2f}, Razón: {reason}",
            component="SmallcapMayordomo",
            timestamp=datetime.now(),
            data={"symbol": symbol, "pnl": pnl, "reason": reason}
        )
        
        await self.send_alert(alert)
    
    async def alert_risk_limit_exceeded(self, limit_type: str, current_value: float, limit: float):
        """Alerta cuando se excede un límite de riesgo"""
        alert = Alert(
            level=AlertLevel.CRITICAL,
            title=f"🚨 Límite de Riesgo Excedido: {limit_type}",
            message=f"Valor actual: {current_value:.2f}, Límite: {limit:.2f}",
            component="RiskManager",
            timestamp=datetime.now(),
            data={"limit_type": limit_type, "current_value": current_value, "limit": limit}
        )
        
        await self.send_alert(alert)
    
    async def alert_scanner_failure(self, error_message: str):
        """Alerta cuando el scanner falla"""
        alert = Alert(
            level=AlertLevel.CRITICAL,
            title="❌ Fallo del Scanner",
            message=f"Error: {error_message}",
            component="HybridScanner",
            timestamp=datetime.now(),
            data={"error": error_message}
        )
        
        await self.send_alert(alert)
    
    async def alert_connection_lost(self, connection_type: str):
        """Alerta cuando se pierde conexión crítica"""
        alert = Alert(
            level=AlertLevel.EMERGENCY,
            title=f"🆘 Conexión Perdida: {connection_type}",
            message=f"Conexión {connection_type} perdida. Sistema en modo degradado.",
            component="ConnectionManager",
            timestamp=datetime.now(),
            data={"connection_type": connection_type}
        )
        
        await self.send_alert(alert)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Obtener resumen de alertas"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        
        recent_alerts = [a for a in self.alert_history if a.timestamp >= last_hour]
        
        by_level = {}
        for alert in recent_alerts:
            level = alert.level.value
            if level not in by_level:
                by_level[level] = 0
            by_level[level] += 1
        
        return {
            "total_alerts_sent": len(self.alert_history),
            "alerts_last_hour": len(recent_alerts),
            "alerts_by_level_last_hour": by_level,
            "channels_enabled": [name for name, config in self.channels.items() if config["enabled"]],
            "last_alert": self.alert_history[-1].to_dict() if self.alert_history else None
        }

# Instancia global para uso fácil
smallcap_alerts = SmallcapAlertSystem()

# Funciones de conveniencia
async def send_play_alert(play_data: Dict[str, Any]):
    """Función de conveniencia para alertas de plays"""
    await smallcap_alerts.alert_exceptional_play(play_data)

async def send_position_alert(action: str, symbol: str, **kwargs):
    """Función de conveniencia para alertas de posiciones"""
    if action == "opened":
        await smallcap_alerts.alert_position_opened(symbol, kwargs.get("price", 0), kwargs.get("size", 0))
    elif action == "closed":
        await smallcap_alerts.alert_position_closed(symbol, kwargs.get("pnl", 0), kwargs.get("reason", ""))

async def send_system_alert(alert_type: str, **kwargs):
    """Función de conveniencia para alertas del sistema"""
    if alert_type == "risk_limit":
        await smallcap_alerts.alert_risk_limit_exceeded(
            kwargs.get("limit_type", ""), 
            kwargs.get("current_value", 0), 
            kwargs.get("limit", 0)
        )
    elif alert_type == "scanner_failure":
        await smallcap_alerts.alert_scanner_failure(kwargs.get("error", ""))
    elif alert_type == "connection_lost":
        await smallcap_alerts.alert_connection_lost(kwargs.get("connection_type", ""))

if __name__ == "__main__":
    # Test del sistema de alertas
    async def test_alerts():
        print("🧪 Testing sistema de alertas...")
        
        # Test alerta de play excepcional
        test_play = {
            "symbol": "HYPE",
            "gap_percentage": 0.18,
            "volume_ratio": 6.5,
            "quality_score": 8.5
        }
        
        await send_play_alert(test_play)
        
        # Test alerta de posición
        await send_position_alert("opened", "HYPE", price=5.25, size=1000)
        
        # Test alerta de sistema
        await send_system_alert("scanner_failure", error="Test error message")
        
        print("✅ Tests completados")
    
    asyncio.run(test_alerts())