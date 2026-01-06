#!/usr/bin/env python3
"""
Strategy Code Analyzer
======================

Analiza el código de las estrategias reales y sugiere modificaciones específicas
para mejorar la generación de señales y rentabilidad.
"""

import os
import sys
import ast
import inspect
from typing import Dict, List, Any, Tuple
import re

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import STRATEGY_REGISTRY

class StrategyCodeAnalyzer:
    """Analizador de código de estrategias"""
    
    def __init__(self):
        self.strategy_analyses = {}
        
    def analyze_strategy_code(self, strategy_name: str) -> Dict:
        """Analizar el código de una estrategia"""
        
        if strategy_name not in STRATEGY_REGISTRY:
            return {'error': f'Strategy {strategy_name} not found'}
        
        strategy_class = STRATEGY_REGISTRY[strategy_name]
        
        # Obtener código fuente
        try:
            source_code = inspect.getsource(strategy_class)
            source_file = inspect.getfile(strategy_class)
        except Exception as e:
            return {'error': f'Could not get source code: {e}'}
        
        analysis = {
            'strategy_name': strategy_name,
            'source_file': source_file,
            'source_code': source_code,
            'issues': [],
            'improvements': [],
            'code_metrics': self._analyze_code_metrics(source_code),
            'signal_generation': self._analyze_signal_generation(source_code),
            'parameter_analysis': self._analyze_parameters(source_code),
            'filter_analysis': self._analyze_filters(source_code)
        }
        
        # Identificar problemas comunes
        self._identify_common_issues(analysis)
        
        # Generar sugerencias de mejora
        self._generate_improvements(analysis)
        
        self.strategy_analyses[strategy_name] = analysis
        return analysis
    
    def _analyze_code_metrics(self, source_code: str) -> Dict:
        """Analizar métricas básicas del código"""
        lines = source_code.split('\n')
        
        metrics = {
            'total_lines': len(lines),
            'code_lines': len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
            'comment_lines': len([l for l in lines if l.strip().startswith('#')]),
            'method_count': len(re.findall(r'def \w+\(', source_code)),
            'if_statements': len(re.findall(r'\bif\b', source_code)),
            'and_conditions': len(re.findall(r'\band\b', source_code)),
            'or_conditions': len(re.findall(r'\bor\b', source_code))
        }
        
        # Calcular complejidad relativa
        metrics['complexity_score'] = (
            metrics['if_statements'] * 2 + 
            metrics['and_conditions'] * 1.5 + 
            metrics['or_conditions'] * 1.2
        )
        
        return metrics
    
    def _analyze_signal_generation(self, source_code: str) -> Dict:
        """Analizar lógica de generación de señales"""
        
        signal_analysis = {
            'has_long_signals': 'SignalType.LONG' in source_code or 'LONG' in source_code,
            'has_short_signals': 'SignalType.SHORT' in source_code or 'SHORT' in source_code,
            'return_patterns': [],
            'signal_conditions': [],
            'potential_bottlenecks': []
        }
        
        # Buscar patrones de retorno
        return_matches = re.findall(r'return\s+([^#\n]+)', source_code)
        signal_analysis['return_patterns'] = return_matches
        
        # Buscar condiciones complejas
        complex_conditions = re.findall(r'if\s+(.+?):', source_code)
        signal_analysis['signal_conditions'] = [c.strip() for c in complex_conditions if len(c.strip()) > 20]
        
        # Identificar posibles cuellos de botella
        if len(signal_analysis['signal_conditions']) > 5:
            signal_analysis['potential_bottlenecks'].append("Too many complex conditions")
        
        if signal_analysis['signal_conditions']:
            avg_condition_length = sum(len(c) for c in signal_analysis['signal_conditions']) / len(signal_analysis['signal_conditions'])
            if avg_condition_length > 80:
                signal_analysis['potential_bottlenecks'].append("Very complex conditional logic")
        
        return signal_analysis
    
    def _analyze_parameters(self, source_code: str) -> Dict:
        """Analizar parámetros de la estrategia"""
        
        param_analysis = {
            'parameter_references': [],
            'hardcoded_values': [],
            'configurable_params': []
        }
        
        # Buscar referencias a self.params
        param_refs = re.findall(r'self\.params?\[?[\'"](\w+)[\'"]?\]?', source_code)
        param_analysis['parameter_references'] = list(set(param_refs))
        
        # Buscar valores hardcodeados (números mágicos)
        hardcoded = re.findall(r'\b(\d+\.?\d*)\b', source_code)
        # Filtrar números muy comunes
        filtered_hardcoded = [v for v in hardcoded if v not in ['0', '1', '2', '100', '0.0', '1.0']]
        param_analysis['hardcoded_values'] = list(set(filtered_hardcoded))
        
        # Parámetros típicos encontrados
        common_params = ['volume_threshold', 'rsi_period', 'macd_fast', 'macd_slow', 'sma_period', 'stop_loss', 'take_profit']
        for param in common_params:
            if param in source_code:
                param_analysis['configurable_params'].append(param)
        
        return param_analysis
    
    def _analyze_filters(self, source_code: str) -> Dict:
        """Analizar filtros aplicados"""
        
        filter_analysis = {
            'volume_filters': [],
            'price_filters': [],
            'time_filters': [],
            'technical_filters': [],
            'filter_strictness': 'MEDIUM'
        }
        
        # Filtros de volumen
        if 'volume' in source_code.lower():
            volume_patterns = re.findall(r'volume[^<>=]*[<>=]+[^<>=]*[\d.]+', source_code.lower())
            filter_analysis['volume_filters'] = volume_patterns
        
        # Filtros técnicos
        technical_indicators = ['rsi', 'macd', 'sma', 'ema', 'bollinger', 'atr', 'stoch']
        for indicator in technical_indicators:
            if indicator in source_code.lower():
                filter_analysis['technical_filters'].append(indicator)
        
        # Evaluar strictness
        total_filters = (len(filter_analysis['volume_filters']) + 
                        len(filter_analysis['technical_filters']) + 
                        len(filter_analysis['price_filters']))
        
        if total_filters > 6:
            filter_analysis['filter_strictness'] = 'VERY_HIGH'
        elif total_filters > 4:
            filter_analysis['filter_strictness'] = 'HIGH'
        elif total_filters > 2:
            filter_analysis['filter_strictness'] = 'MEDIUM'
        else:
            filter_analysis['filter_strictness'] = 'LOW'
        
        return filter_analysis
    
    def _identify_common_issues(self, analysis: Dict):
        """Identificar problemas comunes"""
        
        code_metrics = analysis['code_metrics']
        signal_gen = analysis['signal_generation']
        filters = analysis['filter_analysis']
        
        # Issue 1: Complejidad excesiva
        if code_metrics['complexity_score'] > 20:
            analysis['issues'].append({
                'type': 'HIGH_COMPLEXITY',
                'severity': 'HIGH',
                'description': f"Lógica muy compleja (score: {code_metrics['complexity_score']:.1f})",
                'impact': 'Difícil de optimizar y puede perder señales'
            })
        
        # Issue 2: Filtros muy restrictivos
        if filters['filter_strictness'] in ['HIGH', 'VERY_HIGH']:
            analysis['issues'].append({
                'type': 'OVER_FILTERING',
                'severity': 'MEDIUM',
                'description': f"Filtros muy restrictivos ({filters['filter_strictness']})",
                'impact': 'Pocas señales generadas'
            })
        
        # Issue 3: Solo señales en una dirección
        if signal_gen['has_long_signals'] and not signal_gen['has_short_signals']:
            analysis['issues'].append({
                'type': 'DIRECTIONAL_BIAS',
                'severity': 'MEDIUM', 
                'description': 'Solo genera señales LONG',
                'impact': 'Pierde oportunidades en mercados bajistas'
            })
        elif signal_gen['has_short_signals'] and not signal_gen['has_long_signals']:
            analysis['issues'].append({
                'type': 'DIRECTIONAL_BIAS',
                'severity': 'MEDIUM',
                'description': 'Solo genera señales SHORT', 
                'impact': 'Pierde oportunidades en mercados alcistas'
            })
        
        # Issue 4: Muchos valores hardcodeados
        param_analysis = analysis['parameter_analysis']
        if len(param_analysis['hardcoded_values']) > 10:
            analysis['issues'].append({
                'type': 'HARDCODED_VALUES',
                'severity': 'LOW',
                'description': f"Muchos valores hardcodeados ({len(param_analysis['hardcoded_values'])})",
                'impact': 'Difícil de optimizar parámetros'
            })
    
    def _generate_improvements(self, analysis: Dict):
        """Generar sugerencias de mejora específicas"""
        
        issues = analysis['issues']
        code_metrics = analysis['code_metrics']
        signal_gen = analysis['signal_generation']
        param_analysis = analysis['parameter_analysis']
        filters = analysis['filter_analysis']
        
        # Mejora 1: Simplificar lógica compleja
        if any(issue['type'] == 'HIGH_COMPLEXITY' for issue in issues):
            analysis['improvements'].append({
                'type': 'SIMPLIFY_LOGIC',
                'priority': 'HIGH',
                'title': 'Simplificar lógica de decisión',
                'description': 'Dividir condiciones complejas en métodos separados',
                'code_suggestions': [
                    'Extraer condiciones complejas a métodos privados',
                    'Usar early returns para reducir anidamiento',
                    'Separar validaciones de lógica de negocio'
                ],
                'example_change': '''
# En lugar de:
if (volume > threshold and rsi < 30 and macd > signal and price > sma):
    return SignalType.LONG

# Usar:
if not self._volume_confirms():
    return None
if not self._oversold_confirmed():
    return None
if not self._momentum_positive():
    return None
return SignalType.LONG
                '''
            })
        
        # Mejora 2: Reducir filtros excesivos
        if any(issue['type'] == 'OVER_FILTERING' for issue in issues):
            analysis['improvements'].append({
                'type': 'REDUCE_FILTERS',
                'priority': 'HIGH',
                'title': 'Optimizar filtros restrictivos',
                'description': 'Reducir o relajar filtros para generar más señales',
                'code_suggestions': [
                    'Reducir thresholds de volumen de 3.0 a 2.0',
                    'Ampliar rangos de RSI de (30,70) a (25,75)',
                    'Usar OR en lugar de AND en algunas condiciones',
                    'Implementar filtros adaptativos basados en volatilidad'
                ],
                'example_change': '''
# En lugar de:
if volume_ratio > 3.0 and rsi < 30 and macd_hist > 0:
    
# Usar:
if volume_ratio > 2.0 and (rsi < 35 or macd_hist > 0.1):
                '''
            })
        
        # Mejora 3: Añadir direccionalidad
        if any(issue['type'] == 'DIRECTIONAL_BIAS' for issue in issues):
            analysis['improvements'].append({
                'type': 'ADD_BIDIRECTIONAL',
                'priority': 'MEDIUM',
                'title': 'Implementar señales bidireccionales',
                'description': 'Añadir lógica para señales en ambas direcciones',
                'code_suggestions': [
                    'Añadir condiciones para SHORT cuando RSI > 70',
                    'Implementar reversión en soportes/resistencias',
                    'Usar momentum negativo para señales SHORT'
                ],
                'example_change': '''
# Añadir después de la lógica LONG:
elif rsi > 70 and volume_ratio > 2.0 and macd_hist < 0:
    return SignalType.SHORT
                '''
            })
        
        # Mejora 4: Parametrizar valores
        if len(param_analysis['hardcoded_values']) > 5:
            analysis['improvements'].append({
                'type': 'PARAMETERIZE_VALUES',
                'priority': 'LOW',
                'title': 'Convertir valores hardcodeados en parámetros',
                'description': 'Hacer valores configurables para optimización',
                'code_suggestions': [
                    'Añadir parámetros al __init__',
                    'Usar self.params en lugar de números literales',
                    'Documentar rangos válidos para cada parámetro'
                ],
                'example_change': '''
# En lugar de:
if rsi < 30:

# Usar:
if rsi < self.params.get('rsi_oversold_threshold', 30):
                '''
            })
        
        # Mejora 5: Mejorar timing
        analysis['improvements'].append({
            'type': 'IMPROVE_TIMING',
            'priority': 'MEDIUM',
            'title': 'Optimizar timing de entrada',
            'description': 'Mejorar el momento exacto de generación de señales',
            'code_suggestions': [
                'Añadir confirmación en barra siguiente',
                'Usar breakouts en lugar de solo indicadores',
                'Implementar filtros de momentum reciente',
                'Considerar gaps y niveles clave'
            ],
            'example_change': '''
# Añadir confirmación:
if signal_conditions_met and self._confirm_breakout():
    return SignalType.LONG
            '''
        })
    
    def print_analysis_report(self, analysis: Dict):
        """Imprimir reporte de análisis detallado"""
        
        strategy_name = analysis['strategy_name']
        
        print(f"\n🔬 ANÁLISIS DE CÓDIGO - {strategy_name}")
        print("=" * 70)
        
        # Métricas de código
        metrics = analysis['code_metrics']
        print("📊 MÉTRICAS DE CÓDIGO:")
        print(f"   Líneas totales: {metrics['total_lines']}")
        print(f"   Líneas de código: {metrics['code_lines']}")
        print(f"   Métodos: {metrics['method_count']}")
        print(f"   Complejidad: {metrics['complexity_score']:.1f}")
        
        # Análisis de señales
        signal_gen = analysis['signal_generation']
        print(f"\n📈 GENERACIÓN DE SEÑALES:")
        print(f"   Señales LONG: {'✅' if signal_gen['has_long_signals'] else '❌'}")
        print(f"   Señales SHORT: {'✅' if signal_gen['has_short_signals'] else '❌'}")
        print(f"   Condiciones complejas: {len(signal_gen['signal_conditions'])}")
        
        # Análisis de filtros
        filters = analysis['filter_analysis']
        print(f"\n🔍 FILTROS:")
        print(f"   Restrictividad: {filters['filter_strictness']}")
        print(f"   Filtros técnicos: {', '.join(filters['technical_filters'])}")
        
        # Problemas identificados
        issues = analysis['issues']
        if issues:
            print(f"\n⚠️ PROBLEMAS IDENTIFICADOS ({len(issues)}):")
            for i, issue in enumerate(issues, 1):
                severity_icons = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
                icon = severity_icons.get(issue['severity'], '⚪')
                print(f"   {i}. {icon} {issue['type']}")
                print(f"      • {issue['description']}")
                print(f"      • Impacto: {issue['impact']}")
        
        # Mejoras sugeridas
        improvements = analysis['improvements']
        if improvements:
            print(f"\n💡 MEJORAS SUGERIDAS ({len(improvements)}):")
            for i, improvement in enumerate(improvements, 1):
                priority_icons = {'HIGH': '🔥', 'MEDIUM': '⚡', 'LOW': '💡'}
                icon = priority_icons.get(improvement['priority'], '💡')
                print(f"\n   {i}. {icon} {improvement['title']} (Prioridad: {improvement['priority']})")
                print(f"      📝 {improvement['description']}")
                print(f"      🔧 Sugerencias:")
                for suggestion in improvement['code_suggestions']:
                    print(f"         • {suggestion}")
                
                if 'example_change' in improvement:
                    print(f"      📄 Ejemplo de código:")
                    print(f"{improvement['example_change']}")
        
        print("=" * 70)

