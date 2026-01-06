#!/usr/bin/env python3
"""
Report Generator - Generador de reportes HTML para replay testing

Genera reportes visuales HTML con:
- Summary del replay session
- Timeline de decisiones
- Comparación replay vs real
- Análisis de discrepancias
- Gráficos de performance
"""

import os
import logging
from typing import Dict, List, Any
from datetime import datetime


class ReportGenerator:
    """
    Generador de reportes HTML para replay sessions
    """

    def __init__(self, output_dir: str = "replay_testing/reports"):
        """
        Initialize report generator

        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def generate_session_report(
        self,
        session: Any,
        comparison: Dict = None,
        verification: Dict = None
    ) -> str:
        """
        Genera reporte HTML completo de una sesión de replay

        Args:
            session: ReplaySession object
            comparison: Optional comparison results
            verification: Optional verification results

        Returns:
            Path to generated HTML file
        """
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"replay_{session.date}_{session.worker_name}_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)

        # Generate HTML content
        html = self._generate_html(session, comparison, verification)

        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        self.logger.info(f"Report saved: {filepath}")

        return filepath

    def _generate_html(
        self,
        session: Any,
        comparison: Dict = None,
        verification: Dict = None
    ) -> str:
        """
        Generate HTML content

        Args:
            session: ReplaySession object
            comparison: Comparison results
            verification: Verification results

        Returns:
            HTML string
        """
        html_parts = []

        # HTML header
        html_parts.append(self._html_header(session))

        # Summary section
        html_parts.append(self._html_summary(session))

        # Events section
        html_parts.append(self._html_events(session))

        # Discrepancies section
        if session.discrepancies:
            html_parts.append(self._html_discrepancies(session))

        # Comparison section
        if comparison:
            html_parts.append(self._html_comparison(comparison))

        # Verification section
        if verification:
            html_parts.append(self._html_verification(verification))

        # Timeline section
        html_parts.append(self._html_timeline(session))

        # HTML footer
        html_parts.append(self._html_footer())

        return "\n".join(html_parts)

    def _html_header(self, session: Any) -> str:
        """Generate HTML header"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Replay Report - {session.date} - {session.worker_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-card.success {{
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        }}
        .stat-card.warning {{
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }}
        .stat-card.error {{
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge.success {{
            background-color: #27ae60;
            color: white;
        }}
        .badge.warning {{
            background-color: #f39c12;
            color: white;
        }}
        .badge.error {{
            background-color: #e74c3c;
            color: white;
        }}
        .timeline {{
            position: relative;
            padding: 20px 0;
        }}
        .timeline-item {{
            position: relative;
            padding: 10px 0 10px 30px;
            border-left: 2px solid #3498db;
            margin-left: 10px;
        }}
        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -6px;
            top: 15px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: #3498db;
        }}
        .timeline-item.entry::before {{
            background-color: #27ae60;
        }}
        .timeline-item.exit::before {{
            background-color: #e74c3c;
        }}
        .discrepancy {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .discrepancy.high {{
            background-color: #f8d7da;
            border-left-color: #dc3545;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Replay Testing Report</h1>
        <p><strong>Date:</strong> {session.date} | <strong>Worker:</strong> {session.worker_name}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
"""

    def _html_summary(self, session: Any) -> str:
        """Generate summary section"""
        elapsed = (session.end_time - session.start_time).total_seconds() if session.start_time and session.end_time else 0

        return f"""
        <h2>Summary</h2>
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-label">Events Processed</div>
                <div class="stat-value">{session.total_events}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Bars Processed</div>
                <div class="stat-value">{session.total_bars_processed}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Decisions Made</div>
                <div class="stat-value">{session.total_decisions}</div>
            </div>
            <div class="stat-card success">
                <div class="stat-label">Entries Approved</div>
                <div class="stat-value">{session.entries_approved}</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">Entries Rejected</div>
                <div class="stat-value">{session.entries_rejected}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Exits Executed</div>
                <div class="stat-value">{session.exits_executed}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Simulated Trades</div>
                <div class="stat-value">{len(session.simulated_trades)}</div>
            </div>
            <div class="stat-card {'error' if session.total_discrepancies > 0 else 'success'}">
                <div class="stat-label">Discrepancies</div>
                <div class="stat-value">{session.total_discrepancies}</div>
            </div>
        </div>
        <p><strong>Execution Time:</strong> {elapsed:.1f}s</p>
"""

    def _html_events(self, session: Any) -> str:
        """Generate events section"""
        rows = []

        for symbol, event in session.events.items():
            workers_evaluated = ', '.join(event.get_workers_that_evaluated())
            workers_traded = ', '.join(event.get_workers_that_traded()) or '-'

            status_badge = f'<span class="badge success">✓ OK</span>' if len(event.discrepancies) == 0 else f'<span class="badge error">⚠ {len(event.discrepancies)} issues</span>'

            rows.append(f"""
                <tr>
                    <td>{symbol}</td>
                    <td>{len(event.get_all_decisions())}</td>
                    <td>{len(event.simulated_trades)}</td>
                    <td>{len(event.real_trades)}</td>
                    <td>{workers_evaluated}</td>
                    <td>{workers_traded}</td>
                    <td>{status_badge}</td>
                </tr>
            """)

        return f"""
        <h2>Events</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Decisions</th>
                    <th>Simulated Trades</th>
                    <th>Real Trades</th>
                    <th>Workers Evaluated</th>
                    <th>Workers Traded</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
"""

    def _html_discrepancies(self, session: Any) -> str:
        """Generate discrepancies section"""
        items = []

        for disc in session.discrepancies[:20]:  # Show first 20
            severity_class = disc.get('severity', 'MEDIUM').lower()
            disc_type = disc.get('type', 'UNKNOWN')
            message = disc.get('message', 'No message')
            symbol = disc.get('symbol', 'N/A')

            items.append(f"""
                <div class="discrepancy {severity_class}">
                    <strong>[{disc_type}] {symbol}</strong>: {message}
                </div>
            """)

        remaining = len(session.discrepancies) - 20
        if remaining > 0:
            items.append(f'<p><em>... and {remaining} more discrepancies</em></p>')

        return f"""
        <h2>Discrepancies ({len(session.discrepancies)})</h2>
        {"".join(items)}
"""

    def _html_comparison(self, comparison: Dict) -> str:
        """Generate comparison section"""
        summary = comparison.get('summary', {})

        return f"""
        <h2>Comparison Analysis</h2>
        <p><strong>Match Rate:</strong> {summary.get('match_rate', 0)*100:.1f}%</p>
        <p><strong>Price Discrepancies:</strong> {summary.get('price_discrepancy_count', 0)}</p>
        <p><strong>Timing Discrepancies:</strong> {summary.get('timing_discrepancy_count', 0)}</p>
        <p><strong>Unmatched Simulated:</strong> {summary.get('unmatched_simulated_count', 0)}</p>
        <p><strong>Unmatched Real:</strong> {summary.get('unmatched_real_count', 0)}</p>
"""

    def _html_verification(self, verification: Dict) -> str:
        """Generate verification section"""
        return f"""
        <h2>Verification Results</h2>
        <p><strong>Total Verifications:</strong> {verification.get('total_verifications', 0)}</p>
        <p><strong>Passed:</strong> {verification.get('passed', 0)}</p>
        <p><strong>Failed:</strong> {verification.get('failed', 0)}</p>
        <p><strong>Pass Rate:</strong> {verification.get('pass_rate', 0)*100:.1f}%</p>
"""

    def _html_timeline(self, session: Any) -> str:
        """Generate timeline section"""
        items = []

        # Collect all decisions from all events
        all_decisions = []
        for event in session.events.values():
            for decision in event.get_all_decisions():
                all_decisions.append(decision)

        # Sort by timestamp
        all_decisions.sort(key=lambda d: d.timestamp)

        # Generate timeline items (max 50)
        for decision in all_decisions[:50]:
            decision_class = decision.decision_type.lower()
            icon = "🟢" if decision.decision_type == "ENTRY" else "🔴" if decision.decision_type == "EXIT" else "⚪"

            time_str = decision.timestamp.strftime("%H:%M:%S")

            if decision.decision_type == "ENTRY":
                details = f"${decision.entry_price:.2f}, pattern={decision.pattern_completion:.1f}%"
            elif decision.decision_type == "EXIT":
                details = f"${decision.exit_price:.2f}, reason={decision.exit_reason}"
            else:
                details = decision.notes

            items.append(f"""
                <div class="timeline-item {decision_class}">
                    <strong>{icon} {time_str} - {decision.symbol}</strong> ({decision.worker_name})<br>
                    {decision.decision_type}: {details}
                </div>
            """)

        remaining = len(all_decisions) - 50
        if remaining > 0:
            items.append(f'<p><em>... and {remaining} more decisions</em></p>')

        return f"""
        <h2>Timeline</h2>
        <div class="timeline">
            {"".join(items)}
        </div>
"""

    def _html_footer(self) -> str:
        """Generate HTML footer"""
        return """
    </div>
</body>
</html>
"""
