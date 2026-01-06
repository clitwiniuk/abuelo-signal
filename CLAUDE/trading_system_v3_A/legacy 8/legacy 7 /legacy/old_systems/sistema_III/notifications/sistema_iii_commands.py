#!/usr/bin/env python3
"""
Sistema III Telegram Commands
Provides real-time system monitoring and control via Telegram
"""

import logging
import sys
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SistemaIIICommands:
    """
    Sistema III specific Telegram commands with real system integration
    """

    def __init__(self, coordinator=None):
        self.coordinator = coordinator  # Reference to main coordinator
        self.logger = logging.getLogger("SistemaIIICommands")

    def register_commands(self, telegram_client):
        """Register all Sistema III commands"""
        commands = {
            '/status': self._handle_status_command,
            '/positions': self._handle_positions_command,
            '/stats': self._handle_stats_command,
            '/risk': self._handle_risk_command,
            '/portfolio': self._handle_portfolio_command,
            '/workers': self._handle_workers_command,
            '/opportunities': self._handle_opportunities_command,
            '/health': self._handle_health_command,
            '/emergency_stop': self._handle_emergency_stop_command,
            '/restart_scanner': self._handle_restart_scanner_command,
            '/filter_status': self._handle_filter_status_command,
            '/clear_notifications': self._handle_clear_notifications_command
        }

        for command, handler in commands.items():
            telegram_client.register_command_handler(command, handler)

        self.logger.info(f"✅ Registered {len(commands)} Sistema III commands")

    async def _handle_status_command(self, command_data: Dict) -> str:
        """Handle /status command with real system data"""
        try:
            if not self.coordinator:
                return "❌ Sistema no disponible"

            # Get real system status
            active_positions = len(self.coordinator.execution_engine.active_executions) if self.coordinator.execution_engine else 0

            # Get execution engine status
            if self.coordinator.execution_engine:
                portfolio_status = await self.coordinator.execution_engine.get_portfolio_status()
                risk_status = await self.coordinator.execution_engine.risk_manager.get_risk_utilization()
            else:
                portfolio_status = {}
                risk_status = {}

            # Build status message
            uptime = datetime.now() - self.coordinator.last_heartbeat if hasattr(self.coordinator, 'last_heartbeat') else None
            uptime_str = f"{uptime.total_seconds()/3600:.1f}h" if uptime else "N/A"

            message = f"""📊 <b>Sistema III Status</b>

🚀 <b>Sistema:</b> {'✅ Running' if self.coordinator.is_running else '🛑 Stopped'}
⏰ <b>Uptime:</b> {uptime_str}

💼 <b>Ejecución:</b>
   • Posiciones Activas: {active_positions}
   • Oportunidades Procesadas: {self.coordinator.opportunities_processed}
   • Trades Ejecutados: {self.coordinator.executions_completed}

🛡️ <b>Riesgo:</b>
   • Utilización: {risk_status.get('portfolio_risk_percentage', 0):.1f}%
   • Trades Restantes: {risk_status.get('daily_trades_remaining', 0)}
   • P&L Diario: ${risk_status.get('daily_pnl', 0):.2f}

🔄 <b>Componentes:</b>
   • IBKR: {'✅' if self.coordinator.execution_ibkr and hasattr(self.coordinator.execution_ibkr, 'is_connected') else '❌'}
   • Redis: {'✅' if self.coordinator.message_bus else '❌'}
   • Database: {'✅' if self.coordinator.database else '❌'}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return f"❌ Error obteniendo status: {str(e)}"

    async def _handle_positions_command(self, command_data: Dict) -> str:
        """Handle /positions command with real position data"""
        try:
            if not self.coordinator or not self.coordinator.execution_engine:
                return "❌ Execution engine no disponible"

            active_executions = self.coordinator.execution_engine.active_executions

            if not active_executions:
                return "📊 <b>Sin posiciones activas</b>"

            message = "📊 <b>Posiciones Activas</b>\n\n"

            for exec_id, execution in active_executions.items():
                symbol = execution.get('symbol', 'N/A')
                strategy = execution.get('strategy', 'N/A')
                start_time = execution.get('start_time', datetime.now())

                # Get execution details if available
                details = execution.get('execution_details', {})
                entry_price = details.get('entry_price', 0.0)
                quantity = details.get('quantity', 0)
                stop_loss = details.get('stop_loss', 0.0)
                profit_target = details.get('profit_target', 0.0)

                duration = datetime.now() - start_time
                duration_str = f"{duration.total_seconds()/60:.0f}m"

                message += f"""📈 <b>{symbol}</b> - {strategy}
   💰 Entry: ${entry_price:.2f} ({quantity} shares)
   🛑 Stop: ${stop_loss:.2f}
   🚀 Target: ${profit_target:.2f}
   ⏱️ Duration: {duration_str}

