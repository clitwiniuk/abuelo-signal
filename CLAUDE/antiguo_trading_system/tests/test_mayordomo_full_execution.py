#!/usr/bin/env python3
"""
Test Integrado del Mayordomo - Ejecución Completa de Trades
Incluye todo el flujo: Decisión → Señal → Validación → Orden → Ejecución
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'scanner', 'smallcap'))

# Import required modules
try:
    from core.risk_manager import create_smallcap_mayordomo
    from core.interfaces import TradingConfig, Signal, SignalType, Order, OrderSide, OrderType, Position
    from scanner.smallcap.catalyst_analyzer import CatalystInfo
    from scanner.smallcap.smallcap_context import SmallcapContext
    from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MayordomoFullTest")

def create_test_play(symbol: str, gap_pct: float, volume_ratio: float, catalyst_type: str, catalyst_strength: int) -> SmallcapPlay:
    """Create a test SmallcapPlay object"""
    
    # Create mock catalyst
    catalyst = CatalystInfo(
        catalyst_type=catalyst_type,
        strength=catalyst_strength,
        age_hours=1.5,  # Fresh news
        keywords_found=['test', 'catalyst'],
        headline=f"Test news for {symbol}",
        confidence=0.85
    )
    
    # Create mock context
    context = SmallcapContext(
        symbol=symbol,
        timestamp=datetime.now(),
        current_price=10.50,
        gap_percentage=gap_pct / 100.0,  # Convert to decimal
        premarket_high=11.00,
        premarket_low=9.80,
        premarket_volume=500_000,
        avg_daily_volume=1_000_000,
        premarket_volume_ratio=volume_ratio,
        news_catalyst_type=catalyst_type,
        news_age_hours=1.5,
        catalyst_strength=catalyst_strength,
        float_size=5_000_000,
        market_cap=52_500_000,
        price_vs_premarket_high=0.95,  # 95% of PM high
        volume_spike_confirmed=volume_ratio > 3.0,
        market_fear_level="LOW"
    )
    
    # Calculate quality score (simplified)
    quality_score = min(10.0, (gap_pct / 10.0) + (volume_ratio * 1.5) + catalyst_strength)
    
    return SmallcapPlay(
        symbol=symbol,
        context=context,
        catalyst=catalyst,
        quality_score=quality_score,
        trading_recommendation={},
        scan_timestamp=datetime.now(),
        ibkr_rank=1
    )

class MockTradingEngineForTest:
    """Mock TradingEngine that tracks signals and orders for testing"""
    
    def __init__(self):
        self.monitored_symbols = set()
        self.generated_signals: List[Signal] = []
        self.executed_orders: List[Order] = []
        self.positions: Dict[str, Position] = {}
        self.initialized = False
        
        # Mock strategy and analysis stage
        self.strategy = Mock()
        self.strategy.pending_signals = {}
        self.analysis_stage = Mock()
        self.analysis_stage.strategies = [Mock()]
        
        # Mock broker adapter
        self.broker_adapter = Mock()
        
    async def initialize(self):
        """Initialize mock trading engine"""
        self.initialized = True
        logger.info("🔧 Mock TradingEngine initialized")
        return True
    
    async def add_symbol(self, symbol: str, skip_validation: bool = False):
        """Add symbol to monitoring"""
        self.monitored_symbols.add(symbol)
        logger.info(f"📊 Symbol {symbol} added to monitoring (total: {len(self.monitored_symbols)})")
        return True
    
    async def process_signal(self, signal: Signal) -> bool:
        """Process signal through the full pipeline"""
        try:
            logger.info(f"⚡ Processing signal for {signal.symbol}: {signal.signal_type.value}")
            
            # Store signal
            self.generated_signals.append(signal)
            
            # NEW: Simulate Strategy Evaluation
            strategy_approved = await self._simulate_strategy_evaluation(signal)
            if not strategy_approved:
                logger.warning(f"❌ Strategy rejected signal for {signal.symbol}")
                return False
            
            # Simulate Risk Manager validation
            risk_approved = await self._simulate_risk_validation(signal)
            if not risk_approved:
                logger.warning(f"❌ Risk Manager rejected signal for {signal.symbol}")
                return False
            
            # Simulate order creation
            order = await self._create_order_from_signal(signal)
            if not order:
                logger.error(f"❌ Failed to create order for {signal.symbol}")
                return False
            
            # Simulate order execution
            execution_success = await self._execute_order(order)
            if not execution_success:
                logger.error(f"❌ Failed to execute order for {signal.symbol}")
                return False
            
            # Create position
            await self._create_position_from_order(order, signal)
            
            logger.info(f"✅ Signal fully processed for {signal.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing signal for {signal.symbol}: {e}")
            return False
    
    async def _simulate_strategy_evaluation(self, signal: Signal) -> bool:
        """Simulate ML Engine Strategy Selection (like SmallcapContextualBandit)"""
        logger.info(f"🧠 ML Engine evaluating strategies for {signal.symbol}...")
        
        # Extract signal metadata
        metadata = signal.metadata
        catalyst_type = metadata.get('catalyst_type', 'OTHER')
        catalyst_strength = metadata.get('catalyst_strength', 5)
        gap_percentage = metadata.get('gap_percentage', 0)
        volume_ratio = metadata.get('volume_ratio', 1)
        
        # Simulate strategy selection logic (like SmallcapContextualBandit)
        available_strategies = ['gap_go', 'daily_plays', 'volume_breakout', 'vwap_reclaim']
        selected_strategies = []
        
        # Strategy 1: gap_go - Good for large gaps
        if gap_percentage > 0.08:  # 8%+ gap
            gap_go_score = min(gap_percentage * 2, 1.0)  # Max score 1.0
            selected_strategies.append(('gap_go', gap_go_score))
            logger.info(f"   📈 gap_go strategy candidate: score {gap_go_score:.2f} (gap {gap_percentage*100:.1f}%)")
        
        # Strategy 2: daily_plays - Good for catalysts
        if catalyst_strength >= 5:
            catalyst_score = catalyst_strength / 10.0
            daily_plays_score = catalyst_score * (1.2 if catalyst_type in ['FDA', 'M&A'] else 0.8)
            selected_strategies.append(('daily_plays', daily_plays_score))
            logger.info(f"   🎯 daily_plays strategy candidate: score {daily_plays_score:.2f} ({catalyst_type} catalyst)")
        
        # Strategy 3: volume_breakout - Good for high volume
        if volume_ratio > 2.0:
            volume_score = min(volume_ratio / 5.0, 1.0)  # Normalize to max 1.0
            selected_strategies.append(('volume_breakout', volume_score))
            logger.info(f"   📊 volume_breakout strategy candidate: score {volume_score:.2f} (vol {volume_ratio:.1f}x)")
        
        # Strategy 4: vwap_reclaim - Good for moderate moves
        if gap_percentage > 0.05 and volume_ratio > 1.5:
            vwap_score = (gap_percentage + volume_ratio/5) / 2
            selected_strategies.append(('vwap_reclaim', vwap_score))
            logger.info(f"   📊 vwap_reclaim strategy candidate: score {vwap_score:.2f}")
        
        # Select best strategies (top 2)
        if selected_strategies:
            selected_strategies.sort(key=lambda x: x[1], reverse=True)
            top_strategies = selected_strategies[:2]
            strategy_names = [s[0] for s in top_strategies]
            
            logger.info(f"🧠 ML Engine recomienda estrategia para {signal.symbol}: {strategy_names}")
            
            # Simulate SmallcapContextualBandit selection
            for strategy_name, score in top_strategies:
                logger.info(f"Selected strategy for {signal.symbol}: {strategy_name}")
                logger.info(f"   Gap: {gap_percentage*100:.1f}%, Volume: {volume_ratio:.1f}x")
                logger.info(f"   Catalyst: {catalyst_strength/10:.1f}, Type: {catalyst_type}")
            
            # Return True if we have at least one good strategy
            best_score = top_strategies[0][1]
            if best_score >= 0.6:  # Need 60% strategy confidence
                logger.info(f"✅ Strategy selection passed: best score {best_score:.2f} >= 0.60")
                return True
            else:
                logger.warning(f"❌ Strategy selection failed: best score {best_score:.2f} < 0.60")
                return False
        else:
            logger.warning(f"❌ No suitable strategies found for {signal.symbol}")
            return False
    
    async def _simulate_risk_validation(self, signal: Signal) -> bool:
        """Simulate Risk Manager validation"""
        logger.info(f"🔍 Risk Manager validating signal for {signal.symbol}...")
        
        # Simulate basic risk checks
        if signal.strength < 0.3:
            logger.warning(f"Signal strength too low: {signal.strength}")
            return False
        
        if signal.price <= 0:
            logger.warning(f"Invalid price: {signal.price}")
            return False
        
        # Check position limits (simplified)
        if len(self.positions) >= 5:  # Max 5 positions
            logger.warning(f"Position limit reached: {len(self.positions)}/5")
            return False
        
        logger.info(f"✅ Risk validation passed for {signal.symbol}")
        return True
    
    async def _create_order_from_signal(self, signal: Signal) -> Order:
        """Create order from signal"""
        try:
            # Calculate position size
            portfolio_value = 10000.0  # $10k test portfolio
            risk_per_trade = 0.02  # 2% risk
            position_size_usd = portfolio_value * signal.metadata.get('position_size', 0.05)  # Default 5%
            
            # Calculate shares
            shares = int(position_size_usd / signal.price)
            if shares <= 0:
                shares = 1  # Minimum 1 share
            
            order = Order(
                order_id="",  # Will be auto-generated
                symbol=signal.symbol,
                side=OrderSide.BUY,
                quantity=shares,
                order_type=OrderType.MARKET,
                price=signal.price,
                timestamp=datetime.now()
            )
            
            logger.info(f"📋 Order created: {order.side.value} {order.quantity} {order.symbol} @ ${order.price:.2f}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None
    
    async def _execute_order(self, order: Order) -> bool:
        """Simulate order execution"""
        try:
            logger.info(f"⚡ Executing order: {order.side.value} {order.quantity} {order.symbol}")
            
            # Simulate execution delay
            await asyncio.sleep(0.1)
            
            # Simulate fill
            order.filled_quantity = order.quantity
            order.avg_fill_price = order.price + 0.01  # Small slippage
            order.status = "filled"
            
            self.executed_orders.append(order)
            
            logger.info(f"✅ Order executed: {order.quantity} shares @ ${order.avg_fill_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return False
    
    async def _create_position_from_order(self, order: Order, signal: Signal):
        """Create position from executed order"""
        try:
            position = Position(
                symbol=order.symbol,
                quantity=order.filled_quantity,
                avg_price=order.avg_fill_price,
                market_price=order.avg_fill_price,
                market_value=order.filled_quantity * order.avg_fill_price,
                unrealized_pnl=0.0,
                entry_time=datetime.now()
            )
            
            self.positions[order.symbol] = position
            
            logger.info(f"📊 Position created: {position.quantity} {position.symbol} @ ${position.avg_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error creating position: {e}")

async def test_mayordomo_initialization():
    """Test 1: Initialize Mayordomo and TradingEngine"""
    print("\n🔧 TEST 1: Inicialización completa del sistema")
    print("-" * 60)
    
    try:
        # Create trading config
        config = TradingConfig(
            max_positions=5,
            max_risk_per_trade=0.02,
            max_daily_loss=-1000.0,
            max_daily_trades=20,
            portfolio_capital=10000.0,
            strategy_name="smallcap_test"
        )
        
        # Create Mayordomo
        mayordomo = create_smallcap_mayordomo(config)
        if not mayordomo:
            print("❌ Failed to create Mayordomo")
            return None, None
        
        # Create mock TradingEngine
        trading_engine = MockTradingEngineForTest()
        await trading_engine.initialize()
        
        print("✅ Sistema inicializado correctamente")
        print(f"   Mayordomo: {type(mayordomo).__name__}")
        print(f"   TradingEngine: {type(trading_engine).__name__}")
        print(f"   Portfolio: ${config.portfolio_capital:,.0f}")
        print(f"   Max posiciones: {config.max_positions}")
        
        return mayordomo, trading_engine
        
    except Exception as e:
        print(f"❌ Error inicializando sistema: {e}")
        import traceback
        traceback.print_exc()
        return None, None

async def test_full_trade_execution(mayordomo, trading_engine, test_play):
    """Test 2: Execute complete trade flow"""
    print(f"\n⚡ TEST 2: Ejecución completa de trade para {test_play.symbol}")
    print("-" * 60)
    
    try:
        # Step 1: Mayordomo evaluates opportunity
        print(f"🎯 Paso 1: Evaluación del Mayordomo...")
        opportunity = {
            'symbol': test_play.symbol,
            'catalyst_type': test_play.context.news_catalyst_type,
            'catalyst_strength': test_play.context.catalyst_strength,
            'gap_percentage': test_play.context.gap_percentage,
            'volume_ratio': test_play.context.premarket_volume_ratio,
            'current_price': test_play.context.current_price
        }
        
        decision = mayordomo.evaluate_position_rotation(opportunity)
        print(f"   Decisión: {decision.get('action', 'NO_ACTION')}")
        print(f"   Razón: {decision.get('reason', 'N/A')}")
        
        if decision.get('action') != 'OPEN_POSITION':
            print(f"❌ Mayordomo rechazó la oportunidad - no se ejecuta trade")
            return False
        
        print("✅ Mayordomo aprobó la oportunidad")
        
        # Step 2: Add symbol to TradingEngine
        print(f"📊 Paso 2: Agregando {test_play.symbol} al TradingEngine...")
        success = await trading_engine.add_symbol(test_play.symbol, skip_validation=True)
        if not success:
            print(f"❌ No se pudo agregar {test_play.symbol} al TradingEngine")
            return False
        
        # Step 3: Create and process signal
        print(f"📡 Paso 3: Creando señal de trading...")
        signal = Signal(
            signal_id="",
            symbol=test_play.symbol,
            signal_type=SignalType.LONG,
            strength=min(test_play.quality_score / 10.0, 1.0),
            price=test_play.context.current_price,
            timestamp=datetime.now(),
            strategy_name="SmallcapMayordomo",
            metadata={
                "catalyst_type": test_play.catalyst.catalyst_type,
                "catalyst_strength": test_play.catalyst.strength,
                "gap_percentage": test_play.context.gap_percentage,
                "volume_ratio": test_play.context.premarket_volume_ratio,
                "quality_score": test_play.quality_score,
                "mayordomo_decision": decision,
                "position_size": decision.get('position_size', 0.05)
            }
        )
        
        print(f"   Señal creada: {signal.signal_type.value} {signal.symbol} @ ${signal.price:.2f}")
        print(f"   Fortaleza: {signal.strength:.2f}")
        
        # Step 4: Process signal through TradingEngine pipeline
        print(f"⚙️ Paso 4: Procesando señal a través del pipeline completo...")
        print(f"   🧠 ML Engine evaluará la estrategia")
        print(f"   🔍 Risk Manager validará los riesgos")  
        print(f"   💰 Execution Engine creará y ejecutará la orden")
        execution_success = await trading_engine.process_signal(signal)
        
        if execution_success:
            print("✅ Trade ejecutado exitosamente!")
            
            # Show results
            print(f"\n📊 RESULTADOS DEL TRADE:")
            print(f"   Símbolo: {test_play.symbol}")
            print(f"   Tipo: {signal.signal_type.value}")
            print(f"   Precio entrada: ${signal.price:.2f}")
            
            if test_play.symbol in trading_engine.positions:
                position = trading_engine.positions[test_play.symbol]
                print(f"   Cantidad: {position.quantity} acciones")
                print(f"   Precio promedio: ${position.avg_price:.2f}")
                print(f"   Valor posición: ${position.market_value:.2f}")
            
            return True
        else:
            print("❌ Fallo en la ejecución del trade")
            return False
            
    except Exception as e:
        print(f"❌ Error en ejecución completa: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_execution_summary(trading_engine, successful_trades):
    """Test 3: Summary of execution results"""
    print(f"\n📊 TEST 3: Resumen de ejecución")
    print("=" * 60)
    
    print(f"💼 PORTFOLIO FINAL:")
    print(f"   Símbolos monitoreados: {len(trading_engine.monitored_symbols)}")
    print(f"   Señales generadas: {len(trading_engine.generated_signals)}")
    print(f"   Órdenes ejecutadas: {len(trading_engine.executed_orders)}")
    print(f"   Posiciones abiertas: {len(trading_engine.positions)}")
    
    if trading_engine.positions:
        print(f"\n📈 POSICIONES ACTIVAS:")
        total_value = 0
        for symbol, position in trading_engine.positions.items():
            print(f"   {symbol}: {position.quantity} @ ${position.avg_price:.2f} = ${position.market_value:.2f}")
            total_value += position.market_value
        print(f"   TOTAL INVERTIDO: ${total_value:.2f}")
    
    if trading_engine.generated_signals:
        print(f"\n📡 SEÑALES GENERADAS:")
        for signal in trading_engine.generated_signals:
            metadata = signal.metadata
            print(f"   {signal.symbol}: {signal.signal_type.value} | "
                  f"Catalyst: {metadata.get('catalyst_type')} | "
                  f"Strength: {signal.strength:.2f}")
    
    success_rate = len(successful_trades) / max(len(trading_engine.generated_signals), 1) * 100
    print(f"\n🎯 TASA DE ÉXITO: {success_rate:.1f}%")
    
    if len(trading_engine.positions) > 0:
        print(f"✅ RESULTADO: Sistema ejecutando trades correctamente")
        return True
    else:
        print(f"⚠️ RESULTADO: No se ejecutaron trades")
        return False

async def main():
    """Execute full integration test"""
    print("🧪 TEST INTEGRADO MAYORDOMO - EJECUCIÓN COMPLETA DE TRADES")
    print("=" * 70)
    
    # Create test plays
    test_plays = [
        create_test_play("THAR", 25.5, 2.1, "FDA", 8),      # Strong FDA
        create_test_play("STRONG", 45.0, 5.2, "M&A", 10),   # Very strong M&A
        create_test_play("WEAK", 5.2, 0.8, "OTHER", 3),     # Weak opportunity
    ]
    
    print(f"📋 Test plays preparados: {len(test_plays)} oportunidades")
    for play in test_plays:
        print(f"   {play.symbol}: {play.catalyst.catalyst_type} "
              f"(strength {play.catalyst.strength}), "
              f"gap {play.context.gap_percentage*100:.1f}%, "
              f"vol {play.context.premarket_volume_ratio:.1f}x")
    
    # Test 1: Initialize system
    mayordomo, trading_engine = await test_mayordomo_initialization()
    if not mayordomo or not trading_engine:
        print("\n❌ FALLO CRÍTICO: No se pudo inicializar el sistema")
        return False
    
    # Test 2: Execute trades for each play
    successful_trades = []
    for play in test_plays:
        success = await test_full_trade_execution(mayordomo, trading_engine, play)
        if success:
            successful_trades.append(play.symbol)
    
    # Test 3: Summary
    overall_success = test_execution_summary(trading_engine, successful_trades)
    
    print(f"\n{'='*70}")
    if overall_success:
        print("🎉 RESULTADO FINAL: TESTS PASADOS - Sistema ejecutando trades")
        print(f"✅ Trades exitosos: {len(successful_trades)}/{len(test_plays)}")
    else:
        print("⚠️ RESULTADO FINAL: TESTS FALLIDOS - Revisar sistema")
    
    return overall_success

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Test interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)