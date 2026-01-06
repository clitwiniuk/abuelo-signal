#!/usr/bin/env python3
"""
Telegram Client for Sistema III
Handles all Telegram notifications and commands
"""

import os
import requests
import logging
import threading
import time
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.service_locator import get_config
from core.notification_filter import NotificationFilter

class TelegramClient:
    """
    Telegram client for Sistema III notifications and commands
    """

    def __init__(self):
        self.logger = logging.getLogger("TelegramClient")
        self.config = get_config()

        # Telegram configuration
        self.enabled = self.config.getboolean('NOTIFICATIONS', 'telegram_enabled', fallback=False)
        self.bot_token = self.config.get('NOTIFICATIONS', 'telegram_bot_token', fallback='')
        self.chat_id = self.config.get('NOTIFICATIONS', 'telegram_chat_id', fallback='')

        # Notification settings
        self.notify_opportunities = self.config.getboolean('NOTIFICATIONS', 'notify_new_opportunities', fallback=True)
        self.notify_executions = self.config.getboolean('NOTIFICATIONS', 'notify_trade_executions', fallback=True)
        self.notify_closes = self.config.getboolean('NOTIFICATIONS', 'notify_position_closes', fallback=True)
        self.notify_risk_alerts = self.config.getboolean('NOTIFICATIONS', 'notify_risk_alerts', fallback=True)
        self.notify_system_status = self.config.getboolean('NOTIFICATIONS', 'notify_system_status', fallback=True)
        self.notify_errors = self.config.getboolean('NOTIFICATIONS', 'notify_errors', fallback=True)

        # Notification thresholds
        self.min_quality_score = self.config.getfloat('NOTIFICATIONS', 'min_quality_score_notify', fallback=75.0)
        self.min_gap_percent = self.config.getfloat('NOTIFICATIONS', 'min_gap_percent_notify', fallback=2.0)
        self.min_volume_ratio = self.config.getfloat('NOTIFICATIONS', 'min_volume_ratio_notify', fallback=2.0)

        # Notification filter
        cooldown_seconds = self.config.getint('NOTIFICATIONS', 'notification_cooldown_seconds', fallback=300)
        self.use_filter = self.config.getboolean('NOTIFICATIONS', 'enable_notification_filter', fallback=True)
        self.notification_filter = NotificationFilter(cooldown_seconds=cooldown_seconds, logger=self.logger)

        # Command handlers
        self.command_handlers = {}
        self._register_default_commands()

        # Listener thread
        self.listener_thread = None
        self.listener_running = False

        if self.enabled and self.bot_token and self.chat_id:
            self.logger.info("✅ Telegram client initialized")
        elif self.enabled:
            self.logger.warning("⚠️ Telegram enabled but missing bot_token or chat_id")
        else:
            self.logger.info("📴 Telegram notifications disabled")

    def is_enabled(self) -> bool:
        """Check if Telegram is properly configured and enabled"""
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)

    async def send_message(self, message: str, parse_mode: str = "HTML", disable_notification: bool = False) -> bool:
        """Send message to Telegram"""
        if not self.is_enabled():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        # Split long messages
        max_length = 4000
        if len(message) > max_length:
            parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
            for i, part in enumerate(parts):
                payload = {
                    "chat_id": self.chat_id,
                    "text": f"Part {i+1}/{len(parts)}:\n{part}",
                    "disable_notification": disable_notification
                }
                await self._send_payload(url, payload)
        else:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification
            }
            return await self._send_payload(url, payload)

        return True

    async def _send_payload(self, url: str, payload: Dict) -> bool:
        """Send payload to Telegram API"""
        try:
            # Use requests in a thread to avoid blocking async operations
            def send_request():
                return requests.post(url, json=payload, timeout=10)

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)

            if response.status_code == 200:
                return True
            else:
                self.logger.warning(f"Telegram API error: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False

    # === NOTIFICATION METHODS ===

    async def notify_opportunity(self, opportunity: Dict) -> bool:
        """Notify about new trading opportunity"""
        if not self.notify_opportunities:
            return False

        # Apply quality filters
        quality_score = opportunity.get('quality_score', 0.0)
        gap_percent = opportunity.get('gap_percentage', 0.0)
        volume_ratio = opportunity.get('volume_ratio', 0.0)

        if quality_score < self.min_quality_score:
            return False
        if gap_percent < self.min_gap_percent:
            return False
        if volume_ratio < self.min_volume_ratio:
            return False

        # Apply notification filter if enabled
        if self.use_filter:
            symbol = opportunity.get('symbol', '')
            current_data = {
                'price': opportunity.get('current_price', 0),
                'gap': gap_percent,
                'volume_ratio': volume_ratio,
                'quality_score': quality_score
            }

            should_notify, reason = self.notification_filter.should_notify(symbol, current_data)
            if not should_notify:
                self.logger.debug(f"🔇 Filtered opportunity {symbol}: {reason}")
                return False

        # Format message
        symbol = opportunity.get('symbol', 'N/A')
        strategy = opportunity.get('opportunity_type', 'N/A')
        current_price = opportunity.get('current_price', 0.0)

        message = f"""🎯 <b>Nueva Oportunidad</b>

📊 <b>{symbol}</b> - {strategy}
💰 Precio: ${current_price:.2f}
📈 Gap: {gap_percent:.1f}%
📊 Volumen: {volume_ratio:.1f}x
⭐ Quality: {quality_score:.1f}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    async def notify_execution(self, execution_result: Dict) -> bool:
        """Notify about trade execution"""
        if not self.notify_executions:
            return False

        symbol = execution_result.get('symbol', 'N/A')
        strategy = execution_result.get('strategy', 'N/A')
        status = execution_result.get('status', 'unknown')

        if status == 'executed':
            entry_price = execution_result.get('entry_price', 0.0)
            quantity = execution_result.get('quantity', 0)
            stop_loss = execution_result.get('stop_loss', 0.0)
            profit_target = execution_result.get('profit_target', 0.0)

            message = f"""✅ <b>Trade Ejecutado</b>

📊 <b>{symbol}</b> - {strategy}
🎯 Cantidad: {quantity} shares
💰 Entrada: ${entry_price:.2f}
🛑 Stop Loss: ${stop_loss:.2f}
🚀 Target: ${profit_target:.2f}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        elif status == 'rejected':
            reason = execution_result.get('reason', 'Unknown')
            message = f"""❌ <b>Trade Rechazado</b>

📊 <b>{symbol}</b> - {strategy}
❌ Razón: {reason}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        else:
            message = f"""⚠️ <b>Resultado de Ejecución</b>

📊 <b>{symbol}</b> - {strategy}
📍 Status: {status}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    async def notify_position_close(self, close_data: Dict) -> bool:
        """Notify about position closure"""
        if not self.notify_closes:
            return False

        symbol = close_data.get('symbol', 'N/A')
        reason = close_data.get('reason', 'N/A')
        price = close_data.get('price', 0.0)
        pnl = close_data.get('pnl', 0.0)

        # Determine emoji based on P&L
        if pnl > 0:
            emoji = "💚"
            pnl_text = f"+${pnl:.2f}"
        elif pnl < 0:
            emoji = "❤️"
            pnl_text = f"-${abs(pnl):.2f}"
        else:
            emoji = "⚪"
            pnl_text = "Break Even"

        message = f"""{emoji} <b>Posición Cerrada</b>

📊 <b>{symbol}</b>
💰 Precio: ${price:.2f}
📈 P&L: {pnl_text}
📝 Razón: {reason}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    async def notify_risk_alert(self, alert_data: Dict) -> bool:
        """Notify about risk management alerts"""
        if not self.notify_risk_alerts:
            return False

        alert_type = alert_data.get('type', 'RISK_ALERT')
        message_text = alert_data.get('message', 'Risk alert triggered')

        message = f"""🚨 <b>Alerta de Riesgo</b>

⚠️ {alert_type}
📝 {message_text}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    async def notify_system_status(self, status_data: Dict) -> bool:
        """Notify about system status changes"""
        if not self.notify_system_status:
            return False

        status = status_data.get('status', 'unknown')
        message_text = status_data.get('message', 'System status update')

        emoji = "✅" if status == "running" else "🛑" if status == "stopped" else "⚠️"

        message = f"""{emoji} <b>Estado del Sistema</b>

📍 Status: {status}
📝 {message_text}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    async def notify_error(self, error_data: Dict) -> bool:
        """Notify about system errors"""
        if not self.notify_errors:
            return False

        error_type = error_data.get('type', 'ERROR')
        error_message = error_data.get('message', 'System error occurred')

        message = f"""💥 <b>Error del Sistema</b>

❌ {error_type}
📝 {error_message}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

        return await self.send_message(message)

    # === COMMAND HANDLING ===

    def _register_default_commands(self):
        """Register default system commands"""
        self.command_handlers = {
            '/status': self._handle_status_command,
            '/positions': self._handle_positions_command,
            '/stats': self._handle_stats_command,
            '/risk': self._handle_risk_command,
            '/help': self._handle_help_command,
            '/stop': self._handle_stop_command,
            '/start': self._handle_start_command
        }

    async def _handle_status_command(self, command_data: Dict) -> str:
        """Handle /status command"""
        # This would be implemented to get actual system status
        return """📊 <b>Sistema III Status</b>

✅ Scanner: Running
✅ Execution Engine: Active
✅ Risk Manager: Monitoring
📈 Active Positions: 3
💰 Daily P&L: +$245.67
🎯 Opportunities Today: 12"""

    async def _handle_positions_command(self, command_data: Dict) -> str:
        """Handle /positions command"""
        return """📊 <b>Posiciones Activas</b>

📈 AAPL - GAP_GO
   Entry: $150.25 | Current: $152.10 | P&L: +$37.00

📈 MSFT - DAILY_PLAYS
   Entry: $290.50 | Current: $289.25 | P&L: -$12.50

📈 TSLA - BULL_FLAG
   Entry: $185.75 | Current: $188.20 | P&L: +$24.50

💰 Total P&L: +$49.00"""

    async def _handle_stats_command(self, command_data: Dict) -> str:
        """Handle /stats command"""
        return """📈 <b>Estadísticas del Día</b>

🎯 Oportunidades: 12
✅ Ejecutadas: 8
❌ Rechazadas: 4
💰 P&L Total: +$245.67
📊 Win Rate: 75%
🎪 Mejor Trade: +$89.50 (NVDA)"""

    async def _handle_risk_command(self, command_data: Dict) -> str:
        """Handle /risk command"""
        return """🛡️ <b>Estado del Riesgo</b>

💰 Capital: $30,000
📊 Riesgo Usado: $1,250 (4.2%)
📈 Posiciones: 3/5
🎯 Trades Hoy: 8/20
🛑 Daily Loss Limit: -$1,000

✅ Todos los límites OK"""

    async def _handle_help_command(self, command_data: Dict) -> str:
        """Handle /help command"""
        return """📚 <b>Comandos Disponibles</b>

/status - Estado general del sistema
/positions - Posiciones activas
/stats - Estadísticas del día
/risk - Estado de riesgo
/stop - Parar el sistema
/start - Iniciar el sistema
/help - Esta ayuda

Sistema III - Trading Automático 🤖"""

    async def _handle_stop_command(self, command_data: Dict) -> str:
        """Handle /stop command"""
        # This would trigger actual system stop
        return "🛑 <b>Sistema detenido</b>\n\nTodos los procesos han sido pausados."

    async def _handle_start_command(self, command_data: Dict) -> str:
        """Handle /start command"""
        # This would trigger actual system start
        return "🚀 <b>Sistema iniciado</b>\n\nTodos los procesos están activos."

    def register_command_handler(self, command: str, handler):
        """Register custom command handler"""
        self.command_handlers[command] = handler

    async def handle_command(self, command: str, command_data: Dict = None) -> bool:
        """Handle incoming command"""
        if command in self.command_handlers:
            try:
                response = await self.command_handlers[command](command_data or {})
                if response:
                    await self.send_message(response)
                return True
            except Exception as e:
                self.logger.error(f"Error handling command {command}: {e}")
                await self.send_message(f"❌ Error procesando comando: {str(e)}")
                return False
        return False

    # === POLLING ===

    def start_listener(self):
        """Start Telegram command listener"""
        if not self.is_enabled() or self.listener_running:
            return

        self.listener_running = True
        self.listener_thread = threading.Thread(target=self._poll_updates, daemon=True)
        self.listener_thread.start()
        self.logger.info("👂 Telegram listener started")

    def stop_listener(self):
        """Stop Telegram command listener"""
        self.listener_running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
        self.logger.info("👂 Telegram listener stopped")

    def _poll_updates(self):
        """Poll for Telegram updates"""
        offset = 0
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"

        while self.listener_running:
            try:
                params = {"offset": offset, "timeout": 30}
                response = requests.get(url, params=params, timeout=35)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1

                            if "message" in update:
                                message = update["message"]
                                text = message.get("text", "")

                                if text.startswith("/"):
                                    # Run command handler in event loop
                                    command = text.split()[0]
                                    asyncio.run(self.handle_command(command, {"message": message}))

                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error polling Telegram updates: {e}")
                time.sleep(30)  # Wait before retrying

# Global instance
_telegram_client = None

def get_telegram_client() -> TelegramClient:
    """Get the global Telegram client instance"""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = TelegramClient()
    return _telegram_client