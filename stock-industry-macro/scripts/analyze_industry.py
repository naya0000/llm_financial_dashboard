#!/usr/bin/env python3
"""
Stock Industry & Macro Analysis Script
Analyzes industry positioning, competitive landscape, and macro environment impacts.

Usage:
    python analyze_industry.py --input validated_data.json --output industry_analysis.json
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


class IndustryAnalyzer:
    """Analyzes industry and macroeconomic factors affecting a stock."""

    # Default sector/industry benchmarks (can be extended with real data)
    SECTOR_BENCHMARKS = {
        'Technology': {
            'avg_pe': 25.0,
            'avg_pb': 3.5,
            'avg_roe': 18.0,
            'description': 'Technology companies'
        },
        'Healthcare': {
            'avg_pe': 22.0,
            'avg_pb': 2.8,
            'avg_roe': 15.0,
            'description': 'Healthcare companies'
        },
        'Financials': {
            'avg_pe': 12.0,
            'avg_pb': 1.2,
            'avg_roe': 12.0,
            'description': 'Financial services'
        },
        'Industrials': {
            'avg_pe': 14.0,
            'avg_pb': 1.5,
            'avg_roe': 13.0,
            'description': 'Industrial companies'
        },
        'Consumer Discretionary': {
            'avg_pe': 15.0,
            'avg_pb': 1.8,
            'avg_roe': 14.0,
            'description': 'Consumer discretionary'
        },
        'Consumer Staples': {
            'avg_pe': 18.0,
            'avg_pb': 2.0,
            'avg_roe': 16.0,
            'description': 'Consumer staples'
        },
        'Energy': {
            'avg_pe': 11.0,
            'avg_pb': 1.0,
            'avg_roe': 11.0,
            'description': 'Energy companies'
        },
        'Materials': {
            'avg_pe': 10.0,
            'avg_pb': 1.3,
            'avg_roe': 12.0,
            'description': 'Materials/Mining'
        },
        'Utilities': {
            'avg_pe': 16.0,
            'avg_pb': 1.6,
            'avg_roe': 10.0,
            'description': 'Utility companies'
        },
        'Real Estate': {
            'avg_pe': 14.0,
            'avg_pb': 0.8,
            'avg_roe': 8.0,
            'description': 'Real estate'
        },
        'Semiconductors': {
            'avg_pe': 28.0,
            'avg_pb': 4.0,
            'avg_roe': 20.0,
            'description': 'Semiconductor manufacturers'
        },
        'Pharmaceuticals': {
            'avg_pe': 16.0,
            'avg_pb': 2.5,
            'avg_roe': 14.0,
            'description': 'Pharmaceutical companies'
        }
    }

    def __init__(self):
        """Initialize industry analyzer."""
        self.sector_benchmarks = self.SECTOR_BENCHMARKS

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

    def extract_company_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract company information from validated_data structure."""
        inner = data.get('validated_data', data)
        ci = inner.get('company_info', {})
        ticker = inner.get('metadata', {}).get('ticker', data.get('ticker', 'UNKNOWN'))

        # Detect currency from ticker suffix
        currency = 'USD'
        if ticker.endswith('.TW') or ticker.endswith('.TWO'):
            currency = 'TWD'
        elif ticker.endswith('.HK'):
            currency = 'HKD'

        roe_raw = ci.get('return_on_equity')
        return {
            'ticker': ticker,
            'company_name': ci.get('name', 'N/A'),
            'sector': ci.get('sector', 'Unknown'),
            'industry': ci.get('industry', 'Unknown'),
            'market_cap': ci.get('market_cap'),
            'pe_ratio': ci.get('pe_ratio'),
            'pb_ratio': ci.get('pb_ratio'),
            'roe': round(roe_raw * 100, 2) if roe_raw else None,
            'debt_to_equity': ci.get('debt_to_equity'),
            'current_ratio': ci.get('current_ratio'),
            'currency': currency,
            'industry_peers': ci.get('industry_peers', [])
        }

    def analyze_market_position(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze company's market position within sector."""
        sector = company_info.get('sector', 'Unknown')
        market_cap = company_info.get('market_cap')

        # Market cap classification
        if market_cap:
            if market_cap >= 200e9:
                cap_class = 'large-cap'
                position = 1
            elif market_cap >= 10e9:
                cap_class = 'mid-cap'
                position = 2
            elif market_cap >= 2e9:
                cap_class = 'small-cap'
                position = 3
            else:
                cap_class = 'micro-cap'
                position = 4
        else:
            cap_class = 'unknown'
            position = None

        # Get sector benchmarks
        benchmarks = self.sector_benchmarks.get(sector, {})
        sector_avg_pe = benchmarks.get('avg_pe')
        sector_avg_pb = benchmarks.get('avg_pb')
        sector_avg_roe = benchmarks.get('avg_roe')

        # Calculate relative valuations
        pe_comparison = None
        pb_comparison = None
        roe_comparison = None

        company_pe = company_info.get('pe_ratio')
        if company_pe and sector_avg_pe:
            pe_premium = ((company_pe - sector_avg_pe) / sector_avg_pe) * 100
            if pe_premium > 20:
                pe_interpretation = 'significantly overvalued vs sector'
            elif pe_premium > 5:
                pe_interpretation = 'moderately overvalued vs sector'
            elif pe_premium > -5:
                pe_interpretation = 'fairly valued vs sector'
            elif pe_premium > -20:
                pe_interpretation = 'moderately undervalued vs sector'
            else:
                pe_interpretation = 'significantly undervalued vs sector'

            pe_comparison = {
                'company_pe': round(company_pe, 2),
                'sector_average_pe': round(sector_avg_pe, 2),
                'premium_discount': round(pe_premium, 1),
                'interpretation': pe_interpretation
            }

        company_pb = company_info.get('pb_ratio')
        if company_pb and sector_avg_pb:
            pb_premium = ((company_pb - sector_avg_pb) / sector_avg_pb) * 100
            pb_comparison = {
                'company_pb': round(company_pb, 2),
                'sector_average_pb': round(sector_avg_pb, 2),
                'premium_discount': round(pb_premium, 1)
            }

        company_roe = company_info.get('roe')
        if company_roe and sector_avg_roe:
            if company_roe > sector_avg_roe + 2:
                roe_interpretation = 'above sector average'
            elif company_roe >= sector_avg_roe - 2:
                roe_interpretation = 'in line with sector'
            else:
                roe_interpretation = 'below sector average'

            roe_comparison = {
                'company_roe': round(company_roe, 2),
                'sector_average_roe': round(sector_avg_roe, 2),
                'interpretation': roe_interpretation
            }

        return {
            'sector': sector,
            'industry': company_info.get('industry', 'Unknown'),
            'market_cap_ranking': {
                'position': position,
                'total_companies_in_sector': 'N/A (estimated from market)',
                'percentile': None,
                'interpretation': cap_class
            },
            'relative_valuation': {
                'pe_vs_sector': pe_comparison,
                'pb_vs_sector': pb_comparison,
                'roe_vs_sector': roe_comparison
            }
        }

    def analyze_competitive_position(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze competitive position."""
        # This would be enhanced with actual competitive data
        market_cap = company_info.get('market_cap')
        industry_peers = company_info.get('industry_peers', [])

        if market_cap and market_cap >= 50e9:
            market_position = 'market leader'
        elif market_cap and market_cap >= 10e9:
            market_position = 'strong competitor'
        else:
            market_position = 'niche player'

        # Generic competitive advantages/risks based on sector
        sector = company_info.get('sector', '')
        advantages = self._get_sector_advantages(sector)
        risks = self._get_sector_risks(sector)

        return {
            'market_position': market_position,
            'competitive_advantages': advantages,
            'competitive_risks': risks,
            'industry_fragmentation': 'moderate',  # Would be determined from actual data
            'estimated_market_share': None,
            'key_competitors': industry_peers[:5] if industry_peers else []
        }

    def _get_sector_advantages(self, sector: str) -> List[str]:
        """Get typical competitive advantages by sector."""
        advantages_map = {
            'Technology': ['Innovation capability', 'Intellectual property', 'Switching costs', 'Network effects'],
            'Healthcare': ['Patent protection', 'Brand loyalty', 'Regulatory moats', 'Switching costs'],
            'Pharmaceuticals': ['Patent exclusivity', 'R&D pipeline', 'Regulatory barriers'],
            'Semiconductors': ['Technology leadership', 'Manufacturing scale', 'Capital intensity barrier'],
            'Financials': ['Brand reputation', 'Customer relationships', 'Capital position'],
            'Utilities': ['Regulatory monopoly', 'Essential services', 'Stable cash flows'],
            'Consumer Staples': ['Brand strength', 'Distribution network', 'Customer loyalty'],
            'Energy': ['Reserves', 'Extraction technology', 'Cost position'],
            'Materials': ['Access to resources', 'Scale economies', 'Production efficiency']
        }
        return advantages_map.get(sector, ['Market position', 'Operational efficiency'])

    def _get_sector_risks(self, sector: str) -> List[str]:
        """Get typical competitive risks by sector."""
        risks_map = {
            'Technology': ['Rapid obsolescence', 'New competitors', 'Regulation', 'Talent retention'],
            'Healthcare': ['Regulatory changes', 'Patent expiration', 'Reimbursement pressure'],
            'Pharmaceuticals': ['Generic competition', 'Patent cliffs', 'Clinical trial failure'],
            'Semiconductors': ['Cyclicality', 'Competition', 'Capital requirements', 'Geopolitical risk'],
            'Financials': ['Interest rate sensitivity', 'Credit risk', 'Regulatory changes'],
            'Utilities': ['Regulatory risk', 'Capital intensity', 'Energy transition'],
            'Consumer Staples': ['Competition', 'Margin pressure', 'Consumer shifts'],
            'Energy': ['Commodity price exposure', 'Transition risk', 'Geopolitical risk'],
            'Materials': ['Commodity price exposure', 'Cyclicality', 'Environmental regulation']
        }
        return risks_map.get(sector, ['Market competition', 'Economic sensitivity'])

    def analyze_industry_cycle(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze industry cycle stage and outlook."""
        sector = company_info.get('sector', '')
        roe = company_info.get('roe', 0)

        # Simplified cycle analysis based on ROE
        if roe and roe > 15:
            cycle_stage = 'mid cycle'
            growth = 'expanding'
        elif roe and roe > 8:
            cycle_stage = 'early cycle'
            growth = 'stable'
        else:
            cycle_stage = 'late cycle'
            growth = 'contracting'

        cycle_drivers = self._get_cycle_drivers(sector)

        return {
            'current_stage': cycle_stage,
            'cycle_drivers': cycle_drivers,
            'growth_outlook': growth,
            'investment_implication': self._get_investment_implication(cycle_stage)
        }

    def _get_cycle_drivers(self, sector: str) -> List[str]:
        """Get typical cycle drivers by sector."""
        drivers_map = {
            'Technology': ['Revenue growth', 'Cloud adoption', 'AI/ML trends', 'Product cycles'],
            'Healthcare': ['Aging population', 'New drug approvals', 'Healthcare spending', 'Patent dynamics'],
            'Semiconductors': ['Device demand', 'Capacity utilization', 'Price trends', 'Technology node transitions'],
            'Financials': ['Interest rates', 'Loan demand', 'Credit quality', 'Asset quality'],
            'Energy': ['Oil/gas prices', 'Demand cycles', 'Geopolitical factors', 'Energy transition'],
            'Consumer Staples': ['Consumer spending', 'Pricing power', 'Competitive dynamics'],
            'Real Estate': ['Interest rates', 'Economic growth', 'Vacancy rates', 'Rent growth']
        }
        return drivers_map.get(sector, ['Demand', 'Pricing', 'Competition', 'Regulation'])

    def _get_investment_implication(self, cycle_stage: str) -> str:
        """Get investment implication for cycle stage."""
        implications = {
            'early cycle': 'favorable',
            'mid cycle': 'neutral',
            'late cycle': 'cautious',
            'downturn': 'unattractive'
        }
        return implications.get(cycle_stage, 'neutral')

    def analyze_macro_environment(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze macroeconomic environment impacts."""
        sector = company_info.get('sector', '')
        debt_to_equity = company_info.get('debt_to_equity')

        return {
            'interest_rate_sensitivity': self._get_rate_sensitivity(sector, debt_to_equity),
            'currency_exposure': self._get_currency_exposure(sector, company_info.get('currency')),
            'inflation_impact': self._get_inflation_impact(sector),
            'commodity_exposure': self._get_commodity_exposure(sector)
        }

    def _get_rate_sensitivity(self, sector: str, debt_ratio: Optional[float]) -> Dict[str, str]:
        """Analyze interest rate sensitivity."""
        rate_sensitivities = {
            'Financials': {'sensitivity': 'high', 'direction': 'negative', 'explanation': 'Higher rates reduce lending margins and mortgage demand'},
            'Real Estate': {'sensitivity': 'high', 'direction': 'negative', 'explanation': 'Higher rates reduce property valuations and REITs'},
            'Utilities': {'sensitivity': 'moderate', 'direction': 'negative', 'explanation': 'Higher discount rates reduce asset valuations'},
            'Healthcare': {'sensitivity': 'moderate', 'direction': 'neutral', 'explanation': 'Moderate sensitivity to rates through debt costs'},
            'Technology': {'sensitivity': 'high', 'direction': 'negative', 'explanation': 'High multiples compress with rising rates'},
            'Consumer Staples': {'sensitivity': 'low', 'direction': 'neutral', 'explanation': 'Defensive, less sensitive to rates'}
        }

        result = rate_sensitivities.get(sector, {'sensitivity': 'moderate', 'direction': 'neutral', 'explanation': 'Standard economic sensitivity'})

        return result

    def _get_currency_exposure(self, sector: str, currency: Optional[str]) -> Dict[str, Any]:
        """Analyze currency exposure."""
        exposure_map = {
            'Technology': {'sensitivity': 'high', 'beneficiaries': 'strong local currency'},
            'Energy': {'sensitivity': 'high', 'beneficiaries': 'weak local currency'},
            'Pharma': {'sensitivity': 'high', 'beneficiaries': 'weak local currency'},
            'Exporters': {'sensitivity': 'high', 'beneficiaries': 'weak local currency'},
        }

        base_exposure = exposure_map.get(sector, {'sensitivity': 'moderate', 'beneficiaries': 'neutral'})

        relevant_pairs = []
        if currency == 'TWD':
            relevant_pairs = ['TWD/USD', 'TWD/CNY', 'TWD/JPY']
        elif currency == 'USD':
            relevant_pairs = ['USD/CNY', 'USD/EUR', 'DXY']
        elif currency == 'EUR':
            relevant_pairs = ['EUR/USD', 'EUR/GBP']

        return {
            'primary_currency': currency or 'USD',
            'fx_sensitivity': base_exposure['sensitivity'],
            'beneficiaries': base_exposure['beneficiaries'],
            'relevant_pairs': relevant_pairs
        }

    def _get_inflation_impact(self, sector: str) -> Dict[str, str]:
        """Analyze inflation impact."""
        inflation_impacts = {
            'Utilities': {'sensitivity': 'moderate', 'pricing_power': 'strong', 'cost_pass_through': 'easy'},
            'Consumer Staples': {'sensitivity': 'high', 'pricing_power': 'strong', 'cost_pass_through': 'easy'},
            'Technology': {'sensitivity': 'low', 'pricing_power': 'strong', 'cost_pass_through': 'easy'},
            'Financials': {'sensitivity': 'moderate', 'pricing_power': 'moderate', 'cost_pass_through': 'moderate'},
            'Industrials': {'sensitivity': 'high', 'pricing_power': 'moderate', 'cost_pass_through': 'difficult'},
            'Materials': {'sensitivity': 'high', 'pricing_power': 'weak', 'cost_pass_through': 'difficult'}
        }

        return inflation_impacts.get(sector, {'sensitivity': 'moderate', 'pricing_power': 'moderate', 'cost_pass_through': 'moderate'})

    def _get_commodity_exposure(self, sector: str) -> Dict[str, Any]:
        """Analyze commodity exposure."""
        commodity_map = {
            'Energy': {'commodities': ['crude oil', 'natural gas'], 'sensitivity': 'high'},
            'Materials': {'commodities': ['metals', 'agricultural commodities'], 'sensitivity': 'high'},
            'Chemicals': {'commodities': ['crude oil', 'natural gas'], 'sensitivity': 'high'},
            'Airlines': {'commodities': ['jet fuel'], 'sensitivity': 'high'},
            'Consumer Staples': {'commodities': ['agricultural commodities'], 'sensitivity': 'moderate'},
            'Technology': {'commodities': ['rare earth metals'], 'sensitivity': 'low'}
        }

        exposure = commodity_map.get(sector, {'commodities': [], 'sensitivity': 'low'})

        return {
            'relevant_commodities': exposure.get('commodities', []),
            'price_sensitivity': exposure.get('sensitivity', 'low')
        }

    def analyze_policy_environment(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze policy and regulatory environment."""
        sector = company_info.get('sector', '')

        return {
            'regulatory_risks': self._get_regulatory_risks(sector),
            'policy_tailwinds': self._get_policy_tailwinds(sector),
            'geopolitical_risks': self._get_geopolitical_risks(sector),
            'esg_considerations': self._get_esg_considerations(sector)
        }

    def _get_regulatory_risks(self, sector: str) -> List[str]:
        """Get regulatory risks by sector."""
        risks_map = {
            'Technology': ['Antitrust scrutiny', 'Data privacy regulation', 'Content moderation rules', 'AI regulation'],
            'Healthcare': ['Drug pricing regulation', 'Medicare negotiation', 'FDA approval delays'],
            'Financials': ['Capital requirements', 'Stress tests', 'Consumer protection', 'Fintech regulation'],
            'Energy': ['Environmental regulation', 'Carbon pricing', 'Fossil fuel restrictions'],
            'Utilities': ['Rate regulation', 'Renewable mandates', 'Grid modernization'],
            'Pharma': ['Patent reform', 'Pricing controls', 'Approval processes'],
            'Semiconductors': ['Export controls', 'Foreign investment rules', 'Supply chain security']
        }
        return risks_map.get(sector, ['Regulatory changes', 'Compliance costs'])

    def _get_policy_tailwinds(self, sector: str) -> List[str]:
        """Get policy tailwinds by sector."""
        tailwinds_map = {
            'Clean Energy': ['Renewable subsidies', 'Tax credits', 'Grid investment incentives'],
            'Healthcare': ['Aging population policies', 'Healthcare spending', 'R&D tax credits'],
            'Semiconductors': ['CHIPS Act subsidies', 'Supply chain incentives', 'Tech investment'],
            'Technology': ['5G infrastructure', 'AI research funding', 'Tech talent programs'],
            'Infrastructure': ['Infrastructure spending', 'Project pipelines', 'Government contracts'],
            'EVs': ['EV subsidies', 'Charging infrastructure', 'Emissions standards']
        }
        return tailwinds_map.get(sector, [])

    def _get_geopolitical_risks(self, sector: str) -> List[str]:
        """Get geopolitical risks by sector."""
        risks_map = {
            'Energy': ['OPEC dynamics', 'Middle East tensions', 'Russia sanctions', 'Supply disruptions'],
            'Semiconductors': ['China tensions', 'Export controls', 'Taiwan relations', 'Supply chain'],
            'Technology': ['US-China trade', 'Data sovereignty', 'Tech nationalism'],
            'Materials': ['Trade wars', 'Sanctions', 'Supply concentration'],
            'Defense': ['Geopolitical tensions', 'Military spending', 'International conflicts']
        }
        return risks_map.get(sector, [])

    def _get_esg_considerations(self, sector: str) -> str:
        """Get ESG considerations by sector."""
        esg_map = {
            'Energy': 'High ESG scrutiny; transition risk from climate policies; stranded assets risk',
            'Materials': 'Environmental impacts; water usage; mining practices; recycling focus',
            'Utilities': 'Transition to renewable energy; grid modernization; carbon reduction targets',
            'Healthcare': 'Drug pricing ethics; access to medicines; clinical trial diversity',
            'Technology': 'Data privacy; labor practices; supply chain accountability; energy usage',
            'Consumer Staples': 'Product safety; supply chain ethics; environmental sourcing',
            'Financials': 'Climate risk disclosure; fossil fuel lending; ESG investing growth'
        }
        return esg_map.get(sector, 'Standard ESG considerations apply')

    def assess_sector_attractiveness(self, company_info: Dict[str, Any],
                                   industry_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall sector attractiveness."""
        cycle = industry_analysis.get('industry_cycle_analysis', {})
        cycle_stage = cycle.get('current_stage', 'mid cycle')

        if cycle_stage == 'early cycle':
            growth = 'high'
        elif cycle_stage == 'mid cycle':
            growth = 'moderate'
        else:
            growth = 'low'

        return {
            'growth_potential': growth,
            'profitability': 'moderate',
            'competitive_intensity': 'moderate',
            'overall_attractiveness': 'attractive' if cycle_stage in ['early cycle', 'mid cycle'] else 'neutral',
            'key_catalysts': self._get_sector_catalysts(company_info.get('sector', '')),
            'headwinds': self._get_sector_headwinds(company_info.get('sector', ''))
        }

    def _get_sector_catalysts(self, sector: str) -> List[str]:
        """Get key catalysts for sector."""
        catalysts_map = {
            'Technology': ['AI adoption acceleration', 'Cloud growth', 'Digital transformation', 'Tech M&A'],
            'Healthcare': ['Aging demographics', 'Drug launches', 'Healthcare spending growth'],
            'Semiconductors': ['Device demand recovery', 'AI chip demand', 'Capacity expansion'],
            'Energy': ['Energy demand growth', 'OPEC decisions', 'Geopolitical factors'],
            'EVs': ['EV adoption growth', 'Battery technology', 'Charging infrastructure expansion']
        }
        return catalysts_map.get(sector, ['Market growth', 'Technology improvements', 'M&A activity'])

    def _get_sector_headwinds(self, sector: str) -> List[str]:
        """Get key headwinds for sector."""
        headwinds_map = {
            'Technology': ['Valuations', 'Regulation', 'Competition', 'Macro sensitivity'],
            'Retail': ['E-commerce competition', 'Margin pressure', 'Labor costs'],
            'Energy': ['Transition pressure', 'Volatility', 'Supply challenges'],
            'Financials': ['Low rates', 'Regulation', 'Credit risk'],
            'Traditional Media': ['Cord cutting', 'Advertising pressure', 'Content costs']
        }
        return headwinds_map.get(sector, ['Competition', 'Economic sensitivity', 'Regulation'])

    def validate_data_quality(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data quality and completeness."""
        warnings = []
        sector_data = self.sector_benchmarks.get(company_info.get('sector', 'Unknown'), {})

        if not company_info.get('sector') or company_info.get('sector') == 'Unknown':
            warnings.append('Sector classification not available')

        if not company_info.get('industry') or company_info.get('industry') == 'Unknown':
            warnings.append('Industry classification not available')

        if not sector_data:
            warnings.append('Sector benchmarks not available for detailed comparison')

        if not company_info.get('market_cap'):
            warnings.append('Market cap data not available')

        if not company_info.get('pe_ratio'):
            warnings.append('P/E ratio not available for valuation comparison')

        return {
            'sector_data_available': bool(sector_data),
            'industry_data_available': bool(company_info.get('industry')),
            'comparable_companies_found': len(company_info.get('industry_peers', [])),
            'data_currency': 'Most recent available',
            'warnings': warnings
        }

    def calculate_confidence(self, company_info: Dict[str, Any],
                           data_quality: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence scores."""
        sector_available = data_quality.get('sector_data_available', False)
        data_avail = 0.7 if sector_available else 0.4
        data_avail = min(1.0, data_avail + (len(data_quality.get('warnings', [])) > 0 and -0.2 or 0))

        sector_clarity = 0.8 if company_info.get('sector') != 'Unknown' else 0.3
        macro_visibility = 0.7  # Standard macro data availability

        overall = (data_avail * 0.4 + sector_clarity * 0.4 + macro_visibility * 0.2)

        if overall >= 0.75:
            recommendation = 'Reliable framework'
        elif overall >= 0.5:
            recommendation = 'Use as context'
        else:
            recommendation = 'Subject to macro shifts'

        return {
            'overall': min(1.0, max(0.0, overall)),
            'factors': {
                'data_availability': min(1.0, max(0.0, data_avail)),
                'sector_definition_clarity': min(1.0, max(0.0, sector_clarity)),
                'macro_visibility': min(1.0, max(0.0, macro_visibility))
            },
            'recommendation': recommendation
        }

    def analyze(self, input_path: str, output_path: str):
        """Main analysis workflow."""
        try:
            # Load data
            data = self.load_data(input_path)

            # Extract company info
            company_info = self.extract_company_info(data)

            # Perform analyses
            industry_position = self.analyze_market_position(company_info)
            competitive = self.analyze_competitive_position(company_info)
            industry_cycle = self.analyze_industry_cycle(company_info)
            macro_env = self.analyze_macro_environment(company_info)
            policy_env = self.analyze_policy_environment(company_info)
            data_quality = self.validate_data_quality(company_info)

            # Assemble industry analysis dict for sector attractiveness
            industry_analysis = {
                'industry_cycle_analysis': industry_cycle
            }
            sector_attr = self.assess_sector_attractiveness(company_info, industry_analysis)

            confidence = self.calculate_confidence(company_info, data_quality)

            # Build output
            output = {
                'ticker': company_info['ticker'],
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'industry_position': industry_position,
                'competitive_analysis': competitive,
                'industry_cycle_analysis': industry_cycle,
                'macro_environment': macro_env,
                'policy_environment': policy_env,
                'sector_attractiveness': sector_attr,
                'anti_hallucination_checks': data_quality,
                'confidence': confidence
            }

            # Save output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            print(f"Industry analysis complete. Results saved to {output_path}")
            return output

        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Stock Industry & Macro Analysis Tool'
    )
    parser.add_argument('--input', required=True, help='Input JSON file with validated stock data')
    parser.add_argument('--output', required=True, help='Output JSON file for analysis results')

    args = parser.parse_args()

    analyzer = IndustryAnalyzer()
    analyzer.analyze(args.input, args.output)


if __name__ == '__main__':
    main()
