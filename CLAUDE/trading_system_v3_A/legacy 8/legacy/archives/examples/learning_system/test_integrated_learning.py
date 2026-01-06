#!/usr/bin/env python3
"""
Test del Sistema de Aprendizaje Integrado
========================================

Script para probar la integración completa del sistema de aprendizaje
con el análisis avanzado de calidad.
"""

import sys
from pathlib import Path
import sqlite3
from datetime import datetime
import random

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir / "quality_core"))

from quality_core.advanced_setup_analyzer import AdvancedSetupAnalyzer, analyze_setup_comprehensive
from quality_core.learning_system import AutoLearningSystem

def create_test_database():
    """Crear base de datos de prueba"""
    db_path = "test_learning.db"
    
    # Eliminar si existe
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    return db_path

def test_basic_integration():
    """Test básico de integración"""
    print("🧪 Testing Basic Integration")
    print("=" * 40)
    
    db_path = create_test_database()
    
    try:
        # Initialize analyzer with learning system
        analyzer = AdvancedSetupAnalyzer(learning_db_path=db_path)
        
        print(f"✅ Analyzer initialized with learning system")
        print(f"🗄️  Database: {db_path}")
        print(f"🧠 Learning system available: {analyzer.learning_system is not None}")
        
        # Test analysis with PPSI example (the problematic case)
        print(f"\n📊 Testing PPSI Analysis (Problematic Case)")
        analysis = analyzer.comprehensive_setup_analysis(
            ticker="PPSI",
            current_price=4.42,
            current_volume=80_600_000,
            premarket_gap_pct=42.1
        )
        
        print(f"📈 PPSI Results:")
        print(f"   Grade: {analysis.grade}")
        print(f"   Score: {analysis.overall_score}/100")
        print(f"   Recommendation: {analysis.recommendation}")
        
        if analysis.red_flags:
            print(f"   🔴 Red Flags: {len(analysis.red_flags)}")
            for flag in analysis.red_flags:
                print(f"      • {flag}")
        
        if analysis.key_factors:
            print(f"   ✅ Key Factors: {len(analysis.key_factors)}")
            for factor in analysis.key_factors:
                print(f"      • {factor}")
        
        # Test another ticker with better consolidation pattern
        print(f"\n📊 Testing Hypothetical Good Setup")
        good_analysis = analyzer.comprehensive_setup_analysis(
            ticker="GOOD",
            current_price=3.50,
            current_volume=5_000_000,
            premarket_gap_pct=15.2
        )
        
        print(f"📈 GOOD Results:")
        print(f"   Grade: {good_analysis.grade}")
        print(f"   Score: {good_analysis.overall_score}/100")
        print(f"   Recommendation: {good_analysis.recommendation}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in basic integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_learning_progression():
    """Test progresión del aprendizaje"""
    print(f"\n🎓 Testing Learning Progression")
    print("=" * 40)
    
    db_path = "test_learning.db"
    
    try:
        auto_system = AutoLearningSystem(db_path)
        
        # Generate multiple predictions with different outcomes
        test_tickers = ["TICK1", "TICK2", "TICK3", "TICK4", "TICK5"]
        
        print(f"📊 Simulating {len(test_tickers)} predictions...")
        
        for i, ticker in enumerate(test_tickers):
            # Create varied analysis results
            analysis_result = {
                'ticker': ticker,
                'price': random.uniform(2.0, 10.0),
                'volume': random.randint(1_000_000, 50_000_000),
                'premarket_gap_pct': random.uniform(10.0, 60.0),
                'consolidation_score': random.randint(20, 90),
                'timing_score': random.randint(30, 80),
                'volume_score': random.randint(40, 95),
                'news_score': random.randint(45, 85),
                'overall_score': random.randint(40, 85),
                'grade': random.choice(['A+', 'A', 'A-', 'B+', 'B']),
                'recommendation': 'BUY - Test prediction'
            }
            
            pred_id, weights = auto_system.log_and_learn(ticker, analysis_result)
            print(f"   {i+1}. {ticker} - Prediction ID: {pred_id}")
        
        # Show current stats
        stats = auto_system.get_system_stats()
        print(f"\n📈 Current System Stats:")
        print(f"   Total Predictions: {stats['total_predictions']}")
        print(f"   Learning Enabled: {stats['learning_enabled']}")
        print(f"   Current Weights: {stats['current_weights']}")
        
        # Simulate some results (in real system this would happen automatically)
        print(f"\n🔄 Simulating results update...")
        
        # Check for untracked predictions
        tracker = auto_system.tracker
        untracked = tracker.get_untracked_predictions()
        print(f"   Found {len(untracked)} untracked predictions")
        
        # Simulate results for first few predictions
        for pred in untracked[:3]:
            # Simulate success/failure
            success = random.choice([True, False])
            return_pct = random.uniform(15.0, 40.0) if success else random.uniform(-10.0, -25.0)
            
            # Manually insert simulated result
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            final_result = 'win' if return_pct >= 10 else 'loss' if return_pct <= -5 else 'neutral'
            
            cursor.execute("""
                INSERT INTO prediction_results (
                    prediction_id, ticker, return_eod, final_result,
                    price_eod, max_gain_pct, max_loss_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pred['prediction_id'], pred['ticker'], return_pct, final_result,
                pred['original_price'] * (1 + return_pct/100),
                max(0, return_pct), min(0, return_pct)
            ))
            
            cursor.execute("""
                UPDATE predictions SET result_tracked = TRUE WHERE id = ?
            """, (pred['prediction_id'],))
            
            conn.commit()
            conn.close()
            
            print(f"   {pred['ticker']}: {final_result} ({return_pct:.1f}%)")
        
        # Check updated stats
        updated_stats = auto_system.get_system_stats()
        print(f"\n📊 Updated Stats:")
        print(f"   Total Predictions: {updated_stats['total_predictions']}")
        if 'accuracy_metrics' in updated_stats:
            metrics = updated_stats['accuracy_metrics']
            print(f"   Win Rate: {metrics['win_rate']:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in learning progression test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_function():
    """Test función de integración standalone"""
    print(f"\n🔧 Testing Integration Function")
    print("=" * 40)
    
    try:
        # Test with default learning database
        result = analyze_setup_comprehensive(
            ticker="INTEG",
            current_price=5.25,
            current_volume=15_000_000,
            premarket_gap_pct=25.5
        )
        
        print(f"📊 Integration Function Results:")
        print(f"   Ticker: {result['ticker']}")
        print(f"   Grade: {result['grade']}")
        print(f"   Overall Score: {result['overall_score']}")
        print(f"   Recommendation: {result['recommendation']}")
        print(f"   Risk Level: {result['risk_level']}")
        
        # Test with custom learning database
        custom_result = analyze_setup_comprehensive(
            ticker="CUSTOM",
            current_price=3.75,
            current_volume=8_000_000,
            premarket_gap_pct=18.3,
            learning_db_path="test_learning.db"
        )
        
        print(f"\n📊 Custom DB Results:")
        print(f"   Ticker: {custom_result['ticker']}")
        print(f"   Grade: {custom_result['grade']}")
        print(f"   Overall Score: {custom_result['overall_score']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in integration function test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Ejecutar todos los tests"""
    print("🚀 INTEGRATED LEARNING SYSTEM TEST")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Basic Integration", test_basic_integration),
        ("Learning Progression", test_learning_progression),
        ("Integration Function", test_integration_function)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n" + "=" * 60)
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
    
    print(f"\n" + "=" * 60)
    print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Learning system integration is working correctly.")
        print(f"\n💡 Next steps:")
        print(f"   1. Use 'python quality_core/learning_monitor.py stats' to monitor learning")
        print(f"   2. Integrate with main quality_trading_standalone.py")
        print(f"   3. Start collecting real predictions and results")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    print(f"\n🗄️  Test database created: test_learning.db")
    print(f"🔧 Use learning_monitor.py to inspect the test data")

if __name__ == "__main__":
    main()