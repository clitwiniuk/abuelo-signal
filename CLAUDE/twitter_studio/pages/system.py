"""System status page."""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

from config.settings import COOKIES_FILE, LOGS_DIR, settings
from database.schema import DBKeyword, DBTweet, DBUser, SessionLocal
from twikit_client.client import twitter_client


def _row(label: str, value: str, ok: bool = True) -> None:
    icon = "🟢" if ok else "🔴"
    st.markdown(f"{icon} **{label}:** {value}")


def render() -> None:
    st.markdown("## ⚙️ Estado del sistema")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Autenticación")
        _row("Sesión activa", "Sí" if twitter_client.is_authenticated else "No", twitter_client.is_authenticated)
        _row("Cookies guardadas", "Sí" if COOKIES_FILE.exists() else "No", COOKIES_FILE.exists())
        if twitter_client.me:
            _row("Usuario", f"@{twitter_client.me.screen_name}")

        st.markdown("---")
        st.markdown("### Entorno")
        _row("Python", sys.version.split()[0])
        _row("Plataforma", platform.system())
        _row("Hora UTC", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    with col2:
        st.markdown("### Base de datos")
        db = SessionLocal()
        try:
            n_tweets = db.query(DBTweet).count()
            n_users = db.query(DBUser).count()
            n_kw = db.query(DBKeyword).filter(DBKeyword.active == True).count()
        finally:
            db.close()
        _row("Tweets almacenados", str(n_tweets))
        _row("Usuarios almacenados", str(n_users))
        _row("Keywords activas", str(n_kw))

        st.markdown("---")
        st.markdown("### Configuración")
        _row("Cache TTL", f"{settings.cache_ttl}s")
        _row("Monitor interval", f"{settings.monitor_interval}s")
        _row("Log level", settings.log_level)
        _row("Max resultados default", str(settings.default_search_limit))

    st.markdown("---")
    st.markdown("### Almacenamiento")
    log_size = sum(f.stat().st_size for f in LOGS_DIR.glob("**/*") if f.is_file())
    st.caption(f"Logs: {log_size / 1024:.1f} KB")
