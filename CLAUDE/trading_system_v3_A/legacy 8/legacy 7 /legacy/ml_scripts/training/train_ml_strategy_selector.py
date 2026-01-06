#!/usr/bin/env python3
"""
Train ML Strategy Selector - Entrenar el selector contextual de estrategias
Usa datos reales de database.db para entrenar Thompson Sampling
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
import sys
from typing import Dict, List, Tuple
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ml_strategy_selector import (
    ContextualBandit, 
    TickerContext,
    create_ml_strategy_selector
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyTrainer:
    """Entrena el ML Strategy Selector con datos históricos"""
    
    def __init__(self, db_path: str = "database_quality.db"):  # ✅ Usando base de datos de calidad
        self.db_path = db_path
        
        # ✅ EXACTAS 7 ESTRATEGIAS CORRECTAS (definitivas)
        self.strategy_mapping = {
            'orb': 'ORBStrategy',
            'gap_go': 'GapGoStrategy',
            'macdv_smallcaps': 'MACDVStrategy',
            'vwap_reclaim': 'VWAPReclaimStrategy', 
            'catalyst_momentum': 'CatalystMomentumStrategy',
            'eod_momentum': 'EndOfDayMomentumStrategy',
            'volume_breakout': 'VolumeBreakoutStrategy'
        }
        
        self.strategies = list(self.strategy_mapping.keys())
        
    def load_training_data(self) -> pd.DataFrame:
        """Carga datos históricos para entrenamiento"""
        logger.info("📊 Cargando datos históricos para entrenamiento de Strategy Selector...")
        
        conn = sqlite3.connect(self.db_path)
        
        # Query MEJORADA: Filtrar eventos de CALIDAD (evitar spikes destructivos)
        query = """
        SELECT 
            se.id_event,
            se.ticker,
            se.timestamp,
            sd.sector,
            sd.percent_var,
            sd.ratio_vol,
            sd.precio,
            sd.volumen,
            
            -- OHLC aggregated data
            COUNT(o.id_ohlc) as total_bars,
            AVG(o.volume) as avg_volume,
            MAX(o.volume) as max_volume,
            MIN(o.volume) as min_volume,
            
            -- Price action metrics MEJORADAS
            AVG(o.close) as avg_price,
            MAX(o.high) as day_high,
            MIN(o.low) as day_low,
            (MAX(o.high) - MIN(o.low)) / AVG(o.close) as daily_range_pct,
            
            -- FILTROS DE CALIDAD: detectar momentum sostenido vs spikes  
            (MAX(o.high) - MIN(o.close)) / MAX(o.high) as fade_from_high,  -- % bajada desde máximo
            
            -- Time features
            strftime('%H', se.timestamp) as hour,
            strftime('%w', se.timestamp) as day_of_week,
            
            -- Market data
            COALESCE(dtd.market_cap, sd.precio * AVG(o.volume) * 0.1) as market_cap,
            COALESCE(dtd.float_shares, AVG(o.volume) * 50) as float_shares,
            COALESCE(dtd.avg_volume, AVG(o.volume)) as daily_avg_volume
            
        FROM ScannerEvents se 
        JOIN ScannerData sd ON se.id_event = sd.id_event
        JOIN OHLCData o ON se.id_event = o.id_event  
        LEFT JOIN DailyTickerData dtd ON se.id_event = dtd.id_event
        WHERE sd.percent_var IS NOT NULL 
          AND sd.ratio_vol IS NOT NULL
          AND sd.ratio_vol BETWEEN 1.2 AND 8.0  -- Evitar ratios extremos (spikes artificiales)
          AND sd.percent_var BETWEEN 2.0 AND 25.0  -- Evitar movimientos extremos
          AND sd.precio BETWEEN 2.0 AND 30.0  -- Precios razonables para trading
          AND o.volume > 10000  -- Volumen mínimo real
        GROUP BY se.id_event, se.ticker, se.timestamp
        HAVING COUNT(o.id_ohlc) >= 60  -- Al menos 1 hora de datos
          AND daily_range_pct < 0.40  -- Evitar rangos extremos (>40%)
          AND fade_from_high < 0.60   -- Evitar crashes >60% desde máximo
        ORDER BY se.timestamp DESC
        LIMIT 1500  -- Menos eventos pero de mejor calidad
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"✅ Cargados {len(df)} eventos para entrenamiento")
        return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ingeniería de features para entrenamiento"""
        logger.info("🔧 Aplicando ingeniería de features...")
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['hour'].astype(int)
        df['day_of_week'] = df['day_of_week'].astype(int)
        
        # Time-based features
        df['time_of_day'] = df['hour'] / 24.0
        df['minutes_from_open'] = (df['hour'] - 9) * 60  # Assuming 9:30 AM open
        df['is_first_hour'] = df['minutes_from_open'] < 60
        df['is_last_hour'] = df['minutes_from_open'] > 330
        
        # Price and volume features
        df['current_price'] = df['precio']
        df['volume_ratio_current'] = df['ratio_vol']
        df['price_change_1h'] = df['percent_var'] / 100.0  # Convert to decimal
        df['price_change_4h'] = df['percent_var'] / 100.0  # Proxy
        
        # Technical indicators (simplified)
        df['rsi_14'] = np.clip(50 + (df['percent_var'] / 4), 10, 90)  # Proxy RSI
        df['volatility_10'] = df['daily_range_pct']
        df['volatility_50'] = df['daily_range_pct']
        
        # Volume features
        df['avg_volume_10'] = df['avg_volume']
        df['avg_volume_50'] = df['daily_avg_volume']
        df['volume_spike_frequency'] = np.where(df['ratio_vol'] > 2.0, 0.3, 0.1)
        
        # Market context
        df['market_trend'] = 0.0  # Neutral
        df['sector_performance'] = 0.0  # Neutral
        df['breakout_success_rate'] = 0.5  # Default
        df['mean_reversion_tendency'] = 0.5  # Default
        
        # Fill NaN values
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(0)
        df['sector'] = df['sector'].fillna('Technology')
        
        return df
    
    def assign_best_strategy(self, row) -> str:
        """
        Asigna la mejor estrategia basada en características del ticker
        Heurística inteligente basada en patrones de trading
        """
        hour = row['hour']
        percent_var = row['percent_var'] 
        ratio_vol = row['ratio_vol']
        price = row['precio']
        sector = row.get('sector', 'Unknown')
        
        # Morning Power (9:30-11:00)
        if 9 <= hour <= 11:
            if percent_var > 5 and ratio_vol > 2.0:
                return 'gap_go'  # Gap & Go para gaps grandes con volumen
            elif ratio_vol > 1.5:
                return 'orb'     # ORB para opening ranges
                
        # All-Day Core (11:00-15:00)  
        elif 11 <= hour <= 15:
            if sector in ['Technology', 'Healthcare', 'Biotechnology']:
                if ratio_vol >= 1.2:
                    return 'vwap_reclaim'  # VWAP para tech con volumen
                else:
                    return 'macdv'         # MACDV para momentum sostenido
            else:
                return 'vwap_smallcaps'    # VWAP smallcaps para otros sectores
        
        # Specialized (15:00-16:00)
        elif hour >= 15:
            if percent_var > 3:
                return 'eod_momentum'      # EOD momentum para movimientos fuertes
            else:
                return 'volume_breakout'   # Volume breakout para closes
        
        # Event-Driven (cualquier hora con condiciones específicas)
        if percent_var > 10 and ratio_vol > 4.0:
            return 'catalyst_momentum'     # Catalyst para eventos extremos
        
        if ratio_vol > 8.0:
            return 'explosive_volume'      # Explosive volume para picos extremos
        
        # Default fallback
        return 'macdv'
    
    def backtest_strategies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Backtest REAL con datos OHLC para obtener PnL reales por estrategia
        """
        logger.info("📈 Ejecutando backtesting REAL con datos OHLCData...")
        
        def get_ohlc_data(id_event: int) -> pd.DataFrame:
            """Obtiene datos OHLC para un evento específico"""
            conn = sqlite3.connect(self.db_path)
            
            query = """
            SELECT date, open, high, low, close, volume
            FROM OHLCData 
            WHERE id_event = ?
            ORDER BY date ASC
            """
            
            ohlc_df = pd.read_sql_query(query, conn, params=(id_event,))
            conn.close()
            
            if len(ohlc_df) > 0:
                ohlc_df['date'] = pd.to_datetime(ohlc_df['date'])
                ohlc_df.set_index('date', inplace=True)
            
            return ohlc_df
        
        def backtest_strategy(ohlc_data: pd.DataFrame, strategy: str, context: dict) -> float:
            """Backtest una estrategia específica con datos OHLC reales"""
            if len(ohlc_data) < 10:  # Necesitamos datos mínimos
                return 0.0
                
            entry_price = None
            exit_price = None
            max_profit = 0.0
            max_loss = 0.0
            
            # Estrategia-specific entry logic usando datos reales
            for i in range(5, len(ohlc_data)):  # Empezar después de los primeros 5 minutos
                current_bar = ohlc_data.iloc[i]
                prev_bars = ohlc_data.iloc[max(0, i-10):i]  # Últimas 10 barras
                
                if entry_price is None:  # Buscar entry
                    
                    # 🌅 MORNING POWER STRATEGIES
                    if strategy == 'gap_go':
                        # Gap & Go: EVITAR entry inmediato después del spike
                        if (9 <= context['hour'] <= 10 and i >= 15):  # Esperar 15 min después de open
                            # Buscar pullback + reclaim, NO el primer spike
                            recent_high = prev_bars['high'].tail(10).max()
                            if (current_bar['high'] > recent_high and
                                current_bar['volume'] > prev_bars['volume'].mean() * 1.5 and
                                context['percent_var'] > 3 and
                                context['ratio_vol'] > 1.5):
                                entry_price = current_bar['high'] + 0.01
                            
                    elif strategy == 'orb':
                        # ORB: Entry en breakout CONSOLIDADO del rango opening
                        if (9 <= context['hour'] <= 11 and i >= 40):  # Al menos 40 min de datos
                            orb_high = ohlc_data.iloc[5:35]['high'].max()  # Rango opening
                            orb_low = ohlc_data.iloc[5:35]['low'].min()
                            orb_range = (orb_high - orb_low) / orb_low
                            
                            # Solo si el ORB no es extremo (evitar spikes)
                            if (orb_range < 0.15 and  # Rango opening razonable (<15%)
                                current_bar['high'] > orb_high and
                                current_bar['volume'] > prev_bars['volume'].mean()):
                                entry_price = orb_high + 0.01
                    
                    # 🕐 ALL-DAY CORE STRATEGIES            
                    elif strategy == 'macdv_smallcaps':
                        # MACDV SmallCaps: Momentum sostenido, NO spikes
                        if (10 <= context['hour'] <= 15):
                            sma_5 = prev_bars['close'].rolling(5).mean().iloc[-1]
                            sma_10 = prev_bars['close'].rolling(10).mean().iloc[-1]
                            
                            # Trend confirmado + volumen sostenido
                            if (current_bar['close'] > sma_5 > sma_10 and
                                current_bar['volume'] > prev_bars['volume'].mean() and
                                context['ratio_vol'] > 1.2):
                                entry_price = current_bar['close']
                                
                    elif strategy == 'vwap_reclaim':
                        # VWAP Reclaim: Reclaim VWAP con confirmación
                        if (10 <= context['hour'] <= 15):
                            vwap = (prev_bars['close'] * prev_bars['volume']).sum() / prev_bars['volume'].sum()
                            prev_close = prev_bars['close'].iloc[-1]
                            
                            # Reclaim VWAP desde abajo
                            if (prev_close <= vwap and 
                                current_bar['close'] > vwap and
                                current_bar['volume'] > prev_bars['volume'].mean() * 1.3):
                                entry_price = current_bar['close']
                    
                    # 📰 EVENT-DRIVEN STRATEGIES
                    elif strategy == 'catalyst_momentum':
                        # Catalyst: SOLO eventos significativos con seguimiento
                        if (context['percent_var'] > 6 and 
                            context['ratio_vol'] > 2.5 and
                            i >= 20):  # Esperar confirmación, no entry inmediato
                            
                            # Confirmar que el momentum se mantiene
                            recent_closes = prev_bars['close'].tail(5)
                            if (current_bar['close'] > recent_closes.mean() and
                                current_bar['volume'] > prev_bars['volume'].tail(10).mean()):
                                entry_price = current_bar['close']
                    
                    # 🌆 SPECIALIZED STRATEGIES        
                    elif strategy == 'eod_momentum':
                        # EOD Momentum: Últimas 2 horas con confirmación
                        if (14 <= context['hour'] <= 15):
                            sma_3 = prev_bars['close'].rolling(3).mean().iloc[-1]
                            
                            if (current_bar['close'] > sma_3 and
                                current_bar['volume'] > prev_bars['volume'].mean() and
                                context['percent_var'] > 2):
                                entry_price = current_bar['close']
                                
                    elif strategy == 'volume_breakout':
                        # Volume Breakout: Breakout con volumen confirmado
                        if (context['ratio_vol'] > 2 and
                            current_bar['volume'] > prev_bars['volume'].mean() * 1.8):
                            
                            # Breakout de resistencia con volumen
                            resistance = prev_bars['high'].rolling(10).max().iloc[-1]
                            if (current_bar['high'] > resistance and
                                current_bar['volume'] > prev_bars['volume'].mean() * 1.5):
                                entry_price = current_bar['close']
                
                else:  # Ya tenemos entry, buscar exit
                    current_pnl_pct = (current_bar['close'] - entry_price) / entry_price
                    max_profit = max(max_profit, current_pnl_pct)
                    max_loss = min(max_loss, current_pnl_pct)
                    
                    # Exit conditions (stop loss o take profit)
                    should_exit = False
                    
                    # Universal stop loss
                    if current_pnl_pct <= -0.05:  # -5% stop loss
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    # Universal take profit  
                    elif current_pnl_pct >= 0.15:  # 15% take profit
                        should_exit = True  
                        exit_price = current_bar['close']
                        
                    # Time-based exit (EOD)
                    elif i >= len(ohlc_data) - 5:  # Últimos 5 minutos
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    # Strategy-specific exits MEJORADAS
                    elif strategy == 'gap_go' and context['hour'] >= 10.5:
                        # Gap&Go exit después de 10:30 AM (ventana más corta)
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'orb' and current_pnl_pct >= 0.12:
                        # ORB toma profits en 12%+ (target conservador)
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'macdv_smallcaps' and current_pnl_pct >= 0.10:
                        # MACDV SmallCaps target moderado 10%
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'vwap_reclaim' and current_pnl_pct >= 0.08:
                        # VWAP Reclaim target conservador 8%
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'catalyst_momentum' and current_pnl_pct >= 0.20:
                        # Catalyst target agresivo 20%
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'eod_momentum' and current_pnl_pct >= 0.06:
                        # EOD momentum target rápido 6%
                        should_exit = True
                        exit_price = current_bar['close']
                        
                    elif strategy == 'volume_breakout' and current_pnl_pct >= 0.12:
                        # Volume Breakout target moderado 12%
                        should_exit = True
                        exit_price = current_bar['close']
                    
                    if should_exit:
                        break
            
            # Calcular PnL final
            if entry_price and exit_price:
                pnl_pct = (exit_price - entry_price) / entry_price
                return pnl_pct
            else:
                return 0.0  # No trade
        
        # Aplicar backtesting a cada evento
        logger.info(f"🔄 Ejecutando backtesting en {len(df)} eventos...")
        
        for strategy in self.strategies:
            df[f'reward_{strategy}'] = 0.0
        
        for idx, row in df.iterrows():
            if idx % 100 == 0:  # Progress indicator
                logger.info(f"   Procesando evento {idx}/{len(df)}...")
                
            try:
                ohlc_data = get_ohlc_data(row['id_event'])
                
                if len(ohlc_data) >= 30:  # Mínimo 30 barras para backtest
                    context = {
                        'hour': row['hour'],
                        'percent_var': row['percent_var'],
                        'ratio_vol': row['ratio_vol'],
                        'price': row['precio']
                    }
                    
                    # Backtest cada estrategia
                    for strategy in self.strategies:
                        pnl = backtest_strategy(ohlc_data, strategy, context)
                        df.at[idx, f'reward_{strategy}'] = pnl
                        
            except Exception as e:
                logger.warning(f"Error backtesting evento {row['id_event']}: {e}")
                continue
        
        logger.info("✅ Backtesting completado")
        return df
    
    def train_model(self) -> ContextualBandit:
        """Entrena el modelo ML Strategy Selector"""
        logger.info("🧠 Entrenando ML Strategy Selector...")
        
        # Cargar y preparar datos
        df = self.load_training_data()
        df = self.engineer_features(df)
        df = self.backtest_strategies(df)  # BACKTESTING REAL con OHLC data
        
        # Crear modelo
        model = create_ml_strategy_selector(self.strategies)
        
        # Entrenar con datos simulados
        training_samples = 0
        
        for _, row in df.iterrows():
            try:
                # Crear contexto
                context = TickerContext(
                    symbol=row['ticker'],
                    current_price=row['current_price'],
                    avg_volume_10=row['avg_volume_10'],
                    avg_volume_50=row['avg_volume_50'],
                    volatility_10=row['volatility_10'],
                    volatility_50=row['volatility_50'],
                    price_change_1h=row['price_change_1h'],
                    price_change_4h=row['price_change_4h'],
                    rsi_14=row['rsi_14'],
                    volume_ratio_current=row['volume_ratio_current'],
                    volume_spike_frequency=row['volume_spike_frequency'],
                    hour_of_day=row['time_of_day'],
                    minutes_from_open=max(0, row['minutes_from_open']),
                    is_first_hour=row['is_first_hour'],
                    is_last_hour=row['is_last_hour'],
                    market_trend=row['market_trend'],
                    sector_performance=row['sector_performance'],
                    breakout_success_rate=row['breakout_success_rate'],
                    mean_reversion_tendency=row['mean_reversion_tendency']
                )
                
                # Entrenar con todas las estrategias y sus rewards
                for strategy in self.strategies:
                    reward = row[f'reward_{strategy}']
                    model.update_model(context, strategy, reward)
                    training_samples += 1
                    
            except Exception as e:
                logger.warning(f"Error procesando fila: {e}")
                continue
        
        logger.info(f"✅ Entrenamiento completado: {training_samples} samples")
        return model
    
    def save_model(self, model: ContextualBandit):
        """Guarda el modelo entrenado"""
        model_dir = "data/ml_models"
        os.makedirs(model_dir, exist_ok=True)
        
        model_path = os.path.join(model_dir, "strategy_selector.json")
        model.save_model(model_path)
        
        logger.info(f"💾 Modelo guardado en: {model_path}")

