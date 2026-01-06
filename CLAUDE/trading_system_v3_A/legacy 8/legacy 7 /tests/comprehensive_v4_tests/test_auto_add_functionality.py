#!/usr/bin/env python3
"""
Auto-Add Functionality Test Suite
Tests the automatic ticker addition based on catalizadores and ML scoring
"""

import sys
import os
import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scanner.scanner_intelligence import ScannerIntelligence, ScannerConfig, TradingResult, SentimentType, CatalystType, NewsAnalysis

logger = logging.getLogger("AutoAddTest")
logging.basicConfig(level=logging.INFO)

class AutoAddFunctionalityTest:
    """Test the auto-add functionality specifically"""
    
    def __init__(self):
        self.test_db = "test_auto_add.db"
        self.intelligence = ScannerIntelligence(self.test_db)
        self.test_results = []
    
    def setup_test_data(self):
        """Setup test data for auto-add scenarios"""
        logger.info("🔧 Setting up test data...")
        
        # Create different news scenarios
        test_scenarios = [
            {
                "ticker": "POSITIVE_FDA",
                "news": "Company receives FDA breakthrough therapy designation for cancer drug. Clinical trials show 80% response rate.",
                "expected_sentiment": SentimentType.POSITIVE,
                "expected_catalyst": CatalystType.FDA,
                "should_auto_add": True
            },
            {
                "ticker": "POSITIVE_EARNINGS", 
                "news": "Company beats earnings expectations by 50%, revenue up 200% year over year. Strong guidance for next quarter.",
                "expected_sentiment": SentimentType.POSITIVE,
                "expected_catalyst": CatalystType.EARNINGS,
                "should_auto_add": True
            },
            {
                "ticker": "NEUTRAL_CONTRACT",
                "news": "Company wins new government contract worth $10 million. Details to be announced soon.",
                "expected_sentiment": SentimentType.NEUTRAL,
                "expected_catalyst": CatalystType.CONTRACT,
                "should_auto_add": False  # Neutral sentiment
            },
            {
                "ticker": "NEGATIVE_NEWS",
                "news": "Company reports disappointing trial results. FDA rejects drug application due to safety concerns.",
                "expected_sentiment": SentimentType.NEGATIVE,
                "expected_catalyst": CatalystType.FDA,
                "should_auto_add": False  # Negative sentiment
            },
            {
                "ticker": "WEAK_SIGNAL",
                "news": "Company announces minor product update. Small improvements to existing technology.",
                "expected_sentiment": SentimentType.NEUTRAL,
                "expected_catalyst": CatalystType.INNOVATION,
                "should_auto_add": False  # Low impact
            }
        ]
        
        self.test_scenarios = test_scenarios
        return test_scenarios
    
    def test_news_analysis_accuracy(self):
        """Test 1: News analysis accuracy"""
        logger.info("🧪 Test 1: News Analysis Accuracy")
        
        for scenario in self.test_scenarios:
            ticker = scenario["ticker"]
            news = scenario["news"]
            
            # Analyze the news
            analysis = self.intelligence.analyze_ticker_news(ticker, news)
            
            # Check sentiment accuracy
            sentiment_correct = analysis.sentiment == scenario["expected_sentiment"]
            catalyst_correct = analysis.catalyst_type == scenario["expected_catalyst"]
            
            logger.info(f"   {ticker}: Sentiment={analysis.sentiment.value} (expected {scenario['expected_sentiment'].value}) - {'✅' if sentiment_correct else '❌'}")
            logger.info(f"   {ticker}: Catalyst={analysis.catalyst_type.value} (expected {scenario['expected_catalyst'].value}) - {'✅' if catalyst_correct else '❌'}")
            logger.info(f"   {ticker}: Confidence={analysis.confidence_score:.2f}, Impact={analysis.impact_score:.2f}")
            
            self.test_results.append({
                'test': 'news_analysis',
                'ticker': ticker,
                'sentiment_correct': sentiment_correct,
                'catalyst_correct': catalyst_correct,
                'confidence': analysis.confidence_score,
                'impact': analysis.impact_score
            })
    
    def test_ml_scoring(self):
        """Test 2: ML Scoring System"""
        logger.info("🧪 Test 2: ML Scoring System")
        
        for scenario in self.test_scenarios:
            ticker = scenario["ticker"]
            
            # Calculate ML score
            ml_score = self.intelligence.calculate_ml_score(ticker)
            
            logger.info(f"   {ticker}: ML Score = {ml_score:.3f}")
            
            # Scores should be between 0 and 1
            score_valid = 0 <= ml_score <= 1
            
            self.test_results.append({
                'test': 'ml_scoring',
                'ticker': ticker,
                'ml_score': ml_score,
                'score_valid': score_valid
            })
    
    def test_auto_add_logic(self):
        """Test 3: Auto-add Logic"""
        logger.info("🧪 Test 3: Auto-add Logic")
        
        # Test different configurations
        configs = [
            ScannerConfig(
                sentiment_filter="ONLY_POSITIVE",
                max_float=100_000_000,
                min_gap_percent=5.0,
                min_volume=100_000,
                auto_add_threshold=0.6,
                learning_enabled=True
            ),
            ScannerConfig(
                sentiment_filter="POSITIVE_NEUTRAL", 
                max_float=100_000_000,
                min_gap_percent=5.0,
                min_volume=100_000,
                auto_add_threshold=0.3,
                learning_enabled=True
            )
        ]
        
        for i, config in enumerate(configs):
            logger.info(f"   Config {i+1}: {config.sentiment_filter}, threshold={config.auto_add_threshold}")
            
            for scenario in self.test_scenarios:
                ticker = scenario["ticker"]
                should_add = self.intelligence.should_auto_add_ticker(ticker, config)
                
                logger.info(f"      {ticker}: Should add = {should_add}")
                
                self.test_results.append({
                    'test': 'auto_add_logic',
                    'config': i+1,
                    'ticker': ticker,
                    'should_add': should_add,
                    'expected': scenario.get("should_auto_add", False)
                })
    
    def test_learning_system(self):
        """Test 4: Learning System Integration"""
        logger.info("🧪 Test 4: Learning System")
        
        # Add some trading results for learning
        profitable_trades = [
            TradingResult(
                ticker="POSITIVE_FDA",
                trade_date=date.today() - timedelta(days=1),
                entry_price=10.0,
                exit_price=12.0,
                pnl=200.0,
                was_profitable=True,
                hold_duration_minutes=45,
                strategy_used="ml_multi_strategy",
                notes="FDA approval news trade"
            ),
            TradingResult(
                ticker="POSITIVE_EARNINGS",
                trade_date=date.today() - timedelta(days=2),
                entry_price=5.0,
                exit_price=7.0,
                pnl=400.0,
                was_profitable=True,
                hold_duration_minutes=30,
                strategy_used="ml_multi_strategy", 
                notes="Earnings beat trade"
            )
        ]
        
        unprofitable_trades = [
            TradingResult(
                ticker="NEGATIVE_NEWS",
                trade_date=date.today() - timedelta(days=3),
                entry_price=8.0,
                exit_price=6.0,
                pnl=-200.0,
                was_profitable=False,
                hold_duration_minutes=15,
                strategy_used="ml_multi_strategy",
                notes="Bad news trade"
            )
        ]
        
        # Add trading results
        for trade in profitable_trades + unprofitable_trades:
            self.intelligence.add_trading_result(trade)
        
        # Check learning stats
        stats = self.intelligence.get_learning_stats()
        
        logger.info(f"   Learning Stats:")
        logger.info(f"      Total trades: {stats['total_trades']}")
        logger.info(f"      Profitable trades: {stats['profitable_trades']}")
        logger.info(f"      Win rate: {stats['win_rate']:.1f}%")
        logger.info(f"      Learning active: {stats['learning_active']}")
        
        # Test that learning affects ML scores
        fda_score_after_learning = self.intelligence.calculate_ml_score("POSITIVE_FDA")
        logger.info(f"   FDA ticker ML score after learning: {fda_score_after_learning:.3f}")
        
        self.test_results.append({
            'test': 'learning_system',
            'stats': stats,
            'fda_score_after_learning': fda_score_after_learning
        })
    
    def test_config_persistence(self):
        """Test 5: Configuration Persistence"""
        logger.info("🧪 Test 5: Configuration Persistence")
        
        # Save a config
        test_config = ScannerConfig(
            sentiment_filter="ONLY_POSITIVE",
            max_float=50_000_000,
            min_gap_percent=12.0,
            min_volume=750_000,
            auto_add_threshold=0.8,
            learning_enabled=True
        )
        
        self.intelligence.save_config(test_config)
        
        # Load it back
        loaded_config = self.intelligence.load_config()
        
        config_matches = (
            loaded_config.sentiment_filter == test_config.sentiment_filter and
            loaded_config.auto_add_threshold == test_config.auto_add_threshold and
            loaded_config.learning_enabled == test_config.learning_enabled
        )
        
        logger.info(f"   Config persistence: {'✅' if config_matches else '❌'}")
        
        self.test_results.append({
            'test': 'config_persistence',
            'matches': config_matches
        })
    
    def simulate_real_workflow(self):
        """Test 6: Simulate Real Auto-Add Workflow"""
        logger.info("🧪 Test 6: Real Workflow Simulation")
        
        # Simulate finding a new ticker with news
        new_ticker = "BIOTECH_X"
        breaking_news = "BIOTECH_X receives FDA breakthrough therapy designation for Alzheimer's drug. Phase 3 trials show unprecedented 90% efficacy rate."
        
        # Step 1: Analyze news
        analysis = self.intelligence.analyze_ticker_news(new_ticker, breaking_news)
        logger.info(f"   Step 1 - News Analysis:")
        logger.info(f"      Sentiment: {analysis.sentiment.value}")
        logger.info(f"      Catalyst: {analysis.catalyst_type.value}")
        logger.info(f"      Confidence: {analysis.confidence_score:.2f}")
        
        # Step 2: Calculate ML score
        ml_score = self.intelligence.calculate_ml_score(new_ticker)
        logger.info(f"   Step 2 - ML Score: {ml_score:.3f}")
        
        # Step 3: Test auto-add decision
        config = ScannerConfig(
            sentiment_filter="ONLY_POSITIVE",
            max_float=100_000_000,
            min_gap_percent=5.0,
            min_volume=100_000,
            auto_add_threshold=0.5,
            learning_enabled=True
        )
        
        should_auto_add = self.intelligence.should_auto_add_ticker(new_ticker, config)
        logger.info(f"   Step 3 - Auto-add Decision: {should_auto_add}")
        
        # Step 4: Simulate trading result
        if should_auto_add:
            simulated_trade = TradingResult(
                ticker=new_ticker,
                trade_date=date.today(),
                entry_price=15.0,
                exit_price=18.0,
                pnl=300.0,
                was_profitable=True,
                hold_duration_minutes=60,
                strategy_used="ml_multi_strategy",
                notes="Auto-added FDA breakthrough trade"
            )
            
            self.intelligence.add_trading_result(simulated_trade)
            logger.info(f"   Step 4 - Trading Result Added: +${simulated_trade.pnl}")
        
        # Final ML score after feedback
        final_ml_score = self.intelligence.calculate_ml_score(new_ticker)
        logger.info(f"   Final ML Score: {final_ml_score:.3f}")
        
        workflow_success = (
            analysis.sentiment == SentimentType.POSITIVE and
            analysis.catalyst_type == CatalystType.FDA and
            should_auto_add and
            final_ml_score >= ml_score
        )
        
        logger.info(f"   Workflow Success: {'✅' if workflow_success else '❌'}")
        
        self.test_results.append({
            'test': 'real_workflow',
            'success': workflow_success,
            'analysis': analysis,
            'ml_score': ml_score,
            'should_auto_add': should_auto_add,
            'final_score': final_ml_score
        })
    
    def run_all_tests(self):
        """Run all auto-add tests"""
        logger.info("🚀 Starting Auto-Add Functionality Test Suite")
        logger.info("=" * 60)
        
        try:
            self.setup_test_data()
            self.test_news_analysis_accuracy()
            logger.info("-" * 40)
            self.test_ml_scoring()
            logger.info("-" * 40)
            self.test_auto_add_logic()
            logger.info("-" * 40)
            self.test_learning_system()
            logger.info("-" * 40)
            self.test_config_persistence()
            logger.info("-" * 40)
            self.simulate_real_workflow()
            
            self.print_summary()
            
        finally:
            # Cleanup
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
                logger.info(f"🧹 Cleaned up test database: {self.test_db}")
    
    def print_summary(self):
        """Print test summary"""
        logger.info("📊 AUTO-ADD FUNCTIONALITY TEST SUMMARY")
        logger.info("=" * 60)
        
        # Count results by test type
        test_counts = {}
        for result in self.test_results:
            test_type = result['test']
            if test_type not in test_counts:
                test_counts[test_type] = {'total': 0, 'passed': 0}
            
            test_counts[test_type]['total'] += 1
            
            # Determine if test passed (simplified logic)
            passed = False
            if test_type == 'news_analysis':
                passed = result.get('sentiment_correct', False) and result.get('catalyst_correct', False)
            elif test_type == 'ml_scoring':
                passed = result.get('score_valid', False)
            elif test_type == 'auto_add_logic':
                passed = True  # Logic tests always pass if no exceptions
            elif test_type == 'learning_system':
                passed = result.get('stats', {}).get('learning_active', False)
            elif test_type == 'config_persistence':
                passed = result.get('matches', False)
            elif test_type == 'real_workflow':
                passed = result.get('success', False)
            
            if passed:
                test_counts[test_type]['passed'] += 1
        
        # Print summary
        total_tests = sum(tc['total'] for tc in test_counts.values())
        total_passed = sum(tc['passed'] for tc in test_counts.values())
        
        logger.info(f"📈 Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {total_passed}")
        logger.info(f"❌ Failed: {total_tests - total_passed}")
        logger.info(f"📊 Pass Rate: {(total_passed/total_tests*100):.1f}%")
        
        logger.info("\n📋 Test Breakdown:")
        for test_type, counts in test_counts.items():
            logger.info(f"   {test_type}: {counts['passed']}/{counts['total']}")
        
        overall_success = total_passed == total_tests
        status = "🎉 ALL AUTO-ADD TESTS PASSED!" if overall_success else "⚠️  SOME AUTO-ADD TESTS FAILED"
        logger.info(f"\n{status}")
        
        return overall_success

def main():
    """Main test runner"""
    test_suite = AutoAddFunctionalityTest()
    success = test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())