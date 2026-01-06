"""
Telegram Command: /regime
Shows current market regime and adaptive thresholds
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)


def handle_regime_command() -> str:
    """
    Handle /regime command - show current market regime and thresholds

    Returns:
        Formatted message with regime info
    """
    try:
        from core.market_regime_detector import get_market_regime_detector
        from core.adaptive_threshold_manager import get_adaptive_threshold_manager

        # Get regime detector
        detector = get_market_regime_detector()
        conditions = detector.get_current_regime()

        if not conditions:
            return "⚠️ Market regime data not available yet. Try again in a few minutes."

        # Get threshold manager
        threshold_mgr = get_adaptive_threshold_manager()
        thresholds = threshold_mgr.get_thresholds()
        summary = threshold_mgr.get_regime_summary()

        # Build message
        msg = "🌍 **MARKET REGIME REPORT**\n"
        msg += "=" * 40 + "\n\n"

        # Regime header
        regime_emoji = {
            "bull_high_liquidity": "🐂💧",
            "bull_low_liquidity": "🐂",
            "bear_high_vol": "🐻⚡",
            "bear_low_vol": "🐻",
            "choppy": "🌊",
            "panic": "🚨",
            "unknown": "❓"
        }

        regime_name = conditions.regime.value
        emoji = regime_emoji.get(regime_name, "❓")

        msg += f"{emoji} **{regime_name.upper().replace('_', ' ')}**\n"
        msg += f"Confidence: {conditions.confidence:.0f}%\n\n"

        # Market metrics
        msg += "📊 **Market Metrics:**\n"
        msg += f"• SPY Trend: {conditions.spy_trend:+.2f}%\n"
        msg += f"• Volatility: {conditions.spy_volatility:.2f}%\n"
        msg += f"• Volume Ratio: {conditions.volume_ratio:.1f}x\n"
        msg += f"• Liquidity Score: {conditions.liquidity_score:.0f}/100\n"
        msg += f"• Sentiment: {conditions.sentiment_score:+.0f}/100\n\n"

        # Entry status
        if thresholds.allow_entries:
            msg += "✅ **Entries: ENABLED**\n\n"
        else:
            msg += "🚫 **Entries: DISABLED**\n\n"

        # Adaptive thresholds
        msg += "🎚️ **Adaptive Thresholds:**\n"
        msg += f"• VWAP Tolerance: {thresholds.vwap_price_tolerance_pct:.1f}%\n"
        msg += f"• VWAP Trend: {thresholds.vwap_trend_tolerance_pct:+.2f}%\n"
        msg += f"• Min Quality: {thresholds.min_quality_score:.0f}\n"
        msg += f"• Min Pattern: {thresholds.min_pattern_completion:.0f}%\n"
        msg += f"• Position Size: {thresholds.position_size_multiplier:.1f}x\n"
        msg += f"• Daily Trades: {thresholds.max_daily_trades_multiplier:.1f}x\n\n"

        # Risk interpretation
        risk_factor = conditions.get_risk_adjustment_factor()
        if risk_factor >= 1.2:
            risk_msg = "🟢 Aggressive (favorable conditions)"
        elif risk_factor >= 1.0:
            risk_msg = "🟡 Normal"
        elif risk_factor >= 0.7:
            risk_msg = "🟠 Conservative (cautious)"
        elif risk_factor > 0.0:
            risk_msg = "🔴 Very Conservative (high risk)"
        else:
            risk_msg = "🚨 NO ENTRIES (panic mode)"

        msg += f"⚖️ **Risk Mode:** {risk_msg}\n\n"

        # Last update
        import pytz
        eastern = pytz.timezone('US/Eastern')
        timestamp_et = conditions.timestamp.astimezone(eastern)
        msg += f"🕒 Updated: {timestamp_et.strftime('%H:%M:%S ET')}"

        return msg

    except Exception as e:
        logger.error(f"Error handling /regime command: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Error getting regime info: {str(e)}"