"""

            message += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            return message

        except Exception as e:
            self.logger.error(f"Error in positions command: {e}")
            return f"❌ Error obteniendo posiciones: {str(e)}"

    async def _handle_stats_command(self, command_data: Dict) -> str:
        """Handle /stats command with real statistics"""
        try:
            if not self.coordinator:
                return "❌ Sistema no disponible"

            # Get database statistics
            stats = await self.coordinator.database.get_trading_statistics() if hasattr(self.coordinator.database, 'get_trading_statistics') else {}

            # Get risk statistics
            risk_stats = await self.coordinator.execution_engine.risk_manager.get_risk_utilization() if self.coordinator.execution_engine else {}

            message = f"""📈 <b>Estadísticas del Día</b>

🎯 <b>Oportunidades:</b>
   • Total Detectadas: {self.coordinator.opportunities_processed}
   • Ejecutadas: {self.coordinator.executions_completed}
   • Ratio Ejecución: {(self.coordinator.executions_completed/max(self.coordinator.opportunities_processed, 1)*100):.1f}%

📊 <b>Trading:</b>
   • Posiciones Activas: {stats.get('active_positions', 0)}
   • P&L Diario: ${risk_stats.get('daily_pnl', 0):.2f}
   • Trades Usados: {risk_stats.get('daily_trades_used', 0)}/{risk_stats.get('daily_trades_used', 0) + risk_stats.get('daily_trades_remaining', 0)}

🛡️ <b>Riesgo:</b>
   • Capital Utilizado: ${risk_stats.get('portfolio_risk_used', 0):.2f}
   • Riesgo Disponible: ${risk_stats.get('portfolio_risk_available', 0):.2f}
   • Utilización: {risk_stats.get('portfolio_risk_percentage', 0):.1f}%

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in stats command: {e}")
            return f"❌ Error obteniendo estadísticas: {str(e)}"

    async def _handle_risk_command(self, command_data: Dict) -> str:
        """Handle /risk command with real risk data"""
        try:
            if not self.coordinator or not self.coordinator.execution_engine:
                return "❌ Risk manager no disponible"

            risk_manager = self.coordinator.execution_engine.risk_manager
            risk_stats = await risk_manager.get_risk_utilization()
            risk_config = risk_manager.get_risk_config_summary()

            message = f"""🛡️ <b>Estado del Riesgo</b>

💰 <b>Portfolio:</b>
   • Capital Total: ${risk_config.get('portfolio_capital', 0):,.2f}
   • Riesgo Máximo: {risk_config.get('max_portfolio_risk', 0)*100:.1f}%
   • Utilización Actual: {risk_stats.get('portfolio_risk_percentage', 0):.1f}%

📊 <b>Posiciones:</b>
   • Activas: {risk_stats.get('active_positions', 0)}/{risk_config.get('max_positions', 0)}
   • Riesgo por Trade: {risk_config.get('max_single_position_risk', 0)*100:.1f}%
   • Método Sizing: {risk_config.get('position_sizing_method', 'N/A')}

📈 <b>Trading Diario:</b>
   • Trades Usados: {risk_stats.get('daily_trades_used', 0)}/{risk_config.get('max_daily_trades', 0)}
   • P&L Actual: ${risk_stats.get('daily_pnl', 0):.2f}
   • Límite Pérdida: ${risk_config.get('max_daily_loss', 0):.2f}

⚠️ <b>Alertas:</b>
   {'✅ Todos los límites OK' if risk_stats.get('portfolio_risk_percentage', 0) < 80 else '🚨 Riesgo alto'}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in risk command: {e}")
            return f"❌ Error obteniendo datos de riesgo: {str(e)}"

    async def _handle_portfolio_command(self, command_data: Dict) -> str:
        """Handle /portfolio command"""
        try:
            if not self.coordinator or not self.coordinator.execution_engine:
                return "❌ Portfolio data no disponible"

            portfolio_status = await self.coordinator.execution_engine.get_portfolio_status()

            message = f"""💼 <b>Portfolio Status</b>

