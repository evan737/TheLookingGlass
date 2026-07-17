import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from database import initialize_database, get_recent_scans_as_dicts
from opportunity_engine import build_opportunities
from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from tennis_opportunity_engine import build_tennis_opportunities, TENNIS_SERIES_TICKERS
from sportsbook_odds import fetch_atp_matches, fetch_wta_matches
from tennis_utils import normalize_player_name
from claims_opportunity_engine import build_claims_opportunities, CLAIMS_SERIES_TICKER
from risk_manager import (
    drawdown_pct, trades_opened_today, category_exposure_pct, all_correlated_group_exposures,
    kill_switch_engaged, MAX_DRAWDOWN_PCT, MAX_DAILY_TRADES, MAX_CATEGORY_EXPOSURE_PCT,
    MAX_CORRELATED_GROUP_EXPOSURE_PCT,
)
from bankroll import get_current_bankroll, STARTING_BANKROLL

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


@st.cache_data(ttl=1800)
def load_tennis_opportunities(odds_api_key):
    """
    Cached for 30 minutes -- much longer than weather. The odds API's free
    tier is capped at 100 requests/hour, and this dashboard can auto-refresh
    every 15 seconds, so without a long cache this would burn through the
    quota almost immediately.
    """
    try:
        markets = get_registered_markets(MARKET_SERIES)
        tennis_markets = [m for m in markets if m.get("series_ticker") in TENNIS_SERIES_TICKERS]

        target_surnames = {
            normalize_player_name(m.get("yes_sub_title", ""))
            for m in tennis_markets
        }
        target_surnames.discard("")

        if not target_surnames:
            return []

        atp_matches = fetch_atp_matches(odds_api_key, target_surnames)
        wta_matches = fetch_wta_matches(odds_api_key, target_surnames)

        return build_tennis_opportunities(tennis_markets, atp_matches + wta_matches)
    except Exception as error:
        st.session_state["tennis_error"] = str(error)
        return []


@st.cache_data(ttl=3600)
def load_claims_opportunities(fred_api_key):
    """
    Cached for 1 hour -- jobless claims data only updates weekly, so
    there's no need to hit FRED on every dashboard refresh.
    """
    try:
        markets = get_registered_markets(MARKET_SERIES)
        claims_markets = [m for m in markets if m.get("series_ticker") == CLAIMS_SERIES_TICKER]
        return build_claims_opportunities(claims_markets, fred_api_key)
    except Exception as error:
        st.session_state["claims_error"] = str(error)
        return []


@st.cache_data(ttl=10)
def load_bankroll_status():
    """
    Bundles the 3 risk-manager reads into one cached call. Without this,
    every single rerun (every refresh tick, every widget interaction)
    re-reads paper_trades.csv and paper_trade_results.csv from disk
    multiple times over -- this is the main cause of the dashboard
    feeling frozen on refresh.
    """
    return get_current_bankroll(), drawdown_pct(), trades_opened_today()


@st.cache_data(ttl=10)
def load_category_exposures():
   return {cat: category_exposure_pct(cat) for cat in ["Weather", "Economics", "Tennis", "Futures"]}

@st.cache_data(ttl=10)
def load_correlation_exposures():
    return all_correlated_group_exposures()

@st.cache_data(ttl=10)
def load_trades_df():
    trade_log_path = Path("paper_trades.csv")
    if not trade_log_path.exists():
        return None
    trades_df = pd.read_csv(trade_log_path)
    trades_df["timestamp"] = pd.to_datetime(trades_df["timestamp"])
    return trades_df.sort_values("timestamp", ascending=False)


@st.cache_data(ttl=10)
def load_results_df():
    results_path = Path("paper_trade_results.csv")
    if not results_path.exists():
        return None
    return pd.read_csv(results_path)


