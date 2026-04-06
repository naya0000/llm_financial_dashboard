#!/usr/bin/env python3
"""
assemble_report.py — Mechanical assembly of integrated_report.json

Reads all 6 agent outputs + validated_data.json + a small LLM-generated
synthesis JSON, and merges them into the final integrated_report.json.

This eliminates the need for the LLM to generate the full ~29KB report,
reducing it to only the ~3KB reasoning portion (scores, narrative, summary).

Usage:
    python assemble_report.py \
        --dir <output_dir>            # directory containing agent JSONs \
        --synthesis <synthesis.json>   # LLM-generated reasoning portion \
        --output <integrated_report.json>
"""

import argparse
import json
import os
import sys
from datetime import date


# ── Agent file → integrated key mapping ──────────────────────────────────
AGENT_FILE_MAP = {
    "financial_analysis.json":      "financial_analyst",
    "technical_analysis.json":      "technical_analyst",
    "quant_analysis.json":          "quantitative_analyst",
    "industry_analysis.json":       "industry_macro",
    "sentiment_analysis.json":      "news_sentiment",
    "institutional_analysis.json":  "institutional_flow",
}

# dimension_scores key for each agent
DIMENSION_KEY_MAP = {
    "financial_analyst":      "fundamental",
    "technical_analyst":      "technical",
    "quantitative_analyst":   "quantitative",
    "industry_macro":         "industry",
    "news_sentiment":         "sentiment",
    "institutional_flow":     "fund_flow",
}

# Default weights for overall_score calculation (used if not provided)
DEFAULT_WEIGHTS = {
    "financial_analyst":      25,
    "technical_analyst":      20,
    "quantitative_analyst":   10,
    "industry_macro":         20,
    "news_sentiment":         10,
    "institutional_flow":     15,
}


