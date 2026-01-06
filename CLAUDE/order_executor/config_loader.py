"""
Módulo para cargar y validar la configuración desde archivos YAML.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator, root_validator
from datetime import time
import pytz
import logging

# Configuración básica de logging
logger = logging.getLogger(__name__)

class DatabaseConfig(BaseModel):
    """Configuración de la base de datos."""
    enabled: bool = True
    type: str = "sqlite"
    sqlite_file: str = "trading.db"
    host: str = "localhost"
    port: int = 5432
    name: str = "trading_db"
    user: str = "user"
    password: str = "password"

class EmailConfig(BaseModel):
    """Configuración de notificaciones por email."""
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    recipients: list[str] = []

class SlackConfig(BaseModel):
    """Configuración de notificaciones por Slack."""
    enabled: bool = False
    webhook_url: str = ""
    channel: str = "#trading-alerts"

class NotificationsConfig(BaseModel):
    """Configuración de notificaciones."""
    email: EmailConfig = EmailConfig()
    slack: SlackConfig = SlackConfig()

class TradingHoursConfig(BaseModel):
    """Configuración de horarios de trading."""
    enabled: bool = True
    start: str = "09:30"
    end: str = "16:00"
    timezone: str = "America/New_York"
    
    @validator('start', 'end')
    def validate_time_format(cls, v):
        try:
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Formato de hora inválido: {v}. Use formato HH:MM")
    
    @validator('timezone')
    def validate_timezone(cls, v):
        if v not in pytz.all_timezones:
            raise ValueError(f"Zona horaria no válida: {v}")
        return v

class StrategyConfig(BaseModel):
    """Configuración específica por estrategia."""
    max_position_size_pct: Optional[float] = None
    max_strategy_risk_pct: Optional[float] = None

class RiskConfig(BaseModel):
    """Configuración de gestión de riesgo."""
    max_position_size_pct: float = 10.0
    max_strategy_risk_pct: float = 30.0
    max_daily_loss_pct: float = 2.0
    max_leverage: float = 3.0
    max_orders_per_day: int = 100
    trading_hours: TradingHoursConfig = TradingHoursConfig()
    blacklist: list[str] = []
    strategies: Dict[str, StrategyConfig] = {}

class LoggingConfig(BaseModel):
    """Configuración de logging."""
    level: str = "INFO"
    file: str = "order_executor.log"
    max_size_mb: int = 10
    backup_count: int = 5
    
    @validator('level')
    def validate_log_level(cls, v):
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Nivel de log no válido: {v}")
        return v

class IBKRConfig(BaseModel):
    """Configuración de conexión con IBKR."""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    timeout: int = 30

class Config(BaseModel):
    """Configuración principal de la aplicación."""
    ibkr: IBKRConfig = IBKRConfig()
    risk: RiskConfig = RiskConfig()
    logging: LoggingConfig = LoggingConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    database: DatabaseConfig = DatabaseConfig()
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> 'Config':
        """Carga la configuración desde un archivo YAML."""
        config_path = Path(config_path)
        if not config_path.exists():
            logger.warning(f"Archivo de configuración no encontrado: {config_path}. Usando valores por defecto.")
            return cls()
            
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        
        return cls.parse_obj(config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a un diccionario."""
        return self.dict(exclude_unset=True)

def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Carga la configuración desde el archivo especificado o busca en ubicaciones por defecto.
    
    Args:
        config_path: Ruta al archivo de configuración. Si es None, busca en:
                   - ./config/config.yaml
                   - ~/.order_executor/config.yaml
                   - /etc/order_executor/config.yaml
    
    Returns:
        Config: Objeto de configuración cargado
    """
    # Si no se especifica una ruta, buscar en ubicaciones por defecto
    if config_path is None:
        possible_paths = [
            Path("config/config.yaml"),
            Path.home() / ".order_executor" / "config.yaml",
            Path("/etc/order_executor/config.yaml")
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = path
                logger.info(f"Cargando configuración desde: {config_path}")
                break
        else:
            logger.warning("No se encontró ningún archivo de configuración. Usando valores por defecto.")
            return Config()
    
    # Cargar la configuración
    return Config.from_yaml(config_path)

# Instancia global de configuración
config = load_config()

def get_config() -> Config:
    """
    Obtiene la configuración cargada.
    
    Returns:
        Config: Objeto de configuración
    """
    global config
    return config

def reload_config(config_path: Optional[Union[str, Path]] = None) -> None:
    """
    Recarga la configuración desde el archivo.
    
    Args:
        config_path: Ruta al archivo de configuración. Si es None, usa la ruta por defecto.
    """
    global config
    config = load_config(config_path)
    logger.info("Configuración recargada")
