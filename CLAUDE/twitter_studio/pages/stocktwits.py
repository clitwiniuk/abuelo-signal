"""Stocktwits page — download and browse ticker message history."""

from __future__ import annotations

import asyncio
import html
import threading

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from database.schema import DBStocktwitsPost
from services.stocktwits_service import (
    count_posts, delete_ticker, download_ticker, get_checkpoint, get_translation,
    list_tickers, query_posts, ticker_stats,
)
from stocktwits_client.client import StocktwitsClient
from utils.export_helper import to_csv_bytes, export_filename
from utils.logger import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_card(p: DBStocktwitsPost, translate: bool = False) -> None:
    fecha_str = p.created_at.strftime("%d %b %Y · %H:%M") if p.created_at else ""
    sentiment_color = {"Bullish": "#3fb950", "Bearish": "#f85149"}.get(p.sentiment, "#8b949e")
    sentiment_html = (
        f"<span style='color:{sentiment_color};font-weight:600;font-size:0.78rem;'>{p.sentiment}</span>"
        if p.sentiment else ""
    )
    link_html = (
        f'<a href="{p.post_url}" target="_blank" style="color:#58a6ff;font-size:0.78rem;text-decoration:none;">'
        f'Ver en Stocktwits ↗</a>' if p.post_url else ""
    )
    # A blank line inside the message body would terminate Streamlit's markdown
    # HTML block early (per CommonMark, raw HTML blocks end at the first blank
    # line), spilling the rest of our tags as literal text. Collapse newlines
    # to <br> so the whole card stays a single unbroken HTML block.
    main_text = p.body
    original_html = ""
    if translate:
        translated = get_translation(p.id, p.ticker)  # cached on the row after first call
        if translated:
            main_text = translated
            original_html = (
                f'<div style="color:#6e7681;font-size:0.82rem;line-height:1.4;margin-top:6px;font-style:italic;">'
                f'{html.escape(p.body).replace(chr(10), "<br>")}</div>'
            )
    body_html = html.escape(main_text).replace("\n", "<br>")

    media_html = (
        f'<img src="{p.media_url}" style="max-width:100%;border-radius:8px;margin-top:10px;display:block;">'
        if p.media_url else ""
    )

    link_preview_html = ""
    if p.link_url:
        preview_img = (
            f'<img src="{p.link_image_url}" style="width:100%;max-height:160px;object-fit:cover;'
            f'border-radius:8px 8px 0 0;display:block;">'
            if p.link_image_url else ""
        )
        link_preview_html = (
            f'<a href="{p.link_url}" target="_blank" style="text-decoration:none;">'
            f'<div style="border:1px solid #30363d;border-radius:8px;margin-top:10px;overflow:hidden;">'
            f'{preview_img}'
            f'<div style="padding:8px 10px;color:#8b949e;font-size:0.82rem;">{html.escape(p.link_title or p.link_url)}</div>'
            f'</div></a>'
        )

    card_html = (
        f'<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 16px;margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
        f'<div>'
        f'<span style="font-weight:700;color:#c9d1d9;">@{p.author_username}</span>'
        f'<span style="color:#8b949e;font-size:0.82rem;margin-left:6px;">{fecha_str}</span>'
        f'{sentiment_html}'
        f'</div>'
        f'{link_html}'
        f'</div>'
        f'<div style="color:#c9d1d9;font-size:0.95rem;line-height:1.5;">{body_html}</div>'
        f'{original_html}'
        f'{media_html}'
        f'{link_preview_html}'
        f'<div style="display:flex;gap:16px;color:#8b949e;font-size:0.82rem;border-top:1px solid #21262d;padding-top:8px;margin-top:10px;">'
        f'<span>❤️ {p.like_count:,}</span>'
        f'<span>💬 {p.reply_count:,}</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def _auto_click_when_visible(button_label: str, nonce: object) -> None:
    """Fake infinite scroll: auto-clicks a Streamlit button once it scrolls
    near the viewport, instead of making the user click "Cargar más"
    themselves. Streamlit has no native scroll-triggered rerun, so this
    reaches into the parent document (same-origin, the component iframe can
    see it) and drives the real button — the button stays as a visible
    fallback in case JS is blocked or the click race is missed.

    `nonce` must change across reruns (e.g. the current page size) so the
    browser treats each render as new content and re-executes the script —
    identical HTML/JS is not guaranteed to re-run otherwise.
    """
    components.html(
        f"""
        <script>
        // nonce={nonce}
        (function() {{
            const label = {button_label!r};
            function findButton() {{
                const buttons = window.parent.document.querySelectorAll('button');
                for (const b of buttons) {{
                    if (b.innerText && b.innerText.trim() === label.trim()) return b;
                }}
                return null;
            }}
            let clicked = false;
            const btn = findButton();
            if (btn && window.parent.IntersectionObserver) {{
                const observer = new window.parent.IntersectionObserver((entries) => {{
                    entries.forEach((entry) => {{
                        if (entry.isIntersecting && !clicked) {{
                            clicked = true;
                            btn.click();
                        }}
                    }});
                }}, {{ root: null, rootMargin: '600px', threshold: 0 }});
                observer.observe(btn);
            }}
        }})();
        </script>
        """,
        height=0,
    )


def _posts_to_export_dicts(posts: list[DBStocktwitsPost]) -> list[dict]:
    return [{
        "id": p.id,
        "ticker": p.ticker,
        "fecha": p.created_at.isoformat() if p.created_at else "",
        "usuario": p.author_username,
        "texto": p.body,
        "likes": p.like_count,
        "replies": p.reply_count,
        "cashtags": p.cashtags or "",
        "sentimiento": p.sentiment or "",
        "enlace": p.post_url or "",
    } for p in posts]


def _download_worker(ticker: str, from_date: str | None, to_date: str | None,
                      max_messages: int, resume: bool, stop_event: threading.Event, status: dict) -> None:
    """Runs in a background thread with its own event loop and its own
    StocktwitsClient instance — kept fully independent from the shared
    singleton/event loop used elsewhere, so it's safe to drive from a thread
    Streamlit didn't create, and so the "Stop" button stays responsive while
    this blocks on Playwright/network calls.
    """
    loop = asyncio.new_event_loop()
    client = StocktwitsClient()
    try:
        async def _run():
            await client.start(headless=False)
            try:
                return await download_ticker(
                    client, ticker,
                    from_date=from_date, to_date=to_date,
                    max_messages=max_messages, resume=resume,
                    should_stop=stop_event.is_set,
                )
            finally:
                await client.stop()

        saved = loop.run_until_complete(_run())
        status["saved"] = saved
        status["state"] = "stopped" if stop_event.is_set() else "done"
    except Exception as exc:
        logger.error(f"Stocktwits download worker error: {exc}")
        status["state"] = "error"
        status["error"] = str(exc)
    finally:
        loop.close()


@st.fragment(run_every=1)
def _download_progress_fragment() -> None:
    """Polls the background download thread + DB every 2s while a download is
    running, without re-running the whole page (which would otherwise reset
    the ticker/date inputs and fight the thread for the Streamlit session).
    """
    thread: threading.Thread | None = st.session_state.get("st_dl_thread")
    status: dict | None = st.session_state.get("st_dl_status")
    ticker: str | None = st.session_state.get("st_dl_ticker")
    if thread is None or status is None or ticker is None:
        return

    stats = ticker_stats(ticker)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric(f"{ticker} en DB", stats["total"])
    s2.metric("Bullish", stats["bullish"])
    s3.metric("Bearish", stats["bearish"])
    s4.metric("Sin etiqueta", stats["no_sentiment"])

    if thread.is_alive():
        return  # still running — next tick will re-check

    # Thread finished. Stash the result and force a full-page rerun so the
    # form's disabled inputs re-enable immediately — but render the summary
    # from session_state in the main render() body, not here, since this
    # fragment's own output would otherwise be wiped by that same rerun.
    st.session_state["st_dl_last_result"] = {"ticker": ticker, "state": status["state"],
                                              "saved": status["saved"], "error": status["error"]}
    st.session_state["st_dl_thread"] = None
    st.rerun(scope="app")


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render() -> None:
    st.markdown("## 📈 Stocktwits")
    st.markdown("---")

    tab_download, tab_browse, tab_manage = st.tabs(["⬇️  Descargar", "🔎  Explorar", "🗑️  Gestionar"])

    # -----------------------------------------------------------------------
    with tab_download:
        st.caption(
            "Requiere un navegador visible en esta máquina para superar el challenge "
            "de Cloudflare (no funciona en modo headless todavía)."
        )
        st.caption(
            "Para descargas grandes en tickers muy activos, súbete al Límite de seguridad y ten "
            "paciencia — cada página tarda unos segundos, pero ya no hay tope artificial de mensajes."
        )

        thread: threading.Thread | None = st.session_state.get("st_dl_thread")
        is_running = thread is not None and thread.is_alive()

        ticker = st.text_input("Ticker", placeholder="TSLA", disabled=is_running).strip().upper()
        c1, c2 = st.columns(2)
        from_date = c1.date_input("Desde (opcional)", value=None, disabled=is_running,
                                   help="Deja vacío para no poner límite antiguo.")
        to_date = c2.date_input("Hasta (opcional)", value=None, disabled=is_running,
                                 help="Deja vacío para empezar desde el mensaje más reciente.")
        resume = st.checkbox("Modo sync (solo mensajes nuevos)", value=True, disabled=is_running,
                              help="Si está marcado, se detiene al llegar al último mensaje ya guardado "
                                   "para este ticker. Desmárcalo para redescargar el periodo completo.")
        max_messages = st.number_input(
            "Límite de seguridad (nº de mensajes)", min_value=100, max_value=50_000, value=5000, step=500,
            disabled=is_running,
            help="Tope máximo por si el periodo elegido es muy largo. No es el objetivo — el objetivo es el rango de fechas.",
        )

        if ticker and not is_running:
            checkpoint = get_checkpoint(ticker)
            if checkpoint:
                st.info(f"Último mensaje sincronizado para {ticker}: id {checkpoint}")

        if not is_running:
            if st.button("▶️  Descargar", use_container_width=True, type="primary", disabled=not ticker):
                stop_event = threading.Event()
                status = {"state": "running", "saved": 0, "error": None}
                worker_thread = threading.Thread(
                    target=_download_worker,
                    args=(ticker, from_date.isoformat() if from_date else None,
                          to_date.isoformat() if to_date else None,
                          int(max_messages), resume, stop_event, status),
                    daemon=True,
                )
                st.session_state["st_dl_thread"] = worker_thread
                st.session_state["st_dl_stop_event"] = stop_event
                st.session_state["st_dl_status"] = status
                st.session_state["st_dl_ticker"] = ticker
                st.session_state["st_dl_last_result"] = None
                st.session_state["browse_ticker"] = ticker  # pre-rellena la pestaña Explorar
                worker_thread.start()
                st.rerun()

            last = st.session_state.get("st_dl_last_result")
            if last:
                if last["state"] == "error":
                    st.error(f"Error descargando {last['ticker']}: {last['error']}")
                elif last["state"] == "stopped":
                    st.warning(f"Detenido por el usuario. {last['saved']} mensajes nuevos guardados para {last['ticker']}.")
                else:
                    st.success(f"{last['saved']} mensajes nuevos guardados para {last['ticker']}.")

                stats = ticker_stats(last["ticker"])
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Total en DB", stats["total"])
                s2.metric("Bullish", stats["bullish"])
                s3.metric("Bearish", stats["bearish"])
                s4.metric("Sin etiqueta", stats["no_sentiment"])

                st.markdown("---")
                st.markdown(f"**Últimos mensajes de {last['ticker']}:**")
                for p in query_posts(ticker=last["ticker"], limit=20):
                    _post_card(p)
        else:
            dl_ticker = st.session_state.get("st_dl_ticker", ticker)
            st.info(f"Descargando **{dl_ticker}**... no cierres la ventana de Chrome.")
            if st.button("⏹️  Detener", use_container_width=True, type="secondary"):
                st.session_state["st_dl_stop_event"].set()
                st.info("Deteniendo tras la página en curso... se guardará lo ya descargado.")

        _download_progress_fragment()

    # -----------------------------------------------------------------------
    with tab_browse:
        c1, c2, c3 = st.columns([2, 2, 2])
        f_ticker = c1.text_input("Ticker", key="browse_ticker", placeholder="TSLA").strip().upper()
        f_sentiment = c2.selectbox("Sentimiento", ["Todos", "Bullish", "Bearish"])
        f_keyword = c3.text_input("Buscar palabra clave", key="browse_keyword")

        d1, d2 = st.columns(2)
        f_from = d1.date_input("Desde (opcional)", value=None, key="browse_from")
        f_to = d2.date_input("Hasta (opcional)", value=None, key="browse_to")
        translate = st.checkbox(
            "🌐 Traducir al español", value=True,
            help="Se traduce y guarda la primera vez que se ve cada mensaje; las siguientes veces es instantáneo.",
        )

        if f_ticker:
            stats = ticker_stats(f_ticker)
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Total", stats["total"])
            s2.metric("Bullish", stats["bullish"])
            s3.metric("Bearish", stats["bearish"])
            s4.metric("Sin etiqueta", stats["no_sentiment"])

        from_date = f_from.isoformat() if f_from else None
        # End-of-day, not midnight — otherwise a bare "YYYY-MM-DD" upper bound
        # excludes every message on that day (string comparison against a
        # DateTime column: "...T15:00:00" > "...T00:00:00").
        to_date = f"{f_to.isoformat()}T23:59:59" if f_to else None
        sentiment = None if f_sentiment == "Todos" else f_sentiment

        # Lazy-load pagination: start small and grow on "Cargar más" instead
        # of a fixed cap that a single high-volume day could fill entirely.
        # Reset the page size whenever the filters themselves change, so a
        # new search doesn't inherit a huge limit from a previous one.
        filters_key = (f_ticker, from_date, to_date, sentiment, f_keyword)
        if st.session_state.get("browse_filters_key") != filters_key:
            st.session_state["browse_filters_key"] = filters_key
            st.session_state["browse_page_size"] = 50

        page_size = st.session_state["browse_page_size"]
        posts = query_posts(
            ticker=f_ticker or None, from_date=from_date, to_date=to_date,
            sentiment=sentiment, keyword=f_keyword or None, limit=page_size,
        )
        total = count_posts(
            ticker=f_ticker or None, from_date=from_date, to_date=to_date,
            sentiment=sentiment, keyword=f_keyword or None,
        )

        if not posts:
            st.info("No hay mensajes guardados con esos filtros. Descarga un ticker en la pestaña anterior.")
        else:
            st.markdown(f"**Mostrando {len(posts)} de {total} mensaje(s)**")
            csv_bytes = to_csv_bytes(pd.DataFrame(_posts_to_export_dicts(
                query_posts(ticker=f_ticker or None, from_date=from_date, to_date=to_date,
                            sentiment=sentiment, keyword=f_keyword or None, limit=total or 1)
            )))
            st.download_button(
                "⬇️  Exportar CSV (todo el rango filtrado)",
                data=csv_bytes,
                file_name=export_filename(f"stocktwits_{f_ticker or 'all'}", "csv"),
                mime="text/csv",
            )
            st.markdown("---")
            for p in posts:
                _post_card(p, translate=translate)

            if len(posts) < total:
                c_more, c_all = st.columns(2)
                if c_more.button("⬇️  Cargar más", use_container_width=True, key="browse_load_more"):
                    st.session_state["browse_page_size"] = page_size + 50
                    st.rerun()
                if c_all.button(f"⬇️  Cargar todo ({total})", use_container_width=True, key="browse_load_all"):
                    st.session_state["browse_page_size"] = total
                    st.rerun()
                _auto_click_when_visible("⬇️  Cargar más", nonce=page_size)

    # -----------------------------------------------------------------------
    with tab_manage:
        st.caption("Tickers descargados actualmente. Borrar es permanente e incluye el checkpoint de sincronización.")
        tickers = list_tickers()

        if not tickers:
            st.info("Todavía no has descargado ningún ticker.")
        else:
            for t in tickers:
                c1, c2, c3, c4 = st.columns([1.5, 1, 3, 1.5])
                c1.markdown(f"**{t['ticker']}**")
                c2.markdown(f"{t['count']:,} msgs")
                oldest = t["oldest"].strftime("%d %b %Y") if t["oldest"] else "?"
                newest = t["newest"].strftime("%d %b %Y") if t["newest"] else "?"
                c3.markdown(f"<span style='color:#8b949e;'>{oldest} → {newest}</span>", unsafe_allow_html=True)

                confirm_key = f"confirm_del_{t['ticker']}"
                if st.session_state.get(confirm_key):
                    if c4.button("✅ Confirmar", key=f"confirmbtn_{t['ticker']}", use_container_width=True):
                        deleted = delete_ticker(t["ticker"])
                        st.session_state.pop(confirm_key, None)
                        st.success(f"{deleted} mensajes de {t['ticker']} borrados.")
                        st.rerun()
                else:
                    if c4.button("🗑️ Borrar", key=f"delbtn_{t['ticker']}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
