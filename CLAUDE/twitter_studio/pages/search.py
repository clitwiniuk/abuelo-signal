"""Advanced search page."""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from services.tweet_service import map_tweets
from twikit_client.client import twitter_client
from utils.charts import engagement_over_time, sentiment_pie, top_hashtags_bar
from utils.export_helper import export_filename, to_csv_bytes, to_excel_bytes, tweets_to_dataframe
from utils.tweet_card import tweet_feed


def _build_query(
    text: str,
    language: str,
    date_from: str,
    date_to: str,
    only_images: bool,
    only_videos: bool,
    only_verified: bool,
    exclude_replies: bool,
    exclude_retweets: bool,
) -> str:
    parts = [text.strip()]
    if language and language != "Todos":
        parts.append(f"lang:{language}")
    if date_from:
        parts.append(f"since:{date_from}")
    if date_to:
        parts.append(f"until:{date_to}")
    if only_images:
        parts.append("filter:images")
    if only_videos:
        parts.append("filter:videos")
    if only_verified:
        parts.append("filter:verified")
    if exclude_replies:
        parts.append("-filter:replies")
    if exclude_retweets:
        parts.append("-filter:retweets")
    return " ".join(p for p in parts if p)


def _render_user_search() -> None:
    """Search tweets from a specific user."""
    with st.form("user_search_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            username_input = st.text_input("@usuario", placeholder="@elonmusk")
        with col2:
            max_results = st.number_input("Máx. tweets", min_value=10, max_value=500, value=100, step=10)
        order = st.selectbox("Orden", ["Tweets", "TweetsAndReplies", "Media"])
        submitted = st.form_submit_button("🔍 Buscar tweets del usuario", use_container_width=True)

    if not submitted:
        st.info("Introduce un @usuario para ver sus últimos tweets.")
        return

    clean = username_input.lstrip("@").strip()
    if not clean:
        st.error("Introduce un nombre de usuario válido.")
        return

    with st.spinner(f"Cargando tweets de @{clean}..."):
        try:
            raw_user = asyncio.run(twitter_client.get_user_by_screen_name(clean))
        except Exception as e:
            st.error(f"Error buscando usuario: {e}")
            return

    if raw_user is None:
        st.error(f"No se encontró el usuario @{clean}.")
        return

    with st.spinner("Descargando tweets..."):
        try:
            raw = asyncio.run(
                twitter_client.get_user_tweets(str(raw_user.id), tweet_type=order, count=int(max_results))
            )
        except Exception as e:
            st.error(f"Error descargando tweets: {e}")
            return

    if not raw:
        st.warning("No se encontraron tweets.")
        return

    tweets = map_tweets(raw)
    df = tweets_to_dataframe(tweets)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Tweets", len(tweets))
    s2.metric("Likes totales", int(df["likes"].sum()))
    s3.metric("Retweets totales", int(df["retweets"].sum()))
    s4.metric("Replies totales", int(df["replies"].sum()))

    st.markdown("---")
    tab_eng, tab_sent, tab_hash = st.tabs(["Engagement", "Sentimiento", "Hashtags"])
    with tab_eng:
        st.plotly_chart(engagement_over_time(df), use_container_width=True)
    with tab_sent:
        st.plotly_chart(sentiment_pie(df), use_container_width=True)
    with tab_hash:
        st.plotly_chart(top_hashtags_bar(df), use_container_width=True)

    st.markdown("---")
    st.markdown(f"### Tweets de @{clean}")
    tweet_feed(tweets)

    st.markdown("---")
    e1, e2 = st.columns(2)
    with e1:
        st.download_button("📥 CSV", data=to_csv_bytes(df),
                           file_name=export_filename(f"usuario_{clean}", "csv"),
                           mime="text/csv", use_container_width=True)
    with e2:
        st.download_button("📥 Excel", data=to_excel_bytes(df),
                           file_name=export_filename(f"usuario_{clean}", "xlsx"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)


def render() -> None:
    st.markdown("## 🔍 Búsqueda")
    st.markdown("---")

    tab_keyword, tab_user = st.tabs(["Por texto / hashtag", "Por usuario"])

    with tab_user:
        _render_user_search()

    with tab_keyword:
        _render_keyword_search()


def _render_keyword_search() -> None:
    # ---- Search form ------------------------------------------------------
    with st.form("search_form"):
        query_text = st.text_input("Texto o hashtag", placeholder="#smallcaps $AAPL earnings")

        col1, col2, col3 = st.columns(3)
        with col1:
            language = st.selectbox(
                "Idioma",
                ["Todos", "es", "en", "fr", "de", "it", "pt"],
            )
            order = st.selectbox("Orden", ["Latest", "Top"])
        with col2:
            date_from = st.date_input("Desde", value=None)
            date_to = st.date_input("Hasta", value=None)
        with col3:
            max_results = st.number_input("Máx. resultados", min_value=10, max_value=500, value=50, step=10)

        st.markdown("**Filtros**")
        f1, f2, f3, f4, f5 = st.columns(5)
        only_images = f1.checkbox("Solo imágenes")
        only_videos = f2.checkbox("Solo vídeos")
        only_verified = f3.checkbox("Solo verificadas")
        exclude_replies = f4.checkbox("Excluir replies")
        exclude_retweets = f5.checkbox("Excluir retweets")

        submitted = st.form_submit_button("🔍 Buscar", use_container_width=True)

    if not submitted:
        st.info("Introduce un término de búsqueda y pulsa Buscar.")
        return

    if not query_text.strip():
        st.error("El campo de búsqueda no puede estar vacío.")
        return

    query = _build_query(
        text=query_text,
        language=language,
        date_from=str(date_from) if date_from else "",
        date_to=str(date_to) if date_to else "",
        only_images=only_images,
        only_videos=only_videos,
        only_verified=only_verified,
        exclude_replies=exclude_replies,
        exclude_retweets=exclude_retweets,
    )

    st.caption(f"Query enviada: `{query}`")

    progress = st.progress(0, text="Buscando tweets...")
    with st.spinner(""):
        raw = asyncio.run(
            twitter_client.search_tweets_paginated(
                query=query,
                product=order,
                max_results=int(max_results),
            )
        )
    progress.progress(100, text=f"✅ {len(raw)} tweets obtenidos")

    if not raw:
        st.warning("No se encontraron resultados para esta búsqueda.")
        return

    tweets = map_tweets(raw)
    df = tweets_to_dataframe(tweets)

    # ---- Stats summary ----------------------------------------------------
    st.markdown("---")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Tweets", len(tweets))
    s2.metric("Likes totales", int(df["likes"].sum()))
    s3.metric("Retweets totales", int(df["retweets"].sum()))
    s4.metric("Usuarios únicos", df["usuario"].nunique())
    s5.metric("Idiomas", df["idioma"].nunique())

    # ---- Charts -----------------------------------------------------------
    st.markdown("---")
    tab_eng, tab_sent, tab_hash = st.tabs(["Engagement", "Sentimiento", "Hashtags"])
    with tab_eng:
        st.plotly_chart(engagement_over_time(df), use_container_width=True)
    with tab_sent:
        st.plotly_chart(sentiment_pie(df), use_container_width=True)
    with tab_hash:
        st.plotly_chart(top_hashtags_bar(df), use_container_width=True)

    # ---- Results table ----------------------------------------------------
    st.markdown("---")
    st.markdown(f"### Resultados ({len(tweets)} tweets)")
    tweet_feed(tweets)

    # ---- Export -----------------------------------------------------------
    st.markdown("---")
    st.markdown("### Exportar")
    exp1, exp2 = st.columns(2)
    with exp1:
        st.download_button(
            "📥 Exportar CSV",
            data=to_csv_bytes(df),
            file_name=export_filename("busqueda", "csv"),
            mime="text/csv",
            use_container_width=True,
        )
    with exp2:
        st.download_button(
            "📥 Exportar Excel",
            data=to_excel_bytes(df),
            file_name=export_filename("busqueda", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
