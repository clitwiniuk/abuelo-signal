
import asyncio
import unittest
import logging
from datetime import datetime

from core.time_provider import SimulatedTimeProvider
from core.entry_competition import EntryCompetition

# Configure Logging
logging.basicConfig(level=logging.INFO)

class TestEntryCompetition(unittest.IsolatedAsyncioTestCase):
    async def test_competition_winner(self):
        """Verify the worker with highest pattern score wins"""
        clock = SimulatedTimeProvider()
        clock.set_time(datetime(2025, 1, 1, 10, 0, 0))
        
        comp = EntryCompetition(clock, competition_window_seconds=0.05)
        symbol = "TEST_SYM"
        
        # Simulate concurrent requests
        # Worker A: Score 80
        # Worker B: Score 90 (Should Win)
        # Worker C: Score 85
        
        async def worker_a():
            return comp.register_entry(symbol, "WorkerA", {"symbol": symbol}, 80.0)

        async def worker_b():
            return comp.register_entry(symbol, "WorkerB", {"symbol": symbol}, 90.0)

        async def worker_c():
            return comp.register_entry(symbol, "WorkerC", {"symbol": symbol}, 85.0)

        # Launch concurrently (note: register_entry is sync, but we wrap in async for testing)
        results = await asyncio.gather(worker_a(), worker_b(), worker_c())
        
        # Check results
        res_a, res_b, res_c = results
        
        print(f"Results: A={res_a}, B={res_b}, C={res_c}")
        
        self.assertEqual(res_a, 'LOSER')
        self.assertEqual(res_b, 'WINNER')
        self.assertEqual(res_c, 'LOSER')
        
    async def test_competition_tie_breaker(self):
        """Verify tie breaker works (alphabetical)"""
        clock = SimulatedTimeProvider()
        clock.set_time(datetime(2025, 1, 1, 10, 0, 0))
        
        comp = EntryCompetition(clock, competition_window_seconds=0.05)
        symbol = "TIE_SYM"
        
        # Worker X: Score 90
        # Worker Y: Score 90 
        # By our logic: max key is (score, strategy). 'WorkerY' > 'WorkerX'.
        # So WorkerY should win.
        
        async def worker_x():
            return comp.register_entry(symbol, "WorkerX", {"symbol": symbol}, 90.0)

        async def worker_y():
            return comp.register_entry(symbol, "WorkerY", {"symbol": symbol}, 90.0)
            
        results = await asyncio.gather(worker_x(), worker_y())
        res_x, res_y = results
        
        print(f"Tie Results: X={res_x}, Y={res_y}")
        
        self.assertEqual(res_x, 'LOSER')
        self.assertEqual(res_y, 'WINNER')

if __name__ == "__main__":
    unittest.main()
