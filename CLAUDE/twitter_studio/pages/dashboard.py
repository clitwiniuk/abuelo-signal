"""Dashboard page — account overview + recent activity + stats."""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from services.tweet_service import map_tweets
from twikit_client.client import twitter_client
from utils.charts import (
    engagement_over_time,
    hourly_distribution,
    sentiment_pie,
    tweet_volume_histogram,
)
from utils.export_helper import tweets_to_dataframe
from utils.tweet_card import tweet_feed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _metric_card(label: str, value: str, delta: str = "") -> None:
    delta_html = f"<div style='color:#3fb950;font-size:0.8rem;'>{delta}</div>" if delta else ""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_recent_tweets() -> list:
    """Fetch user's last 50 tweets (cached 5 min)."""
    try:
        me = twitter_client.me
        if me is None:
            return []
        raw = asyncio.run(
            twitter_client.get_user_tweets(str(me.id), tweet_type="Tweets", count=50)
        )
        return map_tweets(raw)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render() -> None:
    user = st.session_state.get("current_user")
    if user is None:
        st.warning("No se pudo cargar la información del usuario.")
        return

    # ---- Header -----------------------------------------------------------
    col_avatar, col_info = st.columns([1, 6])
    with col_avatar:
        if user.avatar_url:
            st.image(user.avatar_url, width=80)
    with col_info:
        verified_badge = " ✓" if (user.is_verified or user.is_blue_verified) else ""
        st.markdown(
            f"## {user.name}{verified_badge}  \n"
            f"<span style='color:#8b949e;'>@{user.username}</span>",
            unsafe_allow_html=True,
        )
        if user.description:
            st.caption(user.description)
        if user.location:
            st.caption(f"📍 {user.location}")

    st.markdown("---")

    # ---- Metrics ----------------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _metric_card("Seguidores", f"{user.followers_count:,}")
    with m2:
        _metric_card("Seguidos", f"{user.following_count:,}")
    with m3:
        _metric_card("Tweets", f"{user.tweet_count:,}")
    with m4:
        _metric_card("Miembro desde", user.created_at.strftime("%b %Y") if user.created_at else "—")

    st.markdown("---")

    # ---- Recent tweets ----------------------------------------------------
    st.markdown("### Actividad reciente")
    with st.spinner("Cargando tweets recientes..."):
        tweets = _fetch_recent_tweets()

    if not tweets:
        st.info("No se encontraron tweets recientes.")
        return

    df = tweets_to_dataframe(tweets)

    # Quick stats row
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        _metric_card("Tweets cargados", str(len(tweets)))
    with s2:
        _metric_card("Likes (media)", f"{df['likes'].mean():.1f}")
    with s3:
        _metric_card("Retweets (media)", f"{df['retweets'].mean():.1f}")
    with s4:
        _metric_card("Replies (media)", f"{df['replies'].mean():.1f}")

    st.markdown("---")

    # ---- Charts -----------------------------------------------------------
    tab_vol, tab_eng, tab_hour, tab_sent = st.tabs(
        ["Volumen", "Engagement", "Por hora", "Sentimiento"]
    )
    with tab_vol:
        st.plotly_chart(tweet_volume_histogram(df), use_container_width=True)
    with tab_eng:
        st.plotly_chart(engagement_over_time(df), use_container_width=True)
    with tab_hour:
        st.plotly_chart(hourly_distribution(df), use_container_width=True)
    with tab_sent:
        st.plotly_chart(sentiment_pie(df), use_container_width=True)

    st.markdown("---")

    # ---- Tweet list -------------------------------------------------------
    st.markdown("### Últimos tweets")
    tweet_feed(tweets, max_items=20)
