# production/hybrid_config_manager.py
"""
Hybrid Config Manager - Aprovecha config.ini existente y agrega solo lo necesario
NO duplica parámetros, solo complementa lo que falta
"""

import configparser
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class HybridConfigManager:
    """
    Manager que aprovecha tu config.ini existente al 100%
    Solo agrega parámetros específicos de producción que NO están duplicados
    """
    
    def __init__(self, config_ini_path: Optional[str] = None):
        self.logger = logging.getLogger("HybridConfigManager")
        
        # Buscar config.ini en directorio raíz
        if config_ini_path is None:
            project_root = Path(__file__).parent.parent
            config_ini_path = project_root / "config.ini"
        
        self.config_path = Path(config_ini_path)
        # Usar RawConfigParser para evitar problemas con % en valores
        self.config = configparser.RawConfigParser()
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"❌ config.ini no encontrado: {self.config_path}")
        
        self.config.read(self.config_path)
        self.logger.info(f"✅ config.ini cargado: {self.config_path}")
    
    def get_base_config_from_ini(self) -> Dict[str, Any]:
        """
        Lee TODA la configuración desde tu config.ini existente
        NO modifica nada, solo convierte a dict para fácil acceso
        """
        base_config = {}
        
        # Convertir todas las secciones de config.ini a dict
        for section_name in self.config.sections():
            base_config[section_name.lower()] = dict(self.config[section_name])
        
        self.logger.info(f"📋 Cargadas {len(base_config)} secciones desde config.ini")
        return base_config
    
    def get_production_extensions(self) -> Dict[str, Any]:
        """
        SOLO los parámetros que NO están en config.ini
        Configuración específica para producción smallcaps intraday
        """
        return {
            # ===== PARÁMETROS NUEVOS (no en config.ini) =====
            
            # Scanning intervals (no existe en config.ini)
            "scanning_intervals": {
                "regular_market_seconds": 30,      # Cada 30 segundos en horario regular
                "premarket_seconds": 60,           # Cada 60 segundos en premarket
                "afterhours_seconds": 120,         # Cada 2 minutos afterhours
                "weekend_seconds": 300             # Cada 5 minutos fines de semana
            },
            
            # Tiingo configuration (no existe en config.ini)
            "tiingo": {
                "api_key": os.getenv('TIINGO_API_KEY', ''),
                "base_url": "https://api.tiingo.com",
                "rate_limit_per_hour": 1000,
                "timeout_seconds": 15,
                "batch_size": 50,
                "retry_attempts": 3
            },
            
            # Telegram configuration (aprovechando config.ini existente)
            "telegram": self.get_telegram_config(),
            
            # Production monitoring (no existe en config.ini)
            "production_monitoring": {
                "health_check_interval_seconds": 60,
                "metrics_collection_interval": 30,
                "performance_alert_thresholds": {
                    "scan_latency_ms": 5000,
                    "error_rate_percent": 5.0,
                    "memory_usage_mb": 500,
                    "cpu_usage_percent": 80
                },
                "auto_restart_on_failure": True,
                "max_restart_attempts": 3
            },
            
            # Alert system (no existe en config.ini)
            "production_alerts": {
                "slack_webhook_url": os.getenv('SLACK_WEBHOOK_URL', ''),
                "alert_cooldown_minutes": {
                    "INFO": 5,
                    "WARNING": 15,
                    "CRITICAL": 30,
                    "EMERGENCY": 60
                },
                "exceptional_play_thresholds": {
                    "min_gap_for_alert": 0.15,      # 15% gap triggers alert
                    "min_volume_ratio_for_alert": 5.0,  # 5x volume triggers alert
                    "min_quality_score_for_alert": 8.0  # Score >8 triggers alert
                }
            },
            
            # Deployment validation (no existe en config.ini)
            "deployment": {
                "required_components": [
                    "adapters/ibkr_adapter.py",
                    "core/risk_manager.py",
                    "strategies/multi_strategy_engine_ml.py",
                    "scanner/smallcap/smallcap_daily_scanner.py",
                    "scanner/hybrid_scanner.py",
                    "scanner/tiingo_data_provider.py"
                ],
                "required_env_vars": [
                    "IBKR_ACCOUNT",
                    "TIINGO_API_KEY"
                ],
                "optional_env_vars": [
                    "SLACK_WEBHOOK_URL",
                    "EMAIL_TO",
                    "EMAIL_SMTP_SERVER"
                ]
            },
            
            # Hybrid scanner configuration (no existe en config.ini)
            "hybrid_scanner": {
                "data_source_priority": ["ibkr", "tiingo"],
                "fallback_timeout_ms": 5000,
                "cross_validation_enabled": True,
                "max_price_deviation_percent": 0.05,
                "data_freshness_threshold_seconds": 60
            },
            
            # Live trading safety (no existe en config.ini)
            "live_trading_safety": {
                "require_manual_confirmation": False,
                "max_orders_per_minute": 10,
                "order_size_safety_check": True,
                "prevent_weekend_trading": True,
                "emergency_stop_enabled": True
            }
        }
    
    def get_complete_hybrid_config(self) -> Dict[str, Any]:
        """
        Configuración completa: config.ini + extensiones de producción
        """
        # 1. Cargar TODO desde config.ini existente
        base_config = self.get_base_config_from_ini()
        
        # 2. Agregar SOLO extensiones nuevas
        production_extensions = self.get_production_extensions()
        
        # 3. Combinar sin duplicar
        complete_config = {
            "config_source": "hybrid",
            "config_ini_path": str(self.config_path),
            "base_config": base_config,
            "production_extensions": production_extensions
        }
        
        return complete_config
    
    def get_ibkr_config(self) -> Dict[str, Any]:
        """Configuración IBKR desde config.ini + env vars"""
        ibkr_section = self.config['IBKR']
        
        return {
            # Desde config.ini existente
            "host": ibkr_section.get('host', '127.0.0.1'),
            "port": int(ibkr_section.get('port', '7497')),
            "client_id": int(ibkr_section.get('client_id', '100')),
            
            # Solo desde env vars (no duplicar en config.ini)
            "account": os.getenv('IBKR_ACCOUNT', ''),
            
            # Configuración de conexión desde ADVANCED section
            "auto_reconnect": self.config['ADVANCED'].getboolean('auto_reconnect', True),
            "max_reconnect_attempts": int(self.config['ADVANCED'].get('max_reconnect_attempts', '3')),
            "reconnect_delay": int(self.config['ADVANCED'].get('reconnect_delay', '30'))
        }
    
    def get_trading_params(self) -> Dict[str, Any]:
        """Parámetros de trading desde config.ini existente"""
        trading = self.config['TRADING']
        global_config = self.config['GLOBAL']
        
        return {
            # Portfolio y límites
            "portfolio_capital": float(trading.get('portfolio_capital', '2000.0')),
            "max_positions": int(trading.get('max_positions', '10')),
            "max_daily_trades": int(global_config.get('max_daily_trades', '5')),
            "daily_loss_limit": float(global_config.get('daily_loss_limit', '100.0')),
            "risk_per_trade": float(global_config.get('risk_per_trade', '0.015')),
            
            # CRITICAL: Position sizing parameters from config.ini
            "max_position_value": float(global_config.get('max_position_value', '200.0')),
            "min_quantity": int(global_config.get('min_quantity', '10')),
            
            # Pyramid trading parameters (DISABLED by default)
            "allow_pyramiding": global_config.getboolean('allow_pyramiding', False),
            "max_pyramid_levels": int(global_config.get('max_pyramid_levels', '1')),
            "pyramid_profit_threshold": float(global_config.get('pyramid_profit_threshold', '0.05')),
            "pyramid_size_fraction": float(global_config.get('pyramid_size_fraction', '0.5')),
            "pyramid_cooldown_minutes": int(global_config.get('pyramid_cooldown_minutes', '30')),
            
            # Horarios
            "market_open_hour": float(global_config.get('market_open_hour', '9.5')),
            "market_close_hour": float(global_config.get('market_close_hour', '16.0')),
            "no_entry_after": float(global_config.get('no_entry_after', '14.0')),
            
            # Strategy
            "strategy": trading.get('strategy', 'ml_multi_strategy'),
            "active_profile": trading.get('active_profile', 'PRODUCTION')
        }
    
    def get_telegram_config(self) -> Dict[str, Any]:
        """Configuración de Telegram desde config.ini existente"""
        if 'NOTIFICATIONS' not in self.config:
            self.logger.warning("⚠️ NOTIFICATIONS no encontrada en config.ini")
            return {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
                "command_listener_enabled": False
            }
        
        notifications = self.config['NOTIFICATIONS']
        
        # Verificar si Telegram está habilitado
        telegram_enabled = notifications.get('telegram_enabled', 'false').lower() == 'true'
        
        return {
            "enabled": telegram_enabled,
            "bot_token": self._clean_config_value(notifications.get('telegram_bot_token', '')),
            "chat_id": self._clean_config_value(notifications.get('telegram_chat_id', '')),
            "command_listener_enabled": telegram_enabled,  # Auto-enable listener si Telegram está habilitado
            
            # Configuración específica para smallcaps
            "smallcap_alerts": {
                "exceptional_plays": True,      # Alertar plays excepcionales
                "position_updates": True,       # Alertar cambios de posición
                "daily_summary": True,          # Resumen diario
                "error_alerts": True            # Alertar errores críticos
            }
        }
    
    def _clean_config_value(self, value: str) -> str:
        """Limpiar valor de config removiendo comentarios en línea"""
        if '#' in value:
            value = value.split('#')[0]
        return value.strip()
    
    def get_smallcap_strategy_config(self) -> Dict[str, Any]:
        """Configuración específica de daily plays desde config.ini"""
        if 'DAILY_PLAYS_STRATEGY' not in self.config:
            self.logger.warning("⚠️ DAILY_PLAYS_STRATEGY no encontrada en config.ini")
            return {}
        
        daily_plays = self.config['DAILY_PLAYS_STRATEGY']
        return {
            # Filtros de precio y volumen
            "min_price": float(self._clean_config_value(daily_plays.get('min_price', '1.0'))),
            "max_price": float(self._clean_config_value(daily_plays.get('max_price', '15.0'))),
            "min_volume": int(self._clean_config_value(daily_plays.get('min_volume', '500000'))),
            "min_gap_percent": float(self._clean_config_value(daily_plays.get('min_gap_percent', '10.0'))),
            "volume_multiplier": float(self._clean_config_value(daily_plays.get('volume_multiplier', '2.0'))),
            
            # Risk management
            "stop_loss_pct": float(self._clean_config_value(daily_plays.get('stop_loss_pct', '0.06'))),
            "take_profit_pct": float(self._clean_config_value(daily_plays.get('take_profit_pct', '0.12'))),
            "trailing_activation": float(self._clean_config_value(daily_plays.get('trailing_activation', '0.08'))),
            "trailing_distance": float(self._clean_config_value(daily_plays.get('trailing_distance', '0.04'))),
            
            # Timing
            "first_30_minutes": int(self._clean_config_value(daily_plays.get('first_30_minutes', '30'))),
            "max_hold_time": int(self._clean_config_value(daily_plays.get('max_hold_time', '120'))),
            "cooldown_minutes": int(self._clean_config_value(daily_plays.get('cooldown_minutes', '15')))
        }
    
    def validate_hybrid_config(self) -> Dict[str, Any]:
        """Validar configuración híbrida"""
        results = {
            "config_ini_valid": False,
            "production_extensions_valid": False,
            "env_vars_valid": False,
            "errors": [],
            "warnings": []
        }
        
        # 1. Validar config.ini
        try:
            required_sections = ['IBKR', 'TRADING', 'GLOBAL', 'DAILY_PLAYS_STRATEGY']
            missing_sections = [s for s in required_sections if s not in self.config]
            
            if missing_sections:
                results["errors"].append(f"Secciones faltantes en config.ini: {missing_sections}")
            else:
                results["config_ini_valid"] = True
                
        except Exception as e:
            results["errors"].append(f"Error validando config.ini: {e}")
        
        # 2. Validar extensiones de producción
        try:
            extensions = self.get_production_extensions()
            if not extensions.get("tiingo", {}).get("api_key"):
                results["warnings"].append("TIINGO_API_KEY no configurada")
            
            results["production_extensions_valid"] = True
            
        except Exception as e:
            results["errors"].append(f"Error en extensiones de producción: {e}")
        
        # 3. Validar variables de entorno críticas
        required_env = ["IBKR_ACCOUNT", "TIINGO_API_KEY"]
        missing_env = [var for var in required_env if not os.getenv(var)]
        
        if missing_env:
            results["errors"].append(f"Variables de entorno faltantes: {missing_env}")
        else:
            results["env_vars_valid"] = True
        
        # Resultado general
        results["overall_valid"] = (
            results["config_ini_valid"] and 
            results["production_extensions_valid"] and 
            results["env_vars_valid"]
        )
        
        return results
    
    def print_config_summary(self):
        """Imprimir resumen de configuración híbrida"""
        print("📋 HYBRID CONFIG MANAGER - RESUMEN")
        print("=" * 50)
        
        # Config.ini info
        print(f"📁 config.ini: {self.config_path}")
        print(f"📊 Secciones en config.ini: {len(self.config.sections())}")
        
        # IBKR config
        ibkr_config = self.get_ibkr_config()
        print(f"🔗 IBKR: {ibkr_config['host']}:{ibkr_config['port']} (cliente {ibkr_config['client_id']})")
        
        # Trading params
        trading_params = self.get_trading_params()
        print(f"💰 Capital: ${trading_params['portfolio_capital']}")
        print(f"📈 Max posiciones: {trading_params['max_positions']}")
        print(f"⚠️ Pérdida diaria máx: ${trading_params['daily_loss_limit']}")
        
        # Smallcap strategy
        smallcap_config = self.get_smallcap_strategy_config()
        if smallcap_config:
            print(f"🎯 Smallcap range: ${smallcap_config['min_price']}-${smallcap_config['max_price']}")
            print(f"📊 Min gap: {smallcap_config['min_gap_percent']:.1f}%")
            print(f"🔊 Min volumen: {smallcap_config['min_volume']:,}")
        
        # Validación
        validation = self.validate_hybrid_config()
        status = "✅ VÁLIDA" if validation["overall_valid"] else "❌ INVÁLIDA"
        print(f"🔍 Configuración: {status}")
        
        if validation["errors"]:
            print("❌ Errores:")
            for error in validation["errors"]:
                print(f"   - {error}")
        
        if validation["warnings"]:
            print("⚠️ Advertencias:")
            for warning in validation["warnings"]:
                print(f"   - {warning}")

# Función de conveniencia
def create_hybrid_config(config_ini_path: Optional[str] = None) -> HybridConfigManager:
    """Crear manager de configuración híbrida"""
    return HybridConfigManager(config_ini_path)

if __name__ == "__main__":
    # Test del hybrid config manager
    try:
        manager = create_hybrid_config()
        manager.print_config_summary()
        
        print("\n🧪 TESTING configuración híbrida...")
        
        # Test obtener config completa
        complete_config = manager.get_complete_hybrid_config()
        print(f"✅ Configuración completa: {len(complete_config)} secciones principales")
        
        # Test validación
        validation = manager.validate_hybrid_config()
        if validation["overall_valid"]:
            print("✅ Configuración híbrida válida!")
        else:
            print("❌ Configuración híbrida inválida")
            
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()