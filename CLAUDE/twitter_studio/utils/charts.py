"""Plotly chart builders — all return go.Figure, never show()."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_DARK_BG = "#0d1117"
_CARD_BG = "#161b22"
_ACCENT = "#58a6ff"
_TEXT = "#c9d1d9"

_LAYOUT = dict(
    paper_bgcolor=_DARK_BG,
    plot_bgcolor=_CARD_BG,
    font=dict(color=_TEXT, family="Inter, sans-serif"),
    margin=dict(l=16, r=16, t=32, b=16),
)


def engagement_over_time(df: pd.DataFrame) -> go.Figure:
    """Line chart: likes/retweets/replies per day."""
    if df.empty or "fecha" not in df.columns:
        return _empty_fig("Sin datos")
    tmp = df.copy()
    tmp["day"] = pd.to_datetime(tmp["fecha"], errors="coerce").dt.date
    agg = tmp.groupby("day")[["likes", "replies", "retweets"]].sum().reset_index()
    fig = go.Figure()
    for col, color in [("likes", "#58a6ff"), ("retweets", "#3fb950"), ("replies", "#d29922")]:
        fig.add_trace(go.Scatter(
            x=agg["day"], y=agg[col], name=col.capitalize(),
            mode="lines+markers", line=dict(color=color, width=2),
        ))
    fig.update_layout(title="Engagement por día", **_LAYOUT)
    return fig


def sentiment_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty or "sentimiento" not in df.columns:
        return _empty_fig("Sin datos de sentimiento")
    counts = df["sentimiento"].value_counts()
    colors = {"positive": "#3fb950", "neutral": "#58a6ff", "negative": "#f85149"}
    fig = go.Figure(go.Pie(
        labels=counts.index,
        values=counts.values,
        marker=dict(colors=[colors.get(l, _ACCENT) for l in counts.index]),
        hole=0.45,
    ))
    fig.update_layout(title="Distribución de sentimiento", **_LAYOUT)
    return fig


def top_hashtags_bar(df: pd.DataFrame, n: int = 15) -> go.Figure:
    if df.empty or "hashtags" not in df.columns:
        return _empty_fig("Sin hashtags")
    all_tags: list[str] = []
    for row in df["hashtags"].dropna():
        all_tags.extend([t.strip().lower() for t in str(row).split(",") if t.strip()])
    if not all_tags:
        return _empty_fig("Sin hashtags")
    counts = Counter(all_tags).most_common(n)
    tags, vals = zip(*counts)
    fig = go.Figure(go.Bar(
        x=list(vals), y=list(tags), orientation="h",
        marker_color=_ACCENT,
    ))
    fig.update_layout(
        title=f"Top {n} hashtags",
        yaxis=dict(autorange="reversed"),
        **_LAYOUT,
    )
    return fig


def tweet_volume_histogram(df: pd.DataFrame) -> go.Figure:
    if df.empty or "fecha" not in df.columns:
        return _empty_fig("Sin datos")
    dates = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    counts = dates.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color=_ACCENT))
    fig.update_layout(title="Volumen de tweets por día", **_LAYOUT)
    return fig


def hourly_distribution(df: pd.DataFrame) -> go.Figure:
    if df.empty or "fecha" not in df.columns:
        return _empty_fig("Sin datos")
    hours = pd.to_datetime(df["fecha"], errors="coerce").dt.hour
    counts = hours.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color="#d29922"))
    fig.update_layout(
        title="Publicaciones por hora del día",
        xaxis=dict(tickmode="linear", dtick=1),
        **_LAYOUT,
    )
    return fig


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, showarrow=False, font=dict(size=14, color=_TEXT))
    fig.update_layout(**_LAYOUT)
    return fig
