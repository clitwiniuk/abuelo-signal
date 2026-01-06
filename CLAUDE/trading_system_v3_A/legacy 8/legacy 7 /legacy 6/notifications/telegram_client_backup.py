"""Telegram notification client.
Sends messages to a Telegram chat using the Bot API.
Reads credentials from `config.ini` under the [NOTIFICATIONS] section or from
environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as fallback.
"""

from __future__ import annotations

# Core Python imports
import configparser
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Third-party imports
import pandas as pd
import requests
import urllib3

# Suppress SSL warnings when using verify=False fallback
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize logger after all imports
_logger = logging.getLogger("TelegramClient")

# Locate the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_FILE = _PROJECT_ROOT / "config.ini"

# Load configuration file if present
_config = configparser.ConfigParser()
if _CONFIG_FILE.exists():
    _config.read(_CONFIG_FILE)
else:
    _logger.warning("config.ini not found – falling back to env vars for Telegram credentials")

# Helper to read boolean safely from config

def _get_bool(section: str, key: str, default: bool = False) -> bool:
    try:
        return _config.getboolean(section, key)
    except Exception:
        return default


# === Public helpers ==========================================================

def is_enabled() -> bool:
    """Return True if Telegram notifications are enabled in config.ini"""
    return _get_bool("NOTIFICATIONS", "telegram_enabled", False)


def _get_token() -> Optional[str]:
    if _config.has_option("NOTIFICATIONS", "telegram_bot_token"):
        return _config.get("NOTIFICATIONS", "telegram_bot_token")
    return os.getenv("TELEGRAM_BOT_TOKEN")


def _get_chat_id() -> Optional[str]:
    if _config.has_option("NOTIFICATIONS", "telegram_chat_id"):
        return _config.get("NOTIFICATIONS", "telegram_chat_id")
    return os.getenv("TELEGRAM_CHAT_ID")


def _chunk_message(text: str, max_len: int = 4000):
    """Yield chunks under Telegram size limit"""
    for i in range(0, len(text), max_len):
        yield text[i : i + max_len]


