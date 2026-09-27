from pathlib import Path
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------- paths ----------
DATA_CSV = Path("csv/events.csv")
OUT_DIR = Path("dashboard/linkedin")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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


def style_cartesian_axes(fig: go.Figure, y_category: bool = False) -> None:
    axis_common = dict(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        linecolor=GRID,
        tickfont=dict(color=TEXT),
        title_font=dict(color=MUTED, size=13),
    )
    fig.update_xaxes(**axis_common)
    fig.update_yaxes(**axis_common)
    if y_category:
        fig.update_yaxes(categoryorder="total ascending", automargin=True)


def save(fig: go.Figure, name: str, **theme_kw) -> None:
    apply_theme(fig, **theme_kw)
    html_path = OUT_DIR / f"{name}.html"
    png_path = OUT_DIR / f"{name}.png"
    fig.write_html(str(html_path))
    h = theme_kw.get("height", 760)
    w = theme_kw.get("width", 1280)
    fig.write_image(str(png_path), width=w, height=h, scale=2)
    print(f"Saved {png_path}")


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
    colors = category_colors(cat["category"].tolist())
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
    colors = category_colors(cat["category"].tolist())
    summary = build_summary(cat_all)

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
        marker=dict(
            color=[colors[c] for c in cat_ev["category"]],
            line=dict(color=PLOT_BG, width=1),
        ),
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
            line=dict(color=PLOT_BG, width=1),
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
            marker=dict(
                size=size,
                color=color,
                opacity=0.88,
                line=dict(width=1.5, color=PLOT_BG),
            ),
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
            marker=dict(color=ACCENT, opacity=0.85),
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

# ---------- Chart 5: Executive dashboard (KPIs + 2×2) ----------
fig5 = make_subplots(
    rows=3,
    cols=2,
    row_heights=[0.22, 0.39, 0.39],
    column_widths=[0.58, 0.42],
    specs=[
        [{"type": "indicator"}, {"type": "indicator"}],
        [{"type": "bar"}, {"type": "bar"}],
        [{"type": "scatter"}, {"type": "pie"}],
    ],
    subplot_titles=(
        "",
        "",
        "Event count by category (top 10)",
        "Volume share (top 10)",
        "Liquidity vs volume (log–log)",
        "Event distribution (donut)",
    ),
    vertical_spacing=0.11,
    horizontal_spacing=0.12,
)

fig5.add_trace(
    go.Indicator(
        mode="number+delta",
        value=summary["events"],
        number=dict(font=dict(size=36, color=TEXT), valueformat=",", suffix=" events"),
        title=dict(text="Active events", font=dict(size=14, color=MUTED)),
        domain={"x": [0, 1], "y": [0, 1]},
    ),
    row=1,
    col=1,
)
_vol = summary["volume"]
if _vol >= 1e9:
    _vol_display, _vol_suffix = _vol / 1e9, "B"
elif _vol >= 1e6:
    _vol_display, _vol_suffix = _vol / 1e6, "M"
elif _vol >= 1e3:
    _vol_display, _vol_suffix = _vol / 1e3, "K"
else:
    _vol_display, _vol_suffix = _vol, ""
fig5.add_trace(
    go.Indicator(
        mode="number",
        value=_vol_display,
        number=dict(
            prefix="$",
            suffix=_vol_suffix,
            font=dict(size=34, color=TEXT),
            valueformat=",.2f",
        ),
        title=dict(text="Total trading volume (USD)", font=dict(size=14, color=MUTED)),
    ),
    row=1,
    col=2,
)

hero = rollup_categories(cat_all, top_n=10).sort_values("events", ascending=False)
hero_vol = hero.sort_values("total_volume", ascending=True)

fig5.add_trace(
    go.Bar(
        x=hero["category"],
        y=hero["events"],
        marker=dict(color=[colors.get(c, ACCENT) for c in hero["category"]]),
        text=[fmt_int(e) for e in hero["events"]],
        textposition="outside",
        textfont=dict(size=10),
        showlegend=False,
        hovertemplate="<b>%{x}</b><br>Events: %{y:,}<extra></extra>",
    ),
    row=2,
    col=1,
)
fig5.add_trace(
    go.Bar(
        y=hero_vol["category"],
        x=hero_vol["total_volume"],
        orientation="h",
        marker=dict(
            color=[colors.get(c, ACCENT) for c in hero_vol["category"]],
            line=dict(color=PLOT_BG, width=1),
        ),
        text=[fmt_usd(v) for v in hero_vol["total_volume"]],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=10, color="white"),
        showlegend=False,
        hovertemplate="<b>%{y}</b><br>Volume: %{customdata[0]}<extra></extra>",
        customdata=[fmt_usd(v) for v in hero_vol["total_volume"]],
    ),
    row=2,
    col=2,
)

