"""
Market Replay — Interactive candle-by-candle day replay with order execution.

The user selects a curated scenario, watches the chart unfold bar by bar,
and can enter/exit trades at any point.  Educational feedback is provided
contextually.  A scorecard is shown at the end.
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time
from datetime import datetime

from utils.replay_engine import (
    SCENARIOS, get_scenarios_for_level, generate_scenario_data,
    create_replay_state, execute_buy, execute_sell, advance_bar,
    get_entry_feedback, get_exit_feedback, generate_scorecard,
    ReplayState,
)
from database.db_manager import add_xp_to_user, create_replay_session, close_replay_session


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPEED_MAP = {"1x": 1.0, "2x": 0.5, "5x": 0.2, "10x": 0.1, "Pause": 0}


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

def _build_replay_chart(df: pd.DataFrame, n_bars: int, state: ReplayState,
                        symbol: str = "REPLAY") -> go.Figure:
    """Build a Plotly candlestick chart showing only the first *n_bars* bars."""
    visible = df.iloc[:n_bars].copy()
    if visible.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=list(range(len(visible))),
        open=visible["open"], high=visible["high"],
        low=visible["low"], close=visible["close"],
        increasing_line_color="#00C805", decreasing_line_color="#FF5000",
        increasing_fillcolor="#00C805", decreasing_fillcolor="#FF5000",
        name="Price",
    ), row=1, col=1)

    # VWAP line
    if "vwap" in visible.columns:
        fig.add_trace(go.Scatter(
            x=list(range(len(visible))),
            y=visible["vwap"], mode="lines",
            line=dict(color="#00D4FF", width=1.5, dash="dot"),
            name="VWAP",
        ), row=1, col=1)

    # EMA 9
    if "ema9" in visible.columns:
        fig.add_trace(go.Scatter(
            x=list(range(len(visible))),
            y=visible["ema9"], mode="lines",
            line=dict(color="#FFD700", width=1),
            name="EMA 9",
        ), row=1, col=1)

    # Trade markers
    for trade in state.closed_trades:
        if trade.entry_bar < n_bars:
            fig.add_trace(go.Scatter(
                x=[trade.entry_bar], y=[trade.entry_price],
                mode="markers", marker=dict(symbol="triangle-up", size=12, color="#00C805"),
                name=f"Buy #{trade.trade_id}", showlegend=False,
            ), row=1, col=1)
        if trade.exit_bar is not None and trade.exit_bar < n_bars:
            color = "#00C805" if trade.pnl >= 0 else "#FF5000"
            fig.add_trace(go.Scatter(
                x=[trade.exit_bar], y=[trade.exit_price],
                mode="markers", marker=dict(symbol="triangle-down", size=12, color=color),
                name=f"Sell #{trade.trade_id}", showlegend=False,
            ), row=1, col=1)

    # Open position markers
    if state.open_position and state.open_position.entry_bar < n_bars:
        pos = state.open_position
        fig.add_trace(go.Scatter(
            x=[pos.entry_bar], y=[pos.entry_price],
            mode="markers", marker=dict(symbol="triangle-up", size=14, color="#00D4FF"),
            name="Open Entry", showlegend=False,
        ), row=1, col=1)
        # Stop loss line
        fig.add_hline(y=pos.stop_loss, line_dash="dash", line_color="#FF5000",
                      annotation_text=f"SL ${pos.stop_loss:.2f}",
                      annotation_font_color="#FF5000", row=1, col=1)
        # Take profit line
        fig.add_hline(y=pos.take_profit, line_dash="dash", line_color="#00C805",
                      annotation_text=f"TP ${pos.take_profit:.2f}",
                      annotation_font_color="#00C805", row=1, col=1)

    # Volume bars
    colors = ["#00C805" if visible["close"].iloc[i] >= visible["open"].iloc[i]
              else "#FF5000" for i in range(len(visible))]
    fig.add_trace(go.Bar(
        x=list(range(len(visible))),
        y=visible["volume"], marker_color=colors,
        name="Volume", showlegend=False,
    ), row=2, col=1)

    # Layout
    current_price = visible["close"].iloc[-1]
    fig.update_layout(
        plot_bgcolor="#0E0E0E",
        paper_bgcolor="#0A0A0A",
        font_color="white",
        height=520,
        margin=dict(l=50, r=50, t=30, b=30),
        showlegend=False,
        xaxis_rangeslider_visible=False,
        xaxis2_title="Bar #",
    )
    fig.update_xaxes(gridcolor="#1A1A1A", showgrid=True)
    fig.update_yaxes(gridcolor="#1A1A1A", showgrid=True)

    return fig


# ---------------------------------------------------------------------------
# Scorecard rendering
# ---------------------------------------------------------------------------

def _render_scorecard(state: ReplayState):
    """Render the end-of-session scorecard."""
    sc = generate_scorecard(state)

    st.markdown("---")
    st.markdown("## Session Scorecard")

    if sc["total_trades"] == 0:
        st.info(sc.get("message", "No trades taken."))
        return

    # Grade banner
    grade_colors = {"A": "#00C805", "B": "#00D4FF", "C": "#FFD700",
                    "C-": "#FFA500", "D+": "#FF5000", "D": "#FF0000", "F": "#FF0000"}
    gc = grade_colors.get(sc["grade"], "#B0B0B0")

    st.markdown(f"""
    <div style="text-align:center; padding:20px; background:linear-gradient(135deg, #141414, #1E1E1E);
                border:2px solid {gc}; border-radius:16px; margin-bottom:20px;">
        <div style="font-size:64px; font-weight:bold; color:{gc};">{sc['grade']}</div>
        <div style="font-size:16px; color:#B0B0B0; margin-top:8px;">{sc['grade_message']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        color = "#00C805" if sc["total_pnl"] >= 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#B0B0B0; font-size:11px;">TOTAL P&L</div>
            <div style="color:{color}; font-size:22px; font-weight:bold;">
                {'+'if sc['total_pnl']>=0 else ''}${sc['total_pnl']:.2f}
            </div>
        </div>""", unsafe_allow_html=True)
    with c2:
        color = "#00C805" if sc["win_rate"] >= 50 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#B0B0B0; font-size:11px;">WIN RATE</div>
            <div style="color:{color}; font-size:22px; font-weight:bold;">{sc['win_rate']}%</div>
            <div style="font-size:11px; color:#666;">{sc['winners']}W / {sc['losers']}L</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#B0B0B0; font-size:11px;">AVG R-MULTIPLE</div>
            <div style="color:#00D4FF; font-size:22px; font-weight:bold;">{sc['avg_r_multiple']}R</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        pf = sc["profit_factor"]
        pf_str = f"{pf}" if isinstance(pf, str) else f"{pf:.2f}"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#B0B0B0; font-size:11px;">PROFIT FACTOR</div>
            <div style="color:#FFD700; font-size:22px; font-weight:bold;">{pf_str}</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#B0B0B0; font-size:11px;">MAX DRAWDOWN</div>
            <div style="color:#FF5000; font-size:22px; font-weight:bold;">{sc['max_drawdown']}%</div>
        </div>""", unsafe_allow_html=True)

    # Trade log
    if state.closed_trades:
        st.markdown("### Trade Log")
        rows = []
        for t in state.closed_trades:
            rows.append({
                "#": t.trade_id,
                "Side": t.side,
                "Entry": f"${t.entry_price:.2f}",
                "Exit": f"${t.exit_price:.2f}" if t.exit_price else "-",
                "Size": t.size,
                "P&L": f"${t.pnl:+.2f}",
                "R": f"{t.r_multiple:.1f}R",
                "Reason": t.exit_reason or "-",
                "Bars Held": (t.exit_bar - t.entry_bar) if t.exit_bar else "-",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # XP calculation
    xp = 15  # base for completing replay
    if sc["total_pnl"] > 0:
        xp += 10
    if sc["grade"] in ("A", "B"):
        xp += 25
    if sc["win_rate"] >= 60:
        xp += 10

    st.markdown(f"""
    <div style="text-align:center; padding:15px; background:#141414; border-radius:12px;
                border:1px solid #2A2A2A; margin-top:15px;">
        <span style="color:#FFD700; font-size:18px; font-weight:bold;">+{xp} XP</span>
        <span style="color:#B0B0B0;"> earned from this replay session</span>
    </div>
    """, unsafe_allow_html=True)

    return xp


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_market_replay_page():
    """Render the full Market Replay page."""
    user = st.session_state.user

    # ---- Session state init ----
    if "replay_state" not in st.session_state:
        st.session_state.replay_state = None
    if "replay_df" not in st.session_state:
        st.session_state.replay_df = None
    if "replay_scenario" not in st.session_state:
        st.session_state.replay_scenario = None
    if "replay_messages" not in st.session_state:
        st.session_state.replay_messages = []
    if "replay_auto_play" not in st.session_state:
        st.session_state.replay_auto_play = False

    state: ReplayState = st.session_state.replay_state
    df: pd.DataFrame = st.session_state.replay_df

    # ---- No active session: show scenario picker ----
    if state is None or state.is_finished:
        _render_scenario_picker(user, state)
        return

    # ---- Active session ----
    scenario = st.session_state.replay_scenario

    # Header bar
    col_title, col_bar, col_pnl, col_pos = st.columns([2.5, 1.5, 1.5, 1.5])
    with col_title:
        st.markdown(f"### {scenario['name']}")
    with col_bar:
        pct = state.current_bar / (len(df) - 1) * 100
        st.markdown(f"""
        <div style="margin-top:12px;">
            <div style="font-size:11px; color:#B0B0B0;">Bar {state.current_bar}/{len(df)-1}</div>
            <div class="xp-progress-container" style="height:8px;">
                <div class="xp-progress-bar" style="width:{pct}%;"></div>
            </div>
        </div>""", unsafe_allow_html=True)
    with col_pnl:
        pnl_color = "#00C805" if state.daily_pnl >= 0 else "#FF5000"
        st.markdown(f"""
        <div style="text-align:center; margin-top:8px;">
            <div style="font-size:11px; color:#B0B0B0;">SESSION P&L</div>
            <div style="color:{pnl_color}; font-size:20px; font-weight:bold;">
                {'+'if state.daily_pnl>=0 else ''}${state.daily_pnl:.2f}
            </div>
        </div>""", unsafe_allow_html=True)
    with col_pos:
        if state.open_position:
            pos = state.open_position
            cur_price = float(df.iloc[state.current_bar]["close"])
            unrealized = (cur_price - pos.entry_price) * pos.size
            u_color = "#00C805" if unrealized >= 0 else "#FF5000"
            st.markdown(f"""
            <div style="text-align:center; margin-top:8px;">
                <div style="font-size:11px; color:#B0B0B0;">OPEN P&L</div>
                <div style="color:{u_color}; font-size:20px; font-weight:bold;">
                    {'+'if unrealized>=0 else ''}${unrealized:.2f}
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="text-align:center; margin-top:8px;">
                <div style="font-size:11px; color:#B0B0B0;">CAPITAL</div>
                <div style="color:#B0B0B0; font-size:20px; font-weight:bold;">
                    ${state.capital:,.0f}
                </div>
            </div>""", unsafe_allow_html=True)

    # ---- Chart + Order Panel ----
    col_chart, col_panel = st.columns([3.5, 1.2])

    with col_chart:
        n_visible = state.current_bar + 1
        fig = _build_replay_chart(df, n_visible, state)
        current_price = float(df.iloc[state.current_bar]["close"])

        # Price info bar
        bar_data = df.iloc[state.current_bar]
        time_str = bar_data.name.strftime("%H:%M") if hasattr(bar_data.name, "strftime") else str(state.current_bar)
        chg = (current_price - float(df.iloc[0]["open"])) / float(df.iloc[0]["open"]) * 100
        chg_color = "#00C805" if chg >= 0 else "#FF5000"

        st.markdown(f"""
        <div style="display:flex; gap:20px; padding:8px 12px; background:#141414;
                    border-radius:8px; margin-bottom:8px; font-size:13px;">
            <span style="color:#B0B0B0;">Time: <b style="color:white;">{time_str}</b></span>
            <span style="color:#B0B0B0;">Price: <b style="color:white;">${current_price:.2f}</b></span>
            <span style="color:#B0B0B0;">Chg: <b style="color:{chg_color};">{'+'if chg>=0 else ''}{chg:.1f}%</b></span>
            <span style="color:#B0B0B0;">Vol: <b style="color:white;">{int(bar_data['volume']):,}</b></span>
            <span style="color:#B0B0B0;">VWAP: <b style="color:#00D4FF;">${float(bar_data.get('vwap', 0)):.2f}</b></span>
        </div>""", unsafe_allow_html=True)

        st.plotly_chart(fig, use_container_width=True, key="replay_chart")

    with col_panel:
        st.markdown("#### Order Entry")

        # Position info
        if state.open_position:
            pos = state.open_position
            cur = float(df.iloc[state.current_bar]["close"])
            unr = (cur - pos.entry_price) * pos.size
            unr_c = "#00C805" if unr >= 0 else "#FF5000"
            st.markdown(f"""
            <div style="background:#141414; padding:12px; border-radius:8px;
                        border-left:3px solid {unr_c}; margin-bottom:12px;">
                <div style="font-weight:bold; font-size:13px;">LONG {pos.size} shares</div>
                <div style="font-size:12px; color:#888;">
                    Entry: ${pos.entry_price:.2f}<br>
                    SL: ${pos.stop_loss:.2f} | TP: ${pos.take_profit:.2f}<br>
                    Unrealized: <span style="color:{unr_c};">{'+'if unr>=0 else ''}${unr:.2f}</span>
                </div>
            </div>""", unsafe_allow_html=True)

            if st.button("CLOSE POSITION", type="primary", use_container_width=True, key="btn_close"):
                msg = execute_sell(state, df, reason="manual")
                st.session_state.replay_messages.append(("sell", msg))
                # Post-trade feedback
                if state.closed_trades:
                    fb = get_exit_feedback(state.closed_trades[-1])
                    if fb:
                        st.session_state.replay_messages.append(("education", fb))
                st.rerun()
        else:
            # New order form
            with st.form("replay_order", clear_on_submit=True):
                setup = st.selectbox("Setup", [scenario["setup"], "Other"])
                size = st.number_input("Shares", min_value=10, max_value=5000,
                                       value=100, step=50)
                sl_default = round(current_price * 0.97, 2)
                tp_default = round(current_price * 1.06, 2)
                stop_loss = st.number_input("Stop Loss", value=sl_default,
                                            min_value=0.01, step=0.01, format="%.2f")
                take_profit = st.number_input("Take Profit", value=tp_default,
                                              min_value=0.01, step=0.01, format="%.2f")

                # R:R display
                risk = abs(current_price - stop_loss)
                reward = abs(take_profit - current_price)
                rr = reward / risk if risk > 0 else 0
                rr_color = "#00C805" if rr >= 2 else "#FFD700" if rr >= 1.5 else "#FF5000"

                st.markdown(f"""
                <div style="font-size:12px; padding:8px; background:#1E1E1E; border-radius:6px;">
                    Risk: <span style="color:#FF5000;">${risk:.2f}/sh</span> |
                    Reward: <span style="color:#00C805;">${reward:.2f}/sh</span><br>
                    R:R = <span style="color:{rr_color}; font-weight:bold;">{rr:.1f}:1</span> |
                    Max Loss: <span style="color:#FF5000;">${risk*size:.0f}</span>
                </div>""", unsafe_allow_html=True)

                submitted = st.form_submit_button("BUY", type="primary",
                                                   use_container_width=True)
                if submitted:
                    msg = execute_buy(state, df, size, stop_loss, take_profit,
                                      setup=setup)
                    st.session_state.replay_messages.append(("buy", msg))
                    # Entry feedback
                    fb = get_entry_feedback(state, df)
                    if fb:
                        st.session_state.replay_messages.append(("education", fb))
                    st.rerun()

        st.markdown("---")

        # Closed trades summary
        if state.closed_trades:
            st.markdown(f"**Trades: {len(state.closed_trades)}**")
            for t in reversed(state.closed_trades[-3:]):
                c = "#00C805" if t.pnl >= 0 else "#FF5000"
                st.markdown(f"""
                <div style="font-size:11px; padding:6px; background:#141414;
                            border-radius:4px; margin:3px 0; border-left:2px solid {c};">
                    #{t.trade_id} {'+'if t.pnl>=0 else ''}${t.pnl:.2f} ({t.r_multiple:.1f}R)
                    — {t.exit_reason}
                </div>""", unsafe_allow_html=True)

    # ---- Controls bar ----
    st.markdown("---")
    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, ctrl6, ctrl7 = st.columns([1, 1, 1, 1, 1.5, 1.5, 1.5])

    with ctrl1:
        if st.button("Step", use_container_width=True, key="btn_step",
                      disabled=state.is_finished):
            msg = advance_bar(state, df)
            if msg:
                st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    with ctrl2:
        if st.button("+5 Bars", use_container_width=True, key="btn_5",
                      disabled=state.is_finished):
            for _ in range(5):
                if state.is_finished:
                    break
                msg = advance_bar(state, df)
                if msg:
                    st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    with ctrl3:
        if st.button("+15 Bars", use_container_width=True, key="btn_15",
                      disabled=state.is_finished):
            for _ in range(15):
                if state.is_finished:
                    break
                msg = advance_bar(state, df)
                if msg:
                    st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    with ctrl4:
        if st.button("+30 Bars", use_container_width=True, key="btn_30",
                      disabled=state.is_finished):
            for _ in range(30):
                if state.is_finished:
                    break
                msg = advance_bar(state, df)
                if msg:
                    st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    with ctrl5:
        if st.button("Skip to End", use_container_width=True, key="btn_end",
                      disabled=state.is_finished):
            while not state.is_finished:
                msg = advance_bar(state, df)
                if msg:
                    st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    with ctrl6:
        if st.button("End Session", use_container_width=True, key="btn_quit"):
            # Force close
            if state.open_position:
                execute_sell(state, df, reason="eod")
            state.is_finished = True
            state.is_playing = False
            st.rerun()

    with ctrl7:
        bar_jump = st.number_input("Jump to bar", min_value=state.current_bar,
                                   max_value=len(df)-1, value=state.current_bar,
                                   key="bar_jump", label_visibility="collapsed")
        if bar_jump > state.current_bar:
            while state.current_bar < bar_jump and not state.is_finished:
                msg = advance_bar(state, df)
                if msg:
                    st.session_state.replay_messages.append(("system", msg))
            st.rerun()

    # ---- Message log ----
    if st.session_state.replay_messages:
        st.markdown("#### Activity Log")
        for msg_type, msg in reversed(st.session_state.replay_messages[-8:]):
            if msg_type == "buy":
                icon, color = "BUY", "#00C805"
            elif msg_type == "sell":
                icon, color = "SELL", "#FF5000"
            elif msg_type == "system":
                icon, color = "SYS", "#FFD700"
            elif msg_type == "education":
                icon, color = "TIP", "#00D4FF"
            else:
                icon, color = "INFO", "#B0B0B0"

            st.markdown(f"""
            <div style="padding:8px 12px; background:#141414; border-radius:6px;
                        margin:4px 0; border-left:3px solid {color}; font-size:13px;">
                <span style="color:{color}; font-weight:bold;">[{icon}]</span> {msg}
            </div>""", unsafe_allow_html=True)

    # ---- Scorecard (if finished) ----
    if state.is_finished:
        xp = _render_scorecard(state)
        if xp:
            add_xp_to_user(user["id"], xp)
            # Save to DB
            sc = generate_scorecard(state)
            try:
                close_replay_session(
                    user_id=user["id"],
                    scenario_id=state.scenario_id,
                    total_trades=sc["total_trades"],
                    total_pnl=sc["total_pnl"],
                    win_rate=sc["win_rate"],
                    grade=sc["grade"],
                    xp_earned=xp,
                )
            except Exception:
                pass  # DB not yet migrated — graceful fallback

        if st.button("New Replay Session", type="primary", use_container_width=True):
            st.session_state.replay_state = None
            st.session_state.replay_df = None
            st.session_state.replay_scenario = None
            st.session_state.replay_messages = []
            st.rerun()


# ---------------------------------------------------------------------------
# Scenario picker
# ---------------------------------------------------------------------------

def _render_scenario_picker(user, finished_state: ReplayState = None):
    """Show the scenario selection screen."""
    st.markdown("<h1>Market Replay</h1>", unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#141414; padding:16px; border-radius:10px; margin-bottom:20px;
                border-left:4px solid #00D4FF;">
        <div style="font-size:15px; color:#B0B0B0;">
            Revive real market scenarios bar by bar. Practice entries, exits, and risk management
            in realistic conditions — without risking a cent.
        </div>
    </div>
    """, unsafe_allow_html=True)

    nivel = user["nivel_actual"]
    available = get_scenarios_for_level(nivel)

    # Difficulty filter
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        diff_filter = st.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"])

    if diff_filter != "All":
        available = [s for s in available if s["difficulty"] == diff_filter.lower()]

    # Scenario cards (3 per row)
    for i in range(0, len(available), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(available):
                break
            s = available[idx]
            diff_colors = {"easy": "#00C805", "medium": "#FFD700", "hard": "#FF5000"}
            dc = diff_colors.get(s["difficulty"], "#B0B0B0")

            with col:
                st.markdown(f"""
                <div style="background:#141414; padding:16px; border-radius:12px;
                            border:1px solid #2A2A2A; min-height:180px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="font-weight:bold; font-size:14px;">{s['name']}</span>
                        <span style="color:{dc}; font-size:11px; font-weight:bold;
                                     text-transform:uppercase;">{s['difficulty']}</span>
                    </div>
                    <div style="font-size:12px; color:#888; margin-bottom:12px;">{s['description'][:120]}...</div>
                    <div style="font-size:11px; color:#666;">
                        Setup: {s['setup']} | ~{s['total_minutes']} min | Lvl {s['level_required']}+
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"Start", key=f"start_{s['id']}", use_container_width=True):
                    _start_scenario(s, user)

    # Locked scenarios
    locked = [s for s in SCENARIOS if s["level_required"] > nivel]
    if locked:
        st.markdown("---")
        st.markdown(f"### Locked Scenarios (Level {nivel + 1}+)")
        for s in locked:
            st.markdown(f"""
            <div style="background:#0E0E0E; padding:12px; border-radius:8px; margin:6px 0;
                        opacity:0.5; border:1px solid #1A1A1A;">
                {s['name']} — <span style="color:#FF5000;">Requires Level {s['level_required']}</span>
            </div>""", unsafe_allow_html=True)


def _start_scenario(scenario: dict, user: dict):
    """Initialize and start a replay scenario."""
    with st.spinner(f"Loading {scenario['name']}..."):
        cfg, df = generate_scenario_data(scenario["id"])

        state = create_replay_state(
            scenario_id=scenario["id"],
            capital=user["capital_virtual"],
        )
        state.total_bars = len(df)

        st.session_state.replay_state = state
        st.session_state.replay_df = df
        st.session_state.replay_scenario = cfg
        st.session_state.replay_messages = [
            ("education", cfg["briefing"]),
        ]
        st.session_state.replay_auto_play = False

        # Save session start to DB
        try:
            create_replay_session(user["id"], scenario["id"], scenario["name"])
        except Exception:
            pass  # DB not yet migrated

    st.rerun()