def main():
    """Función principal de entrenamiento"""
    print("🧠 ENTRENAMIENTO ML STRATEGY SELECTOR")
    print("=" * 60)
    
    trainer = StrategyTrainer()
    
    print(f"📋 Estrategias a entrenar: {len(trainer.strategies)}")
    for i, strategy in enumerate(trainer.strategies, 1):
        mapped_name = trainer.strategy_mapping.get(strategy, strategy)
        print(f"  {i:2d}. {strategy:20} -> {mapped_name}")
    
    print("\n🎯 Iniciando entrenamiento...")
    
    try:
        # Entrenar modelo
        model = trainer.train_model()
        
        # Guardar modelo
        trainer.save_model(model)
        
        # Estadísticas finales
        print("\n📊 ESTADÍSTICAS DE ENTRENAMIENTO:")
        print("=" * 40)
        
        for strategy in trainer.strategies:
            stats = model.strategy_stats[strategy]
            print(f"{strategy:20} | Trades: {stats.total_trades:4d} | "
                  f"Avg PnL: {stats.avg_pnl:+.3f} | "
                  f"Win Rate: {stats.win_rate:.1%}")
        
        print("\n✅ Entrenamiento completado exitosamente")
        print("🚀 El modelo está listo para selección inteligente de estrategias")
        
    except Exception as e:
        logger.error(f"❌ Error durante entrenamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()