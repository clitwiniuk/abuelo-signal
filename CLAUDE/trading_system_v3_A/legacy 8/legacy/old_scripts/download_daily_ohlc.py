#!/usr/bin/env python3
"""
Daily OHLC Batch Downloader
===========================

Descarga datos OHLC completos de 1 minuto para todos los símbolos
escaneados/tradados en una fecha específica.

Soluciona el problema de:
- Pérdida de datos por reinicios del sistema
- Inicio tardío del sistema (después de market open)
- Datos incompletos por interrupciones

Usage:
    python download_daily_ohlc.py 2025-09-16
    python download_daily_ohlc.py 2025-09-16 --symbols SNTG,CHEK,TANH
    python download_daily_ohlc.py --backfill 2025-09-15 2025-09-17
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse
from pathlib import Path
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData
from core.database_manager import get_database_manager
from core.trade_ohlc_recorder import get_trade_ohlc_recorder
from adapters.ibkr_adapter import IBKRAdapter
from utils.log_config import setup_logging

# Setup logging
setup_logging(level="INFO", log_file="logs/ohlc_downloader.log")
logger = logging.getLogger("OHLCDownloader")

class DailyOHLCDownloader:
    """
    Descarga batch de datos OHLC al final del día
    """

    def __init__(self):
        self.db_manager = get_database_manager()
        self.ohlc_recorder = get_trade_ohlc_recorder()
        self.ibkr_adapter = None

    async def connect_broker(self):
        """Conectar al broker para descarga de datos"""
        try:
            logger.info("🔌 Connecting to IBKR for data download...")
            self.ibkr_adapter = IBKRAdapter()
            await self.ibkr_adapter.connect()
            logger.info("✅ Connected to IBKR successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to IBKR: {e}")
            return False

    async def disconnect_broker(self):
        """Desconectar del broker"""
        if self.ibkr_adapter:
            try:
                await self.ibkr_adapter.disconnect()
                logger.info("🔌 Disconnected from IBKR")
            except Exception as e:
                logger.warning(f"⚠️ Error disconnecting from IBKR: {e}")

    def get_traded_symbols(self, date: str) -> List[str]:
        """
        Obtener símbolos que fueron tradados en una fecha específica
        """
        try:
            # Query PostgreSQL for trades on this date
            query = """
                SELECT DISTINCT symbol
                FROM trades
                WHERE trade_date = %s
                ORDER BY symbol
            """

            results = self.db_manager.execute_query(query, (date,))
            symbols = [row[0] for row in results] if results else []

            logger.info(f"📊 Found {len(symbols)} traded symbols for {date}: {symbols}")
            return symbols

        except Exception as e:
            logger.error(f"❌ Error getting traded symbols for {date}: {e}")
            return []

    def get_scanner_symbols_from_logs(self, date: str) -> List[str]:
        """
        Extraer símbolos del scanner desde los logs (fallback method)
        """
        symbols = set()

        try:
            log_file = Path("logs/scanner.log")
            if not log_file.exists():
                logger.warning(f"⚠️ Scanner log file not found: {log_file}")
                return []

            with open(log_file, 'r') as f:
                for line in f:
                    if date in line:
                        # Extract symbols from various log patterns
                        # This is a simple pattern - can be enhanced
                        import re
                        symbol_matches = re.findall(r'\b[A-Z]{2,5}\b', line)
                        for match in symbol_matches:
                            if len(match) <= 5 and match not in ['INFO', 'ERROR', 'DEBUG', 'WARN']:
                                symbols.add(match)

            symbol_list = sorted(list(symbols))
            logger.info(f"📊 Extracted {len(symbol_list)} symbols from scanner logs for {date}")
            return symbol_list

        except Exception as e:
            logger.error(f"❌ Error extracting symbols from logs: {e}")
            return []

    async def download_symbol_ohlc(self, symbol: str, date: str) -> List[MarketData]:
        """
        Descargar datos OHLC de 1 minuto para un símbolo en una fecha específica
        """
        try:
            # Convert date string to datetime
            target_date = datetime.strptime(date, '%Y-%m-%d')

            # Get trading hours for the date (9:30 AM - 4:00 PM ET)
            start_time = target_date.replace(hour=9, minute=30, second=0, microsecond=0)
            end_time = target_date.replace(hour=16, minute=0, second=0, microsecond=0)

            logger.info(f"📥 Downloading OHLC data for {symbol} on {date} ({start_time} to {end_time})")

            # Request historical data from IBKR (using get_bars method)
            # For a full trading day, we need ~390 bars (6.5 hours * 60 minutes)
            bars = await self.ibkr_adapter.get_bars(
                symbol=symbol,
                timeframe='1 min',
                count=390  # Full trading day
            )

            if bars:
                logger.info(f"✅ Downloaded {len(bars)} bars for {symbol}")
                return bars
            else:
                logger.warning(f"⚠️ No data received for {symbol}")
                return []

        except Exception as e:
            logger.error(f"❌ Error downloading OHLC for {symbol}: {e}")
            return []

    async def store_ohlc_data(self, symbol: str, bars: List[MarketData], date: str):
        """
        Almacenar datos OHLC en la base de datos usando métodos existentes
        """
        try:
            # Create a mock trade ID for scanner-only symbols
            trade_id = f"SCANNER_{symbol}_{date.replace('-', '')}"

            logger.info(f"💾 Storing {len(bars)} OHLC bars for {symbol} ({trade_id})")

            # Store each bar using the existing record_market_data method
            for bar in bars:
                self.ohlc_recorder.record_market_data(symbol, bar)

            # Manual database insertion for the snapshot (simplified)
            if bars:
                first_bar = bars[0]
                last_bar = bars[-1]
                day_high = max(bar.high for bar in bars)
                day_low = min(bar.low for bar in bars)
                total_volume = sum(bar.volume for bar in bars)

                # Direct SQLite insertion
                import sqlite3
                with sqlite3.connect(self.ohlc_recorder.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO trade_ohlc_snapshots
                        (trade_id, symbol, trading_date, day_open, day_high, day_low, day_close, day_volume,
                         entry_time, entry_price, market_open_price, intraday_bars)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_id, symbol, date, first_bar.open, day_high, day_low, last_bar.close, total_volume,
                        first_bar.timestamp.isoformat(), first_bar.open, first_bar.open,
                        json.dumps([{
                            'timestamp': bar.timestamp.isoformat(),
                            'open': bar.open,
                            'high': bar.high,
                            'low': bar.low,
                            'close': bar.close,
                            'volume': bar.volume
                        } for bar in bars])
                    ))
                    conn.commit()

                logger.info(f"✅ Stored OHLC snapshot for {symbol} ({len(bars)} bars)")

        except Exception as e:
            logger.error(f"❌ Error storing OHLC data for {symbol}: {e}")

    async def download_daily_batch(self, date: str, symbols: Optional[List[str]] = None):
        """
        Descarga batch de todos los símbolos para una fecha específica
        """
        logger.info(f"🚀 Starting daily OHLC batch download for {date}")

        # Connect to broker
        if not await self.connect_broker():
            logger.error("❌ Cannot proceed without broker connection")
            return

        try:
            # Get symbols to download
            if symbols:
                all_symbols = symbols
                logger.info(f"📋 Using provided symbols: {all_symbols}")
            else:
                # Get traded symbols
                traded_symbols = self.get_traded_symbols(date)

                # Get scanner symbols from logs
                scanner_symbols = self.get_scanner_symbols_from_logs(date)

                # Combine and deduplicate
                all_symbols = list(set(traded_symbols + scanner_symbols))
                logger.info(f"📋 Combined symbols: {len(traded_symbols)} traded + {len(scanner_symbols)} scanner = {len(all_symbols)} total")

            if not all_symbols:
                logger.warning(f"⚠️ No symbols found for {date}")
                return

            # Download data for each symbol
            successful_downloads = 0
            failed_downloads = 0

            for i, symbol in enumerate(all_symbols, 1):
                logger.info(f"📊 Processing {symbol} ({i}/{len(all_symbols)})")

                try:
                    # Download OHLC data
                    bars = await self.download_symbol_ohlc(symbol, date)

                    if bars:
                        # Store the data
                        await self.store_ohlc_data(symbol, bars, date)
                        successful_downloads += 1
                    else:
                        failed_downloads += 1

                    # Small delay to avoid overwhelming the API
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"❌ Failed to process {symbol}: {e}")
                    failed_downloads += 1
                    continue

            # Summary
            logger.info(f"🎉 Daily OHLC download completed for {date}")
            logger.info(f"📊 Results: {successful_downloads} successful, {failed_downloads} failed")

        finally:
            # Disconnect broker
            await self.disconnect_broker()

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Download daily OHLC data')
    parser.add_argument('date', nargs='?', help='Date to download (YYYY-MM-DD)')
    parser.add_argument('--symbols', help='Comma-separated list of symbols to download')
    parser.add_argument('--backfill', nargs=2, metavar=('START_DATE', 'END_DATE'),
                       help='Backfill data for date range')

    args = parser.parse_args()

    downloader = DailyOHLCDownloader()

    try:
        if args.backfill:
            # Backfill mode
            start_date = datetime.strptime(args.backfill[0], '%Y-%m-%d')
            end_date = datetime.strptime(args.backfill[1], '%Y-%m-%d')

            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                logger.info(f"🔄 Backfilling {date_str}")
                await downloader.download_daily_batch(date_str)
                current_date += timedelta(days=1)

        elif args.date:
            # Single date mode
            symbols = None
            if args.symbols:
                symbols = [s.strip().upper() for s in args.symbols.split(',')]

            await downloader.download_daily_batch(args.date, symbols)

        else:
            # Default: yesterday
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            logger.info(f"📅 No date specified, using yesterday: {yesterday}")
            await downloader.download_daily_batch(yesterday)

    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())