from database.db_manager import (
    unlock_achievement, check_achievement_exists, get_trades_by_user,
    get_daily_reports_stats, get_setups_mastery
)

def check_all_achievements(user_id):
    """
    Verificar y desbloquear todos los logros posibles para un usuario
    
    Returns:
        Lista de logros nuevos desbloqueados
    """
    nuevos_logros = []
    
    # Obtener datos necesarios
    trades = get_trades_by_user(user_id)
    daily_reports = get_daily_reports_stats(user_id, dias=365)
    setups = get_setups_mastery(user_id)
    
    # Logro: First Blood - Primer trade
    if len(trades) >= 1:
        if unlock_achievement_if_not_exists(user_id, "First Blood", "🥉", 
            "Ejecutaste tu primer trade. ¡Bienvenido al mundo del trading!"):
            nuevos_logros.append("First Blood")
    
    # Logro: Consistency King - 10 trades siguiendo plan
    trades_cumpliendo_plan = sum(1 for t in trades if t.get('cumplio_plan'))
    if trades_cumpliendo_plan >= 10:
        if unlock_achievement_if_not_exists(user_id, "Consistency King", "👑",
            "10 trades ejecutados siguiendo tu plan al pie de la letra."):
            nuevos_logros.append("Consistency King")
    
    # Logro: VWAP Master - 20 trades ganadores con Setup B
    vwap_wins = sum(1 for t in trades if t.get('setup') == 'VWAP Bounce' and t.get('pnl', 0) > 0)
    if vwap_wins >= 20:
        if unlock_achievement_if_not_exists(user_id, "VWAP Master", "📊",
            "20 trades ganadores usando el setup VWAP Bounce de Alex Temiz."):
            nuevos_logros.append("VWAP Master")
    
    # Logro: Morning Panic Pro - 20 trades ganadores con Setup A
    panic_wins = sum(1 for t in trades if t.get('setup') == 'Morning Panic Dip' and t.get('pnl', 0) > 0)
    if panic_wins >= 20:
        if unlock_achievement_if_not_exists(user_id, "Morning Panic Pro", "🌅",
            "20 trades ganadores usando el setup Morning Panic Dip de Kyle Williams."):
            nuevos_logros.append("Morning Panic Pro")
    
    # Logro: Risk Manager - 30 días sin exceder riesgo
    dias_cumpliendo_riesgo = sum(1 for r in daily_reports if r.get('cumplio_sueno'))
    if dias_cumpliendo_riesgo >= 30:
        if unlock_achievement_if_not_exists(user_id, "Risk Manager", "🛡️",
            "30 días de trading disciplinado sin exceder tus límites de riesgo."):
            nuevos_logros.append("Risk Manager")
    
    # Logro: Setup Collector - Dominar todos los setups
    setups_dominados = sum(1 for s in setups if s.get('dominado'))
    if setups_dominados >= 4:
        if unlock_achievement_if_not_exists(user_id, "Setup Collector", "🎓",
            "Has dominado los 4 setups de la academia. ¡Eres un trader completo!"):
            nuevos_logros.append("Setup Collector")
    
    # Logro: Psychology Master - 7 daily reports consecutivos
    if len(daily_reports) >= 7:
        if unlock_achievement_if_not_exists(user_id, "Journal Keeper", "📓",
            "7 Daily Report Cards completados. La disciplina es la clave."):
            nuevos_logros.append("Journal Keeper")
    
    # Logro: Win Rate Warrior - 55% win rate con 50+ trades
    if len(trades) >= 50:
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = (winning_trades / len(trades)) * 100
        if win_rate >= 55:
            if unlock_achievement_if_not_exists(user_id, "Win Rate Warrior", "⚔️",
                f"{win_rate:.1f}% win rate en {len(trades)} trades. ¡Excelente consistencia!"):
                nuevos_logros.append("Win Rate Warrior")
    
    # Logro: Profit Factor Pro - PF > 1.5 con 30+ trades
    if len(trades) >= 30:
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        if gross_loss > 0:
            pf = gross_profit / gross_loss
            if pf >= 1.5:
                if unlock_achievement_if_not_exists(user_id, "Profit Factor Pro", "💰",
                    f"Profit Factor de {pf:.2f}. Tus ganancias superan tus pérdidas significativamente."):
                    nuevos_logros.append("Profit Factor Pro")
    
    # Logro: 100 Trades Club
    if len(trades) >= 100:
        if unlock_achievement_if_not_exists(user_id, "100 Trades Club", "💯",
            "Has ejecutado 100 trades. La experiencia es el mejor maestro."):
            nuevos_logros_logros.append("100 Trades Club")
    
    # Logro: Elite Status - Alcanzar Nivel 5
    from database.db_manager import get_user_by_id
    user = get_user_by_id(user_id)
    if user and user.get('nivel_actual') >= 5:
        if unlock_achievement_if_not_exists(user_id, "Elite Status", "🏆",
            "Has alcanzado el Nivel 5: Elite Trader. ¡Eres parte de la élite!"):
            nuevos_logros.append("Elite Status")
    
    # Logro: R-Multiple Master - Promedio R > 2R
    if len(trades) >= 20:
        r_multiples = [t.get('r_multiple', 0) for t in trades if t.get('r_multiple') is not None]
        if r_multiples:
            avg_r = sum(r_multiples) / len(r_multiples)
            if avg_r >= 2:
                if unlock_achievement_if_not_exists(user_id, "R-Multiple Master", "📈",
                    f"Promedio de {avg_r:.2f}R por trade. Ganas el doble de lo que arriesgas."):
                    nuevos_logros.append("R-Multiple Master")
    
    # Logro: No FOMO - 20 trades sin FOMO
    trades_sin_fomo = sum(1 for t in trades if not t.get('fomo', False))
    if trades_sin_fomo >= 20:
        if unlock_achievement_if_not_exists(user_id, "No FOMO", "🧘",
            "20 trades ejecutados sin caer en el FOMO. Control emocional excepcional."):
            nuevos_logros.append("No FOMO")
    
    # Logro: Backtest King - Completar 20 backtests
    backtests = sum(1 for r in daily_reports if r.get('backtests_completados', 0))
    if backtests >= 20:
        if unlock_achievement_if_not_exists(user_id, "Backtest King", "🔬",
            "Has completado 20 sesiones de backtesting. La preparación es clave."):
            nuevos_logros.append("Backtest King")
    
    return nuevos_logros

