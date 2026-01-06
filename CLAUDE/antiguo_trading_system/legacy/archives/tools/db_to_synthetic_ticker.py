#!/usr/bin/env python3
"""
DB to Synthetic Ticker Generator
===============================

Basado en db_data_visualizer.py, este script conecta directamente a la base de datos
y combina todos los eventos de explosiones en tickers sintéticos secuenciales.

Características:
- Usa eventos reales de la BD sin modificar sus variaciones
- Combina explosiones una después de otra en secuencia temporal
- Control de rango de precios (0.2 - 10.0)
- Genera múltiples tickers (AAA.csv, AAB.csv, etc.) cuando se sale del rango
- Datos OHLC auténticos del scanner
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from typing import Dict, List, Any, Tuple, Optional

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class DBToSyntheticTickerGenerator:
    """Generador de tickers sintéticos desde base de datos"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
        # Configuración de generación
        self.config = {
            'min_ratio_vol': 2.0,         # Ratio mínimo muy permisivo para más eventos
            'min_percent_var': 0.5,       # Variación muy permisiva
            'min_price': 0.2,             # Precio mínimo permitido
            'max_price': 10.0,            # Precio máximo permitido
            'base_price': 5.0,            # Precio inicial
            'max_events': 100,            # Máximo eventos por ticker (50-100 como querías)
            'bars_per_event': 1,          # 1 barra OHLC por evento para unión secuencial
            'base_symbol': 'AAA',         # Símbolo base (AAA, AAB, AAC...)
            'total_events_limit': 2000    # Límite total más alto para buscar más eventos
        }
    
    def connect_to_database(self) -> bool:
        """Conectar a la base de datos"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            print(f"✅ Conectado a la base de datos: {os.path.basename(self.db_path)}")
            return True
        except Exception as e:
            print(f"❌ Error conectando a la base de datos: {e}")
            return False
    
    def get_all_explosion_events(self, limit: int = 1000) -> pd.DataFrame:
        """
        Obtener todos los eventos de explosiones ordenados cronológicamente
        
        Args:
            limit: Límite máximo de eventos
            
        Returns:
            DataFrame con eventos y sus datos OHLC
        """
        try:
            # Query modificada para priorizar EVENTOS ÚNICOS diferentes
            # en lugar de muchas barras del mismo evento
            query = """
            WITH EventSelection AS (
                SELECT DISTINCT se.id_event, se.ticker, se.timestamp as event_timestamp,
                       sd.ratio_vol, sd.percent_var, sd.precio, sd.volumen
                FROM ScannerEvents se
                JOIN ScannerData sd ON se.id_event = sd.id_event
                WHERE sd.ratio_vol >= ?
                    AND ABS(sd.percent_var) >= ?
                ORDER BY se.timestamp DESC
                LIMIT ?
            )
            SELECT 
                es.id_event,
                es.ticker,
                es.event_timestamp,
                es.ratio_vol,
                es.percent_var,
                es.precio,
                es.volumen,
                oh.date as bar_date,
                oh.open,
                oh.high,
                oh.low,
                oh.close,
                oh.volume as bar_volume
            FROM EventSelection es
            JOIN OHLCData oh ON es.id_event = oh.id_event
            WHERE oh.open > 0
                AND oh.high > 0
                AND oh.low > 0
                AND oh.close > 0
                AND oh.volume > 0
            ORDER BY es.event_timestamp DESC, oh.date
            """
            
            # Parámetros: min_ratio_vol, min_percent_var, limit_events
            # El limit es para eventos únicos, no barras totales
            max_unique_events = min(limit // 10, 200)  # Máximo 200 eventos únicos
            df = pd.read_sql_query(
                query, 
                self.connection, 
                params=[self.config['min_ratio_vol'], self.config['min_percent_var'], max_unique_events]
            )
            
            if df.empty:
                print(f"❌ No se encontraron eventos con ratio >= {self.config['min_ratio_vol']}x")
                return df
            
            # Convertir timestamps
            df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
            df['bar_date'] = pd.to_datetime(df['bar_date'])
            
            print(f"✅ Extraídos {len(df)} barras OHLC de eventos de explosión")
            print(f"   📊 Ratio promedio: {df['ratio_vol'].mean():.1f}x")
            print(f"   📈 Variación promedio: {df['percent_var'].abs().mean():.1f}%")
            print(f"   📅 Período: {df['event_timestamp'].min()} a {df['event_timestamp'].max()}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo eventos: {e}")
            return pd.DataFrame()
    
    def select_best_bars_per_event(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Seleccionar la mejor barra de cada evento único para crear secuencia
        TOMAR MUCHOS EVENTOS ÚNICOS para llegar a 50-100 barras
        
        Args:
            df: DataFrame con todos los datos
            
        Returns:
            DataFrame con 1 barra por evento, hasta max_events barras totales
        """
        selected_bars = []
        unique_events = df['id_event'].unique()
        
        print(f"🎯 Eventos únicos disponibles: {len(unique_events)}")
        print(f"🎯 Objetivo: {self.config['max_events']} barras (1 por evento)")
        
        # Limitar a max_events para no sobrepasar
        events_to_use = unique_events[:self.config['max_events']]
        print(f"✅ Usando {len(events_to_use)} eventos únicos")
        
        # Tomar 1 barra de cada evento (la mejor)
        for event_id in events_to_use:
            event_data = df[df['id_event'] == event_id].copy()
            
            if not event_data.empty:
                # Calcular volatilidad de cada barra
                event_data['volatility'] = event_data['high'] - event_data['low']
                event_data['body_size'] = abs(event_data['close'] - event_data['open'])
                
                # Tomar solo la mejor barra de este evento
                best_bar = event_data.nlargest(1, 'body_size')
                selected_bars.append(best_bar)
        
        if selected_bars:
            result_df = pd.concat(selected_bars, ignore_index=True)
            # Re-ordenar cronológicamente por evento (no por fecha real)
            result_df = result_df.sort_values(['event_timestamp']).reset_index(drop=True)
            print(f"✅ Seleccionadas {len(result_df)} barras de {len(result_df['id_event'].unique())} eventos únicos")
            return result_df
        
        return pd.DataFrame()
    
    def generate_ticker_name(self, ticker_number: int) -> str:
        """
        Generar nombre de ticker sintético (AAA, AAB, AAC...)
        
        Args:
            ticker_number: Número del ticker (0, 1, 2...)
            
        Returns:
            Nombre del ticker (AAA, AAB, etc.)
        """
        # Convertir número a formato AAA, AAB, AAC...
        if ticker_number < 26:
            return f"AA{chr(65 + ticker_number)}"  # AAA, AAB, AAC...
        elif ticker_number < 676:  # 26*26
            first = (ticker_number // 26) - 1
            second = ticker_number % 26
            return f"A{chr(65 + first)}{chr(65 + second)}"  # ABA, ABB, ABC...
        else:
            # Para más de 676 tickers
            first = ((ticker_number // 676) % 26)
            second = ((ticker_number // 26) % 26)
            third = ticker_number % 26
            return f"{chr(65 + first)}{chr(65 + second)}{chr(65 + third)}"
    
    def normalize_and_split_tickers(self, df: pd.DataFrame) -> List[Dict]:
        """
        Normalizar precios y dividir en múltiples tickers cuando se sale del rango
        
        Args:
            df: DataFrame con barras seleccionadas
            
        Returns:
            Lista de tickers sintéticos
        """
        if df.empty:
            return []
        
        print("🔧 Normalizando precios y creando tickers sintéticos...")
        
        synthetic_tickers = []
        current_ticker_data = []
        current_price = self.config['base_price']
        ticker_number = 0
        
        for idx, row in df.iterrows():
            # Calcular variación real de esta barra
            original_open = row['open']
            original_close = row['close']
            original_high = row['high']
            original_low = row['low']
            
            # Variación porcentual real de la barra
            if original_open > 0:
                real_variation = ((original_close - original_open) / original_open) * 100
            else:
                real_variation = 0
            
            # Aplicar variación al precio actual del ticker sintético
            if len(current_ticker_data) > 0:  # No para la primera barra
                new_price = current_price * (1 + real_variation / 100)
            else:
                new_price = current_price
            
            # Verificar si se sale del rango permitido
            if new_price > self.config['max_price'] or new_price < self.config['min_price']:
                # Finalizar ticker actual si tiene datos
                if current_ticker_data:
                    ticker_name = self.generate_ticker_name(ticker_number)
                    synthetic_tickers.append({
                        'ticker_name': ticker_name,
                        'ticker_number': ticker_number,
                        'data': current_ticker_data.copy(),
                        'start_price': current_ticker_data[0]['normalized_close'],
                        'end_price': current_ticker_data[-1]['normalized_close'],
                        'total_bars': len(current_ticker_data)
                    })
                    ticker_number += 1
                
                # Reiniciar para nuevo ticker
                current_ticker_data = []
                current_price = self.config['base_price']
                new_price = current_price * (1 + real_variation / 100)
                
                print(f"🔄 Creando ticker #{ticker_number} - Precio fuera de rango")
            
            # Calcular factor de normalización manteniendo proporciones OHLC
            if original_close > 0:
                price_factor = new_price / original_close
            else:
                price_factor = 1.0
            
            # Crear barra normalizada manteniendo proporciones exactas
            normalized_bar = {
                'original_ticker': row['ticker'],
                'original_timestamp': row['bar_date'],
                'event_id': row['id_event'],
                'ratio_vol': row['ratio_vol'],
                'percent_var': row['percent_var'],
                'original_open': original_open,
                'original_high': original_high,
                'original_low': original_low,
                'original_close': original_close,
                'original_volume': row['bar_volume'] or row['volumen'],
                'normalized_open': round(original_open * price_factor, 2),
                'normalized_high': round(original_high * price_factor, 2),
                'normalized_low': round(original_low * price_factor, 2),
                'normalized_close': round(new_price, 2),
                'normalized_volume': row['bar_volume'] or row['volumen'],
                'price_factor': price_factor,
                'real_variation': real_variation
            }
            
            current_ticker_data.append(normalized_bar)
            current_price = new_price
            
            # Verificar límite máximo de eventos por ticker
            if len(current_ticker_data) >= self.config['max_events']:
                ticker_name = self.generate_ticker_name(ticker_number)
                synthetic_tickers.append({
                    'ticker_name': ticker_name,
                    'ticker_number': ticker_number,
                    'data': current_ticker_data.copy(),
                    'start_price': current_ticker_data[0]['normalized_close'],
                    'end_price': current_ticker_data[-1]['normalized_close'],
                    'total_bars': len(current_ticker_data)
                })
                ticker_number += 1
                current_ticker_data = []
                current_price = self.config['base_price']
                print(f"📊 Ticker completado por límite de eventos: {self.config['max_events']}")
        
        # Añadir último ticker si tiene datos
        if current_ticker_data:
            ticker_name = self.generate_ticker_name(ticker_number)
            synthetic_tickers.append({
                'ticker_name': ticker_name,
                'ticker_number': ticker_number,
                'data': current_ticker_data.copy(),
                'start_price': current_ticker_data[0]['normalized_close'],
                'end_price': current_ticker_data[-1]['normalized_close'],
                'total_bars': len(current_ticker_data)
            })
        
        print(f"✅ Creados {len(synthetic_tickers)} tickers sintéticos")
        
        return synthetic_tickers
    
    def create_sequential_timeline_for_ticker(self, ticker_data: List[Dict]) -> pd.DataFrame:
        """
        Crear timeline secuencial uniendo barras de eventos reales consecutivamente
        SIN barras intermedias - solo eventos reales unidos uno tras otro
        
        Args:
            ticker_data: Lista de barras normalizadas de múltiples eventos
            
        Returns:
            DataFrame con timeline secuencial de eventos reales
        """
        if not ticker_data:
            return pd.DataFrame()
        
        print(f"🔗 Creando timeline secuencial con {len(ticker_data)} barras reales...")
        
        # Crear timeline secuencial - una barra tras otra sin gaps
        timeline = []
        current_date = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        
        for i, explosion in enumerate(ticker_data):
            # Avanzar al siguiente día laborable si es necesario
            if current_date.hour >= 16:
                current_date = current_date.replace(hour=9, minute=30) + timedelta(days=1)
            
            # Saltar weekends
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                current_date = current_date.replace(hour=9, minute=30)
            
            # Crear barra con datos reales normalizados
            bar_data = {
                'timestamp': current_date.strftime('%Y-%m-%d %H:%M:%S'),
                'open': explosion['normalized_open'],
                'high': explosion['normalized_high'],
                'low': explosion['normalized_low'],
                'close': explosion['normalized_close'],
                'volume': explosion['normalized_volume'],
                'is_explosion': True,  # Todas son explosiones reales
                'original_ticker': explosion['original_ticker'],
                'ratio_vol': explosion['ratio_vol'],
                'event_id': explosion['event_id'],
                'original_date': explosion['original_timestamp']
            }
            
            timeline.append(bar_data)
            
            # Avanzar tiempo (cada barra = +1 minuto para continuidad)
            current_date += timedelta(minutes=1)
        
        df = pd.DataFrame(timeline)
        print(f"✅ Timeline secuencial creado: {len(df)} barras consecutivas")
        print(f"   📅 Período sintético: {df['timestamp'].min()} a {df['timestamp'].max()}")
        print(f"   🎯 Eventos únicos incluidos: {len(df['event_id'].unique())}")
        
        return df
    
    def save_ticker_to_csv(self, ticker_info: Dict, output_dir: str) -> bool:
        """
        Guardar ticker sintético a archivo CSV
        
        Args:
            ticker_info: Información del ticker
            output_dir: Directorio de salida
            
        Returns:
            True si se guardó correctamente
        """
        try:
            # Crear timeline secuencial (solo eventos reales unidos)
            timeline_df = self.create_sequential_timeline_for_ticker(ticker_info['data'])
            
            if timeline_df.empty:
                print(f"❌ No se pudo crear timeline para {ticker_info['ticker_name']}")
                return False
            
            # Preparar datos para CSV
            csv_data = timeline_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            csv_data.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            
            # Formatear volumen como entero
            csv_data['Volume'] = csv_data['Volume'].astype(int)
            
            # Crear archivo CSV
            filename = f"{ticker_info['ticker_name']}.csv"
            filepath = os.path.join(output_dir, filename)
            
            csv_data.to_csv(filepath, index=False)
            
            # Estadísticas
            explosions_count = timeline_df['is_explosion'].sum()
            file_size = os.path.getsize(filepath) / 1024  # KB
            
            print(f"✅ {filename}: {len(csv_data):,} barras, {explosions_count} explosiones, {file_size:.1f} KB")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando {ticker_info['ticker_name']}: {e}")
            return False
    
    def generate_all_synthetic_tickers(self) -> bool:
        """
        Proceso completo de generación de tickers sintéticos
        
        Returns:
            True si se generaron correctamente
        """
        print("🚀 GENERANDO TICKERS SINTÉTICOS DESDE BASE DE DATOS REAL")
        print("=" * 70)
        
        try:
            # 1. Conectar a BD
            if not self.connect_to_database():
                return False
            
            # 2. Obtener todos los eventos de explosión
            print("\n📊 Extrayendo eventos de explosiones...")
            all_events_df = self.get_all_explosion_events(self.config['total_events_limit'])
            
            if all_events_df.empty:
                print("❌ No se encontraron eventos válidos")
                return False
            
            # 3. Seleccionar mejores barras por evento
            print("\n🎯 Seleccionando mejores barras por evento...")
            selected_df = self.select_best_bars_per_event(all_events_df)
            
            if selected_df.empty:
                print("❌ No se pudieron seleccionar barras válidas")
                return False
            
            print(f"   ✅ Seleccionadas {len(selected_df)} barras de {len(selected_df['id_event'].unique())} eventos")
            
            # 4. Normalizar y dividir en tickers
            print("\n🔧 Normalizando precios y creando tickers...")
            synthetic_tickers = self.normalize_and_split_tickers(selected_df)
            
            if not synthetic_tickers:
                print("❌ No se pudieron crear tickers sintéticos")
                return False
            
            # 5. Guardar archivos CSV
            print(f"\n💾 Guardando {len(synthetic_tickers)} tickers sintéticos...")
            
            output_dir = os.path.dirname(os.path.abspath(__file__))
            saved_count = 0
            
            for ticker_info in synthetic_tickers:
                if self.save_ticker_to_csv(ticker_info, output_dir):
                    saved_count += 1
            
            # 6. Mostrar resumen final
            if saved_count > 0:
                print(f"\n🎉 ¡{saved_count} TICKERS SINTÉTICOS GENERADOS EXITOSAMENTE!")
                print("=" * 70)
                
                for ticker_info in synthetic_tickers:
                    price_change = ((ticker_info['end_price'] - ticker_info['start_price']) / ticker_info['start_price']) * 100
                    print(f"📊 {ticker_info['ticker_name']}.csv:")
                    print(f"   💥 Explosiones reales incluidas: {len(ticker_info['data'])}")
                    print(f"   📈 Rango precio: ${ticker_info['start_price']:.2f} → ${ticker_info['end_price']:.2f} ({price_change:+.1f}%)")
                
                print(f"\n✅ Archivos listos para usar en trading_system_v3")
                print(f"💡 Copia los archivos a data/csv_data/ para usar en simulaciones")
                
                return True
            else:
                print("❌ No se pudo guardar ningún ticker")
                return False
            
        except Exception as e:
            print(f"❌ Error en generación: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.connection:
                self.connection.close()
    
    def close_connection(self):
        """Cerrar conexión a la base de datos"""
        if self.connection:
            self.connection.close()
            self.connection = None


def main():
    """Interfaz principal"""
    
    print("🎯 GENERADOR DE TICKERS SINTÉTICOS DESDE BD")
    print("=" * 60)
    print("Combina eventos reales de explosiones en tickers sintéticos secuenciales")
    print()
    
    # Ruta fija de la base de datos
    db_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/data_fetch to mysql/database.db"
    
    print(f"📂 Base de datos: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos: {db_path}")
        return
    
    # Crear generador
    generator = DBToSyntheticTickerGenerator(db_path)
    
    # Configuración
    print(f"\n⚙️ CONFIGURACIÓN:")
    print(f"   📊 Ratio volumen mínimo: {generator.config['min_ratio_vol']}x")
    print(f"   📈 Variación mínima: {generator.config['min_percent_var']}%")
    print(f"   💰 Rango precios: ${generator.config['min_price']} - ${generator.config['max_price']}")
    print(f"   🎯 Precio inicial: ${generator.config['base_price']}")
    print(f"   📝 Nombres tickers: AAA.csv, AAB.csv, AAC.csv...")
    
    # Confirmación (auto-confirmar para ejecución automática)
    print(f"\n🚀 Generando tickers sintéticos automáticamente...")
    confirm = 'y'
    
    # Generar tickers
    try:
        success = generator.generate_all_synthetic_tickers()
        
        if success:
            print(f"\n🎉 ¡Proceso completado exitosamente!")
        else:
            print(f"\n❌ Error en la generación")
            
    except KeyboardInterrupt:
        print(f"\n👋 Proceso cancelado")
    finally:
        generator.close_connection()


if __name__ == "__main__":
    main()