"""System page — Estado, Logs, Acerca de."""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

from config.settings import COOKIES_FILE, LOGS_DIR, settings
from database.schema import DBKeyword, DBTweet, DBUser, SessionLocal
from twikit_client.client import twitter_client

LOG_FILE = LOGS_DIR / "twitter_studio.log"


def _row(label: str, value: str, ok: bool = True) -> None:
    icon = "🟢" if ok else "🔴"
    st.markdown(f"{icon} **{label}:** {value}")


def _render_estado() -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Autenticación")
        _row("Sesión activa", "Sí" if twitter_client.is_authenticated else "No", twitter_client.is_authenticated)
        _row("Cookies guardadas", "Sí" if COOKIES_FILE.exists() else "No", COOKIES_FILE.exists())
        if twitter_client.me:
            _row("Usuario", f"@{twitter_client.me.screen_name}")

        st.write("")
        st.markdown("#### Entorno")
        _row("Python", sys.version.split()[0])
        _row("Plataforma", platform.system())
        _row("Hora UTC", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    with col2:
        st.markdown("#### Base de datos")
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

        st.write("")
        st.markdown("#### Configuración")
        _row("Cache TTL", f"{settings.cache_ttl}s")
        _row("Monitor interval", f"{settings.monitor_interval}s")
        _row("Log level", settings.log_level)
        _row("Max resultados default", str(settings.default_search_limit))

    st.write("")
    st.markdown("#### Almacenamiento")
    log_size = sum(f.stat().st_size for f in LOGS_DIR.glob("**/*") if f.is_file())
    st.caption(f"Logs: {log_size / 1024:.1f} KB")


def _render_logs() -> None:
    col1, col2 = st.columns([3, 1])
    with col1:
        level_filter = st.selectbox("Filtrar nivel", ["TODOS", "INFO", "WARNING", "ERROR", "DEBUG"])
    with col2:
        max_lines = st.number_input("Últimas N líneas", min_value=50, max_value=2000, value=200, step=50)

    if not LOG_FILE.exists():
        st.info("No hay archivo de log todavía.")
        return

    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = lines[-int(max_lines):]

    if level_filter != "TODOS":
        lines = [l for l in lines if level_filter in l]

    if not lines:
        st.info("No hay entradas que coincidan con el filtro.")
        return

    colored = []
    for line in reversed(lines):
        if "ERROR" in line:
            colored.append(f'<span style="color:#f85149;">{line}</span>')
        elif "WARNING" in line:
            colored.append(f'<span style="color:#d29922;">{line}</span>')
        elif "INFO" in line:
            colored.append(f'<span style="color:#c9d1d9;">{line}</span>')
        else:
            colored.append(f'<span style="color:#8b949e;">{line}</span>')

    st.markdown(
        f"""
        <div style="background:#0d1117; border:1px solid #30363d; border-radius:8px;
                    padding:16px; font-family:monospace; font-size:0.78rem;
                    max-height:600px; overflow-y:auto;">
            {"<br>".join(colored)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.download_button(
        "📥 Descargar log completo",
        data=LOG_FILE.read_bytes(),
        file_name="twitter_studio.log",
        mime="text/plain",
    )


def _render_about() -> None:
    st.markdown(
        """
        **Twitter Studio** es una plataforma de inteligencia para X (Twitter),
        orientada al análisis, monitorización y exportación de datos públicos.

        ### Funcionalidades
        - Login con cookies persistentes via Twikit
        - Búsqueda avanzada con filtros (idioma, fechas, media, verificados...)
        - Análisis de perfiles: métricas, estadísticas, palabras frecuentes
        - Monitor de palabras clave con histórico en SQLite
        - Exportación CSV / Excel
        - Gráficas interactivas (Plotly)
        - Análisis de sentimiento (TextBlob)
        - Viewer de logs en tiempo real

        ### Tecnologías
        | Componente | Tecnología |
        |------------|-----------|
        | Frontend | Streamlit |
        | Cliente X | Twikit |
        | Base de datos | SQLite + SQLAlchemy |
        | Modelos | Pydantic v2 |
        | Visualización | Plotly |
        | Logging | Loguru |
        | Sentimiento | TextBlob |

        ### Aviso legal
        Esta herramienta es exclusivamente de **consulta y análisis**.
        No publica, responde ni modifica contenido en X.
        Úsala respetando los [Términos de servicio de X](https://x.com/en/tos).

        **Versión:** 1.0.0
        """
    )


def render() -> None:
    st.title("Sistema")

    tab_estado, tab_logs, tab_about = st.tabs(["Estado", "Logs", "Acerca de"])

    with tab_estado:
        st.write("")
        _render_estado()

    with tab_logs:
        st.write("")
        _render_logs()

    with tab_about:
        st.write("")
        _render_about()
