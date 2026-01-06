#!/usr/bin/env python3
"""
Script de diagnóstico mejorado para depurar el backtest - ANÁLISIS AVANZADO
Incluye gráficos, métricas detalladas y análisis profundo de resultados
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from typing import Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from backtesting import (
    BacktestEngine, BacktestConfig, BacktestDataLoader
)
from strategies.macdv_strategy import MACDVStrategy
from strategies.gap_go_strategy import GapGoStrategy
from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
from backtests.backtest_config import (
    BacktestConfigurations,
    StrategyConfigurations
)
from core.interfaces import Signal, Order, Position, SignalType, MarketData
from core.risk_manager import RiskManager

# Configurar matplotlib para mejor visualización
plt.style.use('seaborn-v0_8')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10

# Configuración de estrategias disponibles
AVAILABLE_STRATEGIES = {
    '1': {
        'name': 'MACD-V Strategy',
        'class': MACDVStrategy,
        'params_getter': StrategyConfigurations.get_macdv_default_5min,
        'timeframe': '5min'
    },
    '2': {
        'name': 'Gap & Go Strategy',
        'class': GapGoStrategy,
        'params_getter': StrategyConfigurations.get_gap_go_params,
        'timeframe': '1min'
    },
    '3': {
        'name': 'Optimized Gap & Go Strategy',
        'class': OptimizedGapGoStrategy,
        'params_getter': StrategyConfigurations.get_optimized_gap_go_params,
        'timeframe': '1min'
    }
}


def setup_logging():
    """Configurar logging detallado para diagnóstico"""
    logging.basicConfig(
        level=logging.INFO,  # Cambiar a INFO para menos ruido
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('debug_backtest.log')
        ]
    )


class EnhancedDiagnosticMonitor:
    def __init__(self):
        self.signals_generated = 0
        self.signals_validated = 0
        self.signals_rejected = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        
        # Nuevas métricas detalladas
        self.signal_details = []
        self.trade_details = []
        self.equity_curve = []
        self.drawdown_periods = []
        self.monthly_returns = {}
        self.symbol_performance = {}
        self.strategy_metrics = {}
        
    def reset(self):
        self.signals_generated = 0
        self.signals_validated = 0
        self.signals_rejected = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        self.signal_details.clear()
        self.trade_details.clear()
        self.equity_curve.clear()
        self.drawdown_periods.clear()
        self.monthly_returns.clear()
        self.symbol_performance.clear()
        self.strategy_metrics.clear()
        
    def record_signal(self, signal_info: Dict[str, Any]):
        """Registrar detalles de señal"""
        self.signal_details.append({
            'timestamp': signal_info.get('timestamp'),
            'symbol': signal_info.get('symbol'),
            'signal_type': signal_info.get('signal_type'),
            'price': signal_info.get('price'),
            'conditions_met': signal_info.get('conditions_met', 0),
            'strength': signal_info.get('strength', 0.0)
        })
        
    def record_trade(self, trade_info: Dict[str, Any]):
        """Registrar detalles de trade"""
        self.trade_details.append(trade_info)
        
    def calculate_advanced_metrics(self, results):
        """Calcular métricas avanzadas"""
        if not results or results.total_trades == 0:
            return {}
        
        trades_df = pd.DataFrame(self.trade_details) if self.trade_details else pd.DataFrame()
        
        metrics = {
            # Métricas básicas
            'total_return_pct': results.total_return_pct,
            'cagr': results.cagr,
            'volatility': results.volatility_annual,
            'sharpe_ratio': results.sharpe_ratio,
            'sortino_ratio': self._calculate_sortino_ratio(results),
            'max_drawdown_pct': results.max_drawdown_pct,
            'calmar_ratio': results.cagr / abs(results.max_drawdown_pct) if results.max_drawdown_pct != 0 else 0,
            
            # Métricas de trading
            'total_trades': results.total_trades,
            'win_rate': results.win_rate,
            'profit_factor': results.profit_factor,
            'average_trade': results.avg_trade_pnl,
            'best_trade': results.best_trade,
            'worst_trade': results.worst_trade,
            
            # Métricas avanzadas
            'expectancy': self._calculate_expectancy(trades_df),
            'recovery_factor': self._calculate_recovery_factor(results),
            'sterling_ratio': self._calculate_sterling_ratio(results),
            'trades_per_month': self._calculate_trades_per_month(results),
            'avg_time_in_trade': self._calculate_avg_time_in_trade(trades_df),
            'consecutive_wins': self._calculate_consecutive_wins(trades_df),
            'consecutive_losses': self._calculate_consecutive_losses(trades_df),
        }
        
        return metrics
    
    def _calculate_sortino_ratio(self, results):
        """Calcular Sortino Ratio"""
        try:
            if hasattr(results, 'daily_returns') and len(results.daily_returns) > 0:
                downside_returns = [r for r in results.daily_returns if r < 0]
                if downside_returns:
                    downside_deviation = np.std(downside_returns) * np.sqrt(252)
                    return (results.cagr - 0.02) / downside_deviation  # Asumiendo 2% risk-free rate
            return 0
        except:
            return 0
    
    def _calculate_expectancy(self, trades_df):
        """Calcular expectancy por trade"""
        if trades_df.empty or 'pnl' not in trades_df.columns:
            return 0
        
        wins = trades_df[trades_df['pnl'] > 0]['pnl']
        losses = trades_df[trades_df['pnl'] < 0]['pnl']
        
        if len(wins) == 0 or len(losses) == 0:
            return trades_df['pnl'].mean()
        
        win_rate = len(wins) / len(trades_df)
        avg_win = wins.mean()
        avg_loss = abs(losses.mean())
        
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    def _calculate_recovery_factor(self, results):
        """Calcular Recovery Factor"""
        if results.max_drawdown_pct == 0:
            return float('inf')
        return results.total_return_pct / abs(results.max_drawdown_pct)
    
    def _calculate_sterling_ratio(self, results):
        """Calcular Sterling Ratio"""
        if results.max_drawdown_pct == 0:
            return float('inf')
        return results.cagr / abs(results.max_drawdown_pct)
    
    def _calculate_trades_per_month(self, results):
        """Calcular trades por mes"""
        if hasattr(results, 'start_date') and hasattr(results, 'end_date'):
            months = (results.end_date - results.start_date).days / 30.44
            return results.total_trades / months if months > 0 else 0
        return 0
    
    def _calculate_avg_time_in_trade(self, trades_df):
        """Calcular tiempo promedio en trade"""
        if trades_df.empty or 'entry_time' not in trades_df.columns or 'exit_time' not in trades_df.columns:
            return 0
        
        try:
            trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
            trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
            durations = (trades_df['exit_time'] - trades_df['entry_time']).dt.total_seconds() / 3600
            return durations.mean()
        except:
            return 0
    
    def _calculate_consecutive_wins(self, trades_df):
        """Calcular máxima racha de wins consecutivos"""
        if trades_df.empty or 'pnl' not in trades_df.columns:
            return 0
        
        wins = (trades_df['pnl'] > 0).astype(int)
        max_consecutive = 0
        current_consecutive = 0
        
        for win in wins:
            if win:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
                
        return max_consecutive
    
    def _calculate_consecutive_losses(self, trades_df):
        """Calcular máxima racha de losses consecutivos"""
        if trades_df.empty or 'pnl' not in trades_df.columns:
            return 0
        
        losses = (trades_df['pnl'] < 0).astype(int)
        max_consecutive = 0
        current_consecutive = 0
        
        for loss in losses:
            if loss:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
                
        return max_consecutive
        
    def print_comprehensive_summary(self, results, strategy_name):
        """Imprimir resumen comprehensivo con métricas avanzadas"""
        print("\n" + "=" * 80)
        print(f"📊 ANÁLISIS COMPREHENSIVO - {strategy_name.upper()}")
        print("=" * 80)
        
        if not results:
            print("❌ No hay resultados para analizar")
            return
        
        # Calcular métricas avanzadas
        metrics = self.calculate_advanced_metrics(results)
        
        # Sección 1: Resumen Ejecutivo
        print(f"\n🎯 RESUMEN EJECUTIVO:")
        print("-" * 50)
        print(f"Capital Final:        ${results.final_capital:>10,.2f}")
        print(f"Retorno Total:        {results.total_return_pct:>10.2f}%")
        print(f"CAGR:                 {results.cagr:>10.2f}%")
        print(f"Sharpe Ratio:         {results.sharpe_ratio:>10.2f}")
        print(f"Max Drawdown:         {results.max_drawdown_pct:>10.2f}%")
        
        # Sección 2: Métricas de Risk-Adjusted Returns
        print(f"\n📈 MÉTRICAS DE RETORNO AJUSTADO POR RIESGO:")
        print("-" * 50)
        print(f"Sortino Ratio:        {metrics.get('sortino_ratio', 0):>10.2f}")
        print(f"Calmar Ratio:         {metrics.get('calmar_ratio', 0):>10.2f}")
        print(f"Sterling Ratio:       {metrics.get('sterling_ratio', 0):>10.2f}")
        print(f"Recovery Factor:      {metrics.get('recovery_factor', 0):>10.2f}")
        print(f"Volatilidad Anual:    {results.volatility_annual:>10.2f}%")
        
        # Sección 3: Métricas de Trading
        print(f"\n🎯 MÉTRICAS DE TRADING:")
        print("-" * 50)
        print(f"Total Trades:         {results.total_trades:>10}")
        print(f"Win Rate:             {results.win_rate:>10.2f}%")
        print(f"Profit Factor:        {results.profit_factor:>10.2f}")
        print(f"Expectancy/Trade:     ${metrics.get('expectancy', 0):>10.2f}")
        print(f"Trade Promedio:       ${results.avg_trade_pnl:>10.2f}")
        print(f"Mejor Trade:          ${results.best_trade:>10.2f}")
        print(f"Peor Trade:           ${results.worst_trade:>10.2f}")
        
        # Sección 4: Patrones de Trading
        print(f"\n🔍 PATRONES DE TRADING:")
        print("-" * 50)
        print(f"Trades/Mes:           {metrics.get('trades_per_month', 0):>10.1f}")
        print(f"Tiempo Promedio:      {metrics.get('avg_time_in_trade', 0):>10.1f}h")
        print(f"Máx Wins Consec:      {metrics.get('consecutive_wins', 0):>10}")
        print(f"Máx Losses Consec:    {metrics.get('consecutive_losses', 0):>10}")
        
        # Sección 5: Análisis de Señales
        print(f"\n🔔 ANÁLISIS DE SEÑALES:")
        print("-" * 50)
        print(f"Señales Generadas:    {self.signals_generated:>10}")
        print(f"Trades Ejecutados:    {self.trades_executed:>10}")
        print(f"Ratio Ejecución:      {(self.trades_executed/self.signals_generated*100) if self.signals_generated > 0 else 0:>10.1f}%")
        
        # Análisis específico por estrategia
        if 'Gap' in strategy_name:
            self._print_gap_specific_analysis()
        elif 'MACD' in strategy_name:
            self._print_macd_specific_analysis()
    
    def _print_gap_specific_analysis(self):
        """Análisis específico para Gap & Go"""
        print(f"\n🌅 ANÁLISIS ESPECÍFICO GAP & GO:")
        print("-" * 50)
        
        gap_signals = [s for s in self.signal_details if 'LONG' in str(s.get('signal_type', ''))]
        
        if gap_signals:
            strengths = [s.get('strength', 0) for s in gap_signals if s.get('strength')]
            conditions = [s.get('conditions_met', 0) for s in gap_signals if s.get('conditions_met')]
            
            print(f"Gaps Detectados:      {len(gap_signals):>10}")
            print(f"Strength Promedio:    {np.mean(strengths) if strengths else 0:>10.2f}")
            print(f"Condiciones Prom:     {np.mean(conditions) if conditions else 0:>10.1f}")
            
            # Análisis por símbolo
            symbols = {}
            for signal in gap_signals:
                symbol = signal.get('symbol')
                if symbol:
                    symbols[symbol] = symbols.get(symbol, 0) + 1
            
            print(f"\nGaps por símbolo:")
            for symbol, count in symbols.items():
                print(f"  {symbol:>6}: {count:>3} gaps")
    
    def _print_macd_specific_analysis(self):
        """Análisis específico para MACD-V"""
        print(f"\n📊 ANÁLISIS ESPECÍFICO MACD-V:")
        print("-" * 50)
        
        macd_signals = self.signal_details
        
        if macd_signals:
            print(f"Divergencias MACD:    {len(macd_signals):>10}")
            
            # Análisis por tipo de señal
            signal_types = {}
            for signal in macd_signals:
                sig_type = str(signal.get('signal_type', ''))
                signal_types[sig_type] = signal_types.get(sig_type, 0) + 1
            
            print(f"\nSeñales por tipo:")
            for sig_type, count in signal_types.items():
                print(f"  {sig_type:>10}: {count:>3}")


def select_strategy() -> tuple:
    """Permitir al usuario seleccionar la estrategia a debuggear"""
    print("\n📊 ESTRATEGIAS DISPONIBLES PARA DEBUG:")
    print("=" * 50)
    
    for key, strategy_info in AVAILABLE_STRATEGIES.items():
        print(f"{key}. {strategy_info['name']} (Timeframe: {strategy_info['timeframe']})")
    
    while True:
        choice = input("\n👉 Selecciona la estrategia a debuggear (1-3): ").strip()
        if choice in AVAILABLE_STRATEGIES:
            return AVAILABLE_STRATEGIES[choice]
        print("❌ Opción inválida. Intenta de nuevo.")


def find_symbol_files(symbol: str, data_path: str = "data") -> list:
    """Buscar archivos de datos para un símbolo específico"""
    data_dir = Path(data_path)
    
    patterns = [
        f"{symbol}*.csv",
        f"{symbol}*.parquet",
        f"*{symbol}*.csv",
        f"*{symbol}*.parquet"
    ]
    
    files = []
    for pattern in patterns:
        files.extend(list(data_dir.glob(pattern)))
    
    return [str(f) for f in files]


def normalize_timezone(df: pd.DataFrame, target_tz: str = None) -> pd.DataFrame:
    """Normaliza el timezone del DataFrame para evitar errores de comparación."""
    if df.empty:
        return df
    
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            return df
    
    if df.index.tz is None and target_tz is None:
        return df
    
    if df.index.tz is not None and target_tz is None:
        df.index = df.index.tz_localize(None)
        return df
    
    if df.index.tz is None and target_tz is not None:
        df.index = df.index.tz_localize(target_tz)
        return df
    
    if df.index.tz is not None and target_tz is not None:
        df.index = df.index.tz_convert(target_tz)
        return df
    
    return df


def load_symbol_data_directly(symbol: str, data_path: str = "data") -> pd.DataFrame:
    """Cargar datos directamente desde archivos sin usar BacktestDataLoader"""
    print(f"\n📈 Cargando datos para {symbol}...")
    
    files = find_symbol_files(symbol, data_path)
    
    if not files:
        print(f"❌ No se encontraron archivos para {symbol}")
        return pd.DataFrame()
    
    file_path = files[0]
    
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.parquet'):
            df = pd.read_parquet(file_path)
        else:
            print(f"❌ Formato no soportado: {file_path}")
            return pd.DataFrame()
        
        expected_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns.str.lower() for col in expected_columns):
            print(f"❌ Columnas faltantes en {file_path}")
            return pd.DataFrame()
        
        df.columns = df.columns.str.lower()
        
        column_mapping = {
            'datetime': 'timestamp',
            'date': 'timestamp',
            'time': 'timestamp'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        df = normalize_timezone(df, target_tz=None)
        
        print(f"✅ {symbol}: {len(df)} barras | {df.index[0]} a {df.index[-1]}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error cargando {file_path}: {e}")
        return pd.DataFrame()


def create_performance_plots(results, monitor, strategy_name, symbols):
    """Crear gráficos de performance detallados"""
    
    # Configurar el estilo de los gráficos
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # Crear figura con subplots
    fig = plt.figure(figsize=(20, 15))
    fig.suptitle(f'Análisis de Performance - {strategy_name}', fontsize=16, fontweight='bold')
    
    # 1. Equity Curve
    ax1 = plt.subplot(2, 3, 1)
    if hasattr(results, 'equity_curve') and len(results.equity_curve) > 0:
        equity_df = pd.DataFrame(results.equity_curve)
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        ax1.plot(equity_df['timestamp'], equity_df['total_value'], linewidth=2, color='blue')
        ax1.set_title('Curva de Equity', fontweight='bold')
        ax1.set_ylabel('Valor del Portfolio ($)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    else:
        ax1.text(0.5, 0.5, 'No hay datos de equity curve', 
                horizontalalignment='center', verticalalignment='center', transform=ax1.transAxes)
        ax1.set_title('Curva de Equity', fontweight='bold')
    
    # 2. Drawdown
    ax2 = plt.subplot(2, 3, 2)
    if hasattr(results, 'drawdown_series') and len(results.drawdown_series) > 0:
        dd_df = pd.DataFrame(results.drawdown_series)
        dd_df['timestamp'] = pd.to_datetime(dd_df['timestamp'])
        ax2.fill_between(dd_df['timestamp'], dd_df['drawdown_pct'], 0, 
                        color='red', alpha=0.7, label='Drawdown')
        ax2.set_title('Drawdown (%)', fontweight='bold')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    else:
        ax2.text(0.5, 0.5, 'No hay datos de drawdown', 
                horizontalalignment='center', verticalalignment='center', transform=ax2.transAxes)
        ax2.set_title('Drawdown (%)', fontweight='bold')
    
    # 3. Trade Distribution
    ax3 = plt.subplot(2, 3, 3)
    if monitor.trade_details:
        trade_pnls = [trade.get('pnl', 0) for trade in monitor.trade_details if trade.get('pnl') is not None]
        if trade_pnls:
            ax3.hist(trade_pnls, bins=min(20, len(trade_pnls)), alpha=0.7, color='green', edgecolor='black')
            ax3.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break-even')
            ax3.set_title('Distribución de P&L por Trade', fontweight='bold')
            ax3.set_xlabel('P&L ($)')
            ax3.set_ylabel('Frecuencia')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
    else:
        ax3.text(0.5, 0.5, 'No hay datos de trades', 
                horizontalalignment='center', verticalalignment='center', transform=ax3.transAxes)
        ax3.set_title('Distribución de P&L por Trade', fontweight='bold')
    
    # 4. Performance by Symbol
    ax4 = plt.subplot(2, 3, 4)
    if monitor.trade_details:
        symbol_pnl = {}
        for trade in monitor.trade_details:
            symbol = trade.get('symbol', 'Unknown')
            pnl = trade.get('pnl', 0)
            symbol_pnl[symbol] = symbol_pnl.get(symbol, 0) + pnl
        
        if symbol_pnl:
            symbols_list = list(symbol_pnl.keys())
            pnls = list(symbol_pnl.values())
            colors = ['green' if pnl >= 0 else 'red' for pnl in pnls]
            
            bars = ax4.bar(symbols_list, pnls, color=colors, alpha=0.7, edgecolor='black')
            ax4.set_title('P&L por Símbolo', fontweight='bold')
            ax4.set_ylabel('P&L Total ($)')
            ax4.grid(True, alpha=0.3, axis='y')
            
            # Añadir valores en las barras
            for bar, pnl in zip(bars, pnls):
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height + (5 if height >= 0 else -15),
                        f'${pnl:.0f}', ha='center', va='bottom' if height >= 0 else 'top', fontweight='bold')
    else:
        ax4.text(0.5, 0.5, 'No hay datos por símbolo', 
                horizontalalignment='center', verticalalignment='center', transform=ax4.transAxes)
        ax4.set_title('P&L por Símbolo', fontweight='bold')
    
    # 5. Signal Strength Analysis (específico para Gap & Go)
    ax5 = plt.subplot(2, 3, 5)
    if 'Gap' in strategy_name and monitor.signal_details:
        strengths = [s.get('strength', 0) for s in monitor.signal_details if s.get('strength') and s.get('strength') > 0]
        if strengths:
            ax5.hist(strengths, bins=min(15, len(strengths)), alpha=0.7, color='orange', edgecolor='black')
            ax5.set_title('Distribución de Signal Strength', fontweight='bold')
            ax5.set_xlabel('Signal Strength')
            ax5.set_ylabel('Frecuencia')
            ax5.grid(True, alpha=0.3)
            
            # Añadir línea de promedio
            avg_strength = np.mean(strengths)
            ax5.axvline(x=avg_strength, color='red', linestyle='--', linewidth=2, 
                       label=f'Promedio: {avg_strength:.2f}')
            ax5.legend()
    else:
        ax5.text(0.5, 0.5, 'No hay datos de signal strength', 
                horizontalalignment='center', verticalalignment='center', transform=ax5.transAxes)
        ax5.set_title('Distribución de Signal Strength', fontweight='bold')
    
    # 6. Monthly Returns Heatmap
    ax6 = plt.subplot(2, 3, 6)
    if hasattr(results, 'equity_curve') and len(results.equity_curve) > 0:
        try:
            equity_df = pd.DataFrame(results.equity_curve)
            equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
            equity_df['month'] = equity_df['timestamp'].dt.to_period('M')
            
            monthly_returns = equity_df.groupby('month').agg({
                'total_value': ['first', 'last']
            }).reset_index()
            
            monthly_returns.columns = ['month', 'start_value', 'end_value']
            monthly_returns['monthly_return'] = ((monthly_returns['end_value'] - monthly_returns['start_value']) / 
                                               monthly_returns['start_value']) * 100
            
            if len(monthly_returns) > 1:
                months = [str(m) for m in monthly_returns['month']]
                returns = monthly_returns['monthly_return'].values
                
                colors = ['green' if r >= 0 else 'red' for r in returns]
                bars = ax6.bar(months, returns, color=colors, alpha=0.7, edgecolor='black')
                
                ax6.set_title('Retornos Mensuales', fontweight='bold')
                ax6.set_ylabel('Retorno (%)')
                ax6.grid(True, alpha=0.3, axis='y')
                plt.setp(ax6.xaxis.get_majorticklabels(), rotation=45)
                
                # Añadir valores en las barras
                for bar, ret in zip(bars, returns):
                    height = bar.get_height()
                    ax6.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height >= 0 else -0.3),
                            f'{ret:.1f}%', ha='center', va='bottom' if height >= 0 else 'top', fontweight='bold')
            else:
                ax6.text(0.5, 0.5, 'Período muy corto\npara análisis mensual', 
                        horizontalalignment='center', verticalalignment='center', transform=ax6.transAxes)
                ax6.set_title('Retornos Mensuales', fontweight='bold')
        except Exception as e:
            ax6.text(0.5, 0.5, f'Error calculando\nretornos mensuales\n{str(e)[:30]}...', 
                    horizontalalignment='center', verticalalignment='center', transform=ax6.transAxes)
            ax6.set_title('Retornos Mensuales', fontweight='bold')
    else:
        ax6.text(0.5, 0.5, 'No hay datos de equity curve', 
                horizontalalignment='center', verticalalignment='center', transform=ax6.transAxes)
        ax6.set_title('Retornos Mensuales', fontweight='bold')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Guardar gráfico
    filename = f"performance_analysis_{strategy_name.replace(' ', '_').lower()}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n📊 Gráficos guardados en: {filename}")
    
    # Mostrar gráfico
    plt.show()
    
    return filename


def create_trade_analysis_chart(monitor, strategy_name):
    """Crear gráfico detallado de análisis de trades"""
    if not monitor.trade_details:
        print("⚠️  No hay trades para analizar")
        return
    
    trades_df = pd.DataFrame(monitor.trade_details)
    
    # Crear figura para análisis de trades
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'Análisis Detallado de Trades - {strategy_name}', fontsize=16, fontweight='bold')
    
    # 1. Trade P&L Timeline
    if 'entry_time' in trades_df.columns and 'pnl' in trades_df.columns:
        try:
            trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
            trades_df_sorted = trades_df.sort_values('entry_time')
            
            colors = ['green' if pnl >= 0 else 'red' for pnl in trades_df_sorted['pnl']]
            scatter = ax1.scatter(trades_df_sorted['entry_time'], trades_df_sorted['pnl'], 
                                c=colors, alpha=0.7, s=60, edgecolors='black')
            
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
            ax1.set_title('Timeline de P&L por Trade', fontweight='bold')
            ax1.set_xlabel('Fecha')
            ax1.set_ylabel('P&L ($)')
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
            # Añadir línea de tendencia
            if len(trades_df_sorted) > 1:
                x_numeric = mdates.date2num(trades_df_sorted['entry_time'])
                z = np.polyfit(x_numeric, trades_df_sorted['pnl'], 1)
                p = np.poly1d(z)
                ax1.plot(trades_df_sorted['entry_time'], p(x_numeric), "r--", alpha=0.8, linewidth=2, label='Tendencia')
                ax1.legend()
        except Exception as e:
            ax1.text(0.5, 0.5, f'Error en timeline\n{str(e)[:30]}...', 
                    horizontalalignment='center', verticalalignment='center', transform=ax1.transAxes)
            ax1.set_title('Timeline de P&L por Trade', fontweight='bold')
    
    # 2. Win/Loss Ratio Analysis
    wins = trades_df[trades_df['pnl'] > 0]['pnl']
    losses = trades_df[trades_df['pnl'] < 0]['pnl']
    
    win_loss_data = [len(wins), len(losses)]
    labels = [f'Wins ({len(wins)})', f'Losses ({len(losses)})']
    colors_pie = ['green', 'red']
    
    wedges, texts, autotexts = ax2.pie(win_loss_data, labels=labels, colors=colors_pie, autopct='%1.1f%%', 
                                      startangle=90, explode=(0.05, 0.05))
    ax2.set_title('Distribución Win/Loss', fontweight='bold')
    
    # Mejorar la apariencia del pie chart
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    
    # 3. Trade Duration Analysis
    if 'entry_time' in trades_df.columns and 'exit_time' in trades_df.columns:
        try:
            trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
            trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
            trades_df['duration_hours'] = (trades_df['exit_time'] - trades_df['entry_time']).dt.total_seconds() / 3600
            
            ax3.hist(trades_df['duration_hours'], bins=min(15, len(trades_df)), alpha=0.7, 
                    color='blue', edgecolor='black')
            ax3.set_title('Distribución de Duración de Trades', fontweight='bold')
            ax3.set_xlabel('Duración (horas)')
            ax3.set_ylabel('Frecuencia')
            ax3.grid(True, alpha=0.3)
            
            # Añadir línea de promedio
            avg_duration = trades_df['duration_hours'].mean()
            ax3.axvline(x=avg_duration, color='red', linestyle='--', linewidth=2, 
                       label=f'Promedio: {avg_duration:.1f}h')
            ax3.legend()
        except Exception as e:
            ax3.text(0.5, 0.5, f'Error calculando duración\n{str(e)[:30]}...', 
                    horizontalalignment='center', verticalalignment='center', transform=ax3.transAxes)
            ax3.set_title('Distribución de Duración de Trades', fontweight='bold')
    
    # 4. Cumulative P&L
    trades_df_sorted = trades_df.sort_values('entry_time') if 'entry_time' in trades_df.columns else trades_df
    cumulative_pnl = trades_df_sorted['pnl'].cumsum()
    
    ax4.plot(range(len(cumulative_pnl)), cumulative_pnl, linewidth=2, color='purple', marker='o', markersize=4)
    ax4.set_title('P&L Acumulado por Trade', fontweight='bold')
    ax4.set_xlabel('Número de Trade')
    ax4.set_ylabel('P&L Acumulado ($)')
    ax4.grid(True, alpha=0.3)
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    
    # Resaltar el mejor y peor momento
    max_pnl_idx = cumulative_pnl.idxmax()
    min_pnl_idx = cumulative_pnl.idxmin()
    
    max_pnl_trade_num = list(cumulative_pnl.index).index(max_pnl_idx)
    min_pnl_trade_num = list(cumulative_pnl.index).index(min_pnl_idx)
    
    ax4.scatter(max_pnl_trade_num, cumulative_pnl[max_pnl_idx], color='green', s=100, 
               marker='^', label=f'Máximo: ${cumulative_pnl[max_pnl_idx]:.2f}', zorder=5)
    ax4.scatter(min_pnl_trade_num, cumulative_pnl[min_pnl_idx], color='red', s=100, 
               marker='v', label=f'Mínimo: ${cumulative_pnl[min_pnl_idx]:.2f}', zorder=5)
    ax4.legend()
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Guardar gráfico
    filename = f"trade_analysis_{strategy_name.replace(' ', '_').lower()}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"📈 Análisis de trades guardado en: {filename}")
    
    plt.show()
    
    return filename


def export_detailed_results(results, monitor, strategy_name, symbols):
    """Exportar resultados detallados a Excel"""
    filename = f"detailed_backtest_results_{strategy_name.replace(' ', '_').lower()}.xlsx"
    
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Hoja 1: Resumen de métricas
            metrics = monitor.calculate_advanced_metrics(results)
            metrics_df = pd.DataFrame([metrics]).T
            metrics_df.columns = ['Valor']
            metrics_df.to_excel(writer, sheet_name='Métricas', index_label='Métrica')
            
            # Hoja 2: Trades detallados
            if monitor.trade_details:
                trades_df = pd.DataFrame(monitor.trade_details)
                trades_df.to_excel(writer, sheet_name='Trades', index=False)
            
            # Hoja 3: Señales detalladas
            if monitor.signal_details:
                signals_df = pd.DataFrame(monitor.signal_details)
                signals_df.to_excel(writer, sheet_name='Señales', index=False)
            
            # Hoja 4: Equity curve
            if hasattr(results, 'equity_curve') and results.equity_curve:
                equity_df = pd.DataFrame(results.equity_curve)
                equity_df.to_excel(writer, sheet_name='Equity_Curve', index=False)
            
            # Hoja 5: Drawdown series
            if hasattr(results, 'drawdown_series') and results.drawdown_series:
                dd_df = pd.DataFrame(results.drawdown_series)
                dd_df.to_excel(writer, sheet_name='Drawdown', index=False)
        
        print(f"📋 Resultados detallados exportados a: {filename}")
        return filename
        
    except Exception as e:
        print(f"⚠️  Error exportando a Excel: {e}")
        return None


def get_strategy_specific_config(strategy_info):
    """Obtener configuración específica para cada estrategia"""
    strategy_name = strategy_info['name']
    timeframe = strategy_info['timeframe']
    
    if timeframe == '1min':
        config = BacktestConfigurations.get_default_1min_config()
    else:
        config = BacktestConfigurations.get_default_1min_config()
        config.data_frequency = timeframe
    
    # Ajustar fechas según la estrategia
    config.start_date = datetime(2025, 4, 1)
    config.end_date = datetime(2025, 5, 1)
    config.simulation_mode = True
    
    print(f"📊 Configuración para {strategy_name}:")
    if 'Gap' in strategy_name:
        print(f"   • Incluye premarket y afterhours para detectar gaps")
        print(f"   • Timeframe: {timeframe} (alta frecuencia para entries precisos)")
    else:
        print(f"   • Enfocado en horario regular de mercado")
        print(f"   • Timeframe: {timeframe} (balanceado para señales)")
    
    return config


def adjust_strategy_params_for_debug(strategy_info):
    """Ajustar parámetros de estrategia para facilitar el debug"""
    params = strategy_info['params_getter']()
    strategy_name = strategy_info['name']
    
    print(f"\n🔧 Ajustando parámetros para debug de {strategy_name}:")
    
    if 'MACD' in strategy_name:
        params['volume_threshold'] = 0.5
        params['min_conditions'] = 1
        params['rsi_confirmation'] = False
        params['adx_confirmation'] = False
        params['bb_confirmation'] = False
        print("   • Volume threshold reducido")
        print("   • Confirmaciones adicionales desactivadas")
        print("   • Condiciones mínimas reducidas")
    
    elif 'Gap' in strategy_name:
        if 'gap_threshold' in params:
            params['gap_threshold'] = 0.02
        if 'volume_spike_threshold' in params:
            params['volume_spike_threshold'] = 1.5
        if 'min_price' in params:
            params['min_price'] = 1.0
        print("   • Gap threshold reducido a 2%")
        print("   • Volume spike menos restrictivo")
        print("   • Precio mínimo reducido")
    
    return params


async def debug_backtest():
    """Ejecutar backtest en modo diagnóstico con análisis avanzado"""
    print("\n" + "=" * 60)
    print("🔍 DIAGNÓSTICO AVANZADO DE BACKTEST - MULTI-ESTRATEGIA")
    print("=" * 60)
    
    # Seleccionar estrategia
    strategy_info = select_strategy()
    print(f"\n✅ Estrategia seleccionada: {strategy_info['name']}")
    
    monitor = EnhancedDiagnosticMonitor()
    
    # Verificar archivos de datos disponibles
    data_path = Path("data")
    if not data_path.exists():
        print("❌ Directorio 'data' no encontrado")
        return
    
    print(f"📁 Verificando archivos en: {data_path.absolute()}")
    
    csv_files = list(data_path.glob("*.csv"))
    parquet_files = list(data_path.glob("*.parquet"))
    
    print(f"✅ Archivos CSV: {len(csv_files)} | Parquet: {len(parquet_files)}")
    
    if not csv_files and not parquet_files:
        print("❌ No se encontraron archivos de datos")
        return
    
    # Extraer símbolos
    symbols = set()
    for file in csv_files + parquet_files:
        symbol = file.name.split('_')[0].split('.')[0]
        symbols.add(symbol)
    
    symbols = sorted(list(symbols))
    available_symbols = symbols[:2]
    print(f"\n🔬 Usando símbolos: {available_symbols}")
    
    # Configuración
    config = get_strategy_specific_config(strategy_info)
    strategy_params = adjust_strategy_params_for_debug(strategy_info)
    
    print(f"\n📊 Configuración final:")
    print(f"   Período: {config.start_date.strftime('%Y-%m-%d')} a {config.end_date.strftime('%Y-%m-%d')}")
    print(f"   Capital: ${config.initial_capital:,} | Timeframe: {strategy_info['timeframe']}")
    
    # Función de carga de datos
    def debug_data_loader(symbol, start_date, end_date):
        df = load_symbol_data_directly(symbol, "data")
        
        if df.empty:
            return df
        
        df = normalize_timezone(df, target_tz=None)
        
        if hasattr(start_date, 'tz') and start_date.tz is not None:
            start_date = start_date.replace(tzinfo=None)
        if hasattr(end_date, 'tz') and end_date.tz is not None:
            end_date = end_date.replace(tzinfo=None)
        
        try:
            mask = (df.index >= start_date) & (df.index <= end_date)
            filtered_df = df[mask]
            
            if filtered_df.empty:
                print(f"❌ No hay datos en rango para {symbol}, usando últimos 1000")
                filtered_df = df.tail(1000)
            else:
                print(f"✅ {symbol}: {len(filtered_df)} barras en rango")
            
            return filtered_df
            
        except Exception as e:
            print(f"❌ Error filtrando {symbol}: {e}")
            return df.tail(1000)
    
    # Crear estrategia con monitoreo avanzado
    strategy_class = strategy_info['class']
    
    class EnhancedDiagnosticStrategy(strategy_class):
        async def on_bar(self, bar: MarketData):
            signal = await super().on_bar(bar)
            if signal:
                signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                print(f"\n🔔 Señal: {bar.symbol} {signal_type} @ ${bar.close:.2f}")
                monitor.signals_generated += 1
                
                # Registrar detalles de la señal
                monitor.record_signal({
                    'timestamp': bar.timestamp,
                    'symbol': bar.symbol,
                    'signal_type': signal_type,
                    'price': bar.close,
                    'conditions_met': getattr(signal, 'conditions_met', 0),
                    'strength': getattr(signal, 'strength', 0.0)
                })
                
            return signal
    
    # Ejecutar backtest
    engine = BacktestEngine(config)
    strategy = EnhancedDiagnosticStrategy(strategy_params)
    
    engine.add_strategy(strategy)
    engine.set_data_loader(debug_data_loader)
    
    try:
        print(f"\n⚡ Ejecutando backtest avanzado...")
        results = await engine.run_backtest(available_symbols)
        
        # Extraer detalles de trades de los resultados
        if results and hasattr(results, 'trades') and results.trades:
            for trade in results.trades:
                monitor.record_trade({
                    'symbol': trade.symbol,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'pnl': trade.pnl,
                    'side': trade.side
                })
                monitor.trades_executed += 1
        
        # Mostrar análisis comprehensivo
        monitor.print_comprehensive_summary(results, strategy_info['name'])
        
        if results and results.total_trades > 0:
            print(f"\n🎨 Generando visualizaciones...")
            
            # Crear gráficos de performance
            performance_file = create_performance_plots(results, monitor, strategy_info['name'], available_symbols)
            
            # Crear análisis de trades
            trade_analysis_file = create_trade_analysis_chart(monitor, strategy_info['name'])
            
            # Exportar resultados detallados
            excel_file = export_detailed_results(results, monitor, strategy_info['name'], available_symbols)
            
            print(f"\n📁 ARCHIVOS GENERADOS:")
            print(f"   📊 Gráficos: {performance_file}")
            print(f"   📈 Trades: {trade_analysis_file}")
            if excel_file:
                print(f"   📋 Excel: {excel_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        setup_logging()
        print("\n🚀 Iniciando diagnóstico avanzado multi-estrategia...")
        asyncio.run(debug_backtest())
        
    except KeyboardInterrupt:
        print("\n\n👋 Diagnóstico interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)