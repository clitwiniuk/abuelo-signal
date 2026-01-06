#!/bin/bash
#
# Trading System Supervisor - Auto-restart & Schedule Manager
# ============================================================
# Mantiene el sistema de trading corriendo 24/7 con reinicio inteligente
#
# Features:
# - Detecta desconexiones de TWS y reinicia automáticamente
# - Schedule diario: Apaga a medianoche, enciende a las 08:00 ET
# - Watchdog para el trading system (reinicia si crashea)
# - Logging completo de eventos
# - Compatible con IBC para login automático
#
# Usage:
#   chmod +x trading_system_supervisor.sh
#   ./trading_system_supervisor.sh start
#   ./trading_system_supervisor.sh stop
#   ./trading_system_supervisor.sh restart
#   ./trading_system_supervisor.sh status
#
# Run as background service:
#   nohup ./trading_system_supervisor.sh start > supervisor.log 2>&1 &

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IBC_DIR="$HOME/ibc"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON="$VENV_DIR/bin/python"
TRADER_MAIN="$PROJECT_ROOT/trader_main.py"

# PIDs
SUPERVISOR_PID_FILE="/tmp/trading_supervisor.pid"
TRADER_PID_FILE="/tmp/trader_main.pid"
TWS_PID_FILE="/tmp/tws_ibc.pid"

# Logs
LOG_DIR="$PROJECT_ROOT/logs/supervisor"
SUPERVISOR_LOG="$LOG_DIR/supervisor.log"
RESTART_LOG="$LOG_DIR/restarts.log"

# Schedule (ET timezone)
SHUTDOWN_HOUR=17   # 17:00 ET (5:00 PM - after market close)
STARTUP_HOUR=8     # 08:00 ET (morning)

# Market Calendar (holidays, early closes)
USE_MARKET_CALENDAR=true      # Check if today is a trading day
MARKET_CALENDAR_SCRIPT="$PROJECT_ROOT/scripts/automation/check_market_day.py"

# Health check intervals (seconds)
HEALTH_CHECK_INTERVAL=60      # Check every 60 seconds
TWS_CHECK_INTERVAL=30         # Check TWS every 30 seconds

# Max restart attempts
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=300          # 5 minutes between restart attempts

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$SUPERVISOR_LOG"
}

log_restart() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$RESTART_LOG"
}

get_et_hour() {
    # Get current hour in ET timezone
    TZ='America/New_York' date '+%H'
}

is_trading_day() {
    # Check if today is a valid trading day (not holiday)
    if [ "$USE_MARKET_CALENDAR" = "true" ]; then
        if [ -f "$MARKET_CALENDAR_SCRIPT" ]; then
            # Run Python script to check market calendar
            if "$PYTHON" "$MARKET_CALENDAR_SCRIPT" is_market_day 2>/dev/null; then
                return 0  # True - market is open today
            else
                return 1  # False - market is closed (holiday)
            fi
        else
            log "⚠️  Market calendar script not found: $MARKET_CALENDAR_SCRIPT"
            log "   Assuming it's a trading day (fallback)"
            return 0  # Fallback to assuming it's a trading day
        fi
    else
        return 0  # Market calendar disabled - assume trading day
    fi
}

get_market_close_time() {
    # Get market close time for today (handles early closes)
    if [ "$USE_MARKET_CALENDAR" = "true" ] && [ -f "$MARKET_CALENDAR_SCRIPT" ]; then
        local close_time=$("$PYTHON" "$MARKET_CALENDAR_SCRIPT" get_close_time 2>/dev/null)
        if [ -n "$close_time" ]; then
            echo "$close_time"
        else
            echo "16"  # Default: 4:00 PM
        fi
    else
        echo "16"  # Default: 4:00 PM
    fi
}

is_within_trading_hours() {
    local hour=$(get_et_hour)

    # Check if today is a trading day first
    if ! is_trading_day; then
        return 1  # Market is closed (holiday)
    fi

    # Trading hours: STARTUP_HOUR - 23:59 ET (or early close)
    if [ "$hour" -ge "$STARTUP_HOUR" ] && [ "$hour" -lt "$SHUTDOWN_HOUR" ]; then
        return 0  # True
    else
        return 1  # False
    fi
}

is_process_running() {
    local pid_file=$1

    if [ ! -f "$pid_file" ]; then
        return 1  # PID file doesn't exist
    fi

    local pid=$(cat "$pid_file")

    if ps -p "$pid" > /dev/null 2>&1; then
        return 0  # Process is running
    else
        return 1  # Process is not running
    fi
}

# =============================================================================
# TWS/IBC MANAGEMENT
# =============================================================================

