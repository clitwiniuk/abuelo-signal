#!/usr/bin/env python3
"""
Test del comando /performance en Telegram
"""

import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from production.telegram_smallcap_commands import SmallcapTelegramCommands
    from production.smallcap_production_runner import SmallcapProductionRunner
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_performance_command():
    """Test comando /performance"""
    print("\n🧪 TEST: Comando /performance")
    print("-" * 50)
    
    try:
        # Create mock production runner
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Create telegram commands handler
        telegram_commands = SmallcapTelegramCommands(runner)
        
        print("✅ Components created successfully")
        
        # Test if command is recognized
        handled = telegram_commands.handle_smallcap_command("/performance")
        
        if handled:
            print("✅ Command /performance recognized and handled")
        else:
            print("❌ Command /performance not recognized")
            return False
        
        # Test performance summary method
        summary = runner.get_performance_summary()
        print(f"✅ Performance summary generated: {len(summary)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run performance command test"""
    print("🚀 TESTING /performance COMMAND")
    print("=" * 50)
    
    try:
        success = test_performance_command()
        
        if success:
            print(f"\n✅ COMANDO /performance FUNCIONANDO")
            print("🎯 Ahora debería aparecer en el menú de Telegram")
            print("📱 Usa /help para ver la lista completa de comandos")
        else:
            print(f"\n❌ COMANDO /performance NO FUNCIONA")
            
        return success
        
    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)