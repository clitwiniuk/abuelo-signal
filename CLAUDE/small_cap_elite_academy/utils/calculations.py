import numpy as np

def calculate_r_multiple(entry, exit_price, stop_loss, position_type='LONG'):
    """
    Calcular R-Multiple de un trade
    
    R-Multiple = (Exit - Entry) / (Entry - Stop Loss) para LONG
    R-Multiple = (Entry - Exit) / (Stop Loss - Entry) para SHORT
    
    Args:
        entry: Precio de entrada
        exit_price: Precio de salida
        stop_loss: Precio del stop loss
        position_type: 'LONG' o 'SHORT'
    
    Returns:
        R-Multiple del trade
    """
    if position_type == 'LONG':
        risk = entry - stop_loss
        reward = exit_price - entry
    else:  # SHORT
        risk = stop_loss - entry
        reward = entry - exit_price
    
    if risk == 0:
        return 0
    
    return round(reward / risk, 2)

def calculate_position_size(capital, risk_percent, entry, stop_loss, 
                           slippage=0.002, commission_per_share=0.005):
    """
    Calcular tamaño de posición basado en riesgo
    
    Args:
        capital: Capital disponible
        risk_percent: Porcentaje del capital a arriesgar
        entry: Precio de entrada
        stop_loss: Precio del stop loss
        slippage: Slippage estimado (default 0.2%)
        commission_per_share: Comisión por acción
    
    Returns:
        Dict con shares, risk_amount, total_cost, etc.
    """
    if entry <= stop_loss:
        return {'error': 'Stop loss debe ser menor que entrada para LONG'}
    
    # Cantidad a arriesgar
    risk_amount = capital * (risk_percent / 100)
    
    # Riesgo por acción incluyendo slippage
    price_risk = abs(entry - stop_loss)
    slippage_amount = entry * slippage
    total_risk_per_share = price_risk + slippage_amount + commission_per_share
    
    # Número de acciones
    shares = int(risk_amount / total_risk_per_share)
    
    # Costo total
    total_cost = shares * entry
    commission = shares * commission_per_share
    
    return {
        'shares': shares,
        'risk_amount': risk_amount,
        'risk_per_share': total_risk_per_share,
        'total_cost': total_cost,
        'commission': commission,
        'slippage_cost': shares * slippage_amount,
        'max_loss': shares * total_risk_per_share
    }

def calculate_slippage(price, volume, avg_volume, volatility=0.3, 
                      base_slippage=0.002, is_market_order=True):
    """
    Calcular slippage realista para small caps
    
    Args:
        price: Precio de la acción
        volume: Volumen actual
        avg_volume: Volumen promedio
        volatility: Volatilidad del stock
        base_slippage: Slippage base
        is_market_order: Si es orden de mercado
    
    Returns:
        Porcentaje de slippage
    """
    if not is_market_order:
        return 0  # Limit orders no tienen slippage si se ejecutan
    
    # Factor de volumen (menor volumen = mayor slippage)
    volume_factor = 1 + (avg_volume / max(volume, 1) - 1) * 0.5
    
    # Factor de volatilidad
    vol_factor = 1 + volatility
    
    # Factor de precio (stocks más baratos tienen más slippage)
    price_factor = 1 + max(0, (5 - price) / 10)
    
    slippage = base_slippage * volume_factor * vol_factor * price_factor
    
    return min(slippage, 0.02)  # Máximo 2% de slippage

def calculate_profit_factor(gross_profit, gross_loss):
    """
    Calcular Profit Factor
    
    Profit Factor = Gross Profit / Gross Loss
    
    Args:
        gross_profit: Ganancias brutas totales
        gross_loss: Pérdidas brutas totales (valor positivo)
    
    Returns:
        Profit Factor
    """
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0
    
    return round(gross_profit / gross_loss, 2)

def calculate_expected_value(win_rate, avg_winner, avg_loser):
    """
    Calcular Expected Value (EV) por trade
    
    EV = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
    
    Args:
        win_rate: Porcentaje de trades ganadores (0-100)
        avg_winner: Ganancia promedio de trades ganadores
        avg_loser: Pérdida promedio de trades perdedores (positivo)
    
    Returns:
        Expected Value por trade
    """
    win_rate_decimal = win_rate / 100
    loss_rate_decimal = 1 - win_rate_decimal
    
    ev = (win_rate_decimal * avg_winner) - (loss_rate_decimal * abs(avg_loser))
    
    return round(ev, 2)

def calculate_sharpe_ratio(returns, risk_free_rate=0.02, periods_per_year=252):
    """
    Calcular Sharpe Ratio simplificado
    
    Args:
        returns: Serie de retornos diarios
        risk_free_rate: Tasa libre de riesgo anual
        periods_per_year: Períodos por año (252 para días hábiles)
    
    Returns:
        Sharpe Ratio anualizado
    """
    if len(returns) < 2:
        return 0
    
    excess_returns = returns - (risk_free_rate / periods_per_year)
    
    if excess_returns.std() == 0:
        return 0
    
    sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(periods_per_year)
    
    return round(sharpe, 2)

def calculate_max_drawdown(equity_curve):
    """
    Calcular Maximum Drawdown
    
    Args:
        equity_curve: Serie con valores del equity curve
    
    Returns:
        Máximo drawdown en porcentaje
    """
    if len(equity_curve) < 2:
        return 0
    
    # Calcular running maximum
    running_max = equity_curve.cummax()
    
    # Calcular drawdown
    drawdown = (equity_curve - running_max) / running_max
    
    # Máximo drawdown
    max_dd = drawdown.min()
    
    return round(max_dd * 100, 2)

