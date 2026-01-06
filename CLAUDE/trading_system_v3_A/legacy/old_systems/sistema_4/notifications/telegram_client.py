#!/usr/bin/env python3
"""
Telegram Client for Sistema_4 - Adapted from trading_system_v3
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

# Opportunity notification filtering to prevent spam
_last_notifications = {}  # symbol -> timestamp
_notification_cooldown = 300  # 5 minutes cooldown per symbol

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

        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        today_lines = [line.strip() for line in all_lines if line.startswith(today)]

        if not today_lines:
            send_message(f"ℹ️ No logs found for today ({today})")
            return

        if len(today_lines) > lines:
            today_lines = today_lines[-lines:]

        content = "\n".join(today_lines)
        header = f"🔍 Scanner logs ({today}) - Last {len(today_lines)} lines:"

        full_message = f"{header}\n{content}"
        if len(full_message) > 4000:
            send_message(full_message, use_html=False)
        else:
            import html
            escaped_content = html.escape(content)
            formatted_message = f"{header}\n<pre>{escaped_content}</pre>"
            send_message(formatted_message, use_html=True)

        _logger.info(f"Sent {len(today_lines)} log lines to Telegram")

    except Exception as e:
        _logger.error(f"Error sending scanner logs: {e}")
        send_message(f"❌ Error reading scanner logs: {str(e)}")

def send_main_menu():
    """Send main menu with available commands"""
    menu_msg = """🤖 **SISTEMA_4 CONTROL PANEL**
═══════════════════════════════

📊 **ESTADÍSTICAS**
• /stats - Estadísticas del sistema
• /performance - Resumen de rendimiento

📈 **TRADES & POSITIONS**
• /trades - Trades recientes
• /positions - Posiciones abiertas
• /opportunities - Oportunidades detectadas

🔍 **SCANNER & WORKERS**
• /scanner_status - Estado del scanner
• /workers_status - Estado de workers
• /execution_status - Estado del execution engine

📋 **LOGS**
• /scanner_log - Últimos 50 scanner logs
• /execution_log - Últimos 50 execution logs
• /system_log - Logs del sistema principal

🔧 **UTILIDADES**
• /status - Estado general del sistema
• /help - Ayuda detallada
• /menu - Mostrar este menú

═══════════════════════════════
🚀 **Sistema_4 Distributed Trading System**"""
    send_message(menu_msg, use_html=True)

def send_help_message():
    """Send help message"""
    help_msg = """🆘 **COMMAND HELP - SISTEMA_4**
═══════════════════════

**Sistema_4 Commands:**
• `/scanner_status` - Estado del scanner centralizado
• `/workers_status` - Estado de todos los workers
• `/execution_status` - Estado del execution engine
• `/opportunities` - Oportunidades detectadas por el scanner
• `/positions` - Posiciones abiertas (desde execution engine)
• `/stats` - Estadísticas del sistema distribuido
• `/performance` - Rendimiento general

**Logs:**
• `/scanner_log` - Scanner logs
• `/execution_log` - Execution engine logs
• `/system_log` - Sistema principal logs

**General:**
• `/status` - Estado general
• `/menu` - Main menu

**Tips:**
• Sistema_4 es distribuido: Scanner + Workers + Execution Engine
• Cada componente tiene logs separados
• Use /menu para opciones principales

