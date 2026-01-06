"""
Strategy Switch Limiter - Circuit Breaker for Over-switching
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class StrategySwitch:
    timestamp: datetime
    from_strategy: str
    to_strategy: str
    confidence_difference: float
    reason: str

class StrategySwitchLimiter:
    def __init__(self, config=None):
        self.logger = logging.getLogger("StrategySwitchLimiter")
        self.max_switches_per_day = 3
        self.min_confidence_difference = 0.15
        self.cooldown_minutes = 15

        self.daily_switches: Dict[str, List[StrategySwitch]] = {}
        self.current_strategies: Dict[str, str] = {}
        self.last_switch_time: Dict[str, datetime] = {}

    def can_switch_strategy(self, symbol: str, from_strategy: str, to_strategy: str,
                           confidence_difference: float) -> tuple[bool, str]:
        if from_strategy == to_strategy:
            return False, "Same strategy"
        if confidence_difference < self.min_confidence_difference:
            return False, f"Confidence diff {confidence_difference:.2f} < {self.min_confidence_difference}"
        if not self._is_cooldown_expired(symbol):
            return False, "Cooldown active"
        if not self._is_under_daily_limit(symbol):
            return False, "Daily limit reached"
        return True, "Switch allowed"

    def record_strategy_switch(self, symbol: str, from_strategy: str, to_strategy: str,
                             confidence_difference: float, reason: str = ""):
        now = datetime.now()
        switch = StrategySwitch(now, from_strategy, to_strategy, confidence_difference, reason)

        key = f"{symbol}_{date.today().isoformat()}"
        if key not in self.daily_switches:
            self.daily_switches[key] = []
        self.daily_switches[key].append(switch)

        self.current_strategies[symbol] = to_strategy
        self.last_switch_time[symbol] = now

        self.logger.info(f"🔄 {symbol}: {from_strategy} → {to_strategy} (+{confidence_difference:.1%})")

    def set_initial_strategy(self, symbol: str, strategy: str):
        self.current_strategies[symbol] = strategy

    def get_current_strategy(self, symbol: str) -> Optional[str]:
        return self.current_strategies.get(symbol)

    def _is_under_daily_limit(self, symbol: str) -> bool:
        key = f"{symbol}_{date.today().isoformat()}"
        switches = self.daily_switches.get(key, [])
        return len(switches) < self.max_switches_per_day

    def _is_cooldown_expired(self, symbol: str) -> bool:
        if symbol not in self.last_switch_time:
            return True
        last = self.last_switch_time[symbol]
        return datetime.now() - last > timedelta(minutes=self.cooldown_minutes)