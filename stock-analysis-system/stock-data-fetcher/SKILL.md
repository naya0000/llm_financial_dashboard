---
name: stock-data-fetcher
description: 個股資料抓取 Agent。從 Yahoo Finance 等公開 API 並行抓取財務報表、即時股價、技術指標、新聞等原始資料。當使用者需要分析個股、抓取股票資料、查詢財務數據時觸發。支援台股（如 2330.TW）與美股（如 AAPL, NVDA）。
---

## Purpose

This skill acts as a data fetcher for the multi-agent stock analysis system. It retrieves comprehensive financial data from Yahoo Finance API using the `yfinance` library, preparing raw data for downstream analysis agents (sentiment analysis, technical analysis, fundamental analysis, etc.).

When users need to analyze individual stocks, fetch stock data, or query financial metrics, this skill is triggered to gather the initial dataset.

## Supported Data Types

The skill fetches and processes the following data categories:

1. **Company Information**
   - Company name, sector, industry, market cap
   - P/E ratio, P/B ratio, EPS, dividend yield
   - 52-week high/low, trailing PE, forward PE, PEG ratio
   - Business summary and website

2. **Financial Statements** (Quarterly & Annual)
   - Income statement: revenue, operating income, net income, EPS
   - Balance sheet: total assets, liabilities, equity, cash, inventory
   - Cash flow statement: operating cash flow, free cash flow, capital expenditure

3. **Price History & Technical Data**
   - Daily OHLCV (Open, High, Low, Close, Volume) for past 1 year
   - Moving averages: 5, 10, 20, 60, 120, 240-day SMA
   - Technical indicators:
     - RSI (14-period): Relative Strength Index
     - MACD (12/26/9): Moving Average Convergence Divergence
     - Bollinger Bands (20-period, 2 std dev): Upper, middle, lower bands
     - KD Stochastic (9-period): Fast %K and %D lines

4. **News & Social Sentiment**
   - Recent news headlines (last 30 days)
   - News timestamps and sources

5. **Holdings & Analyst Data**
   - Major shareholders information
   - Analyst recommendations and price targets
   - Insider trading activity

6. **Market Metadata**
   - Data fetch timestamp and freshness indicators
   - Data quality metrics (missing data count, API response status)

## Supported Markets

- Taiwan Stock Exchange: Tickers like `2330.TW` (TSMC), `2454.TW` (MediaTek)
- US Stock Exchange: Tickers like `AAPL`, `NVDA`, `MSFT`, etc.
- Extensible to other international markets supported by Yahoo Finance

## Output Format

The skill outputs a comprehensive JSON data package containing:

```json
{
  "metadata": {
    "ticker": "2330.TW",
    "fetch_timestamp": "2026-04-03T10:30:00Z",
    "data_freshness": "same-day",
    "missing_data": [],
    "api_status": "success"
  },
  "company_info": { ... },
  "price_history": [ ... ],
  "technical_indicators": { ... },
  "financial_statements": { ... },
  "news": [ ... ],
  "holders": { ... },
  "analyst_data": { ... }
}
```

The output file is saved to a specified path and can be consumed by downstream analysis agents.

## Error Handling Strategy

The skill implements robust error handling:

1. **Timeout Handling**: If a data source takes too long (>10s per source), it's skipped with a warning logged
2. **Retry Logic**: Failed API calls are retried up to 3 times with exponential backoff
3. **Fallback Strategy**: If a data source fails, the skill continues fetching other data types instead of aborting
4. **Graceful Degradation**: Partial data is better than no data; the JSON output includes a `missing_data` field listing what couldn't be fetched
5. **Data Validation**: All timestamps and NaN values are converted to JSON-serializable formats

## Usage

```bash
python {{SKILLS_DIR}}/stock-data-fetcher/scripts/fetch_data.py 2330.TW --output {{OUTPUT_DIR}}/tsmc/raw_data.json
python {{SKILLS_DIR}}/stock-data-fetcher/scripts/fetch_data.py AAPL --output {{OUTPUT_DIR}}/aapl/raw_data.json --verbose
```

### Command-line Arguments

- `ticker`: Stock ticker symbol (required, e.g., "2330.TW", "AAPL")
- `--output`: Output JSON file path (default: `./stock_data_{ticker}.json`)
- `--verbose`: Enable verbose logging (optional)

## Dependencies

- `yfinance>=0.2.0`: Yahoo Finance data fetcher
- `pandas>=1.5.0`: Data manipulation and time series analysis
- `numpy>=1.23.0`: Numerical computing for indicator calculations
- `requests>=2.28.0`: HTTP library for resilience

## Implementation Details

The Python script (`scripts/fetch_data.py`) implements all technical indicator calculations manually using pandas/numpy:

- **RSI (Relative Strength Index)**: 14-period momentum indicator using gains/losses
- **MACD**: 12/26/9 exponential moving average convergence/divergence
- **Bollinger Bands**: 20-day SMA with 2 standard deviations
- **Stochastic KD**: 9-period %K (fast) and %D (slow, 3-period SMA) calculation

No external technical analysis libraries (TA-Lib, etc.) are used; all indicators are computed from raw OHLCV data.

## Monitoring & Logging

The skill logs:
- Each API call and response time
- Any data quality issues or missing fields
- Retry attempts and backoff timing
- Final data summary (number of records, date ranges, completeness)

## Integration with Multi-Agent System

This skill is designed to be called by:
- **Technical Analysis Agent**: Uses price history and technical indicators
- **Fundamental Analysis Agent**: Uses financial statements and company info
- **Sentiment Analysis Agent**: Uses news headlines for context
- **Portfolio Agent**: Aggregates data for multiple stocks

The JSON output from this skill serves as the canonical data source for all downstream agents, ensuring consistency and reducing redundant API calls.
