"""
Data Feed para Backtrader - Integración con IBKR y trading_data.db

Este módulo proporciona feeds de datos personalizados para backtrader
que integran datos reales de IBKR con la base de datos de trading.

Soporta dos tipos de feeds:
1. Intraday: Datos de 1min desde tabla trade_intraday_bars
2. Daily: Datos diarios agregados desde tabla trade_ohlc_snapshots
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Any
import logging

import backtrader as bt
from backtrader.feeds import PandasData


class IBKRIntradayDataFeed:
    """
    Feed de datos INTRADAY (1min) desde market_data.db o trading_data.db

    Carga barras de 1 minuto con prioridad:
    1. market_data.db::intraday_bars (datos completos de Polygon con pre/post market)
    2. trading_data.db::trade_intraday_bars (fallback para símbolos sin datos de Polygon)
    """

    def __init__(self, symbol: str, market_db_path: str = None,
                 trading_db_path: str = None,
                 start_date: str = None, end_date: str = None,
                 use_market_data: bool = True):
        """
        Inicializar data feed intraday

        Args:
            symbol: Símbolo del ticker
            market_db_path: Ruta a market_data.db (auto-detecta si None)
            trading_db_path: Ruta a trading_data.db (auto-detecta si None)
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
            use_market_data: Usar market_data.db (True) o trading_data.db (False)
        """
        self.symbol = symbol
        self.market_db_path = market_db_path or self._get_market_db_path()
        self.trading_db_path = trading_db_path or self._get_trading_db_path()
        self.start_date = start_date
        self.end_date = end_date
        self.use_market_data = use_market_data

        # Cargar datos intraday
        df = self._load_intraday_data()

        if df.empty:
            logging.warning(f"No intraday data found for {symbol}")
            df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        # Asegurar que datetime sea índice
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)

        # Logging
        if not df.empty:
            logging.info(f"[INTRADAY] {symbol}: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        else:
            logging.warning(f"[INTRADAY] {symbol}: No data loaded")

        self.df = df

    def _get_market_db_path(self) -> str:
        """Obtener ruta por defecto a market_data.db"""
        # Desde backtesting_system/data/ -> trading_system_v3/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'market_data.db')

    def _get_trading_db_path(self) -> str:
        """Obtener ruta por defecto a trading_data.db"""
        # Desde backtesting_system/data/ -> trading_system_v3/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'trading_data.db')

    def _load_intraday_data(self) -> pd.DataFrame:
        """
        Cargar datos intraday con prioridad market_data.db -> trading_data.db

        Returns:
            DataFrame con datos OHLCV intraday
        """
        try:
            # Intentar primero con market_data.db (datos de Polygon)
            if self.use_market_data and os.path.exists(self.market_db_path):
                df = self._load_from_market_db()
                if not df.empty:
                    logging.info(f"Loaded {len(df)} bars from market_data.db for {self.symbol}")
                    return df
                else:
                    logging.info(f"No market data found for {self.symbol}, trying trade data...")

            # Fallback: usar trading_data.db::trade_intraday_bars
            if os.path.exists(self.trading_db_path):
                df = self._load_from_trading_db()
                if not df.empty:
                    logging.info(f"Loaded {len(df)} bars from trading_data.db for {self.symbol}")
                    return df

            logging.warning(f"No intraday data found for {self.symbol}")
            return pd.DataFrame()

        except Exception as e:
            logging.error(f"Error loading intraday data for {self.symbol}: {e}")
            return pd.DataFrame()

    def _load_from_market_db(self) -> pd.DataFrame:
        """
        Cargar datos desde market_data.db::intraday_bars

        Returns:
            DataFrame con datos OHLCV
        """
        try:
            conn = sqlite3.connect(self.market_db_path)

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

            params = [self.symbol]

            # Agregar filtros de fecha
            if self.start_date:
                query += " AND DATE(bar_timestamp) >= ?"
                params.append(self.start_date)

            if self.end_date:
                query += " AND DATE(bar_timestamp) <= ?"
                params.append(self.end_date)

            query += " ORDER BY bar_timestamp ASC"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            return df

        except Exception as e:
            logging.debug(f"Error loading from market_data.db: {e}")
            return pd.DataFrame()

    def _load_from_trading_db(self) -> pd.DataFrame:
        """
        Cargar datos desde trading_data.db::trade_intraday_bars (fallback)

        Returns:
            DataFrame con datos OHLCV
        """
        try:
            conn = sqlite3.connect(self.trading_db_path)

            query = """
                SELECT
                    tib.bar_timestamp as datetime,
                    tib.open_price as open,
                    tib.high_price as high,
                    tib.low_price as low,
                    tib.close_price as close,
                    tib.volume as volume
                FROM trade_intraday_bars tib
                JOIN trades t ON tib.trade_id = t.trade_id
                WHERE t.symbol = ?
            """

            params = [self.symbol]

            # Agregar filtros de fecha
            if self.start_date:
                query += " AND DATE(tib.bar_timestamp) >= ?"
                params.append(self.start_date)

            if self.end_date:
                query += " AND DATE(tib.bar_timestamp) <= ?"
                params.append(self.end_date)

            query += " ORDER BY tib.bar_timestamp ASC"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            return df

        except Exception as e:
            logging.debug(f"Error loading from trading_data.db: {e}")
            return pd.DataFrame()


class IBKRDailyDataFeed:
    """
    Feed de datos DAILY agregados desde tabla trade_ohlc_snapshots

    Carga datos diarios consolidando múltiples snapshots por día
    de la tabla trade_ohlc_snapshots.
    """

    def __init__(self, symbol: str, db_path: str = None,
                 start_date: str = None, end_date: str = None):
        """
        Inicializar data feed daily

        Args:
            symbol: Símbolo del ticker
            db_path: Ruta a la base de datos
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
        """
        self.symbol = symbol
        self.db_path = db_path or self._get_default_db_path()
        self.start_date = start_date
        self.end_date = end_date

        # Cargar datos diarios
        df = self._load_daily_data()

        if df.empty:
            logging.warning(f"No daily data found for {symbol}")
            df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        # Asegurar que datetime sea índice
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)

        # Logging
        if not df.empty:
            logging.info(f"[DAILY] {symbol}: {len(df)} days from {df.index[0]} to {df.index[-1]}")
        else:
            logging.warning(f"[DAILY] {symbol}: No data loaded")

        self.df = df

    def _get_default_db_path(self) -> str:
        """Obtener ruta por defecto a la base de datos"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'trading_data.db')

    def _load_daily_data(self) -> pd.DataFrame:
        """
        Cargar datos diarios desde tabla trade_ohlc_snapshots

        Consolida múltiples snapshots del mismo día en una sola barra diaria.

        Returns:
            DataFrame con datos OHLCV diarios
        """
        try:
            if not os.path.exists(self.db_path):
                logging.error(f"Database not found: {self.db_path}")
                return pd.DataFrame()

            conn = sqlite3.connect(self.db_path)

            # Query para obtener datos diarios (usar los primeros valores del día)
            # Como cada snapshot ya tiene day_open, day_high, etc. del día completo,
            # tomamos el primer registro de cada día
            query = """
                SELECT
                    trading_date as datetime,
                    day_open as open,
                    day_high as high,
                    day_low as low,
                    day_close as close,
                    day_volume as volume
                FROM trade_ohlc_snapshots
                WHERE symbol = ?
            """

            params = [self.symbol]

            if self.start_date:
                query += " AND trading_date >= ?"
                params.append(self.start_date)

            if self.end_date:
                query += " AND trading_date <= ?"
                params.append(self.end_date)

            # Agrupar por trading_date y tomar el primer registro
            query += """
                GROUP BY trading_date
                ORDER BY trading_date ASC
            """

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            logging.info(f"Loaded {len(df)} daily bars for {self.symbol}")
            return df

        except Exception as e:
            logging.error(f"Error loading daily data for {self.symbol}: {e}")
            return pd.DataFrame()