def unlock_achievement_if_not_exists(user_id, badge_name, badge_icon, descripcion):
    """Desbloquear logro solo si no existe"""
    if not check_achievement_exists(user_id, badge_name):
        return unlock_achievement(user_id, badge_name, badge_icon, descripcion)
    return False

def get_achievement_progress(user_id, achievement_name):
    """
    Obtener progreso hacia un logro específico
    
    Returns:
        Dict con progreso actual y requerido
    """
    trades = get_trades_by_user(user_id)
    daily_reports = get_daily_reports_stats(user_id, dias=365)
    setups = get_setups_mastery(user_id)
    
    progress_map = {
        "First Blood": {
            "current": len(trades),
            "required": 1,
            "unit": "trades"
        },
        "Consistency King": {
            "current": sum(1 for t in trades if t.get('cumplio_plan')),
            "required": 10,
            "unit": "trades según plan"
        },
        "VWAP Master": {
            "current": sum(1 for t in trades if t.get('setup') == 'VWAP Bounce' and t.get('pnl', 0) > 0),
            "required": 20,
            "unit": "trades ganados"
        },
        "Morning Panic Pro": {
            "current": sum(1 for t in trades if t.get('setup') == 'Morning Panic Dip' and t.get('pnl', 0) > 0),
            "required": 20,
            "unit": "trades ganados"
        },
        "Risk Manager": {
            "current": sum(1 for r in daily_reports if r.get('cumplio_sueno')),
            "required": 30,
            "unit": "días"
        },
        "Setup Collector": {
            "current": sum(1 for s in setups if s.get('dominado')),
            "required": 4,
            "unit": "setups dominados"
        },
        "Journal Keeper": {
            "current": len(daily_reports),
            "required": 7,
            "unit": "daily reports"
        },
        "Win Rate Warrior": {
            "current": len(trades),
            "required": 50,
            "unit": "trades totales (necesitas 55% WR)"
        },
        "100 Trades Club": {
            "current": len(trades),
            "required": 100,
            "unit": "trades"
        },
        "R-Multiple Master": {
            "current": len([t for t in trades if t.get('r_multiple') is not None]),
            "required": 20,
            "unit": "trades con R (necesitas 2R promedio)"
        }
    }
    
    return progress_map.get(achievement_name, {"current": 0, "required": 1, "unit": ""})

