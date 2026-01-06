# core/events.py
"""
Event system implementation for decoupled communication between components.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Set
from datetime import datetime

from .interfaces import Event, EventHandler, EventBus

logger = logging.getLogger(__name__)


class AsyncEventBus(EventBus):
    """
    Asynchronous event bus implementation.
    Provides publish/subscribe pattern for system-wide communication.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Set[EventHandler]] = defaultdict(set)
        self._wildcard_handlers: Set[EventHandler] = set()
        self._lock = asyncio.Lock()
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers"""
        async with self._lock:
            handlers = self._handlers.get(event.event_type, set()).copy()
            wildcard_handlers = self._wildcard_handlers.copy()
        
        # Combine specific and wildcard handlers
        all_handlers = handlers | wildcard_handlers
        
        if not all_handlers:
            logger.debug(f"No handlers for event type: {event.event_type}")
            return
        
        # Execute handlers concurrently
        tasks = []
        for handler in all_handlers:
            task = asyncio.create_task(self._safe_handle(handler, event))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type"""
        if event_type == "*":
            self._wildcard_handlers.add(handler)
        else:
            self._handlers[event_type].add(handler)
        
        logger.debug(f"Handler {handler.__class__.__name__} subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from events"""
        if event_type == "*":
            self._wildcard_handlers.discard(handler)
        else:
            self._handlers[event_type].discard(handler)
        
        logger.debug(f"Handler {handler.__class__.__name__} unsubscribed from {event_type}")
    
    async def _safe_handle(self, handler: EventHandler, event: Event) -> None:
        """Safely execute handler with error handling"""
        try:
            await handler.handle(event)
        except Exception as e:
            logger.error(f"Error in event handler {handler.__class__.__name__}: {e}", exc_info=True)


# Event Types
class EventTypes:
    """Standard event types used throughout the system"""
    
    # Market data events
    BAR_RECEIVED = "bar_received"
    PRICE_UPDATE = "price_update"
    
    # Trading events
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    
    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    ERROR_OCCURRED = "error_occurred"
    
    # Strategy events
    STRATEGY_INITIALIZED = "strategy_initialized"
    STRATEGY_ERROR = "strategy_error"


# Predefined Events
def create_bar_event(bar_data: 'MarketData') -> Event:
    """Create a bar received event"""
    return Event(
        event_id="",
        event_type=EventTypes.BAR_RECEIVED,
        timestamp=datetime.now(),
        data={
            "symbol": bar_data.symbol,
            "bar": bar_data
        }
    )


def create_signal_event(signal: 'Signal') -> Event:
    """Create a signal generated event"""
    return Event(
        event_id="",
        event_type=EventTypes.SIGNAL_GENERATED,
        timestamp=datetime.now(),
        data={
            "signal": signal
        }
    )


def create_order_event(order: 'Order', event_type: str) -> Event:
    """Create an order-related event"""
    return Event(
        event_id="",
        event_type=event_type,
        timestamp=datetime.now(),
        data={
            "order": order
        }
    )


def create_position_event(position: 'Position', event_type: str) -> Event:
    """Create a position-related event"""
    return Event(
        event_id="",
        event_type=event_type,
        timestamp=datetime.now(),
        data={
            "position": position
        }
    )


def create_error_event(error: Exception, component: str) -> Event:
    """Create an error event"""
    return Event(
        event_id="",
        event_type=EventTypes.ERROR_OCCURRED,
        timestamp=datetime.now(),
        data={
            "error": str(error),
            "component": component,
            "error_type": type(error).__name__
        }
    )


# Base Event Handlers
class BaseEventHandler(EventHandler):
    """Base event handler with common functionality"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(self.name)
    
    async def handle(self, event: Event) -> None:
        """Base handle method with logging"""
        self.logger.debug(f"Handling event: {event.event_type}")
        await self.process_event(event)
    
    async def process_event(self, event: Event) -> None:
        """Override this method in subclasses"""
        pass


class LoggingEventHandler(BaseEventHandler):
    """Event handler that logs all events"""
    
    def __init__(self, log_level: int = logging.INFO):
        super().__init__("EventLogger")
        self.log_level = log_level
    
    async def process_event(self, event: Event) -> None:
        """Log the event"""
        self.logger.log(
            self.log_level,
            f"Event: {event.event_type} | Data: {event.data}"
        )


class ErrorEventHandler(BaseEventHandler):
    """Handler specifically for error events"""
    
    def __init__(self):
        super().__init__("ErrorHandler")
    
    async def process_event(self, event: Event) -> None:
        """Handle error events"""
        if event.event_type == EventTypes.ERROR_OCCURRED:
            error_data = event.data
            self.logger.error(
                f"System Error in {error_data.get('component', 'unknown')}: "
                f"{error_data.get('error', 'unknown error')}"
            )


# Event Decorators
def event_handler(event_type: str):
    """Decorator to mark methods as event handlers"""
    def decorator(func):
        func._event_type = event_type
        func._is_event_handler = True
        return func
    return decorator


class EventHandlerMixin:
    """Mixin to automatically register event handlers"""
    
    def __init__(self, event_bus: EventBus = None):
        self.event_bus = event_bus
        if event_bus:
            self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Automatically register methods marked with @event_handler"""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_is_event_handler'):
                event_type = attr._event_type
                handler = EventMethodHandler(attr)
                self.event_bus.subscribe(event_type, handler)


class EventMethodHandler(EventHandler):
    """Wrapper to use regular methods as event handlers"""
    
    def __init__(self, method):
        self.method = method
    
    async def handle(self, event: Event) -> None:
        if asyncio.iscoroutinefunction(self.method):
            await self.method(event)
        else:
            self.method(event)