class IBKRDataFeed:
    """
    DEPRECATED: Clase legacy mantenida para compatibilidad

    Usa IBKRIntradayDataFeed o IBKRDailyDataFeed en su lugar.
    """

    def __init__(self, symbol: str, db_path: str = None,
                 start_date: str = None, end_date: str = None, timeframe: str = '1min'):
        """
        Inicializar data feed (LEGACY)

        Args:
            symbol: Símbolo del ticker
            db_path: Ruta a la base de datos
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
            timeframe: Marco temporal ('1min', '5min', '15min', etc.)
        """
        logging.warning("IBKRDataFeed is deprecated. Use IBKRIntradayDataFeed or IBKRDailyDataFeed instead.")

        self.symbol = symbol
        self.db_path = db_path
        self.start_date = start_date
        self.end_date = end_date
        self.timeframe = timeframe

        # Cargar datos usando método legacy
        df = self._load_data()

        if df.empty:
            logging.warning(f"No data found for {symbol} in timeframe {timeframe}")
            df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        # Asegurar que datetime sea índice
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)

        self.df = df
        logging.info(f"Prepared data for {self.symbol} with {len(df)} rows")

    def _load_data(self) -> pd.DataFrame:
        """
        Cargar datos desde la base de datos

        Returns:
            DataFrame con datos OHLCV
        """
        try:
            # Verificar que la base de datos existe
            if not os.path.exists(self.db_path):
                logging.error(f"Database file not found: {self.db_path}")
                logging.info(f"Current working directory: {os.getcwd()}")
                logging.info(f"Files in current directory: {os.listdir('.')}")
                # Intentar con ruta relativa desde el directorio del proyecto
                alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'trading_data.db')
                logging.info(f"Trying alternative path: {alt_path}")
                if os.path.exists(alt_path):
                    logging.info(f"Found database at alternative path: {alt_path}")
                    self.db_path = alt_path
                else:
                    return pd.DataFrame()

            conn = sqlite3.connect(self.db_path)

            # Verificar que la tabla existe
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_ohlc_snapshots';")
            if not cursor.fetchone():
                logging.warning(f"Table 'trade_ohlc_snapshots' not found in database")
                conn.close()
                return pd.DataFrame()

            # Intentar primero con datos OHLC directos (si existieran)
            query_ohlc = """
                SELECT
                    entry_time as datetime,
                    day_open as open,
                    day_high as high,
                    day_low as low,
                    day_close as close,
                    day_volume as volume
                FROM trade_ohlc_snapshots
                WHERE symbol = ?
            """

            params = [self.symbol]

            # Agregar filtros de fecha si se especifican
            if self.start_date:
                query_ohlc += " AND date(entry_time) >= ?"
                params.append(self.start_date)

            if self.end_date:
                query_ohlc += " AND date(entry_time) <= ?"
                params.append(self.end_date)

            query_ohlc += " ORDER BY entry_time ASC"

            df = pd.read_sql_query(query_ohlc, conn, params=params)

            # Si no hay datos diarios, intentar con datos intraday del JSON
            if df.empty:
                logging.info(f"No daily OHLC data found for {self.symbol}, trying intraday data...")
                query_intraday = """
                    SELECT
                        trading_date,
                        intraday_bars
                    FROM trade_ohlc_snapshots
                    WHERE symbol = ?
                    ORDER BY trading_date ASC
                """

                df_intraday = pd.read_sql_query(query_intraday, conn, params=[self.symbol])
                logging.info(f"Found {len(df_intraday)} intraday records for {self.symbol}")

                if not df_intraday.empty:
                    # Parsear el JSON de barras intraday
                    all_bars = []
                    for idx, row in df_intraday.iterrows():
                        try:
                            logging.debug(f"Processing record {idx} for {self.symbol}")
                            bars_json = row['intraday_bars']
                            logging.debug(f"Raw JSON length: {len(str(bars_json))}")

                            bars = json.loads(bars_json)
                            logging.info(f"Parsed {len(bars)} bars from JSON for {self.symbol}")

                            for bar in bars:
                                all_bars.append({
                                    'datetime': bar['timestamp'],
                                    'open': bar['open'],
                                    'high': bar['high'],
                                    'low': bar['low'],
                                    'close': bar['close'],
                                    'volume': bar['volume']
                                })
                        except (json.JSONDecodeError, KeyError) as e:
                            logging.warning(f"Error parsing intraday bars for {self.symbol} record {idx}: {e}")
                            continue

                    if all_bars:
                        df = pd.DataFrame(all_bars)
                        logging.info(f"Successfully loaded {len(all_bars)} intraday bars for {self.symbol}")
                    else:
                        logging.warning(f"No bars parsed from intraday data for {self.symbol}")

            conn.close()

            return df

        except Exception as e:
            logging.error(f"Error loading data for {self.symbol}: {e}")
            return pd.DataFrame()

    def _load_data_fallback(self) -> pd.DataFrame:
        """
        Método de respaldo para generar datos sintéticos cuando no hay datos reales

        Returns:
            DataFrame con datos sintéticos
        """
        logging.info(f"Generating synthetic data for {self.symbol}")

        # Generar fechas
        if self.start_date and self.end_date:
            start = pd.to_datetime(self.start_date)
            end = pd.to_datetime(self.end_date)
        else:
            start = pd.Timestamp.now() - pd.Timedelta(days=30)
            end = pd.Timestamp.now()

        dates = pd.date_range(start=start, end=end, freq='1min')

        # Generar precios sintéticos basados en small caps típicos ($1-25)
        base_price = np.random.uniform(1.0, 25.0)
        n_points = len(dates)

        # Simular movimiento browniano con drift
        returns = np.random.normal(0.0001, 0.01, n_points)  # Drift positivo pequeño
        prices = base_price * np.exp(np.cumsum(returns))

        # Crear OHLCV
        high_mult = 1 + np.abs(np.random.normal(0, 0.02, n_points))
        low_mult = 1 - np.abs(np.random.normal(0, 0.02, n_points))

        df = pd.DataFrame({
            'datetime': dates,
            'open': prices,
            'high': prices * high_mult,
            'low': prices * low_mult,
            'close': prices * (1 + np.random.normal(0, 0.005, n_points)),
            'volume': np.random.randint(1000, 100000, n_points)
        })

        df.set_index('datetime', inplace=True)
        return df


