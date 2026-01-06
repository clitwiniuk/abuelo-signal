#!/usr/bin/env python3
"""
Structured Logging for Trading System
Emits JSON logs for Grafana Loki ingestion

Features:
- JSON structured logs with all relevant context
- Worker decision tracking
- Trade lifecycle logging
- Scanner event logging
- Execution event logging
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class LogEventType(Enum):
    """Types of events we log"""
    WORKER_DECISION = "worker_decision"
    SCANNER_OPPORTUNITY = "scanner_opportunity"
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    EXECUTION = "execution"
    CONTEXT_ANALYSIS = "context_analysis"
    SYSTEM = "system"


class DecisionType(Enum):
    """Worker decision types"""
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXITED = "EXITED"


class StructuredLogger:
    """
    Structured logger that emits JSON logs for Grafana Loki

    Usage:
        logger = StructuredLogger("buy_and_hold")
        logger.log_decision(
            symbol="AAPL",
            decision=DecisionType.REJECTED,
            reason="vwap_slope_too_flat",
            vwap_slope=0.00005,
            current_price=150.25
        )
    """

    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.logger = logging.getLogger(f"structured.{worker_name}")

    def _emit(self, event_type: LogEventType, data: Dict[str, Any]):
        """Emit structured JSON log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "worker": self.worker_name,
            "event_type": event_type.value,
            **data
        }

        # Emit as JSON string
        self.logger.info(json.dumps(log_entry))

    def log_decision(
        self,
        symbol: str,
        decision: DecisionType,
        reason: str,
        **context
    ):
        """
        Log a worker decision (ACCEPTED/REJECTED)

        Args:
            symbol: Stock symbol
            decision: DecisionType (ACCEPTED/REJECTED)
            reason: Reason for decision (e.g., "vwap_slope_too_flat")
            **context: Additional context (price, quality_score, vwap_slope, etc.)
        """
        self._emit(LogEventType.WORKER_DECISION, {
            "symbol": symbol,
            "decision": decision.value,
            "reason": reason,
            **context
        })

    def log_scanner_opportunity(
        self,
        symbol: str,
        catalyst: str,
        quality_score: float,
        **context
    ):
        """
        Log scanner opportunity received

        Args:
            symbol: Stock symbol
            catalyst: Catalyst type
            quality_score: Scanner quality score
            **context: Additional scanner data
        """
        self._emit(LogEventType.SCANNER_OPPORTUNITY, {
            "symbol": symbol,
            "catalyst": catalyst,
            "quality_score": quality_score,
            **context
        })

    def log_trade_entry(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        take_profit: float,
        **context
    ):
        """
        Log trade entry execution

        Args:
            symbol: Stock symbol
            entry_price: Entry price
            quantity: Quantity entered
            stop_loss: Stop loss price
            take_profit: Take profit price
            **context: Additional entry data
        """
        self._emit(LogEventType.TRADE_ENTRY, {
            "symbol": symbol,
            "entry_price": entry_price,
            "quantity": quantity,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            **context
        })

    def log_trade_exit(
        self,
        symbol: str,
        exit_price: float,
        quantity: int,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        **context
    ):
        """
        Log trade exit execution

        Args:
            symbol: Stock symbol
            exit_price: Exit price
            quantity: Quantity exited
            pnl: PnL in dollars
            pnl_pct: PnL in percentage
            exit_reason: Reason for exit
            **context: Additional exit data
        """
        self._emit(LogEventType.TRADE_EXIT, {
            "symbol": symbol,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": exit_reason,
            **context
        })

    def log_context_analysis(
        self,
        symbol: str,
        market_context: str,
        confidence: float,
        **metrics
    ):
        """
        Log market context analysis

        Args:
            symbol: Stock symbol
            market_context: Detected context (TREND/MOMENTUM/etc)
            confidence: Context confidence score
            **metrics: ADX, ATR, volume_zscore, etc.
        """
        self._emit(LogEventType.CONTEXT_ANALYSIS, {
            "symbol": symbol,
            "market_context": market_context,
            "confidence": confidence,
            **metrics
        })

    def log_execution(
        self,
        symbol: str,
        action: str,
        status: str,
        **details
    ):
        """
        Log execution event (order sent, filled, rejected)

        Args:
            symbol: Stock symbol
            action: BUY/SELL
            status: SENT/FILLED/REJECTED/CANCELLED
            **details: Order details
        """
        self._emit(LogEventType.EXECUTION, {
            "symbol": symbol,
            "action": action,
            "status": status,
            **details
        })

    def log_system(
        self,
        component: str,
        event: str,
        **details
    ):
        """
        Log system event

        Args:
            component: Component name (scanner, broker, etc)
            event: Event type
            **details: Event details
        """
        self._emit(LogEventType.SYSTEM, {
            "component": component,
            "event": event,
            **details
        })


def configure_structured_logging(log_file: str = "logs/structured.log"):
    """
    Configure structured logging to output to file in JSON format

    Args:
        log_file: Path to structured log file
    """
    # Create structured logger
    structured_logger = logging.getLogger("structured")
    structured_logger.setLevel(logging.INFO)
    structured_logger.propagate = False  # Don't propagate to root logger

    # File handler for JSON logs
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.INFO)

    # No formatter - we emit raw JSON
    handler.setFormatter(logging.Formatter('%(message)s'))

    structured_logger.addHandler(handler)

    return structured_logger
