---
name: stock-dashboard
description: Dashboard 視覺化報告 Agent。將 integrated_report.json 轉化為富邦風格專業互動式 HTML 儀表板。由 Orchestrator 的最後步驟自動觸發，執行 generate_dashboard.py 腳本。當使用者說「產生報告」、「做 Dashboard」、「視覺化結果」時也可單獨觸發。
---

# Dashboard Generator — 富邦理財助理（個股分析）

Generates a professional, Fubon-style HTML dashboard from analysis results.

## Design Style

- **UI 風格**: 富邦銀行專業商業化設計（白底、Navy 主色 #003366、clean cards、無動畫）
- **品牌**: 富邦證券 logo（base64 內嵌）+ 「富邦理財助理」標題 + 「個股分析」副標
- **語言**: 中文為主、英文為輔（section 標題、report heading 皆中英並列）
- **分析師頭貼**: 6 位分析師各有獨立 avatar 圖片（base64 內嵌，圓形裁切）
- **Sparkline**: Header 公司名稱旁顯示近 60 天股價走勢迷你圖（SVG，漲綠跌紅）
- **導航**: Sticky header + 6 項中文 nav，scroll-margin-top 120px 防遮擋
- **Radar Chart**: Chart.js 六維雷達圖，Navy 填充
- **Print friendly**: @media print 支援

## Assets

```
stock-dashboard/
├── assets/
│   ├── fubon-logo.png          # 富邦證券 logo
│   └── avatars/
│       ├── financial.png       # 財務分析師
│       ├── technical.png       # 技術分析師
│       ├── quant.png           # 量化分析師
│       ├── industry.png        # 產業總經分析師
│       ├── sentiment.png       # 新聞情緒分析師
│       └── institutional.png   # 法人籌碼分析師
├── scripts/
│   └── generate_dashboard.py
└── SKILL.md
```

## Usage

Typically triggered automatically by the orchestrator as the final step. Can also be triggered manually:

```bash
python {{SKILLS_DIR}}/stock-dashboard/scripts/generate_dashboard.py \
  --integrated {{OUTPUT_DIR}}/{name}/integrated_report.json \
  --validated {{OUTPUT_DIR}}/{name}/validated_data.json \
  --output {{OUTPUT_DIR}}/{name}/dashboard.html
```

Then open the HTML file in a browser:
```bash
open {{OUTPUT_DIR}}/{name}/dashboard.html
```

## Expected Input Format

### integrated_report.json

Supports two schema variants (auto-detected):

**New format (preferred):**
- `metadata` → `ticker`, `company_name`, `analysis_date`
- `overall_score` (0-10)
- `weighted_scores` → dict with `raw_score` per dimension (`financial`, `technical`, `quant`, `industry`, `sentiment`, `institutional`)
- `individual_analyses` → dict with `score`, `confidence`, `summary` per analyst
- `narrative_report` → `investment_summary`, `fundamental_analysis`, `technical_analysis`, `risk_factors`, `investment_recommendation`
- `one_line_summary` — displayed in overview card

**Legacy format:**
- `stock_info` → `ticker`, `company_name`
- `dimension_scores` (0-10 each), `analysts` dict, `metrics` dict

### validated_data.json

- `validated_data.company_info` → `pe_ratio`, `pb_ratio`, `eps`, `return_on_equity`, `dividend_yield`, `debt_to_equity`
- `validated_data.price_history[]` → `date`, `close`, `volume` (used for header sparkline; last 60 points)

## Dashboard Sections

| Nav | Section ID | Content |
|-----|-----------|---------|
| 投資評等 | `#overview` | Score circle + rating badge + summary + confidence |
| 多維分析 | `#dimensions` | Radar chart + 6 dimension score cards |
| 財務指標 | `#metrics` | 3x2 grid: PE, PB, EPS, ROE, Dividend Yield, Debt Ratio |
| 分析師觀點 | `#analysts` | Accordion with avatar, score bar, expandable summary |
| 研究報告 | `#report` | 5 blocks: 投資摘要 / 基本面 / 技術面 / 風險 / 投資建議 |
| 風險聲明 | `#risk` | Chinese legal disclaimer |

## Sparkline Behavior

- Extracts `close` prices from `validated_data.price_history`
- Takes last 60 data points
- Renders SVG polyline in header next to company name
- Shows latest price + percentage change badge
- Green (#00805a) if up, red (#c0392b) if down
- Graceful fallback: hidden when no price data available
