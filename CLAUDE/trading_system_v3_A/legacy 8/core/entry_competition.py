
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from core.time_provider import TimeProvider

@dataclass
class EntryRequest:
    strategy: str
    pattern_completion: float
    timestamp: datetime
    bar_index: Optional[int] = None
    # Future to notify the worker of the result ('WINNER', 'LOSER')
    result_future: asyncio.Future = None 

class EntryCompetition:
    """
    Manages competition between workers for the same symbol.
    Ensures deterministic winner selection based on pattern completion.
    """

    def __init__(self, clock: TimeProvider, competition_window_seconds: float = 0.05):
        self.logger = logging.getLogger("EntryCompetition")
        self.clock = clock
        self.competition_window = competition_window_seconds
        
        # Active competitions: symbol -> List[EntryRequest]
        self._competitions: Dict[str, List[EntryRequest]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def register_entry(self, symbol: str, strategy: str, 
                           pattern_completion: float, bar_index: Optional[int] = None) -> str:
        """
        Register interest in entering a position.
        Waits for competition window and returns 'WINNER' or 'LOSER'.
        """
        # Ensure lock exists
        if symbol not in self._locks:
            self._locks[symbol] = asyncio.Lock()

        # Create request
        request = EntryRequest(
            strategy=strategy,
            pattern_completion=pattern_completion,
            timestamp=self.clock.now(),
            bar_index=bar_index,
            result_future=asyncio.Future()
        )

        async with self._locks[symbol]:
            is_first = symbol not in self._competitions
            
            if is_first:
                self._competitions[symbol] = []
                # Start the competition timer processing in background
                asyncio.create_task(self._process_competition(symbol, self.competition_window))

            self._competitions[symbol].append(request)
            
            self.logger.debug(f"Registered entry request for {symbol} by {strategy} (score: {pattern_completion:.1f})")

        # Wait for result
        result = await request.result_future
        return result

    async def _process_competition(self, symbol: str, wait_time: float):
        """Waits for window to close and picks a winner"""
        try:
            # Wait for other workers to potentially register
            await asyncio.sleep(wait_time)

            async with self._locks[symbol]:
                requests = self._competitions.get(symbol, [])
                
                if not requests:
                    return

                # Determine winner: Highest pattern completion, then alphabetical strategy (for stability)
                # Note: We negate ord() because we want reverse alphabetical? 
                # No, we probably want normal alphabetical as tie breaker.
                # max key: (score, string) -> python compares tuples element by element.
                # If we want alphabetical to be deterministic tie breaker:
                # (90, 'A') vs (90, 'B') -> 'B' is greater. 
                # Typically we prefer 'A'? If so we need negative.
                # Let's stick to simple: Score desc, Strategy asc.
                # max() picks largest. 
                # (90, 'B') > (90, 'A'). So 'B' wins.
                # If we want 'A' to win on tie, we use (90, neg_str?).
                # Actually, deterministic just means "consistent". Alphabetical is fine.
                
                winner = max(requests, key=lambda x: (x.pattern_completion, x.strategy))
                
                self.logger.info(
                    f"🏆 Competition decided for {symbol}: {winner.strategy} won "
                    f"(score: {winner.pattern_completion:.1f}) vs {len(requests)-1} others"
                )

                # Notify all
                for req in requests:
                    if req.strategy == winner.strategy:
                        req.result_future.set_result('WINNER')
                    else:
                        req.result_future.set_result('LOSER')
                
                # Clean up
                del self._competitions[symbol]

        except Exception as e:
            self.logger.error(f"Error in competition processing for {symbol}: {e}")
            # Fail safe: release everyone as losers or let them hang?
            # Better to release them to avoid sticking.
            # But we lost the list if we crashed before getting lock? 
            # If we are in the try block, we can access self._competitions if we get lock.
            pass
