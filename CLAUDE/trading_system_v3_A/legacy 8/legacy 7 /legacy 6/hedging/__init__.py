# hedging/__init__.py
"""
Advanced Hedging Module with Transformers and Reinforcement Learning
Provides intelligent portfolio protection and risk management
"""

from .portfolio_hedger import PortfolioHedger, HedgeRecommendation, HedgeType
from .transformer_hedge_analyzer import TransformerHedgeAnalyzer, MarketRegime
from .rl_hedge_agent import RLHedgeAgent, HedgeAction, HedgeEnvironment

__all__ = [
    'PortfolioHedger',
    'HedgeRecommendation', 
    'HedgeType',
    'TransformerHedgeAnalyzer',
    'MarketRegime',
    'RLHedgeAgent',
    'HedgeAction',
    'HedgeEnvironment'
]