def infer_category_from_ticker(ticker):
    """
    Fallback category inference from the ticker prefix. Needed because
    some settled trades are old enough that their ticker no longer
    appears in the current paper_trades.csv (it's been rotated into
    paper_trades_old.csv), so a straight join against the trade log
    misses them and they'd otherwise show up as "Unknown".
    """
    if not isinstance(ticker, str):
        return "Unknown"
    if ticker.startswith("KXHIGH"):
        return "Weather"
    if ticker.startswith("KXATPMATCH") or ticker.startswith("KXWTAMATCH"):
        return "Tennis"
    if ticker.startswith("KXATP-") or ticker.startswith("KXWTA-"):
        return "Futures"
    if ticker.startswith("KXJOBLESSCLAIMS"):
        return "Economics"
    return "Unknown"


@st.cache_data(ttl=10)
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
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
    --bg: #0A0C0E;
    --panel: #14171B;
    --panel-raised: #1A1E23;
    --border: rgba(255,255,255,0.08);
    --border-strong: rgba(255,255,255,0.16);
    --text: #E8EAED;
    --text-muted: #7A8290;
    --cyan: #5EEAD4;
    --amber: #F5A623;
    --green: #22C55E;
    --red: #EF4444;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}
[data-testid="stSidebar"] {
    background-color: #0D0F12;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Terminal-style headers */
h1, h2, h3, .big-title {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -0.01em;
}
h2, h3, [data-testid="stMarkdownContainer"] h3 {
    text-transform: uppercase;
    font-size: 13px !important;
    letter-spacing: 0.12em !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin-bottom: 12px !important;
}

/* All numbers/data get monospace with tabular alignment */
[data-testid="stMetricValue"], [data-testid="stMetricDelta"], .stDataFrame, p, span, div {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}

.big-title {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
    text-transform: none;
    border: none;
}
.subtitle {
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 4px;
}

/* Ticker strip -- the signature element */
.ticker-strip {
    display: flex;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
    margin: 16px 0 20px 0;
    background: var(--panel);
}
.ticker-chip {
    flex: 1;
    padding: 10px 16px;
    border-right: 1px solid var(--border);
}
.ticker-chip:last-child { border-right: none; }
.ticker-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 3px;
}
.ticker-value {
    font-size: 18px;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.ticker-value.pos { color: var(--green); }
.ticker-value.neg { color: var(--red); }
.ticker-value.cyan { color: var(--cyan); }
.ticker-value.amber { color: var(--amber); }

/* Opportunity cards -- sharp terminal panels, not rounded glowing cards */
.opportunity-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-left: 2px solid var(--cyan);
    border-radius: 2px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
}
.opportunity-card.negative-edge {
    border-left-color: var(--amber);
}
.small-muted {
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Tabs -- sharpen and de-emphasize the default rounded pill look */
[data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
[data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace !important;
    text-transform: uppercase;
    font-size: 12px !important;
    letter-spacing: 0.08em;
    color: var(--text-muted) !important;
}
[aria-selected="true"] {
    color: var(--cyan) !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
}

/* Metrics -- give them real bordered stat-block panels instead of
   floating default Streamlit styling */
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 12px 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
[data-testid="stMetricLabel"] {
    text-transform: uppercase;
    font-size: 10px !important;
    letter-spacing: 0.08em;
    color: var(--text-muted) !important;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 600 !important;
}

/* Sidebar widgets -- sharpen corners, tint to match terminal palette */
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
    background-color: var(--panel-raised) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 2px !important;
    color: var(--text) !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] div[role="slider"] {
    background-color: var(--cyan) !important;
}
[data-testid="stSidebar"] button {
    background-color: var(--panel-raised) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 2px !important;
    color: var(--cyan) !important;
    text-transform: uppercase;
    font-size: 11px !important;
    letter-spacing: 0.06em;
}
[data-testid="stSidebar"] button:hover {
    border-color: var(--cyan) !important;
}

/* Progress bars (risk exposure) -- match palette */
[data-testid="stProgress"] > div > div {
    background-color: var(--cyan) !important;
}

/* Subtle depth on opportunity cards */
.opportunity-card {
    box-shadow: 0 1px 4px rgba(0,0,0,0.25);
}
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="subtitle">Event Market Intelligence Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="big-title">THE LOOKING GLASS</div>', unsafe_allow_html=True)

_bankroll, _dd, _ = load_bankroll_status()
_pnl = _bankroll - STARTING_BANKROLL
_kill = kill_switch_engaged()

st.markdown(f"""
<div class="ticker-strip">
    <div class="ticker-chip">
        <div class="ticker-label">Bankroll</div>
        <div class="ticker-value {'pos' if _pnl >= 0 else 'neg'}">${_bankroll:,.2f}</div>
    </div>
    <div class="ticker-chip">
        <div class="ticker-label">P&amp;L</div>
        <div class="ticker-value {'pos' if _pnl >= 0 else 'neg'}">{_pnl:+,.2f}</div>
    </div>
    <div class="ticker-chip">
        <div class="ticker-label">Drawdown</div>
        <div class="ticker-value {'neg' if _dd > 10 else 'amber' if _dd > 0 else 'cyan'}">{_dd:.1f}%</div>
    </div>
    <div class="ticker-chip">
        <div class="ticker-label">Status</div>
        <div class="ticker-value {'neg' if _kill else 'pos'}">{'HALTED' if _kill else 'ACTIVE'}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("Controls")
limit = st.sidebar.slider("Rows to load", 50, 2000, 500)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_seconds = st.sidebar.slider("Refresh seconds", 15, 120, 30)

if st.sidebar.button("Manual refresh"):
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Tennis")
odds_api_key = st.secrets.get("ODDS_API_KEY", "") or st.sidebar.text_input(
    "Odds API key", type="password",
    help="From odds-api.io. Tennis odds are cached 30 min to protect your free-tier quota."
)

st.sidebar.divider()
st.sidebar.header("Economics")
fred_api_key = st.secrets.get("FRED_API_KEY", "") or st.sidebar.text_input(
    "FRED API key", type="password",
    help="From fred.stlouisfed.org. Jobless claims data is cached 1 hour."
)

if auto_refresh:
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="{refresh_seconds}">
        """,
        unsafe_allow_html=True,
    )

tab_weather, tab_tennis, tab_economics, tab_trades, tab_bankroll = st.tabs(
    ["🌤️ Weather", "🎾 Tennis", "📊 Economics", "📝 Trades", "💰 Bankroll"]
)

# ---------------------------------------------------------------- Weather --
with tab_weather:
    df = load_data(limit)

    if df.empty:
        st.warning("No scan data yet. Start scanner_service.py first.")
    else:
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
                "Timestamp", "Category", "Series", "Title",
                "YES Bid ¢", "YES Ask ¢", "Last Price ¢", "Spread ¢", "Status",
            ]

            st.dataframe(filtered[display_cols], width='stretch', height=620)
        with right:
            st.subheader("Top Opportunities")

            opportunities = load_opportunities()

            if not opportunities:
                st.info(
                    "No weather opportunities right now -- either no registered "
                    "weather markets are open, or their dates fall outside the "
                    "forecast window."
                )
            else:
                for opp in opportunities[:5]:
                    edge = opp["edge_pct"]
                    direction = (
                        "YES looks underpriced" if edge > 0
                        else "NO looks underpriced" if edge < 0
                        else "Fairly priced"
                    )
                    card_class = "opportunity-card negative-edge" if edge < 0 else "opportunity-card"
                    st.markdown(
                        f"""
                        <div class="{card_class}">
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
                    f"{latest['city']} forecast for {latest['target_date']}: "
                    f"{latest['forecast_mean_f']}\u00b0F "
                    f"(\u00b1 {latest['forecast_std_f']}\u00b0F model spread)"
                )
            else:
                st.caption("Forecast will appear once opportunities are found.")

# ----------------------------------------------------------------- Tennis --
with tab_tennis:
    st.subheader("🎾 ATP / WTA Match Opportunities")

    if not odds_api_key:
        st.info("Enter your odds-api.io API key in the sidebar to see tennis opportunities.")
    else:
        tennis_opportunities = load_tennis_opportunities(odds_api_key)

        if "tennis_error" in st.session_state:
            st.warning(f"Tennis data error: {st.session_state['tennis_error']}")

        if not tennis_opportunities:
            st.info(
                "No tennis opportunities right now -- either no ATP/WTA markets "
                "are open on Kalshi, or no sportsbook currently has a line on "
                "those specific players."
            )
        else:
            for opp in tennis_opportunities:
                edge = opp["edge_pct"]
                direction = (
                    "YES looks underpriced" if edge > 0
                    else "NO looks underpriced" if edge < 0
                    else "Fairly priced"
                )
                card_class = "opportunity-card negative-edge" if edge < 0 else "opportunity-card"
                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <b>{opp["player"]}</b><br>
                        <span class="small-muted">{opp["tournament"]} &middot; {direction} &middot; {opp["num_books"]} book(s)</span><br><br>
                        Kalshi: <b>{opp["market_prob_pct"]}%</b> &nbsp;&nbsp; Sportsbook: <b>{opp["sportsbook_prob_pct"]}%</b><br>
                        Edge: <b>{edge:+.1f}%</b> &nbsp;&nbsp; Confidence: <b>{opp["confidence"]}%</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.caption("Tennis odds are cached for 30 minutes to protect your odds-api.io free-tier quota (100 requests/hour).")

# -------------------------------------------------------------- Economics --
with tab_economics:
    st.subheader("📊 Jobless Claims")

    if not fred_api_key:
        st.info("Enter your FRED API key in the sidebar to see jobless claims opportunities.")
    else:
        claims_opportunities = load_claims_opportunities(fred_api_key)

        if "claims_error" in st.session_state:
            st.warning(f"Economics data error: {st.session_state['claims_error']}")

        if not claims_opportunities:
            st.info(
                "No jobless claims opportunities right now -- either no "
                "KXJOBLESSCLAIMS markets have real trading volume, or the "
                "FRED forecast couldn't be built."
            )
        else:
            latest = claims_opportunities[0]
            st.caption(
                f"Last observed initial claims ({latest['last_observed_date']}): "
                f"{latest['last_observed_value']:,.0f} -- FRED trend forecast: "
                f"{latest['forecast_mean']:,.0f} (\u00b1 {latest['forecast_std']:,.0f})"
            )

            for opp in claims_opportunities:
                edge = opp["edge_pct"]
                direction = (
                    "YES looks underpriced" if edge > 0
                    else "NO looks underpriced" if edge < 0
                    else "Fairly priced"
                )
                card_class = "opportunity-card negative-edge" if edge < 0 else "opportunity-card"
                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <b>{opp["bracket"]}</b><br>
                        <span class="small-muted">{direction} &middot; volume {opp["volume"]:,.0f}</span><br><br>
                        Kalshi: <b>{opp["market_prob_pct"]}%</b> &nbsp;&nbsp; Model: <b>{opp["model_prob_pct"]}%</b><br>
                        Edge: <b>{edge:+.1f}%</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.caption(
            "This model is a simple FRED trend estimate, not a genuine multi-source "
            "ensemble like the weather engine -- treat edges here as hypotheses, not "
            "validated signals."
        )

# ----------------------------------------------------------------- Trades --
with tab_trades:
    st.subheader("📝 Paper Trades")

    trades_df = load_trades_df()

    if trades_df is None:
        st.info("No paper trades logged yet. Run paper_trade_scan.py to generate some.")
    else:
        # This tab is "open positions" only -- anything settled (win, loss,
        # or void) has a final outcome and belongs in the Bankroll tab
        # instead, so it doesn't pile up here forever.
        results_df = load_results_df()
        settled_tickers = set()
        if results_df is not None:
            settled_tickers = set(results_df["ticker"])

        settled_count = len(trades_df[trades_df["ticker"].isin(settled_tickers)])
        trades_df = trades_df[~trades_df["ticker"].isin(settled_tickers)].copy()

        buy_yes_count = len(trades_df[trades_df["decision"] == "BUY YES"])
        buy_no_count = len(trades_df[trades_df["decision"] == "BUY NO"])

        tcol1, tcol2, tcol3 = st.columns(3)
        tcol1.metric("Open Paper Trades", len(trades_df))
        tcol2.metric("BUY YES calls", buy_yes_count)
        tcol3.metric("BUY NO calls", buy_no_count)
        if settled_count:
            st.caption(f"{settled_count} settled trade(s) moved to the Bankroll tab.")

        st.dataframe(
            trades_df[[
                "timestamp", "category", "ticker", "title",
                "decision", "yes_bid", "yes_ask", "last_price", "reason",
            ]],
            width='stretch',
            height=400,
        )

# ---------------------------------------------------------------- Bankroll --
with tab_bankroll:
    st.subheader("💰 Bankroll")

    results_df = load_results_df()

    if results_df is None:
        st.info(f"No settled trades yet. Bankroll: ${STARTING_BANKROLL:,.2f} (starting, unchanged)")
    else:
        total_profit = results_df["profit"].sum()
        wins = int(results_df["won"].astype(str).str.strip().eq("True").sum())
        losses = int(results_df["won"].astype(str).str.strip().eq("False").sum())
        voids = int(results_df["result"].astype(str).str.strip().eq("void").sum()) if "result" in results_df.columns else 0
        current_bankroll = STARTING_BANKROLL + total_profit

        bcol1, bcol2, bcol3, bcol4, bcol5 = st.columns(5)
        bcol1.metric("Bankroll", f"${current_bankroll:,.2f}", f"{total_profit:+,.2f}")
        bcol2.metric("Settled Trades", len(results_df))
        bcol3.metric("Wins", wins)
        bcol4.metric("Losses", losses)
        bcol5.metric("Voids", voids, help="Market closed with no yes/no result (walkover, retirement, etc.) -- stake refunded, not counted as a win or loss.")

        # Performance by category -- the aggregate numbers above hide the
        # fact that categories can behave very differently (e.g. one with
        # a long track record vs. another with a handful of trades so
        # far). Category is looked up from the trade log where possible,
        # falling back to inferring it from the ticker prefix for older
        # settled trades that have since rotated out of paper_trades.csv.
        trades_lookup_df = load_trades_df()
        category_lookup = {}
        if trades_lookup_df is not None:
            category_lookup = dict(zip(trades_lookup_df["ticker"], trades_lookup_df["category"]))

        settled_only = results_df[results_df.get("result") != "void"].copy() if "result" in results_df.columns else results_df.copy()
        if not settled_only.empty:
            settled_only["category"] = settled_only["ticker"].map(category_lookup)
            settled_only["category"] = settled_only.apply(
                lambda r: r["category"] if pd.notna(r["category"]) else infer_category_from_ticker(r["ticker"]),
                axis=1,
            )
            settled_only["won_bool"] = settled_only["won"].astype(str).str.strip().eq("True")

            cat_summary = settled_only.groupby("category").agg(
                Trades=("won_bool", "count"),
                Wins=("won_bool", "sum"),
                Profit=("profit", "sum"),
            ).reset_index().rename(columns={"category": "Category"})
            cat_summary["Win Rate"] = (cat_summary["Wins"] / cat_summary["Trades"] * 100).round(1)
            cat_summary["Profit"] = cat_summary["Profit"].round(2)
            cat_summary = cat_summary[["Category", "Trades", "Wins", "Win Rate", "Profit"]].sort_values("Profit", ascending=False)

            st.caption("Performance by category (small sample sizes can swing win rate a lot -- check Trades before reading too much into it):")
            st.dataframe(
                cat_summary,
                width='stretch',
                hide_index=True,
                column_config={
                    "Win Rate": st.column_config.NumberColumn(format="%.1f%%"),
                    "Profit": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

        if "settled_at" in results_df.columns:
            chart_df = results_df.copy()
            chart_df["settled_at"] = pd.to_datetime(chart_df["settled_at"], errors="coerce")
            chart_df = chart_df.dropna(subset=["settled_at"]).sort_values("settled_at")

            if not chart_df.empty:
                chart_df["cumulative_bankroll"] = STARTING_BANKROLL + chart_df["profit"].cumsum()

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=chart_df["settled_at"],
                    y=chart_df["cumulative_bankroll"],
                    mode="lines+markers",
                    line=dict(color="#5EEAD4", width=2),
                    marker=dict(size=5, color="#5EEAD4"),
                    fill="tozeroy",
                    fillcolor="rgba(94, 234, 212, 0.08)",
                ))
                fig.add_hline(y=STARTING_BANKROLL, line_dash="dot", line_color="#7A8290", line_width=1)
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="JetBrains Mono, monospace", color="#E8EAED", size=11),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=260,
                    xaxis=dict(showgrid=False, color="#7A8290"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", color="#7A8290", tickprefix="$"),
                )
                st.plotly_chart(fig, width='stretch')
        else:
            st.caption("Bankroll trend chart will appear once settle_trades.py starts recording settlement timestamps.")

        # Pull in title/category from paper_trades.csv so this table shows
        # what the trade actually was, not just a bare ticker -- the
        # settlement log alone doesn't carry that context.
        settled_display = results_df.copy()
        trades_lookup_df = load_trades_df()
        if trades_lookup_df is not None:
            trade_info = (
                trades_lookup_df[["ticker", "category", "title"]]
                .drop_duplicates(subset="ticker", keep="last")
            )
            settled_display = settled_display.merge(trade_info, on="ticker", how="left")

        if "settled_at" in settled_display.columns:
            settled_display = settled_display.sort_values("settled_at", ascending=False)
        else:
            settled_display = settled_display.sort_values("ticker", ascending=False)

        display_cols = [c for c in [
            "settled_at", "category", "title", "ticker", "decision",
            "result", "won", "profit", "fee", "entry_price",
        ] if c in settled_display.columns]

        st.dataframe(
            settled_display[display_cols],
            width='stretch',
            height=300,
        )

    st.divider()
    st.subheader("Risk Status")

    if kill_switch_engaged():
        st.error("🛑 Kill switch engaged (STOP_TRADING file present) -- no new trades will open.")
    else:
        st.success("✅ Kill switch not engaged -- trading is active.")

    _, dd, opened_today = load_bankroll_status()

    rcol1, rcol2 = st.columns(2)
    rcol1.metric("Current Drawdown", f"{dd:.1f}%", f"limit: {MAX_DRAWDOWN_PCT}%")
    rcol2.metric("Trades Opened Today", opened_today, f"limit: {MAX_DAILY_TRADES}")

    st.caption("Category exposure (% of currently-open stake):")
    exposures = load_category_exposures()
    for category, exposure in exposures.items():
        st.progress(
            min(exposure / MAX_CATEGORY_EXPOSURE_PCT, 1.0),
            text=f"{category}: {exposure:.1f}% (cap {MAX_CATEGORY_EXPOSURE_PCT}%)",
        )
    st.caption("Correlated group exposure (positions likely to move together):")
    correlation_exposures = load_correlation_exposures()
    if not correlation_exposures:
        st.caption("No open positions to group.")
    else:
        for group, exposure in correlation_exposures.items():
            st.progress(
                min(exposure / MAX_CORRELATED_GROUP_EXPOSURE_PCT, 1.0),
                text=f"{group}: {exposure:.1f}% (cap {MAX_CORRELATED_GROUP_EXPOSURE_PCT}%)",
            )