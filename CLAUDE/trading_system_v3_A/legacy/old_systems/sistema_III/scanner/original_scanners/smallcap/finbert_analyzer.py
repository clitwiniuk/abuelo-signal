# scanner/smallcap/finbert_analyzer.py
"""
FinBERT-based sentiment analyzer for financial news
Much more sophisticated than keyword-based approach
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

@dataclass
class FinBERTResult:
    """Result from FinBERT analysis"""
    sentiment: str  # 'positive', 'negative', 'neutral'
    confidence: float  # 0.0 to 1.0
    catalyst_strength: int  # 1-10 scale
    catalyst_type: str  # 'FDA', 'M&A', 'EARNINGS', etc.
    keywords_found: List[str]
    reasoning: str

class FinBERTAnalyzer:
    """
    Advanced financial sentiment analyzer using FinBERT
    Specialized for trading catalyst detection
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        
        # Enhanced catalyst keywords for classification
        self.catalyst_patterns = {
            'FDA': {
                'keywords': [
                    'fda', 'fda approval', 'drug approval', 'clinical trial', 'phase i', 'phase ii', 'phase iii',
                    'breakthrough therapy', 'orphan drug', 'fast track', 'priority review', 'biologics',
                    'pharmacokinetic', 'bioavailability', 'dosing', 'safety profile', 'efficacy',
                    'investigational', 'new drug application', 'nda', 'anda', 'ind', 'regulatory',
                    'prophylaxis', 'treatment', 'therapy', 'drug candidate', 'compound', 'molecule',
                    # 2024-2025 FDA keywords
                    'accelerated approval', 'real-world evidence', 'adaptive trial', 'precision medicine',
                    'biomarker', 'companion diagnostic', 'cell therapy', 'gene therapy', 'mrna',
                    'crispr', 'car-t', 'immunotherapy', 'oncology', 'rare disease', 'pediatric',
                    'breakthrough designation', 'regenerative medicine', 'digital therapeutics',
                    'ai-assisted drug', 'personalized medicine', 'biosimilar', 'follow-on biologic'
                ],
                'base_strength': 8,
                'positive_multiplier': 1.2
            },
            'M&A': {
                'keywords': [
                    'acquisition', 'merger', 'buyout', 'takeover', 'acquired by', 'agrees to acquire',
                    'purchase agreement', 'definitive agreement', 'cash offer', 'tender offer',
                    'strategic buyer', 'private equity', 'going private', 'deal', 'transaction',
                    # 2024-2025 M&A keywords
                    'strategic investment', 'partnership agreement', 'joint venture', 'licensing deal',
                    'platform acquisition', 'bolt-on acquisition', 'asset purchase', 'merger of equals',
                    'go-private transaction', 'management buyout', 'spac merger', 'reverse merger',
                    'business combination', 'strategic alliance', 'collaboration', 'option to acquire',
                    'letter of intent', 'due diligence', 'regulatory approval', 'synergies',
                    'enterprise value', 'premium', 'consolidation', 'divestiture', 'spin-off'
                ],
                'base_strength': 9,
                'positive_multiplier': 1.3
            },
            'EARNINGS': {
                'keywords': [
                    'earnings', 'quarterly results', 'revenue beat', 'earnings beat', 'guidance raised',
                    'guidance increased', 'outlook', 'profit', 'revenue', 'sales growth', 'record revenue',
                    'eps', 'beat estimates', 'strong quarter', 'outperform', 'exceed expectations',
                    # 2024-2025 earnings keywords
                    'adjusted ebitda', 'operating leverage', 'margin expansion', 'free cash flow',
                    'recurring revenue', 'subscription growth', 'customer acquisition', 'retention rate',
                    'same-store sales', 'organic growth', 'guidance raise', 'forward-looking',
                    'positive surprise', 'consensus beat', 'top-line growth', 'bottom-line',
                    'milestone payment', 'royalty revenue', 'licensing income'
                ],
                'base_strength': 6,
                'positive_multiplier': 1.1
            },
            'CONTRACT': {
                'keywords': [
                    'contract', 'agreement', 'deal', 'order', 'awarded', 'selected', 'partnership',
                    'collaboration', 'joint venture', 'license agreement', 'supply agreement',
                    'distribution agreement', 'government contract', 'military contract', 'wins contract',
                    'secures', 'lands', 'signs'
                ],
                'base_strength': 7,
                'positive_multiplier': 1.15
            },
            'BREAKTHROUGH': {
                'keywords': [
                    'breakthrough', 'innovation', 'patent', 'patent approval', 'intellectual property',
                    'technology advance', 'revolutionary', 'game changing', 'first of its kind',
                    'proprietary', 'exclusive', 'patent granted', 'ip', 'disruptive', 'novel'
                ],
                'base_strength': 7,
                'positive_multiplier': 1.2
            },
            'AI_TECH': {
                'keywords': [
                    'artificial intelligence', 'ai platform', 'machine learning', 'deep learning',
                    'neural network', 'large language model', 'llm', 'generative ai', 'chatbot',
                    'automation', 'computer vision', 'natural language', 'data analytics',
                    'cloud computing', 'saas', 'software as a service', 'platform as a service',
                    'api integration', 'digital transformation', 'ai-powered', 'ai-driven',
                    'quantum computing', 'edge computing', 'cybersecurity', 'blockchain'
                ],
                'base_strength': 8,
                'positive_multiplier': 1.25
            },
            'ESG_SUSTAINABILITY': {
                'keywords': [
                    'sustainability', 'esg', 'environmental', 'carbon neutral', 'green energy',
                    'renewable energy', 'solar', 'wind power', 'battery technology', 'ev charging',
                    'electric vehicle', 'clean technology', 'carbon capture', 'net zero',
                    'sustainable practices', 'climate change', 'decarbonization', 'green bonds',
                    'social responsibility', 'governance', 'diversity inclusion', 'impact investing'
                ],
                'base_strength': 6,
                'positive_multiplier': 1.1
            }
        }
        
        logger.info("FinBERT Analyzer initialized")
    
    def _load_model(self):
        """Load FinBERT model (lazy loading)"""
        if self.model_loaded:
            return
        
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
            
            logger.info("Loading FinBERT model (this may take a moment)...")
            
            # Use enhanced FinBERT-tone for better financial sentiment analysis (2024 upgrade)
            model_name = "yiyanghkust/finbert-tone"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # Create pipeline for easier use
            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                return_all_scores=True
            )
            
            self.model_loaded = True
            logger.info("✅ FinBERT model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            logger.error("Falling back to keyword-based analysis")
            self.model_loaded = False
    
    def analyze_headline(self, headline: str, age_hours: float = 0.0) -> FinBERTResult:
        """
        Analyze financial headline using FinBERT + enhanced catalyst detection
        
        Args:
            headline: News headline to analyze
            age_hours: Age of news in hours
            
        Returns:
            FinBERTResult with sentiment, strength, and catalyst info
        """
        if not headline or not headline.strip():
            return FinBERTResult(
                sentiment='neutral',
                confidence=0.0,
                catalyst_strength=1,
                catalyst_type='OTHER',
                keywords_found=[],
                reasoning='Empty headline'
            )
        
        # Load model if needed
        self._load_model()
        
        # Step 1: FinBERT sentiment analysis
        sentiment_result = self._get_finbert_sentiment(headline)
        
        # Step 2: Catalyst classification and strength
        catalyst_info = self._classify_catalyst(headline)
        
        # Step 3: Calculate final strength based on sentiment + catalyst
        final_strength = self._calculate_final_strength(
            sentiment_result, catalyst_info, age_hours
        )
        
        # Step 4: Generate reasoning
        reasoning = self._generate_reasoning(sentiment_result, catalyst_info, final_strength)
        
        return FinBERTResult(
            sentiment=sentiment_result['label'].lower(),
            confidence=sentiment_result['score'],
            catalyst_strength=final_strength,
            catalyst_type=catalyst_info['type'],
            keywords_found=catalyst_info['keywords'],
            reasoning=reasoning
        )
    
    def _get_finbert_sentiment(self, headline: str) -> Dict:
        """Get sentiment from FinBERT model"""
        if not self.model_loaded:
            # Fallback to simple keyword analysis
            return self._fallback_sentiment(headline)
        
        try:
            # FinBERT analysis
            results = self.sentiment_pipeline(headline)
            
            # Handle the results format (list of dicts)
            if isinstance(results, list) and len(results) > 0:
                if isinstance(results[0], list):
                    # Format: [[{'label': 'positive', 'score': 0.8}, ...]]
                    scores = results[0]
                else:
                    # Format: [{'label': 'positive', 'score': 0.8}, ...]
                    scores = results
                
                # Find the highest confidence result
                best_result = max(scores, key=lambda x: x['score'])
                
                return {
                    'label': best_result['label'],
                    'score': best_result['score']
                }
            else:
                # Fallback if unexpected format
                return {'label': 'neutral', 'score': 0.5}
            
        except Exception as e:
            logger.warning(f"FinBERT analysis failed: {e}")
            return self._fallback_sentiment(headline)
    
    def _fallback_sentiment(self, headline: str) -> Dict:
        """Fallback sentiment analysis if FinBERT fails"""
        headline_lower = headline.lower()
        
        positive_words = ['approval', 'beat', 'growth', 'success', 'win', 'breakthrough', 'positive']
        negative_words = ['fail', 'reject', 'loss', 'decline', 'warning', 'concern']
        
        pos_count = sum(1 for word in positive_words if word in headline_lower)
        neg_count = sum(1 for word in negative_words if word in headline_lower)
        
        if pos_count > neg_count:
            return {'label': 'positive', 'score': 0.7}
        elif neg_count > pos_count:
            return {'label': 'negative', 'score': 0.7}
        else:
            return {'label': 'neutral', 'score': 0.6}
    
    def _classify_catalyst(self, headline: str) -> Dict:
        """Classify catalyst type and find keywords"""
        headline_lower = headline.lower()
        
        best_match = {
            'type': 'OTHER',
            'keywords': [],
            'base_strength': 3,
            'multiplier': 1.0
        }
        
        max_keywords_found = 0
        
        # Check each catalyst type
        for catalyst_type, pattern_info in self.catalyst_patterns.items():
            keywords_found = []
            
            for keyword in pattern_info['keywords']:
                if keyword in headline_lower:
                    keywords_found.append(keyword)
            
            # Choose the catalyst type with most keyword matches
            if len(keywords_found) > max_keywords_found:
                max_keywords_found = len(keywords_found)
                best_match = {
                    'type': catalyst_type,
                    'keywords': keywords_found,
                    'base_strength': pattern_info['base_strength'],
                    'multiplier': pattern_info['positive_multiplier']
                }
        
        return best_match
    
    def _calculate_final_strength(self, sentiment_result: Dict, catalyst_info: Dict, age_hours: float) -> int:
        """Calculate final catalyst strength (1-10) - ENHANCED for FinBERT-tone"""
        base_strength = catalyst_info['base_strength']
        
        # ENHANCED sentiment modifier leveraging FinBERT-tone's better accuracy
        sentiment_confidence = sentiment_result['score']
        sentiment_label = sentiment_result['label'].lower()
        
        if sentiment_label == 'positive':
            # FinBERT-tone has better positive sentiment detection
            confidence_boost = 1.0 + (sentiment_confidence - 0.5) * 0.4  # Scale 0.5-1.0 to 1.0-1.2
            sentiment_modifier = catalyst_info.get('positive_multiplier', 1.2) * confidence_boost
        elif sentiment_label == 'negative':
            # More nuanced negative handling for different catalyst types
            if catalyst_info['type'] in ['FDA', 'M&A', 'AI_TECH']:
                sentiment_modifier = 0.4  # Less penalty for high-impact catalysts
            else:
                sentiment_modifier = 0.25  # Standard penalty
        else:  # neutral
            # Better neutral handling with confidence consideration
            neutral_modifier = 0.7 + (sentiment_confidence * 0.2)  # Scale 0.7-0.9
            sentiment_modifier = neutral_modifier
        
        # Enhanced keyword bonus with 2024-2025 term weighting
        keyword_bonus = min(len(catalyst_info['keywords']) * 0.6, 2.5)  # Increased max bonus
        
        # ENHANCED age penalty with catalyst-specific decay
        age_penalty = 1.0
        catalyst_type = catalyst_info.get('type', 'OTHER')
        
        # Different decay rates for different catalyst types
        if catalyst_type in ['FDA', 'BREAKTHROUGH', 'AI_TECH']:
            # Slower decay for breakthrough news
            if age_hours > 24:
                age_penalty = 0.6
            elif age_hours > 12:
                age_penalty = 0.8
            elif age_hours > 6:
                age_penalty = 0.9
        elif catalyst_type in ['M&A', 'CONTRACT']:
            # Standard decay for M&A/contracts
            if age_hours > 12:
                age_penalty = 0.7
            elif age_hours > 6:
                age_penalty = 0.85
        else:
            # Faster decay for earnings/other
            if age_hours > 6:
                age_penalty = 0.65
            elif age_hours > 3:
                age_penalty = 0.8
        
        # Calculate final strength with enhanced formula
        final_strength = (base_strength + keyword_bonus) * sentiment_modifier * age_penalty
        
        # Ensure it's in valid range
        return max(1, min(10, int(round(final_strength))))
    
    def _generate_reasoning(self, sentiment_result: Dict, catalyst_info: Dict, strength: int) -> str:
        """Generate human-readable reasoning"""
        sentiment = sentiment_result['label'].lower()
        confidence = sentiment_result['score']
        catalyst_type = catalyst_info['type']
        keywords = catalyst_info['keywords']
        
        reasoning = f"{sentiment.upper()} sentiment ({confidence:.2f} confidence)"
        
        if keywords:
            reasoning += f", {catalyst_type} catalyst with keywords: {', '.join(keywords[:3])}"
        else:
            reasoning += f", classified as {catalyst_type}"
        
        reasoning += f" -> Strength: {strength}/10"
        
        return reasoning

# Convenience function for easy testing
def test_finbert_analyzer():
    """Test function for FinBERT analyzer"""
    analyzer = FinBERTAnalyzer()
    
    test_headlines = [
        "Tharimmune Reports Pharmacokinetic Simulation Results for TH104 as Prophylaxis Against Respiratory Depression",
        "Company beats earnings estimates by 15%",
        "FDA approves breakthrough cancer treatment",
        "Stock price declines on regulatory concerns"
    ]
    
    print("🧪 Testing FinBERT Analyzer...")
    for headline in test_headlines:
        result = analyzer.analyze_headline(headline)
        print(f"\nHeadline: {headline[:60]}...")
        print(f"Sentiment: {result.sentiment} ({result.confidence:.2f})")
        print(f"Strength: {result.catalyst_strength}/10")
        print(f"Type: {result.catalyst_type}")
        print(f"Keywords: {result.keywords_found}")
        print(f"Reasoning: {result.reasoning}")

if __name__ == "__main__":
    test_finbert_analyzer()