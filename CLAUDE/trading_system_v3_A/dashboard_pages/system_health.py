import streamlit as st
import time
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
render_header("🛡️ System Health", "Monitor system status and worker health")

render_section_header("🛡️ System Health Monitor")

# Worker Status
st.markdown("#### Active Workers")

workers = utils.get_worker_statuses()
if workers:
    cols = st.columns(min(len(workers), 4))

    for i, (name, details) in enumerate(workers.items()):
        with cols[i % 4]:
            status = details['status']
            is_active = status == 'active'

            status_html = f"""
            <div class="metric-card">
                <div class="metric-label">{name}</div>
                <div class="status-badge {'online' if is_active else 'offline'}">
                    <span class="status-indicator {'online' if is_active else 'offline'}"></span>
                    {status.upper()}
                </div>
            </div>
            """
            st.markdown(status_html, unsafe_allow_html=True)
else:
    st.info("No worker information available")

st.markdown("<br>", unsafe_allow_html=True)

# System Controls
render_section_header("🚨 Emergency Controls")

st.warning("""
**⚠️ WARNING: Emergency Shutdown**

Pressing the kill switch will immediately terminate all trading processes.
- Active positions may be left open
- Pending orders may not be cancelled
- Use only in emergency situations
""")

col_btn, col_space = st.columns([1, 3])

with col_btn:
    if st.button("🛑 EMERGENCY KILL SWITCH", type="primary", use_container_width=True):
        with st.spinner("Initiating emergency shutdown..."):
            try:
                import subprocess
                subprocess.run(["python3", "scripts/tools/emergency_kill.py"], timeout=5)
                st.success("✅ System terminated successfully")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error during shutdown: {e}")
