#!/usr/bin/env python3
"""
Script para diagnosticar por qué las estrategias no están generando señales
"""

import asyncio
import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta

# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.interfaces import MarketData
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
from core.config_manager import ConfigManager
from core.database_manager import get_database_manager

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def diagnose_strategy_signals():
    """Diagnosticar por qué las estrategias no generan señales"""
    print("🔍 DIAGNÓSTICO DE SEÑALES DE ESTRATEGIA")
    print("=" * 60)
    
    try:
        # 1. Inicializar ML Engine
        print("🚀 Inicializando ML Multi-Strategy Engine...")
        config_manager = ConfigManager()
        ml_engine = MLMultiStrategyEngine(config_manager.config)
        await ml_engine.initialize()
        
        print(f"✅ ML Engine inicializado con {len(ml_engine.available_strategies)} estrategias disponibles")
        print(f"📊 Estrategias disponibles: {list(ml_engine.available_strategies)[:5]}...")
        
        # 2. Crear datos de mercado de prueba
        print("\n📊 Creando datos de mercado de prueba...")
        test_symbols = ['CSIQ', 'SMXT', 'AAPL', 'NVDA', 'TSLA']
        
        for symbol in test_symbols:
            print(f"\n🎯 PROBANDO SÍMBOLO: {symbol}")
            print("-" * 40)
            
            # Crear datos de mercado simulados
            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                open=100.0,
                high=105.0,
                low=98.0,
                close=103.0,
                volume=1000000,
                vwap=102.0
            )
            
            # 3. Probar selección ML de estrategias
            print("🧠 Probando selección ML de estrategias...")
            try:
                # Simular el flujo completo
                signal = await ml_engine.on_bar(market_data)
                
                if signal:
                    strategy_name = signal.metadata.get('strategy_name', 'Unknown')
                    confidence = getattr(signal, 'confidence', 0)
                    print(f"✅ SEÑAL GENERADA:")
                    print(f"   Estrategia: {strategy_name}")
                    print(f"   Tipo: {signal.signal_type}")
                    print(f"   Precio: ${signal.price:.2f}")
                    print(f"   Confianza: {confidence:.1%}")
                else:
                    print("❌ NO se generó señal")
                    
                    # Diagnosticar por qué no se generó señal
                    await diagnose_no_signal(ml_engine, symbol, market_data)
                    
            except Exception as e:
                print(f"❌ Error procesando {symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        # 4. Probar estrategias individuales
        print(f"\n🔍 PROBANDO ESTRATEGIAS INDIVIDUALES")
        print("=" * 60)
        
        # Probar las estrategias que el ML está seleccionando
        test_strategies = ['macdv_smallcaps', 'eod_momentum', 'volume_breakout', 'vcp']
        
        for strategy_name in test_strategies:
            print(f"\n🎯 PROBANDO ESTRATEGIA: {strategy_name}")
            print("-" * 40)
            
            try:
                # Cargar estrategia
                if strategy_name not in ml_engine.strategy_instances:
                    strategy_instance = await ml_engine._load_strategy_instance(strategy_name)
                    if strategy_instance:
                        if ml_engine.event_bus:
                            await strategy_instance.initialize(ml_engine.event_bus)
                        ml_engine.strategy_instances[strategy_name] = strategy_instance
                
                strategy = ml_engine.strategy_instances.get(strategy_name)
                if not strategy:
                    print(f"❌ No se pudo cargar estrategia {strategy_name}")
                    continue
                
                print(f"✅ Estrategia {strategy_name} cargada")
                
                # Probar con diferentes símbolos
                for symbol in ['CSIQ', 'SMXT']:
                    market_data = MarketData(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        open=100.0,
                        high=105.0,
                        low=98.0,
                        close=103.0,
                        volume=1000000,
                        vwap=102.0
                    )
                    
                    # Configurar datos de la estrategia
                    if hasattr(strategy, 'bars_history'):
                        if isinstance(strategy.bars_history, dict):
                            strategy.bars_history[symbol] = [market_data]
                        elif isinstance(strategy.bars_history, list):
                            strategy.bars_history = [market_data]
                    
                    # Probar generación de señal
                    try:
                        signal = await asyncio.wait_for(strategy.on_bar(market_data), timeout=2.0)
                        
                        if signal:
                            print(f"   ✅ {symbol}: Señal generada - {signal.signal_type}")
                        else:
                            print(f"   ❌ {symbol}: No generó señal")
                            
                    except asyncio.TimeoutError:
                        print(f"   ⏰ {symbol}: Timeout")
                    except Exception as e:
                        print(f"   ❌ {symbol}: Error - {e}")
                        
            except Exception as e:
                print(f"❌ Error con estrategia {strategy_name}: {e}")
        
        print(f"\n🎯 DIAGNÓSTICO COMPLETADO")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()

async def diagnose_no_signal(ml_engine, symbol, market_data):
    """Diagnosticar por qué no se generó señal"""
    print("🔍 Diagnosticando ausencia de señal...")
    
    try:
        # 1. Verificar contexto de ticker
        context = ml_engine.ticker_profiler.profile_ticker(symbol, market_data)
        print(f"   📊 Contexto generado: {len(context.to_feature_vector()) if hasattr(context, 'to_feature_vector') else 'N/A'} features")
        
        # 2. Verificar selección ML
        selected_strategies = ml_engine.ml_selector.select_strategies(context, top_k=2)
        print(f"   🧠 Estrategias seleccionadas por ML: {selected_strategies}")
        
        # 3. Verificar ejecución de estrategias
        candidate_signals = await ml_engine._execute_selected_strategies(
            symbol, market_data, selected_strategies
        )
        print(f"   📊 Señales candidatas generadas: {len(candidate_signals)}")
        
        if not candidate_signals:
            print("   ❌ Las estrategias seleccionadas no generaron señales")
            print("   💡 Posibles causas:")
            print("      - Condiciones de mercado no cumplen criterios")
            print("      - Parámetros de estrategia muy restrictivos")
            print("      - Falta de datos históricos suficientes")
        
    except Exception as e:
        print(f"   ❌ Error en diagnóstico detallado: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_strategy_signals())
