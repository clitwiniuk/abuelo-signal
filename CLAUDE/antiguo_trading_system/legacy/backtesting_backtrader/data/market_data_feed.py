import backtrader as bt
import pandas as pd
import sqlite3
from datetime import datetime, time
import logging

class MarketDataFeed(bt.feeds.PandasData):
    """
    Feed de datos desde market_data.db o database.db para Backtrader
    Filtra datos para horario regular de mercado (9:30-16:00)
    """

    params = (
        ('db_path', '../../clasificador_trades/database.db'),
        ('symbol', None),
        ('event_id', None),
        ('start_date', None),
        ('end_date', None),
        ('market_open', '15:30'),
        ('market_close', '22:00'),  # Hora española
    )

    def __init__(self):
        # Backtrader ya habrá establecido self.p con los parámetros
        if not self.p.event_id:
            raise ValueError("Se requiere especificar un event_id")

        # Determinar qué base de datos usar
        try:
            int(self.p.event_id)  # Intentar convertir a int
            # Es un event_id numérico, usar database.db
            actual_db_path = self.p.db_path
            load_function = self._load_data_from_database_db
        except ValueError:
            # Es un símbolo, usar market_data.db
            actual_db_path = '../../market_data.db'
            load_function = self._load_data_from_market_db

        # Cargar datos desde la base de datos ANTES de llamar a super().__init__
        df = load_function(
            self.p.event_id,
            actual_db_path,
            self.p.start_date,
            self.p.end_date,
            self.p.market_open,
            self.p.market_close
        )

        # Establecer el DataFrame como dataname
        self.p.dataname = df

        # Ahora llamar a super().__init__()
        super().__init__()

    @staticmethod
    def _load_data_from_database_db(event_id, db_path, start_date, end_date, market_open, market_close):
        """Cargar datos desde database.db (eventos clasificados)"""
        try:
            conn = sqlite3.connect(db_path)

            query = """
            SELECT
                date as datetime,
                open,
                high,
                low,
                close,
                volume
            FROM OHLCData
            WHERE id_event = ?
            """

            params = [event_id]

            # Agregar filtros de fecha si se especifican
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND date <= ?"
                params.append(end_date)

            query += " ORDER BY date"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty:
                logging.warning(f"No se encontraron datos para event_id {event_id}")
                return pd.DataFrame()  # DataFrame vacío para evitar errores

            # Convertir datetime string a datetime object
            df['datetime'] = pd.to_datetime(df['datetime'])

            # Filtrar solo horario regular de mercado
            market_open_time = datetime.strptime(market_open, '%H:%M').time()
            market_close_time = datetime.strptime(market_close, '%H:%M').time()
            mask = df['datetime'].apply(lambda x: market_open_time <= x.time() <= market_close_time)
            df = df[mask]

            if df.empty:
                logging.warning(f"No hay datos en horario de mercado para event_id {event_id}")
                return pd.DataFrame()  # DataFrame vacío para evitar errores

            # Establecer datetime como índice
            df.set_index('datetime', inplace=True)

            logging.info(f"Cargados {len(df)} registros para event_id {event_id}")
            return df

        except Exception as e:
            logging.error(f"Error cargando datos para event_id {event_id}: {e}")
            raise

    @staticmethod
    def _load_data_from_market_db(symbol, db_path, start_date, end_date, market_open, market_close):
        """Cargar datos desde market_data.db (datos de mercado intradiarios)"""
        try:
            conn = sqlite3.connect(db_path)

            query = """
            SELECT
                bar_timestamp as datetime,
                open_price as open,
                high_price as high,
                low_price as low,
                close_price as close,
                volume as volume
            FROM intraday_bars
            WHERE symbol = ?
            """

            params = [symbol]

            # Agregar filtros de fecha si se especifican
            if start_date:
                query += " AND date(bar_timestamp) >= ?"
                params.append(start_date)

            if end_date:
                query += " AND date(bar_timestamp) <= ?"
                params.append(end_date)

            query += " ORDER BY bar_timestamp"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty:
                logging.warning(f"No se encontraron datos para símbolo {symbol}")
                return pd.DataFrame()  # DataFrame vacío para evitar errores

            # Convertir datetime string a datetime object
            df['datetime'] = pd.to_datetime(df['datetime'])

            # Filtrar por horario de mercado (hora España: 15:30-22:00 = USA 9:30-16:00)
            logging.info(f"Datos antes del filtro horario: {len(df)} registros")
            market_open_time = datetime.strptime(market_open, '%H:%M').time()
            market_close_time = datetime.strptime(market_close, '%H:%M').time()
            mask = df['datetime'].apply(lambda x: market_open_time <= x.time() <= market_close_time)
            df = df[mask]
            logging.info(f"Datos después del filtro horario: {len(df)} registros")
            print(f"DEBUG: Cargados {len(df)} registros para {symbol}")
            if not df.empty:
                print(f"DEBUG: Primeras fechas: {df['datetime'].head().tolist()}")
                print(f"DEBUG: Últimas fechas: {df['datetime'].tail().tolist()}")

            if df.empty:
                logging.warning(f"No hay datos en horario de mercado para símbolo {symbol}")
                return pd.DataFrame()  # DataFrame vacío para evitar errores

            # Establecer datetime como índice
            df.set_index('datetime', inplace=True)

            logging.info(f"Cargados {len(df)} registros para símbolo {symbol}")
            return df

        except Exception as e:
            logging.error(f"Error cargando datos para símbolo {symbol}: {e}")
            raise

def create_data_feed(event_id, db_path='../../clasificador_trades/database.db', start_date=None, end_date=None):
    """
    Función helper para crear un feed de datos

    Args:
        event_id: ID del evento o símbolo
        db_path: Ruta a database.db
        start_date: Fecha inicio (YYYY-MM-DD)
        end_date: Fecha fin (YYYY-MM-DD)

    Returns:
        MarketDataFeed configurado
    """
    # Si event_id parece un símbolo (no numérico), usar market_data.db
    try:
        int(event_id)  # Intentar convertir a int
        # Es un event_id numérico, usar database.db
        actual_db_path = db_path
    except ValueError:
        # Es un símbolo, usar market_data.db
        actual_db_path = '../../market_data.db'

    return MarketDataFeed(
        db_path=actual_db_path,
        event_id=event_id,
        start_date=start_date,
        end_date=end_date
    )