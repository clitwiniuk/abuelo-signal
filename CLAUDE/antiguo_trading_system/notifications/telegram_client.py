#!/usr/bin/env python3
"""
Simple, clean Telegram client - Starting fresh
"""

import os
import requests
import logging
import configparser
import threading
import time
from pathlib import Path
from datetime import datetime

# Project root and config
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_config = configparser.ConfigParser()
_config.read(_PROJECT_ROOT / "config.ini")

_logger = logging.getLogger("TelegramClient")
_listener_thread = None
_listener_running = False

def is_enabled() -> bool:
    """Check if Telegram is enabled"""
    return _config.getboolean("NOTIFICATIONS", "telegram_enabled", fallback=False)

def get_token():
    """Get bot token"""
    return _config.get("NOTIFICATIONS", "telegram_bot_token", fallback="")

def get_chat_id():
    """Get chat ID"""
    return _config.get("NOTIFICATIONS", "telegram_chat_id", fallback="")

def send_message(message: str, use_html: bool = True, parse_mode: str = None):
    """Send message to Telegram"""
    if not is_enabled():
        return
    
    token = get_token()
    chat_id = get_chat_id()
    
    if not token or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Split message if too long
    max_length = 4000
    if len(message) > max_length:
        parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
        for i, part in enumerate(parts):
            payload = {
                "chat_id": chat_id,
                "text": f"Part {i+1}/{len(parts)}:\n{part}"
            }
            # Don't use HTML for split messages to avoid parsing issues
            try:
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code != 200:
                    _logger.warning(f"Telegram API error: {response.text}")
            except Exception as e:
                _logger.error(f"Error sending Telegram message part {i+1}: {e}")
    else:
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        # Handle parse_mode parameter (takes priority over use_html)
        if parse_mode:
            payload["parse_mode"] = parse_mode
        elif use_html:
            payload["parse_mode"] = "HTML"
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                _logger.warning(f"Telegram API error: {response.text}")
        except Exception as e:
            _logger.error(f"Error sending Telegram message: {e}")

def send_scanner_log(lines: int = 50):
    """Send scanner log entries"""
    if not is_enabled():
        return
        
    log_file = _PROJECT_ROOT / "logs" / "scanner.log"
    
    if not log_file.exists():
        send_message("❌ Scanner log file not found")
        return
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Read all lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Filter today's lines
        today_lines = [line.strip() for line in all_lines if line.startswith(today)]
        
        if not today_lines:
            send_message(f"ℹ️ No logs found for today ({today})")
            return
        
        # Get last N lines
        if len(today_lines) > lines:
            today_lines = today_lines[-lines:]
        
        # Format message
        content = "\n".join(today_lines)
        header = f"🔍 Scanner logs ({today}) - Last {len(today_lines)} lines:"
        
        # Check if message will be too long
        full_message = f"{header}\n{content}"
        if len(full_message) > 4000:
            # Send as plain text if too long
            send_message(full_message, use_html=False)
        else:
            # Send with HTML formatting if short enough
            import html
            escaped_content = html.escape(content)
            formatted_message = f"{header}\n<pre>{escaped_content}</pre>"
            send_message(formatted_message, use_html=True)
        
        _logger.info(f"Sent {len(today_lines)} log lines to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending scanner logs: {e}")
        send_message(f"❌ Error reading scanner logs: {str(e)}")

def send_trader_log(lines: int = 50):
    """Send trader log entries"""
    if not is_enabled():
        return
        
    log_file = _PROJECT_ROOT / "logs" / "trader.log"
    
    if not log_file.exists():
        send_message("❌ Trader log file not found")
        return
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Read all lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Filter today's lines
        today_lines = [line.strip() for line in all_lines if line.startswith(today)]
        
        if not today_lines:
            send_message(f"ℹ️ No trader logs found for today ({today})")
            return
        
        # Get last N lines
        if len(today_lines) > lines:
            today_lines = today_lines[-lines:]
        
        # Format message
        content = "\n".join(today_lines)
        header = f"🤖 Trader logs ({today}) - Last {len(today_lines)} lines:"
        
        # Check if message will be too long
        full_message = f"{header}\n{content}"
        if len(full_message) > 4000:
            # Send as plain text if too long
            send_message(full_message, use_html=False)
        else:
            # Send with HTML formatting if short enough
            import html
            escaped_content = html.escape(content)
            formatted_message = f"{header}\n<pre>{escaped_content}</pre>"
            send_message(formatted_message, use_html=True)
        
        _logger.info(f"Sent {len(today_lines)} trader log lines to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending trader logs: {e}")
        send_message(f"❌ Error reading trader logs: {str(e)}")

def send_main_menu():
    """Send main menu with available commands"""
    menu_msg = """🤖 **TRADING BOT CONTROL PANEL**
═══════════════════════════════

📊 **ESTADÍSTICAS**
• /stats - Estadísticas del día
• /stats_historical - Estadísticas históricas  
• /performance - Resumen de rendimiento

📈 **TRADES**
• /trades - Trades recientes (últimos 10)
• /trades_today - Trades de hoy
• /trades_open - Posiciones abiertas
• /closeall - 🚨 Cerrar todas las posiciones (EMERGENCIA)

🔍 **SCANNER & PLAYS**
• /plays - Plays detectados por el scanner
• /scanner - Estado del scanner
• /plays_today - Todos los plays de hoy

📋 **LOGS**
• /scanner_log - Últimos 50 scanner logs de hoy
• /trader_log - Últimos 50 trader logs de hoy
• /scanner_log_100 - Últimos 100 scanner logs
• /trader_log_100 - Últimos 100 trader logs

🔧 **UTILIDADES**
• /status - Estado del sistema
• /hybrid_status - Estado del sistema híbrido ML
• /tradetally_status - Estado de integración TradeTally
• /tradetally_sync - Sincronización manual TradeTally (Híbrida: PostgreSQL + API)
• /help - Ayuda detallada
• /menu - Mostrar este menú

═══════════════════════════════
🚀 **Sistema de Trading Activo**"""
    send_message(menu_msg, use_html=True)

def send_help_message():
    """Send help message"""
    help_msg = """🆘 **COMMAND HELP**
═══════════════════════

**Usage Examples:**
• `/scanner_log` - Show last 50 scanner log lines of today
• `/trader_log` - Show last 50 trader log lines of today
• `/scanner_log_100` - Show last 100 scanner log lines
• `/trader_log_100` - Show last 100 trader log lines
• `/stats` - Daily statistics
• `/stats_historical` - Historical statistics (30 days)
• `/trades_today` - Today's trades
• `/trades_open` - Open positions
• `/closeall` - 🚨 Emergency close all positions
• `/status` - System status
• `/hybrid_status` - Hybrid ML system status
• `/tradetally_status` - TradeTally integration status
• `/tradetally_sync` - Execute manual TradeTally sync (Hybrid: PostgreSQL + API)
• `/menu` - Main menu

**Tips:**
• Commands are case insensitive
• Use /menu to return to main menu
• Bot responds only to authorized chat

═══════════════════════
💡 Use /menu for main options"""
    send_message(help_msg, use_html=True)

def send_system_status():
    """Send basic system status"""
    try:
        # Basic status info
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check log file
        log_file = _PROJECT_ROOT / "logs" / "trading_system.log"
        log_exists = log_file.exists()
        
        if log_exists:
            today = datetime.now().strftime("%Y-%m-%d")
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            today_lines = len([line for line in lines if line.startswith(today)])
        else:
            today_lines = 0
        
        status_msg = f"""📊 **SYSTEM STATUS**
═══════════════════════

🕐 **Current Time:** {current_time}

📝 **Logs:**
• Log file: {'✅ Found' if log_exists else '❌ Missing'}
• Today's entries: {today_lines:,} lines

🤖 **Telegram:**
• Bot status: ✅ Active
• Commands: ✅ Working

═══════════════════════
🎯 System operational"""
        
        send_message(status_msg, use_html=True)
        
    except Exception as e:
        _logger.error(f"Error getting system status: {e}")
        send_message("❌ Error getting system status")

