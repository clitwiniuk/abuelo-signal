"""Swing Consolidation Scanner

EOD Scanner (14:00 ET):
1. Get smallcap universe from IBKR
2. Filter by config params
3. Fetch 130 days daily data per candidate
4. Detect consolidation patterns
5. Calculate breakout score
6. Apply cooldown filter
7. Select top 4 setups (>40 score)
8. Save to DB for next day execution
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sqlite3
import pandas as pd

from adapters.ibkr_adapter import IBKRAdapter  # Assume exists
from .consolidation_pattern_detector import ConsolidationPatternDetector
from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class SwingConsolidationScanner:
    def __init__(self, config_manager: ConfigManager, ibkr_adapter: IBKRAdapter, db_path: str = "trading_data.db"):
        self.config = config_manager.get_section('SWING_TRADING')
        self.ibkr = ibkr_adapter
        self.db_path = db_path
        self.detector = ConsolidationPatternDetector()
        self.cooldown_days = self.config.get('cooldown_days', 3)
        self.recent_picks = self._load_recent_picks()

    def _load_recent_picks(self) -> Dict:
        """Load recent picks from DB for cooldown"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, last_pick_date FROM swing_picks_cache
                WHERE last_pick_date > date('now', '-{} days')
            """.format(self.cooldown_days))
            picks = {row[0]: datetime.strptime(row[1], '%Y-%m-%d').date() for row in cursor.fetchall()}
            conn.close()
            return picks
        except Exception as e:
            logger.warning(f"Could not load recent picks: {e}")
            return {}

    async def scan_for_consolidations(self) -> List[Dict]:
        """Main scan method"""
        logger.info("🔍 Starting Swing Consolidation Scan")

        # 1. Get universe
        universe = await self._get_scan_universe()

        # 2. Analyze candidates
        candidates = []
        for symbol in universe[:50]:  # Limit for speed
            try:
                df = await self._get_daily_data(symbol)
                if df is None or len(df) < 20:
                    continue
                pattern = self.detector.detect_pattern(df)
                if pattern:
                    pattern['symbol'] = symbol
                    candidates.append(pattern)
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        # 3. Filter cooldown
        available = self._filter_recent_picks(candidates)

        # 4. Sort and select top 4
        top_picks = sorted(available, key=lambda x: x['breakout_score'], reverse=True)[:4]

        # 5. Save to DB
        self._save_picks(top_picks)

        logger.info(f"✅ Scan complete: {len(top_picks)} picks - {[p['symbol'] for p in top_picks]}")
        return top_picks

    async def _get_scan_universe(self) -> List[str]:
        """Get smallcap candidates from IBKR"""
        params = {
            'min_price': self.config.get('min_price', 0.5),
            'max_price': self.config.get('max_price', 25.0),
            'min_avg_volume_90d': self.config.get('min_avg_volume_90d', 10000),
            'min_market_cap': self.config.get('min_market_cap', 1000000),
            'max_market_cap': self.config.get('max_market_cap', 2000000000),
            'max_results': self.config.get('max_results', 200),  # Increase to 200 candidates to find better patterns
        }
        return await self.ibkr.scan_market_for_swing(**params)

    async def _get_daily_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch 130 days daily data"""
        end = datetime.now()
        start = end - timedelta(days=200)  # Extra for safety
        bars = await self.ibkr.get_historical_data(symbol, '1D', start, end)
        if not bars:
            return None
        df = pd.DataFrame(bars)
        df['datetime'] = pd.to_datetime(df['date'])
        df = df.sort_values('datetime').set_index('datetime')
        return df[['open', 'high', 'low', 'close', 'volume']].rename(columns=str.lower)

    def _filter_recent_picks(self, candidates: List[Dict]) -> List[Dict]:
        """Filter recent picks"""
        today = datetime.now().date()
        filtered = []
        for cand in candidates:
            symbol = cand['symbol']
            if symbol in self.recent_picks:
                days_since = (today - self.recent_picks[symbol]).days
                if days_since < self.cooldown_days:
                    logger.info(f"⚪ {symbol}: Cooldown ({days_since}d < {self.cooldown_days}d)")
                    continue
            filtered.append(cand)
        return filtered

    def _save_picks(self, picks: List[Dict]):
        """Save top picks to DB"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables if not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swing_trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                pattern_type TEXT,
                consolidation_days INTEGER,
                resistance_level REAL,
                support_level REAL,
                breakout_score REAL,
                entry_mode TEXT,
                status TEXT DEFAULT 'PENDING',
                scan_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swing_picks_cache (
                symbol TEXT PRIMARY KEY,
                last_pick_date DATE,
                pick_count INTEGER DEFAULT 1
            )
        """)

        today = datetime.now().date()
        for pick in picks:
            # Save trade (Updated to match DB schema)
            cursor.execute("""
                INSERT OR REPLACE INTO swing_trades 
                (symbol, pattern_type, consolidation_days, resistance_level, support_level, breakout_score, scan_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pick['symbol'], pick['pattern_type'], pick['consolidation_days'],
                  pick['resistance'], pick['support'], pick['breakout_score'], today))

            # Update cache
            cursor.execute("""
                INSERT OR REPLACE INTO swing_picks_cache (symbol, last_pick_date, pick_count)
                VALUES (?, ?, COALESCE((SELECT pick_count + 1 FROM swing_picks_cache WHERE symbol = ?), 1))
            """, (pick['symbol'], today, pick['symbol']))

        conn.commit()
        conn.close()