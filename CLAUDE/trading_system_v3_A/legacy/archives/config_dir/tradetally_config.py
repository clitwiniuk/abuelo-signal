"""
Configuración para TradeTally Integration
"""

import os
from pathlib import Path
from typing import Optional

# Cargar variables de entorno desde .env y .env.local
print(f"🔍 TRADETALLY CONFIG DEBUG - Starting environment variable loading...")
try:
    from dotenv import load_dotenv
    
    print(f"🔍 TRADETALLY CONFIG DEBUG - Loading .env file...")
    env_loaded = load_dotenv('.env')
    print(f"🔍 TRADETALLY CONFIG DEBUG - .env file loaded: {env_loaded}")
    
    print(f"🔍 TRADETALLY CONFIG DEBUG - Loading .env.local file (with override)...")
    env_local_loaded = load_dotenv('.env.local', override=True)  # .env.local tiene prioridad
    print(f"🔍 TRADETALLY CONFIG DEBUG - .env.local file loaded: {env_local_loaded}")
    
    # Check what's actually in the environment after loading
    tradetally_api_key = os.getenv('TRADETALLY_API_KEY')
    tradetally_base_url = os.getenv('TRADETALLY_BASE_URL')
    print(f"🔍 TRADETALLY CONFIG DEBUG - After loading, TRADETALLY_API_KEY: {tradetally_api_key[:20] + '...' if tradetally_api_key and len(tradetally_api_key) > 20 else tradetally_api_key}")
    print(f"🔍 TRADETALLY CONFIG DEBUG - After loading, TRADETALLY_BASE_URL: {tradetally_base_url}")
    
except ImportError as e:
    print(f"🔍 TRADETALLY CONFIG DEBUG - dotenv not available: {e}")
    pass  # dotenv no está instalado, usar solo variables del sistema

class TradeTallyConfig:
    """Configuración centralizada para TradeTally"""
    
    def __init__(self):
        # Ruta base del proyecto
        self.project_root = Path(__file__).parent.parent
        
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
        """Obtener API key desde variables de entorno o archivo"""
        # Prioridad: variable de entorno > archivo de configuración
        print(f"🔍 TRADETALLY CONFIG DEBUG - Looking for API key...")
        
        api_key = os.getenv('TRADETALLY_API_KEY')
        print(f"🔍 TRADETALLY CONFIG DEBUG - Environment variable TRADETALLY_API_KEY: {api_key[:20] + '...' if api_key and len(api_key) > 20 else api_key}")
        
        if not api_key:
            # Intentar leer desde archivo de configuración
            config_file = self.project_root / "config" / "tradetally_api.key"
            print(f"🔍 TRADETALLY CONFIG DEBUG - Checking config file: {config_file}")
            print(f"🔍 TRADETALLY CONFIG DEBUG - Config file exists: {config_file.exists()}")
            
            if config_file.exists():
                try:
                    api_key = config_file.read_text().strip()
                    print(f"🔍 TRADETALLY CONFIG DEBUG - API key from file: {api_key[:20] + '...' if api_key and len(api_key) > 20 else api_key}")
                except Exception as e:
                    print(f"Error leyendo archivo de API key: {e}")
        
        print(f"🔍 TRADETALLY CONFIG DEBUG - Final API key: {api_key[:20] + '...' if api_key and len(api_key) > 20 else api_key}")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Final API key length: {len(api_key) if api_key else 0}")
        
        return api_key
    
    def _get_base_url(self) -> str:
        """Obtener URL base de TradeTally"""
        return os.getenv('TRADETALLY_BASE_URL', 'https://tradetally.io/api/v2')
    
    def is_configured(self) -> bool:
        """Verificar si la configuración está completa"""
        print(f"🔍 TRADETALLY CONFIG DEBUG - is_configured() check:")
        print(f"🔍 TRADETALLY CONFIG DEBUG - API key exists: {self.api_key is not None}")
        if not self.api_key:
            print(f"🔍 TRADETALLY CONFIG DEBUG - No API key found")
            return False
        
        print(f"🔍 TRADETALLY CONFIG DEBUG - API key: {self.api_key[:10]}...")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Starts with 'tt_live_': {self.api_key.startswith('tt_live_')}")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Starts with 'eyJ': {self.api_key.startswith('eyJ')}")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Length: {len(self.api_key)}")
        
        # Aceptar tanto API keys de producción (tt_live_), JWT tokens (eyJ), o API keys locales (32 chars alfanuméricos)
        is_production_key = self.api_key.startswith('tt_live_')
        is_jwt_token = self.api_key.startswith('eyJ') and len(self.api_key) > 50
        is_local_api_key = len(self.api_key) == 32 and self.api_key.isalnum()  # Local TradeTally API key format
        
        print(f"🔍 TRADETALLY CONFIG DEBUG - Is production key: {is_production_key}")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Is JWT token: {is_jwt_token}")
        print(f"🔍 TRADETALLY CONFIG DEBUG - Is local API key: {is_local_api_key}")
        
        result = is_production_key or is_jwt_token or is_local_api_key
        print(f"🔍 TRADETALLY CONFIG DEBUG - Final is_configured result: {result}")
        
        return result
    
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
        if not api_key:
            return False
        # Aceptar tanto API keys de producción como JWT tokens
        return (api_key.startswith('tt_live_') and len(api_key) > 20) or \
               (api_key.startswith('eyJ') and len(api_key) > 50)


# Instancia global de configuración
config = TradeTallyConfig()