if is_aggregated:
    for _, row in hero.iterrows():
        fig5.add_trace(
            go.Scatter(
                x=[max(row["liquidity"], 1)],
                y=[max(row["total_volume"], 1)],
                mode="markers",
                marker=dict(
                    size=max(10, row["events"] ** 0.5 * 2.2),
                    color=colors.get(row["category"], ACCENT),
                    line=dict(width=1, color=PLOT_BG),
                ),
                name=str(row["category"]),
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['category']}</b><br>"
                    f"Liquidity: {fmt_usd(row['liquidity'])}<br>"
                    f"Volume: {fmt_usd(row['total_volume'])}<br>"
                    f"Events: {row['events']:,}<extra></extra>"
                ),
            ),
            row=3,
            col=1,
        )
    fig5.add_trace(
        go.Pie(
            labels=hero["category"],
            values=hero["events"],
            hole=0.52,
            sort=False,
            direction="clockwise",
            marker=dict(colors=[colors.get(c, ACCENT) for c in hero["category"]], line=dict(color=PLOT_BG, width=2)),
            textinfo="label+percent",
            textposition="outside",
            textfont=dict(size=9),
            hovertemplate="<b>%{label}</b><br>Events: %{value:,}<br>Share: %{percent}<extra></extra>",
            showlegend=False,
        ),
        row=3,
        col=2,
    )
    for _, row in hero.nlargest(5, "total_volume").iterrows():
        fig5.add_annotation(
            x=max(row["liquidity"], 1),
            y=max(row["total_volume"], 1),
            xref="x5",
            yref="y5",
            text=row["category"],
            showarrow=True,
            arrowhead=2,
            arrowsize=0.7,
            arrowwidth=1,
            arrowcolor=MUTED,
            ax=22,
            ay=-20,
            font=dict(size=9, color=TEXT),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor=GRID,
            borderwidth=1,
        )
else:
    fig5.add_trace(
        go.Scatter(
            x=scatter["volume_24hr"].clip(lower=1),
            y=scatter["volume"].clip(lower=1),
            mode="markers",
            marker=dict(size=8, color=ACCENT, opacity=0.65),
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    closed = df["is_closed"].value_counts()
    fig5.add_trace(
        go.Pie(
            labels=["Open", "Closed"],
            values=[closed.get(False, 0), closed.get(True, 0)],
            hole=0.55,
            marker=dict(colors=["#059669", "#94A3B8"]),
            showlegend=False,
        ),
        row=3,
        col=2,
    )

fig5.update_xaxes(row=3, col=1, title_text="Liquidity (USD, log)")
fig5.update_yaxes(row=3, col=1, title_text="Volume (USD, log)")
log_usd_axis(fig5, "x", row=3, col=1)
log_usd_axis(fig5, "y", row=3, col=1)
fig5.update_xaxes(tickangle=-35, row=2, col=1, title_text="Category")
fig5.update_yaxes(row=2, col=1, title_text="Events (count)")
fig5.update_xaxes(row=2, col=2, title_text="Volume (USD, log)")
log_usd_axis(fig5, "x", row=2, col=2)

for ann in fig5.layout.annotations:
    if ann.text and ann.text not in ("", " "):
        ann.font = dict(size=13, color=MUTED)
        ann.xanchor = "left"

apply_theme(
    fig5,
    title="PolyETL · Polymarket category intelligence",
    subtitle=f"{summary['categories']} categories · {fmt_usd(summary['liquidity'])} aggregate liquidity · {REPORT_DATE}",
    height=980,
    width=1280,
    margin=dict(l=72, r=56, t=118, b=64),
    show_legend=False,
)

png_hero = OUT_DIR / "00_linkedin_hero_dashboard.png"
fig5.write_html(str(OUT_DIR / "00_linkedin_hero_dashboard.html"))
fig5.write_image(str(png_hero), width=1280, height=980, scale=2)
print(f"Saved {png_hero}")

print("\nDone! Use PNG files in dashboard/linkedin/ for LinkedIn.")
