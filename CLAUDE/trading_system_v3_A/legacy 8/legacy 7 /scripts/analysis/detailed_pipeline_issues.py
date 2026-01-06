#!/usr/bin/env python3
"""
Detailed Pipeline Issues Analysis
================================

Deep dive into the most critical issues found in the system analysis
"""

import os
import re
from pathlib import Path

class DetailedIssuesAnalyzer:
    
    def __init__(self):
        self.root_path = Path("/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3")
        print("🔍 Detailed Pipeline Issues Analysis")
        print("=" * 50)
    
    def analyze_obsolete_code(self):
        """Analyze obsolete code patterns in detail"""
        print("\n🚨 CRITICAL: Obsolete Code Analysis")
        print("-" * 50)
        
        obsolete_patterns = {
            'ProRealTime': 'Old data source - should use IBKR',
            'strategy_time_orchestrator': 'Replaced by Smart Game Plan Manager',
            'StrategyTimeOrchestrator': 'Old class - replaced by SGP',
            'TEMP': 'Temporary code that should be removed',
            'TODO.*REMOVE': 'Code marked for removal',
            'DEPRECATED': 'Deprecated functionality',
            'LEGACY': 'Legacy code',
            'OBSOLETE': 'Obsolete implementation'
        }
        
        critical_files = []
        
        for pattern, description in obsolete_patterns.items():
            print(f"\n🔍 Searching for: {pattern} ({description})")
            matches = self.search_pattern_in_files(pattern)
            
            if matches:
                print(f"   Found in {len(matches)} files:")
                for file_path, lines in matches[:5]:  # Show top 5
                    print(f"   📁 {file_path} ({len(lines)} occurrences)")
                    for line_num, line_content in lines[:2]:  # Show first 2 lines
                        print(f"      Line {line_num}: {line_content.strip()[:80]}...")
                
                critical_files.extend([f[0] for f in matches])
        
        # Remove duplicates
        unique_critical_files = list(set(critical_files))
        
        print(f"\n📊 Summary:")
        print(f"   Files with obsolete patterns: {len(unique_critical_files)}")
        print(f"   Most problematic files:")
        
        # Count occurrences per file
        file_counts = {}
        for file_path in critical_files:
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        
        # Sort by occurrence count
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        
        for file_path, count in sorted_files[:10]:
            print(f"   📁 {file_path}: {count} issues")
        
        return unique_critical_files
    
    def analyze_large_files(self):
        """Analyze large files that might be god objects"""
        print("\n🚨 CRITICAL: Large Files Analysis")
        print("-" * 50)
        
        large_files = []
        
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            lines = len(content.split('\n'))
                            
                            if lines > 1000:
                                # Analyze what makes it large
                                classes = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
                                functions = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
                                methods = len(re.findall(r'^\s+def\s+\w+', content, re.MULTILINE))
                                
                                relative_path = file_path.relative_to(self.root_path)
                                large_files.append({
                                    'path': str(relative_path),
                                    'lines': lines,
                                    'classes': classes,
                                    'functions': functions,
                                    'methods': methods,
                                    'kb': len(content) / 1024
                                })
                    except:
                        pass
        
        # Sort by lines
        large_files.sort(key=lambda x: x['lines'], reverse=True)
        
        print(f"📊 Found {len(large_files)} files with >1000 lines")
        print("\n🎯 Top 10 largest files:")
        
        for i, file_info in enumerate(large_files[:10], 1):
            print(f"{i:2d}. {file_info['path']}")
            print(f"    📏 {file_info['lines']:,} lines | {file_info['kb']:.1f}KB")
            print(f"    🏗️ {file_info['classes']} classes | {file_info['functions']} functions | {file_info['methods']} methods")
            
            # Analyze if it's a god object
            complexity_score = (file_info['classes'] * 2) + file_info['functions'] + (file_info['methods'] * 0.5)
            if complexity_score > 50:
                print(f"    🚨 HIGH COMPLEXITY SCORE: {complexity_score:.1f}")
            elif complexity_score > 25:
                print(f"    ⚠️ Medium complexity: {complexity_score:.1f}")
            
            print()
        
        return large_files
    
    def analyze_active_vs_archive(self):
        """Analyze active code vs archived code"""
        print("\n📊 Active vs Archived Code Analysis")
        print("-" * 50)
        
        categories = {
            'active': {'patterns': ['core/', 'engine/', 'scanner/', 'adapters/'], 'files': []},
            'archive': {'patterns': ['archive/', 'archived/', 'backup/', 'old/', 'temp/'], 'files': []},
            'test': {'patterns': ['test_', '_test.py', 'tests/'], 'files': []},
            'experimental': {'patterns': ['experiment', 'demo', 'example', 'prototype'], 'files': []},
            'config': {'patterns': ['config', 'settings', '.ini', '.yaml', '.json'], 'files': []}
        }
        
        total_lines = {'active': 0, 'archive': 0, 'test': 0, 'experimental': 0, 'config': 0}
        
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.root_path)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = len(f.read().split('\n'))
                    except:
                        lines = 0
                    
                    # Categorize file
                    categorized = False
                    for category, info in categories.items():
                        for pattern in info['patterns']:
                            if pattern.lower() in str(relative_path).lower():
                                info['files'].append(str(relative_path))
                                total_lines[category] += lines
                                categorized = True
                                break
                        if categorized:
                            break
                    
                    if not categorized:
                        categories['active']['files'].append(str(relative_path))
                        total_lines['active'] += lines
        
        print("📊 Code Distribution:")
        total_all_lines = sum(total_lines.values())
        
        for category, info in categories.items():
            files_count = len(info['files'])
            lines_count = total_lines[category]
            percentage = (lines_count / total_all_lines * 100) if total_all_lines > 0 else 0
            
            icon = "🎯" if category == 'active' else "📦" if category == 'archive' else "🧪" if category == 'test' else "🔬" if category == 'experimental' else "⚙️"
            
            print(f"   {icon} {category.title():12} {files_count:3d} files | {lines_count:6,} lines ({percentage:5.1f}%)")
        
        # Identify potential cleanup opportunities
        print(f"\n💡 Cleanup Opportunities:")
        
        archive_ratio = total_lines['archive'] / total_all_lines * 100 if total_all_lines > 0 else 0
        if archive_ratio > 20:
            print(f"   🚨 HIGH: {archive_ratio:.1f}% of code is archived - consider permanent removal")
        
        experimental_ratio = total_lines['experimental'] / total_all_lines * 100 if total_all_lines > 0 else 0
        if experimental_ratio > 10:
            print(f"   ⚠️ MEDIUM: {experimental_ratio:.1f}% is experimental - review and promote or remove")
        
        test_ratio = total_lines['test'] / total_lines['active'] * 100 if total_lines['active'] > 0 else 0
        if test_ratio < 20:
            print(f"   📝 INFO: Only {test_ratio:.1f}% test coverage - consider adding more tests")
        elif test_ratio > 50:
            print(f"   📝 INFO: {test_ratio:.1f}% test coverage - good coverage")
        
        return categories
    
    def search_pattern_in_files(self, pattern: str) -> list:
        """Search for a pattern in all Python files"""
        matches = []
        
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.root_path)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            
                        file_matches = []
                        for line_num, line in enumerate(lines, 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                file_matches.append((line_num, line))
                        
                        if file_matches:
                            matches.append((str(relative_path), file_matches))
                    except:
                        pass
        
        return matches
    
    def identify_conflicting_implementations(self):
        """Identify potentially conflicting implementations"""
        print("\n⚠️ Conflicting Implementations Analysis")
        print("-" * 50)
        
        # Look for multiple implementations of key concepts
        key_concepts = {
            'scanner': ['scanner', 'scan'],
            'strategy': ['strategy', 'strat'],
            'engine': ['engine', 'executor'],
            'adapter': ['adapter', 'connector'],
            'manager': ['manager', 'handler']
        }
        
        conflicts = {}
        
        for concept, patterns in key_concepts.items():
            concept_files = []
            
            for root, dirs, files in os.walk(self.root_path):
                for file in files:
                    if file.endswith('.py') and not any(skip in file.lower() for skip in ['test', 'archive', 'backup']):
                        file_path = Path(root) / file
                        relative_path = str(file_path.relative_to(self.root_path))
                        
                        # Check if file name contains concept patterns
                        for pattern in patterns:
                            if pattern in file.lower():
                                concept_files.append(relative_path)
                                break
            
            if len(concept_files) > 3:  # More than 3 files might indicate conflicts
                conflicts[concept] = concept_files
        
        print("🔍 Potential Conflicts:")
        for concept, files in conflicts.items():
            print(f"\n   📊 {concept.title()} ({len(files)} implementations):")
            for file_path in files[:8]:  # Show first 8
                print(f"      - {file_path}")
            if len(files) > 8:
                print(f"      ... and {len(files) - 8} more")
        
        return conflicts
    
    def generate_priority_action_plan(self, obsolete_files, large_files, conflicts):
        """Generate priority action plan"""
        print("\n🎯 PRIORITY ACTION PLAN")
        print("=" * 50)
        
        actions = []
        
        # High priority: Remove obsolete code
        if obsolete_files:
            actions.append({
                'priority': 1,
                'category': '🚨 IMMEDIATE',
                'title': 'Remove Obsolete Code',
                'description': f'Clean up {len(obsolete_files)} files with obsolete patterns',
                'impact': 'HIGH - Reduces confusion and maintenance burden',
                'effort': 'MEDIUM',
                'files_affected': len(obsolete_files),
                'action_items': [
                    'Search for ProRealTime references and replace with IBKR',
                    'Remove strategy_time_orchestrator and related files',
                    'Clean up TEMP/TODO/DEPRECATED comments and code',
                    'Update imports and dependencies'
                ]
            })
        
        # High priority: Refactor large files
        very_large_files = [f for f in large_files if f['lines'] > 1500]
        if very_large_files:
            actions.append({
                'priority': 1,
                'category': '🚨 IMMEDIATE',
                'title': 'Refactor God Objects',
                'description': f'Break down {len(very_large_files)} files with >1500 lines',
                'impact': 'HIGH - Improves maintainability and reduces complexity',
                'effort': 'HIGH',
                'files_affected': len(very_large_files),
                'top_files': [f['path'] for f in very_large_files[:3]],
                'action_items': [
                    'Split large classes into smaller, focused classes',
                    'Extract utility functions into separate modules',
                    'Apply Single Responsibility Principle',
                    'Create proper module hierarchy'
                ]
            })
        
        # Medium priority: Resolve conflicts
        high_conflict_concepts = {k: v for k, v in conflicts.items() if len(v) > 5}
        if high_conflict_concepts:
            actions.append({
                'priority': 2,
                'category': '⚠️ SOON',
                'title': 'Resolve Implementation Conflicts',
                'description': f'Consolidate {len(high_conflict_concepts)} concepts with multiple implementations',
                'impact': 'MEDIUM - Reduces confusion and potential bugs',
                'effort': 'MEDIUM',
                'concepts': list(high_conflict_concepts.keys()),
                'action_items': [
                    'Identify the canonical implementation for each concept',
                    'Migrate code to use canonical implementations',
                    'Remove or archive obsolete implementations',
                    'Update documentation and imports'
                ]
            })
        
        # Medium priority: Archive cleanup
        actions.append({
            'priority': 2,
            'category': '⚠️ SOON',
            'title': 'Archive Cleanup',
            'description': 'Remove or properly archive experimental/old code',
            'impact': 'MEDIUM - Reduces codebase size and confusion',
            'effort': 'LOW',
            'action_items': [
                'Review archived/ and backup/ directories',
                'Permanently delete confirmed obsolete code',
                'Move experimental code to dedicated experiment branch',
                'Document any code that must be kept for reference'
            ]
        })
        
        # Low priority: Performance optimization
        actions.append({
            'priority': 3,
            'category': '📈 LATER',
            'title': 'Performance Optimization',
            'description': 'Optimize files with performance issues',
            'impact': 'LOW-MEDIUM - Improves runtime performance',
            'effort': 'MEDIUM',
            'action_items': [
                'Replace blocking sleep calls with async alternatives',
                'Use list comprehensions instead of append loops',
                'Optimize repeated dictionary lookups',
                'Remove wildcard imports'
            ]
        })
        
        # Display action plan
        for action in actions:
            priority_icons = {1: '🚨', 2: '⚠️', 3: '📈'}
            icon = priority_icons.get(action['priority'], '📝')
            
            print(f"\n{icon} PRIORITY {action['priority']} - {action['category']}")
            print(f"📋 {action['title']}")
            print(f"   Description: {action['description']}")
            print(f"   Impact: {action['impact']}")
            print(f"   Effort: {action['effort']}")
            
            if 'files_affected' in action:
                print(f"   Files Affected: {action['files_affected']}")
            
            if 'top_files' in action:
                print(f"   Top Files: {action['top_files']}")
            
            if 'concepts' in action:
                print(f"   Concepts: {action['concepts']}")
            
            print("   Action Items:")
            for item in action['action_items']:
                print(f"      • {item}")
        
        print(f"\n💡 RECOMMENDATION:")
        print(f"   Start with Priority 1 items immediately - they have highest impact")
        print(f"   Complete Priority 2 items within next week")
        print(f"   Schedule Priority 3 items for next maintenance cycle")
        
        return actions
    
    def run_detailed_analysis(self):
        """Run detailed analysis of critical issues"""
        print("Running detailed pipeline issues analysis...")
        
        # Analyze obsolete code
        obsolete_files = self.analyze_obsolete_code()
        
        # Analyze large files
        large_files = self.analyze_large_files()
        
        # Analyze active vs archive
        code_distribution = self.analyze_active_vs_archive()
        
        # Identify conflicts
        conflicts = self.identify_conflicting_implementations()
        
        # Generate action plan
        actions = self.generate_priority_action_plan(obsolete_files, large_files, conflicts)
        
        print(f"\n" + "="*50)
        print("📋 DETAILED ANALYSIS COMPLETE")
        print("="*50)
        print(f"🚨 Critical files to address: {len(obsolete_files)}")
        print(f"🏗️ Large files to refactor: {len([f for f in large_files if f['lines'] > 1000])}")
        print(f"⚠️ Implementation conflicts: {len(conflicts)}")
        print(f"🎯 Priority actions: {len(actions)}")
        
        return {
            'obsolete_files': obsolete_files,
            'large_files': large_files,
            'code_distribution': code_distribution,
            'conflicts': conflicts,
            'actions': actions
        }


if __name__ == "__main__":
    analyzer = DetailedIssuesAnalyzer()
    results = analyzer.run_detailed_analysis()