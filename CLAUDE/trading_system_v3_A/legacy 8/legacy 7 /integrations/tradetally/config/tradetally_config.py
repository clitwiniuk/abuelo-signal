"""
Configuración para TradeTally Integration
"""

import os
from pathlib import Path
from typing import Optional

class TradeTallyConfig:
    """Configuración centralizada para TradeTally"""
    
    def __init__(self):
        # Ruta base del proyecto (4 niveles arriba desde tradetally/config/)
        self.project_root = Path(__file__).parent.parent.parent.parent
        
        # Configuración de API
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        
        # Configuración de base de datos
        self.db_path = str(self.project_root / "trading_data.db")
        
        # Configuración de sincronización
        self.batch_size = int(os.getenv('TRADETALLY_BATCH_SIZE', '10'))
        self.request_delay = float(os.getenv('TRADETALLY_REQUEST_DELAY', '1.0'))
        self.retry_attempts = int(os.getenv('TRADETALLY_RETRY_ATTEMPTS', '3'))
        
        # Configuración de broker
        self.broker_name = os.getenv('TRADETALLY_BROKER_NAME', 'IBKR')
        
    def _get_api_key(self) -> Optional[str]:
        """Obtener API key desde variables de entorno o config.ini"""
        # Prioridad: variable de entorno > config.ini
        api_key = os.getenv('TRADETALLY_API_KEY')
        
        if not api_key:
            # Leer desde config.ini principal
            try:
                import configparser
                config_file = self.project_root / "config.ini"
                if config_file.exists():
                    config = configparser.ConfigParser()
                    config.read(config_file)
                    api_key = config.get('TRADETALLY', 'api_key', fallback=None)
            except Exception as e:
                print(f"Error leyendo config.ini: {e}")
        
        return api_key
    
    def _get_base_url(self) -> str:
        """Obtener URL base de TradeTally"""
        base_url = os.getenv('TRADETALLY_BASE_URL')
        
        if not base_url:
            # Leer desde config.ini principal
            try:
                import configparser
                config_file = self.project_root / "config.ini"
                if config_file.exists():
                    config = configparser.ConfigParser()
                    config.read(config_file)
                    base_url = config.get('TRADETALLY', 'base_url', fallback='https://app.tradetally.com')
            except Exception as e:
                print(f"Error leyendo base_url desde config.ini: {e}")
                base_url = 'https://app.tradetally.com'
        
        return base_url
    
    def is_configured(self) -> bool:
        """Verificar si la configuración está completa"""
        return bool(self.api_key and self.api_key.startswith('tt_live_'))
    
    def get_config_dict(self) -> dict:
        """Obtener configuración como diccionario"""
        return {
            'api_key': self.api_key,
            'base_url': self.base_url,
            'db_path': self.db_path,
            'batch_size': self.batch_size,
            'request_delay': self.request_delay,
            'retry_attempts': self.retry_attempts,
            'broker_name': self.broker_name,
            'is_configured': self.is_configured()
        }
    
    def save_api_key(self, api_key: str) -> bool:
        """Guardar API key en archivo de configuración"""
        try:
            config_dir = self.project_root / "config"
            config_dir.mkdir(exist_ok=True)
            
            config_file = config_dir / "tradetally_api.key"
            config_file.write_text(api_key.strip())
            
            # Actualizar permisos del archivo (solo lectura para el propietario)
            os.chmod(config_file, 0o600)
            
            self.api_key = api_key
            return True
            
        except Exception as e:
            print(f"Error guardando API key: {e}")
            return False
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validar formato de API key"""
        return api_key and api_key.startswith('tt_live_') and len(api_key) > 20


# Instancia global de configuración
config = TradeTallyConfig()