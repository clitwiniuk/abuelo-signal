# scanner/sentiment_analyzer.py
"""
Sentiment Analysis for News Catalysts
Determines if news catalysts are positive or negative for long positions
"""

import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum

class SentimentType(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"

@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    sentiment: SentimentType
    confidence: float  # 0-1 score
    positive_keywords: List[str]
    negative_keywords: List[str]
    context_phrases: List[str]
    summary: str

class CatalystSentimentAnalyzer:
    """Analyze sentiment of financial news catalysts"""
    
    def __init__(self):
        # Positive catalyst patterns for LONG positions
        self.positive_patterns = {
            # FDA/Regulatory Success (Enhanced for better detection)
            'fda_approval': ['fda approval', 'fda approved', 'approved by fda', 'regulatory approval',
                           'announces.*fda approval', 'full fda approval', 'fda.*approved.*therapy',
                           'first.*approved therapy', 'only approved therapy', 'receives.*fda approval'],
            'clinical_success': ['trial success', 'positive results', 'met endpoints', 'phase.*success'],
            'breakthrough': ['breakthrough', 'breakthrough therapy', 'fast track', 'orphan designation', 'priority review'],
            
            # Financial Success
            'earnings_beat': ['beat earnings', 'beat estimates', 'beats earnings', 'beats estimates', 'exceeds expectations', 'strong earnings'],
            'revenue_growth': ['revenue growth', 'sales increase', 'record revenue', 'revenue up'],
            'guidance_raise': ['raised guidance', 'raises guidance', 'increased outlook', 'upgraded forecast'],
            
            # M&A/Partnerships (Usually positive for target)
            'acquisition': ['acquisition.*target', 'buyout offer', 'takeover bid', 'merger agreement'],
            'partnership': ['strategic partnership', 'partnership', 'collaboration', 'joint venture', 'alliance'],
            
            # Business Wins
            'contracts': ['contract awarded', 'order received', 'major order', 'order', 'deal signed', 'agreement signed'],
            'expansion': ['expansion', 'new facility', 'capacity increase', 'market entry'],
            
            # Analyst/Market Positive
            'upgrades': ['analyst upgrade', 'price target.*raised', 'rating.*upgrade', 'recommendation.*buy'],
            'institutional': ['institutional buying', 'insider buying', 'investment from'],
            
            # Product/Technology
            'product_success': ['product launch', 'new product', 'patent granted', 'innovation'],
            'market_success': ['market share.*gain', 'competitive advantage', 'market leader']
        }
        
        # Negative catalyst patterns for LONG positions
        self.negative_patterns = {
            # FDA/Regulatory Issues
            'fda_rejection': ['fda rejection', 'fda denied', 'regulatory delay', 'clinical hold'],
            'trial_failure': ['trial failed', 'missed endpoints', 'safety concerns', 'adverse events'],
            
            # Financial Issues
            'earnings_miss': ['missed earnings', 'missed estimates', 'below expectations', 'weak earnings'],
            'revenue_decline': ['revenue decline', 'sales drop', 'revenue down', 'sales miss'],
            'guidance_cut': ['lowered guidance', 'reduced outlook', 'cut forecast', 'outlook.*down'],
            
            # Legal/Compliance
            'legal_issues': ['lawsuit', 'investigation', 'sec inquiry', 'regulatory.*investigation'],
            'fraud': ['fraud', 'accounting.*irregularities', 'financial.*misconduct'],
            
            # Business Problems
            'financial_distress': ['bankruptcy', 'debt default', 'financial.*difficulty', 'cash.*concern'],
            'operational': ['layoffs', 'plant.*closure', 'restructuring', 'downsizing'],
            'product_issues': ['recall', 'safety.*issue', 'product.*failure', 'quality.*concern'],
            
            # Market/Analyst Negative
            'downgrades': ['analyst.*downgrade', 'price target.*cut', 'rating.*sell', 'recommendation.*sell'],
            'short_attacks': ['short.*report', 'short.*seller', 'bearish.*report'],
            
            # Market Structure
            'delisting': ['delisting', 'nasdaq.*compliance', 'exchange.*notice', 'halt.*trading']
        }
        
        # Negation patterns that reverse sentiment (Enhanced with FDA-specific exceptions)
        self.negation_patterns = [
            # Direct negations
            'not', 'no', 'never', 'none', 'neither', 'nothing', 'nowhere',
            # Failed/missed patterns
            'failed to', 'missed', 'unable to', 'did not', 'does not', 'will not',
            'cannot', 'could not', 'should not', 'would not',
            # Rejection patterns
            'rejected', 'denied', 'declined', 'refused', 'suspended', 'halted',
            # Delay patterns
            'delayed', 'postponed', 'deferred', 'pushed back', 'on hold'
        ]
        
        # FDA-specific positive phrases that should override negation detection
        self.fda_positive_overrides = [
            'fda approval', 'fda approved', 'announces.*fda approval', 'full fda approval',
            'first.*approved therapy', 'only approved therapy', 'approved.*therapy.*treatment'
        ]
        
        # Magnitude modifiers (strength of catalyst)
        self.strong_positive_modifiers = [
            'significantly', 'substantially', 'dramatically', 'massively', 'greatly',
            'strongly', 'sharply', 'impressively', 'record-breaking', 'unprecedented',
            'major', 'huge', 'enormous', 'exceptional', 'outstanding'
        ]
        
        self.moderate_positive_modifiers = [
            'moderately', 'solid', 'good', 'decent', 'notable', 'considerable',
            'meaningful', 'positive', 'favorable', 'encouraging'
        ]
        
        self.weak_positive_modifiers = [
            'slightly', 'marginally', 'barely', 'modest', 'minor', 'small',
            'limited', 'minimal', 'narrow', 'thin'
        ]
        
        self.strong_negative_modifiers = [
            'dramatically', 'significantly', 'substantially', 'severely', 'sharply',
            'deeply', 'heavily', 'major', 'massive', 'huge', 'catastrophic'
        ]
        
        self.moderate_negative_modifiers = [
            'concerning', 'disappointing', 'weak', 'poor', 'negative', 'adverse',
            'unfavorable', 'troubling', 'worrying'
        ]
        
        # Conditional/uncertainty words that reduce confidence
        self.uncertainty_words = [
            'potential', 'possible', 'rumor', 'speculation', 'may', 'might',
            'could', 'preliminary', 'unconfirmed', 'alleged', 'reportedly',
            'expected', 'anticipated', 'projected', 'estimated'
        ]
        
        # Context qualifiers that affect interpretation
        self.timing_qualifiers = {
            'immediate': 1.2,      # Boost confidence for immediate impact
            'pending': 0.7,        # Reduce for pending/future events
            'approved': 1.3,       # Strong boost for completed approvals
            'announced': 1.1,      # Slight boost for announcements
            'confirmed': 1.2,      # Boost for confirmed events
            'rumored': 0.5,        # Major reduction for rumors
            'expected': 0.8,       # Moderate reduction for expected events
        }
    
    def analyze_text(self, text: str, ticker: str = "") -> SentimentResult:
        """Enhanced sentiment analysis with negation, magnitude, and context detection"""
        
        text_lower = text.lower()
        positive_matches = []
        negative_matches = []
        confidence_score = 0.5  # Start neutral
        magnitude_adjustments = []
        negation_detected = False
        
        # Step 1: Detect negations that might reverse sentiment
        negation_contexts = self._detect_negations(text_lower)
        
        # Step 2: Find positive patterns (with negation awareness)
        for category, patterns in self.positive_patterns.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower))
                for match in matches:
                    match_text = match.group()
                    match_start = match.start()
                    
                    # Check if this match is negated
                    is_negated = self._is_phrase_negated(text_lower, match_start, match_text, negation_contexts)
                    
                    if is_negated:
                        # Convert positive to negative due to negation
                        negative_matches.append(f"negated_{match_text}")
                        confidence_score -= 0.15  # Stronger penalty for negated positives
                        negation_detected = True
                    else:
                        positive_matches.append(match_text)
                        # Calculate magnitude-adjusted score
                        magnitude_boost = self._calculate_magnitude_boost(text_lower, match_start, match_text)
                        confidence_score += (0.1 + magnitude_boost)
                        magnitude_adjustments.append(magnitude_boost)
        
        # Step 3: Find negative patterns (with negation awareness)
        for category, patterns in self.negative_patterns.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower))
                for match in matches:
                    match_text = match.group()
                    match_start = match.start()
                    
                    # Check if this negative is negated (double negative = positive)
                    is_negated = self._is_phrase_negated(text_lower, match_start, match_text, negation_contexts)
                    
                    if is_negated:
                        # Double negative becomes positive
                        positive_matches.append(f"double_neg_{match_text}")
                        confidence_score += 0.1
                        negation_detected = True
                    else:
                        negative_matches.append(match_text)
                        # Calculate magnitude-adjusted score
                        magnitude_penalty = self._calculate_magnitude_penalty(text_lower, match_start, match_text)
                        confidence_score -= (0.1 + magnitude_penalty)
                        magnitude_adjustments.append(-magnitude_penalty)
        
        # Step 4: Apply timing qualifiers
        timing_adjustment = self._calculate_timing_adjustment(text_lower)
        confidence_score *= timing_adjustment
        
        # Step 5: Reduce confidence for uncertainty
        uncertainty_penalty = self._calculate_uncertainty_penalty(text_lower)
        confidence_score -= uncertainty_penalty
        
        # Step 6: Determine final sentiment
        sentiment = self._determine_final_sentiment(positive_matches, negative_matches, negation_detected)
        
        # Step 7: Clamp confidence score
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        # Step 8: Generate enhanced summary
        summary = self._generate_enhanced_summary(sentiment, positive_matches, negative_matches, 
                                                ticker, magnitude_adjustments, negation_detected)
        
        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence_score,
            positive_keywords=positive_matches,
            negative_keywords=negative_matches,
            context_phrases=self._extract_context_phrases(text, positive_matches + negative_matches),
            summary=summary
        )
    
    def _extract_context_phrases(self, text: str, keywords: List[str]) -> List[str]:
        """Extract relevant phrases containing keywords"""
        phrases = []
        sentences = re.split(r'[.!?]+', text)
        
        for keyword in keywords[:3]:  # Limit to first 3 keywords
            for sentence in sentences:
                if keyword.lower() in sentence.lower():
                    # Clean and truncate sentence
                    clean_sentence = sentence.strip()[:100]
                    if clean_sentence and clean_sentence not in phrases:
                        phrases.append(clean_sentence)
                    break
        
        return phrases[:3]  # Max 3 phrases
    
    def _detect_negations(self, text: str) -> List[Tuple[int, str]]:
        """Detect negation patterns and their positions in text"""
        negations = []
        for pattern in self.negation_patterns:
            for match in re.finditer(pattern, text):
                negations.append((match.start(), pattern))
        return negations
    
    def _is_phrase_negated(self, text: str, phrase_start: int, phrase: str, 
                          negation_contexts: List[Tuple[int, str]]) -> bool:
        """Check if a phrase is negated by nearby negation words"""
        
        # First, check if this is an FDA positive override phrase
        phrase_lower = phrase.lower()
        for override_pattern in self.fda_positive_overrides:
            if re.search(override_pattern, phrase_lower):
                return False  # Never negate FDA approval phrases
        
        # Look for negations within 50 characters before the phrase
        window_start = max(0, phrase_start - 50)
        
        for neg_pos, neg_word in negation_contexts:
            if window_start <= neg_pos < phrase_start:
                # Check if there are intervening punctuation that might break the negation
                between_text = text[neg_pos + len(neg_word):phrase_start]
                if not re.search(r'[.!?;]', between_text):  # No sentence breaks
                    return True
        return False
    
    def _calculate_magnitude_boost(self, text: str, match_start: int, match_text: str) -> float:
        """Calculate boost based on magnitude modifiers near positive matches"""
        # Look for modifiers within 30 characters before and after the match
        window_start = max(0, match_start - 30)
        window_end = min(len(text), match_start + len(match_text) + 30)
        context = text[window_start:window_end]
        
        boost = 0.0
        
        # Check for strong positive modifiers
        for modifier in self.strong_positive_modifiers:
            if modifier in context:
                boost += 0.15
                break
        
        # Check for moderate positive modifiers
        for modifier in self.moderate_positive_modifiers:
            if modifier in context:
                boost += 0.08
                break
        
        # Check for weak positive modifiers (actually reduce boost)
        for modifier in self.weak_positive_modifiers:
            if modifier in context:
                boost -= 0.05
                break
        
        return max(0.0, min(boost, 0.2))  # Cap boost at 0.2
    
    def _calculate_magnitude_penalty(self, text: str, match_start: int, match_text: str) -> float:
        """Calculate penalty based on magnitude modifiers near negative matches"""
        window_start = max(0, match_start - 30)
        window_end = min(len(text), match_start + len(match_text) + 30)
        context = text[window_start:window_end]
        
        penalty = 0.0
        
        # Check for strong negative modifiers
        for modifier in self.strong_negative_modifiers:
            if modifier in context:
                penalty += 0.15
                break
        
        # Check for moderate negative modifiers
        for modifier in self.moderate_negative_modifiers:
            if modifier in context:
                penalty += 0.08
                break
        
        return max(0.0, min(penalty, 0.2))  # Cap penalty at 0.2
    
    def _calculate_timing_adjustment(self, text: str) -> float:
        """Adjust confidence based on timing qualifiers"""
        adjustment = 1.0
        
        for qualifier, multiplier in self.timing_qualifiers.items():
            if qualifier in text:
                adjustment *= multiplier
                break  # Take first match
        
        return max(0.3, min(adjustment, 1.5))  # Keep within reasonable bounds
    
    def _calculate_uncertainty_penalty(self, text: str) -> float:
        """Calculate penalty for uncertainty words"""
        uncertainty_count = sum(1 for word in self.uncertainty_words if word in text)
        return min(uncertainty_count * 0.05, 0.3)  # Max 30% penalty
    
    def _determine_final_sentiment(self, positive_matches: List[str], 
                                 negative_matches: List[str], negation_detected: bool) -> SentimentType:
        """Determine final sentiment with enhanced logic"""
        pos_count = len(positive_matches)
        neg_count = len(negative_matches)
        
        # If negation was detected, be more cautious
        if negation_detected:
            if pos_count > neg_count + 1:  # Need stronger positive signal
                return SentimentType.POSITIVE
            elif neg_count > pos_count + 1:  # Need stronger negative signal
                return SentimentType.NEGATIVE
            else:
                return SentimentType.MIXED
        else:
            # Standard logic
            if pos_count > neg_count:
                return SentimentType.POSITIVE if neg_count == 0 else SentimentType.MIXED
            elif neg_count > pos_count:
                return SentimentType.NEGATIVE if pos_count == 0 else SentimentType.MIXED
            else:
                return SentimentType.NEUTRAL
    
    def _generate_enhanced_summary(self, sentiment: SentimentType, positive: List[str], 
                                 negative: List[str], ticker: str, magnitude_adjustments: List[float],
                                 negation_detected: bool) -> str:
        """Generate enhanced human-readable summary"""
        
        # Calculate average magnitude
        avg_magnitude = sum(magnitude_adjustments) / len(magnitude_adjustments) if magnitude_adjustments else 0
        
        # Build summary with magnitude info
        if sentiment == SentimentType.POSITIVE:
            key_catalysts = positive[:2]
            magnitude_desc = "STRONG" if avg_magnitude > 0.1 else "MODERATE" if avg_magnitude > 0.05 else "WEAK"
            base_summary = f"POSITIVE ({magnitude_desc}) for {ticker}: {', '.join(key_catalysts)}"
        
        elif sentiment == SentimentType.NEGATIVE:
            key_catalysts = negative[:2]
            magnitude_desc = "STRONG" if avg_magnitude < -0.1 else "MODERATE" if avg_magnitude < -0.05 else "WEAK"
            base_summary = f"NEGATIVE ({magnitude_desc}) for {ticker}: {', '.join(key_catalysts)}"
        
        elif sentiment == SentimentType.MIXED:
            base_summary = f"MIXED for {ticker}: {len(positive)} positive vs {len(negative)} negative catalysts"
        
        else:
            base_summary = f"NEUTRAL for {ticker}: No clear catalysts detected"
        
        # Add negation warning if detected
        if negation_detected:
            base_summary += " (⚠️ Negations detected)"
        
        return base_summary
    
    def _generate_summary(self, sentiment: SentimentType, positive: List[str], 
                         negative: List[str], ticker: str) -> str:
        """Generate human-readable summary (legacy method)"""
        return self._generate_enhanced_summary(sentiment, positive, negative, ticker, [], False)
    
    def is_suitable_for_long(self, sentiment_result: SentimentResult, 
                           min_confidence: float = 0.6) -> bool:
        """Determine if catalyst is suitable for LONG positions"""
        
        # For long positions, we want:
        # 1. Positive sentiment with good confidence
        # 2. OR mixed sentiment with more positive than negative
        
        if sentiment_result.sentiment == SentimentType.POSITIVE:
            return sentiment_result.confidence >= min_confidence
        
        elif sentiment_result.sentiment == SentimentType.MIXED:
            # Mixed: check if positive outweighs negative
            pos_count = len(sentiment_result.positive_keywords)
            neg_count = len(sentiment_result.negative_keywords)
            return pos_count > neg_count and sentiment_result.confidence >= min_confidence
        
        else:
            return False

