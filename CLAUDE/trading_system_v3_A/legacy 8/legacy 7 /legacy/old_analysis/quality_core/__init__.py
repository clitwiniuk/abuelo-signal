"""
Quality Core Module
==================

Advanced quality analysis system with learning capabilities for trading setups.

Main components:
- advanced_setup_analyzer: Multi-factor analysis with consolidation, timing, volume, and news
- learning_system: Automatic learning and weight optimization
- learning_monitor: Monitoring and management tools
"""

from .advanced_setup_analyzer import analyze_setup_comprehensive, AdvancedSetupAnalyzer
from .learning_system import AutoLearningSystem, PredictionTracker, WeightLearningSystem

__version__ = "1.0.0"
__author__ = "Trading System v3"

__all__ = [
    'analyze_setup_comprehensive',
    'AdvancedSetupAnalyzer', 
    'AutoLearningSystem',
    'PredictionTracker',
    'WeightLearningSystem'
]