def calculate_consecutive_stats(trades_df):
    """
    Calcular rachas consecutivas de ganadores y perdedores
    
    Args:
        trades_df: DataFrame con trades y columna 'pnl'
    
    Returns:
        Dict con max_consecutive_wins y max_consecutive_losses
    """
    if trades_df.empty or 'pnl' not in trades_df.columns:
        return {'max_consecutive_wins': 0, 'max_consecutive_losses': 0}
    
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0
    
    for pnl in trades_df['pnl']:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
    
    return {
        'max_consecutive_wins': max_wins,
        'max_consecutive_losses': max_losses
    }

def calculate_win_rate_by_setup(trades_df):
    """
    Calcular win rate por tipo de setup
    
    Args:
        trades_df: DataFrame con trades, columnas 'setup' y 'pnl'
    
    Returns:
        DataFrame con win rate por setup
    """
    if trades_df.empty or 'setup' not in trades_df.columns:
        return pd.DataFrame()
    
    setup_stats = trades_df.groupby('setup').agg({
        'pnl': ['count', lambda x: (x > 0).sum(), 'mean', 'sum']
    }).reset_index()
    
    setup_stats.columns = ['setup', 'total_trades', 'winning_trades', 'avg_pnl', 'total_pnl']
    setup_stats['win_rate'] = (setup_stats['winning_trades'] / setup_stats['total_trades'] * 100).round(2)
    
    return setup_stats.sort_values('win_rate', ascending=False)

def calculate_risk_reward_ratio(entry, stop_loss, target):
    """
    Calcular ratio riesgo/beneficio
    
    Args:
        entry: Precio de entrada
        stop_loss: Precio de stop loss
        target: Precio objetivo/take profit
    
    Returns:
        Ratio R:R (ej: 1:3 = 3.0)
    """
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    
    if risk == 0:
        return 0
    
    return round(reward / risk, 2)

def calculate_breakeven_win_rate(risk_reward_ratio):
    """
    Calcular win rate necesario para break-even dado un R:R
    
    Args:
        risk_reward_ratio: Ratio riesgo/beneficio
    
    Returns:
        Win rate mínimo necesario en porcentaje
    """
    if risk_reward_ratio <= 0:
        return 100
    
    # Fórmula: BE Win Rate = 1 / (1 + R:R)
    be_win_rate = 1 / (1 + risk_reward_ratio)
    
    return round(be_win_rate * 100, 2)

def calculate_kelly_criterion(win_rate, avg_winner, avg_loser):
    """
    Calcular fracción óptima de Kelly para sizing
    
    Args:
        win_rate: Porcentaje de trades ganadores (0-100)
        avg_winner: Ganancia promedio
        avg_loser: Pérdida promedio (positivo)
    
    Returns:
        Fracción óptima del capital a arriesgar
    """
    w = win_rate / 100
    l = 1 - w
    
    if avg_loser == 0:
        return 0
    
    b = avg_winner / avg_loser  # Odds
    
    kelly = (w * b - l) / b
    
    return max(0, min(kelly, 0.25))  # Limitar a 25% máximo

def calculate_daily_loss_limit(capital, max_daily_loss_percent=5):
    """
    Calcular límite de pérdida diaria
    
    Args:
        capital: Capital actual
        max_daily_loss_percent: Porcentaje máximo de pérdida diaria
    
    Returns:
        Monto máximo de pérdida diaria permitida
    """
    return capital * (max_daily_loss_percent / 100)

def should_stop_trading(daily_pnl, capital, max_loss_percent=5):
    """
    Determinar si se debe detener el trading por límite de pérdida
    
    Args:
        daily_pnl: P&L del día
        capital: Capital actual
        max_loss_percent: Porcentaje máximo de pérdida permitido
    
    Returns:
        Bool indicando si se debe detener
    """
    max_loss = calculate_daily_loss_limit(capital, max_loss_percent)
    
    return daily_pnl <= -max_loss

def validate_trade_plan(entry, stop_loss, target, setup, max_risk_amount):
    """
    Validar que un trade cumple con las reglas del plan
    
    Args:
        entry: Precio de entrada
        stop_loss: Precio de stop loss
        target: Precio objetivo
        setup: Setup utilizado
        max_risk_amount: Riesgo máximo permitido
    
    Returns:
        Dict con validación y mensajes
    """
    errors = []
    warnings = []
    
    # Validar stop loss
    if stop_loss >= entry:
        errors.append("Stop loss debe ser menor que el precio de entrada")
    
    # Validar target
    if target <= entry:
        warnings.append("Target está por debajo de la entrada. ¿Estás seguro?")
    
    # Calcular riesgo
    risk = entry - stop_loss
    
    # Validar R:R mínimo
    rr = calculate_risk_reward_ratio(entry, stop_loss, target)
    if rr < 2:
        warnings.append(f"Ratio R:R es {rr}:1. Se recomienda mínimo 2:1")
    
    # Validar riesgo máximo
    if risk > max_risk_amount:
        errors.append(f"Riesgo (${risk:.2f}) excede el máximo permitido (${max_risk_amount:.2f})")
    
    # Validar setup
    if not setup:
        errors.append("Debes seleccionar un setup válido")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'risk_reward': rr,
        'risk_amount': risk
    }