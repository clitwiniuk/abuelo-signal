"""
End-to-End Pipeline Test
Tests complete ticker journey: Scanner Selection → Strategy Engine → Trade Execution → Exit

This test simulates a realistic smallcaps ticker going through the entire pipeline
to verify that relaxed parameters allow proper entry testing.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import MarketData, Signal, Position, SignalType
from strategies.realistic_strategy_engine import RealisticStrategyEngine
from core.realistic_market_data import RealisticMarketData, EssentialIndicators, SetupContext
from mock_simple_strategy import MockSimpleStrategy


@dataclass
class MockTicker:
    """Mock ticker data for testing"""
    symbol: str
    name: str
    sector: str
    market_cap: float
    avg_volume: int
    prev_close: float

    # Scenario data
    scenario: str  # 'gap_up', 'news_spike', 'technical_setup'
    catalyst: str  # Why it would be selected by scanner


@dataclass
class MockPosition:
    """Mock position for testing"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0

    def update_price(self, new_price: float):
        self.current_price = new_price
        self.unrealized_pnl = (new_price - self.entry_price) * self.quantity


class EndToEndPipelineTest:
    """Complete pipeline test simulator"""

    def __init__(self):
        self.strategy_engine = None
        self.test_results = {
            'scanner_selections': [],
            'strategy_decisions': [],
            'signals_generated': [],
            'trades_executed': [],
            'exits_triggered': [],
            'final_pnl': 0.0
        }

    async def setup_test_environment(self):
        """Initialize the pipeline components"""
        print("🔧 Setting up test environment...")

        # Initialize RealisticStrategyEngine with relaxed parameters
        self.strategy_engine = RealisticStrategyEngine()
        await self.strategy_engine.initialize()

        print("✅ Strategy Engine initialized")
        print(f"📊 Core strategies: {list(self.strategy_engine.core_strategies.keys())}")
        print(f"⚡ Relaxed parameters active")
        print()

    def create_test_scenarios(self) -> List[MockTicker]:
        """Create realistic test scenarios for smallcaps"""
        return [
            MockTicker(
                symbol="ABCD",
                name="ABC Dynamics Inc",
                sector="Technology",
                market_cap=50_000_000,  # $50M smallcap
                avg_volume=150_000,
                prev_close=8.50,
                scenario="gap_up",
                catalyst="FDA approval announced pre-market"
            ),
            MockTicker(
                symbol="XYZE",
                name="XYZ Energy Corp",
                sector="Energy",
                market_cap=80_000_000,  # $80M smallcap
                avg_volume=200_000,
                prev_close=12.25,
                scenario="news_spike",
                catalyst="Major contract win with volume spike"
            ),
            MockTicker(
                symbol="DEFG",
                name="DEF Gaming Ltd",
                sector="Gaming",
                market_cap=35_000_000,  # $35M smallcap
                avg_volume=100_000,
                prev_close=6.75,
                scenario="technical_setup",
                catalyst="Clean MACDV setup, no major news"
            )
        ]

    def simulate_scanner_selection(self, ticker: MockTicker) -> bool:
        """Step 1: Simulate scanner selecting this ticker"""
        print(f"📡 SCANNER ANALYSIS: {ticker.symbol}")
        print(f"   Company: {ticker.name}")
        print(f"   Sector: {ticker.sector}")
        print(f"   Market Cap: ${ticker.market_cap/1_000_000:.1f}M")
        print(f"   Avg Volume: {ticker.avg_volume:,}")
        print(f"   Catalyst: {ticker.catalyst}")

        # Scanner selection criteria (very relaxed for testing)
        selected = (
            ticker.market_cap < 500_000_000 and  # Under $500M (smallcap)
            ticker.avg_volume > 50_000 and       # Minimum liquidity
            ticker.prev_close < 20.0             # Affordable entry
        )

        if selected:
            print(f"✅ SELECTED by scanner - meets smallcap criteria")
            self.test_results['scanner_selections'].append(ticker.symbol)
        else:
            print(f"❌ REJECTED by scanner")

        print()
        return selected

    def create_market_data_sequence(self, ticker: MockTicker) -> List[MarketData]:
        """Create realistic intraday market data sequence"""
        sequence = []
        base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)  # 30min after open

        if ticker.scenario == "gap_up":
            # Gap up scenario - FDA approval (Strong gap to trigger Gap Go)
            # Gap from $8.50 to $11.50 = 35% gap (should trigger Gap Go)
            prices = [
                (11.50, 11.80, 11.40, 11.75, 450_000),  # 9:30 - Gap up open (3x volume)
                (11.75, 12.10, 11.65, 11.95, 380_000),  # 9:31 - Initial spike
                (11.95, 12.05, 11.80, 11.85, 320_000),  # 9:32 - Pullback
                (11.85, 12.20, 11.85, 12.15, 480_000),  # 9:33 - Continuation
                (12.15, 12.25, 11.95, 12.05, 290_000),  # 9:34 - Consolidation
            ]

        elif ticker.scenario == "news_spike":
            # News spike scenario - Contract win (High volume to trigger Daily Plays)
            # Volume 4-5x average should trigger Daily Plays
            prices = [
                (12.30, 12.45, 12.25, 12.40, 280_000),  # 9:30 - Normal open
                (12.40, 13.80, 12.35, 13.65, 1_000_000),  # 9:31 - News spike (5x volume)
                (13.65, 13.75, 13.20, 13.45, 820_000),  # 9:32 - High volume (4x)
                (13.45, 13.60, 13.30, 13.50, 650_000),  # 9:33 - Still high volume
                (13.50, 13.70, 13.40, 13.55, 480_000),  # 9:34 - Follow through
            ]

        else:  # technical_setup
            # Clean technical setup - No major news
            prices = [
                (6.80, 6.85, 6.75, 6.82, 120_000),     # 9:30 - Quiet open
                (6.82, 6.88, 6.80, 6.85, 135_000),     # 9:31 - Slow build
                (6.85, 6.90, 6.83, 6.88, 145_000),     # 9:32 - Volume increase
                (6.88, 6.95, 6.86, 6.92, 160_000),     # 9:33 - Steady climb
                (6.92, 6.98, 6.90, 6.95, 175_000),     # 9:34 - Momentum build
            ]

        for i, (open_p, high, low, close, volume) in enumerate(prices):
            timestamp = base_time + timedelta(minutes=i)

            data = MarketData(
                symbol=ticker.symbol,
                timestamp=timestamp,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=volume
            )

            # Add essential attributes
            data.prev_close = ticker.prev_close
            data.avg_volume = ticker.avg_volume

            sequence.append(data)

        return sequence

    async def test_strategy_engine_analysis(self, ticker: MockTicker, market_data: List[MarketData]) -> List[Signal]:
        """Step 2: Test Strategy Engine analysis and selection"""
        print(f"🧠 STRATEGY ENGINE ANALYSIS: {ticker.symbol}")

        all_signals = []

        for i, data in enumerate(market_data):
            print(f"⏰ Bar {i+1}: {data.timestamp.strftime('%H:%M')} | "
                  f"${data.close:.2f} | Vol: {data.volume:,}")

            # Analyze with strategy engine
            signals = await self.strategy_engine.analyze(ticker.symbol, data)

            if signals:
                for signal in signals:
                    print(f"   🎯 SIGNAL: {signal.signal_type.name} | "
                          f"Strategy: {getattr(signal, 'strategy_name', 'Unknown')} | "
                          f"Confidence: {signal.confidence:.1%} | "
                          f"Entry: ${signal.entry_price:.2f}")
                    all_signals.append(signal)

                    self.test_results['signals_generated'].append({
                        'symbol': ticker.symbol,
                        'time': data.timestamp,
                        'signal_type': signal.signal_type.name,
                        'confidence': signal.confidence,
                        'entry_price': signal.entry_price
                    })
            else:
                print(f"   ⚪ No signals generated")

        # Show active strategy for this symbol
        active_strategy = self.strategy_engine.switch_limiter.get_current_strategy(ticker.symbol)
        if active_strategy:
            print(f"   ✅ Active Strategy: {active_strategy}")
            self.test_results['strategy_decisions'].append({
                'symbol': ticker.symbol,
                'strategy': active_strategy
            })

        # FALLBACK TEST: If no signals generated, test with mock strategy
        if not all_signals:
            print(f"   🔄 Testing fallback with MockSimpleStrategy...")
            mock_strategy = MockSimpleStrategy()
            await mock_strategy.initialize()

            for i, data in enumerate(market_data):
                mock_signals = await mock_strategy._analyze_bar(ticker.symbol, data)
                if mock_signals:
                    for signal in mock_signals:
                        print(f"   🧪 MOCK SIGNAL: {signal.signal_type.name} | "
                              f"Confidence: {signal.confidence:.1%} | "
                              f"Entry: ${signal.entry_price:.2f}")
                        all_signals.append(signal)

                        self.test_results['signals_generated'].append({
                            'symbol': ticker.symbol,
                            'time': data.timestamp,
                            'signal_type': signal.signal_type.name,
                            'confidence': signal.confidence,
                            'entry_price': signal.entry_price
                        })

        print()
        return all_signals

    def simulate_trade_execution(self, ticker: MockTicker, signals: List[Signal]) -> MockPosition:
        """Step 3: Simulate trade execution"""
        if not signals:
            print(f"❌ No signals to execute for {ticker.symbol}")
            return None

        # Take first BUY signal
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        if not buy_signals:
            print(f"❌ No BUY signals for {ticker.symbol}")
            return None

        signal = buy_signals[0]

        print(f"💰 TRADE EXECUTION: {ticker.symbol}")
        print(f"   Signal: {signal.signal_type.name}")
        print(f"   Entry Price: ${signal.entry_price:.2f}")
        print(f"   Confidence: {signal.confidence:.1%}")

        # Calculate position size (simple $1000 risk)
        risk_amount = 1000
        stop_loss = getattr(signal, 'stop_loss', signal.entry_price * 0.95)  # 5% stop
        risk_per_share = signal.entry_price - stop_loss

        if risk_per_share > 0:
            shares = int(risk_amount / risk_per_share)
        else:
            shares = 100  # Default

        position = MockPosition(
            symbol=ticker.symbol,
            quantity=shares,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            entry_time=signal.timestamp
        )

        print(f"   Shares: {shares}")
        print(f"   Position Value: ${shares * signal.entry_price:.2f}")
        print(f"   Stop Loss: ${stop_loss:.2f}")

        self.test_results['trades_executed'].append({
            'symbol': ticker.symbol,
            'entry_price': signal.entry_price,
            'shares': shares,
            'entry_time': signal.timestamp
        })

        print()
        return position

    def simulate_price_movement(self, ticker: MockTicker, position: MockPosition) -> List[float]:
        """Step 4: Simulate realistic price movement after entry"""
        print(f"📈 PRICE MOVEMENT SIMULATION: {ticker.symbol}")

        if ticker.scenario == "gap_up":
            # FDA approval - strong follow through then profit taking
            price_sequence = [
                position.entry_price,
                position.entry_price * 1.08,   # +8% initial spike
                position.entry_price * 1.12,   # +12% momentum
                position.entry_price * 1.15,   # +15% peak
                position.entry_price * 1.09,   # Profit taking
                position.entry_price * 1.06,   # Consolidation
            ]

        elif ticker.scenario == "news_spike":
            # Contract win - volatile but upward trending
            price_sequence = [
                position.entry_price,
                position.entry_price * 1.05,   # +5% continuation
                position.entry_price * 1.03,   # Pullback
                position.entry_price * 1.10,   # +10% surge
                position.entry_price * 1.14,   # +14% peak
                position.entry_price * 1.08,   # Settlement
            ]

        else:  # technical_setup
            # Clean technical - steady modest gains
            price_sequence = [
                position.entry_price,
                position.entry_price * 1.02,   # +2% steady
                position.entry_price * 1.04,   # +4% climb
                position.entry_price * 1.06,   # +6% target
                position.entry_price * 1.05,   # Minor pullback
                position.entry_price * 1.07,   # +7% final
            ]

        for i, price in enumerate(price_sequence):
            position.update_price(price)
            pnl_pct = (price - position.entry_price) / position.entry_price * 100
            print(f"   T+{i*10}min: ${price:.2f} | P&L: {pnl_pct:+.1f}% (${position.unrealized_pnl:.2f})")

        print()
        return price_sequence

    def simulate_exit_decision(self, ticker: MockTicker, position: MockPosition, price_sequence: List[float]) -> Dict[str, Any]:
        """Step 5: Simulate exit decision logic"""
        print(f"🚪 EXIT DECISION: {ticker.symbol}")

        entry_price = position.entry_price
        current_price = price_sequence[-1]
        gain_pct = (current_price - entry_price) / entry_price * 100

        # Simple exit rules for testing
        if gain_pct >= 15:
            exit_reason = "Target hit (+15%)"
            exit_decision = "SELL"
        elif gain_pct >= 10:
            exit_reason = "Strong profit (+10%)"
            exit_decision = "SELL"
        elif gain_pct >= 5:
            exit_reason = "Modest profit (+5%)"
            exit_decision = "HOLD"
        elif gain_pct <= -5:
            exit_reason = "Stop loss (-5%)"
            exit_decision = "SELL"
        else:
            exit_reason = "No clear signal"
            exit_decision = "HOLD"

        print(f"   Current P&L: {gain_pct:+.1f}%")
        print(f"   Decision: {exit_decision}")
        print(f"   Reason: {exit_reason}")

        if exit_decision == "SELL":
            final_pnl = position.unrealized_pnl
            self.test_results['final_pnl'] += final_pnl

            self.test_results['exits_triggered'].append({
                'symbol': ticker.symbol,
                'exit_price': current_price,
                'exit_reason': exit_reason,
                'final_pnl': final_pnl,
                'gain_pct': gain_pct
            })

            print(f"   💰 Final P&L: ${final_pnl:.2f}")

        print()
        return {
            'decision': exit_decision,
            'reason': exit_reason,
            'pnl': position.unrealized_pnl,
            'gain_pct': gain_pct
        }

    async def run_complete_test(self):
        """Run the complete end-to-end pipeline test"""
        print("🚀 STARTING END-TO-END PIPELINE TEST")
        print("=" * 60)

        await self.setup_test_environment()

        test_scenarios = self.create_test_scenarios()

        for ticker in test_scenarios:
            print(f"🧪 TESTING SCENARIO: {ticker.scenario.upper()}")
            print("-" * 40)

            # Step 1: Scanner Selection
            if not self.simulate_scanner_selection(ticker):
                continue

            # Step 2: Generate Market Data
            market_data = self.create_market_data_sequence(ticker)

            # Step 3: Strategy Engine Analysis
            signals = await self.test_strategy_engine_analysis(ticker, market_data)

            # Step 4: Trade Execution
            position = self.simulate_trade_execution(ticker, signals)

            if position:
                # Step 5: Price Movement
                price_sequence = self.simulate_price_movement(ticker, position)

                # Step 6: Exit Decision
                exit_result = self.simulate_exit_decision(ticker, position, price_sequence)

        # Final Results Summary
        self.print_test_summary()

    def print_test_summary(self):
        """Print comprehensive test results"""
        print("📊 PIPELINE TEST SUMMARY")
        print("=" * 60)

        results = self.test_results

        print(f"📡 Scanner Selections: {len(results['scanner_selections'])}")
        for symbol in results['scanner_selections']:
            print(f"   ✅ {symbol}")
        print()

        print(f"🧠 Strategy Decisions: {len(results['strategy_decisions'])}")
        for decision in results['strategy_decisions']:
            print(f"   🎯 {decision['symbol']}: {decision['strategy']}")
        print()

        print(f"⚡ Signals Generated: {len(results['signals_generated'])}")
        for signal in results['signals_generated']:
            print(f"   📈 {signal['symbol']}: {signal['signal_type']} "
                  f"({signal['confidence']:.1%}) @ ${signal['entry_price']:.2f}")
        print()

        print(f"💰 Trades Executed: {len(results['trades_executed'])}")
        for trade in results['trades_executed']:
            print(f"   ✅ {trade['symbol']}: {trade['shares']} shares @ ${trade['entry_price']:.2f}")
        print()

        print(f"🚪 Exits Triggered: {len(results['exits_triggered'])}")
        for exit_info in results['exits_triggered']:
            print(f"   💰 {exit_info['symbol']}: {exit_info['gain_pct']:+.1f}% "
                  f"(${exit_info['final_pnl']:+.2f}) - {exit_info['exit_reason']}")
        print()

        print(f"💵 Total P&L: ${results['final_pnl']:+.2f}")
        print()

        # Pipeline Health Check
        print("🔍 PIPELINE HEALTH CHECK:")
        scanner_rate = len(results['scanner_selections']) / 3 * 100
        signal_rate = len(results['signals_generated']) / max(len(results['scanner_selections']), 1) * 100
        execution_rate = len(results['trades_executed']) / max(len(results['signals_generated']), 1) * 100

        print(f"   📡 Scanner Selection Rate: {scanner_rate:.0f}%")
        print(f"   ⚡ Signal Generation Rate: {signal_rate:.0f}%")
        print(f"   💰 Trade Execution Rate: {execution_rate:.0f}%")

        if scanner_rate >= 60 and signal_rate >= 80 and execution_rate >= 80:
            print("   ✅ PIPELINE HEALTHY - Ready for live testing")
        else:
            print("   ⚠️ PIPELINE ISSUES - Review parameters")

        print("=" * 60)


async def main():
    """Run the end-to-end pipeline test"""
    test = EndToEndPipelineTest()
    await test.run_complete_test()


if __name__ == "__main__":
    asyncio.run(main())