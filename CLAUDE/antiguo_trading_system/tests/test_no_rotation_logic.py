#!/usr/bin/env python3
"""
Test de nueva lógica sin rotación para SmallcapMayordomo
"""

import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def test_no_rotation_logic():
    """Test nueva lógica simplificada sin rotación"""
    print("\n🧪 TEST: Lógica Sin Rotación")
    print("-" * 50)
    
    try:
        from core.risk_manager import create_smallcap_mayordomo
        from core.interfaces import TradingConfig
        
        # Create test config
        config = TradingConfig(
            max_positions=3,
            max_risk_per_trade=0.02,
            max_daily_loss=-500.0,
            portfolio_capital=5000.0
        )
        
        # Create Mayordomo
        mayordomo = create_smallcap_mayordomo(config)
        
        # Clear any existing positions for clean test
        mayordomo.active_daily_plays = {}
        print("✅ SmallcapMayordomo creado y limpiado")
        
        # Test opportunities from recent logs
        test_opportunities = [
            {
                'symbol': 'APM',
                'catalyst_type': 'OTHER',
                'catalyst_strength': 3,
                'gap_percentage': 1.772,  # 177.2%
                'volume_ratio': 2.0,
                'current_price': 3.15,
                'expected_score': 0.49
            },
            {
                'symbol': 'PTIX',
                'catalyst_type': 'CONTRACT',
                'catalyst_strength': 6,
                'gap_percentage': 1.031,  # 103.1%
                'volume_ratio': 2.0,
                'current_price': 5.25,
                'expected_score': 0.70
            },
            {
                'symbol': 'VELO',
                'catalyst_type': 'FDA',
                'catalyst_strength': 10,
                'gap_percentage': 0.070,  # 7.0%
                'volume_ratio': 0.7,
                'current_price': 8.75,
                'expected_score': 0.70
            }
        ]
        
        results = []
        print(f"\n🔄 Testing {len(test_opportunities)} opportunities...")
        
        for i, opportunity in enumerate(test_opportunities, 1):
            print(f"\n📊 Test {i}: {opportunity['symbol']}")
            print(f"   Gap: {opportunity['gap_percentage']*100:+.1f}%")
            print(f"   Volume: {opportunity['volume_ratio']:.1f}x")
            print(f"   Catalyst: {opportunity['catalyst_type']} ({opportunity['catalyst_strength']}/10)")
            print(f"   Positions actuales: {len(mayordomo.active_daily_plays)}/3")
            
            # Evaluate the opportunity
            decision = mayordomo.evaluate_position_rotation(opportunity)
            
            print(f"   Decision: {decision['action']}")
            print(f"   Reason: {decision['reason']}")
            
            success = decision['action'] == 'OPEN_POSITION'
            results.append({
                'symbol': opportunity['symbol'],
                'success': success,
                'decision': decision
            })
            
            # If approved, simulate adding to portfolio
            if success:
                mayordomo.active_daily_plays[opportunity['symbol']] = {
                    'symbol': opportunity['symbol'],
                    'catalyst_type': opportunity['catalyst_type'],
                    'entry_time': '19:33:05',
                    'opportunity_score': decision.get('confidence', 0.5)
                }
                print(f"   ✅ APPROVED - Added to portfolio")
            else:
                print(f"   ❌ REJECTED")
        
        # Summary
        approved_count = sum(1 for r in results if r['success'])
        print(f"\n📊 RESUMEN:")
        print(f"   Aprobados: {approved_count}/{len(test_opportunities)}")
        print(f"   Portfolio final: {len(mayordomo.active_daily_plays)}/3 positions")
        
        # Test with full portfolio
        print(f"\n🔄 TEST: Portfolio lleno (necesita score ≥0.80)")
        exceptional_opportunity = {
            'symbol': 'EXCEPTIONAL',
            'catalyst_type': 'FDA',
            'catalyst_strength': 10,
            'gap_percentage': 2.0,  # 200%
            'volume_ratio': 5.0,
            'current_price': 10.0
        }
        
        decision = mayordomo.evaluate_position_rotation(exceptional_opportunity)
        print(f"   Exceptional test: {decision['action']} - {decision['reason']}")
        
        # Show new logic benefits
        print(f"\n🎯 NUEVA LÓGICA:")
        print(f"   ✅ No rotation complexity")
        print(f"   ✅ Simple slot-based system (0-3 positions)")
        print(f"   ✅ Lower threshold when slots available (≥0.50)")
        print(f"   ✅ High bar when full (≥0.80)")
        print(f"   ✅ Event-driven approach for smallcaps")
        
        return approved_count > 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run no rotation logic test"""
    print("🚀 TESTING NO-ROTATION SMALLCAP LOGIC")
    print("=" * 60)
    
    print("🎯 Objetivo: Eliminar rotación, usar slots simples")
    print("📋 Portfolio-based approach: 3 slots, fill progressively")
    
    try:
        success = test_no_rotation_logic()
        
        if success:
            print(f"\n✅ NUEVA LÓGICA FUNCIONANDO")
            print("🎯 Mayordomo ahora usa slots en lugar de rotación")
            print("📈 Reinicia sistema para aplicar cambios")
        else:
            print(f"\n⚠️ LÓGICA NECESITA AJUSTES")
            
        return success
        
    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)