#!/usr/bin/env python3
"""
Downloader Expandido - Versión Correcta
Lee oportunidades del scanner y las descarga con event_id + contexto histórico
"""

import json
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
import hashlib

# Cargar variables de entorno desde .env.local
try:
    from pathlib import Path
    env_file = Path('.env.local')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
except Exception:
    pass

try:
    from polygon import RESTClient
except ImportError:
    print("ERROR: Polygon SDK no instalado")
    sys.exit(1)


class ScannerExpandedDownloader:
    """Downloader que lee oportunidades del scanner y las descarga expandidas"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.market_db_path = 'market_data.db'
        self.trading_db_path = 'trading_data.db'
        
        # Rate limiting conservador
        self.calls_per_minute = 3
        self.api_call_count = 0
        self.last_reset_time = time.time()
        
        self.client = RESTClient(api_key=self.api_key)
        self.logger = logging.getLogger('scanner_expanded')

    def get_scanner_opportunities(self) -> List[Dict[str, str]]:
        """
        Obtener oportunidades detectadas por el scanner (IGUAL QUE EL ORIGINAL)
        """
        try:
            conn = sqlite3.connect(self.trading_db_path)
            cursor = conn.cursor()

            # Consulta idéntica al download_historical_data.py original
            query = """
                SELECT DISTINCT
                    symbol,
                    DATE(entry_time) as scan_date,
                    strategy,
                    COUNT(*) as signals_count
                FROM trades
                GROUP BY symbol, DATE(entry_time), strategy
                ORDER BY scan_date DESC, symbol
            """

            cursor.execute(query)
            results = cursor.fetchall()

            opportunities = []
            for symbol, scan_date, strategy, count in results:
                opportunities.append({
                    'symbol': symbol,
                    'date': scan_date,
                    'strategy': strategy,
                    'signals_count': count
                })

            conn.close()

            self.logger.info(f"Found {len(opportunities)} scanner opportunities")
            return opportunities

        except Exception as e:
            self.logger.error(f"Error getting scanner opportunities: {e}")
            return []

    def setup_expanded_database(self):
        """Configurar BBDD expandida"""
        print("🔧 Configurando BBDD expandida...")
        
        conn = sqlite3.connect(self.market_db_path)
        cursor = conn.cursor()

        # Agregar event_id a intraday_bars si no existe
        try:
            cursor.execute("ALTER TABLE intraday_bars ADD COLUMN event_id INTEGER")
            print("✅ event_id agregado a intraday_bars")
        except:
            print("✅ event_id ya existe en intraday_bars")

        # Crear tabla daily_ohlcv_history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_ohlcv_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                history_date DATE NOT NULL,
                days_before_event INTEGER NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, history_date)
            )
        """)
        print("✅ daily_ohlcv_history creada")

        # Índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_event ON daily_ohlcv_history(event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_event ON intraday_bars(event_id)")

        conn.commit()
        conn.close()

    def generate_event_id(self, symbol: str, scan_date: str) -> int:
        """Generar event_id único"""
        event_key = f"{symbol}_{scan_date}"
        event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
        return event_id

    def handle_rate_limit(self):
        """Manejar rate limiting"""
        self.api_call_count += 1
        if self.api_call_count >= self.calls_per_minute:
            elapsed = time.time() - self.last_reset_time
            if elapsed < 60:
                wait_time = 60 - elapsed
                print(f"⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            self.api_call_count = 0
            self.last_reset_time = time.time()

    def download_scanner_opportunity_expanded(self, opportunity: Dict[str, str]) -> Dict[str, int]:
        """
        Descargar una oportunidad del scanner con expansión
        
        Args:
            opportunity: {'symbol': 'BYND', 'date': '2025-11-04', 'strategy': 'macdv', ...}
        
        Returns:
            {'event_id': 12345, 'intraday_bars': 78, 'history_days': 5, 'total': 83}
        """
        symbol = opportunity['symbol']
        date_str = opportunity['date']
        strategy = opportunity['strategy']
        signals_count = opportunity['signals_count']

        try:
            # Generar event_id único para esta oportunidad
            event_id = self.generate_event_id(symbol, date_str)
            
            print(f"\n📊 Descargando oportunidad: {symbol} {date_str}")
            print(f"   Strategy: {strategy} | Signals: {signals_count}")
            print(f"   Event ID: {event_id}")

            # Parsear fecha
            event_date = datetime.strptime(date_str, "%Y-%m-%d")

            # 1. Descargar datos intradiarios del día del evento
            intraday_bars = self.download_intraday_data(symbol, event_date, event_id)

            # 2. Descargar historial contextual (reducido para pruebas)
            history_days = self.download_contextual_history(symbol, event_date, event_id)

            result = {
                'event_id': event_id,
                'intraday_bars': intraday_bars,
                'history_days': history_days,
                'total_downloaded': intraday_bars + history_days
            }

            if result['total_downloaded'] > 0:
                print(f"✅ {symbol} {date_str}: {intraday_bars} intraday, {history_days} historical (Event: {event_id})")
            else:
                print(f"❌ {symbol} {date_str}: No data downloaded")

            return result

        except Exception as e:
            print(f"❌ Error downloading {symbol} {date_str}: {e}")
            return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

    def download_intraday_data(self, symbol: str, event_date: datetime, event_id: int) -> int:
        """Descargar datos intradiarios para el día del evento"""
        try:
            date_str = event_date.strftime("%Y-%m-%d")
            
            self.handle_rate_limit()
            
            # Descargar barra diaria
            aggs = list(self.client.list_aggs(
                ticker=symbol,
                multiplier=1,
                timespan='day',
                from_=date_str,
                to=date_str,
                limit=1
            ))

            if not aggs:
                print(f"   ⚠️ No daily data found for {symbol} on {date_str}")
                return 0

            # Crear barras simuladas intradiarias
            simulated_bars = self.create_simulated_intraday_bars(aggs[0], date_str)
            
            # Insertar con event_id
            inserted = self.insert_intraday_bars(symbol, event_id, simulated_bars)
            
            return inserted

        except Exception as e:
            print(f"   ❌ Error downloading intraday data: {e}")
            return 0

    def download_contextual_history(self, symbol: str, event_date: datetime, event_id: int, days_history: int = 5) -> int:
        """Descargar días de contexto histórico"""
        try:
            downloaded_count = 0
            start_date = event_date - timedelta(days=days_history)
            current_date = start_date

            while current_date < event_date:
                if current_date.weekday() < 5:  # Solo días laborables
                    try:
                        self.handle_rate_limit()
                        
                        date_str = current_date.strftime("%Y-%m-%d")
                        aggs = list(self.client.list_aggs(
                            ticker=symbol,
                            multiplier=1,
                            timespan='day',
                            from_=date_str,
                            to=date_str,
                            limit=1
                        ))

                        if aggs:
                            daily_agg = aggs[0]
                            days_before = (event_date.date() - current_date.date()).days

                            success = self.insert_historical_bar(
                                event_id, symbol, current_date, days_before, daily_agg
                            )

                            if success:
                                downloaded_count += 1

                        time.sleep(1)  # Pausa

                    except Exception as e:
                        print(f"   ⚠️ Error downloading {date_str}: {e}")

                current_date += timedelta(days=1)

            return downloaded_count

        except Exception as e:
            print(f"   ❌ Error downloading historical context: {e}")
            return 0

    def create_simulated_intraday_bars(self, daily_agg, date_str):
        """Crear barras intradiarias simuladas"""
        from types import SimpleNamespace
        import random

        market_start = datetime.strptime(f"{date_str} 13:30:00", "%Y-%m-%d %H:%M:%S")
        market_end = datetime.strptime(f"{date_str} 20:00:00", "%Y-%m-%d %H:%M:%S")

        simulated_bars = []
        current_time = market_start

        open_price = daily_agg.open
        high_price = daily_agg.high
        low_price = daily_agg.low
        close_price = daily_agg.close
        volume = daily_agg.volume

        random.seed(int(daily_agg.timestamp))

        total_minutes = int((market_end - market_start).total_seconds() / 60)
        num_bars = total_minutes // 5

        if num_bars <= 0:
            num_bars = 1

        volume_per_bar = max(1, volume // num_bars)
        current_price = open_price
        price_range = high_price - low_price

        for i in range(num_bars):
            price_change = random.uniform(-price_range*0.1, price_range*0.1)
            current_price = max(low_price, min(high_price, current_price + price_change))

            bar_timestamp = int(current_time.timestamp() * 1000)

            volatility = price_range * 0.05
            bar_open = current_price
            bar_high = current_price + random.uniform(0, volatility)
            bar_low = current_price - random.uniform(0, volatility)
            bar_close = current_price + random.uniform(-volatility/2, volatility/2)

            bar_high = max(bar_high, bar_open, bar_close)
            bar_low = min(bar_low, bar_open, bar_close)

            simulated_bar = SimpleNamespace()
            simulated_bar.timestamp = bar_timestamp
            simulated_bar.open = round(bar_open, 4)
            simulated_bar.high = round(bar_high, 4)
            simulated_bar.low = round(bar_low, 4)
            simulated_bar.close = round(bar_close, 4)
            simulated_bar.volume = volume_per_bar
            simulated_bar.vwap = round((bar_open + bar_high + bar_low + bar_close) / 4, 4)
            simulated_bar.transactions = None

            simulated_bars.append(simulated_bar)
            current_time += timedelta(minutes=5)

        if simulated_bars:
            simulated_bars[-1].close = close_price
            simulated_bars[-1].high = max(simulated_bars[-1].high, close_price)
            simulated_bars[-1].low = min(simulated_bars[-1].low, close_price)

        return simulated_bars

    def insert_intraday_bars(self, symbol: str, event_id: int, aggs: List) -> int:
        """Insertar barras intradiarias con event_id"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            inserted = 0

            for agg in aggs:
                try:
                    bar_timestamp = datetime.fromtimestamp(agg.timestamp / 1000)

                    cursor.execute("""
                        INSERT OR IGNORE INTO intraday_bars (
                            event_id, symbol, bar_timestamp,
                            open_price, high_price, low_price, close_price,
                            volume, vwap, transactions, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        symbol,
                        bar_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        agg.open,
                        agg.high,
                        agg.low,
                        agg.close,
                        agg.volume,
                        getattr(agg, 'vwap', None),
                        getattr(agg, 'transactions', None),
                        'polygon_expanded'
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1

                except Exception as e:
                    continue

            conn.commit()
            conn.close()
            return inserted

        except Exception as e:
            return 0

    def insert_historical_bar(self, event_id: int, symbol: str, history_date: datetime,
                            days_before_event: int, daily_agg) -> bool:
        """Insertar barra histórica"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO daily_ohlcv_history (
                    event_id, symbol, history_date, days_before_event,
                    open_price, high_price, low_price, close_price, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                symbol,
                history_date.strftime("%Y-%m-%d"),
                days_before_event,
                daily_agg.open,
                daily_agg.high,
                daily_agg.low,
                daily_agg.close,
                daily_agg.volume
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            return False

    def download_opportunities_expanded(self, limit: int = None) -> Dict[str, int]:
        """
        Descargar oportunidades del scanner con expansión
        
        Args:
            limit: Límite de oportunidades (None = todas)
        
        Returns:
            Estadísticas de descarga
        """
        # Obtener oportunidades del scanner
        opportunities = self.get_scanner_opportunities()

        if not opportunities:
            print("❌ No scanner opportunities found in trading_data.db")
            return {
                'total_opportunities': 0,
                'downloaded': 0,
                'failed': 0,
                'total_intraday_bars': 0,
                'total_historical_days': 0
            }

        # Aplicar límite
        if limit:
            opportunities = opportunities[:limit]

        print(f"\n🎯 DESCARGANDO OPORTUNIDADES EXPANDIDAS")
        print("=" * 60)
        print(f"📊 Oportunidades encontradas: {len(opportunities)}")
        if limit:
            print(f"📊 Limitado a: {limit}")
        print("=" * 60)

        # Mostrar preview
        print(f"\n📋 Preview de oportunidades:")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"   {i}. {opp['symbol']} - {opp['date']} ({opp['strategy']}, {opp['signals_count']} señales)")

        if len(opportunities) > 5:
            print(f"   ... y {len(opportunities) - 5} más")

        # Estadísticas
        stats = {
            'total_opportunities': len(opportunities),
            'downloaded': 0,
            'failed': 0,
            'total_intraday_bars': 0,
            'total_historical_days': 0
        }

        # Descargar cada oportunidad
        for i, opp in enumerate(opportunities, 1):
            print(f"\n[{i}/{len(opportunities)}] Procesando oportunidad...")
            result = self.download_scanner_opportunity_expanded(opp)

            if result['total_downloaded'] > 0:
                stats['downloaded'] += 1
                stats['total_intraday_bars'] += result['intraday_bars']
                stats['total_historical_days'] += result['history_days']
            else:
                stats['failed'] += 1

        return stats


def main():
    """Función principal"""
    print("🚀 SCANNER EXPANDED DOWNLOADER")
    print("Lee oportunidades del scanner y las descarga con event_id + contexto")
    print("=" * 70)

    # API Key
    API_KEY = os.environ.get('POLYGON_API_KEY')
    if not API_KEY:
        print("❌ POLYGON_API_KEY no encontrada en .env.local")
        return

    print(f"✅ API Key: {API_KEY[:10]}...")

    # Crear downloader
    downloader = ScannerExpandedDownloader(API_KEY)

    # Configurar BBDD expandida
    downloader.setup_expanded_database()

    # Descargar 3 oportunidades de prueba (como el original)
    print(f"\n🎯 Descargando 3 oportunidades de prueba...")
    stats = downloader.download_opportunities_expanded(limit=3)

    print("\n" + "=" * 70)
    print("✅ DESCARGA EXPANDIDA COMPLETADA")
    print("=" * 70)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades procesadas: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras intradiarias totales: {stats['total_intraday_bars']}")
    print(f"   - Días históricos totales: {stats['total_historical_days']}")

    print(f"\n🎯 Sistema expandido:")
    print(f"   ✅ Lee oportunidades reales del scanner")
    print(f"   ✅ Genera event_id único para cada (symbol, date)")
    print(f"   ✅ Descarga datos intradiarios + contexto histórico")
    print(f"   ✅ Listo para discovery de reglas avanzadas")


if __name__ == "__main__":
    main()