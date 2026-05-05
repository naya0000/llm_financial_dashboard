# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A **Claude Code Skills plugin** — a multi-agent stock analysis system where 6 AI analyst agents run in parallel to produce a professional investment dashboard. The system is designed to be installed into `~/.claude/skills/` and triggered from any directory via natural language.

## Setup & Installation

```bash
# Install (copies skills to ~/.claude/skills/, installs Python deps, configures permissions)
./install.sh

# Custom output directory
./install.sh --output-dir ~/Desktop/stock-reports

# Skip interactive permission prompt
./install.sh --auto-permissions

# Uninstall
./uninstall.sh
./uninstall.sh --remove-reports   # also deletes generated reports
```

Python dependencies: `yfinance`, `pandas`, `numpy`, `requests`

```bash
pip install -r requirements.txt
```

After installation, skills live at `~/.claude/skills/` and reports output to `~/stock-reports/` (configurable).

## Running Scripts Manually

All scripts reference `{{SKILLS_DIR}}` and `{{OUTPUT_DIR}}` placeholders — these are replaced with absolute paths during `install.sh`. When running from this repo directly, substitute paths manually.

```bash
SKILLS=~/.claude/skills
OUT=~/stock-reports/tsmc

# Quick single-field lookup (fast, ~1s)
python $SKILLS/stock-data-fetcher/scripts/quick_quote.py 2330.TW --fields current_price,pe_ratio

# Quick price trend
python $SKILLS/stock-data-fetcher/scripts/quick_quote.py 2330.TW --history 2mo

# Full fetch + validate (combined, parallel API calls internally)
python $SKILLS/stock-data-fetcher/scripts/fetch_and_validate.py 2330.TW \
  --output $OUT/validated_data.json --raw-output $OUT/raw_data.json
# Exit: 0=passed, 2=hard_stop (confidence<30%), 1=error

# Quantitative metrics (run in background, parallel with agents)
python $SKILLS/stock-quant-analyst/scripts/analyze_quant.py \
  --input $OUT/validated_data.json --output $OUT/quant_analysis.json

# Assemble integrated report from synthesis.json + 6 agent JSONs
python $SKILLS/stock-integrator/scripts/assemble_report.py \
  --dir $OUT --synthesis $OUT/synthesis.json --output $OUT/integrated_report.json

# Generate HTML dashboard
python $SKILLS/stock-dashboard/scripts/generate_dashboard.py \
  --integrated $OUT/integrated_report.json \
  --validated $OUT/validated_data.json \
  --output $OUT/dashboard.html

open $OUT/dashboard.html
```

## Architecture

### Execution Pipeline (7 steps, orchestrated by `stock-orchestrator/SKILL.md`)

```
User intent → Mode classification → [Cache check] → fetch_and_validate.py
→ Tiered quality gate → 6 agents in parallel → synthesis.json (LLM)
→ assemble_report.py (Python) → generate_dashboard.py → open browser
```

