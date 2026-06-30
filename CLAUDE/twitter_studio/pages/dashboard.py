"""Dashboard — overview of the authenticated user's own account."""

from __future__ import annotations

import asyncio

import streamlit as st

from services.tweet_service import map_tweets
from twikit_client.client import twitter_client, run
from utils.charts import (
    engagement_over_time,
    hourly_distribution,
    sentiment_pie,
    tweet_volume_histogram,
)
from utils.export_helper import tweets_to_dataframe
from utils.tweet_card import tweet_feed


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_tweets(pages: int) -> list:
    try:
        me = twitter_client.me
        if me is None:
            return []
        raw = run(
            twitter_client.get_user_tweets(str(me.id), tweet_type="Tweets", pages=pages)
        )
        return map_tweets(raw)
    except Exception:
        return []


def render() -> None:
    user = st.session_state.get("current_user")
    if user is None:
        st.warning("No se pudo cargar la información del usuario.")
        return

    # ---- Header -----------------------------------------------------------
    col_av, col_info, col_metrics = st.columns([1, 4, 2])

    with col_av:
        if user.avatar_url:
            st.image(user.avatar_url, width=80)

    with col_info:
        v = " ✓" if (getattr(user, "is_verified", False) or getattr(user, "is_blue_verified", False)) else ""
        st.markdown(
            f"**{user.name}{v}**  \n"
            f"<span style='color:#8b949e;'>@{user.username}</span>",
            unsafe_allow_html=True,
        )
        if user.description:
            st.caption(user.description)
        if user.location:
            st.caption(f"📍 {user.location}")

    with col_metrics:
        r1, r2, r3 = st.columns(3)
        r1.metric("Seguidores", f"{user.followers_count:,}")
        r2.metric("Siguiendo", f"{user.following_count:,}")
        r3.metric("Tweets", f"{user.tweet_count:,}")

    st.write("")

    # ---- Pagination control -----------------------------------------------
    if "dashboard_pages" not in st.session_state:
        st.session_state.dashboard_pages = 1

    col_title, col_more = st.columns([4, 1])
    with col_title:
        st.markdown("#### Actividad reciente")
    with col_more:
        if st.button("Cargar más", use_container_width=True):
            st.session_state.dashboard_pages += 1
            st.cache_data.clear()

    pages = st.session_state.dashboard_pages

    with st.spinner("Cargando tweets..."):
        tweets = _fetch_tweets(pages)

    if not tweets:
        st.info("No se encontraron tweets recientes.")
        return

    df = tweets_to_dataframe(tweets)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Tweets cargados", len(tweets))
    s2.metric("Likes (media)", f"{df['likes'].mean():.1f}")
    s3.metric("Retweets (media)", f"{df['retweets'].mean():.1f}")
    s4.metric("Replies (media)", f"{df['replies'].mean():.1f}")

    st.write("")

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

    st.write("")
    st.markdown(f"#### Tweets ({len(tweets)})")
    tweet_feed(tweets)
