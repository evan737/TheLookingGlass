import streamlit as st
import pandas as pd

from database import initialize_database, get_recent_scans_as_dicts


st.set_page_config(
    page_title="The Looking Glass",
    page_icon="🔮",
    layout="wide",
)

initialize_database()

st.title("🔮 The Looking Glass")
st.caption("Event Market Intelligence Platform")

st.sidebar.header("Controls")

limit = st.sidebar.slider("Recent scans to show", 10, 1000, 200)

if st.sidebar.button("Refresh"):
    st.rerun()

rows = get_recent_scans_as_dicts(limit)
df = pd.DataFrame(rows)

col1, col2, col3 = st.columns(3)

col1.metric("Saved Rows", len(df))
col2.metric("Unique Markets", df["Ticker"].nunique() if not df.empty else 0)
col3.metric("Latest Scan", df["Timestamp"].max() if not df.empty else "None")

st.divider()

st.subheader("Recent Market Scans")

if df.empty:
    st.warning("No database scans found yet. Start scanner_service.py first.")
else:
    st.dataframe(df, use_container_width=True, height=650)