**Three modes** (auto-classified from user's natural language):
- `quick_answer`: Single data point or price trend → `quick_quote.py` → reply directly. Never runs agents or dashboard.
- `selective`: 1-3 specific dimensions → only relevant agents.
- `full_analysis`: All 6 agents in parallel.

### The 6 Analyst Agents

Each agent is defined by its `SKILL.md` and writes output to `{OUTPUT_DIR}/{name}/{agent}_analysis.json` via the Write tool.

| Agent | Script | Output file | Data it receives |
|-------|--------|-------------|-----------------|
| Financial | `analyze_financial.py` | `financial_analysis.json` | `company_info` + `financial_statements` |
| Technical | `analyze_technical.py` | `technical_analysis.json` | `company_info` + `technical_indicators` + last 5 price points |
| Quantitative | `analyze_quant.py` | `quant_analysis.json` | Pre-calculated metrics from script + `company_info.beta` |
| Industry & Macro | `analyze_industry.py` | `industry_analysis.json` | `company_info` (name, sector, industry, market_cap, pe, pb, roe) |
| News Sentiment | `analyze_sentiment.py` | `sentiment_analysis.json` | Ticker + company name only — **collects news independently via WebSearch** |
| Institutional Flow | `analyze_institutional.py` | `institutional_analysis.json` | `holders` + `analyst_data` + `twse_data` + price/currency |

**Agents receive only the data they need** (data slicing). Never dump full `validated_data.json` to every agent — it's 100-230KB, with price_history being ~92%.

**CRITICAL — Parallel launch**: All active agents MUST be launched in a single response with multiple Agent tool calls. Sequential launches waste 5x time.

### Integration: Hybrid LLM + Python

The integrator is split in two:
1. **LLM writes `synthesis.json`** (~3KB): weighted scores, narrative report, cross-dimension insights, curated data limitations.
2. **`assemble_report.py`** mechanically merges synthesis + 6 agent JSONs + validated_data metrics → `integrated_report.json` (~29KB). ~4x faster than having LLM generate the full report.

### Validated Data — How to Read It

**Never use the Read tool on `validated_data.json`** — it's 100-230KB. Always extract a compact summary:

```bash
python3 -c "
import json
with open('path/to/validated_data.json') as f:
    d = json.load(f)
vd = d.get('validated_data', d)
out = {
    'validation_tier': d.get('validation_tier'),
    'overall_confidence': d.get('overall_confidence'),
    'company_info': vd.get('company_info', {}),
    'technical_indicators': vd.get('technical_indicators', {}),
    'price_history_count': len(vd.get('price_history', [])),
    'price_history_last5': vd.get('price_history', [])[-5:],
}
print(json.dumps(out, indent=2, ensure_ascii=False))
"
```

### Data Quality Gate (three tiers)

| Tier | Confidence | Action |
|------|-----------|--------|
| `hard_stop` | < 30% | Stop, report to user |
| `warning` | 30–49% | Warn and continue |
| `passed` | ≥ 50% | Proceed normally |

Taiwan stocks use market-specific thresholds (single-day change limit = 11% vs. default 20%).

### Caching

- **Dashboard-level**: If today's `dashboard.html` exists, skip entire pipeline (`full_analysis` only).
- **Agent-level**: If today's `{agent}_analysis.json` exists, skip that agent. This handles selective → full_analysis transitions efficiently.

## Ticker Formats

| Market | Format | Examples |
|--------|--------|---------|
| Taiwan TSE | `{code}.TW` | `2330.TW`, `2317.TW` |
| Taiwan OTC | `{code}.TWO` | `6547.TWO` |
| US | symbol | `AAPL`, `NVDA` |
| Japan | `{code}.T` | `4704.T` |
| Hong Kong | `{code}.HK` | `0700.HK` |

## Output Per Analysis

```
~/stock-reports/{stock_name}/
├── raw_data.json               # Yahoo Finance raw
├── validated_data.json         # Validated + quality-scored (~100-230KB)
├── {agent}_analysis.json       # 6 analyst outputs
├── synthesis.json              # LLM-generated reasoning (~3KB)
├── integrated_report.json      # Assembled final report (~29KB)
└── dashboard.html              # Self-contained HTML (Chart.js + Tailwind via CDN)
```

## Zero Hallucination Policy

All 6 agents enforce this (`shared/zero_hallucination_policy.md`):
- No training data used to fill missing fields
- All missing data listed in `data_limitations` (mandatory field, even if `[]`)
- `summary` must end with `⚠ 資料限制` section when data is incomplete
- `confidence` must drop proportionally with data gaps
- News Sentiment must only use live WebSearch results, never training knowledge

## Adding a New Analyst Agent

1. Create `stock-{name}/SKILL.md` with frontmatter (`name`, `description`) and define the output JSON format (must include `agent`, `ticker`, `score` 0-10, `confidence`, `summary`, `data_limitations`).
2. Create `stock-{name}/scripts/analyze_{name}.py` if pre-computed metrics are needed.
3. Add the agent to Step 4 in `stock-orchestrator/SKILL.md` and update the `active_analysts` list in Step 5's synthesis schema.
4. Add the agent's data slice to the agent-data mapping table in Step 4.
5. Update `install.sh`'s `SKILLS` array to include the new directory.

## Analyst Score Weights (configurable in `stock-orchestrator/SKILL.md` Step 5)

| Analyst | Weight |
|---------|--------|
| Financial | 25% |
| Technical | 20% |
| Industry & Macro | 20% |
| Institutional Flow | 15% |
| Quantitative | 10% |
| News Sentiment | 10% |
