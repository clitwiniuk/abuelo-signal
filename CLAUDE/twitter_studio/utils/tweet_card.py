"""Reusable tweet card renderer."""

from __future__ import annotations

import html
import streamlit as st
import streamlit.components.v1 as components

from models.tweet import TweetModel


_SENTIMENT_COLOR = {"positive": "#3fb950", "negative": "#f85149", "neutral": "#8b949e"}


def tweet_card(t: TweetModel, marked: bool = False) -> None:
    """Render a tweet as a self-contained visual card."""
    date_str = t.created_at.strftime("%d %b %Y · %H:%M") if t.created_at else ""
    sentiment_color = _SENTIMENT_COLOR.get(t.sentiment or "neutral", "#8b949e")
    sentiment_label = {"positive": "↑ positivo", "negative": "↓ negativo", "neutral": "· neutro"}.get(t.sentiment or "neutral", "")

    avatar_html = (
        f'<img src="{t.author_avatar}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;margin-right:10px;flex-shrink:0;">'
        if t.author_avatar else
        '<div style="width:40px;height:40px;border-radius:50%;background:#30363d;margin-right:10px;flex-shrink:0;"></div>'
    )

    rt_badge = '<span style="color:#3fb950;font-size:0.75rem;font-weight:600;margin-left:6px;">RT</span>' if t.is_retweet else ""
    reply_badge = '<span style="color:#8b949e;font-size:0.75rem;margin-left:6px;">↩ reply</span>' if t.is_reply else ""

    hashtags_html = " ".join(
        f'<span style="color:#58a6ff;">#{html.escape(h)}</span>' for h in (t.hashtags or [])[:5]
    )

    link_html = (
        f'<a href="{t.tweet_url}" target="_blank" style="color:#58a6ff;font-size:0.78rem;text-decoration:none;">Ver en X ↗</a>'
        if t.tweet_url else ""
    )

    views_html = f'<span>👁 {t.view_count:,}</span>' if t.view_count else ""

    # Dim card if marked as read
    opacity = "0.45" if marked else "1"
    border_color = "#21262d" if marked else "#30363d"

    card = (
        f'<div style="background:#161b22;border:1px solid {border_color};border-radius:10px;'
        f'padding:14px 16px;margin-bottom:4px;font-family:sans-serif;opacity:{opacity};">'
            '<div style="display:flex;align-items:center;margin-bottom:10px;">'
                f'{avatar_html}'
                '<div style="flex:1;">'
                    f'<div style="font-weight:700;color:#c9d1d9;font-size:0.95rem;">{html.escape(t.author_name)}{rt_badge}{reply_badge}</div>'
                    f'<div style="color:#8b949e;font-size:0.82rem;">@{html.escape(t.author_username)} · {date_str}</div>'
                '</div>'
                f'<div style="color:{sentiment_color};font-size:0.75rem;font-weight:600;margin-left:8px;">{sentiment_label}</div>'
            '</div>'
            f'<div style="color:#c9d1d9;font-size:0.95rem;line-height:1.5;margin-bottom:10px;white-space:pre-wrap;">{html.escape(t.text)}</div>'
            f'<div style="font-size:0.82rem;margin-bottom:10px;">{hashtags_html}</div>'
            '<div style="display:flex;gap:20px;color:#8b949e;font-size:0.82rem;border-top:1px solid #21262d;padding-top:10px;align-items:center;">'
                f'<span>❤️ {t.like_count:,}</span>'
                f'<span>🔁 {t.retweet_count:,}</span>'
                f'<span>💬 {t.reply_count:,}</span>'
                f'{views_html}'
                f'<span style="margin-left:auto;">{link_html}</span>'
            '</div>'
        '</div>'
    )

    lines = max(1, len(t.text) // 60)
    height = 160 + lines * 22
    components.html(card, height=height, scrolling=False)

    # ---- Media below the card --------------------------------------------
    if t.media_images:
        cols = st.columns(min(len(t.media_images), 3))
        for col, img_url in zip(cols, t.media_images):
            col.image(img_url, use_container_width=True)

    if t.media_video_url:
        import requests
        vc1, vc2 = st.columns([3, 1])
        vc1.video(t.media_video_url)
        try:
            video_bytes = requests.get(t.media_video_url, timeout=15).content
            vc2.download_button(
                "⬇️ Descargar vídeo",
                data=video_bytes,
                file_name=f"tweet_{t.id}.mp4",
                mime="video/mp4",
                use_container_width=True,
                key=f"dl_video_{t.id}",
            )
        except Exception:
            pass


def tweet_feed(
    tweets: list[TweetModel],
    max_items: int = 200,
    markable: bool = False,
    marked_ids: set[str] | None = None,
) -> None:
    """Render a list of tweets as a feed of cards.

    If markable=True, a checkbox appears above each card to toggle read/used state.
    marked_ids should be the current set of marked tweet IDs.
    """
    from services import marked_tweets_service as mts

    if marked_ids is None and markable:
        marked_ids = mts.load_all()

    for t in tweets[:max_items]:
        if markable:
            tid = str(t.id)
            is_marked = tid in (marked_ids or set())
            col_check, col_card = st.columns([1, 20])
            with col_check:
                st.markdown("<div style='padding-top:14px;'>", unsafe_allow_html=True)
                checked = st.checkbox(
                    "visto",
                    value=is_marked,
                    key=f"mark_{tid}",
                    label_visibility="collapsed",
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if checked != is_marked:
                    mts.toggle(tid)
                    st.rerun()
            with col_card:
                tweet_card(t, marked=is_marked)
        else:
            tweet_card(t)
