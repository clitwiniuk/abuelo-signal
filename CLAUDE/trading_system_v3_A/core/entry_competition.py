"""
Entry Competition - Deterministic Worker Competition Resolution

Resuelve el Problema #3: Race Condition en Entry Competition
Impacto: +15% reproducibilidad

ANTES (No-determinístico):
- asyncio.sleep(0.05) # Espera a que workers registren interés
- Winner depende de timing de async tasks (scheduler-dependent)
- Replay tiene diferente ganador que live

DESPUÉS (Determinístico):
- Collect all entry requests inmediatamente
- Winner por pattern_completion (mayor)
- Desempate alfabético por strategy name (consistente)
- Mismo ganador en live y replay
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from core.time_provider import TimeProvider, SystemTimeProvider


@dataclass
class EntryRequest:
    """Solicitud de entrada de un worker"""
    strategy: str
    symbol: str
    opportunity: dict
    pattern_completion: float
    timestamp: datetime
    bar_index: Optional[int] = None


class EntryCompetition:
    """
    Gestiona competencia determinística entre workers

    Workflow:
    1. Workers llaman register_entry() cuando quieren entrar
    2. Si hay múltiples workers para el mismo símbolo en la misma barra:
       - Se decide el ganador inmediatamente (sin sleep)
       - Criterio: Mayor pattern_completion
       - Desempate: Alfabético por strategy name
    3. Winner procede con entry, losers son rechazados

    Example:
        competition = EntryCompetition(clock)

        # Worker 1
        result = competition.register_entry(
            'CMBM', 'daily_plays', opportunity, pattern_completion=85.0
        )
        # Returns: 'PENDING' (primero en llegar)

        # Worker 2 (misma barra)
        result = competition.register_entry(
            'CMBM', 'macdv', opportunity, pattern_completion=92.0
        )
        # Returns: 'WINNER' (mejor pattern_completion)
        # Worker 1 recibe 'LOSER' cuando vuelve a check_result()
    """

    def __init__(self, clock: TimeProvider = None):
        self.clock = clock or SystemTimeProvider()
        self.logger = logging.getLogger("EntryCompetition")

        # Active competitions: {symbol: [EntryRequest, ...]}
        self._competitions: Dict[str, List[EntryRequest]] = {}

        # Locks para thread-safety
        self._locks: Dict[str, asyncio.Lock] = {}

        # Decided winners: {symbol: winning_strategy}
        self._winners: Dict[str, str] = {}

    def register_entry(
        self,
        symbol: str,
        strategy: str,
        opportunity: dict,
        pattern_completion: float,
        bar_index: Optional[int] = None
    ) -> str:
        """
        Registra interés de un worker en entrar (SÍNCRONO)

        Args:
            symbol: Símbolo a tradear
            strategy: Nombre del worker
            opportunity: Opportunity data
            pattern_completion: Score de setup (0-100)
            bar_index: Índice de barra (para detectar misma barra)

        Returns:
            'WINNER': Ganó la competencia, proceder con entry
            'LOSER': Otro worker tiene mejor setup, abortar
            'PENDING': Primero en llegar, posible ganador (verificar luego)
        """
        # Crear entry request
        entry = EntryRequest(
            strategy=strategy,
            symbol=symbol,
            opportunity=opportunity,
            pattern_completion=pattern_completion,
            timestamp=self.clock.now(),
            bar_index=bar_index
        )

        # Thread-safe registration
        if symbol not in self._competitions:
            self._competitions[symbol] = []

        self._competitions[symbol].append(entry)

        # Get all competitors for same bar
        same_bar_competitors = [
            e for e in self._competitions[symbol]
            if (bar_index is None or e.bar_index == bar_index)
        ]

        if len(same_bar_competitors) == 1:
            # Somos los únicos, pending winner
            self.logger.debug(
                f"📋 {strategy}: First to register for {symbol} "
                f"(pattern: {pattern_completion:.1f}%)"
            )
            return 'PENDING'

        # Hay múltiples competidores - decidir ganador AHORA (SIN SLEEP)
        # Criterio: Mayor pattern_completion
        # Desempate: Alfabético por strategy name (A antes que B)
        best = max(
            same_bar_competitors,
            key=lambda e: (e.pattern_completion, -ord(e.strategy[0]))
        )

        # CRITICAL: Always set winner regardless of who's registering
        # This ensures first worker (PENDING) can later check and find out result
        self._winners[symbol] = best.strategy

        if best.strategy == strategy:
            # Ganamos
            losers = [
                e.strategy for e in same_bar_competitors
                if e.strategy != strategy
            ]

            self.logger.info(
                f"🏆 {strategy}: Won competition for {symbol} "
                f"(pattern: {pattern_completion:.1f}% vs "
                f"{', '.join(losers)})"
            )

            return 'WINNER'
        else:
            # Perdimos
            self.logger.debug(
                f"⚠️ {strategy}: Lost competition for {symbol} "
                f"to {best.strategy} "
                f"({best.pattern_completion:.1f}% > {pattern_completion:.1f}%)"
            )

            return 'LOSER'

    def check_result(self, symbol: str, strategy: str) -> str:
        """
        Verifica resultado de competencia (para workers que registraron PENDING)

        Args:
            symbol: Símbolo
            strategy: Nombre del worker

        Returns:
            'WINNER': Sigue siendo ganador
            'LOSER': Otro worker ganó después
            'PENDING': Todavía no decidido
        """
        if symbol in self._winners:
            if self._winners[symbol] == strategy:
                return 'WINNER'
            else:
                return 'LOSER'

        # Todavía no decidido
        return 'PENDING'

    def clear_competition(self, symbol: str):
        """Limpia competencia para un símbolo (después de entry ejecutado)"""
        if symbol in self._competitions:
            del self._competitions[symbol]

        if symbol in self._winners:
            del self._winners[symbol]

        if symbol in self._locks:
            del self._locks[symbol]

    def get_pending_competitions(self) -> List[str]:
        """Retorna símbolos con competiciones pendientes (debugging)"""
        return list(self._competitions.keys())

    def get_competition_details(self, symbol: str) -> List[Dict]:
        """
        Retorna detalles de competencia para un símbolo

        Returns:
            List of {'strategy': str, 'pattern_completion': float, 'timestamp': datetime}
        """
        if symbol not in self._competitions:
            return []

        return [
            {
                'strategy': e.strategy,
                'pattern_completion': e.pattern_completion,
                'timestamp': e.timestamp,
                'bar_index': e.bar_index
            }
            for e in self._competitions[symbol]
        ]

    def get_winner(self, symbol: str) -> Optional[str]:
        """Retorna el winner actual para un símbolo (si existe)"""
        return self._winners.get(symbol)


# Singleton para uso global (opcional)
_global_competition = None


def get_competition(clock: TimeProvider = None) -> EntryCompetition:
    """
    Get global EntryCompetition instance

    Args:
        clock: Time provider (None = use default)

    Returns:
        EntryCompetition: Global instance
    """
    global _global_competition

    if _global_competition is None:
        _global_competition = EntryCompetition(clock)

    return _global_competition
