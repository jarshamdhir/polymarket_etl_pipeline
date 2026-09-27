import re
import shutil
import tempfile
from pathlib import Path
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------- paths ----------
DATA_CSV = Path("csv/events.csv")
OUT_DIR = Path("dashboard/linkedin")
DOCS_DIR = Path("docs")
DOCS_CHARTS = DOCS_DIR / "charts"
DOCS_ASSETS = DOCS_DIR / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_CHARTS.mkdir(parents=True, exist_ok=True)
DOCS_ASSETS.mkdir(parents=True, exist_ok=True)

# ---------- design system (colorblind-safe, publication-style) ----------
BG = "#F7F9FC"
PLOT_BG = "#FFFFFF"
GRID = "#E2E8F0"
TEXT = "#1A202C"
MUTED = "#64748B"
ACCENT = "#2563EB"
PALETTE = [
    "#2563EB",
    "#DC2626",
    "#059669",
    "#D97706",
    "#7C3AED",
    "#0891B2",
    "#DB2777",
    "#4F46E5",
    "#0D9488",
    "#CA8A04",
    "#9333EA",
    "#EA580C",
]
FONT = "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
FOOTNOTE = "Source: Polymarket (Gamma API) · aggregated by category · PolyETL pipeline"
REPORT_DATE = date.today().strftime("%Y-%m-%d")
# Bump when chart HTML changes so browsers/CDNs fetch fresh assets (GitHub Pages + custom domain).
SITE_VERSION = datetime.now().strftime("%Y%m%d%H%M")

# ---------- load & clean ----------
df = pd.read_csv(DATA_CSV)
df["category"] = df["category"].fillna("Unknown").astype(str).str.strip()

numeric_cols = [
    "events",
    "total_volume",
    "volume",
    "volume_24hr",
    "volume_1wk",
    "liquidity",
    "open_interest",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

is_aggregated = (
    "events" in df.columns
    and "total_volume" in df.columns
    and "event_id" not in df.columns
)


def fmt_usd(value: float, decimals: int = 1) -> str:
    v = float(value)
    if v >= 1e9:
        return f"${v / 1e9:.{decimals}f}B"
    if v >= 1e6:
        return f"${v / 1e6:.{decimals}f}M"
    if v >= 1e3:
        return f"${v / 1e3:.{decimals}f}K"
    return f"${v:,.0f}"


def fmt_int(value: float) -> str:
    return f"{int(round(value)):,}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def category_colors(categories: list[str]) -> dict[str, str]:
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(categories)}


def rollup_categories(frame: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    """Keep top N by volume; roll remainder into one row so charts stay readable."""
    sorted_df = frame.sort_values("total_volume", ascending=False).reset_index(drop=True)
    if len(sorted_df) <= top_n:
        out = sorted_df.copy()
    else:
        head = sorted_df.head(top_n).copy()
        tail = sorted_df.iloc[top_n:]
        other = {
            "category": f"Other ({len(tail)} categories)",
            "events": tail["events"].sum(),
            "total_volume": tail["total_volume"].sum(),
            "liquidity": tail["liquidity"].sum(),
            "open_interest": tail["open_interest"].sum(),
        }
        out = pd.concat([head, pd.DataFrame([other])], ignore_index=True)
    total_vol = out["total_volume"].sum()
    total_ev = out["events"].sum()
    out["volume_share_pct"] = (out["total_volume"] / total_vol * 100) if total_vol else 0
    out["events_share_pct"] = (out["events"] / total_ev * 100) if total_ev else 0
    out["avg_volume_per_event"] = out.apply(
        lambda r: r["total_volume"] / r["events"] if r["events"] else 0, axis=1
    )
    return out


def apply_theme(
    fig: go.Figure,
    *,
    title: str,
    subtitle: str = "",
    height: int = 760,
    width: int = 1280,
    margin: dict | None = None,
    show_legend: bool = True,
    legend_title: str = "Category",
) -> None:
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:14px;color:{MUTED}'>{subtitle}</span>",
            x=0,
            xanchor="left",
            font=dict(family=FONT, size=22, color=TEXT),
        ),
        font=dict(family=FONT, size=13, color=TEXT),
        paper_bgcolor=BG,
        plot_bgcolor=PLOT_BG,
        height=height,
        width=width,
        margin=margin or dict(l=88, r=48, t=110, b=72),
        hoverlabel=dict(bgcolor=PLOT_BG, font_size=13, font_family=FONT),
        showlegend=show_legend,
    )
    if show_legend:
        fig.update_layout(
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor=GRID,
                borderwidth=1,
                font=dict(size=11, color=TEXT),
                title=dict(text=legend_title, font=dict(size=12, color=MUTED)),
            ),
        )
    fig.add_annotation(
        text=FOOTNOTE,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.12,
        showarrow=False,
        font=dict(size=11, color=MUTED),
        xanchor="left",
    )