class MultiSymbolDataFeed:
    """
    Gestor de múltiples feeds de datos

    Permite cargar y gestionar datos para múltiples símbolos simultáneamente.
    Soporta tanto datos intraday como daily.
    """

    def __init__(self, symbols: List[str],
                 start_date: str = None, end_date: str = None,
                 data_type: str = 'intraday'):
        """
        Inicializar multi-symbol data feed

        Args:
            symbols: Lista de símbolos
            start_date: Fecha inicio
            end_date: Fecha fin
            data_type: 'intraday' o 'daily'
        """
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.data_type = data_type
        self.feeds = {}

        self._load_all_feeds()

    def _load_all_feeds(self):
        """Cargar feeds para todos los símbolos"""
        for symbol in self.symbols:
            try:
                # Seleccionar clase según tipo de datos
                if self.data_type == 'daily':
                    feed = IBKRDailyDataFeed(
                        symbol=symbol,
                        start_date=self.start_date,
                        end_date=self.end_date
                    )
                else:
                    feed = IBKRIntradayDataFeed(
                        symbol=symbol,
                        start_date=self.start_date,
                        end_date=self.end_date
                    )

                # Solo agregar si tiene datos
                if not feed.df.empty:
                    self.feeds[symbol] = feed
                    logging.info(f"Loaded {self.data_type} data feed for {symbol}")
                else:
                    logging.warning(f"No {self.data_type} data for {symbol}, skipping")

            except Exception as e:
                logging.error(f"Failed to load {self.data_type} feed for {symbol}: {e}")

    def get_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Obtener DataFrame para un símbolo específico"""
        feed_obj = self.feeds.get(symbol)
        if feed_obj and hasattr(feed_obj, 'df'):
            return feed_obj.df
        else:
            logging.warning(f"No data available for {symbol}")
            return None

    def get_all_feeds(self) -> Dict[str, pd.DataFrame]:
        """Obtener todos los DataFrames"""
        return {symbol: feed_obj.df for symbol, feed_obj in self.feeds.items()}

    def get_available_symbols(self) -> List[str]:
        """Obtener lista de símbolos con datos disponibles"""
        return list(self.feeds.keys())


class DataManager:
    """
    Gestor central de datos para el sistema de backtesting

    Proporciona interfaz unificada para acceder a datos históricos,
    trades realizados y análisis de mercado.
    """

    def __init__(self, db_path: str = 'CLAUDE/trading_system_v3/trading_data.db'):
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def get_trades_data(self, strategy_filter: List[str] = None,
                       start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        Obtener datos de trades realizados

        Args:
            strategy_filter: Lista de estrategias a filtrar
            start_date: Fecha inicio
            end_date: Fecha fin

        Returns:
            DataFrame con datos de trades
        """
        query = """
            SELECT * FROM trades
            WHERE pnl IS NOT NULL
        """

        params = []

        if strategy_filter:
            placeholders = ','.join('?' * len(strategy_filter))
            query += f" AND strategy IN ({placeholders})"
            params.extend(strategy_filter)

        if start_date:
            query += " AND date(entry_time) >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date(entry_time) <= ?"
            params.append(end_date)

        query += " ORDER BY entry_time DESC"

        return pd.read_sql_query(query, self.conn, params=params)

    def get_symbol_performance(self, symbol: str) -> Dict[str, float]:
        """
        Obtener estadísticas de performance para un símbolo

        Args:
            symbol: Símbolo del ticker

        Returns:
            Diccionario con métricas de performance
        """
        query = """
            SELECT
                COUNT(*) as total_trades,
                AVG(pnl) as avg_pnl,
                SUM(pnl) as total_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
                AVG(duration_minutes) as avg_duration
            FROM trades
            WHERE symbol = ? AND pnl IS NOT NULL
        """

        result = pd.read_sql_query(query, self.conn, params=[symbol])

        if result.empty:
            return {}

        return result.iloc[0].to_dict()

    def get_market_context_data(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Obtener datos de contexto de mercado para un símbolo en una fecha específica

        Args:
            symbol: Símbolo del ticker
            date: Fecha (YYYY-MM-DD)

        Returns:
            Diccionario con datos de contexto
        """
        # Esta función se puede expandir para incluir más datos de contexto
        # Por ahora retorna datos básicos
        return {
            'symbol': symbol,
            'date': date,
            'context': 'NEUTRAL',  # Placeholder
            'volatility': 0.0,
            'trend': 0.0
        }