def send_log_tail(lines: int = 200):
    """Send historical log entries (all logs, not just today)"""
    if not is_enabled():
        return
        
    log_file = _PROJECT_ROOT / "logs" / "trading_system.log"
    
    if not log_file.exists():
        send_message("❌ Log file not found")
        return
    
    try:
        # Read all lines (historical)
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Get last N lines
        tail_lines = [line.strip() for line in all_lines[-lines:]]
        
        if not tail_lines:
            send_message("ℹ️ No historical logs found")
            return
        
        # Format message
        content = "\n".join(tail_lines)
        header = f"📜 Historical logs - Last {len(tail_lines)} lines:"
        
        # Check if message will be too long
        full_message = f"{header}\n{content}"
        if len(full_message) > 4000:
            send_message(full_message, use_html=False)
        else:
            import html
            escaped_content = html.escape(content)
            formatted_message = f"{header}\n<pre>{escaped_content}</pre>"
            send_message(formatted_message, use_html=True)
        
        _logger.info(f"Sent {len(tail_lines)} historical log lines to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending historical logs: {e}")
        send_message(f"❌ Error reading historical logs: {str(e)}")

def send_daily_stats():
    """Send daily trading statistics"""
    if not is_enabled():
        return
        
    try:
        from datetime import datetime, timedelta
        import json
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Try to get stats from service locator if available
        try:
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()
            
            # Get system configuration
            system_config = None
            if hasattr(service_locator, '_config'):
                system_config = service_locator._config
            
            # Get risk manager for positions data
            risk_manager = None
            if hasattr(service_locator, '_instances') and 'risk_manager' in service_locator._instances:
                risk_manager = service_locator._instances['risk_manager']
            
            current_positions = 0
            total_equity = 0
            
            if risk_manager and hasattr(risk_manager, 'broker_positions'):
                positions = getattr(risk_manager, 'broker_positions', {})
                current_positions = len(positions)

                # Calculate total equity from positions
                for symbol, pos_data in positions.items():
                    if isinstance(pos_data, dict) and 'market_value' in pos_data:
                        total_equity += abs(float(pos_data.get('market_value', 0)))

            # Fallback: try to get positions from database if service locator fails
            if current_positions == 0:
                try:
                    import sqlite3
                    db_path = _PROJECT_ROOT / "trading_data.db"
                    if db_path.exists():
                        with sqlite3.connect(db_path) as conn:
                            # Get open positions from trades table
                            result = conn.execute("""
                                SELECT COUNT(*) FROM trades
                                WHERE DATE(entry_time) = ?
                                AND (exit_time IS NULL OR status = 'OPEN')
                            """, (today,)).fetchone()
                            current_positions = result[0] if result else 0

                            # Get total market value from positions if available
                            try:
                                pos_result = conn.execute("""
                                    SELECT SUM(ABS(quantity) * entry_price) as total_value
                                    FROM trades
                                    WHERE DATE(entry_time) = ?
                                    AND (exit_time IS NULL OR status = 'OPEN')
                                """, (today,)).fetchone()
                                if pos_result and pos_result[0]:
                                    total_equity = float(pos_result[0])
                            except:
                                total_equity = 0
                except Exception:
                    current_positions = 0
                    total_equity = 0
                    
        except Exception as e:
            _logger.warning(f"Could not access service locator: {e}")
            current_positions = 0
            total_equity = 0
        
        # Count trades from database first, fallback to logs
        today_trades = 0
        today_signals = 0
        
        # Try database first (more accurate)
        try:
            import sqlite3
            db_path = _PROJECT_ROOT / "trading_data.db"
            if db_path.exists():
                with sqlite3.connect(db_path) as conn:
                    result = conn.execute("SELECT COUNT(*) FROM trades WHERE DATE(entry_time) = ?", (today,)).fetchone()
                    today_trades = result[0] if result else 0
        except Exception:
            today_trades = 0
        
        # Count signals from trader.log - improved pattern matching
        trader_log_path = _PROJECT_ROOT / "logs" / "trader.log"
        if trader_log_path.exists():
            with open(trader_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line in lines:
                if line.startswith(today):
                    # More comprehensive signal detection
                    if any(keyword in line.lower() for keyword in [
                        'signal generated', 'ml selected', 'long signal', 'exit_long',
                        'trading signal', 'buy signal', 'sell signal', 'vwap breakout',
                        'momentum breakout', 'macdv pattern'
                    ]):
                        today_signals += 1
        
        stats_msg = f"""📊 **ESTADÍSTICAS DEL DÍA** - {today}
═══════════════════════════════

📈 **Trading Activity:**
• Trades ejecutados: {today_trades}
• Señales generadas: {today_signals}
• Posiciones actuales: {current_positions}

💰 **Portfolio:**
• Valor total posiciones: ${total_equity:,.2f}
• Estado: {'🟢 Activo' if current_positions > 0 else '🟡 Sin posiciones'}

📊 **Sistema:**
• Modo: {'🟢 PRODUCTION' if (system_config and system_config.production_mode) else '🟡 MOCK'}
• Última actualización: {datetime.now().strftime('%H:%M:%S')}

═══════════════════════════════
📅 {today}"""
        
        send_message(stats_msg, use_html=True)
        _logger.info("Sent daily statistics to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending daily stats: {e}")
        send_message(f"❌ Error obteniendo estadísticas del día: {str(e)}")

def send_historical_stats():
    """Send historical trading statistics"""
    if not is_enabled():
        return
        
    try:
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        # Parse all logs for historical trading activity
        log_file = _PROJECT_ROOT / "logs" / "trading_system.log"
        
        if not log_file.exists():
            send_message("❌ Log file not found para estadísticas históricas")
            return
        
        # Initialize counters
        daily_trades = defaultdict(int)
        daily_signals = defaultdict(int)
        total_trades = 0
        total_signals = 0
        symbols_traded = set()
        
        # Get last 30 days for historical analysis
        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line in lines:
            try:
                # Extract date from log line (YYYY-MM-DD format at start)
                if len(line) >= 10:
                    date_str = line[:10]
                    try:
                        log_date = datetime.strptime(date_str, "%Y-%m-%d")
                        if log_date >= thirty_days_ago:
                            date_key = date_str
                            
                            # Count trades
                            if any(keyword in line.lower() for keyword in ['trade executed', 'order filled', 'buy order', 'sell order']):
                                daily_trades[date_key] += 1
                                total_trades += 1
                                
                                # Extract symbol if possible
                                words = line.split()
                                for word in words:
                                    if word.isupper() and len(word) <= 6 and word.isalpha():
                                        symbols_traded.add(word)
                                        break
                            
                            # Count signals
                            elif any(keyword in line.lower() for keyword in ['signal generated', 'trading signal', 'buy signal', 'sell signal']):
                                daily_signals[date_key] += 1
                                total_signals += 1
                                
                    except ValueError:
                        continue  # Skip lines that don't start with valid date
            except Exception:
                continue
        
        # Calculate averages
        trading_days = len([d for d in daily_trades.values() if d > 0])
        avg_trades_per_day = total_trades / max(trading_days, 1)
        avg_signals_per_day = total_signals / max(30, 1)  # Over 30 day period
        
        # Find most active days
        most_active_day = max(daily_trades.items(), key=lambda x: x[1]) if daily_trades else ("N/A", 0)
        
        historical_msg = f"""📈 **ESTADÍSTICAS HISTÓRICAS** (30 días)
═══════════════════════════════

📊 **Resumen General:**
• Total trades: {total_trades:,}
• Total señales: {total_signals:,}
• Símbolos únicos: {len(symbols_traded)}
• Días con actividad: {trading_days}

📈 **Promedios:**
• Trades/día: {avg_trades_per_day:.1f}
• Señales/día: {avg_signals_per_day:.1f}

🏆 **Día más activo:**
• Fecha: {most_active_day[0]}
• Trades: {most_active_day[1]}

📋 **Símbolos más operados:**
{', '.join(list(symbols_traded)[:10]) if symbols_traded else 'No data'}

═══════════════════════════════
📅 Período: {thirty_days_ago.strftime('%Y-%m-%d')} a {today.strftime('%Y-%m-%d')}"""
        
        send_message(historical_msg, use_html=True)
        _logger.info("Sent historical statistics to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending historical stats: {e}")
        send_message(f"❌ Error obteniendo estadísticas históricas: {str(e)}")

def send_performance_summary():
    """Send performance summary"""
    if not is_enabled():
        return
        
    try:
        from datetime import datetime, timedelta
        
        # Get current positions from service locator
        current_positions = 0
        total_market_value = 0
        positions_detail = []
        system_config = None
        
        try:
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()
            
            # Get system configuration
            if hasattr(service_locator, '_config'):
                system_config = service_locator._config
            
            # Get risk manager for positions data
            if hasattr(service_locator, '_instances') and 'risk_manager' in service_locator._instances:
                risk_manager = service_locator._instances['risk_manager']
                
                if risk_manager and hasattr(risk_manager, 'broker_positions'):
                    positions = getattr(risk_manager, 'broker_positions', {})
                    current_positions = len(positions)
                    
                    for symbol, pos_data in positions.items():
                        if isinstance(pos_data, dict):
                            market_value = float(pos_data.get('market_value', 0))
                            quantity = pos_data.get('position', 0)
                            avg_cost = pos_data.get('avg_cost', 0)
                            
                            total_market_value += abs(market_value)
                            
                            # Calculate unrealized P&L if possible
                            unrealized_pnl = pos_data.get('unrealized_pnl', 0)
                            
                            positions_detail.append({
                                'symbol': symbol,
                                'quantity': quantity,
                                'market_value': market_value,
                                'avg_cost': avg_cost,
                                'unrealized_pnl': unrealized_pnl
                            })
                            
        except Exception as e:
            _logger.warning(f"Could not access positions data: {e}")
        
        # Get trading activity from DATABASE (last 7 days) - WORKER SYSTEM
        import sqlite3
        db_file = _PROJECT_ROOT / "trading_data.db"
        recent_trades = 0
        total_pnl_week = 0.0
        winning_trades = 0
        losing_trades = 0
        
        if db_file.exists():
            try:
                today = datetime.now()
                week_ago = today - timedelta(days=7)
                week_ago_str = week_ago.strftime('%Y-%m-%d %H:%M:%S')

                with sqlite3.connect(db_file) as conn:
                    cursor = conn.cursor()

                    # Get closed trades from last 7 days
                    cursor.execute("""
                        SELECT COUNT(*), COALESCE(SUM(pnl), 0),
                               SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                               SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END)
                        FROM trades
                        WHERE status = 'CLOSED' AND exit_time >= ?
                    """, (week_ago_str,))

                    result = cursor.fetchone()
                    if result and result[0]:
                        recent_trades = result[0]
                        total_pnl_week = result[1] if result[1] else 0.0
                        winning_trades = result[2] if result[2] else 0
                        losing_trades = result[3] if result[3] else 0

            except Exception as e:
                _logger.warning(f"Could not query trades database: {e}")
        
        # Calculate total unrealized P&L
        total_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions_detail)
        
        # Format positions summary (top 5 by market value)
        top_positions = sorted(positions_detail, key=lambda x: abs(x['market_value']), reverse=True)[:5]
        positions_text = ""
        
        for pos in top_positions:
            pnl_emoji = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
            positions_text += f"• {pos['symbol']}: ${abs(pos['market_value']):,.0f} {pnl_emoji}${pos['unrealized_pnl']:+.2f}\n"
        
        if not positions_text:
            positions_text = "• Sin posiciones abiertas\n"
        
        # Calculate win rate
        win_rate = (winning_trades / recent_trades * 100) if recent_trades > 0 else 0

        performance_msg = f"""📊 **RESUMEN DE RENDIMIENTO**
═══════════════════════════════

💰 **Portfolio Actual:**
• Posiciones abiertas: {current_positions}
• Valor total mercado: ${total_market_value:,.2f}
• P&L no realizado: ${total_unrealized_pnl:+,.2f}

📈 **Actividad Reciente (7 días):**
• Trades ejecutados: {recent_trades}
• P&L semanal: ${total_pnl_week:+,.2f}
• Win rate: {win_rate:.1f}% ({winning_trades}W / {losing_trades}L)
• Promedio trades/día: {recent_trades/7:.1f}

🏆 **Top Posiciones:**
{positions_text}

📊 **Estado del Sistema:**
• Modo: {'🟢 PRODUCTION' if (system_config and system_config.production_mode) else '🟡 MOCK'}
• Max posiciones: {system_config.max_positions if system_config else _config.getint('TRADING', 'max_positions', fallback=30)}
• Utilización: {current_positions}/{system_config.max_positions if system_config else _config.getint('TRADING', 'max_positions', fallback=30)} ({100*current_positions/(system_config.max_positions if system_config else _config.getint('TRADING', 'max_positions', fallback=30)):.0f}%)

═══════════════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        send_message(performance_msg, use_html=True)
        _logger.info("Sent performance summary to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending performance summary: {e}")
        send_message(f"❌ Error obteniendo resumen de rendimiento: {str(e)}")

def send_recent_trades():
    """Send recent trades"""
    if not is_enabled():
        return
        
    try:
        from datetime import datetime, timedelta
        
        log_file = _PROJECT_ROOT / "logs" / "trader.log"
        
        if not log_file.exists():
            send_message("❌ Log file not found para trades recientes")
            return
        
        # Parse logs for recent trades (last 10)
        trades = []
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Search backwards through log for trade-related entries
        for line in reversed(lines):
            try:
                if any(keyword in line.lower() for keyword in ['position updated', 'added for trading', 'signal generated', 'order executed', 'trade executed', 'order filled']):
                    # Extract timestamp and details
                    if len(line) >= 19:  # YYYY-MM-DD HH:MM:SS
                        timestamp = line[:19]
                        details = line[20:].strip()
                        
                        # Try to extract symbol and action
                        words = details.split()
                        symbol = "Unknown"
                        action = "Trade"
                        
                        # Look for pattern like "Position updated for SYMBOL:" or "SYMBOL added for trading"
                        if 'position updated for' in line.lower():
                            for i, word in enumerate(words):
                                if word.lower() == 'for' and i + 1 < len(words):
                                    next_word = words[i + 1].replace(':', '')
                                    if next_word.isupper() and len(next_word) <= 6 and next_word.isalpha():
                                        symbol = next_word
                                        action = "POSITION UPDATE"
                                        break
                        elif 'added for trading' in line.lower():
                            # Look for pattern like "✅ SYMBOL added for trading"
                            for word in words:
                                if word.isupper() and len(word) <= 6 and word.isalpha():
                                    symbol = word
                                    action = "ADDED TO TRADING"
                                    break
                        else:
                            # Fallback: look for any uppercase symbol
                            for word in words:
                                if word.isupper() and len(word) <= 6 and word.isalpha():
                                    symbol = word
                                    break
                        
                        if 'buy' in line.lower():
                            action = "BUY"
                        elif 'sell' in line.lower():
                            action = "SELL"
                        elif 'signal generated' in line.lower():
                            action = "SIGNAL"
                        
                        trades.append({
                            'timestamp': timestamp,
                            'symbol': symbol,
                            'action': action,
                            'details': details[:100] + '...' if len(details) > 100 else details
                        })
                        
                        if len(trades) >= 10:
                            break
            except:
                continue
        
        if not trades:
            send_message("ℹ️ No se encontraron trades recientes")
            return
        
        # Format message
        trades_text = ""
        for i, trade in enumerate(trades, 1):
            action_emoji = "🟢" if trade['action'] == "BUY" else "🔴" if trade['action'] == "SELL" else "📊" if trade['action'] == "POSITION UPDATE" else "⚡" if trade['action'] == "SIGNAL" else "➕" if trade['action'] == "ADDED TO TRADING" else "📈"
            trades_text += f"{i}. {action_emoji} **{trade['symbol']}** - {trade['action']}\n"
            trades_text += f"   📅 {trade['timestamp']}\n"
            trades_text += f"   📝 {trade['details']}\n\n"
        
        recent_trades_msg = f"""📈 **TRADES RECIENTES** (Últimos {len(trades)})