start_tws() {
    log "🚀 Starting TWS via IBC..."

    # Check if IBC is installed
    if [ ! -d "$IBC_DIR" ]; then
        log "❌ IBC not found at $IBC_DIR"
        log "   Run: ./install_ibc.sh first"
        return 1
    fi

    # Check if config exists
    if [ ! -f "$IBC_DIR/config.ini" ]; then
        log "❌ IBC config not found at $IBC_DIR/config.ini"
        log "   Run: cp $IBC_DIR/config.ini.template $IBC_DIR/config.ini"
        log "   Then edit with your IBKR credentials"
        return 1
    fi

    # Kill existing TWS if running
    if is_process_running "$TWS_PID_FILE"; then
        log "⚠️  TWS already running, stopping first..."
        stop_tws
        sleep 5
    fi

    # Start TWS/Gateway via IBC
    cd "$IBC_DIR"
    # Use gatewaystartmacos.sh (lighter) or twsstartmacos.sh (full UI)
    # Gateway is recommended for automated trading
    nohup ./gatewaystartmacos.sh > "$LOG_DIR/tws.log" 2>&1 &
    local tws_pid=$!
    echo "$tws_pid" > "$TWS_PID_FILE"

    log "✅ Gateway started via IBC (PID: $tws_pid)"
    log "   Waiting 60 seconds for Gateway to initialize and auto-login..."
    sleep 60

    return 0
}

stop_tws() {
    log "🛑 Stopping TWS..."

    if is_process_running "$TWS_PID_FILE"; then
        local pid=$(cat "$TWS_PID_FILE")
        kill "$pid" 2>/dev/null || true
        sleep 3

        # Force kill if still running
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -9 "$pid" 2>/dev/null || true
        fi

        rm -f "$TWS_PID_FILE"
        log "✅ TWS stopped"
    else
        log "ℹ️  TWS was not running"
    fi
}

check_tws_health() {
    # Check if TWS process is running
    if ! is_process_running "$TWS_PID_FILE"; then
        return 1  # TWS is down
    fi

    # TODO: Add more sophisticated health checks
    # - Check if TWS API port is responsive
    # - Check last market data update timestamp
    # - Check if connection is alive

    return 0  # TWS is healthy
}

# =============================================================================
# TRADING SYSTEM MANAGEMENT
# =============================================================================

start_trader() {
    log "🤖 Starting Trading System..."

    # Check if already running
    if is_process_running "$TRADER_PID_FILE"; then
        log "⚠️  Trading system already running"
        return 0
    fi

    # Ensure TWS is running first
    if ! check_tws_health; then
        log "⚠️  TWS not running, starting TWS first..."
        start_tws

        if [ $? -ne 0 ]; then
            log "❌ Failed to start TWS, cannot start trading system"
            return 1
        fi
    fi

    # Start trader_main.py
    cd "$PROJECT_ROOT"
    nohup "$PYTHON" "$TRADER_MAIN" > "$LOG_DIR/trader.log" 2>&1 &
    local trader_pid=$!
    echo "$trader_pid" > "$TRADER_PID_FILE"

    log "✅ Trading System started (PID: $trader_pid)"
    log_restart "STARTUP: Trading system started"

    return 0
}

stop_trader() {
    log "🛑 Stopping Trading System..."

    if is_process_running "$TRADER_PID_FILE"; then
        local pid=$(cat "$TRADER_PID_FILE")

        # Graceful shutdown (SIGTERM)
        kill "$pid" 2>/dev/null || true
        sleep 5

        # Force kill if still running (SIGKILL)
        if ps -p "$pid" > /dev/null 2>&1; then
            log "⚠️  Graceful shutdown failed, forcing..."
            kill -9 "$pid" 2>/dev/null || true
        fi

        rm -f "$TRADER_PID_FILE"
        log "✅ Trading System stopped"
        log_restart "SHUTDOWN: Trading system stopped"
    else
        log "ℹ️  Trading system was not running"
    fi
}

restart_trader() {
    log "🔄 Restarting Trading System..."
    log_restart "RESTART: Manual restart triggered"

    stop_trader
    sleep 3
    start_trader
}

check_trader_health() {
    # Check if trader process is running
    if ! is_process_running "$TRADER_PID_FILE"; then
        return 1  # Trader is down
    fi

    # TODO: Add more sophisticated health checks
    # - Check last log timestamp
    # - Check if worker threads are alive
    # - Check API connection status

    return 0  # Trader is healthy
}

# =============================================================================
# WATCHDOG - Main Supervisor Loop
# =============================================================================

