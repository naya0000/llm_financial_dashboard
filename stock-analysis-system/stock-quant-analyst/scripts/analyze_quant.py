#!/usr/bin/env python3
"""
Stock Quantitative Analysis Script
Calculates key financial metrics for stocks: returns, volatility, Sharpe ratio, Sortino ratio, Beta, drawdown, scenario analysis.

Usage:
    python analyze_quant.py --input validated_data.json --output quant_analysis.json
"""

import json
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
import statistics
import logging

import numpy as np
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class QuantAnalyzer:
    """Performs quantitative analysis on stock price data."""

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize analyzer with risk-free rate (default 2% annual)."""
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = 252

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

    def extract_prices(self, data: Dict[str, Any]) -> Tuple[List[float], List[str]]:
        """Extract closing prices and dates from historical data."""
        try:
            # Support both direct and nested validated_data structure
            inner = data.get('validated_data', data)
            historical = inner.get('price_history', inner.get('historical_prices', []))
            if not historical:
                raise ValueError("No price_history or historical_prices found in data")

            prices = []
            dates = []
            for item in historical:
                if isinstance(item, dict):
                    price = item.get('close')
                    date = item.get('date')
                    if price is not None and date is not None:
                        try:
                            prices.append(float(price))
                            dates.append(str(date))
                        except (ValueError, TypeError):
                            continue

            if len(prices) < 2:
                raise ValueError("Insufficient valid price data (need at least 2 points)")

            return prices, dates
        except (KeyError, TypeError) as e:
            raise ValueError(f"Error extracting prices: {e}")

    def calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate daily log returns from prices."""
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = np.log(prices[i] / prices[i-1])
                returns.append(ret)
        return returns

    def calculate_annualized_return(self, prices: List[float], dates: List[str]) -> Tuple[float, int]:
        """Calculate annualized return from price series."""
        try:
            if len(prices) < 2:
                return None, 0

            start_price = prices[0]
            end_price = prices[-1]

            # Calculate holding period
            start_date = datetime.strptime(dates[0], '%Y-%m-%d')
            end_date = datetime.strptime(dates[-1], '%Y-%m-%d')
            days_held = (end_date - start_date).days

            if days_held <= 0:
                return None, 0

            # Total return
            total_return = (end_price - start_price) / start_price

            # Annualize
            years = days_held / 365.25
            annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

            return annualized * 100, days_held
        except (ValueError, IndexError) as e:
            return None, 0

    def calculate_volatility(self, prices: List[float]) -> Optional[float]:
        """Calculate annualized volatility from daily returns."""
        returns = self.calculate_returns(prices)
        if len(returns) < 2:
            return None

        std_dev = np.std(returns)
        annualized_vol = std_dev * np.sqrt(self.trading_days_per_year)
        return annualized_vol * 100

    def calculate_sharpe_ratio(self, prices: List[float]) -> Optional[float]:
        """Calculate Sharpe ratio (risk-free rate = 2% annual)."""
        returns = self.calculate_returns(prices)
        if len(returns) < self.trading_days_per_year:
            return None  # Need at least 1 year of data

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return None

        # Annualized excess return / annualized volatility
        excess_return = (mean_return * self.trading_days_per_year) - self.risk_free_rate
        annual_vol = std_return * np.sqrt(self.trading_days_per_year)

        sharpe = excess_return / annual_vol if annual_vol > 0 else None
        return sharpe

    def calculate_sortino_ratio(self, prices: List[float]) -> Optional[float]:
        """Calculate Sortino ratio (focuses on downside deviation)."""
        returns = self.calculate_returns(prices)
        if len(returns) < self.trading_days_per_year:
            return None  # Need at least 1 year of data

        mean_return = np.mean(returns)

        # Downside deviation: only negative returns
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return None

        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return None

        excess_return = (mean_return * self.trading_days_per_year) - self.risk_free_rate
        annual_downside = downside_std * np.sqrt(self.trading_days_per_year)

        sortino = excess_return / annual_downside if annual_downside > 0 else None
        return sortino

    def calculate_maximum_drawdown(self, prices: List[float], dates: List[str]) -> Dict[str, Any]:
        """Calculate maximum drawdown and recovery period."""
        if len(prices) < 2:
            return {'value': None, 'date_peak': None, 'date_trough': None, 'recovery_days': None}

        max_drawdown = 0
        best_peak_idx = 0
        best_trough_idx = 0

        # Running peak tracks the highest price seen so far and its index
        running_peak = prices[0]
        running_peak_idx = 0

        for i in range(1, len(prices)):
            if prices[i] > running_peak:
                running_peak = prices[i]
                running_peak_idx = i

            if running_peak > 0:
                current_drawdown = (running_peak - prices[i]) / running_peak
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    best_peak_idx = running_peak_idx
                    best_trough_idx = i

        # Calculate recovery: find when price returns to the peak level after the trough
        recovery_days = None
        peak_level = prices[best_peak_idx]
        if best_trough_idx < len(prices) - 1:
            for i in range(best_trough_idx + 1, len(prices)):
                if prices[i] >= peak_level:
                    try:
                        trough_date = datetime.strptime(dates[best_trough_idx], '%Y-%m-%d')
                        recovery_date = datetime.strptime(dates[i], '%Y-%m-%d')
                        recovery_days = (recovery_date - trough_date).days
                    except ValueError:
                        recovery_days = None
                    break

        return {
            'value': max_drawdown * 100,
            'date_peak': dates[best_peak_idx] if best_peak_idx < len(dates) else None,
            'date_trough': dates[best_trough_idx] if best_trough_idx < len(dates) else None,
            'recovery_days': recovery_days
        }

    def calculate_beta(self, prices: List[float], benchmark_prices: Optional[List[float]]) -> Dict[str, Any]:
        """Calculate Beta relative to benchmark."""
        if not benchmark_prices or len(benchmark_prices) < 2 or len(prices) < 2:
            return {
                'value': None,
                'benchmark': 'Not calculated',
                'interpretation': 'Insufficient benchmark data'
            }

        # Match lengths
        min_len = min(len(prices), len(benchmark_prices))
        prices = prices[-min_len:]
        benchmark_prices = benchmark_prices[-min_len:]

        stock_returns = self.calculate_returns(prices)
        benchmark_returns = self.calculate_returns(benchmark_prices)

        if len(stock_returns) < 2 or len(benchmark_returns) < 2:
            return {
                'value': None,
                'benchmark': 'Not calculated',
                'interpretation': 'Insufficient return data'
            }

        # Ensure same length
        min_ret_len = min(len(stock_returns), len(benchmark_returns))
        stock_returns = stock_returns[-min_ret_len:]
        benchmark_returns = benchmark_returns[-min_ret_len:]

        covariance = np.cov(stock_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)

        if benchmark_variance == 0:
            beta = None
        else:
            beta = covariance / benchmark_variance

        benchmark_name = 'Benchmark'
        interpretation = ''
        if beta is not None:
            if beta > 1.2:
                interpretation = f'Higher volatility than market ({beta:.2f}x)'
            elif beta > 0.8:
                interpretation = f'Similar volatility to market ({beta:.2f}x)'
            else:
                interpretation = f'Lower volatility than market ({beta:.2f}x)'

        return {
            'value': beta,
            'benchmark': benchmark_name,
            'interpretation': interpretation
        }

    def calculate_relative_strength(self, prices: List[float], dates: List[str],
                                     benchmark_prices: Optional[List[float]]) -> Dict[str, Any]:
        """Calculate relative strength vs benchmark."""
        if not benchmark_prices or len(prices) < 2 or len(benchmark_prices) < 2 or len(dates) < 2:
            return {
                'vs_benchmark': None,
                'outperformance': None,
                'note': 'Insufficient data or no benchmark available'
            }

        # Use actual dates for annualized return calculation
        min_len = min(len(prices), len(benchmark_prices), len(dates))
        stock_ret, _ = self.calculate_annualized_return(prices[-min_len:], dates[-min_len:])
        bench_ret, _ = self.calculate_annualized_return(benchmark_prices[-min_len:], dates[-min_len:])

        if stock_ret is None or bench_ret is None:
            return {
                'vs_benchmark': None,
                'outperformance': None,
                'note': 'Could not calculate annualized returns'
            }

        relative_strength = stock_ret - bench_ret
        outperformance = relative_strength > 0

        return {
            'vs_benchmark': round(relative_strength, 2),
            'outperformance': outperformance
        }

    def scenario_analysis(self, prices: List[float], volatility: Optional[float]) -> Dict[str, Any]:
        """Generate bull/base/bear scenario estimates."""
        if volatility is None or len(prices) < 2:
            return {
                'bull_case': {'estimated_return': None, 'basis': 'Insufficient data'},
                'base_case': {'estimated_return': None, 'basis': 'Insufficient data'},
                'bear_case': {'estimated_return': None, 'basis': 'Insufficient data'}
            }

        returns = self.calculate_returns(prices)
        historical_return = np.mean(returns) * self.trading_days_per_year * 100 if returns else 0
        volatility_decimal = volatility / 100

        return {
            'bull_case': {
                'estimated_return': historical_return + volatility,
                'basis': 'Historical average + 1 std dev'
            },
            'base_case': {
                'estimated_return': historical_return,
                'basis': 'Historical average return'
            },
            'bear_case': {
                'estimated_return': historical_return - volatility,
                'basis': 'Historical average - 1 std dev'
            }
        }

    def validate_data_quality(self, prices: List[float], dates: List[str]) -> Dict[str, Any]:
        """Validate data quality and completeness."""
        warnings = []

        if len(prices) < 252:
            warnings.append(f"Less than 1 year of data ({len(prices)} trading days)")

        if len(prices) < 2:
            warnings.append("Insufficient data points for analysis")

        # Check for data gaps
        if len(dates) >= 2:
            try:
                date_gaps = []
                for i in range(1, len(dates)):
                    d1 = datetime.strptime(dates[i-1], '%Y-%m-%d')
                    d2 = datetime.strptime(dates[i], '%Y-%m-%d')
                    gap = (d2 - d1).days
                    if gap > 10:  # More than 10 days
                        date_gaps.append(gap)

                if date_gaps:
                    warnings.append(f"Data gaps detected (max {max(date_gaps)} days)")
            except ValueError:
                warnings.append("Invalid date format in data")

        return {
            'min_data_points': len(prices) >= 252,
            'data_quality': (len(prices) / max(252, len(prices))) * 100 if prices else 0,
            'benchmark_available': False,  # To be set by caller
            'warnings': warnings
        }

    def calculate_confidence(self, prices: List[float], dates: List[str],
                           returns: Optional[List[float]] = None) -> Dict[str, Any]:
        """Calculate confidence scores for analysis."""
        data_completeness = min(1.0, len(prices) / 252)  # Perfect at 1 year

        # Time period adequacy
        if len(prices) >= 756:  # 3 years
            time_period_score = 1.0
        elif len(prices) >= 252:  # 1 year
            time_period_score = 0.75
        else:
            time_period_score = 0.5

        # Volatility stability (if we have enough returns)
        volatility_score = 0.7  # Default
        if returns and len(returns) >= 60:
            try:
                rolling_vols = []
                for i in range(30, len(returns), 10):
                    vol = np.std(returns[max(0, i-30):i])
                    rolling_vols.append(vol)

                if rolling_vols:
                    cv = np.std(rolling_vols) / np.mean(rolling_vols) if np.mean(rolling_vols) > 0 else 0
                    volatility_score = 1.0 - min(0.5, cv)  # Lower CV = higher score
            except:
                volatility_score = 0.7

        overall = (data_completeness * 0.4 + time_period_score * 0.35 + volatility_score * 0.25)

        if overall >= 0.8:
            recommendation = "Highly reliable"
        elif overall >= 0.6:
            recommendation = "Reliable"
        else:
            recommendation = "Use with caution"

        return {
            'overall': min(1.0, overall),
            'factors': {
                'data_completeness': data_completeness,
                'time_period_adequacy': time_period_score,
                'volatility_stability': volatility_score
            },
            'recommendation': recommendation
        }

    @staticmethod
    def _infer_benchmark(ticker: str) -> Optional[str]:
        """Infer the appropriate market benchmark for a given ticker."""
        t = ticker.upper()
        if t.endswith('.TW') or t.endswith('.TWO'):
            return '^TWII'       # TAIEX
        elif t.endswith('.T'):
            return '^N225'       # Nikkei 225
        elif t.endswith('.HK'):
            return '^HSI'        # Hang Seng
        elif t.endswith('.L'):
            return '^FTSE'       # FTSE 100
        else:
            return '^GSPC'       # S&P 500 (default for US stocks)

    @staticmethod
    def _fetch_benchmark_prices(benchmark_ticker: str, dates: List[str]) -> Optional[List[float]]:
        """Fetch benchmark closing prices aligned with the stock's date range."""
        try:
            import yfinance as yf
            if not dates or len(dates) < 2:
                return None

            start = datetime.strptime(dates[0], '%Y-%m-%d') - timedelta(days=5)
            end = datetime.strptime(dates[-1], '%Y-%m-%d') + timedelta(days=1)

            bench = yf.Ticker(benchmark_ticker)
            hist = bench.history(start=start, end=end)

            if hist.empty or len(hist) < 2:
                return None

            # Align to stock dates as closely as possible
            bench_prices = []
            bench_dates_idx = {d.strftime('%Y-%m-%d'): row['Close'] for d, row in hist.iterrows()}
            available_dates = sorted(bench_dates_idx.keys())

            for d in dates:
                if d in bench_dates_idx:
                    bench_prices.append(float(bench_dates_idx[d]))
                else:
                    # Use nearest previous available date
                    prev = [ad for ad in available_dates if ad <= d]
                    if prev:
                        bench_prices.append(float(bench_dates_idx[prev[-1]]))
                    elif bench_prices:
                        bench_prices.append(bench_prices[-1])

            return bench_prices if len(bench_prices) >= 2 else None

        except Exception as e:
            logger.warning(f"Failed to fetch benchmark {benchmark_ticker}: {e}")
            return None

    def analyze(self, input_path: str, output_path: str):
        """Main analysis workflow."""
        try:
            # Load data
            data = self.load_data(input_path)
            inner = data.get('validated_data', data)
            ticker = inner.get('metadata', {}).get('ticker', data.get('ticker', 'UNKNOWN'))

            # Extract prices
            prices, dates = self.extract_prices(data)
            returns = self.calculate_returns(prices)

            # Fetch benchmark for Beta calculation
            benchmark_ticker = self._infer_benchmark(ticker)
            benchmark_prices = None
            benchmark_name = 'N/A'
            if benchmark_ticker:
                logger.info(f"Fetching benchmark {benchmark_ticker} for Beta calculation...")
                benchmark_prices = self._fetch_benchmark_prices(benchmark_ticker, dates)
                if benchmark_prices:
                    benchmark_name = benchmark_ticker

            # Calculate metrics
            annualized_return, period_days = self.calculate_annualized_return(prices, dates)
            volatility = self.calculate_volatility(prices)
            sharpe = self.calculate_sharpe_ratio(prices)
            sortino = self.calculate_sortino_ratio(prices)
            beta = self.calculate_beta(prices, benchmark_prices)
            if beta.get('value') is not None:
                beta['benchmark'] = benchmark_name
            drawdown = self.calculate_maximum_drawdown(prices, dates)
            rel_strength = self.calculate_relative_strength(prices, dates, benchmark_prices)
            scenarios = self.scenario_analysis(prices, volatility)

            # Data quality and confidence
            data_quality = self.validate_data_quality(prices, dates)
            confidence = self.calculate_confidence(prices, dates, returns)

            # Sharpe/Sortino interpretation
            sharpe_interp = 'N/A'
            if sharpe is not None:
                if sharpe > 1:
                    sharpe_interp = 'High risk-adjusted return'
                elif sharpe > 0:
                    sharpe_interp = 'Moderate risk-adjusted return'
                else:
                    sharpe_interp = 'Low/negative risk-adjusted return'

            sortino_interp = 'N/A'
            if sortino is not None:
                if sortino > 1.5:
                    sortino_interp = 'Strong downside protection'
                elif sortino > 0.5:
                    sortino_interp = 'Moderate downside protection'
                else:
                    sortino_interp = 'Limited downside protection'

            # Build output
            output = {
                'ticker': ticker,
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'metrics': {
                    'annualized_return': {
                        'value': round(annualized_return, 2) if annualized_return else None,
                        'period_days': period_days
                    },
                    'annualized_volatility': {
                        'value': round(volatility, 2) if volatility else None,
                        'calculation_basis': 'daily log returns'
                    },
                    'sharpe_ratio': {
                        'value': round(sharpe, 3) if sharpe else None,
                        'risk_free_rate': '2% (annual)',
                        'interpretation': sharpe_interp
                    },
                    'sortino_ratio': {
                        'value': round(sortino, 3) if sortino else None,
                        'risk_free_rate': '2% (annual)',
                        'interpretation': sortino_interp
                    },
                    'beta': beta,
                    'maximum_drawdown': {
                        'value': round(drawdown['value'], 2) if drawdown['value'] else None,
                        'date_peak': drawdown['date_peak'],
                        'date_trough': drawdown['date_trough'],
                        'recovery_days': drawdown['recovery_days']
                    },
                    'relative_strength': rel_strength
                },
                'scenario_analysis': scenarios,
                'anti_hallucination_checks': data_quality,
                'confidence': confidence
            }

            # Save output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            print(f"Analysis complete. Results saved to {output_path}")
            return output

        except Exception as e:
            print(f"Error during analysis: {e}", file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Stock Quantitative Analysis Tool'
    )
    parser.add_argument('--input', required=True, help='Input JSON file with validated stock data')
    parser.add_argument('--output', required=True, help='Output JSON file for analysis results')
    parser.add_argument('--risk-free-rate', type=float, default=0.02,
                       help='Risk-free rate for Sharpe/Sortino calculation (default: 0.02 = 2%)')

    args = parser.parse_args()

    analyzer = QuantAnalyzer(risk_free_rate=args.risk_free_rate)
    analyzer.analyze(args.input, args.output)


if __name__ == '__main__':
    main()