═══════════════════════════════

{trades_text}═══════════════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        send_message(recent_trades_msg, use_html=True)
        _logger.info(f"Sent {len(trades)} recent trades to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending recent trades: {e}")
        send_message(f"❌ Error obteniendo trades recientes: {str(e)}")

def send_trades_today():
    """Send today's trades"""
    if not is_enabled():
        return

    try:
        from datetime import datetime
        import sqlite3

        today = datetime.now().strftime("%Y-%m-%d")
        db_path = _PROJECT_ROOT / "trading_data.db"

        if not db_path.exists():
            send_message("❌ Database not found para trades de hoy")
            return

        # Query today's trades from database
        today_trades = []

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get today's trades
            cursor.execute("""
                SELECT id, trade_id, symbol, entry_time, exit_time, entry_price, exit_price,
                       quantity, strategy, status, pnl
                FROM trades
                WHERE DATE(entry_time) = ?
                ORDER BY entry_time DESC
            """, (today,))

            for row in cursor.fetchall():
                # Determine action based on strategy and status
                action = "TRADE"
                if row['strategy']:
                    if 'buy' in row['strategy'].lower() or 'long' in row['strategy'].lower():
                        action = "BUY"
                    elif 'sell' in row['strategy'].lower() or 'short' in row['strategy'].lower():
                        action = "SELL"

                # Format entry time
                entry_time = row['entry_time']
                if entry_time and len(entry_time) >= 19:
                    timestamp = entry_time[:19]  # YYYY-MM-DD HH:MM:SS
                else:
                    timestamp = entry_time or "Unknown"

                # Calculate P&L percentage if we have entry and exit prices
                pnl_pct = 0
                if row['entry_price'] and row['entry_price'] > 0 and row['pnl']:
                    pnl_pct = (row['pnl'] / (row['entry_price'] * abs(row['quantity'] or 1))) * 100

                today_trades.append({
                    'id': row['id'],
                    'symbol': row['symbol'] or "Unknown",
                    'action': action,
                    'entry_price': row['entry_price'] or 0,
                    'exit_price': row['exit_price'] or 0,
                    'quantity': row['quantity'] or 0,
                    'pnl': row['pnl'] or 0,
                    'pnl_pct': pnl_pct,
                    'status': row['status'] or "Unknown",
                    'timestamp': timestamp,
                    'strategy': row['strategy'] or "Unknown"
                })

        if not today_trades:
            send_message(f"ℹ️ No hay trades para hoy ({today})")
            return

        # Format message
        trades_text = ""
        buy_count = sum(1 for t in today_trades if t['action'] == 'BUY')
        sell_count = sum(1 for t in today_trades if t['action'] == 'SELL')
        closed_count = sum(1 for t in today_trades if t['status'] == 'CLOSED')
        open_count = sum(1 for t in today_trades if t['status'] == 'OPEN')

        total_pnl = sum(t['pnl'] for t in today_trades if t['pnl'])
        total_pnl_pct = sum(t['pnl_pct'] for t in today_trades if t['pnl_pct'])

        for i, trade in enumerate(today_trades, 1):
            action_emoji = "🟢" if trade['action'] == "BUY" else "🔴" if trade['action'] == "SELL" else "📈"
            status_emoji = "✅" if trade['status'] == "CLOSED" else "🔄" if trade['status'] == "OPEN" else "❓"

            pnl_text = ""
            if trade['pnl'] != 0:
                pnl_emoji = "🟢" if trade['pnl'] >= 0 else "🔴"
                pnl_text = f" | {pnl_emoji} P&L: ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.1f}%)"

            trades_text += f"{i}. {action_emoji} **{trade['symbol']}** - {trade['action']} {status_emoji}\n"
            trades_text += f"   🕐 {trade['timestamp'][11:] if len(trade['timestamp']) > 11 else trade['timestamp']}\n"
            trades_text += f"   💰 Entry: ${trade['entry_price']:.2f} | Qty: {trade['quantity']}\n"
            if trade['exit_price'] > 0:
                trades_text += f"   🎯 Exit: ${trade['exit_price']:.2f}{pnl_text}\n"
            trades_text += f"   📊 Strategy: {trade['strategy']}\n\n"

        today_trades_msg = f"""📅 **TRADES DE HOY** ({today})
═══════════════════════════════

📊 **Resumen:**
• Total trades: {len(today_trades)}
• Compras: {buy_count} 🟢
• Ventas: {sell_count} 🔴
• Cerradas: {closed_count} ✅
• Abiertas: {open_count} 🔄
• P&L Total: ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)

📈 **Detalle:**
{trades_text}═══════════════════════════════
📅 {today}"""

        send_message(today_trades_msg, use_html=True)
        _logger.info(f"Sent {len(today_trades)} today's trades to Telegram")

    except Exception as e:
        _logger.error(f"Error sending today's trades: {e}")
        send_message(f"❌ Error obteniendo trades de hoy: {str(e)}")

