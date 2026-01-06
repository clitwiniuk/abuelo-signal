#!/usr/bin/env python3
"""
Independent Scanner Process
Finds opportunities and publishes them via Redis pub/sub to trader
"""

import asyncio
import logging
import signal
import sys
import os
from typing import List, Dict, Any
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import get_config
from core.scanner_trader_bridge import ScannerTraderBridge
from adapters.ibkr_adapter import IBKRAdapter
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from scanner.smallcap.proactive_scanner import ProactiveScanner
from scanner.midcap.midcap_daily_scanner import MidCapDailyScanner
from scanner.daily_bounce.daily_bounce_scanner import DailyBounceScanner
from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner
from scanner.opportunity_tracker import OpportunityTracker
from utils.log_config import setup_logging

# ENHANCEMENT: Import pattern classifiers for advanced opportunity enrichment
from core.ods_classifier import ODSClassifier
from core.intraday_structure_classifier import IntradayStructureClassifier
from core.parabolic_extension_detector import ParabolicExtensionDetector


# ============================================================================
# ENHANCEMENT: Scanner Helper Functions
# ============================================================================

class BarWrapper:
    """
    Wrapper to convert bar dicts to objects with attributes
    Bars from scanner are dicts, but helper functions expect objects
    """
    def __init__(self, bar_dict):
        self.timestamp = bar_dict.get('timestamp')
        self.open = bar_dict.get('open', 0.0)
        self.high = bar_dict.get('high', 0.0)
        self.low = bar_dict.get('low', 0.0)
        self.close = bar_dict.get('close', 0.0)
        self.volume = bar_dict.get('volume', 0)

def calculate_atr(bars, period=14):
    """
    Calculate Average True Range (ATR) as percentage of price

    Args:
        bars: List of bar dicts or objects with high, low, close
        period: ATR period (default 14)

    Returns:
        float: ATR as percentage of current price
    """
    if not bars or len(bars) < period + 1:
        return 0.0

    try:
        # Wrap bars if they are dicts
        wrapped_bars = []
        for bar in bars:
            if isinstance(bar, dict):
                wrapped_bars.append(BarWrapper(bar))
            else:
                wrapped_bars.append(bar)

        true_ranges = []
        for i in range(1, len(wrapped_bars)):
            high_low = wrapped_bars[i].high - wrapped_bars[i].low
            high_close = abs(wrapped_bars[i].high - wrapped_bars[i-1].close)
            low_close = abs(wrapped_bars[i].low - wrapped_bars[i-1].close)
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)

        if len(true_ranges) < period:
            return 0.0

        # Average of last 'period' true ranges
        atr = sum(true_ranges[-period:]) / period

        # Convert to percentage of current price
        current_price = wrapped_bars[-1].close if wrapped_bars[-1].close > 0 else wrapped_bars[-1].high
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0.0

        return round(atr_pct, 2)

    except Exception as e:
        logging.getLogger("Scanner").error(f"Error calculating ATR: {e}")
        return 0.0


def extract_orb_data(bars_1min):
    """
    Extract ORB (Opening Range Breakout) specific data from bars
    ORB = 9:30-10:00 AM range (30 minutes)

    Args:
        bars_1min: List of 1-minute bar dicts or objects

    Returns:
        dict: ORB data or None if insufficient bars
    """
    from datetime import time, datetime as dt

    if not bars_1min or len(bars_1min) < 20:
        return None

    try:
        # Wrap bars if they are dicts
        wrapped_bars = []
        for bar in bars_1min:
            if isinstance(bar, dict):
                wrapped_bars.append(BarWrapper(bar))
            else:
                wrapped_bars.append(bar)

        orb_start = time(9, 30)
        orb_end = time(10, 0)

        orb_bars = []
        for bar in wrapped_bars:
            # Handle both datetime and time objects, and string timestamps
            if isinstance(bar.timestamp, str):
                try:
                    # Parse ISO format timestamp
                    bar_dt = dt.fromisoformat(bar.timestamp.replace('Z', '+00:00'))
                    bar_time = bar_dt.time()
                except:
                    continue
            elif hasattr(bar.timestamp, 'time'):
                bar_time = bar.timestamp.time()
            else:
                bar_time = bar.timestamp

            if orb_start <= bar_time < orb_end:
                orb_bars.append(bar)

        if len(orb_bars) < 20:  # Need at least 20/30 bars for valid ORB
            return None

        # Calculate ORB range
        orb_high = max(b.high for b in orb_bars)
        orb_low = min(b.low for b in orb_bars)
        orb_range_pct = ((orb_high - orb_low) / orb_low * 100) if orb_low > 0 else 0.0

        # Determine current price position vs ORB
        current_price = wrapped_bars[-1].close
        if current_price > orb_high:
            position = 'ABOVE_HIGH'
        elif current_price < orb_low:
            position = 'BELOW_LOW'
        else:
            position = 'INSIDE_RANGE'

        # Calculate average volume during ORB
        orb_avg_volume = sum(b.volume for b in orb_bars) / len(orb_bars)

        return {
            'orb_high': round(orb_high, 2),
            'orb_low': round(orb_low, 2),
            'orb_range_pct': round(orb_range_pct, 2),
            'orb_bar_count': len(orb_bars),
            'current_vs_orb': position,
            'orb_avg_volume': int(orb_avg_volume)
        }

    except Exception as e:
        logging.getLogger("Scanner").error(f"Error extracting ORB data: {e}")
        return None


