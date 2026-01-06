#!/usr/bin/env python3
"""
Análisis Detallado de POM - 2025-12-05

Investiga por qué buy_the_dip entró en POM en el sistema real
pero lo rechazó en el replay.
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def analyze_pom_trade():
    """Analiza el trade de POM en detalle"""
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS DETALLADO: POM @ 2025-12-05")
    print("="*80 + "\n")
    
    # Connect to database
    conn = sqlite3.connect('trading_data.db')
    
    # 1. Get trade details
    print("📊 TRADE REAL (buy_the_dip):")
    print("-" * 80)
    
    trade_query = """
    SELECT 
        symbol, strategy, worker_name,
        entry_time, entry_price, 
        exit_time, exit_price,
        pnl, duration_minutes,
        confidence, signal_strength,
        volume_ratio, gap_percentage
    FROM trades
    WHERE symbol = 'POM' AND date(entry_time) = '2025-12-05'
    """
    
    trade_df = pd.read_sql_query(trade_query, conn)
    
    if not trade_df.empty:
        trade = trade_df.iloc[0]
        print(f"Symbol: {trade['symbol']}")
        print(f"Strategy: {trade['strategy']}")
        print(f"Worker: {trade['worker_name']}")
        print(f"Entry Time: {trade['entry_time']}")
        print(f"Entry Price: ${trade['entry_price']:.2f}")
        print(f"Exit Time: {trade['exit_time']}")
        print(f"Exit Price: ${trade['exit_price']:.2f}")
        print(f"P&L: {trade['pnl']:.2f}%")
        print(f"Duration: {trade['duration_minutes']} minutes")
        print(f"Confidence: {trade['confidence']}")
        print(f"Signal Strength: {trade['signal_strength']}")
        print(f"Volume Ratio: {trade['volume_ratio']}")
        print(f"Gap %: {trade['gap_percentage']}")
    
    # 2. Get intraday bars
    print("\n\n📈 BARRAS INTRADAY:")
    print("-" * 80)
    
    bars_query = """
    SELECT 
        tib.bar_timestamp,
        tib.open_price,
        tib.high_price,
        tib.low_price,
        tib.close_price,
        tib.volume
    FROM trade_intraday_bars tib
    JOIN trades t ON tib.trade_id = t.trade_id
    WHERE t.symbol = 'POM' AND date(tib.bar_timestamp) = '2025-12-05'
    ORDER BY tib.bar_timestamp
    """
    
    bars_df = pd.read_sql_query(bars_query, conn)
    
    if not bars_df.empty:
        print(f"Total bars: {len(bars_df)}")
        print(f"First bar: {bars_df.iloc[0]['bar_timestamp']}")
        print(f"Last bar: {bars_df.iloc[-1]['bar_timestamp']}")
        
        # Calculate VWAP
        bars_df['typical_price'] = (bars_df['high_price'] + bars_df['low_price'] + bars_df['close_price']) / 3
        bars_df['tp_volume'] = bars_df['typical_price'] * bars_df['volume']
        bars_df['cum_tp_volume'] = bars_df['tp_volume'].cumsum()
        bars_df['cum_volume'] = bars_df['volume'].cumsum()
        bars_df['vwap'] = bars_df['cum_tp_volume'] / bars_df['cum_volume'].replace(0, 1)
        
        # Find entry bar
        entry_time = pd.to_datetime(trade['entry_time'])
        entry_bar_idx = bars_df[bars_df['bar_timestamp'] <= str(entry_time)].index[-1] if len(bars_df[bars_df['bar_timestamp'] <= str(entry_time)]) > 0 else 0
        
        print(f"\n🎯 CONDICIONES EN EL MOMENTO DE ENTRADA ({entry_time}):")
        print("-" * 80)
        
        if entry_bar_idx >= 0:
            entry_bar = bars_df.iloc[entry_bar_idx]
            print(f"Bar Time: {entry_bar['bar_timestamp']}")
            print(f"Open: ${entry_bar['open_price']:.2f}")
            print(f"High: ${entry_bar['high_price']:.2f}")
            print(f"Low: ${entry_bar['low_price']:.2f}")
            print(f"Close: ${entry_bar['close_price']:.2f}")
            print(f"Volume: {entry_bar['volume']:,}")
            print(f"VWAP: ${entry_bar['vwap']:.2f}")
            
            # Price vs VWAP
            price_vs_vwap = ((entry_bar['close_price'] - entry_bar['vwap']) / entry_bar['vwap']) * 100
            print(f"Price vs VWAP: {price_vs_vwap:+.2f}%")
            
            # Calculate VWAP slope (last 10 bars)
            if entry_bar_idx >= 10:
                recent_bars = bars_df.iloc[entry_bar_idx-10:entry_bar_idx+1]
                vwap_change = recent_bars['vwap'].iloc[-1] - recent_bars['vwap'].iloc[0]
                vwap_slope = (vwap_change / recent_bars['vwap'].iloc[0]) * 100
                print(f"VWAP Slope (10 bars): {vwap_slope:+.2f}%")
            
            # Calculate ATR (simplified - using high-low range)
            if entry_bar_idx >= 14:
                recent_bars = bars_df.iloc[entry_bar_idx-14:entry_bar_idx+1]
                recent_bars['range'] = recent_bars['high_price'] - recent_bars['low_price']
                atr = recent_bars['range'].mean()
                atr_pct = (atr / entry_bar['close_price']) * 100
                print(f"ATR (14 bars): ${atr:.2f} ({atr_pct:.2f}%)")
            
            # Find recent high
            if entry_bar_idx >= 20:
                recent_bars = bars_df.iloc[entry_bar_idx-20:entry_bar_idx+1]
                recent_high = recent_bars['high_price'].max()
                dip_from_high = ((entry_bar['close_price'] - recent_high) / recent_high) * 100
                print(f"Recent High (20 bars): ${recent_high:.2f}")
                print(f"Dip from High: {dip_from_high:+.2f}%")
        
        # Show bars around entry time
        print(f"\n📊 BARRAS ALREDEDOR DE LA ENTRADA:")
        print("-" * 80)
        
        # Show 5 bars before and after entry
        start_idx = max(0, entry_bar_idx - 5)
        end_idx = min(len(bars_df), entry_bar_idx + 6)
        
        context_bars = bars_df.iloc[start_idx:end_idx].copy()
        context_bars['price_vs_vwap'] = ((context_bars['close_price'] - context_bars['vwap']) / context_bars['vwap'] * 100).round(2)
        
        print(context_bars[['bar_timestamp', 'close_price', 'volume', 'vwap', 'price_vs_vwap']].to_string(index=False))
        
        # Highlight entry bar
        if entry_bar_idx >= start_idx and entry_bar_idx < end_idx:
            relative_idx = entry_bar_idx - start_idx
            print(f"\n{'':>19}{'↑ ENTRY BAR':^50}")
    
    # 3. Check OHLC snapshot
    print("\n\n📸 OHLC SNAPSHOT:")
    print("-" * 80)
    
    snapshot_query = """
    SELECT 
        symbol, trading_date,
        day_open, day_high, day_low, day_close,
        entry_time, entry_price,
        exit_time, exit_price,
        premarket_high, gap_percent, market_open_price
    FROM trade_ohlc_snapshots
    WHERE symbol = 'POM' AND date(entry_time) = '2025-12-05'
    """
    
    snapshot_df = pd.read_sql_query(snapshot_query, conn)
    
    if not snapshot_df.empty:
        snapshot = snapshot_df.iloc[0]
        print(f"Day Open: ${snapshot['day_open']:.2f}")
        print(f"Day High: ${snapshot['day_high']:.2f}")
        print(f"Day Low: ${snapshot['day_low']:.2f}")
        print(f"Day Close: ${snapshot['day_close']:.2f}")
        
        # Handle potentially None values
        premarket_high = snapshot['premarket_high']
        if premarket_high is not None:
            print(f"Premarket High: ${premarket_high:.2f}")
        else:
            print(f"Premarket High: N/A")
        
        gap_percent = snapshot['gap_percent']
        if gap_percent is not None:
            print(f"Gap %: {gap_percent:.2f}%")
        else:
            print(f"Gap %: N/A")
        
        market_open_price = snapshot['market_open_price']
        if market_open_price is not None:
            print(f"Market Open Price: ${market_open_price:.2f}")
        else:
            print(f"Market Open Price: N/A")
    
    conn.close()
    
    # 4. Summary and hypothesis
    print("\n\n💡 HIPÓTESIS: ¿Por qué el replay rechazó POM?")
    print("="*80)
    print("""
Posibles razones:

1. **Timing exacto**: El sistema real puede haber evaluado POM en un momento
   específico donde las condiciones eran favorables, pero el replay evalúa
   en cada barra, y la mayoría no cumplía los criterios.

2. **Indicadores faltantes**: El replay calcula VWAP on-the-fly, pero puede
   que falten otros indicadores como RSI que el worker necesita.

3. **Configuración diferente**: Los parámetros del worker pueden haber cambiado
   desde el 5 de diciembre.

4. **Contexto de mercado**: El worker puede usar información adicional
   (como noticias, catalizadores, o datos de otros símbolos) que no está
   disponible en el replay.

5. **Anti-overtrading**: Si el worker ya había "considerado" POM antes
   en el día (aunque no entrara), puede haberlo marcado como "ya evaluado".

RECOMENDACIÓN: Ejecutar el replay con logs DEBUG completos para ver
exactamente qué filtros están rechazando POM en cada barra.
    """)
    
    print("="*80 + "\n")


if __name__ == '__main__':
    analyze_pom_trade()
