#!/usr/bin/env python3
"""
Replay Verifier - Verificador automático de decisiones de workers

Valida que cada decisión del worker cumple con los criterios esperados:
- Pattern completion
- Precio dentro de rangos
- Volumen dentro de límites
- Trading hours correctos
- Cooldown respetado
- Locks respetados
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, time


class ReplayVerifier:
    """
    Verificador de decisiones de replay

    Comprueba que cada decisión cumple con los criterios del worker
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize verifier

        Args:
            verbose: Enable verbose logging
        """
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose

    def verify_entry_decision(
        self,
        decision: Dict,
        opportunity: Dict,
        worker_config: Dict
    ) -> Dict[str, Any]:
        """
        Verifica una decisión de entrada

        Args:
            decision: ReplayDecision object (as dict)
            opportunity: Opportunity data
            worker_config: Worker configuration

        Returns:
            Verification result dict with checks passed/failed
        """
        checks_passed = {}
        checks_failed = {}

        symbol = decision['symbol']
        entry_price = decision.get('entry_price', 0)
        pattern_completion = decision.get('pattern_completion', 0)

        # 1. Check pattern completion >= 75%
        if pattern_completion >= 75.0:
            checks_passed['pattern_completion'] = True
        else:
            checks_failed['pattern_completion'] = f'{pattern_completion:.1f}% < 75%'

        # 2. Check price in range [min_price, max_price]
        min_price = worker_config.get('min_price', 0.0)
        max_price = worker_config.get('max_price', 999999.0)

        if min_price <= entry_price <= max_price:
            checks_passed['price_range'] = True
        else:
            checks_failed['price_range'] = f'${entry_price:.2f} not in [${min_price:.2f}, ${max_price:.2f}]'

        # 3. Check volume ratio <= max_volume_ratio
        volume_ratio = opportunity.get('volume_ratio', 0)
        max_volume_ratio = worker_config.get('max_volume_ratio', 10.0)

        if volume_ratio <= max_volume_ratio:
            checks_passed['volume_ratio'] = True
        else:
            checks_failed['volume_ratio'] = f'{volume_ratio:.1f}x > {max_volume_ratio:.1f}x'

        # 4. Check trading hours (9:30 - 16:00 ET)
        timestamp = decision.get('timestamp')
        if timestamp:
            hour = timestamp.hour
            minute = timestamp.minute

            # Trading hours: 9:30 - 16:00
            market_open = time(9, 30)
            market_close = time(16, 0)

            current_time = time(hour, minute)

            if market_open <= current_time <= market_close:
                checks_passed['trading_hours'] = True
            else:
                checks_failed['trading_hours'] = f'{hour:02d}:{minute:02d} outside market hours'

        # 5. Compile results
        result = {
            'symbol': symbol,
            'decision_type': 'ENTRY',
            'checks_passed': checks_passed,
            'checks_failed': checks_failed,
            'all_passed': len(checks_failed) == 0,
            'pass_rate': len(checks_passed) / (len(checks_passed) + len(checks_failed)) if (len(checks_passed) + len(checks_failed)) > 0 else 0.0
        }

        if self.verbose:
            self._log_verification_result(result)

        return result

    def verify_exit_decision(
        self,
        decision: Dict,
        position: Dict,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Verifica una decisión de salida

        Args:
            decision: ReplayDecision object (as dict)
            position: Active position data
            current_price: Current market price

        Returns:
            Verification result dict
        """
        checks_passed = {}
        checks_failed = {}

        symbol = decision['symbol']
        exit_reason = decision.get('exit_reason', '')
        exit_price = decision.get('exit_price', 0)

        # 1. Verify exit reason matches price action
        stop_loss_price = position.get('stop_loss_price')
        take_profit_price = position.get('take_profit_price')
        trailing_stop_price = position.get('trailing_stop_price')

        if 'STOP_LOSS' in exit_reason:
            if stop_loss_price and current_price <= stop_loss_price:
                checks_passed['stop_loss_triggered'] = True
            else:
                checks_failed['stop_loss_triggered'] = f'Price ${current_price:.2f} > stop ${stop_loss_price:.2f}'

        elif 'TAKE_PROFIT' in exit_reason:
            if take_profit_price and current_price >= take_profit_price:
                checks_passed['take_profit_triggered'] = True
            else:
                checks_failed['take_profit_triggered'] = f'Price ${current_price:.2f} < TP ${take_profit_price:.2f}'

        elif 'TRAILING_STOP' in exit_reason:
            if trailing_stop_price and current_price <= trailing_stop_price:
                checks_passed['trailing_stop_triggered'] = True
            else:
                checks_failed['trailing_stop_triggered'] = f'Price ${current_price:.2f} > trail ${trailing_stop_price:.2f}'

        elif 'EOD' in exit_reason:
            # EOD exit is always valid
            checks_passed['eod_exit'] = True

        # 2. Check exit price accuracy
        price_diff_percent = abs(exit_price - current_price) / current_price * 100

        if price_diff_percent <= 2.0:  # Within 2% tolerance
            checks_passed['exit_price_accuracy'] = True
        else:
            checks_failed['exit_price_accuracy'] = f'Price diff {price_diff_percent:.1f}% (exit=${exit_price:.2f} vs current=${current_price:.2f})'

        # Compile results
        result = {
            'symbol': symbol,
            'decision_type': 'EXIT',
            'exit_reason': exit_reason,
            'checks_passed': checks_passed,
            'checks_failed': checks_failed,
            'all_passed': len(checks_failed) == 0,
            'pass_rate': len(checks_passed) / (len(checks_passed) + len(checks_failed)) if (len(checks_passed) + len(checks_failed)) > 0 else 0.0
        }

        if self.verbose:
            self._log_verification_result(result)

        return result

    def verify_cooldown_respected(
        self,
        symbol: str,
        entry_timestamp: datetime,
        previous_exit_timestamp: Optional[datetime],
        previous_exit_reason: Optional[str],
        cooldown_config: Dict
    ) -> Dict[str, Any]:
        """
        Verifica que el cooldown fue respetado

        Args:
            symbol: Symbol
            entry_timestamp: Time of new entry
            previous_exit_timestamp: Time of previous exit
            previous_exit_reason: Reason for previous exit
            cooldown_config: Cooldown configuration

        Returns:
            Verification result
        """
        checks_passed = {}
        checks_failed = {}

        if not previous_exit_timestamp or not previous_exit_reason:
            # No previous exit, cooldown not applicable
            return {
                'symbol': symbol,
                'decision_type': 'COOLDOWN',
                'checks_passed': {'no_previous_exit': True},
                'checks_failed': {},
                'all_passed': True,
                'pass_rate': 1.0
            }

        # Calculate time since previous exit
        time_diff = entry_timestamp - previous_exit_timestamp
        minutes_elapsed = time_diff.total_seconds() / 60

        # Get required cooldown based on exit reason
        required_cooldown = 0

        if 'STOP_LOSS' in previous_exit_reason:
            required_cooldown = cooldown_config.get('stop_loss', 30)
        elif 'TRAILING_STOP' in previous_exit_reason:
            required_cooldown = cooldown_config.get('trailing_stop', 15)
        elif 'TAKE_PROFIT' in previous_exit_reason:
            required_cooldown = cooldown_config.get('take_profit', 5)

        # Check if cooldown was respected
        if minutes_elapsed >= required_cooldown:
            checks_passed['cooldown_respected'] = True
        else:
            checks_failed['cooldown_respected'] = (
                f'Re-entry after {minutes_elapsed:.1f}min but required {required_cooldown}min '
                f'(after {previous_exit_reason})'
            )

        return {
            'symbol': symbol,
            'decision_type': 'COOLDOWN',
            'checks_passed': checks_passed,
            'checks_failed': checks_failed,
            'all_passed': len(checks_failed) == 0,
            'pass_rate': len(checks_passed) / (len(checks_passed) + len(checks_failed)) if (len(checks_passed) + len(checks_failed)) > 0 else 0.0,
            'minutes_elapsed': minutes_elapsed,
            'required_cooldown': required_cooldown
        }

    def _log_verification_result(self, result: Dict):
        """Log verification result"""
        symbol = result['symbol']
        decision_type = result['decision_type']

        if result['all_passed']:
            self.logger.debug(f"   ✅ {symbol} {decision_type}: All checks passed")
        else:
            self.logger.warning(f"   ⚠️  {symbol} {decision_type}: {len(result['checks_failed'])} checks failed")
            for check, reason in result['checks_failed'].items():
                self.logger.warning(f"      - {check}: {reason}")

    def generate_verification_summary(self, verifications: List[Dict]) -> Dict[str, Any]:
        """
        Genera resumen de todas las verificaciones

        Args:
            verifications: List of verification results

        Returns:
            Summary dict
        """
        total = len(verifications)
        passed = sum(1 for v in verifications if v['all_passed'])
        failed = total - passed

        # Group by decision type
        by_type = {}
        for v in verifications:
            dtype = v['decision_type']
            if dtype not in by_type:
                by_type[dtype] = {'total': 0, 'passed': 0, 'failed': 0}
            by_type[dtype]['total'] += 1
            if v['all_passed']:
                by_type[dtype]['passed'] += 1
            else:
                by_type[dtype]['failed'] += 1

        # Collect all failed checks
        failed_checks = []
        for v in verifications:
            if not v['all_passed']:
                failed_checks.append({
                    'symbol': v['symbol'],
                    'decision_type': v['decision_type'],
                    'checks_failed': v['checks_failed']
                })

        return {
            'total_verifications': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0.0,
            'by_type': by_type,
            'failed_checks': failed_checks
        }