# Test function
def test_sentiment_analyzer():
    """Test the sentiment analyzer with sample news"""
    
    analyzer = CatalystSentimentAnalyzer()
    
    test_cases = [
        # Original cases
        ("GEVO", "GEVO announces breakthrough in sustainable aviation fuel production, signs major partnership with airline"),
        ("NVDA", "NVIDIA dramatically beats earnings estimates, significantly raises guidance on strong AI demand"),
        ("TLRY", "Tilray faces FDA investigation over clinical trial data irregularities"),
        
        # Negation test cases
        ("AAPL", "Apple did not beat earnings estimates, failed to meet guidance expectations"),
        ("TSLA", "Tesla's FDA approval was not granted, trial results were disappointing"),
        ("AMD", "AMD's partnership talks failed, no deal was signed despite speculation"),
        
        # Magnitude test cases  
        ("MSFT", "Microsoft slightly beats earnings, marginally raises guidance"),
        ("GOOGL", "Google massively outperforms estimates, dramatically increases outlook"),
        ("META", "Meta reports modest revenue growth, small partnership announced"),
        
        # Complex/mixed cases
        ("AMZN", "Amazon beats revenue but misses profit, mixed quarterly results announced"),
        ("NFLX", "Netflix confirmed major content deal, but subscriber growth disappoints analysts"),
        
        # Timing/uncertainty cases
        ("UBER", "Uber's potential acquisition rumored, unconfirmed reports suggest deal pending"),
        ("LYFT", "Lyft approved for expansion, immediate implementation confirmed")
    ]
    
    print("🧪 Testing Sentiment Analyzer")
    print("=" * 60)
    
    for ticker, news_text in test_cases:
        print(f"\n📰 {ticker}: {news_text}")
        
        result = analyzer.analyze_text(news_text, ticker)
        
        print(f"   📊 Sentiment: {result.sentiment.value.upper()}")
        print(f"   🎯 Confidence: {result.confidence:.2f}")
        print(f"   ✅ Positive: {result.positive_keywords}")
        print(f"   ❌ Negative: {result.negative_keywords}")
        print(f"   📈 Good for LONG: {analyzer.is_suitable_for_long(result)}")
        print(f"   📝 Summary: {result.summary}")

if __name__ == "__main__":
    test_sentiment_analyzer()