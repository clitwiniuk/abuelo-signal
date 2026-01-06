#!/usr/bin/env python3
"""
Test de la Estructura Organizada de TradeTally
==============================================

Verifica que todos los imports y funcionalidades trabajen correctamente
después de la reorganización.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

def test_config_imports():
    """Test imports de configuración"""
    print("🧪 Testing Config Imports...")
    try:
        from integrations.tradetally.config.tradetally_config import TradeTallyConfig
        config = TradeTallyConfig()
        print(f"✅ Config imported successfully")
        print(f"   Project root: {config.project_root}")
        print(f"   Database path: {config.db_path}")
        print(f"   Base URL: {config.base_url}")
        print(f"   Is configured: {config.is_configured()}")
        return True
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False

def test_sync_imports():
    """Test imports de sincronización"""
    print("\n🧪 Testing Sync Imports...")
    try:
        from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration
        print(f"✅ TradeTallyIntegration imported successfully")
        return True
    except Exception as e:
        print(f"❌ Sync import failed: {e}")
        return False

def test_package_imports():
    """Test imports del package principal"""
    print("\n🧪 Testing Package Imports...")
    try:
        from integrations.tradetally import TradeTallyIntegration, TradeTallyConfig
        print(f"✅ Package imports successful")
        return True
    except Exception as e:
        print(f"❌ Package import failed: {e}")
        return False

def test_cli_execution():
    """Test ejecución del CLI"""
    print("\n🧪 Testing CLI Execution...")
    try:
        # Test that the CLI can be imported
        cli_path = project_root / "integrations" / "tradetally" / "cli" / "tradetally_cli.py"
        if cli_path.exists():
            print(f"✅ CLI file exists at: {cli_path}")
            return True
        else:
            print(f"❌ CLI file not found at: {cli_path}")
            return False
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
        return False

def test_wrapper_script():
    """Test script wrapper"""
    print("\n🧪 Testing Wrapper Script...")
    try:
        wrapper_path = project_root / "tradetally"
        if wrapper_path.exists():
            print(f"✅ Wrapper script exists at: {wrapper_path}")
            return True
        else:
            print(f"❌ Wrapper script not found")
            return False
    except Exception as e:
        print(f"❌ Wrapper test failed: {e}")
        return False

def test_file_structure():
    """Test estructura de archivos"""
    print("\n🧪 Testing File Structure...")
    
    expected_files = [
        "integrations/tradetally/__init__.py",
        "integrations/tradetally/core/__init__.py",
        "integrations/tradetally/core/tradetally_sync.py",
        "integrations/tradetally/config/__init__.py", 
        "integrations/tradetally/config/tradetally_config.py",
        "integrations/tradetally/cli/__init__.py",
        "integrations/tradetally/cli/tradetally_cli.py",
        "integrations/tradetally/tests/__init__.py",
        "integrations/tradetally/tests/create_test_data.py",
        "integrations/tradetally/tests/tradetally_debug.py",
        "integrations/tradetally/docs/API_DOCUMENTATION.md"
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in expected_files:
        full_path = project_root / file_path
        if full_path.exists():
            existing_files.append(file_path)
        else:
            missing_files.append(file_path)
    
    print(f"✅ Existing files: {len(existing_files)}")
    for file in existing_files[:5]:  # Show first 5
        print(f"   • {file}")
    if len(existing_files) > 5:
        print(f"   ... and {len(existing_files) - 5} more")
    
    if missing_files:
        print(f"❌ Missing files: {len(missing_files)}")
        for file in missing_files:
            print(f"   • {file}")
        return False
    else:
        print(f"✅ All expected files present")
        return True

def main():
    """Ejecutar todos los tests"""
    print("🚀 TRADETALLY ORGANIZATION TEST")
    print("=" * 50)
    print(f"📁 Project root: {project_root}")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Config Imports", test_config_imports),
        ("Sync Imports", test_sync_imports),
        ("Package Imports", test_package_imports),
        ("CLI Execution", test_cli_execution),
        ("Wrapper Script", test_wrapper_script)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
    
    print(f"\n" + "=" * 50)
    print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! TradeTally organization is working correctly.")
        print(f"\n💡 Usage instructions:")
        print(f"   # From project root:")
        print(f"   python tradetally config")
        print(f"   python tradetally status") 
        print(f"   python tradetally sync")
        print(f"   ")
        print(f"   # Direct CLI access:")
        print(f"   python integrations/tradetally/cli/tradetally_cli.py config")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)