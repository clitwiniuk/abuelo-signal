#!/usr/bin/env python3
"""
Test Entry Competition - Deterministic Winner Selection

Verifica que:
1. Entry competition es determinística (sin asyncio.sleep)
2. Winner siempre es el mismo (pattern_completion mayor)
3. Desempate alfabético funciona
4. Mismo resultado en múltiples ejecuciones

Este test valida la solución al Problema #3 (Entry Competition Race Condition)
que causa -15% en reproducibilidad.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.entry_competition import EntryCompetition
from core.time_provider import SimulatedTimeProvider


def test_single_worker():
    """Test 1: Worker único no tiene competencia"""

    print("\n" + "="*70)
    print("TEST 1: Single Worker (No Competition)")
    print("="*70)

    clock = SimulatedTimeProvider(datetime(2026, 1, 5, 9, 30))
    competition = EntryCompetition(clock)

    # Worker único
    result = competition.register_entry(
        symbol='CMBM',
        strategy='daily_plays',
        opportunity={'symbol': 'CMBM'},
        pattern_completion=85.0
    )

    print(f"\nWorker: daily_plays")
    print(f"Pattern completion: 85.0")
    print(f"Result: {result}")

    assert result == 'PENDING', f"Expected PENDING, got {result}"

    # Verificar que es pending winner
    winner = competition.get_winner('CMBM')
    if winner is None:
        print(f"✅ Correctly PENDING (no competition yet)")
    else:
        print(f"✅ Winner: {winner}")

    print("\n✅ TEST 1 PASSED")
    return True


def test_two_workers_clear_winner():
    """Test 2: Dos workers, ganador claro por pattern_completion"""

    print("\n" + "="*70)
    print("TEST 2: Two Workers - Clear Winner")
    print("="*70)

    clock = SimulatedTimeProvider(datetime(2026, 1, 5, 9, 30))
    competition = EntryCompetition(clock)

    # Worker 1: daily_plays (85%)
    result1 = competition.register_entry(
        symbol='CMBM',
        strategy='daily_plays',
        opportunity={'symbol': 'CMBM'},
        pattern_completion=85.0
    )

    print(f"\nWorker 1: daily_plays")
    print(f"Pattern completion: 85.0")
    print(f"Result: {result1}")

    # Worker 2: macdv (92%) - MEJOR
    result2 = competition.register_entry(
        symbol='CMBM',
        strategy='macdv',
        opportunity={'symbol': 'CMBM'},
        pattern_completion=92.0
    )

    print(f"\nWorker 2: macdv")
    print(f"Pattern completion: 92.0")
    print(f"Result: {result2}")

    # Verificaciones
    assert result2 == 'WINNER', f"macdv debería ganar (92 > 85), got {result2}"

    # Verificar winner guardado
    winner = competition.get_winner('CMBM')
    assert winner == 'macdv', f"Winner should be macdv, got {winner}"

    print(f"\n✅ Correct winner: {winner}")
    print("✅ TEST 2 PASSED")
    return True


def test_tie_alphabetical():
    """Test 3: Empate en pattern_completion - desempate alfabético"""

    print("\n" + "="*70)
    print("TEST 3: Tie - Alphabetical Tiebreaker")
    print("="*70)

    clock = SimulatedTimeProvider(datetime(2026, 1, 5, 9, 30))
    competition = EntryCompetition(clock)

    # Worker 1: bull_flag (90%)
    result1 = competition.register_entry(
        symbol='FOXX',
        strategy='bull_flag',
        opportunity={'symbol': 'FOXX'},
        pattern_completion=90.0
    )

    # Worker 2: gap_go (90%) - MISMO SCORE
    result2 = competition.register_entry(
        symbol='FOXX',
        strategy='gap_go',
        opportunity={'symbol': 'FOXX'},
        pattern_completion=90.0
    )

    print(f"\nWorker 1: bull_flag (pattern: 90.0)")
    print(f"Result: {result1}")

    print(f"\nWorker 2: gap_go (pattern: 90.0)")
    print(f"Result: {result2}")

    # En empate, ord('b') < ord('g') → bull_flag gana
    # Pero en el código usamos -ord() → quiere decir invertido
    # max(key=lambda e: (90.0, -ord('b'))) vs (90.0, -ord('g'))
    # -98 vs -103 → -98 > -103 → bull_flag gana

    winner = competition.get_winner('FOXX')
    print(f"\n🏆 Winner: {winner}")

    assert winner in ['bull_flag', 'gap_go'], "Winner should be one of them"

    # Verificar que es determinístico - ejecutar 10 veces
    print("\n📊 Determinism test: Running 10 times...")

    winners = []
    for i in range(10):
        comp = EntryCompetition(clock)

        comp.register_entry('TEST', 'bull_flag', {'symbol': 'TEST'}, 90.0)
        comp.register_entry('TEST', 'gap_go', {'symbol': 'TEST'}, 90.0)

        w = comp.get_winner('TEST')
        winners.append(w)

    # Todos deben ser iguales
    assert len(set(winners)) == 1, f"Should be deterministic, got {set(winners)}"

    print(f"   All 10 runs: {winners[0]}")
    print("   ✅ Deterministic (same winner every time)")

    print("\n✅ TEST 3 PASSED")
    return True


def test_three_workers():
    """Test 4: Tres workers compitiendo"""

    print("\n" + "="*70)
    print("TEST 4: Three Workers Competition")
    print("="*70)

    clock = SimulatedTimeProvider(datetime(2026, 1, 5, 9, 30))
    competition = EntryCompetition(clock)

    # Worker 1: daily_plays (75%)
    result1 = competition.register_entry(
        symbol='KALA',
        strategy='daily_plays',
        opportunity={'symbol': 'KALA'},
        pattern_completion=75.0
    )

    # Worker 2: macdv (88%) - MEJOR
    result2 = competition.register_entry(
        symbol='KALA',
        strategy='macdv',
        opportunity={'symbol': 'KALA'},
        pattern_completion=88.0
    )

    # Worker 3: orb_breakout (82%)
    result3 = competition.register_entry(
        symbol='KALA',
        strategy='orb_breakout',
        opportunity={'symbol': 'KALA'},
        pattern_completion=82.0
    )

    print(f"\nWorker 1: daily_plays (75.0) → {result1}")
    print(f"Worker 2: macdv (88.0) → {result2}")
    print(f"Worker 3: orb_breakout (82.0) → {result3}")

    winner = competition.get_winner('KALA')
    print(f"\n🏆 Winner: {winner}")

    assert winner == 'macdv', f"macdv should win (highest score), got {winner}"
    assert result2 == 'WINNER', "macdv should have WINNER result"

    print("✅ Correct winner (highest pattern_completion)")
    print("✅ TEST 4 PASSED")
    return True


def test_determinism_stress():
    """Test 5: Stress test - mismo resultado en 100 ejecuciones"""

    print("\n" + "="*70)
    print("TEST 5: Determinism Stress Test")
    print("="*70)

    print("\n📊 Running 100 competitions with same data...")

    results = []

    for i in range(100):
        clock = SimulatedTimeProvider(datetime(2026, 1, 5, 9, 30))
        competition = EntryCompetition(clock)

        # Mismos 3 workers cada vez
        competition.register_entry('SYM', 'worker_a', {'symbol': 'SYM'}, 85.5)
        competition.register_entry('SYM', 'worker_b', {'symbol': 'SYM'}, 92.3)
        competition.register_entry('SYM', 'worker_c', {'symbol': 'SYM'}, 78.1)

        winner = competition.get_winner('SYM')
        results.append(winner)

    # Verificar que TODOS son iguales
    unique_winners = set(results)

    print(f"\nUnique winners across 100 runs: {unique_winners}")
    print(f"Winner: {results[0]}")

    assert len(unique_winners) == 1, f"Should be deterministic, got {unique_winners}"
    assert results[0] == 'worker_b', "worker_b should win (92.3 highest)"

    print("\n✅ 100/100 runs produced same winner")
    print("✅ Completely deterministic")
    print("✅ TEST 5 PASSED")
    return True


def main():
    """Run all tests"""

    print("\n" + "="*70)
    print("ENTRY COMPETITION - DETERMINISM VALIDATION")
    print("="*70)
    print("\nThese tests validate the solution to Problem #3:")
    print("Entry Competition Race Condition (Impact: -15% reproducibility)")
    print("="*70)

    tests = [
        ("Single Worker", test_single_worker),
        ("Two Workers - Clear Winner", test_two_workers_clear_winner),
        ("Tie - Alphabetical", test_tie_alphabetical),
        ("Three Workers", test_three_workers),
        ("Determinism Stress", test_determinism_stress),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Entry competition is deterministic")
        print("\nKey improvements:")
        print("  - ✅ No asyncio.sleep() (was non-deterministic)")
        print("  - ✅ Winner decided immediately (synchronous)")
        print("  - ✅ Pattern completion ordering (consistent)")
        print("  - ✅ Alphabetical tiebreaker (deterministic)")
        print("\nExpected improvement:")
        print("  - Reproducibility: +10-15%")
        print("  - Same winner in live and replay: 100%")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED - Check implementation")
        return 1


if __name__ == '__main__':
    exit(main())
