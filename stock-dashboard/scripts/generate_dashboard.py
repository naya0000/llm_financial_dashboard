#!/usr/bin/env python3
"""
Stock Dashboard Generator
Transforms integrated analysis results into a professional HTML dashboard.
"""

import json
import argparse
import base64
from datetime import datetime
from pathlib import Path


def load_json(filepath):
    """Load JSON file safely."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {filepath}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {filepath}: {e}")


def get_rating_color(score):
    """Get color and label for a score."""
    if score >= 7.0:
        return '#00805a', 'buy', '買入', 'BUY'
    elif score >= 5.0:
        return '#b8860b', 'hold', '持有', 'HOLD'
    else:
        return '#c0392b', 'sell', '賣出', 'SELL'


def normalize_score(score, max_val=10):
    """Normalize score to 0-100 scale."""
    return min(100, max(0, (score / max_val) * 100))


def get_score_color(score):
    """Get color based on normalized score."""
    if score >= 70:
        return '#00805a'
    elif score >= 50:
        return '#b8860b'
    else:
        return '#c0392b'


# --- Base64 asset cache (computed once per process, reused across calls) ---
_base64_cache = {}

def _load_and_cache_base64(cache_key: str, file_path: Path) -> str:
    """Load a file as base64 data URI, with in-memory caching."""
    if cache_key in _base64_cache:
        return _base64_cache[cache_key]
    if file_path.exists():
        b64 = base64.b64encode(file_path.read_bytes()).decode('utf-8')
        result = f'data:image/png;base64,{b64}'
    else:
        result = ''
    _base64_cache[cache_key] = result
    return result


def load_logo_base64():
    """Load logo as base64 data URI (cached)."""
    logo_path = Path(__file__).parent.parent / 'assets' / 'logo.png'
    return _load_and_cache_base64('logo', logo_path)


# Map analyst keys to avatar filenames
_AVATAR_MAP = {
    'financial_analyst': 'financial',
    'technical_analyst': 'technical',
    'quantitative_analyst': 'quant',
    'industry_macro': 'industry',
    'news_sentiment': 'sentiment',
    'institutional_flow': 'institutional',
}

def load_avatar_base64(name):
    """Load analyst avatar as base64 data URI (cached)."""
    filename = _AVATAR_MAP.get(name, name)
    avatar_path = Path(__file__).parent.parent / 'assets' / 'avatars' / f'{filename}.png'
    return _load_and_cache_base64(f'avatar_{filename}', avatar_path)


def generate_sparkline_svg(prices, width=120, height=32):
    """Generate an inline SVG sparkline from price data."""
    if not prices or len(prices) < 2:
        return ''
    min_p, max_p = min(prices), max(prices)
    price_range = max_p - min_p if max_p != min_p else 1
    n = len(prices)
    points = []
    for i, p in enumerate(prices):
        x = (i / (n - 1)) * width
        y = height - ((p - min_p) / price_range) * (height - 4) - 2
        points.append(f'{x:.1f},{y:.1f}')
    polyline = ' '.join(points)
    # Color: green if last > first, red if down
    color = '#00805a' if prices[-1] >= prices[0] else '#c0392b'
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def generate_html_dashboard(integrated_report, validated_data):
    """Generate complete HTML dashboard from analysis data."""

    logo_uri = load_logo_base64()

    # Detect analysis mode (selective vs full)
    mode = integrated_report.get('mode', 'full_analysis')
    active_analysts = integrated_report.get('active_analysts', None)
    is_selective = mode == 'selective' and active_analysts is not None

    # Support both old and new JSON structures
    metadata = integrated_report.get('metadata', {})
    stock_info = integrated_report.get('stock_info', metadata)
    overall_score = integrated_report.get('overall_score', 5.0)
    confidence = integrated_report.get('confidence_level', 'Medium')
    summary = integrated_report.get('summary', integrated_report.get('one_line_summary', 'No summary available'))
    analysis_date = integrated_report.get('analysis_date', metadata.get('analysis_date', datetime.now().strftime('%Y-%m-%d')))

    ticker = stock_info.get('ticker', metadata.get('ticker', 'UNKNOWN'))
    company_name = stock_info.get('company_name', metadata.get('company_name', 'Unknown Company'))

    # Analysts: support both 'analysts' and 'individual_analyses'
    analysts = integrated_report.get('analysts', integrated_report.get('individual_analyses', {}))

    # Scores: support both 'dimension_scores' and 'weighted_scores'
    raw_scores = integrated_report.get('dimension_scores', {})
    if not raw_scores:
        ws = integrated_report.get('weighted_scores', {})
        raw_scores = {k: v.get('raw_score', 50) / 10 for k, v in ws.items()}

    # Normalize key names
    score_key_map = {'financial': 'fundamental', 'quant': 'quantitative', 'institutional': 'fund_flow'}
    scores = {}
    for k, v in raw_scores.items():
        mapped = score_key_map.get(k, k)
        scores[mapped] = v

    # Metrics: prefer from integrated_report, fallback to validated_data.validated_data.company_info
    metrics = integrated_report.get('metrics', {})
    if not metrics or all(v == 'N/A' for v in metrics.values()):
        ci = validated_data.get('validated_data', {}).get('company_info', {})
        roe_raw = ci.get('return_on_equity')
        dy_raw = ci.get('dividend_yield')
        dte_raw = ci.get('debt_to_equity')
        metrics = {
            'pe_ratio': ci.get('pe_ratio', 'N/A'),
            'pb_ratio': ci.get('pb_ratio', 'N/A'),
            'eps': ci.get('eps', 'N/A'),
            'roe': f"{roe_raw*100:.1f}%" if roe_raw else 'N/A',
            'dividend_yield': f"{dy_raw:.2f}%" if dy_raw else 'N/A',
            'debt_ratio': f"{dte_raw:.1f}%" if dte_raw else 'N/A',
        }

    # Extract price history for sparkline
    price_history = validated_data.get('validated_data', {}).get('price_history', [])
    if not price_history:
        price_history = validated_data.get('price_history', [])
    close_prices = []
    for p in price_history:
        if isinstance(p, dict) and p.get('close') is not None:
            close_prices.append(float(p['close']))
    # Take last 60 data points for sparkline
    sparkline_data = close_prices[-60:] if close_prices else []
    sparkline_svg = generate_sparkline_svg(sparkline_data)

    # Price change info for sparkline badge
    if sparkline_data and len(sparkline_data) >= 2:
        last_price = sparkline_data[-1]
        first_price = sparkline_data[0]
        pct_change = ((last_price - first_price) / first_price) * 100
        spark_price_str = f'{last_price:,.2f}'
        spark_sign = '+' if pct_change >= 0 else ''
        spark_change_str = f'{spark_sign}{pct_change:.1f}%'
        spark_class = 'spark-up' if pct_change >= 0 else 'spark-down'
    else:
        spark_price_str = ''
        spark_change_str = ''
        spark_class = ''

    rating_color, rating_class, rating_cn, rating_en = get_rating_color(overall_score)

    # Map analyst names to dimension keys
    analyst_to_dim = {
        'financial_analyst': 'fundamental',
        'technical_analyst': 'technical',
        'quantitative_analyst': 'quantitative',
        'industry_macro': 'industry',
        'news_sentiment': 'sentiment',
        'institutional_flow': 'fund_flow',
    }

    all_dims = ['fundamental', 'technical', 'quantitative', 'industry', 'sentiment', 'fund_flow']

    if is_selective:
        active_dims = set(analyst_to_dim.get(a, a) for a in active_analysts)
        radar_data = {d: normalize_score(scores.get(d, 0)) for d in all_dims if d in active_dims}
    else:
        radar_data = {d: normalize_score(scores.get(d, 5.0)) for d in all_dims}

    # Build analyst views HTML
    analyst_views_html = ""
    analyst_labels = {
        'financial': ('財務分析師', 'Financial Analyst'),
        'financial_analyst': ('財務分析師', 'Financial Analyst'),
        'technical': ('技術分析師', 'Technical Analyst'),
        'technical_analyst': ('技術分析師', 'Technical Analyst'),
        'quant': ('量化分析師', 'Quantitative Analyst'),
        'quantitative_analyst': ('量化分析師', 'Quantitative Analyst'),
        'industry': ('產業總經分析師', 'Industry & Macro Analyst'),
        'industry_macro': ('產業總經分析師', 'Industry & Macro Analyst'),
        'sentiment': ('新聞情緒分析師', 'News Sentiment Analyst'),
        'news_sentiment': ('新聞情緒分析師', 'News Sentiment Analyst'),
        'institutional': ('法人籌碼分析師', 'Institutional Flow Analyst'),
        'institutional_flow': ('法人籌碼分析師', 'Institutional Flow Analyst'),
    }
    for analyst_name, analyst_data in analysts.items():
        analyst_score = analyst_data.get('score', 5.0)
        analyst_conf = analyst_data.get('confidence', 'Medium')
        analyst_summary = analyst_data.get('summary', 'No summary available')
        score_color = get_score_color(normalize_score(analyst_score))
        label_zh, label_en = analyst_labels.get(analyst_name, (analyst_name, analyst_name))
        avatar_uri = load_avatar_base64(analyst_name)

        # Render summary: split on \n\n for paragraphs, \n for line breaks
        paragraphs = analyst_summary.split('\n\n')
        summary_html = ''.join(
            f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs if p.strip()
        )

        # Build sources HTML for news_sentiment analyst
        sources_html = ""
        if analyst_name == 'news_sentiment':
            sources = analyst_data.get('sources', [])
            if sources:
                sources_items = ""
                for src in sources:
                    title = src.get('title', '未知標題')
                    url = src.get('url', '#')
                    publisher = src.get('publisher', '未知來源')
                    date = src.get('date', '')
                    date_str = f' ({date})' if date else ''
                    sources_items += f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a><span class="source-meta"> — {publisher}{date_str}</span></li>'
                sources_html = f'<div class="analyst-sources"><div class="sources-title">參考來源 Sources ({len(sources)})</div><ul>{sources_items}</ul></div>'

        analyst_views_html += f"""
        <div class="analyst-row">
            <div class="analyst-header" onclick="toggleAnalyst(this.parentNode)">
                <div class="analyst-left">
                    <div class="analyst-avatar"><img src="{avatar_uri}" alt="{label_zh}"></div>
                    <div>
                        <div class="analyst-name">{label_zh} <span style="color:#888;font-size:12px;font-weight:400">{label_en}</span></div>
                        <div class="analyst-conf">信心水準: {analyst_conf}</div>
                    </div>
                </div>
                <div class="analyst-right">
                    <div class="analyst-score" style="color:{score_color}">{analyst_score:.1f}</div>
                    <div class="analyst-bar-wrap">
                        <div class="analyst-bar" style="width:{normalize_score(analyst_score)}%;background:{score_color}"></div>
                    </div>
                    <span class="analyst-arrow">+</span>
                </div>
            </div>
            <div class="analyst-detail"><div class="analyst-summary">{summary_html}</div>{sources_html}</div>
        </div>"""

    # Build financial metrics
    metric_items = [
        ('PE Ratio', '本益比', metrics.get('pe_ratio', 'N/A')),
        ('PB Ratio', '股價淨值比', metrics.get('pb_ratio', 'N/A')),
        ('EPS', '每股盈餘', metrics.get('eps', 'N/A')),
        ('ROE', '股東權益報酬率', metrics.get('roe', 'N/A')),
        ('Dividend Yield', '殖利率', metrics.get('dividend_yield', 'N/A')),
        ('Debt Ratio', '負債比', metrics.get('debt_ratio', 'N/A')),
    ]

    metrics_html = ""
    for en_label, cn_label, value in metric_items:
        metrics_html += f"""
        <div class="metric-cell">
            <div class="metric-label">{cn_label}<span class="metric-label-en">{en_label}</span></div>
            <div class="metric-value">{value}</div>
        </div>"""

    # Build narrative report
    narrative = integrated_report.get('narrative_report', {})
    # Build dimension cards and radar chart data dynamically
    dim_labels = {
        'fundamental': ('財務分析', 'Fundamental'),
        'technical': ('技術分析', 'Technical'),
        'quantitative': ('量化分析', 'Quantitative'),
        'industry': ('產業總經', 'Industry'),
        'sentiment': ('情緒分析', 'Sentiment'),
        'fund_flow': ('籌碼分析', 'Fund Flow'),
    }

    dim_cards_html = ""
    radar_labels_js = []
    radar_values_js = []
    for dim_key in all_dims:
        if dim_key not in radar_data:
            continue
        val = radar_data[dim_key]
        cn, en = dim_labels[dim_key]
        dim_cards_html += f'<div class="dim-card"><div class="dim-score" style="color:{get_score_color(val)}">{val:.0f}</div><div class="dim-label">{cn}</div><div class="dim-label-en">{en}</div></div>'
        radar_labels_js.append(f"'{cn}'")
        radar_values_js.append(f"{val:.1f}")

    dim_count = len(radar_labels_js)
    dim_grid_cols = 'repeat(2,1fr)' if dim_count >= 2 else '1fr'

    # Selective mode badge (shown in header)
    selective_badge_html = ""
    if is_selective:
        analyst_cn_names = {
            'financial_analyst': '財務', 'technical_analyst': '技術', 'quantitative_analyst': '量化',
            'industry_macro': '產業', 'news_sentiment': '情緒', 'institutional_flow': '籌碼',
        }
        active_names = ' / '.join(analyst_cn_names.get(a, a) for a in active_analysts)
        selective_badge_html = f'<span style="display:inline-block;margin-left:12px;padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;color:#fff;background:#b8860b;vertical-align:middle">精選分析：{active_names}</span>'

    # Build narrative report blocks dynamically — only include sections that exist
    narrative_sections = [
        ('investment_summary', '投資摘要 Investment Summary', 'var(--navy)'),
        ('fundamental_analysis', '基本面分析 Fundamental Analysis', 'var(--navy)'),
        ('technical_analysis', '技術面分析 Technical Analysis', 'var(--navy)'),
        ('risk_factors', '風險因素 Risk Factors', 'var(--navy)'),
        ('investment_recommendation', '投資建議 Recommendation', 'var(--navy)'),
    ]
    narrative_blocks_html = ""
    for key, heading, color in narrative_sections:
        text = narrative.get(key)
        if text:
            narrative_blocks_html += f'<div class="report-block"><div class="report-heading" style="border-left-color:{color}">{heading}</div><div class="report-text">{text}</div></div>'

    # Build data limitations section
    data_limitations = integrated_report.get('data_limitations', [])
    narrative_limitations = narrative.get('data_limitations', '')
    limitations_html = ""
    if data_limitations or narrative_limitations:
        items_html = ""
        if narrative_limitations:
            items_html += f'<p style="margin-bottom:12px">{narrative_limitations}</p>'
        if data_limitations:
            items_html += '<ul style="margin:0;padding-left:20px">'
            for item in data_limitations:
                items_html += f'<li style="margin-bottom:4px;font-size:13px;color:var(--g600)">{item}</li>'
            items_html += '</ul>'
        limitations_html = f"""
                <div class="report-block"><div class="report-heading" style="border-left-color:var(--amber);color:var(--amber)">&#9888; 資料限制 Data Limitations</div><div class="report-text">{items_html}</div></div>"""

    # Pre-build chart section HTML and JS (avoids nested f-string issues in Python 3.9)
    labels_js = ",".join(radar_labels_js)
    values_js = ",".join(radar_values_js)

    if dim_count >= 3:
        # Radar chart
        chart_html = (
            f'<div class="radar-wrap">'
            f'<div class="radar-container"><canvas id="radarChart"></canvas></div>'
            f'<div style="display:grid;grid-template-columns:{dim_grid_cols};gap:12px">'
            f'{dim_cards_html}</div></div>'
        )
        chart_js = (
            f"var ctx=document.getElementById('radarChart').getContext('2d');"
            f"new Chart(ctx,{{type:'radar',data:{{labels:[{labels_js}],"
            f"datasets:[{{label:'Score',data:[{values_js}],"
            f"borderColor:'#003366',backgroundColor:'rgba(0,51,102,0.08)',fill:true,"
            f"pointBackgroundColor:'#003366',pointBorderColor:'#fff',pointBorderWidth:2,"
            f"borderWidth:2,pointRadius:4,pointHoverRadius:6}}]}},"
            f"options:{{responsive:true,maintainAspectRatio:false,"
            f"plugins:{{legend:{{display:false}}}},"
            f"scales:{{r:{{beginAtZero:true,max:100,"
            f"ticks:{{color:'#adb5bd',stepSize:20,backdropColor:'transparent',font:{{size:10}}}},"
            f"grid:{{color:'#dee2e6'}},angleLines:{{color:'#dee2e6'}},"
            f"pointLabels:{{color:'#495057',font:{{size:12,weight:'600'}}}}}}}}}}}});"
        )
    else:
        # Horizontal bar chart for < 3 dimensions
        bar_colors = ",".join(
            f"'{get_score_color(float(v))}'" for v in radar_values_js
        )
        chart_height = 60 * dim_count + 40
        chart_html = (
            f'<div style="max-width:480px;margin:0 auto">'
            f'<canvas id="barChart" height="{chart_height}"></canvas></div>'
            f'<div style="display:grid;grid-template-columns:{dim_grid_cols};gap:12px;margin-top:20px">'
            f'{dim_cards_html}</div>'
        )
        chart_js = (
            f"var bctx=document.getElementById('barChart').getContext('2d');"
            f"var barColors=[{bar_colors}];"
            f"new Chart(bctx,{{type:'bar',data:{{labels:[{labels_js}],"
            f"datasets:[{{data:[{values_js}],backgroundColor:barColors,"
            f"borderColor:barColors,borderWidth:1,borderRadius:4,barThickness:28}}]}},"
            f"options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,"
            f"plugins:{{legend:{{display:false}}}},"
            f"scales:{{x:{{beginAtZero:true,max:100,"
            f"ticks:{{color:'#adb5bd',stepSize:20,font:{{size:11}}}},"
            f"grid:{{color:'#e9ecef'}}}},"
            f"y:{{ticks:{{color:'#495057',font:{{size:13,weight:'600'}}}},"
            f"grid:{{display:false}}}}}}}}}});"
        )

    # Nav label for dimensions section
    nav_dim_label = "精選分析" if is_selective else "多維分析"
    dim_section_title = "精選分析" if is_selective else "多維度分析"
    dim_section_title_en = "Selective Analysis" if is_selective else "Six-Dimension Scoring"

    conf_map = {
        'Very High': 95, 'High': 85, 'Medium-High': 75,
        'Medium': 65, 'Medium-Low': 50, 'Low': 35, 'Very Low': 20
    }
    conf_pct = conf_map.get(confidence, 65)
    overall_display = normalize_score(overall_score)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ticker} | Stock Analysis Report</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
        :root {{
            --navy:#003366;--navy-dark:#002244;--green:#00805a;--red:#c0392b;--amber:#b8860b;
            --g50:#f8f9fa;--g100:#f1f3f5;--g200:#e9ecef;--g300:#dee2e6;--g400:#adb5bd;
            --g500:#868e96;--g600:#495057;--g700:#343a40;--white:#fff;--border:#d5dce6;
        }}
        *{{margin:0;padding:0;box-sizing:border-box}}
        html{{scroll-behavior:smooth}}
        body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei","Noto Sans TC",sans-serif;background:var(--g50);color:var(--g700);line-height:1.6;-webkit-font-smoothing:antialiased}}

        .header{{background:var(--navy);color:var(--white);position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,51,102,.25)}}
        .header-inner{{max-width:1120px;margin:0 auto;padding:0 24px}}
        .header-top{{display:flex;align-items:center;justify-content:space-between;padding:18px 0 10px}}
        .brand{{display:flex;align-items:center;gap:14px}}
        .brand-logo{{flex-shrink:0;line-height:0}}
        .brand-logo img{{height:32px;width:auto;display:block}}
        .brand-divider{{width:1px;height:24px;background:rgba(255,255,255,.25);flex-shrink:0}}
        .brand-text{{display:flex;align-items:baseline;gap:6px}}
        .brand-name{{font-size:20px;font-weight:700;letter-spacing:1px}}
        .brand-sub{{font-size:13px;font-weight:400;opacity:.6;letter-spacing:.5px}}
        .header-date{{font-size:12px;opacity:.6;letter-spacing:.3px}}
        .header-stock{{display:flex;align-items:center;gap:12px;padding:2px 0 14px}}
        .stock-name{{font-size:20px;font-weight:700;letter-spacing:.3px}}
        .stock-ticker{{font-size:13px;opacity:.55;font-weight:400}}
        .sparkline-wrap{{display:flex;align-items:center;gap:8px;margin-left:4px;padding:3px 10px;background:rgba(255,255,255,.08);border-radius:4px}}
        .sparkline-wrap .spark-price{{font-size:12px;opacity:.7;font-weight:500;white-space:nowrap}}
        .sparkline-wrap .spark-change{{font-size:11px;font-weight:600;padding:1px 6px;border-radius:3px}}
        .spark-up{{color:#4ade80;background:rgba(74,222,128,.12)}}
        .spark-down{{color:#f87171;background:rgba(248,113,113,.12)}}

        .nav{{background:var(--navy-dark)}}
        .nav-inner{{max-width:1120px;margin:0 auto;padding:0 24px;display:flex;overflow-x:auto}}
        .nav-inner::-webkit-scrollbar{{display:none}}
        .nav a{{display:block;padding:10px 16px;color:rgba(255,255,255,.65);text-decoration:none;font-size:13px;font-weight:500;white-space:nowrap;border-bottom:2px solid transparent;transition:color .2s,border-color .2s}}
        .nav a:hover{{color:var(--white);border-bottom-color:var(--green)}}

        .main{{max-width:1120px;margin:0 auto;padding:32px 24px 48px}}
        .section{{margin-bottom:28px;scroll-margin-top:120px}}
        .section-title{{font-size:16px;font-weight:700;color:var(--navy);padding-bottom:10px;margin-bottom:16px;border-bottom:2px solid var(--navy);display:flex;align-items:baseline;gap:8px}}
        .section-title-en{{font-size:12px;font-weight:400;color:var(--g400)}}

        .card{{background:var(--white);border:1px solid var(--border);border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
        .card-body{{padding:24px}}

        .overview-grid{{display:grid;grid-template-columns:200px 1fr;gap:32px;align-items:start}}
        @media(max-width:768px){{.overview-grid{{grid-template-columns:1fr}}}}
        .score-circle{{width:160px;height:160px;border-radius:50%;border:6px solid {rating_color};display:flex;flex-direction:column;align-items:center;justify-content:center;margin:0 auto}}
        .score-number{{font-size:42px;font-weight:800;color:{rating_color};line-height:1}}
        .score-label{{font-size:12px;color:var(--g500);margin-top:4px}}
        .rating-badge{{display:inline-block;margin-top:12px;padding:4px 16px;border-radius:4px;font-size:13px;font-weight:700;color:var(--white);background:{rating_color}}}
        .overview-info{{display:flex;flex-direction:column;gap:16px}}
        .overview-summary{{font-size:15px;color:var(--g600);line-height:1.7}}
        .overview-meta{{display:flex;gap:32px;flex-wrap:wrap}}
        .meta-item{{display:flex;flex-direction:column;gap:4px}}
        .meta-label{{font-size:11px;color:var(--g400);text-transform:uppercase;letter-spacing:.5px}}
        .meta-value{{font-size:14px;font-weight:600;color:var(--g700)}}
        .confidence-track{{width:120px;height:6px;background:var(--g200);border-radius:3px;overflow:hidden}}
        .confidence-fill{{height:100%;background:var(--navy);border-radius:3px}}

        .radar-wrap{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center}}
        @media(max-width:768px){{.radar-wrap{{grid-template-columns:1fr}}}}
        .radar-container{{position:relative;height:320px}}
        .dim-card{{text-align:center;padding:16px 8px;border-radius:6px;background:var(--g50);border:1px solid var(--g200)}}
        .dim-score{{font-size:28px;font-weight:700;line-height:1.2}}
        .dim-label{{font-size:12px;color:var(--g500);margin-top:4px}}
        .dim-label-en{{font-size:10px;color:var(--g400)}}

        .metrics-grid{{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
        @media(max-width:768px){{.metrics-grid{{grid-template-columns:repeat(2,1fr)}}}}
        .metric-cell{{padding:20px;border-right:1px solid var(--g200);border-bottom:1px solid var(--g200);background:var(--white)}}
        .metric-cell:nth-child(3n){{border-right:none}}
        .metric-cell:nth-last-child(-n+3){{border-bottom:none}}
        .metric-label{{font-size:13px;color:var(--g500);margin-bottom:6px}}
        .metric-label-en{{font-size:11px;color:var(--g400);margin-left:6px}}
        .metric-value{{font-size:24px;font-weight:700;color:var(--navy)}}

        .analyst-row{{border-bottom:1px solid var(--g200);cursor:pointer}}
        .analyst-row:last-child{{border-bottom:none}}
        .analyst-header{{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;transition:background .15s}}
        .analyst-header:hover{{background:var(--g50)}}
        .analyst-left{{display:flex;align-items:center;gap:12px}}
        .analyst-icon{{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--white);font-weight:700;font-size:14px;flex-shrink:0}}
        .analyst-avatar{{width:44px;height:44px;flex-shrink:0;border-radius:50%;overflow:hidden;border:2px solid var(--g200)}}
        .analyst-avatar img{{width:100%;height:100%;object-fit:cover;display:block}}
        .analyst-name{{font-size:14px;font-weight:600;color:var(--g700)}}
        .analyst-conf{{font-size:11px;color:var(--g400)}}
        .analyst-right{{display:flex;align-items:center;gap:12px}}
        .analyst-score{{font-size:20px;font-weight:700;min-width:40px;text-align:right}}
        .analyst-bar-wrap{{width:80px;height:6px;background:var(--g200);border-radius:3px;overflow:hidden}}
        .analyst-bar{{height:100%;border-radius:3px}}
        .analyst-arrow{{font-size:14px;color:var(--g400);width:20px;text-align:center}}
        .analyst-detail{{max-height:0;overflow:hidden;transition:max-height .3s ease}}
        .analyst-detail.open{{max-height:5000px}}
        .analyst-summary{{padding:16px 20px 8px 68px}}
        .analyst-summary p{{font-size:13px;color:var(--g600);line-height:1.8;margin-bottom:12px}}
        .analyst-summary p:last-child{{margin-bottom:16px}}
        .analyst-sources{{padding:0 20px 16px 68px}}
        .sources-title{{font-size:12px;font-weight:700;color:var(--navy);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--g200)}}
        .analyst-sources ul{{list-style:none;padding:0;margin:0}}
        .analyst-sources li{{font-size:12px;line-height:1.6;padding:3px 0;border-bottom:1px dotted var(--g200)}}
        .analyst-sources li:last-child{{border-bottom:none}}
        .analyst-sources a{{color:var(--navy);text-decoration:none}}
        .analyst-sources a:hover{{text-decoration:underline;color:var(--green)}}
        .source-meta{{color:var(--g400);font-size:11px}}

        .report-block{{margin-bottom:24px}}
        .report-block:last-child{{margin-bottom:0}}
        .report-heading{{font-size:14px;font-weight:700;color:var(--navy);padding:8px 12px;background:var(--g50);border-left:3px solid var(--navy);margin-bottom:12px}}
        .report-text{{font-size:14px;color:var(--g600);line-height:1.8;padding-left:16px}}

        .disclaimer{{background:var(--g100);border:1px solid var(--g300);border-radius:8px;padding:24px}}
        .disclaimer-title{{font-size:13px;font-weight:700;color:var(--red);margin-bottom:8px}}
        .disclaimer p{{font-size:12px;color:var(--g500);line-height:1.7;margin-bottom:8px}}
        .disclaimer p:last-child{{margin-bottom:0}}

        .footer{{max-width:1120px;margin:0 auto;padding:24px 24px 40px;text-align:center;font-size:12px;color:var(--g400);border-top:1px solid var(--g200);letter-spacing:.3px}}
        .footer-brand{{font-weight:700;color:var(--navy);font-size:13px}}
        @media print{{.header{{position:relative}}.nav{{display:none}}.card{{break-inside:avoid}}}}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-inner">
            <div class="header-top">
                <div class="brand">
                    <div class="brand-logo"><img src="{logo_uri}" alt="Logo"></div>
                    <div class="brand-divider"></div>
                    <div class="brand-text"><span class="brand-name">理財助理</span><span class="brand-sub">個股分析</span></div>
                </div>
                <div class="header-date">分析日期 {analysis_date}</div>
            </div>
            <div class="header-stock">
                <span class="stock-name">{company_name}</span>
                <span class="stock-ticker">{ticker}</span>{selective_badge_html}
                {"" if not sparkline_svg else f'''<div class="sparkline-wrap"><span style="font-size:10px;opacity:.45;margin-right:2px">近3月</span>{sparkline_svg}<span class="spark-price">{spark_price_str}</span><span class="spark-change {spark_class}">{spark_change_str}</span></div>'''}
            </div>
        </div>
    </div>

    <div class="nav">
        <div class="nav-inner">
            <a href="#overview">投資評等</a>
            <a href="#dimensions">{nav_dim_label}</a>
            <a href="#metrics">財務指標</a>
            <a href="#analysts">分析師觀點</a>
            <a href="#report">研究報告</a>
            <a href="#risk">風險聲明</a>
        </div>
    </div>

    <div class="main">
        <section id="overview" class="section">
            <div class="section-title">投資評等<span class="section-title-en">Investment Rating</span></div>
            <div class="card"><div class="card-body">
                <div class="overview-grid">
                    <div style="text-align:center">
                        <div class="score-circle">
                            <div class="score-number">{overall_display:.0f}</div>
                            <div class="score-label">/ 100</div>
                        </div>
                        <div class="rating-badge">{rating_cn} {rating_en}</div>
                    </div>
                    <div class="overview-info">
                        <div class="overview-summary">{summary}</div>
                        <div class="overview-meta">
                            <div class="meta-item">
                                <span class="meta-label">綜合評分</span>
                                <span class="meta-value">{overall_score:.1f} / 10</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">信心度</span>
                                <div style="display:flex;align-items:center;gap:8px">
                                    <div class="confidence-track"><div class="confidence-fill" style="width:{conf_pct}%"></div></div>
                                    <span class="meta-value">{confidence}</span>
                                </div>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">分析日期</span>
                                <span class="meta-value">{analysis_date}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div></div>
        </section>

        <section id="dimensions" class="section">
            <div class="section-title">{dim_section_title}<span class="section-title-en">{dim_section_title_en}</span></div>
            <div class="card"><div class="card-body">
                {chart_html}
            </div></div>
        </section>

        <section id="metrics" class="section">
            <div class="section-title">財務指標<span class="section-title-en">Financial Metrics</span></div>
            <div class="metrics-grid">{metrics_html}</div>
        </section>

        <section id="analysts" class="section">
            <div class="section-title">分析師觀點<span class="section-title-en">Analyst Views</span></div>
            <div class="card" style="overflow:hidden">{analyst_views_html}</div>
        </section>

        <section id="report" class="section">
            <div class="section-title">詳細研究報告<span class="section-title-en">Research Report</span></div>
            <div class="card"><div class="card-body">
                {narrative_blocks_html}{limitations_html}
            </div></div>
        </section>

        <section id="risk" class="section">
            <div class="disclaimer">
                <div class="disclaimer-title">風險聲明 Risk Disclosure</div>
                <p>本報告由 AI 智能分析系統自動生成，僅供參考，不構成任何投資建議或推薦。股票投資存在風險，包括但不限於市場風險、流動性風險、政策風險等。過往表現不代表未來結果，投資者應根據自身風險承受能力獨立判斷，並於投資前諮詢專業財務顧問。</p>
                <p>本報告所涉資料來自公開市場資訊與計算模型，經交叉驗證但仍可能存在延遲或偏差，實際結果可能與預測存在重大差異。報告生成方對因使用本報告資訊而導致之任何損失不承擔責任。</p>
            </div>
        </section>
    </div>

    <div class="footer">
        <span class="footer-brand">富邦理財助理</span> 個股分析
        &middot; 報告生成時間 {datetime.now().strftime('%Y-%m-%d %H:%M')}
        &middot; AI 智能分析系統
    </div>

    <script>
        function toggleAnalyst(row){{var d=row.querySelector('.analyst-detail'),a=row.querySelector('.analyst-arrow');if(d.classList.contains('open')){{d.classList.remove('open');a.textContent='+'}}else{{d.classList.add('open');a.textContent='\u2212'}}}}
        {chart_js}
    </script>
</body>
</html>"""

    return html_content


def main():
    parser = argparse.ArgumentParser(description='Generate HTML stock analysis dashboard')
    parser.add_argument('--integrated', required=True, help='Path to integrated_report.json')
    parser.add_argument('--validated', required=True, help='Path to validated_data.json')
    parser.add_argument('--output', default='dashboard.html', help='Output HTML file path')

    args = parser.parse_args()

    print(f"Loading integrated report from: {args.integrated}")
    integrated_report = load_json(args.integrated)

    print(f"Loading validated data from: {args.validated}")
    validated_data = load_json(args.validated)

    print("Generating HTML dashboard...")
    html_content = generate_html_dashboard(integrated_report, validated_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Dashboard generated successfully: {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"  Open in browser: file://{output_path.absolute()}")


if __name__ == '__main__':
    main()
