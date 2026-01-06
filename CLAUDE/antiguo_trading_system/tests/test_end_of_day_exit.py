#!/usr/bin/env python3
"""
Test End of Day Exit específicamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.stop_loss_manager import create_stop_params_from_config, get_stop_loss_manager
from core.interfaces import MarketData
from datetime import datetime, timezone
import pytz

def test_end_of_day_timing():
    """Test específico para verificar timing del end of day exit"""
    print("🧪 TEST: End of Day Exit Timing")
    
    stop_manager = get_stop_loss_manager()
    stop_manager.clear_all_positions()
    
    stop_params = create_stop_params_from_config({})
    
    # Register position
    symbol = "EOD_TEST"
    entry_price = 10.00
    entry_time = datetime.now(timezone.utc).replace(hour=14, minute=30)  # 2:30 PM UTC (10:30 AM ET)
    
    stop_manager.register_position(
        symbol=symbol,
        entry_price=entry_price,
        entry_time=entry_time,
        side='bullish',
        strategy_name='eod_test',
        stop_params=stop_params
    )
    
    print(f"   📊 Position registered at {entry_time.strftime('%H:%M UTC')}")
    print(f"   📋 End of day exit enabled: {stop_params.end_of_day_exit}")
    
    # Test different times - config.ini: market_close_time=16:00 ET, minutes_before_close_to_exit=5
    # This means positions should close at 16:00 - 5min = 15:55 ET
    # Conversión correcta: 15:55 ET = 19:55 UTC = 21:55 CEST (Madrid)
    test_times = [
        (17, 30, False, "3:30 PM ET - Should NOT trigger"),  # 17:30 UTC = 15:30 ET = 19:30 CEST
        (19, 54, False, "3:54 PM ET - Should NOT trigger"),  # 19:54 UTC = 15:54 ET = 21:54 CEST  
        (19, 55, True, "3:55 PM ET - Should trigger"),      # 19:55 UTC = 15:55 ET = 21:55 CEST (config: 16:00-5min)
        (19, 58, True, "3:58 PM ET - Should trigger"),      # 19:58 UTC = 15:58 ET = 21:58 CEST
        (20, 0, False, "4:00 PM ET - Market closed, should NOT trigger"),  # 20:00 UTC = 16:00 ET = 22:00 CEST (market closed)
    ]
    
    for hour, minute, should_trigger, description in test_times:
        # Re-register position for each test to avoid it being removed after first exit
        if symbol not in stop_manager.active_positions:
            stop_manager.register_position(
                symbol=symbol,
                entry_price=entry_price,
                entry_time=entry_time,
                side='bullish',
                strategy_name='eod_test',
                stop_params=stop_params
            )
        
        test_time = datetime.now(timezone.utc).replace(hour=hour, minute=minute)
        
        test_bar = MarketData(
            symbol=symbol,
            timestamp=test_time,
            open=entry_price,
            high=entry_price,
            low=entry_price,
            close=entry_price,
            volume=10000
        )
        
        exit_signal = stop_manager.check_exit_conditions(symbol, test_bar)
        
        if should_trigger:
            if exit_signal and exit_signal.metadata.get('exit_reason') == 'end_of_day':
                print(f"   ✅ {description} - CORRECTO: Exit signal generated")
            else:
                print(f"   ❌ {description} - ERROR: Should have triggered but didn't")
                return False
        else:
            if not exit_signal:
                print(f"   ✅ {description} - CORRECTO: No exit signal")
            else:
                print(f"   ❌ {description} - ERROR: Should NOT have triggered but did")
                return False
    
    return True

def test_config_end_of_day_settings():
    """Test configuraciones específicas de end of day"""
    print("\n🧪 TEST: Configuraciones End of Day")
    
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Check config values
    market_close_time = config.get('GLOBAL', 'market_close_time', fallback='16:00')
    end_of_day_exit = config.getboolean('GLOBAL', 'end_of_day_exit', fallback=True)
    end_of_day_exit_time = config.get('GLOBAL', 'end_of_day_exit_time', fallback='15:55')
    
    print(f"   📋 market_close_time: {market_close_time}")
    print(f"   📋 end_of_day_exit: {end_of_day_exit}")
    print(f"   📋 end_of_day_exit_time: {end_of_day_exit_time}")
    
    # Verify stop params use these settings
    stop_params = create_stop_params_from_config({})
    print(f"   🔍 StopLossParameters.end_of_day_exit: {stop_params.end_of_day_exit}")
    
    if stop_params.end_of_day_exit == end_of_day_exit:
        print("   ✅ End of day exit configurado correctamente")
        return True
    else:
        print("   ❌ End of day exit NO configurado correctamente")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO TEST ESPECÍFICO DE END OF DAY EXIT")
    print("=" * 50)
    
    try:
        config_test = test_config_end_of_day_settings()
        timing_test = test_end_of_day_timing()
        
        print("\n" + "=" * 50)
        print("📊 RESUMEN:")
        print(f"{'✅' if config_test else '❌'} Configuración End of Day - {'PASSED' if config_test else 'FAILED'}")
        print(f"{'✅' if timing_test else '❌'} Timing End of Day - {'PASSED' if timing_test else 'FAILED'}")
        
        if config_test and timing_test:
            print("\n🎉 END OF DAY EXIT FUNCIONA CORRECTAMENTE")
            print("📋 El sistema cerrará posiciones a las 3:55 PM ET (15:55) según config.ini")
        else:
            print("\n⚠️ HAY PROBLEMAS CON EL END OF DAY EXIT")
            
    except Exception as e:
        print(f"\n❌ ERROR EN TEST: {e}")
        import traceback
        traceback.print_exc()