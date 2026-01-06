#!/usr/bin/env python3
"""
Test Worker Routing Logic
Simula diferentes opportunities y verifica qué workers matchean
"""

def match_workers(opportunity):
    """
    Replica lógica de _match_workers() del WorkerBasedStrategyEngine
    """
    workers = []

    # Extraer métricas
    gap = abs(opportunity.get('gap_percentage', 0))
    volume_ratio = opportunity.get('volume_ratio', 0)
    catalyst_type = opportunity.get('catalyst_type', '')
    catalyst_strength = opportunity.get('catalyst_strength', 0)
    quality_score = opportunity.get('quality_score', 0)
    current_price = opportunity.get('current_price', 0)
    symbol = opportunity.get('symbol', 'TEST')

    print(f"\n{'='*80}")
    print(f"Testing: {symbol}")
    print(f"  Gap: {gap:.1f}%")
    print(f"  Volume Ratio: {volume_ratio:.1f}x")
    print(f"  Catalyst: {catalyst_type} (strength={catalyst_strength})")
    print(f"  Quality Score: {quality_score:.1f}")
    print(f"  Price: ${current_price:.2f}")
    print(f"{'-'*80}")

    # Strong catalysts
    strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT']
    has_strong_catalyst = (catalyst_type in strong_catalysts and catalyst_strength >= 6)

    # Match 1: Gap-Go
    gap_go_match = (
        gap >= 8.0 and
        volume_ratio >= 2.0 and
        current_price <= 15.0 and
        quality_score >= 50.0 and
        not has_strong_catalyst
    )

    if gap_go_match:
        workers.append('gap_go')
        print(f"  ✅ Gap-Go: MATCHED")
        print(f"     - Gap {gap:.1f}% >= 8.0 ✓")
        print(f"     - Volume {volume_ratio:.1f}x >= 2.0 ✓")
        print(f"     - Price ${current_price:.2f} <= 15.0 ✓")
        print(f"     - Quality {quality_score:.1f} >= 50.0 ✓")
        print(f"     - No strong catalyst ✓")
    else:
        print(f"  ❌ Gap-Go: NOT MATCHED")
        if gap < 8.0:
            print(f"     - Gap {gap:.1f}% < 8.0 ✗")
        if volume_ratio < 2.0:
            print(f"     - Volume {volume_ratio:.1f}x < 2.0 ✗")
        if current_price > 15.0:
            print(f"     - Price ${current_price:.2f} > 15.0 ✗")
        if quality_score < 50.0:
            print(f"     - Quality {quality_score:.1f} < 50.0 ✗")
        if has_strong_catalyst:
            print(f"     - Has strong catalyst ({catalyst_type}) ✗")

    # Match 2: MACDV
    macdv_match = (
        catalyst_type == 'TECHNICAL' and
        gap <= 5.0 and
        volume_ratio >= 1.5 and
        1.0 <= current_price <= 25.0 and
        quality_score >= 50.0
    )

    if macdv_match:
        workers.append('macdv')
        print(f"  ✅ MACDV: MATCHED")
        print(f"     - Catalyst TECHNICAL ✓")
        print(f"     - Gap {gap:.1f}% <= 5.0 ✓")
        print(f"     - Volume {volume_ratio:.1f}x >= 1.5 ✓")
        print(f"     - Price ${current_price:.2f} in [1.0, 25.0] ✓")
        print(f"     - Quality {quality_score:.1f} >= 50.0 ✓")
    else:
        print(f"  ❌ MACDV: NOT MATCHED")
        if catalyst_type != 'TECHNICAL':
            print(f"     - Catalyst '{catalyst_type}' != 'TECHNICAL' ✗")
        if gap > 5.0:
            print(f"     - Gap {gap:.1f}% > 5.0 ✗")
        if volume_ratio < 1.5:
            print(f"     - Volume {volume_ratio:.1f}x < 1.5 ✗")
        if not (1.0 <= current_price <= 25.0):
            print(f"     - Price ${current_price:.2f} not in [1.0, 25.0] ✗")
        if quality_score < 50.0:
            print(f"     - Quality {quality_score:.1f} < 50.0 ✗")

    # Match 3: Daily Plays
    daily_plays_match = (
        catalyst_type in strong_catalysts and
        catalyst_strength >= 6 and
        volume_ratio >= 0.5 and
        1.0 <= current_price <= 50.0 and
        quality_score >= 35.0
    )

    if daily_plays_match:
        workers.append('daily_plays')
        print(f"  ✅ Daily Plays: MATCHED")
        print(f"     - Catalyst {catalyst_type} in strong_catalysts ✓")
        print(f"     - Strength {catalyst_strength} >= 6 ✓")
        print(f"     - Volume {volume_ratio:.1f}x >= 0.5 ✓")
        print(f"     - Price ${current_price:.2f} in [1.0, 50.0] ✓")
        print(f"     - Quality {quality_score:.1f} >= 35.0 ✓")
    else:
        print(f"  ❌ Daily Plays: NOT MATCHED")
        if catalyst_type not in strong_catalysts:
            print(f"     - Catalyst '{catalyst_type}' not in {strong_catalysts} ✗")
        if catalyst_strength < 6:
            print(f"     - Strength {catalyst_strength} < 6 ✗")
        if volume_ratio < 0.5:
            print(f"     - Volume {volume_ratio:.1f}x < 0.5 ✗")
        if not (1.0 <= current_price <= 50.0):
            print(f"     - Price ${current_price:.2f} not in [1.0, 50.0] ✗")
        if quality_score < 35.0:
            print(f"     - Quality {quality_score:.1f} < 35.0 ✗")

    # Match 4: Bull Flag
    extreme_catalysts = ['FDA', 'M&A', 'EARNINGS']
    bull_flag_match = (
        3.0 <= gap <= 8.0 and
        volume_ratio >= 2.0 and
        catalyst_type not in extreme_catalysts and
        1.0 <= current_price <= 15.0 and
        quality_score >= 50.0
    )

    if bull_flag_match:
        workers.append('bull_flag')
        print(f"  ✅ Bull Flag: MATCHED")
        print(f"     - Gap {gap:.1f}% in [3.0, 8.0] ✓")
        print(f"     - Volume {volume_ratio:.1f}x >= 2.0 ✓")
        print(f"     - Catalyst {catalyst_type} not in extreme ✓")
        print(f"     - Price ${current_price:.2f} in [1.0, 15.0] ✓")
        print(f"     - Quality {quality_score:.1f} >= 50.0 ✓")
    else:
        print(f"  ❌ Bull Flag: NOT MATCHED")
        if not (3.0 <= gap <= 8.0):
            print(f"     - Gap {gap:.1f}% not in [3.0, 8.0] ✗")
        if volume_ratio < 2.0:
            print(f"     - Volume {volume_ratio:.1f}x < 2.0 ✗")
        if catalyst_type in extreme_catalysts:
            print(f"     - Catalyst {catalyst_type} in extreme ✗")
        if not (1.0 <= current_price <= 15.0):
            print(f"     - Price ${current_price:.2f} not in [1.0, 15.0] ✗")
        if quality_score < 50.0:
            print(f"     - Quality {quality_score:.1f} < 50.0 ✗")

    print(f"{'-'*80}")
    if workers:
        print(f"  🎯 RESULT: Routed to {len(workers)} worker(s): {workers}")
    else:
        print(f"  ⚪ RESULT: NO WORKERS MATCHED")

    return workers