watchdog() {
    log "=================================================="
    log "🐕 Trading System Supervisor Started"
    log "=================================================="
    log "Schedule:"
    log "  - Startup:  $STARTUP_HOUR:00 ET"
    log "  - Shutdown: $SHUTDOWN_HOUR:00 ET (after market close)"
    log ""
    log "Market Calendar:"
    log "  - Enabled: $USE_MARKET_CALENDAR"
    if [ "$USE_MARKET_CALENDAR" = "true" ]; then
        if is_trading_day; then
            local close_time=$(get_market_close_time)
            log "  - Today: TRADING DAY (closes at ${close_time}:00 ET)"
        else
            log "  - Today: HOLIDAY/WEEKEND (market closed)"
        fi
    fi
    log ""
    log "Health Checks:"
    log "  - Trading System: Every ${HEALTH_CHECK_INTERVAL}s"
    log "  - TWS Connection: Every ${TWS_CHECK_INTERVAL}s"
    log "=================================================="

    local restart_attempts=0
    local last_restart_time=0
    local last_trading_day_check=$(date +%Y-%m-%d)

    while true; do
        current_time=$(date +%s)
        current_hour=$(get_et_hour)
        current_date=$(date +%Y-%m-%d)

        # =================================================================
        # DAILY TRADING DAY CHECK (once per day at startup hour)
        # =================================================================
        if [ "$current_date" != "$last_trading_day_check" ] && [ "$current_hour" -eq "$STARTUP_HOUR" ]; then
            last_trading_day_check=$current_date

            if ! is_trading_day; then
                log "📅 $(date '+%Y-%m-%d') is NOT a trading day (holiday/weekend)"
                log "   Skipping today - system will sleep until tomorrow"
                log_restart "HOLIDAY: Market closed today - no trading"

                # Stop any running systems
                if is_process_running "$TRADER_PID_FILE"; then
                    stop_trader
                fi
                if is_process_running "$TWS_PID_FILE"; then
                    stop_tws
                fi

                # Sleep until next day check (6 hours)
                sleep 21600
                continue
            else
                local close_time=$(get_market_close_time)
                log "✅ $(date '+%Y-%m-%d') is a TRADING DAY (market closes at ${close_time}:00 ET)"

                if [ "$close_time" != "16" ]; then
                    log "⚠️  EARLY CLOSE detected: Market closes at ${close_time}:00 ET instead of 16:00 ET"
                    log_restart "EARLY_CLOSE: Market closes at ${close_time}:00 ET today"
                fi
            fi
        fi

        # =================================================================
        # SCHEDULED SHUTDOWN (17:00 ET - After Market Close)
        # =================================================================
        if [ "$current_hour" -eq "$SHUTDOWN_HOUR" ]; then
            if is_process_running "$TRADER_PID_FILE"; then
                log "🌙 17:00 ET - Scheduled shutdown (after market close)"
                stop_trader
                stop_tws

                # Sleep until startup time (17:00 ET to 08:00 ET = 15 hours)
                log "😴 Sleeping until ${STARTUP_HOUR}:00 ET..."
                sleep 54000  # 15 hours (15 * 3600 seconds)
                continue
            fi
        fi

        # =================================================================
        # SCHEDULED STARTUP (08:00 ET)
        # =================================================================
        if [ "$current_hour" -eq "$STARTUP_HOUR" ]; then
            if ! is_process_running "$TRADER_PID_FILE"; then
                log "☀️  ${STARTUP_HOUR}:00 ET - Scheduled startup"
                start_tws
                sleep 10
                start_trader
            fi
        fi

        # =================================================================
        # HEALTH CHECKS (During trading hours only)
        # =================================================================
        if is_within_trading_hours; then

            # Check TWS health
            if ! check_tws_health; then
                log "❌ TWS health check failed - TWS is down"
                log_restart "TWS_DOWN: Detected TWS disconnection"

                # Check restart cooldown
                time_since_restart=$((current_time - last_restart_time))
                if [ $time_since_restart -lt $RESTART_COOLDOWN ]; then
                    log "⏳ Restart cooldown active (${time_since_restart}s / ${RESTART_COOLDOWN}s)"
                    sleep 30
                    continue
                fi

                # Check max restart attempts
                if [ $restart_attempts -ge $MAX_RESTART_ATTEMPTS ]; then
                    log "🚨 MAX RESTART ATTEMPTS REACHED ($MAX_RESTART_ATTEMPTS)"
                    log "   Manual intervention required"
                    log "   Stopping supervisor..."
                    log_restart "CRITICAL: Max restart attempts reached - supervisor stopped"
                    break
                fi

                # Restart TWS
                restart_attempts=$((restart_attempts + 1))
                last_restart_time=$current_time

                log "🔄 Restarting TWS (Attempt $restart_attempts/$MAX_RESTART_ATTEMPTS)..."
                log_restart "TWS_RESTART: Attempt $restart_attempts/$MAX_RESTART_ATTEMPTS"

                stop_tws
                sleep 5
                start_tws

                # Restart trader if it was running
                if is_process_running "$TRADER_PID_FILE"; then
                    log "🔄 Restarting trading system after TWS restart..."
                    restart_trader
                fi
            fi

            # Check Trader health
            if ! check_trader_health; then
                log "❌ Trading system health check failed - Trader is down"
                log_restart "TRADER_DOWN: Detected trader crash"

                # Check restart cooldown
                time_since_restart=$((current_time - last_restart_time))
                if [ $time_since_restart -lt $RESTART_COOLDOWN ]; then
                    log "⏳ Restart cooldown active"
                    sleep 30
                    continue
                fi

                # Check max restart attempts
                if [ $restart_attempts -ge $MAX_RESTART_ATTEMPTS ]; then
                    log "🚨 MAX RESTART ATTEMPTS REACHED"
                    log_restart "CRITICAL: Max restart attempts reached"
                    break
                fi

                # Restart trader
                restart_attempts=$((restart_attempts + 1))
                last_restart_time=$current_time

                log "🔄 Restarting trader (Attempt $restart_attempts/$MAX_RESTART_ATTEMPTS)..."
                log_restart "TRADER_RESTART: Attempt $restart_attempts/$MAX_RESTART_ATTEMPTS"

                restart_trader
            else
                # Reset restart counter on successful health check
                if [ $restart_attempts -gt 0 ]; then
                    log "✅ System stable - resetting restart counter"
                    restart_attempts=0
                fi
            fi
        fi

        # Sleep before next check
        sleep "$HEALTH_CHECK_INTERVAL"
    done

    log "🛑 Watchdog terminated"
}

