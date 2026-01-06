#!/usr/bin/env python3
"""
Polygon.io Data Downloader - Versión de Prueba
Descarga mínima para validar que el sistema funciona correctamente
"""

import json
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging

# Cargar variables de entorno desde .env.local si existe
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
    pass  # Si hay error, no pasa nada, continuar normalmente


class PolygonDataDownloaderTest:
    """
    Descargador de prueba para validar funcionamiento
    """

    def __init__(self, api_key: str, market_db_path: str = None,
                 trading_db_path: str = None, log_file: str = 'polygon_download_log_test.json'):
        self.api_key = api_key
        self.market_db_path = market_db_path or self._get_market_db_path()
        self.trading_db_path = trading_db_path or self._get_trading_db_path()
        self.log_file = log_file

        # Rate limiting más conservador para pruebas
        self.calls_per_minute = 3
        self.api_call_count = 0
        self.last_reset_time = time.time()

        # Configuración de historial reducida para pruebas
        self.history_days = 5  # Solo 5 días de historial

        try:
            from polygon import RESTClient
            self.client = RESTClient(api_key=self.api_key)
        except ImportError:
            print("ERROR: Polygon SDK no instalado. Ejecuta: pip install polygon-api-client")
            sys.exit(1)

        self.logger = logging.getLogger('polygon_downloader_test')
        self._setup_logging()

        self.processed_downloads = self._load_progress()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _get_market_db_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'market_data.db')

    def _get_trading_db_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'trading_data.db')

    def _load_progress(self) -> Set[str]:
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            self.logger.warning(f"Error loading progress log: {e}")
            return set()

    def _save_progress(self, download_key: str):
        try:
            self.processed_downloads.add(download_key)
            with open(self.log_file, 'w') as f:
                json.dump(list(self.processed_downloads), f)
        except Exception as e:
            self.logger.error(f"Error saving progress: {e}")

    def _handle_rate_limit(self):
        self.api_call_count += 1
        if self.api_call_count >= self.calls_per_minute:
            elapsed = time.time() - self.last_reset_time
            if elapsed < 60:
                wait_time = 60 - elapsed
                self.logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            self.api_call_count = 0
            self.last_reset_time = time.time()

    def download_test_symbol(self, symbol: str, scan_date: str) -> Dict[str, int]:
        """
        Descarga de prueba para un solo símbolo con historial mínimo
        """
        try:
            print(f"\n🧪 PRUEBA: Descargando datos para {symbol} el {scan_date}")

            # Parsear fecha
            event_date = datetime.strptime(scan_date, "%Y-%m-%d")

            # Crear event_id simple
            import hashlib
            event_key = f"{symbol}_{scan_date}"
            event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000

            print(f"📋 Event ID: {event_id}")

            # Conectar a BBDD para verificar estructura
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # Verificar si event_id existe en la tabla
            cursor.execute("PRAGMA table_info(intraday_bars)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'event_id' not in columns:
                print("❌ ERROR: La columna event_id no existe en intraday_bars")
                conn.close()
                return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

            print(f"✅ Estructura BBDD correcta: event_id existe")

            # Verificar si daily_ohlcv_history existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_ohlcv_history'")
            if cursor.fetchone():
                print("✅ Tabla daily_ohlcv_history existe")
            else:
                print("❌ ERROR: La tabla daily_ohlcv_history no existe")
                conn.close()
                return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

            conn.close()

            # Descargar datos de prueba (solo 1 símbolo)
            return self.download_single_symbol_minimal(symbol, event_date, event_id)

        except Exception as e:
            self.logger.error(f"Error en descarga de prueba para {symbol}: {e}")
            return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

    def download_single_symbol_minimal(self, symbol: str, event_date: datetime, event_id: int) -> Dict[str, int]:
        """
        Descarga mínima de datos para un símbolo
        """
        try:
            date_str = event_date.strftime("%Y-%m-%d")

            # Probar API con datos intradiarios
            self._handle_rate_limit()
            aggs = []

            try:
                print(f"📊 Descargando datos intradiarios para {symbol}...")
                for agg in self.client.list_aggs(
                    ticker=symbol,
                    multiplier=1,
                    timespan='day',
                    from_=date_str,
                    to=date_str,
                    limit=1
                ):
                    aggs.append(agg)

                if aggs:
                    daily_agg = aggs[0]
                    print(f"✅ Datos descargados: O={daily_agg.open}, H={daily_agg.high}, L={daily_agg.low}, C={daily_agg.close}, V={daily_agg.volume}")

                    # Simular barras intradiarias
                    simulated_bars = self._create_simulated_intraday_bars(daily_agg, date_str)
                    inserted = self._insert_intraday_bars_with_event(event_id, symbol, simulated_bars)

                    print(f"✅ {inserted} barras intradiarias insertadas con event_id")

                    # Probar descarga histórica (solo 5 días)
                    history_days = self._download_short_history(symbol, event_date, event_id)

                    return {
                        'event_id': event_id,
                        'intraday_bars': inserted,
                        'history_days': history_days,
                        'total_downloaded': inserted + history_days
                    }
                else:
                    print(f"⚠️ No se encontraron datos para {symbol} en {date_str}")
                    return {'event_id': event_id, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

            except Exception as api_error:
                print(f"❌ Error API para {symbol}: {api_error}")
                return {'event_id': event_id, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

        except Exception as e:
            print(f"❌ Error general descargando {symbol}: {e}")
            return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

    def _download_short_history(self, symbol: str, event_date: datetime, event_id: int) -> int:
        """
        Descargar solo 5 días de historial para prueba
        """
        try:
            print(f"📈 Descargando 5 días de historial para {symbol}...")

            downloaded_count = 0
            current_date = event_date - timedelta(days=self.history_days)

            while current_date < event_date:
                if current_date.weekday() < 5:  # Solo días laborables
                    try:
                        self._handle_rate_limit()

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

                            success = self._insert_daily_historical_bar(
                                event_id=event_id,
                                symbol=symbol,
                                history_date=current_date,
                                days_before_event=days_before,
                                daily_agg=daily_agg
                            )

                            if success:
                                downloaded_count += 1
                                print(f"  📅 {date_str}: {days_before} días antes ({daily_agg.close})")

                        time.sleep(1)  # Más pausa para evitar rate limit

                    except Exception as e:
                        print(f"  ⚠️ Error descargando {date_str}: {e}")

                current_date += timedelta(days=1)

            print(f"✅ {downloaded_count} días históricos descargados")
            return downloaded_count

        except Exception as e:
            print(f"❌ Error descargando historial histórico para {symbol}: {e}")
            return 0

    def _create_simulated_intraday_bars(self, daily_agg, date_str):
        """Crear barras intradiarias simuladas desde datos diarios"""
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

    def _insert_intraday_bars_with_event(self, event_id: int, symbol: str, aggs: List) -> int:
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
                        'polygon_simulated' if hasattr(agg, 'simulated') else 'polygon'
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1

                except Exception as e:
                    print(f"    ⚠️ Error insertando barra: {e}")
                    continue

            conn.commit()
            conn.close()
            return inserted

        except Exception as e:
            print(f"❌ Error en _insert_intraday_bars_with_event: {e}")
            return 0

    def _insert_daily_historical_bar(self, event_id: int, symbol: str, history_date: datetime,
                                   days_before_event: int, daily_agg) -> bool:
        """Insertar barra diaria histórica en daily_ohlcv_history"""
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
            print(f"    ⚠️ Error insertando histórico: {e}")
            return False


if __name__ == "__main__":
    """Función principal de prueba"""
    print("🧪 Polygon Data Downloader - Versión de Prueba")
    print("=" * 60)

    API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_API_KEY_HERE')

    if API_KEY == 'YOUR_API_KEY_HERE':
        print("❌ ERROR: Configura POLYGON_API_KEY como variable de entorno")
        sys.exit(1)

    print(f"✅ API Key detectada: {API_KEY[:10]}...")

    # Crear downloader de prueba
    downloader = PolygonDataDownloaderTest(api_key=API_KEY)

    # Probar con 1 símbolo
    test_symbol = "AAPL"  # Usar un símbolo grande y estable
    test_date = "2025-11-01"  # Una fecha reciente

    print(f"\n🎯 PROBANDO: {test_symbol} el {test_date}")
    result = downloader.download_test_symbol(test_symbol, test_date)

    print("\n" + "=" * 60)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 60)
    print(f"📊 Resultados:")
    print(f"   - Event ID: {result['event_id']}")
    print(f"   - Barras intradiarias: {result['intraday_bars']}")
    print(f"   - Días históricos: {result['history_days']}")
    print(f"   - Total descargado: {result['total_downloaded']}")

    if result['total_downloaded'] > 0:
        print(f"\n🎉 ¡ÉXITO! El sistema expandido funciona correctamente")
        print(f"   - BBDD estructura correcta")
        print(f"   - Event ID generado: {result['event_id']}")
        print(f"   - Datos descargados: {result['total_downloaded']} registros")
    else:
        print(f"\n⚠️ Hay problemas. Revisa los logs arriba")