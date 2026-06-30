"""Keyword monitor page — track terms over time."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from database.schema import DBKeyword, DBTweet, SessionLocal
from services.tweet_service import map_tweets
from twikit_client.client import twitter_client
from utils.charts import engagement_over_time, top_hashtags_bar, tweet_volume_histogram
from utils.export_helper import export_filename, to_csv_bytes, to_excel_bytes, tweets_to_dataframe


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _get_keywords() -> list[DBKeyword]:
    db = SessionLocal()
    try:
        return db.query(DBKeyword).filter(DBKeyword.active == True).all()
    finally:
        db.close()


def _add_keyword(kw: str) -> bool:
    db = SessionLocal()
    try:
        existing = db.query(DBKeyword).filter(DBKeyword.keyword == kw).first()
        if existing:
            existing.active = True
        else:
            db.add(DBKeyword(keyword=kw))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def _delete_keyword(kid: int) -> None:
    db = SessionLocal()
    try:
        db.query(DBKeyword).filter(DBKeyword.id == kid).update({"active": False})
        db.commit()
    finally:
        db.close()


def _save_tweets(tweets, keyword_id: int) -> int:
    db = SessionLocal()
    saved = 0
    try:
        for t in tweets:
            exists = db.query(DBTweet).filter(DBTweet.id == t.id).first()
            if exists:
                continue
            db.add(DBTweet(
                id=t.id,
                text=t.text,
                author_id=t.author_id,
                author_name=t.author_name,
                author_username=t.author_username,
                created_at=t.created_at,
                like_count=t.like_count,
                reply_count=t.reply_count,
                retweet_count=t.retweet_count,
                view_count=t.view_count,
                language=t.language,
                hashtags=",".join(t.hashtags),
                mentions=",".join(t.mentions),
                is_retweet=t.is_retweet,
                is_reply=t.is_reply,
                sentiment=t.sentiment,
                sentiment_score=t.sentiment_score,
                tweet_url=t.tweet_url,
                keyword_id=keyword_id,
            ))
            saved += 1
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()
    return saved


def _get_stored_tweets(keyword_id: int) -> list[DBTweet]:
    db = SessionLocal()
    try:
        return (
            db.query(DBTweet)
            .filter(DBTweet.keyword_id == keyword_id)
            .order_by(DBTweet.created_at.desc())
            .limit(500)
            .all()
        )
    finally:
        db.close()


def _db_tweets_to_df(rows: list[DBTweet]) -> pd.DataFrame:
    data = []
    for r in rows:
        data.append({
            "fecha": r.created_at.isoformat() if r.created_at else "",
            "usuario": r.author_username,
            "texto": r.text,
            "likes": r.like_count or 0,
            "replies": r.reply_count or 0,
            "retweets": r.retweet_count or 0,
            "sentimiento": r.sentiment or "",
            "hashtags": r.hashtags or "",
            "idioma": r.language or "",
        })
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render() -> None:
    st.markdown("## 📡 Monitor de palabras clave")
    st.markdown("---")

    # ---- Add keyword ------------------------------------------------------
    with st.form("add_keyword_form", clear_on_submit=True):
        col_inp, col_btn = st.columns([4, 1])
        new_kw = col_inp.text_input("Nueva palabra clave", placeholder="$AAPL smallcaps biotech")
        add_clicked = col_btn.form_submit_button("Añadir", use_container_width=True)

    if add_clicked and new_kw.strip():
        if _add_keyword(new_kw.strip()):
            st.success(f"Palabra añadida: **{new_kw.strip()}**")
            st.rerun()

    # ---- Keywords list ----------------------------------------------------
    keywords = _get_keywords()
    if not keywords:
        st.info("No hay palabras clave configuradas. Añade una para empezar.")
        return

    st.markdown("### Palabras monitorizadas")
    for kw in keywords:
        col_kw, col_check, col_del = st.columns([5, 2, 1])
        col_kw.markdown(f"**{kw.keyword}**")
        last = kw.last_checked.strftime("%d/%m %H:%M") if kw.last_checked else "nunca"
        col_check.caption(f"Última comprobación: {last} | {kw.tweet_count} tweets")
        if col_del.button("🗑", key=f"del_{kw.id}"):
            _delete_keyword(kw.id)
            st.rerun()

    st.markdown("---")

    # ---- Manual scan ------------------------------------------------------
    st.markdown("### Escanear ahora")
    selected_kw = st.selectbox(
        "Selecciona palabra clave",
        options=[(k.id, k.keyword) for k in keywords],
        format_func=lambda x: x[1],
    )
    scan_count = st.slider("Tweets a buscar", 10, 200, 50, 10)

    if st.button("▶️  Escanear", use_container_width=True):
        kid, kw_text = selected_kw
        progress = st.progress(0, text=f"Buscando tweets para «{kw_text}»...")
        raw = asyncio.run(
            twitter_client.search_tweets_paginated(
                query=kw_text,
                product="Latest",
                max_results=scan_count,
            )
        )
        progress.progress(60, text="Procesando...")
        tweets = map_tweets(raw)
        saved = _save_tweets(tweets, kid)
        # Update last_checked + count
        db = SessionLocal()
        try:
            db.query(DBKeyword).filter(DBKeyword.id == kid).update({
                "last_checked": datetime.utcnow(),
                "tweet_count": DBKeyword.tweet_count + saved,
            })
            db.commit()
        finally:
            db.close()
        progress.progress(100, text=f"✅ {saved} tweets nuevos guardados")
        st.rerun()

    # ---- Dashboard for selected keyword -----------------------------------
    st.markdown("---")
    st.markdown(f"### Dashboard — {selected_kw[1]}")
    rows = _get_stored_tweets(selected_kw[0])
    if not rows:
        st.info("Sin datos almacenados. Haz un escaneo primero.")
        return

    df = _db_tweets_to_df(rows)

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Tweets almacenados", len(df))
    d2.metric("Usuarios únicos", df["usuario"].nunique())
    d3.metric("Likes totales", int(df["likes"].sum()))
    d4.metric("Retweets totales", int(df["retweets"].sum()))

    tab_vol, tab_eng, tab_hash = st.tabs(["Volumen", "Engagement", "Hashtags"])
    with tab_vol:
        st.plotly_chart(tweet_volume_histogram(df), use_container_width=True)
    with tab_eng:
        st.plotly_chart(engagement_over_time(df), use_container_width=True)
    with tab_hash:
        st.plotly_chart(top_hashtags_bar(df), use_container_width=True)

    # ---- Export -----------------------------------------------------------
    st.markdown("---")
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "📥 CSV",
            data=to_csv_bytes(df),
            file_name=export_filename(f"monitor_{selected_kw[1]}", "csv"),
            mime="text/csv",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "📥 Excel",
            data=to_excel_bytes(df),
            file_name=export_filename(f"monitor_{selected_kw[1]}", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