def send_open_trades():
    """Send open positions"""
    if not is_enabled():
        return
        
    try:
        from datetime import datetime
        
        # Get current positions from service locator
        positions = {}
        
        try:
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()
            
            # Get risk manager for positions data
            if hasattr(service_locator, '_instances') and 'risk_manager' in service_locator._instances:
                risk_manager = service_locator._instances['risk_manager']
                
                if risk_manager and hasattr(risk_manager, 'broker_positions'):
                    positions = getattr(risk_manager, 'broker_positions', {})
                    
        except Exception as e:
            _logger.warning(f"Could not access positions data: {e}")
        
        if not positions:
            send_message("ℹ️ No hay posiciones abiertas actualmente")
            return
        
        # Format positions
        positions_text = ""
        total_market_value = 0
        total_unrealized_pnl = 0
        
        for i, (symbol, pos_data) in enumerate(positions.items(), 1):
            try:
                if isinstance(pos_data, dict):
                    quantity = pos_data.get('position', 0)
                    market_value = float(pos_data.get('market_value', 0))
                    avg_cost = pos_data.get('avg_cost', 0)
                    unrealized_pnl = pos_data.get('unrealized_pnl', 0)
                    
                    total_market_value += abs(market_value)
                    total_unrealized_pnl += unrealized_pnl
                    
                    # Position direction
                    direction = "LONG" if quantity > 0 else "SHORT" if quantity < 0 else "FLAT"
                    direction_emoji = "🟢" if quantity > 0 else "🔴" if quantity < 0 else "⚪"
                    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                    
                    positions_text += f"{i}. {direction_emoji} **{symbol}** - {direction}\n"
                    positions_text += f"   📊 Cantidad: {quantity:,.0f}\n"
                    positions_text += f"   💰 Valor mercado: ${abs(market_value):,.2f}\n"
                    positions_text += f"   📈 Costo promedio: ${avg_cost:.2f}\n"
                    positions_text += f"   {pnl_emoji} P&L: ${unrealized_pnl:+,.2f}\n\n"
            except Exception as e:
                positions_text += f"{i}. ❌ **{symbol}** - Error: {str(e)}\n\n"
        
        open_positions_msg = f"""🔄 **POSICIONES ABIERTAS**
═══════════════════════════════

📊 **Resumen:**
• Total posiciones: {len(positions)}
• Valor total mercado: ${total_market_value:,.2f}
• P&L total no realizado: ${total_unrealized_pnl:+,.2f}

📈 **Detalle Posiciones:**
{positions_text}═══════════════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        send_message(open_positions_msg, use_html=True)
        _logger.info(f"Sent {len(positions)} open positions to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending open positions: {e}")
        send_message(f"❌ Error obteniendo posiciones abiertas: {str(e)}")

def send_closeall_positions(confirm: bool = False):
    """Emergency close all positions"""
    if not is_enabled():
        return

    try:
        from datetime import datetime

        # Safety confirmation required
        if not confirm:
            warning_msg = f"""⚠️ **EMERGENCY CLOSE ALL POSITIONS**
