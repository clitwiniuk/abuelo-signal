#!/usr/bin/env python3
"""
Generic_01 Edge Analysis
Analiza si generic_01 tiene un edge real usando train/test split
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

# Configuración
DB_PATH = 'trading_data.db'
WORKER_NAME = 'generic_01'

# Train/Test Split
TRAIN_START = '2025-11-10'
TRAIN_END = '2025-11-18'
TEST_START = '2025-11-20'
TEST_END = '2025-11-24'

def load_signal_events(start_date, end_date):
    """Carga signal_events para un período"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
    SELECT 
        signal_id,
        symbol,
        timestamp,
        entered,
        rejection_reason,
        entry_price,
        confidence,
        quality_score,
        ods_classification,
        forward_return_5m,
        forward_return_15m,
        forward_return_60m,
        forward_return_240m,
        mfe_percent,
        mae_percent
    FROM signal_events
    WHERE worker_name = ?
      AND DATE(timestamp) BETWEEN ? AND ?
    ORDER BY timestamp
    """
    
    df = pd.read_sql_query(query, conn, params=(WORKER_NAME, start_date, end_date))
    conn.close()
    
    return df

def analyze_edge(df, period_name):
    """Analiza el edge de un conjunto de datos"""
    print(f"\n{'='*80}")
    print(f"📊 ANÁLISIS DE EDGE - {period_name}")
    print(f"{'='*80}\n")
    
    total_signals = len(df)
    entered_signals = df[df['entered'] == 1]
    rejected_signals = df[df['entered'] == 0]
    
    print(f"Total Signals: {total_signals}")
    print(f"Entered: {len(entered_signals)} ({len(entered_signals)/total_signals*100:.1f}%)")
    print(f"Rejected: {len(rejected_signals)} ({len(rejected_signals)/total_signals*100:.1f}%)")
    
    if len(entered_signals) == 0:
        print("\n⚠️  No hay señales con entrada - no se puede analizar edge")
        return None
    
    # Análisis de Forward Returns
    print(f"\n📈 Forward Returns (Entered Signals Only)")
    print(f"{'='*80}")
    
    for timeframe in ['5m', '15m', '60m', '240m']:
        col = f'forward_return_{timeframe}'
        returns = entered_signals[col].dropna()
        
        if len(returns) == 0:
            print(f"\n{timeframe}: No data available")
            continue
            
        print(f"\n{timeframe.upper()} Returns:")
        print(f"  Count: {len(returns)}")
        print(f"  Mean: {returns.mean():.2f}%")
        print(f"  Median: {returns.median():.2f}%")
        print(f"  Std: {returns.std():.2f}%")
        print(f"  Win Rate: {(returns > 0).sum() / len(returns) * 100:.1f}%")
        print(f"  P25: {returns.quantile(0.25):.2f}%")
        print(f"  P75: {returns.quantile(0.75):.2f}%")
        print(f"  Max: {returns.max():.2f}%")
        print(f"  Min: {returns.min():.2f}%")
    
    # MFE/MAE Analysis
    print(f"\n📊 MFE/MAE Analysis")
    print(f"{'='*80}")
    
    mfe = entered_signals['mfe_percent'].dropna()
    mae = entered_signals['mae_percent'].dropna()
    
    if len(mfe) > 0:
        print(f"\nMFE (Max Favorable Excursion):")
        print(f"  Mean: {mfe.mean():.2f}%")
        print(f"  Median: {mfe.median():.2f}%")
        print(f"  P75: {mfe.quantile(0.75):.2f}%")
        
    if len(mae) > 0:
        print(f"\nMAE (Max Adverse Excursion):")
        print(f"  Mean: {mae.mean():.2f}%")
        print(f"  Median: {mae.median():.2f}%")
        print(f"  P25: {mae.quantile(0.25):.2f}%")
    
    # Confidence Analysis
    print(f"\n🎯 Confidence vs Performance")
    print(f"{'='*80}")
    
    conf_bins = pd.cut(entered_signals['confidence'], bins=[0, 60, 80, 100], 
                       labels=['Low (0-60)', 'Med (60-80)', 'High (80-100)'])
    
    for bin_name in ['Low (0-60)', 'Med (60-80)', 'High (80-100)']:
        bin_data = entered_signals[conf_bins == bin_name]
        if len(bin_data) == 0:
            continue
            
        returns_60m = bin_data['forward_return_60m'].dropna()
        if len(returns_60m) > 0:
            print(f"\n{bin_name}:")
            print(f"  Count: {len(bin_data)}")
            print(f"  Avg Confidence: {bin_data['confidence'].mean():.1f}")
            print(f"  60m Return: {returns_60m.mean():.2f}% (median: {returns_60m.median():.2f}%)")
            print(f"  Win Rate: {(returns_60m > 0).sum() / len(returns_60m) * 100:.1f}%")
    
    # Top Symbols
    print(f"\n🔝 Top Symbols by Entry Count")
    print(f"{'='*80}")
    
    top_symbols = entered_signals.groupby('symbol').agg({
        'signal_id': 'count',
        'forward_return_60m': 'mean',
        'confidence': 'mean'
    }).sort_values('signal_id', ascending=False).head(10)
    
    top_symbols.columns = ['Entries', 'Avg_60m_Return', 'Avg_Confidence']
    print(top_symbols.to_string())
    
    # Edge Calculation
    print(f"\n💰 EDGE CALCULATION")
    print(f"{'='*80}")
    
    returns_60m = entered_signals['forward_return_60m'].dropna()
    if len(returns_60m) > 0:
        mean_return = returns_60m.mean()
        win_rate = (returns_60m > 0).sum() / len(returns_60m)
        avg_win = returns_60m[returns_60m > 0].mean() if (returns_60m > 0).any() else 0
        avg_loss = returns_60m[returns_60m < 0].mean() if (returns_60m < 0).any() else 0
        
        print(f"\nBased on 60m Forward Returns:")
        print(f"  Sample Size: {len(returns_60m)}")
        print(f"  Mean Return: {mean_return:.2f}%")
        print(f"  Win Rate: {win_rate*100:.1f}%")
        print(f"  Avg Win: {avg_win:.2f}%")
        print(f"  Avg Loss: {avg_loss:.2f}%")
        
        if avg_loss != 0:
            profit_factor = abs(avg_win * win_rate / (avg_loss * (1 - win_rate)))
            print(f"  Profit Factor: {profit_factor:.2f}")
        
        # Statistical Significance (t-test)
        from scipy import stats
        t_stat, p_value = stats.ttest_1samp(returns_60m, 0)
        print(f"\n  T-statistic: {t_stat:.2f}")
        print(f"  P-value: {p_value:.4f}")
        
        if p_value < 0.05:
            if mean_return > 0:
                print(f"  ✅ EDGE ESTADÍSTICAMENTE SIGNIFICATIVO (p < 0.05)")
            else:
                print(f"  ❌ EDGE NEGATIVO ESTADÍSTICAMENTE SIGNIFICATIVO (p < 0.05)")
        else:
            print(f"  ⚠️  NO HAY EDGE ESTADÍSTICAMENTE SIGNIFICATIVO (p >= 0.05)")
            print(f"      Los resultados podrían ser AZAR")
    
    return {
        'total_signals': total_signals,
        'entered': len(entered_signals),
        'entry_rate': len(entered_signals) / total_signals if total_signals > 0 else 0,
        'mean_return_60m': returns_60m.mean() if len(returns_60m) > 0 else None,
        'win_rate': win_rate if len(returns_60m) > 0 else None,
        'p_value': p_value if len(returns_60m) > 0 else None
    }

def main():
    print(f"\n{'='*80}")
    print(f"🔬 GENERIC_01 EDGE ANALYSIS")
    print(f"{'='*80}\n")
    print(f"Worker: {WORKER_NAME}")
    print(f"Train Period: {TRAIN_START} to {TRAIN_END}")
    print(f"Test Period: {TEST_START} to {TEST_END}")
    
    # Load data
    print(f"\n📥 Loading data...")
    train_df = load_signal_events(TRAIN_START, TRAIN_END)
    test_df = load_signal_events(TEST_START, TEST_END)
    
    print(f"Train: {len(train_df)} signals")
    print(f"Test: {len(test_df)} signals")
    
    # Analyze train period
    train_results = analyze_edge(train_df, "TRAIN PERIOD")
    
    # Analyze test period
    test_results = analyze_edge(test_df, "TEST PERIOD")
    
    # Compare
    if train_results and test_results:
        print(f"\n{'='*80}")
        print(f"📊 TRAIN vs TEST COMPARISON")
        print(f"{'='*80}\n")
        
        print(f"Entry Rate:")
        print(f"  Train: {train_results['entry_rate']*100:.2f}%")
        print(f"  Test: {test_results['entry_rate']*100:.2f}%")
        print(f"  Δ: {(test_results['entry_rate'] - train_results['entry_rate'])*100:.2f}%")
        
        if train_results['mean_return_60m'] and test_results['mean_return_60m']:
            print(f"\nMean 60m Return:")
            print(f"  Train: {train_results['mean_return_60m']:.2f}%")
            print(f"  Test: {test_results['mean_return_60m']:.2f}%")
            print(f"  Δ: {test_results['mean_return_60m'] - train_results['mean_return_60m']:.2f}%")
        
        if train_results['win_rate'] and test_results['win_rate']:
            print(f"\nWin Rate:")
            print(f"  Train: {train_results['win_rate']*100:.1f}%")
            print(f"  Test: {test_results['win_rate']*100:.1f}%")
            print(f"  Δ: {(test_results['win_rate'] - train_results['win_rate'])*100:.1f}%")
        
        # Verdict
        print(f"\n{'='*80}")
        print(f"🎯 VEREDICTO FINAL")
        print(f"{'='*80}\n")
        
        if train_results['p_value'] and train_results['p_value'] < 0.05:
            if train_results['mean_return_60m'] > 0:
                print(f"✅ TRAIN: Edge estadísticamente significativo")
                
                if test_results['mean_return_60m'] and test_results['mean_return_60m'] > 0:
                    print(f"✅ TEST: Edge se mantiene positivo")
                    print(f"\n🎉 CONCLUSIÓN: generic_01 tiene un EDGE REAL")
                    print(f"   - Consistente entre train y test")
                    print(f"   - No es azar")
                else:
                    print(f"⚠️  TEST: Edge no se mantiene")
                    print(f"\n⚠️  CONCLUSIÓN: Posible OVERFITTING")
                    print(f"   - Edge en train pero no en test")
                    print(f"   - Requiere más datos para confirmar")
            else:
                print(f"❌ TRAIN: Edge negativo")
                print(f"\n❌ CONCLUSIÓN: generic_01 NO tiene edge")
        else:
            print(f"⚠️  TRAIN: No hay edge estadísticamente significativo")
            print(f"\n⚠️  CONCLUSIÓN: Resultados indistinguibles de AZAR")
            print(f"   - Sample size insuficiente O")
            print(f"   - No hay patrón real")

if __name__ == '__main__':
    main()