═══════════════════════
💡 Use /menu for main options"""
    send_message(help_msg, use_html=True)

def send_system_status():
    """Send Sistema_4 system status"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check log files
        scanner_log = _PROJECT_ROOT / "logs" / "scanner.log"
        execution_log = _PROJECT_ROOT / "logs" / "execution_engine.log"
        main_log = _PROJECT_ROOT / "logs" / "sistema4_main.log"

        scanner_status = "✅ Active" if scanner_log.exists() else "❌ Not found"
        execution_status = "✅ Active" if execution_log.exists() else "❌ Not found"
        main_status = "✅ Active" if main_log.exists() else "❌ Not found"

        # Count today's log entries
        today = datetime.now().strftime("%Y-%m-%d")
        scanner_lines = 0
        execution_lines = 0
        main_lines = 0

        if scanner_log.exists():
            with open(scanner_log, 'r', encoding='utf-8', errors='ignore') as f:
                scanner_lines = len([line for line in f if line.startswith(today)])

        if execution_log.exists():
            with open(execution_log, 'r', encoding='utf-8', errors='ignore') as f:
                execution_lines = len([line for line in f if line.startswith(today)])

        if main_log.exists():
            with open(main_log, 'r', encoding='utf-8', errors='ignore') as f:
                main_lines = len([line for line in f if line.startswith(today)])

        status_msg = f"""📊 **SISTEMA_4 STATUS**
═══════════════════════

🕐 **Current Time:** {current_time}

🏗️ **Architecture Components:**
• Scanner: {scanner_status} ({scanner_lines:,} logs today)
• Execution Engine: {execution_status} ({execution_lines:,} logs today)
• Main Coordinator: {main_status} ({main_lines:,} logs today)

🔄 **Distributed System:**
• Workers: 4 specialized strategies
• Message Bus: Redis coordination
• Database: SQLite coordination

🤖 **Telegram:**
• Bot status: ✅ Active
• Commands: ✅ Working

═══════════════════════
🎯 Sistema_4 operational"""

        send_message(status_msg, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting system status: {e}")
        send_message("❌ Error getting system status")

def send_scanner_status():
    """Send scanner status specific to Sistema_4"""
    try:
        current_time = datetime.now()
        today_str = current_time.strftime('%Y-%m-%d')

        scanner_log_file = _PROJECT_ROOT / "logs" / "scanner.log"

        if not scanner_log_file.exists():
            send_message("❌ Scanner log file not found - Scanner may not be running")
            return

        with open(scanner_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        today_lines = [line.strip() for line in all_lines if line.startswith(today_str)]

        if not today_lines:
            send_message(f"📭 No scanner activity found for today ({today_str})")
            return

        recent_lines = today_lines[-10:] if len(today_lines) > 10 else today_lines
        last_line = today_lines[-1] if today_lines else ""

        last_activity_time = "Unknown"
        if last_line and len(last_line) > 19:
            last_activity_time = last_line[:19]

        # Count activities
        scan_cycles = len([line for line in today_lines if "Starting scan cycle" in line])
        opportunities = len([line for line in today_lines if "opportunities" in line.lower()])
        errors = len([line for line in today_lines if "ERROR" in line.upper()])

        # Determine status
        scanner_status = "🟢 Active"
        if "ERROR" in last_line.upper():
            scanner_status = "🔴 Error"
        elif "Waiting" in last_line:
            scanner_status = "🟡 Waiting"
        elif "No opportunities" in last_line:
            scanner_status = "🟠 Scanning"

        status_msg = f"""🔍 **SISTEMA_4 SCANNER STATUS**
═══════════════════════

📊 **Current Status:** {scanner_status}
⏰ **Last Activity:** {last_activity_time}

📈 **Today's Activity:**
• Scan Cycles: {scan_cycles}
• Opportunities Found: {opportunities}
• Errors: {errors}

🎯 **Architecture:**
• Lightweight scanner (no enhancement)
• Basic filtering only
• Workers handle detailed analysis

📋 **Recent Activity:**"""

        # Add recent significant lines
        for line in recent_lines[-3:]:
            if any(keyword in line for keyword in ["opportunities", "Starting", "ERROR", "complete"]):
                parts = line.split(" - ", 3)
                if len(parts) >= 4:
                    message = parts[3].replace("<", "").replace(">", "")
                    status_msg += f"\n• {message}"

        send_message(status_msg, use_html=False)

    except Exception as e:
        _logger.error(f"Error getting scanner status: {e}")
        send_message(f"❌ Error getting scanner status: {str(e)}")

def send_opportunities():
    """Send detected opportunities from scanner"""
    try:
        # Read recent scanner logs for opportunities
        scanner_log_file = _PROJECT_ROOT / "logs" / "scanner.log"

        if not scanner_log_file.exists():
            send_message("❌ Scanner log not found")
            return

        today = datetime.now().strftime("%Y-%m-%d")

        with open(scanner_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Find opportunity lines from today
        opportunities = []
        for line in lines:
            if line.startswith(today) and any(word in line.lower() for word in ["opportunities", "found", "detected"]):
                if "symbol" in line.lower() or any(symbol in line for symbol in ["BULL_FLAG", "GAP_GO", "DAILY_PLAYS", "MACDV"]):
                    opportunities.append(line.strip())

        if not opportunities:
            send_message("ℹ️ No opportunities detected today yet")
            return

        # Format recent opportunities
        recent_opportunities = opportunities[-5:] if len(opportunities) > 5 else opportunities

        opps_text = ""
        for opp in recent_opportunities:
            # Extract time and message
            time_part = opp[:19] if len(opp) > 19 else opp[:10]
            message_part = opp[19:] if len(opp) > 19 else ""
            opps_text += f"• {time_part[-8:]}: {message_part}\n"

        message = f"""🎯 **OPPORTUNITIES DETECTED**
═══════════════════════

📊 **Today:** {len(opportunities)} total opportunities
🕐 **Recent Activity:**

{opps_text}
🔄 **Scanner running automatically**
📨 **Workers notified via Redis**

Use /scanner_status for detailed scanner info"""

        send_message(message, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting opportunities: {e}")
        send_message(f"❌ Error getting opportunities: {str(e)}")

def send_workers_status():
    """Send workers status"""
    try:
        # Check worker log files (if they exist)
        workers = ["gap_go", "daily_plays", "macdv", "bull_flag"]
        worker_status = {}

        for worker in workers:
            log_file = _PROJECT_ROOT / "logs" / f"{worker}_worker.log"
            if log_file.exists():
                worker_status[worker] = "✅ Active"
            else:
                worker_status[worker] = "❌ No logs"

        status_msg = f"""👥 **SISTEMA_4 WORKERS STATUS**
═══════════════════════

🔧 **Specialized Workers:**
• GAP_GO Worker: {worker_status['gap_go']}
• Daily Plays Worker: {worker_status['daily_plays']}
• MACDV Worker: {worker_status['macdv']}
• Bull Flag Worker: {worker_status['bull_flag']}

🎯 **Architecture:**
• Each worker handles specific strategies
• Enhancement service for detailed analysis
• Redis coordination with scanner
• Independent IBKR connections

📊 **System:** Distributed processing
🔄 **Status:** {len([s for s in worker_status.values() if "Active" in s])}/4 workers active

Use individual worker logs for detailed status"""

        send_message(status_msg, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting workers status: {e}")
        send_message("❌ Error getting workers status")

def send_execution_status():
    """Send execution engine status"""
    try:
        execution_log = _PROJECT_ROOT / "logs" / "execution_engine.log"

        if not execution_log.exists():
            send_message("❌ Execution engine log not found")
            return

        today = datetime.now().strftime("%Y-%m-%d")

        with open(execution_log, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        today_lines = [line for line in lines if line.startswith(today)]

        # Count activities
        trade_requests = len([line for line in today_lines if "trade request" in line.lower()])
        executions = len([line for line in today_lines if "executed" in line.lower() or "filled" in line.lower()])
        rejections = len([line for line in today_lines if "rejected" in line.lower()])

        # Get last activity
        last_activity = "Unknown"
        if today_lines:
            last_line = today_lines[-1]
            if len(last_line) > 19:
                last_activity = last_line[:19]

        status_msg = f"""⚙️ **EXECUTION ENGINE STATUS**
═══════════════════════

📊 **Today's Activity:**
• Trade Requests: {trade_requests}
• Executions: {executions}
• Rejections: {rejections}

⏰ **Last Activity:** {last_activity}

🎯 **Centralized Execution:**
• All trades validated and executed centrally
• Risk management integration
• IBKR adapter with bracket orders
• Redis communication with workers

🔧 **Features:**
• Order timeout protection
• Concurrent order limits
• Position tracking
• Trade responses to workers

Status: {'🟢 Active' if today_lines else '🟡 Idle'}"""

        send_message(status_msg, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting execution status: {e}")
        send_message("❌ Error getting execution status")

def send_positions():
    """Send current positions from execution engine"""
    try:
        # Try to read positions from database
        from shared.database import Sistema4Database

        db = Sistema4Database()
        positions = db.get_active_positions()

        if not positions:
            send_message("ℹ️ No active positions currently")
            return

        positions_text = ""
        total_value = 0

        for i, pos in enumerate(positions, 1):
            symbol = pos.get('symbol', 'Unknown')
            side = pos.get('side', 'Unknown')
            quantity = pos.get('quantity', 0)
            entry_price = pos.get('entry_price', 0.0)
            owner = pos.get('owner', 'Unknown')

            value = quantity * entry_price
            total_value += value

            side_emoji = "🟢" if side == "BUY" else "🔴"

            positions_text += f"""
{i}. {side_emoji} **{symbol}** - {side}
   📊 Quantity: {quantity:,}
   💰 Entry: ${entry_price:.2f}
   📈 Value: ${value:,.2f}
   👤 Owner: {owner}
"""

        message = f"""🔄 **ACTIVE POSITIONS**
═══════════════════════

📊 **Summary:**
• Total Positions: {len(positions)}
• Total Value: ${total_value:,.2f}

📈 **Position Details:**
{positions_text}
═══════════════════════
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        send_message(message, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting positions: {e}")
        send_message(f"❌ Error getting positions: {str(e)}")

def send_stats():
    """Send Sistema_4 statistics"""
    try:
        current_time = datetime.now()
        today_str = current_time.strftime('%Y-%m-%d')

        # Get stats from various logs
        scanner_log = _PROJECT_ROOT / "logs" / "scanner.log"
        execution_log = _PROJECT_ROOT / "logs" / "execution_engine.log"

        scanner_activities = 0
        execution_activities = 0
        opportunities = 0

        if scanner_log.exists():
            with open(scanner_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            today_lines = [line for line in lines if line.startswith(today_str)]
            scanner_activities = len(today_lines)
            opportunities = len([line for line in today_lines if "opportunities" in line.lower()])

        if execution_log.exists():
            with open(execution_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            today_lines = [line for line in lines if line.startswith(today_str)]
            execution_activities = len(today_lines)

        # Get positions count
        positions_count = 0
        try:
            from shared.database import Sistema4Database
            db = Sistema4Database()
            positions = db.get_active_positions()
            positions_count = len(positions)
        except:
            pass

        stats_msg = f"""📊 **SISTEMA_4 STATISTICS** - {today_str}
═══════════════════════════════

🏗️ **Distributed Architecture:**
• Scanner activities: {scanner_activities:,}
• Execution activities: {execution_activities:,}
• Opportunities detected: {opportunities:,}
• Active positions: {positions_count}

🔧 **System Components:**
• 1 Scanner (lightweight)
• 4 Workers (specialized)
• 1 Execution Engine (centralized)
• Redis coordination
• SQLite database

📈 **Performance:**
• Enhancement: On-demand only
• Rate limiting: Distributed
• Scalability: Linear with workers

⏰ **Last update:** {current_time.strftime('%H:%M:%S')}
═══════════════════════════════
📅 Sistema_4 operational"""

        send_message(stats_msg, use_html=True)

    except Exception as e:
        _logger.error(f"Error getting stats: {e}")
        send_message("❌ Error getting statistics")

def handle_command(text: str):
    """Handle incoming commands for Sistema_4"""
    text = text.strip().lower()

    if text.startswith("/start") or text.startswith("/menu"):
        send_main_menu()
    elif text == "/scanner_log":
        send_scanner_log(50)
    elif text == "/scanner_status":
        send_scanner_status()
    elif text == "/workers_status":
        send_workers_status()
    elif text == "/execution_status":
        send_execution_status()
    elif text == "/opportunities":
        send_opportunities()
    elif text == "/positions":
        send_positions()
    elif text == "/stats":
        send_stats()
    elif text == "/status":
        send_system_status()
    elif text == "/help":
        send_help_message()
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

    _logger.info("Telegram command listener started for Sistema_4")

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
                                _logger.info(f"Received Sistema_4 command: {text}")
                                handle_command(text)
            elif response.status_code == 409:
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

    if _listener_thread and _listener_thread.is_alive():
        _logger.info("Telegram listener already running")
        return True

    try:
        _listener_running = True
        _listener_thread = threading.Thread(target=listen_for_commands, daemon=True)
        _listener_thread.start()
        _logger.info("Started Sistema_4 Telegram command listener thread")
        return True
    except Exception as e:
        _logger.error(f"Failed to start Telegram listener: {e}")
        _listener_running = False
        return False

def stop_command_listener():
    """Stop the command listener"""
    global _listener_running
    _listener_running = False
    _logger.info("Stopped Sistema_4 Telegram command listener")

# Notification functions for Sistema_4 events

def notify_trade_executed(symbol: str, action: str, quantity: int, price: float, worker_id: str):
    """Notify when a trade is executed"""
    if not is_enabled():
        return

    action_emoji = "🟢" if action == "BUY" else "🔴"
    message = f"""🚀 **TRADE EXECUTED**

{action_emoji} **{symbol}** - {action}
💰 Price: ${price:.2f}
📊 Quantity: {quantity:,} shares
🎯 Value: ${price * quantity:,.2f}

👤 Worker: {worker_id}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

📈 Sistema_4 Distributed Trading"""

    send_message(message, use_html=True)

def notify_opportunity_detected(symbol: str, opportunity_type: str, details: dict):
    """Notify when an opportunity is detected (with anti-spam filtering)"""
    if not is_enabled():
        return

    # Anti-spam filtering: Check if we've recently notified about this symbol
    current_time = time.time()
    last_notification_time = _last_notifications.get(symbol, 0)

    if current_time - last_notification_time < _notification_cooldown:
        _logger.debug(f"Skipping notification for {symbol} - cooldown active ({current_time - last_notification_time:.0f}s ago)")
        return

    # Debug: Log the actual data structure we received
    _logger.debug(f"Opportunity data for {symbol}: {details}")

    strategy_emoji = {
        "GAP_GO": "🚀",
        "DAILY_PLAYS": "📈",
        "INTRADAY_MOMENTUM": "⚡",
        "RED_TO_GREEN": "🔴➡️🟢",
        "MACDV": "📊",
        "BULL_FLAG": "🏁"
    }.get(opportunity_type, "🎯")

    # Handle different opportunity structures
    price = details.get('current_price', 0.0)
    gap = details.get('gap_percentage', 0.0)

    # Volume handling - could be 'volume' or 'volume_ratio'
    volume = details.get('volume', 0)
    if volume == 0:
        volume_ratio = details.get('volume_ratio', 0.0)
        volume_text = f"Ratio: {volume_ratio:.1f}x" if volume_ratio > 0 else "N/A"
    else:
        volume_text = f"{volume:,}"

    # Quality score
    quality_score = details.get('quality_score', 0.0)

    # Filter out opportunities with invalid data (all zeros)
    if price == 0.0 and gap == 0.0 and volume == 0 and details.get('volume_ratio', 0.0) == 0.0:
        _logger.warning(f"Skipping opportunity {symbol} - all values are zero")
        _logger.debug(f"Available fields in details: {list(details.keys())}")
        return

    # Only send notification for quality opportunities with valid data
    if quality_score < 6.0:
        _logger.debug(f"Skipping low quality opportunity {symbol} (score: {quality_score})")
        return

    # Format gap percentage (handle both decimal and percentage formats)
    if gap != 0:
        if abs(gap) < 1:  # If it's already a decimal (0.05 for 5%)
            gap_text = f"{gap*100:+.1f}%"
        else:  # If it's already a percentage (5.0 for 5%)
            gap_text = f"{gap:+.1f}%"
    else:
        gap_text = "0.0%"

    message = f"""🎯 **OPPORTUNITY DETECTED**

{strategy_emoji} **{symbol}** - {opportunity_type}
💰 Price: ${price:.2f}
📊 Gap: {gap_text}
📈 Volume: {volume_text}
⭐ Quality: {quality_score:.1f}/10

🔄 Sent to specialized worker
⏰ {datetime.now().strftime('%H:%M:%S')}"""

    # Update last notification time
    _last_notifications[symbol] = current_time

    send_message(message, use_html=True)
    _logger.info(f"Sent Telegram notification for {symbol} ({opportunity_type}, Q:{quality_score:.1f})")

def notify_system_error(component: str, error: str):
    """Notify system errors"""
    if not is_enabled():
        return

    message = f"""❌ **SISTEMA_4 ERROR**

🔧 Component: {component}
🚨 Error: {error}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

🔍 Check logs for details"""

    send_message(message, use_html=True)

def notify_system_startup():
    """Notify when Sistema_4 starts"""
    if not is_enabled():
        return

    message = f"""🚀 **SISTEMA_4 STARTED**

🏗️ **Distributed Trading System Active**
• Scanner: Detecting opportunities
• Workers: 4 specialized strategies
• Execution: Centralized validation
• Database: SQLite coordination
• Message Bus: Redis communication

⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📱 Use /menu for commands"""

    send_message(message, use_html=True)