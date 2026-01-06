#!/usr/bin/env python3
"""
Test Contextual Intelligence - Prueba exhaustiva de la inteligencia contextual
Verifica que el ML se adapte apropiadamente a diferentes contextos de mercado
"""

import sys
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.ml_volume_engine import MLVolumeEngine, create_market_context

class ContextualIntelligenceTester:
    """Tester para verificar inteligencia contextual del ML"""
    
    def __init__(self):
        self.ml_engine = MLVolumeEngine()
        if not self.ml_engine.load_models():
            raise ValueError("No se pudieron cargar modelos ML")
        
        # Old hardcoded values for comparison
        self.old_values = {
            'macdv_smallcaps': 1.2,
            'daily_plays': 0.8,
            'gap_go': 1.5,
            'volume_breakout': 2.0,
            'orb': 1.3
        }
        
        self.strategies = list(self.old_values.keys())
        
    def test_time_sensitivity(self):
        """Test: ¿Se adapta el ML a diferentes horas del día?"""
        print("🕐 TEST 1: SENSIBILIDAD TEMPORAL")
        print("-" * 50)
        
        base_ticker = {
            'ticker': 'TIME_TEST', 'price': 4.0, 'market_cap': 80000000,
            'avg_volume': 40000, 'float_shares': 20000000, 'sector': 'Technology',
            'percent_var': 3.0, 'ratio_vol': 1.5, 'volatility': 0.3
        }
        
        time_periods = [
            {'hour': 9, 'minute': 30, 'name': 'Market Open', 'expected': 'más restrictivo'},
            {'hour': 11, 'minute': 0, 'name': 'Mid Morning', 'expected': 'normal'},
            {'hour': 13, 'minute': 0, 'name': 'Lunch Time', 'expected': 'más restrictivo'},
            {'hour': 15, 'minute': 0, 'name': 'Power Hour', 'expected': 'normal'},
            {'hour': 15, 'minute': 45, 'name': 'Near Close', 'expected': 'más restrictivo'}
        ]
        
        results = {}
        
        for period in time_periods:
            test_time = datetime.now().replace(hour=period['hour'], minute=period['minute'])
            context = create_market_context(base_ticker, test_time)
            
            period_requirements = {}
            for strategy in self.strategies:
                req = self.ml_engine.predict_volume_requirement(strategy, context)
                period_requirements[strategy] = req
                
            results[period['name']] = period_requirements
            
            avg_req = np.mean(list(period_requirements.values()))
            print(f"   {period['name']:12} ({period['hour']:02d}:{period['minute']:02d}): Avg requirement = {avg_req:.2f}x")
        
        # Analyze time sensitivity
        morning_avg = np.mean(list(results['Mid Morning'].values()))
        lunch_avg = np.mean(list(results['Lunch Time'].values()))
        close_avg = np.mean(list(results['Near Close'].values()))
        
        time_sensitive = abs(morning_avg - lunch_avg) > 0.1 or abs(morning_avg - close_avg) > 0.1
        
        print(f"   📊 Variación temporal: {'✅ SÍ' if time_sensitive else '❌ NO'}")
        return time_sensitive
        
    def test_volatility_adaptation(self):
        """Test: ¿Se adapta el ML a diferentes niveles de volatilidad?"""
        print("\n📈 TEST 2: ADAPTACIÓN A VOLATILIDAD")
        print("-" * 50)
        
        base_ticker = {
            'ticker': 'VOL_TEST', 'price': 5.0, 'market_cap': 100000000,
            'avg_volume': 50000, 'float_shares': 25000000, 'sector': 'Healthcare',
            'percent_var': 0.0, 'ratio_vol': 2.0
        }
        
        volatility_scenarios = [
            {'volatility': 0.1, 'percent_var': 1.0, 'name': 'Baja Volatilidad', 'expected': 'menos restrictivo'},
            {'volatility': 0.3, 'percent_var': 3.0, 'name': 'Volatilidad Normal', 'expected': 'normal'},
            {'volatility': 0.6, 'percent_var': 8.0, 'name': 'Alta Volatilidad', 'expected': 'más restrictivo'},
            {'volatility': 0.9, 'percent_var': 15.0, 'name': 'Volatilidad Extrema', 'expected': 'muy restrictivo'}
        ]
        
        vol_requirements = {}
        
        for scenario in volatility_scenarios:
            ticker = base_ticker.copy()
            ticker['volatility'] = scenario['volatility']
            ticker['percent_var'] = scenario['percent_var']
            
            context = create_market_context(ticker)
            avg_req = np.mean([
                self.ml_engine.predict_volume_requirement(strategy, context)
                for strategy in self.strategies
            ])
            
            vol_requirements[scenario['name']] = avg_req
            print(f"   {scenario['name']:18}: Avg requirement = {avg_req:.2f}x")
        
        # Check if higher volatility = higher requirements
        low_vol = vol_requirements['Baja Volatilidad']
        high_vol = vol_requirements['Alta Volatilidad']
        extreme_vol = vol_requirements['Volatilidad Extrema']
        
        volatility_adaptive = high_vol > low_vol and extreme_vol >= high_vol
        
        print(f"   📊 Adaptación a volatilidad: {'✅ SÍ' if volatility_adaptive else '❌ NO'}")
        print(f"   📈 Progresión: {low_vol:.2f}x -> {high_vol:.2f}x -> {extreme_vol:.2f}x")
        return volatility_adaptive
        
    def test_market_cap_sensitivity(self):
        """Test: ¿Diferencia el ML entre large cap vs small cap?"""
        print("\n💰 TEST 3: SENSIBILIDAD AL MARKET CAP")
        print("-" * 50)
        
        cap_scenarios = [
            {'market_cap': 10000000, 'name': 'Micro Cap (<$10M)', 'expected': 'más restrictivo'},
            {'market_cap': 50000000, 'name': 'Small Cap ($50M)', 'expected': 'normal'},
            {'market_cap': 500000000, 'name': 'Mid Cap ($500M)', 'expected': 'menos restrictivo'},
            {'market_cap': 5000000000, 'name': 'Large Cap ($5B)', 'expected': 'menos restrictivo'}
        ]
        
        cap_requirements = {}
        
        for scenario in cap_scenarios:
            ticker = {
                'ticker': 'CAP_TEST', 'price': 8.0, 'market_cap': scenario['market_cap'],
                'avg_volume': 75000, 'float_shares': scenario['market_cap'] // 8,
                'sector': 'Technology', 'percent_var': 4.0, 'ratio_vol': 1.8, 'volatility': 0.4
            }
            
            context = create_market_context(ticker)
            avg_req = np.mean([
                self.ml_engine.predict_volume_requirement(strategy, context)
                for strategy in ['macdv_smallcaps', 'daily_plays', 'gap_go']  # Most relevant for caps
            ])
            
            cap_requirements[scenario['name']] = avg_req
            print(f"   {scenario['name']:20}: Avg requirement = {avg_req:.2f}x")
        
        # Check market cap sensitivity
        micro_req = cap_requirements['Micro Cap (<$10M)']
        large_req = cap_requirements['Large Cap ($5B)']
        
        cap_sensitive = abs(micro_req - large_req) > 0.2
        
        print(f"   📊 Sensibilidad al cap: {'✅ SÍ' if cap_sensitive else '❌ NO'}")
        return cap_sensitive
        
    def test_volume_context_intelligence(self):
        """Test: ¿Ajusta requirements basado en volumen actual vs requerido?"""
        print("\n📊 TEST 4: INTELIGENCIA DE CONTEXTO DE VOLUMEN")
        print("-" * 50)
        
        base_ticker = {
            'ticker': 'VOL_CONTEXT', 'price': 3.0, 'market_cap': 60000000,
            'avg_volume': 30000, 'float_shares': 20000000, 'sector': 'Energy',
            'percent_var': 5.0, 'volatility': 0.4
        }
        
        volume_scenarios = [
            {'ratio_vol': 0.5, 'name': 'Muy Bajo Volumen (0.5x)', 'expected': 'requirements bajos'},
            {'ratio_vol': 1.0, 'name': 'Volumen Normal (1.0x)', 'expected': 'requirements normales'},
            {'ratio_vol': 3.0, 'name': 'Alto Volumen (3.0x)', 'expected': 'requirements normales'},
            {'ratio_vol': 6.0, 'name': 'Volumen Extremo (6.0x)', 'expected': 'requirements altos (sospechoso)'}
        ]
        
        print("   Strategy comparison para diferentes niveles de volumen:")
        
        strategy_adaptations = {strategy: [] for strategy in self.strategies}
        
        for scenario in volume_scenarios:
            ticker = base_ticker.copy()
            ticker['ratio_vol'] = scenario['ratio_vol']
            
            context = create_market_context(ticker)
            
            print(f"\n   {scenario['name']}:")
            for strategy in self.strategies:
                ml_req = self.ml_engine.predict_volume_requirement(strategy, context)
                old_req = self.old_values[strategy]
                
                strategy_adaptations[strategy].append(ml_req)
                
                diff_pct = ((ml_req - old_req) / old_req) * 100
                if diff_pct > 10:
                    trend = "📈"
                elif diff_pct < -10:
                    trend = "📉"
                else:
                    trend = "➡️"
                    
                print(f"     {strategy:18}: {old_req:.2f}x -> {ml_req:.2f}x ({diff_pct:+5.1f}%) {trend}")
        
        # Check if ML adapts to volume context
        volume_intelligent = False
        for strategy, adaptations in strategy_adaptations.items():
            variation = max(adaptations) - min(adaptations)
            if variation > 0.3:  # Significant adaptation
                volume_intelligent = True
                break
        
        print(f"\n   📊 Inteligencia de volumen: {'✅ SÍ' if volume_intelligent else '❌ NO'}")
        return volume_intelligent
        
    def test_sector_awareness(self):
        """Test: ¿Diferencia el ML entre sectores?"""
        print("\n🏭 TEST 5: CONCIENCIA SECTORIAL")
        print("-" * 50)
        
        sectors = [
            {'sector': 'Technology', 'expected': 'requirements moderados'},
            {'sector': 'Healthcare', 'expected': 'requirements altos (volatilidad)'},
            {'sector': 'Energy', 'expected': 'requirements altos (volatilidad)'},
            {'sector': 'Finance', 'expected': 'requirements bajos (estabilidad)'},
            {'sector': 'Consumer', 'expected': 'requirements moderados'}
        ]
        
        base_ticker = {
            'ticker': 'SECTOR_TEST', 'price': 6.0, 'market_cap': 150000000,
            'avg_volume': 60000, 'float_shares': 25000000,
            'percent_var': 3.5, 'ratio_vol': 2.0, 'volatility': 0.35
        }
        
        sector_requirements = {}
        
        for sector_info in sectors:
            ticker = base_ticker.copy()
            ticker['sector'] = sector_info['sector']
            
            context = create_market_context(ticker)
            avg_req = np.mean([
                self.ml_engine.predict_volume_requirement(strategy, context)
                for strategy in self.strategies
            ])
            
            sector_requirements[sector_info['sector']] = avg_req
            print(f"   {sector_info['sector']:12}: Avg requirement = {avg_req:.2f}x")
        
        # Check sector differentiation
        sector_values = list(sector_requirements.values())
        sector_aware = (max(sector_values) - min(sector_values)) > 0.2
        
        print(f"   📊 Conciencia sectorial: {'✅ SÍ' if sector_aware else '❌ NO'}")
        return sector_aware
        
    def test_strategy_specialization(self):
        """Test: ¿Cada estrategia tiene comportamiento diferenciado?"""
        print("\n🎯 TEST 6: ESPECIALIZACIÓN POR ESTRATEGIA")
        print("-" * 50)
        
        # Single context, multiple strategies
        ticker = {
            'ticker': 'STRATEGY_TEST', 'price': 4.5, 'market_cap': 90000000,
            'avg_volume': 45000, 'float_shares': 20000000, 'sector': 'Technology',
            'percent_var': 6.0, 'ratio_vol': 2.5, 'volatility': 0.45
        }
        
        context = create_market_context(ticker)
        
        strategy_requirements = {}
        for strategy in self.strategies:
            ml_req = self.ml_engine.predict_volume_requirement(strategy, context)
            old_req = self.old_values[strategy]
            
            strategy_requirements[strategy] = {
                'ml': ml_req,
                'old': old_req,
                'diff': ml_req - old_req,
                'diff_pct': ((ml_req - old_req) / old_req) * 100
            }
        
        print("   Comparación por estrategia (mismo contexto):")
        for strategy, reqs in strategy_requirements.items():
            trend = "📈" if reqs['diff_pct'] > 5 else "📉" if reqs['diff_pct'] < -5 else "➡️"
            print(f"   {strategy:18}: {reqs['old']:.2f}x -> {reqs['ml']:.2f}x ({reqs['diff_pct']:+5.1f}%) {trend}")
        
        # Check strategy differentiation
        ml_values = [reqs['ml'] for reqs in strategy_requirements.values()]
        old_values = [reqs['old'] for reqs in strategy_requirements.values()]
        
        ml_variation = max(ml_values) - min(ml_values)
        old_variation = max(old_values) - min(old_values)
        
        more_specialized = ml_variation > old_variation
        
        print(f"   📊 Especialización ML: {'✅ MAYOR' if more_specialized else '❌ MENOR'}")
        print(f"   📈 Variación: Hardcoded={old_variation:.2f}x vs ML={ml_variation:.2f}x")
        return more_specialized