# Diccionario de todos los logros disponibles
ALL_ACHIEVEMENTS = {
    "First Blood": {
        "icon": "🥉",
        "name": "First Blood",
        "description": "Ejecuta tu primer trade",
        "category": "Principiante",
        "difficulty": "Fácil"
    },
    "Consistency King": {
        "icon": "👑",
        "name": "Consistency King",
        "description": "10 trades ejecutados siguiendo tu plan",
        "category": "Disciplina",
        "difficulty": "Media"
    },
    "VWAP Master": {
        "icon": "📊",
        "name": "VWAP Master",
        "description": "20 trades ganadores usando VWAP Bounce",
        "category": "Setup Mastery",
        "difficulty": "Media"
    },
    "Morning Panic Pro": {
        "icon": "🌅",
        "name": "Morning Panic Pro",
        "description": "20 trades ganadores usando Morning Panic Dip",
        "category": "Setup Mastery",
        "difficulty": "Media"
    },
    "Risk Manager": {
        "icon": "🛡️",
        "name": "Risk Manager",
        "description": "30 días sin exceder límites de riesgo",
        "category": "Gestión de Riesgo",
        "difficulty": "Difícil"
    },
    "Setup Collector": {
        "icon": "🎓",
        "name": "Setup Collector",
        "description": "Domina los 4 setups de la academia",
        "category": "Maestría",
        "difficulty": "Difícil"
    },
    "Journal Keeper": {
        "icon": "📓",
        "name": "Journal Keeper",
        "description": "7 Daily Report Cards completados",
        "category": "Disciplina",
        "difficulty": "Fácil"
    },
    "Win Rate Warrior": {
        "icon": "⚔️",
        "name": "Win Rate Warrior",
        "description": "55% win rate con al menos 50 trades",
        "category": "Rendimiento",
        "difficulty": "Difícil"
    },
    "Profit Factor Pro": {
        "icon": "💰",
        "name": "Profit Factor Pro",
        "description": "Profit Factor mayor a 1.5 con 30+ trades",
        "category": "Rendimiento",
        "difficulty": "Difícil"
    },
    "100 Trades Club": {
        "icon": "💯",
        "name": "100 Trades Club",
        "description": "Ejecuta 100 trades",
        "category": "Experiencia",
        "difficulty": "Media"
    },
    "Elite Status": {
        "icon": "🏆",
        "name": "Elite Status",
        "description": "Alcanza el Nivel 5: Elite Trader",
        "category": "Progresión",
        "difficulty": "Muy Difícil"
    },
    "R-Multiple Master": {
        "icon": "📈",
        "name": "R-Multiple Master",
        "description": "Promedio de 2R o más por trade",
        "category": "Rendimiento",
        "difficulty": "Difícil"
    },
    "No FOMO": {
        "icon": "🧘",
        "name": "No FOMO",
        "description": "20 trades sin caer en el FOMO",
        "category": "Psicología",
        "difficulty": "Media"
    },
    "Backtest King": {
        "icon": "🔬",
        "name": "Backtest King",
        "description": "Completa 20 sesiones de backtesting",
        "category": "Preparación",
        "difficulty": "Media"
    }
}