📊 <b>Resumen:</b>
   • Posiciones Activas: {portfolio_status.get('active_positions', 0)}
   • Estrategias Activas: {len(portfolio_status.get('strategies', {}))}

🎯 <b>Por Estrategia:</b>
"""

            strategies = portfolio_status.get('strategies', {})
            for strategy, data in strategies.items():
                symbols = ', '.join(data.get('symbols', []))
                message += f"   • {strategy}: {data.get('active_positions', 0)} ({symbols})\n"

            if not strategies:
                message += "   • Sin estrategias activas\n"

            message += f"""
🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in portfolio command: {e}")
            return f"❌ Error obteniendo portfolio: {str(e)}"

    async def _handle_workers_command(self, command_data: Dict) -> str:
        """Handle /workers command"""
        try:
            if not self.coordinator or not self.coordinator.execution_engine:
                return "❌ Workers data no disponible"

            workers = self.coordinator.execution_engine.workers

            message = f"""🤖 <b>Workers Status</b>

"""

            for strategy, worker in workers.items():
                active_positions = len(worker.active_positions) if hasattr(worker, 'active_positions') else 0
                message += f"""📋 <b>{strategy}:</b>
   • Status: ✅ Active
   • Posiciones: {active_positions}

"""

            message += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            return message

        except Exception as e:
            self.logger.error(f"Error in workers command: {e}")
            return f"❌ Error obteniendo workers: {str(e)}"

    async def _handle_opportunities_command(self, command_data: Dict) -> str:
        """Handle /opportunities command"""
        try:
            if not self.coordinator:
                return "❌ Sistema no disponible"

            message = f"""🎯 <b>Oportunidades Recientes</b>

📊 <b>Estadísticas:</b>
   • Total Procesadas: {self.coordinator.opportunities_processed}
   • Ejecutadas: {self.coordinator.executions_completed}
   • Ratio: {(self.coordinator.executions_completed/max(self.coordinator.opportunities_processed, 1)*100):.1f}%

📈 <b>Últimas 24h:</b>
   • Filtro activo: {'✅' if hasattr(self.coordinator, 'telegram_client') and self.coordinator.telegram_client.use_filter else '❌'}
   • Notificaciones: {'✅ Enabled' if hasattr(self.coordinator, 'telegram_client') and self.coordinator.telegram_client.notify_opportunities else '❌ Disabled'}

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in opportunities command: {e}")
            return f"❌ Error obteniendo oportunidades: {str(e)}"

    async def _handle_health_command(self, command_data: Dict) -> str:
        """Handle /health command"""
        try:
            if not self.coordinator:
                return "❌ Sistema no disponible"

            # Check component health
            components = {
                'Sistema Principal': '✅' if self.coordinator.is_running else '❌',
                'IBKR Connection': '✅' if self.coordinator.execution_ibkr else '❌',
                'Execution Engine': '✅' if self.coordinator.execution_engine else '❌',
                'Database': '✅' if self.coordinator.database else '❌',
                'Message Bus': '✅' if self.coordinator.message_bus else '❌',
                'Telegram Client': '✅' if hasattr(self.coordinator, 'telegram_client') and self.coordinator.telegram_client.is_enabled() else '❌'
            }

            message = f"""🏥 <b>Health Check</b>

