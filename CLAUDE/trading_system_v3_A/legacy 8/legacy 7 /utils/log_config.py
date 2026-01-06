"""
Utility module for configuring logging levels for specific components.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional

def configure_strategy_logging(strategy_loggers: Dict[str, str]) -> None:
    """
    Configure logging levels for specific strategy loggers.
    
    Args:
        strategy_loggers: Dictionary mapping strategy names to logging levels
                         (e.g., {'MACDV': 'WARNING', 'GapGo': 'INFO'})
    """
    for strategy_name, level in strategy_loggers.items():
        logger = logging.getLogger(f"Strategy.{strategy_name}")
        logger.setLevel(getattr(logging, level))
        logger.info(f"Set logging level for {strategy_name} strategy to {level}")

def get_strategy_log_level(strategy_name: str, config_section: Optional[Dict] = None) -> str:
    """
    Get the logging level for a specific strategy from config or default to INFO.
    
    Args:
        strategy_name: Name of the strategy
        config_section: Optional config section with log_level key
        
    Returns:
        Logging level as string (e.g., 'INFO', 'WARNING', 'ERROR')
    """
    if config_section and 'log_level' in config_section:
        return config_section['log_level']
    return 'INFO'

def setup_worker_logging(worker_name: str, level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """
    Setup logging for a specific worker with its own log file.

    Args:
        worker_name: Name of the worker (e.g., 'gap_go', 'macdv')
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files

    Returns:
        Configured logger for the worker
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create worker-specific logger
    logger_name = f"Worker.{worker_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create worker-specific log file
    log_file = os.path.join(log_dir, f"worker_{worker_name}.log")

    try:
        # Use RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=50*1024*1024,  # 50MB max size
            backupCount=3,          # Keep 3 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Also add console handler for workers (unless suppressed)
        if os.environ.get('SUPPRESS_WORKER_STDOUT', '').lower() != 'true':
            console_handler = logging.StreamHandler()
            console_handler.setLevel(numeric_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        logger.info(f"Worker logging initialized - {worker_name} -> {log_file}")

    except Exception as e:
        logging.warning(f"Failed to setup worker logging for {worker_name}: {e}")

    return logger

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Setup logging configuration with both console and file output.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file. If provided, logs will be written to file.
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if log_file specified
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        try:
            # Use RotatingFileHandler optimized for trading operations
            # Max 100MB per file, keep 3 backup files (covers recent trading sessions)
            # This allows reviewing previous trading sessions and patterns
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=100*1024*1024,  # 100MB max size (2 days typical trading)
                backupCount=3,           # Keep 3 backup files (recent history)
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Log initial message to confirm file logging is working
            logging.info(f"----------------------------------------------------------")
            logging.info(f"#############      INICIO OPERATIVA      #################")
            logging.info(f"----------------------------------------------------------")
            logging.info(f"Logging initialized - Level: {level}, File: {log_file} (rotating, max 100MB, 3 backups)")

        except Exception as e:
            # If file logging fails, log to console only
            logging.warning(f"Failed to setup file logging to {log_file}: {e}")
            logging.warning("Continuing with console logging only")