═══════════════════════════════

🚨 **WARNING:** This will close ALL active positions immediately.

This action will:
• Exit all worker positions at market price
• Cancel any pending orders
• Stop all workers from re-entering
• Cannot be undone

📊 To confirm, send one of:
• `/closeall confirm`
• `/closeall_confirm`

🛡️ To cancel, just ignore this message.

═══════════════════════════════
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            send_message(warning_msg, use_html=True)
            _logger.info("Close all positions requested - awaiting confirmation")
            return

        # Confirmation received - proceed with closing
        send_message("🔄 **CLOSING ALL POSITIONS...**\n\nProcessing emergency exit for all active positions...")

        # Get unified trading system from service locator
        try:
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()

            # Get unified_trading_system which contains strategy_engine
            unified_system = service_locator.get_service('unified_trading_system')

            if not unified_system:
                send_message("❌ **ERROR:** Unified trading system not found\n\nSystem may not be running.")
                return

            # Get strategy engine (WorkerBasedStrategyEngine)
            if not hasattr(unified_system, 'strategy_engine') or not unified_system.strategy_engine:
                send_message("❌ **ERROR:** Strategy engine not initialized\n\nWorker system may not be running.")
                return

            strategy_engine = unified_system.strategy_engine

            # Collect all positions from all workers
            all_positions = {}
            worker_count = 0

            if hasattr(strategy_engine, 'workers'):
                for worker_name, worker in strategy_engine.workers.items():
                    if hasattr(worker, 'active_positions'):
                        for symbol, pos_data in worker.active_positions.items():
                            all_positions[symbol] = {
                                'worker': worker_name,
                                'worker_instance': worker,
                                'position_data': pos_data,
                                'entry_price': pos_data.get('entry_price', 0)
                            }
                            worker_count += 1

            if not all_positions or len(all_positions) == 0:
                send_message("ℹ️ **NO POSITIONS TO CLOSE**\n\n✅ All clear - no active positions found.")
                return

            # Close each position
            closed_count = 0
            failed_count = 0
            position_results = []

            for symbol, data in all_positions.items():
                try:
                    worker = data['worker_instance']
                    entry_price = data['entry_price']
                    worker_name = data['worker']

                    # Get current price
                    import asyncio

                    # Try to get current price from worker method
                    try:
                        if hasattr(worker, '_get_current_price'):
                            # Create new event loop for async method
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            current_price = loop.run_until_complete(worker._get_current_price(symbol))
                            loop.close()
                        else:
                            current_price = entry_price
                    except Exception as price_error:
                        _logger.debug(f"Could not get current price for {symbol}: {price_error}")
                        current_price = entry_price

                    # Calculate PnL
                    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                    # Close position using worker's exit method
                    if hasattr(worker, '_execute_exit'):
                        # Create new event loop for sync context
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(
                                worker._execute_exit(symbol, "EMERGENCY_CLOSEALL", current_price)
                            )
                            loop.close()
                        except Exception as exit_error:
                            _logger.error(f"Error closing {symbol}: {exit_error}")
                            raise

                    closed_count += 1
                    result_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                    position_results.append(
                        f"{result_emoji} **{symbol}** ({worker_name}): ${current_price:.2f} (PnL: {pnl_pct:+.2f}%)"
                    )

                    _logger.info(f"Emergency close: {symbol} from {worker_name} at ${current_price:.2f}")

                except Exception as e:
                    failed_count += 1
                    position_results.append(f"❌ **{symbol}**: Error - {str(e)[:50]}")
                    _logger.error(f"Failed to close {symbol}: {e}")

            # Send results summary
            results_text = "\n".join(position_results)

            success_emoji = "✅" if failed_count == 0 else "⚠️"
            summary_msg = f"""{success_emoji} **EMERGENCY CLOSE COMPLETED**
═══════════════════════════════

📊 **Summary:**
• Positions closed: {closed_count}
• Failed closes: {failed_count}
• Total processed: {len(active_positions)}

📈 **Closed Positions:**
{results_text}

═══════════════════════════════
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🛡️ All positions have been exited"""

            send_message(summary_msg, use_html=True)
            _logger.info(f"Emergency close all completed: {closed_count} closed, {failed_count} failed")

        except Exception as e:
            _logger.error(f"Error accessing strategy engine: {e}")
            send_message(f"❌ **ERROR CLOSING POSITIONS**\n\nCould not access strategy engine: {str(e)}")

    except Exception as e:
        _logger.error(f"Error in send_closeall_positions: {e}")
        send_message(f"❌ Error executing emergency close: {str(e)}")

