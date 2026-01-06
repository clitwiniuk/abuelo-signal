#!/usr/bin/env python3
"""
Learning and Feedback System Test Suite
Tests the ML learning capabilities and feedback mechanisms
"""

import sys
import os
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
import random

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scanner.scanner_intelligence import (
    ScannerIntelligence, ScannerConfig, TradingResult, 
    SentimentType, CatalystType, NewsAnalysis
)

logger = logging.getLogger("LearningFeedbackTest")
logging.basicConfig(level=logging.INFO)

class LearningFeedbackSystemTest:
    """Comprehensive test for learning and feedback system"""
    
    def __init__(self):
        self.test_db = "test_learning_feedback.db"
        self.intelligence = ScannerIntelligence(self.test_db)
        self.test_results = []
        
        # Create realistic test data
        self.historical_scenarios = self._create_historical_scenarios()
    
    def _create_historical_scenarios(self):
        """Create realistic historical trading scenarios for learning"""
        scenarios = [
            # FDA Approvals - Generally profitable
            {
                "news": "FDA grants breakthrough therapy designation for cancer treatment",
                "sentiment": SentimentType.POSITIVE,
                "catalyst": CatalystType.FDA,
                "trades": [
                    {"pnl": 500, "duration": 45, "profitable": True},
                    {"pnl": 300, "duration": 30, "profitable": True},
                    {"pnl": -100, "duration": 15, "profitable": False},
                    {"pnl": 700, "duration": 60, "profitable": True}
                ]
            },
            # Earnings Beats - Mixed results
            {
                "news": "Company beats earnings expectations, revenue up 150%",
                "sentiment": SentimentType.POSITIVE,
                "catalyst": CatalystType.EARNINGS,
                "trades": [
                    {"pnl": 200, "duration": 25, "profitable": True},
                    {"pnl": -150, "duration": 20, "profitable": False},
                    {"pnl": 350, "duration": 40, "profitable": True},
                    {"pnl": 100, "duration": 30, "profitable": True},
                    {"pnl": -200, "duration": 10, "profitable": False}
                ]
            },
            # Mergers - Highly profitable but rare
            {
                "news": "Company announces acquisition deal at premium valuation",
                "sentiment": SentimentType.POSITIVE,
                "catalyst": CatalystType.MERGER,
                "trades": [
                    {"pnl": 800, "duration": 90, "profitable": True},
                    {"pnl": 600, "duration": 120, "profitable": True},
                    {"pnl": 400, "duration": 60, "profitable": True}
                ]
            },
            # Negative FDA news - Generally unprofitable
            {
                "news": "FDA rejects drug application due to safety concerns",
                "sentiment": SentimentType.NEGATIVE,
                "catalyst": CatalystType.FDA,
                "trades": [
                    {"pnl": -300, "duration": 10, "profitable": False},
                    {"pnl": -500, "duration": 5, "profitable": False},
                    {"pnl": -200, "duration": 15, "profitable": False}
                ]
            },
            # Partnerships - Moderately profitable
            {
                "news": "Strategic partnership with major pharma company announced",
                "sentiment": SentimentType.POSITIVE,
                "catalyst": CatalystType.PARTNERSHIP,
                "trades": [
                    {"pnl": 150, "duration": 35, "profitable": True},
                    {"pnl": 250, "duration": 50, "profitable": True},
                    {"pnl": -50, "duration": 20, "profitable": False},
                    {"pnl": 300, "duration": 45, "profitable": True}
                ]
            }
        ]
        
        return scenarios
    
    def populate_historical_data(self):
        """Populate database with historical learning data"""
        logger.info("🔧 Populating historical data for learning...")
        
        ticker_counter = 1
        
        for scenario in self.historical_scenarios:
            # Generate unique tickers for each scenario
            for trade_data in scenario["trades"]:
                ticker = f"LEARN{ticker_counter:03d}"
                ticker_counter += 1
                
                # Add news analysis
                analysis = NewsAnalysis(
                    ticker=ticker,
                    date=date.today() - timedelta(days=random.randint(1, 30)),
                    sentiment=scenario["sentiment"],
                    catalyst_type=scenario["catalyst"],
                    confidence_score=random.uniform(0.6, 0.9),
                    impact_score=random.uniform(0.7, 1.0),
                    keywords=["test", "learning"],
                    source_text=scenario["news"]
                )
                
                self.intelligence._store_news_analysis(analysis)
                
                # Add trading result
                trade_result = TradingResult(
                    ticker=ticker,
                    trade_date=analysis.date,
                    entry_price=random.uniform(5, 20),
                    exit_price=None if trade_data["pnl"] < 0 else random.uniform(5, 25),
                    pnl=trade_data["pnl"],
                    was_profitable=trade_data["profitable"],
                    hold_duration_minutes=trade_data["duration"],
                    strategy_used="ml_multi_strategy",
                    notes=f"Learning test - {scenario['catalyst'].value}"
                )
                
                self.intelligence.add_trading_result(trade_result)
        
        logger.info(f"   ✅ Added {ticker_counter-1} historical scenarios")
    
    def test_pattern_learning(self):
        """Test 1: Pattern Learning from Historical Data"""
        logger.info("🧪 Test 1: Pattern Learning from Historical Data")
        
        # Get learning stats before and after pattern updates
        stats_before = self.intelligence.get_learning_stats()
        
        # Force pattern update
        self.intelligence._update_learned_patterns()
        
        stats_after = self.intelligence.get_learning_stats()
        
        # Check if patterns were learned
        patterns_learned = len(stats_after.get('best_patterns', [])) > 0
        learning_active = stats_after.get('learning_active', False)
        
        logger.info(f"   Learning active: {'✅' if learning_active else '❌'}")
        logger.info(f"   Patterns learned: {'✅' if patterns_learned else '❌'}")
        logger.info(f"   Total trades: {stats_after.get('total_trades', 0)}")
        logger.info(f"   Win rate: {stats_after.get('win_rate', 0):.1f}%")
        
        # Analyze best patterns
        best_patterns = stats_after.get('best_patterns', [])
        if best_patterns:
            logger.info(f"   Best patterns found: {len(best_patterns)}")
            for i, pattern in enumerate(best_patterns[:3]):
                pattern_type, success_rate, confidence, sample_size = pattern
                logger.info(f"      {i+1}. {pattern_type}: {success_rate:.1%} success ({sample_size} samples)")
        
        self.test_results.append({
            'test': 'pattern_learning',
            'passed': learning_active and patterns_learned,
            'learning_active': learning_active,
            'patterns_count': len(best_patterns),
            'total_trades': stats_after.get('total_trades', 0)
        })
    
    def test_ml_score_evolution(self):
        """Test 2: ML Score Evolution with Learning"""
        logger.info("🧪 Test 2: ML Score Evolution with Learning")
        
        # Test different catalyst types and their learned performance
        test_tickers = [
            ("FDA_POSITIVE", CatalystType.FDA, SentimentType.POSITIVE),
            ("MERGER_POSITIVE", CatalystType.MERGER, SentimentType.POSITIVE),
            ("EARNINGS_POSITIVE", CatalystType.EARNINGS, SentimentType.POSITIVE),
            ("FDA_NEGATIVE", CatalystType.FDA, SentimentType.NEGATIVE)
        ]
        
        scores = {}
        
        for ticker, catalyst, sentiment in test_tickers:
            # Create news analysis for scoring
            news_text = f"Test news for {catalyst.value} with {sentiment.value} sentiment"
            analysis = self.intelligence.analyze_ticker_news(ticker, news_text)
            
            # Calculate ML score
            ml_score = self.intelligence.calculate_ml_score(ticker)
            scores[ticker] = ml_score
            
            logger.info(f"   {ticker}: ML Score = {ml_score:.3f}")
        
        # Verify that positive FDA scores higher than negative FDA
        fda_positive_score = scores.get("FDA_POSITIVE", 0)
        fda_negative_score = scores.get("FDA_NEGATIVE", 0)
        fda_learning_works = fda_positive_score > fda_negative_score
        
        logger.info(f"   FDA positive > FDA negative: {'✅' if fda_learning_works else '❌'}")
        
        # Verify that merger scores are generally high (if learned as profitable)
        merger_score = scores.get("MERGER_POSITIVE", 0)
        merger_learning_works = merger_score > 0.5
        
        logger.info(f"   Merger scoring appropriately: {'✅' if merger_learning_works else '❌'}")
        
        self.test_results.append({
            'test': 'ml_score_evolution',
            'passed': fda_learning_works and merger_learning_works,
            'scores': scores,
            'fda_learning_works': fda_learning_works,
            'merger_learning_works': merger_learning_works
        })
    
    def test_feedback_loop_integration(self):
        """Test 3: Complete Feedback Loop Integration"""
        logger.info("🧪 Test 3: Complete Feedback Loop Integration")
        
        # Simulate complete workflow with feedback
        test_ticker = "FEEDBACK_TEST"
        
        # Step 1: News analysis
        breaking_news = "FEEDBACK_TEST receives FDA breakthrough designation for revolutionary cancer treatment with 95% efficacy"
        analysis = self.intelligence.analyze_ticker_news(test_ticker, breaking_news)
        
        # Step 2: Initial ML score
        initial_score = self.intelligence.calculate_ml_score(test_ticker)
        
        # Step 3: Auto-add decision
        config = ScannerConfig(
            sentiment_filter="ONLY_POSITIVE",
            max_float=100_000_000,
            min_gap_percent=5.0,
            min_volume=100_000,
            auto_add_threshold=0.4,
            learning_enabled=True
        )
        
        should_add = self.intelligence.should_auto_add_ticker(test_ticker, config)
        
        # Step 4: Simulate successful trade
        if should_add:
            successful_trade = TradingResult(
                ticker=test_ticker,
                trade_date=date.today(),
                entry_price=12.0,
                exit_price=15.0,
                pnl=600.0,
                was_profitable=True,
                hold_duration_minutes=45,
                strategy_used="ml_multi_strategy",
                notes="Feedback loop test - successful FDA trade"
            )
            
            self.intelligence.add_trading_result(successful_trade)
        
        # Step 5: Check updated ML score
        updated_score = self.intelligence.calculate_ml_score(test_ticker)
        
        # Step 6: Verify learning stats updated
        final_stats = self.intelligence.get_learning_stats()
        
        logger.info(f"   Initial ML score: {initial_score:.3f}")
        logger.info(f"   Should auto-add: {should_add}")
        logger.info(f"   Updated ML score: {updated_score:.3f}")
        logger.info(f"   Final win rate: {final_stats.get('win_rate', 0):.1f}%")
        
        feedback_loop_works = (
            analysis.sentiment == SentimentType.POSITIVE and
            analysis.catalyst_type == CatalystType.FDA and
            should_add and
            final_stats.get('learning_active', False)
        )
        
        logger.info(f"   Complete feedback loop: {'✅' if feedback_loop_works else '❌'}")
        
        self.test_results.append({
            'test': 'feedback_loop_integration',
            'passed': feedback_loop_works,
            'initial_score': initial_score,
            'updated_score': updated_score,
            'should_add': should_add,
            'final_stats': final_stats
        })
    
    def test_sentiment_filtering_learning(self):
        """Test 4: Sentiment Filtering with Learning"""
        logger.info("🧪 Test 4: Sentiment Filtering with Learning")
        
        # Test different sentiment configurations
        test_scenarios = [
            {
                "ticker": "SENT_POS",
                "news": "Amazing breakthrough in cancer research with 100% success rate",
                "expected_sentiment": SentimentType.POSITIVE
            },
            {
                "ticker": "SENT_NEU", 
                "news": "Company announces minor product update with standard improvements",
                "expected_sentiment": SentimentType.NEUTRAL
            },
            {
                "ticker": "SENT_NEG",
                "news": "Drug trial fails, company stock plummets due to safety concerns",
                "expected_sentiment": SentimentType.NEGATIVE
            }
        ]
        
        configs = [
            ("ONLY_POSITIVE", ScannerConfig(
                sentiment_filter="ONLY_POSITIVE",
                max_float=100_000_000,
                min_gap_percent=5.0,
                min_volume=100_000,
                auto_add_threshold=0.3,
                learning_enabled=True
            )),
            ("POSITIVE_NEUTRAL", ScannerConfig(
                sentiment_filter="POSITIVE_NEUTRAL",
                max_float=100_000_000,
                min_gap_percent=5.0,
                min_volume=100_000,
                auto_add_threshold=0.3,
                learning_enabled=True
            ))
        ]
        
        filter_results = {}
        
        for config_name, config in configs:
            filter_results[config_name] = {}
            
            for scenario in test_scenarios:
                # Analyze news
                analysis = self.intelligence.analyze_ticker_news(scenario["ticker"], scenario["news"])
                
                # Test auto-add decision
                should_add = self.intelligence.should_auto_add_ticker(scenario["ticker"], config)
                
                filter_results[config_name][scenario["ticker"]] = {
                    'sentiment': analysis.sentiment,
                    'should_add': should_add
                }
                
                logger.info(f"   {config_name} - {scenario['ticker']}: {analysis.sentiment.value} -> {'ADD' if should_add else 'SKIP'}")
        
        # Verify filtering logic
        only_positive_results = filter_results["ONLY_POSITIVE"]
        positive_neutral_results = filter_results["POSITIVE_NEUTRAL"]
        
        # ONLY_POSITIVE should only add positive sentiment
        only_pos_correct = (
            only_positive_results["SENT_POS"]["should_add"] and
            not only_positive_results["SENT_NEG"]["should_add"]
        )
        
        # POSITIVE_NEUTRAL should add positive and neutral but not negative
        pos_neu_correct = (
            positive_neutral_results["SENT_POS"]["should_add"] and
            not positive_neutral_results["SENT_NEG"]["should_add"]
        )
        
        sentiment_filtering_works = only_pos_correct and pos_neu_correct
        
        logger.info(f"   Sentiment filtering logic: {'✅' if sentiment_filtering_works else '❌'}")
        
        self.test_results.append({
            'test': 'sentiment_filtering_learning',
            'passed': sentiment_filtering_works,
            'filter_results': filter_results,
            'only_pos_correct': only_pos_correct,
            'pos_neu_correct': pos_neu_correct
        })
    
    def test_performance_metrics_tracking(self):
        """Test 5: Performance Metrics Tracking"""
        logger.info("🧪 Test 5: Performance Metrics Tracking")
        
        # Get comprehensive learning stats
        stats = self.intelligence.get_learning_stats()
        
        # Verify required metrics are tracked
        required_metrics = [
            'total_news_analyzed',
            'total_trades',
            'profitable_trades',
            'win_rate',
            'best_patterns',
            'learning_active'
        ]
        
        metrics_tracked = all(metric in stats for metric in required_metrics)
        
        logger.info(f"   All metrics tracked: {'✅' if metrics_tracked else '❌'}")
        
        # Check metric values make sense
        total_trades = stats.get('total_trades', 0)
        profitable_trades = stats.get('profitable_trades', 0)
        win_rate = stats.get('win_rate', 0)
        
        metrics_logical = (
            profitable_trades <= total_trades and
            0 <= win_rate <= 100 and
            (win_rate == 0 if total_trades == 0 else True)
        )
        
        logger.info(f"   Metrics logically consistent: {'✅' if metrics_logical else '❌'}")
        
        # Display current metrics
        logger.info(f"   Current metrics:")
        logger.info(f"      Total trades: {total_trades}")
        logger.info(f"      Profitable trades: {profitable_trades}")
        logger.info(f"      Win rate: {win_rate:.1f}%")
        logger.info(f"      News analyzed: {stats.get('total_news_analyzed', 0)}")
        logger.info(f"      Best patterns: {len(stats.get('best_patterns', []))}")
        
        performance_tracking_works = metrics_tracked and metrics_logical
        
        self.test_results.append({
            'test': 'performance_metrics_tracking',
            'passed': performance_tracking_works,
            'metrics_tracked': metrics_tracked,
            'metrics_logical': metrics_logical,
            'stats': stats
        })
    
    def test_database_persistence(self):
        """Test 6: Database Persistence and Recovery"""
        logger.info("🧪 Test 6: Database Persistence and Recovery")
        
        # Get current state
        initial_stats = self.intelligence.get_learning_stats()
        
        # Create new intelligence instance (simulating restart)
        new_intelligence = ScannerIntelligence(self.test_db)
        
        # Verify data persisted
        recovered_stats = new_intelligence.get_learning_stats()
        
        data_persisted = (
            recovered_stats.get('total_trades', 0) == initial_stats.get('total_trades', 0) and
            recovered_stats.get('total_news_analyzed', 0) == initial_stats.get('total_news_analyzed', 0)
        )
        
        logger.info(f"   Data persistence: {'✅' if data_persisted else '❌'}")
        
        # Test config persistence
        test_config = ScannerConfig(
            sentiment_filter="POSITIVE_NEUTRAL",
            max_float=75_000_000,
            min_gap_percent=8.0,
            min_volume=600_000,
            auto_add_threshold=0.6,
            learning_enabled=True
        )
        
        new_intelligence.save_config(test_config)
        loaded_config = new_intelligence.load_config()
        
        config_persisted = (
            loaded_config.sentiment_filter == test_config.sentiment_filter and
            loaded_config.auto_add_threshold == test_config.auto_add_threshold
        )
        
        logger.info(f"   Config persistence: {'✅' if config_persisted else '❌'}")
        
        persistence_works = data_persisted and config_persisted
        
        self.test_results.append({
            'test': 'database_persistence',
            'passed': persistence_works,
            'data_persisted': data_persisted,
            'config_persisted': config_persisted
        })
    
    def run_all_tests(self):
        """Run all learning and feedback system tests"""
        logger.info("🚀 Starting Learning and Feedback System Test Suite")
        logger.info("=" * 70)
        
        try:
            # Setup historical data for learning
            self.populate_historical_data()
            logger.info("-" * 50)
            
            # Run all tests
            self.test_pattern_learning()
            logger.info("-" * 50)
            
            self.test_ml_score_evolution()
            logger.info("-" * 50)
            
            self.test_feedback_loop_integration()
            logger.info("-" * 50)
            
            self.test_sentiment_filtering_learning()
            logger.info("-" * 50)
            
            self.test_performance_metrics_tracking()
            logger.info("-" * 50)
            
            self.test_database_persistence()
            
            self.print_summary()
            
        finally:
            # Cleanup
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
                logger.info(f"🧹 Cleaned up test database: {self.test_db}")
    
    def print_summary(self):
        """Print comprehensive test summary"""
        logger.info("📊 LEARNING & FEEDBACK SYSTEM TEST SUMMARY")
        logger.info("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.get('passed', False))
        failed_tests = total_tests - passed_tests
        
        logger.info(f"📈 Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        
        if total_tests > 0:
            pass_rate = (passed_tests / total_tests) * 100
            logger.info(f"📊 Pass Rate: {pass_rate:.1f}%")
        
        # Detailed test results
        logger.info("\n📋 Detailed Results:")
        for result in self.test_results:
            test_name = result['test']
            passed = result.get('passed', False)
            status = "✅" if passed else "❌"
            logger.info(f"   {status} {test_name}")
        
        # Show failures
        failed_results = [r for r in self.test_results if not r.get('passed', False)]
        if failed_results:
            logger.info("\n❌ Failed Test Details:")
            for result in failed_results:
                logger.info(f"   • {result['test']}: {result}")
        
        overall_success = failed_tests == 0
        status = "🎉 ALL LEARNING TESTS PASSED!" if overall_success else "⚠️  SOME LEARNING TESTS FAILED"
        logger.info(f"\n{status}")
        
        return overall_success

def main():
    """Main test runner"""
    test_suite = LearningFeedbackSystemTest()
    success = test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())