#!/usr/bin/env python3
"""
Debug ML Strategy Selector - Diagnóstico específico del problema
Ubicación: scripts/testing/ (estructura organizada)
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path (3 levels up from scripts/testing/)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def debug_strategy_selector():
    """Debug específico del ML Strategy Selector"""
    print("🔍 DEBUG ML STRATEGY SELECTOR")
    print("=" * 50)
    print("📍 Desde: scripts/testing/debug_ml_strategy_selector.py")
    print("=" * 50)
    
    # 1. Verificar archivo modelo
    print("\n1️⃣ ARCHIVO DE MODELO")
    model_file = "data/ml_models/strategy_selector.json"
    
    if os.path.exists(model_file):
        size = os.path.getsize(model_file)
        print(f"✅ Encontrado: {size:,} bytes")
        
        # 2. Analizar contenido JSON
        print("\n2️⃣ CONTENIDO JSON")
        try:
            with open(model_file, 'r') as f:
                data = json.load(f)
            
            print("✅ JSON válido")
            print(f"📊 Claves: {list(data.keys())}")
            
            # 3. Analizar estructura 'arms'
            if 'arms' in data:
                arms = data['arms']
                print(f"\n3️⃣ ANÁLISIS DE 'ARMS': {len(arms)} estrategias")
                
                if len(arms) > 0:
                    # Verificar primera estrategia
                    first = arms[0]
                    print(f"📋 Estructura ejemplo: {list(first.keys())}")
                    
                    # Verificar campos requeridos
                    required = ['name', 'wins', 'total']
                    valid_count = 0
                    invalid_examples = []
                    
                    for i, arm in enumerate(arms):
                        has_all_fields = all(field in arm for field in required)
                        if has_all_fields:
                            # Verificar tipos
                            name_ok = isinstance(arm['name'], str)
                            wins_ok = isinstance(arm['wins'], (int, float))
                            total_ok = isinstance(arm['total'], (int, float))
                            
                            if name_ok and wins_ok and total_ok:
                                valid_count += 1
                            else:
                                invalid_examples.append(f"Estrategia {i}: tipos incorrectos")
                        else:
                            missing = [f for f in required if f not in arm]
                            invalid_examples.append(f"Estrategia {i}: faltan {missing}")
                    
                    print(f"✅ Estrategias válidas: {valid_count}/{len(arms)}")
                    
                    if invalid_examples:
                        print(f"❌ Problemas encontrados:")
                        for example in invalid_examples[:3]:  # Mostrar primeros 3
                            print(f"   {example}")
                    
                    # Si hay estrategias válidas, mostrar estadísticas
                    if valid_count > 0:
                        total_trials = sum(arm.get('total', 0) for arm in arms)
                        total_wins = sum(arm.get('wins', 0) for arm in arms)
                        success_rate = (total_wins / max(total_trials, 1)) * 100
                        
                        print(f"\n📊 ESTADÍSTICAS:")
                        print(f"   Total trials: {total_trials}")
                        print(f"   Success rate: {success_rate:.1f}%")
                        
                        # Top 3 estrategias
                        sorted_arms = sorted(arms, 
                                           key=lambda x: x.get('wins', 0) / max(x.get('total', 1), 1),
                                           reverse=True)[:3]
                        
                        print(f"🏆 Top 3:")
                        for i, arm in enumerate(sorted_arms):
                            name = arm.get('name', 'Unknown')
                            wins = arm.get('wins', 0)
                            total = arm.get('total', 0)
                            rate = (wins / max(total, 1)) * 100
                            print(f"   {i+1}. {name}: {rate:.1f}% ({wins}/{total})")
                        
                        print("\n✅ DATOS PARECEN VÁLIDOS")
                    else:
                        print("\n❌ NINGUNA ESTRATEGIA VÁLIDA ENCONTRADA")
                else:
                    print("\n❌ LISTA 'ARMS' VACÍA")
            else:
                print(f"\n❌ CLAVE 'ARMS' NO ENCONTRADA")
                print(f"   Claves disponibles: {list(data.keys())}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON inválido: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print(f"❌ No encontrado: {model_file}")
    
    # 4. Test de importación
    print(f"\n4️⃣ TEST DE IMPORTACIÓN")
    try:
        from strategies.ml_strategy_selector import ContextualMAB
        print("✅ ContextualMAB importado")
        
        # Test de inicialización
        try:
            mab = ContextualMAB()
            print("✅ ContextualMAB inicializado")
        except Exception as e:
            print(f"❌ Error inicialización: {e}")
            
    except ImportError as e:
        print(f"❌ Error importación: {e}")
        
        # Verificar archivo
        selector_file = "strategies/ml_strategy_selector.py"
        if os.path.exists(selector_file):
            print(f"✅ Archivo existe: {selector_file}")
            
            # Buscar clases definidas
            try:
                with open(selector_file, 'r') as f:
                    content = f.read()
                
                import re
                classes = re.findall(r'class\s+(\w+)', content)
                print(f"📊 Clases: {classes}")
                
                if 'ContextualMAB' not in classes:
                    print("❌ ContextualMAB NO DEFINIDA")
                    print("💡 Este es el problema de importación")
                
            except Exception as e:
                print(f"❌ Error leyendo: {e}")
        else:
            print(f"❌ Archivo no existe: {selector_file}")
    
    print("\n" + "=" * 50)
    print("🎯 DEBUG COMPLETADO")
    print("💡 Revisar resultados para identificar el problema")

if __name__ == "__main__":
    debug_strategy_selector()