#!/usr/bin/env python3
"""
End-of-Day OHLC Downloader
===========================
Descarga datos OHLC de 1 minuto para todos los símbolos operados en el día.
Se ejecuta automáticamente a las 22:00 hora española (16:00 ET, después del cierre).

Proceso:
1. Obtiene todos los símbolos operados hoy desde trading_data.db
2. Descarga barras de 1 minuto desde market open hasta close
3. Guarda en trade_ohlc_snapshots y trade_intraday_bars
4. Genera reporte de éxito/fallos
"""

import sys
import os
import sqlite3
import logging
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Set
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.ibkr_adapter import IBKRAdapter
from core.interfaces import MarketData
from utils.log_config import setup_logging


class EODOHLCDownloader:
    """Descargador de datos OHLC al final del día con extended hours"""

    def __init__(self, db_path: str = None, update_all: bool = False, target_date: str = None):
        self.db_path = db_path or str(project_root / "trading_data.db")
        self.logger = logging.getLogger("EODOHLCDownloader")
        self.ibkr = None
        self.phase = None  # 'phase1' (pre-close) or 'phase2' (post-close) or 'bulk_update'
        self.target_date = target_date  # Specific date to download data for
        self.update_all = update_all  # If True, download data for ALL historical trades
        self.bulk_dates = []  # List of dates to process in bulk update
        self.stats = {
            'total_symbols': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'phase': None,
            'target_date': None,
            'bulk_update': False,
            'total_dates': 0,
            'processed_dates': 0
        }

    async def initialize(self):
        """Inicializar conexión IBKR"""
        try:
            # Usar client_id diferente para no interferir con trader
            self.ibkr = IBKRAdapter(
                host="127.0.0.1",
                port=7497,  # Paper trading
                client_id=9999  # ID único para este script
            )
            await self.ibkr.connect()
            self.logger.info("✅ IBKR connected for EOD download")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to IBKR: {e}")
            return False

    async def cleanup(self):
        """Limpiar recursos"""
        if self.ibkr:
            await self.ibkr.disconnect()
            self.logger.info("✅ IBKR disconnected")

    def determine_execution_phase(self):
        """
        Determinar fase de ejecución basada en parámetros y hora actual
        FASE 1: Antes del cierre (15:50 ET / 21:50 España) - descarga datos del día anterior
        FASE 2: Después del cierre (22:00 España / 16:00 ET) - descarga datos del día actual
        BULK_UPDATE: Actualización masiva de todos los trades históricos
        """
        if self.update_all:
            # BULK UPDATE MODE: Process all historical trades
            self.phase = 'bulk_update'
            self.bulk_dates = self._get_all_trading_dates()
            self.stats['bulk_update'] = True
            self.stats['total_dates'] = len(self.bulk_dates)
            self.logger.info(f"📊 BULK UPDATE MODE: Processing {len(self.bulk_dates)} trading dates")
            for i, dt in enumerate(self.bulk_dates[:5]):  # Show first 5 dates
                self.logger.info(f"   • {dt}")
            if len(self.bulk_dates) > 5:
                self.logger.info(f"   ... and {len(self.bulk_dates) - 5} more dates")

        elif self.target_date:
            # SPECIFIC DATE MODE: Process only the specified date
            self.phase = 'specific_date'
            self.logger.info(f"🎯 SPECIFIC DATE MODE: Processing data for {self.target_date}")

        else:
            # NORMAL PHASE MODE: Based on current time
            now = datetime.now()
            current_hour = now.hour

            # FASE 1: Antes del cierre del mercado (antes de las 22:00 España = 16:00 ET)
            if current_hour < 22:
                self.phase = 'phase1'
                self.target_date = (date.today() - timedelta(days=1)).isoformat()  # Día anterior
                self.logger.info(f"🏃 FASE 1: Pre-close execution - downloading data for {self.target_date}")
            else:
                # FASE 2: Después del cierre (22:00 España en adelante)
                self.phase = 'phase2'
                self.target_date = date.today().isoformat()  # Día actual
                self.logger.info(f"🌙 FASE 2: Post-close execution - downloading data for {self.target_date}")

        self.stats['phase'] = self.phase
        self.stats['target_date'] = self.target_date

    def _get_all_trading_dates(self) -> List[str]:
        """
        Obtener todas las fechas únicas donde hubo trades
        Returns: Lista ordenada de fechas en formato YYYY-MM-DD
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all unique trading dates from trades
            query = """
                SELECT DISTINCT date(entry_time) as trade_date
                FROM trades
                WHERE entry_time IS NOT NULL
                ORDER BY trade_date DESC
            """
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            dates = [row[0] for row in results if row[0]]

            # Filter to last 30 days (IBKR limitation)
            cutoff_date = (date.today() - timedelta(days=30)).isoformat()
            recent_dates = [d for d in dates if d >= cutoff_date]

            self.logger.info(f"📅 Found {len(dates)} total trading dates, {len(recent_dates)} within last 30 days")
            return recent_dates

        except Exception as e:
            self.logger.error(f"❌ Error getting trading dates: {e}")
            return []

    def get_target_date_symbols(self, target_date: str = None) -> List[Tuple[str, str]]:
        """
        Obtener todos los símbolos operados en la fecha objetivo

        Args:
            target_date: Fecha específica (opcional, usa self.target_date si no se especifica)

        Returns:
            List of (symbol, trade_id) tuples
        """
        date_to_use = target_date or self.target_date

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all trades from target date (both entry and exit dates)
            query = """
                SELECT DISTINCT symbol, trade_id
                FROM trades
                WHERE date(entry_time) = ? OR date(exit_time) = ?
                ORDER BY symbol
            """
            cursor.execute(query, (date_to_use, date_to_use))
            results = cursor.fetchall()

            conn.close()

            if self.phase == 'bulk_update':
                self.logger.debug(f"📊 Found {len(results)} symbols traded on {date_to_use}")
            else:
                phase_desc = "yesterday" if self.phase == 'phase1' else "today"
                self.logger.info(f"📊 Found {len(results)} symbols traded {phase_desc} ({date_to_use})")
            return results

        except Exception as e:
            self.logger.error(f"❌ Error getting target date symbols for {date_to_use}: {e}")
            return []

    async def download_symbol_ohlc(self, symbol: str, trade_id: str) -> bool:
        """
        Descargar datos OHLC de 1 minuto para un símbolo con extended hours

        Args:
            symbol: Símbolo a descargar
            trade_id: ID del trade para asociar datos

        Returns:
            bool: True si exitoso
        """
        try:
            self.logger.info(f"📥 Downloading extended OHLC data for {symbol} (Phase: {self.phase})...")

            # Obtener barras de 1 minuto para el día completo CON EXTENDED HOURS
            # Extended hours: 4:00 AM - 8:00 PM ET = 960 minutos (16 horas)
            bars = await self.ibkr.get_bars(
                symbol=symbol,
                timeframe="1 min",  # Corrected format for IBKRAdapter
                count=960  # Full day with extended hours (4:00 AM - 8:00 PM ET)
                # Note: useRTH parameter removed - handled internally by IBKRAdapter
            )

            if not bars or len(bars) == 0:
                self.logger.warning(f"⚠️  No data received for {symbol}")
                return False

            self.logger.info(f"✅ Downloaded {len(bars)} bars for {symbol} (extended hours)")

            # Guardar en base de datos (INSERT OR REPLACE - no genera duplicados)
            self._save_ohlc_data(symbol, trade_id, bars)

            return True

        except Exception as e:
            self.logger.error(f"❌ Error downloading {symbol}: {e}")
            self.stats['errors'].append(f"{symbol}: {str(e)}")
            return False

    def _save_ohlc_data(self, symbol: str, trade_id: str, bars: List[MarketData]):
        """
        Guardar datos OHLC extendidos en la base de datos (INSERT OR REPLACE - no duplicados)

        Args:
            symbol: Símbolo
            trade_id: ID del trade
            bars: Lista de barras OHLC con extended hours
        """
        if not bars:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calcular datos del día (extended hours)
            trading_date = bars[0].timestamp.date().isoformat()
            day_open = bars[0].open
            day_high = max(bar.high for bar in bars)
            day_low = min(bar.low for bar in bars)
            day_close = bars[-1].close
            day_volume = sum(bar.volume for bar in bars)

            # Obtener trade details
            cursor.execute("""
                SELECT entry_time, entry_price, exit_time, exit_price
                FROM trades
                WHERE trade_id = ?
            """, (trade_id,))
            trade_data = cursor.fetchone()

            if not trade_data:
                self.logger.warning(f"⚠️  Trade {trade_id} not found in database")
                conn.close()
                return

            entry_time, entry_price, exit_time, exit_price = trade_data

            # Find entry and exit bars (ahora con extended hours data)
            entry_bar = self._find_closest_bar(bars, entry_time)
            exit_bar = self._find_closest_bar(bars, exit_time) if exit_time else None

            # Convertir barras a JSON para almacenar (extended hours)
            import json
            intraday_bars_json = json.dumps([{
                'timestamp': bar.timestamp.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'session': self._classify_bar_session(bar.timestamp)  # Nueva clasificación
            } for bar in bars])

            entry_bar_json = json.dumps({
                'open': entry_bar.open,
                'high': entry_bar.high,
                'low': entry_bar.low,
                'close': entry_bar.close,
                'volume': entry_bar.volume,
                'session': self._classify_bar_session(entry_bar.timestamp)
            }) if entry_bar else None

            exit_bar_json = json.dumps({
                'open': exit_bar.open,
                'high': exit_bar.high,
                'low': exit_bar.low,
                'close': exit_bar.close,
                'volume': exit_bar.volume,
                'session': self._classify_bar_session(exit_bar.timestamp)
            }) if exit_bar else None

            # Insert or replace snapshot (EXTENDED HOURS)
            cursor.execute("""
                INSERT OR REPLACE INTO trade_ohlc_snapshots (
                    trade_id, symbol, trading_date,
                    day_open, day_high, day_low, day_close, day_volume,
                    entry_time, entry_price, entry_bar,
                    exit_time, exit_price, exit_bar,
                    intraday_bars, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                trade_id, symbol, trading_date,
                day_open, day_high, day_low, day_close, day_volume,
                entry_time, entry_price, entry_bar_json,
                exit_time, exit_price, exit_bar_json,
                intraday_bars_json
            ))

            # Insert individual bars into trade_intraday_bars (INSERT OR REPLACE - no duplicados)
            for i, bar in enumerate(bars):
                is_entry = (entry_bar and abs((bar.timestamp - entry_bar.timestamp).total_seconds()) < 60)
                is_exit = (exit_bar and abs((bar.timestamp - exit_bar.timestamp).total_seconds()) < 60)
                session = self._classify_bar_session(bar.timestamp)

                cursor.execute("""
                    INSERT OR REPLACE INTO trade_intraday_bars (
                        trade_id, bar_timestamp, timeframe,
                        open_price, high_price, low_price, close_price, volume,
                        bar_sequence, is_entry_bar, is_exit_bar, session_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id, bar.timestamp, '1min',
                    bar.open, bar.high, bar.low, bar.close, bar.volume,
                    i, is_entry, is_exit, session
                ))

            conn.commit()
            conn.close()

            self.logger.info(f"✅ Saved {len(bars)} extended bars for {symbol} (trade {trade_id[:8]}...) - Phase: {self.phase}")

        except Exception as e:
            self.logger.error(f"❌ Error saving extended OHLC data for {symbol}: {e}")
            if conn:
                conn.close()

    def _classify_bar_session(self, timestamp) -> str:
        """
        Clasificar la sesión de mercado de una barra
        """
        hour = timestamp.hour
        minute = timestamp.minute

        if hour < 9 or (hour == 9 and minute < 30):
            return 'premarket'
        elif hour < 16 or (hour == 16 and minute == 0):
            return 'regular'
        else:
            return 'afterhours'

    def _find_closest_bar(self, bars: List[MarketData], target_time: str) -> MarketData:
        """Encontrar la barra más cercana a un timestamp"""
        if not bars or not target_time:
            return None

        try:
            if isinstance(target_time, str):
                # Handle both naive and aware datetimes
                if target_time.endswith('Z'):
                    target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
                else:
                    target_dt = datetime.fromisoformat(target_time)
            else:
                target_dt = target_time

            # Ensure target_dt is naive (remove timezone info if present)
            if hasattr(target_dt, 'tzinfo') and target_dt.tzinfo is not None:
                target_dt = target_dt.replace(tzinfo=None)

            # Find closest bar, handling timezone differences
            closest_bar = None
            min_diff = float('inf')

            for bar in bars:
                bar_time = bar.timestamp
                # Make bar timestamp naive if it's aware
                if hasattr(bar_time, 'tzinfo') and bar_time.tzinfo is not None:
                    bar_time = bar_time.replace(tzinfo=None)

                diff = abs((bar_time - target_dt).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_bar = bar

            return closest_bar

        except Exception as e:
            self.logger.error(f"Error finding closest bar: {e}")
            return bars[0] if bars else None

    async def run(self):
        """Ejecutar descarga completa EOD con extended hours"""
        self.logger.info("=" * 60)
        if self.update_all:
            self.logger.info("🔄 BULK UPDATE MODE: UPDATING ALL HISTORICAL TRADES")
        else:
            self.logger.info("🌅 END-OF-DAY OHLC DOWNLOAD (EXTENDED HOURS) STARTED")
        self.logger.info(f"📅 Current Date: {date.today().isoformat()}")
        self.logger.info(f"⏰ Current Time: {datetime.now().strftime('%H:%M:%S')}")

        # Determinar fase de ejecución
        self.determine_execution_phase()
        self.logger.info(f"🎯 Phase: {self.phase.upper()}")
        if self.phase == 'bulk_update':
            self.logger.info(f"📊 Total Dates to Process: {len(self.bulk_dates)}")
        else:
            self.logger.info(f"📅 Target Date: {self.target_date}")
        self.logger.info("=" * 60)

        # Initialize IBKR
        if not await self.initialize():
            self.logger.error("❌ Failed to initialize. Exiting.")
            return False

        if self.phase == 'bulk_update':
            # BULK UPDATE MODE: Process all dates
            return await self._run_bulk_update()
        else:
            # NORMAL MODE: Process single date
            return await self._run_single_date()

    async def _run_bulk_update(self):
        """Ejecutar actualización masiva de todas las fechas históricas"""
        self.logger.info("🚀 Starting bulk update of all historical trades...")

        total_symbols_processed = 0
        total_successful = 0
        total_failed = 0

        for i, target_date in enumerate(self.bulk_dates):
            self.stats['processed_dates'] = i + 1
            self.logger.info(f"\n📅 Processing date {i+1}/{len(self.bulk_dates)}: {target_date}")

            # Get symbols for this specific date
            symbols = self.get_target_date_symbols(target_date)

            if not symbols:
                self.logger.info(f"⚠️  No symbols traded on {target_date}, skipping...")
                continue

            self.logger.info(f"📊 Processing {len(symbols)} symbols for {target_date}")

            # Process symbols for this date
            date_successful = 0
            date_failed = 0

            for symbol, trade_id in symbols:
                success = await self.download_symbol_ohlc(symbol, trade_id)
                if success:
                    date_successful += 1
                    total_successful += 1
                else:
                    date_failed += 1
                    total_failed += 1

                total_symbols_processed += 1

                # Progress logging every 10 symbols
                if total_symbols_processed % 10 == 0:
                    self.logger.info(f"📈 Progress: {total_symbols_processed} symbols processed, "
                                   f"{total_successful} successful, {total_failed} failed")

                # Small delay to avoid rate limiting
                await asyncio.sleep(1)

            self.logger.info(f"✅ Date {target_date} completed: {date_successful}/{date_successful + date_failed} symbols")

            # Longer delay between dates to avoid rate limiting
            if i < len(self.bulk_dates) - 1:  # Don't delay after last date
                await asyncio.sleep(5)

        # Cleanup
        await self.cleanup()

        # Final summary
        self.logger.info("=" * 60)
        self.logger.info("🎉 BULK UPDATE COMPLETED!")
        self.logger.info(f"📅 Dates Processed: {len(self.bulk_dates)}")
        self.logger.info(f"📊 Total Symbols: {total_symbols_processed}")
        self.logger.info(f"✅ Successful: {total_successful}")
        self.logger.info(f"❌ Failed: {total_failed}")
        self.logger.info(f"📈 Success Rate: {(total_successful / max(total_symbols_processed, 1) * 100):.1f}%")

        if self.stats['errors']:
            self.logger.info(f"\n🚨 Total Errors: {len(self.stats['errors'])}")
            # Show last 5 errors
            for error in self.stats['errors'][-5:]:
                self.logger.info(f"   • {error}")

        self.logger.info("=" * 60)

        return total_failed == 0

    async def _run_single_date(self):
        """Ejecutar descarga para una sola fecha (modo normal)"""
        # Get symbols to download for target date
        symbols = self.get_target_date_symbols()
        self.stats['total_symbols'] = len(symbols)

        if not symbols:
            phase_desc = "yesterday" if self.phase == 'phase1' else "today"
            self.logger.warning(f"⚠️  No symbols traded {phase_desc}. Nothing to download.")
            await self.cleanup()
            return True

        # Download extended OHLC for each symbol
        for symbol, trade_id in symbols:
            success = await self.download_symbol_ohlc(symbol, trade_id)
            if success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(1)

        # Cleanup
        await self.cleanup()

        # Print summary
        self.logger.info("=" * 60)
        self.logger.info("📊 DOWNLOAD SUMMARY (EXTENDED HOURS)")
        self.logger.info(f"🎯 Phase: {self.phase.upper()}")
        self.logger.info(f"📅 Target Date: {self.target_date}")
        self.logger.info(f"✅ Successful: {self.stats['successful']}/{self.stats['total_symbols']}")
        self.logger.info(f"❌ Failed: {self.stats['failed']}/{self.stats['total_symbols']}")

        if self.stats['errors']:
            self.logger.info("\n🚨 Errors:")
            for error in self.stats['errors']:
                self.logger.info(f"   • {error}")

        self.logger.info("=" * 60)

        return self.stats['failed'] == 0


async def main():
    """Main function"""
    setup_logging(level="INFO", log_file="logs/ohlc_downloader.log")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download EOD OHLC data with extended hours')
    parser.add_argument('--update-all', action='store_true',
                       help='Update all historical trades (last 30 days)')
    parser.add_argument('--target-date', type=str,
                       help='Specific date to download data for (YYYY-MM-DD format)')
    parser.add_argument('--db-path', type=str,
                       help='Path to trading database file')

    args = parser.parse_args()

    # Create downloader with arguments
    downloader = EODOHLCDownloader(
        db_path=args.db_path,
        update_all=args.update_all,
        target_date=args.target_date
    )

    success = await downloader.run()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
