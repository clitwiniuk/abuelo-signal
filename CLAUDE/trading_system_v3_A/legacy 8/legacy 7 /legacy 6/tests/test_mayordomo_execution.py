#!/usr/bin/env python3
"""
Test del Mayordomo - Verificar ejecución de trades
Simula plays reales para probar si el Mayordomo toma decisiones correctas
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'scanner', 'smallcap'))

# Import required modules
try:
    from core.risk_manager import create_smallcap_mayordomo
    from core.interfaces import TradingConfig
    from scanner.smallcap.catalyst_analyzer import CatalystInfo
    from scanner.smallcap.smallcap_context import SmallcapContext
    from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MayordomoTest")

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

async def test_mayordomo_initialization():
    """Test 1: Verificar que el Mayordomo se inicializa correctamente"""
    print("\n🔧 TEST 1: Inicialización del Mayordomo")
    print("-" * 50)
    
    try:
        # Create minimal trading config
        config = TradingConfig(
            max_positions=5,
            max_risk_per_trade=0.02,  # 2%
            max_daily_loss=-1000.0,  # $1000 max loss
            max_daily_trades=20,
            portfolio_capital=10000.0,  # $10k for testing
            strategy_name="smallcap_test"
        )
        
        # Create mayordomo
        mayordomo = create_smallcap_mayordomo(config)
        
        if mayordomo:
            print("✅ Mayordomo inicializado correctamente")
            print(f"   Tipo: {type(mayordomo).__name__}")
            return mayordomo
        else:
            print("❌ Mayordomo es None")
            return None
            
    except Exception as e:
        print(f"❌ Error inicializando Mayordomo: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_mayordomo_registration(mayordomo, test_plays):
    """Test 2: Verificar capacidad de registro (sin pre-registrar)"""
    print("\n📋 TEST 2: Verificar capacidad de registro del Mayordomo")
    print("-" * 50)
    
    try:
        print("✅ Mayordomo listo para evaluar oportunidades")
        print("   📝 Los plays se registrarán automáticamente cuando sean aprobados")
        print(f"   🎯 {len(test_plays)} oportunidades preparadas para evaluación")
        print("   📊 Portfolio inicial: VACÍO (correcto para testing)")
        
        # Verificar que el portfolio está vacío inicialmente
        active_plays = len(mayordomo.active_daily_plays)
        print(f"   📈 Posiciones activas actuales: {active_plays}")
        
        if active_plays == 0:
            print("   ✅ Portfolio vacío confirmado - listo para evaluaciones")
            return True
        else:
            print(f"   ⚠️  Portfolio no está vacío: {list(mayordomo.active_daily_plays.keys())}")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando capacidad de registro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mayordomo_evaluation(mayordomo, test_plays):
    """Test 3: Verificar evaluación de posiciones"""
    print("\n⚖️  TEST 3: Evaluación de posiciones por el Mayordomo")
    print("-" * 50)
    
    decisions = []
    
    try:
        for play in test_plays:
            print(f"\n🔍 Evaluando {play.symbol}...")
            
            # Create opportunity dict (same format as production)
            opportunity = {
                'symbol': play.symbol,
                'catalyst_type': play.context.news_catalyst_type,
                'catalyst_strength': play.context.catalyst_strength,
                'gap_percentage': play.context.gap_percentage,
                'volume_ratio': play.context.premarket_volume_ratio,
                'current_price': play.context.current_price
            }
            
            # Get mayordomo decision
            decision = mayordomo.evaluate_position_rotation(opportunity)
            decisions.append((play.symbol, decision))
            
            if decision:
                action = decision.get('action', 'NO_ACTION')
                reason = decision.get('reason', 'No reason provided')
                confidence = decision.get('confidence', 0.0)
                
                if action == 'OPEN_POSITION':
                    print(f"✅ {play.symbol}: APROBADO para trading")
                    print(f"   Action: {action}")
                    print(f"   Reason: {reason}")
                    print(f"   Confidence: {confidence:.2f}")
                    if 'position_size' in decision:
                        print(f"   Position Size: {decision['position_size']:.3f}")
                    
                    # IMPORTANT: Only register play AFTER it's approved
                    # This simulates actually opening the position
                    print(f"   🎯 Registering {play.symbol} as active position...")
                    mayordomo.register_daily_play(
                        symbol=play.symbol,
                        catalyst_type=play.context.news_catalyst_type,
                        catalyst_strength=play.context.catalyst_strength,
                        gap_percentage=play.context.gap_percentage,
                        volume_ratio=play.context.premarket_volume_ratio,
                        entry_price=play.context.current_price
                    )
                    
                elif action == 'ROTATE':
                    print(f"🔄 {play.symbol}: ROTACIÓN APROBADA")
                    print(f"   Action: {action}")
                    print(f"   Reason: {reason}")
                    print(f"   Close: {decision.get('close_symbol', 'N/A')}")
                    print(f"   Open: {decision.get('open_symbol', 'N/A')}")
                    if 'confidence' in decision:
                        print(f"   Confidence: {decision['confidence']:.2f}")
                else:
                    print(f"❌ {play.symbol}: RECHAZADO")
                    print(f"   Action: {action}")
                    print(f"   Reason: {reason}")
            else:
                print(f"❌ {play.symbol}: Sin decisión (None)")
                
        return decisions
        
    except Exception as e:
        print(f"❌ Error evaluando posiciones: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_summary(decisions):
    """Test 4: Resumen de resultados"""
    print("\n📊 RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    approved = []
    rejected = []
    no_decision = []
    
    for symbol, decision in decisions:
        if decision and decision.get('action') == 'OPEN_POSITION':
            approved.append(symbol)
        elif decision:
            rejected.append(symbol)
        else:
            no_decision.append(symbol)
    
    print(f"✅ APROBADOS ({len(approved)}): {', '.join(approved) if approved else 'Ninguno'}")
    print(f"❌ RECHAZADOS ({len(rejected)}): {', '.join(rejected) if rejected else 'Ninguno'}")
    print(f"❓ SIN DECISIÓN ({len(no_decision)}): {', '.join(no_decision) if no_decision else 'Ninguno'}")
    
    total_decisions = len([d for _, d in decisions if d])
    print(f"\nTotal evaluaciones: {len(decisions)}")
    print(f"Decisiones válidas: {total_decisions}")
    print(f"Tasa de aprobación: {len(approved)/max(total_decisions, 1)*100:.1f}%")
    
    if approved:
        print(f"\n🎯 RESULTADO: El Mayordomo SÍ está tomando decisiones de trading")
        print("✅ Sistema funcionando correctamente")
        return True
    else:
        print(f"\n⚠️ RESULTADO: El Mayordomo NO aprobó ningún trade")
        print("❌ Puede haber un problema en la lógica de evaluación")
        return False

async def main():
    """Ejecutar todos los tests del Mayordomo"""
    print("🧪 TESTING DEL MAYORDOMO - EJECUCIÓN DE TRADES")
    print("=" * 60)
    
    # Create test plays (realistic scenarios)
    test_plays = [
        create_test_play("THAR", 25.5, 2.1, "FDA", 8),      # Strong FDA catalyst
        create_test_play("SPAI", 15.2, 3.5, "M&A", 9),      # Strong M&A catalyst  
        create_test_play("NVNO", 8.5, 1.8, "EARNINGS", 6),  # Moderate earnings
        create_test_play("TEST", 5.2, 0.8, "OTHER", 3),     # Weak catalyst
        create_test_play("STRONG", 45.0, 5.2, "M&A", 10),   # Very strong play
    ]
    
    print(f"📋 Test plays creados: {len(test_plays)} símbolos")
    for play in test_plays:
        print(f"   {play.symbol}: {play.catalyst.catalyst_type} (strength {play.catalyst.strength}), gap {play.context.gap_percentage*100:.1f}%, vol {play.context.premarket_volume_ratio:.1f}x")
    
    # Test 1: Initialize Mayordomo
    mayordomo = await test_mayordomo_initialization()
    if not mayordomo:
        print("\n❌ FALLO CRÍTICO: No se pudo inicializar el Mayordomo")
        return False
    
    # Test 2: Register plays
    registration_success = test_mayordomo_registration(mayordomo, test_plays)
    if not registration_success:
        print("\n❌ FALLO: Error en el registro de plays")
        return False
    
    # Test 3: Evaluate positions
    decisions = test_mayordomo_evaluation(mayordomo, test_plays)
    if not decisions:
        print("\n❌ FALLO: Error en la evaluación de posiciones")
        return False
    
    # Test 4: Summary
    success = test_summary(decisions)
    
    print(f"\n{'='*60}")
    if success:
        print("🎉 RESULTADO FINAL: TESTS PASADOS - Mayordomo funcionando")
    else:
        print("⚠️ RESULTADO FINAL: TESTS FALLIDOS - Revisar configuración")
    
    return success

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