"""Research page — análisis de listas de traders con filtrado semántico."""

from __future__ import annotations

import asyncio
import json
import html
from pathlib import Path

import streamlit as st

from services.research_service import (
    TweetResearch,
    cargar_config,
    ejecutar_research,
    guardar_config,
)
from twikit_client.client import twitter_client
from utils.logger import logger

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "research_config.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _research_card(t: TweetResearch) -> None:
    fecha_str = t.fecha.strftime("%d %b %Y · %H:%M") if t.fecha else ""
    palabras_html = " ".join(
        f"<span style='background:#1f3a5f;color:#58a6ff;border-radius:4px;padding:2px 6px;font-size:0.72rem;'>{p}</span>"
        for p in t.palabras_encontradas[:6]
    )
    link_html = (
        f'<a href="{t.url}" target="_blank" style="color:#58a6ff;font-size:0.78rem;text-decoration:none;">Ver en X ↗</a>'
        if t.url else ""
    )
    st.markdown(
        f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 16px;margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <div>
                    <span style="font-weight:700;color:#c9d1d9;">{t.autor}</span>
                    <span style="color:#8b949e;font-size:0.82rem;margin-left:6px;">@{t.autor_username} · {fecha_str}</span>
                </div>
                {link_html}
            </div>
            <div style="color:#c9d1d9;font-size:0.95rem;line-height:1.5;margin-bottom:10px;white-space:pre-wrap;">{html.escape(t.texto)}</div>
            <div style="margin-bottom:8px;">{palabras_html}</div>
            <div style="display:flex;gap:16px;color:#8b949e;font-size:0.82rem;border-top:1px solid #21262d;padding-top:8px;">
                <span>❤️ {t.likes:,}</span>
                <span>🔁 {t.retweets:,}</span>
                <span>💬 {t.replies:,}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render() -> None:
    st.markdown("## 🔬 Research de listas")
    st.markdown("---")

    cfg = cargar_config()

    tab_run, tab_config = st.tabs(["▶️  Ejecutar research", "⚙️  Configuración"])

    # -----------------------------------------------------------------------
    with tab_run:
        listas_activas = [l for l in cfg.listas if l.get("activa", True) and l.get("id")]
        if not listas_activas:
            st.warning("No hay listas configuradas. Ve a **Configuración** y añade el ID de una lista de X.")
        else:
            lista_sel = st.selectbox(
                "Lista a analizar",
                options=listas_activas,
                format_func=lambda l: l["nombre"],
            )
            max_tweets = st.slider("Tweets a descargar", 20, 500, 100, 10)

            if st.button("▶️  Iniciar research", use_container_width=True, type="primary"):
                if not twitter_client.is_authenticated or twitter_client._client is None:
                    st.error("No hay sesión activa.")
                else:
                    with st.spinner(f"Analizando lista «{lista_sel['nombre']}»... (puede tardar por las pausas anti-ban)"):
                        try:
                            resultados: list[TweetResearch] = asyncio.run(
                                ejecutar_research(
                                    twitter_client._client,
                                    lista_sel["id"],
                                    max_tweets=max_tweets,
                                )
                            )
                        except Exception as e:
                            st.error(f"Error: {e}")
                            logger.error(f"Research error: {e}")
                            resultados = []

                    if not resultados:
                        st.info("Ningún tweet superó el filtro con la configuración actual.")
                    else:
                        st.success(f"{len(resultados)} tweets relevantes encontrados")
                        st.markdown("---")
                        for t in resultados:
                            _research_card(t)

    # -----------------------------------------------------------------------
    with tab_config:
        st.markdown("### Listas de X")
        st.caption("Añade el ID numérico de la lista. Lo encuentras en la URL: x.com/i/lists/**123456789**")

        for i, lista in enumerate(cfg.listas):
            c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
            lista["nombre"] = c1.text_input("Nombre", lista.get("nombre", ""), key=f"ln_{i}")
            lista["id"] = c2.text_input("ID de lista", lista.get("id", ""), key=f"lid_{i}")
            lista["activa"] = c3.checkbox("Activa", lista.get("activa", True), key=f"la_{i}")
            if c4.button("🗑", key=f"ldel_{i}"):
                cfg.listas.pop(i)
                guardar_config(cfg)
                st.rerun()

        if st.button("➕ Añadir lista"):
            cfg.listas.append({"id": "", "nombre": "Nueva lista", "activa": True})
            guardar_config(cfg)
            st.rerun()

        st.markdown("---")
        st.markdown("### Palabras de valor")
        st.caption("Tweets que contengan al menos una de estas palabras pasarán el filtro.")
        valor_text = st.text_area(
            "Una por línea",
            value="\n".join(cfg.palabras_valor),
            height=200,
            key="palabras_valor_edit",
        )

        st.markdown("### Palabras de ruido")
        st.caption("Tweets con cualquiera de estas palabras serán descartados.")
        ruido_text = st.text_area(
            "Una por línea",
            value="\n".join(cfg.palabras_ruido),
            height=150,
            key="palabras_ruido_edit",
        )

        st.markdown("### Pausas anti-ban")
        c1, c2 = st.columns(2)
        p_min_tw = c1.number_input("Pausa mín. entre tweets (s)", 1.0, 30.0, cfg.pausa_min_tweets, 0.5)
        p_max_tw = c2.number_input("Pausa máx. entre tweets (s)", 1.0, 60.0, cfg.pausa_max_tweets, 0.5)
        c3, c4 = st.columns(2)
        p_min_cy = c3.number_input("Pausa mín. entre ciclos (s)", 10.0, 600.0, cfg.pausa_min_ciclos, 10.0)
        p_max_cy = c4.number_input("Pausa máx. entre ciclos (s)", 10.0, 3600.0, cfg.pausa_max_ciclos, 10.0)

        if st.button("💾 Guardar configuración", use_container_width=True, type="primary"):
            cfg.palabras_valor = [p.strip().lower() for p in valor_text.splitlines() if p.strip()]
            cfg.palabras_ruido = [p.strip().lower() for p in ruido_text.splitlines() if p.strip()]
            cfg.pausa_min_tweets = p_min_tw
            cfg.pausa_max_tweets = p_max_tw
            cfg.pausa_min_ciclos = p_min_cy
            cfg.pausa_max_ciclos = p_max_cy

            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            raw["palabras_valor"] = cfg.palabras_valor
            raw["palabras_ruido"] = cfg.palabras_ruido
            raw["listas"] = cfg.listas
            raw["anti_ban"] = {
                "pausa_min_entre_tweets": p_min_tw,
                "pausa_max_entre_tweets": p_max_tw,
                "pausa_min_entre_ciclos": p_min_cy,
                "pausa_max_entre_ciclos": p_max_cy,
            }
            _CONFIG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=4), encoding="utf-8")
            st.success("Configuración guardada.")
