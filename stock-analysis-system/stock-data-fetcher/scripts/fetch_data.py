#!/usr/bin/env python3
"""
Stock Data Fetcher for Multi-Agent Stock Analysis System
Fetches comprehensive financial data from Yahoo Finance API using yfinance library.

Supports Taiwan Stock Exchange (e.g., 2330.TW) and US Stock Exchange (e.g., AAPL).
Calculates technical indicators (RSI, MACD, Bollinger Bands, KD Stochastic) from raw OHLCV data.
Outputs a comprehensive JSON data package with all financial data, price history, and technical indicators.

Usage:
    python fetch_data.py 2330.TW --output /path/to/output.json
    python fetch_data.py AAPL --output ./data/aapl_data.json --verbose
"""

import argparse
import json
import logging
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from pandas import DataFrame


# Configure logging
def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class StockDataFetcher:
    """Fetches and processes comprehensive stock data from Yahoo Finance."""

    def __init__(self, ticker: str, verbose: bool = False):
        """
        Initialize the fetcher.

        Args:
            ticker: Stock ticker symbol (e.g., "2330.TW", "AAPL")
            verbose: Enable verbose logging
        """
        self.ticker = ticker
        self.verbose = verbose
        self.logger = setup_logging(verbose)
        self.data = {
            "metadata": {
                "ticker": ticker,
                "fetch_timestamp": None,
                "data_freshness": None,
                "missing_data": [],
                "api_status": "pending"
            },
            "company_info": {},
            "price_history": [],
            "technical_indicators": {},
            "financial_statements": {
                "income_statement": {},
                "balance_sheet": {},
                "cash_flow": {}
            },
            "holders": {},
            "analyst_data": {},
            "twse_data": {
                "institutional_trading": {},
                "margin_trading": {}
            }
        }
        self.yf_ticker = None
        self.price_df = None

    def fetch(self) -> Dict[str, Any]:
        """
        Fetch all stock data using parallel API calls for maximum speed.

        Returns:
            Dictionary containing all fetched stock data
        """
        try:
            self.logger.info(f"Starting data fetch for ticker: {self.ticker}")
            self.data["metadata"]["fetch_timestamp"] = datetime.utcnow().isoformat() + "Z"

            # Initialize yfinance ticker object (must be done first — shared by all fetchers)
            self._init_yfinance_ticker()

            # Phase 1: Parallel fetch — all independent API calls run concurrently
            # price_history must complete before technical_indicators, so it's in phase 1
            # and technical_indicators is calculated in phase 2.
            parallel_tasks = {
                "company_info": self._fetch_company_info,
                "price_history": self._fetch_price_history,
                "financial_statements": self._fetch_financial_statements,
                "holders": self._fetch_holders,
                "analyst_data": self._fetch_analyst_data,
            }

            # Add TWSE tasks for Taiwan stocks
            is_taiwan = self.ticker.endswith('.TW') or self.ticker.endswith('.TWO')
            if is_taiwan:
                parallel_tasks["twse_institutional"] = self._fetch_twse_institutional
                parallel_tasks["twse_margin"] = self._fetch_twse_margin

            with ThreadPoolExecutor(max_workers=len(parallel_tasks)) as executor:
                futures = {
                    executor.submit(fn): name
                    for name, fn in parallel_tasks.items()
                }
                for future in as_completed(futures):
                    task_name = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        self.logger.warning(f"Parallel task '{task_name}' failed: {e}")

            # Phase 2: Calculate technical indicators (depends on price_history from phase 1)
            self._calculate_technical_indicators()

            self.data["metadata"]["api_status"] = "success"
            self.logger.info(f"Successfully fetched data for {self.ticker}")

        except Exception as e:
            self.logger.error(f"Error during data fetch: {str(e)}")
            self.data["metadata"]["api_status"] = f"error: {str(e)}"
            self.data["metadata"]["missing_data"].append("all_data_due_to_error")

        return self.data

    def _init_yfinance_ticker(self) -> None:
        """Initialize yfinance ticker object (lightweight — no API call)."""
        self.yf_ticker = yf.Ticker(self.ticker)
        self.logger.debug(f"Yfinance ticker initialized: {self.ticker}")

    def _fetch_company_info(self) -> None:
        """Fetch company information."""
        try:
            self.logger.debug("Fetching company information...")
            info = self.yf_ticker.info

            company_info = {
                "name": info.get("longName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": _serialize_value(info.get("marketCap")),
                "pe_ratio": _serialize_value(info.get("trailingPE")),
                "forward_pe": _serialize_value(info.get("forwardPE")),
                "peg_ratio": _serialize_value(info.get("pegRatio")),
                "pb_ratio": _serialize_value(info.get("priceToBook")),
                "eps": _serialize_value(info.get("trailingEps")),
                "dividend_yield": _serialize_value(info.get("dividendYield")),
                "dividend_rate": _serialize_value(info.get("dividendRate")),
                "trailing_12_month_revenue": _serialize_value(info.get("totalRevenue")),
                "profit_margin": _serialize_value(info.get("profitMargins")),
                "operating_margin": _serialize_value(info.get("operatingMargins")),
                "return_on_equity": _serialize_value(info.get("returnOnEquity")),
                "return_on_assets": _serialize_value(info.get("returnOnAssets")),
                "debt_to_equity": _serialize_value(info.get("debtToEquity")),
                "current_ratio": _serialize_value(info.get("currentRatio")),
                "quick_ratio": _serialize_value(info.get("quickRatio")),
                "five_year_avg_dividend_yield": _serialize_value(info.get("fiveYearAvgDividendYield")),
                "52_week_high": _serialize_value(info.get("fiftyTwoWeekHigh")),
                "52_week_low": _serialize_value(info.get("fiftyTwoWeekLow")),
                "50_day_average": _serialize_value(info.get("fiftyDayAverage")),
                "200_day_average": _serialize_value(info.get("twoHundredDayAverage")),
                "beta": _serialize_value(info.get("beta")),
                "website": info.get("website", ""),
                "description": info.get("longBusinessSummary", "")[:500],  # Truncate for brevity
                "currency": info.get("currency", ""),
                "exchange": info.get("exchange", ""),
                "current_price": _serialize_value(info.get("currentPrice") or info.get("regularMarketPrice")),
                "previous_close": _serialize_value(info.get("previousClose") or info.get("regularMarketPreviousClose")),
                "average_volume": _serialize_value(info.get("averageVolume")),
                "average_volume_10d": _serialize_value(info.get("averageDailyVolume10Day")),
            }

            self.data["company_info"] = company_info
            self.logger.debug("Company information fetched successfully")

        except Exception as e:
            self.logger.warning(f"Failed to fetch company info: {str(e)}")
            self.data["metadata"]["missing_data"].append("company_info")

    def _fetch_price_history(self) -> None:
        """Fetch historical price data (2 years to ensure sufficient data for all indicators)."""
        try:
            self.logger.debug("Fetching price history (2 years)...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)

            self.price_df = self.yf_ticker.history(start=start_date, end=end_date)

            if self.price_df.empty:
                raise ValueError("No price data retrieved")

            # Add moving averages (require full window to avoid misleading partial MAs)
            for window in (5, 10, 20, 60, 120, 240):
                self.price_df[f'MA_{window}'] = self.price_df['Close'].rolling(
                    window=window, min_periods=window
                ).mean()

            # Convert to serializable format (round prices to 2 decimals, strip null MAs)
            price_history = []
            for date, row in self.price_df.iterrows():
                price_record = {
                    "date": date.strftime("%Y-%m-%d"),
                    "open": _round2(row['Open']),
                    "high": _round2(row['High']),
                    "low": _round2(row['Low']),
                    "close": _round2(row['Close']),
                    "volume": int(row['Volume']) if pd.notna(row['Volume']) else None,
                }
                # Only include MAs that have computed values (skip early nulls)
                for window in (5, 10, 20, 60, 120, 240):
                    val = row[f'MA_{window}']
                    if pd.notna(val):
                        price_record[f'ma_{window}'] = round(float(val), 2)
                price_history.append(price_record)

            self.data["price_history"] = price_history
            self.logger.debug(f"Price history fetched: {len(price_history)} records")

        except Exception as e:
            self.logger.warning(f"Failed to fetch price history: {str(e)}")
            self.data["metadata"]["missing_data"].append("price_history")

    def _calculate_technical_indicators(self) -> None:
        """Calculate technical indicators from price data."""
        if self.price_df is None or self.price_df.empty:
            self.logger.warning("Cannot calculate technical indicators: no price data")
            return

        try:
            self.logger.debug("Calculating technical indicators...")

            # RSI (14-period)
            rsi = self._calculate_rsi(self.price_df['Close'], period=14)

            # MACD (12/26/9)
            macd, macd_signal, macd_hist = self._calculate_macd(self.price_df['Close'])

            # Bollinger Bands (20-period, 2 std dev)
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
                self.price_df['Close'], period=20, std_dev=2
            )

            # Stochastic KD (9-period)
            k_percent, d_percent = self._calculate_stochastic(
                self.price_df['High'], self.price_df['Low'], self.price_df['Close'], period=9
            )

            # Get latest values
            latest_idx = -1
            indicators = {
                "rsi_14": {
                    "value": _serialize_value(rsi.iloc[latest_idx]),
                    "period": 14,
                    "interpretation": _interpret_rsi(rsi.iloc[latest_idx])
                },
                "macd": {
                    "macd": _serialize_value(macd.iloc[latest_idx]),
                    "signal": _serialize_value(macd_signal.iloc[latest_idx]),
                    "histogram": _serialize_value(macd_hist.iloc[latest_idx]),
                    "periods": "12/26/9"
                },
                "bollinger_bands": {
                    "upper": _serialize_value(bb_upper.iloc[latest_idx]),
                    "middle": _serialize_value(bb_middle.iloc[latest_idx]),
                    "lower": _serialize_value(bb_lower.iloc[latest_idx]),
                    "period": 20,
                    "std_dev": 2
                },
                "stochastic_kd": {
                    "k_percent": _serialize_value(k_percent.iloc[latest_idx]),
                    "d_percent": _serialize_value(d_percent.iloc[latest_idx]),
                    "period": 9,
                    "interpretation": _interpret_stochastic(k_percent.iloc[latest_idx], d_percent.iloc[latest_idx])
                }
            }

            self.data["technical_indicators"] = indicators
            self.logger.debug("Technical indicators calculated successfully")

        except Exception as e:
            self.logger.warning(f"Failed to calculate technical indicators: {str(e)}")
            self.data["metadata"]["missing_data"].append("technical_indicators")

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index using Wilder's smoothing (EMA)."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # Wilder's smoothing = EMA with alpha=1/period
        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist

    @staticmethod
    def _calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = prices.rolling(window=period, min_periods=period).mean()
        std = prices.rolling(window=period, min_periods=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    @staticmethod
    def _calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic %K and %D."""
        low_min = low.rolling(window=period, min_periods=period).min()
        high_max = high.rolling(window=period, min_periods=period).max()

        k_percent = 100 * ((close - low_min) / (high_max - low_min).replace(0, np.nan))
        d_percent = k_percent.rolling(window=3, min_periods=3).mean()

        return k_percent, d_percent

    def _fetch_financial_statements(self) -> None:
        """Fetch income statement, balance sheet, and cash flow statements."""
        try:
            self.logger.debug("Fetching financial statements...")

            financials = {
                "income_statement": self._process_financials(self.yf_ticker.quarterly_financials, "income_statement"),
                "balance_sheet": self._process_financials(self.yf_ticker.quarterly_balance_sheet, "balance_sheet"),
                "cash_flow": self._process_financials(self.yf_ticker.quarterly_cashflow, "cash_flow")
            }

            self.data["financial_statements"] = financials
            self.logger.debug("Financial statements fetched successfully")

        except Exception as e:
            self.logger.warning(f"Failed to fetch financial statements: {str(e)}")
            self.data["metadata"]["missing_data"].append("financial_statements")

    # Key fields per statement type — keeps JSON compact (~5KB vs ~21KB)
    _KEEP_FIELDS = {
        "income_statement": {
            "Total Revenue", "Gross Profit", "Operating Income", "Net Income",
            "Basic EPS", "Diluted EPS", "EBITDA", "Operating Revenue",
            "Cost Of Revenue", "Operating Expense",
        },
        "balance_sheet": {
            "Total Assets", "Total Liabilities Net Minority Interest",
            "Stockholders Equity", "Current Assets", "Current Liabilities",
            "Total Debt", "Cash And Cash Equivalents",
        },
        "cash_flow": {
            "Operating Cash Flow", "Free Cash Flow", "Capital Expenditure",
            "Financing Cash Flow", "Investing Cash Flow",
        },
    }

    @classmethod
    def _process_financials(cls, financial_df: DataFrame, statement_type: str) -> Dict[str, Any]:
        """Process financial statement dataframes, keeping only key fields."""
        if financial_df is None or financial_df.empty:
            return {}

        keep = cls._KEEP_FIELDS.get(statement_type)
        result = {}
        try:
            cols = financial_df.columns[:4] if len(financial_df.columns) >= 4 else financial_df.columns
            for date in cols:
                date_str = date.strftime("%Y-%m-%d")
                result[date_str] = {}
                for index, value in financial_df[date].items():
                    field_name = str(index)
                    if keep and field_name not in keep:
                        continue
                    result[date_str][field_name] = _serialize_value(value)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error processing {statement_type}: {str(e)}")

        return result

    def _fetch_twse_institutional(self) -> None:
        """Fetch TWSE institutional trading data (三大法人買賣超) for Taiwan stocks."""
        try:
            self.logger.debug("Fetching TWSE institutional trading data...")
            stock_no = self.ticker.replace('.TW', '').replace('.TWO', '')

            results = []
            for target_date in _recent_trading_days(max_days=5):
                date_str = target_date.strftime('%Y%m%d')
                url = (
                    f"https://www.twse.com.tw/rwd/zh/fund/T86"
                    f"?date={date_str}&selectType=ALLBUT0999&response=json"
                )
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json',
                    })
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode('utf-8'))

                    if data.get('stat') == 'OK' and data.get('data'):
                        for row in data['data']:
                            if row[0].strip() == stock_no:
                                results.append({
                                    "date": target_date.strftime('%Y-%m-%d'),
                                    "foreign_buy_sell": _safe_int(row[4]),
                                    "investment_trust_buy_sell": _safe_int(row[10]),
                                    "dealer_buy_sell": _safe_int(row[11]),
                                    "total_institutional_buy_sell": _safe_int(row[18]) if len(row) > 18 else None,
                                })
                                break
                    if results:
                        break
                    time.sleep(0.15)
                except Exception as e:
                    self.logger.debug(f"TWSE fetch for {date_str}: {e}")
                    continue

            if results:
                self.data["twse_data"]["institutional_trading"] = results
                self.logger.debug(f"TWSE institutional data fetched: {len(results)} days")
            else:
                self.data["metadata"]["missing_data"].append("twse_institutional")
                self.logger.debug("No TWSE institutional data found")

        except Exception as e:
            self.logger.warning(f"Failed to fetch TWSE institutional data: {e}")
            self.data["metadata"]["missing_data"].append("twse_institutional")

    def _fetch_twse_margin(self) -> None:
        """Fetch TWSE margin trading data (融資融券) for Taiwan stocks."""
        try:
            self.logger.debug("Fetching TWSE margin trading data...")
            stock_no = self.ticker.replace('.TW', '').replace('.TWO', '')

            for target_date in _recent_trading_days(max_days=5):
                date_str = target_date.strftime('%Y%m%d')
                url = (
                    f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
                    f"?date={date_str}&selectType=ALL&response=json"
                )
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json',
                    })
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode('utf-8'))

                    if data.get('stat') == 'OK' and data.get('tables'):
                        table = data['tables'][1] if len(data['tables']) > 1 else data['tables'][0]
                        rows = table.get('data', [])
                        for row in rows:
                            if row[0].strip() == stock_no:
                                self.data["twse_data"]["margin_trading"] = {
                                    "date": target_date.strftime('%Y-%m-%d'),
                                    "margin_buy": _safe_int(row[1]),
                                    "margin_sell": _safe_int(row[2]),
                                    "margin_balance": _safe_int(row[4]),
                                    "short_sell": _safe_int(row[6]),
                                    "short_cover": _safe_int(row[7]),
                                    "short_balance": _safe_int(row[9]),
                                }
                                self.logger.debug(f"TWSE margin data fetched for {date_str}")
                                return
                    time.sleep(0.15)
                except Exception as e:
                    self.logger.debug(f"TWSE margin fetch for {date_str}: {e}")
                    continue

            self.data["metadata"]["missing_data"].append("twse_margin")
            self.logger.debug("No TWSE margin data found")

        except Exception as e:
            self.logger.warning(f"Failed to fetch TWSE margin data: {e}")
            self.data["metadata"]["missing_data"].append("twse_margin")

    def _fetch_holders(self) -> None:
        """Fetch major shareholders information."""
        try:
            self.logger.debug("Fetching holders information...")

            holders_info = {}

            # Major holders
            try:
                major_holders = self.yf_ticker.major_holders
                if major_holders is not None and not major_holders.empty:
                    major_holders_list = []
                    for _, row in major_holders.iterrows():
                        major_holders_list.append({
                            "holder": row.get(0, ""),
                            "percentage": str(row.get(1, ""))
                        })
                    holders_info["major_holders"] = major_holders_list
            except Exception as e:
                self.logger.debug(f"Major holders fetch: {str(e)}")

            # Institutional holders
            try:
                inst_holders = self.yf_ticker.institutional_holders
                if inst_holders is not None and not inst_holders.empty:
                    inst_list = []
                    for _, row in inst_holders.iterrows():
                        inst_list.append({
                            "holder": row.get("Holder", ""),
                            "shares": _serialize_value(row.get("Shares", 0)),
                            "date_reported": str(row.get("Date Reported", ""))
                        })
                    holders_info["institutional_holders"] = inst_list[:10]  # Top 10
            except Exception as e:
                self.logger.debug(f"Institutional holders fetch: {str(e)}")

            self.data["holders"] = holders_info
            self.logger.debug("Holders information fetched")

        except Exception as e:
            self.logger.warning(f"Failed to fetch holders: {str(e)}")
            self.data["metadata"]["missing_data"].append("holders")

    def _fetch_analyst_data(self) -> None:
        """Fetch analyst recommendations and price targets."""
        try:
            self.logger.debug("Fetching analyst data...")

            analyst_info = {}

            # Recommendations
            try:
                recommendations = self.yf_ticker.recommendations
                if recommendations is not None and not recommendations.empty:
                    recent_rec = recommendations.tail(1)
                    if not recent_rec.empty:
                        rec_row = recent_rec.iloc[0]
                        analyst_info["recent_recommendation"] = {
                            "strong_buy": int(rec_row.get("strongBuy", 0)),
                            "buy": int(rec_row.get("buy", 0)),
                            "hold": int(rec_row.get("hold", 0)),
                            "sell": int(rec_row.get("sell", 0)),
                            "strong_sell": int(rec_row.get("strongSell", 0)),
                            "date": str(recent_rec.index[0])
                        }
            except Exception as e:
                self.logger.debug(f"Recommendations fetch: {str(e)}")

            # Target price
            try:
                target_price = self.yf_ticker.info.get("targetMeanPrice")
                if target_price:
                    analyst_info["target_mean_price"] = _serialize_value(target_price)
            except Exception as e:
                self.logger.debug(f"Target price fetch: {str(e)}")

            self.data["analyst_data"] = analyst_info
            self.logger.debug("Analyst data fetched")

        except Exception as e:
            self.logger.warning(f"Failed to fetch analyst data: {str(e)}")
            self.data["metadata"]["missing_data"].append("analyst_data")

    def save_to_json(self, output_path: str) -> None:
        """
        Save fetched data to JSON file.

        Args:
            output_path: Path to save the JSON file
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Data saved to: {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to save data to JSON: {str(e)}")
            raise


def _recent_trading_days(max_days: int = 5):
    """Yield recent dates, skipping weekends (Sat/Sun)."""
    d = datetime.now()
    yielded = 0
    while yielded < max_days:
        if d.weekday() < 5:  # Mon-Fri
            yield d
            yielded += 1
        d -= timedelta(days=1)


def _safe_int(value: Any) -> Optional[int]:
    """Parse TWSE numeric strings (may contain commas) to int."""
    if value is None:
        return None
    try:
        return int(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        return None


def _round2(value: Any) -> Any:
    """Round numeric value to 2 decimal places for compact JSON output."""
    if value is None:
        return None
    if pd.isna(value):
        return None
    return round(float(value), 2)


def _serialize_value(value: Any) -> Any:
    """Convert pandas/numpy types to JSON-serializable Python types."""
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)


def _interpret_rsi(rsi_value: float) -> str:
    """Interpret RSI value."""
    if pd.isna(rsi_value):
        return "insufficient data"
    if rsi_value >= 70:
        return "overbought"
    elif rsi_value <= 30:
        return "oversold"
    else:
        return "neutral"


def _interpret_stochastic(k_value: float, d_value: float) -> str:
    """Interpret Stochastic KD values."""
    if pd.isna(k_value) or pd.isna(d_value):
        return "insufficient data"
    if k_value >= 80 or d_value >= 80:
        return "overbought"
    elif k_value <= 20 or d_value <= 20:
        return "oversold"
    elif k_value > d_value:
        return "uptrend"
    else:
        return "downtrend"


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Fetch comprehensive stock data from Yahoo Finance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fetch_data.py 2330.TW --output ./data/tsmc.json
  python fetch_data.py AAPL --output ./data/aapl.json --verbose
  python fetch_data.py NVDA
        """
    )

    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g., 2330.TW for TSMC, AAPL for Apple)"
    )

    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: ./stock_data_{ticker}.json)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    logger_main = setup_logging(args.verbose)

    try:
        # Validate ticker format
        ticker = args.ticker.upper()
        logger_main.info(f"Processing ticker: {ticker}")

        # Fetch data
        fetcher = StockDataFetcher(ticker, verbose=args.verbose)
        fetcher.fetch()

        # Determine output path
        output_path = args.output or f"./stock_data_{ticker}.json"

        # Save to JSON
        fetcher.save_to_json(output_path)

        logger_main.info(f"Successfully completed data fetch for {ticker}")
        print(json.dumps({"status": "success", "ticker": ticker, "output": output_path}, indent=2))

        sys.exit(0)

    except Exception as e:
        logger_main.error(f"Fatal error: {str(e)}", exc_info=True)
        print(json.dumps({"status": "error", "message": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
