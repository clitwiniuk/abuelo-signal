
"""
scanner/smallcap/proactive_scanner.py

Proactive Scanner - "The Day 0 Detector"
Identifies candidates for future watchlists based on daily chart structure.
Tracks "Green Day 1", "Fake Breakdown", and "Short Squeeze" setups over T+2 to T+7 window.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import json
import pytz

from core.database_manager import DatabaseManager
from scanner.ibkr_native_scanner import IBKRNativeScanner, IBKRScanResult
from adapters.ibkr_adapter import IBKRAdapter
from scanner.smallcap.multi_source_news import MultiSourceNewsChecker, NewsSourceConfig
from scanner.smallcap.catalyst_analyzer import CatalystAnalyzer # NEW: Finbert Analysis

class ProactiveScanner:
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(f"{__name__}.ProactiveScanner")
        self.db_manager = DatabaseManager()
        self.ibkr_adapter = ibkr_adapter or IBKRAdapter()
        self.ibkr_scanner = IBKRNativeScanner(self.ibkr_adapter)
        self.config = config or {}

        # Load ProactiveScanner specific config
        self._load_config()

        # Initialize News Checker
        news_config = NewsSourceConfig(
            max_headlines_per_source=5,
            days_back=4  # Extended to 4 days for Monday weekend lookback
        )
        self.news_checker = MultiSourceNewsChecker(news_config)
        
        # Initialize Catalyst Analyzer (Finbert)
        self.catalyst_analyzer = CatalystAnalyzer()

    def _load_config(self):
        """Load configuration from [PROACTIVE_SCANNER] section"""
        # Helper to get config values (supports both ConfigParser and dict)
        def get_config_value(key, default, value_type=str):
            """Get config value with type conversion"""
            try:
                if hasattr(self.config, 'has_section'):
                    # ConfigParser object
                    if self.config.has_section('PROACTIVE_SCANNER'):
                        if value_type == bool:
                            val = self.config.getboolean('PROACTIVE_SCANNER', key, fallback=default)
                            # print(f"DEBUG CONFIG: {key} = {val} (from configparser)")
                            return val
                        elif value_type == int:
                            return self.config.getint('PROACTIVE_SCANNER', key, fallback=default)
                        elif value_type == float:
                            return self.config.getfloat('PROACTIVE_SCANNER', key, fallback=default)
                        else:
                            return self.config.get('PROACTIVE_SCANNER', key, fallback=default)
                else:
                    # Dict object
                    scanner_config = self.config.get('PROACTIVE_SCANNER', {})
                    return scanner_config.get(key, default)
            except:
                return default

        # Pattern Filters
        self.min_price = get_config_value('min_price', 1.0, float)
        self.max_price = get_config_value('max_price', 10.0, float)
        self.min_rel_vol = get_config_value('min_rel_vol', 3.0, float)
        self.min_gain_pct = get_config_value('min_gain_pct', 20.0, float)
        self.max_gain_pct = get_config_value('max_gain_pct', 150.0, float)
        self.min_retention_pct = get_config_value('min_retention_pct', 45.0, float)

        # Catalyst Configuration
        # CRITICAL: Default to True to enforce "Causality" (Volume must be explained)
        self.catalyst_required = get_config_value('catalyst_required', True, bool)
        self.min_quality_score = get_config_value('min_quality_score', 50.0, float)
        self.min_quality_score_no_catalyst = get_config_value('min_quality_score_no_catalyst', 65.0, float)

        # Catalyst Age Logic
        self.catalyst_max_age_weekday = get_config_value('catalyst_max_age_weekday', 30, int)
        self.catalyst_max_age_monday = get_config_value('catalyst_max_age_monday', 84, int)

        # Catalyst Type Specific Ages
        self.catalyst_max_age_fda = get_config_value('catalyst_max_age_fda', 168, int)
        self.catalyst_max_age_earnings = get_config_value('catalyst_max_age_earnings', 72, int)
        self.catalyst_max_age_ma = get_config_value('catalyst_max_age_ma', 48, int)
        self.catalyst_max_age_contract = get_config_value('catalyst_max_age_contract', 48, int)
        self.catalyst_max_age_breakthrough = get_config_value('catalyst_max_age_breakthrough', 48, int)
        self.catalyst_max_age_other = get_config_value('catalyst_max_age_other', 30, int)

        # Catalyst Strength
        self.min_catalyst_strength = get_config_value('min_catalyst_strength', 3, int)

        # Borrows
        self.require_short_interest_check = get_config_value('require_short_interest_check', True, bool)
        self.prefer_htb = get_config_value('prefer_htb', True, bool)

        # Volume
        self.min_avg_volume = get_config_value('min_avg_volume', 100000, int)
        self.min_dollar_volume = get_config_value('min_dollar_volume', 200000, int)

        # Scanning Schedule
        self.run_premarket = get_config_value('run_premarket', True, bool)
        self.run_during_market = get_config_value('run_during_market', False, bool)
        self.run_postmarket = get_config_value('run_postmarket', True, bool)

        self.logger.info(f"📋 ProactiveScanner Config Loaded:")
        self.logger.info(f"   Catalyst Required: {self.catalyst_required}")
        self.logger.info(f"   Min Quality (with catalyst): {self.min_quality_score}")
        self.logger.info(f"   Min Quality (no catalyst): {self.min_quality_score_no_catalyst}")
        self.logger.info(f"   Max Age Weekday: {self.catalyst_max_age_weekday}h")
        self.logger.info(f"   Max Age Monday: {self.catalyst_max_age_monday}h")
        self.logger.info(f"   Run Premarket: {self.run_premarket}")
        self.logger.info(f"   Run During Market: {self.run_during_market}")
        self.logger.info(f"   Run Postmarket: {self.run_postmarket}")

    def _get_max_catalyst_age_hours(self, catalyst_type: Optional[str] = None) -> float:
        """
        Get maximum catalyst age in hours based on current day of week and catalyst type.

        Logic:
        - Martes-Viernes: Noticias del día anterior (30h)
        - Lunes: Noticias del fin de semana (84h para viernes/sábado/domingo)
        - Catalizadores fuertes (FDA, Earnings): Más tiempo permitido

        Returns:
            Max age in hours
        """
        now = datetime.now()
        weekday = now.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday

        # Base age based on day of week
        if weekday == 0:  # Monday
            base_age = self.catalyst_max_age_monday  # 84h (permite viernes, sábado, domingo)
        else:  # Tuesday-Friday
            base_age = self.catalyst_max_age_weekday  # 30h (permite día anterior)

        # If catalyst type is strong, use extended age
        if catalyst_type:
            catalyst_type_lower = catalyst_type.lower()

            if 'fda' in catalyst_type_lower or 'approval' in catalyst_type_lower:
                type_age = self.catalyst_max_age_fda
            elif 'earning' in catalyst_type_lower or 'eps' in catalyst_type_lower:
                type_age = self.catalyst_max_age_earnings
            elif 'merger' in catalyst_type_lower or 'acquisition' in catalyst_type_lower or 'm&a' in catalyst_type_lower:
                type_age = self.catalyst_max_age_ma
            elif 'contract' in catalyst_type_lower or 'deal' in catalyst_type_lower:
                type_age = self.catalyst_max_age_contract
            elif 'breakthrough' in catalyst_type_lower or 'clinical' in catalyst_type_lower:
                type_age = self.catalyst_max_age_breakthrough
            else:
                type_age = self.catalyst_max_age_other

            # Use the MAXIMUM of base_age and type_age
            # This allows strong catalysts to be valid longer
            return max(base_age, type_age)

        return base_age

    def should_run_now(self) -> bool:
        """
        Check if scanner should run based on current time and config.

        Returns:
            True if scanner should run, False otherwise
        """
        if not self.config:
             return False

        # Get current ET time
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        current_hour = now_et.hour
        current_minute = now_et.minute

        # Market hours: 9:30 - 16:00 ET
        is_premarket = current_hour < 9 or (current_hour == 9 and current_minute < 30)
        is_postmarket = current_hour >= 16
        is_market_hours = not is_premarket and not is_postmarket

        # Check if we should run
        if is_premarket and self.run_premarket:
            self.logger.info(f"⏰ Premarket scan enabled - Running at {now_et.strftime('%H:%M')} ET")
            return True
        elif is_market_hours and self.run_during_market:
            self.logger.info(f"⏰ Market hours scan enabled - Running at {now_et.strftime('%H:%M')} ET")
            return True
        elif is_market_hours and not self.run_during_market:
            self.logger.debug(f"⏸️ Market hours ({now_et.strftime('%H:%M')} ET) - Scanner paused")
            return False
        elif is_postmarket and self.run_postmarket:
            self.logger.info(f"⏰ Postmarket scan enabled - Running at {now_et.strftime('%H:%M')} ET")
            return True

        return False

    async def scan_and_update_watchlist(self):
        """
        Main entry point:
        1. Check if we should run based on schedule (premarket/postmarket)
        2. Reuse IBKR Native Scanner to find active smallcap universe.
        3. Filter for specific 'Proactive' patterns (Day 0).
        4. Save new candidates to DB.
        5. Update status of existing candidates (Day 1-7).
        """
        # Check if we should run now
        if not self.should_run_now():
            return

        self.logger.info("🚀 Starting Proactive Scanner...")

        # 1. Daily Maintenance: Update days_since_detection and expire old candidates
        # CRITICAL: Do this FIRST, before scanning for new candidates
        self._update_candidate_days_and_expire()

        # 2. Get Universe (Active Smallcaps)
        # We use a broad scan to find anything moving today
        candidates = await self.ibkr_scanner.scan_daily_plays(max_results=200)

        # 3. Analyze and save NEW candidates (if any found)
        new_candidates = []
        if candidates:
            self.logger.info(f"📊 Analyzing {len(candidates)} candidates for Proactive Patterns...")

            for result in candidates:
                pattern = await self._analyze_daily_structure(result)
                if pattern:
                    new_candidates.append(pattern)
                    self.logger.info(f"✨ Found Candidate: {result.symbol} - {pattern['pattern_type']}")

            # Save new candidates to database
            self._save_candidates(new_candidates)
        else:
            self.logger.warning("No new candidates found from IBKR Scanner.")

        # 4. Monitor Existing Watchlist (Day 1-7 Monitoring)
        # CRITICAL: Always run this, even if no new candidates found
        await self._monitor_existing_candidates()
        
    async def _analyze_daily_structure(self, result: IBKRScanResult) -> Optional[Dict]:
        """Analyze daily structure for the given result"""
        symbol = result.symbol
        try:
            # Fetch daily bars (at least 20 days for context)
            bars = await self.ibkr_adapter.get_bars(symbol, '1 day', 30)
            if not bars or len(bars) < 5:
                # Fallback to result's daily change if bars fail
                return None
                
            df = pd.DataFrame([{
                'date': b.timestamp,  # MarketData uses 'timestamp', not 'date'
                'open': b.open,
                'high': b.high,
                'low': b.low,
                'close': b.close,
                'volume': b.volume
            } for b in bars])
            
            # Pattern 1: Green Day 1
            if self._is_green_day_1(df):
                # Calculate metrics FIRST to pass context to Catalyst Analyzer
                rel_vol = self._calculate_daily_rel_vol(df)
                change_pct = ((df.iloc[-1]['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close']) * 100
                
                # Apply additional filters for quality
                # 1. News Catalyst (Finbert with Context)
                # We pass change_pct as 'gap_pct' proxy and rel_vol as volume_ratio
                has_catalyst, catalyst_type, news_age = await self._check_news_catalyst(
                    symbol, 
                    gap_pct=change_pct, 
                    volume_ratio=rel_vol
                )

                # If catalyst is required and not found, reject
                if self.catalyst_required and not has_catalyst:
                    self.logger.debug(f"❌ {symbol}: Rejected - Catalyst required but not found")
                    return None

                # If no catalyst, we'll need higher quality score (checked later)
                if not has_catalyst:
                    self.logger.info(f"⚠️ {symbol}: No catalyst - will require higher quality score ({self.min_quality_score_no_catalyst})")

                # 2. Borrow Availability
                # CRITICAL: Day 0 must be ETB (Easy To Borrow). 
                # If it's already HTB/None, we are late to the party.
                borrows_ok, quality = await self._check_ibkr_borrows(symbol)
                
                if quality != 'NORMAL':
                    self.logger.info(f"💎 {symbol}: Accepted - HTB/No Borrows ({quality}) detected on Day 0. Strong Squeeze Potential.")
                    # return None # REMOVED: Now we WANT these candidates
                    
                if not borrows_ok:
                    self.logger.debug(f"❌ {symbol}: Rejected - Borrow check failed error")
                    return None
                
                # Calculate quality score
                # Simple quality score (0-100)
                quality_score = 0.0
                quality_score += min(rel_vol * 10, 30)  # Max 30 points for volume (3x = 30 pts)
                quality_score += min(change_pct * 0.5, 30)  # Max 30 points for gain (60% = 30 pts)
                
                # SQUEEZE BONUSES:
                if quality == 'ULTIMATE': # No Borrows
                    quality_score += 30 # MAXIMUM BONUS
                elif quality == 'IDEAL': # HTB
                    quality_score += 20 # HIGH BONUS
                else: # NORMAL (ETB)
                    quality_score += 10 # Base points for valid ETB
                
                quality_score += 20 if has_catalyst else 0  # 20 points bonus for catalyst

                # Apply quality threshold
                min_quality_threshold = self.min_quality_score if has_catalyst else self.min_quality_score_no_catalyst

                if quality_score < min_quality_threshold:
                    self.logger.debug(
                        f"❌ {symbol}: Quality score too low ({quality_score:.1f} < {min_quality_threshold})"
                    )
                    return None

                self.logger.info(f"✅ {symbol}: GREEN_DAY_1 - Quality: {quality_score:.1f}/100")

                return {
                    'symbol': symbol,
                    'pattern_type': 'GREEN_DAY_1',
                    'detection_date': datetime.now().date(),
                    'metrics': {
                        'rel_vol': rel_vol,
                        'close': df.iloc[-1]['close'],
                        'volume': int(df.iloc[-1]['volume']),
                        'change_pct': change_pct,
                        'squeeze_quality': quality,
                        'quality_score': quality_score,
                        'has_catalyst': has_catalyst,
                        'catalyst_type': catalyst_type,
                        'catalyst_age_hours': news_age
                    },
                    'key_levels': {
                        'day1_high': df.iloc[-1]['high'],
                        'day1_low': df.iloc[-1]['low'],
                        'resistance': self._find_resistance(df)
                    }
                }
            
            # Pattern 2: Fake Breakdown Reversal
            if self._is_fake_breakdown(df):
                return {
                    'symbol': symbol,
                    'pattern_type': 'FAKE_BREAKDOWN',
                    'detection_date': datetime.now().date(),
                    'metrics': {
                        'rel_vol': self._calculate_daily_rel_vol(df),
                        'close': df.iloc[-1]['close']
                    },
                    'key_levels': {
                        'reclaimed_support': df.iloc[-1]['low'], # Approx
                        'resistance': self._find_resistance(df)
                    }
                }

            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing structure for {symbol}: {e}")
            return None

    def _is_green_day_1(self, df: pd.DataFrame) -> bool:
        """
        Refined Criteria:
        1. Today is Green (Close > Open).
        2. High Relative Volume (> 3x).
        3. Gain between 20% and 120% (indicative upper bound).
        4. Price Retention > 50% (Close >= (High + PrevClose) / 2).
        """
        if len(df) < 2:
            return False
            
        current = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # 1. Green candle
        if current['close'] <= current['open']:
            return False
            
        # 2. Rel Vol
        rel_vol = self._calculate_daily_rel_vol(df)
        if rel_vol < 3.0:
            # Fallback for short history
            if len(df) < 11 and current['volume'] > yesterday['volume'] * 3.0:
                pass
            else:
                return False

        # 2b. Minimum Volume (Liquid runners only)
        # > 4 Million shares to ensure strong institutional/retail participation
        if current['volume'] < 4_000_000:
            return False
            
        # 3. % Gain (20% to 120% approx)
        prev_close = yesterday['close']
        if prev_close == 0: return False
        pct_gain = (current['close'] - prev_close) / prev_close * 100
        
        # Floor is strict (20%)
        if pct_gain < 20.0:
            return False
            
        # Ceiling is flexible (indicative 120%)
        if pct_gain > 150.0: # Irrational move limit
            return False
            
        # 4. Price Retention (indicative 50%)
        # Retention = (Close - PrevClose) / (High - PrevClose)
        day_range = current['high'] - prev_close
        if day_range > 0:
            retention = (current['close'] - prev_close) / day_range
            if retention < 0.45: # 50% target with 5% margin
                return False
            
        # 5. Day 1 Check
        if len(df) >= 3:
            day_before_yesterday = df.iloc[-3]
            if day_before_yesterday['close'] > 0:
                yest_gain = (yesterday['close'] - day_before_yesterday['close']) / day_before_yesterday['close'] * 100
                if yest_gain > 5.0: # Already running
                    return False
            
        return True

    async def _check_news_catalyst(self, symbol: str, gap_pct: float = 0.0, volume_ratio: float = 0.0) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Check for news catalyst using CatalystAnalyzer (Finbert).

        Args:
            symbol: Ticker symbol
            gap_pct: Percentage gap (Context for sentiment validation)
            volume_ratio: Relative volume (Context for sentiment validation)

        Returns:
            (has_valid_catalyst, catalyst_type, news_age_hours)
        """
        try:
            # MultiSourceNewsChecker.get_news_for_symbols returns Dict[symbol, List[Tuple[headline, age_hours]]]
            news_dict = await self.news_checker.get_news_for_symbols([symbol])

            if not news_dict or symbol not in news_dict:
                return False, None, None

            # Get headlines for this symbol (List of tuples: (headline, age_hours))
            headlines = news_dict.get(symbol, [])
            if len(headlines) == 0:
                return False, None, None

            # CRITICAL: Use Finbert Analyzer to detect powerful catalysts
            # analyze_multiple_headlines finds the strongest catalyst in the list
            catalyst_info = self.catalyst_analyzer.analyze_multiple_headlines(
                headlines, 
                gap_pct=gap_pct, 
                volume_ratio=volume_ratio
            )
            
            if not catalyst_info:
                return False, None, None
                
            # Check strength threshold
            if catalyst_info.strength >= self.min_catalyst_strength:
                self.logger.info(
                    f"✅ {symbol}: Valid Finbert Catalyst - Type: {catalyst_info.catalyst_type}, "
                    f"Strength: {catalyst_info.strength}/10, Age: {catalyst_info.age_hours:.1f}h"
                )
                return True, catalyst_info.catalyst_type, catalyst_info.age_hours
            else:
                self.logger.debug(
                    f"⚠️ {symbol}: Weak Catalyst - Strength {catalyst_info.strength} < {self.min_catalyst_strength}"
                )
                return False, catalyst_info.catalyst_type, catalyst_info.age_hours

        except Exception as e:
            self.logger.error(f"Error checking news for {symbol}: {e}", exc_info=True)
            return False, None, None

    def _detect_catalyst_type(self, headline: str) -> Optional[str]:
        """Detect catalyst type from headline text"""
        headline_lower = headline.lower()

        if any(word in headline_lower for word in ['fda', 'approval', 'approved', 'clearance']):
            return 'FDA'
        elif any(word in headline_lower for word in ['earning', 'earnings', 'eps', 'revenue']):
            return 'EARNINGS'
        elif any(word in headline_lower for word in ['merger', 'acquisition', 'acquire', 'm&a', 'buyout']):
            return 'M&A'
        elif any(word in headline_lower for word in ['contract', 'deal', 'partnership', 'agreement']):
            return 'CONTRACT'
        elif any(word in headline_lower for word in ['breakthrough', 'clinical', 'trial', 'study']):
            return 'BREAKTHROUGH'
        else:
            return 'OTHER'

    async def _check_ibkr_borrows(self, symbol: str) -> Tuple[bool, str]:
        """
        Check borrow availability. 
        Returns (is_valid, quality_string)
        """
        try:
            data = await self.ibkr_adapter.get_short_data(symbol)
            status = data.get('short_status', 'NONE')
            shares = data.get('shortable_shares', 0)
            
            if status == 'NONE' or shares == 0:
                self.logger.info(f"💎 {symbol}: ULTIMATE Squeeze Potential - Zero borrows available")
                return True, 'ULTIMATE'
            elif status == 'HTB':
                self.logger.info(f"🔥 {symbol}: IDEAL Squeeze Potential - Hard to Borrow")
                return True, 'IDEAL'
            else:
                self.logger.info(f"✅ {symbol}: Normal Squeeze Potential - Easy to Borrow")
                return True, 'NORMAL'
                
        except Exception as e:
            self.logger.error(f"Error checking borrows for {symbol}: {e}")
            return True, 'NORMAL' # Default to NORMAL if check fails

    def _is_fake_breakdown(self, df: pd.DataFrame) -> bool:
        """
        Criteria:
        1. Today made a new low (vs recent support) but closed strong.
        2. Long lower wick (Hammer-like).
        """
        if len(df) < 5:
            return False

        # VOLUME CHECK: Filter out low volume noise (e.g. MSTX 0.49x)
        rel_vol = self._calculate_daily_rel_vol(df)
        if rel_vol < 3.0:
            return False

            
        current = df.iloc[-1]
        
        # 1. Price Floor Check (> $0.50)
        if current['close'] < 0.50:
            return False

        # 2. Green Candle Check (Buyers won the day)
        if current['close'] <= current['open']:
            return False

        # 3. Wick Structure Check (Long lower tail)
        # For a green candle, body_bottom is open
        body_bottom = current['open']
        lower_wick = body_bottom - current['low']
        candle_range = current['high'] - current['low']
        
        # Wick must be distinct (>= 30% of range)
        if candle_range > 0:
            if (lower_wick / candle_range) < 0.3:
                return False
        else:
            return False # Zero range candle? Skip.

        
        # Find recent support (min low of last 10 days excluding today, or whatever we have)
        lookback = min(10, len(df) - 1)
        recent_lows = df.iloc[-(lookback+1):-1]['low'].min()
        
        # Did we break it?
        if current['low'] < recent_lows:
            # Did we close above it? (Reclaim)
            if current['close'] > recent_lows:
                # Close must be in upper half of range
                candle_range = current['high'] - current['low']
                if candle_range > 0:
                    pos = (current['close'] - current['low']) / candle_range
                    if pos > 0.6: # Upper 40%
                        return True
                
        return False
        
    def _calculate_daily_rel_vol(self, df: pd.DataFrame) -> float:
        """Calculate relative volume vs 10-day average"""
        if len(df) < 11:
            return 1.0
        
        current_vol = df.iloc[-1]['volume']
        avg_vol = df.iloc[-11:-1]['volume'].mean()
        
        return current_vol / avg_vol if avg_vol > 0 else 1.0
    
    def _find_resistance(self, df: pd.DataFrame) -> float:
        """Simple resistance finder: Max high of last 10 days"""
        return df.iloc[-10:]['high'].max()

    def _save_candidates(self, candidates: List[Dict[str, Any]]):
        """Save new candidates to DB"""
        if not candidates:
            return
            
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                for c in candidates:
                    # Check if already exists for today
                    exists = conn.execute(
                        "SELECT id FROM proactive_candidates WHERE symbol = ? AND detection_date = ?",
                        (c['symbol'], c['detection_date'])
                    ).fetchone()
                    
                    if not exists:
                        conn.execute("""
                            INSERT INTO proactive_candidates (
                                symbol, detection_date, pattern_type, status, metrics, key_levels, days_since_detection, last_check_time
                            ) VALUES (?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
                        """, (
                            c['symbol'],
                            c['detection_date'],
                            c['pattern_type'],
                            'WATCHING',
                            json.dumps(c['metrics']),
                            json.dumps(c['key_levels'])
                        ))
                conn.commit()
                self.logger.info(f"💾 Saved {len(candidates)} new candidates to DB")
        except Exception as e:
            self.logger.error(f"Error saving candidates: {e}")

    async def _monitor_existing_candidates(self):
        """
        Monitor existing candidates (Day 1 - Day 7) for:
        1. Update resistance levels when new daily highs are made
        2. Detect daily structure (HIGHER_HIGH, INSIDE_DAY, LOWER_HIGH)
        3. Update key_levels with day-specific highs (day2_high, day3_high, etc.)

        This ensures workers have current resistance levels, not stale Day 0 levels.
        """
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Get active candidates detected in last 7 days
                rows = conn.execute("""
                    SELECT * FROM proactive_candidates
                    WHERE status IN ('WATCHING', 'TRIGGERED')
                    AND detection_date >= date('now', '-7 days')
                """).fetchall()

            if not rows:
                return

            self.logger.info(f"👀 Monitoring {len(rows)} watchlist candidates for daily updates...")

            updated_count = 0
            for row in rows:
                symbol = row['symbol']
                days_since = row['days_since_detection']
                key_levels = json.loads(row['key_levels']) if row['key_levels'] else {}

                # Skip if no day1_high (shouldn't happen but defensive)
                if 'day1_high' not in key_levels:
                    self.logger.warning(f"{symbol}: Missing day1_high, skipping")
                    continue

                try:
                    # Fetch last 10 days of daily bars to analyze structure
                    bars = await self.ibkr_adapter.get_bars(
                        symbol=symbol,
                        timeframe='1d',
                        count=10,
                        end_date=None  # Now
                    )

                    if not bars or len(bars) < 2:
                        self.logger.debug(f"{symbol}: Insufficient daily bars ({len(bars) if bars else 0})")
                        continue

                    # Analyze yesterday's daily candle (last complete bar)
                    yesterday_bar = bars[-2] if len(bars) >= 2 else bars[-1]
                    today_bar = bars[-1]  # Today's incomplete bar

                    # --- DYNAMIC BORROW CHECK (Crucial for Squeeze Thesis) ---
                    # We check if shares have become harder to borrow (ETB -> HTB -> NONE)
                    borrows_ok, current_quality = await self._check_ibkr_borrows(symbol)
                    
                    # Update metrics with current borrow status
                    metrics = json.loads(row['metrics']) if row['metrics'] else {}
                    old_quality = metrics.get('squeeze_quality', 'UNKNOWN')
                    metrics['squeeze_quality'] = current_quality # Update current status
                    metrics['previous_squeeze_quality'] = old_quality # Track history
                    
                    if old_quality != current_quality:
                        self.logger.info(f"🔄 {symbol}: Borrow Status Changed: {old_quality} -> {current_quality}")
                    
                    # Update resistance and daily structure
                    updated = await self._update_candidate_levels(
                        symbol=symbol,
                        days_since=days_since,
                        key_levels=key_levels,
                        metrics=metrics, # Pass updated metrics
                        yesterday_bar=yesterday_bar,
                        today_bar=today_bar,
                        historical_bars=bars[:-1]  # Last 9 complete days
                    )

                    if updated:
                        updated_count += 1

                except Exception as e:
                   self.logger.error(f"Error monitoring {symbol}: {e}")
                   import traceback
                   traceback.print_exc()

            if updated_count > 0:
                self.logger.info(f"✅ Updated {updated_count}/{len(rows)} candidates with new levels/structure")

        except Exception as e:
            self.logger.error(f"Error monitoring candidates: {e}")
            import traceback
            traceback.print_exc()

    async def _update_candidate_levels(
        self,
        symbol: str,
        days_since: int,
        key_levels: Dict,
        metrics: Dict,
        yesterday_bar: Any,
        today_bar: Any,
        historical_bars: List
    ) -> bool:
        """
        Update candidate key_levels with:
        1. New resistance if yesterday broke previous high
        2. Day-specific high (day2_high, day3_high, etc.)
        3. Daily structure (HIGHER_HIGH, INSIDE_DAY, LOWER_HIGH)
        4. Update metrics (Borrow Status)

        Returns True if levels were updated in DB.
        """
        try:
            updated = False
            current_resistance = key_levels.get('resistance', key_levels.get('day1_high', 0))
            day1_high = key_levels.get('day1_high', 0)

            # Analyze daily structure
            daily_structure = self._classify_structure_type(
                yesterday_bar=yesterday_bar,
                previous_high=current_resistance,
                day1_high=day1_high
            )

            # Check if yesterday made a new high
            yesterday_high = float(yesterday_bar.high)
            if yesterday_high > current_resistance:
                # Update resistance to new high
                key_levels['resistance'] = yesterday_high
                self.logger.info(
                    f"📈 {symbol} (Day {days_since}): NEW HIGH! "
                    f"Resistance ${current_resistance:.2f} → ${yesterday_high:.2f} ({daily_structure})"
                )
                updated = True

            # Add day-specific high (day2_high, day3_high, etc.) if not already stored
            day_key = f"day{days_since}_high"
            if day_key not in key_levels and days_since > 0:
                key_levels[day_key] = yesterday_high
                self.logger.debug(f"{symbol}: Stored {day_key} = ${yesterday_high:.2f}")
                updated = True

            # Store daily structure
            if key_levels.get('daily_structure') != daily_structure:
                key_levels['daily_structure'] = daily_structure
                updated = True

            # Check if metrics changed (Borrow Status update from caller)
            # We assume if metrics are passed, they might have changed
            if metrics:
                 # Check against DB state if we wanted to be super optimized, but rewriting is safe
                 updated = True 

            # Update database if changes were made
            if updated:
                with sqlite3.connect(self.db_manager.db_path) as conn:
                    conn.execute("""
                        UPDATE proactive_candidates
                        SET key_levels = ?, metrics = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE symbol = ?
                    """, (json.dumps(key_levels), json.dumps(metrics), symbol))
                    conn.commit()

                self.logger.info(
                    f"✅ {symbol} (Day {days_since}): Updated levels - "
                    f"Resistance: ${key_levels['resistance']:.2f}, Structure: {daily_structure}"
                )

            return updated

        except Exception as e:
            self.logger.error(f"Error updating levels for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _classify_structure_type(
        self,
        yesterday_bar: Any,
        previous_high: float,
        day1_high: float
    ) -> str:
        """
        Analyze yesterday's daily candle structure relative to previous levels.

        Returns:
        - BREAKOUT: Broke Day 1 High by >1% (only on first break)
        - HIGHER_HIGH: Made new high above previous resistance (continuation)
        - INSIDE_DAY: Consolidation (high <= previous high)
        - LOWER_HIGH: Weakness (high > previous but below day1_high threshold)
        """
        try:
            yesterday_high = float(yesterday_bar.high)
            yesterday_low = float(yesterday_bar.low)

            # PRIORITY 1: Check if made higher high (broke previous resistance)
            if yesterday_high > previous_high * 1.005:  # >0.5% above previous
                # Check if this is first break of Day 1 High (BREAKOUT is special)
                if previous_high == day1_high and yesterday_high > day1_high * 1.01:
                    return "BREAKOUT"  # First break of Day 1 High
                else:
                    return "HIGHER_HIGH"  # Continuation, making new highs

            # PRIORITY 2: Inside day (consolidation)
            elif yesterday_high <= previous_high:
                return "INSIDE_DAY"

            # PRIORITY 3: Lower high (made some progress but not enough)
            else:
                return "LOWER_HIGH"

        except Exception as e:
            self.logger.warning(f"Error analyzing daily structure: {e}")
            return "UNKNOWN"

    def _update_candidate_days_and_expire(self):
        """
        Daily maintenance task:
        1. Update days_since_detection for all active candidates
        2. Mark candidates as EXPIRED if detection_date > 7 days ago

        This enables post-trade analysis to correlate:
        - Win rate by days_since_detection (Day 1 vs Day 3 vs Day 6)
        - Pattern quality vs actual squeeze success
        - Expiration tracking for analytics
        """
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # 1. Update days_since_detection for active candidates
                updated = conn.execute("""
                    UPDATE proactive_candidates
                    SET days_since_detection = CAST(JULIANDAY(date('now')) - JULIANDAY(detection_date) AS INTEGER)
                    WHERE status IN ('WATCHING', 'TRIGGERED')
                """).rowcount

                if updated > 0:
                    self.logger.debug(f"📅 Updated days_since_detection for {updated} candidates")

                # 2. Mark expired candidates (> 7 days old, not yet traded)
                expired = conn.execute("""
                    UPDATE proactive_candidates
                    SET status = 'EXPIRED'
                    WHERE status = 'WATCHING'
                    AND detection_date < date('now', '-7 days')
                """).rowcount

                if expired > 0:
                    self.logger.info(f"⏰ Marked {expired} candidates as EXPIRED (> 7 days)")

                conn.commit()

        except Exception as e:
            self.logger.error(f"Error updating candidate days/expiration: {e}")

# Needed for database access
import sqlite3
