#!/usr/bin/env python3
"""
Stock Institutional Flow & Analyst Consensus Analysis Script
Analyzes institutional ownership, insider transactions, and analyst recommendations.

Usage:
    python analyze_institutional.py --input validated_data.json --output institutional_analysis.json
"""

import json
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict


class InstitutionalAnalyzer:
    """Analyzes institutional flows and analyst consensus."""

    MAJOR_INSTITUTIONS = {
        'BlackRock': 'passive',
        'Vanguard': 'passive',
        'State Street': 'passive',
        'Berkshire Hathaway': 'active',
        'Citadel': 'hedge fund',
        'Elliott Management': 'hedge fund',
        'D.E. Shaw': 'hedge fund',
        'Fidelity': 'active',
        'T. Rowe Price': 'active',
        'CalPERS': 'pension fund',
        'APG': 'pension fund',
        'MassMutual': 'insurance',
        'PIMCO': 'active'
    }

    def __init__(self):
        """Initialize institutional analyzer."""
        pass

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

    def extract_holdings(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and process holdings data from validated_data structure."""
        inner = data.get('validated_data', data)
        holders_raw = inner.get('holders', data.get('holders', {}))
        processed_holders = []

        # Handle nested structure: {major_holders: [...], institutional_holders: [...]}
        if isinstance(holders_raw, dict):
            # Process major_holders
            for holder in holders_raw.get('major_holders', []):
                if isinstance(holder, dict):
                    processed_holders.append({
                        'name': holder.get('holder', holder.get('name', 'Unknown')),
                        'shares': holder.get('shares', 0),
                        'value': holder.get('value'),
                        'percentage': self._parse_percentage(holder.get('percentage', 0)),
                        'type': 'other',
                        'change': holder.get('change', 'no change')
                    })
            # Process institutional_holders
            for holder in holders_raw.get('institutional_holders', []):
                if isinstance(holder, dict):
                    processed_holders.append({
                        'name': holder.get('holder', holder.get('name', 'Unknown')),
                        'shares': holder.get('shares', 0),
                        'value': holder.get('value'),
                        'percentage': self._parse_percentage(holder.get('percentage', 0)),
                        'type': 'institution',
                        'change': holder.get('change', 'no change')
                    })
        elif isinstance(holders_raw, list):
            for holder in holders_raw:
                if isinstance(holder, dict):
                    processed_holders.append({
                        'name': holder.get('name', 'Unknown'),
                        'shares': holder.get('shares', 0),
                        'value': holder.get('value'),
                        'percentage': holder.get('percentage', 0),
                        'type': holder.get('type', 'other'),
                        'change': holder.get('change', 'no change')
                    })

        return processed_holders

    @staticmethod
    def _parse_percentage(value) -> float:
        """Parse percentage value from various formats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace('%', '').strip())
            except ValueError:
                return 0.0
        return 0.0

    def extract_recommendations(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and process analyst recommendations from validated_data structure."""
        inner = data.get('validated_data', data)
        analyst_data = inner.get('analyst_data', data.get('analyst_data', {}))
        processed_recs = []

        # Handle yfinance summary format: {recent_recommendation: {strong_buy: N, buy: N, ...}}
        recent_rec = analyst_data.get('recent_recommendation', {})
        if recent_rec and isinstance(recent_rec, dict):
            today = datetime.now().strftime('%Y-%m-%d')
            # Expand summary counts into individual recommendation entries
            for _ in range(recent_rec.get('strong_buy', 0)):
                processed_recs.append({'date': today, 'analyst_name': 'Consensus', 'rating': 'Strong Buy', 'price_target': analyst_data.get('target_mean_price'), 'change': 'reaffirm'})
            for _ in range(recent_rec.get('buy', 0)):
                processed_recs.append({'date': today, 'analyst_name': 'Consensus', 'rating': 'Buy', 'price_target': analyst_data.get('target_mean_price'), 'change': 'reaffirm'})
            for _ in range(recent_rec.get('hold', 0)):
                processed_recs.append({'date': today, 'analyst_name': 'Consensus', 'rating': 'Hold', 'price_target': None, 'change': 'reaffirm'})
            for _ in range(recent_rec.get('sell', 0)):
                processed_recs.append({'date': today, 'analyst_name': 'Consensus', 'rating': 'Sell', 'price_target': None, 'change': 'reaffirm'})
            for _ in range(recent_rec.get('strong_sell', 0)):
                processed_recs.append({'date': today, 'analyst_name': 'Consensus', 'rating': 'Strong Sell', 'price_target': None, 'change': 'reaffirm'})

        # Also handle list format for backwards compatibility
        recommendations = data.get('recommendations', [])
        for rec in recommendations:
            if isinstance(rec, dict):
                processed_recs.append({
                    'date': rec.get('date', ''),
                    'analyst_name': rec.get('analyst_name', 'Unknown'),
                    'rating': rec.get('rating', 'Hold'),
                    'price_target': rec.get('price_target'),
                    'change': rec.get('change', 'reaffirm')
                })

        return processed_recs

    def analyze_ownership_structure(self, holders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze ownership structure."""
        institutional_pct = 0
        insider_pct = 0
        board_pct = 0
        retail_pct = 0

        institutional_holders = []
        insider_holders = []

        for holder in holders:
            pct = holder.get('percentage', 0)
            holder_type = holder.get('type', '').lower()

            if holder_type == 'institution':
                institutional_pct += pct
                institutional_holders.append(holder)
            elif holder_type == 'insider':
                insider_pct += pct
                insider_holders.append(holder)
            elif holder_type == 'board':
                board_pct += pct
            elif holder_type == 'other':
                pass

        # Remaining is retail
        retail_pct = max(0, 100 - institutional_pct - insider_pct - board_pct)

        # Get major institutions (top 5)
        major_insts = sorted(institutional_holders, key=lambda x: x.get('percentage', 0), reverse=True)[:5]

        major_institutions_list = []
        for rank, inst in enumerate(major_insts, 1):
            inst_name = inst.get('name', '')
            inst_type = self._classify_institution(inst_name)

            activity = self._assess_activity(inst.get('change', 'no change'))

            major_institutions_list.append({
                'rank': rank,
                'name': inst_name,
                'shares': inst.get('shares', 0),
                'percentage': round(inst.get('percentage', 0), 2),
                'value': inst.get('value'),
                'type': inst_type,
                'recent_activity': activity,
                'holding_trend': activity
            })

        # Insider analysis
        key_insiders = sorted(insider_holders, key=lambda x: x.get('percentage', 0), reverse=True)[:5]

        key_insiders_list = []
        for insider in key_insiders:
            key_insiders_list.append({
                'name': insider.get('name', ''),
                'title': 'Not specified',  # Would come from dedicated insider title field
                'shares': insider.get('shares', 0),
                'percentage': round(insider.get('percentage', 0), 2)
            })

        return {
            'ownership_structure': {
                'institutional_percentage': round(institutional_pct, 1),
                'insider_percentage': round(insider_pct, 1),
                'board_percentage': round(board_pct, 1),
                'retail_percentage': round(retail_pct, 1)
            },
            'major_institutions': major_institutions_list,
            'insider_holdings': {
                'total_insider_percentage': round(insider_pct, 1),
                'key_insiders': key_insiders_list,
                'recent_insider_transactions': self._extract_insider_signals(insider_holders),
                'insider_conviction_signal': self._assess_insider_conviction(insider_holders)
            }
        }

    def _classify_institution(self, inst_name: str) -> str:
        """Classify institution type."""
        name_lower = inst_name.lower()

        if any(term in name_lower for term in ['fund', 'capital', 'advisors', 'partners', 'management']):
            if any(term in name_lower for term in ['citadel', 'elliott', 'renaissance', 'millennium', 'point72']):
                return 'hedge fund'
            else:
                return 'asset manager'
        elif any(term in name_lower for term in ['pension', 'retirement', 'calpers', 'apg']):
            return 'pension fund'
        elif any(term in name_lower for term in ['insurance', 'mutual', 'massmutual']):
            return 'insurance'
        elif 'berkshire' in name_lower:
            return 'conglomerate'
        else:
            return 'other'

    def _assess_activity(self, change: str) -> str:
        """Assess shareholder activity."""
        change_lower = change.lower() if change else ''

        if '+' in change_lower or 'buy' in change_lower or 'accumul' in change_lower:
            return 'accumulating'
        elif '-' in change_lower or 'sell' in change_lower or 'reduc' in change_lower:
            return 'reducing'
        else:
            return 'stable'

    def _extract_insider_signals(self, insiders: List[Dict[str, Any]]) -> List[str]:
        """Extract insider transaction signals."""
        signals = []

        for insider in insiders:
            change = insider.get('change', '').lower()
            name = insider.get('name', '')

            if '+' in str(change) or 'buy' in change:
                signals.append(f"{name} accumulating shares")
            elif '-' in str(change) or 'sell' in change:
                signals.append(f"{name} reducing position")

        return signals

    def _assess_insider_conviction(self, insiders: List[Dict[str, Any]]) -> str:
        """Assess insider conviction signal."""
        buying_count = sum(1 for i in insiders if '+' in str(i.get('change', '')))
        selling_count = sum(1 for i in insiders if '-' in str(i.get('change', '')))

        if buying_count > selling_count:
            return 'accumulating'
        elif selling_count > buying_count:
            return 'distributing'
        else:
            return 'neutral'

    def analyze_institutional_trends(self, holders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze institutional trends and flows."""
        institutional_holders = [h for h in holders if h.get('type', '').lower() == 'institution']

        # Assess flow direction
        buying = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['+', 'buy', 'accumulating'])
        selling = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['-', 'sell', 'reducing'])
        neutral = len(institutional_holders) - buying - selling

        if buying > selling:
            flow_direction = 'net buying'
        elif selling > buying:
            flow_direction = 'net selling'
        else:
            flow_direction = 'stable'

        # Assess concentration
        total_institutional = sum(h.get('percentage', 0) for h in institutional_holders)
        top5_pct = sum(h.get('percentage', 0) for h in sorted(institutional_holders, key=lambda x: x.get('percentage', 0), reverse=True)[:5])

        if top5_pct > 50:
            concentration = 'highly concentrated'
            concentration_risk = 'high'
        elif top5_pct > 35:
            concentration = 'moderately concentrated'
            concentration_risk = 'moderate'
        else:
            concentration = 'dispersed'
            concentration_risk = 'low'

        # Passive vs active split
        passive_count = sum(1 for h in institutional_holders if self._classify_institution(h.get('name', '')) == 'passive')
        passive_pct = (passive_count / len(institutional_holders) * 100) if institutional_holders else 0

        # Major accumulations/liquidations
        major_accums = [h.get('name', '') for h in institutional_holders if h.get('change', '').lower() in ['+', 'buy'] and h.get('percentage', 0) > 1]
        major_liquids = [h.get('name', '') for h in institutional_holders if h.get('change', '').lower() in ['-', 'sell'] and h.get('percentage', 0) > 1]

        return {
            'flow_direction': flow_direction,
            'major_accumulations': major_accums,
            'major_liquidations': major_liquids,
            'turnover_rate': 'moderate',  # Would need more data to determine
            'concentration_level': concentration,
            'concentration_risk': concentration_risk,
            'passive_vs_active': f"{passive_pct:.0f}% passive / {100-passive_pct:.0f}% active"
        }

    def analyze_analyst_consensus(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze analyst ratings and consensus."""
        if not recommendations:
            return self._create_empty_consensus()

        # Get most recent ratings (last 60 days)
        today = datetime.now()
        recent_recs = []

        for rec in recommendations:
            try:
                rec_date = datetime.strptime(rec.get('date', ''), '%Y-%m-%d')
                days_ago = (today - rec_date).days
                if days_ago <= 60:
                    recent_recs.append(rec)
            except ValueError:
                recent_recs.append(rec)  # Include if date parsing fails

        if not recent_recs:
            recent_recs = recommendations  # Use all if none in last 60 days

        # Standardize ratings
        rating_counts = defaultdict(int)
        price_targets = []

        for rec in recent_recs:
            rating = rec.get('rating', 'Hold')
            standardized = self._standardize_rating(rating)
            rating_counts[standardized] += 1

            if rec.get('price_target'):
                try:
                    price_targets.append(float(rec.get('price_target')))
                except (ValueError, TypeError):
                    pass

        total_ratings = sum(rating_counts.values())
        buy_count = rating_counts.get('Buy', 0)
        hold_count = rating_counts.get('Hold', 0)
        sell_count = rating_counts.get('Sell', 0)
        other_count = rating_counts.get('Other', 0)

        # Consensus rating
        if buy_count > hold_count and buy_count > sell_count:
            consensus = 'Buy'
            conviction = 'strong consensus' if buy_count / total_ratings > 0.6 else 'moderate consensus'
        elif sell_count > hold_count and sell_count > buy_count:
            consensus = 'Sell'
            conviction = 'strong consensus' if sell_count / total_ratings > 0.6 else 'moderate consensus'
        else:
            consensus = 'Hold'
            conviction = 'no consensus' if abs(buy_count - sell_count) < 2 else 'moderate consensus'

        # Price targets
        avg_target = sum(price_targets) / len(price_targets) if price_targets else None
        high_target = max(price_targets) if price_targets else None
        low_target = min(price_targets) if price_targets else None

        upside_downside = None  # Would need current price from data

        # Buy/Hold/Sell split
        split_str = f"{buy_count}% Buy, {hold_count}% Hold, {sell_count}% Sell"
        if total_ratings > 0:
            split_str = f"{buy_count/total_ratings*100:.0f}% Buy, {hold_count/total_ratings*100:.0f}% Hold, {sell_count/total_ratings*100:.0f}% Sell"

        return {
            'recommendation_summary': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'total_ratings': total_ratings,
                'buy_count': buy_count,
                'hold_count': hold_count,
                'sell_count': sell_count,
                'other_count': other_count
            },
            'consensus_rating': {
                'rating': consensus,
                'conviction_level': conviction,
                'buy_hold_sell_split': split_str
            },
            'price_targets': {
                'current_price': None,
                'average_price_target': round(avg_target, 2) if avg_target else None,
                'high_price_target': round(high_target, 2) if high_target else None,
                'low_price_target': round(low_target, 2) if low_target else None,
                'upside_downside': upside_downside,
                'price_target_range': self._format_price_range(low_target, high_target)
            },
            'analysts_coverage': {
                'count': len(set(r.get('analyst_name', '') for r in recent_recs)),
                'major_houses': self._extract_major_houses(recent_recs),
                'coverage_trend': 'stable'  # Would need historical data
            }
        }

    def _standardize_rating(self, rating: str) -> str:
        """Standardize analyst rating to Buy/Hold/Sell."""
        rating_lower = rating.lower() if rating else ''

        if any(term in rating_lower for term in ['buy', 'strong buy', 'outperform', 'positive']):
            return 'Buy'
        elif any(term in rating_lower for term in ['sell', 'strong sell', 'underperform', 'negative', 'reduce']):
            return 'Sell'
        else:
            return 'Hold'

    def _format_price_range(self, low: Optional[float], high: Optional[float]) -> str:
        """Format price target range."""
        if low and high:
            return f"Targets range ${low:.2f}-${high:.2f}"
        elif low:
            return f"Target: ${low:.2f}"
        elif high:
            return f"Target: ${high:.2f}"
        else:
            return "Price targets not available"

    def _extract_major_houses(self, recommendations: List[Dict[str, Any]]) -> List[str]:
        """Extract major analyst firms."""
        analysts = [r.get('analyst_name', '') for r in recommendations]
        # Count occurrences
        analyst_counts = defaultdict(int)
        for analyst in analysts:
            analyst_counts[analyst] += 1

        # Return top 3
        return [a for a, _ in sorted(analyst_counts.items(), key=lambda x: x[1], reverse=True)[:3]]

    def analyze_recommendation_trends(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends in analyst recommendations."""
        if not recommendations:
            return self._create_empty_trends()

        # Sort by date
        try:
            sorted_recs = sorted(recommendations, key=lambda x: x.get('date', ''))
        except:
            sorted_recs = recommendations

        # Recent changes
        recent_changes = []
        for rec in sorted_recs[-10:]:  # Last 10 recommendations
            if rec.get('change', '').lower() in ['upgrade', 'downgrade', 'new']:
                recent_changes.append({
                    'date': rec.get('date', ''),
                    'analyst': rec.get('analyst_name', ''),
                    'previous_rating': None,  # Would need historical data
                    'new_rating': rec.get('rating', ''),
                    'action': rec.get('change', 'reaffirm'),
                    'rationale': 'Not provided'
                })

        # Trend analysis
        upgrades = sum(1 for r in recommendations if r.get('change', '').lower() == 'upgrade')
        downgrades = sum(1 for r in recommendations if r.get('change', '').lower() == 'downgrade')

        if upgrades > downgrades:
            trend_direction = 'ratings improving'
            momentum = 'improvement' if upgrades > 2 else 'stable'
        elif downgrades > upgrades:
            trend_direction = 'ratings deteriorating'
            momentum = 'deterioration' if downgrades > 2 else 'stable'
        else:
            trend_direction = 'ratings stable'
            momentum = 'stable'

        upgrade_downgrade_ratio = upgrades / downgrades if downgrades > 0 else None

        return {
            'recent_changes': recent_changes,
            'trend_direction': trend_direction,
            'momentum': momentum,
            'days_analyzed': 365,  # Assume 1 year lookback
            'upgrade_downgrade_ratio': round(upgrade_downgrade_ratio, 2) if upgrade_downgrade_ratio else None
        }

    def analyze_alignment(self, holdings: List[Dict[str, Any]],
                         recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze alignment between institutional actions and analyst ratings."""
        # Institutional sentiment
        institutional_holders = [h for h in holdings if h.get('type', '').lower() == 'institution']
        buying = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['+', 'buy'])
        selling = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['-', 'sell'])

        if buying > selling:
            inst_sentiment = 1  # Bullish
        elif selling > buying:
            inst_sentiment = -1  # Bearish
        else:
            inst_sentiment = 0  # Neutral

        # Analyst sentiment
        analyst_consensus = self.analyze_analyst_consensus(recommendations)
        consensus_rating = analyst_consensus.get('consensus_rating', {}).get('rating', 'Hold')

        if consensus_rating == 'Buy':
            analyst_sentiment = 1
        elif consensus_rating == 'Sell':
            analyst_sentiment = -1
        else:
            analyst_sentiment = 0

        # Alignment
        if (inst_sentiment == 1 and analyst_sentiment == 1) or (inst_sentiment == -1 and analyst_sentiment == -1):
            alignment = 'strongly aligned'
            score = 0.8
        elif inst_sentiment == analyst_sentiment:
            alignment = 'aligned'
            score = 0.6
        elif inst_sentiment * analyst_sentiment == 0:
            alignment = 'mixed signals'
            score = 0.5
        else:
            alignment = 'divergent'
            score = 0.2

        # Insider alignment
        insider_holders = [h for h in holdings if h.get('type', '').lower() == 'insider']
        insider_buying = sum(1 for h in insider_holders if h.get('change', '').lower() in ['+', 'buy'])
        insider_selling = sum(1 for h in insider_holders if h.get('change', '').lower() in ['-', 'sell'])

        if insider_buying > insider_selling:
            insider_sent = 'bullish'
        elif insider_selling > insider_buying:
            insider_sent = 'bearish'
        else:
            insider_sent = 'neutral'

        insider_alignment = alignment if (insider_sent == 'bullish' and analyst_sentiment == 1) or \
                           (insider_sent == 'bearish' and analyst_sentiment == -1) else 'divergent'

        # Red flags
        red_flags = []
        if alignment == 'divergent':
            red_flags.append('Institutions and analysts have opposing views')
        if insider_sent != 'neutral' and analyst_sentiment == 0:
            red_flags.append('Insider activity contradicts neutral analyst consensus')

        return {
            'institutional_vs_analyst_alignment': {
                'alignment_score': round(score, 2),
                'assessment': alignment,
                'interpretation': f"Institutions {'buying' if inst_sentiment > 0 else 'selling' if inst_sentiment < 0 else 'neutral'} while analysts {'bullish' if analyst_sentiment > 0 else 'bearish' if analyst_sentiment < 0 else 'neutral'}"
            },
            'insider_vs_analyst_alignment': {
                'alignment_score': round(score * 0.9, 2) if insider_sent != 'neutral' else 0.5,
                'assessment': insider_alignment,
                'interpretation': f"Insiders {insider_sent} vs analysts {('bullish' if analyst_sentiment > 0 else 'bearish' if analyst_sentiment < 0 else 'neutral')}"
            },
            'narrative_consistency': self._assess_narrative(inst_sentiment, analyst_sentiment, insider_sent),
            'red_flags': red_flags
        }

    def _assess_narrative(self, inst_sent: int, analyst_sent: int, insider_sent: str) -> str:
        """Assess narrative consistency."""
        all_bullish = inst_sent > 0 and analyst_sent > 0 and insider_sent == 'bullish'
        all_bearish = inst_sent < 0 and analyst_sent < 0 and insider_sent == 'bearish'

        if all_bullish:
            return 'consistent bullish'
        elif all_bearish:
            return 'consistent bearish'
        else:
            return 'mixed'

    def assess_flow_signals(self, holdings: List[Dict[str, Any]],
                           recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess smart money flow signals."""
        institutional_holders = [h for h in holdings if h.get('type', '').lower() == 'institution']
        buying = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['+', 'buy'])
        selling = sum(1 for h in institutional_holders if h.get('change', '').lower() in ['-', 'sell'])

        if buying > selling:
            accum = 'strong accumulation'
            signal = 'bullish'
        elif selling > buying:
            accum = 'strong distribution'
            signal = 'bearish'
        else:
            accum = 'neutral'
            signal = 'neutral'

        # Liquidity
        unique_institutions = len(set(h.get('name', '') for h in institutional_holders))
        if unique_institutions > 50:
            liquidity = 'high'
        elif unique_institutions > 20:
            liquidity = 'moderate'
        else:
            liquidity = 'low'

        return {
            'accumulation_distribution': accum,
            'smart_money_signal': signal,
            'liquidity_profile': liquidity,
            'potential_catalysts_from_flows': self._identify_catalysts(holdings)
        }

    def _identify_catalysts(self, holdings: List[Dict[str, Any]]) -> List[str]:
        """Identify potential catalysts from holdings changes."""
        catalysts = []

        for holder in holdings:
            if holder.get('change', '').lower() in ['+', 'buy'] and holder.get('percentage', 0) > 1:
                catalysts.append(f"Major institution {holder.get('name', '')} accumulating")
            elif holder.get('change', '').lower() in ['-', 'sell'] and holder.get('percentage', 0) > 1:
                catalysts.append(f"Potential shareholder changes with {holder.get('name', '')} reducing")

        return catalysts[:5]

    def validate_data_quality(self, holders: List[Dict[str, Any]],
                            recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate data quality."""
        warnings = []

        if len(holders) == 0:
            warnings.append('No holdings data available')

        if len(recommendations) == 0:
            warnings.append('No analyst recommendations available')

        # Check percentage sum
        total_pct = sum(h.get('percentage', 0) for h in holders)
        if total_pct > 0 and (total_pct < 95 or total_pct > 105):
            warnings.append(f'Holdings percentages sum to {total_pct:.1f}% (expected ~100%)')

        return {
            'holders_data_available': len(holders) > 0,
            'holders_count': len(holders),
            'holdings_date': 'Most recent available',
            'recommendations_data_available': len(recommendations) > 0,
            'ratings_count': len(recommendations),
            'ratings_freshness': self._assess_freshness(recommendations),
            'percentage_data_verified': 95 <= total_pct <= 105 if holders else True,
            'warnings': warnings
        }

    def _assess_freshness(self, recommendations: List[Dict[str, Any]]) -> int:
        """Assess freshness of recommendations in days."""
        if not recommendations:
            return 999

        today = datetime.now()
        freshness = 999

        for rec in recommendations:
            try:
                rec_date = datetime.strptime(rec.get('date', ''), '%Y-%m-%d')
                days = (today - rec_date).days
                freshness = min(freshness, days)
            except ValueError:
                pass

        return freshness

    def calculate_confidence(self, holders: List[Dict[str, Any]],
                           recommendations: List[Dict[str, Any]],
                           data_quality: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence scores."""
        data_avail = min(1.0, (len(holders) / 20 * 0.5 + len(recommendations) / 15 * 0.5))
        freshness = 1.0 if data_quality.get('ratings_freshness', 999) < 60 else 0.5
        coverage = min(1.0, len(set(r.get('analyst_name', '') for r in recommendations)) / 20)

        # Signal clarity
        if len(recommendations) >= 5:
            signal_clarity = 0.8
        elif len(recommendations) >= 3:
            signal_clarity = 0.6
        else:
            signal_clarity = 0.3

        overall = data_avail * 0.4 + freshness * 0.3 + coverage * 0.15 + signal_clarity * 0.15

        if overall >= 0.75:
            recommendation = 'high conviction'
        elif overall >= 0.55:
            recommendation = 'strong signal'
        elif overall >= 0.35:
            recommendation = 'reliable baseline'
        else:
            recommendation = 'weak signal'

        return {
            'overall': round(min(1.0, max(0.0, overall)), 2),
            'factors': {
                'data_completeness': round(data_avail, 2),
                'data_recency': round(freshness, 2),
                'coverage_depth': round(coverage, 2),
                'signal_clarity': round(signal_clarity, 2)
            },
            'recommendation': recommendation,
            'caveats': [
                'Holdings data is point-in-time; does not capture full trading activity',
                'Analyst ratings can be influenced by conflicts of interest',
                'Institutional ownership does not guarantee near-term price support',
                'Insider buying/selling can be driven by non-fundamental reasons'
            ]
        }

    def _create_empty_consensus(self) -> Dict[str, Any]:
        """Create empty consensus template."""
        return {
            'recommendation_summary': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'total_ratings': 0,
                'buy_count': 0,
                'hold_count': 0,
                'sell_count': 0
            },
            'consensus_rating': {
                'rating': 'No consensus',
                'conviction_level': 'No data',
                'buy_hold_sell_split': 'No ratings'
            },
            'price_targets': {
                'average_price_target': None,
                'high_price_target': None,
                'low_price_target': None
            }
        }

    def _create_empty_trends(self) -> Dict[str, Any]:
        """Create empty trends template."""
        return {
            'recent_changes': [],
            'trend_direction': 'No data',
            'momentum': 'No data',
            'days_analyzed': 0,
            'upgrade_downgrade_ratio': None
        }

    def analyze(self, input_path: str, output_path: str):
        """Main analysis workflow."""
        try:
            # Load data
            data = self.load_data(input_path)
            inner = data.get('validated_data', data)
            ticker = inner.get('metadata', {}).get('ticker', data.get('ticker', 'UNKNOWN'))

            # Extract holdings and recommendations
            holders = self.extract_holdings(data)
            recommendations = self.extract_recommendations(data)

            # Perform analyses
            inst_summary = self.analyze_ownership_structure(holders)
            inst_trends = self.analyze_institutional_trends(holders)
            analyst_consensus = self.analyze_analyst_consensus(recommendations)
            rec_trends = self.analyze_recommendation_trends(recommendations)
            alignment = self.analyze_alignment(holders, recommendations)
            flow_signals = self.assess_flow_signals(holders, recommendations)
            data_quality = self.validate_data_quality(holders, recommendations)
            confidence = self.calculate_confidence(holders, recommendations, data_quality)

            # Build output
            output = {
                'ticker': ticker,
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'institutional_summary': {
                    **inst_summary['ownership_structure'],
                    'major_institutions': inst_summary['major_institutions'],
                    'insider_holdings': inst_summary['insider_holdings']
                },
                'institutional_trends': inst_trends,
                'analyst_consensus': analyst_consensus,
                'recommendation_trends': rec_trends,
                'alignment_analysis': alignment,
                'flow_signals': flow_signals,
                'anti_hallucination_checks': data_quality,
                'confidence': confidence
            }

            # Save output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            print(f"Institutional analysis complete. Results saved to {output_path}")
            return output

        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Stock Institutional Flow & Analyst Consensus Analysis Tool'
    )
    parser.add_argument('--input', required=True, help='Input JSON file with validated stock data')
    parser.add_argument('--output', required=True, help='Output JSON file for analysis results')

    args = parser.parse_args()

    analyzer = InstitutionalAnalyzer()
    analyzer.analyze(args.input, args.output)


if __name__ == '__main__':
    main()
