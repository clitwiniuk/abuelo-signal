#!/usr/bin/env python3
"""
Extract Full Trading Days from Database Events
==============================================

Por cada evento de explosión, extrae TODO el día completo de datos OHLC
y lo guarda en un CSV separado (AAAA.csv, AAAB.csv, AAAC.csv...).

Características:
- Un CSV por cada evento de explosión
- Datos completos del día (sin filtros de horario)
- Nomenclatura: AAAA.csv, AAAB.csv, AAAC.csv...
- Hasta 200 eventos por defecto (configurable)
- Datos OHLC auténticos sin modificar
- Guardado en carpeta synthetic_data/
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


class FullTradingDaysExtractor:
    """Extractor de días completos de trading por evento"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
        # Configuración
        self.config = {
            'min_ratio_vol': 2.0,         # Ratio mínimo para seleccionar eventos
            'min_percent_var': 0.5,       # Variación mínima de precio
            'max_events': 200,            # Máximo eventos a extraer
            'base_symbol': 'AAA',         # Prefijo para nomenclatura
            'price_decimals': 2,          # Decimales para precios
            'output_folder': 'synthetic_data'  # Carpeta de salida
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
    
    def create_output_directory(self, base_dir: str) -> str:
        """
        Crear directorio de salida
        
        Args:
            base_dir: Directorio base
            
        Returns:
            Ruta completa del directorio creado
        """
        output_dir = os.path.join(base_dir, self.config['output_folder'])
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            print(f"📂 Directorio creado/verificado: {output_dir}")
            return output_dir
        except Exception as e:
            print(f"❌ Error creando directorio {output_dir}: {e}")
            return base_dir  # Fallback al directorio base
    
    def get_explosion_events(self, limit: int = 200) -> List[Dict]:
        """
        Obtener lista de eventos de explosiones únicos
        
        Args:
            limit: Número máximo de eventos a obtener
            
        Returns:
            Lista de eventos con sus metadatos
        """
        try:
            query = """
            SELECT DISTINCT 
                se.id_event,
                se.ticker,
                se.timestamp as event_timestamp,
                sd.ratio_vol,
                sd.percent_var,
                sd.precio,
                sd.volumen,
                DATE(se.timestamp) as event_date
            FROM ScannerEvents se
            JOIN ScannerData sd ON se.id_event = sd.id_event
            WHERE sd.ratio_vol >= ?
                AND ABS(sd.percent_var) >= ?
            ORDER BY se.timestamp DESC
            LIMIT ?
            """
            
            df = pd.read_sql_query(
                query, 
                self.connection, 
                params=[self.config['min_ratio_vol'], self.config['min_percent_var'], limit]
            )
            
            if df.empty:
                print(f"❌ No se encontraron eventos con ratio >= {self.config['min_ratio_vol']}x")
                return []
            
            events = []
            for _, row in df.iterrows():
                event = {
                    'id_event': row['id_event'],
                    'ticker': row['ticker'],
                    'event_timestamp': row['event_timestamp'],
                    'event_date': row['event_date'],
                    'ratio_vol': row['ratio_vol'],
                    'percent_var': row['percent_var'],
                    'precio': row['precio'],
                    'volumen': row['volumen']
                }
                events.append(event)
            
            print(f"✅ Encontrados {len(events)} eventos de explosión únicos")
            print(f"   📊 Ratio promedio: {df['ratio_vol'].mean():.1f}x")
            print(f"   📈 Variación promedio: {abs(df['percent_var']).mean():.1f}%")
            print(f"   📅 Período: {df['event_timestamp'].min()} a {df['event_timestamp'].max()}")
            
            return events
            
        except Exception as e:
            print(f"❌ Error obteniendo eventos: {e}")
            return []
    
    def get_full_day_ohlc_data(self, event_id: int) -> pd.DataFrame:
        """
        Obtener TODOS los datos OHLC del día completo para un evento
        
        Args:
            event_id: ID del evento
            
        Returns:
            DataFrame con todos los datos OHLC del día
        """
        try:
            query = """
            SELECT 
                oh.date as timestamp,
                oh.open,
                oh.high,
                oh.low,
                oh.close,
                oh.volume,
                se.ticker,
                sd.ratio_vol,
                sd.percent_var
            FROM OHLCData oh
            JOIN ScannerEvents se ON oh.id_event = se.id_event
            JOIN ScannerData sd ON oh.id_event = sd.id_event
            WHERE oh.id_event = ?
                AND oh.open > 0
                AND oh.high > 0
                AND oh.low > 0
                AND oh.close > 0
                AND oh.volume >= 0
            ORDER BY oh.date ASC
            """
            
            df = pd.read_sql_query(query, self.connection, params=[event_id])
            
            if df.empty:
                return df
            
            # Convertir timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Redondear precios a 2 decimales
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                df[col] = df[col].round(self.config['price_decimals'])
            
            # Asegurar que volumen sea entero
            df['volume'] = df['volume'].astype(int)
            
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo datos OHLC para evento {event_id}: {e}")
            return pd.DataFrame()
    
    def generate_csv_filename(self, event_number: int) -> str:
        """
        Generar nombre de archivo CSV (AAAA, AAAB, AAAC...)
        
        Args:
            event_number: Número del evento (0, 1, 2...)
            
        Returns:
            Nombre del archivo CSV
        """
        # Convertir número a formato de 4 letras: AAAA, AAAB, AAAC...
        if event_number < 26:
            return f"AAA{chr(65 + event_number)}.csv"  # AAAA, AAAB, AAAC...
        elif event_number < 676:  # 26*26
            first = (event_number // 26) - 1
            second = event_number % 26
            return f"AA{chr(65 + first)}{chr(65 + second)}.csv"  # AABA, AABB, AABC...
        elif event_number < 17576:  # 26*26*26
            first = ((event_number // 676) % 26)
            second = ((event_number // 26) % 26)
            third = event_number % 26
            return f"A{chr(65 + first)}{chr(65 + second)}{chr(65 + third)}.csv"  # ABAA, ABAB...
        else:
            # Para más de 17576 eventos
            first = (((event_number // 17576) % 26))
            second = (((event_number // 676) % 26))
            third = (((event_number // 26) % 26))
            fourth = event_number % 26
            return f"{chr(65 + first)}{chr(65 + second)}{chr(65 + third)}{chr(65 + fourth)}.csv"
    
    def save_event_day_to_csv(self, event_info: Dict, event_number: int, output_dir: str) -> bool:
        """
        Guardar día completo de un evento a CSV
        
        Args:
            event_info: Información del evento
            event_number: Número secuencial del evento
            output_dir: Directorio de salida
            
        Returns:
            True si se guardó correctamente
        """
        try:
            # Obtener datos OHLC del día completo
            day_df = self.get_full_day_ohlc_data(event_info['id_event'])
            
            if day_df.empty:
                print(f"⚠️ Evento {event_info['id_event']} ({event_info['ticker']}) sin datos OHLC")
                return False
            
            # Generar nombre del archivo
            filename = self.generate_csv_filename(event_number)
            filepath = os.path.join(output_dir, filename)
            
            # Preparar datos para CSV en formato estándar
            csv_data = day_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            csv_data.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            
            # Guardar CSV
            csv_data.to_csv(filepath, index=False)
            
            # Estadísticas del archivo
            file_size = os.path.getsize(filepath) / 1024  # KB
            total_volume = csv_data['Volume'].sum()
            max_volume = csv_data['Volume'].max()
            price_range = ((csv_data['High'].max() - csv_data['Low'].min()) / csv_data['Open'].iloc[0]) * 100
            
            print(f"✅ {filename}: {len(csv_data):,} barras | {event_info['ticker']} | "
                  f"{event_info['ratio_vol']:.1f}x ratio | {file_size:.1f} KB")
            print(f"   📊 Volumen total: {total_volume:,} | Max: {max_volume:,} | "
                  f"Rango precio: {price_range:.1f}%")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando evento {event_info['id_event']}: {e}")
            return False
    
    def save_events_metadata(self, events_info: List[Dict], output_dir: str) -> bool:
        """
        Guardar archivo de metadatos con información de cada evento
        
        Args:
            events_info: Lista con información de eventos y archivos generados
            output_dir: Directorio de salida
            
        Returns:
            True si se guardó correctamente
        """
        try:
            metadata_path = os.path.join(output_dir, 'events_metadata.csv')
            
            metadata_rows = []
            for event_data in events_info:
                row = {
                    'synthetic_ticker': event_data['csv_filename'].replace('.csv', ''),
                    'csv_file': event_data['csv_filename'],
                    'original_ticker': event_data['original_ticker'],
                    'event_timestamp': event_data['event_timestamp'],
                    'event_date': event_data['event_date'],
                    'ratio_vol': event_data['ratio_vol'],
                    'percent_var': event_data['percent_var'],
                    'precio': event_data['precio'],
                    'volumen': event_data['volumen'],
                    'total_bars': event_data['total_bars'],
                    'id_event': event_data['id_event']
                }
                metadata_rows.append(row)
            
            # Crear DataFrame y guardar
            metadata_df = pd.DataFrame(metadata_rows)
            metadata_df.to_csv(metadata_path, index=False)
            
            print(f"✅ Metadatos guardados: events_metadata.csv ({len(metadata_rows)} eventos)")
            print(f"   📊 Incluye hora exacta de cada evento para backtesting")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando metadatos: {e}")
            return False
    
    def extract_all_trading_days(self, base_output_dir: str = None) -> bool:
        """
        Proceso completo: extraer días completos para todos los eventos
        
        Args:
            base_output_dir: Directorio base de salida (opcional)
            
        Returns:
            True si se completó exitosamente
        """
        print("🚀 EXTRAYENDO DÍAS COMPLETOS DE TRADING POR EVENTO")
        print("=" * 60)
        
        try:
            # 1. Conectar a BD
            if not self.connect_to_database():
                return False
            
            # 2. Crear directorio de salida
            if not base_output_dir:
                base_output_dir = os.path.dirname(os.path.abspath(__file__))
            
            output_dir = self.create_output_directory(base_output_dir)
            
            # 3. Obtener eventos de explosión
            print(f"\n📊 Buscando eventos de explosión (límite: {self.config['max_events']})...")
            events = self.get_explosion_events(self.config['max_events'])
            
            if not events:
                print("❌ No se encontraron eventos válidos")
                return False
            
            print(f"\n💾 Guardando días completos en: {output_dir}")
            print(f"🎯 Formato de archivos: AAAA.csv, AAAB.csv, AAAC.csv...")
            
            # 4. Procesar cada evento
            successful_extractions = 0
            total_bars = 0
            events_metadata = []  # Para recopilar información de metadatos
            
            for i, event_info in enumerate(events):
                print(f"\n📈 Procesando evento {i+1}/{len(events)}: "
                      f"{event_info['ticker']} (ID: {event_info['id_event']})")
                
                success = self.save_event_day_to_csv(event_info, i, output_dir)
                if success:
                    successful_extractions += 1
                    # Contar barras del archivo recién creado
                    filename = self.generate_csv_filename(i)
                    filepath = os.path.join(output_dir, filename)
                    bars_count = 0
                    if os.path.exists(filepath):
                        df_temp = pd.read_csv(filepath)
                        bars_count = len(df_temp)
                        total_bars += bars_count
                    
                    # Recopilar información para metadatos
                    event_metadata = {
                        'csv_filename': filename,
                        'original_ticker': event_info['ticker'],
                        'event_timestamp': event_info['event_timestamp'],
                        'event_date': event_info['event_date'],
                        'ratio_vol': event_info['ratio_vol'],
                        'percent_var': event_info['percent_var'],
                        'precio': event_info['precio'],
                        'volumen': event_info['volumen'],
                        'total_bars': bars_count,
                        'id_event': event_info['id_event']
                    }
                    events_metadata.append(event_metadata)
            
            # 5. Guardar metadatos
            if events_metadata:
                self.save_events_metadata(events_metadata, output_dir)
            
            # 6. Resumen final
            if successful_extractions > 0:
                print(f"\n🎉 ¡{successful_extractions} DÍAS DE TRADING EXTRAÍDOS EXITOSAMENTE!")
                print("=" * 70)
                print(f"📊 Total archivos generados: {successful_extractions}")
                print(f"📊 Total barras OHLC: {total_bars:,}")
                print(f"📊 Promedio barras por día: {total_bars // successful_extractions:.0f}")
                print(f"📂 Ubicación: {output_dir}")
                print(f"📋 Metadatos: events_metadata.csv (hora exacta de cada evento)")
                print(f"\n✅ Cada CSV contiene un día completo de trading con una explosión real")
                print(f"💡 Consulta events_metadata.csv para saber cuándo ocurrió cada evento")
                
                return True
            else:
                print("❌ No se pudo extraer ningún día de trading")
                return False
            
        except Exception as e:
            print(f"❌ Error en extracción: {e}")
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
    
    print("🎯 EXTRACTOR DE DÍAS COMPLETOS DE TRADING")
    print("=" * 50)
    print("Extrae días completos de trading por cada evento de explosión")
    print("Guarda cada día en un CSV separado en carpeta synthetic_data/")
    print()
    
    # Ruta de la base de datos
    db_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/data_fetch to mysql/database.db"
    
    print(f"📂 Base de datos: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos: {db_path}")
        return
    
    # Crear extractor
    extractor = FullTradingDaysExtractor(db_path)
    
    # Configuración
    print(f"\n⚙️ CONFIGURACIÓN ACTUAL:")
    print(f"   📊 Ratio volumen mínimo: {extractor.config['min_ratio_vol']}x")
    print(f"   📈 Variación mínima: {extractor.config['min_percent_var']}%")
    print(f"   🎯 Máximo eventos: {extractor.config['max_events']}")
    print(f"   📁 Carpeta de salida: {extractor.config['output_folder']}/")
    print(f"   📝 Formato archivos: AAAA.csv, AAAB.csv, AAAC.csv...")
    
    # Extraer eventos por defecto (100)
    print(f"\n🚀 Extrayendo {extractor.config['max_events']} eventos automáticamente...")
    confirm = 'y'
    
    # Extraer días completos
    try:
        success = extractor.extract_all_trading_days()
        
        if success:
            print(f"\n🎉 ¡Proceso completado exitosamente!")
        else:
            print(f"\n❌ Error en la extracción")
            
    except KeyboardInterrupt:
        print(f"\n👋 Proceso cancelado")
    finally:
        extractor.close_connection()


if __name__ == "__main__":
    main()