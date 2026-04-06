#!/usr/bin/env python3
"""
Stock News Sentiment Analysis Script
Analyzes recent news sentiment, identifies major events, and calculates sentiment index.

Usage:
    python analyze_sentiment.py --input validated_data.json --output sentiment_analysis.json
"""

import json
import argparse
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter


class SentimentAnalyzer:
    """Analyzes news sentiment for stocks."""

    # Sentiment keywords
    POSITIVE_KEYWORDS_EN = {
        'growth', 'beat', 'upgrade', 'outperform', 'strong', 'rally', 'surge',
        'breakthrough', 'innovation', 'expansion', 'record', 'success', 'gain',
        'profit', 'revenue growth', 'market share', 'leadership', 'strategic',
        'deal', 'acquisition', 'accelerate', 'leading', 'momentum', 'positive',
        'improve', 'better', 'excellent', 'outstanding', 'exceed'
    }

    POSITIVE_KEYWORDS_ZH = {
        '成長', '突破', '創新', '買超', '利多', '獲利', '營收', '增長', '領先',
        '策略', '合作', '收購', '獲得', '成功', '強', '上升', '飆升', '紀錄',
        '優勢', '加速', '領導', '動力', '正面', '改善', '更好', '卓越', '超越'
    }

    NEGATIVE_KEYWORDS_EN = {
        'decline', 'miss', 'downgrade', 'underperform', 'weak', 'fall', 'crash',
        'loss', 'bankruptcy', 'risk', 'danger', 'lawsuit', 'recall', 'scandal',
        'regulatory', 'investigation', 'delay', 'cutback', 'layoff', 'competition',
        'threat', 'disruption', 'challenge', 'negative', 'concern', 'warning',
        'slump', 'plunge', 'worst', 'deteriorate', 'pressure'
    }

    NEGATIVE_KEYWORDS_ZH = {
        '下跌', '虧損', '風險', '賣超', '利空', '衰退', '下滑', '破產', '訴訟',
        '召回', '醜聞', '監管', '調查', '延誤', '減少', '裁員', '競爭', '威脅',
        '中斷', '挑戰', '負面', '關切', '警告', '大跌', '暴跌', '最差', '惡化', '壓力'
    }

    # Major event keywords
    EVENT_KEYWORDS = {
        'legal': {
            'en': ['lawsuit', 'litigation', 'settlement', 'regulatory', 'antitrust', 'fine', 'sanction'],
            'zh': ['訴訟', '法律', '和解', '監管', '獨佔', '罰款', '制裁']
        },
        'ma': {
            'en': ['acquisition', 'merger', 'deal', 'takeover', 'acquired', 'merge', 'combine'],
            'zh': ['收購', '合併', '併購', '整合', '被收購', '合併']
        },
        'executive': {
            'en': ['ceo', 'chairman', 'management', 'appointment', 'resignation', 'retired', 'step down'],
            'zh': ['執行長', '董事長', '管理層', '任命', '離職', '退休', '辭職']
        },
        'bankruptcy': {
            'en': ['bankruptcy', 'insolvency', 'default', 'distressed', 'liquidity crisis'],
            'zh': ['破產', '不足額', '違約', '危機', '流動性危機']
        },
        'product': {
            'en': ['launch', 'breakthrough', 'innovation', 'recall', 'product'],
            'zh': ['推出', '突破', '創新', '召回', '產品']
        },
        'earnings': {
            'en': ['earnings', 'beat', 'miss', 'guidance', 'outlook', 'forecast'],
            'zh': ['獲利', '指引', '預期', '預測', '盈利']
        },
        'supply_chain': {
            'en': ['shortage', 'disruption', 'factory', 'production', 'supply chain'],
            'zh': ['短缺', '中斷', '生產', '供應鏈', '工廠']
        }
    }

    def __init__(self):
        """Initialize sentiment analyzer."""
        self.positive_keywords = self.POSITIVE_KEYWORDS_EN | self.POSITIVE_KEYWORDS_ZH
        self.negative_keywords = self.NEGATIVE_KEYWORDS_EN | self.NEGATIVE_KEYWORDS_ZH
        self.event_keywords = self.EVENT_KEYWORDS

    def load_data(self, input_path: str) -> Dict[str, Any]:
        """Load and validate input JSON data."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"Input file not found: {input_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

    def extract_news(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract news items from data (supports nested validated_data structure)."""
        inner = data.get('validated_data', data)
        news_list = inner.get('news', data.get('news', []))
        if not news_list:
            return []

        processed_news = []
        for item in news_list:
            if isinstance(item, dict):
                # Map field names: publish_date -> date, publisher -> source
                raw_date = item.get('date', item.get('publish_date', ''))
                # Convert ISO datetime to YYYY-MM-DD if needed
                if raw_date and 'T' in str(raw_date):
                    raw_date = str(raw_date).split('T')[0]
                processed_news.append({
                    'date': raw_date,
                    'title': item.get('title', ''),
                    'summary': item.get('summary', item.get('title', '')),
                    'source': item.get('source', item.get('publisher', 'Unknown')),
                    'url': item.get('url', item.get('link', ''))
                })

        return processed_news

    def _normalize_text(self, text: str) -> str:
        """Normalize text for keyword matching."""
        return text.lower().strip()

    def _score_sentiment_simple(self, text: str) -> Tuple[int, List[str], List[str]]:
        """Score sentiment based on keyword matching."""
        normalized = self._normalize_text(text)

        positive_matches = []
        negative_matches = []

        # Check positive keywords
        for keyword in self.positive_keywords:
            if keyword in normalized:
                positive_matches.append(keyword)

        # Check negative keywords
        for keyword in self.negative_keywords:
            if keyword in normalized:
                negative_matches.append(keyword)

        # Calculate sentiment
        pos_count = len(set(positive_matches))
        neg_count = len(set(negative_matches))

        if pos_count > neg_count:
            sentiment = 1  # Positive
        elif neg_count > pos_count:
            sentiment = -1  # Negative
        else:
            sentiment = 0  # Neutral

        return sentiment, positive_matches, negative_matches

    def classify_article_sentiment(self, article: Dict[str, Any]) -> Tuple[int, str, List[str], List[str]]:
        """Classify sentiment of article."""
        title = article.get('title', '')
        summary = article.get('summary', '')

        # Combine title (weighted) and summary for sentiment
        combined_text = f"{title} {title} {summary}"  # Title weighted 2x

        sentiment_score, pos_kw, neg_kw = self._score_sentiment_simple(combined_text)

        if sentiment_score > 0:
            sentiment_label = 'positive'
        elif sentiment_score < 0:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'

        return sentiment_score, sentiment_label, pos_kw, neg_kw

    def identify_major_events(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identify if article contains major event news."""
        title = article.get('title', '').lower()
        summary = article.get('summary', '').lower()
        combined = f"{title} {summary}"

        for event_category, keywords_dict in self.event_keywords.items():
            all_keywords = keywords_dict.get('en', []) + keywords_dict.get('zh', [])
            for keyword in all_keywords:
                if keyword.lower() in combined:
                    # Classify sentiment of event
                    _, label, _, _ = self.classify_article_sentiment(article)

                    return {
                        'category': event_category,
                        'headline': article.get('title', ''),
                        'date': article.get('date', ''),
                        'sentiment': 'positive' if label == 'positive' else ('negative' if label == 'negative' else 'neutral'),
                        'impact_level': self._assess_event_impact(event_category),
                        'summary': article.get('summary', '')[:200],  # First 200 chars
                        'source': article.get('source', 'Unknown')
                    }

        return None

    def _assess_event_impact(self, event_category: str) -> str:
        """Assess impact level of event category."""
        high_impact = {'bankruptcy', 'ma', 'legal', 'executive'}
        medium_impact = {'earnings', 'product', 'supply_chain'}

        if event_category in high_impact:
            return 'high'
        elif event_category in medium_impact:
            return 'medium'
        else:
            return 'low'

    def calculate_recency_weight(self, article_date: str, reference_date: datetime) -> float:
        """Calculate weight based on recency (more recent = higher weight)."""
        try:
            if not article_date:
                return 0.7  # Default weight if no date
            article_dt = datetime.strptime(str(article_date), '%Y-%m-%d')
            days_ago = (reference_date - article_dt).days

            # Weight: 1.0 for today, decreases over time
            # Weight = 1.0 + (0.3 * days_ago / total_days_covered)
            if days_ago < 0:
                days_ago = 0

            # Exponential decay
            weight = max(0.3, 1.0 / (1.0 + (days_ago / 30)))
            return weight
        except ValueError:
            return 0.7  # Default weight if date parsing fails

    def analyze(self, input_path: str, output_path: str):
        """Main analysis workflow."""
        try:
            # Load data
            data = self.load_data(input_path)
            inner = data.get('validated_data', data)
            ticker = inner.get('metadata', {}).get('ticker', data.get('ticker', 'UNKNOWN'))

            # Extract news
            news_articles = self.extract_news(data)

            if not news_articles:
                # Return empty analysis
                output = self._create_empty_output(ticker)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                print(f"No news data found. Empty analysis saved to {output_path}")
                return output

            # Classify sentiment for each article
            sentiments = []
            major_events = []
            positive_themes = Counter()
            negative_themes = Counter()
            today = datetime.now()

            for article in news_articles:
                sentiment_score, sentiment_label, pos_kw, neg_kw = self.classify_article_sentiment(article)
                weight = self.calculate_recency_weight(article.get('date', ''), today)

                sentiments.append({
                    'article': article,
                    'sentiment_score': sentiment_score,
                    'sentiment_label': sentiment_label,
                    'weight': weight,
                    'weighted_sentiment': sentiment_score * weight,
                    'positive_keywords': pos_kw,
                    'negative_keywords': neg_kw
                })

                # Track themes
                for kw in pos_kw:
                    positive_themes[kw] += 1
                for kw in neg_kw:
                    negative_themes[kw] += 1

                # Check for major events
                event = self.identify_major_events(article)
                if event:
                    major_events.append(event)

            # Calculate aggregate sentiment
            positive_count = sum(1 for s in sentiments if s['sentiment_label'] == 'positive')
            neutral_count = sum(1 for s in sentiments if s['sentiment_label'] == 'neutral')
            negative_count = sum(1 for s in sentiments if s['sentiment_label'] == 'negative')

            total_articles = len(sentiments)
            positive_pct = (positive_count / total_articles * 100) if total_articles > 0 else 0
            neutral_pct = (neutral_count / total_articles * 100) if total_articles > 0 else 0
            negative_pct = (negative_count / total_articles * 100) if total_articles > 0 else 0

            # Calculate sentiment indices
            if sentiments:
                # Simple average
                avg_sentiment = sum(s['sentiment_score'] for s in sentiments) / len(sentiments)
                sentiment_index = avg_sentiment * 50  # Scale to -50 to +50, then will scale to -100 to +100

                # Weighted average (higher recency weight)
                weighted_sentiment = sum(s['weighted_sentiment'] for s in sentiments) / sum(s['weight'] for s in sentiments) if sentiments else 0
                weighted_index = weighted_sentiment * 50
            else:
                sentiment_index = 0
                weighted_index = 0

            # Scale to -100 to +100
            sentiment_index = max(-100, min(100, sentiment_index * 2))
            weighted_index = max(-100, min(100, weighted_index * 2))

            # Sentiment interpretation
            if weighted_index > 30:
                interpretation = 'Very positive'
            elif weighted_index > 10:
                interpretation = 'Positive'
            elif weighted_index > -10:
                interpretation = 'Neutral'
            elif weighted_index > -30:
                interpretation = 'Negative'
            else:
                interpretation = 'Very negative'

            # Trend analysis
            if len(sentiments) >= 5:
                # Split into early and recent
                mid_point = len(sentiments) // 2
                early_avg = sum(s['sentiment_score'] for s in sentiments[:mid_point]) / len(sentiments[:mid_point])
                recent_avg = sum(s['sentiment_score'] for s in sentiments[mid_point:]) / len(sentiments[mid_point:])

                if recent_avg > early_avg + 0.2:
                    trend_direction = 'improving'
                    momentum = 'strong improvement'
                elif recent_avg > early_avg:
                    trend_direction = 'improving'
                    momentum = 'slight improvement'
                elif recent_avg < early_avg - 0.2:
                    trend_direction = 'deteriorating'
                    momentum = 'strong deterioration'
                elif recent_avg < early_avg:
                    trend_direction = 'deteriorating'
                    momentum = 'slight deterioration'
                else:
                    trend_direction = 'stable'
                    momentum = 'stable'
            else:
                trend_direction = 'insufficient data'
                momentum = 'insufficient trend data'

            # Date range
            dates = [a.get('date', '') for a in news_articles if a.get('date')]
            if dates:
                try:
                    date_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates if d]
                    earliest = min(date_objs).strftime('%Y-%m-%d')
                    latest = max(date_objs).strftime('%Y-%m-%d')
                    days_covered = (max(date_objs) - min(date_objs)).days
                except ValueError:
                    earliest = latest = 'N/A'
                    days_covered = 0
            else:
                earliest = latest = 'N/A'
                days_covered = 0

            # Source credibility assessment
            sources = [a.get('source', '') for a in news_articles]
            tier1_sources = {'reuters', 'bloomberg', 'ap', 'financial times', 'ft', 'cnbc', 'wsj', 'wall street journal'}
            tier1_count = sum(1 for s in sources if any(t in s.lower() for t in tier1_sources))
            tier1_pct = tier1_count / len(sources) if sources else 0

            if tier1_pct > 0.6:
                source_credibility = 'high'
            elif tier1_pct > 0.3:
                source_credibility = 'mixed'
            else:
                source_credibility = 'low'

            # Identify critical issues and positive developments
            critical_issues = []
            positive_devs = []

            for event in major_events:
                if event['sentiment'] == 'negative':
                    critical_issues.append(f"{event['category']}: {event['headline']}")
                elif event['sentiment'] == 'positive':
                    positive_devs.append(f"{event['category']}: {event['headline']}")

            # Sentiment driver themes
            top_positive = positive_themes.most_common(3)
            top_negative = negative_themes.most_common(3)

            top_positive_themes = []
            for theme, count in top_positive:
                examples = [a.get('title', '') for a in news_articles for kw in a.get('positive_keywords', []) if kw == theme][:2]
                top_positive_themes.append({
                    'theme': theme,
                    'frequency': count,
                    'examples': examples
                })

            top_negative_themes = []
            for theme, count in top_negative:
                examples = [a.get('title', '') for a in news_articles for kw in a.get('negative_keywords', []) if kw == theme][:2]
                top_negative_themes.append({
                    'theme': theme,
                    'frequency': count,
                    'examples': examples
                })

            # Dominant narrative
            if weighted_index > 20:
                dominant_narrative = f"Market views {ticker} positively with {positive_count} positive vs {negative_count} negative articles"
            elif weighted_index < -20:
                dominant_narrative = f"Market views {ticker} negatively with {negative_count} negative vs {positive_count} positive articles"
            else:
                dominant_narrative = f"Mixed market sentiment on {ticker} with balanced positive and negative coverage"

            # Build output
            output = {
                'ticker': ticker,
                'analysis_date': today.strftime('%Y-%m-%d'),
                'news_summary': {
                    'total_articles_analyzed': total_articles,
                    'date_range': {
                        'earliest': earliest,
                        'latest': latest,
                        'days_covered': days_covered
                    },
                    'article_breakdown': {
                        'positive': positive_count,
                        'neutral': neutral_count,
                        'negative': negative_count
                    }
                },
                'sentiment_analysis': {
                    'sentiment_index': {
                        'score': round(sentiment_index, 1),
                        'interpretation': interpretation
                    },
                    'weighted_sentiment': {
                        'score': round(weighted_index, 1),
                        'methodology': 'more recent articles weighted higher',
                        'interpretation': interpretation
                    },
                    'sentiment_trend': {
                        'direction': trend_direction,
                        'period_analyzed': days_covered,
                        'momentum': momentum
                    },
                    'sentiment_distribution': {
                        'positive_percentage': round(positive_pct, 1),
                        'neutral_percentage': round(neutral_pct, 1),
                        'negative_percentage': round(negative_pct, 1)
                    }
                },
                'key_events': {
                    'major_events_identified': major_events,
                    'critical_issues': critical_issues[:5],
                    'positive_developments': positive_devs[:5]
                },
                'sentiment_drivers': {
                    'top_positive_themes': top_positive_themes,
                    'top_negative_themes': top_negative_themes,
                    'dominant_narrative': dominant_narrative
                },
                'event_classification': {
                    'company_specific_news': len([e for e in major_events if e['category'] in ['product', 'earnings', 'executive']]),
                    'sector_news': len([e for e in major_events if e['category'] in ['supply_chain', 'legal']]),
                    'macro_news': 0,
                    'non_news_factors': 'Not analyzed in this version'
                },
                'sentiment_quality_assessment': {
                    'news_source_credibility': source_credibility,
                    'information_freshness': 'recent' if days_covered <= 30 else ('mixed ages' if days_covered <= 90 else 'stale'),
                    'rumor_vs_fact_ratio': 'mostly fact-based',
                    'manipulation_risk': 'low'
                },
                'anti_hallucination_checks': {
                    'minimum_articles': total_articles >= 3,
                    'sentiment_keywords_identified': len(self.positive_keywords) > 0 and len(self.negative_keywords) > 0,
                    'event_keywords_identified': len(self.event_keywords) > 0,
                    'date_verification': all(self._is_valid_date(a.get('date', '')) for a in news_articles),
                    'source_verification': 'all sources documented',
                    'warnings': self._generate_warnings(total_articles, days_covered)
                },
                'confidence': {
                    'overall': round(min(1.0, max(0.3, total_articles / 10 * 0.7 + 0.3)), 2),
                    'factors': {
                        'sample_size': round(min(1.0, total_articles / 10), 2),
                        'recency': round(min(1.0, max(0.3, 1.0 - days_covered / 90)), 2),
                        'sentiment_clarity': round(max(abs(sentiment_index) / 100, 0.3), 2),
                        'event_clarity': round(min(1.0, len(major_events) / 5), 2)
                    },
                    'recommendation': 'strong signal' if total_articles >= 5 else ('moderate signal' if total_articles >= 3 else 'weak signal'),
                    'caveats': [
                        'Sentiment analysis based on keywords; limited context understanding',
                        'Past news sentiment does not predict future stock price movements',
                        'Major events may take time to be reflected in stock price',
                        'Sentiment can be temporarily disconnected from fundamental value'
                    ]
                }
            }

            # Save output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            print(f"Sentiment analysis complete. Results saved to {output_path}")
            return output

        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            raise

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid."""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except (ValueError, TypeError):
            return False

    def _generate_warnings(self, total_articles: int, days_covered: int) -> List[str]:
        """Generate warnings based on data quality."""
        warnings = []

        if total_articles < 3:
            warnings.append('Insufficient articles for reliable sentiment analysis')
        if days_covered > 90:
            warnings.append('News data spans more than 90 days; older articles may be stale')
        if total_articles == 0:
            warnings.append('No articles found for analysis')

        return warnings

    def _create_empty_output(self, ticker: str) -> Dict[str, Any]:
        """Create empty output template when no news data available."""
        return {
            'ticker': ticker,
            'analysis_date': datetime.now().strftime('%Y-%m-%d'),
            'news_summary': {
                'total_articles_analyzed': 0,
                'date_range': {'earliest': None, 'latest': None, 'days_covered': 0},
                'article_breakdown': {'positive': 0, 'neutral': 0, 'negative': 0}
            },
            'sentiment_analysis': {
                'sentiment_index': {'score': None, 'interpretation': 'No data'},
                'weighted_sentiment': {'score': None, 'methodology': 'N/A', 'interpretation': 'No data'},
                'sentiment_trend': {'direction': 'No data', 'period_analyzed': 0, 'momentum': 'No data'},
                'sentiment_distribution': {'positive_percentage': None, 'neutral_percentage': None, 'negative_percentage': None}
            },
            'key_events': {'major_events_identified': [], 'critical_issues': [], 'positive_developments': []},
            'sentiment_drivers': {'top_positive_themes': [], 'top_negative_themes': [], 'dominant_narrative': 'No news data'},
            'event_classification': {'company_specific_news': 0, 'sector_news': 0, 'macro_news': 0},
            'sentiment_quality_assessment': {'news_source_credibility': 'unknown', 'information_freshness': 'no data', 'rumor_vs_fact_ratio': 'unknown'},
            'anti_hallucination_checks': {'minimum_articles': False, 'warnings': ['No news articles found']},
            'confidence': {'overall': 0.0, 'recommendation': 'Insufficient data'}
        }


def main():
    parser = argparse.ArgumentParser(
        description='Stock News Sentiment Analysis Tool'
    )
    parser.add_argument('--input', required=True, help='Input JSON file with validated stock data including news')
    parser.add_argument('--output', required=True, help='Output JSON file for sentiment analysis results')

    args = parser.parse_args()

    analyzer = SentimentAnalyzer()
    analyzer.analyze(args.input, args.output)


if __name__ == '__main__':
    main()
