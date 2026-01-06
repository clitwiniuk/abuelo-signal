#!/usr/bin/env python3
"""
Test del FinBERT Upgrade - Comparar modelo original vs mejorado
"""

import sys
import os
from datetime import datetime

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'scanner', 'smallcap'))

try:
    from scanner.smallcap.finbert_analyzer import FinBERTAnalyzer, test_finbert_analyzer
    print("✅ FinBERT Analyzer imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_2024_2025_keywords():
    """Test new 2024-2025 keywords detection"""
    print("\n🧪 TEST 1: Detección de keywords 2024-2025")
    print("-" * 50)
    
    analyzer = FinBERTAnalyzer()
    
    # Test headlines with new keywords
    test_cases = [
        {
            'headline': "Company announces AI-powered precision medicine platform for cancer treatment",
            'expected_type': 'AI_TECH',
            'expected_strength': '≥7'
        },
        {
            'headline': "Biotech receives accelerated approval for breakthrough CAR-T therapy",
            'expected_type': 'FDA',
            'expected_strength': '≥8'
        },
        {
            'headline': "Strategic alliance for CRISPR gene therapy development announced",
            'expected_type': 'M&A',
            'expected_strength': '≥7'
        },
        {
            'headline': "Company launches carbon neutral renewable energy initiative",
            'expected_type': 'ESG_SUSTAINABILITY',
            'expected_strength': '≥6'
        },
        {
            'headline': "Partnership for quantum computing digital therapeutics platform",
            'expected_type': 'AI_TECH',
            'expected_strength': '≥7'
        }
    ]
    
    results = []
    for i, case in enumerate(test_cases, 1):
        print(f"\n📰 Test {i}: {case['headline'][:60]}...")
        
        try:
            result = analyzer.analyze_headline(case['headline'], age_hours=2.0)
            
            print(f"   Catalyst Type: {result.catalyst_type}")
            print(f"   Strength: {result.catalyst_strength}/10")
            print(f"   Sentiment: {result.sentiment.upper()} ({result.confidence:.2f})")
            print(f"   Keywords: {', '.join(result.keywords_found[:3])}")
            print(f"   Reasoning: {result.reasoning}")
            
            # Check if meets expectations
            type_match = result.catalyst_type == case['expected_type']
            strength_ok = result.catalyst_strength >= int(case['expected_strength'].replace('≥', ''))
            
            status = "✅ PASS" if type_match and strength_ok else "❌ FAIL"
            print(f"   Status: {status}")
            
            if not type_match:
                print(f"   ⚠️  Expected type: {case['expected_type']}, got: {result.catalyst_type}")
            if not strength_ok:
                print(f"   ⚠️  Expected strength: {case['expected_strength']}, got: {result.catalyst_strength}")
            
            results.append({
                'headline': case['headline'],
                'success': type_match and strength_ok,
                'result': result
            })
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                'headline': case['headline'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    successes = sum(1 for r in results if r['success'])
    print(f"\n📊 RESUMEN TEST 1:")
    print(f"   Exitosos: {successes}/{len(test_cases)} ({successes/len(test_cases)*100:.1f}%)")
    
    return results

def test_enhanced_scoring():
    """Test enhanced scoring algorithm"""
    print("\n🧪 TEST 2: Algoritmo de scoring mejorado")
    print("-" * 50)
    
    analyzer = FinBERTAnalyzer()
    
    # Test cases comparing old vs new expected behavior
    test_cases = [
        {
            'headline': "FDA grants breakthrough therapy designation for revolutionary AI-assisted immunotherapy",
            'age_hours': 1.0,
            'expected_min_strength': 8,
            'reason': "FDA + AI + immunotherapy keywords should trigger high strength"
        },
        {
            'headline': "Company reports positive earnings but facing regulatory concerns",
            'age_hours': 4.0,
            'expected_min_strength': 4,
            'reason': "Mixed sentiment should get moderate strength"
        },
        {
            'headline': "Strategic partnership for quantum computing platform development announced",
            'age_hours': 12.0,
            'expected_min_strength': 5,
            'reason': "AI_TECH catalyst should have slower decay"
        },
        {
            'headline': "Quarterly earnings beat estimates by small margin",
            'age_hours': 8.0,
            'expected_max_strength': 5,
            'reason': "Standard earnings should have faster decay"
        }
    ]
    
    results = []
    for i, case in enumerate(test_cases, 1):
        print(f"\n📊 Test {i}: {case['headline'][:60]}...")
        print(f"   Age: {case['age_hours']} hours")
        
        try:
            result = analyzer.analyze_headline(case['headline'], age_hours=case['age_hours'])
            
            print(f"   Catalyst: {result.catalyst_type}")
            print(f"   Strength: {result.catalyst_strength}/10")
            print(f"   Sentiment: {result.sentiment.upper()} ({result.confidence:.2f})")
            print(f"   Reasoning: {result.reasoning}")
            
            # Check expectations
            if 'expected_min_strength' in case:
                meets_expectation = result.catalyst_strength >= case['expected_min_strength']
                print(f"   Expected: ≥{case['expected_min_strength']} | Got: {result.catalyst_strength} | {'✅' if meets_expectation else '❌'}")
            else:
                meets_expectation = result.catalyst_strength <= case['expected_max_strength']
                print(f"   Expected: ≤{case['expected_max_strength']} | Got: {result.catalyst_strength} | {'✅' if meets_expectation else '❌'}")
            
            print(f"   Reason: {case['reason']}")
            
            results.append({
                'headline': case['headline'],
                'success': meets_expectation,
                'result': result
            })
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                'headline': case['headline'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    successes = sum(1 for r in results if r['success'])
    print(f"\n📊 RESUMEN TEST 2:")
    print(f"   Exitosos: {successes}/{len(test_cases)} ({successes/len(test_cases)*100:.1f}%)")
    
    return results

def test_real_headlines():
    """Test with real smallcap headlines"""
    print("\n🧪 TEST 3: Headlines reales de smallcaps")
    print("-" * 50)
    
    analyzer = FinBERTAnalyzer()
    
    # Real headlines from recent smallcap movers
    real_headlines = [
        "Tharimmune Reports Pharmacokinetic Simulation Results for TH104 as Prophylaxis Against Respiratory Depression",
        "SPAI announces strategic collaboration for AI-powered diagnostic platform",
        "Biotech receives FDA fast track designation for novel CAR-T cell therapy",
        "Company completes merger agreement with private equity firm at premium valuation",
        "Quarterly earnings exceed expectations driven by strong SaaS revenue growth"
    ]
    
    print(f"Testing {len(real_headlines)} real headlines...")
    
    results = []
    for i, headline in enumerate(real_headlines, 1):
        print(f"\n📰 Real headline {i}:")
        print(f"   \"{headline}\"")
        
        try:
            result = analyzer.analyze_headline(headline, age_hours=1.5)
            
            print(f"   🎯 Type: {result.catalyst_type}")
            print(f"   💪 Strength: {result.catalyst_strength}/10")
            print(f"   😊 Sentiment: {result.sentiment.upper()} ({result.confidence:.2f})")
            print(f"   🔑 Keywords: {', '.join(result.keywords_found)}")
            print(f"   🧠 Reasoning: {result.reasoning}")
            
            # Grade the result
            if result.catalyst_strength >= 7:
                grade = "🟢 STRONG"
            elif result.catalyst_strength >= 5:
                grade = "🟡 MODERATE" 
            else:
                grade = "🔴 WEAK"
            
            print(f"   📊 Grade: {grade}")
            
            results.append({
                'headline': headline,
                'result': result,
                'grade': grade
            })
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                'headline': headline,
                'error': str(e)
            })
    
    # Summary
    strong_count = sum(1 for r in results if 'result' in r and r['result'].catalyst_strength >= 7)
    moderate_count = sum(1 for r in results if 'result' in r and 5 <= r['result'].catalyst_strength < 7)
    weak_count = sum(1 for r in results if 'result' in r and r['result'].catalyst_strength < 5)
    
    print(f"\n📊 RESUMEN TEST 3:")
    print(f"   🟢 Strong (≥7): {strong_count}")
    print(f"   🟡 Moderate (5-6): {moderate_count}")
    print(f"   🔴 Weak (<5): {weak_count}")
    
    return results

def main():
    """Run all FinBERT upgrade tests"""
    print("🚀 TESTING FINBERT UPGRADE - 2024-2025 ENHANCED")
    print("=" * 60)
    
    print("📋 Testing enhanced FinBERT-tone model with:")
    print("   • Model: yiyanghkust/finbert-tone (upgraded from ProsusAI/finbert)")
    print("   • Enhanced keywords: 2024-2025 terms")
    print("   • Improved scoring: catalyst-specific decay")
    print("   • New categories: AI_TECH, ESG_SUSTAINABILITY")
    
    all_results = []
    
    try:
        # Test 1: 2024-2025 keywords
        results1 = test_2024_2025_keywords()
        all_results.extend(results1)
        
        # Test 2: Enhanced scoring
        results2 = test_enhanced_scoring()
        all_results.extend(results2)
        
        # Test 3: Real headlines
        results3 = test_real_headlines()
        all_results.extend(results3)
        
        # Overall summary
        print(f"\n{'='*60}")
        print("🎉 RESUMEN FINAL DEL UPGRADE")
        print("=" * 60)
        
        total_tests = len([r for r in all_results if 'success' in r])
        successful_tests = len([r for r in all_results if r.get('success', False)])
        
        if total_tests > 0:
            success_rate = successful_tests / total_tests * 100
            print(f"✅ Tests exitosos: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
        
        print(f"📊 Headlines analizados: {len(all_results)}")
        print(f"🎯 Nuevas categorías: AI_TECH, ESG_SUSTAINABILITY")
        print(f"🔑 Keywords expandidos: ~50+ términos 2024-2025")
        print(f"🧠 Modelo mejorado: yiyanghkust/finbert-tone")
        
        if success_rate >= 80:
            print(f"\n🎉 UPGRADE EXITOSO - FinBERT mejorado significativamente!")
        elif success_rate >= 60:
            print(f"\n✅ UPGRADE BUENO - FinBERT mejorado con ajustes menores necesarios")
        else:
            print(f"\n⚠️ UPGRADE PARCIAL - Revisar configuración y thresholds")
        
        return success_rate >= 60
        
    except Exception as e:
        print(f"\n💥 Error en testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Test interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error inesperado: {e}")
        sys.exit(1)