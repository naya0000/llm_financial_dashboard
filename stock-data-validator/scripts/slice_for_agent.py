#!/usr/bin/env python3
"""
slice_for_agent.py — 將 validated_data.json 按 Agent 職責切片。

每個 Agent 只拿到與自己分析相關的欄位，避免無關資料干擾 LLM 推理，
也讓各 Agent 的輸入大小從 ~200KB 降到 ~10-30KB。

支援的 Agent 角色：
  financial     財務分析師
  technical     技術分析師
  quantitative  量化分析師
  institutional 法人籌碼分析師
  sentiment     新聞情緒分析師
  industry      產業總經分析師

使用方式：
  # 作為模組匯入（主要用途）
  from slice_for_agent import slice_for_agent
  payload = slice_for_agent("technical", validated_data)

  # 作為 CLI 工具
  python slice_for_agent.py --input validated_data.json --agent technical
  python slice_for_agent.py --input validated_data.json --agent financial --output financial_slice.json
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

# ── 每個 Agent 需要的 company_info 欄位子集 ──────────────────────────────────

_CI_FINANCIAL = {
    "name", "market_cap", "pe_ratio", "forward_pe", "peg_ratio", "pb_ratio",
    "eps", "dividend_yield", "dividend_rate", "five_year_avg_dividend_yield",
    "trailing_12_month_revenue", "profit_margin", "operating_margin",
    "return_on_equity", "return_on_assets", "debt_to_equity",
    "current_ratio", "quick_ratio", "currency",
}

_CI_TECHNICAL = {
    "current_price", "previous_close", "52_week_high", "52_week_low",
    "50_day_average", "200_day_average", "average_volume", "average_volume_10d",
    "beta", "currency",
}

_CI_QUANTITATIVE = {
    "beta", "currency", "name",
}

_CI_INSTITUTIONAL = {
    "name", "market_cap", "currency", "exchange",
}

_CI_SENTIMENT = {
    "name", "sector", "industry", "currency",
}

_CI_INDUSTRY = {
    "name", "sector", "industry", "market_cap",
    "pe_ratio", "pb_ratio", "return_on_equity", "debt_to_equity",
    "beta", "currency", "exchange", "description",
}

# ── price_history 欄位 ───────────────────────────────────────────────────────

_PH_OHLCV   = {"date", "open", "high", "low", "close", "volume"}
_PH_CLOSE   = {"date", "close"}                          # 量化師只需要收盤價
_PH_WITH_MA = _PH_OHLCV | {"ma_5", "ma_10", "ma_20", "ma_60", "ma_120", "ma_240"}


def _pick(d: Dict, keys: set) -> Dict:
    """從 dict 取出指定 key 的子集，忽略不存在的 key。"""
    return {k: v for k, v in d.items() if k in keys}


def _filter_price_history(ph: List[Dict], fields: set) -> List[Dict]:
    return [_pick(record, fields) for record in ph]


# ── 各 Agent 切片函式 ────────────────────────────────────────────────────────

def _slice_financial(vd: Dict) -> Dict:
    """財務分析師：財務比率、財報三表、最新收盤（估值基準）。"""
    ph = vd.get("price_history", [])
    latest_close = ph[-1].get("close") if ph else None

    return {
        "metadata":             vd.get("metadata", {}),
        "company_info":         _pick(vd.get("company_info", {}), _CI_FINANCIAL),
        "latest_close":         latest_close,
        "financial_statements": vd.get("financial_statements", {}),
        "_validation":          vd.get("_validation", {}),
    }


def _slice_technical(vd: Dict) -> Dict:
    """技術分析師：完整 OHLCV + MA、技術指標、52週高低。"""
    return {
        "metadata":             vd.get("metadata", {}),
        "company_info":         _pick(vd.get("company_info", {}), _CI_TECHNICAL),
        "price_history":        _filter_price_history(vd.get("price_history", []), _PH_WITH_MA),
        "technical_indicators": vd.get("technical_indicators", {}),
        "_validation":          vd.get("_validation", {}),
    }


def _slice_quantitative(vd: Dict) -> Dict:
    """量化分析師：只需要日期 + 收盤價序列（用來算報酬、波動、Sharpe）。"""
    return {
        "metadata":      vd.get("metadata", {}),
        "company_info":  _pick(vd.get("company_info", {}), _CI_QUANTITATIVE),
        "price_history": _filter_price_history(vd.get("price_history", []), _PH_CLOSE),
        "_validation":   vd.get("_validation", {}),
    }


def _slice_institutional(vd: Dict) -> Dict:
    """法人籌碼分析師：持股結構、分析師評級、TWSE 三大法人 + 融資融券。"""
    return {
        "metadata":      vd.get("metadata", {}),
        "company_info":  _pick(vd.get("company_info", {}), _CI_INSTITUTIONAL),
        "holders":       vd.get("holders", {}),
        "analyst_data":  vd.get("analyst_data", {}),
        "twse_data":     vd.get("twse_data", {}),
        "_validation":   vd.get("_validation", {}),
    }


def _slice_sentiment(vd: Dict) -> Dict:
    """新聞情緒分析師：只需要新聞列表 + 基本公司識別。"""
    return {
        "metadata":     vd.get("metadata", {}),
        "company_info": _pick(vd.get("company_info", {}), _CI_SENTIMENT),
        "news":         vd.get("news", []),
        "_validation":  vd.get("_validation", {}),
    }


def _slice_industry(vd: Dict) -> Dict:
    """產業總經分析師：產業定位、估值比率、總體財務概況（不含逐季財報明細）。"""
    return {
        "metadata":     vd.get("metadata", {}),
        "company_info": _pick(vd.get("company_info", {}), _CI_INDUSTRY),
        "_validation":  vd.get("_validation", {}),
    }


# ── 公開介面 ─────────────────────────────────────────────────────────────────

AGENTS = {
    "financial":    _slice_financial,
    "technical":    _slice_technical,
    "quantitative": _slice_quantitative,
    "institutional":_slice_institutional,
    "sentiment":    _slice_sentiment,
    "industry":     _slice_industry,
}


def slice_for_agent(agent: str, validated_package: Dict[str, Any]) -> Dict[str, Any]:
    """
    從完整的 validated_data.json 切出指定 Agent 所需的欄位子集。

    Args:
        agent: Agent 名稱，必須是 AGENTS 其中之一
        validated_package: validate_data.py 輸出的完整 dict

    Returns:
        切片後的 dict，包含 agent、ticker、slice_fields、payload 四個頂層欄位

    Raises:
        ValueError: agent 名稱不在支援清單中
    """
    if agent not in AGENTS:
        raise ValueError(f"未知的 agent：'{agent}'，支援：{list(AGENTS)}")

    # validated_package 頂層是 validate_data.py 的輸出，
    # 實際資料在 validated_data 子鍵內
    vd = validated_package.get("validated_data", validated_package)
    ticker = validated_package.get("ticker") or vd.get("metadata", {}).get("ticker", "UNKNOWN")

    payload = AGENTS[agent](vd)

    return {
        "agent":        agent,
        "ticker":       ticker,
        "slice_fields": list(payload.keys()),
        "payload":      payload,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="將 validated_data.json 按 Agent 職責切片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
支援的 Agent：
  {', '.join(AGENTS)}

範例：
  python slice_for_agent.py --input validated_data.json --agent technical
  python slice_for_agent.py --input validated_data.json --agent financial --output fin_slice.json
  python slice_for_agent.py --input validated_data.json --agent quantitative --sizes
        """,
    )
    parser.add_argument("--input",  "-i", required=True, help="validated_data.json 路徑")
    parser.add_argument("--agent",  "-a", required=True, choices=list(AGENTS), help="目標 Agent")
    parser.add_argument("--output", "-o", default=None,  help="輸出路徑（省略則印到 stdout）")
    parser.add_argument("--sizes",  action="store_true", help="同時印出各 Agent 切片大小比較")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            validated_package = json.load(f)
    except FileNotFoundError:
        print(f"Error: 找不到 {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: JSON 格式錯誤 — {e}", file=sys.stderr)
        sys.exit(1)

    result = slice_for_agent(args.agent, validated_package)

    if args.sizes:
        full_size = len(json.dumps(validated_package, ensure_ascii=False))
        print(f"\n{'Agent':<15} {'大小(KB)':>10}  {'佔原始%':>8}  {'欄位'}", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        for name in AGENTS:
            s = slice_for_agent(name, validated_package)
            sz = len(json.dumps(s["payload"], ensure_ascii=False))
            pct = sz / full_size * 100
            fields = ", ".join(s["slice_fields"])
            print(f"  {name:<13} {sz/1024:>9.1f}  {pct:>7.1f}%  {fields}", file=sys.stderr)
        print(f"\n  {'原始完整':<13} {full_size/1024:>9.1f}  {'100.0%':>8}", file=sys.stderr)
        print(file=sys.stderr)

    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json + "\n")
        print(f"已寫入：{args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
