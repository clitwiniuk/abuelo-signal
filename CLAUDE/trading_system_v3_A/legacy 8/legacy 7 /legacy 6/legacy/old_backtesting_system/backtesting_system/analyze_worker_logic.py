"""
Analizador de Lógica de Workers
===============================

Herramienta simple para analizar la lógica de decisión de los workers
SIN dependencias complejas, solo examinando el código.

Extrae y analiza los criterios de decisión de cada worker.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any


class WorkerLogicAnalyzer:
    """Analizador de lógica de workers"""
    
    def __init__(self):
        self.workers_dir = Path("../strategies/workers")
        
    def analyze_worker_file(self, worker_file: str) -> Dict[str, Any]:
        """Analizar un archivo de worker específico"""
        
        worker_path = self.workers_dir / worker_file
        
        if not worker_path.exists():
            return {'error': f"Worker file not found: {worker_file}"}
        
        try:
            with open(worker_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extraer información básica
            analysis = {
                'file': worker_file,
                'lines': len(content.split('\n')),
                'class_name': self._extract_class_name(content),
                'method_signatures': self._extract_method_signatures(content),
                'criteria_analysis': self._extract_decision_criteria(content),
                'key_parameters': self._extract_key_parameters(content),
                'rejection_reasons': self._extract_rejection_reasons(content),
                'approval_reasons': self._extract_approval_reasons(content),
                'config_values': self._extract_config_values(content)
            }
            
            return analysis
            
        except Exception as e:
            return {'error': f"Error analyzing {worker_file}: {e}"}
    
    def _extract_class_name(self, content: str) -> str:
        """Extraer nombre de la clase"""
        match = re.search(r'class\s+(\w+)', content)
        return match.group(1) if match else "Unknown"
    
    def _extract_method_signatures(self, content: str) -> List[str]:
        """Extraer firmas de métodos"""
        methods = re.findall(r'def\s+(\w+)\s*\([^)]*\):', content)
        return methods
    
    def _extract_decision_criteria(self, content: str) -> Dict[str, List[str]]:
        """Extraer criterios de decisión"""
        
        criteria = {
            'gap_criteria': [],
            'volume_criteria': [],
            'price_criteria': [],
            'quality_criteria': [],
            'time_criteria': [],
            'other_criteria': []
        }
        
        # Buscar patrones de criterios
        gap_patterns = [
            r'gap.*?(\d+(?:\.\d+)?)',
            r'max.*?gap.*?(\d+(?:\.\d+)?)',
            r'min.*?gap.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in gap_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                criteria['gap_criteria'].append(f"Gap criteria: {match}")
        
        # Buscar criterios de volumen
        volume_patterns = [
            r'volume.*?(\d+(?:\.\d+)?)',
            r'min.*?volume.*?(\d+(?:\.\d+)?)',
            r'volume.*?ratio.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in volume_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                criteria['volume_criteria'].append(f"Volume criteria: {match}")
        
        # Buscar criterios de precio
        price_patterns = [
            r'price.*?(\d+(?:\.\d+)?)',
            r'max.*?price.*?(\d+(?:\.\d+)?)',
            r'min.*?price.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                criteria['price_criteria'].append(f"Price criteria: {match}")
        
        return criteria
    
    def _extract_key_parameters(self, content: str) -> Dict[str, Any]:
        """Extraer parámetros clave"""
        
        parameters = {}
        
        # Buscar asignaciones a self
        assignments = re.findall(r'self\.(\w+)\s*=\s*(.+)', content)
        
        for var_name, value in assignments:
            # Limpiar el valor
            value = value.rstrip(';,\n')
            
            # Intentar convertir números
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except (ValueError, TypeError):
                # Mantener como string si no es número
                pass
            
            parameters[var_name] = value
        
        return parameters
    
    def _extract_rejection_reasons(self, content: str) -> List[str]:
        """Extraer razones de rechazo"""
        
        rejection_patterns = [
            r'REJECTED.*?([^.!?]+)',
            r'reject.*?([^.!?]+)',
            r'not.*?([^.!?]+)',
            r'insufficient.*?([^.!?]+)'
        ]
        
        reasons = []
        for pattern in rejection_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            reasons.extend(matches)
        
        # Limpiar y deduplicar
        cleaned_reasons = []
        for reason in reasons:
            reason = reason.strip()
            if len(reason) > 5 and reason not in cleaned_reasons:
                cleaned_reasons.append(reason)
        
        return cleaned_reasons[:10]  # Limitar a 10 razones
    
    def _extract_approval_reasons(self, content: str) -> List[str]:
        """Extraer razones de aprobación"""
        
        approval_patterns = [
            r'APPROVED.*?([^.!?]+)',
            r'approved.*?([^.!?]+)',
            r'entry.*?([^.!?]+)',
            r'signal.*?([^.!?]+)'
        ]
        
        reasons = []
        for pattern in approval_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            reasons.extend(matches)
        
        # Limpiar y deduplicar
        cleaned_reasons = []
        for reason in reasons:
            reason = reason.strip()
            if len(reason) > 5 and reason not in cleaned_reasons:
                cleaned_reasons.append(reason)
        
        return cleaned_reasons[:10]  # Limitar a 10 razones
    
    def _extract_config_values(self, content: str) -> Dict[str, str]:
        """Extraer valores de configuración"""
        
        config_patterns = [
            r'max_gap\s*=\s*(\d+(?:\.\d+)?)',
            r'min_volume_ratio\s*=\s*(\d+(?:\.\d+)?)',
            r'min_price\s*=\s*(\d+(?:\.\d+)?)',
            r'max_price\s*=\s*(\d+(?:\.\d+)?)',
            r'max_hour\s*=\s*(\d+(?:\.\d+)?)',
            r'min_hour\s*=\s*(\d+(?:\.\d+)?)'
        ]
        
        config = {}
        for pattern in config_patterns:
            match = re.search(pattern, content)
            if match:
                param_name = pattern.split('\\')[0].replace('\\', '')
                config[param_name] = match.group(1)
        
        return config
    
    def analyze_all_workers(self) -> Dict[str, Any]:
        """Analizar todos los workers disponibles"""
        
        worker_files = [
            'macdv_worker_logic.py',
            'daily_plays_worker_logic.py',
            'vwap_worker_logic.py',
            'generic_01_worker_logic.py',
            'volume_absorption_worker_logic.py',
            'momentum_breakout_worker_logic.py',
            'vcp_smallcap_worker_logic.py'
        ]
        
        results = {}
        
        for worker_file in worker_files:
            worker_name = worker_file.replace('_worker_logic.py', '').replace('_', '-')
            print(f"📊 Analizando: {worker_file}")
            
            analysis = self.analyze_worker_file(worker_file)
            results[worker_name] = analysis
            
            if 'error' not in analysis:
                print(f"   ✅ Clase: {analysis['class_name']}")
                print(f"   📏 Líneas: {analysis['lines']}")
                print(f"   🔧 Métodos: {len(analysis['method_signatures'])}")
        
        return results
    
    def generate_decision_report(self, worker_analysis: Dict[str, Any]) -> str:
        """Generar reporte de decisión de un worker"""
        
        report = []
        report.append(f"## ANÁLISIS DE WORKER: {worker_analysis.get('class_name', 'Unknown')}")
        report.append(f"**Archivo:** {worker_analysis['file']}")
        report.append(f"**Líneas de código:** {worker_analysis['lines']}")
        report.append("")
        
        # Parámetros clave
        if worker_analysis.get('config_values'):
            report.append("### 🔧 Parámetros de Configuración")
            for param, value in worker_analysis['config_values'].items():
                report.append(f"- {param}: {value}")
            report.append("")
        
        # Criterios de decisión
        criteria = worker_analysis.get('criteria_analysis', {})
        if criteria and any(criteria.values()):
            report.append("### 📋 Criterios de Decisión")
            
            for criteria_type, items in criteria.items():
                if items:
                    report.append(f"**{criteria_type.replace('_', ' ').title()}:**")
                    for item in items:
                        report.append(f"- {item}")
                    report.append("")
        
        # Razones de rechazo
        if worker_analysis.get('rejection_reasons'):
            report.append("### ❌ Razones de Rechazo Comunes")
            for reason in worker_analysis['rejection_reasons']:
                report.append(f"- {reason}")
            report.append("")
        
        return "\n".join(report)


def main():
    """Función principal"""
    
    print("🔍 ANALIZADOR DE LÓGICA DE WORKERS")
    print("="*50)
    print("Analizando la lógica de decisión de los workers...")
    print()
    
    analyzer = WorkerLogicAnalyzer()
    results = analyzer.analyze_all_workers()
    
    # Generar reportes detallados
    print(f"\n{'='*50}")
    print("📊 REPORTES DETALLADOS")
    print(f"{'='*50}")
    
    for worker_name, analysis in results.items():
        if 'error' not in analysis:
            print(f"\n{analyzer.generate_decision_report(analysis)}")
        else:
            print(f"\n❌ Error analizando {worker_name}: {analysis['error']}")
    
    # Resumen final
    print(f"\n{'='*50}")
    print("📋 RESUMEN")
    print(f"{'='*50}")
    
    for worker_name, analysis in results.items():
        if 'error' not in analysis:
            print(f"{worker_name:<20}: {analysis['class_name']} ({analysis['lines']} líneas)")
        else:
            print(f"{worker_name:<20}: ERROR - {analysis['error']}")


if __name__ == "__main__":
    main()