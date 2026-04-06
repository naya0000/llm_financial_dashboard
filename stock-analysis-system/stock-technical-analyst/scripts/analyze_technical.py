#!/usr/bin/env python3
"""
Stock Technical Analyst Script
Analyzes price action, indicators, and volume to generate trading signals.
"""

import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import sys


class TechnicalAnalyzer:
    """Performs technical analysis on stock price data."""

    # Indicator thresholds
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    RSI_NEUTRAL_HIGH = 60
    RSI_NEUTRAL_LOW = 40

    MACD_HISTOGRAM_MIN_STRENGTH = 0.001  # Minimum meaningful histogram value

    KD_OVERBOUGHT = 80
    KD_OVERSOLD = 20

    BOLLINGER_BAND_WIDTH_THRESHOLD = 0.05  # 5% for squeeze detection

    def __init__(self):
        self.signals = []

    def analyze(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform complete technical analysis.

        Args:
            validated_data: Validated data package from validator

        Returns:
            Technical analysis report with signals and targets
        """
        self.signals = []
        inner = validated_data.get('validated_data', {})
        ticker = inner.get('metadata', {}).get('ticker', validated_data.get('ticker', 'UNKNOWN'))
        ci = inner.get('company_info', {})
        ph = inner.get('price_history', [])
        latest = ph[-1] if ph else {}
        price = latest.get('close', 0)

        # Flatten data for downstream methods
        data = {
            'ticker': ticker,
            'price': price,
            'volume': latest.get('volume'),
            'volume_average': None,
            'high_52week': ci.get('52_week_high'),
            'low_52week': ci.get('52_week_low'),
        }

        # Extract and flatten indicator data
        raw_ti = inner.get('technical_indicators', {})
        indicators = {
            'rsi': raw_ti.get('rsi_14', {}).get('value'),
            'macd_line': raw_ti.get('macd', {}).get('macd'),
            'macd_signal': raw_ti.get('macd', {}).get('signal'),
            'macd_histogram': raw_ti.get('macd', {}).get('histogram'),
            'bb_upper': raw_ti.get('bollinger_bands', {}).get('upper'),
            'bb_middle': raw_ti.get('bollinger_bands', {}).get('middle'),
            'bb_lower': raw_ti.get('bollinger_bands', {}).get('lower'),
            'kd_k': raw_ti.get('stochastic_kd', {}).get('k_percent'),
            'kd_d': raw_ti.get('stochastic_kd', {}).get('d_percent'),
            'ma_20': latest.get('ma_20'),
            'ma_50': ci.get('50_day_average'),
            'ma_200': ci.get('200_day_average'),
        }

        # Trend Analysis
        trend = self._analyze_trend(data, indicators)

        # Support and Resistance
        supp_resist = self._identify_support_resistance(data, indicators)

        # Momentum Indicators
        momentum = self._analyze_momentum(indicators)

        # Bollinger Bands
        bollinger = self._analyze_bollinger_bands(data, indicators)

        # Volume Analysis
        volume = self._analyze_volume(data, indicators)

        # Generate Trading Signals
        self._generate_signals(trend, momentum, supp_resist, bollinger, volume)

        # Price Targets
        price_targets = self._calculate_price_targets(price, supp_resist, trend, momentum)

        # Risk Levels
        risk_levels = self._calculate_risk_levels(price, supp_resist, trend)

        # Calculate confidence
        confidence = self._calculate_confidence(trend, momentum, self.signals)

        # Build summary
        summary = self._generate_summary(ticker, price, trend, momentum, supp_resist)

        # Build report
        report = {
            'agent': 'stock-technical-analyst',
            'ticker': ticker,
            'analysis_date': datetime.now().isoformat(),
            'trend_analysis': trend,
            'support_resistance': supp_resist,
            'momentum_indicators': momentum,
            'bollinger_bands': bollinger,
            'volume_analysis': volume,
            'signals': self.signals,
            'price_targets': price_targets,
            'risk_levels': risk_levels,
            'summary': summary,
            'confidence': confidence,
            'risk_note': self._get_risk_disclaimer()
        }

        return report

    def _analyze_trend(self, data: Dict, indicators: Dict) -> Dict[str, Any]:
        """Analyze trend direction and strength."""
        trend = {
            'current_trend': 'consolidation',
            'trend_strength': 50,
            'ma20': indicators.get('ma_20', None),
            'ma50': indicators.get('ma_50', None),
            'ma200': indicators.get('ma_200', None),
            'ma_alignment': 'mixed',
            'price_position_vs_ma': 'neutral',
            'hma': indicators.get('hma', None),
            'trend_description': ''
        }

        price = data.get('price', 0)
        ma20 = indicators.get('ma_20', None)
        ma50 = indicators.get('ma_50', None)
        ma200 = indicators.get('ma_200', None)

        if not all([ma20, ma50, ma200, price]):
            trend['trend_description'] = 'Insufficient data for trend analysis'
            return trend

        # Determine MA alignment
        if ma20 > ma50 > ma200:
            trend['ma_alignment'] = 'bullish'
            trend['current_trend'] = 'bullish'
            trend['trend_strength'] = 85
            trend['trend_description'] = 'Strong uptrend: MA 20 > MA 50 > MA 200'

            if price > ma20:
                trend['price_position_vs_ma'] = 'above'
                trend['trend_strength'] = 95
            elif price > ma50:
                trend['price_position_vs_ma'] = 'above'
                trend['trend_strength'] = 85
            else:
                trend['price_position_vs_ma'] = 'below'
                trend['trend_strength'] = 70

        elif ma20 < ma50 < ma200:
            trend['ma_alignment'] = 'bearish'
            trend['current_trend'] = 'bearish'
            trend['trend_strength'] = 85
            trend['trend_description'] = 'Strong downtrend: MA 20 < MA 50 < MA 200'

            if price < ma20:
                trend['price_position_vs_ma'] = 'below'
                trend['trend_strength'] = 95
            elif price < ma50:
                trend['price_position_vs_ma'] = 'below'
                trend['trend_strength'] = 85
            else:
                trend['price_position_vs_ma'] = 'above'
                trend['trend_strength'] = 70

        else:
            trend['ma_alignment'] = 'mixed'
            trend['current_trend'] = 'consolidation'
            trend['trend_strength'] = 45
            trend['trend_description'] = 'Consolidation: Moving averages tangled, no clear direction'

            # Determine price position
            if price > max(ma20, ma50, ma200):
                trend['price_position_vs_ma'] = 'above'
            elif price < min(ma20, ma50, ma200):
                trend['price_position_vs_ma'] = 'below'
            else:
                trend['price_position_vs_ma'] = 'crossover_zone'

        return trend

    def _identify_support_resistance(self, data: Dict, indicators: Dict) -> Dict[str, Any]:
        """Identify key support and resistance levels."""
        supp_resist = {
            'key_support_levels': [],
            'key_resistance_levels': [],
            'immediate_support': None,
            'immediate_resistance': None
        }

        price = data.get('price', 0)

        # Use provided support/resistance if available
        if 'support_levels' in indicators:
            for level_data in indicators['support_levels']:
                if isinstance(level_data, dict):
                    supp_resist['key_support_levels'].append(level_data)
                else:
                    supp_resist['key_support_levels'].append({
                        'level': level_data,
                        'strength': 'moderate',
                        'touches': 1,
                        'notes': 'Identified support level'
                    })

        if 'resistance_levels' in indicators:
            for level_data in indicators['resistance_levels']:
                if isinstance(level_data, dict):
                    supp_resist['key_resistance_levels'].append(level_data)
                else:
                    supp_resist['key_resistance_levels'].append({
                        'level': level_data,
                        'strength': 'moderate',
                        'touches': 1,
                        'notes': 'Identified resistance level'
                    })

        # Set immediate support/resistance
        if supp_resist['key_support_levels']:
            supp_resist['immediate_support'] = max(
                [s['level'] for s in supp_resist['key_support_levels'] if s['level'] < price],
                default=None
            )

        if supp_resist['key_resistance_levels']:
            supp_resist['immediate_resistance'] = min(
                [r['level'] for r in supp_resist['key_resistance_levels'] if r['level'] > price],
                default=None
            )

        # If no explicit levels provided, use recent highs/lows
        if not supp_resist['key_support_levels']:
            if 'low_52week' in data:
                supp_resist['key_support_levels'].append({
                    'level': data['low_52week'],
                    'strength': 'moderate',
                    'touches': 1,
                    'notes': '52-week low'
                })

        if not supp_resist['key_resistance_levels']:
            if 'high_52week' in data:
                supp_resist['key_resistance_levels'].append({
                    'level': data['high_52week'],
                    'strength': 'moderate',
                    'touches': 1,
                    'notes': '52-week high'
                })

        return supp_resist

    def _analyze_momentum(self, indicators: Dict) -> Dict[str, Any]:
        """Analyze momentum indicators: RSI, MACD, KD."""
        momentum = {
            'rsi': {
                'value': None,
                'status': 'neutral',
                'signal': 'neutral'
            },
            'macd': {
                'macd_line': None,
                'signal_line': None,
                'histogram': None,
                'position': 'neutral',
                'crossover_signal': 'none',
                'signal': 'neutral'
            },
            'kd': {
                'k_value': None,
                'd_value': None,
                'status': 'neutral',
                'crossover': 'none',
                'signal': 'neutral'
            }
        }

        # RSI Analysis
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            momentum['rsi']['value'] = round(rsi, 2)

            if rsi > self.RSI_OVERBOUGHT:
                momentum['rsi']['status'] = 'overbought'
                momentum['rsi']['signal'] = 'bearish'
            elif rsi < self.RSI_OVERSOLD:
                momentum['rsi']['status'] = 'oversold'
                momentum['rsi']['signal'] = 'bullish'
            else:
                momentum['rsi']['status'] = 'neutral'
                momentum['rsi']['signal'] = 'neutral'

        # MACD Analysis
        if 'macd_line' in indicators and 'macd_signal' in indicators:
            macd = indicators['macd_line']
            signal = indicators['macd_signal']
            histogram = indicators.get('macd_histogram', macd - signal)

            momentum['macd']['macd_line'] = round(macd, 4)
            momentum['macd']['signal_line'] = round(signal, 4)
            momentum['macd']['histogram'] = round(histogram, 4)

            # Position relative to zero
            if macd > 0:
                momentum['macd']['position'] = 'above_zero'
            else:
                momentum['macd']['position'] = 'below_zero'

            # Crossover signal
            if histogram > self.MACD_HISTOGRAM_MIN_STRENGTH and macd > signal:
                momentum['macd']['crossover_signal'] = 'bullish'
                if momentum['macd']['position'] == 'above_zero':
                    momentum['macd']['signal'] = 'bullish'
            elif histogram < -self.MACD_HISTOGRAM_MIN_STRENGTH and macd < signal:
                momentum['macd']['crossover_signal'] = 'bearish'
                if momentum['macd']['position'] == 'below_zero':
                    momentum['macd']['signal'] = 'bearish'

        # KD Analysis
        if 'kd_k' in indicators and 'kd_d' in indicators:
            k = indicators['kd_k']
            d = indicators['kd_d']

            momentum['kd']['k_value'] = round(k, 2)
            momentum['kd']['d_value'] = round(d, 2)

            # Status
            if k > self.KD_OVERBOUGHT:
                momentum['kd']['status'] = 'overbought'
            elif k < self.KD_OVERSOLD:
                momentum['kd']['status'] = 'oversold'
            else:
                momentum['kd']['status'] = 'neutral'

            # Crossover signal
            if k > d:
                momentum['kd']['crossover'] = 'bullish'
                if k < self.KD_OVERBOUGHT:
                    momentum['kd']['signal'] = 'bullish'
            elif k < d:
                momentum['kd']['crossover'] = 'bearish'
                if k > self.KD_OVERSOLD:
                    momentum['kd']['signal'] = 'bearish'

        return momentum

    def _analyze_bollinger_bands(self, data: Dict, indicators: Dict) -> Dict[str, Any]:
        """Analyze Bollinger Bands."""
        bollinger = {
            'upper_band': None,
            'middle_band': None,
            'lower_band': None,
            'band_width': None,
            'band_width_pct': None,
            'price_position': 'between',
            'squeeze_status': 'normal',
            'signal': 'neutral'
        }

        if not all(k in indicators for k in ['bb_upper', 'bb_middle', 'bb_lower']):
            return bollinger

        upper = indicators['bb_upper']
        middle = indicators['bb_middle']
        lower = indicators['bb_lower']
        price = data.get('price', middle)

        bollinger['upper_band'] = round(upper, 2)
        bollinger['middle_band'] = round(middle, 2)
        bollinger['lower_band'] = round(lower, 2)

        # Band width
        band_width = upper - lower
        bollinger['band_width'] = round(band_width, 2)
        if middle > 0:
            band_width_pct = (band_width / middle) * 100
            bollinger['band_width_pct'] = round(band_width_pct, 2)

            # Squeeze detection
            if band_width_pct < self.BOLLINGER_BAND_WIDTH_THRESHOLD * 100:
                bollinger['squeeze_status'] = 'squeezed'
            elif band_width_pct > self.BOLLINGER_BAND_WIDTH_THRESHOLD * 100 * 2:
                bollinger['squeeze_status'] = 'expanded'
            else:
                bollinger['squeeze_status'] = 'normal'

        # Price position
        if price > upper:
            bollinger['price_position'] = 'above_upper'
            bollinger['signal'] = 'bearish'  # Overbought
        elif price < lower:
            bollinger['price_position'] = 'below_lower'
            bollinger['signal'] = 'bullish'  # Oversold
        else:
            bollinger['price_position'] = 'between'
            bollinger['signal'] = 'neutral'

        return bollinger

    def _analyze_volume(self, data: Dict, indicators: Dict) -> Dict[str, Any]:
        """Analyze volume trends."""
        volume_analysis = {
            'current_volume': data.get('volume'),
            'average_volume': data.get('volume_average'),
            'volume_ratio': None,
            'volume_trend': 'stable',
            'volume_confirmation': 'neutral',
            'obv': indicators.get('obv'),
            'obv_trend': 'neutral',
            'signal': 'neutral'
        }

        if data.get('volume') and data.get('volume_average'):
            ratio = data['volume'] / data['volume_average']
            volume_analysis['volume_ratio'] = round(ratio, 2)

            if ratio > 1.5:
                volume_analysis['volume_trend'] = 'increasing'
                volume_analysis['signal'] = 'bullish'  # High volume usually confirms moves
            elif ratio < 0.7:
                volume_analysis['volume_trend'] = 'decreasing'
                volume_analysis['signal'] = 'bearish'

        # OBV trend
        if 'obv' in indicators and 'obv_prev' in indicators:
            if indicators['obv'] > indicators['obv_prev']:
                volume_analysis['obv_trend'] = 'increasing'
            elif indicators['obv'] < indicators['obv_prev']:
                volume_analysis['obv_trend'] = 'decreasing'

        return volume_analysis

    def _generate_signals(self, trend: Dict, momentum: Dict, supp_resist: Dict,
                         bollinger: Dict, volume: Dict):
        """Generate trading signals from all indicators."""

        # MA-based signals
        if trend['current_trend'] == 'bullish' and trend['ma_alignment'] == 'bullish':
            self.signals.append({
                'type': 'ma_alignment',
                'signal': 'bullish',
                'strength': 'strong' if trend['trend_strength'] > 80 else 'moderate',
                'description': f"Strong bullish MA alignment: 20 > 50 > 200",
                'confidence': min(100, trend['trend_strength'] + 10)
            })
        elif trend['current_trend'] == 'bearish' and trend['ma_alignment'] == 'bearish':
            self.signals.append({
                'type': 'ma_alignment',
                'signal': 'bearish',
                'strength': 'strong' if trend['trend_strength'] > 80 else 'moderate',
                'description': f"Strong bearish MA alignment: 20 < 50 < 200",
                'confidence': min(100, trend['trend_strength'] + 10)
            })

        # RSI-based signals
        if momentum['rsi']['signal'] == 'bullish':
            if momentum['rsi']['status'] == 'oversold':
                self.signals.append({
                    'type': 'rsi_oversold',
                    'signal': 'bullish',
                    'strength': 'moderate',
                    'description': f"RSI {momentum['rsi']['value']} indicating oversold, potential bounce",
                    'confidence': 65
                })

        elif momentum['rsi']['signal'] == 'bearish':
            if momentum['rsi']['status'] == 'overbought':
                self.signals.append({
                    'type': 'rsi_overbought',
                    'signal': 'bearish',
                    'strength': 'moderate',
                    'description': f"RSI {momentum['rsi']['value']} indicating overbought, potential pullback",
                    'confidence': 65
                })

        # MACD-based signals
        if momentum['macd']['signal'] == 'bullish':
            self.signals.append({
                'type': 'macd_cross',
                'signal': 'bullish',
                'strength': 'moderate',
                'description': f"MACD bullish crossover, histogram positive",
                'confidence': 70
            })
        elif momentum['macd']['signal'] == 'bearish':
            self.signals.append({
                'type': 'macd_cross',
                'signal': 'bearish',
                'strength': 'moderate',
                'description': f"MACD bearish crossover, histogram negative",
                'confidence': 70
            })

        # KD-based signals
        if momentum['kd']['signal'] == 'bullish':
            self.signals.append({
                'type': 'kd_cross',
                'signal': 'bullish',
                'strength': 'moderate',
                'description': f"KD bullish crossover, K > D",
                'confidence': 65
            })
        elif momentum['kd']['signal'] == 'bearish':
            self.signals.append({
                'type': 'kd_cross',
                'signal': 'bearish',
                'strength': 'moderate',
                'description': f"KD bearish crossover, K < D",
                'confidence': 65
            })

        # Bollinger Band signals
        if bollinger['signal'] == 'bullish':
            self.signals.append({
                'type': 'bollinger_oversold',
                'signal': 'bullish',
                'strength': 'weak',
                'description': f"Price at lower Bollinger Band, potential mean reversion buy",
                'confidence': 50
            })
        elif bollinger['signal'] == 'bearish':
            self.signals.append({
                'type': 'bollinger_overbought',
                'signal': 'bearish',
                'strength': 'weak',
                'description': f"Price at upper Bollinger Band, potential mean reversion sell",
                'confidence': 50
            })

    def _calculate_price_targets(self, price: float, supp_resist: Dict, trend: Dict,
                                 momentum: Dict) -> Dict[str, Any]:
        """Calculate price targets."""
        targets = {
            'bullish_target_1': None,
            'bullish_target_2': None,
            'bearish_target_1': None,
            'bearish_target_2': None
        }

        if not price or price <= 0:
            return targets

        # Bullish targets
        if trend['current_trend'] == 'bullish':
            resistance_levels = supp_resist.get('key_resistance_levels', [])
            if resistance_levels:
                res_values = sorted([r['level'] for r in resistance_levels if r['level'] > price])
                if len(res_values) >= 1:
                    targets['bullish_target_1'] = {
                        'level': round(res_values[0], 2),
                        'basis': 'resistance_breakout',
                        'confidence': 70
                    }
                if len(res_values) >= 2:
                    targets['bullish_target_2'] = round(res_values[1], 2)

        # Bearish targets
        if trend['current_trend'] == 'bearish':
            support_levels = supp_resist.get('key_support_levels', [])
            if support_levels:
                sup_values = sorted([s['level'] for s in support_levels if s['level'] < price],
                                   reverse=True)
                if len(sup_values) >= 1:
                    targets['bearish_target_1'] = {
                        'level': round(sup_values[0], 2),
                        'basis': 'support_breakdown',
                        'confidence': 70
                    }
                if len(sup_values) >= 2:
                    targets['bearish_target_2'] = round(sup_values[1], 2)

        return targets

    def _calculate_risk_levels(self, price: float, supp_resist: Dict, trend: Dict) -> Dict[str, Any]:
        """Calculate risk and entry levels."""
        risk = {
            'stop_loss_for_long': None,
            'stop_loss_for_short': None,
            'optimal_entry_zone': 'Market dependent'
        }

        if not price or price <= 0:
            return risk

        support = supp_resist.get('immediate_support')
        resistance = supp_resist.get('immediate_resistance')

        if trend['current_trend'] == 'bullish':
            if support:
                risk['stop_loss_for_long'] = round(support * 0.98, 2)  # 2% below support
            else:
                risk['stop_loss_for_long'] = round(price * 0.95, 2)  # 5% below current

            risk['optimal_entry_zone'] = 'At or slightly below immediate support'

        elif trend['current_trend'] == 'bearish':
            if resistance:
                risk['stop_loss_for_short'] = round(resistance * 1.02, 2)  # 2% above resistance
            else:
                risk['stop_loss_for_short'] = round(price * 1.05, 2)  # 5% above current

            risk['optimal_entry_zone'] = 'At or slightly below immediate resistance'

        return risk

    def _calculate_confidence(self, trend: Dict, momentum: Dict, signals: List[Dict]) -> int:
        """Calculate overall analysis confidence."""
        confidence = 60  # Base

        # Trend strength affects confidence
        if trend['trend_strength'] > 80:
            confidence += 20
        elif trend['trend_strength'] > 60:
            confidence += 10

        # Number of confirming signals
        bullish_signals = sum(1 for s in signals if s['signal'] == 'bullish')
        bearish_signals = sum(1 for s in signals if s['signal'] == 'bearish')

        signal_count = max(bullish_signals, bearish_signals)
        confidence += min(signal_count * 5, 15)

        return min(100, confidence)

    def _generate_summary(self, ticker: str, price: float, trend: Dict, momentum: Dict,
                         supp_resist: Dict) -> str:
        """Generate executive summary."""
        summary_parts = []

        summary_parts.append(f"Technical Analysis for {ticker} (Price: ${price})")
        summary_parts.append("")

        # Trend summary
        summary_parts.append(f"Trend: {trend['current_trend'].upper()} ({trend['trend_strength']}/100)")
        summary_parts.append(f"MA Status: {trend['ma_alignment']}")
        summary_parts.append(f"Price Position: {trend['price_position_vs_ma']} moving averages")
        summary_parts.append("")

        # Support and resistance
        summary_parts.append("Key Levels:")
        if supp_resist.get('immediate_resistance'):
            summary_parts.append(f"  Resistance: ${supp_resist['immediate_resistance']:.2f}")
        if supp_resist.get('immediate_support'):
            summary_parts.append(f"  Support: ${supp_resist['immediate_support']:.2f}")
        summary_parts.append("")

        # Momentum
        if momentum['rsi']['value']:
            rsi_label = "OVERBOUGHT" if momentum['rsi']['status'] == 'overbought' else \
                       "OVERSOLD" if momentum['rsi']['status'] == 'oversold' else "NEUTRAL"
            summary_parts.append(f"RSI: {momentum['rsi']['value']} ({rsi_label})")

        if momentum['macd']['signal_line']:
            macd_status = "BULLISH" if momentum['macd']['signal'] == 'bullish' else \
                         "BEARISH" if momentum['macd']['signal'] == 'bearish' else "NEUTRAL"
            summary_parts.append(f"MACD: {macd_status}")

        if momentum['kd']['d_value']:
            kd_status = "BULLISH" if momentum['kd']['signal'] == 'bullish' else \
                       "BEARISH" if momentum['kd']['signal'] == 'bearish' else "NEUTRAL"
            summary_parts.append(f"KD: {kd_status}")

        return "\n".join(summary_parts)

    def _get_risk_disclaimer(self) -> str:
        """Get standard risk disclaimer."""
        return (
            "** IMPORTANT RISK DISCLAIMER ** "
            "Technical analysis is probabilistic, not predictive. This analysis provides "
            "educational insights only and does NOT constitute investment advice. Actual price "
            "movements depend on countless unpredictable factors including market sentiment, "
            "macroeconomic events, corporate announcements, and black swan events. Past patterns "
            "are not guarantees of future results. Only risk capital you can afford to lose. "
            "Consult a licensed financial advisor before making investment decisions."
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Perform technical analysis on validated stock data'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input validated data JSON file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output technical analysis JSON file'
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
    analyzer = TechnicalAnalyzer()
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