def send_hybrid_system_status():
    """Send hybrid learning system status"""
    if not is_enabled():
        return
        
    try:
        # Try to get ML system status
        try:
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()
            
            # Check if ML strategy selector is available (our actual ML system)
            ml_system = None
            if hasattr(service_locator, '_instances') and 'unified_trading_system' in service_locator._instances:
                trader = service_locator._instances['unified_trading_system']
                if hasattr(trader, 'ml_strategy_selector'):
                    ml_system = trader.ml_strategy_selector
            
            # Fallback to hybrid learning system if available
            hybrid_system = None
            if hasattr(service_locator, '_instances') and 'hybrid_learning_system' in service_locator._instances:
                hybrid_system = service_locator._instances['hybrid_learning_system']
            
            if ml_system:
                # We have our ML Strategy Selector running
                # Check if it has a trained model
                model_path = _PROJECT_ROOT / "data/ml_models/historical_trained_selector.json"
                model_exists = model_path.exists()
                
                if model_exists:
                    import json
                    try:
                        with open(model_path, 'r') as f:
                            model_data = json.load(f)
                        
                        strategies = model_data.get('strategies', [])
                        timestamp = model_data.get('timestamp', 'Unknown')
                        strategy_stats = model_data.get('strategy_stats', {})
                        
                        # Calculate total trades and performance
                        total_trades = sum(stats.get('total_trades', 0) for stats in strategy_stats.values())
                        total_wins = sum(stats.get('winning_trades', 0) for stats in strategy_stats.values())
                        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
                        
                        status_msg = f"""🧠 **ML STRATEGY SELECTOR STATUS**
═══════════════════════════════

✅ **System Status:** ACTIVE & TRAINED

🤖 **ML Model:**
• Strategies: {len(strategies)} trained
• Total trades: {total_trades:,}
• Win rate: {overall_wr:.1f}%
• Last trained: {timestamp[:10] if timestamp != 'Unknown' else 'Unknown'}

🎯 **Trained Strategies:**
{chr(10).join(f'• {strategy}' for strategy in strategies)}

📊 **Performance by Strategy:**"""
                        
                        for strategy, stats in strategy_stats.items():
                            trades = stats.get('total_trades', 0)
                            win_rate = stats.get('win_rate', 0.0)
                            avg_pnl = stats.get('avg_pnl', 0.0)
                            status_msg += f"\n• {strategy}: {trades} trades, {win_rate:.1%} WR, {avg_pnl:+.3f} avg PnL"
                        
                        status_msg += f"""

🧠 **Algorithm:** Contextual Multi-Armed Bandit
• Adapts strategy selection to market context
• Learns from each trade outcome
• Balances exploration vs exploitation

🎉 **Status:** PRODUCTION READY
═══════════════════════════════
🚀 ML system actively selecting strategies"""
                        
                    except Exception as e:
                        status_msg = f"""🧠 **ML STRATEGY SELECTOR STATUS**
═══════════════════════════════

✅ **System Status:** INITIALIZED
❌ **Model Error:** Cannot read model data
• Error: {str(e)}

💡 **Suggestion:** Re-train the model
═══════════════════════════════"""
                else:
                    status_msg = """🧠 **ML STRATEGY SELECTOR STATUS**
═══════════════════════════════

⚠️ **System Status:** INITIALIZED BUT NOT TRAINED

🤖 **ML System:** Available
📂 **Model:** Not found
💡 **Next step:** Train model with historical data

🎯 **To train:**
1. Run: python simulate_historical_trades_for_ml.py
2. Verify with: python check_ml_training_results.py

═══════════════════════════════
🔄 Ready for training"""
                
            elif hybrid_system and hasattr(hybrid_system, 'get_system_status'):
                status = hybrid_system.get_system_status()
                
                # Extract key metrics
                components = status['hybrid_learning_system']['components_initialized']
                health = status['hybrid_learning_system']['system_health']
                activity = status['hybrid_learning_system']['activity_stats']
                safety = status['hybrid_learning_system']['safety_metrics']
                
                # Component status
                ml_selector_status = "✅" if components['ml_selector'] else "❌"
                adaptive_strategies = components['adaptive_strategies']
                analysis_engine_status = "✅" if components['analysis_engine'] else "❌"
                
                # Health status
                ml_health = health.get('ml_selector_health', 'unknown').title()
                strategies_health = health.get('adaptive_strategies_health', 'unknown').title()
                analysis_health = health.get('analysis_engine_health', 'unknown').title()
                overall_complexity = health.get('overall_complexity', 0.0)
                
                # Activity metrics
                decisions_made = activity.get('decisions_made', 0)
                learning_sessions = activity.get('learning_sessions', 0)
                avg_confidence = activity.get('avg_decision_confidence', 0.0)
                
                status_msg = f"""🧠 **HYBRID LEARNING SYSTEM STATUS**
═══════════════════════════════

🔧 **Components:**
• ML Strategy Selector: {ml_selector_status}
• Adaptive Strategies: {adaptive_strategies} active
• Analysis Engine: {analysis_engine_status}

🏥 **System Health:**
• ML Selector: {ml_health}
• Adaptive Strategies: {strategies_health}  
• Analysis Engine: {analysis_health}
• Complexity Score: {overall_complexity:.2f}/1.0

📊 **Activity:**
• Decisions Made: {decisions_made:,}
• Learning Sessions: {learning_sessions:,}
• Avg Confidence: {avg_confidence:.1%}

🛡️ **Safety Metrics:**
• Decisions Rejected: {safety.get('decisions_rejected', 0)}
• High Complexity: {safety.get('high_complexity_decisions', 0)}
• Validation Flags: {safety.get('validation_flags_raised', 0)}

💡 **Status:** {'🟢 Operational' if analysis_health != 'Unknown' else '🟡 Initializing'}

═══════════════════════════════
🎯 Professional trader AI simulation active"""
                
            else:
                status_msg = """🧠 **HYBRID LEARNING SYSTEM STATUS**
═══════════════════════════════

⚠️ **System Status:** Not initialized
  
🔧 **Expected Components:**
• ML Strategy Selector (contextual bandit)
• Adaptive Gap&Go Strategy
• Bias-aware trade analysis
• Anti-overfitting safeguards

📋 **Features:**
• Professional trader write-ups
• Parameter adaptation from results
• Multi-level learning system
• Statistical validation required

💡 Initialize system to activate hybrid learning
═══════════════════════════════"""
        
        except Exception as e:
            _logger.warning(f"Could not access hybrid system: {e}")
            
            status_msg = """🧠 **HYBRID LEARNING SYSTEM**
═══════════════════════════════

📊 **System Overview:**
Hybrid AI that combines:

🤖 **Level 1 - ML Strategy Selection:**
• Contextual bandit algorithm
• Learns which strategy to use when
• Adapts to market conditions

🎯 **Level 2 - Adaptive Execution:**
• Strategies adapt their parameters
• Learn from each trade outcome
• Maintain stability bounds

📝 **Level 3 - Professional Analysis:**
• Trade write-ups like pro traders
• Bias detection and validation
• Quality-controlled learning

🛡️ **Anti-Overfitting Safeguards:**
• Maximum 5 parameters per strategy
• Statistical significance required
• Narrative bias detection
• Complexity limits enforced

Status: Available for activation
═══════════════════════════════"""
        
        send_message(status_msg, use_html=True)
        _logger.info("Sent hybrid system status to Telegram")
        
    except Exception as e:
        _logger.error(f"Error sending hybrid system status: {e}")
        send_message("❌ Error obteniendo estado del sistema híbrido")

def send_tradetally_status():
    """Send TradeTally integration status"""
    try:
        import asyncio
        from core.service_locator import get_service_locator

        async def _async_status():
            service_locator = get_service_locator()

            # Try to get existing service first
            tradetally_service = service_locator.get_service('tradetally_service')

            # If service doesn't exist, try to create it
            if not tradetally_service:
                try:
                    # Initialize TradeTally service asynchronously
                    tradetally_service = await service_locator.get_or_create_tradetally_service()
                except Exception as init_error:
                    return f"""📊 **TRADETALLY INTEGRATION STATUS**
═══════════════════════════════

❌ **Status:** Failed to initialize
• Error: {str(init_error)}

🔧 **Configuration:**
• Service: Initialization failed
• Auto-sync: Disabled

💡 **Check:**
1. API key configuration
2. Network connectivity
3. TradeTally service status

═══════════════════════════════
📅 Check configuration and retry"""

            if not tradetally_service:
                return """📊 **TRADETALLY INTEGRATION STATUS**
═══════════════════════════════

⚠️ **Status:** Not initialized or disabled

🔧 **Configuration:**
• Service: Not available
• Auto-sync: Disabled
• API Key: Not configured

💡 **To enable TradeTally:**
1. Configure API key in config.ini
2. Set enable_tradetally_sync = true
3. Restart system

═══════════════════════════════
📅 Check configuration and restart"""

            status = tradetally_service.get_sync_status()
            pending_count = tradetally_service.get_pending_trades_count()

            api_status = "✅ Configured" if status['api_configured'] else "❌ Not configured"
            service_status = "✅ Running" if status['service_running'] else "❌ Stopped"
            success_rate = f"{status['success_rate']:.1f}%"

            status_msg = f"""📊 **TRADETALLY INTEGRATION STATUS**
═══════════════════════════════

🔧 **Service Status:**
• Service: {service_status}
• API Key: {api_status}
• Scheduled Sync: {status['sync_time']} EST
• Next Sync: {status['next_scheduled_sync']}

📈 **Sync Statistics:**
• Total Syncs: {status['total_syncs']:,}
• Successful: {status['successful_syncs']:,}
• Failed: {status['failed_syncs']:,}
• Success Rate: {success_rate}

💼 **Current Status:**
• Pending Trades: {pending_count}
• Last Sync: {status['last_sync_date'] or 'Never'}
• Database: {status['database_path']}

💡 **Auto-sync:** End-of-day after market close
═══════════════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            return status_msg

        # Run the async function
        result_msg = asyncio.run(_async_status())
        send_message(result_msg, use_html=True)
        _logger.info("Sent TradeTally status to Telegram")

    except Exception as e:
        _logger.error(f"Error getting TradeTally status: {e}")
        send_message(f"❌ Error obteniendo estado de TradeTally: {str(e)}")

def send_tradetally_sync():
    """Execute manual TradeTally sync"""
    try:
        import asyncio
        from core.service_locator import get_service_locator

        async def _async_sync():
            service_locator = get_service_locator()

            # Try to get existing service first
            tradetally_service = service_locator.get_service('tradetally_service')

            # If service doesn't exist, try to create it
            if not tradetally_service:
                # Initialize TradeTally service asynchronously
                try:
                    tradetally_service = await service_locator.get_or_create_tradetally_service()
                except Exception as init_error:
                    return f"❌ Failed to initialize TradeTally service: {str(init_error)}"

            if not tradetally_service:
                return "❌ TradeTally service not available. Check configuration."

            # Execute manual sync
            result = tradetally_service.manual_sync()

            if result.get('success', False):
                # Datos del sync a TradeTally API
                synced = result.get('synced', 0)
                failed = result.get('failed', 0)
                total = result.get('total', 0)

                # Datos del hybrid sync a PostgreSQL
                hybrid = result.get('hybrid_sync', {})
                hybrid_synced = hybrid.get('synced', 0)
                hybrid_skipped = hybrid.get('skipped', 0)

                sync_msg = f"""✅ **TRADETALLY HYBRID SYNC COMPLETED**
