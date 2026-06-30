"""Logs viewer page."""

from __future__ import annotations

import streamlit as st

from config.settings import LOGS_DIR

LOG_FILE = LOGS_DIR / "twitter_studio.log"


def render() -> None:
    st.markdown("## 📋 Logs del sistema")
    st.markdown("---")

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

    st.download_button(
        "📥 Descargar log completo",
        data=LOG_FILE.read_bytes(),
        file_name="twitter_studio.log",
        mime="text/plain",
    )
