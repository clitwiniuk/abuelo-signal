#!/usr/bin/env python3
"""
Calcular Strategy Outcomes - Backtesting simulado para eventos históricos
Ubicación: scripts/maintenance/ (estructura organizada)

Este script calcula qué estrategias habrían sido exitosas en cada evento scanner
usando los datos OHLC disponibles para generar outcomes de entrenamiento ML.
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StrategyOutcomeCalculator:
    """Calculador de outcomes de estrategias usando backtesting"""
    
    def __init__(self, db_path="database_quality.db"):
        self.db_path = db_path
        self.strategies = [
            'orb',  # ORBStrategy
            'gap_go',  # GapGoStrategy  
            'macdv_smallcaps',  # MACDVStrategy
            'vwap_smallcaps',  # VWAPSmallcapsStrategy
            'catalyst_momentum',  # CatalystMomentumStrategy
            'eod_momentum',  # EndOfDayMomentumStrategy
            'explosive_volume'  # ExplosiveVolumeStrategy
        ]
        
        # Strategy-specific parameters (UPDATED - only active strategies)
        self.strategy_params = {
            'gap_go': {'profit_target': 0.03, 'stop_loss': 0.015, 'max_hold_minutes': 90},
            'gap_crap_reversal': {'profit_target': 0.025, 'stop_loss': 0.012, 'max_hold_minutes': 120},
            'daily_plays': {'profit_target': 0.035, 'stop_loss': 0.018, 'max_hold_minutes': 180},
            'first_day_bounce': {'profit_target': 0.025, 'stop_loss': 0.015, 'max_hold_minutes': 240},
            'macdv_smallcaps': {'profit_target': 0.025, 'stop_loss': 0.012, 'max_hold_minutes': 120},
            'red_to_green': {'profit_target': 0.02, 'stop_loss': 0.01, 'max_hold_minutes': 60}
        }

    def create_strategy_outcomes_table(self):
        """Crear tabla strategy_outcomes si no existe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_event INTEGER,
                strategy_name TEXT NOT NULL,
                success INTEGER NOT NULL, -- 0 or 1
                pnl_pct REAL,
                duration_minutes INTEGER,
                exit_reason TEXT, -- 'profit', 'stop', 'time', 'manual'
                volume_requirement_used REAL,
                entry_price REAL,
                exit_price REAL,
                max_pnl_reached REAL,
                min_pnl_reached REAL,
                timestamp_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_event) REFERENCES ScannerEvents(id_event)
            )
        """)
        
        # Crear índice para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_outcomes_event 
            ON strategy_outcomes(id_event)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_outcomes_strategy 
            ON strategy_outcomes(strategy_name)
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ Tabla strategy_outcomes creada/verificada")

    def get_scanner_events(self):
        """Obtener eventos scanner con datos completos"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT se.id_event, se.ticker, se.timestamp,
               sd.percent_var, sd.ratio_vol, sd.precio, sd.volumen, sd.sector
        FROM ScannerEvents se
        JOIN ScannerData sd ON se.id_event = sd.id_event
        WHERE sd.percent_var IS NOT NULL 
          AND sd.ratio_vol IS NOT NULL 
          AND sd.precio IS NOT NULL
        ORDER BY se.timestamp DESC
        """
        
        events_df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"📊 Eventos scanner encontrados: {len(events_df)}")
        return events_df

    def get_ohlc_data_for_event(self, id_event, ticker, event_timestamp):
        """Obtener datos OHLC para un evento específico"""
        conn = sqlite3.connect(self.db_path)
        
        # Buscar datos OHLC del día del evento y siguientes días
        event_date = pd.to_datetime(event_timestamp).date()
        end_date = event_date + timedelta(days=5)  # 5 días de datos post-evento
        
        query = """
        SELECT date, open, high, low, close, volume
        FROM OHLCData
        WHERE id_event = ? 
          AND date >= ? 
          AND date <= ?
        ORDER BY date ASC
        """
        
        ohlc_df = pd.read_sql_query(query, conn, params=(id_event, event_date, end_date))
        conn.close()
        
        if len(ohlc_df) == 0:
            logger.warning(f"❌ No OHLC data para evento {id_event} ({ticker})")
            return None
            
        # Convertir date a datetime para cálculos
        ohlc_df['date'] = pd.to_datetime(ohlc_df['date'])
        return ohlc_df

    def calculate_strategy_outcome(self, strategy_name, ohlc_df, entry_price, event_timestamp):
        """Calcular outcome de una estrategia específica"""
        if ohlc_df is None or len(ohlc_df) == 0:
            return None
            
        params = self.strategy_params[strategy_name]
        profit_target = params['profit_target']
        stop_loss = params['stop_loss']
        max_hold_minutes = params['max_hold_minutes']
        
        # Precio objetivo y stop loss
        target_price = entry_price * (1 + profit_target)
        stop_price = entry_price * (1 - stop_loss)
        
        # Simulación minuto a minuto (aproximada usando OHLC diario)
        event_datetime = pd.to_datetime(event_timestamp)
        
        max_pnl = 0
        min_pnl = 0
        
        for idx, row in ohlc_df.iterrows():
            # Calcular tiempo transcurrido (aproximado)
            time_diff = (row['date'] - event_datetime).total_seconds() / 60
            
            if time_diff > max_hold_minutes:
                # Time exit
                exit_price = row['open']  # Asumimos exit al open del día
                pnl_pct = (exit_price - entry_price) / entry_price
                return {
                    'success': 1 if pnl_pct > 0 else 0,
                    'pnl_pct': pnl_pct,
                    'duration_minutes': int(time_diff),
                    'exit_reason': 'time',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'max_pnl_reached': max_pnl,
                    'min_pnl_reached': min_pnl
                }
            
            # Check si se alcanzó profit target (usando high del día)
            if row['high'] >= target_price:
                pnl_pct = profit_target
                return {
                    'success': 1,
                    'pnl_pct': pnl_pct,
                    'duration_minutes': int(time_diff),
                    'exit_reason': 'profit',
                    'entry_price': entry_price,
                    'exit_price': target_price,
                    'max_pnl_reached': pnl_pct,
                    'min_pnl_reached': min_pnl
                }
            
            # Check si se alcanzó stop loss (usando low del día)
            if row['low'] <= stop_price:
                pnl_pct = -stop_loss
                return {
                    'success': 0,
                    'pnl_pct': pnl_pct,
                    'duration_minutes': int(time_diff),
                    'exit_reason': 'stop',
                    'entry_price': entry_price,
                    'exit_price': stop_price,
                    'max_pnl_reached': max_pnl,
                    'min_pnl_reached': pnl_pct
                }
            
            # Actualizar max/min PnL alcanzados
            high_pnl = (row['high'] - entry_price) / entry_price
            low_pnl = (row['low'] - entry_price) / entry_price
            max_pnl = max(max_pnl, high_pnl)
            min_pnl = min(min_pnl, low_pnl)
        
        # Si llegamos aquí, se acabaron los datos - exit por tiempo
        last_row = ohlc_df.iloc[-1]
        exit_price = last_row['close']
        pnl_pct = (exit_price - entry_price) / entry_price
        
        return {
            'success': 1 if pnl_pct > 0 else 0,
            'pnl_pct': pnl_pct,
            'duration_minutes': max_hold_minutes,
            'exit_reason': 'time',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'max_pnl_reached': max_pnl,
            'min_pnl_reached': min_pnl
        }

    def calculate_volume_requirement(self, strategy_name, scanner_data):
        """Calcular volume requirement aproximado para la estrategia"""
        # Valores típicos basados en la estrategia
        base_requirements = {
            'orb': 100000,
            'gap_go': 150000,
            'macdv_smallcaps': 80000,
            'vwap_smallcaps': 120000,
            'catalyst_momentum': 200000,
            'eod_momentum': 60000,
            'explosive_volume': 300000
        }
        
        base_vol = base_requirements.get(strategy_name, 100000)
        
        # Ajustar basado en ratio_vol y precio
        ratio_vol = scanner_data.get('ratio_vol', 1.0)
        precio = scanner_data.get('precio', 10.0)
        
        # Mayor precio = mayor volume requirement
        price_multiplier = max(0.5, min(2.0, precio / 20.0))
        
        # Mayor ratio_vol = menor volume requirement (ya hay mucha actividad)
        vol_multiplier = max(0.3, min(1.5, 1.0 / max(1.0, ratio_vol * 0.5)))
        
        volume_requirement = base_vol * price_multiplier * vol_multiplier
        
        return volume_requirement

    def save_strategy_outcome(self, id_event, strategy_name, outcome, volume_requirement):
        """Guardar outcome en la base de datos"""
        if outcome is None:
            return False
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO strategy_outcomes 
            (id_event, strategy_name, success, pnl_pct, duration_minutes, exit_reason,
             volume_requirement_used, entry_price, exit_price, max_pnl_reached, min_pnl_reached)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_event, strategy_name, outcome['success'], outcome['pnl_pct'],
            outcome['duration_minutes'], outcome['exit_reason'], volume_requirement,
            outcome['entry_price'], outcome['exit_price'], 
            outcome['max_pnl_reached'], outcome['min_pnl_reached']
        ))
        
        conn.commit()
        conn.close()
        return True

    def process_all_events(self):
        """Procesar todos los eventos scanner"""
        logger.info("🚀 Iniciando cálculo de strategy outcomes...")
        
        # Crear tabla si no existe
        self.create_strategy_outcomes_table()
        
        # Verificar qué eventos ya fueron procesados
        conn = sqlite3.connect(self.db_path)
        processed_events = pd.read_sql_query("""
            SELECT DISTINCT id_event FROM strategy_outcomes
        """, conn)
        processed_event_ids = set(processed_events['id_event'].tolist())
        conn.close()
        
        # Obtener eventos para procesar
        events_df = self.get_scanner_events()
        
        # Filtrar eventos no procesados
        events_to_process = events_df[~events_df['id_event'].isin(processed_event_ids)]
        logger.info(f"📊 Eventos a procesar: {len(events_to_process)} (ya procesados: {len(processed_event_ids)})")
        
        total_outcomes = 0
        successful_outcomes = 0
        
        for idx, event in events_to_process.iterrows():
            id_event = event['id_event']
            ticker = event['ticker']
            timestamp = event['timestamp']
            
            logger.info(f"📈 Procesando evento {id_event}: {ticker} ({idx+1}/{len(events_to_process)})")
            
            # Obtener datos OHLC
            ohlc_df = self.get_ohlc_data_for_event(id_event, ticker, timestamp)
            
            if ohlc_df is None:
                logger.warning(f"⚠️ Sin datos OHLC para evento {id_event}")
                continue
            
            # Precio de entrada (precio del scanner)
            entry_price = float(event['precio'])
            
            # Datos del scanner para volume requirement
            scanner_data = {
                'ratio_vol': event['ratio_vol'],
                'precio': event['precio'],
                'percent_var': event['percent_var']
            }
            
            # Calcular outcome para cada estrategia
            for strategy_name in self.strategies:
                outcome = self.calculate_strategy_outcome(strategy_name, ohlc_df, entry_price, timestamp)
                volume_requirement = self.calculate_volume_requirement(strategy_name, scanner_data)
                
                if self.save_strategy_outcome(id_event, strategy_name, outcome, volume_requirement):
                    total_outcomes += 1
                    if outcome and outcome['success']:
                        successful_outcomes += 1
        
        success_rate = (successful_outcomes / max(1, total_outcomes)) * 100
        logger.info(f"✅ Procesamiento completado:")
        logger.info(f"   📊 Total outcomes calculados: {total_outcomes}")
        logger.info(f"   🎯 Outcomes exitosos: {successful_outcomes} ({success_rate:.1f}%)")
        logger.info(f"   💾 Guardados en strategy_outcomes table")

    def generate_summary_report(self):
        """Generar reporte resumen de outcomes"""
        conn = sqlite3.connect(self.db_path)
        
        # Summary por estrategia
        summary_query = """
        SELECT strategy_name,
               COUNT(*) as total_outcomes,
               SUM(success) as successful_outcomes,
               ROUND(AVG(success) * 100, 1) as success_rate_pct,
               ROUND(AVG(pnl_pct) * 100, 2) as avg_pnl_pct,
               ROUND(AVG(duration_minutes), 1) as avg_duration_min
        FROM strategy_outcomes
        GROUP BY strategy_name
        ORDER BY success_rate_pct DESC
        """
        
        summary_df = pd.read_sql_query(summary_query, conn)
        
        print("\n📊 REPORTE RESUMEN - STRATEGY OUTCOMES")
        print("=" * 70)
        
        for _, row in summary_df.iterrows():
            print(f"🎯 {row['strategy_name'].upper()}:")
            print(f"   📈 Success Rate: {row['success_rate_pct']}% ({row['successful_outcomes']}/{row['total_outcomes']})")
            print(f"   💰 Avg PnL: {row['avg_pnl_pct']}%")
            print(f"   ⏱️ Avg Duration: {row['avg_duration_min']} min")
            print()
        
        # Exit reasons
        exit_reasons_query = """
        SELECT exit_reason, COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM strategy_outcomes), 1) as percentage
        FROM strategy_outcomes
        GROUP BY exit_reason
        ORDER BY count DESC
        """
        
        exit_reasons_df = pd.read_sql_query(exit_reasons_query, conn)
        
        print("📊 EXIT REASONS:")
        for _, row in exit_reasons_df.iterrows():
            print(f"   {row['exit_reason']}: {row['count']} ({row['percentage']}%)")
        
        conn.close()

def main():
    """Función principal"""
    print("🎯 CALCULANDO STRATEGY OUTCOMES PARA ML TRAINING")
    print("=" * 60)
    
    calculator = StrategyOutcomeCalculator()
    
    try:
        # Procesar todos los eventos
        calculator.process_all_events()
        
        # Generar reporte
        calculator.generate_summary_report()
        
        print("\n" + "=" * 60)
        print("✅ Strategy outcomes calculados exitosamente")
        print("💡 Los datos están listos para entrenar ML Strategy Selector")
        
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {e}")
        raise

if __name__ == "__main__":
    main()