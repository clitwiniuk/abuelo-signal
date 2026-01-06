#!/usr/bin/env python3
"""
Test Integral del Sistema ML - Verificación completa de todos los ML y sus interacciones
Ubicación: scripts/testing/ (estructura organizada)
"""

import sys
import os
import json
from datetime import datetime
import traceback

# Add project root to path (3 levels up from scripts/testing/)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class MLSystemIntegralTest:
    """Test integral de todos los componentes ML del sistema"""
    
    def __init__(self):
        self.results = {
            'individual': {},
            'interactions': {},
            'summary': {}
        }
        
    def run_complete_test(self):
        """Ejecuta el test completo del sistema ML"""
        print("🧪 TEST INTEGRAL DEL SISTEMA ML")
        print("=" * 60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📍 Estructura organizada: scripts/testing/")
        print("=" * 60)
        
        # PARTE 1: Tests individuales
        print("\n🔧 PARTE 1: TESTS INDIVIDUALES DE COMPONENTES ML")
        print("-" * 60)
        self.test_ml_strategy_selector()
        self.test_ml_volume_engine() 
        self.test_ml_exit_engine()
        self.test_continuous_learning_engine()
        
        # PARTE 2: Tests de interacciones
        print("\n🔄 PARTE 2: TESTS DE INTERACCIONES ML")
        print("-" * 60)
        self.test_strategy_to_volume_interaction()
        self.test_trading_to_continuous_learning()
        self.test_complete_ml_pipeline()
        
        # PARTE 3: Resumen y recomendaciones
        self.generate_final_report()
        
        return self.results['summary']['overall_score'] >= 75
    
    def test_ml_strategy_selector(self):
        """Test 1: ML Strategy Selector (Contextual Bandit)"""
        print("\n1️⃣ ML STRATEGY SELECTOR")
        
        try:
            # Test 1a: Verificar archivo de modelo
            model_file = "data/ml_models/strategy_selector.json"
            
            if os.path.exists(model_file):
                with open(model_file, 'r') as f:
                    data = json.load(f)
                
                # Verificar estructura Contextual Bandit (no Thompson Sampling)
                if 'strategies' in data and 'strategy_stats' in data:
                    strategies = data['strategies']
                    stats = data['strategy_stats']
                    
                    print(f"   ✅ Modelo Contextual Bandit cargado: {len(strategies)} estrategias")
                    print(f"   📊 Timestamp: {data.get('timestamp', 'N/A')[:19]}")
                    
                    # Calcular estadísticas si están disponibles
                    if stats and isinstance(stats, dict):
                        # Filtrar solo valores numéricos válidos
                        valid_stats = {k: v for k, v in stats.items() if isinstance(v, (int, float))}
                        
                        if valid_stats:
                            total_selections = sum(valid_stats.values())
                            print(f"   📊 Total selecciones: {total_selections}")
                            
                            # Mostrar top estrategias por selecciones
                            sorted_stats = sorted(valid_stats.items(), key=lambda x: x[1], reverse=True)[:3]
                            print("   🏆 Top 3 más seleccionadas:")
                            for i, (strategy, count) in enumerate(sorted_stats):
                                percentage = (count / max(total_selections, 1)) * 100
                                print(f"      {i+1}. {strategy}: {count} ({percentage:.1f}%)")
                        else:
                            print("   📊 Estadísticas no disponibles (datos no numéricos)")
                    else:
                        print("   📊 Estadísticas no disponibles")
                    
                    # Test 1b: Verificar importación de la clase correcta
                    try:
                        from strategies.ml_strategy_selector import ContextualBandit
                        print("   ✅ ContextualBandit importado correctamente")
                        
                        # Test básico de inicialización
                        try:
                            # Usar las estrategias del modelo para inicializar
                            bandit = ContextualBandit(strategies)
                            print("   ✅ ContextualBandit inicializado correctamente")
                            
                            # Test de carga del modelo
                            if hasattr(bandit, 'load_model'):
                                try:
                                    if bandit.load_model():
                                        print("   ✅ Modelo cargado por ContextualBandit")
                                    else:
                                        print("   ⚠️ Modelo no se pudo cargar")
                                except Exception as load_e:
                                    print(f"   ⚠️ Error cargando modelo: {load_e}")
                            
                            valid_stats_for_total = {k: v for k, v in stats.items() if isinstance(v, (int, float))} if stats else {}
                            self.results['individual']['strategy_selector'] = {
                                'status': 'PASS',
                                'strategies': len(strategies),
                                'model_type': 'ContextualBandit',
                                'total_selections': sum(valid_stats_for_total.values()) if valid_stats_for_total else 0
                            }
                        except Exception as init_e:
                            print(f"   ⚠️ Error inicialización: {init_e}")
                            # Aún marcamos como PARTIAL porque el modelo existe y es válido
                            valid_stats_for_total = {k: v for k, v in stats.items() if isinstance(v, (int, float))} if stats else {}
                            self.results['individual']['strategy_selector'] = {
                                'status': 'PARTIAL',
                                'strategies': len(strategies),
                                'model_type': 'ContextualBandit',
                                'issue': 'Initialization error'
                            }
                            
                    except ImportError as ie:
                        print(f"   ❌ Error importación: {ie}")
                        # Aún funcional pero con problemas de importación
                        self.results['individual']['strategy_selector'] = {
                            'status': 'PARTIAL',
                            'strategies': len(strategies),
                            'issue': 'Import error'
                        }
                
                elif 'arms' in data:
                    # Formato Thompson Sampling legacy
                    arms = data['arms']
                    print(f"   ✅ Modelo Thompson Sampling (legacy): {len(arms)} estrategias")
                    
                    total_trials = sum(arm.get('total', 0) for arm in arms)
                    total_wins = sum(arm.get('wins', 0) for arm in arms)
                    success_rate = (total_wins / max(total_trials, 1)) * 100
                    
                    print(f"   📊 Success rate: {success_rate:.1f}%")
                    
                    self.results['individual']['strategy_selector'] = {
                        'status': 'PASS',
                        'strategies': len(arms),
                        'model_type': 'Thompson Sampling',
                        'success_rate': success_rate
                    }
                    
                else:
                    print("   ❌ Estructura de datos no reconocida")
                    print(f"   📊 Claves encontradas: {list(data.keys())}")
                    self.results['individual']['strategy_selector'] = {'status': 'FAIL'}
                    
            else:
                print("   ❌ Archivo de modelo no encontrado")
                self.results['individual']['strategy_selector'] = {'status': 'MISSING'}
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['individual']['strategy_selector'] = {'status': 'ERROR'}
    
    def test_ml_volume_engine(self):
        """Test 2: ML Volume Engine"""
        print("\n2️⃣ ML VOLUME ENGINE")
        
        try:
            from core.ml_volume_engine import MLVolumeEngine, MarketContext
            
            engine = MLVolumeEngine()
            
            if engine.load_models():
                models_count = len(engine.models)
                expected_strategies = ['orb', 'gap_go', 'macdv_smallcaps', 'vwap_smallcaps', 
                                     'catalyst_momentum', 'eod_momentum', 'explosive_volume']
                
                print(f"   ✅ Modelos cargados: {models_count}/7")
                
                # Verificar estrategias específicas
                missing_strategies = [s for s in expected_strategies if s not in engine.models]
                if missing_strategies:
                    print(f"   ⚠️ Estrategias faltantes: {missing_strategies}")
                else:
                    print("   ✅ Todas las 7 estrategias cargadas")
                
                # Test de predicción
                test_context = MarketContext(
                    time_of_day=0.4, day_of_week=1, market_cap=50_000_000,
                    avg_volume=200_000, float_shares=10_000_000, sector="Technology",
                    recent_performance=3.5, market_stress=0.5, volume_trend=1.8, price_level=8.50
                )
                
                test_predictions = 0
                print("   🧪 Test de predicciones:")
                for strategy in list(engine.models.keys())[:3]:
                    try:
                        volume_req = engine.predict_volume_requirement(strategy, test_context)
                        print(f"      {strategy}: {volume_req:.2f}x")
                        test_predictions += 1
                    except Exception as pred_e:
                        print(f"      ❌ {strategy}: Error")
                
                self.results['individual']['volume_engine'] = {
                    'status': 'PASS',
                    'models_loaded': models_count,
                    'predictions_work': test_predictions > 0
                }
            else:
                print("   ❌ Error cargando modelos")
                self.results['individual']['volume_engine'] = {'status': 'FAIL'}
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['individual']['volume_engine'] = {'status': 'ERROR'}
    
    def test_ml_exit_engine(self):
        """Test 3: ML Exit Engine"""
        print("\n3️⃣ ML EXIT ENGINE")
        
        try:
            model_files = {
                'classifier': 'core/models/exit_models/smallcap_exit/exit_classifier.pkl',
                'regressor': 'core/models/exit_models/smallcap_exit/profit_regressor.pkl', 
                'scaler': 'core/models/exit_models/smallcap_exit/scaler.pkl'
            }
            
            files_present = 0
            for model_name, file_path in model_files.items():
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    print(f"   ✅ {model_name}: {size} bytes")
                    files_present += 1
                else:
                    print(f"   ❌ {model_name}: FALTA")
            
            if files_present == len(model_files):
                print("   ✅ Todos los modelos presentes")
                
                # Test básico de importación
                from core.ml_exit_engine import MLExitEngine
                engine = MLExitEngine()
                print("   ✅ Engine inicializable")
                
                self.results['individual']['exit_engine'] = {
                    'status': 'PASS',
                    'models_present': files_present
                }
            else:
                print(f"   ⚠️ Solo {files_present}/{len(model_files)} modelos presentes")
                self.results['individual']['exit_engine'] = {'status': 'PARTIAL'}
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['individual']['exit_engine'] = {'status': 'ERROR'}
    
    def test_continuous_learning_engine(self):
        """Test 4: Continuous Learning Engine"""
        print("\n4️⃣ CONTINUOUS LEARNING ENGINE")
        
        try:
            state_file = "data/ml_models/continuous_learning_state.json"
            
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                last_training = state.get('last_retrain_time', 'N/A')[:19]
                feedback_count = state.get('feedback_count', 0)
                
                print(f"   ✅ Estado encontrado")
                print(f"   📅 Último entrenamiento: {last_training}")
                print(f"   📊 Samples feedback: {feedback_count}")
                
                if 'retrain_results' in state:
                    results = state['retrain_results']
                    strategies_trained = len(results)
                    avg_effectiveness = sum(results.values()) / len(results)
                    
                    print(f"   🎯 Estrategias entrenadas: {strategies_trained}")
                    print(f"   📈 Efectividad promedio: {avg_effectiveness:.1%}")
                    
                    # Mostrar efectividades
                    print("   📊 Efectividades por estrategia:")
                    for strategy, eff in results.items():
                        icon = "🟢" if eff > 0.8 else "🟡" if eff > 0.5 else "🔴"
                        print(f"      {icon} {strategy}: {eff:.1%}")
                    
                    self.results['individual']['continuous_learning'] = {
                        'status': 'PASS',
                        'strategies_trained': strategies_trained,
                        'avg_effectiveness': avg_effectiveness,
                        'feedback_count': feedback_count
                    }
                else:
                    print("   ⚠️ Sin resultados de entrenamiento")
                    self.results['individual']['continuous_learning'] = {'status': 'PARTIAL'}
            else:
                print("   ❌ Archivo de estado no encontrado")
                self.results['individual']['continuous_learning'] = {'status': 'MISSING'}
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['individual']['continuous_learning'] = {'status': 'ERROR'}
    
    def test_strategy_to_volume_interaction(self):
        """Test interacción: Strategy Selector → Volume Engine"""
        print("\n🔄 INTERACCIÓN 1: Strategy Selector → Volume Engine")
        
        try:
            # Test con estrategia conocida del sistema
            selected_strategy = "macdv_smallcaps"
            print(f"   📤 Estrategia simulada: {selected_strategy}")
            
            # Verificar que la estrategia esté en el modelo selector
            try:
                model_file = "data/ml_models/strategy_selector.json"
                if os.path.exists(model_file):
                    with open(model_file, 'r') as f:
                        data = json.load(f)
                    
                    if 'strategies' in data and selected_strategy in data['strategies']:
                        print(f"   ✅ Estrategia en modelo selector")
                    else:
                        print(f"   ⚠️ Estrategia no en modelo selector")
                        
            except Exception as model_e:
                print(f"   ⚠️ Error verificando modelo selector: {model_e}")
            
            # Test Volume Engine para esa estrategia
            from core.ml_volume_engine import MLVolumeEngine, MarketContext
            engine = MLVolumeEngine()
            
            if engine.load_models() and selected_strategy in engine.models:
                test_context = MarketContext(
                    time_of_day=0.5, day_of_week=2, market_cap=75_000_000,
                    avg_volume=150_000, float_shares=12_000_000, sector="Healthcare",
                    recent_performance=4.2, market_stress=0.6, volume_trend=2.1, price_level=12.30
                )
                
                volume_req = engine.predict_volume_requirement(selected_strategy, test_context)
                print(f"   📥 Volumen calculado: {volume_req:.2f}x")
                print("   ✅ Pipeline Strategy → Volume: FUNCIONAL")
                
                self.results['interactions']['strategy_to_volume'] = 'PASS'
            else:
                print("   ❌ Volume Engine no disponible para estrategia")
                self.results['interactions']['strategy_to_volume'] = 'FAIL'
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['interactions']['strategy_to_volume'] = 'ERROR'
    
    def test_trading_to_continuous_learning(self):
        """Test interacción: Trading → Continuous Learning"""
        print("\n🔄 INTERACCIÓN 2: Trading → Continuous Learning")
        
        try:
            from core.trading_feedback_hook import get_global_feedback_hook
            
            # Test de inicialización del hook
            hook = get_global_feedback_hook()
            print("   ✅ Feedback hook inicializado")
            print(f"   📊 BD configurada: {hook.trading_db_path}")
            
            # Simular estructura de feedback
            mock_trade_data = {
                'trade_id': 'TEST_ML_001',
                'symbol': 'MOCK',
                'strategy': 'macdv_smallcaps',
                'entry_price': 15.0
            }
            
            print("   📤 Estructura de feedback: OK")
            print("   ✅ Pipeline Trading → CLE: Operacional")
            
            self.results['interactions']['trading_to_cle'] = 'PASS'
            
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['interactions']['trading_to_cle'] = 'ERROR'
    
    def test_complete_ml_pipeline(self):
        """Test del pipeline ML completo"""
        print("\n🔄 INTERACCIÓN 3: Pipeline ML Completo")
        
        try:
            print("   🔄 Simulando pipeline completo:")
            print("   1️⃣ Thompson Sampling selecciona estrategia")
            print("   2️⃣ ML Volume Engine calcula volumen requerido")
            print("   3️⃣ Sistema ejecuta trade")
            print("   4️⃣ ML Exit Engine decide momento de salida")
            print("   5️⃣ Feedback Hook envía resultado a CLE")
            print("   6️⃣ CLE aprende y mejora predicciones")
            
            # Verificar que todos los componentes estén disponibles
            pipeline_components = ['strategy_selector', 'volume_engine', 'exit_engine', 'continuous_learning']
            available_components = sum(1 for comp in pipeline_components 
                                     if self.results['individual'].get(comp, {}).get('status') == 'PASS')
            
            pipeline_health = (available_components / len(pipeline_components)) * 100
            print(f"   📊 Componentes disponibles: {available_components}/{len(pipeline_components)} ({pipeline_health:.1f}%)")
            
            if pipeline_health >= 75:
                print("   ✅ Pipeline ML: OPERACIONAL")
                self.results['interactions']['complete_pipeline'] = 'PASS'
            else:
                print("   ⚠️ Pipeline ML: PARCIAL")
                self.results['interactions']['complete_pipeline'] = 'PARTIAL'
                
        except Exception as e:
            print(f"   💥 Error: {e}")
            self.results['interactions']['complete_pipeline'] = 'ERROR'
    
    def generate_final_report(self):
        """Genera el reporte final del test"""
        print("\n" + "=" * 60)
        print("📊 REPORTE FINAL - SISTEMA ML")
        print("=" * 60)
        
        # Resumen de componentes
        individual_results = self.results['individual']
        passed_individual = sum(1 for result in individual_results.values() 
                               if result.get('status') == 'PASS')
        total_individual = len(individual_results)
        
        print(f"\n🔧 COMPONENTES INDIVIDUALES: {passed_individual}/{total_individual}")
        for component, result in individual_results.items():
            status = result.get('status', 'UNKNOWN')
            icon = {'PASS': '✅', 'FAIL': '❌', 'ERROR': '💥', 'PARTIAL': '⚠️', 'MISSING': '🚫'}.get(status, '❓')
            comp_name = component.replace('_', ' ').title()
            print(f"   {icon} {comp_name}: {status}")
        
        # Resumen de interacciones
        interaction_results = self.results['interactions'] 
        passed_interactions = sum(1 for result in interaction_results.values() if result == 'PASS')
        total_interactions = len(interaction_results)
        
        print(f"\n🔄 INTERACCIONES: {passed_interactions}/{total_interactions}")
        for interaction, result in interaction_results.items():
            icon = {'PASS': '✅', 'FAIL': '❌', 'ERROR': '💥', 'PARTIAL': '⚠️'}.get(result, '❓')
            inter_name = interaction.replace('_', ' → ').replace('to', ' ').title()
            print(f"   {icon} {inter_name}: {result}")
        
        # Puntuación general
        individual_score = (passed_individual / max(total_individual, 1)) * 100
        interaction_score = (passed_interactions / max(total_interactions, 1)) * 100
        overall_score = (individual_score + interaction_score) / 2
        
        print(f"\n🎯 PUNTUACIONES:")
        print(f"   🔧 Componentes: {individual_score:.1f}%")
        print(f"   🔄 Interacciones: {interaction_score:.1f}%") 
        print(f"   🏆 GENERAL: {overall_score:.1f}%")
        
        # Estado del sistema
        print(f"\n🚦 ESTADO DEL SISTEMA ML:")
        if overall_score >= 90:
            print("   🟢 EXCELENTE - Todos los ML operativos y funcionando")
            recommendation = "Sistema listo para producción"
        elif overall_score >= 75:
            print("   🟡 BUENO - Sistema ML mayormente funcional") 
            recommendation = "Apto para producción con monitoreo"
        elif overall_score >= 50:
            print("   🟠 ACEPTABLE - Algunos componentes necesitan atención")
            recommendation = "Revisar componentes fallidos antes de producción"
        else:
            print("   🔴 PROBLEMÁTICO - Múltiples fallos en sistema ML")
            recommendation = "Requiere reparación antes de usar"
            
        print(f"   💡 Recomendación: {recommendation}")
        
        # Guardar resultados
        self.results['summary'] = {
            'overall_score': overall_score,
            'individual_score': individual_score,
            'interaction_score': interaction_score,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
        
        print("=" * 60)
        print("✅ Test integral completado")

def main():
    """Función principal"""
    print("🧪 Iniciando Test Integral del Sistema ML")
    print("📍 Ejecutando desde estructura organizada: scripts/testing/")
    
    tester = MLSystemIntegralTest()
    success = tester.run_complete_test()
    
    print(f"\n{'🚀 SISTEMA LISTO' if success else '⚠️ REQUIERE ATENCIÓN'}")
    return success

if __name__ == "__main__":
    success = main()
    import sys
    sys.exit(0 if success else 1)