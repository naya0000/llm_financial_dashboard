#!/usr/bin/env python3
"""
verify_report.py — 驗證 integrated_report.json 關鍵數字是否與當前 yfinance 一致。

對比項目：
  - 財務指標：PE、PB、EPS、ROE、殖利率、負債比
  - 最新收盤價（與報告分析日收盤比對）
  - 六維評分合理性（dimension_scores 加權驗算 overall_score）

使用方式：
  python verify_report.py --report /path/to/integrated_report.json
  python verify_report.py --report ./2330.tw/integrated_report.json --tolerance 0.10
  python verify_report.py --report ./2330.tw/integrated_report.json --json
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Optional

import yfinance as yf

# 容差設定（預設各項目）
DEFAULT_TOLERANCE = {
    "pe_ratio":       0.10,   # ±10%（PE 每日浮動）
    "pb_ratio":       0.10,
    "eps":            0.05,   # ±5%（EPS 相對穩定）
    "roe":            0.15,   # ±15%（yfinance 有時用 TTM vs 年度）
    "dividend_yield": 0.15,
    "debt_ratio":     0.15,
}

# 維度權重（與 assemble_report.py DEFAULT_WEIGHTS 一致）
DIMENSION_WEIGHTS = {
    "fundamental":   0.25,
    "technical":     0.20,
    "quantitative":  0.10,
    "industry":      0.20,
    "sentiment":     0.10,
    "fund_flow":     0.15,
}

ANSI_GREEN  = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RED    = "\033[91m"
ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"


def _color(text: str, code: str, use_color: bool) -> str:
    return f"{code}{text}{ANSI_RESET}" if use_color else text


def fetch_live(ticker: str) -> dict:
    """從 yfinance 抓即時財務指標，並保留原始 info 供 DuPont 計算使用。"""
    info = yf.Ticker(ticker).info

    def _pct(key: str) -> Optional[float]:
        v = info.get(key)
        if v is None:
            return None
        # yfinance 對不同股票回傳小數（0.0133）或百分比（1.33）兩種格式
        # 若值 < 1，視為小數形式，乘以 100 轉為百分比
        return round(v * 100, 4) if abs(v) < 1 else round(float(v), 4)

    return {
        "pe_ratio":       _safe_round(info.get("trailingPE"), 2),
        "pb_ratio":       _safe_round(info.get("priceToBook"), 2),
        "eps":            _safe_round(info.get("trailingEps"), 2),
        "roe":            _pct("returnOnEquity"),
        "dividend_yield": _pct("dividendYield"),
        "debt_ratio":     _safe_round(info.get("debtToEquity"), 2),
        "current_price":  _safe_round(
            info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"), 2
        ),
        "currency":       info.get("currency", ""),
        "company_name":   info.get("longName") or info.get("shortName") or ticker,
        "_raw_info":      info,  # 保留給 DuPont 和殖利率反推使用
    }


def _safe_round(v: Any, n: int) -> Optional[float]:
    try:
        return round(float(v), n) if v is not None else None
    except (TypeError, ValueError):
        return None


def parse_report_metrics(report: dict) -> dict:
    """從 integrated_report.json 的 metrics 段落取出數字，統一轉為 float。"""
    m = report.get("metrics", {})

    def _parse_pct(val) -> Optional[float]:
        if val is None:
            return None
        s = str(val).replace("%", "").strip()
        try:
            return round(float(s), 4)
        except ValueError:
            return None

    def _parse_num(val) -> Optional[float]:
        if val is None:
            return None
        try:
            return round(float(val), 4)
        except (TypeError, ValueError):
            return None

    return {
        "pe_ratio":       _parse_num(m.get("pe_ratio")),
        "pb_ratio":       _parse_num(m.get("pb_ratio")),
        "eps":            _parse_num(m.get("eps")),
        "roe":            _parse_pct(m.get("roe")),
        "dividend_yield": _parse_pct(m.get("dividend_yield")),
        "debt_ratio":     _parse_pct(m.get("debt_ratio")),
    }


def check_metric(name: str, report_val: Optional[float], live_val: Optional[float],
                 tolerance: float, use_color: bool) -> dict:
    """比對單一指標，回傳結果 dict。"""
    if report_val is None and live_val is None:
        status = "skip"
        detail = "兩邊都沒有資料"
    elif report_val is None:
        status = "skip"
        detail = f"報告無此欄位（yfinance 當前值：{live_val}）"
    elif live_val is None:
        status = "skip"
        detail = f"yfinance 無資料（報告值：{report_val}）"
    else:
        diff_pct = abs(report_val - live_val) / abs(live_val) if live_val != 0 else float("inf")
        if diff_pct <= tolerance:
            status = "pass"
        elif diff_pct <= tolerance * 2:
            status = "warn"
        else:
            status = "fail"
        detail = (
            f"報告={report_val:>10.2f}  |  即時={live_val:>10.2f}  |  差異={diff_pct*100:+.1f}%"
            f"  (容差±{tolerance*100:.0f}%)"
        )

    return {"name": name, "status": status, "detail": detail,
            "report_val": report_val, "live_val": live_val}


def verify_score_arithmetic(report: dict) -> dict:
    """驗算 overall_score 是否符合 dimension_scores 加權結果。"""
    dim = report.get("dimension_scores", {})
    reported = report.get("overall_score")

    if not dim or reported is None:
        return {"status": "skip", "detail": "缺少 dimension_scores 或 overall_score"}

    computed = sum(
        dim.get(k, 0) * w for k, w in DIMENSION_WEIGHTS.items() if k in dim
    )
    weight_sum = sum(w for k, w in DIMENSION_WEIGHTS.items() if k in dim)
    if weight_sum < 0.99:
        return {"status": "warn",
                "detail": f"部分維度缺失（有效權重合計 {weight_sum*100:.0f}%），加權分僅供參考"}

    diff = abs(computed - reported)
    status = "pass" if diff <= 0.3 else ("warn" if diff <= 1.0 else "fail")
    return {
        "status": status,
        "detail": (
            f"加權計算值={computed:.2f}  |  報告值={reported:.2f}  |  差={diff:.2f}"
        ),
        "computed": round(computed, 2),
        "reported": reported,
        "dimension_scores": dim,
    }


def verify_dupont(live: dict) -> dict:
    """
    用 DuPont 公式反推 ROE：淨利率 × 資產周轉率 × 財務槓桿。
    所有數值從 yfinance info 即時抓取，與報告 ROE 比對。
    """
    ticker_obj_info = live.get("_raw_info", {})
    if not ticker_obj_info:
        return {"status": "skip", "detail": "缺少原始 yfinance info，無法計算 DuPont"}

    net_margin  = ticker_obj_info.get("profitMargins")       # 淨利率（小數）
    asset_turn  = ticker_obj_info.get("assetTurnover")       # 資產周轉率
    total_assets = ticker_obj_info.get("totalAssets")
    total_equity = ticker_obj_info.get("bookValue")          # per share
    shares       = ticker_obj_info.get("sharesOutstanding")
    revenue      = ticker_obj_info.get("totalRevenue")
    net_income   = ticker_obj_info.get("netIncomeToCommon")

    # 嘗試自己計算缺失的分項
    if asset_turn is None and total_assets and revenue:
        asset_turn = revenue / total_assets

    # 財務槓桿 = 總資產 ÷ 股東權益
    equity_total = None
    if total_equity and shares:
        equity_total = total_equity * shares
    leverage = None
    if total_assets and equity_total and equity_total > 0:
        leverage = total_assets / equity_total

    if net_margin is None or asset_turn is None or leverage is None:
        missing = []
        if net_margin is None:  missing.append("淨利率")
        if asset_turn is None:  missing.append("資產周轉率")
        if leverage is None:    missing.append("財務槓桿")
        return {"status": "skip", "detail": f"缺少 DuPont 分項資料：{', '.join(missing)}"}

    dupont_roe = net_margin * asset_turn * leverage * 100  # 轉為百分比
    live_roe   = live.get("roe")  # 已是百分比

    if live_roe is None:
        return {
            "status": "warn",
            "detail": (
                f"DuPont 反推 ROE={dupont_roe:.2f}%"
                f"（淨利率={net_margin*100:.1f}% × 資產周轉={asset_turn:.2f} × 槓桿={leverage:.2f}）"
                f"  |  yfinance ROE 不可用，無法交叉比對"
            ),
            "dupont_roe": round(dupont_roe, 2),
        }

    diff_pct = abs(dupont_roe - live_roe) / abs(live_roe) if live_roe != 0 else float("inf")
    status = "pass" if diff_pct <= 0.20 else ("warn" if diff_pct <= 0.40 else "fail")
    return {
        "status": status,
        "detail": (
            f"DuPont 反推={dupont_roe:.2f}%  |  yfinance ROE={live_roe:.2f}%  |  差異={diff_pct*100:+.1f}%"
            f"（淨利率={net_margin*100:.1f}% × 資產周轉={asset_turn:.2f} × 槓桿={leverage:.2f}）"
        ),
        "dupont_roe": round(dupont_roe, 2),
        "live_roe":   round(live_roe, 2),
    }


def verify_dividend_yield_consistency(live: dict) -> dict:
    """
    用 DPS ÷ 股價反推殖利率，確認與 yfinance dividendYield 邏輯一致。
    DPS = dividendsPerShare（過去 12 個月現金股利）
    """
    info = live.get("_raw_info", {})
    if not info:
        return {"status": "skip", "detail": "缺少原始 yfinance info"}

    dps   = info.get("lastDividendValue") or info.get("dividendsPerShare")
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    yf_yield = info.get("dividendYield")  # yfinance 的殖利率（小數）

    if dps is None:
        return {"status": "skip", "detail": "無股利資料（可能為不配息股票）"}
    if price is None or price == 0:
        return {"status": "skip", "detail": "無法取得即時股價"}

    computed_yield = (dps / price) * 100  # 轉為百分比
    yf_yield_pct   = yf_yield * 100 if yf_yield is not None else None

    if yf_yield_pct is None:
        return {
            "status": "warn",
            "detail": (
                f"DPS÷股價反推殖利率={computed_yield:.2f}%"
                f"（DPS={dps}，股價={price}）  |  yfinance dividendYield 不可用"
            ),
            "computed_yield": round(computed_yield, 2),
        }

    diff_pct = abs(computed_yield - yf_yield_pct) / abs(yf_yield_pct) if yf_yield_pct != 0 else float("inf")
    status = "pass" if diff_pct <= 0.10 else ("warn" if diff_pct <= 0.25 else "fail")
    return {
        "status": status,
        "detail": (
            f"DPS÷股價={computed_yield:.2f}%  |  yfinance yield={yf_yield_pct:.2f}%  |  差異={diff_pct*100:+.1f}%"
            f"（DPS={dps}，股價={price}）"
        ),
        "computed_yield": round(computed_yield, 2),
        "yf_yield":       round(yf_yield_pct, 2),
    }


def verify_price_staleness(report: dict, live_price: Optional[float]) -> dict:
    """
    檢查報告分析日 vs 今天，並比較報告期間收盤價與即時價的距離。
    不判定對錯（價格本來就會變），只回報資訊。
    """
    analysis_date = report.get("analysis_date", "")
    today = datetime.now().date()
    try:
        rd = datetime.strptime(analysis_date, "%Y-%m-%d").date()
        age_days = (today - rd).days
    except ValueError:
        return {"status": "skip", "detail": "無法解析 analysis_date"}

    # 從 narrative 抓報告撰寫時的股價（若有寫明）
    summary = report.get("summary", "")
    detail = f"分析日：{analysis_date}（{age_days} 天前）"
    if live_price:
        detail += f"  |  即時價：{live_price}"

    status = "pass" if age_days <= 7 else ("warn" if age_days <= 30 else "fail")
    return {"status": status, "detail": detail, "age_days": age_days}


def print_result(result: dict, label: str, use_color: bool):
    icons = {"pass": "✓", "warn": "△", "fail": "✗", "skip": "—"}
    colors = {"pass": ANSI_GREEN, "warn": ANSI_YELLOW, "fail": ANSI_RED, "skip": ""}
    st = result["status"]
    icon = _color(icons.get(st, "?"), colors.get(st, ""), use_color)
    print(f"  {icon}  {label:<20} {result['detail']}")


def run_verification(report_path: str, global_tolerance: Optional[float],
                     use_color: bool, as_json: bool) -> int:
    """主驗證流程，回傳 exit code（0=全過，1=有警告，2=有失敗）。"""
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    ticker = report.get("stock_info", {}).get("ticker", "")
    company = report.get("stock_info", {}).get("company_name", "")
    if not ticker:
        print("Error: integrated_report.json 缺少 stock_info.ticker", file=sys.stderr)
        return 2

    if not as_json:
        print(f"\n{ANSI_BOLD if use_color else ''}=== 驗證報告：{company}（{ticker}）==={ANSI_RESET if use_color else ''}")
        print(f"  報告路徑：{report_path}")
        print(f"  驗證時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 抓即時資料
    if not as_json:
        print("  [1/4] 從 yfinance 抓即時資料...")
    live = fetch_live(ticker)

    report_metrics = parse_report_metrics(report)

    results = {}

    # ── 財務指標比對 ──
    metric_labels = {
        "pe_ratio":       "本益比 (PE)",
        "pb_ratio":       "股價淨值比 (PB)",
        "eps":            "每股盈餘 (EPS)",
        "roe":            "股東權益報酬率 (ROE %)",
        "dividend_yield": "殖利率 (%)",
        "debt_ratio":     "負債比 (%)",
    }

    metric_results = {}
    for key, label in metric_labels.items():
        tol = global_tolerance if global_tolerance is not None else DEFAULT_TOLERANCE.get(key, 0.10)
        r = check_metric(key, report_metrics.get(key), live.get(key), tol, use_color)
        metric_results[key] = r

    results["metrics"] = metric_results

    # ── 評分加權驗算 ──
    score_result = verify_score_arithmetic(report)
    results["score_arithmetic"] = score_result

    # ── 業務邏輯驗算 ──
    dupont_result   = verify_dupont(live)
    yield_result    = verify_dividend_yield_consistency(live)
    results["dupont_roe"]      = dupont_result
    results["yield_crosscheck"] = yield_result

    # ── 資料時效性 ──
    staleness_result = verify_price_staleness(report, live.get("current_price"))
    results["data_staleness"] = staleness_result

    # 輸出時排除內部用的 _raw_info
    live_output = {k: v for k, v in live.items() if k != "_raw_info"}

    if as_json:
        print(json.dumps({
            "ticker": ticker,
            "company_name": company,
            "live_data": live_output,
            "report_metrics": report_metrics,
            "results": results,
        }, ensure_ascii=False, indent=2))
        counts = _count_statuses(results)
        return 2 if counts["fail"] > 0 else (1 if counts["warn"] > 0 else 0)

    # ── 人類可讀輸出 ──
    print(f"  即時資料：{live.get('company_name')}  |  即時價格：{live.get('current_price')} {live.get('currency')}\n")

    print(_color("  【財務指標比對】", ANSI_BOLD, use_color))
    for key, r in metric_results.items():
        print_result(r, metric_labels[key], use_color)

    print()
    print(_color("  【評分加權驗算】", ANSI_BOLD, use_color))
    print_result(score_result, "overall_score", use_color)
    if score_result.get("dimension_scores"):
        dim = score_result["dimension_scores"]
        for k, w in DIMENSION_WEIGHTS.items():
            if k in dim:
                contrib = dim[k] * w
                print(f"      {k:<15} {dim[k]:.1f} × {w*100:.0f}% = {contrib:.2f}")

    print()
    print(_color("  【業務邏輯驗算】", ANSI_BOLD, use_color))
    print_result(dupont_result,  "DuPont 反推 ROE", use_color)
    print_result(yield_result,   "DPS÷股價→殖利率", use_color)

    print()
    print(_color("  【報告時效性】", ANSI_BOLD, use_color))
    print_result(staleness_result, "分析日齡", use_color)

    # ── 彙總 ──
    counts = _count_statuses(results)
    print()
    n_pass = counts["pass"]
    n_warn = counts["warn"]
    n_fail = counts["fail"]
    n_skip = counts["skip"]
    summary_line = (
        f"  結果：{_color(f'{n_pass} 通過', ANSI_GREEN, use_color)}  "
        f"{_color(f'{n_warn} 警告', ANSI_YELLOW, use_color)}  "
        f"{_color(f'{n_fail} 失敗', ANSI_RED, use_color)}  "
        f"（{n_skip} 略過）"
    )
    print(summary_line)

    if counts["fail"] > 0:
        print(_color("\n  ⚠ 有指標差距超過容差兩倍，建議重新抓取資料後再分析。", ANSI_RED, use_color))
    elif counts["warn"] > 0:
        print(_color("\n  △ 部分指標略超容差，可能是 yfinance 更新時間差，注意留意。", ANSI_YELLOW, use_color))
    else:
        print(_color("\n  ✓ 所有可驗證指標均在容差範圍內。", ANSI_GREEN, use_color))

    print()
    return 2 if counts["fail"] > 0 else (1 if counts["warn"] > 0 else 0)


def _count_statuses(results: dict) -> dict:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for section in results.values():
        if isinstance(section, dict):
            if "status" in section:
                counts[section["status"]] = counts.get(section["status"], 0) + 1
            else:
                for item in section.values():
                    if isinstance(item, dict) and "status" in item:
                        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="驗證 integrated_report.json 關鍵數字與 yfinance 即時資料的一致性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python verify_report.py --report ./2330.tw/integrated_report.json
  python verify_report.py --report ./AAPL/integrated_report.json --tolerance 0.15
  python verify_report.py --report ./2330.tw/integrated_report.json --json
        """,
    )
    parser.add_argument("--report", "-r", required=True,
                        help="integrated_report.json 的路徑")
    parser.add_argument("--tolerance", "-t", type=float, default=None,
                        help="統一容差（0.10 = ±10%），不設則各指標用預設值")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式輸出（適合程式串接）")
    parser.add_argument("--no-color", action="store_true",
                        help="關閉 ANSI 顏色輸出")
    args = parser.parse_args()

    use_color = not args.no_color and sys.stdout.isatty()

    try:
        exit_code = run_verification(args.report, args.tolerance, use_color, args.json)
    except FileNotFoundError:
        print(f"Error: 找不到檔案 {args.report}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