def load_json(path):
    """Load a JSON file, return None if missing or invalid."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        return None


def extract_agent_entry(agent_key, data):
    """Extract the standardized {score, confidence, summary, sources?} for one agent."""
    if data is None:
        return None

    entry = {}

    # Quant agent has a special structure (no top-level score/summary)
    if agent_key == "quantitative_analyst":
        conf = data.get("confidence", {})
        if isinstance(conf, dict):
            overall_conf = conf.get("overall", 0.5)
            # Map 0-1 float to 0-10 score (if not overridden by synthesis)
            entry["score"] = round(overall_conf * 10, 1)
            entry["confidence"] = conf.get("recommendation", "Medium")
        else:
            entry["score"] = 5.0
            entry["confidence"] = str(conf)
        entry["summary"] = data.get("summary", "")
    else:
        entry["score"] = data.get("score", 5.0)
        conf = data.get("confidence", "Medium")
        # Normalize float confidence (e.g. 0.75) to string
        if isinstance(conf, (int, float)):
            if conf <= 1.0:
                thresholds = [(0.8, "High"), (0.6, "Medium-High"), (0.4, "Medium"), (0.2, "Medium-Low")]
                label = "Low"
                for t, l in thresholds:
                    if conf >= t:
                        label = l
                        break
                conf = label
            else:
                conf = str(conf)
        entry["confidence"] = conf
        entry["summary"] = data.get("summary", "")

    # Copy sources for news_sentiment
    if agent_key == "news_sentiment" and "sources" in data:
        entry["sources"] = data["sources"]

    return entry


def extract_metrics(validated_data):
    """Extract dashboard metrics from validated_data.json."""
    if validated_data is None:
        return {}

    vd = validated_data.get("validated_data", validated_data)
    info = vd.get("company_info", {})

    metrics = {}
    for key in ["pe_ratio", "pb_ratio", "eps"]:
        val = info.get(key)
        if val is not None:
            metrics[key] = round(val, 2) if isinstance(val, float) else val

    roe = info.get("return_on_equity")
    if roe is not None:
        metrics["roe"] = f"{round(roe * 100, 2)}%" if isinstance(roe, float) and roe < 1 else f"{roe}%"

    dy = info.get("dividend_yield")
    if dy is not None:
        metrics["dividend_yield"] = f"{round(dy * 100, 2)}%" if isinstance(dy, float) and dy < 1 else f"{dy}%"

    dte = info.get("debt_to_equity")
    if dte is not None:
        dte_rounded = round(dte, 2) if isinstance(dte, float) else dte
        metrics["debt_ratio"] = f"{dte_rounded}%"

    return metrics


def extract_all_data_limitations(agent_data_map):
    """Collect data_limitations from all agent outputs into a flat list."""
    all_limits = []
    for agent_key, data in agent_data_map.items():
        if data is None:
            continue
        limits = data.get("data_limitations", [])
        if isinstance(limits, list):
            all_limits.extend(limits)
        elif isinstance(limits, str):
            all_limits.append(limits)
    return all_limits


def extract_stock_info(validated_data, agent_data_map):
    """Extract ticker and company_name."""
    info = {"ticker": "", "company_name": ""}

    if validated_data:
        vd = validated_data.get("validated_data", validated_data)
        ci = vd.get("company_info", {})
        info["ticker"] = ci.get("ticker", validated_data.get("ticker", ""))
        info["company_name"] = ci.get("company_name", "")

    # Fallback: try agent outputs
    if not info["ticker"]:
        for data in agent_data_map.values():
            if data and data.get("ticker"):
                info["ticker"] = data["ticker"]
                break

    return info


def assemble(args):
    data_dir = args.dir
    synthesis_path = args.synthesis
    output_path = args.output

    # Load synthesis (LLM-generated reasoning)
    synthesis = load_json(synthesis_path)
    if synthesis is None:
        print(f"Error: synthesis file not found: {synthesis_path}", file=sys.stderr)
        sys.exit(1)

    # Load validated_data
    validated_data = load_json(os.path.join(data_dir, "validated_data.json"))

    # Load all agent outputs
    agent_data_map = {}
    for filename, agent_key in AGENT_FILE_MAP.items():
        agent_data_map[agent_key] = load_json(os.path.join(data_dir, filename))

    # Determine active analysts
    active = synthesis.get("active_analysts")
    mode = synthesis.get("mode", "full_analysis")
    if active is None:
        active = [k for k, v in agent_data_map.items() if v is not None]

    # ── Build analysts section (mechanical) ──
    analysts = {}
    dimension_scores = {}
    for agent_key in active:
        data = agent_data_map.get(agent_key)
        entry = extract_agent_entry(agent_key, data)
        if entry is None:
            continue

        # Allow synthesis to override scores
        synth_scores = synthesis.get("dimension_scores", {})
        dim_key = DIMENSION_KEY_MAP.get(agent_key)
        if dim_key and dim_key in synth_scores:
            entry["score"] = synth_scores[dim_key]

        # Allow synthesis to provide/override summary (needed for quant agent
        # which has no top-level summary in its script output)
        synth_analysts = synthesis.get("analysts", {})
        if agent_key in synth_analysts:
            overrides = synth_analysts[agent_key]
            if overrides.get("summary"):
                entry["summary"] = overrides["summary"]
            if overrides.get("confidence"):
                entry["confidence"] = overrides["confidence"]

        analysts[agent_key] = entry
        if dim_key:
            dimension_scores[dim_key] = entry["score"]

    # ── Build metrics (mechanical) ──
    metrics = extract_metrics(validated_data)

    # ── Build data_limitations (mechanical base, synthesis can override) ──
    raw_limitations = extract_all_data_limitations(agent_data_map)

    # ── Build stock_info (synthesis overrides validated_data) ──
    stock_info = extract_stock_info(validated_data, agent_data_map)
    synth_info = synthesis.get("stock_info", {})
    if synth_info.get("company_name"):
        stock_info["company_name"] = synth_info["company_name"]
    if synth_info.get("ticker"):
        stock_info["ticker"] = synth_info["ticker"]

    # ── Assemble final report ──
    report = {
        "stock_info": stock_info,
        "overall_score": synthesis.get("overall_score", 5.0),
        "confidence_level": synthesis.get("confidence_level", "Medium"),
        "summary": synthesis.get("summary", ""),
        "analysis_date": str(date.today()),
        "dimension_scores": dimension_scores,
        "analysts": analysts,
        "narrative_report": synthesis.get("narrative_report", {}),
        "metrics": metrics,
        "data_limitations": synthesis.get("data_limitations", raw_limitations),
    }

    # Add mode/active_analysts for selective
    if mode == "selective":
        report["mode"] = "selective"
        report["active_analysts"] = active
    elif mode == "full_analysis":
        report["mode"] = "full_analysis"

    # Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"✓ Assembled integrated_report.json ({len(json.dumps(report, ensure_ascii=False))} bytes)")
    print(f"  Agents: {len(analysts)}, Dimensions: {len(dimension_scores)}, Metrics: {len(metrics)}")
    print(f"  Data limitations: {len(report['data_limitations'])} items")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble integrated_report.json from agent outputs + LLM synthesis")
    parser.add_argument("--dir", required=True, help="Directory containing agent output JSONs and validated_data.json")
    parser.add_argument("--synthesis", required=True, help="Path to LLM-generated synthesis JSON")
    parser.add_argument("--output", required=True, help="Output path for integrated_report.json")
    args = parser.parse_args()
    assemble(args)
