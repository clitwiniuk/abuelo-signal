# core/config_manager.py
"""
Centralized Configuration Manager with Validation
Validates and manages all configuration parameters with type safety
"""

import os
import configparser
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass

class ConfigType(Enum):
    """Supported configuration value types"""
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"

@dataclass
class ConfigRule:
    """Configuration validation rule"""
    required: bool = False
    type: ConfigType = ConfigType.STRING
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    default: Any = None

class ConfigManager:
    """
    Centralized configuration management with comprehensive validation
    """

    # Configuration validation rules
    VALIDATION_RULES = {
        'GLOBAL': {
            'min_price': ConfigRule(required=True, type=ConfigType.FLOAT, min_value=0.1, max_value=100.0),
            'max_price': ConfigRule(required=True, type=ConfigType.FLOAT, min_value=1.0, max_value=1000.0),
            'min_daily_volume': ConfigRule(required=True, type=ConfigType.INT, min_value=1000),
            'risk_per_trade': ConfigRule(required=True, type=ConfigType.FLOAT, min_value=0.001, max_value=0.1),
            'max_positions': ConfigRule(required=False, type=ConfigType.INT, min_value=1, max_value=100, default=10),
        },
        'TRADING': {
            'max_daily_trades': ConfigRule(required=True, type=ConfigType.INT, min_value=1, max_value=200),
            'max_daily_loss': ConfigRule(required=False, type=ConfigType.FLOAT, min_value=-10000.0, max_value=0.0, default=-1000.0),
            'portfolio_capital': ConfigRule(required=True, type=ConfigType.FLOAT, min_value=100.0),
        },
        'IBKR': {
            'host': ConfigRule(required=True, type=ConfigType.STRING),
            'port': ConfigRule(required=True, type=ConfigType.INT, min_value=4000, max_value=8000),
            'client_id': ConfigRule(required=True, type=ConfigType.INT, min_value=0, max_value=1000000),
        }
    }

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), '..', 'config.ini')
        self.config = configparser.ConfigParser()
        self._load_config()
        self._validate_config()
        logger.info("✅ Configuration loaded and validated successfully")

    def _load_config(self):
        """Load configuration from file with error handling"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            self.config.read(self.config_path)
            logger.info(f"📄 Configuration loaded from: {self.config_path}")
        except configparser.Error as e:
            raise ConfigValidationError(f"Error parsing configuration file: {e}")

    def _validate_config(self):
        """Comprehensive configuration validation"""
        errors = []

        # Check required sections
        required_sections = ['GLOBAL', 'TRADING', 'IBKR']
        for section in required_sections:
            if not self.config.has_section(section):
                errors.append(f"Required section missing: {section}")

        # Validate individual parameters
        for section, rules in self.VALIDATION_RULES.items():
            if not self.config.has_section(section):
                continue

            for key, rule in rules.items():
                try:
                    self._validate_parameter(section, key, rule)
                except Exception as e:
                    errors.append(f"Section [{section}] {key}: {e}")

        if errors:
            error_msg = f"Configuration validation failed:\n" + "\n".join(f"  • {error}" for error in errors)
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)

    def _validate_parameter(self, section: str, key: str, rule: ConfigRule):
        """Validate individual parameter"""
        if not self.config.has_option(section, key):
            if rule.required:
                raise ValueError(f"Required parameter missing")
            return

        raw_value = self.config.get(section, key)
        value = self._convert_value(raw_value, rule.type)

        # Type validation
        if rule.type == ConfigType.INT and not isinstance(value, int):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        elif rule.type == ConfigType.FLOAT and not isinstance(value, (int, float)):
            raise ValueError(f"Expected number, got {type(value).__name__}")
        elif rule.type == ConfigType.BOOL and not isinstance(value, bool):
            raise ValueError(f"Expected boolean, got {type(value).__name__}")

        # Range validation
        if rule.min_value is not None and value < rule.min_value:
            raise ValueError(f"Value {value} below minimum {rule.min_value}")
        if rule.max_value is not None and value > rule.max_value:
            raise ValueError(f"Value {value} above maximum {rule.max_value}")

        # Allowed values validation
        if rule.allowed_values is not None and value not in rule.allowed_values:
            raise ValueError(f"Value {value} not in allowed values: {rule.allowed_values}")

    def _convert_value(self, value: str, config_type: ConfigType) -> Any:
        """Convert string value to appropriate type"""
        if config_type == ConfigType.BOOL:
            return value.lower() in ('true', 'yes', '1', 'on')
        elif config_type == ConfigType.INT:
            return int(float(value))  # Handle "1.0" -> 1
        elif config_type == ConfigType.FLOAT:
            return float(value)
        elif config_type == ConfigType.LIST:
            return [item.strip() for item in value.split(',')]
        else:
            return value

    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Get configuration value with type conversion and validation"""
        if not self.config.has_section(section) or not self.config.has_option(section, key):
            if fallback is not None:
                return fallback
            # Check if there's a default in validation rules
            if section in self.VALIDATION_RULES and key in self.VALIDATION_RULES[section]:
                rule = self.VALIDATION_RULES[section][key]
                if rule.default is not None:
                    return rule.default
            return None

        raw_value = self.config.get(section, key)

        # Try to determine type from validation rules
        if section in self.VALIDATION_RULES and key in self.VALIDATION_RULES[section]:
            rule = self.VALIDATION_RULES[section][key]
            return self._convert_value(raw_value, rule.type)

        # Fallback type conversion
        if raw_value.lower() in ('true', 'false'):
            return raw_value.lower() == 'true'
        elif raw_value.replace('.', '').replace('-', '').isdigit():
            return float(raw_value) if '.' in raw_value else int(raw_value)
        else:
            return raw_value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire section as dictionary with type conversion"""
        if not self.config.has_section(section):
            return {}

        result = {}
        for key in self.config.options(section):
            result[key] = self.get(section, key)

        return result

    def set(self, section: str, key: str, value: Any):
        """Set configuration value with validation"""
        if not self.config.has_section(section):
            self.config.add_section(section)

        # Validate before setting
        if section in self.VALIDATION_RULES and key in self.VALIDATION_RULES[section]:
            rule = self.VALIDATION_RULES[section][key]
            converted_value = self._convert_value(str(value), rule.type)
            self._validate_parameter_value(converted_value, rule)

        self.config.set(section, key, str(value))

    def _validate_parameter_value(self, value: Any, rule: ConfigRule):
        """Validate parameter value against rule"""
        # Range validation
        if rule.min_value is not None and value < rule.min_value:
            raise ValueError(f"Value {value} below minimum {rule.min_value}")
        if rule.max_value is not None and value > rule.max_value:
            raise ValueError(f"Value {value} above maximum {rule.max_value}")

        # Allowed values validation
        if rule.allowed_values is not None and value not in rule.allowed_values:
            raise ValueError(f"Value {value} not in allowed values: {rule.allowed_values}")

    def save(self):
        """Save configuration to file with backup"""
        try:
            # Create backup
            backup_path = f"{self.config_path}.backup"
            if os.path.exists(self.config_path):
                import shutil
                shutil.copy2(self.config_path, backup_path)

            # Save new config
            with open(self.config_path, 'w') as f:
                self.config.write(f)

            logger.info(f"💾 Configuration saved to: {self.config_path}")

        except Exception as e:
            logger.error(f"❌ Error saving configuration: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get configuration status for monitoring"""
        return {
            "config_file": self.config_path,
            "config_exists": os.path.exists(self.config_path),
            "sections_count": len(self.config.sections()),
            "total_parameters": sum(len(self.config.options(section)) for section in self.config.sections()),
            "validation_errors": [],  # Would be populated if validation failed
        }