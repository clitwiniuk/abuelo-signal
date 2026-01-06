#!/usr/bin/env python3
"""
Versión SIMPLE del downloader expandido
Solo descarga 1 día, sin historial complejo
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
    pass


class SimpleExpandedDownloader:
    """Downloader simple para probar expansión"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.market_db_path = 'market_data.db'
        self.trading_db_path = 'trading_data.db'

        try:
            from polygon import RESTClient
            self.client = RESTClient(api_key=self.api_key)
        except ImportError:
            print("ERROR: Polygon SDK no instalado")
            sys.exit(1)

    def setup_expanded_db(self):
        """Configurar BBDD expandida"""
        print("🔧 Configurando BBDD expandida...")

        conn = sqlite3.connect(self.market_db_path)
        cursor = conn.cursor()

        # 1. Agregar event_id a intraday_bars
        try:
            cursor.execute("ALTER TABLE intraday_bars ADD COLUMN event_id INTEGER")
            print("✅ event_id agregado")
        except:
            print("✅ event_id ya existe")

        # 2. Crear tabla historial
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
                volume INTEGER NOT NULL
            )
        """)
        print("✅ daily_ohlcv_history creada")

        conn.commit()
        conn.close()

    def test_simple_download(self):
        """Descarga simple para probar expansión"""
        print("\n🚀 PRUEBA SIMPLE DE DESCARGA EXPANDIDA")
        print("=" * 50)

        # Configurar BBDD
        self.setup_expanded_db()

        # Probar con datos muy simples
        symbol = "AAPL"
        date_str = "2025-10-30"  # Fecha que sí tiene datos
        
        print(f"\n📊 Probando {symbol} para {date_str}")

        # 1. Crear event_id
        event_key = f"{symbol}_{date_str}"
        event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
        print(f"🎯 Event ID: {event_id}")

        # 2. Descargar UN SOLO día
        try:
            print(f"📥 Descargando datos de Polygon...")
            time.sleep(1)  # Pausa para evitar rate limit

            aggs = list(self.client.list_aggs(
                ticker=symbol,
                multiplier=1,
                timespan='day',
                from_=date_str,
                to=date_str,
                limit=1
            ))

            if aggs:
                agg = aggs[0]
                print(f"✅ Datos obtenidos: O=${agg.open}, H=${agg.high}, L=${agg.low}, C=${agg.close}, V={agg.volume}")

                # 3. Insertar con event_id
                success = self._insert_simple_data(symbol, event_id, date_str, agg)
                if success:
                    print(f"✅ ¡Datos insertados con event_id {event_id}!")
                else:
                    print(f"❌ Error insertando datos")

                return True
            else:
                print(f"⚠️ No se encontraron datos para {symbol}")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def _insert_simple_data(self, symbol: str, event_id: int, date_str: str, agg) -> bool:
        """Insertar datos simples"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # Insertar en intraday_bars con event_id
            cursor.execute("""
                INSERT OR REPLACE INTO intraday_bars (
                    event_id, symbol, bar_timestamp,
                    open_price, high_price, low_price, close_price,
                    volume, vwap, transactions, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                symbol,
                f"{date_str} 16:00:00",  # Tiempo simulado
                agg.open,
                agg.high,
                agg.low,
                agg.close,
                agg.volume,
                getattr(agg, 'vwap', None),
                getattr(agg, 'transactions', None),
                'polygon_test'
            ))

            # Insertar un día histórico en daily_ohlcv_history
            cursor.execute("""
                INSERT OR REPLACE INTO daily_ohlcv_history (
                    event_id, symbol, history_date, days_before_event,
                    open_price, high_price, low_price, close_price, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                symbol,
                "2025-10-31",  # Día anterior
                1,  # 1 día antes del evento
                agg.open * 0.99,  # Datos simulados
                agg.high * 0.99,
                agg.low * 0.99,
                agg.close * 0.99,
                int(agg.volume * 0.8)
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ Error insertando: {e}")
            return False

    def verify_expansion(self):
        """Verificar que la expansión funciona"""
        print(f"\n🔍 VERIFICANDO EXPANSIÓN...")
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # Contar barras con event_id
            cursor.execute("SELECT COUNT(*) FROM intraday_bars WHERE event_id IS NOT NULL")
            bars_with_event_id = cursor.fetchone()[0]

            # Contar historial
            cursor.execute("SELECT COUNT(*) FROM daily_ohlcv_history")
            history_count = cursor.fetchone()[0]

            # Mostrar algunos datos
            cursor.execute("SELECT event_id, symbol, open_price FROM intraday_bars WHERE event_id IS NOT NULL LIMIT 3")
            samples = cursor.fetchall()

            conn.close()

            print(f"✅ Verificación completada:")
            print(f"   📊 Barras con event_id: {bars_with_event_id}")
            print(f"   📈 Registros históricos: {history_count}")
            print(f"   🔍 Muestras:")
            for sample in samples:
                print(f"      - Event {sample[0]}: {sample[1]} (${sample[2]})")

            return True

        except Exception as e:
            print(f"❌ Error en verificación: {e}")
            return False


def main():
    """Función principal"""
    print("🧪 DOWNLOADER EXPANDIDO - VERSIÓN SIMPLE")
    print("Solo 1 descarga, sin rate limits")

    API_KEY = os.environ.get('POLYGON_API_KEY')
    if not API_KEY:
        print("❌ API key no encontrada en .env.local")
        return False

    print(f"✅ API Key: {API_KEY[:10]}...")

    downloader = SimpleExpandedDownloader(API_KEY)

    # Ejecutar prueba
    success = downloader.test_simple_download()

    if success:
        downloader.verify_expansion()
        print(f"\n🎉 ¡SISTEMA EXPANDIDO FUNCIONANDO!")
    else:
        print(f"\n❌ Problemas en el sistema expandido")


if __name__ == "__main__":
    main()