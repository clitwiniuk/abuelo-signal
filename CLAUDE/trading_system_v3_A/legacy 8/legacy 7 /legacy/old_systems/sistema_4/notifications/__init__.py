# notifications/__init__.py
"""
Notification system for Sistema_4
"""

from .telegram_client import (
    send_message,
    notify_trade_executed,
    notify_opportunity_detected,
    notify_system_error,
    notify_system_startup,
    start_command_listener,
    stop_command_listener,
    is_enabled
)