def send_message(text: str, parse_mode: str | None = None, disable_web_page_preview: bool = True) -> None:
    """Send a text message to the configured Telegram chat.

    If notifications are disabled or credentials are missing, the call is a no-op.
    """
    if not is_enabled():
        # Silently ignore if disabled – avoids cluttering logs
        return

    token = _get_token()
    chat_id = _get_chat_id()

    if not token or not chat_id:
        _logger.warning("Telegram credentials missing – message not sent")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        data["parse_mode"] = parse_mode

    # Retry mechanism with exponential backoff for SSL errors
    max_retries = 3
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Use shorter timeout and disable SSL verification as fallback
            resp = requests.post(url, data=data, timeout=5)
            if resp.status_code != 200 or not resp.json().get("ok", False):
                _logger.error("Telegram API error (%s): %s", resp.status_code, resp.text[:200])
            else:
                # Success
                if attempt > 0:
                    _logger.info(f"Telegram message sent successfully on attempt {attempt + 1}")
                return
                
        except requests.exceptions.SSLError as ssl_exc:
            _logger.warning(f"SSL error on attempt {attempt + 1}: {ssl_exc}")
            if attempt == max_retries - 1:
                # Last attempt: try without SSL verification
                try:
                    resp = requests.post(url, data=data, timeout=5, verify=False)
                    if resp.status_code == 200 and resp.json().get("ok", False):
                        _logger.info("Telegram message sent without SSL verification")
                        return
                except Exception as fallback_exc:
                    _logger.error(f"Failed even without SSL verification: {fallback_exc}")
            else:
                # Wait with exponential backoff
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                
        except requests.exceptions.Timeout as timeout_exc:
            _logger.warning(f"Timeout on attempt {attempt + 1}: {timeout_exc}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            
        except Exception as exc:
            _logger.error(f"Failed to send Telegram message on attempt {attempt + 1}: {exc}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            
    _logger.error(f"Failed to send Telegram message after {max_retries} attempts")


# ----------------------------------------------------------------------------
#  COMMAND LISTENER (optional)
# ----------------------------------------------------------------------------

_listener_thread: threading.Thread | None = None
_listener_running = False


def _handle_command(text: str):
    """Handle incoming Telegram commands with enhanced menu system"""
    text = text.strip()
    
    if text.startswith("/start") or text.startswith("/menu"):
        send_main_menu()
    elif text.startswith("/log"):
        # Enhanced log commands
        try:
            parts = text.split()
            if len(parts) > 1 and parts[1] == "old":
                lines = int(parts[2]) if len(parts) > 2 else 200
                send_log_tail(lines)
            else:
                lines = int(parts[1]) if len(parts) > 1 else 200
                send_log_today(lines)
        except (IndexError, ValueError):
            send_log_today(200)
    elif text.startswith("/stats"):
        # Trading statistics commands
        parts = text.split()
        if len(parts) > 1 and parts[1] == "historical":
            send_historical_stats()
        else:
            send_daily_stats()
    elif text.startswith("/trades"):
        # Trade summary commands
        parts = text.split()
        if len(parts) > 1 and parts[1] == "today":
            send_trades_today()
        elif len(parts) > 1 and parts[1] == "open":
            send_open_trades()
        else:
            send_recent_trades()
    elif text.startswith("/performance"):
        send_performance_summary()
    elif text.startswith("/clear_cache"):
        clear_mayordomo_cache()
    elif text.startswith("/help"):
        send_help_menu()
    else:
        send_message("❓ Comando no reconocido. Usa /menu para ver opciones disponibles.")


def _listen_loop(poll_interval: int = 5):
    global _listener_running
    token = _get_token()
    chat_id = _get_chat_id()
    if not token or not chat_id:
        return
    offset = None
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while _listener_running:
        try:
            params = {"timeout": 30}  # Increased timeout for better stability
            if offset:
                params["offset"] = offset
                
            # Try with SSL first, then without if it fails
            resp = None
            try:
                resp = requests.get(url, params=params, timeout=35)  # Increased timeout
            except requests.exceptions.SSLError:
                _logger.warning("SSL error in listener, trying without verification")
                resp = requests.get(url, params=params, timeout=35, verify=False)
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
                _logger.warning(f"Connection/timeout error: {e}")
                consecutive_errors += 1
                continue
            
            if resp.status_code == 200 and resp.json().get("ok", False):
                consecutive_errors = 0  # Reset error counter on success
                for update in resp.json()["result"]:
                    offset = update["update_id"] + 1
                    msg = update.get("message")
                    if not msg or str(msg.get("chat", {}).get("id")) != str(chat_id):
                        continue  # Ignore other chats
                    text = msg.get("text", "")
                    _handle_command(text)
            elif resp.status_code == 409:  # Conflict - multiple instances
                _logger.error("Error 409: Multiple bot instances detected. Waiting longer...")
                time.sleep(60)  # Wait longer for other instance to stop
                consecutive_errors += 1
            else:
                _logger.warning(f"HTTP {resp.status_code}: {resp.text}")
                consecutive_errors += 1
                
        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            _logger.error(f"Network error in listener: {e}")
        except Exception as exc:
            consecutive_errors += 1
            _logger.error(f"Unexpected listener error: {exc}")
            
        # Enhanced error handling with exponential backoff
        if consecutive_errors >= max_consecutive_errors:
            backoff_time = min(poll_interval * (2 ** min(consecutive_errors - max_consecutive_errors, 4)), 300)  # Max 5 minutes
            _logger.warning(f"Too many consecutive errors ({consecutive_errors}), backing off for {backoff_time}s")
            time.sleep(backoff_time)
            consecutive_errors = max_consecutive_errors - 1  # Keep near threshold
        else:
            time.sleep(poll_interval)


def start_command_listener():
    """Start background thread to listen for Telegram commands (/log)."""
    global _listener_thread, _listener_running
    if not is_enabled() or _listener_thread and _listener_thread.is_alive():
        return
    _listener_running = True
    _listener_thread = threading.Thread(target=_listen_loop, daemon=True)
    _listener_thread.start()


def stop_command_listener():
    global _listener_running
    _listener_running = False

# ----------------------------------------------------------------------------


def send_log_tail(lines: int = 200, log_path: str | Path = None) -> None:
    """Read last *lines* from log file and send to Telegram as <pre> block(s)."""
    if not is_enabled():
        return

    # Use unified trading system log
    if log_path is None:
        possible_paths = [
            _PROJECT_ROOT / "logs" / "trading_system.log"
        ]
        path = None
        for p in possible_paths:
            if p.exists():
                path = p
                break
    else:
        path = Path(log_path)
    
    if path is None or not path.exists():
        send_message("❌ Log file no encontrado en las ubicaciones esperadas")
        return

    try:
        # Read and split lines
        tail_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
        
        if not tail_lines:
            send_message(f"⚠️ El archivo {path.name} está vacío")
            return
            
        content = "\n".join(tail_lines)
        total_lines_in_file = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        header = f"📄 Últimas {len(tail_lines)} líneas de {total_lines_in_file} ({path.name}):"
        
        # Split into chunks for Telegram's message limit
        chunks = list(_chunk_message(content))
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                prefix = header
            else:
                prefix = f"(cont. {i+1}/{len(chunks)})"
            # Escape HTML characters to prevent parsing errors
            import html
            escaped_chunk = html.escape(chunk)
            send_message(f"{prefix}\n<pre>{escaped_chunk}</pre>", parse_mode="HTML", disable_web_page_preview=True)
            
        _logger.info(f"Sent {len(chunks)} log chunks via Telegram ({len(tail_lines)} lines from {path})")
        
    except Exception as exc:
        _logger.error("Failed to send log tail: %s", exc)
        send_message(f"❌ Error enviando log: {exc}")


def send_log_today(lines: int = 200, log_path: str | Path = None) -> None:
    """Send only today's log entries via Telegram."""
    if not is_enabled():
        return

    # Use unified trading system log
    if log_path is None:
        possible_paths = [
            _PROJECT_ROOT / "logs" / "trading_system.log"
        ]
        path = None
        for p in possible_paths:
            if p.exists():
                path = p
                break
    else:
        path = Path(log_path)
    
    if path is None or not path.exists():
        send_message("❌ Log file no encontrado en las ubicaciones esperadas")
        return

    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Read all lines and filter by today's date
        all_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        today_lines = [line for line in all_lines if line.startswith(today)]
        
        if not today_lines:
            send_message(f"ℹ️ No hay logs de hoy ({today}) en {path.name}")
            return
        
        # Limit to requested number of lines (most recent)
        if len(today_lines) > lines:
            today_lines = today_lines[-lines:]  # Get last N lines
            
        content = "\n".join(today_lines)
        header = f"📅 Logs de HOY ({today}) - últimas {len(today_lines)} líneas ({path.name}):"
        
        # Split into chunks for Telegram's message limit
        chunks = list(_chunk_message(content))
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                prefix = header
            else:
                prefix = f"(cont. {i+1}/{len(chunks)})"
            # Escape HTML characters to prevent parsing errors
            import html
            escaped_chunk = html.escape(chunk)
            send_message(f"{prefix}\n<pre>{escaped_chunk}</pre>", parse_mode="HTML", disable_web_page_preview=True)
            
        _logger.info(f"Sent {len(chunks)} TODAY log chunks via Telegram ({len(today_lines)} lines from {path})")
        
    except Exception as exc:
        _logger.error("Failed to send today's log: %s", exc)
        send_message(f"❌ Error enviando logs de hoy: {exc}")


# ----------------------------------------------------------------------------
#  TELEGRAM MENU AND TRADING STATISTICS
# ----------------------------------------------------------------------------

def send_main_menu():
    """Send interactive main menu with buttons"""
    menu_text = """
🤖 **TRADING BOT CONTROL PANEL**
═══════════════════════════════

📊 **ESTADÍSTICAS**
/stats - Estadísticas del día
/stats historical - Estadísticas históricas
/performance - Resumen de rendimiento

📈 **TRADES**
/trades - Trades recientes (últimos 10)
/trades today - Trades de hoy
/trades open - Posiciones abiertas

📋 **LOGS**
/log 50 - Últimos 50 logs de hoy
/log 100 - Últimos 100 logs de hoy
/log old 200 - Últimos 200 logs históricos

🔧 **UTILIDADES**
/help - Ayuda detallada
/menu - Mostrar este menú

═══════════════════════════════
💡 Tip: Usa los comandos directamente o escribe /help para más detalles
"""
    send_message(menu_text, parse_mode="Markdown")

def send_help_menu():
    """Send detailed help information"""
    help_text = """
🆘 **AYUDA - COMANDOS DISPONIBLES**
═══════════════════════════════

**📊 ESTADÍSTICAS DE TRADING:**
• `/stats` - Estadísticas del día actual
• `/stats historical` - Estadísticas de todos los tiempos
• `/performance` - Resumen completo de rendimiento

**📈 INFORMACIÓN DE TRADES:**
• `/trades` - Últimos 10 trades ejecutados
• `/trades today` - Todos los trades de hoy
• `/trades open` - Posiciones actualmente abiertas

**📋 LOGS DEL SISTEMA:**
• `/log 50` - Últimos 50 logs de hoy
• `/log 100` - Últimos 100 logs de hoy  
• `/log 200` - Últimos 200 logs de hoy
• `/log old 100` - Últimos 100 logs históricos

**🔧 COMANDOS DE CONTROL:**
• `/menu` o `/start` - Mostrar menú principal
• `/help` - Mostrar esta ayuda
• `/clear_cache` - Limpiar cache del Mayordomo (fix ANTI-MARTINGALA)

═══════════════════════════════
🚀 El bot responde automáticamente a todos los comandos
"""
    send_message(help_text, parse_mode="Markdown")

def _get_database_connection():
    """Get database connection with fallback paths"""
    db_paths = [
        "trading_data.db",
        "data/trading_data.db",
        "logs/trading_data.db"
    ]
    
    for db_path in db_paths:
        try:
            if Path(db_path).exists():
                return sqlite3.connect(db_path)
        except Exception:
            continue
    
    raise Exception("No se pudo conectar a ninguna base de datos")

def send_daily_stats():
    """Send today's trading statistics"""
    try:
        with _get_database_connection() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Trades de hoy
            today_trades = pd.read_sql_query("""
                SELECT COUNT(*) as total_trades,
                       COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                       COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades,
                       COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as total_pnl,
                       COALESCE(AVG(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as avg_pnl,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl > 0 THEN 1 END) as winning_trades,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl < 0 THEN 1 END) as losing_trades
                FROM trades 
                WHERE DATE(entry_time) = ?
            """, conn, params=[today])
            
            # Estadísticas por estrategia hoy
            strategy_stats = pd.read_sql_query("""
                SELECT strategy,
                       COUNT(*) as trades,
                       COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed,
                       COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as pnl,
                       COALESCE(AVG(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as avg_pnl
                FROM trades 
                WHERE DATE(entry_time) = ?
                GROUP BY strategy
                ORDER BY pnl DESC
            """, conn, params=[today])
            
            stats = today_trades.iloc[0]
            
            # Calcular win rate
            total_closed = stats['closed_trades']
            win_rate = (stats['winning_trades'] / total_closed * 100) if total_closed > 0 else 0
            
            # Formatear mensaje
            pnl_emoji = "🟢" if stats['total_pnl'] > 0 else "🔴" if stats['total_pnl'] < 0 else "⚪"
            
            message = f"""
📊 **ESTADÍSTICAS DEL DÍA** - {today}
═══════════════════════════════

**📈 RESUMEN GENERAL:**
• Total Trades: **{stats['total_trades']}**
• Trades Cerrados: **{stats['closed_trades']}**
• Posiciones Abiertas: **{stats['open_trades']}**

**💰 RENDIMIENTO:**
{pnl_emoji} PnL Total: **${stats['total_pnl']:.2f}**
📊 PnL Promedio: **${stats['avg_pnl']:.2f}**
🎯 Win Rate: **{win_rate:.1f}%** ({stats['winning_trades']}/{total_closed})

**📋 TRADES POR RESULTADO:**
🟢 Ganadores: **{stats['winning_trades']}**
🔴 Perdedores: **{stats['losing_trades']}**
"""
            
            if not strategy_stats.empty:
                message += "\n**🎯 RENDIMIENTO POR ESTRATEGIA:**\n"
                for _, row in strategy_stats.iterrows():
                    pnl_emoji = "🟢" if row['pnl'] > 0 else "🔴" if row['pnl'] < 0 else "⚪"
                    message += f"• {row['strategy']}: {pnl_emoji} ${row['pnl']:.2f} ({row['closed']} trades)\n"
            
            message += "\n═══════════════════════════════"
            
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo estadísticas del día: {str(e)}")

def send_historical_stats():
    """Send historical trading statistics"""
    try:
        with _get_database_connection() as conn:
            # Estadísticas generales
            general_stats = pd.read_sql_query("""
                SELECT COUNT(*) as total_trades,
                       COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                       COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades,
                       COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as total_pnl,
                       COALESCE(AVG(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as avg_pnl,
                       COALESCE(MAX(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as best_trade,
                       COALESCE(MIN(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as worst_trade,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl > 0 THEN 1 END) as winning_trades,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl < 0 THEN 1 END) as losing_trades
                FROM trades
            """, conn)
            
            # Top estrategias
            top_strategies = pd.read_sql_query("""
                SELECT strategy,
                       COUNT(*) as total_trades,
                       COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                       COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as total_pnl,
                       COALESCE(AVG(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as avg_pnl,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl > 0 THEN 1 END) as wins,
                       COUNT(CASE WHEN status = 'CLOSED' AND pnl < 0 THEN 1 END) as losses
                FROM trades
                GROUP BY strategy
                ORDER BY total_pnl DESC
                LIMIT 5
            """, conn)
            
            stats = general_stats.iloc[0]
            
            # Calcular métricas
            total_closed = stats['closed_trades']
            win_rate = (stats['winning_trades'] / total_closed * 100) if total_closed > 0 else 0
            
            pnl_emoji = "🟢" if stats['total_pnl'] > 0 else "🔴" if stats['total_pnl'] < 0 else "⚪"
            
            message = f"""
📈 **ESTADÍSTICAS HISTÓRICAS**
═══════════════════════════════

**📊 RESUMEN TOTAL:**
• Total Trades: **{stats['total_trades']}**
• Trades Cerrados: **{stats['closed_trades']}**
• Posiciones Abiertas: **{stats['open_trades']}**

**💰 RENDIMIENTO TOTAL:**
{pnl_emoji} PnL Total: **${stats['total_pnl']:.2f}**
📊 PnL Promedio: **${stats['avg_pnl']:.2f}**
🎯 Win Rate: **{win_rate:.1f}%**

**🏆 MEJORES/PEORES TRADES:**
🟢 Mejor Trade: **${stats['best_trade']:.2f}**
🔴 Peor Trade: **${stats['worst_trade']:.2f}**

**📋 DISTRIBUCIÓN:**
🟢 Trades Ganadores: **{stats['winning_trades']}**
🔴 Trades Perdedores: **{stats['losing_trades']}**
"""
            
            if not top_strategies.empty:
                message += "\n**🏆 TOP 5 ESTRATEGIAS:**\n"
                for i, row in top_strategies.iterrows():
                    pnl_emoji = "🟢" if row['total_pnl'] > 0 else "🔴" if row['total_pnl'] < 0 else "⚪"
                    wr = (row['wins'] / row['closed_trades'] * 100) if row['closed_trades'] > 0 else 0
                    message += f"{i+1}. **{row['strategy']}**: {pnl_emoji} ${row['total_pnl']:.2f} (WR: {wr:.1f}%)\n"
            
            message += "\n═══════════════════════════════"
            
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo estadísticas históricas: {str(e)}")

def send_recent_trades():
    """Send recent trades summary"""
    try:
        with _get_database_connection() as conn:
            recent_trades = pd.read_sql_query("""
                SELECT symbol, strategy, side, quantity, entry_price, exit_price, 
                       pnl, status, entry_time, exit_time
                FROM trades
                ORDER BY entry_time DESC
                LIMIT 10
            """, conn)
            
            if recent_trades.empty:
                send_message("📭 No hay trades recientes para mostrar")
                return
            
            message = """
📈 **ÚLTIMOS 10 TRADES**
═══════════════════════════════

"""
            
            for _, trade in recent_trades.iterrows():
                # Formatear datos
                pnl_emoji = "🟢" if trade['pnl'] and trade['pnl'] > 0 else "🔴" if trade['pnl'] and trade['pnl'] < 0 else "⚪"
                status_emoji = "🔓" if trade['status'] == 'OPEN' else "🔒"
                
                entry_time = pd.to_datetime(trade['entry_time']).strftime('%m-%d %H:%M')
                
                pnl_text = f"${trade['pnl']:.2f}" if trade['pnl'] else "N/A"
                exit_price_text = f"${trade['exit_price']:.2f}" if trade['exit_price'] else "N/A"
                
                message += f"""
{status_emoji} **{trade['symbol']}** ({trade['strategy']})
   {trade['side']} {trade['quantity']} @ ${trade['entry_price']:.2f}
   Exit: {exit_price_text} | PnL: {pnl_emoji} {pnl_text}
   📅 {entry_time}
"""
            
            message += "\n═══════════════════════════════"
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo trades recientes: {str(e)}")

def send_trades_today():
    """Send today's trades"""
    try:
        with _get_database_connection() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            
            today_trades = pd.read_sql_query("""
                SELECT symbol, strategy, side, quantity, entry_price, exit_price, 
                       pnl, status, entry_time, exit_time
                FROM trades
                WHERE DATE(entry_time) = ?
                ORDER BY entry_time DESC
            """, conn, params=[today])
            
            if today_trades.empty:
                send_message(f"📭 No hay trades para hoy ({today})")
                return
            
            message = f"""
📅 **TRADES DE HOY** - {today}
═══════════════════════════════

"""
            
            for _, trade in today_trades.iterrows():
                pnl_emoji = "🟢" if trade['pnl'] and trade['pnl'] > 0 else "🔴" if trade['pnl'] and trade['pnl'] < 0 else "⚪"
                status_emoji = "🔓" if trade['status'] == 'OPEN' else "🔒"
                
                entry_time = pd.to_datetime(trade['entry_time']).strftime('%H:%M')
                pnl_text = f"${trade['pnl']:.2f}" if trade['pnl'] else "N/A"
                exit_price_text = f"${trade['exit_price']:.2f}" if trade['exit_price'] else "N/A"
                
                message += f"""
{status_emoji} **{trade['symbol']}** ({trade['strategy']})
   {trade['side']} {trade['quantity']} @ ${trade['entry_price']:.2f}
   Exit: {exit_price_text} | PnL: {pnl_emoji} {pnl_text}
   ⏰ {entry_time}
"""
            
            message += f"\n📊 Total: {len(today_trades)} trades hoy"
            message += "\n═══════════════════════════════"
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo trades de hoy: {str(e)}")

def send_open_trades():
    """Send currently open positions"""
    try:
        with _get_database_connection() as conn:
            open_trades = pd.read_sql_query("""
                SELECT symbol, strategy, side, quantity, entry_price, entry_time
                FROM trades
                WHERE status = 'OPEN'
                ORDER BY entry_time DESC
            """, conn)
            
            if open_trades.empty:
                send_message("📭 No hay posiciones abiertas actualmente")
                return
            
            message = """
🔓 **POSICIONES ABIERTAS**
═══════════════════════════════

"""
            
            for _, trade in open_trades.iterrows():
                entry_time = pd.to_datetime(trade['entry_time']).strftime('%m-%d %H:%M')
                side_emoji = "📈" if trade['side'] == 'BUY' else "📉"
                
                message += f"""
{side_emoji} **{trade['symbol']}** ({trade['strategy']})
   {trade['side']} {trade['quantity']} @ ${trade['entry_price']:.2f}
   📅 Abierto: {entry_time}
"""
            
            message += f"\n🔢 Total: {len(open_trades)} posiciones abiertas"
            message += "\n═══════════════════════════════"
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo posiciones abiertas: {str(e)}")

def send_performance_summary():
    """Send comprehensive performance summary"""
    try:
        with _get_database_connection() as conn:
            # Rendimiento por día (últimos 7 días)
            daily_performance = pd.read_sql_query("""
                SELECT DATE(entry_time) as date,
                       COUNT(*) as trades,
                       COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed,
                       COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as daily_pnl
                FROM trades
                WHERE entry_time >= date('now', '-7 days')
                GROUP BY DATE(entry_time)
                ORDER BY date DESC
            """, conn)
            
            # Mejores y peores trades
            best_worst = pd.read_sql_query("""
                SELECT symbol, strategy, pnl, entry_time,
                       CASE WHEN pnl = (SELECT MAX(pnl) FROM trades WHERE status = 'CLOSED') 
                            THEN 'BEST' ELSE 'WORST' END as type
                FROM trades
                WHERE status = 'CLOSED' 
                AND (pnl = (SELECT MAX(pnl) FROM trades WHERE status = 'CLOSED')
                     OR pnl = (SELECT MIN(pnl) FROM trades WHERE status = 'CLOSED'))
                ORDER BY pnl DESC
            """, conn)
            
            message = """
🏆 **RESUMEN DE RENDIMIENTO**
═══════════════════════════════

"""
            
            if not daily_performance.empty:
                message += "**📅 ÚLTIMOS 7 DÍAS:**\n"
                total_week_pnl = 0
                for _, day in daily_performance.iterrows():
                    pnl_emoji = "🟢" if day['daily_pnl'] > 0 else "🔴" if day['daily_pnl'] < 0 else "⚪"
                    date_formatted = pd.to_datetime(day['date']).strftime('%m-%d')
                    message += f"• {date_formatted}: {pnl_emoji} ${day['daily_pnl']:.2f} ({day['closed']} trades)\n"
                    total_week_pnl += day['daily_pnl']
                
                week_emoji = "🟢" if total_week_pnl > 0 else "🔴" if total_week_pnl < 0 else "⚪"
                message += f"\n📊 **Total Semana**: {week_emoji} ${total_week_pnl:.2f}\n"
            
            if not best_worst.empty:
                message += "\n**🏆 MEJORES/PEORES TRADES:**\n"
                for _, trade in best_worst.iterrows():
                    emoji = "🥇" if trade['type'] == 'BEST' else "💥"
                    date_formatted = pd.to_datetime(trade['entry_time']).strftime('%m-%d')
                    message += f"{emoji} {trade['symbol']} ({trade['strategy']}): ${trade['pnl']:.2f} - {date_formatted}\n"
            
            message += "\n═══════════════════════════════"
            send_message(message, parse_mode="Markdown")
            
    except Exception as e:
        send_message(f"❌ Error obteniendo resumen de rendimiento: {str(e)}")

def clear_mayordomo_cache():
    """Clear Mayordomo active daily plays cache to fix stuck positions"""
    try:
        # Import production runner to access Mayordomo instance
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Try to get the running Mayordomo instance from production runner
        from production.smallcap_production_runner import SmallcapProductionRunner
        
        # This is a bit hacky, but we need access to the running instance
        # In a real production system, you'd have a better way to access this
        try:
            # Method 1: Try to access global production runner instance if it exists
            import production.smallcap_production_runner as prod_module
            runner = None
            
            if hasattr(prod_module, '_global_runner_instance') and prod_module._global_runner_instance:
                runner = prod_module._global_runner_instance
                send_message("✅ Encontrada instancia global del sistema")
            else:
                send_message("⚠️ Instancia global no encontrada, intentando método alternativo...")
                
                # Method 2: Try to create temporary Mayordomo instance to clear cache files
                try:
                    from core.interfaces import TradingConfig
                    from core.risk_manager import create_smallcap_mayordomo
                    
                    # Create minimal config for cache clearing
                    temp_config = TradingConfig(
                        max_daily_trades=10,
                        max_daily_loss=-1000.0,
                        max_position_value=500.0,
                        position_size=0.02
                    )
                    
                    # Create temporary Mayordomo instance
                    temp_mayordomo = create_smallcap_mayordomo(temp_config)
                    
                    # Check if it has active plays and clear them
                    if hasattr(temp_mayordomo, 'active_daily_plays') and temp_mayordomo.active_daily_plays:
                        count = len(temp_mayordomo.active_daily_plays)
                        symbols = list(temp_mayordomo.active_daily_plays.keys())
                        temp_mayordomo.clear_active_plays(force=True)
                        send_message(f"🔄 **CACHE LIMPIADO (método alternativo)**\n\n{count} posiciones eliminadas: {', '.join(symbols[:5])}\n\nEl sistema ya puede procesar nuevos tickers.")
                        return
                    else:
                        send_message("ℹ️ No se encontraron posiciones activas en el cache.")
                        return
                        
                except Exception as method2_e:
                    send_message(f"⚠️ Método alternativo también falló: {str(method2_e)}")
            
            if runner and hasattr(runner, 'mayordomo') and runner.mayordomo:
                # Clear active plays using global instance
                if hasattr(runner.mayordomo, 'active_daily_plays') and runner.mayordomo.active_daily_plays:
                    count = len(runner.mayordomo.active_daily_plays)
                    symbols = list(runner.mayordomo.active_daily_plays.keys())
                    runner.mayordomo.clear_active_plays(force=True)
                    send_message(f"🔄 **CACHE LIMPIADO**\n\n{count} posiciones eliminadas: {', '.join(symbols[:5])}\n\nEl sistema ya puede procesar nuevos tickers.")
                else:
                    send_message("ℹ️ No se encontraron posiciones activas en el cache.")
            else:
                send_message("⚠️ No se pudo acceder al Mayordomo. El sistema puede no estar ejecutándose.")
                
        except Exception as inner_e:
            send_message(f"⚠️ Todos los métodos fallaron: {str(inner_e)}\n\n**SOLUCIÓN MANUAL:**\nReinicia el sistema completamente para limpiar el cache.")
            
    except Exception as e:
        send_message(f"❌ Error limpiando cache del Mayordomo: {str(e)}")
