#!/usr/bin/env python3
"""
Stock Data Validator Script
Validates raw stock data from fetch_data.py against quality thresholds
and assigns confidence scores.

Expects the NESTED structure output by fetch_data.py:
  metadata, company_info, price_history[], technical_indicators,
  financial_statements, news[], holders, analyst_data
"""

import json
import argparse
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import sys


class StockDataValidator:
    """Validates stock data and assigns confidence scores."""

    # --- Default validation thresholds ---
    DEFAULT_THRESHOLDS = {
        "price_freshness_days": 3,          # Daily data; 3 calendar days covers weekends
        "financial_freshness_days": 120,    # Quarterly financials can be up to ~4 months old
        "news_freshness_days": 30,
        "pe_min": 0,
        "pe_max": 500,
        "pb_min": 0,
        "pb_max": 100,
        "single_day_change_limit": 0.20,    # 20%
        "eps_growth_limit": 3.0,            # 300%
        "volume_spike_ratio": 5.0,          # 500% of average
        "min_price_records": 20,            # Minimum price history records
        "min_confidence_pass": 50,          # Overall confidence threshold to pass
        "hard_stop_confidence": 30,         # Below this: abort analysis entirely
    }

    # --- Market-specific threshold overrides ---
    MARKET_OVERRIDES = {
        "TW": {                             # Taiwan stocks: 10% daily limit
            "single_day_change_limit": 0.11,
        },
        "TWO": {                            # Taiwan OTC: same limit
            "single_day_change_limit": 0.11,
        },
        "T": {                              # Japan stocks
            "single_day_change_limit": 0.20,
        },
    }

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None, market: Optional[str] = None):
        self.anomalies: List[Dict[str, Any]] = []
        self.validation_notes: List[str] = []
        self.excluded_fields: List[Dict[str, Any]] = []

        # Build thresholds: defaults → market overrides → user overrides
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if market and market in self.MARKET_OVERRIDES:
            self.thresholds.update(self.MARKET_OVERRIDES[market])
        if thresholds:
            self.thresholds.update(thresholds)

    def validate_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main validation pipeline.

        Args:
            raw_data: Raw data dictionary from fetch_data.py (nested structure)

        Returns:
            Validated data package with confidence scores and anomaly reports
        """
        self.anomalies = []
        self.validation_notes = []
        self.excluded_fields = []

        metadata = raw_data.get("metadata", {})
        ticker = metadata.get("ticker", "UNKNOWN")

        # Step 1: Structural completeness check
        completeness = self._check_completeness(raw_data, metadata)

        # Step 2: Freshness check
        freshness = self._check_freshness(raw_data)

        # Step 3: Price data integrity
        price_integrity = self._validate_price_data(raw_data.get("price_history", []))

        # Step 4: Company info anomaly detection
        self._detect_company_info_anomalies(raw_data.get("company_info", {}))

        # Step 5: Financial statements sanity check
        self._validate_financial_statements(raw_data.get("financial_statements", {}))

        # Step 6: Technical indicators range check
        self._validate_technical_indicators(raw_data.get("technical_indicators", {}))

        # Step 7: Calculate confidence scores per category
        confidence_scores = self._calculate_confidence_scores(
            completeness, freshness, price_integrity
        )
        overall_confidence = self._calculate_overall_confidence(confidence_scores)

        # Step 8: Build validated data (pass-through with annotations)
        validated_data = self._build_validated_data(raw_data, confidence_scores)

        # Tiered validation gate
        hard_stop = self.thresholds["hard_stop_confidence"]
        soft_pass = self.thresholds["min_confidence_pass"]
        if overall_confidence < hard_stop:
            validation_tier = "hard_stop"    # Abort: data too unreliable
        elif overall_confidence < soft_pass:
            validation_tier = "warning"      # Proceed with caution, warn user
        else:
            validation_tier = "passed"       # Good to go

        return {
            "ticker": ticker,
            "validation_timestamp": datetime.now().isoformat(),
            "data_completeness": completeness,
            "data_freshness": freshness,
            "price_integrity": price_integrity,
            "anomaly_detection": self.anomalies,
            "confidence_scores": confidence_scores,
            "overall_confidence": overall_confidence,
            "validated_data": validated_data,
            "excluded_fields": self.excluded_fields,
            "validation_notes": self.validation_notes,
            "passed_validation": overall_confidence >= soft_pass,
            "validation_tier": validation_tier,
            "thresholds_used": self.thresholds,
        }

    # ------------------------------------------------------------------
    # Step 1: Structural completeness
    # ------------------------------------------------------------------
    def _check_completeness(self, data: Dict, metadata: Dict) -> Dict[str, Any]:
        """Check which data sections are present and non-empty."""
        missing_from_api = metadata.get("missing_data", [])

        sections = {
            "company_info": bool(data.get("company_info")),
            "price_history": bool(data.get("price_history")),
            "technical_indicators": bool(data.get("technical_indicators")),
            "financial_statements": self._has_financial_data(data.get("financial_statements", {})),
            "holders": bool(data.get("holders")),
            "analyst_data": bool(data.get("analyst_data")),
            "twse_institutional": bool(data.get("twse_data", {}).get("institutional_trading")),
            "twse_margin": bool(data.get("twse_data", {}).get("margin_trading")),
        }

        present_count = sum(1 for v in sections.values() if v)
        total_count = len(sections)
        completeness_pct = round(present_count / total_count * 100, 1)

        missing_sections = [k for k, v in sections.items() if not v]
        if missing_sections:
            self.validation_notes.append(
                f"Missing data sections: {', '.join(missing_sections)}"
            )

        if missing_from_api:
            self.validation_notes.append(
                f"API reported missing: {', '.join(missing_from_api)}"
            )

        return {
            "sections": sections,
            "present": present_count,
            "total": total_count,
            "completeness_pct": completeness_pct,
            "api_reported_missing": missing_from_api,
        }

    @staticmethod
    def _has_financial_data(fs: Dict) -> bool:
        """Check if financial statements have actual data."""
        for stmt_type in ("income_statement", "balance_sheet", "cash_flow"):
            stmt = fs.get(stmt_type, {})
            if isinstance(stmt, dict) and len(stmt) > 0:
                return True
        return False

    # ------------------------------------------------------------------
    # Step 2: Freshness
    # ------------------------------------------------------------------
    def _check_freshness(self, data: Dict) -> Dict[str, Any]:
        """Check freshness of different data categories."""
        now = datetime.now()
        freshness: Dict[str, Any] = {}

        # -- Fetch timestamp --
        fetch_ts = data.get("metadata", {}).get("fetch_timestamp")
        if fetch_ts:
            try:
                ft = datetime.fromisoformat(fetch_ts.replace("Z", "+00:00")).replace(tzinfo=None)
                age_hours = (now - ft).total_seconds() / 3600
                freshness["fetch"] = {
                    "timestamp": fetch_ts,
                    "age_hours": round(age_hours, 2),
                    "fresh": age_hours < 24,
                }
                if age_hours >= 24:
                    self.validation_notes.append(
                        f"Data was fetched {age_hours:.1f} hours ago (>24h)"
                    )
            except (ValueError, TypeError):
                freshness["fetch"] = {"timestamp": fetch_ts, "error": "unparseable timestamp"}

        # -- Price data freshness (last record date vs today) --
        price_history = data.get("price_history", [])
        if price_history:
            last_date_str = price_history[-1].get("date") if isinstance(price_history[-1], dict) else None
            if last_date_str:
                try:
                    last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                    age_days = (now - last_date).days
                    freshness["price"] = {
                        "last_date": last_date_str,
                        "age_days": age_days,
                        "fresh": age_days <= self.thresholds["price_freshness_days"],
                        "max_age_days": self.thresholds["price_freshness_days"],
                    }
                    thresh = self.thresholds["price_freshness_days"]
                    if age_days > thresh:
                        self.validation_notes.append(
                            f"Latest price data is {age_days} days old "
                            f"(threshold: {thresh}d)"
                        )
                except ValueError:
                    pass

        # -- Financial statements freshness --
        fs = data.get("financial_statements", {})
        latest_fin_date = self._get_latest_financial_date(fs)
        if latest_fin_date:
            age_days = (now - latest_fin_date).days
            freshness["financial"] = {
                "latest_date": latest_fin_date.strftime("%Y-%m-%d"),
                "age_days": age_days,
                "fresh": age_days <= self.thresholds["financial_freshness_days"],
                "max_age_days": self.thresholds["financial_freshness_days"],
            }
            fin_thresh = self.thresholds["financial_freshness_days"]
            if age_days > fin_thresh:
                self.validation_notes.append(
                    f"Financial data is {age_days} days old "
                    f"(threshold: {fin_thresh}d)"
                )

        # -- News freshness --
        news = data.get("news", [])
        if news:
            newest_date = self._get_newest_news_date(news)
            if newest_date:
                age_days = (now - newest_date).days
                freshness["news"] = {
                    "newest_date": newest_date.isoformat(),
                    "age_days": age_days,
                    "fresh": age_days <= self.thresholds["news_freshness_days"],
                    "max_age_days": self.thresholds["news_freshness_days"],
                }

        return freshness

    @staticmethod
    def _get_latest_financial_date(fs: Dict) -> Optional[datetime]:
        """Extract the most recent date from financial statements."""
        dates = []
        for stmt_type in ("income_statement", "balance_sheet", "cash_flow"):
            stmt = fs.get(stmt_type, {})
            if isinstance(stmt, dict):
                for date_str in stmt.keys():
                    try:
                        dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                    except ValueError:
                        continue
        return max(dates) if dates else None

    @staticmethod
    def _get_newest_news_date(news: List[Dict]) -> Optional[datetime]:
        """Get the newest news article date."""
        dates = []
        for item in news:
            pd_str = item.get("publish_date")
            if pd_str:
                try:
                    dates.append(datetime.fromisoformat(pd_str))
                except (ValueError, TypeError):
                    continue
        return max(dates) if dates else None

    # ------------------------------------------------------------------
    # Step 3: Price data integrity
    # ------------------------------------------------------------------
    def _validate_price_data(self, price_history: List[Dict]) -> Dict[str, Any]:
        """Validate price history records for integrity."""
        result = {
            "total_records": len(price_history),
            "sufficient": len(price_history) >= self.thresholds["min_price_records"],
            "null_prices": 0,
            "negative_prices": 0,
            "large_daily_moves": [],
            "date_gaps": [],
        }

        min_records = self.thresholds["min_price_records"]
        if len(price_history) < min_records:
            self.validation_notes.append(
                f"Only {len(price_history)} price records "
                f"(minimum recommended: {min_records})"
            )

        prev_close = None
        prev_date = None
        volumes = []

        for i, record in enumerate(price_history):
            close = record.get("close")
            volume = record.get("volume")
            date_str = record.get("date")

            # Null check
            if close is None:
                result["null_prices"] += 1
                continue

            # Negative check
            if close < 0:
                result["negative_prices"] += 1
                self.anomalies.append({
                    "type": "negative_price",
                    "date": date_str,
                    "value": close,
                    "severity": "high",
                })
                continue

            # Large daily move check
            if prev_close and prev_close > 0:
                change = abs(close - prev_close) / prev_close
                if change > self.thresholds["single_day_change_limit"]:
                    result["large_daily_moves"].append({
                        "date": date_str,
                        "change_pct": round(change * 100, 2),
                        "from": prev_close,
                        "to": close,
                    })
                    self.anomalies.append({
                        "type": "price_spike",
                        "date": date_str,
                        "change_pct": round(change * 100, 2),
                        "threshold_pct": self.thresholds["single_day_change_limit"] * 100,
                        "severity": "medium",
                    })

            # Date gap check
            if prev_date and date_str:
                try:
                    d1 = datetime.strptime(prev_date, "%Y-%m-%d")
                    d2 = datetime.strptime(date_str, "%Y-%m-%d")
                    gap = (d2 - d1).days
                    if gap > 7:  # More than a week gap (holidays can cause 4-5 day gaps)
                        result["date_gaps"].append({
                            "from": prev_date,
                            "to": date_str,
                            "gap_days": gap,
                        })
                except ValueError:
                    pass

            if volume is not None and volume > 0:
                volumes.append(volume)

            prev_close = close
            prev_date = date_str

        # Volume spike check
        if volumes:
            avg_volume = sum(volumes) / len(volumes)
            last_volume = volumes[-1] if volumes else 0
            if avg_volume > 0 and last_volume / avg_volume > self.thresholds["volume_spike_ratio"]:
                self.anomalies.append({
                    "type": "volume_anomaly",
                    "volume_ratio": round(last_volume / avg_volume, 2),
                    "threshold": self.thresholds["volume_spike_ratio"],
                    "latest_volume": last_volume,
                    "average_volume": round(avg_volume),
                    "severity": "low",
                })
            result["avg_volume"] = round(avg_volume)

        return result

    # ------------------------------------------------------------------
    # Step 4: Company info anomalies
    # ------------------------------------------------------------------
    def _detect_company_info_anomalies(self, info: Dict) -> None:
        """Detect anomalies in company info values."""
        if not info:
            return

        # PE ratio
        pe = info.get("pe_ratio")
        pe_min, pe_max = self.thresholds["pe_min"], self.thresholds["pe_max"]
        if pe is not None:
            if pe < pe_min or pe > pe_max:
                self.anomalies.append({
                    "type": "pe_ratio_anomaly",
                    "value": pe,
                    "acceptable_range": f"{pe_min} to {pe_max}",
                    "severity": "high" if pe < 0 else "medium",
                })
            elif pe < 0:
                self.anomalies.append({
                    "type": "negative_pe",
                    "value": pe,
                    "note": "Negative PE indicates losses; data is valid but flag for analysts",
                    "severity": "medium",
                })

        # PB ratio
        pb = info.get("pb_ratio")
        pb_min, pb_max = self.thresholds["pb_min"], self.thresholds["pb_max"]
        if pb is not None and (pb < pb_min or pb > pb_max):
            self.anomalies.append({
                "type": "pb_ratio_anomaly",
                "value": pb,
                "acceptable_range": f"{pb_min} to {pb_max}",
                "severity": "medium",
            })

        # Dividend yield sanity (>20% is suspicious)
        # yfinance returns dividend_yield in different formats: decimal (0.0472) or pct (4.72)
        dy = info.get("dividend_yield")
        if dy is not None and dy > 20.0:  # If >20, treat as percentage and flag
            self.anomalies.append({
                "type": "dividend_yield_anomaly",
                "value": dy,
                "note": "Dividend yield >20% is unusual; verify data",
                "severity": "medium",
            })

        # ROE sanity
        roe = info.get("return_on_equity")
        if roe is not None and (roe > 2.0 or roe < -2.0):
            self.anomalies.append({
                "type": "roe_anomaly",
                "value": roe,
                "note": "ROE >200% or <-200% is unusual",
                "severity": "low",
            })

        # Debt-to-equity
        dte = info.get("debt_to_equity")
        if dte is not None and dte > 500:
            self.anomalies.append({
                "type": "high_leverage",
                "value": dte,
                "note": "Debt/Equity >500% — highly leveraged",
                "severity": "medium",
            })

        # Market cap should be positive
        mcap = info.get("market_cap")
        if mcap is not None and mcap <= 0:
            self.anomalies.append({
                "type": "invalid_market_cap",
                "value": mcap,
                "severity": "high",
            })

    # ------------------------------------------------------------------
    # Step 5: Financial statements sanity
    # ------------------------------------------------------------------
    def _validate_financial_statements(self, fs: Dict) -> None:
        """Basic sanity checks on financial statement data."""
        if not fs:
            return

        # Check income statement for negative revenue (unusual but possible for special cases)
        income = fs.get("income_statement", {})
        for date_str, items in income.items():
            if not isinstance(items, dict):
                continue
            total_revenue = items.get("Total Revenue") or items.get("TotalRevenue")
            if total_revenue is not None and total_revenue < 0:
                self.anomalies.append({
                    "type": "negative_revenue",
                    "date": date_str,
                    "value": total_revenue,
                    "severity": "medium",
                })

    # ------------------------------------------------------------------
    # Step 6: Technical indicators range check
    # ------------------------------------------------------------------
    def _validate_technical_indicators(self, indicators: Dict) -> None:
        """Validate technical indicator values are in expected ranges."""
        if not indicators:
            return

        # RSI should be 0-100
        rsi_data = indicators.get("rsi_14", {})
        rsi_val = rsi_data.get("value") if isinstance(rsi_data, dict) else None
        if rsi_val is not None and (rsi_val < 0 or rsi_val > 100):
            self.anomalies.append({
                "type": "rsi_out_of_range",
                "value": rsi_val,
                "expected_range": "0 to 100",
                "severity": "high",
            })

        # Stochastic K/D should be 0-100
        kd_data = indicators.get("stochastic_kd", {})
        for key in ("k_percent", "d_percent"):
            val = kd_data.get(key) if isinstance(kd_data, dict) else None
            if val is not None and (val < 0 or val > 100):
                self.anomalies.append({
                    "type": f"stochastic_{key}_out_of_range",
                    "value": val,
                    "expected_range": "0 to 100",
                    "severity": "high",
                })

    # ------------------------------------------------------------------
    # Step 7: Confidence scoring
    # ------------------------------------------------------------------
    def _calculate_confidence_scores(
        self,
        completeness: Dict,
        freshness: Dict,
        price_integrity: Dict,
    ) -> Dict[str, int]:
        """Calculate confidence scores for each data category (0-100)."""
        scores: Dict[str, int] = {}

        # --- Price confidence ---
        price_conf = 70  # Base
        if price_integrity.get("sufficient"):
            price_conf += 15
        if freshness.get("price", {}).get("fresh"):
            price_conf += 10
        # Penalties
        price_conf -= len(price_integrity.get("large_daily_moves", [])) * 5
        price_conf -= price_integrity.get("null_prices", 0) * 2
        price_conf -= price_integrity.get("negative_prices", 0) * 10
        for a in self.anomalies:
            if a["type"] == "volume_anomaly":
                price_conf -= 5
        scores["price"] = max(0, min(100, price_conf))

        # --- Financial confidence ---
        fin_conf = 60  # Base
        if completeness["sections"].get("company_info"):
            fin_conf += 15
        if completeness["sections"].get("financial_statements"):
            fin_conf += 10
        if freshness.get("financial", {}).get("fresh"):
            fin_conf += 10
        for a in self.anomalies:
            if a["type"] in ("pe_ratio_anomaly", "negative_pe", "pb_ratio_anomaly",
                             "negative_revenue", "high_leverage", "invalid_market_cap"):
                fin_conf -= 10
        scores["financial"] = max(0, min(100, fin_conf))

        # --- Technical indicator confidence ---
        tech_conf = 70
        if completeness["sections"].get("technical_indicators"):
            tech_conf += 15
        for a in self.anomalies:
            if "out_of_range" in a.get("type", ""):
                tech_conf -= 20
        scores["technical"] = max(0, min(100, tech_conf))

        # --- Holders / analyst confidence ---
        holder_conf = 50
        if completeness["sections"].get("holders"):
            holder_conf += 15
        if completeness["sections"].get("analyst_data"):
            holder_conf += 15
        # TWSE data bonus for Taiwan stocks
        if completeness["sections"].get("twse_institutional"):
            holder_conf += 10
        if completeness["sections"].get("twse_margin"):
            holder_conf += 10
        scores["institutional"] = max(0, min(100, holder_conf))

        return scores

    def _calculate_overall_confidence(self, scores: Dict[str, int]) -> int:
        """Weighted average of category confidence scores."""
        weights = {
            "price": 0.30,
            "financial": 0.30,
            "technical": 0.20,
            "institutional": 0.20,
        }

        total = 0.0
        for cat, weight in weights.items():
            total += scores.get(cat, 50) * weight

        # Penalty for high-severity anomalies
        high_count = sum(1 for a in self.anomalies if a.get("severity") == "high")
        total -= high_count * 10

        return max(0, min(100, int(total)))

    # ------------------------------------------------------------------
    # Step 9: Build validated data
    # ------------------------------------------------------------------
    def _build_validated_data(self, raw_data: Dict, confidence: Dict) -> Dict[str, Any]:
        """
        Build the validated data package.
        Pass through all data but annotate with validation metadata.
        Low-confidence sections get flagged but are NOT removed —
        downstream agents need the data and can decide how to weight it.
        """
        validated = {}

        # Pass through all sections from raw_data
        for key in ("metadata", "company_info", "price_history", "technical_indicators",
                     "financial_statements", "holders", "analyst_data", "twse_data"):
            validated[key] = raw_data.get(key, {})

        # Add validation annotations
        validated["_validation"] = {
            "confidence_scores": confidence,
            "anomaly_count": len(self.anomalies),
            "high_severity_anomalies": sum(
                1 for a in self.anomalies if a.get("severity") == "high"
            ),
            "low_confidence_sections": [
                k for k, v in confidence.items() if v < self.thresholds["min_confidence_pass"]
            ],
        }

        return validated


def _detect_market(ticker: str) -> Optional[str]:
    """Detect market suffix from ticker (e.g. '2330.TW' → 'TW')."""
    if '.' in ticker:
        return ticker.rsplit('.', 1)[-1].upper()
    return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate stock data and assign confidence scores"
    )
    parser.add_argument("--input", required=True, help="Input raw data JSON file")
    parser.add_argument("--output", required=True, help="Output validated data JSON file")
    parser.add_argument("--config", default=None,
                        help="Optional JSON config file with threshold overrides")

    args = parser.parse_args()

    # Read raw data
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Load optional threshold overrides
    custom_thresholds = None
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                custom_thresholds = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load config: {e}", file=sys.stderr)

    # Auto-detect market from ticker
    ticker = raw_data.get("metadata", {}).get("ticker", "")
    market = _detect_market(ticker)

    # Validate
    validator = StockDataValidator(thresholds=custom_thresholds, market=market)
    validated_package = validator.validate_data(raw_data)

    # Summary output
    overall = validated_package["overall_confidence"]
    anomaly_count = len(validated_package["anomaly_detection"])
    passed = validated_package["passed_validation"]

    tier = validated_package["validation_tier"]
    tier_label = {"passed": "PASSED", "warning": "WARNING (low confidence)", "hard_stop": "HARD STOP (abort)"}
    print(f"=== Validation Report for {validated_package['ticker']} ===")
    print(f"  Overall Confidence: {overall}/100 — {tier_label.get(tier, tier)}")
    print(f"  Anomalies Detected: {anomaly_count}")
    print(f"  Data Completeness:  {validated_package['data_completeness']['completeness_pct']}%")

    if validated_package["validation_notes"]:
        print(f"  Notes:")
        for note in validated_package["validation_notes"]:
            print(f"    - {note}")

    # Write output
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(validated_package, f, indent=2, ensure_ascii=False)
        print(f"\nValidated data written to: {args.output}")
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
