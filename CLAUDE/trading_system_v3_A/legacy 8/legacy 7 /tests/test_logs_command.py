#!/usr/bin/env python3
"""
Test del comando /logs en Telegram
"""

import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def create_test_log():
    """Create test log file"""
    os.makedirs("logs", exist_ok=True)
    
    with open("logs/trading_system.log", "w") as f:
        f.write("2024-08-21 14:30:15,123 - INFO - Sistema iniciado\n")
        f.write("2024-08-21 14:30:20,456 - INFO - IBKR conectado\n")
        f.write("2024-08-21 14:30:25,789 - INFO - Scanner activado\n")
        f.write("2024-08-21 14:35:01,012 - INFO - Play encontrado: AAPL\n")
        f.write("2024-08-21 14:35:05,345 - INFO - FinBERT analysis: EARNINGS catalyst\n")
        f.write("2024-08-21 14:35:10,678 - INFO - Mayordomo decision: APPROVE\n")
        f.write("2024-08-21 14:35:15,901 - INFO - Trade executed: AAPL at $180.50\n")

def test_logs_command():
    """Test comando /logs"""
    print("\n🧪 TEST: Comando /logs")
    print("-" * 50)
    
    try:
        from production.telegram_smallcap_commands import SmallcapTelegramCommands
        
        # Create test log file
        create_test_log()
        print("✅ Test log file created")
        
        # Create telegram commands handler
        telegram_commands = SmallcapTelegramCommands()
        
        # Test basic logs command
        handled = telegram_commands.handle_smallcap_command("/logs")
        if handled:
            print("✅ Command /logs recognized and handled")
        else:
            print("❌ Command /logs not recognized")
            return False
        
        # Test logs with number
        handled = telegram_commands.handle_smallcap_command("/logs 10")
        if handled:
            print("✅ Command /logs 10 recognized and handled")
        else:
            print("❌ Command /logs 10 not recognized")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run logs command test"""
    print("🚀 TESTING /logs COMMAND")
    print("=" * 50)
    
    try:
        success = test_logs_command()
        
        if success:
            print(f"\n✅ COMANDO /logs FUNCIONANDO")
            print("📝 Ahora puedes usar:")
            print("   • /logs - Ver últimas 50 líneas")
            print("   • /logs 100 - Ver últimas 100 líneas")
            print("   • /logs 20 - Ver últimas 20 líneas")
            print(f"📁 Archivo: logs/trading_system.log")
        else:
            print(f"\n❌ COMANDO /logs NO FUNCIONA")
            
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