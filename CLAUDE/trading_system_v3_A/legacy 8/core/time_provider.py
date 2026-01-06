from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

class TimeProvider(ABC):
    """Abstract base class for time providers."""
    
    @abstractmethod
    def now(self) -> datetime:
        """Get the current time."""
        pass

class SystemTimeProvider(TimeProvider):
    """Time provider that returns the system's current time."""
    
    def now(self) -> datetime:
        return datetime.now()

class SimulatedTimeProvider(TimeProvider):
    """Time provider that returns a simulated time."""
    
    def __init__(self, initial_time: Optional[datetime] = None):
        self._current_time = initial_time
    
    def now(self) -> datetime:
        if self._current_time is None:
            raise RuntimeError("Simulated time not set. Call set_time() before accessing time.")
        return self._current_time
    
    def set_time(self, timestamp: datetime):
        """Update the simulated time."""
        self._current_time = timestamp
