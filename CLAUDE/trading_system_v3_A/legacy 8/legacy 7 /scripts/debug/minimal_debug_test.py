#!/usr/bin/env python3
"""
TEST MINIMALISTA - Solo 1 símbolo, parámetros ultra-permisivos
Para identificar exactamente dónde está fallando
"""

import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from backtesting import BacktestEngine, BacktestConfig, BacktestDataLoader
from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
from core.interfaces import MarketData

class MinimalTestStrategy(OptimizedGapGoStrategy):
    """Estrategia ULTRA-SIMPLIFICADA para debugging"""
    
    def __init__(self, parameters=None):
        # Parámetros MINIMALISTAS
        ultra_simple_params = {
            # Gap detection - MUY PERMISIVO
            'min_gap_percent': 0.1,          # 0.1% mínimo
            'auto_detect_gaps': True,
            'gap_percent_threshold': 0.1,
            'gap_confirmation_bars': 0,
            
            # Entry - SIN RESTRICCIONES
            'min_conditions_met': 0,         # Sin condiciones
            'momentum_confirmation': False,
            'volume_multiplier': 0.1,
            'min_volume': 1,
            
            # Risk - MUY PERMISIVO
            'stop_loss_pct': 0.5,            # 50% stop loss
            'take_profit_pct': 0.5,          # 50% take profit
            'max_position_value': 10000.0,
            'min_position_value': 10.0,
            
            # Timing - TODO EL DÍA
            'market_open_hour': 0.0,         # Todo el día
            'no_entry_after': 24.0,
            'max_hold_time': 1440,           # 24 horas
            
            # Anti-overtrading - DESACTIVADO
            'max_daily_trades': 100,
            'cooldown_period': 0,
            'max_concurrent_positions': 100,
            'daily_loss_limit': 100000.0,
            
            # Quality - SIN FILTROS
            'min_price': 0.01,
            'max_price': 10000.0,
            'min_daily_volume': 1,
            
            # Debug
            'debug_verbose': True
        }
        
        if parameters:
            ultra_simple_params.update(parameters)
        
        super().__init__(ultra_simple_params)
        
        # Contadores para debugging
        self.bars_processed = 0
        self.gaps_detected = 0
        self.signals_generated = 0
        self.entries_made = 0
        self.exits_made = 0
    
    async def on_bar(self, bar: MarketData):
        """Procesamiento con logging extensivo"""
        self.bars_processed += 1
        symbol = bar.symbol
        
        # Log progreso
        if self.bars_processed % 200 == 0:
            print(f"📊 Processed {self.bars_processed} bars")
            print(f"   Gaps detected: {self.gaps_detected}")
            print(f"   Signals generated: {self.signals_generated}")
            print(f"   Entries: {self.entries_made}, Exits: {self.exits_made}")
            print(f"   Active positions: {len(self.active_positions)}")
        
        # Verificar gaps antes
        gaps_before = len(self.scanner_gaps)
        
        # Llamar función original
        signal = await super().on_bar(bar)
        
        # Verificar gaps después
        gaps_after = len(self.scanner_gaps)
        if gaps_after > gaps_before:
            self.gaps_detected += 1
            gap_info = self.scanner_gaps.get(symbol, {})
            print(f"🟢 GAP DETECTED: {symbol} = {gap_info.get('gap_percent', 0):.1f}% at {bar.timestamp}")
        
        # Verificar señales
        if signal:
            self.signals_generated += 1
            
            if signal.metadata.get('is_entry', False):
                self.entries_made += 1
                print(f"🟢 ENTRY CREATED: {symbol} @ ${signal.price:.2f}")
            elif 'EXIT' in str(signal.signal_type):
                self.exits_made += 1
                print(f"🔴 EXIT CREATED: {symbol} @ ${signal.price:.2f}")
            else:
                print(f"🔵 SIGNAL CREATED: {symbol} - {signal.signal_type}")
        
        return signal
    
    def _auto_detect_gap(self, symbol: str, bar: MarketData) -> None:
        """Gap detection con logging extensivo"""
        try:
            # Log CADA LLAMADA para debugging
            if self.bars_processed % 50 == 0:  # Cada 50 barras
                print(f"🔍 Gap check: {symbol} at {bar.timestamp} (hour: {bar.timestamp.hour}, min: {bar.timestamp.minute})")
            
            current_hour = bar.timestamp.hour
            current_minute = bar.timestamp.minute
            
            # Guardar prev_close MÁS AGRESIVAMENTE
            if current_hour >= 15:  # Desde las 15:00
                old_close = self.prev_closes.get(symbol, 0)
                self.prev_closes[symbol] = bar.close
                if old_close != bar.close:
                    print(f"💾 PREV_CLOSE SAVED: {symbol} = ${bar.close:.2f} at {bar.timestamp}")
            
            # Buscar gaps TODO EL DÍA (no solo 9:30)
            if current_hour >= 9:  # Desde las 9:00
                if symbol in self.prev_closes and self.prev_closes[symbol] > 0:
                    prev_close = self.prev_closes[symbol]
                    gap_pct = (bar.open - prev_close) / prev_close * 100.0
                    
                    print(f"🔍 GAP CALCULATION: {symbol}")
                    print(f"   Open: ${bar.open:.2f}, Prev Close: ${prev_close:.2f}")
                    print(f"   Gap: {gap_pct:.2f}%, Threshold: {self._parameters.get('gap_percent_threshold', 0.1)}%")
                    
                    if abs(gap_pct) >= self._parameters.get('gap_percent_threshold', 0.1):
                        direction = 'up' if gap_pct > 0 else 'down'
                        
                        self.scanner_gaps[symbol] = {
                            'gap_percent': gap_pct,
                            'direction': direction,
                            'volume_ratio': 1.0,
                            'price': bar.open,
                            'timestamp': bar.timestamp,
                            'scanner_score': abs(gap_pct),
                            'confirmed': True,  # Auto-confirmar
                            'confirmation_bars': 1
                        }
                        
                        print(f"✅ GAP REGISTERED: {symbol} = {gap_pct:.1f}% ({direction})")
                        return
                    else:
                        if self.bars_processed % 100 == 0:  # Log periódico
                            print(f"   ⚪ Gap too small: {gap_pct:.2f}%")
                else:
                    if self.bars_processed % 100 == 0:
                        print(f"   ⚠️  No prev_close for {symbol}")
                        
        except Exception as e:
            print(f"❌ Gap detection error: {e}")
            import traceback
            traceback.print_exc()

