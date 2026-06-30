"""Dashboard — redirects to search (kept for backwards compat)."""

import streamlit as st


def render() -> None:
    st.session_state.page = "search"
    st.rerun()
