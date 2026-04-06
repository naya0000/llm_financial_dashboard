#!/usr/bin/env python3
"""
DEPRECATED — This script is no longer used in the pipeline.

Integration is handled by the Orchestrator (stock-orchestrator/SKILL.md Step 5)
using LLM reasoning, which produces richer narrative synthesis than weighted averaging.

This file is kept for reference only. Do NOT call it from the pipeline.
If you need programmatic integration, refactor the Orchestrator's Step 5 logic instead.

Original description:
Stock Analysis Integrator — Combines outputs from all 6 analyst agents
with weighted scoring and consensus detection.
"""

import json
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class AnalysisIntegrator:
    """Integrates multiple analyst outputs with weighted scoring."""

    # Weights for each analyst (must sum to 100)
    ANALYST_WEIGHTS = {
        'financial': 0.25,      # 25%
        'technical': 0.15,      # 15%
        'quant': 0.15,          # 15%
        'industry': 0.20,       # 20%
        'sentiment': 0.10,      # 10%
        'institutional': 0.15   # 15%
    }

    # Rating thresholds
    RATING_THRESHOLDS = {
        'strong_buy': 80,
        'buy': 65,
        'hold': 45,
        'sell': 30,
        'strong_sell': 0  # Below 30
    }

    def __init__(self):
        """Initialize the integrator."""
        self.analyses = {}
        self.ticker = 'UNKNOWN'
        self.integration_timestamp = datetime.now().isoformat()

    def load_analyses(self, financial: str, technical: str, quant: str,
                     industry: str, sentiment: str, institutional: str) -> bool:
        """
        Load all analysis JSON files.

        Args:
            financial: Path to financial analysis JSON
            technical: Path to technical analysis JSON
            quant: Path to quantitative analysis JSON
            industry: Path to industry analysis JSON
            sentiment: Path to sentiment analysis JSON
            institutional: Path to institutional analysis JSON

        Returns:
            True if all files loaded successfully
        """
        files = {
            'financial': financial,
            'technical': technical,
            'quant': quant,
            'industry': industry,
            'sentiment': sentiment,
            'institutional': institutional
        }

        for analyst_type, filepath in files.items():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.analyses[analyst_type] = data
                    if analyst_type == 'financial' and 'ticker' in data:
                        self.ticker = data['ticker']
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error loading {analyst_type} analysis from {filepath}: {e}",
                      file=sys.stderr)
                return False

        return True

    def integrate(self) -> Dict[str, Any]:
        """
        Integrate all analyses and generate final report.

        Returns:
            Integrated analysis report
        """
        if not self.analyses:
            raise ValueError("No analyses loaded")

        # Extract scores from each analyst
        weighted_scores = self._extract_weighted_scores()

        # Calculate overall score
        overall_score = sum(
            weighted_scores[analyst_type]['weighted_score']
            for analyst_type in self.ANALYST_WEIGHTS.keys()
        )

        # Determine rating
        rating = self._determine_rating(overall_score)

        # Detect consensus and divergence
        consensus_points = self._detect_consensus()
        divergence_points = self._detect_divergence()

        # Generate recommendation
        recommendation = self._generate_recommendation(
            overall_score, rating, consensus_points, divergence_points
        )

        # Build integrated report
        report = {
            'metadata': {
                'ticker': self.ticker,
                'integration_timestamp': self.integration_timestamp,
                'integration_agent': 'stock-integrator'
            },
            'overall_score': round(overall_score, 2),
            'rating': rating,
            'weighted_scores': weighted_scores,
            'consensus_points': consensus_points,
            'divergence_points': divergence_points,
            'recommendation': recommendation,
            'risk_disclosure': self._generate_risk_disclosure(),
            'analyst_summaries': self._extract_analyst_summaries(),
            'integration_rationale': self._generate_integration_rationale(
                weighted_scores, consensus_points, divergence_points
            )
        }

        return report

    def _extract_weighted_scores(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract scores from each analyst and apply weights.

        Returns:
            Dictionary of weighted scores by analyst type
        """
        weighted_scores = {}

        for analyst_type, weight in self.ANALYST_WEIGHTS.items():
            analysis = self.analyses.get(analyst_type, {})
            score = self._extract_score(analyst_type, analysis)

            # Normalize score to 0-100 range
            score = max(0, min(100, score))
            weighted_score = score * weight

            weighted_scores[analyst_type] = {
                'raw_score': round(score, 2),
                'weight': weight,
                'weighted_score': round(weighted_score, 2)
            }

        return weighted_scores

    def _extract_score(self, analyst_type: str, analysis: Dict[str, Any]) -> float:
        """Extract a meaningful 0-100 score from each analyst's output."""

        if analyst_type == 'financial':
            # Score based on bullish vs bearish points + confidence
            bullish = len(analysis.get('bullish_points', []))
            bearish = len(analysis.get('bearish_points', []))
            total = bullish + bearish
            if total > 0:
                ratio = bullish / total  # 0 to 1
                return ratio * 100
            return analysis.get('confidence_score', 50)

        elif analyst_type == 'technical':
            # Use trend strength + signal direction
            trend = analysis.get('trend_analysis', {})
            trend_strength = trend.get('trend_strength', 50)
            signals = analysis.get('signals', [])
            bullish_signals = sum(1 for s in signals if s.get('signal') == 'bullish')
            bearish_signals = sum(1 for s in signals if s.get('signal') == 'bearish')
            signal_bias = (bullish_signals - bearish_signals) * 10
            current_trend = trend.get('current_trend', '')
            if current_trend == 'bullish':
                return min(100, trend_strength + signal_bias)
            elif current_trend == 'bearish':
                return max(0, (100 - trend_strength) + signal_bias)
            else:
                return 50 + signal_bias

        elif analyst_type == 'quant':
            # Score from annualized return & risk metrics
            metrics = analysis.get('metrics', {})
            ann_ret = metrics.get('annualized_return', {}).get('value')
            max_dd = metrics.get('maximum_drawdown', {}).get('value')
            score = 50
            if ann_ret is not None:
                # Map return: -20%->20, 0%->40, 20%->60, 50%->75, 100%->90
                score = min(95, max(10, 40 + ann_ret * 0.5))
            if max_dd is not None and max_dd > 30:
                score -= 15  # Penalty for large drawdown
            return max(0, min(100, score))

        elif analyst_type == 'industry':
            # Score from cycle stage + valuation position
            cycle = analysis.get('industry_cycle_analysis', {})
            stage = cycle.get('current_stage', 'mid cycle')
            pe_vs = analysis.get('industry_position', {}).get('relative_valuation', {}).get('pe_vs_sector', {})
            score = 50
            if stage == 'early cycle':
                score = 70
            elif stage == 'mid cycle':
                score = 55
            elif stage == 'late cycle':
                score = 35
            # Adjust for valuation
            if pe_vs and pe_vs.get('premium_discount') is not None:
                premium = pe_vs['premium_discount']
                score -= premium * 0.3  # Penalize high premium
            return max(0, min(100, score))

        elif analyst_type == 'sentiment':
            # Map sentiment index (-100 to +100) to score (0-100)
            sa = analysis.get('sentiment_analysis', {})
            si = sa.get('weighted_sentiment', sa.get('sentiment_index', {}))
            if isinstance(si, dict):
                idx = si.get('score', 0) or 0
            else:
                idx = si or 0
            return max(0, min(100, 50 + idx / 2))

        elif analyst_type == 'institutional':
            # Score from analyst consensus
            ac = analysis.get('analyst_consensus', {})
            cr = ac.get('consensus_rating', {})
            rating = cr.get('rating', 'Hold')
            rs = ac.get('recommendation_summary', {})
            total = rs.get('total_ratings', 0)
            buy = rs.get('buy_count', 0)
            if rating == 'Buy' or rating == 'Strong Buy':
                score = 70
                if total > 0:
                    buy_pct = buy / total
                    score = 50 + buy_pct * 40
            elif rating == 'Sell' or rating == 'Strong Sell':
                score = 25
            else:
                score = 50
            return max(0, min(100, score))

        # Fallback
        return analysis.get('confidence_score', analysis.get('overall_score', 50))

    def _determine_rating(self, overall_score: float) -> str:
        """
        Determine investment rating based on overall score.

        Args:
            overall_score: Overall composite score (0-100)

        Returns:
            Rating string
        """
        if overall_score >= self.RATING_THRESHOLDS['strong_buy']:
            return 'Strong Buy'
        elif overall_score >= self.RATING_THRESHOLDS['buy']:
            return 'Buy'
        elif overall_score >= self.RATING_THRESHOLDS['hold']:
            return 'Hold'
        elif overall_score >= self.RATING_THRESHOLDS['sell']:
            return 'Sell'
        else:
            return 'Strong Sell'

    def _detect_consensus(self) -> List[Dict[str, Any]]:
        """
        Detect areas where multiple analysts agree.

        Returns:
            List of consensus points
        """
        consensus_points = []

        # Check for bullish consensus
        bullish_analysts = 0
        bullish_details = []
        for analyst_type in self.ANALYST_WEIGHTS.keys():
            analysis = self.analyses.get(analyst_type, {})
            score = None

            if 'confidence_score' in analysis:
                score = analysis['confidence_score']
            elif 'signal_strength' in analysis:
                score = analysis['signal_strength']
            elif 'sentiment_score' in analysis:
                score = analysis['sentiment_score']
            elif 'overall_score' in analysis:
                score = analysis['overall_score']

            if score and score >= 65:
                bullish_analysts += 1
                if 'summary' in analysis:
                    bullish_details.append(f"{analyst_type}: {analysis['summary'][:100]}")

        if bullish_analysts >= 4:
            consensus_points.append({
                'point': f'Strong bullish consensus: {bullish_analysts} of 6 analysts bullish',
                'strength': 'strong',
                'supporting_analysts': bullish_analysts
            })

        # Check for bearish consensus
        bearish_analysts = 0
        bearish_details = []
        for analyst_type in self.ANALYST_WEIGHTS.keys():
            analysis = self.analyses.get(analyst_type, {})
            score = None

            if 'confidence_score' in analysis:
                score = analysis['confidence_score']
            elif 'signal_strength' in analysis:
                score = analysis['signal_strength']
            elif 'sentiment_score' in analysis:
                score = analysis['sentiment_score']
            elif 'overall_score' in analysis:
                score = analysis['overall_score']

            if score and score < 45:
                bearish_analysts += 1
                if 'summary' in analysis:
                    bearish_details.append(f"{analyst_type}: {analysis['summary'][:100]}")

        if bearish_analysts >= 4:
            consensus_points.append({
                'point': f'Strong bearish consensus: {bearish_analysts} of 6 analysts bearish',
                'strength': 'strong',
                'supporting_analysts': bearish_analysts
            })

        # Check for neutral/mixed signals
        if not consensus_points:
            consensus_points.append({
                'point': 'Analysts show mixed signals with no clear consensus',
                'strength': 'mixed',
                'supporting_analysts': 0
            })

        return consensus_points

    def _detect_divergence(self) -> List[Dict[str, Any]]:
        """
        Detect areas where analysts disagree.

        Returns:
            List of divergence points
        """
        divergence_points = []

        # Collect analyst views
        analyst_views = {}
        for analyst_type in self.ANALYST_WEIGHTS.keys():
            analysis = self.analyses.get(analyst_type, {})

            # Extract key opinions
            bullish_points = analysis.get('bullish_points', [])
            bearish_points = analysis.get('bearish_points', [])

            analyst_views[analyst_type] = {
                'bullish_count': len(bullish_points),
                'bearish_count': len(bearish_points),
                'net_sentiment': len(bullish_points) - len(bearish_points)
            }

        # Find divergences - analysts with opposite views
        scores = [v['net_sentiment'] for v in analyst_views.values()]
        if scores:
            max_sentiment = max(scores)
            min_sentiment = min(scores)

            if max_sentiment > 3 and min_sentiment < -3:
                bullish_analysts = [k for k, v in analyst_views.items()
                                   if v['net_sentiment'] > 2]
                bearish_analysts = [k for k, v in analyst_views.items()
                                   if v['net_sentiment'] < -2]

                if bullish_analysts and bearish_analysts:
                    divergence_points.append({
                        'point': 'Significant disagreement between analyst groups',
                        'bullish_analysts': bullish_analysts,
                        'bearish_analysts': bearish_analysts,
                        'severity': 'high'
                    })

        # Check for key opinion divergences
        financial_analysis = self.analyses.get('financial', {})
        technical_analysis = self.analyses.get('technical', {})

        if financial_analysis and technical_analysis:
            financial_valuation = financial_analysis.get('valuation_analysis', {}).get('valuation_status', '')
            technical_trend = technical_analysis.get('overall_trend', '')

            if financial_valuation == 'undervalued' and technical_trend == 'downtrend':
                divergence_points.append({
                    'point': 'Fundamental-technical divergence: Stock fundamentally undervalued but technically weak',
                    'analysis_pair': ['financial', 'technical'],
                    'severity': 'medium',
                    'trading_implication': 'Potential reversal signal - monitor technical support levels'
                })
            elif financial_valuation == 'overvalued' and technical_trend == 'uptrend':
                divergence_points.append({
                    'point': 'Fundamental-technical divergence: Stock technically strong but fundamentally expensive',
                    'analysis_pair': ['financial', 'technical'],
                    'severity': 'medium',
                    'trading_implication': 'Momentum may continue but watch for trend reversal'
                })

        return divergence_points

    def _extract_analyst_summaries(self) -> Dict[str, Dict[str, Any]]:
        """Extract key summaries from each analyst, generating descriptions when missing."""
        summaries = {}

        for analyst_type, analysis in self.analyses.items():
            summary_text = analysis.get('summary', '')
            if not summary_text or summary_text == 'No summary available':
                summary_text = self._generate_analyst_summary(analyst_type, analysis)

            score = self._extract_score(analyst_type, analysis)

            summary_data = {
                'analyst': analyst_type,
                'summary': summary_text,
                'confidence_score': score,
                'key_insights': [],
                'data_sources': analysis.get('data_sources_used', [])
            }

            # Extract key bullish points
            bullish = analysis.get('bullish_points', [])
            if bullish:
                summary_data['key_insights'].append({
                    'type': 'bullish',
                    'top_point': bullish[0] if isinstance(bullish, list) else str(bullish)[:100]
                })

            # Extract key bearish points
            bearish = analysis.get('bearish_points', [])
            if bearish:
                summary_data['key_insights'].append({
                    'type': 'bearish',
                    'top_point': bearish[0] if isinstance(bearish, list) else str(bearish)[:100]
                })

            summaries[analyst_type] = summary_data

        return summaries

    def _generate_analyst_summary(self, analyst_type: str, analysis: Dict[str, Any]) -> str:
        """Generate a meaningful summary from analyst data when no explicit summary exists."""
        ticker = self.ticker
        parts = []

        if analyst_type == 'quant':
            m = analysis.get('metrics', {})
            ann_ret = m.get('annualized_return', {}).get('value')
            vol = m.get('annualized_volatility', {}).get('value')
            sharpe = m.get('sharpe_ratio', {}).get('value')
            sharpe_interp = m.get('sharpe_ratio', {}).get('interpretation', '')
            max_dd = m.get('maximum_drawdown', {}).get('value')
            period = m.get('annualized_return', {}).get('period_days', 0)
            parts.append(f"Quantitative Analysis for {ticker} ({period} days)")
            if ann_ret is not None:
                direction = 'positive' if ann_ret > 0 else 'negative'
                parts.append(f"Annualized return: {ann_ret:.1f}% ({direction})")
            if vol is not None:
                parts.append(f"Volatility: {vol:.1f}%")
            if sharpe is not None:
                parts.append(f"Sharpe ratio: {sharpe:.3f} ({sharpe_interp})")
            if max_dd is not None:
                parts.append(f"Max drawdown: {max_dd:.1f}%")
            sc = analysis.get('scenario_analysis', {})
            bull = sc.get('bull_case', {}).get('estimated_return')
            bear = sc.get('bear_case', {}).get('estimated_return')
            if bull is not None and bear is not None:
                parts.append(f"Scenario range: {bear:.1f}% (bear) to {bull:.1f}% (bull)")

        elif analyst_type == 'industry':
            ip = analysis.get('industry_position', {})
            sector = ip.get('sector', 'Unknown')
            industry = ip.get('industry', 'Unknown')
            cap_rank = ip.get('market_cap_ranking', {}).get('interpretation', '')
            cycle = analysis.get('industry_cycle_analysis', {})
            stage = cycle.get('current_stage', 'unknown')
            growth = cycle.get('growth_outlook', 'unknown')
            parts.append(f"Industry Analysis for {ticker}")
            parts.append(f"Sector: {sector} / {industry} ({cap_rank})")
            pe_vs = ip.get('relative_valuation', {}).get('pe_vs_sector', {})
            if pe_vs:
                parts.append(f"PE {pe_vs.get('company_pe', 'N/A')} vs sector avg {pe_vs.get('sector_average_pe', 'N/A')} ({pe_vs.get('interpretation', '')})")
            parts.append(f"Industry cycle: {stage}, growth outlook: {growth}")
            comp = analysis.get('competitive_analysis', {})
            pos = comp.get('market_position', '')
            if pos:
                parts.append(f"Competitive position: {pos}")
            sa = analysis.get('sector_attractiveness', {})
            if sa.get('overall_attractiveness'):
                parts.append(f"Sector attractiveness: {sa['overall_attractiveness']}")

        elif analyst_type == 'sentiment':
            ns = analysis.get('news_summary', {})
            total = ns.get('total_articles_analyzed', 0)
            bd = ns.get('article_breakdown', {})
            sa = analysis.get('sentiment_analysis', {})
            si = sa.get('weighted_sentiment', sa.get('sentiment_index', {}))
            score_val = si.get('score', 0) if isinstance(si, dict) else 0
            interp = si.get('interpretation', 'N/A') if isinstance(si, dict) else 'N/A'
            trend = sa.get('sentiment_trend', {})
            parts.append(f"Sentiment Analysis for {ticker}")
            parts.append(f"Analyzed {total} articles: {bd.get('positive', 0)} positive, {bd.get('neutral', 0)} neutral, {bd.get('negative', 0)} negative")
            parts.append(f"Sentiment index: {score_val} ({interp})")
            if trend.get('direction') and trend['direction'] != 'insufficient data':
                parts.append(f"Trend: {trend['direction']} ({trend.get('momentum', '')})")
            drivers = analysis.get('sentiment_drivers', {})
            narrative = drivers.get('dominant_narrative', '')
            if narrative:
                parts.append(f"Narrative: {narrative}")

        elif analyst_type == 'institutional':
            ist = analysis.get('institutional_summary', {})
            inst_pct = ist.get('institutional_percentage', 'N/A')
            ac = analysis.get('analyst_consensus', {})
            cr = ac.get('consensus_rating', {})
            rating = cr.get('rating', 'N/A')
            conviction = cr.get('conviction_level', '')
            split = cr.get('buy_hold_sell_split', '')
            pt = ac.get('price_targets', {})
            avg_target = pt.get('average_price_target')
            flow = analysis.get('flow_signals', {})
            signal = flow.get('smart_money_signal', '')
            parts.append(f"Institutional & Analyst Analysis for {ticker}")
            parts.append(f"Institutional ownership: {inst_pct}%")
            parts.append(f"Analyst consensus: {rating} ({conviction})")
            if split:
                parts.append(f"Rating split: {split}")
            if avg_target:
                parts.append(f"Average price target: {avg_target}")
            if signal:
                parts.append(f"Smart money signal: {signal}")
            align = analysis.get('alignment_analysis', {})
            narr = align.get('narrative_consistency', '')
            if narr:
                parts.append(f"Narrative consistency: {narr}")

        else:
            parts.append(f"{analyst_type.title()} analysis completed")

        return "\n".join(parts)

    def _generate_recommendation(self, overall_score: float, rating: str,
                               consensus: List[Dict], divergence: List[Dict]) -> str:
        """
        Generate final investment recommendation.

        Args:
            overall_score: Overall composite score
            rating: Investment rating
            consensus: Consensus points
            divergence: Divergence points

        Returns:
            Recommendation text
        """
        recommendation = f"Investment Rating: {rating}\n\n"
        recommendation += f"Overall Composite Score: {overall_score:.1f}/100\n\n"

        # Rating rationale
        if rating == 'Strong Buy':
            recommendation += "Rationale: Multiple analysts show strong agreement on positive fundamentals and technical setup. "
            recommendation += "Stock demonstrates compelling value with strong growth prospects.\n"
        elif rating == 'Buy':
            recommendation += "Rationale: Majority of analysts view the stock positively. "
            recommendation += "Fundamentals appear attractive with reasonable technical support.\n"
        elif rating == 'Hold':
            recommendation += "Rationale: Analyst views are mixed with both bullish and bearish signals. "
            recommendation += "Stock may be fairly valued - suitable for current holders but wait for clearer signals before new positions.\n"
        elif rating == 'Sell':
            recommendation += "Rationale: Multiple concerns identified across fundamental and technical analysis. "
            recommendation += "Consider taking profits or reducing exposure.\n"
        else:  # Strong Sell
            recommendation += "Rationale: Significant concerns identified. "
            recommendation += "Multiple analysts view stock negatively - consider avoiding or exiting positions.\n"

        # Add consensus/divergence impact
        if consensus and len(consensus) > 0:
            rec_consensus = consensus[0]
            if 'bullish' in rec_consensus.get('point', '').lower():
                recommendation += f"\nSupport: {rec_consensus['point']}\n"
            elif 'bearish' in rec_consensus.get('point', '').lower():
                recommendation += f"\nConcern: {rec_consensus['point']}\n"

        if divergence and len(divergence) > 0:
            recommendation += f"\nWarning: {divergence[0].get('point', 'Analysts disagree on key factors')}\n"

        recommendation += "\nNote: This rating is based on quantitative analysis of available data. "
        recommendation += "Consult with a financial advisor before making investment decisions."

        return recommendation

    def _generate_integration_rationale(self, weighted_scores: Dict,
                                      consensus: List[Dict],
                                      divergence: List[Dict]) -> str:
        """
        Generate detailed rationale for integration decisions.

        Args:
            weighted_scores: Weighted scores by analyst
            consensus: Consensus points
            divergence: Divergence points

        Returns:
            Integration rationale text
        """
        rationale = "Integration Methodology:\n"
        rationale += "- Financial Analysis (25%): Evaluates valuation, profitability, and financial health\n"
        rationale += "- Technical Analysis (15%): Assesses price trends and technical support/resistance\n"
        rationale += "- Quantitative Analysis (15%): Analyzes statistical patterns and signals\n"
        rationale += "- Industry/Macro Analysis (20%): Evaluates sector trends and macroeconomic factors\n"
        rationale += "- Sentiment Analysis (10%): Gauges market sentiment from news and social media\n"
        rationale += "- Institutional Flow (15%): Tracks large investor positioning and flows\n\n"

        rationale += "Component Scores:\n"
        for analyst_type, scores in weighted_scores.items():
            rationale += f"- {analyst_type.title()}: {scores['raw_score']}/100 (weight: {scores['weight']*100:.0f}%)\n"

        if consensus:
            rationale += f"\n{len(consensus)} consensus point(s) identified\n"
        if divergence:
            rationale += f"{len(divergence)} divergence point(s) identified\n"

        return rationale

    def _generate_risk_disclosure(self) -> Dict[str, Any]:
        """
        Generate risk disclosure statement.

        Returns:
            Risk disclosure dictionary
        """
        return {
            'general_risks': [
                'Stock market investments carry inherent risk of loss',
                'Past performance does not guarantee future results',
                'Analysis is based on available data which may be incomplete or outdated'
            ],
            'market_risks': [
                'Market volatility can cause significant price fluctuations',
                'Macroeconomic conditions and policy changes affect stock performance',
                'Sector-specific risks may impact investment thesis'
            ],
            'data_risks': [
                'Analysis depends on accuracy of underlying financial data',
                'Technical indicators can produce false signals',
                'Sentiment analysis may not reflect true market consensus'
            ],
            'limitation_statement': (
                'This analysis is generated by a quantitative system and should not be considered '
                'investment advice. Investors should conduct their own research and consult with '
                'qualified financial advisors before making investment decisions. The system has '
                'no awareness of individual investor circumstances, risk tolerance, or financial goals.'
            ),
            'not_financial_advice': 'This report is for informational purposes only and does not constitute financial advice.'
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Integrate outputs from all stock analysis agents'
    )
    parser.add_argument(
        '--financial',
        required=True,
        help='Path to financial analysis JSON'
    )
    parser.add_argument(
        '--technical',
        required=True,
        help='Path to technical analysis JSON'
    )
    parser.add_argument(
        '--quant',
        required=True,
        help='Path to quantitative analysis JSON'
    )
    parser.add_argument(
        '--industry',
        required=True,
        help='Path to industry/macro analysis JSON'
    )
    parser.add_argument(
        '--sentiment',
        required=True,
        help='Path to sentiment analysis JSON'
    )
    parser.add_argument(
        '--institutional',
        required=True,
        help='Path to institutional flow analysis JSON'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output integrated analysis JSON file'
    )

    args = parser.parse_args()

    # Create integrator and load analyses
    integrator = AnalysisIntegrator()

    if not integrator.load_analyses(
        args.financial, args.technical, args.quant,
        args.industry, args.sentiment, args.institutional
    ):
        sys.exit(1)

    # Integrate analyses
    try:
        integrated_report = integrator.integrate()
    except Exception as e:
        print(f"Error during integration: {e}", file=sys.stderr)
        sys.exit(1)

    # Write output
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(integrated_report, f, indent=2, ensure_ascii=False)
        print(f"Integration complete. Output written to {args.output}")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