def log_usd_axis(fig: go.Figure, axis: str = "x", row: int | None = None, col: int | None = None) -> None:
    """Readable log USD ticks (avoids Plotly's crowded default log labels)."""
    tickvals = [1e5, 1e6, 1e7, 1e8, 1e9]
    ticktext = ["$100K", "$1M", "$10M", "$100M", "$1B"]
    kwargs = dict(type="log", tickvals=tickvals, ticktext=ticktext, showgrid=True)
    if row is not None and col is not None:
        if axis == "x":
            fig.update_xaxes(**kwargs, row=row, col=col)
        else:
            fig.update_yaxes(**kwargs, row=row, col=col)
    elif axis == "x":
        fig.update_xaxes(**kwargs)
    else:
        fig.update_yaxes(**kwargs)


def smooth_bar_marker(color=None, colors=None) -> dict:
    base = dict(opacity=0.9, line=dict(width=0.6, color="rgba(255,255,255,0.9)"))
    if colors is not None:
        base["color"] = colors
    elif color is not None:
        base["color"] = color
    return base


def smooth_scatter_marker(size: float, color: str) -> dict:
    return dict(
        size=size,
        color=color,
        opacity=0.82,
        line=dict(width=2, color="rgba(255,255,255,0.95)"),
    )


def style_cartesian_axes(fig: go.Figure, y_category: bool = False) -> None:
    axis_common = dict(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=0.8,
        griddash="dot",
        zeroline=False,
        linecolor=GRID,
        tickfont=dict(color=TEXT),
        title_font=dict(color=MUTED, size=13),
    )
    fig.update_xaxes(**axis_common)
    fig.update_yaxes(**axis_common)
    if y_category:
        fig.update_yaxes(categoryorder="total ascending", automargin=True)


def compute_insights(frame: pd.DataFrame, summary: dict) -> list[str]:
    total_vol = summary["volume"]
    total_ev = summary["events"]
    ranked = frame.sort_values("total_volume", ascending=False).copy()
    ranked["vol_share"] = ranked["total_volume"] / total_vol * 100
    ranked["ev_share"] = ranked["events"] / total_ev * 100
    ranked["vol_per_event"] = ranked["total_volume"] / ranked["events"].replace(0, pd.NA)

    top3 = ranked.head(3)
    top3_vol = top3["total_volume"].sum() / total_vol * 100
    top3_names = ", ".join(top3["category"].tolist())

    by_events = ranked.sort_values("events", ascending=False).iloc[0]
    by_volume = ranked.iloc[0]
    capital = ranked.sort_values("vol_per_event", ascending=False).iloc[0]
    thin = ranked[ranked["events"] >= 50].sort_values("vol_per_event").iloc[0]

    return [
        f"Volume is concentrated: top 3 categories ({top3_names}) = {top3_vol:.0f}% of ${total_vol / 1e9:.2f}B traded.",
        f"Catalog leader {by_events['category']} ({by_events['events']:,} events, {by_events['ev_share']:.0f}% of listings) "
        f"≠ volume leader {by_volume['category']} ({by_volume['vol_share']:.0f}% of volume).",
        f"Highest capital intensity: {capital['category']} ({fmt_usd(capital['vol_per_event'], 0)} avg volume per event). "
        f"Long tail: {thin['category']} ({thin['events']:,} events, {fmt_usd(thin['vol_per_event'], 0)} per event).",
    ]