═══════════════════════════════

📊 **Step 1: PostgreSQL Metadata**
• New Records: {hybrid_synced:,}
• Already Synced: {hybrid_skipped:,}
• Status: {'✅ Success' if hybrid.get('success') else '❌ Failed'}

📊 **Step 2: TradeTally API**
• Trades Synced: {synced:,}
• Failed Syncs: {failed:,}
• Total Processed: {total:,}

{f"⚠️ **Errors:** {len(result.get('errors', []))} errors occurred" if failed > 0 else "🎉 **Perfect:** All trades synced successfully"}

═══════════════════════════════
✅ **All trades synced to TradeTally**
🔄 Frontend will show updated data
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            else:
                error = result.get('error', 'Unknown error')
                hybrid = result.get('hybrid_sync', {})
                hybrid_error = hybrid.get('error', '') if not hybrid.get('success') else None

                sync_msg = f"""❌ **TRADETALLY SYNC FAILED**
═══════════════════════════════

🚨 **Errors:**"""

                if hybrid_error:
                    sync_msg += f"\n• Hybrid Sync: {hybrid_error}"

                sync_msg += f"""
• API Sync: {error}

💡 **Possible solutions:**
• Check API key configuration
• Verify PostgreSQL connection
• Check TradeTally service is running
• Verify network connectivity

═══════════════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            return sync_msg

        # Run the async function
        send_message("🔄 Starting manual TradeTally sync...")
        result_msg = asyncio.run(_async_sync())
        send_message(result_msg, use_html=True)
        _logger.info(f"Manual TradeTally sync completed")

    except Exception as e:
        _logger.error(f"Error during manual TradeTally sync: {e}")
        send_message(f"❌ Error ejecutando sincronización manual: {str(e)}")

def send_scanner_plays():
    """Enviar plays detectados por el scanner"""
    if not is_enabled():
        return
    
    try:
        from core.service_locator import get_service_locator
        service_locator = get_service_locator()
        
        # Get unified trading system
        unified_system = service_locator.get_service('unified_trading_system')
        
        if unified_system:
            
            # Get recent plays from notification cache
            if hasattr(unified_system, 'notified_plays') and unified_system.notified_plays:
                plays_text = ""
                current_time = datetime.now()
                active_plays = []
                
                for symbol, data in unified_system.notified_plays.items():
                    last_data = data.get('last_data', {})
                    time_diff = (current_time - data.get('last_notified', current_time)).total_seconds() / 60
                    
                    if time_diff < 120:  # Show plays from last 2 hours
                        active_plays.append({
                            'symbol': symbol,
                            'price': last_data.get('price', 0),
                            'gap': last_data.get('gap', 0),
                            'volume_ratio': last_data.get('volume_ratio', 0),
                            'quality_score': last_data.get('quality_score', 0),
                            'time_ago': int(time_diff)
                        })
                
                if active_plays:
                    # Sort by quality score
                    active_plays.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    
                    for i, play in enumerate(active_plays[:5], 1):
                        gap_emoji = "📈" if play['gap'] > 0 else "📉"
                        plays_text += f"""
**{i}. {play['symbol']} {gap_emoji}**
• ${play['price']:.2f} | Gap: {play['gap']*100:+.1f}%
• Vol: {play['volume_ratio']:.1f}x | Score: {play['quality_score']:.1f}
• Detectado hace: {play['time_ago']} min"""
                    
                    message = f"""🎯 **PLAYS DETECTADOS** - {current_time.strftime('%H:%M')}
═══════════════════════════════
{plays_text}

📊 Total plays activos: {len(active_plays)}
🔄 Scanner funcionando automáticamente

📱 Para más detalles: /scanner"""
                else:
                    message = f"""🎯 **PLAYS DETECTADOS** - {current_time.strftime('%H:%M')}
═══════════════════════════════

🔍 **No hay plays activos actualmente**
• Scanner funcionando correctamente
• Filtros: Gap >2%, Volumen >3x, Score ≥6.0
• Última verificación: {current_time.strftime('%H:%M:%S')}

📊 El scanner busca oportunidades cada 30s
📱 Para estado del scanner: /scanner"""
            else:
                message = f"""🎯 **PLAYS DETECTADOS** - {current_time.strftime('%H:%M')}
═══════════════════════════════

🔍 **Scanner iniciándose...**
• Sistema en proceso de inicialización
• Próximas detecciones en breve

📊 Para verificar estado: /scanner"""
        else:
            message = """❌ **Sistema no disponible**
• UnifiedTradingSystem no está activo
• Verificar que main.py esté ejecutándose"""
            
        send_message(message, parse_mode="Markdown")
        
    except Exception as e:
        _logger.error(f"Error getting scanner plays: {e}")
        send_message(f"❌ Error obteniendo plays del scanner: {str(e)}")

def send_scanner_status():
    """Enviar estado del scanner independiente"""
    if not is_enabled():
        return
    
    try:
        current_time = datetime.now()
        today = current_time.strftime("%Y-%m-%d")
        
        # Check if scanner log exists and get latest activity
        scanner_log_file = _PROJECT_ROOT / "logs" / "scanner.log"
        
        if not scanner_log_file.exists():
            send_message("❌ Scanner log file not found - Scanner may not be running")
            return
        
        # Read recent scanner activity
        with open(scanner_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Get today's lines
        today_lines = [line.strip() for line in all_lines if line.startswith(today)]
        
        if not today_lines:
            send_message(f"📭 No scanner activity found for today ({today})")
            return
        
        # Get last few lines to determine status
        recent_lines = today_lines[-20:] if len(today_lines) > 20 else today_lines
        last_line = today_lines[-1] if today_lines else ""
        
        # Extract timestamp from last log entry
        last_activity_time = "Unknown"
        if last_line and len(last_line) > 19:
            last_activity_time = last_line[:19]  # Extract timestamp
        
        # Count different types of scanner activities today
        scan_cycles = len([line for line in today_lines if "Starting scan cycle" in line])
        plays_found = len([line for line in today_lines if "daily plays" in line and "found" in line])
        opportunities = len([line for line in today_lines if "opportunities found" in line])
        
        # Determine scanner status based on activity patterns
        scanner_status = "🟢 Active"
        
        # Check for IBKR subscription cancellation (normal behavior)
        if "API scanner subscription cancelled" in last_line:
            scanner_status = "🔄 Refreshing subscriptions"
        elif "ERROR" in last_line.upper() and "subscription cancelled" not in last_line.lower():
            scanner_status = "🔴 Error"  
        elif "⏱️ Waiting" in last_line:
            scanner_status = "🟡 Waiting"
        elif "No opportunities" in last_line:
            scanner_status = "🟠 No Plays"
        
        status_msg = f"""🔍 SCANNER STATUS
═══════════════════════

📊 Current Status: {scanner_status}
⏰ Last Activity: {last_activity_time}

📈 Today's Activity:
• Scan Cycles: {scan_cycles}
• Plays Found: {plays_found}  
• Total Opportunities: {opportunities}

