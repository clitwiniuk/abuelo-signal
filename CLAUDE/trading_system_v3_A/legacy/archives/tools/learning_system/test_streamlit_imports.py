#!/usr/bin/env python3
"""
Test script para verificar que los imports de Streamlit funcionan correctamente
"""

import sys
from pathlib import Path

# Add current directory to path (same as in streamlit app)
current_dir = Path(__file__).parent.resolve()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

print(f"Testing imports from: {current_dir}")

# Test the main import that was failing
print("\n1. Testing advanced analyzer import...")
try:
    from quality_core.advanced_setup_analyzer import analyze_setup_comprehensive
    print("✅ Advanced analyzer import: SUCCESS")
except ImportError as e:
    print(f"❌ Advanced analyzer import: FAILED - {e}")

# Test the legacy imports
print("\n2. Testing legacy quality system imports...")
try:
    from quality_core.setup_classifier import HybridSetupClassifier
    from quality_core.interfaces import SetupData
    print("✅ Legacy quality system import: SUCCESS")
except ImportError as e:
    print(f"ℹ️ Legacy quality system import: FAILED - {e} (This is expected)")

# Test learning system imports
print("\n3. Testing learning system imports...")
try:
    from quality_core.learning_system import AutoLearningSystem
    print("✅ Learning system import: SUCCESS")
except ImportError as e:
    print(f"❌ Learning system import: FAILED - {e}")

# Test a complete analysis
print("\n4. Testing complete analysis...")
try:
    result = analyze_setup_comprehensive(
        ticker="TEST",
        current_price=5.0,
        current_volume=1_000_000,
        premarket_gap_pct=15.0
    )
    print(f"✅ Analysis test: SUCCESS - Grade: {result['grade']}")
except Exception as e:
    print(f"❌ Analysis test: FAILED - {e}")

print("\n🎉 Import test completed!")
print("If advanced analyzer import succeeded, Streamlit should work.")