def calculate_enhanced_quality_score(base_score, ods_data, structure_data, atr_pct):
    """
    Enhanced quality score considering pattern alignment and volatility

    Scoring adjustments:
    - ODS STRONG_BULLISH: +10
    - ODS MODERATE_BULLISH: +5
    - Intraday continuation pattern: +5
    - Liquidity sweep detected: +5
    - Low volatility (ATR < 5%): +5

    Args:
        base_score: Original quality score from scanner
        ods_data: ODS classification data (dict or None)
        structure_data: Intraday structure data (dict or None)
        atr_pct: ATR as percentage

    Returns:
        float: Enhanced quality score (0-100)
    """
    enhanced_score = base_score

    try:
        # ODS pattern bonus (based on day_type and strength)
        if ods_data:
            classification = ods_data.get('classification', '')
            strength = ods_data.get('strength', 0)

            # TREND_DRIVE_BULLISH with high strength = strong bullish
            if classification == 'TREND_DRIVE_BULLISH':
                if strength >= 70:
                    enhanced_score += 10  # Strong bullish
                elif strength >= 50:
                    enhanced_score += 5   # Moderate bullish

        # Intraday structure pattern bonus
        if structure_data:
            # Continuation pattern bonus
            continuation_type = structure_data.get('continuation_type', '')
            if continuation_type in ['PULLBACK_TO_VWAP', 'HIGHER_LOW', 'FLAG']:
                enhanced_score += 5

            # Liquidity sweep bonus (strong bullish signal)
            if structure_data.get('liquidity_sweep_detected', False):
                sweep_direction = structure_data.get('sweep_direction', '')
                if sweep_direction == 'BULLISH_RECLAIM':
                    enhanced_score += 5

        # Low volatility bonus (more predictable price action)
        if atr_pct > 0 and atr_pct < 5.0:
            enhanced_score += 5

        # Cap at 100
        return min(enhanced_score, 100.0)

    except Exception as e:
        logging.getLogger("Scanner").error(f"Error calculating enhanced quality score: {e}")
        return base_score


# ============================================================================
# Scanner Class
# ============================================================================

