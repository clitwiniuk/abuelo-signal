"""
Swing Trading Daily Report Generator
Generates daily reports for swing trading activity
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional
import sqlite3


class SwingReportGenerator:
    """
    Generate daily reports for swing trading

    Reports include:
    - EOD scan results
    - Active swing positions
    - Exits during the day
    - Performance metrics
    """

    def __init__(self, db_path: str = "trading_data.db", logger: Optional[logging.Logger] = None):
        """
        Initialize report generator

        Args:
            db_path: Path to trading database
            logger: Optional logger
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger("SwingReportGenerator")

    def generate_daily_report(self, report_date: date = None) -> str:
        """
        Generate daily report for swing trading

        Args:
            report_date: Date for report (default: today)

        Returns:
            Formatted report string
        """
        if report_date is None:
            report_date = date.today()

        try:
            report = []
            report.append("=" * 60)
            report.append(f"SWING TRADING DAILY REPORT - {report_date.strftime('%Y-%m-%d')}")
            report.append("=" * 60)
            report.append("")

            # Section 1: EOD Scan Results
            scan_results = self._get_eod_scan_results(report_date)
            report.append("📊 EOD SCAN RESULTS")
            report.append("-" * 60)
            if scan_results and len(scan_results) > 0:
                for result in scan_results:
                    report.append(
                        f"  ✓ {result['symbol']:6} | "
                        f"{result['pattern_type']:20} | "
                        f"Score: {result['breakout_score']:3.0f} | "
                        f"Mode: {result['entry_mode']}"
                    )
                report.append(f"\nTotal picks: {len(scan_results)}")
            else:
                report.append("  No picks identified")
            report.append("")

            # Section 2: New Entries Today
            new_entries = self._get_new_entries(report_date)
            report.append("🎯 NEW ENTRIES TODAY")
            report.append("-" * 60)
            if new_entries and len(new_entries) > 0:
                for entry in new_entries:
                    report.append(
                        f"  ✓ {entry['symbol']:6} | "
                        f"Entry: ${entry['entry_price']:7.2f} | "
                        f"Qty: {entry['quantity']:4} | "
                        f"Mode: {entry.get('entry_mode', 'N/A')}"
                    )
                report.append(f"\nTotal entries: {len(new_entries)}")
            else:
                report.append("  No new entries")
            report.append("")

            # Section 3: Active Positions
            active_positions = self._get_active_positions()
            report.append("📈 ACTIVE SWING POSITIONS")
            report.append("-" * 60)
            if active_positions and len(active_positions) > 0:
                total_value = 0
                for pos in active_positions:
                    entry_price = pos.get('entry_price', 0)
                    quantity = pos.get('quantity', 0)
                    position_value = entry_price * quantity
                    total_value += position_value
                    days_held = self._calculate_days_held(pos.get('entry_date'))

                    report.append(
                        f"  • {pos['symbol']:6} | "
                        f"Entry: ${entry_price:7.2f} | "
                        f"Qty: {quantity:4} | "
                        f"Value: ${position_value:8.2f} | "
                        f"Days: {days_held:2}"
                    )
                report.append(f"\nTotal positions: {len(active_positions)}")
                report.append(f"Total capital: ${total_value:,.2f}")
            else:
                report.append("  No active positions")
            report.append("")

            # Section 4: Exits Today
            exits_today = self._get_exits_today(report_date)
            report.append("🔚 EXITS TODAY")
            report.append("-" * 60)
            if exits_today and len(exits_today) > 0:
                total_pnl = 0
                wins = 0
                losses = 0

                for exit_trade in exits_today:
                    pnl = exit_trade.get('pnl_gross', 0)
                    pnl_pct = exit_trade.get('pnl_percentage', 0)
                    total_pnl += pnl

                    if pnl > 0:
                        wins += 1
                        emoji = "✅"
                    else:
                        losses += 1
                        emoji = "❌"

                    report.append(
                        f"  {emoji} {exit_trade['symbol']:6} | "
                        f"PnL: ${pnl:+8.2f} ({pnl_pct:+6.2f}%) | "
                        f"Days: {exit_trade.get('days_held', 0):2} | "
                        f"Reason: {exit_trade.get('exit_reason', 'N/A')}"
                    )

                report.append(f"\nTotal exits: {len(exits_today)}")
                report.append(f"Wins: {wins} | Losses: {losses}")
                report.append(f"Total PnL: ${total_pnl:+,.2f}")
            else:
                report.append("  No exits today")
            report.append("")

            # Section 5: Performance Summary
            performance = self._get_performance_summary()
            report.append("📊 PERFORMANCE SUMMARY (ALL TIME)")
            report.append("-" * 60)
            report.append(f"  Total trades: {performance['total_trades']}")
            report.append(f"  Win rate: {performance['win_rate']:.1f}%")
            report.append(f"  Avg win: ${performance['avg_win']:,.2f}")
            report.append(f"  Avg loss: ${performance['avg_loss']:,.2f}")
            report.append(f"  Total PnL: ${performance['total_pnl']:+,.2f}")
            report.append("")

            report.append("=" * 60)

            return "\n".join(report)

        except Exception as e:
            self.logger.error(f"❌ Error generating daily report: {e}")
            return f"Error generating report: {e}"

    def _get_eod_scan_results(self, scan_date: date) -> List[Dict]:
        """Get EOD scan results for date"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT symbol, pattern_type, breakout_score, entry_mode
                FROM swing_picks_cache
                WHERE DATE(last_pick_date) = ?
                ORDER BY breakout_score DESC
            """, (scan_date.isoformat(),))

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

        except Exception as e:
            self.logger.error(f"❌ Error getting EOD scan results: {e}")
            return []

    def _get_new_entries(self, entry_date: date) -> List[Dict]:
        """Get new entries for date"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT symbol, entry_price, quantity, pattern_type
                FROM swing_trades
                WHERE DATE(entry_date) = ?
                AND status = 'ACTIVE'
                ORDER BY entry_date DESC
            """, (entry_date.isoformat(),))

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            # Note: entry_mode not in database schema yet, would need to add
            # For now, return pattern_type as entry_mode fallback
            for result in results:
                result['entry_mode'] = result.get('pattern_type', 'BREAKOUT')

            return results

        except Exception as e:
            self.logger.error(f"❌ Error getting new entries: {e}")
            return []

    def _get_active_positions(self) -> List[Dict]:
        """Get all active swing positions"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT symbol, entry_price, quantity, entry_date
                FROM swing_trades
                WHERE status = 'ACTIVE'
                ORDER BY entry_date DESC
            """)

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

        except Exception as e:
            self.logger.error(f"❌ Error getting active positions: {e}")
            return []

    def _get_exits_today(self, exit_date: date) -> List[Dict]:
        """Get exits for date"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT symbol, pnl_gross, pnl_percentage, days_held, exit_reason
                FROM swing_trades
                WHERE DATE(exit_date) = ?
                AND status = 'CLOSED'
                ORDER BY exit_date DESC
            """, (exit_date.isoformat(),))

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

        except Exception as e:
            self.logger.error(f"❌ Error getting exits: {e}")
            return []

    def _get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all closed trades
            cursor.execute("""
                SELECT pnl_gross
                FROM swing_trades
                WHERE status = 'CLOSED'
                AND pnl_gross IS NOT NULL
            """)

            trades = [row['pnl_gross'] for row in cursor.fetchall()]
            conn.close()

            if not trades or len(trades) == 0:
                return {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'avg_win': 0.0,
                    'avg_loss': 0.0,
                    'total_pnl': 0.0
                }

            wins = [t for t in trades if t > 0]
            losses = [t for t in trades if t <= 0]

            return {
                'total_trades': len(trades),
                'win_rate': (len(wins) / len(trades)) * 100 if len(trades) > 0 else 0.0,
                'avg_win': sum(wins) / len(wins) if len(wins) > 0 else 0.0,
                'avg_loss': sum(losses) / len(losses) if len(losses) > 0 else 0.0,
                'total_pnl': sum(trades)
            }

        except Exception as e:
            self.logger.error(f"❌ Error getting performance summary: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'total_pnl': 0.0
            }

    def _calculate_days_held(self, entry_date_str: str) -> int:
        """Calculate days held from entry date"""
        try:
            if not entry_date_str:
                return 0

            entry_date = datetime.fromisoformat(entry_date_str).date()
            today = date.today()
            delta = today - entry_date

            return delta.days

        except Exception as e:
            self.logger.error(f"❌ Error calculating days held: {e}")
            return 0

    def send_daily_report_telegram(self, report_text: str):
        """
        Send daily report via Telegram

        Args:
            report_text: Report text to send
        """
        try:
            from notifications.telegram_client import send_message, is_enabled

            if not is_enabled():
                self.logger.debug("Telegram not enabled, skipping report")
                return

            # Format for Telegram (monospace for tables)
            telegram_msg = f"```\n{report_text}\n```"

            send_message(telegram_msg, parse_mode="Markdown")
            self.logger.info("📱 Daily swing report sent via Telegram")

        except Exception as e:
            self.logger.error(f"❌ Error sending Telegram report: {e}")
