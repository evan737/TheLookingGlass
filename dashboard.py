import streamlit as st
import pandas as pd

from database import initialize_database, get_recent_scans_as_dicts
from opportunity_engine import build_opportunities
from kalshi import get_registered_markets
from market_registry import MARKET_SERIES

st.set_page_config(
    page_title="The Looking Glass",
    page_icon="🔮",
    layout="wide",
)

initialize_database()


@st.cache_data(ttl=300)
def load_opportunities():
    """
    Cached for 5 minutes so the auto-refreshing dashboard doesn't hammer
    the weather API on every rerun.
    """
    try:
        markets = get_registered_markets(MARKET_SERIES)
        return build_opportunities(markets)
    except Exception:
        return []


def load_data(limit):
    rows = get_recent_scans_as_dicts(limit)
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["YES Bid ¢"] = (df["YES Bid"] * 100).round(1)
    df["YES Ask ¢"] = (df["YES Ask"] * 100).round(1)
    df["Last Price ¢"] = (df["Last Price"] * 100).round(1)

    df["Spread ¢"] = (df["YES Ask ¢"] - df["YES Bid ¢"]).round(1)

    df["Market Price %"] = df["YES Ask ¢"].round(1)

    df["Opportunity Score"] = (
        (100 - df["Market Price %"])
        .clip(lower=0, upper=100)
        .round(1)
    )

    df["Status"] = df["YES Ask ¢"].apply(
        lambda x: "Watch" if x > 0 else "No Price"
    )

    return df


st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #050510 0%, #111126 45%, #1b1035 100%);
    color: #f5f3ff;
}
[data-testid="stSidebar"] {
    background-color: #090914;
}
.metric-card {
    background: rgba(255,255,255,0.06);
    padding: 18px;
    border-radius: 18px;
    border: 1px solid rgba(168,85,247,0.35);
}
.big-title {
    font-size: 44px;
    font-weight: 800;
    letter-spacing: -1px;
}
.subtitle {
    color: #c4b5fd;
    font-size: 16px;
}
.opportunity-card {
    background: rgba(15, 15, 35, 0.95);
    border: 1px solid rgba(168,85,247,0.45);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 14px;
}
.small-muted {
    color: #a1a1aa;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="big-title">🔮 The Looking Glass</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Event Market Intelligence Platform</div>', unsafe_allow_html=True)

st.sidebar.header("Controls")
limit = st.sidebar.slider("Rows to load", 50, 2000, 500)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_seconds = st.sidebar.slider("Refresh seconds", 5, 60, 15)

if st.sidebar.button("Manual refresh"):
    st.rerun()

if auto_refresh:
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="{refresh_seconds}">
        """,
        unsafe_allow_html=True,
    )

df = load_data(limit)

if df.empty:
    st.warning("No scan data yet. Start scanner_service.py first.")
    st.stop()

latest_scan = df["Timestamp"].max()
unique_markets = df["Ticker"].nunique()
watch_count = len(df[df["Status"] == "Watch"])

col1, col2, col3, col4 = st.columns(4)

col1.metric("Latest Scan", latest_scan.strftime("%H:%M:%S"))
col2.metric("Unique Markets", unique_markets)
col3.metric("Watchlist", watch_count)
col4.metric("Rows Loaded", len(df))

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Live Market Feed")

    categories = ["All"] + sorted(df["Category"].dropna().unique().tolist())
    selected_category = st.selectbox("Category", categories)

    search = st.text_input("Search markets")

    filtered = df.copy()

    if selected_category != "All":
        filtered = filtered[filtered["Category"] == selected_category]

    if search:
        filtered = filtered[
            filtered["Title"].str.contains(search, case=False, na=False)
            | filtered["Ticker"].str.contains(search, case=False, na=False)
        ]

    display_cols = [
        "Timestamp",
        "Category",
        "Series",
        "Title",
        "YES Bid ¢",
        "YES Ask ¢",
        "Last Price ¢",
        "Spread ¢",
        "Status",
    ]

    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        height=620,
    )

with right:
    st.subheader("Top Opportunities")

    opportunities = load_opportunities()

    if not opportunities:
        st.info(
            "No weather opportunities right now -- either no KXHIGHNY "
            "markets are open, or their dates fall outside the forecast "
            "window."
        )
    else:
        for opp in opportunities[:5]:
            edge = opp["edge_pct"]
            direction = (
                "YES looks underpriced" if edge > 0
                else "NO looks underpriced" if edge < 0
                else "Fairly priced"
            )
            st.markdown(
                f"""
                <div class="opportunity-card">
                    <b>{opp["city"]} &mdash; {opp["bracket"]}</b><br>
                    <span class="small-muted">{opp["target_date"]} &middot; {direction}</span><br><br>
                    Market: <b>{opp["market_prob_pct"]}%</b> &nbsp;&nbsp; Model: <b>{opp["model_prob_pct"]}%</b><br>
                    Edge: <b>{edge:+.1f}%</b> &nbsp;&nbsp; Confidence: <b>{opp["confidence"]}%</b>
                </div>
                """,
                unsafe_allow_html=True,
            ) 

    st.subheader("Forecast Detail")
    if opportunities:
        latest = opportunities[0]
        st.caption(
            f"NYC forecast for {latest['target_date']}: "
            f"{latest['forecast_mean_f']}\u00b0F "
            f"(\u00b1 {latest['forecast_std_f']}\u00b0F model spread)"
        )
    else:
        st.caption("Forecast will appear once opportunities are found.")