class IndependentScanner:
    """
    Independent scanner process - runs separately from trader
    """
    
    def __init__(self):
        setup_logging(level="INFO", log_file="logs/scanner.log")
        self.logger = logging.getLogger("Scanner")

        # Load config
        self.config = get_config()

        # Scanner components
        self.scanner_ibkr = None
        self.scanner = None
        self.midcap_scanner = None  # NEW: MidCap scanner
        self.daily_bounce_scanner = None
        self.red_to_green_scanner = None
        self.bridge = ScannerTraderBridge()

        # ENHANCEMENT: Pattern classifiers for opportunity enrichment
        self.ods_classifier = ODSClassifier()
        self.structure_classifier = IntradayStructureClassifier()
        self.parabolic_detector = ParabolicExtensionDetector()
        # Inject ODS classifier into structure classifier for enhanced analysis
        self.structure_classifier.set_ods_classifier(self.ods_classifier)
        self.logger.info("✅ Pattern classifiers initialized (ODS + Intraday Structure + Parabolic Extension)")

        # Scheduling control for daily vs intraday scanning
        self.last_daily_scan = None
        self.daily_scan_hour = 6  # 6 AM daily scan time
        self.last_proactive_scan_date = None  # Track proactive scan execution

        # Control
        self.is_running = False
        self.shutdown_requested = False

        # STREAMING MODE: Deduplication cache (symbol -> last_sent_timestamp)
        self.sent_opportunities = {}  # Track when each symbol was last sent

        # SMART UPDATE SYSTEM: Opportunity tracker for intelligent deduplication
        # SAFETY: Can be disabled by setting ENABLE_SMART_UPDATES=False in config
        self.enable_smart_updates = getattr(self.config, 'enable_smart_updates', True)
        
        if self.enable_smart_updates:
            self.opportunity_tracker = OpportunityTracker(
                catalyst_threshold=0.3,  # 30% sentiment change
                volume_threshold=0.5,    # 50% volume increase
                price_threshold=0.05,    # 5% price change
                quality_threshold=15.0,  # 15 point quality improvement
                refresh_interval_minutes=30  # Re-send after 30 min
            )
            self.logger.info("✅ OpportunityTracker initialized (SMART UPDATES ENABLED)")
        else:
            self.opportunity_tracker = None
            self.logger.warning("⚠️ Smart Update System DISABLED - all opportunities will be sent")

        # Load streaming config from config.ini
        self.streaming_enabled = getattr(self.config, 'enable_scanner_streaming', True)
        self.stream_cooldown = getattr(self.config, 'stream_cooldown_seconds', 60)
        self.stream_price_drift = getattr(self.config, 'stream_price_drift_threshold', 0.02)

        mode_str = "ENABLED" if self.streaming_enabled else "DISABLED"
        self.logger.info(f"🔍 Independent Scanner Process initialized (STREAMING MODE {mode_str})")
        
    async def initialize(self):
        """Initialize scanner with separate IBKR connection"""
        try:
            # Connect to Redis bridge
            bridge_connected = await self.bridge.connect()
            if not bridge_connected:
                self.logger.error("❌ Redis connection failed - scanner cannot publish opportunities")
                return False
            
            # Create separate IBKR connection for scanner
            scanner_client_id = self.config.client_id + 100  # Use significantly different client_id (6120)
            self.scanner_ibkr = IBKRAdapter(
                host=self.config.host,
                port=self.config.port,
                client_id=scanner_client_id
            )
            
            await self.scanner_ibkr.connect()
            self.logger.info(f"✅ Scanner IBKR connected (client_id: {scanner_client_id})")
            
            # Initialize intraday scanner with its own IBKR connection
            self.scanner = SmallcapDailyScanner(ibkr_adapter=self.scanner_ibkr)
            self.logger.info("✅ SmallcapDailyScanner (intraday) initialized")

            # Initialize MidCap scanner (shares same IBKR connection)
            self.midcap_scanner = MidCapDailyScanner(ibkr_adapter=self.scanner_ibkr)
            self.logger.info("✅ MidCapDailyScanner (event-driven) initialized")

            # Initialize daily bounce scanner (shares same IBKR connection)
            self.daily_bounce_scanner = DailyBounceScanner(ibkr_adapter=self.scanner_ibkr, logger=self.logger)
            self.logger.info("✅ DailyBounceScanner initialized")

            # Initialize red to green scanner (shares same IBKR connection)
            self.red_to_green_scanner = RedToGreenScanner(ibkr_adapter=self.scanner_ibkr, logger=self.logger)
            self.logger.info("✅ RedToGreenScanner initialized")

            # Initialize Short Squeeze Scanner (New)
            from scanner.swing.short_squeeze_scanner import ShortSqueezeScanner
            self.short_squeeze_scanner = ShortSqueezeScanner(ibkr_adapter=self.scanner_ibkr, logger=self.logger)
            self.logger.info("✅ ShortSqueezeScanner initialized")

            # Initialize Proactive Scanner (The Day 0 Detector)
            # CRITICAL: ProactiveScanner needs ConfigParser, not UnifiedConfig
            import configparser
            config_parser = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
            config_parser.read(config_path)
            self.proactive_scanner = ProactiveScanner(ibkr_adapter=self.scanner_ibkr, config=config_parser)
            self.logger.info("✅ ProactiveScanner initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Scanner initialization failed: {e}")
            return False
    
    async def start(self):
        """Start independent scanner loop"""
        if not await self.initialize():
            return False
            
        self.logger.info("🚀 Starting independent scanner process...")
        self.is_running = True
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info(f"📡 Signal {signum} received - shutting down scanner")
            self.logger.debug(f"🔍 DEBUG: Signal source: {frame.f_code.co_filename}:{frame.f_lineno}")
            import traceback
            traceback.print_stack(frame)
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main scanner loop
        while self.is_running and not self.shutdown_requested:
            try:
                self.logger.info("🔍 Starting scan cycle...")
                self.logger.debug(f"🔍 DEBUG: Loop conditions - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

                # Find opportunities (both intraday and daily)
                opportunities = await self._scan_for_opportunities()

                if opportunities:
                    # Publish to Redis for trader
                    await self.bridge.publish_opportunities(opportunities)
                    self.logger.info(f"📡 Published {len(opportunities)} opportunities to trader")
                else:
                    self.logger.info("📭 No opportunities found in this cycle")

                # OPTIMIZATION: Price streaming - reduce scan interval when optimizations are active
                # With parallel fetching + cache incremental, we can scan every 15 seconds instead of 30
                base_scan_interval = getattr(self.config, 'scan_interval_seconds', 30)
                # RELAXED: Use full base interval to avoid TWS overload (Error 162)
                # Previously halved to 15s, restored to config default (30s)
                scan_interval = max(20, base_scan_interval)  

                self.logger.info(f"⏱️ Waiting {scan_interval}s until next scan (config: {base_scan_interval}s)")
                self.logger.debug(f"🔍 DEBUG: About to sleep for {scan_interval}s - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")
                await asyncio.sleep(scan_interval)
                self.logger.debug(f"🔍 DEBUG: Woke up from sleep - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

            except asyncio.CancelledError:
                self.logger.debug("🔍 DEBUG: Scanner task was cancelled - likely shutdown")
                self.shutdown_requested = True
                break
            except Exception as e:
                self.logger.error(f"❌ Error in scanner cycle: {e}")
                import traceback
                self.logger.error(f"🔍 Exception traceback: {traceback.format_exc()}")
                await asyncio.sleep(30)  # Emergency wait

        # DEBUG: Why did we exit the loop?
        self.logger.debug(f"🔍 DEBUG: Exited scanner loop - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

        await self.stop()
        self.logger.info("🛑 Scanner process stopped")
        return True
    
    async def _stream_opportunity_if_new(self, opportunity: Dict[str, Any]):
        """
        STREAMING MODE: Send opportunity immediately if it's new or price changed significantly

        Deduplication logic:
        - Don't resend same symbol within cooldown period (configurable, default 60s)
        - Send immediately if price changed > threshold (configurable, default 2%)
        """
        # Skip if streaming is disabled
        if not self.streaming_enabled:
            return

        symbol = opportunity['symbol']
        current_price = opportunity['current_price']
        current_time = datetime.now().timestamp()

        # Check if we sent this symbol recently
        if symbol in self.sent_opportunities:
            last_sent_time, last_sent_price = self.sent_opportunities[symbol]

            # Calculate price drift
            price_drift = abs(current_price - last_sent_price) / last_sent_price if last_sent_price > 0 else 0

            # Skip if within cooldown AND price didn't move significantly
            if (current_time - last_sent_time) < self.stream_cooldown and price_drift < self.stream_price_drift:
                self.logger.debug(f"⏭️ STREAM: Skipping {symbol} (sent {int(current_time - last_sent_time)}s ago, drift={price_drift:.2%})")
                return

        # Check with OpportunityTracker if we should send (if enabled)
        if self.enable_smart_updates and self.opportunity_tracker:
            should_send, update_reason = self.opportunity_tracker.should_rescan(symbol, opportunity)
            
            if not should_send:
                self.logger.debug(f"⏭️ TRACKER: Skipping {symbol} - no material changes ({update_reason})")
                return
            
            # Enrich with update metadata if this is a re-send
            if update_reason != "FIRST_SCAN":
                opportunity['is_update'] = True
                opportunity['update_reason'] = update_reason
                opportunity['changes'] = self.opportunity_tracker.get_changes(symbol, opportunity)
                self.logger.info(f"🔄 UPDATE: {symbol} - {update_reason}")
        
        # NEW OPPORTUNITY or significant change - send immediately
        try:
            await self.bridge.publish_opportunities([opportunity])
            
            # Track if smart updates enabled
            if self.enable_smart_updates and self.opportunity_tracker:
                self.opportunity_tracker.track_opportunity(symbol, opportunity)
            
            self.sent_opportunities[symbol] = (current_time, current_price)
            
            if self.enable_smart_updates and update_reason != "FIRST_SCAN":
                self.logger.info(f"⚡ UPDATE: Sent {symbol} @ ${current_price:.2f} ({update_reason}, Q={opportunity['quality_score']:.1f})")
            else:
                self.logger.info(f"⚡ NEW: Sent {symbol} @ ${current_price:.2f} (Q={opportunity['quality_score']:.1f})")
        except Exception as e:
            self.logger.error(f"❌ STREAM: Failed to send {symbol}: {e}")

    async def _scan_for_opportunities(self) -> List[Dict[str, Any]]:
        """Scan for opportunities using UNIFIED scanner (intraday + daily)"""
        try:
            all_opportunities = []

            # 1. INTRADAY SCANNING (every cycle) - OPTIMIZED with parallel fetching
            self.logger.info("🔍 OPTIMIZED: Starting intraday IBKR scanning (parallel news + bars)...")
            intraday_plays = await self.scanner.scan_daily_plays()

            if intraday_plays:
                self.logger.info(f"📊 Intraday scanner found {len(intraday_plays)} plays")

            # 1.5 MIDCAP SCANNING (event-driven, adaptive) - NEW
            midcap_plays = []
            if self.midcap_scanner:
                self.logger.info("🏢 Starting MidCap event-driven scanning...")
                midcap_plays = await self.midcap_scanner.scan_daily_plays()

                if midcap_plays:
                    self.logger.info(f"📊 MidCap scanner found {len(midcap_plays)} plays")

                # Convert to opportunities with ENHANCED data for trader
                for play in intraday_plays:
                    # Get additional data from context
                    market_cap = getattr(play.context, 'market_cap', 0.0) if hasattr(play.context, 'market_cap') else 0.0
                    float_size = getattr(play.context, 'float_size', 0.0) if hasattr(play.context, 'float_size') else 0.0
                    avg_volume = getattr(play.context, 'avg_daily_volume', 0) if hasattr(play.context, 'avg_daily_volume') else 0

                    # Calculate risk management data
                    current_price = play.context.current_price if hasattr(play.context, 'current_price') else 0.0
                    suggested_stop_loss = current_price * 0.97 if current_price > 0 else 0.0  # 3% stop
                    suggested_take_profit = current_price * 1.06 if current_price > 0 else 0.0  # 6% target

                    # Calculate position size (basic - trader will refine)
                    account_balance = 10000  # Default assumption, trader will override
                    risk_per_trade = 0.02  # 2% risk per trade
                    risk_amount = account_balance * risk_per_trade
                    stop_distance = abs(current_price - suggested_stop_loss)
                    suggested_position_size = int(risk_amount / stop_distance) if stop_distance > 0 else 100

                    # ================================================================
                    # ENHANCEMENT 1: Calculate ATR
                    # ================================================================
                    bars_1min = play.bars_1min if hasattr(play, 'bars_1min') and play.bars_1min else []
                    atr_percent = calculate_atr(bars_1min, period=14) if bars_1min else 0.0

                    # ================================================================
                    # ENHANCEMENT 2: ODS Classification
                    # ================================================================
                    ods_data = None
                    if bars_1min and len(bars_1min) >= 12:
                        try:
                            # Call async method properly
                            ods_result = await self.ods_classifier.classify_symbol_ods(
                                symbol=play.symbol,
                                bars=bars_1min,  # Pass all bars, classifier will filter
                                premarket_data=None
                            )
                            if ods_result and ods_result.day_type.value not in ['PENDING', 'INSUFFICIENT_DATA']:
                                ods_data = {
                                    'day_type': ods_result.day_type.value if hasattr(ods_result.day_type, 'value') else str(ods_result.day_type),
                                    'classification': ods_result.day_type.value,  # Use day_type as classification
                                    'strength': ods_result.strength,
                                    'direction': ods_result.direction,
                                    'upside_move_pct': ods_result.upside_move_pct,
                                    'downside_move_pct': ods_result.downside_move_pct,
                                    'range_pct': ods_result.range_pct,
                                    'volume_ratio': ods_result.volume_ratio
                                }
                                self.logger.debug(f"📊 {play.symbol}: ODS={ods_result.day_type.value} (strength={ods_result.strength:.1f})")
                        except Exception as e:
                            self.logger.warning(f"⚠️ {play.symbol}: ODS classification failed: {e}")

                    # ================================================================
                    # ENHANCEMENT 3: Intraday Structure Classification
                    # ================================================================
                    structure_data = None
                    if bars_1min and len(bars_1min) >= 30:
                        try:
                            # Call async method properly
                            structure_result = await self.structure_classifier.classify_symbol(
                                symbol=play.symbol,
                                bars=bars_1min,
                                current_time=None  # Optional, defaults to now()
                            )
                            if structure_result:
                                structure_data = {
                                    'current_phase': structure_result.current_phase.value if hasattr(structure_result.current_phase, 'value') else str(structure_result.current_phase),
                                    'continuation_type': structure_result.continuation_type,
                                    'liquidity_sweep_detected': structure_result.liquidity_sweep_detected,
                                    'sweep_direction': structure_result.sweep_direction,
                                    'midday_structure': structure_result.midday_structure
                                }
                                self.logger.debug(f"📊 {play.symbol}: Structure={structure_result.current_phase.value} (continuation={structure_result.continuation_type})")
                        except Exception as e:
                            self.logger.warning(f"⚠️ {play.symbol}: Intraday structure classification failed: {e}")

                    # ================================================================
                    # ENHANCEMENT 4: Parabolic Extension Detection
                    # ================================================================
                    parabolic_data = None
                    if bars_1min and len(bars_1min) >= 15:
                        try:
                            # Convert bars to MarketData objects if needed
                            from core.interfaces import MarketData
                            wrapped_bars = []
                            for bar in bars_1min:
                                if isinstance(bar, dict):
                                    wrapped_bars.append(MarketData(
                                        symbol=play.symbol,  # Required parameter
                                        timestamp=bar.get('timestamp'),
                                        open=bar.get('open', 0.0),
                                        high=bar.get('high', 0.0),
                                        low=bar.get('low', 0.0),
                                        close=bar.get('close', 0.0),
                                        volume=bar.get('volume', 0)
                                    ))
                                else:
                                    wrapped_bars.append(bar)

                            parabolic_signal = self.parabolic_detector.detect_parabolic_extension(
                                symbol=play.symbol,
                                bars=wrapped_bars
                            )

                            if parabolic_signal:
                                parabolic_data = {
                                    'direction': parabolic_signal.direction,
                                    'stage': parabolic_signal.stage,
                                    'strength': parabolic_signal.strength,
                                    'acceleration': parabolic_signal.acceleration,
                                    'exhaustion_score': parabolic_signal.exhaustion_score,
                                    'long_entry_opportunity': parabolic_signal.long_entry_opportunity,
                                    'hold_signal': parabolic_signal.hold_signal,
                                    'exit_warning': parabolic_signal.exit_warning,
                                    'reasons': parabolic_signal.reasons[:3],  # Top 3 reasons
                                    'technical_data': parabolic_signal.technical_data
                                }
                                self.logger.info(f"🚀 {play.symbol}: PARABOLIC {parabolic_signal.stage} - Strength={parabolic_signal.strength:.2f}, Entry={parabolic_signal.long_entry_opportunity}")
                        except Exception as e:
                            self.logger.warning(f"⚠️ {play.symbol}: Parabolic detection failed: {e}")

                    # ================================================================
                    # ENHANCEMENT 5: Enhanced Quality Score
                    # ================================================================
                    base_quality_score = play.quality_score
                    enhanced_quality_score = calculate_enhanced_quality_score(
                        base_score=base_quality_score,
                        ods_data=ods_data,
                        structure_data=structure_data,
                        atr_pct=atr_percent
                    )

                    # Boost quality for early-stage parabolic LONG opportunities
                    if parabolic_data and parabolic_data.get('long_entry_opportunity'):
                        enhanced_quality_score += 15  # Significant boost for parabolic entry
                        self.logger.info(f"🚀 {play.symbol}: Quality boosted +15 for PARABOLIC ENTRY (stage={parabolic_data['stage']})")
                    # Reduce quality for late-stage parabolic (exit warning)
                    elif parabolic_data and parabolic_data.get('exit_warning'):
                        enhanced_quality_score = max(enhanced_quality_score - 20, 0)  # Reduce for exhaustion
                        self.logger.warning(f"⚠️ {play.symbol}: Quality reduced -20 for PARABOLIC EXHAUSTION")

                    # Cap at 100
                    enhanced_quality_score = min(enhanced_quality_score, 100.0)

                    if enhanced_quality_score > base_quality_score:
                        self.logger.info(f"✨ {play.symbol}: Quality boosted {base_quality_score:.0f} -> {enhanced_quality_score:.0f} (patterns detected)")

                    # ================================================================
                    # FILTER: Validate Price Action for LONG Opportunities
                    # ================================================================
                    # CRITICAL: Don't publish LONG opportunities if price is falling
                    # This prevents workers from receiving bearish setups with high Q scores
                    if bars_1min and len(bars_1min) >= 2:
                        try:
                            # Calculate daily return (current price vs open)
                            first_bar = bars_1min[0] if isinstance(bars_1min[0], dict) else bars_1min[0].__dict__
                            open_price = first_bar.get('open') if isinstance(first_bar, dict) else first_bar['open']

                            if open_price and open_price > 0:
                                daily_return_pct = ((current_price / open_price) - 1) * 100

                                # FILTER: For LONG opportunities, reject if price is falling
                                trading_rec = play.trading_recommendation or {}
                                action = trading_rec.get('action', 'LONG')

                                if action == 'LONG' and daily_return_pct < -1.0:  # Allow small -1% dips for pullbacks
                                    self.logger.info(
                                        f"🚫 {play.symbol}: REJECTED LONG opportunity - Price falling {daily_return_pct:.2f}% "
                                        f"(${open_price:.2f} -> ${current_price:.2f}). Not publishing bearish setup."
                                    )
                                    continue  # Skip publishing this opportunity

                                # Log price action for accepted opportunities
                                if daily_return_pct >= 0:
                                    self.logger.debug(f"✅ {play.symbol}: Price action bullish +{daily_return_pct:.2f}%")
                                else:
                                    self.logger.debug(f"⚠️ {play.symbol}: Minor pullback {daily_return_pct:.2f}% (allowed)")

                        except Exception as e:
                            # If we can't validate price action, log warning but continue
                            self.logger.debug(f"⚠️ {play.symbol}: Could not validate price action: {e}")

                    # ================================================================
                    # ENHANCEMENT 5: ORB Data Extraction
                    # ================================================================
                    orb_data = None
                    # Only extract ORB data during ORB trading window (9:30-10:30 AM)
                    from datetime import time
                    now = datetime.now().time()
                    if time(9, 30) <= now <= time(10, 30) and bars_1min:
                        orb_data = extract_orb_data(bars_1min)
                        if orb_data:
                            self.logger.debug(f"📊 {play.symbol}: ORB detected - range={orb_data['orb_range_pct']:.1f}%, pos={orb_data['current_vs_orb']}")

                    opportunity = {
                        # Core data (existing)
                        'symbol': play.symbol,
                        'opportunity_type': play.opportunity_type.value if hasattr(play, 'opportunity_type') else 'INTRADAY_MOMENTUM',
                        'quality_score': enhanced_quality_score,  # ENHANCED: Now uses enhanced score
                        'strategy_targets': play.strategy_targets,
                        'catalyst_type': play.catalyst.catalyst_type if play.catalyst and hasattr(play.catalyst, 'catalyst_type') else 'TECHNICAL',
                        'catalyst_strength': play.catalyst.strength if play.catalyst and hasattr(play.catalyst, 'strength') else 0.0,
                        'current_price': current_price,
                        'gap_percentage': play.context.gap_percentage if hasattr(play.context, 'gap_percentage') else 0.0,
                        'volume_ratio': play.context.premarket_volume_ratio if hasattr(play.context, 'premarket_volume_ratio') else 0.0,
                        'trading_recommendation': play.trading_recommendation,
                        'scan_timestamp': datetime.now().isoformat(),

                        # CRITICAL: Signal to trader that it needs to subscribe to ticker for fresh prices
                        'needs_subscription': True,
                        'ibkr_rank': play.ibkr_rank,
                        'news_count': len(play.catalyst.news_headlines) if play.catalyst and hasattr(play.catalyst, 'news_headlines') else 0,
                        'sentiment_score': getattr(play.catalyst, 'sentiment_score', 0.0) if play.catalyst else 0.0,

                        # ENHANCED: Bars history (corrected naming for worker compatibility)
                        'bars_history': bars_1min,

                        # ENHANCED: Additional market data
                        'market_cap': market_cap,
                        'float_size': float_size,
                        'avg_volume': avg_volume,

                        # ENHANCED: Risk management data
                        'suggested_stop_loss': suggested_stop_loss,
                        'suggested_take_profit': suggested_take_profit,
                        'suggested_position_size': suggested_position_size,
                        'risk_reward_ratio': (suggested_take_profit - current_price) / (current_price - suggested_stop_loss) if current_price > suggested_stop_loss else 0.0,

                        # ================================================================
                        # NEW ENHANCEMENTS: Pattern data for Trade Arbiter
                        # ================================================================
                        'atr_percent': atr_percent,  # For adaptive risk sizing
                        'ods_data': ods_data,  # For pattern alignment bonus
                        'intraday_structure': structure_data,  # For pattern alignment bonus
                        'orb_data': orb_data,  # For ORB Worker
                        'parabolic_data': parabolic_data  # For Parabolic Extension detection
                    }

                    # STREAMING MODE: Send opportunity immediately if it's new
                    await self._stream_opportunity_if_new(opportunity)

                    all_opportunities.append(opportunity)

            # 1.6 PROCESS MIDCAP PLAYS - NEW
            if midcap_plays:
                self.logger.info(f"🏢 Processing {len(midcap_plays)} MidCap opportunities...")
                for play in midcap_plays:
                    try:
                        # MidCap plays are already simplified, convert directly
                        opportunity = {
                            # Core data
                            'symbol': play.symbol,
                            'opportunity_type': play.opportunity_type.value,
                            'quality_score': play.quality_score,
                            'strategy_targets': play.strategy_targets,
                            'catalyst_type': play.catalyst_type or 'TECHNICAL',
                            'catalyst_strength': play.catalyst_confidence,
                            'current_price': play.current_price,
                            'gap_percentage': play.gap_percentage,
                            'volume_ratio': play.volume / play.avg_volume if play.avg_volume > 0 else 0.0,
                            'scan_timestamp': play.scan_timestamp.isoformat() if play.scan_timestamp else datetime.now().isoformat(),

                            # MidCap specific
                            'market_cap': play.market_cap,
                            'float_size': play.float_shares,
                            'avg_volume': play.avg_volume,
                            'institutional_ownership': play.institutional_ownership,

                            # Technical
                            'bars_history': play.bars_1min,
                            'vwap': play.vwap,
                            'resistance_levels': play.resistance_levels or [],
                            'support_levels': play.support_levels or [],

                            # Signal to trader
                            'needs_subscription': True,
                            'ibkr_rank': play.ibkr_rank,

                            # Risk management (basic)
                            'suggested_stop_loss': play.current_price * 0.93,  # 7% stop for MidCaps
                            'suggested_take_profit': play.current_price * 1.25,  # 25% target
                            'atr_percent': 0.0,  # Will be calculated by worker if needed

                            # Trading metadata
                            'trading_recommendation': {
                                'action': 'BUY',
                                'confidence': 'MEDIUM' if play.quality_score >= 75 else 'LOW',
                                'timeframe': 'SWING'  # MidCaps are swing trades
                            }
                        }

                        # Stream opportunity immediately
                        await self._stream_opportunity_if_new(opportunity)
                        all_opportunities.append(opportunity)

                        self.logger.debug(f"✅ {play.symbol}: MidCap opportunity added (Q={play.quality_score:.0f})")

                    except Exception as e:
                        self.logger.error(f"❌ Error processing MidCap play {play.symbol}: {e}")
                        continue

            # 2. DAILY BOUNCE SCANNING (NEW: using active candidates from IBKR)
            should_run_daily_scan = self._should_run_daily_scan()
            if should_run_daily_scan:
                if intraday_plays:
                    self.logger.info("🎯 NEW APPROACH: Starting daily bounce scanning on active candidates...")
                    # Extract symbols from intraday plays (active movers)
                    active_symbols = [play.symbol for play in intraday_plays]
                    self.logger.info(f"📊 Analyzing {len(active_symbols)} active symbols for bounce patterns")

                    bounce_opportunities = await self.daily_bounce_scanner.scan_bounce_candidates(active_symbols)

                    if bounce_opportunities:
                        self.logger.info(f"📊 Daily bounce scanner found {len(bounce_opportunities)} setups")
                        # FORCE TECHNICAL TYPE for compatibility with DailyPlays worker
                        for opp in bounce_opportunities:
                            opp['catalyst_type'] = 'TECHNICAL'
                        
                        all_opportunities.extend(bounce_opportunities)

                        # Update last daily scan timestamp
                        self.last_daily_scan = datetime.now()
                    else:
                        self.logger.info("📭 No bounce setups found among active symbols")

                    # 2.2 RED TO GREEN SCANNING (on same active symbols)
                    self.logger.info("🔴➡️🟢 Starting Red to Green scanning on active candidates...")
                    r2g_opportunities = await self.red_to_green_scanner.scan_r2g_candidates(active_symbols)

                    if r2g_opportunities:
                        self.logger.info(f"🔴➡️🟢 Red to Green scanner found {len(r2g_opportunities)} setups")
                        # Convert R2G results to standard opportunity format
                        for r2g_setup in r2g_opportunities:
                            opportunity = {
                                'symbol': r2g_setup['symbol'],
                                'opportunity_type': 'RED_TO_GREEN',
                                'quality_score': r2g_setup['r2g_score'],
                                'catalyst_type': 'TECHNICAL',  # Fixed: Add technical catalyst type
                                'strategy_targets': r2g_setup['strategy_targets'],
                                'current_price': r2g_setup['current_price'],
                                'r2g_breakout_level': r2g_setup['r2g_levels']['r2g_breakout_level'],
                                'target_1': r2g_setup['r2g_levels']['target_1'],
                                'target_2': r2g_setup['r2g_levels']['target_2'],
                                'stop_loss': r2g_setup['r2g_levels']['stop_loss'],
                                'distance_to_breakout': r2g_setup['r2g_levels']['distance_to_breakout'],
                                'trading_recommendation': r2g_setup['trading_recommendation'],
                                'scan_timestamp': r2g_setup['scan_timestamp'].isoformat(),
                                'green_candle_volume_ratio': r2g_setup['green_candle_data']['volume_ratio'],
                                'consolidation_range': r2g_setup['consolidation_data']['price_range_percent']
                            }
                            all_opportunities.append(opportunity)
                    else:
                        self.logger.info("📭 No R2G setups found among active symbols")
                else:
                    self.logger.info("📭 No active candidates for bounce analysis - skipping daily bounce scan")

                # 2.3 SHORT SQUEEZE SCANNING (on active candidates)
                # We analyze the same active movers for Squeeze structure
                if intraday_plays:
                    self.logger.info("🐻💥 Starting Short Squeeze analysis on active candidates...")
                    # Convert intraday plays to dicts for scanner
                    candidates = []
                    for play in intraday_plays:
                        candidates.append({
                            'symbol': play.symbol,
                            'current_price': play.context.current_price if hasattr(play.context, 'current_price') else 0,
                            'gap_percentage': play.context.gap_percentage if hasattr(play.context, 'gap_percentage') else 0,
                            'volume_ratio': play.context.premarket_volume_ratio if hasattr(play.context, 'premarket_volume_ratio') else 0,
                            'quality_score': play.quality_score
                        })
                    
                    squeeze_opportunities = await self.short_squeeze_scanner.scan_squeeze_candidates(candidates)
                    
                    if squeeze_opportunities:
                        self.logger.info(f"💎 Found {len(squeeze_opportunities)} Short Squeeze setups!")
                        # FORCE TECHNICAL TYPE for compatibility
                        for opp in squeeze_opportunities:
                            opp['catalyst_type'] = 'TECHNICAL'
                            
                        all_opportunities.extend(squeeze_opportunities)
                    else:
                        self.logger.info("📭 No Short Squeeze setups found")

                # 2.4 PROACTIVE SCANNING (Daily refresh of T+1..T+7 watchlist)
                # Uses ProactiveScanner.should_run_now() to respect schedule configuration
                try:
                    from pytz import timezone
                    et_tz = timezone('US/Eastern')
                    now_et = datetime.now(et_tz)
                    today_et = now_et.date()

                    # Check if we should run based on ProactiveScanner schedule config
                    if self.proactive_scanner.should_run_now() and self.last_proactive_scan_date != today_et:
                        self.logger.info(f"🚀 Starting Proactive Scan ({now_et.strftime('%H:%M')} ET)...")
                        await self.proactive_scanner.scan_and_update_watchlist()
                        self.last_proactive_scan_date = today_et
                        self.logger.info("✅ Proactive Scan completed and watchlist updated")
                    else:
                        if self.last_proactive_scan_date == today_et:
                            self.logger.debug("⏭️ Proactive Scan already completed for today")
                        # If should_run_now() is False, the scanner itself logs the reason

                except Exception as e:
                    self.logger.error(f"❌ Error in Proactive Scan scheduling: {e}")

            # 3. SUMMARY AND RETURN
            if not all_opportunities:
                self.logger.info("📭 No opportunities found in unified scan")
                return []

            # Log summary by opportunity type
            type_counts = {}
            for opp in all_opportunities:
                opp_type = opp['opportunity_type']
                type_counts[opp_type] = type_counts.get(opp_type, 0) + 1

            type_summary = ', '.join([f"{t}: {c}" for t, c in type_counts.items()])
            self.logger.info(f"🎯 Unified scan: {len(all_opportunities)} opportunities - {type_summary}")

            return all_opportunities

        except Exception as e:
            self.logger.error(f"❌ Error in unified scanning: {e}")
            # Emergency fallback - use valid catalyst type
            return [
                {
                    'symbol': 'EMERGENCY',
                    'opportunity_type': 'INTRADAY_MOMENTUM',
                    'quality_score': 50.0,
                    'catalyst_type': 'TECHNICAL',  # Changed from 'ERROR_FALLBACK' to valid catalyst
                    'catalyst_strength': 0.5,
                    'current_price': 10.0,
                    'gap_percentage': 5.0,
                    'volume_ratio': 1.5,
                    'trading_recommendation': 'HOLD',
                    'scan_timestamp': datetime.now().isoformat(),
                    'ibkr_rank': 1,
                    'news_count': 0,
                    'sentiment_score': 0.0
                }
            ]

    def _should_run_daily_scan(self) -> bool:
        """Determine if daily bounce scan should run"""
        try:
            now = datetime.now()

            # Run daily scan at 6 AM or if never run before
            if self.last_daily_scan is None:
                return True

            # Check if it's past daily scan time and we haven't run today
            last_scan_date = self.last_daily_scan.date()
            current_date = now.date()

            if current_date > last_scan_date and now.hour >= self.daily_scan_hour:
                return True

            # For testing: run every 2 hours during market hours
            time_since_last = now - self.last_daily_scan
            if time_since_last.total_seconds() > 7200:  # 2 hours
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking daily scan schedule: {e}")
            return False
    
    async def stop(self):
        """Stop scanner process"""
        try:
            self.is_running = False
            self.shutdown_requested = True
            
            # Disconnect IBKR
            if self.scanner_ibkr:
                await self.scanner_ibkr.disconnect()
                self.logger.info("✅ Scanner IBKR disconnected")
            
            # Disconnect bridge
            await self.bridge.disconnect()
            self.logger.info("✅ Redis bridge disconnected")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping scanner: {e}")

async def main():
    """Main function for independent scanner"""
    scanner = IndependentScanner()

    print("🔍 INDEPENDENT SCANNER PROCESS")
    print("   ✅ Separate IBKR connection")
    print("   ✅ Redis pub/sub communication")
    print("   ✅ Independent of trader")
    print()

    try:
        success = await scanner.start()
        scanner.logger.debug(f"🔍 DEBUG: scanner.start() returned {success}")
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n🛑 Scanner interrupted by user")
        scanner.logger.debug("🔍 DEBUG: KeyboardInterrupt in main()")
        await scanner.stop()
        return 0
    except Exception as e:
        print(f"❌ Scanner failed: {e}")
        scanner.logger.error(f"❌ Exception in main(): {e}")
        import traceback
        scanner.logger.error(f"🔍 Exception traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)