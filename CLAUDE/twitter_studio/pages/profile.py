"""Profile analysis page."""

from __future__ import annotations

import asyncio
import re
from collections import Counter

import pandas as pd
import streamlit as st

from services.tweet_service import map_tweets, map_user
from services import watchlist_service as wl
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
def _fetch_profile(username: str, pages: int = 1):
    raw_user = asyncio.get_event_loop().run_until_complete(twitter_client.get_user_by_screen_name(username))
    if raw_user is None:
        return None, []
    user = map_user(raw_user)
    raw_tweets = asyncio.get_event_loop().run_until_complete(
        twitter_client.get_user_tweets(str(raw_user.id), tweet_type="Tweets", pages=pages)
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


def _render_watchlist_panel() -> str | None:
    """Render the saved profiles panel. Returns username to load if clicked."""
    watched = wl.load()

    st.markdown(
        "<div class='nav-section-label' style='padding:0 0 8px 0;'>Perfiles guardados</div>",
        unsafe_allow_html=True,
    )

    if not watched:
        st.caption("Aún no has guardado ningún perfil.")
    else:
        for u in watched:
            col_info, col_del = st.columns([5, 1])
            with col_info:
                label = f"@{u['username']}"
                if u.get("name"):
                    label = f"{u['name']}\n@{u['username']}"
                if st.button(label, key=f"wl_load_{u['username']}", use_container_width=True):
                    st.session_state["profile_target"] = u["username"]
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"wl_del_{u['username']}"):
                    wl.remove(u["username"])
                    st.rerun()

    st.write("")
    new_user = st.text_input(
        "Añadir usuario",
        placeholder="@usuario",
        label_visibility="collapsed",
        key="wl_add_input",
    )
    if st.button("Guardar", use_container_width=True, key="wl_add_btn"):
        clean = new_user.lstrip("@").strip()
        if clean:
            wl.add(clean)
            st.rerun()

    return None


def render() -> None:
    st.title("Analizar perfil")

    # Two-column layout: narrow watchlist panel | main content
    col_wl, col_main = st.columns([1, 3])

    with col_wl:
        _render_watchlist_panel()

    with col_main:
        # Resolve target: from watchlist click or manual input
        default_target = st.session_state.pop("profile_target", "")

        c1, c2 = st.columns([4, 1])
        with c1:
            username_input = st.text_input(
                "Usuario",
                value=default_target,
                placeholder="@elonmusk",
                label_visibility="collapsed",
                key="profile_input",
            )
        with c2:
            analyze_clicked = st.button("Analizar", use_container_width=True)

        if not analyze_clicked and not default_target:
            st.write("")
            st.markdown(
                "<div style='text-align:center; color:#8b949e; padding:48px 0;'>"
                "<div style='font-size:2.5rem;'>👤</div>"
                "<div style='margin-top:8px; font-size:1rem;'>Selecciona un perfil guardado o introduce un @usuario</div>"
                "<div style='font-size:0.8rem; margin-top:4px;'>Obtendrás métricas, actividad y engagement</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            return

        clean = (username_input or default_target).lstrip("@").strip()
        if not clean:
            st.error("Introduce un nombre de usuario válido.")
            return

        pages_key = f"profile_pages_{clean}"
        if pages_key not in st.session_state:
            st.session_state[pages_key] = 1

        with st.spinner(f"Cargando perfil de @{clean}..."):
            user, tweets = _fetch_profile(clean, pages=st.session_state[pages_key])

        if user is None:
            st.error(f"No se encontró el usuario @{clean}.")
            return

        # ---- Profile header -----------------------------------------------
        st.write("")
        col_av, col_info, col_actions = st.columns([1, 4, 2])

        with col_av:
            if user.avatar_url:
                st.image(user.avatar_url, width=80)

        with col_info:
            v = " ✓" if (user.is_verified or user.is_blue_verified) else ""
            st.markdown(
                f"**{user.name}{v}**  \n"
                f"<span style='color:#8b949e;'>@{user.username}</span>",
                unsafe_allow_html=True,
            )
            if user.description:
                st.caption(user.description)
            meta_parts = []
            if user.location:
                meta_parts.append(f"📍 {user.location}")
            if user.url:
                meta_parts.append(f"🔗 [{user.url}]({user.url})")
            if user.created_at:
                meta_parts.append(f"📅 Desde {user.created_at.strftime('%B %Y')}")
            if meta_parts:
                st.caption("  ·  ".join(meta_parts))

        with col_actions:
            r1, r2, r3 = st.columns(3)
            r1.metric("Seguidores", f"{user.followers_count:,}")
            r2.metric("Tweets", f"{user.tweet_count:,}")
            ratio = (
                round(user.followers_count / user.following_count, 1)
                if user.following_count else "—"
            )
            r3.metric("Ratio", ratio)

            # Save / remove from watchlist
            in_wl = wl.contains(clean)
            if in_wl:
                if st.button("★ Quitar de guardados", use_container_width=True):
                    wl.remove(clean)
                    st.rerun()
            else:
                if st.button("☆ Guardar perfil", use_container_width=True):
                    wl.add(clean, name=user.name, avatar_url=user.avatar_url or "")
                    st.rerun()

        if not tweets:
            st.warning("No se encontraron tweets para este perfil.")
            return

        df = tweets_to_dataframe(tweets)

        st.write("")

        # ---- Tabs ---------------------------------------------------------
        tab_act, tab_eng, tab_words = st.tabs(["Actividad", "Engagement", "Palabras"])

        with tab_act:
            col_title, col_more = st.columns([4, 1])
            col_title.markdown(f"#### {len(tweets)} tweets cargados")
            if col_more.button("Cargar más", use_container_width=True, key="profile_load_more"):
                st.session_state[pages_key] += 1
                st.cache_data.clear()
                st.rerun()
            tweet_feed(tweets)

        with tab_eng:
            st.write("")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Likes (media)", f"{df['likes'].mean():.1f}")
            m2.metric("Retweets (media)", f"{df['retweets'].mean():.1f}")
            m3.metric("Replies (media)", f"{df['replies'].mean():.1f}")
            avg_len = df["texto"].str.len().mean()
            m4.metric("Long. media tweet", f"{avg_len:.0f} ch")

            st.write("")
            sub_tabs = st.tabs(["Engagement temporal", "Por hora", "Sentimiento", "Hashtags"])
            with sub_tabs[0]:
                st.plotly_chart(engagement_over_time(df), use_container_width=True)
            with sub_tabs[1]:
                st.plotly_chart(hourly_distribution(df), use_container_width=True)
            with sub_tabs[2]:
                st.plotly_chart(sentiment_pie(df), use_container_width=True)
            with sub_tabs[3]:
                st.plotly_chart(top_hashtags_bar(df), use_container_width=True)

        with tab_words:
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
            else:
                st.info("No hay suficientes palabras para analizar.")

        # ---- Export -------------------------------------------------------
        with st.expander("⬇️ Exportar datos", expanded=False):
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