# =============================================================================
# COMMAND INTERFACE
# =============================================================================

case "${1:-}" in
    start)
        # Start supervisor as background daemon
        if is_process_running "$SUPERVISOR_PID_FILE"; then
            echo "⚠️  Supervisor already running (PID: $(cat $SUPERVISOR_PID_FILE))"
            exit 1
        fi

        echo "🚀 Starting Trading System Supervisor..."

        # Start watchdog in background
        nohup bash "$0" _watchdog > "$LOG_DIR/supervisor_daemon.log" 2>&1 &
        echo $! > "$SUPERVISOR_PID_FILE"

        echo "✅ Supervisor started (PID: $(cat $SUPERVISOR_PID_FILE))"
        echo "📋 Logs: $SUPERVISOR_LOG"
        echo ""
        echo "To stop: $0 stop"
        echo "To check status: $0 status"
        ;;

    _watchdog)
        # Internal command - run watchdog loop
        watchdog
        ;;

    stop)
        echo "🛑 Stopping Trading System Supervisor..."

        # Stop supervisor
        if is_process_running "$SUPERVISOR_PID_FILE"; then
            kill $(cat "$SUPERVISOR_PID_FILE") 2>/dev/null || true
            rm -f "$SUPERVISOR_PID_FILE"
        fi

        # Stop trader
        stop_trader

        # Stop TWS
        stop_tws

        echo "✅ All systems stopped"
        ;;

    restart)
        $0 stop
        sleep 3
        $0 start
        ;;

    status)
        echo "=================================================="
        echo "Trading System Supervisor Status"
        echo "=================================================="

        # Supervisor status
        if is_process_running "$SUPERVISOR_PID_FILE"; then
            echo "✅ Supervisor: RUNNING (PID: $(cat $SUPERVISOR_PID_FILE))"
        else
            echo "❌ Supervisor: STOPPED"
        fi

        # TWS status
        if is_process_running "$TWS_PID_FILE"; then
            echo "✅ TWS: RUNNING (PID: $(cat $TWS_PID_FILE))"
        else
            echo "❌ TWS: STOPPED"
        fi

        # Trader status
        if is_process_running "$TRADER_PID_FILE"; then
            echo "✅ Trading System: RUNNING (PID: $(cat $TRADER_PID_FILE))"
        else
            echo "❌ Trading System: STOPPED"
        fi

        echo ""
        echo "Current ET Time: $(TZ='America/New_York' date '+%Y-%m-%d %H:%M:%S %Z')"
        echo "Trading Hours: $(is_within_trading_hours && echo 'YES' || echo 'NO')"
        echo ""
        echo "Recent Restarts (last 10):"
        tail -10 "$RESTART_LOG" 2>/dev/null || echo "  (no restarts logged)"
        echo "=================================================="
        ;;

    *)
        echo "Trading System Supervisor"
        echo ""
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start    - Start supervisor (background daemon)"
        echo "  stop     - Stop supervisor and all systems"
        echo "  restart  - Restart supervisor"
        echo "  status   - Show system status"
        exit 1
        ;;
esac
