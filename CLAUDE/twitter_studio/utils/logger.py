"""Loguru logger — configured once, imported everywhere."""

import sys
from loguru import logger
from config.settings import settings, LOGS_DIR

logger.remove()

# Console
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
    colorize=True,
)

# Rotating file
logger.add(
    LOGS_DIR / "twitter_studio.log",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    enqueue=True,
)

__all__ = ["logger"]
