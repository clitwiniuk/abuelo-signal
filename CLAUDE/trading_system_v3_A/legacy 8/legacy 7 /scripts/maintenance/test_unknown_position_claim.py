#!/usr/bin/env python3
"""
Test script para verificar el sistema de "reclamar" posiciones UNKNOWN

Este script simula:
1. Una posición UNKNOWN (ej: NEUP de premarket)
2. Un worker (ej: MACDV) intentando reclamarla
3. Verificar que se actualiza correctamente
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.unified_position_manager import UnifiedPositionManager
from datetime import datetime


def test_unknown_position_claim():
    """Test claiming UNKNOWN positions"""
    print("=" * 70)
    print("🧪 TESTING UNKNOWN POSITION CLAIM SYSTEM")
    print("=" * 70)

    # Create manager with test capital
    manager = UnifiedPositionManager(total_capital=2000.0)

    # Simulate UNKNOWN position (como NEUP registrada desde premarket)
    print("\n📋 STEP 1: Registrar posición UNKNOWN (simula premarket sync)")
    print("-" * 70)

    success = manager.register_position(
        symbol='NEUP',
        strategy_type='day',
        position_data={
            'strategy': 'UNKNOWN',  # Posición sin worker asignado
            'entry_price': 1.95,
            'quantity': 100,
            'position_value': 195.0,
            'entry_time': datetime.now().isoformat(),
            'source': 'IBKR_SYNC'
        }
    )

    if success:
        print("✅ UNKNOWN position registered successfully")
    else:
        print("❌ Failed to register UNKNOWN position")
        return False

    # Verify position exists with UNKNOWN strategy
    position = manager.get_position('NEUP')
    if position:
        print(f"📊 Position state:")
        print(f"   Symbol: NEUP")
        print(f"   Strategy: {position.get('strategy')}")
        print(f"   Strategy Type: {position.get('strategy_type')}")
        print(f"   Entry Price: ${position.get('entry_price'):.2f}")
        print(f"   Position Value: ${position.get('position_value'):.2f}")

    # Check if symbol is blocked (should NOT be blocked because it's UNKNOWN)
    print("\n📋 STEP 2: Verificar si NEUP está bloqueada")
    print("-" * 70)

    is_blocked = manager.is_symbol_blocked('NEUP')
    if not is_blocked:
        print("✅ NEUP is NOT blocked (UNKNOWN positions are claimable)")
    else:
        print("❌ NEUP is blocked (ERROR - UNKNOWN should not block)")
        return False

    # Try to claim the position with MACDV worker
    print("\n📋 STEP 3: MACDV worker intenta reclamar NEUP")
    print("-" * 70)

    can_open, reason = manager.can_open_position('NEUP', 'macdv', 195.0)
    if can_open:
        print(f"✅ can_open_position returned True: {reason}")
    else:
        print(f"❌ can_open_position returned False: {reason}")
        return False

    # Claim the position (register with macdv strategy)
    print("\n📋 STEP 4: Registrar posición con MACDV (reclamar)")
    print("-" * 70)

    success = manager.register_position(
        symbol='NEUP',
        strategy_type='macdv',  # MACDV worker reclamando
        position_data={
            'strategy': 'macdv',
            'entry_price': 1.95,
            'quantity': 100,
            'position_value': 195.0,
            'entry_time': datetime.now().isoformat()
        }
    )

    if success:
        print("✅ Position claimed successfully by MACDV")
    else:
        print("❌ Failed to claim position")
        return False

    # Verify position now belongs to MACDV
    print("\n📋 STEP 5: Verificar que posición ahora pertenece a MACDV")
    print("-" * 70)

    position = manager.get_position('NEUP')
    if position:
        strategy = position.get('strategy')
        strategy_type = position.get('strategy_type')

        print(f"📊 Updated position state:")
        print(f"   Symbol: NEUP")
        print(f"   Strategy: {strategy}")
        print(f"   Strategy Type: {strategy_type}")
        print(f"   Entry Price: ${position.get('entry_price'):.2f}")
        print(f"   Claimed At: {position.get('claimed_at', 'N/A')}")

        if strategy == 'macdv' and strategy_type == 'day':
            print("✅ Position correctly claimed by MACDV")
        else:
            print(f"❌ Position strategy wrong: expected 'macdv', got '{strategy}'")
            return False
    else:
        print("❌ Position not found after claiming")
        return False

    # Try to claim again with different worker (should fail)
    print("\n📋 STEP 6: Otro worker intenta reclamar (debería fallar)")
    print("-" * 70)

    is_blocked = manager.is_symbol_blocked('NEUP')
    if is_blocked:
        print("✅ NEUP is NOW blocked (correctly owned by MACDV)")
    else:
        print("❌ NEUP is still not blocked (ERROR - should be blocked now)")
        return False

    can_open, reason = manager.can_open_position('NEUP', 'gap_go', 195.0)
    if not can_open:
        print(f"✅ can_open_position correctly returned False: {reason}")
    else:
        print(f"❌ can_open_position returned True (ERROR - should be blocked)")
        return False

    # Clean up
    print("\n📋 STEP 7: Cleanup - unregister position")
    print("-" * 70)

    success = manager.unregister_position('NEUP', 'macdv')
    if success:
        print("✅ Position unregistered successfully")
    else:
        print("❌ Failed to unregister position")
        return False

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - UNKNOWN POSITION CLAIM SYSTEM WORKS!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = test_unknown_position_claim()
    sys.exit(0 if success else 1)
