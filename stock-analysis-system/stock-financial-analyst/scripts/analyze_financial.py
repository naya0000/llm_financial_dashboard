#!/usr/bin/env python3
"""
Stock Financial Analyst Script
Performs fundamental financial analysis on validated stock data.
"""

import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import sys


class FinancialAnalyzer:
    """Analyzes stock fundamentals and financial health."""

    # Industry averages (for comparison, can be updated)
    INDUSTRY_PE_AVERAGE = 20.0
    INDUSTRY_GROSS_MARGIN = 0.40  # 40%
    MIN_HEALTHY_ROE = 0.15  # 15%
    MIN_HEALTHY_ROA = 0.08  # 8%
    HEALTHY_DEBT_RATIO = 0.50  # 50%
    HEALTHY_CURRENT_RATIO = 1.5
    MIN_INTEREST_COVERAGE = 2.0

    def __init__(self):
        self.bullish_points = []
        self.bearish_points = []
        self.missing_data = []
        self.limitations = []

    def analyze(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform complete financial analysis.

        Args:
            validated_data: Validated data package from validator

        Returns:
            Financial analysis report
        """
        self.bullish_points = []
        self.bearish_points = []
        self.missing_data = []
        self.limitations = []

        inner = validated_data.get('validated_data', {})
        ticker = inner.get('metadata', {}).get('ticker', validated_data.get('ticker', 'UNKNOWN'))
        ci = inner.get('company_info', {})
        # Flatten company_info into a dict the analysis methods expect
        data = {
            'ticker': ticker,
            'price': inner.get('price_history', [{}])[-1].get('close') if inner.get('price_history') else None,
            'pe_ratio': ci.get('pe_ratio'),
            'forward_pe': ci.get('forward_pe'),
            'pb_ratio': ci.get('pb_ratio'),
            'peg_ratio': ci.get('peg_ratio'),
            'eps_current': ci.get('eps'),
            'market_cap': ci.get('market_cap'),
            'dividend_yield': ci.get('dividend_yield') / 100 if ci.get('dividend_yield') else None,  # yfinance returns %, convert to decimal
            'dividend_rate': ci.get('dividend_rate'),
            'gross_margin': None,  # Not directly available from yfinance info
            'operating_margin': ci.get('operating_margin'),
            'net_margin': ci.get('profit_margin'),
            'roe': ci.get('return_on_equity'),
            'roa': ci.get('return_on_assets'),
            'debt_ratio': None,  # Derived below
            'debt_to_equity': ci.get('debt_to_equity'),
            'current_ratio': ci.get('current_ratio'),
            'quick_ratio': ci.get('quick_ratio'),
        }
        # Derive debt_ratio from debt_to_equity: D/E = D/(D+E) approx
        dte = ci.get('debt_to_equity')
        if dte is not None:
            data['debt_ratio'] = dte / (100 + dte)  # debt_to_equity is in % from yfinance
        sources_used = validated_data.get('data_sources_used', ['Yahoo Finance'])

        # Profitability Analysis
        profitability = self._analyze_profitability(data, sources_used)

        # Valuation Analysis
        valuation = self._analyze_valuation(data, sources_used)

        # Financial Structure Analysis
        structure = self._analyze_financial_structure(data, sources_used)

        # Dividend Analysis
        dividends = self._analyze_dividends(data, sources_used)

        # Calculate overall confidence
        confidence = self._calculate_confidence(
            validated_data.get('overall_confidence', 50),
            len(self.missing_data)
        )

        # Build report
        report = {
            'agent': 'stock-financial-analyst',
            'ticker': ticker,
            'analysis_date': datetime.now().isoformat(),
            'profitability_analysis': profitability,
            'valuation_analysis': valuation,
            'financial_structure': structure,
            'dividend_analysis': dividends,
            'bullish_points': self.bullish_points,
            'bearish_points': self.bearish_points,
            'valuation_target_range': self._estimate_valuation_range(data, valuation),
            'summary': self._generate_summary(data, profitability, valuation, structure, dividends),
            'confidence_score': confidence,
            'confidence_breakdown': {
                'data_completeness': min(100, 100 - (len(self.missing_data) * 10)),
                'data_freshness': validated_data.get('overall_confidence', 50),
                'analysis_reliability': self._calculate_analysis_reliability(
                    profitability, valuation, structure
                )
            },
            'data_sources_used': sources_used,
            'missing_data': self.missing_data,
            'limitations': self.limitations
        }

        return report

    def _analyze_profitability(self, data: Dict, sources: List[str]) -> Dict[str, Any]:
        """Analyze profitability metrics."""
        analysis = {
            'eps_growth_yoy': None,
            'eps_growth_quarterly': None,
            'gross_margin_current': None,
            'gross_margin_trend': None,
            'operating_margin': None,
            'net_margin': None,
            'roe': None,
            'roa': None,
            'data_sources': sources
        }

        # EPS Growth
        if 'eps_current' in data and 'eps_previous' in data:
            eps_curr = data['eps_current']
            eps_prev = data['eps_previous']
            if eps_prev and eps_prev != 0:
                eps_growth = ((eps_curr - eps_prev) / eps_prev) * 100
                analysis['eps_growth_yoy'] = round(eps_growth, 2)
                if eps_growth > 15:
                    self.bullish_points.append({
                        'point': f"Strong EPS growth of {eps_growth:.1f}% YoY",
                        'data_source': 'financial_data',
                        'impact': 'strong'
                    })
                elif eps_growth < 0:
                    self.bearish_points.append({
                        'point': f"Declining EPS ({eps_growth:.1f}% YoY)",
                        'data_source': 'financial_data',
                        'impact': 'strong'
                    })
        else:
            self.missing_data.append('eps_growth')

        # Gross Margin (if available in extended data)
        if 'gross_margin' in data:
            gm = data['gross_margin']
            analysis['gross_margin_current'] = round(gm * 100, 2) if gm else None
            if gm:
                if gm > self.INDUSTRY_GROSS_MARGIN:
                    self.bullish_points.append({
                        'point': f"Gross margin {gm*100:.1f}% above industry average {self.INDUSTRY_GROSS_MARGIN*100:.1f}%",
                        'data_source': 'financial_data',
                        'impact': 'moderate'
                    })
                elif gm < self.INDUSTRY_GROSS_MARGIN * 0.8:
                    self.bearish_points.append({
                        'point': f"Gross margin {gm*100:.1f}% below industry average",
                        'data_source': 'financial_data',
                        'impact': 'moderate'
                    })
        else:
            self.missing_data.append('gross_margin')

        # Operating Margin
        if 'operating_margin' in data:
            om = data['operating_margin']
            analysis['operating_margin'] = round(om * 100, 2) if om else None
        else:
            self.missing_data.append('operating_margin')

        # Net Margin
        if 'net_margin' in data:
            nm = data['net_margin']
            analysis['net_margin'] = round(nm * 100, 2) if nm else None
        else:
            self.missing_data.append('net_margin')

        # ROE
        if 'roe' in data:
            roe = data['roe']
            analysis['roe'] = round(roe * 100, 2) if roe else None
            if roe and roe > self.MIN_HEALTHY_ROE:
                self.bullish_points.append({
                    'point': f"Strong ROE of {roe*100:.1f}% (above {self.MIN_HEALTHY_ROE*100:.0f}% threshold)",
                    'data_source': 'financial_data',
                    'impact': 'strong'
                })
            elif roe and roe < 0:
                self.bearish_points.append({
                    'point': f"Negative ROE indicates losses",
                    'data_source': 'financial_data',
                    'impact': 'strong'
                })
        else:
            self.missing_data.append('roe')

        # ROA
        if 'roa' in data:
            roa = data['roa']
            analysis['roa'] = round(roa * 100, 2) if roa else None
        else:
            self.missing_data.append('roa')

        return analysis

    def _analyze_valuation(self, data: Dict, sources: List[str]) -> Dict[str, Any]:
        """Analyze valuation metrics."""
        analysis = {
            'pe_ratio': None,
            'pe_vs_industry_avg': None,
            'valuation_status': 'unknown',
            'pb_ratio': None,
            'peg_ratio': None,
            'dcf_intrinsic_value': None,
            'dcf_vs_market_price': 'unknown',
            'ev_ebitda': None,
            'valuation_summary': '',
            'data_sources': sources
        }

        # PE Ratio
        if 'pe_ratio' in data and data['pe_ratio'] is not None:
            pe = data['pe_ratio']
            analysis['pe_ratio'] = pe
            pe_diff = pe - self.INDUSTRY_PE_AVERAGE
            analysis['pe_vs_industry_avg'] = round(pe_diff, 2)

            if pe < self.INDUSTRY_PE_AVERAGE * 0.8:
                analysis['valuation_status'] = 'undervalued'
                self.bullish_points.append({
                    'point': f"PE ratio {pe:.1f} is below industry average of {self.INDUSTRY_PE_AVERAGE:.1f}",
                    'data_source': 'financial_data',
                    'impact': 'strong'
                })
            elif pe > self.INDUSTRY_PE_AVERAGE * 1.2:
                analysis['valuation_status'] = 'overvalued'
                self.bearish_points.append({
                    'point': f"PE ratio {pe:.1f} is above industry average of {self.INDUSTRY_PE_AVERAGE:.1f}",
                    'data_source': 'financial_data',
                    'impact': 'strong'
                })
            else:
                analysis['valuation_status'] = 'fairly_valued'
        else:
            self.missing_data.append('pe_ratio')

        # PB Ratio
        if 'pb_ratio' in data:
            pb = data['pb_ratio']
            analysis['pb_ratio'] = pb
            if pb and pb < 1.0:
                self.bullish_points.append({
                    'point': f"Price-to-Book ratio {pb:.2f} < 1.0 suggests discount to book value",
                    'data_source': 'financial_data',
                    'impact': 'moderate'
                })
        else:
            self.missing_data.append('pb_ratio')

        # PEG Ratio (if we have eps growth)
        if 'eps_growth_yoy' in data and 'pe_ratio' in data and data['pe_ratio']:
            eps_growth = data.get('eps_current', 0) - data.get('eps_previous', 0)
            if data.get('eps_previous', 0) and data['eps_previous'] != 0:
                growth_pct = (eps_growth / data['eps_previous']) * 100
                if growth_pct > 0:
                    peg = data['pe_ratio'] / growth_pct
                    analysis['peg_ratio'] = round(peg, 2)
                    if peg < 1.0:
                        self.bullish_points.append({
                            'point': f"PEG ratio {peg:.2f} < 1.0 suggests attractive valuation relative to growth",
                            'data_source': 'derived',
                            'impact': 'moderate'
                        })

        # EV/EBITDA
        if 'ev_ebitda' in data:
            ev_eb = data['ev_ebitda']
            analysis['ev_ebitda'] = ev_eb
        else:
            self.missing_data.append('ev_ebitda')

        # DCF Valuation (simplified)
        if 'market_cap' in data and 'free_cash_flow' in data:
            fcf = data.get('free_cash_flow', 0)
            if fcf and fcf > 0:
                # Simple DCF: assume 3% perpetual growth, 10% discount rate
                growth_rate = 0.03
                discount_rate = 0.10
                terminal_value = (fcf * (1 + growth_rate)) / (discount_rate - growth_rate)
                analysis['dcf_intrinsic_value'] = round(terminal_value, 2)

                price = data.get('price', 1)
                if price and price > 0:
                    if terminal_value < price * 0.8:
                        analysis['dcf_vs_market_price'] = 'over'
                    elif terminal_value > price * 1.2:
                        analysis['dcf_vs_market_price'] = 'under'
                    else:
                        analysis['dcf_vs_market_price'] = 'fairly'

        return analysis

    def _analyze_financial_structure(self, data: Dict, sources: List[str]) -> Dict[str, Any]:
        """Analyze balance sheet strength."""
        analysis = {
            'debt_ratio': None,
            'debt_to_equity': None,
            'current_ratio': None,
            'quick_ratio': None,
            'interest_coverage': None,
            'working_capital': None,
            'financial_health': 'unknown',
            'data_sources': sources
        }

        # Debt Ratio
        if 'debt_ratio' in data:
            dr = data['debt_ratio']
            analysis['debt_ratio'] = round(dr * 100, 2) if dr else None
            if dr:
                if dr < self.HEALTHY_DEBT_RATIO:
                    self.bullish_points.append({
                        'point': f"Low debt ratio of {dr*100:.1f}% indicates conservative capital structure",
                        'data_source': 'financial_data',
                        'impact': 'moderate'
                    })
                elif dr > 0.75:
                    self.bearish_points.append({
                        'point': f"High debt ratio of {dr*100:.1f}% indicates high leverage risk",
                        'data_source': 'financial_data',
                        'impact': 'strong'
                    })
        else:
            self.missing_data.append('debt_ratio')

        # Debt-to-Equity
        if 'debt_to_equity' in data:
            dte = data['debt_to_equity']
            analysis['debt_to_equity'] = round(dte, 2) if dte else None
        else:
            self.missing_data.append('debt_to_equity')

        # Current Ratio
        if 'current_ratio' in data:
            cr = data['current_ratio']
            analysis['current_ratio'] = round(cr, 2) if cr else None
            if cr:
                if cr >= self.HEALTHY_CURRENT_RATIO:
                    self.bullish_points.append({
                        'point': f"Strong current ratio of {cr:.2f} indicates good short-term liquidity",
                        'data_source': 'financial_data',
                        'impact': 'moderate'
                    })
                elif cr < 1.0:
                    self.bearish_points.append({
                        'point': f"Current ratio of {cr:.2f} < 1.0 indicates potential liquidity stress",
                        'data_source': 'financial_data',
                        'impact': 'strong'
                    })
        else:
            self.missing_data.append('current_ratio')

        # Quick Ratio
        if 'quick_ratio' in data:
            qr = data['quick_ratio']
            analysis['quick_ratio'] = round(qr, 2) if qr else None
        else:
            self.missing_data.append('quick_ratio')

        # Interest Coverage
        if 'interest_coverage' in data:
            ic = data['interest_coverage']
            analysis['interest_coverage'] = round(ic, 2) if ic else None
            if ic:
                if ic < self.MIN_INTEREST_COVERAGE:
                    self.bearish_points.append({
                        'point': f"Low interest coverage of {ic:.1f}x indicates debt servicing difficulty",
                        'data_source': 'financial_data',
                        'impact': 'strong'
                    })
        else:
            self.missing_data.append('interest_coverage')

        # Working Capital
        if 'working_capital' in data:
            wc = data['working_capital']
            analysis['working_capital'] = round(wc, 0) if wc else None
        else:
            self.missing_data.append('working_capital')

        # Determine overall financial health
        health_score = 0
        if data.get('debt_ratio') is not None and data['debt_ratio'] < self.HEALTHY_DEBT_RATIO:
            health_score += 1
        if data.get('current_ratio') is not None and data['current_ratio'] >= self.HEALTHY_CURRENT_RATIO:
            health_score += 1
        if data.get('interest_coverage') is not None and data['interest_coverage'] >= self.MIN_INTEREST_COVERAGE:
            health_score += 1

        if health_score >= 2:
            analysis['financial_health'] = 'strong'
        elif health_score >= 1:
            analysis['financial_health'] = 'moderate'
        else:
            analysis['financial_health'] = 'weak'

        return analysis

    def _analyze_dividends(self, data: Dict, sources: List[str]) -> Dict[str, Any]:
        """Analyze dividend policy."""
        analysis = {
            'dividend_yield': None,
            'payout_ratio': None,
            'dividend_growth_rate': None,
            'dividend_stability': 'unknown',
            'is_sustainable': False,
            'data_sources': sources
        }

        # Dividend Yield
        if 'dividend_yield' in data:
            dy = data['dividend_yield']
            analysis['dividend_yield'] = round(dy * 100, 2) if dy else None
            if dy and dy > 0.04:  # 4% is good
                self.bullish_points.append({
                    'point': f"Attractive dividend yield of {dy*100:.2f}%",
                    'data_source': 'dividend_data',
                    'impact': 'moderate'
                })
        else:
            self.missing_data.append('dividend_yield')

        # Payout Ratio
        if 'dividend_payout_ratio' in data:
            pr = data['dividend_payout_ratio']
            analysis['payout_ratio'] = round(pr * 100, 2) if pr else None
            if pr:
                if pr > 0.80:
                    self.bearish_points.append({
                        'point': f"High dividend payout ratio of {pr*100:.1f}% may be unsustainable",
                        'data_source': 'dividend_data',
                        'impact': 'moderate'
                    })
                    analysis['is_sustainable'] = False
                elif pr < 0.50:
                    analysis['is_sustainable'] = True
                else:
                    analysis['is_sustainable'] = True
        else:
            self.missing_data.append('dividend_payout_ratio')

        # Dividend Growth Rate
        if 'dividend_growth_rate' in data:
            dgr = data['dividend_growth_rate']
            analysis['dividend_growth_rate'] = round(dgr * 100, 2) if dgr else None
            if dgr and dgr > 0:
                analysis['dividend_stability'] = 'stable'
                self.bullish_points.append({
                    'point': f"Positive dividend growth rate of {dgr*100:.1f}% shows commitment to shareholders",
                    'data_source': 'dividend_data',
                    'impact': 'moderate'
                })
            elif dgr and dgr < 0:
                analysis['dividend_stability'] = 'declining'
                self.bearish_points.append({
                    'point': f"Declining dividend growth of {dgr*100:.1f}%",
                    'data_source': 'dividend_data',
                    'impact': 'weak'
                })
        else:
            self.missing_data.append('dividend_growth_rate')

        return analysis

    def _estimate_valuation_range(self, data: Dict, valuation: Dict) -> Dict[str, Any]:
        """Estimate fair value range."""
        range_data = {
            'low_target': None,
            'high_target': None,
            'methodology': 'Conservative DCF and PE-based approach'
        }

        price = data.get('price', 0)
        if not price or price <= 0:
            return range_data

        pe = valuation.get('pe_ratio', 0)
        eps = data.get('eps_current', 0)

        if pe and eps and eps > 0:
            # Conservative PE-based target
            conservative_pe = self.INDUSTRY_PE_AVERAGE * 0.9
            aggressive_pe = self.INDUSTRY_PE_AVERAGE * 1.1

            range_data['low_target'] = round(eps * conservative_pe, 2)
            range_data['high_target'] = round(eps * aggressive_pe, 2)

        # Adjust with DCF if available
        if valuation.get('dcf_intrinsic_value'):
            dcf = valuation['dcf_intrinsic_value']
            if range_data['low_target']:
                range_data['low_target'] = round((range_data['low_target'] + dcf * 0.8) / 2, 2)
            if range_data['high_target']:
                range_data['high_target'] = round((range_data['high_target'] + dcf * 1.2) / 2, 2)

        return range_data

    def _generate_summary(self, data: Dict, profitability: Dict, valuation: Dict,
                         structure: Dict, dividends: Dict) -> str:
        """Generate executive summary."""
        summary_parts = []

        ticker = data.get('ticker', 'N/A')
        price = data.get('price', 'N/A')

        summary_parts.append(f"Financial Analysis for {ticker} (Price: ${price})")
        summary_parts.append("")

        # Profitability summary
        if profitability.get('roe'):
            summary_parts.append(
                f"Profitability: ROE of {profitability['roe']:.1f}% indicates "
                f"{'strong' if profitability['roe'] > 15 else 'moderate'} returns on equity. "
                f"EPS growth of {profitability.get('eps_growth_yoy', 'N/A')}% "
                f"shows {'positive' if (profitability.get('eps_growth_yoy') or 0) > 0 else 'negative'} momentum."
            )

        # Valuation summary
        if valuation.get('pe_ratio'):
            summary_parts.append(
                f"Valuation: PE ratio of {valuation['pe_ratio']:.1f}x is {valuation['valuation_status']} "
                f"(industry avg: {self.INDUSTRY_PE_AVERAGE:.1f}x). "
                f"Target range: ${valuation.get('low_target', 'N/A')} - ${valuation.get('high_target', 'N/A')}"
            )

        # Financial health summary
        if structure.get('financial_health'):
            summary_parts.append(
                f"Financial Health: {structure['financial_health'].capitalize()} with "
                f"debt ratio of {structure.get('debt_ratio', 'N/A')}% and "
                f"current ratio of {structure.get('current_ratio', 'N/A')}."
            )

        # Dividend summary
        if dividends.get('dividend_yield'):
            summary_parts.append(
                f"Dividend: Yield of {dividends['dividend_yield']:.2f}% with "
                f"{'sustainable' if dividends['is_sustainable'] else 'questionable'} payout at "
                f"{dividends.get('payout_ratio', 'N/A')}% of earnings."
            )

        # Investment conclusion
        bullish_count = len(self.bullish_points)
        bearish_count = len(self.bearish_points)
        if bullish_count > bearish_count:
            conclusion = "BULLISH - More positive factors support investment potential."
        elif bearish_count > bullish_count:
            conclusion = "BEARISH - More negative factors warrant caution."
        else:
            conclusion = "NEUTRAL - Mixed signals suggest careful consideration."

        summary_parts.append(f"\nOverall Assessment: {conclusion}")

        return "\n".join(summary_parts)

    def _calculate_confidence(self, validator_confidence: int, missing_count: int) -> int:
        """Calculate overall analysis confidence."""
        confidence = validator_confidence
        confidence -= min(missing_count * 5, 30)  # Penalty for missing data
        return max(0, min(100, int(confidence)))

    def _calculate_analysis_reliability(self, profitability: Dict, valuation: Dict,
                                       structure: Dict) -> int:
        """Calculate reliability of analysis based on data completeness."""
        reliability = 100
        total_fields = 0
        missing_fields = 0

        for section in [profitability, valuation, structure]:
            for key, value in section.items():
                if key != 'data_sources':
                    total_fields += 1
                    if value is None or value == 'unknown':
                        missing_fields += 1

        if total_fields > 0:
            reliability = int((total_fields - missing_fields) / total_fields * 100)

        return reliability


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Perform financial analysis on validated stock data'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input validated data JSON file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output financial analysis JSON file'
    )

    args = parser.parse_args()

    # Read validated data
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            validated_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Analyze
    analyzer = FinancialAnalyzer()
    analysis = analyzer.analyze(validated_data)

    # Write output
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"Analysis complete. Output written to {args.output}")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