def run_contextual_intelligence_tests():
    """Ejecuta todos los tests de inteligencia contextual"""
    print("🧠 TESTS DE INTELIGENCIA CONTEXTUAL DEL ML")
    print("=" * 70)
    print("Verificando que el ML se adapte apropiadamente al contexto")
    print("=" * 70)
    
    try:
        tester = ContextualIntelligenceTester()
        
        test_results = {
            'time_sensitivity': tester.test_time_sensitivity(),
            'volatility_adaptation': tester.test_volatility_adaptation(),
            'market_cap_sensitivity': tester.test_market_cap_sensitivity(),
            'volume_intelligence': tester.test_volume_context_intelligence(),
            'sector_awareness': tester.test_sector_awareness(),
            'strategy_specialization': tester.test_strategy_specialization()
        }
        
        # Results summary
        print("\n" + "=" * 70)
        print("📊 RESULTADOS DE INTELIGENCIA CONTEXTUAL")
        print("=" * 70)
        
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        
        for test_name, result in test_results.items():
            status = "✅ SÍ" if result else "❌ NO"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        intelligence_score = (passed_tests / total_tests) * 100
        print(f"\n🧠 PUNTUACIÓN DE INTELIGENCIA: {passed_tests}/{total_tests} ({intelligence_score:.1f}%)")
        
        if intelligence_score >= 80:
            print("🎉 HIPÓTESIS CONFIRMADA: El sistema ML es CONTEXTUALMENTE INTELIGENTE")
            print("✅ Se adapta apropiadamente a diferentes condiciones del mercado")
            print("✅ No es simplemente más/menos conservador - es INTELIGENTE")
        elif intelligence_score >= 60:
            print("⚠️ HIPÓTESIS PARCIAL: El sistema muestra algo de inteligencia contextual")
        else:
            print("❌ HIPÓTESIS RECHAZADA: El sistema no muestra inteligencia contextual significativa")
        
        print("\n💡 CONCLUSIONES:")
        if test_results['time_sensitivity']:
            print("   • ⏰ Se adapta a diferentes horas del día")
        if test_results['volatility_adaptation']:
            print("   • 📈 Aumenta requirements con alta volatilidad")
        if test_results['market_cap_sensitivity']:
            print("   • 💰 Diferencia entre small caps y large caps")
        if test_results['volume_intelligence']:
            print("   • 📊 Ajusta requirements basado en contexto de volumen")
        if test_results['sector_awareness']:
            print("   • 🏭 Considera características sectoriales")
        if test_results['strategy_specialization']:
            print("   • 🎯 Cada estrategia tiene comportamiento especializado")
            
        print("\n🔄 IMPLICACIONES PARA TRADING:")
        print("   • Más estrategias activas en condiciones favorables")
        print("   • Mejor protección de capital en condiciones riesgosas")
        print("   • Eliminación de valores arbitrarios")
        print("   • Adaptación automática sin intervención manual")
        
        return intelligence_score >= 60
        
    except Exception as e:
        print(f"❌ Error en tests de inteligencia contextual: {e}")
        return False

if __name__ == "__main__":
    success = run_contextual_intelligence_tests()
    sys.exit(0 if success else 1)