def main():
    """Interfaz principal del analizador"""
    
    print("🔬 STRATEGY CODE ANALYZER")
    print("=" * 60)
    print("Analizador de código de estrategias con sugerencias de mejora")
    print()
    
    analyzer = StrategyCodeAnalyzer()
    
    # Mostrar estrategias disponibles
    available_strategies = list(STRATEGY_REGISTRY.keys())
    print("📋 ESTRATEGIAS DISPONIBLES:")
    for i, strategy in enumerate(available_strategies, 1):
        print(f"   {i}. {strategy}")
    
    try:
        strategy_choice = input("\n🎯 Selecciona estrategia por número o nombre: ").strip()
        
        if strategy_choice.isdigit():
            idx = int(strategy_choice) - 1
            if 0 <= idx < len(available_strategies):
                selected_strategy = available_strategies[idx]
            else:
                print("❌ Número inválido")
                return
        else:
            # Buscar por nombre
            selected_strategy = None
            for strategy in available_strategies:
                if strategy_choice.lower() in strategy.lower():
                    selected_strategy = strategy
                    break
            
            if not selected_strategy:
                print(f"❌ Estrategia '{strategy_choice}' no encontrada")
                return
        
        print(f"\n🔍 Analizando código de {selected_strategy}...")
        
        analysis = analyzer.analyze_strategy_code(selected_strategy)
        
        if 'error' in analysis:
            print(f"❌ Error: {analysis['error']}")
            return
        
        analyzer.print_analysis_report(analysis)
        
        # Opción de ver código fuente
        show_code = input("\n📄 ¿Mostrar código fuente? (y/n): ").strip().lower()
        if show_code == 'y':
            print(f"\n📄 CÓDIGO FUENTE - {selected_strategy}")
            print("=" * 60)
            print(analysis['source_code'])
        
    except KeyboardInterrupt:
        print("\n👋 Análisis cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()