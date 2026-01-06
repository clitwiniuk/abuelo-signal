import streamlit as st
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("📝 Trading Journal", "Record your observations and trading notes")

render_section_header("📝 Trading Journal & Notes")

# Add new note
with st.form("note_form", clear_on_submit=True):
    st.markdown("#### ✍️ Add New Note")
    new_note = st.text_area(
        "Note content:",
        placeholder="Ex: Noticed strong momentum in tech sector today. Consider adjusting position sizes...",
        height=100
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        submitted = st.form_submit_button("💾 Save Note", use_container_width=True)

    if submitted and new_note:
        utils.save_note(new_note)
        st.success("✅ Note saved successfully!")
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Display existing notes
notes = utils.get_notes()

if notes:
    st.markdown(f"#### 📚 Saved Notes ({len(notes)})")

    for i, note in enumerate(reversed(notes), 1):
        with st.container():
            st.markdown(f"""
            <div class="metric-card fade-in">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <div class="metric-label">Note #{len(notes) - i + 1}</div>
                        <div style="margin-top: 0.5rem; color: var(--text-primary); line-height: 1.6;">
                            {note}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🗑️ Clear All Notes", type="secondary"):
        utils.clear_notes()
        st.success("All notes cleared")
        st.rerun()
else:
    st.info("📝 No notes yet. Add your first trading note above!")
