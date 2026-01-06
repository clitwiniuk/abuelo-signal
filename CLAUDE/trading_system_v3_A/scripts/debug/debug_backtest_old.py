#!/usr/bin/env python3
"""
Script de diagnóstico para depurar el backtest - VERSIÓN CORREGIDA
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import glob

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from backtesting import (
    BacktestEngine, BacktestConfig, BacktestDataLoader
)
from strategies.macdv_strategy import MACDVStrategy
from backtests.backtest_config import (
    BacktestConfigurations,
    StrategyConfigurations
)
from core.interfaces import Signal, Order, Position, SignalType, MarketData
from core.risk_manager import RiskManager


def setup_logging():
    """Configurar logging detallado para diagnóstico"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('debug_backtest.log')
        ]
    )


class DiagnosticMonitor:
    def __init__(self):
        self.signals_generated = 0
        self.signals_validated = 0
        self.signals_rejected = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        
    def reset(self):
        self.signals_generated = 0
        self.signals_validated = 0
        self.signals_rejected = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        
    def print_summary(self):
        print("\n📊 RESUMEN DE DIAGNÓSTICO:")
        print(f"Señales generadas: {self.signals_generated}")
        print(f"Señales validadas: {self.signals_validated}")
        print(f"Señales rechazadas: {self.signals_rejected}")
        print(f"Operaciones ejecutadas: {self.trades_executed}")
        print(f"Operaciones rechazadas: {self.trades_rejected}")


def find_symbol_files(symbol: str, data_path: str = "data") -> list:
    """Buscar archivos de datos para un símbolo específico"""
    data_dir = Path(data_path)
    
    patterns = [
        f"{symbol}*.csv",
        f"{symbol}*.parquet",
        f"*{symbol}*.csv",
        f"*{symbol}*.parquet"
    ]
    
    files = []
    for pattern in patterns:
        files.extend(list(data_dir.glob(pattern)))
    
    return [str(f) for f in files]


def load_symbol_data_directly(symbol: str, data_path: str = "data") -> pd.DataFrame:
    """Cargar datos directamente desde archivos sin usar BacktestDataLoader"""
    print(f"\n📈 Cargando datos directamente para {symbol}...")
    
    # Buscar archivos
    files = find_symbol_files(symbol, data_path)
    
    if not files:
        print(f"❌ No se encontraron archivos para {symbol}")
        return pd.DataFrame()
    
    print(f"✅ Encontrados {len(files)} archivos para {symbol}")
    
    # Cargar el primer archivo encontrado
    file_path = files[0]
    print(f"📁 Cargando archivo: {file_path}")
    
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.parquet'):
            df = pd.read_parquet(file_path)
        else:
            print(f"❌ Formato de archivo no soportado: {file_path}")
            return pd.DataFrame()
        
        # Verificar columnas esperadas
        expected_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns.str.lower() for col in expected_columns):
            print(f"❌ Columnas faltantes en {file_path}")
            print(f"Columnas encontradas: {list(df.columns)}")
            return pd.DataFrame()
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.lower()
        
        # Configurar índice de tiempo si no está configurado
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
        elif not isinstance(df.index, pd.DatetimeIndex):
            print(f"❌ No se pudo identificar columna de tiempo en {file_path}")
            return pd.DataFrame()
        
        print(f"✅ Datos cargados: {len(df)} barras")
        print(f"   Rango de fechas: {df.index[0]} a {df.index[-1]}")
        print(f"   Columnas: {list(df.columns)}")
        
        # Mostrar primeras filas
        print("\nPrimeras 3 filas:")
        print(df.head(3))
        
        return df
        
    except Exception as e:
        print(f"❌ Error cargando {file_path}: {e}")
        return pd.DataFrame()


