#!/usr/bin/env python3
"""
FASE 1: Backtesting Simple para Optimización de Parámetros
Prueba 5 configuraciones diferentes en XXII para encontrar la óptima
"""

import asyncio
import sys
from pathlib import Path
import configparser
import tempfile
import shutil
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

class SimpleBacktest:
    """Simple backtesting for parameter optimization"""
    
    def __init__(self):
        self.original_config = 'config.ini'
        self.backup_config = 'config.ini.backup'
        
    async def test_config(self, config_name: str, params: dict, symbol: str = "XXII", bars: int = 1000):
        """Test a specific parameter configuration"""
        
        print(f"\n🔬 TESTING CONFIG: {config_name}")
        print(f"📋 Parameters: {params}")
        print("-" * 60)
        
        # Update config temporarily
        self._update_testing_config(params)
        
        try:
            # Initialize components
            broker = MockIBKRAdapter()
            data_provider = CSVDataProvider()
            event_bus = AsyncEventBus()
            
            await broker.connect()
            await data_provider.connect()
            
            # Broker is already fresh after connect
            
            # Create multi-strategy engine
            engine = MultiStrategyEngine()
            await engine.initialize(event_bus)
            
            # Get data
            bars_data = await data_provider.get_bars(symbol, "1 min", bars)
            if not bars_data:
                return {"error": "No data available"}
            
            print(f"📊 Processing {len(bars_data)} bars for {symbol}")
            
            signals_count = 0
            trades_count = 0
            
            # Process bars
            for i, bar in enumerate(bars_data):
                signal = await engine.on_bar(bar)
                
                if signal:
                    signals_count += 1
                    print(f"   ✅ Signal {signals_count} at bar {i+1}: {signal.signal_type} @ ${bar.close:.2f}")
                    
                    # Simple trade execution for backtesting
                    if hasattr(signal, 'signal_type') and 'LONG' in str(signal.signal_type):
                        # Calculate position size
                        position_value = 300  # $300 per trade
                        quantity = int(position_value / bar.close)
                        
                        # Execute trade
                        order = await broker.place_order(symbol, quantity, 'BUY', 'MKT')
                        if order:
                            trades_count += 1
                            
                            # Simple exit after 20 bars (for backtesting)
                            if i + 20 < len(bars_data):
                                exit_bar = bars_data[i + 20]
                                exit_order = await broker.place_order(symbol, quantity, 'SELL', 'MKT')
                                if exit_order:
                                    pnl = (exit_bar.close - bar.close) * quantity
                                    print(f"     💰 Trade {trades_count}: ${bar.close:.2f} → ${exit_bar.close:.2f} = ${pnl:.2f}")
            
            # Get final portfolio stats
            portfolio_stats = {}
            try:
                if hasattr(broker, 'portfolio_value'):
                    portfolio_stats['portfolio_value'] = broker.portfolio_value
                if hasattr(broker, 'total_pnl'):
                    portfolio_stats['total_pnl'] = broker.total_pnl
                if hasattr(broker, 'trades_executed'):
                    portfolio_stats['trades_executed'] = broker.trades_executed
            except:
                pass
            
            await broker.disconnect()
            await data_provider.disconnect()
            
            result = {
                "config_name": config_name,
                "signals_generated": signals_count,
                "trades_executed": trades_count,
                "portfolio_stats": portfolio_stats,
                "params": params
            }
            
            print(f"📊 Results: {signals_count} signals, {trades_count} trades")
            return result
            
        except Exception as e:
            print(f"❌ Error in {config_name}: {e}")
            return {"error": str(e), "config_name": config_name}
        finally:
            # Restore original config
            self._restore_config()
    
    def _update_testing_config(self, params: dict):
        """Update TESTING_PROFILE in config.ini"""
        
        # Backup original
        shutil.copy(self.original_config, self.backup_config)
        
        # Read and update config
        config = configparser.ConfigParser()
        config.read(self.original_config)
        
        # Update TESTING_PROFILE section
        for key, value in params.items():
            config.set('TESTING_PROFILE', key, str(value))
        
        # Write back
        with open(self.original_config, 'w') as f:
            config.write(f)
    
    def _restore_config(self):
        """Restore original config"""
        if Path(self.backup_config).exists():
            shutil.move(self.backup_config, self.original_config)
    
    async def run_optimization(self):
        """Run parameter optimization with 5 different configurations"""
        
        print("🚀 FASE 1: BACKTESTING SIMPLE - OPTIMIZACIÓN DE PARÁMETROS")
        print("=" * 70)
        print("🎯 Objetivo: Encontrar configuración que genere más trades en XXII")
        print("📊 Método: Prueba de 5 configuraciones diferentes")
        print("⏱️  Tiempo estimado: 5-10 minutos")
        
        # Define 5 test configurations
        configs = {
            "ULTRA_PERMISSIVE": {
                "macdv_volume_threshold": 0.1,
                "macdv_volume_spike_threshold": 0.2,
                "macdv_min_conditions": 1,
                "gap_go_min_gap_percent": 1.0,
                "gap_go_volume_multiplier": 0.2,
                "orb_volume_spike_threshold": 0.1,
                "orb_min_conditions": 1,
                "pmh_min_premarket_volume": 1000,
                "pmh_breakout_volume_multiplier": 0.1,
                "multi_strategy_default_confidence_threshold": 0.1
            },
            
            "VERY_PERMISSIVE": {
                "macdv_volume_threshold": 0.3,
                "macdv_volume_spike_threshold": 0.5,
                "macdv_min_conditions": 2,
                "gap_go_min_gap_percent": 1.5,
                "gap_go_volume_multiplier": 0.5,
                "orb_volume_spike_threshold": 0.3,
                "orb_min_conditions": 2,
                "pmh_min_premarket_volume": 5000,
                "pmh_breakout_volume_multiplier": 0.3,
                "multi_strategy_default_confidence_threshold": 0.2
            },
            
            "MODERATE": {
                "macdv_volume_threshold": 0.6,
                "macdv_volume_spike_threshold": 1.0,
                "macdv_min_conditions": 2,
                "gap_go_min_gap_percent": 2.0,
                "gap_go_volume_multiplier": 1.0,
                "orb_volume_spike_threshold": 0.8,
                "orb_min_conditions": 3,
                "pmh_min_premarket_volume": 15000,
                "pmh_breakout_volume_multiplier": 1.0,
                "multi_strategy_default_confidence_threshold": 0.3
            },
            
            "CURRENT_OPTIMIZED": {
                "macdv_volume_threshold": 1.0,
                "macdv_volume_spike_threshold": 1.5,
                "macdv_min_conditions": 3,
                "gap_go_min_gap_percent": 2.5,
                "gap_go_volume_multiplier": 1.5,
                "orb_volume_spike_threshold": 1.2,
                "orb_min_conditions": 4,
                "pmh_min_premarket_volume": 25000,
                "pmh_breakout_volume_multiplier": 1.8,
                "multi_strategy_default_confidence_threshold": 0.45
            },
            
            "CONSERVATIVE_TEST": {
                "macdv_volume_threshold": 1.5,
                "macdv_volume_spike_threshold": 2.0,
                "macdv_min_conditions": 4,
                "gap_go_min_gap_percent": 3.0,
                "gap_go_volume_multiplier": 2.0,
                "orb_volume_spike_threshold": 1.8,
                "orb_min_conditions": 5,
                "pmh_min_premarket_volume": 50000,
                "pmh_breakout_volume_multiplier": 2.5,
                "multi_strategy_default_confidence_threshold": 0.6
            }
        }
        
        # Run tests
        results = []
        
        for config_name, params in configs.items():
            result = await self.test_config(config_name, params)
            results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Analyze results
        self._analyze_results(results)
        
        return results
    
    def _analyze_results(self, results):
        """Analyze and rank the results"""
        
        print("\n" + "=" * 70)
        print("📊 ANÁLISIS DE RESULTADOS - FASE 1")
        print("=" * 70)
        
        # Filter valid results
        valid_results = [r for r in results if "error" not in r]
        
        if not valid_results:
            print("❌ No se obtuvieron resultados válidos")
            return
        
        # Sort by trades executed (primary) and signals (secondary)
        sorted_results = sorted(valid_results, 
                               key=lambda x: (x['trades_executed'], x['signals_generated']), 
                               reverse=True)
        
        # Display results table
        print(f"{'Rank':<4} {'Config':<18} {'Trades':<8} {'Signals':<8} {'Key Metrics'}")
        print("-" * 70)
        
        for i, result in enumerate(sorted_results):
            config_name = result['config_name']
            trades = result['trades_executed']
            signals = result['signals_generated']
            
            # Key metrics from params
            params = result['params']
            vol_threshold = params['macdv_volume_threshold']
            confidence = params['multi_strategy_default_confidence_threshold']
            
            key_metrics = f"vol={vol_threshold}, conf={confidence}"
            
            print(f"{i+1:<4} {config_name:<18} {trades:<8} {signals:<8} {key_metrics}")
        
        # Best configuration
        best = sorted_results[0]
        print(f"\n🏆 MEJOR CONFIGURACIÓN: {best['config_name']}")
        print(f"   📊 Trades ejecutados: {best['trades_executed']}")
        print(f"   🎯 Señales generadas: {best['signals_generated']}")
        print(f"   ⚙️  Parámetros clave:")
        
        key_params = {
            'macdv_volume_threshold': best['params']['macdv_volume_threshold'],
            'macdv_min_conditions': best['params']['macdv_min_conditions'],
            'multi_strategy_default_confidence_threshold': best['params']['multi_strategy_default_confidence_threshold']
        }
        
        for param, value in key_params.items():
            print(f"      {param}: {value}")
        
        # Recommendation
        if best['trades_executed'] > 1:
            print(f"\n✅ RECOMENDACIÓN: Usar configuración '{best['config_name']}'")
            print(f"   Esta configuración genera {best['trades_executed']} trades vs 1 actual")
        else:
            print(f"\n⚠️  NOTA: Incluso la mejor configuración solo genera {best['trades_executed']} trade(s)")
            print("   Puede que necesitemos parámetros aún más permisivos o revisar la lógica")

async def main():
    backtest = SimpleBacktest()
    
    try:
        results = await backtest.run_optimization()
        print(f"\n✅ Backtesting completado. Probadas {len(results)} configuraciones.")
        
    except Exception as e:
        print(f"❌ Error en backtesting: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure config is restored
        backtest._restore_config()

if __name__ == "__main__":
    asyncio.run(main())