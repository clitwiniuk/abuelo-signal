import streamlit as st
import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard.dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("⚙️ Configuration", "Strategy settings and system configuration")

render_section_header("⚙️ Strategy Configuration")

config = utils.read_config()
if not config:
    st.error("❌ Configuration file not found")
else:
    strategies = [s for s in config.sections() if s.endswith('_STRATEGY')]

    if strategies:
        st.info("💡 Toggle strategies on/off. Other parameters must be edited in config.ini file for safety.")

        for strat in strategies:
            strat_name = strat.replace('_STRATEGY', '').replace('_', ' ').title()

            with st.expander(f"🤖 {strat_name}", expanded=False):
                col1, col2 = st.columns([1, 2])

                with col1:
                    is_enabled = config.getboolean(strat, 'enabled', fallback=False)

                    new_state = st.toggle(
                        f"Enable {strat_name}",
                        value=is_enabled,
                        key=f"toggle_{strat}"
                    )

                    if new_state != is_enabled:
                        utils.update_config(strat, 'enabled', 'true' if new_state else 'false')
                        st.success(f"✅ {strat_name} {'enabled' if new_state else 'disabled'}")
                        st.rerun()

                with col2:
                    st.markdown("**Configuration Parameters:**")

                    # Display all config options for this strategy
                    params_df = []
                    for key, value in config.items(strat):
                        if key != 'enabled':
                            params_df.append({"Parameter": key, "Value": value})

                    if params_df:
                        st.dataframe(pd.DataFrame(params_df), use_container_width=True, hide_index=True)
                    else:
                        st.caption("No additional parameters configured")
    else:
        st.warning("No strategies found in configuration")
