"""
Swing Consolidation Scanner

End-of-day scanner that detects smallcaps in long consolidation patterns
(4 weeks to 6 months) ready for potential breakouts.

Execution: Daily at 15:40 ET (21:40 España)
Output: Top 2 best consolidation setups for next day market open execution
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import configparser
import sqlite3

logger = logging.getLogger(__name__)


class SwingConsolidationScanner:
    """
    Detects long-term consolidation patterns in smallcap stocks

    Process:
    1. Filter universe (price, volume, market cap)
    2. Fetch daily historical data (120+ days)
    3. Detect consolidation periods (20-120 days)
    4. Identify pattern type (triangle, cup, flag, base)
    5. Calculate breakout score (0-100)
    6. Filter recent picks (cooldown)
    7. Select top 2 setups
    8. Save to database for next day execution
    """

    def __init__(self, ibkr_adapter=None, config_path: str = "config.ini"):
        self.ibkr = ibkr_adapter
        self.logger = logging.getLogger(f"{__name__}.SwingConsolidationScanner")

        # Load configuration
        self.config = self._load_config(config_path)

        # Database connection
        self.db_path = "trading_data.db"

        # Tracking
        self.recent_picks = {}  # {symbol: last_pick_date}
        self._load_recent_picks()

        self.logger.info("🔍 SwingConsolidationScanner initialized")
        self.logger.info(f"   📊 Config: {self.config['min_consolidation_days']}-{self.config['max_consolidation_days']} days consolidation")
        self.logger.info(f"   🎯 Selecting top 2 setups daily")
        self.logger.info(f"   ⏰ Scan time: {self.config['scan_time']} ET")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load swing trading configuration from config.ini"""
        parser = configparser.ConfigParser()
        parser.read(config_path)

        swing_config = parser['SWING_TRADING']

        return {
            # Position sizing
            'max_positions': swing_config.getint('max_swing_positions', 2),
            'min_position_value': swing_config.getfloat('min_swing_position_value', 300.0),
            'max_position_value': swing_config.getfloat('max_swing_position_value', 400.0),
            'swing_capital_pct': swing_config.getfloat('swing_capital_percentage', 0.40),

            # Scanner timing
            'scan_time': swing_config.get('scan_time', '15:40'),
            'cooldown_days': swing_config.getint('cooldown_days', 5),

            # Consolidation detection
            'min_consolidation_days': swing_config.getint('min_consolidation_days', 20),
            'max_consolidation_days': swing_config.getint('max_consolidation_days', 120),
            'min_breakout_score': swing_config.getfloat('min_breakout_score', 70.0),
            'max_consolidation_range_pct': swing_config.getfloat('max_consolidation_range_pct', 25.0),

            # Price/volume filters
            'min_price': swing_config.getfloat('min_price', 1.0),
            'max_price': swing_config.getfloat('max_price', 15.0),
            'min_avg_volume_90d': swing_config.getint('min_avg_volume_90d', 100000),

            # Pattern detection
            'min_resistance_touches': swing_config.getint('min_resistance_touches', 3),
            'min_support_touches': swing_config.getint('min_support_touches', 2),
            'max_distance_from_resistance_pct': swing_config.getfloat('max_distance_from_resistance_pct', 5.0),

            # Technical filters
            'rsi_min': swing_config.getfloat('rsi_min', 45.0),
            'rsi_max': swing_config.getfloat('rsi_max', 65.0),
        }

    def _load_recent_picks(self):
        """Load recent picks from database to avoid duplicates"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Load picks from last cooldown period
                cooldown_date = datetime.now().date() - timedelta(days=self.config['cooldown_days'])

                cursor.execute("""
                    SELECT symbol, last_pick_date
                    FROM swing_picks_cache
                    WHERE last_pick_date >= ?
                """, (cooldown_date,))

                for row in cursor.fetchall():
                    symbol, pick_date_str = row
                    self.recent_picks[symbol] = datetime.strptime(pick_date_str, '%Y-%m-%d').date()

                self.logger.info(f"📋 Loaded {len(self.recent_picks)} recent picks (cooldown: {self.config['cooldown_days']} days)")

        except Exception as e:
            self.logger.warning(f"Could not load recent picks: {e}")
            self.recent_picks = {}

    async def scan_for_consolidations(self) -> List[Dict[str, Any]]:
        """
        Main scan method - Execute daily at 15:40 ET

        Returns:
            List of top 2 consolidation setups ready for breakout
        """
        self.logger.info("🔍 Starting EOD swing consolidation scan...")
        start_time = datetime.now()

        # Step 1: Get universe of candidates
        candidates = await self._get_scan_universe()
        self.logger.info(f"   📊 Universe: {len(candidates)} candidates")

        if not candidates:
            self.logger.warning("⚠️ No candidates found in universe - check IBKR connection and filters")
            return []

        # Step 2: Analyze each candidate for consolidation
        consolidations = []
        analyzed_count = 0
        failed_analysis_count = 0

        for symbol in candidates[:10]:  # Limit to first 10 for detailed analysis
            try:
                analyzed_count += 1
                self.logger.debug(f"🔬 Analyzing {symbol} for consolidation ({analyzed_count}/{len(candidates)})")

                consolidation = await self._analyze_consolidation(symbol)
                if consolidation:
                    consolidations.append(consolidation)
                    self.logger.debug(f"✅ {symbol}: Found consolidation pattern (score: {consolidation.get('breakout_score', 0):.0f})")
                else:
                    failed_analysis_count += 1
                    self.logger.debug(f"❌ {symbol}: No consolidation pattern found")
            except Exception as e:
                failed_analysis_count += 1
                self.logger.debug(f"❌ Error analyzing {symbol}: {e}")
                continue

        self.logger.info(
            f"   🎯 Found {len(consolidations)} consolidation patterns "
            f"({analyzed_count} analyzed, {failed_analysis_count} failed)"
        )

        if not consolidations:
            self.logger.warning(
                f"📭 No consolidation setups found today "
                f"({analyzed_count} analyzed, {failed_analysis_count} failed analysis)"
            )
            return []

        # Step 3: Filter recent picks (cooldown)
        filtered = self._filter_recent_picks(consolidations)
        self.logger.info(f"   ✅ After cooldown filter: {len(filtered)} setups")

        # Step 4: Select top 2 by breakout score
        top_setups = self._select_top_setups(filtered, max_picks=2)

        # Step 5: Save to database
        if top_setups:
            self._save_swing_picks(top_setups)

        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"✅ Scan completed in {elapsed:.1f}s - Selected {len(top_setups)} setups")

        for setup in top_setups:
            self.logger.info(
                f"   🎯 {setup['symbol']}: {setup['pattern_type']} "
                f"(score: {setup['breakout_score']:.0f}, "
                f"consolidation: {setup['consolidation_days']} days)"
            )

        return top_setups

    async def _get_scan_universe(self) -> List[str]:
        """
        Get initial universe of candidates using IBKR scanner

        Filters:
        - Price: $1-15
        - Market cap: $10M-500M
        - Float: <200M shares (reasonable for smallcaps)
        - Avg volume: >100K shares/day
        """
        if not self.ibkr:
            self.logger.warning("⚠️ IBKR adapter not available - using mock universe")
            return ['AAPL', 'TSLA']  # Mock for testing

        self.logger.info("🔍 Fetching scan universe from IBKR...")

        # Use IBKR scanner with smallcap filters
        candidates = await self.ibkr.scan_market_for_swing(
            min_price=self.config['min_price'],
            max_price=self.config['max_price'],
            min_volume=self.config['min_avg_volume_90d'],
            min_market_cap=10_000_000,  # $10M
            max_market_cap=500_000_000,  # $500M
            max_float=200_000_000,  # 200M shares max float (allows more opportunities)
            max_results=200  # Get more candidates for analysis
        )

        return candidates

    async def _analyze_consolidation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a symbol for consolidation pattern

        Returns:
            Dict with consolidation details or None if no pattern found
        """
        try:
            # Get daily historical data (120+ days)
            if not self.ibkr:
                return None

            daily_bars = await self.ibkr.get_historical_data(
                symbol=symbol,
                timeframe='1 day',
                count=130,  # Get extra data for analysis
                use_rth=True  # Regular trading hours only
            )

            if not daily_bars or len(daily_bars) < self.config['min_consolidation_days']:
                self.logger.debug(f"{symbol}: Insufficient historical data")
                return None

            # Use ConsolidationPatternDetector to analyze pattern
            from scanner.swing.consolidation_pattern_detector import ConsolidationPatternDetector

            detector = ConsolidationPatternDetector(config=self.config)
            result = detector.analyze_consolidation(symbol, daily_bars)

            if not result:
                return None

            # Verify minimum breakout score
            if result['breakout_score'] < self.config['min_breakout_score']:
                self.logger.debug(
                    f"{symbol}: Score too low ({result['breakout_score']:.0f} < {self.config['min_breakout_score']})"
                )
                return None

            # Add RSI check for additional confirmation
            rsi = await self._calculate_rsi(symbol, daily_bars)
            if rsi and not (self.config['rsi_min'] <= rsi <= self.config['rsi_max']):
                self.logger.debug(f"{symbol}: RSI {rsi:.0f} outside range")
                return None

            # Return the consolidation setup
            return result

        except Exception as e:
            self.logger.debug(f"Error analyzing {symbol}: {e}")
            return None

    async def _calculate_rsi(self, symbol: str, daily_bars: List[Dict], period: int = 14) -> Optional[float]:
        """Calculate RSI indicator"""
        try:
            if len(daily_bars) < period + 1:
                return None

            closes = [bar['close'] for bar in daily_bars[-(period+1):]]

            # Calculate price changes
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

            # Separate gains and losses
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]

            # Calculate average gain/loss
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.debug(f"Error calculating RSI for {symbol}: {e}")
            return None

    def _filter_recent_picks(self, consolidations: List[Dict]) -> List[Dict]:
        """
        Filter out symbols picked recently (cooldown period)
        """
        today = datetime.now().date()
        filtered = []

        for setup in consolidations:
            symbol = setup['symbol']

            if symbol in self.recent_picks:
                last_pick = self.recent_picks[symbol]
                days_since = (today - last_pick).days

                if days_since < self.config['cooldown_days']:
                    self.logger.debug(
                        f"⚪ {symbol}: Skipped (picked {days_since} days ago, "
                        f"cooldown: {self.config['cooldown_days']} days)"
                    )
                    continue

            filtered.append(setup)

        return filtered

    def _select_top_setups(self, consolidations: List[Dict], max_picks: int = 2) -> List[Dict]:
        """
        Select top N setups by breakout score
        """
        # Filter by minimum score
        qualified = [
            c for c in consolidations
            if c['breakout_score'] >= self.config['min_breakout_score']
        ]

        if not qualified:
            self.logger.info(f"⚠️ No setups meet minimum score ({self.config['min_breakout_score']})")
            return []

        # Sort by score (descending)
        sorted_setups = sorted(qualified, key=lambda x: x['breakout_score'], reverse=True)

        # Take top N
        top_setups = sorted_setups[:max_picks]

        return top_setups

    def _save_swing_picks(self, setups: List[Dict]):
        """
        Save swing picks to database for next day execution
        """
        today = datetime.now().date()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for setup in setups:
                    symbol = setup['symbol']

                    # Create pending swing trade
                    trade_id = f"SWING_{symbol}_{today.strftime('%Y%m%d')}"

                    cursor.execute("""
                        INSERT OR REPLACE INTO swing_trades (
                            trade_id, symbol, strategy, scan_date,
                            consolidation_days, resistance_level, support_level,
                            breakout_score, pattern_type, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_id,
                        symbol,
                        'swing_consolidation_breakout',
                        today,
                        setup['consolidation_days'],
                        setup['resistance'],
                        setup['support'],
                        setup['breakout_score'],
                        setup['pattern_type'],
                        'PENDING'
                    ))

                    # Update picks cache
                    cursor.execute("""
                        INSERT OR REPLACE INTO swing_picks_cache (
                            symbol, last_pick_date, last_breakout_score, updated_at
                        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """, (symbol, today, setup['breakout_score']))

                    # Update in-memory cache
                    self.recent_picks[symbol] = today

                conn.commit()
                self.logger.info(f"✅ Saved {len(setups)} swing picks to database")

        except Exception as e:
            self.logger.error(f"❌ Error saving swing picks: {e}")

    def get_pending_picks(self) -> List[Dict[str, Any]]:
        """
        Get pending swing picks for today's market open execution

        Returns:
            List of pending swing trades to execute at market open
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get pending picks from yesterday (scan_date = yesterday, status = PENDING)
                yesterday = (datetime.now().date() - timedelta(days=1))

                cursor.execute("""
                    SELECT * FROM swing_trades
                    WHERE scan_date = ? AND status = 'PENDING'
                    ORDER BY breakout_score DESC
                """, (yesterday,))

                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Error fetching pending picks: {e}")
            return []


# Test function
async def test_swing_scanner():
    """Test the swing consolidation scanner"""
    scanner = SwingConsolidationScanner()

    print("🧪 Testing Swing Consolidation Scanner")
    print("=" * 50)

    # Test configuration loading
    print(f"✅ Configuration loaded")
    print(f"   Max positions: {scanner.config['max_positions']}")
    print(f"   Consolidation range: {scanner.config['min_consolidation_days']}-{scanner.config['max_consolidation_days']} days")
    print(f"   Min breakout score: {scanner.config['min_breakout_score']}")

    # Test recent picks loading
    print(f"✅ Recent picks loaded: {len(scanner.recent_picks)}")

    # Test scan (will return empty without IBKR)
    results = await scanner.scan_for_consolidations()
    print(f"✅ Scan completed: {len(results)} setups found")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_swing_scanner())
