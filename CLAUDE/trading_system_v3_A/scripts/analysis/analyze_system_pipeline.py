#!/usr/bin/env python3
"""
Complete Trading System Pipeline Analysis
=========================================

Deep analysis of all system components to identify:
1. Obsolete/unused components
2. Conflicting implementations
3. Duplicate functionality
4. Performance bottlenecks
5. Erratic behavior sources
6. Architecture inconsistencies

Author: Claude Code
Date: 2025-08-28
"""

import os
import sys
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
from collections import defaultdict, Counter

class SystemPipelineAnalyzer:
    
    def __init__(self):
        self.root_path = Path("/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3")
        self.components = {}
        self.imports_map = defaultdict(set)
        self.unused_files = set()
        self.duplicate_functionality = defaultdict(list)
        self.performance_issues = []
        self.architecture_issues = []
        
        print("🔍 Trading System Pipeline Analysis")
        print("=" * 50)
        
    def scan_codebase(self):
        """Scan entire codebase and catalog components"""
        print("\n📊 Scanning Codebase Structure")
        print("-" * 40)
        
        python_files = []
        for root, dirs, files in os.walk(self.root_path):
            # Skip common non-code directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'venv', 'env']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    python_files.append(file_path)
        
        print(f"📁 Found {len(python_files)} Python files")
        
        # Analyze each file
        for file_path in python_files:
            try:
                self.analyze_file(file_path)
            except Exception as e:
                print(f"⚠️ Error analyzing {file_path.name}: {e}")
        
        return python_files
    
    def analyze_file(self, file_path: Path):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST for detailed analysis
            tree = ast.parse(content)
            
            relative_path = file_path.relative_to(self.root_path)
            
            file_info = {
                'path': relative_path,
                'size_kb': len(content) / 1024,
                'lines': len(content.split('\n')),
                'classes': [],
                'functions': [],
                'imports': [],
                'obsolete_patterns': [],
                'performance_issues': [],
                'last_modified': file_path.stat().st_mtime
            }
            
            # Extract classes, functions, imports
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    file_info['classes'].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    file_info['functions'].append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        file_info['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        file_info['imports'].append(node.module)
            
            # Check for obsolete patterns
            self.check_obsolete_patterns(content, file_info)
            
            # Check for performance issues
            self.check_performance_issues(content, file_info)
            
            self.components[str(relative_path)] = file_info
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def check_obsolete_patterns(self, content: str, file_info: Dict):
        """Check for obsolete code patterns"""
        obsolete_patterns = [
            ('ProRealTime', 'ProRealTime references (replaced by IBKR)'),
            ('strategy_time_orchestrator', 'Old strategy orchestrator (replaced by SGP)'),
            ('TODO.*REMOVE', 'Code marked for removal'),
            ('DEPRECATED', 'Deprecated code'),
            ('OBSOLETE', 'Obsolete code'),
            ('LEGACY', 'Legacy code'),
            ('TEMP.*DELETE', 'Temporary code to delete'),
            ('HACK', 'Hack/workaround code'),
            ('FIXME', 'Code needing fixes'),
        ]
        
        for pattern, description in obsolete_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                file_info['obsolete_patterns'].append(description)
    
    def check_performance_issues(self, content: str, file_info: Dict):
        """Check for potential performance issues"""
        perf_patterns = [
            ('time\.sleep\([^)]*\)', 'Blocking sleep calls'),
            ('for.*in.*range\(len\(', 'Non-pythonic loops'),
            ('\.append.*for.*in', 'List comprehension opportunity'),
            ('asyncio\.run.*in.*loop', 'Nested asyncio.run calls'),
            ('\.get\(\).*\.get\(\)', 'Multiple dict.get() calls'),
            ('import \*', 'Wildcard imports'),
        ]
        
        for pattern, description in perf_patterns:
            if re.search(pattern, content):
                file_info['performance_issues'].append(description)
    
    def analyze_component_relationships(self):
        """Analyze relationships between components"""
        print("\n🔗 Analyzing Component Relationships")
        print("-" * 40)
        
        # Build import graph
        for file_path, info in self.components.items():
            for imp in info['imports']:
                self.imports_map[file_path].add(imp)
        
        # Find unused files (files not imported by others)
        all_files = set(self.components.keys())
        imported_modules = set()
        
        for file_path, info in self.components.items():
            for imp in info['imports']:
                # Convert import to potential file path
                potential_paths = [
                    f"{imp.replace('.', '/')}.py",
                    f"{imp.replace('.', '/')}/__init__.py",
                    f"core/{imp}.py",
                    f"scanner/{imp}.py",
                    f"engine/{imp}.py"
                ]
                
                for pot_path in potential_paths:
                    if pot_path in all_files:
                        imported_modules.add(pot_path)
        
        # Files that aren't imported (potential unused files)
        potentially_unused = all_files - imported_modules
        
        # Filter out main files and tests
        main_files = {'main.py', 'app.py', 'run.py', 'start.py'}
        test_files = {f for f in potentially_unused if 'test' in f.lower()}
        
        self.unused_files = potentially_unused - main_files - test_files
        
        print(f"📊 Component Relationship Analysis:")
        print(f"   Total files: {len(all_files)}")
        print(f"   Imported modules: {len(imported_modules)}")
        print(f"   Potentially unused: {len(self.unused_files)}")
        
        return self.unused_files
    
    def find_duplicate_functionality(self):
        """Find duplicate or similar functionality"""
        print("\n🔍 Finding Duplicate Functionality")
        print("-" * 40)
        
        # Group by similar class/function names
        class_groups = defaultdict(list)
        function_groups = defaultdict(list)
        
        for file_path, info in self.components.items():
            for class_name in info['classes']:
                # Normalize class names for comparison
                normalized = re.sub(r'(Manager|Handler|Service|Adapter|Controller)$', '', class_name).lower()
                class_groups[normalized].append((file_path, class_name))
            
            for func_name in info['functions']:
                # Normalize function names
                normalized = re.sub(r'^(get_|set_|fetch_|load_|save_)', '', func_name).lower()
                if len(normalized) > 3:  # Skip very short names
                    function_groups[normalized].append((file_path, func_name))
        
        # Find potential duplicates
        for normalized, items in class_groups.items():
            if len(items) > 1:
                self.duplicate_functionality['classes'].append({
                    'normalized_name': normalized,
                    'instances': items
                })
        
        for normalized, items in function_groups.items():
            if len(items) > 1 and len(items) < 10:  # Avoid very common function names
                self.duplicate_functionality['functions'].append({
                    'normalized_name': normalized,
                    'instances': items
                })
        
        print(f"📊 Duplicate Analysis:")
        print(f"   Potential duplicate classes: {len(self.duplicate_functionality['classes'])}")
        print(f"   Potential duplicate functions: {len(self.duplicate_functionality['functions'])}")
    
    def analyze_architecture_issues(self):
        """Analyze architecture and design issues"""
        print("\n🏗️ Analyzing Architecture Issues")
        print("-" * 40)
        
        issues = []
        
        # Check for circular imports (simplified check)
        circular_candidates = []
        for file_path, info in self.components.items():
            for imp in info['imports']:
                # Check if imported module imports back
                imp_file = f"{imp.replace('.', '/')}.py"
                if imp_file in self.components:
                    imp_info = self.components[imp_file]
                    file_module = file_path.replace('.py', '').replace('/', '.')
                    if any(file_module in imported for imported in imp_info['imports']):
                        circular_candidates.append((file_path, imp_file))
        
        if circular_candidates:
            issues.append({
                'type': 'Potential Circular Imports',
                'description': f'Found {len(circular_candidates)} potential circular import pairs',
                'details': circular_candidates[:5]  # Show first 5
            })
        
        # Check for large files (potential god objects)
        large_files = []
        for file_path, info in self.components.items():
            if info['lines'] > 1000:
                large_files.append((file_path, info['lines']))
        
        if large_files:
            issues.append({
                'type': 'Large Files',
                'description': f'Found {len(large_files)} files with >1000 lines',
                'details': sorted(large_files, key=lambda x: x[1], reverse=True)[:5]
            })
        
        # Check for files with many classes (potential god objects)
        multi_class_files = []
        for file_path, info in self.components.items():
            if len(info['classes']) > 5:
                multi_class_files.append((file_path, len(info['classes'])))
        
        if multi_class_files:
            issues.append({
                'type': 'Multi-Class Files',
                'description': f'Found {len(multi_class_files)} files with >5 classes',
                'details': sorted(multi_class_files, key=lambda x: x[1], reverse=True)
            })
        
        self.architecture_issues = issues
        
        for issue in issues:
            print(f"⚠️ {issue['type']}: {issue['description']}")
    
    def identify_pipeline_flow(self):
        """Identify the main pipeline flow"""
        print("\n🌊 Identifying Pipeline Flow")
        print("-" * 40)
        
        # Key components in the trading pipeline
        key_components = {
            'scanner': [],
            'smart_game_plan': [],
            'trading_engine': [],
            'adapters': [],
            'core': []
        }
        
        for file_path, info in self.components.items():
            if 'scanner' in file_path.lower():
                key_components['scanner'].append(file_path)
            elif 'smart_game_plan' in file_path.lower():
                key_components['smart_game_plan'].append(file_path)
            elif 'trading_engine' in file_path.lower() or 'engine' in file_path.lower():
                key_components['trading_engine'].append(file_path)
            elif 'adapter' in file_path.lower():
                key_components['adapters'].append(file_path)
            elif 'core' in file_path.lower():
                key_components['core'].append(file_path)
        
        print("📊 Pipeline Components:")
        for component_type, files in key_components.items():
            print(f"   {component_type.title()}: {len(files)} files")
            for file_path in files[:3]:  # Show first 3
                info = self.components[file_path]
                print(f"      - {file_path} ({info['lines']} lines)")
            if len(files) > 3:
                print(f"      ... and {len(files) - 3} more")
        
        return key_components
    
    def generate_cleanup_recommendations(self):
        """Generate specific cleanup recommendations"""
        print("\n💡 Cleanup Recommendations")
        print("-" * 40)
        
        recommendations = []
        
        # Obsolete code recommendations
        obsolete_files = []
        for file_path, info in self.components.items():
            if info['obsolete_patterns']:
                obsolete_files.append((file_path, info['obsolete_patterns']))
        
        if obsolete_files:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Obsolete Code Removal',
                'description': f'Remove or update {len(obsolete_files)} files with obsolete patterns',
                'action': 'Review and clean up obsolete code references',
                'files': obsolete_files[:5]
            })
        
        # Unused files recommendations
        if self.unused_files:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Dead Code Removal',
                'description': f'Consider removing {len(self.unused_files)} potentially unused files',
                'action': 'Review and remove unused files',
                'files': list(self.unused_files)[:5]
            })
        
        # Performance issues recommendations
        perf_files = []
        for file_path, info in self.components.items():
            if info['performance_issues']:
                perf_files.append((file_path, info['performance_issues']))
        
        if perf_files:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Performance Optimization',
                'description': f'Optimize {len(perf_files)} files with performance issues',
                'action': 'Review and optimize performance bottlenecks',
                'files': perf_files[:5]
            })
        
        # Architecture issues recommendations
        if self.architecture_issues:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Architecture Cleanup',
                'description': f'Address {len(self.architecture_issues)} architecture issues',
                'action': 'Refactor large files and resolve circular dependencies',
                'details': self.architecture_issues
            })
        
        # Duplicate functionality recommendations
        if self.duplicate_functionality['classes'] or self.duplicate_functionality['functions']:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Code Deduplication',
                'description': 'Consolidate duplicate functionality',
                'action': 'Review and merge similar classes/functions',
                'details': {
                    'classes': len(self.duplicate_functionality['classes']),
                    'functions': len(self.duplicate_functionality['functions'])
                }
            })
        
        # Display recommendations
        for i, rec in enumerate(recommendations, 1):
            priority_icon = "🚨" if rec['priority'] == 'HIGH' else "⚠️"
            print(f"{priority_icon} {i}. {rec['category']} ({rec['priority']} Priority)")
            print(f"   Issue: {rec['description']}")
            print(f"   Action: {rec['action']}")
            if 'files' in rec:
                print(f"   Example files: {[f[0] if isinstance(f, tuple) else f for f in rec['files'][:3]]}")
            print()
        
        return recommendations
    
    def run_complete_analysis(self):
        """Run complete system analysis"""
        print("Starting complete trading system pipeline analysis...")
        
        # Scan codebase
        python_files = self.scan_codebase()
        
        # Analyze relationships
        unused_files = self.analyze_component_relationships()
        
        # Find duplicates
        self.find_duplicate_functionality()
        
        # Analyze architecture
        self.analyze_architecture_issues()
        
        # Identify pipeline
        pipeline_components = self.identify_pipeline_flow()
        
        # Generate recommendations
        recommendations = self.generate_cleanup_recommendations()
        
        # Summary
        print("\n" + "="*50)
        print("📋 SYSTEM ANALYSIS SUMMARY")
        print("="*50)
        
        print(f"📁 Total Python files: {len(python_files)}")
        print(f"📊 Components analyzed: {len(self.components)}")
        print(f"🗑️ Potentially unused files: {len(unused_files)}")
        print(f"🔄 Duplicate functionality groups: {len(self.duplicate_functionality['classes']) + len(self.duplicate_functionality['functions'])}")
        print(f"⚠️ Architecture issues: {len(self.architecture_issues)}")
        print(f"💡 Cleanup recommendations: {len(recommendations)}")
        
        # Critical issues
        critical_issues = [rec for rec in recommendations if rec['priority'] == 'HIGH']
        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES TO ADDRESS: {len(critical_issues)}")
            for issue in critical_issues:
                print(f"   - {issue['category']}: {issue['description']}")
        
        # Health score
        total_files = len(self.components)
        obsolete_count = sum(1 for info in self.components.values() if info['obsolete_patterns'])
        perf_issues_count = sum(1 for info in self.components.values() if info['performance_issues'])
        
        health_score = max(0, 100 - (obsolete_count/total_files * 30) - (perf_issues_count/total_files * 20) - (len(self.architecture_issues) * 10))
        
        print(f"\n🎯 System Health Score: {health_score:.1f}/100")
        
        if health_score >= 80:
            print("✅ System is in good health - minor cleanup recommended")
        elif health_score >= 60:
            print("⚠️ System needs maintenance - several issues to address")
        else:
            print("🚨 System needs significant cleanup - multiple critical issues")
        
        return {
            'components': self.components,
            'unused_files': unused_files,
            'recommendations': recommendations,
            'health_score': health_score,
            'pipeline_components': pipeline_components
        }


if __name__ == "__main__":
    analyzer = SystemPipelineAnalyzer()
    results = analyzer.run_complete_analysis()