async def debug_backtest():
    """Ejecutar backtest en modo diagnóstico con carga directa de datos"""
    print("\n" + "=" * 60)
    print("🔍 DIAGNÓSTICO DE BACKTEST - MACDV STRATEGY (VERSIÓN CORREGIDA)")
    print("=" * 60)
    
    monitor = DiagnosticMonitor()
    
    # Verificar archivos de datos disponibles
    data_path = Path("data")
    if not data_path.exists():
        print("❌ Directorio 'data' no encontrado")
        return
    
    print(f"📁 Verificando archivos en: {data_path.absolute()}")
    
    # Listar archivos disponibles
    csv_files = list(data_path.glob("*.csv"))
    parquet_files = list(data_path.glob("*.parquet"))
    
    print(f"✅ Archivos CSV encontrados: {len(csv_files)}")
    print(f"✅ Archivos Parquet encontrados: {len(parquet_files)}")
    
    if not csv_files and not parquet_files:
        print("❌ No se encontraron archivos de datos")
        return
    
    # Mostrar algunos archivos
    all_files = csv_files + parquet_files
    print(f"\nPrimeros 5 archivos:")
    for i, file in enumerate(all_files[:5]):
        print(f"  {i+1}. {file.name}")
    
    # Extraer símbolos de los nombres de archivos
    symbols = set()
    for file in all_files:
        # Asumir que el símbolo está al principio del nombre del archivo
        symbol = file.name.split('_')[0].split('.')[0]
        symbols.add(symbol)
    
    symbols = sorted(list(symbols))
    print(f"\n✅ Símbolos identificados: {symbols[:10]}...")
    
    # Usar solo los primeros 2 símbolos para diagnóstico
    available_symbols = symbols[:2]
    print(f"\n🔬 Usando símbolos para diagnóstico: {available_symbols}")
    
    # Configuración para diagnóstico
    config = BacktestConfigurations.get_default_1min_config()
    
    # Ajustar fechas - usar un rango más amplio
    config.start_date = datetime(2024, 1, 1)
    config.end_date = datetime(2024, 12, 31)
    config.simulation_mode = True
    
    # Parámetros de estrategia más permisivos
    strategy_params = StrategyConfigurations.get_macdv_default_5min()
    strategy_params['volume_threshold'] = 0.5
    strategy_params['min_conditions'] = 1
    strategy_params['rsi_confirmation'] = False
    strategy_params['adx_confirmation'] = False
    strategy_params['bb_confirmation'] = False
    
    print(f"\n📊 Configuración de diagnóstico:")
    print(f"   Período: {config.start_date.strftime('%Y-%m-%d')} a {config.end_date.strftime('%Y-%m-%d')}")
    print(f"   Capital inicial: ${config.initial_capital:,}")
    print(f"   Modo simulación: {config.simulation_mode}")
    
    # Función de carga de datos personalizada
    def debug_data_loader(symbol, start_date, end_date):
        df = load_symbol_data_directly(symbol, "data")
        
        if df.empty:
            print(f"❌ No se pudieron cargar datos para {symbol}")
            return df
        
        # Filtrar por rango de fechas
        mask = (df.index >= start_date) & (df.index <= end_date)
        filtered_df = df[mask]
        
        if filtered_df.empty:
            print(f"❌ No hay datos para {symbol} en el rango {start_date} a {end_date}")
            print(f"   Rango disponible: {df.index[0]} a {df.index[-1]}")
            # Usar los últimos 1000 registros si no hay datos en el rango
            filtered_df = df.tail(1000)
            print(f"   Usando últimos {len(filtered_df)} registros para prueba")
        else:
            print(f"✅ {len(filtered_df)} barras en rango de fechas")
        
        return filtered_df
    
    # Crear estrategia con diagnóstico
    class DiagnosticStrategy(MACDVStrategy):
        async def on_bar(self, bar: MarketData):
            signal = await super().on_bar(bar)
            if signal:
                print(f"\n🔔 Señal generada: {bar.symbol} {signal.signal_type.value} a ${bar.close:.2f}")
                monitor.signals_generated += 1
            return signal
    
    # Crear y configurar engine
    engine = BacktestEngine(config)
    strategy = DiagnosticStrategy(strategy_params)
    
    engine.add_strategy(strategy)
    engine.set_data_loader(debug_data_loader)
    
    try:
        print(f"\n⚡ Ejecutando backtest de diagnóstico...")
        results = await engine.run_backtest(available_symbols)
        
        monitor.print_summary()
        
        print(f"\n📈 RESULTADOS DEL DIAGNÓSTICO:")
        print("-" * 40)
        
        if results:
            print(f"Capital final: ${results.final_capital:,.2f}")
            print(f"Retorno total: {results.total_return_pct:.2f}%")
            print(f"Total trades: {results.total_trades}")
            
            if results.total_trades > 0:
                print(f"Win Rate: {results.win_rate:.2f}%")
                print("✅ Backtest ejecutado exitosamente")
            else:
                print("\n❌ No se generaron operaciones")
                print("Posibles causas:")
                print("- Parámetros de estrategia muy restrictivos")
                print("- Datos insuficientes o de mala calidad")
                print("- Condiciones de mercado no favorables")
        else:
            print("❌ No se obtuvieron resultados del backtest")
        
        return results
        
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        setup_logging()
        print("\n🔍 Iniciando diagnóstico de backtest (versión corregida)...")
        asyncio.run(debug_backtest())
        
    except KeyboardInterrupt:
        print("\n\n👋 Diagnóstico interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)