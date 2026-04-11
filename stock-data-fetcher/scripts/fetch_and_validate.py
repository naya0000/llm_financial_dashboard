#!/usr/bin/env python3
"""
Combined Stock Data Fetcher + Validator
Eliminates one Python cold-start and one JSON serialization round-trip
by running fetch → validate in a single process.

Usage:
    python fetch_and_validate.py 2330.TW --output /path/to/validated_data.json
    python fetch_and_validate.py AAPL --output ./data/aapl.json --raw-output ./data/aapl_raw.json
"""

import argparse
import json
import sys
from pathlib import Path

# Import from sibling packages (resolve paths)
SCRIPTS_DIR = Path(__file__).resolve().parent
FETCHER_DIR = SCRIPTS_DIR
VALIDATOR_DIR = SCRIPTS_DIR.parent.parent / "stock-data-validator" / "scripts"

sys.path.insert(0, str(FETCHER_DIR))
sys.path.insert(0, str(VALIDATOR_DIR))

from fetch_data import StockDataFetcher, setup_logging
from validate_data import StockDataValidator, _detect_market


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and validate stock data in a single process"
    )
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., 2330.TW, AAPL)")
    parser.add_argument("--output", "-o", required=True,
                        help="Output path for validated_data.json")
    parser.add_argument("--raw-output", default=None,
                        help="Optional: also save raw_data.json (for debugging)")
    parser.add_argument("--config", default=None,
                        help="Optional JSON config file with validation threshold overrides")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logger = setup_logging(args.verbose)
    ticker = args.ticker.upper()

    # --- Phase 1: Fetch (with parallel API calls) ---
    logger.info(f"[1/2] Fetching data for {ticker}...")
    fetcher = StockDataFetcher(ticker, verbose=args.verbose)
    raw_data = fetcher.fetch()

    # Optionally save raw data
    if args.raw_output:
        raw_path = Path(args.raw_output)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Raw data saved to: {raw_path}")

    # --- Phase 2: Validate (in-memory, no re-parsing) ---
    logger.info(f"[2/2] Validating data for {ticker}...")
    market = _detect_market(ticker)

    custom_thresholds = None
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                custom_thresholds = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load config: {e}")

    validator = StockDataValidator(thresholds=custom_thresholds, market=market)
    validated_package = validator.validate_data(raw_data)

    # --- Output ---
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(validated_package, f, indent=2, ensure_ascii=False)

    overall = validated_package["overall_confidence"]
    tier = validated_package["validation_tier"]
    tier_label = {"passed": "PASSED", "warning": "WARNING", "hard_stop": "HARD STOP"}

    print(f"=== {ticker}: Confidence {overall}/100 — {tier_label.get(tier, tier)} ===")
    print(json.dumps({
        "status": "success",
        "ticker": ticker,
        "overall_confidence": overall,
        "validation_tier": tier,
        "output": str(output_path),
    }, indent=2))

    if tier == "hard_stop":
        sys.exit(2)  # Exit code 2 = hard stop (distinct from error=1)

    sys.exit(0)


if __name__ == "__main__":
    main()