async def minimal_debug_test():
    """Test ultra-minimalista con 1 símbolo"""
    print("🧪 MINIMAL DEBUG TEST - 1 SÍMBOLO")
    print("=" * 50)
    
    # Buscar archivos
    data_path = Path("data")
    csv_files = list(data_path.glob("*.csv"))
    
    if not csv_files:
        print("❌ No CSV files found")
        return
    
    # Usar solo el PRIMER archivo
    test_file = csv_files[0]
    symbol = test_file.stem.split('_')[0].upper()
    
    print(f"📊 Testing with: {symbol} from {test_file.name}")
    
    # Verificar datos básicos
    df = pd.read_csv(test_file)
    print(f"📈 Raw data: {len(df)} rows, columns: {list(df.columns)}")
    
    # Configuración minimalista
    config = BacktestConfig(
        initial_capital=10000,
        start_date=datetime(2025, 4, 1),
        end_date=datetime(2025, 4, 15),  # Solo 2 semanas
        commission_per_share=0.0,       # Sin comisiones
        slippage_bps=0,                 # Sin slippage
        simulation_mode=True
    )
    
    # Función de carga simple
    def simple_loader(symbol, start_date, end_date):
        df = pd.read_csv(test_file)
        df.columns = df.columns.str.lower()
        
        # Normalizar columnas de fecha
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'datetime' in df.columns:
            df['timestamp'] = pd.to_datetime(df['datetime'])
            df = df.drop('datetime', axis=1)
        else:
            df['timestamp'] = pd.to_datetime(df.index)
        
        df.set_index('timestamp', inplace=True)
        
        # Filtrar fechas
        mask = (df.index >= start_date) & (df.index <= end_date)
        filtered = df[mask]
        
        print(f"📊 Loaded {len(filtered)} bars for {symbol}")
        if len(filtered) > 0:
            print(f"   Range: {filtered.index[0]} to {filtered.index[-1]}")
            print(f"   Price: ${filtered['close'].min():.2f} - ${filtered['close'].max():.2f}")
        
        return filtered
    
    # Crear engine y estrategia
    engine = BacktestEngine(config)
    strategy = MinimalTestStrategy()
    
    engine.add_strategy(strategy)
    engine.set_data_loader(simple_loader)
    
    print(f"\n🚀 Starting minimal backtest...")
    
    try:
        # Ejecutar backtest
        results = await engine.run_backtest([symbol])
        
        print(f"\n📊 RESULTS:")
        print(f"   Bars processed: {strategy.bars_processed}")
        print(f"   Gaps detected: {strategy.gaps_detected}")
        print(f"   Signals generated: {strategy.signals_generated}")
        print(f"   Entries made: {strategy.entries_made}")
        print(f"   Exits made: {strategy.exits_made}")
        
        if results:
            print(f"   Final capital: ${results.final_capital:.2f}")
            print(f"   Total trades: {results.total_trades}")
            print(f"   Return: {results.total_return_pct:.2f}%")
        
        # Diagnóstico
        if strategy.bars_processed == 0:
            print("❌ NO BARS PROCESSED - Problem with data loading")
        elif strategy.gaps_detected == 0:
            print("⚠️  NO GAPS DETECTED - Gap detection not working")
        elif strategy.signals_generated == 0:
            print("⚠️  NO SIGNALS GENERATED - Entry conditions too strict")
        elif strategy.entries_made == 0:
            print("⚠️  NO ENTRIES MADE - Signal to trade conversion failing")
        else:
            print("✅ BASIC FUNCTIONALITY WORKING")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in backtest: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔬 MINIMAL DEBUG TEST")
    print("Ejecuta: python minimal_debug_test.py")
    print("Este test usará solo 1 símbolo con parámetros ultra-permisivos")
    
    asyncio.run(minimal_debug_test())
