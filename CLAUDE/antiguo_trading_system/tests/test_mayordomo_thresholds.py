#!/usr/bin/env python3
"""
Test de thresholds ajustados del SmallcapMayordomo
"""

import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def test_adjusted_thresholds():
    """Test con los casos que se estaban rechazando antes"""
    print("\n🧪 TEST: Thresholds Ajustados del Mayordomo")
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
        mayordomo.rotation_candidates = {}
        mayordomo.active_daily_plays = {}
        print("✅ SmallcapMayordomo creado y limpiado")
        
        # Test cases from production logs that were being rejected
        test_opportunities = [
            {
                'symbol': 'PTIX',
                'catalyst_type': 'CONTRACT',
                'catalyst_strength': 6,
                'gap_percentage': 0.579,  # 57.9%
                'volume_ratio': 2.0,
                'current_price': 5.25,
                'expected_score_range': (0.65, 0.75)
            },
            {
                'symbol': 'APM', 
                'catalyst_type': 'OTHER',
                'catalyst_strength': 3,
                'gap_percentage': 1.189,  # 118.9%
                'volume_ratio': 2.0,
                'current_price': 3.15,
                'expected_score_range': (0.45, 0.55)
            },
            {
                'symbol': 'EVOK',
                'catalyst_type': 'FDA',
                'catalyst_strength': 7,
                'gap_percentage': 0.149,  # 14.9%
                'volume_ratio': 0.6,
                'current_price': 8.75,
                'expected_score_range': (0.60, 0.70)
            },
            {
                'symbol': 'OPEN',
                'catalyst_type': 'EARNINGS',
                'catalyst_strength': 6,
                'gap_percentage': 0.085,  # 8.5%
                'volume_ratio': 2.0,
                'current_price': 3.50,
                'expected_score_range': (0.45, 0.55)
            }
        ]
        
        results = []
        for opportunity in test_opportunities:
            print(f"\n📊 Testing {opportunity['symbol']}:")
            print(f"   Gap: {opportunity['gap_percentage']*100:+.1f}%")
            print(f"   Volume: {opportunity['volume_ratio']:.1f}x")
            print(f"   Catalyst: {opportunity['catalyst_type']} ({opportunity['catalyst_strength']}/10)")
            
            # DON'T register the play first - evaluate as new opportunity
            # This simulates empty portfolio evaluation
            decision = mayordomo.evaluate_position_rotation(opportunity)
            
            print(f"   Decision: {decision['action']}")
            print(f"   Reason: {decision['reason']}")
            
            # Check if decision changed from rejection to approval
            success = decision['action'] == 'OPEN_POSITION'
            results.append({
                'symbol': opportunity['symbol'],
                'success': success,
                'decision': decision
            })
            
            status = "✅ APPROVED" if success else "❌ STILL REJECTED"
            print(f"   Status: {status}")
        
        # Summary
        approved_count = sum(1 for r in results if r['success'])
        print(f"\n📊 RESUMEN:")
        print(f"   Aprobados: {approved_count}/{len(test_opportunities)}")
        print(f"   Mejora: {approved_count > 0}")
        
        # Show threshold changes
        print(f"\n🔧 THRESHOLDS AJUSTADOS:")
        print(f"   • min_quality_threshold: 0.6 → 0.45")
        print(f"   • empty_portfolio_threshold: 0.7 → 0.55") 
        print(f"   • exceptional_threshold: 0.85 → 0.75")
        print(f"   • improvement_threshold: 0.2 → 0.1")
        
        return approved_count > 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run threshold adjustment test"""
    print("🚀 TESTING MAYORDOMO THRESHOLD ADJUSTMENTS")
    print("=" * 60)
    
    print("🎯 Objetivo: Hacer que el Mayordomo sea menos conservador")
    print("📋 Testing con casos reales que se estaban rechazando")
    
    try:
        success = test_adjusted_thresholds()
        
        if success:
            print(f"\n✅ THRESHOLDS AJUSTADOS EXITOSAMENTE")
            print("🎯 El Mayordomo ahora debería aprobar más trades")
            print("📈 Reinicia el sistema para aplicar los cambios")
        else:
            print(f"\n⚠️ NINGÚN TRADE APROBADO TODAVÍA")
            print("🔧 Puede que necesites ajustar más los thresholds")
            
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