def build_hero_dashboard(
    cat_all: pd.DataFrame,
    summary: dict,
    colors: dict[str, str],
    is_aggregated: bool,
) -> go.Figure:
    """Executive view: mismatch (events vs volume), liquidity map, capital per event."""
    insights = compute_insights(cat_all, summary)
    insight_html = "<br>".join(f"• {line}" for line in insights)

    fig = make_subplots(
        rows=2,
        cols=2,
        row_heights=[0.48, 0.52],
        specs=[
            [{"colspan": 2, "type": "xy"}, None],
            [{"type": "xy"}, {"type": "xy"}],
        ],
        subplot_titles=(
            "Catalog share vs trading volume share (top 8 categories)",
            "Liquidity vs volume — bubble size = events",
            "Capital intensity (avg volume per active event)",
        ),
        vertical_spacing=0.14,
        horizontal_spacing=0.1,
    )

    focus = cat_all.nlargest(8, "total_volume").copy()
    focus["ev_share"] = focus["events"] / summary["events"] * 100
    focus["vol_share"] = focus["total_volume"] / summary["volume"] * 100
    focus = focus.sort_values("vol_share", ascending=False)

    fig.add_trace(
        go.Bar(
            name="Share of active events",
            x=focus["category"],
            y=focus["ev_share"],
            marker=smooth_bar_marker(color="#93C5FD"),
            text=[f"{v:.1f}%" for v in focus["ev_share"]],
            textposition="outside",
            textfont=dict(size=10, color=MUTED),
            hovertemplate="<b>%{x}</b><br>Events share: %{y:.1f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            name="Share of trading volume",
            x=focus["category"],
            y=focus["vol_share"],
            marker=smooth_bar_marker(color="#1D4ED8"),
            text=[f"{v:.1f}%" for v in focus["vol_share"]],
            textposition="outside",
            textfont=dict(size=10, color=TEXT),
            hovertemplate="<b>%{x}</b><br>Volume share: %{y:.1f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    scatter_df = focus.copy()
    med_liq = scatter_df["liquidity"].replace(0, pd.NA).median()
    med_vol = scatter_df["total_volume"].replace(0, pd.NA).median()
    for _, row in scatter_df.iterrows():
        size = max(14, min(56, row["events"] ** 0.55 * 3.2))
        fig.add_trace(
            go.Scatter(
                x=[max(row["liquidity"], 1)],
                y=[max(row["total_volume"], 1)],
                mode="markers",
                name=row["category"],
                marker=smooth_scatter_marker(size, colors.get(row["category"], ACCENT)),
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['category']}</b><br>"
                    f"Liquidity: {fmt_usd(row['liquidity'])}<br>"
                    f"Volume: {fmt_usd(row['total_volume'])}<br>"
                    f"Events: {row['events']:,}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    if med_liq and med_vol:
        fig.add_hline(
            y=max(med_vol, 1),
            line=dict(color="#CBD5E1", width=1, dash="dot"),
            row=2,
            col=1,
        )
        fig.add_vline(
            x=max(med_liq, 1),
            line=dict(color="#CBD5E1", width=1, dash="dot"),
            row=2,
            col=1,
        )

    for _, row in scatter_df.nlargest(4, "total_volume").iterrows():
        fig.add_annotation(
            x=max(row["liquidity"], 1),
            y=max(row["total_volume"], 1),
            xref="x2",
            yref="y2",
            text=row["category"],
            showarrow=True,
            arrowhead=2,
            arrowsize=0.65,
            arrowwidth=1,
            arrowcolor=MUTED,
            ax=24,
            ay=-22,
            font=dict(size=10, color=TEXT),
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor=GRID,
            borderwidth=1,
        )

    intensity = cat_all.nlargest(10, "total_volume").copy()
    intensity["vol_per_event"] = intensity["total_volume"] / intensity["events"].replace(0, pd.NA)
    intensity = intensity.sort_values("vol_per_event", ascending=True)

    fig.add_trace(
        go.Bar(
            y=intensity["category"],
            x=intensity["vol_per_event"],
            orientation="h",
            marker=smooth_bar_marker(
                colors=[colors.get(c, ACCENT) for c in intensity["category"]],
            ),
            text=[fmt_usd(v, 0) for v in intensity["vol_per_event"]],
            textposition="outside",
            textfont=dict(size=10, color=TEXT),
            showlegend=False,
            hovertemplate=(
                "<b>%{y}</b><br>Avg volume / event: %{customdata[0]}<br>"
                "Events: %{customdata[1]:,}<br>Total volume: %{customdata[2]}<extra></extra>"
            ),
            customdata=list(
                zip(
                    [fmt_usd(v, 0) for v in intensity["vol_per_event"]],
                    intensity["events"],
                    [fmt_usd(v) for v in intensity["total_volume"]],
                )
            ),
        ),
        row=2,
        col=2,
    )

    fig.update_layout(barmode="group", bargap=0.22, bargroupgap=0.08)
    fig.update_xaxes(tickangle=-28, row=1, col=1, title_text="Category")
    fig.update_yaxes(row=1, col=1, title_text="Share of platform (%)", ticksuffix="%")
    fig.update_xaxes(row=2, col=1, title_text="Liquidity (USD, log)")
    fig.update_yaxes(row=2, col=1, title_text="Trading volume (USD, log)")
    log_usd_axis(fig, "x", row=2, col=1)
    log_usd_axis(fig, "y", row=2, col=1)
    fig.update_xaxes(row=2, col=2, title_text="Average volume per event (USD)")
    fig.update_yaxes(row=2, col=2, title_text="")
    style_cartesian_axes(fig, y_category=True)

    for ann in fig.layout.annotations:
        if ann.text in (
            "Catalog share vs trading volume share (top 8 categories)",
            "Liquidity vs volume — bubble size = events",
            "Capital intensity (avg volume per active event)",
        ):
            ann.font = dict(size=12, color=MUTED)
            ann.xanchor = "left"

    apply_theme(
        fig,
        title="PolyETL · Executive market structure summary",
        subtitle=(
            f"{summary['categories']} categories · {fmt_int(summary['events'])} active events · "
            f"{fmt_usd(summary['volume'], 2)} total volume · {REPORT_DATE}"
        ),
        height=1120,
        width=1280,
        margin=dict(l=78, r=48, t=248, b=80),
        show_legend=True,
        legend_title="Metric",
    )
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.94,
            x=0.5,
            xanchor="center",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor=GRID,
            borderwidth=1,
        ),
    )
    fig.add_annotation(
        text=f"<b>Key insights</b><br>{insight_html}",
        xref="paper",
        yref="paper",
        x=0,
        y=0.995,
        xanchor="left",
        yanchor="top",
        showarrow=False,
        align="left",
        font=dict(size=11, color=TEXT),
        bgcolor="rgba(255,255,255,0.96)",
        bordercolor=GRID,
        borderwidth=1,
        borderpad=10,
    )
    return fig


def export_plotly_html(fig: go.Figure, path: Path) -> None:
    """Iframe-safe Plotly HTML (fixed height, no responsive reflow)."""
    fig.update_layout(autosize=False)
    height = int(fig.layout.height or 760)
    width = int(fig.layout.width or 1280)
    fig.write_html(
        str(path),
        include_plotlyjs="cdn",
        config={"responsive": False, "displayModeBar": True},
    )
    html = path.read_text(encoding="utf-8")
    html = html.replace(
        'style="height:100%; width:100%;"',
        f'style="height:{height}px; width:100%; max-width:{width}px;"',
    )
    html = html.replace(
        "html, body {height: 100%;}",
        "html, body {height: auto; margin: 0; padding: 0; background: #F7F9FC; overflow-x: auto;}",
    )
    html = html.replace('"responsive": true', '"responsive": false')
    html = html.replace('"responsive":true', '"responsive":false')
    html = re.sub(
        r'<div style="height:\d+px; width:\d+px;">',
        f'<div style="height:{height}px; width:100%; max-width:{width}px; margin:0 auto;">',
        html,
    )
    if "Cache-Control" not in html:
        html = html.replace(
            "<head>",
            '<head>\n  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />',
            1,
        )
    path.write_text(html, encoding="utf-8")


def save(fig: go.Figure, name: str, **theme_kw) -> None:
    apply_theme(fig, **theme_kw)
    h = theme_kw.get("height", 760)
    w = theme_kw.get("width", 1280)
    for html_dir in (OUT_DIR, DOCS_CHARTS):
        export_plotly_html(fig, html_dir / f"{name}.html")
    png_path = OUT_DIR / f"{name}.png"
    asset_png = DOCS_ASSETS / f"{name}.png"
    try:
        fig.write_image(str(png_path), width=w, height=h, scale=2)
    except OSError:
        # Kaleido on Windows can fail writing directly to some paths (file lock / path quirks).
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        fig.write_image(str(tmp_path), width=w, height=h, scale=2)
        shutil.copy2(tmp_path, png_path)
        tmp_path.unlink(missing_ok=True)
    shutil.copy2(png_path, asset_png)
    print(f"Saved {png_path}")


def build_github_pages_index(summary: dict) -> None:
    """Single-page dashboard for GitHub Pages (embeds all interactive charts)."""
    charts = [
        (
            "00_linkedin_hero_dashboard",
            "Executive overview",
            "Event vs volume share, liquidity map, capital intensity, and key insights.",
            1180,
        ),
        (
            "01_events_by_category",
            "Event catalog depth",
            "Active event counts and share of catalog by category.",
            820,
        ),
        (
            "02_volume_by_category",
            "Volume concentration",
            "Lifetime trading volume and share of total (log scale).",
            820,
        ),
        (
            "03_volume_scatter_bubble",
            "Liquidity vs volume",
            "Log–log view with bubble size proportional to event count.",
            820,
        ),
        (
            "04_top10_events",
            "Top categories by volume",
            "Ranked volume with event-count comparison.",
            820,
        ),
    ]

    sections = "\n".join(
        f"""
        <section class="panel" id="{slug}">
          <div class="panel-head">
            <h2>{title}</h2>
            <p>{desc}</p>
            <a class="open-chart" href="charts/{slug}.html?v={SITE_VERSION}" target="_blank" rel="noopener">Open full screen</a>
          </div>
          <iframe
            class="chart-frame"
            title="{title}"
            src="charts/{slug}.html?v={SITE_VERSION}"
            loading="lazy"
            scrolling="no"
            height="{height}"
          ></iframe>
        </section>"""
        for slug, title, desc, height in charts
    )

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <title>PolyETL · Polymarket analytics dashboard</title>
  <meta name="description" content="Interactive Polymarket category analytics built with the PolyETL pipeline." />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>" />
  <style>
    :root {{
      --bg: #f0f4f8;
      --card: #ffffff;
      --text: #1a202c;
      --muted: #64748b;
      --accent: #2563eb;
      --border: #e2e8f0;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: linear-gradient(180deg, #eef2ff 0%, var(--bg) 220px, var(--bg) 100%);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
    header.hero {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.75rem 2rem;
      box-shadow: var(--shadow);
      margin-bottom: 1.5rem;
    }}
    header.hero h1 {{ margin: 0 0 0.35rem; font-size: clamp(1.5rem, 3vw, 2rem); }}
    header.hero p {{ margin: 0; color: var(--muted); max-width: 62ch; }}
    .badges {{ margin-top: 1rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .badge {{
      font-size: 0.8rem;
      padding: 0.35rem 0.65rem;
      border-radius: 999px;
      background: #eff6ff;
      color: #1e40af;
      border: 1px solid #bfdbfe;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .kpi {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      box-shadow: var(--shadow);
    }}
    .kpi label {{ display: block; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }}
    .kpi strong {{ display: block; margin-top: 0.25rem; font-size: 1.35rem; }}
    nav.toc {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
    }}
    nav.toc a {{
      text-decoration: none;
      color: var(--accent);
      font-size: 0.9rem;
      padding: 0.4rem 0.75rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--card);
    }}
    nav.toc a:hover {{ background: #eff6ff; }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1rem 1rem 0.5rem;
      margin-bottom: 1.25rem;
      box-shadow: var(--shadow);
    }}
    .panel-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0.5rem 1rem;
      padding: 0.25rem 0.75rem 0.75rem;
      border-bottom: 1px solid var(--border);
    }}
    .panel-head h2 {{ margin: 0; font-size: 1.15rem; flex: 1 1 220px; }}
    .panel-head p {{ margin: 0; flex: 1 1 100%; color: var(--muted); font-size: 0.92rem; }}
    .open-chart {{
      font-size: 0.85rem;
      color: var(--accent);
      text-decoration: none;
      white-space: nowrap;
    }}
    .open-chart:hover {{ text-decoration: underline; }}
    .chart-frame {{
      width: 100%;
      border: 0;
      display: block;
      background: #fff;
      overflow: hidden;
    }}
    .cache-note {{
      font-size: 0.85rem;
      color: var(--muted);
      margin: 0 0 1rem;
      padding: 0.65rem 0.9rem;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 8px;
    }}
    .cache-note a {{ color: var(--accent); }}
    footer {{
      margin-top: 2rem;
      text-align: center;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    footer a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>PolyETL · Polymarket category intelligence</h1>
      <p>
        End-to-end analytics from the PolyETL pipeline: extract from Polymarket Gamma API,
        transform in Python, and visualize category-level trading activity. Data as of {REPORT_DATE}.
      </p>
      <div class="badges">
        <span class="badge">Python · Pandas · Plotly</span>
        <span class="badge">PostgreSQL · Docker</span>
        <span class="badge">Portfolio dashboard</span>
      </div>
    </header>

    <div class="kpi-grid">
      <div class="kpi"><label>Categories</label><strong>{summary["categories"]}</strong></div>
      <div class="kpi"><label>Active events</label><strong>{fmt_int(summary["events"])}</strong></div>
      <div class="kpi"><label>Total volume</label><strong>{fmt_usd(summary["volume"], 2)}</strong></div>
      <div class="kpi"><label>Aggregate liquidity</label><strong>{fmt_usd(summary["liquidity"], 2)}</strong></div>
      <div class="kpi"><label>Top category</label><strong>{summary["top_cat"]}</strong></div>
      <div class="kpi"><label>Top category share</label><strong>{fmt_pct(summary["top_vol_share"])}</strong></div>
    </div>

    <p class="cache-note">
      Dashboard build <strong>{SITE_VERSION}</strong>.
      If charts look stacked or show an old donut layout, hard-refresh
      (<kbd>Ctrl+Shift+R</kbd>) or open the
      <a href="charts/00_linkedin_hero_dashboard.html?v={SITE_VERSION}">executive chart directly</a>.
    </p>

    <nav class="toc" aria-label="Chart sections">
      <a href="#00_linkedin_hero_dashboard">Overview</a>
      <a href="#01_events_by_category">Events</a>
      <a href="#02_volume_by_category">Volume</a>
      <a href="#03_volume_scatter_bubble">Liquidity scatter</a>
      <a href="#04_top10_events">Top 10</a>
    </nav>

    {sections}

    <footer>
      {FOOTNOTE} ·
      <a href="https://github.com/jarshamdhir/polymarket_etl_pipeline">View source on GitHub</a>
    </footer>
  </div>
</body>
</html>
"""
    (DOCS_DIR / ".nojekyll").touch()
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Saved {DOCS_DIR / 'index.html'}")


def build_summary(frame: pd.DataFrame) -> dict:
    return {
        "categories": len(frame),
        "events": int(frame["events"].sum()),
        "volume": float(frame["total_volume"].sum()),
        "liquidity": float(frame["liquidity"].sum()),
        "open_interest": float(frame["open_interest"].sum()),
        "top_cat": frame.sort_values("total_volume", ascending=False).iloc[0]["category"],
        "top_vol_share": float(
            frame.sort_values("total_volume", ascending=False).iloc[0]["total_volume"]
            / frame["total_volume"].sum()
            * 100
        ),
    }


# ---------- category tables ----------
if is_aggregated:
    cat_all = df.copy()
    cat = rollup_categories(cat_all, top_n=12)
    summary = build_summary(cat_all)
else:
    cat_all = (
        df.groupby("category", as_index=False)
        .agg(
            events=("event_id", "count"),
            total_volume=("volume", "sum"),
            liquidity=("liquidity", "sum"),
            open_interest=("open_interest", "sum"),
        )
    )
    cat = rollup_categories(cat_all, top_n=12)
    summary = build_summary(cat_all)
colors = category_colors(cat_all.sort_values("total_volume", ascending=False)["category"].tolist())

subtitle_base = (
    f"Active Polymarket events · {fmt_int(summary['events'])} events · "
    f"{fmt_usd(summary['volume'])} total volume · as of {REPORT_DATE}"
)

# ---------- Chart 1: Event inventory (count) + volume share labels ----------
cat_ev = cat.sort_values("events", ascending=True)
fig1 = go.Figure()
fig1.add_trace(
    go.Bar(
        y=cat_ev["category"],
        x=cat_ev["events"],
        orientation="h",
        marker=smooth_bar_marker(colors=[colors.get(c, ACCENT) for c in cat_ev["category"]]),
        text=[
            f"{fmt_int(r.events)} events · {fmt_pct(r.events_share_pct)} of catalog"
            for r in cat_ev.itertuples()
        ],
        textposition="outside",
        textfont=dict(size=11, color=MUTED),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Events: %{x:,}<br>"
            "Volume: %{customdata[0]}<br>"
            "Share of volume: %{customdata[1]}<extra></extra>"
        ),
        customdata=list(
            zip(
                [fmt_usd(v) for v in cat_ev["total_volume"]],
                [fmt_pct(p) for p in cat_ev["volume_share_pct"]],
            )
        ),
        showlegend=False,
    )
)
fig1.update_layout(
    xaxis_title="Number of active events (count)",
    yaxis_title="",
)
style_cartesian_axes(fig1, y_category=True)
save(
    fig1,
    "01_events_by_category",
    title="Event catalog depth by category",
    subtitle=subtitle_base,
    show_legend=False,
    margin=dict(l=140, r=120, t=110, b=88),
)

# ---------- Chart 2: Volume concentration (horizontal, labeled) ----------
cat_vol = cat.sort_values("total_volume", ascending=True)
fig2 = go.Figure()
fig2.add_trace(
    go.Bar(
        y=cat_vol["category"],
        x=cat_vol["total_volume"],
        orientation="h",
        marker=dict(
            color=cat_vol["volume_share_pct"],
            colorscale=[[0, "#DBEAFE"], [0.5, "#3B82F6"], [1, "#1E3A8A"]],
            showscale=True,
            colorbar=dict(
                title="Share of<br>total volume",
                ticksuffix="%",
                len=0.75,
                thickness=14,
            ),
            line=dict(color="rgba(255,255,255,0.9)", width=0.6),
        ),
        text=[fmt_usd(v) for v in cat_vol["total_volume"]],
        textposition="outside",
        textfont=dict(size=11, color=TEXT),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Total volume: %{customdata[0]}<br>"
            "Share: %{customdata[1]}<br>"
            "Events: %{customdata[2]}<extra></extra>"
        ),
        customdata=list(
            zip(
                [fmt_usd(v) for v in cat_vol["total_volume"]],
                [fmt_pct(p) for p in cat_vol["volume_share_pct"]],
                [fmt_int(e) for e in cat_vol["events"]],
            )
        ),
        showlegend=False,
    )
)
fig2.update_layout(
    xaxis_title="Lifetime trading volume (USD, log scale)",
    yaxis_title="",
)
style_cartesian_axes(fig2, y_category=True)
log_usd_axis(fig2, "x")
save(
    fig2,
    "02_volume_by_category",
    title="Trading volume concentration by category",
    subtitle=(
        f"Top category: {summary['top_cat']} ({fmt_pct(summary['top_vol_share'])} of volume) · "
        f"{summary['categories']} categories in scope"
    ),
    show_legend=False,
    margin=dict(l=140, r=80, t=110, b=88),
)

# ---------- Chart 3: Liquidity vs volume (log-log, sized by events) ----------
if is_aggregated:
    scatter = cat.copy()
    scatter = scatter[(scatter["total_volume"] > 0) | (scatter["liquidity"] > 0)]
    scatter["label"] = scatter["category"]
    x_col, y_col = "liquidity", "total_volume"
    x_label = "Market liquidity (USD)"
    y_label = "Lifetime trading volume (USD)"
else:
    scatter = df[(df["volume"] > 0) | (df["liquidity"] > 0)].copy()
    scatter["label"] = scatter["title"].str.slice(0, 40)
    x_col, y_col = "volume_24hr", "volume"
    x_label = "24-hour trading volume (USD)"
    y_label = "Lifetime trading volume (USD)"

med_x = scatter[x_col].replace(0, pd.NA).dropna().median()
med_y = scatter[y_col].replace(0, pd.NA).dropna().median()

fig3 = go.Figure()
for _, row in scatter.iterrows():
    cat_name = row["category"] if is_aggregated else row.get("category", "Unknown")
    color = colors.get(row["label"], colors.get(cat_name, ACCENT))
    size = max(12, min(52, (row["events"] if is_aggregated else 1) ** 0.55 * 4))
    fig3.add_trace(
        go.Scatter(
            x=[max(row[x_col], 1)],
            y=[max(row[y_col], 1)],
            mode="markers",
            name=str(cat_name),
            marker=smooth_scatter_marker(size, color),
            hovertemplate=(
                f"<b>{row['label']}</b><br>"
                f"{x_label}: %{{x:,.0f}}<br>"
                f"{y_label}: %{{y:,.0f}}<br>"
                + (
                    "Events: %{customdata[0]:,}<br>"
                    "Avg volume / event: %{customdata[1]}<extra></extra>"
                    if is_aggregated
                    else "<extra></extra>"
                )
            ),
            customdata=[[row["events"], fmt_usd(row["avg_volume_per_event"])]]
            if is_aggregated
            else None,
            showlegend=is_aggregated,
        )
    )

if is_aggregated and med_x and med_y:
    fig3.add_hline(
        y=max(med_y, 1),
        line=dict(color=MUTED, width=1, dash="dot"),
        annotation_text=f"Median volume {fmt_usd(med_y)}",
        annotation_position="right",
        annotation_font=dict(size=11, color=MUTED),
    )
    fig3.add_vline(
        x=max(med_x, 1),
        line=dict(color=MUTED, width=1, dash="dot"),
        annotation_text=f"Median liquidity {fmt_usd(med_x)}",
        annotation_position="top",
        annotation_font=dict(size=11, color=MUTED),
    )

# Direct labels for high-impact categories (reduces empty quadrant clutter)
if is_aggregated:
    label_df = scatter.nlargest(6, "total_volume")
    for _, row in label_df.iterrows():
        fig3.add_annotation(
            x=max(row[x_col], 1),
            y=max(row[y_col], 1),
            text=row["category"],
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowwidth=1,
            arrowcolor=MUTED,
            ax=30,
            ay=-28,
            font=dict(size=11, color=TEXT),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor=GRID,
            borderwidth=1,
        )

fig3.update_layout(
    xaxis_title=f"{x_label} (log scale)",
    yaxis_title=f"{y_label} (log scale)",
)
style_cartesian_axes(fig3)
log_usd_axis(fig3, "x")
log_usd_axis(fig3, "y")
save(
    fig3,
    "03_volume_scatter_bubble",
    title="Liquidity vs trading volume",
    subtitle="Bubble area ∝ event count · log scales expose long-tail categories",
    margin=dict(l=88, r=240, t=110, b=88),
    legend_title="Category",
)

# ---------- Chart 4: Top 10 — volume bar + event count markers ----------
if is_aggregated:
    top10 = cat_all.nlargest(10, "total_volume").copy()
    top10 = top10.sort_values("total_volume", ascending=True)
    top10["bar_label"] = [
        f"{fmt_usd(r.total_volume)} ({fmt_pct(r.total_volume / summary['volume'] * 100)})"
        for r in top10.itertuples()
    ]
    fig4 = go.Figure()
    fig4.add_trace(
        go.Bar(
            y=top10["category"],
            x=top10["total_volume"],
            orientation="h",
            name="Total volume",
            marker=smooth_bar_marker(color=ACCENT),
            text=top10["bar_label"],
            textposition="outside",
            textfont=dict(size=11),
            hovertemplate="<b>%{y}</b><br>Volume: %{customdata[0]}<br>Events: %{customdata[1]}<extra></extra>",
            customdata=list(zip([fmt_usd(v) for v in top10["total_volume"]], top10["events"])),
        )
    )
    fig4.add_trace(
        go.Scatter(
            y=top10["category"],
            x=top10["events"] * (top10["total_volume"].max() / max(top10["events"].max(), 1)) * 0.12,
            mode="markers+text",
            name="Event count (scaled)",
            marker=dict(symbol="circle", size=10, color="#059669", line=dict(width=1, color=PLOT_BG)),
            text=[fmt_int(e) for e in top10["events"]],
            textposition="middle right",
            textfont=dict(size=10, color="#059669"),
            hovertemplate="Events: %{customdata[0]:,}<extra></extra>",
            customdata=top10["events"],
        )
    )
    fig4.update_layout(xaxis_title="Total trading volume (USD, log scale)")
    log_usd_axis(fig4, "x")
    chart4_title = "Top 10 categories by trading volume"
    chart4_sub = "Bars = volume · green markers = active event count (scaled for comparison)"
else:
    top10 = df.nlargest(10, "volume").copy()
    top10["title_short"] = top10["title"].str.slice(0, 55)
    top10 = top10.sort_values("volume", ascending=True)
    fig4 = px.bar(
        top10,
        x="volume",
        y="title_short",
        orientation="h",
        color="category",
        color_discrete_map=colors,
        labels={"volume": "Total volume (USD)", "title_short": ""},
    )
    chart4_title = "Top 10 events by trading volume"
    chart4_sub = subtitle_base

style_cartesian_axes(fig4, y_category=True)
save(
    fig4,
    "04_top10_events",
    title=chart4_title,
    subtitle=chart4_sub,
    margin=dict(l=160, r=160, t=110, b=88),
)

# ---------- Chart 5: Executive dashboard (insight-led) ----------
fig5 = build_hero_dashboard(cat_all, summary, colors, is_aggregated)

hero_name = "00_linkedin_hero_dashboard"
png_hero = OUT_DIR / f"{hero_name}.png"
for html_dir in (OUT_DIR, DOCS_CHARTS):
    export_plotly_html(fig5, html_dir / f"{hero_name}.html")
try:
    fig5.write_image(str(png_hero), width=1280, height=1080, scale=2)
except OSError:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    fig5.write_image(str(tmp_path), width=1280, height=1080, scale=2)
    shutil.copy2(tmp_path, png_hero)
    tmp_path.unlink(missing_ok=True)
shutil.copy2(png_hero, DOCS_ASSETS / f"{hero_name}.png")
print(f"Saved {png_hero}")

build_github_pages_index(summary)

print("\nDone!")
print(f"  LinkedIn PNGs: {OUT_DIR}/")
print(f"  GitHub Pages:  {DOCS_DIR}/index.html")
print("  Live URL:      https://jarshamdhir.github.io/polymarket_etl_pipeline/")