# Test Cases
if __name__ == "__main__":
    print("=" * 80)
    print("WORKER ROUTING TEST")
    print("=" * 80)

    test_cases = [
        {
            'name': 'Gap-Go Típico',
            'opportunity': {
                'symbol': 'AIHS',
                'gap_percentage': 12.5,
                'volume_ratio': 3.2,
                'catalyst_type': 'TECHNICAL',
                'catalyst_strength': 0,
                'quality_score': 65.0,
                'current_price': 1.25
            }
        },
        {
            'name': 'MACDV Técnico',
            'opportunity': {
                'symbol': 'AKAN',
                'gap_percentage': 2.3,
                'volume_ratio': 2.1,
                'catalyst_type': 'TECHNICAL',
                'catalyst_strength': 0,
                'quality_score': 58.0,
                'current_price': 3.60
            }
        },
        {
            'name': 'Daily Plays con Catalyst',
            'opportunity': {
                'symbol': 'DVLT',
                'gap_percentage': 6.5,
                'volume_ratio': 1.8,
                'catalyst_type': 'FDA',
                'catalyst_strength': 8,
                'quality_score': 72.0,
                'current_price': 1.35
            }
        },
        {
            'name': 'Bull Flag Moderado',
            'opportunity': {
                'symbol': 'CGNT',
                'gap_percentage': 5.2,
                'volume_ratio': 2.5,
                'catalyst_type': 'NEWS',
                'catalyst_strength': 4,
                'quality_score': 55.0,
                'current_price': 2.80
            }
        },
        {
            'name': 'Intraday Momentum (bajo quality)',
            'opportunity': {
                'symbol': 'GLXG',
                'gap_percentage': 1.8,
                'volume_ratio': 2.3,
                'catalyst_type': 'INTRADAY_MOMENTUM',
                'catalyst_strength': 0,
                'quality_score': 42.0,
                'current_price': 7.65
            }
        },
        {
            'name': 'Gap Grande sin Volume',
            'opportunity': {
                'symbol': 'TEST1',
                'gap_percentage': 15.0,
                'volume_ratio': 1.2,  # Bajo volumen
                'catalyst_type': 'TECHNICAL',
                'catalyst_strength': 0,
                'quality_score': 65.0,
                'current_price': 2.50
            }
        },
        {
            'name': 'Catalyst Débil',
            'opportunity': {
                'symbol': 'TEST2',
                'gap_percentage': 4.5,
                'volume_ratio': 2.0,
                'catalyst_type': 'M&A',
                'catalyst_strength': 4,  # Strength débil
                'quality_score': 58.0,
                'current_price': 5.20
            }
        }
    ]

    results = {}
    for test in test_cases:
        workers = match_workers(test['opportunity'])
        results[test['name']] = workers

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for test_name, workers in results.items():
        if workers:
            print(f"✅ {test_name:30s} → {workers}")
        else:
            print(f"❌ {test_name:30s} → NO MATCH")

    # Worker distribution
    print("\n" + "=" * 80)
    print("WORKER DISTRIBUTION")
    print("=" * 80)

    worker_counts = {'gap_go': 0, 'macdv': 0, 'daily_plays': 0, 'bull_flag': 0}
    for workers in results.values():
        for worker in workers:
            worker_counts[worker] += 1

    for worker, count in worker_counts.items():
        print(f"  {worker:15s}: {count} opportunities")