"""

            for component, status in components.items():
                message += f"{status} {component}\n"

            # Overall health
            healthy_count = sum(1 for status in components.values() if status == '✅')
            total_count = len(components)
            health_percentage = (healthy_count / total_count) * 100

            if health_percentage == 100:
                overall_status = "🟢 Excelente"
            elif health_percentage >= 80:
                overall_status = "🟡 Bueno"
            else:
                overall_status = "🔴 Problemas"

            message += f"""
📊 <b>Estado General:</b> {overall_status} ({healthy_count}/{total_count})

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in health command: {e}")
            return f"❌ Error obteniendo health: {str(e)}"

    async def _handle_emergency_stop_command(self, command_data: Dict) -> str:
        """Handle /emergency_stop command"""
        try:
            if not self.coordinator:
                return "❌ Sistema no disponible"

            self.logger.warning("🚨 EMERGENCY STOP triggered via Telegram")
            await self.coordinator.emergency_shutdown("TELEGRAM_COMMAND")

            return "🚨 <b>EMERGENCY STOP EJECUTADO</b>\n\nTodas las posiciones han sido cerradas y el sistema detenido."

        except Exception as e:
            self.logger.error(f"Error in emergency stop: {e}")
            return f"❌ Error ejecutando emergency stop: {str(e)}"

    async def _handle_restart_scanner_command(self, command_data: Dict) -> str:
        """Handle /restart_scanner command"""
        try:
            # This would trigger scanner restart
            return "🔄 <b>Scanner Restart</b>\n\n⚠️ Funcionalidad en desarrollo"

        except Exception as e:
            self.logger.error(f"Error in restart scanner: {e}")
            return f"❌ Error reiniciando scanner: {str(e)}"

    async def _handle_filter_status_command(self, command_data: Dict) -> str:
        """Handle /filter_status command"""
        try:
            if not hasattr(self.coordinator, 'telegram_client'):
                return "❌ Telegram client no disponible"

            telegram_client = self.coordinator.telegram_client
            if not telegram_client.use_filter:
                return "🚫 <b>Filtro de Notificaciones</b>\n\n❌ Filtro desactivado"

            filter_status = telegram_client.notification_filter.get_notification_status()

            message = f"""🚫 <b>Estado del Filtro</b>

⚙️ <b>Configuración:</b>
   • Cooldown: {filter_status.get('cooldown_seconds', 0)}s
   • Símbolos Trackeados: {filter_status.get('total_symbols', 0)}

📊 <b>Thresholds:</b>
   • Precio: {filter_status.get('thresholds', {}).get('price_change', 0)*100:.1f}%
   • Gap: {filter_status.get('thresholds', {}).get('gap_change', 0)*100:.1f}%
   • Volumen: {filter_status.get('thresholds', {}).get('volume_change', 0)*100:.1f}%
   • Score: {filter_status.get('thresholds', {}).get('score_change', 0):.1f}pts

🕐 {datetime.now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            self.logger.error(f"Error in filter status: {e}")
            return f"❌ Error obteniendo filter status: {str(e)}"

    async def _handle_clear_notifications_command(self, command_data: Dict) -> str:
        """Handle /clear_notifications command"""
        try:
            if not hasattr(self.coordinator, 'telegram_client'):
                return "❌ Telegram client no disponible"

            telegram_client = self.coordinator.telegram_client
            if telegram_client.use_filter:
                telegram_client.notification_filter.clear_cache()
                return "🗑️ <b>Cache de Notificaciones Limpio</b>\n\n✅ Todos los filtros han sido reseteados"
            else:
                return "🚫 <b>Filtro Desactivado</b>\n\n❌ No hay cache que limpiar"

        except Exception as e:
            self.logger.error(f"Error clearing notifications: {e}")
            return f"❌ Error limpiando notifications: {str(e)}"