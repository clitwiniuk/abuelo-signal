"""
Data Loader Real
================

Cargador de datos reales desde market_data.db para backtesting.
Reemplaza pattern_generator con datos reales de Polygon.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import os

logger = logging.getLogger(__name__)


class DataLoaderReal:
    """Cargador de datos reales desde market_data.db"""
    
    def __init__(self, db_path: str = None):
        """
        Inicializar data loader
        
        Args:
            db_path: Ruta a market_data.db (auto-detecta si None)
        """
        if db_path is None:
            # Auto-detectar ruta de market_data.db
            base_dir = os.path.dirname(os.path.dirname(__file__))  # backtesting_system/core
            parent_dir = os.path.dirname(base_dir)  # backtesting_system
            root_dir = os.path.dirname(parent_dir)  # trading_system_v3
            
            # Buscar market_data.db en varios lugares
            possible_paths = [
                os.path.join(root_dir, 'market_data.db'),  # trading_system_v3/market_data.db
                os.path.join(base_dir, 'market_data.db'),  # backtesting_system/core/market_data.db
                os.path.join(parent_dir, 'market_data.db'), # backtesting_system/market_data.db
            ]
            
            db_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
            
            if db_path is None:
                raise FileNotFoundError(f"market_data.db no encontrado en ninguna de estas ubicaciones: {possible_paths}")
        
        self.db_path = db_path
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"market_data.db no encontrado en: {db_path}")
        
        logger.info(f"📊 DataLoaderReal inicializado - DB: {db_path}")

    def get_available_symbols(self) -> List[Dict[str, Any]]:
        """
        Obtener lista de símbolos disponibles con estadísticas
        
        Returns:
            Lista de diccionarios con info de cada símbolo
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT 
                    symbol,
                    COUNT(*) as total_bars,
                    MIN(bar_timestamp) as first_date,
                    MAX(bar_timestamp) as last_date,
                    COUNT(DISTINCT DATE(bar_timestamp)) as trading_days,
                    MIN(close_price) as min_price,
                    MAX(close_price) as max_price,
                    AVG(close_price) as avg_price
                FROM intraday_bars 
                GROUP BY symbol
                ORDER BY total_bars DESC
                """
                
                df = pd.read_sql_query(query, conn)
                
                # Convertir a lista de diccionarios
                symbols_info = []
                for _, row in df.iterrows():
                    symbols_info.append({
                        'symbol': row['symbol'],
                        'total_bars': row['total_bars'],
                        'first_date': row['first_date'],
                        'last_date': row['last_date'],
                        'trading_days': row['trading_days'],
                        'price_range': f"${row['min_price']:.2f} - ${row['max_price']:.2f}",
                        'avg_price': row['avg_price']
                    })
                
                logger.info(f"✅ Encontrados {len(symbols_info)} símbolos disponibles")
                return symbols_info
                
        except Exception as e:
            logger.error(f"Error obteniendo símbolos: {e}")
            return []

    def load_real_opportunities(self, symbols: List[str] = None, 
                              start_date: str = None, 
                              end_date: str = None,
                              min_volume: int = 10000,
                              pattern_type: str = 'all') -> List[Dict[str, Any]]:
        """
        Cargar oportunidades reales desde la base de datos
        
        Args:
            symbols: Lista de símbolos (None = todos)
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)
            min_volume: Volumen mínimo para filtrar
            pattern_type: Tipo de patrón a generar ('gap_go', 'breakout', etc.)
            
        Returns:
            Lista de oportunidades reales basadas en datos históricos
        """
        try:
            # Construir query
            where_conditions = []
            params = []
            
            if symbols:
                placeholders = ','.join(['?' for _ in symbols])
                where_conditions.append(f"symbol IN ({placeholders})")
                params.extend(symbols)
            
            if start_date:
                where_conditions.append("DATE(bar_timestamp) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("DATE(bar_timestamp) <= ?")
                params.append(end_date)
            
            if min_volume:
                where_conditions.append("volume >= ?")
                params.append(min_volume)
            
            where_clause = " AND ".join(where_conditions)
            where_clause = f"WHERE {where_clause}" if where_clause else ""
            
            query = f"""
            SELECT 
                id, symbol, bar_timestamp, open_price, high_price, 
                low_price, close_price, volume, vwap
            FROM intraday_bars 
            {where_clause}
            ORDER BY symbol, bar_timestamp
            """
            
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)
                
            if df.empty:
                logger.warning("No se encontraron datos para los criterios especificados")
                return []
            
            # Convertir a datetime
            df['bar_timestamp'] = pd.to_datetime(df['bar_timestamp'])
            
            # Generar oportunidades basadas en datos reales
            opportunities = self._generate_real_patterns(df, pattern_type)
            
            logger.info(f"✅ Generadas {len(opportunities)} oportunidades reales")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error cargando datos reales: {e}")
            return []

    def _generate_real_patterns(self, df: pd.DataFrame, pattern_type: str) -> List[Dict[str, Any]]:
        """
        Generar oportunidades basadas en patrones reales de los datos
        
        Args:
            df: DataFrame con datos históricos
            pattern_type: Tipo de patrón
            
        Returns:
            Lista de oportunidades generadas
        """
        opportunities = []
        
        # Agrupar por símbolo para análisis intraday
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].sort_values('bar_timestamp')
            
            if len(symbol_data) < 50:  # Necesitamos suficientes datos
                continue
            
            # Generar oportunidades por tipo
            if pattern_type == 'gap_go' or pattern_type == 'all':
                opportunities.extend(self._detect_gap_go_patterns(symbol_data))
            
            if pattern_type == 'breakout' or pattern_type == 'all':
                opportunities.extend(self._detect_breakout_patterns(symbol_data))
            
            if pattern_type == 'volume_spike' or pattern_type == 'all':
                opportunities.extend(self._detect_volume_patterns(symbol_data))
            
            if pattern_type == 'macd_signal' or pattern_type == 'all':
                opportunities.extend(self._detect_macd_patterns(symbol_data))
        
        return opportunities

    def _detect_gap_go_patterns(self, symbol_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detectar patrones Gap-Go en datos reales"""
        opportunities = []
        
        symbol_data = symbol_data.reset_index(drop=True)
        
        for i in range(1, len(symbol_data)):
            current = symbol_data.iloc[i]
            prev_day = symbol_data.iloc[i-1]
            
            # Detectar gap significativo (más del 2%)
            if pd.notna(current['open_price']) and pd.notna(prev_day['close_price']):
                gap_pct = ((current['open_price'] - prev_day['close_price']) / prev_day['close_price']) * 100
                
                if abs(gap_pct) > 2.0:  # Gap significativo
                    opportunities.append({
                        'symbol': current['symbol'],
                        'pattern_type': 'gap_go',
                        'current_price': current['open_price'],
                        'gap_percentage': gap_pct,
                        'volume_ratio': current['volume'] / 100000,  # Normalizado
                        'quality_score': min(100, max(0, 50 + abs(gap_pct) * 5)),
                        'timestamp': current['bar_timestamp'].isoformat(),
                        'bars': self._get_bars_around(symbol_data, i, 20),
                        'catalyst_type': 'historical_gap',
                        'opportunity_id': f"{current['symbol']}_{current['bar_timestamp'].strftime('%Y%m%d_%H%M')}_gap",
                        'real_data': True  # Marcar como datos reales
                    })
        
        return opportunities

    def _detect_breakout_patterns(self, symbol_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detectar patrones de breakout"""
        opportunities = []
        
        symbol_data = symbol_data.reset_index(drop=True)
        
        # Calcular resistencias y soportes móviles
        symbol_data['resistance_20'] = symbol_data['high_price'].rolling(20).max()
        symbol_data['support_20'] = symbol_data['low_price'].rolling(20).min()
        
        for i in range(20, len(symbol_data)):
            current = symbol_data.iloc[i]
            
            # Breakout alcista
            if (pd.notna(current['resistance_20']) and 
                current['close_price'] > current['resistance_20'] and
                current['volume'] > 50000):
                
                breakout_strength = (current['close_price'] - current['resistance_20']) / current['resistance_20'] * 100
                
                opportunities.append({
                    'symbol': current['symbol'],
                    'pattern_type': 'breakout',
                    'current_price': current['close_price'],
                    'gap_percentage': breakout_strength,
                    'volume_ratio': current['volume'] / 100000,
                    'quality_score': min(100, 50 + breakout_strength * 10),
                    'timestamp': current['bar_timestamp'].isoformat(),
                    'bars': self._get_bars_around(symbol_data, i, 30),
                    'catalyst_type': 'technical_breakout',
                    'opportunity_id': f"{current['symbol']}_{current['bar_timestamp'].strftime('%Y%m%d_%H%M')}_breakout",
                    'real_data': True
                })
        
        return opportunities

    def _detect_volume_patterns(self, symbol_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detectar patrones de volumen"""
        opportunities = []
        
        symbol_data = symbol_data.reset_index(drop=True)
        
        # Calcular volumen promedio
        symbol_data['volume_avg'] = symbol_data['volume'].rolling(50).mean()
        symbol_data['volume_spike'] = symbol_data['volume'] / symbol_data['volume_avg']
        
        for i in range(50, len(symbol_data)):
            current = symbol_data.iloc[i]
            
            # Spike de volumen significativo
            if current['volume_spike'] > 3.0 and current['close_price'] > current['open_price']:
                
                opportunities.append({
                    'symbol': current['symbol'],
                    'pattern_type': 'volume_spike',
                    'current_price': current['close_price'],
                    'gap_percentage': ((current['close_price'] - current['open_price']) / current['open_price']) * 100,
                    'volume_ratio': current['volume_spike'],
                    'quality_score': min(100, current['volume_spike'] * 15),
                    'timestamp': current['bar_timestamp'].isoformat(),
                    'bars': self._get_bars_around(symbol_data, i, 25),
                    'catalyst_type': 'volume_surge',
                    'opportunity_id': f"{current['symbol']}_{current['bar_timestamp'].strftime('%Y%m%d_%H%M')}_vol",
                    'real_data': True
                })
        
        return opportunities

    def _detect_macd_patterns(self, symbol_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detectar señales MACD simplificadas"""
        opportunities = []
        
        # MACD simplificado sin dependencia de ta-lib
        symbol_data = symbol_data.reset_index(drop=True)
        
        # Calcular EMAs simples
        symbol_data['ema_12'] = symbol_data['close_price'].ewm(span=12).mean()
        symbol_data['ema_26'] = symbol_data['close_price'].ewm(span=26).mean()
        symbol_data['macd_line'] = symbol_data['ema_12'] - symbol_data['ema_26']
        symbol_data['signal_line'] = symbol_data['macd_line'].ewm(span=9).mean()
        
        for i in range(35, len(symbol_data)):
            current = symbol_data.iloc[i]
            prev = symbol_data.iloc[i-1]
            
            # Cruce alcista MACD
            if (prev['macd_line'] <= prev['signal_line'] and 
                current['macd_line'] > current['signal_line'] and
                current['volume'] > 25000):
                
                momentum = current['macd_line'] - current['signal_line']
                
                opportunities.append({
                    'symbol': current['symbol'],
                    'pattern_type': 'macd_signal',
                    'current_price': current['close_price'],
                    'gap_percentage': 0,  # MACD no tiene gap
                    'volume_ratio': current['volume'] / 100000,
                    'quality_score': min(100, 50 + momentum * 1000),
                    'timestamp': current['bar_timestamp'].isoformat(),
                    'bars': self._get_bars_around(symbol_data, i, 40),
                    'catalyst_type': 'technical_signal',
                    'opportunity_id': f"{current['symbol']}_{current['bar_timestamp'].strftime('%Y%m%d_%H%M')}_macd",
                    'real_data': True
                })
        
        return opportunities

    def _get_bars_around(self, symbol_data: pd.DataFrame, center_index: int, window: int) -> List[Dict[str, Any]]:
        """
        Obtener barras alrededor de un índice específico
        
        Args:
            symbol_data: DataFrame con datos
            center_index: Índice central
            window: Número de barras a cada lado
            
        Returns:
            Lista de barras OHLCV
        """
        start_idx = max(0, center_index - window)
        end_idx = min(len(symbol_data), center_index + window + 1)
        
        bars = []
        for i in range(start_idx, end_idx):
            row = symbol_data.iloc[i]
            bars.append({
                'timestamp': row['bar_timestamp'].isoformat(),
                'open': row['open_price'],
                'high': row['high_price'],
                'low': row['low_price'],
                'close': row['close_price'],
                'volume': row['volume'],
                'vwap': row.get('vwap', row['close_price'])
            })
        
        return bars

    def get_database_summary(self) -> Dict[str, Any]:
        """Obtener resumen de la base de datos"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Estadísticas generales
                query = """
                SELECT 
                    COUNT(*) as total_bars,
                    COUNT(DISTINCT symbol) as total_symbols,
                    COUNT(DISTINCT DATE(bar_timestamp)) as total_trading_days,
                    MIN(bar_timestamp) as first_timestamp,
                    MAX(bar_timestamp) as last_timestamp,
                    AVG(volume) as avg_volume,
                    MIN(close_price) as min_price,
                    MAX(close_price) as max_price
                FROM intraday_bars
                """
                
                result = pd.read_sql_query(query, conn).iloc[0]
                
                # Distribución por símbolo
                symbols_query = """
                SELECT symbol, COUNT(*) as bars
                FROM intraday_bars 
                GROUP BY symbol 
                ORDER BY bars DESC
                LIMIT 10
                """
                
                top_symbols = pd.read_sql_query(symbols_query, conn)
                
                return {
                    'total_bars': int(result['total_bars']),
                    'total_symbols': int(result['total_symbols']),
                    'total_trading_days': int(result['total_trading_days']),
                    'date_range': {
                        'first': result['first_timestamp'],
                        'last': result['last_timestamp']
                    },
                    'price_range': {
                        'min': result['min_price'],
                        'max': result['max_price']
                    },
                    'avg_volume': result['avg_volume'],
                    'top_symbols': top_symbols.to_dict('records')
                }
                
        except Exception as e:
            logger.error(f"Error generando resumen de DB: {e}")
            return {}


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)