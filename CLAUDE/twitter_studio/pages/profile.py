"""Profile analysis page."""

from __future__ import annotations

import asyncio
import re
from collections import Counter

import pandas as pd
import streamlit as st

from services.tweet_service import map_tweets, map_user
from twikit_client.client import twitter_client
from utils.charts import (
    engagement_over_time,
    hourly_distribution,
    sentiment_pie,
    tweet_volume_histogram,
    top_hashtags_bar,
)
from utils.export_helper import export_filename, to_csv_bytes, to_excel_bytes, tweets_to_dataframe
from utils.tweet_card import tweet_feed

_STOP_EN = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "i", "my", "this", "that", "was", "are",
    "be", "have", "has", "had", "do", "did", "will", "would", "could",
    "not", "no", "so", "if", "as", "by", "from", "we", "you", "they",
    "he", "she", "rt", "amp",
}
_STOP_ES = {
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "a", "y",
    "que", "es", "con", "por", "para", "al", "se", "le", "su", "me",
    "lo", "te", "no", "si", "pero", "más", "ya", "como", "mi", "rt",
}
STOPWORDS = _STOP_EN | _STOP_ES


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_profile(username: str):
    raw_user = asyncio.run(twitter_client.get_user_by_screen_name(username))
    if raw_user is None:
        return None, []
    user = map_user(raw_user)
    raw_tweets = asyncio.run(
        twitter_client.get_user_tweets(str(raw_user.id), tweet_type="Tweets", count=100)
    )
    tweets = map_tweets(raw_tweets)
    return user, tweets


def _top_words(tweets, n: int = 20) -> list[tuple[str, int]]:
    words: list[str] = []
    for t in tweets:
        text = re.sub(r"https?://\S+", "", t.text)
        text = re.sub(r"[^a-záéíóúñA-ZÁÉÍÓÚÑ\s]", " ", text)
        for w in text.lower().split():
            if len(w) > 3 and w not in STOPWORDS and not w.startswith(("#", "@")):
                words.append(w)
    return Counter(words).most_common(n)


def render() -> None:
    st.markdown("## 👤 Análisis de perfiles")
    st.markdown("---")

    with st.form("profile_form"):
        username_input = st.text_input("@usuario", placeholder="@elonmusk")
        submitted = st.form_submit_button("Analizar perfil", use_container_width=True)

    if not submitted:
        st.info("Introduce un @usuario y pulsa Analizar.")
        return

    clean = username_input.lstrip("@").strip()
    if not clean:
        st.error("Introduce un nombre de usuario válido.")
        return

    with st.spinner(f"Cargando perfil de @{clean}..."):
        user, tweets = _fetch_profile(clean)

    if user is None:
        st.error(f"No se encontró el usuario @{clean}.")
        return

    # ---- Profile header ---------------------------------------------------
    if user.banner_url:
        st.image(user.banner_url, use_container_width=True)

    col_av, col_info = st.columns([1, 5])
    with col_av:
        if user.avatar_url:
            st.image(user.avatar_url, width=100)
    with col_info:
        v = " ✓" if (user.is_verified or user.is_blue_verified) else ""
        st.markdown(
            f"## {user.name}{v}  \n"
            f"<span style='color:#8b949e;'>@{user.username}</span>",
            unsafe_allow_html=True,
        )
        if user.description:
            st.markdown(user.description)
        meta_parts = []
        if user.location:
            meta_parts.append(f"📍 {user.location}")
        if user.url:
            meta_parts.append(f"🔗 [{user.url}]({user.url})")
        if user.created_at:
            meta_parts.append(f"📅 Desde {user.created_at.strftime('%B %Y')}")
        if meta_parts:
            st.caption("  ·  ".join(meta_parts))

    st.markdown("---")

    # ---- Metrics ----------------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Seguidores", f"{user.followers_count:,}")
    m2.metric("Seguidos", f"{user.following_count:,}")
    m3.metric("Tweets", f"{user.tweet_count:,}")
    m4.metric("Listas", f"{user.listed_count:,}")

    if not tweets:
        st.warning("No se encontraron tweets para este perfil.")
        return

    df = tweets_to_dataframe(tweets)

    st.markdown("---")

    # ---- Stats row --------------------------------------------------------
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Likes (media)", f"{df['likes'].mean():.1f}")
    s2.metric("Retweets (media)", f"{df['retweets'].mean():.1f}")
    s3.metric("Replies (media)", f"{df['replies'].mean():.1f}")
    avg_len = df["texto"].str.len().mean()
    s4.metric("Long. media tweet", f"{avg_len:.0f} chars")

    # ---- Charts -----------------------------------------------------------
    st.markdown("---")
    tabs = st.tabs(["Volumen", "Engagement", "Por hora", "Sentimiento", "Hashtags"])
    with tabs[0]:
        st.plotly_chart(tweet_volume_histogram(df), use_container_width=True)
    with tabs[1]:
        st.plotly_chart(engagement_over_time(df), use_container_width=True)
    with tabs[2]:
        st.plotly_chart(hourly_distribution(df), use_container_width=True)
    with tabs[3]:
        st.plotly_chart(sentiment_pie(df), use_container_width=True)
    with tabs[4]:
        st.plotly_chart(top_hashtags_bar(df), use_container_width=True)

    # ---- Top words --------------------------------------------------------
    st.markdown("---")
    st.markdown("### Palabras más utilizadas")
    top_words = _top_words(tweets)
    if top_words:
        wdf = pd.DataFrame(top_words, columns=["Palabra", "Frecuencia"])
        col_t, col_b = st.columns([2, 3])
        with col_t:
            st.dataframe(wdf, use_container_width=True, hide_index=True)
        with col_b:
            import plotly.express as px
            fig = px.bar(
                wdf.head(15), x="Frecuencia", y="Palabra",
                orientation="h",
                color_discrete_sequence=["#58a6ff"],
            )
            fig.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
                font=dict(color="#c9d1d9"), margin=dict(l=8, r=8, t=8, b=8),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ---- Tweet list -------------------------------------------------------
    st.markdown("---")
    st.markdown("### Últimos tweets")
    tweet_feed(tweets, max_items=50)

    # ---- Export -----------------------------------------------------------
    st.markdown("---")
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "📥 CSV",
            data=to_csv_bytes(df),
            file_name=export_filename(f"perfil_{clean}", "csv"),
            mime="text/csv",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "📥 Excel",
            data=to_excel_bytes(df),
            file_name=export_filename(f"perfil_{clean}", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