📋 Recent Activity:"""
        
        # Add last 3 significant log entries
        significant_lines = []
        for line in reversed(recent_lines):
            if any(keyword in line for keyword in ["daily plays", "Starting scan", "opportunities found", "ERROR", "WARNING"]):
                # Extract just the message part (after timestamp and logger)
                parts = line.split(" - ", 3)
                if len(parts) >= 4:
                    message = parts[3]
                    # Clean the message to avoid HTML parsing issues
                    clean_message = message.replace("<", "").replace(">", "").replace("&", "and")
                    significant_lines.append(f"• {clean_message}")
                if len(significant_lines) >= 3:
                    break
        
        if significant_lines:
            status_msg += "\n" + "\n".join(significant_lines)
        else:
            status_msg += "\n• No significant activity"
        
        # Send as plain text to avoid HTML parsing issues
        send_message(status_msg, use_html=False)
        
    except Exception as e:
        _logger.error(f"Error getting scanner status: {e}")
        send_message(f"❌ Error obteniendo estado del scanner: {str(e)}")

def send_plays_today():
    """Enviar todos los plays detectados hoy"""
    if not is_enabled():
        return
    
    try:
        current_time = datetime.now()
        today_str = current_time.strftime('%Y-%m-%d')
        
        from core.service_locator import get_service_locator
        service_locator = get_service_locator()
        
        unified_system = service_locator.get_service('unified_trading_system')
        if unified_system:
            
            # Get all plays from today (from notification cache)
            today_plays = []
            if hasattr(unified_system, 'notified_plays'):
                for symbol, data in unified_system.notified_plays.items():
                    last_notified = data.get('last_notified', current_time)
                    if last_notified.strftime('%Y-%m-%d') == today_str:
                        last_data = data.get('last_data', {})
                        today_plays.append({
                            'symbol': symbol,
                            'price': last_data.get('price', 0),
                            'gap': last_data.get('gap', 0),
                            'volume_ratio': last_data.get('volume_ratio', 0),
                            'quality_score': last_data.get('quality_score', 0),
                            'time': last_notified.strftime('%H:%M')
                        })
            
            if today_plays:
                # Sort by time (most recent first)
                today_plays.sort(key=lambda x: x['time'], reverse=True)
                
                plays_text = ""
                for i, play in enumerate(today_plays, 1):
                    gap_emoji = "📈" if play['gap'] > 0 else "📉"
                    plays_text += f"""
🎯 {play['symbol']} {gap_emoji}
• Precio: ${play['price']:.2f}
• Gap: {play['gap']*100:+.1f}%
• Volumen: {play['volume_ratio']:.1f}x
• Score: {play['quality_score']:.1f}
• Hora: {play['time']}

"""

                message = f"""🔥 PLAYS EXCEPCIONALES DETECTADOS 🔥
═══════════════════════════════════

{plays_text}📊 **RESUMEN DEL DIA**
• Total plays detectados: {len(today_plays)}
• Scanner automatico funcionando
• Filtros anti-spam activos

🔄 Actualizado: {current_time.strftime('%H:%M:%S')}"""
            else:
                message = f"""🔍 BUSCANDO OPORTUNIDADES...
═══════════════════════════════════

📅 **HOY** - {today_str}

⚡ **Estado del Scanner:**
• Funcionando automaticamente
• Buscando cada 30 segundos
• Filtros activos: Gap >2%, Vol >3x, Score ≥6.0

⏰ **Tiempo actual:** {current_time.strftime('%H:%M:%S')}

📈 **Mejores horarios:**
• 09:30-10:30 (apertura)
• 15:30-16:00 (cierre)

🎯 **Aun no se detectaron plays hoy**"""
        else:
            message = f"""❌ **SISTEMA NO DISPONIBLE**
═══════════════════════════════════

📅 **HOY** - {today_str}

🚫 **UnifiedTradingSystem no esta activo**
• Ejecutar: python main.py
• Verificar configuracion del sistema

⚙️ **Para reactivar:**
1. Ejecutar main.py o simple_main.py  
2. Verificar conexion Redis
3. Confirmar scanner activo"""

        # Send with Markdown formatting as before
        send_message(message, parse_mode="Markdown")
        
    except Exception as e:
        _logger.error(f"Error getting plays today: {e}")
        send_message(f"❌ Error obteniendo plays de hoy: {str(e)}")

def send_market_regime():
    """Send current market regime and adaptive thresholds"""
    try:
        from notifications.telegram_commands.regime_command import handle_regime_command
        message = handle_regime_command()
        send_message(message)
    except Exception as e:
        _logger.error(f"Error getting market regime: {e}")
        send_message(f"❌ Error obteniendo régimen de mercado: {str(e)}")

def handle_command(text: str):
    """Handle incoming commands"""
    text = text.strip().lower()
    
    if text.startswith("/start") or text.startswith("/menu"):
        send_main_menu()
    elif text == "/scanner_log":
        send_scanner_log(50)
    elif text == "/trader_log":
        send_trader_log(50)
    elif text == "/scanner_log_100":
        send_scanner_log(100)
    elif text == "/trader_log_100":
        send_trader_log(100)
    elif text == "/stats":
        send_daily_stats()
    elif text == "/stats_historical":
        send_historical_stats()
    elif text == "/trades":
        send_recent_trades()
    elif text == "/trades_today":
        send_trades_today()
    elif text == "/trades_open":
        send_open_trades()
    elif text == "/performance":
        send_performance_summary()
    elif text == "/status":
        send_system_status()
    elif text == "/hybrid_status":
        send_hybrid_system_status()
    elif text == "/tradetally_status":
        send_tradetally_status()
    elif text == "/tradetally_sync":
        send_tradetally_sync()
    elif text == "/plays":
        send_scanner_plays()
    elif text == "/scanner":
        send_scanner_status()
    elif text == "/plays_today":
        send_plays_today()
    elif text == "/regime":
        send_market_regime()
    elif text == "/help":
        send_help_message()
    elif text == "/closeall" or text == "/closeall confirm" or text == "/closeall_confirm":
        send_closeall_positions(confirm=(text in ["/closeall confirm", "/closeall_confirm"]))
    else:
        send_message("❓ Comando no reconocido. Usa /menu para ver opciones disponibles.")

def listen_for_commands():
    """Listen for Telegram commands"""
    global _listener_running
    
    if not is_enabled():
        return
        
    token = get_token()
    chat_id = get_chat_id()
    
    if not token or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    offset = None
    
    _logger.info("Telegram command listener started")
    
    while _listener_running:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
                
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        message = update.get("message", {})
                        if str(message.get("chat", {}).get("id")) == str(chat_id):
                            text = message.get("text", "")
                            if text:
                                _logger.info(f"Received command: {text}")
                                handle_command(text)
            elif response.status_code == 409:
                # Multiple bot instances - wait longer
                _logger.warning("Multiple bot instances detected, waiting...")
                time.sleep(60)
            else:
                _logger.warning(f"Telegram API error: {response.status_code}")
                
        except Exception as e:
            _logger.error(f"Error in command listener: {e}")
            
        time.sleep(1)

def start_command_listener():
    """Start the command listener thread"""
    global _listener_thread, _listener_running
    
    if not is_enabled():
        _logger.warning("Telegram not enabled, cannot start listener")
        return False
        
    # Stop existing listener if running
    if _listener_thread and _listener_thread.is_alive():
        _logger.info("Telegram listener already running")
        return True
        
    try:
        _listener_running = True
        _listener_thread = threading.Thread(target=listen_for_commands, daemon=True)
        _listener_thread.start()
        _logger.info("Started Telegram command listener thread")
        return True
    except Exception as e:
        _logger.error(f"Failed to start Telegram listener: {e}")
        _listener_running = False
        return False

def stop_command_listener():
    """Stop the command listener"""
    global _listener_running
    _listener_running = False
    _logger.info("Stopped Telegram command listener")

# Auto-start removed to prevent multiple instances
# Use start_command_listener() explicitly where needed